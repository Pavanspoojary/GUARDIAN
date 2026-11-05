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


def test_desk_webcam_sitting_and_chair_reclining():
    """Verify accurate sitting classification and chair reclining without false falls in desk mode."""
    from guardian.activity.activity_classifier import ActivityClassifier

    classifier = ActivityClassifier()

    # Seated at desk in front of webcam (legs out of frame, upright torso)
    obs_desk = MovementObservation(
        timestamp=100.0,
        activity=ActivityState.UNKNOWN,
        torso_angle=8.0,
        relative_body_height=0.75,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.01,
        motion_intensity=0.02,
        floor_proximity=0.55,
        head_y=0.30,
        shoulder_y=0.45,
        has_legs_visible=False,
    )
    assert classifier.classify_frame(obs_desk) == ActivityState.SITTING

    # Reclining back in office chair (torso at 50 degrees, but head still elevated)
    obs_recline = MovementObservation(
        timestamp=101.0,
        activity=ActivityState.UNKNOWN,
        torso_angle=50.0,
        relative_body_height=0.65,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.02,
        floor_proximity=0.55,
        head_y=0.38,
        shoulder_y=0.50,
        has_legs_visible=False,
    )
    assert classifier.classify_frame(obs_recline) == ActivityState.SITTING

    # True fall / collapse to floor (head drops low)
    obs_collapse = MovementObservation(
        timestamp=102.0,
        activity=ActivityState.UNKNOWN,
        torso_angle=65.0,
        relative_body_height=0.40,
        vertical_velocity=0.8,
        vertical_acceleration=0.2,
        movement_velocity=0.0,
        motion_intensity=0.1,
        floor_proximity=0.15,
        head_y=0.75,
        shoulder_y=0.70,
        has_legs_visible=False,
    )
    assert classifier.classify_frame(obs_collapse) == ActivityState.LYING_ON_FLOOR


def test_anatomical_knee_flexion_distinguishes_sitting_from_standing():
    """Verify knee flexion angle cleanly separates sitting (bent knee) from standing (straight knee)."""
    from guardian.activity.activity_classifier import ActivityClassifier

    classifier = ActivityClassifier()

    # Full body visible: bent knee (sitting on chair)
    obs_chair = MovementObservation(
        timestamp=200.0,
        activity=ActivityState.UNKNOWN,
        torso_angle=12.0,
        relative_body_height=0.68,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.01,
        floor_proximity=0.4,
        knee_angle=95.0,
        has_legs_visible=True,
    )
    assert classifier.classify_frame(obs_chair) == ActivityState.SITTING

    # Full body visible: straight knee (standing upright)
    obs_standing = MovementObservation(
        timestamp=201.0,
        activity=ActivityState.UNKNOWN,
        torso_angle=5.0,
        relative_body_height=0.88,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.02,
        floor_proximity=0.85,
        knee_angle=172.0,
        has_legs_visible=True,
    )
    assert classifier.classify_frame(obs_standing) == ActivityState.STANDING
