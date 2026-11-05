"""FastAPI web and WebSocket application for SENTINEL."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pydantic import BaseModel, Field

from sentinel.perception.pose_estimator import SyntheticPoseEstimator, MediaPipePoseEstimator
from sentinel.system import SentinelEngine
from sentinel.engine.context_engine import ZoneDefinition, ZoneType


from contextlib import asynccontextmanager

# Shared global engine instance
engine: Optional[SentinelEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    try:
        pose_estimator = MediaPipePoseEstimator()
    except Exception:
        pose_estimator = SyntheticPoseEstimator()

    engine = SentinelEngine(
        pose_estimator=pose_estimator,
        db_url="sqlite:///sentinel.db",
        rules_directory="configs/rules",
    )
    yield
    if engine:
        engine.close()


app = FastAPI(
    title="SENTINEL Decision Engine API",
    description="Deterministic Human Behaviour & Safety Decision Engine for Care Monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount React dashboard build if available
dashboard_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "dashboard", "dist")
if os.path.exists(dashboard_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(dashboard_dist, "assets")), name="assets")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(os.path.join(dashboard_dist, "index.html"))
class AcknowledgeRequest(BaseModel):
    operator: str = Field(..., min_length=1)
    notes: str = ""


class ResolveRequest(BaseModel):
    operator: str = Field(..., min_length=1)
    notes: str = ""


class ZoneCreateRequest(BaseModel):
    name: str
    zone_type: ZoneType
    bounds: List[float] = Field(..., min_length=4, max_length=4)  # [ymin, xmin, ymax, xmax]
    description: str = ""


class SimulateObservationRequest(BaseModel):
    person_id: str
    activity: str
    torso_angle: float
    relative_body_height: float
    vertical_velocity: float
    vertical_acceleration: float = 0.0
    movement_velocity: float = 0.0
    motion_intensity: float = 0.05
    floor_proximity: float = 0.5
    zone_name: Optional[str] = None
    confidence: float = 1.0
    timestamp: Optional[float] = None
    current_hour: Optional[int] = None


@app.get("/api/health")
def get_health():
    """Health check endpoint."""
    return {
        "status": "HEALTHY",
        "system": "SENTINEL Deterministic Safety Engine",
        "mode": "OFFLINE_DETERMINISTIC",
        "rules_count": len(engine.rule_engine.rules) if engine else 0,
        "camera_status": engine.camera_status if engine else "OFFLINE",
        "total_frames_processed": engine.total_frames_processed if engine else 0,
    }


@app.get("/api/incidents")
def list_incidents(
    person_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    """Retrieve safety incidents list."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    records = engine.event_manager.incident_repo.list_incidents(
        person_id=person_id,
        status=status,
        limit=limit,
    )
    return [
        {
            "incident_id": r.incident_id,
            "person_id": r.person_id,
            "incident_type": r.incident_type,
            "risk_level": r.risk_level,
            "risk_score": r.risk_score,
            "status": r.status,
            "started_at": r.started_at,
            "updated_at": r.updated_at,
            "narrative": r.narrative,
            "recommended_action": r.recommended_action,
            "acknowledged_by": r.acknowledged_by,
            "acknowledged_at": r.acknowledged_at,
            "resolved_at": r.resolved_at,
        }
        for r in records
    ]


@app.get("/api/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    """Fetch complete detail, evidence chain, and rejected hypotheses for an incident."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    record = engine.event_manager.incident_repo.get_by_id(incident_id)
    if not record:
        raise HTTPException(status_code=404, detail="Incident not found")

    evidence = {}
    try:
        evidence = json.loads(record.evidence_json)
    except Exception:
        pass

    return {
        "incident_id": record.incident_id,
        "person_id": record.person_id,
        "incident_type": record.incident_type,
        "risk_level": record.risk_level,
        "risk_score": record.risk_score,
        "status": record.status,
        "started_at": record.started_at,
        "updated_at": record.updated_at,
        "narrative": record.narrative,
        "evidence": evidence,
        "recommended_action": record.recommended_action,
        "acknowledged_by": record.acknowledged_by,
        "acknowledged_at": record.acknowledged_at,
        "resolved_at": record.resolved_at,
        "resolution_notes": record.resolution_notes,
    }


@app.post("/api/incidents/{incident_id}/acknowledge")
def acknowledge_incident(incident_id: str, req: AcknowledgeRequest):
    """Caregiver acknowledges active incident."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    result = engine.event_manager.acknowledge(
        incident_id=incident_id,
        operator_name=req.operator,
        notes=req.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@app.post("/api/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str, req: ResolveRequest):
    """Caregiver or operator marks incident as resolved."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    result = engine.event_manager.resolve(
        incident_id=incident_id,
        operator_name=req.operator,
        notes=req.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@app.get("/api/rules")
def list_rules():
    """List configured deterministic safety policies."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "enabled": r.enabled,
            "priority": r.priority,
            "risk_level": r.risk_level.value,
            "base_risk_score": r.base_risk_score,
            "cooldown_seconds": r.cooldown_seconds,
            "suppresses": r.suppresses,
            "depends_on": r.depends_on,
            "recommended_action": r.recommended_action,
        }
        for r in sorted(engine.rule_engine.rules.values(), key=lambda x: x.priority, reverse=True)
    ]


@app.post("/api/rules/{rule_id}/toggle")
def toggle_rule(rule_id: str):
    """Enable or disable a safety rule."""
    if not engine or rule_id not in engine.rule_engine.rules:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule = engine.rule_engine.rules[rule_id]
    rule.enabled = not rule.enabled
    return {"rule_id": rule_id, "enabled": rule.enabled}


@app.get("/api/zones")
def list_zones():
    """List spatial safe/restricted zones."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    return [
        {
            "name": z.name,
            "zone_type": z.zone_type.value,
            "bounds": list(z.bounds),
            "description": z.description,
        }
        for z in engine.calibration.zones.values()
    ]


