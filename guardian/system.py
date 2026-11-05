"""Central Sentinel system orchestrating perception, feature extraction, rules, and incident management."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session

from guardian.perception.pose_estimator import PoseEstimatorBase, PoseDetectionResult
from guardian.perception.tracker import MultiPersonTracker, TrackedPerson
from guardian.activity.feature_extractor import FeatureExtractor
from guardian.activity.activity_classifier import ActivityClassifier
from guardian.activity.state_machine import PersonStateMachine, MovementObservation
from guardian.engine.context_engine import RoomCalibration, ZoneDefinition, ZoneType
from guardian.engine.rule_engine import RuleEngine
from guardian.engine.condition_registry import EvaluationContext
from guardian.events.event_manager import EventManager
from guardian.intelligence.behavioral_baseline import PersonBehavioralProfile
from guardian.storage.database import init_db


class GuardianEngine:
    """Deep module coordinating the deterministic behavior and safety pipeline."""

    def __init__(
        self,
        pose_estimator: PoseEstimatorBase,
        db_url: str = "sqlite:///guardian.db",
        rules_directory: str = "configs/rules",
        room_id: str = "ROOM_101",
        room_type: str = "BEDROOM",
        floor_level_y: float = 0.85,
    ) -> None:
        self.pose_estimator = pose_estimator
        self.tracker = MultiPersonTracker(max_missed_frames=30, iou_threshold=0.25)
        self.feature_extractor = FeatureExtractor(default_floor_y=floor_level_y)
        self.activity_classifier = ActivityClassifier(smoothing_window_size=5)

        # Context & calibration
        self.calibration = RoomCalibration(
            room_id=room_id,
            room_type=room_type,
            floor_level_y=floor_level_y,
        )
        # Register default room zones
        self.calibration.add_zone(ZoneDefinition(
            name="BED_ZONE",
            zone_type=ZoneType.BED,
            bounds=(0.10, 0.05, 0.65, 0.35),
            description="Calibrated resting bed area",
        ))
        self.calibration.add_zone(ZoneDefinition(
            name="RESTRICTED_STAIRS",
            zone_type=ZoneType.RESTRICTED,
            bounds=(0.05, 0.70, 0.85, 0.98),
            description="Restricted stairway perimeter",
        ))
        self.calibration.add_zone(ZoneDefinition(
            name="SAFE_LIVING_AREA",
            zone_type=ZoneType.SAFE,
            bounds=(0.15, 0.35, 0.85, 0.70),
            description="General safe movement area",
        ))

        # Rule engine
        self.rule_engine = RuleEngine()
        self.rule_engine.load_rules_from_directory(rules_directory)

        # Database and event management
        self.engine, self.SessionLocal = init_db(db_url)
        self.db_session: Session = self.SessionLocal()
        self.event_manager = EventManager(self.db_session, escalation_timeout_seconds=60.0)

        # Per-person runtime state machines and statistical profiles
        self.person_state_machines: Dict[str, PersonStateMachine] = {}
        self.person_baselines: Dict[str, PersonBehavioralProfile] = {}

        # Status telemetry
        self.total_frames_processed = 0
        self.camera_status = "ONLINE"
        self.camera_obstruction_score = 0.0

    def get_or_create_state_machine(self, person_id: str, timestamp: float) -> PersonStateMachine:
        """Fetch or initialize per-person state machine."""
        if person_id not in self.person_state_machines:
            self.person_state_machines[person_id] = PersonStateMachine(
                person_id=person_id,
                initial_timestamp=timestamp,
            )
        return self.person_state_machines[person_id]

    def get_or_create_baseline(self, person_id: str) -> PersonBehavioralProfile:
        """Fetch or initialize per-person behavioral baseline."""
        if person_id not in self.person_baselines:
            self.person_baselines[person_id] = PersonBehavioralProfile(person_id=person_id)
        return self.person_baselines[person_id]

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp: Optional[float] = None,
        hour_of_day: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process a single visual frame through the complete deterministic pipeline."""
        now = timestamp if timestamp is not None else time.time()
        current_hour = hour_of_day if hour_of_day is not None else time.localtime(now).tm_hour
        self.total_frames_processed += 1

        # 1. Perception: Pose Estimation
        detections: List[PoseDetectionResult] = self.pose_estimator.estimate(frame)

        # 2. Tracking: Multi-person association
        tracked_persons: List[TrackedPerson] = self.tracker.update(detections)

        telemetry_tracks: List[Dict[str, Any]] = []
        new_incidents: List[Dict[str, Any]] = []

        # 3. Process each tracked person
        for track in tracked_persons:
            pid = track.track_id
            sm = self.get_or_create_state_machine(pid, now)

            # Determine spatial zone
            ymin, xmin, ymax, xmax = track.bbox
            feet_x = (xmin + xmax) / 2.0
            feet_y = ymax
            zone_obj = self.calibration.get_zone_at_point(feet_x, feet_y)
            zone_name = zone_obj.name if zone_obj else None

            # Extract kinematic features
            obs = self.feature_extractor.extract_features(
                track_id=pid,
                pose=track.pose,
                timestamp=now,
                floor_level_y=self.calibration.floor_level_y,
                zone_name=zone_name,
            )

            # Classify physical activity
            activity = self.activity_classifier.update_and_classify(pid, obs)
            obs.activity = activity

            # Update temporal state machine
            transition = sm.update(obs)

            # Create evaluation context
            eval_ctx = EvaluationContext(
                person_state_machine=sm,
                current_observation=obs,
                room_type=self.calibration.room_type,
                current_hour=current_hour,
                zone_name=zone_name,
                camera_status=self.camera_status,
                camera_obstruction_score=self.camera_obstruction_score,
            )

            # Evaluate deterministic safety rules
            events = self.rule_engine.evaluate(sm, obs, ctx=eval_ctx)

            # Ingest events into EventManager
            for ev in events:
                incident = self.event_manager.ingest_event(ev)
                new_incidents.append({
                    "incident_id": incident.incident_id,
                    "person_id": incident.person_id,
                    "incident_type": incident.incident_type,
                    "risk_level": incident.risk_level,
                    "risk_score": incident.risk_score,
                    "narrative": incident.narrative,
                    "explanation": ev.get("explanation"),
                })

            telemetry_tracks.append({
                "person_id": pid,
                "bbox": track.bbox,
                "activity": activity.value,
                "duration_seconds": round(sm.current_duration_seconds, 1),
                "torso_angle": obs.torso_angle,
                "relative_body_height": obs.relative_body_height,
                "motion_intensity": obs.motion_intensity,
                "zone": zone_name,
                "confidence": obs.confidence,
                "landmarks": track.pose.landmarks,
                "knee_angle": obs.knee_angle,
                "head_y": obs.head_y,
                "shoulder_y": obs.shoulder_y,
                "has_legs_visible": obs.has_legs_visible,
                "floor_proximity": obs.floor_proximity,
                "vertical_velocity": obs.vertical_velocity,
                "movement_velocity": obs.movement_velocity,
            })

        # Check for incident escalations
        escalations = self.event_manager.check_escalations(current_time=now)

        return {
            "timestamp": now,
            "frame_number": self.total_frames_processed,
            "camera_status": self.camera_status,
            "active_tracks_count": len(tracked_persons),
            "tracks": telemetry_tracks,
            "new_incidents": new_incidents,
            "escalations": escalations,
        }

    def close(self) -> None:
        """Clean up resources."""
        self.pose_estimator.close()
        self.db_session.close()
