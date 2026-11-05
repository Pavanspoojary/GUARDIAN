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
    """Concrete pose estimator backed by Google MediaPipe Tasks API."""

    def __init__(
        self,
        model_path: str = "pose_landmarker.task",
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        import os
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        # Check local paths for model
        resolved_path = model_path
        if not os.path.exists(resolved_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            candidate = os.path.join(base_dir, "pose_landmarker.task")
            if os.path.exists(candidate):
                resolved_path = candidate

        base_options = python.BaseOptions(model_asset_path=resolved_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            min_pose_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self.detector = vision.PoseLandmarker.create_from_options(options)

    def estimate(self, frame: np.ndarray) -> List[PoseDetectionResult]:
        """Extract landmarks from OpenCV frame (BGR numpy array)."""
        import cv2
        import mediapipe as mp

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = self.detector.detect(mp_image)

        if not results or not results.pose_landmarks:
            return []

        detections: List[PoseDetectionResult] = []
        for person_lms in results.pose_landmarks:
            landmarks_dict: Dict[str, Tuple[float, float, float]] = {}
            pts_2d: List[Tuple[float, float]] = []
            visibilities: List[float] = []

            for idx, name in MP_INDICES.items():
                if idx < len(person_lms):
                    lm = person_lms[idx]
                    x = max(0.0, min(1.0, float(lm.x)))
                    y = max(0.0, min(1.0, float(lm.y)))
                    vis = max(0.0, min(1.0, float(getattr(lm, "visibility", 1.0))))
                    landmarks_dict[name] = (x, y, vis)
                    pts_2d.append((x, y))
                    visibilities.append(vis)

            bbox = compute_bounding_box(pts_2d)
            mean_confidence = float(np.mean(visibilities)) if visibilities else 1.0

            detections.append(PoseDetectionResult(
                landmarks=landmarks_dict,
                bbox=bbox,
                confidence=mean_confidence,
            ))

        return detections

    def close(self) -> None:
        """Close model instance."""
        if hasattr(self, "detector") and self.detector is not None:
            self.detector.close()


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
