"""Kinematic and geometric feature extraction from body landmarks."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np

from guardian.perception.geometry import (
    compute_angle_with_vertical,
    compute_midpoint,
    compute_distance,
    compute_joint_angle,
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

        # 4. Joint angles & anatomical landmark visibility
        l_knee = lms.get(KEY_LEFT_KNEE)
        r_knee = lms.get(KEY_RIGHT_KNEE)
        l_ank = lms.get(KEY_LEFT_ANKLE)
        r_ank = lms.get(KEY_RIGHT_ANKLE)

        # A leg is visible if knee or ankle is present, has adequate confidence, and is within frame bounds (< 0.94)
        l_knee_visible = bool(l_knee and (len(l_knee) < 3 or l_knee[2] >= 0.35) and l_knee[1] < 0.94)
        r_knee_visible = bool(r_knee and (len(r_knee) < 3 or r_knee[2] >= 0.35) and r_knee[1] < 0.94)
        l_ank_visible = bool(l_ank and (len(l_ank) < 3 or l_ank[2] >= 0.30) and l_ank[1] < 0.96)
        r_ank_visible = bool(r_ank and (len(r_ank) < 3 or r_ank[2] >= 0.30) and r_ank[1] < 0.96)
        has_legs_visible = l_knee_visible or r_knee_visible or l_ank_visible or r_ank_visible

        # Compute knee flexion angle
        knee_angles: List[float] = []
        if l_knee_visible and l_ank and (len(l_ank) < 3 or l_ank[2] >= 0.25):
            ang_l = compute_joint_angle(l_hip, l_knee[:2], l_ank[:2])
            knee_angles.append(ang_l)
        if r_knee_visible and r_ank and (len(r_ank) < 3 or r_ank[2] >= 0.25):
            ang_r = compute_joint_angle(r_hip, r_knee[:2], r_ank[:2])
            knee_angles.append(ang_r)

        knee_angle = round(float(np.mean(knee_angles)), 1) if knee_angles else 180.0

        # Head and shoulder vertical levels
        nose_lm = lms.get(KEY_NOSE)
        head_y = round(float(nose_lm[1]), 3) if nose_lm else round(float(ymin), 3)
        shoulder_y = round(float(sh_mid[1]), 3)

        # 5. Floor proximity
        if has_legs_visible:
            lowest_y = max(
                (l_ank[1] if l_ank else 0.0),
                (r_ank[1] if r_ank else 0.0),
                ymax,
            )
            floor_dist = abs(floor_y - lowest_y)
            floor_proximity = max(0.0, min(1.0, floor_dist))
        else:
            # Desk/webcam mode: bounding box bottom is just the desk/table cutoff, NOT the room floor!
            # Only if the person's head/shoulders drop significantly does proximity to floor drop.
            if head_y >= 0.65:
                floor_proximity = 0.15
            else:
                floor_proximity = 0.55

        # 6. Kinematics from historical frame delta
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
            knee_angle=knee_angle,
            head_y=head_y,
            shoulder_y=shoulder_y,
            has_legs_visible=has_legs_visible,
        )
