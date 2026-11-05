"""Video input intelligence managing video streams, files, dropped frames, and test feeds."""

from __future__ import annotations

import time
from typing import Generator, Optional, Tuple, Union
import cv2
import numpy as np


class VideoSource:
    """Manages video capture from webcams, files, or synthetic test generation."""

    def __init__(
        self,
        source: Union[int, str] = 0,
        target_fps: float = 30.0,
        reconnect_attempts: int = 3,
    ) -> None:
        self.source = source
        self.target_fps = target_fps
        self.reconnect_attempts = reconnect_attempts
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_synthetic = (source == "synthetic" or source == "SYNTHETIC")

        self.frames_processed = 0
        self.dropped_frames = 0
        self.last_frame_timestamp: float = 0.0
        self.is_connected = False

    def connect(self) -> bool:
        """Initialize camera or open video file."""
        if self.is_synthetic:
            self.is_connected = True
            return True

        self.cap = cv2.VideoCapture(self.source)
        self.is_connected = bool(self.cap.isOpened())
        return self.is_connected

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """Read a single frame.

        Returns (success, frame, timestamp_seconds).
        """
        now = time.time()
        if self.is_synthetic:
            self.frames_processed += 1
            # Generate procedural 640x480 test image
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                frame,
                f"SENTINEL Synthetic Feed Frame #{self.frames_processed}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 200),
                1,
            )
            self.last_frame_timestamp = now
            return True, frame, now

        if self.cap is None or not self.cap.isOpened():
            self.is_connected = False
            return False, None, now

        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.dropped_frames += 1
            return False, None, now

        self.frames_processed += 1
        self.last_frame_timestamp = now
        return True, frame, now

    def stream(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        """Generator yielding (frame, timestamp) tuples continuously."""
        if not self.is_connected:
            self.connect()

        while self.is_connected:
            success, frame, ts = self.read_frame()
            if not success:
                break
            yield frame, ts

    def release(self) -> None:
        """Release capture device."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_connected = False
