"""Tests for behavioral baselines, anomaly detection, event correlation, and event lifecycle."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from guardian.storage.database import Base
from guardian.storage.repositories import IncidentRepository, AuditRepository
from guardian.intelligence.behavioral_baseline import PersonBehavioralProfile, compute_median_and_mad
from guardian.intelligence.event_correlator import EventCorrelator
from guardian.events.event_manager import EventManager


@pytest.fixture
def db_session():
    """Create in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_median_and_mad_computation():
    """Verify robust non-parametric median and MAD calculations."""
    # Symmetrical distribution: [10, 20, 30, 40, 50] -> median=30
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    med, mad = compute_median_and_mad(vals)
    assert med == 30.0
    # |X - 30| = [20, 10, 0, 10, 20] -> median absolute deviation = 10 -> scaled = 14.83
    assert abs(mad - 14.83) < 0.1


def test_behavioral_baseline_and_deviation():
    """Establish a 3-day baseline and detect a severe reduction in morning activity."""
    profile = PersonBehavioralProfile(person_id="elder_stat_1", min_samples_for_baseline=3)

    # Historical morning 9 AM routine (Day 1, 2, 3): moves around ~1500s, motionless ~300s
    profile.record_hourly_summary(hour=9, walking_seconds=1450.0, sitting_seconds=1850.0, motionless_seconds=300.0, mean_intensity=0.35)
    profile.record_hourly_summary(hour=9, walking_seconds=1520.0, sitting_seconds=1780.0, motionless_seconds=300.0, mean_intensity=0.38)
    profile.record_hourly_summary(hour=9, walking_seconds=1500.0, sitting_seconds=1800.0, motionless_seconds=300.0, mean_intensity=0.36)

    assert profile.has_sufficient_baseline(hour=9) is True

    # Case A: Normal day (walking 1480s)
    dev_normal = profile.evaluate_deviation(hour=9, observed_walking_seconds=1480.0, observed_motionless_seconds=320.0)
    assert dev_normal is not None
    assert dev_normal["anomaly_detected"] is False

    # Case B: Anomalous day (person barely moved at all - only 50s walking)
    dev_anom = profile.evaluate_deviation(hour=9, observed_walking_seconds=50.0, observed_motionless_seconds=1200.0)
    assert dev_anom is not None
    assert dev_anom["anomaly_detected"] is True
    assert dev_anom["walking_zscore"] < -2.5
    assert "Suggest gentle welfare check" in dev_anom["recommendation"]
    assert "Statistical deviation metric only" in dev_anom["recommendation"]


def test_event_manager_correlation_lifecycle_and_escalation(db_session):
    """Verify event manager ingest, correlation, lifecycle transitions, and timeout escalation."""
    mgr = EventManager(db_session=db_session, escalation_timeout_seconds=5.0)

    # 1. Ingest initial event at t = 100.0
    ev1 = {
        "event_type": "nighttime_bed_exit",
        "rule_name": "Nighttime Bed Exit",
        "person_id": "elder_lifecycle",
        "timestamp": 100.0,
        "risk_level": "WATCH",
        "risk_score": 0.55,
        "recommended_action": "Guide person.",
    }
    inc1 = mgr.ingest_event(ev1)
    assert inc1.status == "DETECTED"
    assert inc1.risk_level == "WATCH"

    # 2. Within 20s, a higher-risk restricted zone crossing occurs (t = 120.0)
    ev2 = {
        "event_type": "restricted_zone_crossing",
        "rule_name": "Restricted Zone Breach",
        "person_id": "elder_lifecycle",
        "timestamp": 120.0,
        "risk_level": "URGENT",
        "risk_score": 0.90,
        "recommended_action": "Immediate interception advised.",
    }
    inc2 = mgr.ingest_event(ev2)
    # Must correlate into the same incident and escalate risk level!
    assert inc2.incident_id == inc1.incident_id
    assert inc2.risk_level == "URGENT"
    assert len(inc2.contributing_events) == 2

    # 3. Check escalation: at t = 122.0 (only 2s elapsed, timeout is 5s)
    esc_early = mgr.check_escalations(current_time=122.0)
    assert len(esc_early) == 0

    # At t = 126.0 (6s elapsed since last update at 120s, exceeding 5s timeout)
    esc_due = mgr.check_escalations(current_time=126.0)
    assert len(esc_due) == 1
    assert esc_due[0]["escalation_level"] == "TIER_2_SUPERVISOR_ALERT"

    # 4. Acknowledge incident
    ack_res = mgr.acknowledge(inc1.incident_id, operator_name="Nurse_Sarah", notes="Checking room now.")
    assert ack_res is not None
    assert ack_res["status"] == "ACKNOWLEDGED"

    # 5. Resolve incident
    res = mgr.resolve(inc1.incident_id, operator_name="Nurse_Sarah", notes="Resident safely returned to bed.")
    assert res is not None
    assert res["status"] == "RESOLVED"
