"""Deterministic rule validation and evaluation models using Pydantic."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from guardian.engine.condition_registry import (
    ComparisonOperator,
    EvaluationContext,
    EvidenceItem,
    evaluate_comparison,
)


class RiskLevel(str, Enum):
    """Deterministic severity / risk levels."""
    NORMAL = "NORMAL"
    INFORMATIONAL = "INFORMATIONAL"
    WATCH = "WATCH"
    REVIEW = "REVIEW"
    URGENT = "URGENT"


class SingleCondition(BaseModel):
    """Single metric comparison condition."""
    metric: str
    operator: ComparisonOperator = ComparisonOperator.EQ
    value: Any
    weight: float = Field(default=1.0, ge=0.0)
    description: Optional[str] = None


class CompoundCondition(BaseModel):
    """Compound condition supporting ALL (AND), ANY (OR), and NONE (NOT) groups."""
    all_of: Optional[List[Union[SingleCondition, CompoundCondition]]] = None
    any_of: Optional[List[Union[SingleCondition, CompoundCondition]]] = None
    none_of: Optional[List[Union[SingleCondition, CompoundCondition]]] = None


class RuleDefinition(BaseModel):
    """Structured, validated definition of a safety rule."""
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = Field(default=50, ge=1, le=1000)
    conditions: CompoundCondition
    risk_level: RiskLevel = RiskLevel.REVIEW
    base_risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=60.0, ge=0.0)
    suppresses: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    recommended_action: str = "Verify person safety."


class RuleEvaluationResult(BaseModel):
    """Result of evaluating a single rule against a context."""
    rule_id: str
    rule_name: str
    triggered: bool
    risk_level: RiskLevel
    risk_score: float
    evidence: List[Dict[str, Any]]
    suppressed: bool = False
    suppressed_by: Optional[str] = None
    in_cooldown: bool = False
    recommended_action: str


def evaluate_single_condition(
    cond: SingleCondition,
    ctx: EvaluationContext,
) -> tuple[bool, EvidenceItem]:
    """Evaluate one condition against context and return (satisfied, EvidenceItem)."""
    actual = ctx.get_value(cond.metric)
    satisfied = evaluate_comparison(cond.operator, actual, cond.value)

    desc = cond.description or f"{cond.metric} {cond.operator.value} {cond.value}"
    ev = EvidenceItem(
        metric_name=cond.metric,
        expected_condition=f"{cond.operator.value} {cond.value}",
        observed_value=actual,
        satisfied=satisfied,
        weight=cond.weight,
        description=desc,
    )
    return satisfied, ev


def evaluate_compound_condition(
    cond: CompoundCondition,
    ctx: EvaluationContext,
) -> tuple[bool, List[EvidenceItem]]:
    """Recursively evaluate compound conditions and collect all evidence items."""
    collected_evidence: List[EvidenceItem] = []

    # ALL OF (Logical AND)
    if cond.all_of:
        for child in cond.all_of:
            if isinstance(child, SingleCondition):
                sat, ev = evaluate_single_condition(child, ctx)
                collected_evidence.append(ev)
                if not sat:
                    return False, collected_evidence
            else:
                sat, child_ev = evaluate_compound_condition(child, ctx)
                collected_evidence.extend(child_ev)
                if not sat:
                    return False, collected_evidence

    # ANY OF (Logical OR)
    if cond.any_of:
        any_satisfied = False
        any_evidence: List[EvidenceItem] = []
        for child in cond.any_of:
            if isinstance(child, SingleCondition):
                sat, ev = evaluate_single_condition(child, ctx)
                any_evidence.append(ev)
                if sat:
                    any_satisfied = True
            else:
                sat, child_ev = evaluate_compound_condition(child, ctx)
                any_evidence.extend(child_ev)
                if sat:
                    any_satisfied = True
        # For ANY OF, include only the passing evidence branch(es) if any passed
        if any_satisfied:
            collected_evidence.extend([ev for ev in any_evidence if ev.satisfied])
        else:
            collected_evidence.extend(any_evidence)
            return False, collected_evidence

    # NONE OF (Logical NOT)
    if cond.none_of:
        for child in cond.none_of:
            if isinstance(child, SingleCondition):
                sat, ev = evaluate_single_condition(child, ctx)
                # The condition for none_of passing is that the child is NOT satisfied
                guard_passed = not sat
                guard_ev = EvidenceItem(
                    metric_name=ev.metric_name,
                    expected_condition=f"NOT ({ev.expected_condition})",
                    observed_value=ev.observed_value,
                    satisfied=guard_passed,
                    weight=ev.weight,
                    description=f"Guard check: NOT ({ev.description})",
                )
                collected_evidence.append(guard_ev)
                if not guard_passed:
                    # If the forbidden condition occurred, compound condition fails
                    return False, collected_evidence
            else:
                sat, child_ev = evaluate_compound_condition(child, ctx)
                guard_passed = not sat
                for ev in child_ev:
                    ev.satisfied = not ev.satisfied
                    ev.description = f"Guard check: NOT ({ev.description})"
                collected_evidence.extend(child_ev)
                if not guard_passed:
                    return False, collected_evidence

    return True, collected_evidence
