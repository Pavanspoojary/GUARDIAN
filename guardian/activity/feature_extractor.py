"""Kinematic and geometric feature extraction from body landmarks."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np

from guardian.perception.geometry import (
    compute_angle_with_vertical,
    compute_midpoint,
    compute_distance,
)
from guardian.perception.pose_estimator import (
    PoseDetectionResult,
    KEY_NOSE,
    KEY_LEFT_SHOULDER,
    KEY_RIGHT_SHOULDER,
    KEY_LEFT_HIP,
    KEY_RIGHT_HIP,
    KEY_LEFT_KNEE,
    KEY_RIGHT_KNEE,
    KEY_LEFT_ANKLE,
    KEY_RIGHT_ANKLE,
)
from guardian.activity.state_machine import ActivityState, MovementObservation


class FeatureExtractor:
    """Computes normalized kinematic, postural, and motion metrics from tracked poses."""

    def __init__(self, default_floor_y: float = 0.85) -> None:
        self.default_floor_y = default_floor_y
        # Cache previous state per track_id: (timestamp, hip_midpoint, vertical_velocity, landmarks)
        self._prev_state: Dict[str, Tuple[float, Tuple[float, float], float, Dict[str, Tuple[float, float, float]]]] = {}

    def extract_features(
        self,
        track_id: str,
        pose: PoseDetectionResult,
        timestamp: float,
        floor_level_y: Optional[float] = None,
        zone_name: Optional[str] = None,
        provisional_activity: ActivityState = ActivityState.UNKNOWN,
    ) -> MovementObservation:
        """Calculate complete MovementObservation for a tracked person."""
        floor_y = floor_level_y if floor_level_y is not None else self.default_floor_y
        lms = pose.landmarks

        # 1. Shoulders & Hips midpoints
        l_sh = lms.get(KEY_LEFT_SHOULDER, (0.5, 0.3, 0.5))[:2]
        r_sh = lms.get(KEY_RIGHT_SHOULDER, (0.5, 0.3, 0.5))[:2]
        sh_mid = compute_midpoint(l_sh, r_sh)

        l_hip = lms.get(KEY_LEFT_HIP, (0.5, 0.5, 0.5))[:2]
        r_hip = lms.get(KEY_RIGHT_HIP, (0.5, 0.5, 0.5))[:2]
        hip_mid = compute_midpoint(l_hip, r_hip)

        # 2. Torso angle with vertical (0 = vertical upright, 90 = horizontal)
        torso_angle = compute_angle_with_vertical(sh_mid, hip_mid)

        # 3. Relative body height from bounding box
        ymin, xmin, ymax, xmax = pose.bbox
        body_height = max(0.01, min(1.0, ymax - ymin))

        # 4. Floor proximity
        l_ank = lms.get(KEY_LEFT_ANKLE, (0.5, 0.8, 0.5))[:2]
        r_ank = lms.get(KEY_RIGHT_ANKLE, (0.5, 0.8, 0.5))[:2]
        lowest_y = max(l_ank[1], r_ank[1], ymax)
        floor_dist = abs(floor_y - lowest_y)
        floor_proximity = max(0.0, min(1.0, floor_dist))

        # 5. Kinematics from historical frame delta
        vert_vel = 0.0
        vert_accel = 0.0
        move_vel = 0.0
        motion_intensity = 0.0

        if track_id in self._prev_state:
            prev_t, prev_hip, prev_v_vel, prev_lms = self._prev_state[track_id]
            dt = max(0.001, timestamp - prev_t)

            # Downward displacement in image coordinates: positive dy means falling/dropping
            dy = hip_mid[1] - prev_hip[1]
            dx = hip_mid[0] - prev_hip[0]

            vert_vel = round(dy / dt, 3)
            vert_accel = round((vert_vel - prev_v_vel) / dt, 3)
            move_vel = round(np.hypot(dx, dy) / dt, 3)

            # Motion intensity: mean displacement of all keypoints
            displacements = []
            for k in lms:
                if k in prev_lms:
                    d = compute_distance(lms[k][:2], prev_lms[k][:2])
                    displacements.append(d)
            if displacements:
                motion_intensity = round(float(np.mean(displacements)) / dt, 3)

        # Update cache
        self._prev_state[track_id] = (timestamp, hip_mid, vert_vel, lms)

        return MovementObservation(
            timestamp=timestamp,
            activity=provisional_activity,
            torso_angle=torso_angle,
            relative_body_height=body_height,
            vertical_velocity=vert_vel,
            vertical_acceleration=vert_accel,
            movement_velocity=move_vel,
            motion_intensity=motion_intensity,
            floor_proximity=floor_proximity,
            in_zone=zone_name,
            confidence=pose.confidence,
        )
