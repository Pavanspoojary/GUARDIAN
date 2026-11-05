"""Non-parametric statistical behavioral baseline profiling using rolling medians and MAD."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def compute_median_and_mad(values: List[float]) -> Tuple[float, float]:
    """Calculate sample median and Median Absolute Deviation (MAD).

    MAD = median(|X - median(X)|).
    Consistent with normal distribution by factor 1.4826.
    """
    if not values:
        return 0.0, 0.0
    arr = np.array(values, dtype=np.float64)
    med = float(np.median(arr))
    abs_deviations = np.abs(arr - med)
    mad = float(np.median(abs_deviations))
    # Scaled MAD to approximate standard deviation
    scaled_mad = 1.4826 * mad
    return round(med, 2), round(scaled_mad, 2)


@dataclass
class HourlyBaseline:
    """Historical baseline metrics for a specific 1-hour window (0 to 23)."""
    hour: int
    samples_count: int = 0
    # Historical values recorded over multiple observation periods
    walking_durations: List[float] = field(default_factory=list)
    sitting_durations: List[float] = field(default_factory=list)
    motionless_durations: List[float] = field(default_factory=list)
    movement_intensity_values: List[float] = field(default_factory=list)

    def add_observation(
        self,
        walking_seconds: float,
        sitting_seconds: float,
        motionless_seconds: float,
        mean_motion_intensity: float,
    ) -> None:
        """Append an observation period (e.g., from a past day) to this hourly bin."""
        self.samples_count += 1
        self.walking_durations.append(walking_seconds)
        self.sitting_durations.append(sitting_seconds)
        self.motionless_durations.append(motionless_seconds)
        self.movement_intensity_values.append(mean_motion_intensity)

    def get_summary(self) -> Dict[str, Any]:
        """Compute robust non-parametric summary statistics."""
        walk_med, walk_mad = compute_median_and_mad(self.walking_durations)
        sit_med, sit_mad = compute_median_and_mad(self.sitting_durations)
        motionless_med, motionless_mad = compute_median_and_mad(self.motionless_durations)
        intensity_med, intensity_mad = compute_median_and_mad(self.movement_intensity_values)

        return {
            "hour": self.hour,
            "samples_count": self.samples_count,
            "walking_median": walk_med,
            "walking_mad": walk_mad,
            "sitting_median": sit_med,
            "sitting_mad": sit_mad,
            "motionless_median": motionless_med,
            "motionless_mad": motionless_mad,
            "intensity_median": intensity_med,
            "intensity_mad": intensity_mad,
        }


class PersonBehavioralProfile:
    """Maintains 24-hour diurnal statistical baselines for an individual."""

    def __init__(self, person_id: str, min_samples_for_baseline: int = 3) -> None:
        self.person_id = person_id
        self.min_samples_for_baseline = min_samples_for_baseline
        # 24 hourly bins (0..23)
        self.hourly_bins: Dict[int, HourlyBaseline] = {
            h: HourlyBaseline(hour=h) for h in range(24)
        }

    def record_hourly_summary(
        self,
        hour: int,
        walking_seconds: float,
        sitting_seconds: float,
        motionless_seconds: float,
        mean_intensity: float,
    ) -> None:
        """Feed a completed hour's historical totals."""
        if 0 <= hour <= 23:
            self.hourly_bins[hour].add_observation(
                walking_seconds=walking_seconds,
                sitting_seconds=sitting_seconds,
                motionless_seconds=motionless_seconds,
                mean_motion_intensity=mean_intensity,
            )

    def has_sufficient_baseline(self, hour: int) -> bool:
        """Verify if enough historical days/samples exist to make assertions."""
        return self.hourly_bins[hour].samples_count >= self.min_samples_for_baseline

    def evaluate_deviation(
        self,
        hour: int,
        observed_walking_seconds: float,
        observed_motionless_seconds: float,
    ) -> Optional[Dict[str, Any]]:
        """Calculate statistical deviation (modified Z-score) against personal baseline.

        Returns None if baseline is insufficient, avoiding premature conclusions.
        """
        if not self.has_sufficient_baseline(hour):
            return None

        bin_data = self.hourly_bins[hour]
        summary = bin_data.get_summary()

        # Modified Z-score for walking duration
        # z = 0.6745 * (x - median) / MAD
        walk_med = summary["walking_median"]
        walk_mad = summary["walking_mad"]
        walk_z = 0.0
        if walk_mad > 1e-4:
            walk_z = round(0.6745 * (observed_walking_seconds - walk_med) / walk_mad, 2)

        # Modified Z-score for motionless duration
        mot_med = summary["motionless_median"]
        mot_mad = summary["motionless_mad"]
        mot_z = 0.0
        if mot_mad > 1e-4:
            mot_z = round(0.6745 * (observed_motionless_seconds - mot_med) / mot_mad, 2)

        is_significant_decrease_in_walking = (walk_z < -2.5 and walk_med > 300.0)
        is_significant_increase_in_motionless = (mot_z > 2.5 and observed_motionless_seconds > 600.0)

        anomaly_detected = is_significant_decrease_in_walking or is_significant_increase_in_motionless

        return {
            "hour": hour,
            "samples_count": bin_data.samples_count,
            "walking_median": walk_med,
            "observed_walking": observed_walking_seconds,
            "walking_zscore": walk_z,
            "motionless_median": mot_med,
            "observed_motionless": observed_motionless_seconds,
            "motionless_zscore": mot_z,
            "anomaly_detected": anomaly_detected,
            "recommendation": (
                "Suggest gentle welfare check: current activity significantly deviates from historical routine. "
                "Note: Statistical deviation metric only, not a clinical or medical diagnosis."
                if anomaly_detected else "Activity aligns with personal historical baseline."
            ),
        }
