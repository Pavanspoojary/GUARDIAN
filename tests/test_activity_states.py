"""Tests verifying the deterministic activity state machine."""

import pytest
from guardian.activity.state_machine import (
    ActivityState,
    PersonStateMachine,
    MovementObservation,
    TransitionTrigger,
)


def test_state_transitions_and_duration():
    """Verify state transitions and accurate continuous duration tracking."""
    sm = PersonStateMachine(person_id="p1", initial_timestamp=100.0)

    # Initially standing
    obs1 = MovementObservation(
        timestamp=100.0,
        activity=ActivityState.STANDING,
        torso_angle=5.0,
        relative_body_height=0.95,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.02,
        floor_proximity=0.9,
    )
    sm.update(obs1)
    assert sm.current_state == ActivityState.STANDING
    assert sm.current_duration_seconds == 0.0

    # 10 seconds later still standing
    obs2 = MovementObservation(
        timestamp=110.0,
        activity=ActivityState.STANDING,
        torso_angle=6.0,
        relative_body_height=0.95,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.02,
        floor_proximity=0.9,
    )
    transition = sm.update(obs2)
    assert transition is None
    assert sm.current_duration_seconds == 10.0

    # Transitions to SITTING at t = 112.0
    obs3 = MovementObservation(
        timestamp=112.0,
        activity=ActivityState.SITTING,
        torso_angle=12.0,
        relative_body_height=0.60,
        vertical_velocity=0.2,
        vertical_acceleration=0.05,
        movement_velocity=0.0,
        motion_intensity=0.1,
        floor_proximity=0.5,
    )
    transition = sm.update(obs3)
    assert transition is not None
    assert transition.state == ActivityState.STANDING
    assert transition.duration_seconds == 12.0
    assert sm.current_state == ActivityState.SITTING
    assert sm.current_duration_seconds == 0.0


def test_failed_standing_attempts_detection():
    """Verify that SITTING -> TRANSITIONING -> SITTING increments failed attempt counter."""
    sm = PersonStateMachine(person_id="p2", initial_timestamp=500.0)

    # Initial sitting state
    sm.update(MovementObservation(
        timestamp=500.0,
        activity=ActivityState.SITTING,
        torso_angle=15.0,
        relative_body_height=0.6,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.05,
        floor_proximity=0.5,
    ))

    # Attempt 1: Tries to stand, enters transitioning for 3 seconds, fails back to sitting
    sm.update(MovementObservation(
        timestamp=510.0,
        activity=ActivityState.TRANSITIONING,
        torso_angle=30.0,
        relative_body_height=0.75,
        vertical_velocity=-0.2,
        vertical_acceleration=0.1,
        movement_velocity=0.1,
        motion_intensity=0.3,
        floor_proximity=0.65,
    ))
    sm.update(MovementObservation(
        timestamp=513.0,
        activity=ActivityState.SITTING,
        torso_angle=20.0,
        relative_body_height=0.6,
        vertical_velocity=0.3,
        vertical_acceleration=-0.1,
        movement_velocity=0.05,
        motion_intensity=0.2,
        floor_proximity=0.5,
    ))
    assert sm.failed_standing_attempts_count == 1

    # Attempt 2: Tries again, fails back to sitting
    sm.update(MovementObservation(
        timestamp=520.0,
        activity=ActivityState.TRANSITIONING,
        torso_angle=25.0,
        relative_body_height=0.72,
        vertical_velocity=-0.15,
        vertical_acceleration=0.05,
        movement_velocity=0.1,
        motion_intensity=0.25,
        floor_proximity=0.62,
    ))
    sm.update(MovementObservation(
        timestamp=524.0,
        activity=ActivityState.SITTING,
        torso_angle=18.0,
        relative_body_height=0.6,
        vertical_velocity=0.2,
        vertical_acceleration=-0.05,
        movement_velocity=0.02,
        motion_intensity=0.1,
        floor_proximity=0.5,
    ))
    assert sm.failed_standing_attempts_count == 2
