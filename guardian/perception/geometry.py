"""Geometric calculations, angles, distances, and spatial bounding boxes."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
import numpy as np


def compute_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def compute_midpoint(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[float, float]:
    """Midpoint between two 2D points."""
    return ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)


def compute_angle_with_vertical(p_top: Tuple[float, float], p_bottom: Tuple[float, float]) -> float:
    """Calculate the angle (in degrees [0, 90]) between the segment (top -> bottom) and vertical axis.

    0 degrees: perfectly vertical (upright).
    90 degrees: perfectly horizontal.
    In image coordinates: top has smaller y than bottom when upright.
    """
    dx = p_bottom[0] - p_top[0]
    dy = p_bottom[1] - p_top[1]

    # If top is below bottom in image, dy is negative, but for angle with vertical:
    # Vector is (dx, dy). Vertical down vector is (0, 1).
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return 0.0

    # Dot product with vertical unit vector (0, 1) is dy / length
    cos_theta = max(-1.0, min(1.0, abs(dy) / length))
    rad = math.acos(cos_theta)
    deg = math.degrees(rad)
    return round(deg, 2)


def compute_joint_angle(
    p_a: Tuple[float, float],
    p_b: Tuple[float, float],
    p_c: Tuple[float, float],
) -> float:
    """Angle in degrees at vertex p_b between vectors BA and BC."""
    v1 = (p_a[0] - p_b[0], p_a[1] - p_b[1])
    v2 = (p_c[0] - p_b[0], p_c[1] - p_b[1])

    dot = v1[0] * v2[0] + v1[1] * v2[1]
    norm1 = math.hypot(v1[0], v1[1])
    norm2 = math.hypot(v2[0], v2[1])

    if norm1 < 1e-6 or norm2 < 1e-6:
        return 180.0

    cos_val = max(-1.0, min(1.0, dot / (norm1 * norm2)))
    return round(math.degrees(math.acos(cos_val)), 2)


def compute_bounding_box(
    landmarks: List[Tuple[float, float]],
    margin: float = 0.05,
) -> Tuple[float, float, float, float]:
    """Calculate normalized [ymin, xmin, ymax, xmax] bounding box covering landmarks."""
    if not landmarks:
        return (0.0, 0.0, 0.0, 0.0)

    xs = [p[0] for p in landmarks]
    ys = [p[1] for p in landmarks]

    xmin = max(0.0, min(xs) - margin)
    xmax = min(1.0, max(xs) + margin)
    ymin = max(0.0, min(ys) - margin)
    ymax = min(1.0, max(ys) + margin)

    return (round(ymin, 4), round(xmin, 4), round(ymax, 4), round(xmax, 4))


def compute_iou(
    box_a: Tuple[float, float, float, float],
    box_b: Tuple[float, float, float, float],
) -> float:
    """Intersection over Union between two [ymin, xmin, ymax, xmax] bounding boxes."""
    ya1, xa1, ya2, xa2 = box_a
    yb1, xb1, yb2, xb2 = box_b

    # Intersection rectangle
    y_inter_min = max(ya1, yb1)
    x_inter_min = max(xa1, xb1)
    y_inter_max = min(ya2, yb2)
    x_inter_max = min(xa2, xb2)

    inter_w = max(0.0, x_inter_max - x_inter_min)
    inter_h = max(0.0, y_inter_max - y_inter_min)
    inter_area = inter_w * inter_h

    area_a = max(0.0, xa2 - xa1) * max(0.0, ya2 - ya1)
    area_b = max(0.0, xb2 - xb1) * max(0.0, yb2 - yb1)
    union_area = area_a + area_b - inter_area

    if union_area <= 1e-6:
        return 0.0

    return inter_area / union_area
