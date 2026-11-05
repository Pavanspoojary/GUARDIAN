"""Tests for computer vision perception, tracking, feature extraction, and activity classification."""

import pytest
import numpy as np

from guardian.perception.geometry import (
    compute_angle_with_vertical,
    compute_iou,
    compute_bounding_box,
)
from guardian.perception.pose_estimator import (
    PoseDetectionResult,
    SyntheticPoseEstimator,
    KEY_LEFT_SHOULDER,
    KEY_RIGHT_SHOULDER,
    KEY_LEFT_HIP,
    KEY_RIGHT_HIP,
    KEY_LEFT_ANKLE,
    KEY_RIGHT_ANKLE,
)
from guardian.perception.tracker import MultiPersonTracker
from guardian.perception.video_source import VideoSource
from guardian.activity.feature_extractor import FeatureExtractor
from guardian.activity.activity_classifier import ActivityClassifier
from guardian.activity.state_machine import ActivityState, PersonStateMachine
from guardian.engine.rule_engine import RuleEngine


def test_geometry_calculations():
    """Verify angle with vertical and IoU calculations."""
    # Perfectly vertical segment
    top = (0.5, 0.2)
    bottom = (0.5, 0.8)
    assert compute_angle_with_vertical(top, bottom) == 0.0

    # Perfectly horizontal segment
    left = (0.2, 0.5)
    right = (0.8, 0.5)
    assert compute_angle_with_vertical(left, right) == 90.0

    # 45-degree angle
    p1 = (0.0, 0.0)
    p2 = (1.0, 1.0)
    assert abs(compute_angle_with_vertical(p1, p2) - 45.0) < 0.1

    # IoU
    box_a = (0.1, 0.1, 0.5, 0.5)
    box_b = (0.1, 0.1, 0.5, 0.5)
    assert compute_iou(box_a, box_b) == 1.0

    box_disjoint = (0.6, 0.6, 0.9, 0.9)
    assert compute_iou(box_a, box_disjoint) == 0.0


def test_multi_person_tracking_and_persistence():
    """Verify Kalman tracking maintains persistent person IDs across frames."""
    tracker = MultiPersonTracker(max_missed_frames=10, iou_threshold=0.2)

    # Frame 1: Person at [0.1, 0.2, 0.8, 0.4]
    det1 = PoseDetectionResult(
        landmarks={},
        bbox=(0.1, 0.2, 0.8, 0.4),
        confidence=0.9,
    )
    tracks_f1 = tracker.update([det1])
    assert len(tracks_f1) == 1
    person_id = tracks_f1[0].track_id
    assert person_id.startswith("person_")

    # Frame 2: Person slightly shifted to [0.12, 0.22, 0.82, 0.42]
    det2 = PoseDetectionResult(
        landmarks={},
        bbox=(0.12, 0.22, 0.82, 0.42),
        confidence=0.92,
    )
    tracks_f2 = tracker.update([det2])
    assert len(tracks_f2) == 1
    # Must preserve same person ID!
    assert tracks_f2[0].track_id == person_id


def test_end_to_end_vision_to_decision_pipeline():
    """Verify end-to-end pipeline from synthetic frames to deterministic decision engine."""
    extractor = FeatureExtractor(default_floor_y=0.85)
    classifier = ActivityClassifier(smoothing_window_size=3)
    rule_engine = RuleEngine()
    rule_engine.load_rules_from_directory("configs/rules")

    sm = PersonStateMachine(person_id="simulated_p1", initial_timestamp=10.0)

    # Simulate upright standing pose
    standing_lms = {
        KEY_LEFT_SHOULDER: (0.45, 0.2, 0.9),
        KEY_RIGHT_SHOULDER: (0.55, 0.2, 0.9),
        KEY_LEFT_HIP: (0.47, 0.5, 0.9),
        KEY_RIGHT_HIP: (0.53, 0.5, 0.9),
        KEY_LEFT_ANKLE: (0.47, 0.84, 0.9),
        KEY_RIGHT_ANKLE: (0.53, 0.84, 0.9),
    }
    pose_standing = PoseDetectionResult(
        landmarks=standing_lms,
        bbox=(0.15, 0.40, 0.85, 0.60),
        confidence=0.95,
    )

    obs_t1 = extractor.extract_features("simulated_p1", pose_standing, timestamp=10.0)
    act_t1 = classifier.update_and_classify("simulated_p1", obs_t1)
    obs_t1.activity = act_t1
    assert act_t1 in (ActivityState.STANDING, ActivityState.WALKING)

    sm.update(obs_t1)
    events = rule_engine.evaluate(sm, obs_t1)
    assert len(events) == 0  # Normal standing, no alerts

    # Now simulate rapid fall to floor at t=10.4 (dt = 0.4s descent)
    floor_lms = {
        KEY_LEFT_SHOULDER: (0.2, 0.82, 0.9),
        KEY_RIGHT_SHOULDER: (0.3, 0.82, 0.9),
        KEY_LEFT_HIP: (0.5, 0.83, 0.9),
        KEY_RIGHT_HIP: (0.6, 0.83, 0.9),
        KEY_LEFT_ANKLE: (0.8, 0.84, 0.9),
        KEY_RIGHT_ANKLE: (0.85, 0.84, 0.9),
    }
    pose_floor = PoseDetectionResult(
        landmarks=floor_lms,
        bbox=(0.75, 0.20, 0.85, 0.85),
        confidence=0.92,
    )

    obs_t2 = extractor.extract_features(
        "simulated_p1",
        pose_floor,
        timestamp=10.4,
        zone_name="FLOOR",
    )
    act_t2 = classifier.update_and_classify("simulated_p1", obs_t2)
    obs_t2.activity = act_t2
    assert act_t2 == ActivityState.LYING_ON_FLOOR

    sm.update(obs_t2)
    events_t2 = rule_engine.evaluate(sm, obs_t2)

    # Must produce safety incident
    assert len(events_t2) > 0
    event_types = [e["event_type"] for e in events_t2]
    assert "possible_fall_detection" in event_types
