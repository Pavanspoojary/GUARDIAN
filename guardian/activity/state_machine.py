"""Deterministic temporal state machine and activity tracking for tracked persons."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class ActivityState(str, Enum):
    """Core recognized physical human activities."""
    STANDING = "STANDING"
    WALKING = "WALKING"
    SITTING = "SITTING"
    LYING = "LYING"
    LYING_ON_FLOOR = "LYING_ON_FLOOR"
    TRANSITIONING = "TRANSITIONING"
    UNKNOWN = "UNKNOWN"


class TransitionTrigger(str, Enum):
    """Deterministic transition events observed during physical movement."""
    NORMAL_POSTURE_CHANGE = "NORMAL_POSTURE_CHANGE"
    SUDDEN_DESCENT = "SUDDEN_DESCENT"
    FLOOR_CONTACT = "FLOOR_CONTACT"
    BED_CONTACT = "BED_CONTACT"
    SOFA_CONTACT = "SOFA_CONTACT"
    PROLONGED_INACTIVITY = "PROLONGED_INACTIVITY"
    RECOVERY_MOVEMENT = "RECOVERY_MOVEMENT"
    FAILED_ASCENT_ATTEMPT = "FAILED_ASCENT_ATTEMPT"
    LOST_TRACKING = "LOST_TRACKING"


@dataclass
class ActivityStateRecord:
    """Record of a historical activity state slice."""
    state: ActivityState
    entered_at: float
    exited_at: Optional[float] = None
    duration_seconds: float = 0.0
    transition_trigger: Optional[TransitionTrigger] = None
    average_motion_intensity: float = 0.0
    average_torso_angle: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MovementObservation:
    """Kinematic observation slice for a person at a discrete timestamp."""
    timestamp: float
    activity: ActivityState
    torso_angle: float  # 0 deg = vertical standing/sitting upright, 90 deg = horizontal lying
    relative_body_height: float  # Normalized height [0.0 - 1.0] relative to upright height
    vertical_velocity: float  # Normalized vertical change per second (positive = downward)
    vertical_acceleration: float
    movement_velocity: float  # Normalized 2D horizontal speed
    motion_intensity: float  # Joint displacement kinetic metric [0.0 - 1.0]
    floor_proximity: float  # Distance to calibrated floor level [0.0 = on floor, 1.0 = top of frame]
    in_zone: Optional[str] = None  # e.g. "BED", "SOFA", "FLOOR", "SAFE", "RESTRICTED"
    confidence: float = 1.0
    knee_angle: float = 180.0
    head_y: float = 0.35
    shoulder_y: float = 0.45
    has_legs_visible: bool = True


class PersonStateMachine:
    """Per-person deterministic state machine maintaining sequence and duration history."""

    def __init__(
        self,
        person_id: str,
        initial_timestamp: Optional[float] = None,
        max_history_records: int = 100,
        recent_observations_window_seconds: float = 30.0,
    ) -> None:
        self.person_id = person_id
        t0 = initial_timestamp if initial_timestamp is not None else time.time()
        self.current_state = ActivityState.UNKNOWN
        self.state_entered_at = t0
        self.last_observation_time = t0

        self.history: List[ActivityStateRecord] = []
        self.max_history_records = max_history_records
        self.recent_observations_window_seconds = recent_observations_window_seconds

        # Circular buffer of raw recent observations
        self.recent_observations: List[MovementObservation] = []

        # Sequence of state transitions (recent states in order)
        self.state_sequence: List[ActivityState] = []
        self.trigger_sequence: List[TransitionTrigger] = []

        # Motionless duration tracking
        self.motionless_duration_seconds: float = 0.0
        self.last_significant_motion_time: float = t0

        # Descent tracking
        self.last_sudden_descent_time: Optional[float] = None
        self.peak_descent_velocity: float = 0.0

        # Repeated attempt tracking (e.g. failed standing)
        self.failed_standing_attempts_count: int = 0
        self.last_failed_attempt_time: Optional[float] = None

    @property
    def current_duration_seconds(self) -> float:
        """Current continuous duration spent in the active state."""
        return max(0.0, self.last_observation_time - self.state_entered_at)

    def update(self, obs: MovementObservation) -> Optional[ActivityStateRecord]:
        """Update state machine with a new observation.

        Returns an ActivityStateRecord if a state transition occurred, else None.
        """
        self.last_observation_time = obs.timestamp

        # Add to recent observations and prune outside window
        self.recent_observations.append(obs)
        cutoff = obs.timestamp - self.recent_observations_window_seconds
        self.recent_observations = [o for o in self.recent_observations if o.timestamp >= cutoff]

        # Track motion intensity and stillness
        if obs.motion_intensity >= 0.08:
            self.last_significant_motion_time = obs.timestamp
            self.motionless_duration_seconds = 0.0
        else:
            self.motionless_duration_seconds = max(0.0, obs.timestamp - self.last_significant_motion_time)

        # Track sudden descent velocity
        if obs.vertical_velocity > 0.8:
            self.last_sudden_descent_time = obs.timestamp
            self.peak_descent_velocity = max(self.peak_descent_velocity, obs.vertical_velocity)

        # Detect transition
        if obs.activity != self.current_state:
            transition_record = self._handle_state_transition(obs)
            return transition_record

        return None

    def _determine_trigger(self, new_state: ActivityState, obs: MovementObservation) -> TransitionTrigger:
        """Determine deterministic transition trigger cause based on kinematics and context."""
        now = obs.timestamp
        had_sudden_descent = (
            self.last_sudden_descent_time is not None
            and (now - self.last_sudden_descent_time) <= 3.0
        )

        if new_state == ActivityState.LYING_ON_FLOOR:
            if had_sudden_descent or obs.vertical_velocity > 0.7:
                return TransitionTrigger.SUDDEN_DESCENT
            return TransitionTrigger.FLOOR_CONTACT

        if new_state == ActivityState.LYING:
            if obs.in_zone == "BED":
                return TransitionTrigger.BED_CONTACT
            if obs.in_zone == "SOFA":
                return TransitionTrigger.SOFA_CONTACT
            if had_sudden_descent:
                return TransitionTrigger.SUDDEN_DESCENT
            return TransitionTrigger.NORMAL_POSTURE_CHANGE

        if new_state == ActivityState.SITTING and self.current_state in (ActivityState.LYING_ON_FLOOR, ActivityState.LYING):
            return TransitionTrigger.RECOVERY_MOVEMENT

        if new_state == ActivityState.STANDING and self.current_state in (ActivityState.LYING_ON_FLOOR, ActivityState.SITTING):
            # Check if this was a successful recovery or return
            return TransitionTrigger.RECOVERY_MOVEMENT

        if self.current_state == ActivityState.SITTING and new_state == ActivityState.TRANSITIONING:
            # Check subsequent return to SITTING without reaching STANDING (detected in activity analyzer)
            pass

        return TransitionTrigger.NORMAL_POSTURE_CHANGE

    def _handle_state_transition(self, obs: MovementObservation) -> ActivityStateRecord:
        """Execute state transition and record history."""
        old_state = self.current_state
        new_state = obs.activity
        now = obs.timestamp

        trigger = self._determine_trigger(new_state, obs)

        # Compute summary metrics for completed state
        duration = max(0.0, now - self.state_entered_at)
        completed_obs = [o for o in self.recent_observations if o.timestamp < now and o.activity == old_state]
        avg_motion = sum(o.motion_intensity for o in completed_obs) / len(completed_obs) if completed_obs else 0.0
        avg_torso = sum(o.torso_angle for o in completed_obs) / len(completed_obs) if completed_obs else 0.0

        completed_record = ActivityStateRecord(
            state=old_state,
            entered_at=self.state_entered_at,
            exited_at=now,
            duration_seconds=duration,
            transition_trigger=trigger,
            average_motion_intensity=avg_motion,
            average_torso_angle=avg_torso,
        )

        self.history.append(completed_record)
        if len(self.history) > self.max_history_records:
            self.history.pop(0)

        # Update sequences
        self.state_sequence.append(new_state)
        if len(self.state_sequence) > 20:
            self.state_sequence.pop(0)

        self.trigger_sequence.append(trigger)
        if len(self.trigger_sequence) > 20:
            self.trigger_sequence.pop(0)

        # Track failed standing attempts: SITTING -> TRANSITIONING -> SITTING within brief window
        if old_state == ActivityState.TRANSITIONING and new_state == ActivityState.SITTING:
            # Check if state before transitioning was SITTING
            if len(self.history) >= 2 and self.history[-2].state == ActivityState.SITTING:
                if completed_record.duration_seconds < 8.0:
                    self.failed_standing_attempts_count += 1
                    self.last_failed_attempt_time = now

        # Reset state timer
        self.current_state = new_state
        self.state_entered_at = now

        # If transition to normal upright state, reset sudden descent tracker
        if new_state in (ActivityState.STANDING, ActivityState.WALKING):
            self.peak_descent_velocity = 0.0
            self.last_sudden_descent_time = None

        return completed_record

    def matches_sequence(self, expected_sequence: List[ActivityState], max_gap_seconds: float = 30.0) -> bool:
        """Check if the person's recent state sequence ends with the given sequence.

        Supports matching sub-sequences within chronological tolerances.
        """
        if not expected_sequence:
            return True

        if len(self.state_sequence) < len(expected_sequence):
            return False

        # Compare tails
        tail = self.state_sequence[-len(expected_sequence):]
        return tail == expected_sequence

    def get_time_since_last_recovery(self) -> Optional[float]:
        """Return seconds elapsed since last recovery trigger, or None if no recovery seen."""
        for rec in reversed(self.history):
            if rec.transition_trigger == TransitionTrigger.RECOVERY_MOVEMENT:
                return max(0.0, self.last_observation_time - (rec.exited_at or rec.entered_at))
        return None

    def reset_failed_attempts(self) -> None:
        """Reset failed attempt counter upon sustained standing or manual reset."""
        self.failed_standing_attempts_count = 0
        self.last_failed_attempt_time = None
