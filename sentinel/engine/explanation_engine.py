"""Deterministic explanation engine generating transparent reasoning and audit evidence."""

from __future__ import annotations

from typing import Any, Dict, List
from sentinel.engine.condition_registry import EvidenceItem
from sentinel.engine.rule_evaluator import RiskLevel, RuleDefinition


class ExplanationEngine:
    """Generates transparent, explainable decision narratives for safety events."""

    @classmethod
    def generate_explanation(
        cls,
        rule: RuleDefinition,
        risk_level: RiskLevel,
        risk_score: float,
        evidence: List[EvidenceItem],
        context_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Produce structured human-readable explanation and rejected hypotheses."""
        summary_lines: List[str] = []
        evidence_details: List[Dict[str, Any]] = []
        rejected_hypotheses: List[str] = []

        summary_lines.append(
            f"Safety event '{rule.name}' triggered with risk level {risk_level.value} "
            f"(computed deterministic score: {risk_score:.3f})."
        )

        for item in evidence:
            status_text = "PASSED" if item.satisfied else "FAILED"
            evidence_details.append({
                "metric": item.metric_name,
                "expected": item.expected_condition,
                "observed": item.observed_value,
                "satisfied": item.satisfied,
                "weight": item.weight,
                "description": item.description,
            })
            if item.satisfied:
                summary_lines.append(
                    f"Observation confirmed: {item.metric_name} observed as {item.observed_value} "
                    f"satisfying requirement ({item.expected_condition})."
                )

        # Contextual hypothesis testing
        zone = context_data.get("zone_name")
        activity = context_data.get("activity_state")
        descent_vel = context_data.get("peak_descent_velocity", 0.0)

        if activity in ("LYING", "LYING_ON_FLOOR"):
            if zone == "BED":
                rejected_hypotheses.append("Unplanned fall hypothesis: Person located within calibrated bed resting zone.")
            elif zone == "SOFA":
                rejected_hypotheses.append("Emergency fall hypothesis: Person resting on calibrated sofa.")
            else:
                if descent_vel > 0.8:
                    rejected_hypotheses.append(
                        f"Intentional resting hypothesis ruled out: Sudden descent velocity measured {descent_vel:.2f} "
                        f"exceeding normal sitting/lying transition limit."
                    )
                else:
                    rejected_hypotheses.append(
                        "Controlled floor positioning considered: Gradual descent observed, but prolonged floor stay exceeds safe threshold."
                    )

        if context_data.get("failed_standing_attempts", 0) > 1:
            summary_lines.append(
                f"Repeated instability observed: {context_data['failed_standing_attempts']} unsuccessful standing attempts detected."
            )

        return {
            "summary": " ".join(summary_lines),
            "evidence_chain": evidence_details,
            "rejected_hypotheses": rejected_hypotheses,
            "recommended_action": rule.recommended_action,
        }
