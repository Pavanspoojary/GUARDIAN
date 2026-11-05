"""Deterministic temporal operators for evaluating behavioural patterns and durations."""

from __future__ import annotations

from typing import List, Optional
from sentinel.activity.state_machine import ActivityState, TransitionTrigger, PersonStateMachine


def check_duration_in_state(
    state_machine: PersonStateMachine,
    required_state: ActivityState,
    min_seconds: float,
    max_seconds: Optional[float] = None,
) -> bool:
    """Verify that person has continuously occupied required_state for specified duration."""
    if state_machine.current_state != required_state:
        return False
    dur = state_machine.current_duration_seconds
    if dur < min_seconds:
        return False
    if max_seconds is not None and dur > max_seconds:
        return False
    return True


def check_prolonged_motionlessness(
    state_machine: PersonStateMachine,
    min_seconds: float,
) -> bool:
    """Verify that person has remained motionless (movement intensity below stillness threshold) for at least min_seconds."""
    return state_machine.motionless_duration_seconds >= min_seconds


def check_sequence_match(
    state_machine: PersonStateMachine,
    expected_sequence: List[str],
) -> bool:
    """Check if person's recent activity state sequence ends with the given states."""
    expected_enums = [ActivityState(s) for s in expected_sequence]
    return state_machine.matches_sequence(expected_enums)


def check_absence_of_recovery(
    state_machine: PersonStateMachine,
    window_seconds: float,
) -> bool:
    """Verify that no recovery movement has occurred in the past window_seconds."""
    elapsed = state_machine.get_time_since_last_recovery()
    if elapsed is None:
        return True  # No recovery ever occurred
    return elapsed >= window_seconds


def check_time_window(
    current_hour: int,
    start_hour: int,
    end_hour: int,
) -> bool:
    """Check if current 24-hour hour falls inside [start_hour, end_hour].

    Correctly handles midnight wrap-around (e.g. 22:00 to 06:00).
    """
    if start_hour <= end_hour:
        return start_hour <= current_hour < end_hour
    else:
        # Wraps over midnight (e.g. 22 to 6)
        return current_hour >= start_hour or current_hour < end_hour
