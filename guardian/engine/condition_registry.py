"""Deterministic condition evaluation registry and operators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from guardian.activity.state_machine import ActivityState, PersonStateMachine, MovementObservation


class ComparisonOperator(str, Enum):
    """Supported deterministic comparison operators."""
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"


@dataclass
class EvidenceItem:
    """Individual piece of deterministic evidence supporting a decision."""
    metric_name: str
    expected_condition: str
    observed_value: Any
    satisfied: bool
    weight: float = 1.0
    description: str = ""


class EvaluationContext:
    """Consolidated runtime state passed to rule evaluation."""

    def __init__(
        self,
        person_state_machine: PersonStateMachine,
        current_observation: MovementObservation,
        room_type: str = "GENERAL",
        current_hour: int = 12,
        zone_name: Optional[str] = None,
        camera_status: str = "ONLINE",
        camera_obstruction_score: float = 0.0,
        historical_stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.sm = person_state_machine
        self.obs = current_observation
        self.room_type = room_type
        self.current_hour = current_hour
        self.zone_name = zone_name or current_observation.in_zone
        self.camera_status = camera_status
        self.camera_obstruction_score = camera_obstruction_score
        self.historical_stats = historical_stats or {}

    def get_value(self, metric: str) -> Any:
        """Resolve metric key dynamically from evaluation context."""
        metric_map: Dict[str, Any] = {
            # State metrics
            "activity_state": self.sm.current_state.value,
            "previous_state": self.sm.history[-1].state.value if self.sm.history else "UNKNOWN",
            "duration_seconds": self.sm.current_duration_seconds,
            "motionless_duration_seconds": self.sm.motionless_duration_seconds,
            "failed_standing_attempts": self.sm.failed_standing_attempts_count,
            "recent_state_sequence": [s.value for s in self.sm.state_sequence],
            "recent_trigger_sequence": [t.value for t in self.sm.trigger_sequence],
            # Kinematic metrics
            "torso_angle": self.obs.torso_angle,
            "relative_body_height": self.obs.relative_body_height,
            "vertical_velocity": self.obs.vertical_velocity,
            "vertical_acceleration": self.obs.vertical_acceleration,
            "movement_velocity": self.obs.movement_velocity,
            "motion_intensity": self.obs.motion_intensity,
            "floor_proximity": self.obs.floor_proximity,
            "observation_confidence": self.obs.confidence,
            "peak_descent_velocity": self.sm.peak_descent_velocity,
            "seconds_since_sudden_descent": (
                (self.obs.timestamp - self.sm.last_sudden_descent_time)
                if self.sm.last_sudden_descent_time is not None
                else 999999.0
            ),
            # Context metrics
            "zone_name": self.zone_name,
            "room_type": self.room_type,
            "current_hour": self.current_hour,
            "camera_status": self.camera_status,
            "camera_obstruction_score": self.camera_obstruction_score,
        }

        # Also support querying historical statistics if present
        if metric in metric_map:
            return metric_map[metric]
        if metric in self.historical_stats:
            return self.historical_stats[metric]

        return None


def evaluate_comparison(
    op: ComparisonOperator,
    actual: Any,
    expected: Any,
) -> bool:
    """Execute deterministic comparison."""
    if actual is None:
        return False

    if op == ComparisonOperator.EQ:
        return actual == expected
    elif op == ComparisonOperator.NEQ:
        return actual != expected
    elif op == ComparisonOperator.GT:
        return float(actual) > float(expected)
    elif op == ComparisonOperator.GTE:
        return float(actual) >= float(expected)
    elif op == ComparisonOperator.LT:
        return float(actual) < float(expected)
    elif op == ComparisonOperator.LTE:
        return float(actual) <= float(expected)
    elif op == ComparisonOperator.IN:
        return actual in expected
    elif op == ComparisonOperator.NOT_IN:
        return actual not in expected
    elif op == ComparisonOperator.BETWEEN:
        low, high = expected
        return float(low) <= float(actual) <= float(high)

    return False
