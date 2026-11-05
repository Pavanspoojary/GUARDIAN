"""Multi-person tracker with Kalman Filtering and Hungarian assignment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import linear_sum_assignment

from guardian.perception.geometry import compute_iou
from guardian.perception.pose_estimator import PoseDetectionResult


class KalmanBoxTracker:
    """Constant-velocity Kalman filter for 2D bounding boxes [cx, cy, w, h]."""

    def __init__(self, bbox: Tuple[float, float, float, float], track_id: str) -> None:
        self.track_id = track_id
        # State: [cx, cy, w, h, vx, vy, vw, vh]
        ymin, xmin, ymax, xmax = bbox
        w = max(0.01, xmax - xmin)
        h = max(0.01, ymax - ymin)
        cx = xmin + w / 2.0
        cy = ymin + h / 2.0

        self.state = np.array([cx, cy, w, h, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # Transition matrix (dt = 1.0)
        self.F = np.eye(8, dtype=np.float32)
        for i in range(4):
            self.F[i, i + 4] = 1.0

        # Measurement matrix: observes [cx, cy, w, h]
        self.H = np.zeros((4, 8), dtype=np.float32)
        for i in range(4):
            self.H[i, i] = 1.0

        # Covariance matrices
        self.P = np.eye(8, dtype=np.float32) * 10.0
        self.Q = np.eye(8, dtype=np.float32) * 0.01
        self.Q[4:, 4:] *= 0.1
        self.R = np.eye(4, dtype=np.float32) * 0.05

        self.time_since_update = 0
        self.total_visible_count = 1
        self.last_pose: Optional[PoseDetectionResult] = None

    def predict(self) -> Tuple[float, float, float, float]:
        """Advance state prediction."""
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q
        self.time_since_update += 1
        return self.get_bbox()

    def update(self, detection: PoseDetectionResult) -> None:
        """Update tracker with observed detection."""
        self.time_since_update = 0
        self.total_visible_count += 1
        self.last_pose = detection

        ymin, xmin, ymax, xmax = detection.bbox
        w = max(0.01, xmax - xmin)
        h = max(0.01, ymax - ymin)
        cx = xmin + w / 2.0
        cy = ymin + h / 2.0

        z = np.array([cx, cy, w, h], dtype=np.float32)
        y = z - (self.H @ self.state)
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.state = self.state + (K @ y)
        self.P = (np.eye(8, dtype=np.float32) - K @ self.H) @ self.P

    def get_bbox(self) -> Tuple[float, float, float, float]:
        """Convert current state back to [ymin, xmin, ymax, xmax]."""
        cx, cy, w, h = self.state[:4]
        xmin = max(0.0, float(cx - w / 2.0))
        xmax = min(1.0, float(cx + w / 2.0))
        ymin = max(0.0, float(cy - h / 2.0))
        ymax = min(1.0, float(cy + h / 2.0))
        return (ymin, xmin, ymax, xmax)


@dataclass
class TrackedPerson:
    """Represents an active person tracked across frames."""
    track_id: str
    bbox: Tuple[float, float, float, float]
    pose: PoseDetectionResult
    total_frames_tracked: int
    time_since_last_seen: int


class MultiPersonTracker:
    """Associates pose detections to persistent tracks using Hungarian algorithm."""

    def __init__(
        self,
        max_missed_frames: int = 30,
        iou_threshold: float = 0.25,
    ) -> None:
        self.max_missed_frames = max_missed_frames
        self.iou_threshold = iou_threshold
        self.trackers: Dict[str, KalmanBoxTracker] = {}
        self._next_id = 1

    def update(self, detections: List[PoseDetectionResult]) -> List[TrackedPerson]:
        """Predict existing tracks, match detections, update, and return active tracks."""
        # 1. Predict all current tracks
        for tracker in self.trackers.values():
            tracker.predict()

        active_track_ids = list(self.trackers.keys())
        active_boxes = [self.trackers[tid].get_bbox() for tid in active_track_ids]
        num_tracks = len(active_track_ids)
        num_dets = len(detections)

        matched_tracks: List[int] = []
        matched_dets: List[int] = []

        if num_tracks > 0 and num_dets > 0:
            # Build cost matrix: 1.0 - IoU
            cost_matrix = np.zeros((num_tracks, num_dets), dtype=np.float32)
            for t_idx, t_box in enumerate(active_boxes):
                for d_idx, det in enumerate(detections):
                    iou = compute_iou(t_box, det.bbox)
                    cost_matrix[t_idx, d_idx] = 1.0 - iou

            row_ind, col_ind = linear_sum_assignment(cost_matrix)

            for r, c in zip(row_ind, col_ind):
                # Only accept match if IoU >= threshold
                if (1.0 - cost_matrix[r, c]) >= self.iou_threshold:
                    matched_tracks.append(r)
                    matched_dets.append(c)
                    t_id = active_track_ids[r]
                    self.trackers[t_id].update(detections[c])

        # 2. Initialize new tracks for unmatched detections
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_dets:
                new_id = f"person_{self._next_id}"
                self._next_id += 1
                tracker = KalmanBoxTracker(det.bbox, track_id=new_id)
                tracker.last_pose = det
                self.trackers[new_id] = tracker

        # 3. Prune dead tracks
        dead_ids = [
            tid for tid, trk in self.trackers.items()
            if trk.time_since_update > self.max_missed_frames
        ]
        for tid in dead_ids:
            del self.trackers[tid]

        # 4. Formulate output
        results: List[TrackedPerson] = []
        for tid, trk in self.trackers.items():
            if trk.last_pose is not None:
                results.append(TrackedPerson(
                    track_id=tid,
                    bbox=trk.get_bbox(),
                    pose=trk.last_pose,
                    total_frames_tracked=trk.total_visible_count,
                    time_since_last_seen=trk.time_since_update,
                ))

        return results
