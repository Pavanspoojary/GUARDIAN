"""Tests verifying rule priorities, suppression, cooldowns, and deduplication."""

import pytest
from guardian.activity.state_machine import (
    ActivityState,
    PersonStateMachine,
    MovementObservation,
)
from guardian.engine.rule_engine import RuleEngine
from guardian.engine.condition_registry import EvaluationContext


@pytest.fixture
def rule_engine():
    engine = RuleEngine()
    engine.load_rules_from_directory("configs/rules")
    return engine


def test_cooldown_prevents_duplicate_spam(rule_engine):
    """Verify that multiple frames of the same condition do not spam duplicate events."""
    sm = PersonStateMachine(person_id="elder_dup", initial_timestamp=100.0)

    obs1 = MovementObservation(
        timestamp=100.0,
        activity=ActivityState.LYING_ON_FLOOR,
        torso_angle=88.0,
        relative_body_height=0.15,
        vertical_velocity=1.2,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.02,
        floor_proximity=0.02,
    )
    sm.update(obs1)
    events1 = rule_engine.evaluate(sm, obs1)
    fall_events = [e for e in events1 if e["event_type"] == "possible_fall_detection"]
    assert len(fall_events) == 1

    # Next frame at 101.0s (1 second later)
    obs2 = MovementObservation(
        timestamp=101.0,
        activity=ActivityState.LYING_ON_FLOOR,
        torso_angle=88.0,
        relative_body_height=0.15,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.02,
        floor_proximity=0.02,
    )
    sm.update(obs2)
    events2 = rule_engine.evaluate(sm, obs2)
    # Because cooldown is 120s, no duplicate fall event should trigger
    dup_falls = [e for e in events2 if e["event_type"] == "possible_fall_detection"]
    assert len(dup_falls) == 0


def test_priority_suppression(rule_engine):
    """Verify that high-priority fall detection suppresses general inactivity alert."""
    sm = PersonStateMachine(person_id="elder_sup", initial_timestamp=100.0)

    # Person fell and has been still for 200 seconds
    sm.last_sudden_descent_time = 100.0
    sm.peak_descent_velocity = 1.3
    sm.motionless_duration_seconds = 200.0
    sm.current_state = ActivityState.LYING_ON_FLOOR

    obs = MovementObservation(
        timestamp=300.0,
        activity=ActivityState.LYING_ON_FLOOR,
        torso_angle=88.0,
        relative_body_height=0.15,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.01,
        floor_proximity=0.02,
    )

    events = rule_engine.evaluate(sm, obs)
    event_types = [e["event_type"] for e in events]

    # Possible fall detection or prolonged floor inactivity must be present
    assert "possible_fall_detection" in event_types or "prolonged_floor_inactivity" in event_types
    # General prolonged inactivity must be suppressed
    assert "general_prolonged_inactivity" not in event_types
