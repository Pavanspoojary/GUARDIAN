"""Repository pattern implementations for database interactions."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from sentinel.storage.database import (
    IncidentEntity,
    PersonProfileEntity,
    AuditLogEntity,
)


class IncidentRepository:
    """Manages persistence and retrieval of safety incidents."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_incident(
        self,
        incident_id: str,
        person_id: str,
        incident_type: str,
        risk_level: str,
        risk_score: float,
        started_at: float,
        updated_at: float,
        narrative: str,
        evidence: Dict[str, Any],
        recommended_action: str,
        status: str = "DETECTED",
    ) -> IncidentEntity:
        """Create or update an incident."""
        entity = self.session.query(IncidentEntity).filter_by(incident_id=incident_id).first()
        if not entity:
            entity = IncidentEntity(
                incident_id=incident_id,
                person_id=person_id,
                incident_type=incident_type,
                risk_level=risk_level,
                risk_score=risk_score,
                status=status,
                started_at=started_at,
                updated_at=updated_at,
                narrative=narrative,
                evidence_json=json.dumps(evidence),
                recommended_action=recommended_action,
            )
            self.session.add(entity)
        else:
            entity.updated_at = updated_at
            entity.risk_level = risk_level
            entity.risk_score = risk_score
            entity.narrative = narrative
            entity.evidence_json = json.dumps(evidence)

        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_id(self, incident_id: str) -> Optional[IncidentEntity]:
        """Fetch incident by unique identifier."""
        return self.session.query(IncidentEntity).filter_by(incident_id=incident_id).first()

    def list_incidents(
        self,
        person_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[IncidentEntity]:
        """Query incidents with optional filters."""
        q = self.session.query(IncidentEntity)
        if person_id:
            q = q.filter_by(person_id=person_id)
        if status:
            q = q.filter_by(status=status)
        return q.order_by(IncidentEntity.updated_at.desc()).limit(limit).all()

    def acknowledge_incident(
        self,
        incident_id: str,
        actor: str,
        notes: str = "",
    ) -> Optional[IncidentEntity]:
        """Transition incident to ACKNOWLEDGED state."""
        entity = self.get_by_id(incident_id)
        if not entity:
            return None
        entity.status = "ACKNOWLEDGED"
        entity.acknowledged_by = actor
        entity.acknowledged_at = time.time()
        if notes:
            entity.narrative += f" [Ack Note: {notes}]"
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def resolve_incident(
        self,
        incident_id: str,
        actor: str,
        notes: str = "",
    ) -> Optional[IncidentEntity]:
        """Transition incident to RESOLVED state."""
        entity = self.get_by_id(incident_id)
        if not entity:
            return None
        entity.status = "RESOLVED"
        entity.resolved_at = time.time()
        entity.resolution_notes = f"Resolved by {actor}. {notes}".strip()
        self.session.commit()
        self.session.refresh(entity)
        return entity


class AuditRepository:
    """Manages system audit trail."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def log_action(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str = "SYSTEM",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntity:
        """Record an immutable audit entry."""
        entry = AuditLogEntity(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            timestamp=time.time(),
            details_json=json.dumps(details or {}),
        )
        self.session.add(entry)
        self.session.commit()
        return entry

    def list_logs(self, limit: int = 100) -> List[AuditLogEntity]:
        """Fetch latest audit logs."""
        return self.session.query(AuditLogEntity).order_by(AuditLogEntity.timestamp.desc()).limit(limit).all()