@app.post("/api/zones")
def create_zone(req: ZoneCreateRequest):
    """Add a new calibrated zone."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    zone = ZoneDefinition(
        name=req.name,
        zone_type=req.zone_type,
        bounds=(req.bounds[0], req.bounds[1], req.bounds[2], req.bounds[3]),
        description=req.description,
    )
    engine.calibration.add_zone(zone)
    return {"name": zone.name, "zone_type": zone.zone_type.value, "bounds": zone.bounds}


@app.get("/api/audit-logs")
def list_audit_logs(limit: int = 50):
    """Audit log trail."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    logs = engine.event_manager.audit_repo.list_logs(limit=limit)
    return [
        {
            "id": l.id,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "action": l.action,
            "actor": l.actor,
            "timestamp": l.timestamp,
            "details": json.loads(l.details_json),
        }
        for l in logs
    ]


@app.post("/api/simulate-observation")
def simulate_observation(req: SimulateObservationRequest):
    """Feed a simulated observation directly into the deterministic decision engine."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")
    from sentinel.activity.state_machine import ActivityState, MovementObservation
    from sentinel.engine.condition_registry import EvaluationContext

    now = req.timestamp or time.time()
    current_hour = req.current_hour if req.current_hour is not None else time.localtime(now).tm_hour

    sm = engine.get_or_create_state_machine(req.person_id, now)

    act_enum = ActivityState(req.activity)
    obs = MovementObservation(
        timestamp=now,
        activity=act_enum,
        torso_angle=req.torso_angle,
        relative_body_height=req.relative_body_height,
        vertical_velocity=req.vertical_velocity,
        vertical_acceleration=req.vertical_acceleration,
        movement_velocity=req.movement_velocity,
        motion_intensity=req.motion_intensity,
        floor_proximity=req.floor_proximity,
        in_zone=req.zone_name,
        confidence=req.confidence,
    )

    sm.update(obs)

    ctx = EvaluationContext(
        person_state_machine=sm,
        current_observation=obs,
        room_type=engine.calibration.room_type,
        current_hour=current_hour,
        zone_name=req.zone_name,
    )

    events = engine.rule_engine.evaluate(sm, obs, ctx=ctx)
    created_incidents = []
    for ev in events:
        inc = engine.event_manager.ingest_event(ev)
        created_incidents.append({
            "incident_id": inc.incident_id,
            "incident_type": inc.incident_type,
            "risk_level": inc.risk_level,
            "risk_score": inc.risk_score,
            "narrative": inc.narrative,
            "explanation": ev.get("explanation"),
        })

    return {
        "person_id": req.person_id,
        "current_activity": sm.current_state.value,
        "duration_seconds": sm.current_duration_seconds,
        "motionless_duration_seconds": sm.motionless_duration_seconds,
        "failed_standing_attempts": sm.failed_standing_attempts_count,
        "triggered_events_count": len(events),
        "incidents": created_incidents,
    }


@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """WebSocket stream transmitting telemetry frames and incidents in real time."""
    await websocket.accept()
    try:
        while True:
            # Send latest engine telemetry every 500ms
            if engine:
                incidents = engine.event_manager.incident_repo.list_incidents(limit=5)
                active_incidents_data = [
                    {
                        "incident_id": inc.incident_id,
                        "person_id": inc.person_id,
                        "incident_type": inc.incident_type,
                        "risk_level": inc.risk_level,
                        "risk_score": inc.risk_score,
                        "status": inc.status,
                        "updated_at": inc.updated_at,
                        "narrative": inc.narrative,
                        "recommended_action": inc.recommended_action,
                    }
                    for inc in incidents if inc.status != "RESOLVED"
                ]

                # Telemetry of active tracked persons
                active_people = []
                for pid, sm in engine.person_state_machines.items():
                    active_people.append({
                        "person_id": pid,
                        "activity": sm.current_state.value,
                        "duration_seconds": round(sm.current_duration_seconds, 1),
                        "motionless_duration": round(sm.motionless_duration_seconds, 1),
                        "failed_attempts": sm.failed_standing_attempts_count,
                    })

                payload = {
                    "timestamp": time.time(),
                    "camera_status": engine.camera_status,
                    "frames_processed": engine.total_frames_processed,
                    "active_people": active_people,
                    "active_incidents": active_incidents_data,
                }
                await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
