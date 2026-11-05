"""Event correlation subsystem unifying related observations into cohesive incidents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


@dataclass
class CorrelatedIncident:
    """Higher-order unified safety incident formed from related atomic events."""
    incident_id: str
    person_id: str
    incident_type: str
    risk_level: str
    risk_score: float
    started_at: float
    updated_at: float
    primary_event: Dict[str, Any]
    contributing_events: List[Dict[str, Any]] = field(default_factory=list)
    narrative: str = ""
    status: str = "DETECTED"  # DETECTED -> UNDER_REVIEW -> ACKNOWLEDGED -> RESOLVED


class EventCorrelator:
    """Aggregates and correlates atomic safety events into consolidated incidents."""

    def __init__(self, correlation_window_seconds: float = 60.0) -> None:
        self.correlation_window_seconds = correlation_window_seconds
        self.active_incidents: Dict[str, CorrelatedIncident] = {}
        self._next_incident_num = 1

    def correlate(self, event: Dict[str, Any]) -> CorrelatedIncident:
        """Evaluate whether event belongs to an existing ongoing incident or forms a new one."""
        person_id = event["person_id"]
        event_time = event["timestamp"]
        event_type = event["event_type"]

        # Check for existing open incident for this person within correlation window
        if person_id in self.active_incidents:
            incident = self.active_incidents[person_id]
            time_gap = event_time - incident.updated_at

            if time_gap <= self.correlation_window_seconds:
                # Merge into existing incident
                incident.updated_at = event_time
                incident.contributing_events.append(event)

                # Escalate risk if incoming event has higher risk score
                if event["risk_score"] > incident.risk_score:
                    incident.risk_score = event["risk_score"]
                    incident.risk_level = event["risk_level"]

                # Enhance narrative
                incident.narrative += (
                    f" Escalated by subsequent event '{event_type}' at t+{time_gap:.1f}s."
                )
                return incident

        # Otherwise create a new correlated incident
        inc_id = f"inc_{self._next_incident_num:04d}"
        self._next_incident_num += 1

        narrative = (
            f"Incident initiated by {event.get('rule_name', event_type)} "
            f"for {person_id} with severity {event['risk_level']}."
        )

        incident = CorrelatedIncident(
            incident_id=inc_id,
            person_id=person_id,
            incident_type=event_type,
            risk_level=event["risk_level"],
            risk_score=event["risk_score"],
            started_at=event_time,
            updated_at=event_time,
            primary_event=event,
            contributing_events=[event],
            narrative=narrative,
            status="DETECTED",
        )
        self.active_incidents[person_id] = incident
        return incident

    def resolve_incident(self, person_id: str) -> Optional[CorrelatedIncident]:
        """Mark person's active incident resolved and remove from active map."""
        if person_id in self.active_incidents:
            inc = self.active_incidents.pop(person_id)
            inc.status = "RESOLVED"
            return inc
        return None
