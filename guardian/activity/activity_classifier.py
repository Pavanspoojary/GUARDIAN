"""Deterministic activity classifier with temporal smoothing and hysteresis."""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional
import numpy as np

from guardian.activity.state_machine import ActivityState, MovementObservation


class ActivityClassifier:
    """Classifies physical human posture and activity with temporal hysteresis smoothing."""

    def __init__(self, smoothing_window_size: int = 5) -> None:
        self.smoothing_window_size = smoothing_window_size
        # Per-person circular buffer of provisional predictions
        self._history: Dict[str, Deque[ActivityState]] = {}

    def classify_frame(self, obs: MovementObservation) -> ActivityState:
        """Deterministic posture & activity classification using anatomical geometry."""
        # Dual-mode classification based on whether lower limbs are visible in frame
        if obs.has_legs_visible:
            # --- FULL-BODY VISIBILITY MODE ---
            # 1. Recumbent postures: Torso horizontal and low to floor plane
            is_recumbent = (
                obs.torso_angle >= 50.0
                and (obs.floor_proximity <= 0.25 or obs.relative_body_height <= 0.35 or obs.in_zone == "FLOOR")
            )
            if is_recumbent:
                if obs.floor_proximity <= 0.25 or obs.in_zone == "FLOOR":
                    return ActivityState.LYING_ON_FLOOR
                return ActivityState.LYING

            # 2. Sitting: Bent knees (flexion angle < 140 deg) with upright/semi-upright torso
            if obs.knee_angle < 140.0 and obs.torso_angle < 50.0:
                return ActivityState.SITTING

            # 3. Upright Standing / Walking: Straight legs (knee angle >= 140 deg)
            if obs.torso_angle < 35.0:
                if obs.relative_body_height >= 0.55 and obs.knee_angle >= 140.0:
                    if obs.movement_velocity >= 0.12 or obs.motion_intensity >= 0.22:
                        return ActivityState.WALKING
                    return ActivityState.STANDING
                elif 0.22 <= obs.relative_body_height < 0.55:
                    return ActivityState.SITTING
                else:
                    return ActivityState.STANDING

            # 4. Intermediate sitting: Torso angle between 30 and 50 degrees
            if 30.0 <= obs.torso_angle < 50.0 and obs.relative_body_height < 0.65:
                return ActivityState.SITTING

            # 5. In-between / dynamic transition
            if obs.motion_intensity > 0.15 or abs(obs.vertical_velocity) > 0.2:
                return ActivityState.TRANSITIONING

            return ActivityState.UNKNOWN

        else:
            # --- DESK / WEBCAM UPPER-BODY MODE ---
            # Legs are hidden below desk or cropped off by close-up framing

            # 1. Floor collapse / Fall check:
            # Both shoulders and head drop down toward floor level, or torso horizontal with dropped center of mass
            is_desk_collapse = (
                (obs.head_y >= 0.70 and obs.shoulder_y >= 0.65)
                or (obs.torso_angle >= 55.0 and obs.shoulder_y >= 0.60)
                or (obs.head_y >= 0.70 and obs.torso_angle >= 50.0)
            )
            if is_desk_collapse:
                return ActivityState.LYING_ON_FLOOR

            # 2. Reclining in chair:
            # Person leans back (torso/shoulder tilt 40-75 deg), but head is still elevated above desk
            if 40.0 <= obs.torso_angle < 75.0 and obs.head_y < 0.55:
                return ActivityState.SITTING

            # 3. Standing up at desk:
            # Head rises toward top frame (< 0.20) and shoulders rise (< 0.30) with upright torso
            if obs.head_y < 0.20 and obs.shoulder_y < 0.30 and obs.torso_angle < 30.0:
                return ActivityState.STANDING

            # 4. Neck flexion / forward tilt at desk (looking down at keyboard, phone, or books):
            # Head/neck tilted forward while seated stably at desk
            if obs.neck_angle > 25.0 and obs.shoulder_y < 0.65:
                return ActivityState.SITTING

            # 5. Seated upright at desk / workstation:
            # Head in normal upper-middle window (head_y >= 0.20) and upright torso (< 45 deg)
            if obs.torso_angle < 45.0:
                return ActivityState.SITTING

            # 6. Dynamic movement / transition (head movement / gestures while seated remain SITTING)
            if abs(obs.vertical_velocity) > 0.35:
                return ActivityState.TRANSITIONING

            return ActivityState.SITTING

    def compute_distribution(
        self,
        obs: Optional[MovementObservation],
        active_state: ActivityState,
        risk_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Compute real-time continuous kinematic probability distribution with dynamic card ordering."""
        if obs is None or active_state == ActivityState.UNKNOWN:
            return [
                {"label": "NO PERSON VISIBLE", "percent": 96.0, "status": "MUTED"},
                {"label": "UNCLEAR / OTHER", "percent": 4.0, "status": "MUTED"},
                {"label": "SITTING", "percent": 0.0, "status": "MUTED"},
                {"label": "STANDING", "percent": 0.0, "status": "MUTED"},
                {"label": "BENDING / FORWARD TILT", "percent": 0.0, "status": "MUTED"},
                {"label": "WALKING", "percent": 0.0, "status": "MUTED"},
                {"label": "LYING / RESTING", "percent": 0.0, "status": "MUTED"},
                {"label": "POSSIBLE FALL · REVIEW", "percent": 0.0, "status": "MUTED"},
            ]

        # 1. Continuous Kinematic Affinity Scores
        torso_upright = max(0.0, min(1.0, 1.0 - obs.torso_angle / 45.0))
        shoulder_level = max(0.0, min(1.0, 1.0 - obs.shoulder_tilt / 35.0))

        # --- Sitting Affinity ---
        if obs.has_legs_visible:
            knee_flex = max(0.0, min(1.0, (155.0 - obs.knee_angle) / 60.0))
            score_sit = 3.2 * torso_upright * (0.35 + 0.65 * knee_flex) + 0.3
        else:
            # Desk mode: seated window between 0.20 and 0.55
            head_in_seat_zone = max(0.0, min(1.0, 1.0 - abs(obs.head_y - 0.35) / 0.28))
            score_sit = 3.4 * torso_upright * shoulder_level * (0.45 + 0.55 * head_in_seat_zone) + 0.5

        # --- Standing Affinity ---
        if obs.has_legs_visible:
            knee_straight = max(0.0, min(1.0, (obs.knee_angle - 130.0) / 45.0))
            height_factor = max(0.0, min(1.0, (obs.relative_body_height - 0.55) / 0.35))
            score_stand = 3.3 * knee_straight * height_factor * torso_upright
        else:
            rise_factor = max(0.0, min(1.0, (0.30 - obs.head_y) / 0.18))
            score_stand = 3.6 * rise_factor * torso_upright

        # --- Bending / Forward Tilt Affinity ---
        neck_flex = max(0.0, min(1.0, (obs.neck_angle - 15.0) / 32.0))
        torso_stoop = max(0.0, min(1.0, 1.0 - abs(obs.torso_angle - 35.0) / 22.0))
        score_bend = 2.8 * max(neck_flex, torso_stoop)

        # --- Walking Affinity ---
        if obs.has_legs_visible:
            move_factor = max(0.0, min(1.0, obs.movement_velocity / 0.22))
            score_walk = 3.2 * move_factor * torso_upright
        else:
            # Upper body gestures do not indicate walking
            score_walk = 0.08 * max(0.0, min(1.0, obs.movement_velocity / 0.30))

        # --- Lying / Resting Affinity ---
        torso_flat = max(0.0, min(1.0, (obs.torso_angle - 45.0) / 35.0))
        shoulder_flat = max(0.0, min(1.0, (obs.shoulder_tilt - 35.0) / 35.0))
        score_lying = 3.2 * max(torso_flat, shoulder_flat)
        if obs.in_zone in ("BED", "SOFA"):
            score_lying += 1.8

        # --- Possible Fall / Emergency Affinity ---
        score_fall = 4.2 * max(0.0, min(1.0, risk_score))
        if active_state == ActivityState.LYING_ON_FLOOR:
            score_fall = max(score_fall, 3.8)
        if obs.floor_proximity <= 0.20 and obs.torso_angle >= 50.0:
            score_fall += 2.0

        # --- Ambient Uncertainty Affinity ---
        score_unclear = 0.22 + 0.6 * max(0.0, 1.0 - obs.confidence)

        # Softmax temperature-scaled normalization
        raw_scores = {
            "SITTING": max(0.01, score_sit),
            "STANDING": max(0.01, score_stand),
            "BENDING / FORWARD TILT": max(0.01, score_bend),
            "WALKING": max(0.01, score_walk),
            "LYING / RESTING": max(0.01, score_lying),
            "POSSIBLE FALL · REVIEW": max(0.01, score_fall),
            "UNCLEAR / OTHER": max(0.01, score_unclear),
        }

        # Temperature parameter controls contrast sharpness
        temp = 1.05
        exp_scores = {k: np.exp(v / temp) for k, v in raw_scores.items()}
        total_exp = sum(exp_scores.values())

        percentages: Dict[str, float] = {}
        for k, v in exp_scores.items():
            percentages[k] = round((v / total_exp) * 100.0, 1)

        # Ensure total sums cleanly to 100%
        rem = 100.0 - sum(percentages.values())
        top_key = max(percentages, key=percentages.get)
        percentages[top_key] = round(percentages[top_key] + rem, 1)

        # Format items sorted descending by percentage
        items = [{"label": k, "percent": max(0.0, p)} for k, p in percentages.items()]
        items.append({"label": "NO PERSON VISIBLE", "percent": 0.0})
        items.sort(key=lambda x: x["percent"], reverse=True)
        return items

    def generate_narrative(
        self,
        active_state: ActivityState,
        obs: Optional[MovementObservation],
        duration: float,
        motionless_duration: float,
        failed_attempts: int,
    ) -> str:
        """Generate situation narrative displayed above the telemetry HUD."""
        if obs is None:
            return "REVIEWING FOOTAGE... NO HUMAN SUBJECT VISIBLE IN MONITORED FRAME."

        if active_state == ActivityState.LYING_ON_FLOOR:
            if motionless_duration > 30.0:
                return (
                    f"PROLONGED RECUMBENCY ON FLOOR ({motionless_duration:.0f}S). ZERO RECOVERY DETECTED. "
                    f"TORSO HORIZONTAL AT {obs.torso_angle:.0f} DEG; CAREGIVER ASSISTANCE REQUIRED."
                )
            if abs(obs.vertical_velocity) > 0.6:
                return (
                    f"RAPID LOWERING DETECTED ({obs.vertical_velocity:.2f} M/S). NOW RECUMBENT ON FLOOR; "
                    f"RELATIVE HEIGHT: {obs.relative_body_height:.2f}; NO RECOVERY OBSERVED."
                )
            return (
                f"PERSON AT REST ON FLOOR PLANE ({duration:.0f}S). TORSO ANGLE {obs.torso_angle:.0f} DEG; "
                f"FLOOR PROXIMITY: {obs.floor_proximity:.2f}. MONITORING RECOVERY."
            )

        if active_state == ActivityState.LYING:
            return (
                f"RESTING POSTURE IN CALIBRATED ZONE ({duration:.0f}S). TORSO RECLINED AT {obs.torso_angle:.0f} DEG. "
                f"CUSHIONING/BED ENGAGED; STABLE SUPPORT."
            )

        if active_state == ActivityState.SITTING:
            if failed_attempts >= 2:
                return (
                    f"REPEATED FAILED STANDING ATTEMPTS ({failed_attempts}X). PERSON IN CHAIR; "
                    f"INSTABILITY OR MUSCLE FATIGUE IDENTIFIED. PHYSICAL ASSISTANCE ADVISED."
                )
            if obs.neck_angle > 25.0:
                return (
                    f"PERSON SEATED AT DESK / WORKSTATION — HEAD/NECK TILTED FORWARD ({obs.neck_angle:.0f} DEG). "
                    f"TORSO ANGLE: {obs.torso_angle:.0f} DEG; STABLE POSTURE."
                )
            if not obs.has_legs_visible:
                return (
                    f"PERSON SEATED AT DESK / WORKSTATION ({duration:.0f}S). "
                    f"TORSO ANGLE: {obs.torso_angle:.0f} DEG; STABLE POSITION."
                )
            return (
                f"PERSON SEATED IN CHAIR ({duration:.0f}S). KNEE ANGLE: {obs.knee_angle:.0f} DEG; "
                f"TORSO ANGLE: {obs.torso_angle:.0f} DEG; NORMAL SITTING STABILITY."
            )

        if active_state == ActivityState.WALKING:
            return (
                f"AMBULATION IN PROGRESS; VELOCITY: {obs.movement_velocity:.2f} M/S. "
                f"UPRIGHT POSTURE ({obs.torso_angle:.0f} DEG); CADENCE STEADY; NO COLLAPSE."
            )

        if active_state == ActivityState.STANDING:
            return (
                f"UPRIGHT STANDING POSTURE ({duration:.0f}S). "
                f"RELATIVE HEIGHT: {obs.relative_body_height:.2f}; TORSO ANGLE: {obs.torso_angle:.0f} DEG. NORMAL BALANCE."
            )

        return (
            f"DYNAMIC POSTURE TRANSITION ({duration:.1f}S). "
            f"MOTION INTENSITY: {obs.motion_intensity:.2f}; AWAITING STABLE POSE."
        )

    def update_and_classify(self, person_id: str, obs: MovementObservation) -> ActivityState:
        """Apply deterministic temporal smoothing and hysteresis over recent frames."""
        raw_state = self.classify_frame(obs)

        if person_id not in self._history:
            self._history[person_id] = deque(maxlen=self.smoothing_window_size)

        buf = self._history[person_id]
        buf.append(raw_state)

        # Hysteresis vote: count states in sliding window
        counts: Dict[ActivityState, int] = {}
        for state in buf:
            counts[state] = counts.get(state, 0) + 1

        # High-salience override: recumbent postures (LYING_ON_FLOOR, LYING) take precedence if observed
        if raw_state in (ActivityState.LYING_ON_FLOOR, ActivityState.LYING) and obs.torso_angle >= 55.0:
            return raw_state

        # Sudden velocity drop override
        if abs(obs.vertical_velocity) > 0.4:
            return raw_state

        # Tie-break in favor of most recent observation
        max_count = max(counts.values())
        candidates = [s for s, c in counts.items() if c == max_count]
        if raw_state in candidates:
            return raw_state

        return candidates[0]
