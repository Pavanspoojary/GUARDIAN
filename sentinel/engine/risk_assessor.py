"""Deterministic multi-factor risk assessment engine."""

from __future__ import annotations

from typing import List
from sentinel.engine.condition_registry import EvidenceItem
from sentinel.engine.rule_evaluator import RiskLevel


class RiskAssessor:
    """Calculates deterministic risk scores and levels from evidence and rule parameters."""

    # Deterministic mapping thresholds
    THRESHOLD_INFORMATIONAL = 0.20
    THRESHOLD_WATCH = 0.40
    THRESHOLD_REVIEW = 0.65
    THRESHOLD_URGENT = 0.85

    @classmethod
    def calculate_risk(
        cls,
        base_score: float,
        target_rule_level: RiskLevel,
        evidence: List[EvidenceItem],
        observation_confidence: float = 1.0,
        motionless_duration_seconds: float = 0.0,
        is_nighttime: bool = False,
    ) -> tuple[RiskLevel, float]:
        """Compute deterministic risk score and resulting risk level.

        Formula:
        Score = BaseScore * EvidenceRatio * ConfidenceScaling * Multipliers
        Clamped to [0.0, 1.0].
        """
        if not evidence:
            return RiskLevel.NORMAL, 0.0

        # Evidence weighting
        total_weight = sum(item.weight for item in evidence)
        satisfied_weight = sum(item.weight for item in evidence if item.satisfied)

        if total_weight <= 0.0 or satisfied_weight <= 0.0:
            return RiskLevel.NORMAL, 0.0

        evidence_ratio = satisfied_weight / total_weight

        # Base confidence scaling: penalize low-confidence pose detections
        confidence_scaling = max(0.5, min(1.0, observation_confidence))

        # Stillness multiplier: progressive escalation for floor or abnormal inactivity
        duration_multiplier = 1.0
        if motionless_duration_seconds > 180.0:
            duration_multiplier = 1.35
        elif motionless_duration_seconds > 60.0:
            duration_multiplier = 1.20
        elif motionless_duration_seconds > 20.0:
            duration_multiplier = 1.10

        # Nighttime context multiplier
        night_multiplier = 1.15 if is_nighttime else 1.0

        # Calculate final normalized score
        raw_score = (
            base_score
            * (0.4 + 0.6 * evidence_ratio)
            * confidence_scaling
            * duration_multiplier
            * night_multiplier
        )

        final_score = round(max(0.0, min(1.0, raw_score)), 3)

        # Map to RiskLevel
        # If the rule explicitly requires URGENT and score >= THRESHOLD_REVIEW, escalate to URGENT
        if target_rule_level == RiskLevel.URGENT and final_score >= cls.THRESHOLD_REVIEW:
            return RiskLevel.URGENT, final_score

        if final_score >= cls.THRESHOLD_URGENT:
            level = RiskLevel.URGENT
        elif final_score >= cls.THRESHOLD_REVIEW:
            level = RiskLevel.REVIEW
        elif final_score >= cls.THRESHOLD_WATCH:
            level = RiskLevel.WATCH
        elif final_score >= cls.THRESHOLD_INFORMATIONAL:
            level = RiskLevel.INFORMATIONAL
        else:
            level = RiskLevel.NORMAL

        return level, final_score
