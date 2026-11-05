"""Pose estimation provider abstraction with MediaPipe and Synthetic implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from sentinel.perception.geometry import compute_bounding_box


# Standard landmark keys
KEY_NOSE = "nose"
KEY_LEFT_SHOULDER = "left_shoulder"
KEY_RIGHT_SHOULDER = "right_shoulder"
KEY_LEFT_ELBOW = "left_elbow"
KEY_RIGHT_ELBOW = "right_elbow"
KEY_LEFT_WRIST = "left_wrist"
KEY_RIGHT_WRIST = "right_wrist"
KEY_LEFT_HIP = "left_hip"
KEY_RIGHT_HIP = "right_hip"
KEY_LEFT_KNEE = "left_knee"
KEY_RIGHT_KNEE = "right_knee"
KEY_LEFT_ANKLE = "left_ankle"
KEY_RIGHT_ANKLE = "right_ankle"

# MediaPipe landmark indices
MP_INDICES = {
    0: KEY_NOSE,
    11: KEY_LEFT_SHOULDER,
    12: KEY_RIGHT_SHOULDER,
    13: KEY_LEFT_ELBOW,
    14: KEY_RIGHT_ELBOW,
    15: KEY_LEFT_WRIST,
    16: KEY_RIGHT_WRIST,
    23: KEY_LEFT_HIP,
    24: KEY_RIGHT_HIP,
    25: KEY_LEFT_KNEE,
    26: KEY_RIGHT_KNEE,
    27: KEY_LEFT_ANKLE,
    28: KEY_RIGHT_ANKLE,
}


@dataclass
class PoseDetectionResult:
    """Standardized representation of detected person pose landmarks."""
    # Maps landmark name to normalized (x, y, visibility)
    landmarks: Dict[str, Tuple[float, float, float]]
    bbox: Tuple[float, float, float, float]  # [ymin, xmin, ymax, xmax]
    confidence: float = 1.0


class PoseEstimatorBase(ABC):
    """Abstract interface for human pose estimation providers."""

    @abstractmethod
    def estimate(self, frame: np.ndarray) -> List[PoseDetectionResult]:
        """Estimate human poses in image frame (BGR format)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Release any underlying model resources."""
        pass


class MediaPipePoseEstimator(PoseEstimatorBase):
    """Concrete pose estimator backed by Google MediaPipe."""

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1,
    ) -> None:
        import mediapipe as mp
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=model_complexity,
        )

    def estimate(self, frame: np.ndarray) -> List[PoseDetectionResult]:
        """Extract landmarks from OpenCV frame."""
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        if not results.pose_landmarks:
            return []

        landmarks_dict: Dict[str, Tuple[float, float, float]] = {}
        pts_2d: List[Tuple[float, float]] = []
        visibilities: List[float] = []

        for idx, name in MP_INDICES.items():
            lm = results.pose_landmarks.landmark[idx]
            x = max(0.0, min(1.0, float(lm.x)))
            y = max(0.0, min(1.0, float(lm.y)))
            vis = max(0.0, min(1.0, float(lm.visibility)))
            landmarks_dict[name] = (x, y, vis)
            pts_2d.append((x, y))
            visibilities.append(vis)

        bbox = compute_bounding_box(pts_2d)
        mean_confidence = float(np.mean(visibilities)) if visibilities else 1.0

        return [PoseDetectionResult(
            landmarks=landmarks_dict,
            bbox=bbox,
            confidence=mean_confidence,
        )]

    def close(self) -> None:
        """Close model instance."""
        if hasattr(self, "pose") and self.pose is not None:
            self.pose.close()


class SyntheticPoseEstimator(PoseEstimatorBase):
    """Deterministic mock pose estimator for testing and simulation."""

    def __init__(self) -> None:
        self.next_detections: List[PoseDetectionResult] = []

    def queue_pose(self, detection: PoseDetectionResult) -> None:
        """Queue a specific pose detection to be emitted."""
        self.next_detections.append(detection)

    def estimate(self, frame: np.ndarray) -> List[PoseDetectionResult]:
        """Return queued detection or synthesize based on frame shape."""
        if self.next_detections:
            return [self.next_detections.pop(0)]
        return []

    def close(self) -> None:
        self.next_detections.clear()
