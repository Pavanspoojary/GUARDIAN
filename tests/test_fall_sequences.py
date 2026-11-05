"""Tests verifying deterministic discrimination between falls and normal resting."""

import time
import pytest
from guardian.activity.state_machine import (
    ActivityState,
    PersonStateMachine,
    MovementObservation,
)
from guardian.engine.rule_engine import RuleEngine
from guardian.engine.context_engine import RoomCalibration, ZoneDefinition, ZoneType


@pytest.fixture
def rule_engine():
    engine = RuleEngine()
    engine.load_rules_from_directory("configs/rules")
    return engine


def test_intentional_lying_on_bed_does_not_trigger_fall(rule_engine):
    """Scenario: Person walks into bedroom, sits on bed, lies down to rest.

    GUARDIAN must NOT trigger a fall alert or prolonged floor alert.
    """
    sm = PersonStateMachine(person_id="elder_1", initial_timestamp=1000.0)

    # 1. Walking towards bed
    obs1 = MovementObservation(
        timestamp=1000.0,
        activity=ActivityState.WALKING,
        torso_angle=5.0,
        relative_body_height=0.9,
        vertical_velocity=0.05,
        vertical_acceleration=0.0,
        movement_velocity=0.3,
        motion_intensity=0.4,
        floor_proximity=0.9,
        in_zone=None,
    )
    sm.update(obs1)
    events1 = rule_engine.evaluate(sm, obs1)
    assert len(events1) == 0

    # 2. Sitting on bed (t = 1005s)
    obs2 = MovementObservation(
        timestamp=1005.0,
        activity=ActivityState.SITTING,
        torso_angle=15.0,
        relative_body_height=0.6,
        vertical_velocity=0.15,  # Gentle controlled sit
        vertical_acceleration=0.05,
        movement_velocity=0.05,
        motion_intensity=0.15,
        floor_proximity=0.5,
        in_zone="BED",
    )
    sm.update(obs2)
    events2 = rule_engine.evaluate(sm, obs2)
    assert len(events2) == 0

    # 3. Lying down on bed (t = 1015s)
    obs3 = MovementObservation(
        timestamp=1015.0,
        activity=ActivityState.LYING,
        torso_angle=85.0,
        relative_body_height=0.25,
        vertical_velocity=0.10,  # Gentle controlled recline
        vertical_acceleration=0.02,
        movement_velocity=0.02,
        motion_intensity=0.05,
        floor_proximity=0.4,
        in_zone="BED",
    )
    sm.update(obs3)
    events3 = rule_engine.evaluate(sm, obs3)
    # Lying in bed must NOT trigger fall
    fall_events = [e for e in events3 if e["event_type"] == "possible_fall_detection"]
    assert len(fall_events) == 0

    # 4. Remains in bed motionless for 60 seconds (t = 1075s)
    obs4 = MovementObservation(
        timestamp=1075.0,
        activity=ActivityState.LYING,
        torso_angle=88.0,
        relative_body_height=0.25,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.01,
        floor_proximity=0.4,
        in_zone="BED",
    )
    sm.update(obs4)
    events4 = rule_engine.evaluate(sm, obs4)
    # Sleeping in bed should not trigger floor inactivity or fall
    assert len([e for e in events4 if e["event_type"] == "possible_fall_detection"]) == 0
    assert len([e for e in events4 if e["event_type"] == "prolonged_floor_inactivity"]) == 0


def test_accidental_fall_sequence_triggers_urgent_alerts(rule_engine):
    """Scenario: Person walking, suffers rapid downward acceleration, hits floor, remains motionless.

    GUARDIAN must trigger possible_fall_detection with URGENT risk level and transparent explanation.
    """
    sm = PersonStateMachine(person_id="elder_2", initial_timestamp=2000.0)

    # 1. Walking in living room (t = 2000s)
    sm.update(MovementObservation(
        timestamp=2000.0,
        activity=ActivityState.WALKING,
        torso_angle=8.0,
        relative_body_height=0.92,
        vertical_velocity=0.05,
        vertical_acceleration=0.01,
        movement_velocity=0.35,
        motion_intensity=0.5,
        floor_proximity=0.9,
        in_zone=None,
    ))

    # 2. Sudden loss of balance and rapid descent (t = 2002.0s)
    sm.update(MovementObservation(
        timestamp=2002.0,
        activity=ActivityState.TRANSITIONING,
        torso_angle=45.0,
        relative_body_height=0.5,
        vertical_velocity=1.45,  # High downward velocity > 0.8 threshold
        vertical_acceleration=2.1,
        movement_velocity=0.4,
        motion_intensity=0.9,
        floor_proximity=0.2,
        in_zone=None,
    ))

    # 3. Hits floor (t = 2003.0s)
    obs_impact = MovementObservation(
        timestamp=2003.0,
        activity=ActivityState.LYING_ON_FLOOR,
        torso_angle=88.0,
        relative_body_height=0.15,
        vertical_velocity=0.1,
        vertical_acceleration=0.0,
        movement_velocity=0.05,
        motion_intensity=0.04,  # Minimal movement after impact
        floor_proximity=0.02,  # Direct contact with floor level
        in_zone="FLOOR",
    )
    sm.update(obs_impact)
    events = rule_engine.evaluate(sm, obs_impact)

    # Must generate possible_fall_detection
    fall_events = [e for e in events if e["event_type"] == "possible_fall_detection"]
    assert len(fall_events) == 1
    fall = fall_events[0]
    assert fall["risk_level"] == "URGENT"
    assert fall["risk_score"] >= 0.85
    assert "Immediate caregiver check required" in fall["recommended_action"]
    assert "Sudden descent velocity" in fall["explanation"]["rejected_hypotheses"][0]
