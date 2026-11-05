"""Deterministic activity classifier with temporal smoothing and hysteresis."""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional
from sentinel.activity.state_machine import ActivityState, MovementObservation


class ActivityClassifier:
    """Classifies physical human posture and activity with temporal hysteresis smoothing."""

    def __init__(self, smoothing_window_size: int = 5) -> None:
        self.smoothing_window_size = smoothing_window_size
        # Per-person circular buffer of provisional predictions
        self._history: Dict[str, Deque[ActivityState]] = {}

    def classify_frame(self, obs: MovementObservation) -> ActivityState:
        """Single-frame deterministic classification based on geometric & kinematic thresholds."""
        # 1. Recumbent postures: Torso angle >= 55 degrees
        if obs.torso_angle >= 55.0:
            if obs.floor_proximity <= 0.18 or obs.in_zone == "FLOOR":
                return ActivityState.LYING_ON_FLOOR
            return ActivityState.LYING

        # 2. Upright postures: Torso angle < 30 degrees
        if obs.torso_angle < 30.0:
            if obs.relative_body_height >= 0.60:
                if obs.movement_velocity >= 0.12 or obs.motion_intensity >= 0.25:
                    return ActivityState.WALKING
                return ActivityState.STANDING
            elif 0.25 <= obs.relative_body_height < 0.60:
                return ActivityState.SITTING

        # 3. Intermediate sitting: Torso angle between 30 and 55 degrees
        if 30.0 <= obs.torso_angle < 55.0 and obs.relative_body_height < 0.65:
            return ActivityState.SITTING

        # 4. In-between / dynamic transition
        if obs.motion_intensity > 0.15 or abs(obs.vertical_velocity) > 0.2:
            return ActivityState.TRANSITIONING

        return ActivityState.UNKNOWN

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
