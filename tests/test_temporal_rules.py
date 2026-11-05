"""Tests verifying deterministic temporal operators and time-of-day rules."""

import pytest
from guardian.activity.state_machine import (
    ActivityState,
    PersonStateMachine,
    MovementObservation,
)
from guardian.engine.rule_engine import RuleEngine
from guardian.engine.condition_registry import EvaluationContext
from guardian.engine.temporal_operators import check_time_window


@pytest.fixture
def rule_engine():
    engine = RuleEngine()
    engine.load_rules_from_directory("configs/rules")
    return engine


def test_time_window_midnight_wrap():
    """Verify time window logic across midnight (22:00 to 06:00)."""
    # 23:00 is within 22:00 - 06:00
    assert check_time_window(23, 22, 6) is True
    # 02:00 is within 22:00 - 06:00
    assert check_time_window(2, 22, 6) is True
    # 22:00 is start bound
    assert check_time_window(22, 22, 6) is True
    # 06:00 is end bound (exclusive)
    assert check_time_window(6, 22, 6) is False
    # 14:00 is outside
    assert check_time_window(14, 22, 6) is False


def test_prolonged_floor_inactivity(rule_engine):
    """Person lying on floor for >= 45 seconds motionless triggers URGENT prolonged floor alert."""
    sm = PersonStateMachine(person_id="elder_floor", initial_timestamp=100.0)

    # 1. First touches floor at t = 100.0
    obs1 = MovementObservation(
        timestamp=100.0,
        activity=ActivityState.LYING_ON_FLOOR,
        torso_angle=85.0,
        relative_body_height=0.18,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.02,
        floor_proximity=0.05,
    )
    sm.update(obs1)
    events1 = rule_engine.evaluate(sm, obs1)
    # At t=100s, motionless duration is 0, so no prolonged floor inactivity alert
    assert len([e for e in events1 if e["event_type"] == "prolonged_floor_inactivity"]) == 0

    # 2. At t = 150.0 (50 seconds later, completely motionless)
    obs2 = MovementObservation(
        timestamp=150.0,
        activity=ActivityState.LYING_ON_FLOOR,
        torso_angle=85.0,
        relative_body_height=0.18,
        vertical_velocity=0.0,
        vertical_acceleration=0.0,
        movement_velocity=0.0,
        motion_intensity=0.01,
        floor_proximity=0.05,
    )
    sm.update(obs2)
    assert sm.motionless_duration_seconds >= 50.0

    events2 = rule_engine.evaluate(sm, obs2)
    floor_events = [e for e in events2 if e["event_type"] == "prolonged_floor_inactivity"]
    assert len(floor_events) == 1
    assert floor_events[0]["risk_level"] == "URGENT"
    assert floor_events[0]["risk_score"] >= 0.85
