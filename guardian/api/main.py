"""FastAPI web and WebSocket application for GUARDIAN."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import base64
import os
import cv2
import numpy as np
from pydantic import BaseModel, Field

from guardian.perception.pose_estimator import SyntheticPoseEstimator, MediaPipePoseEstimator
from guardian.system import GuardianEngine
from guardian.engine.context_engine import ZoneDefinition, ZoneType


from contextlib import asynccontextmanager

# Shared global engine instance
engine: Optional[GuardianEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    try:
        pose_estimator = MediaPipePoseEstimator()
    except Exception:
        pose_estimator = SyntheticPoseEstimator()

    engine = GuardianEngine(
        pose_estimator=pose_estimator,
        db_url="sqlite:///guardian.db",
        rules_directory="configs/rules",
    )
    yield
    if engine:
        engine.close()


app = FastAPI(
    title="GUARDIAN Decision Engine API",
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
        "system": "GUARDIAN Deterministic Safety Engine",
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
    from guardian.activity.state_machine import ActivityState, MovementObservation
    from guardian.engine.condition_registry import EvaluationContext

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


class ProcessLiveFrameRequest(BaseModel):
    image_base64: str
    timestamp: Optional[float] = None
    person_id: Optional[str] = "person_01"


@app.get("/api/sample-video")
@app.head("/api/sample-video")
def get_sample_video():
    """Serves the test video recording for testing and verification."""
    clean_sample = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "sample_surveillance.mp4")
    if os.path.exists(clean_sample):
        return FileResponse(clean_sample, media_type="video/mp4")
    sample_path = "/Users/pavanspoojary/.gemini/antigravity/brain/2115ac10-01e2-423c-a43e-f049b3c4f49a/.user_uploaded/media_1793898016554_d6316989.mp4"
    if os.path.exists(sample_path):
        return FileResponse(sample_path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Sample video not found")


def _format_frame_response(result: Dict[str, Any], now: float) -> Dict[str, Any]:
    """Helper formatting deterministic vision & tracking result into live telemetry."""
    from guardian.activity.state_machine import ActivityState, MovementObservation

    if result["tracks"]:
        track = result["tracks"][0]
        pid = track["person_id"]
        sm = engine.get_or_create_state_machine(pid, now)
        act = ActivityState(track["activity"])

        obs = MovementObservation(
            timestamp=now,
            activity=act,
            torso_angle=track["torso_angle"],
            relative_body_height=track["relative_body_height"],
            vertical_velocity=track.get("vertical_velocity", 0.0),
            vertical_acceleration=0.0,
            movement_velocity=track.get("movement_velocity", 0.0),
            motion_intensity=track["motion_intensity"],
            floor_proximity=track.get("floor_proximity", 0.5),
            confidence=track["confidence"],
            knee_angle=track.get("knee_angle", 180.0),
            head_y=track.get("head_y", 0.35),
            shoulder_y=track.get("shoulder_y", 0.45),
            has_legs_visible=track.get("has_legs_visible", True),
        )

        highest_risk = 0.0
        if result["new_incidents"]:
            highest_risk = max(inc["risk_score"] for inc in result["new_incidents"])

        distribution = engine.activity_classifier.compute_distribution(
            obs=obs,
            active_state=act,
            risk_score=highest_risk,
        )

        narrative = engine.activity_classifier.generate_narrative(
            active_state=act,
            obs=obs,
            duration=sm.current_duration_seconds,
            motionless_duration=sm.motionless_duration_seconds,
            failed_attempts=sm.failed_standing_attempts_count,
        )

        return {
            "status": "SUCCESS",
            "person_id": pid,
            "has_person": True,
            "active_state": act.value,
            "narrative": narrative,
            "distribution": distribution,
            "landmarks": track["landmarks"],
            "bbox": track["bbox"],
            "torso_angle": track["torso_angle"],
            "relative_body_height": track["relative_body_height"],
            "motion_intensity": track["motion_intensity"],
            "motionless_duration": round(sm.motionless_duration_seconds, 1),
            "duration_seconds": round(sm.current_duration_seconds, 1),
            "incidents": result["new_incidents"],
            "frame_number": result["frame_number"],
        }
    else:
        distribution = engine.activity_classifier.compute_distribution(
            obs=None,
            active_state=ActivityState.UNKNOWN,
            risk_score=0.0,
        )
        return {
            "status": "SUCCESS",
            "has_person": False,
            "active_state": "NO_PERSON",
            "narrative": "REVIEWING FOOTAGE... NO HUMAN SUBJECT VISIBLE IN CAMERA FRAME.",
            "distribution": distribution,
            "landmarks": {},
            "bbox": [0, 0, 0, 0],
            "torso_angle": 0.0,
            "relative_body_height": 0.0,
            "motion_intensity": 0.0,
            "motionless_duration": 0.0,
            "duration_seconds": 0.0,
            "incidents": [],
            "frame_number": result["frame_number"],
        }


@app.post("/api/process-live-frame-raw")
async def process_live_frame_raw(request: Request):
    """Ultra-low latency live frame analysis accepting direct binary JPEG payload (zero-copy)."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")

    raw_bytes = await request.body()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty frame body")

    nparr = np.frombuffer(raw_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image payload")

    now = time.time()
    result = engine.process_frame(frame, timestamp=now)
    return _format_frame_response(result, now)


@app.post("/api/process-live-frame")
def process_live_frame(req: ProcessLiveFrameRequest):
    """Processes a live camera video frame from the user's webcam and runs full deterministic analysis."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine uninitialized")

    now = req.timestamp or time.time()
    try:
        b64_data = req.image_base64
        if "," in b64_data:
            _, b64_data = b64_data.split(",", 1)
        raw_bytes = base64.b64decode(b64_data)
        nparr = np.frombuffer(raw_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Failed to decode image frame")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")

    result = engine.process_frame(frame, timestamp=now)
    return _format_frame_response(result, now)


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
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass
