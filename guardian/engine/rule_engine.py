"""Deterministic Rule Engine orchestrating safety rule evaluation, prioritization, and suppression."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import yaml
from pydantic import ValidationError

from guardian.activity.state_machine import PersonStateMachine, MovementObservation
from guardian.engine.condition_registry import EvaluationContext, EvidenceItem
from guardian.engine.rule_evaluator import (
    RuleDefinition,
    RuleEvaluationResult,
    RiskLevel,
    evaluate_compound_condition,
)
from guardian.engine.risk_assessor import RiskAssessor
from guardian.engine.explanation_engine import ExplanationEngine


class RuleEngine:
    """Core deterministic rule engine evaluating behavioral conditions and generating events."""

    def __init__(self) -> None:
        self.rules: Dict[str, RuleDefinition] = {}
        # Cooldown tracking: (person_id, rule_id) -> timestamp of last trigger
        self.cooldown_registry: Dict[tuple[str, str], float] = {}

    def register_rule(self, rule: RuleDefinition) -> None:
        """Register or update a validated rule definition."""
        self.rules[rule.id] = rule

    def load_rule_from_yaml(self, yaml_content: str) -> RuleDefinition:
        """Parse and validate YAML rule definition."""
        data = yaml.safe_load(yaml_content)
        # If wrapped under 'rule:' key, unwrap
        if "rule" in data and isinstance(data["rule"], dict):
            rule_dict = data["rule"]
            if "conditions" in data:
                rule_dict["conditions"] = data["conditions"]
            if "risk" in data and isinstance(data["risk"], dict):
                rule_dict["risk_level"] = data["risk"].get("level", "REVIEW")
                if "base_score" in data["risk"]:
                    rule_dict["base_risk_score"] = data["risk"]["base_score"]
            if "cooldown_seconds" in data:
                rule_dict["cooldown_seconds"] = data["cooldown_seconds"]
            if "suppresses" in data:
                rule_dict["suppresses"] = data["suppresses"]
            if "depends_on" in data:
                rule_dict["depends_on"] = data["depends_on"]
            if "recommended_action" in data:
                rule_dict["recommended_action"] = data["recommended_action"]
            data = rule_dict

        rule = RuleDefinition.model_validate(data)
        self.register_rule(rule)
        return rule

    def load_rules_from_directory(self, dir_path: str) -> List[RuleDefinition]:
        """Load all .yaml or .yml rule files from directory."""
        loaded: List[RuleDefinition] = []
        if not os.path.exists(dir_path):
            return loaded

        for fname in sorted(os.listdir(dir_path)):
            if fname.endswith((".yaml", ".yml")):
                fpath = os.path.join(dir_path, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    try:
                        rule = self.load_rule_from_yaml(content)
                        loaded.append(rule)
                    except ValidationError as err:
                        raise ValueError(f"Validation error loading rule from {fname}: {err}") from err
        return loaded

    def evaluate(
        self,
        sm: PersonStateMachine,
        obs: MovementObservation,
        ctx: Optional[EvaluationContext] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluate all active rules against the person state machine and current observation.

        Respects priorities, dependencies, cooldowns, and suppression sets.
        """
        if ctx is None:
            ctx = EvaluationContext(
                person_state_machine=sm,
                current_observation=obs,
                zone_name=obs.in_zone,
            )

        now = obs.timestamp
        # Sort rules descending by priority (highest priority evaluated first)
        sorted_rules = sorted(
            [r for r in self.rules.values() if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )

        triggered_rule_ids: set[str] = set()
        suppressed_rule_ids: Dict[str, str] = {}  # rule_id -> suppressed_by_rule_id
        generated_events: List[Dict[str, Any]] = []

        for rule in sorted_rules:
            # 1. Check if suppressed by a higher-priority rule
            if rule.id in suppressed_rule_ids:
                continue

            # 2. Check dependencies (if depends_on is specified, all prerequisites must have triggered)
            if rule.depends_on and not all(dep in triggered_rule_ids for dep in rule.depends_on):
                continue

            # 3. Check cooldown
            cooldown_key = (sm.person_id, rule.id)
            last_trigger = self.cooldown_registry.get(cooldown_key)
            if last_trigger is not None and (now - last_trigger) < rule.cooldown_seconds:
                # Rule is in cooldown, suppress duplicate alert
                continue

            # 4. Evaluate condition tree
            satisfied, evidence_items = evaluate_compound_condition(rule.conditions, ctx)

            if satisfied:
                triggered_rule_ids.add(rule.id)
                self.cooldown_registry[cooldown_key] = now

                # Add to suppression set for other rules
                for sup_id in rule.suppresses:
                    suppressed_rule_ids[sup_id] = rule.id

                # Calculate deterministic risk score & level
                risk_level, risk_score = RiskAssessor.calculate_risk(
                    base_score=rule.base_risk_score,
                    target_rule_level=rule.risk_level,
                    evidence=evidence_items,
                    observation_confidence=obs.confidence,
                    motionless_duration_seconds=sm.motionless_duration_seconds,
                    is_nighttime=ctx.current_hour >= 22 or ctx.current_hour < 6,
                )

                # Context summary for explanation
                context_data = {
                    "person_id": sm.person_id,
                    "activity_state": sm.current_state.value,
                    "zone_name": ctx.zone_name,
                    "room_type": ctx.room_type,
                    "current_hour": ctx.current_hour,
                    "peak_descent_velocity": sm.peak_descent_velocity,
                    "failed_standing_attempts": sm.failed_standing_attempts_count,
                    "motionless_duration_seconds": sm.motionless_duration_seconds,
                }

                explanation = ExplanationEngine.generate_explanation(
                    rule=rule,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    evidence=evidence_items,
                    context_data=context_data,
                )

                event = {
                    "event_type": rule.id,
                    "rule_name": rule.name,
                    "person_id": sm.person_id,
                    "timestamp": now,
                    "risk_level": risk_level.value,
                    "risk_score": risk_score,
                    "triggered_rules": [rule.id],
                    "evidence": [item.__dict__ for item in evidence_items],
                    "activity_sequence": [s.value for s in sm.state_sequence],
                    "current_activity": sm.current_state.value,
                    "confidence": obs.confidence,
                    "explanation": explanation,
                    "recommended_action": rule.recommended_action,
                }
                generated_events.append(event)

        return generated_events
