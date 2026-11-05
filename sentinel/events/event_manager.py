"""Event and Incident Lifecycle Manager with deterministic escalation and audit logging."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from sentinel.intelligence.event_correlator import EventCorrelator, CorrelatedIncident
from sentinel.storage.repositories import IncidentRepository, AuditRepository


class EventManager:
    """Manages the lifecycle of safety events, alerts, and caregiver interactions."""

    def __init__(
        self,
        db_session: Session,
        escalation_timeout_seconds: float = 60.0,
    ) -> None:
        self.session = db_session
        self.incident_repo = IncidentRepository(db_session)
        self.audit_repo = AuditRepository(db_session)
        self.correlator = EventCorrelator(correlation_window_seconds=60.0)
        self.escalation_timeout_seconds = escalation_timeout_seconds

    def ingest_event(self, raw_event: Dict[str, Any]) -> CorrelatedIncident:
        """Ingest atomic safety event, correlate with open incidents, and persist."""
        incident = self.correlator.correlate(raw_event)

        # Persist to database
        self.incident_repo.save_incident(
            incident_id=incident.incident_id,
            person_id=incident.person_id,
            incident_type=incident.incident_type,
            risk_level=incident.risk_level,
            risk_score=incident.risk_score,
            started_at=incident.started_at,
            updated_at=incident.updated_at,
            narrative=incident.narrative,
            evidence={
                "primary_event": incident.primary_event,
                "contributing_count": len(incident.contributing_events),
                "contributing_types": [e["event_type"] for e in incident.contributing_events],
            },
            recommended_action=raw_event.get("recommended_action", "Caregiver verification requested."),
            status=incident.status,
        )

        # Audit log creation/update
        self.audit_repo.log_action(
            entity_type="INCIDENT",
            entity_id=incident.incident_id,
            action="INCIDENT_UPDATED" if len(incident.contributing_events) > 1 else "INCIDENT_DETECTED",
            actor="DECISION_ENGINE",
            details={
                "risk_level": incident.risk_level,
                "risk_score": incident.risk_score,
                "event_type": raw_event["event_type"],
            },
        )

        return incident

    def check_escalations(self, current_time: Optional[float] = None) -> List[Dict[str, Any]]:
        """Identify unacknowledged URGENT incidents exceeding timeout and trigger escalation."""
        now = current_time if current_time is not None else time.time()
        escalated: List[Dict[str, Any]] = []

        active_incidents = self.incident_repo.list_incidents(status="DETECTED", limit=50)
        for inc in active_incidents:
            if inc.risk_level == "URGENT":
                elapsed = now - inc.updated_at
                if elapsed >= self.escalation_timeout_seconds:
                    escalation_alert = {
                        "incident_id": inc.incident_id,
                        "person_id": inc.person_id,
                        "escalation_level": "TIER_2_SUPERVISOR_ALERT",
                        "elapsed_seconds": round(elapsed, 1),
                        "message": (
                            f"CRITICAL: Incident {inc.incident_id} for {inc.person_id} "
                            f"unacknowledged after {elapsed:.0f}s. Immediate supervisor intervention required."
                        ),
                    }
                    escalated.append(escalation_alert)

                    # Log escalation to audit trail
                    self.audit_repo.log_action(
                        entity_type="INCIDENT",
                        entity_id=inc.incident_id,
                        action="ESCALATION_DISPATCHED",
                        actor="SYSTEM_ESCALATION_MONITOR",
                        details=escalation_alert,
                    )
        return escalated

    def acknowledge(self, incident_id: str, operator_name: str, notes: str = "") -> Optional[Dict[str, Any]]:
        """Caregiver acknowledges the incident."""
        entity = self.incident_repo.acknowledge_incident(incident_id, operator_name, notes)
        if entity:
            self.audit_repo.log_action(
                entity_type="INCIDENT",
                entity_id=incident_id,
                action="ACKNOWLEDGED",
                actor=operator_name,
                details={"notes": notes},
            )
            return {
                "incident_id": entity.incident_id,
                "status": entity.status,
                "acknowledged_by": entity.acknowledged_by,
                "acknowledged_at": entity.acknowledged_at,
            }
        return None

    def resolve(self, incident_id: str, operator_name: str, notes: str = "") -> Optional[Dict[str, Any]]:
        """Caregiver or system resolves the incident."""
        entity = self.incident_repo.resolve_incident(incident_id, operator_name, notes)
        if entity:
            # Also notify correlator to close open tracking for this person
            self.correlator.resolve_incident(entity.person_id)
            self.audit_repo.log_action(
                entity_type="INCIDENT",
                entity_id=incident_id,
                action="RESOLVED",
                actor=operator_name,
                details={"notes": notes},
            )
            return {
                "incident_id": entity.incident_id,
                "status": entity.status,
                "resolved_at": entity.resolved_at,
                "resolution_notes": entity.resolution_notes,
            }
        return None
