"""
Data models for the Eval framework.

Contains dataclasses for evaluation results, comparisons, and reports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class DiscrepancyType(Enum):
    """Types of discrepancies found during evaluation."""
    FIELD_MISSING = "field_missing"
    FIELD_TYPE_MISMATCH = "field_type_mismatch"
    FIELD_NAME_MISMATCH = "field_name_mismatch"
    RULE_MISSING = "rule_missing"
    RULE_EXTRA = "rule_extra"
    RULE_ACTION_TYPE_MISMATCH = "rule_action_type_mismatch"
    RULE_SOURCE_ID_MISMATCH = "rule_source_id_mismatch"
    RULE_DESTINATION_ID_MISMATCH = "rule_destination_id_mismatch"
    RULE_CONDITION_MISMATCH = "rule_condition_mismatch"
    RULE_CONDITIONAL_VALUES_MISMATCH = "rule_conditional_values_mismatch"
    RULE_PARAMS_MISMATCH = "rule_params_mismatch"
    POST_TRIGGER_RULE_MISSING = "post_trigger_rule_missing"
    POST_TRIGGER_RULE_WRONG_FIELD = "post_trigger_rule_wrong_field"
    SCHEMA_STRUCTURE_ERROR = "schema_structure_error"


class DiscrepancySeverity(Enum):
    """Severity levels for discrepancies."""
    CRITICAL = "critical"  # Blocks functionality
    HIGH = "high"  # Major issue
    MEDIUM = "medium"  # Notable issue
    LOW = "low"  # Minor issue
    INFO = "info"  # Informational only


@dataclass
class Discrepancy:
    """A single discrepancy found during evaluation."""
    type: DiscrepancyType
    severity: DiscrepancySeverity
    field_name: Optional[str]
    rule_id: Optional[int]
    message: str
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    fix_instruction: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "field_name": self.field_name,
            "rule_id": self.rule_id,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "fix_instruction": self.fix_instruction,
        }


@dataclass
class FieldMatch:
    """Result of matching a field name."""
    is_match: bool
    match_type: str  # "exact", "llm", "no_match"
    confidence: float  # 0.0 to 1.0
    generated_name: str
    reference_name: str
    llm_reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_match": self.is_match,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "generated_name": self.generated_name,
            "reference_name": self.reference_name,
            "llm_reasoning": self.llm_reasoning,
        }


@dataclass
class FieldComparison:
    """Result of comparing two fields."""
    generated_field_id: int
    reference_field_id: int
    generated_field_name: str
    reference_field_name: str
    name_match: FieldMatch
    type_match: bool
    generated_type: str
    reference_type: str
    is_panel: bool
    rules_compared: bool = False
    rule_comparison_result: Optional["RuleComparison"] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "generated_field_id": self.generated_field_id,
            "reference_field_id": self.reference_field_id,
            "generated_field_name": self.generated_field_name,
            "reference_field_name": self.reference_field_name,
            "name_match": self.name_match.to_dict(),
            "type_match": self.type_match,
            "generated_type": self.generated_type,
            "reference_type": self.reference_type,
            "is_panel": self.is_panel,
            "rules_compared": self.rules_compared,
        }
        if self.rule_comparison_result:
            result["rule_comparison_result"] = self.rule_comparison_result.to_dict()
        return result


@dataclass
class IdResolution:
    """Result of resolving an ID to its corresponding field."""
    original_id: int
    resolved_field_name: Optional[str]
    resolved_field_type: Optional[str]
    is_valid: bool
    source_json: str  # "generated" or "reference"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_id": self.original_id,
            "resolved_field_name": self.resolved_field_name,
            "resolved_field_type": self.resolved_field_type,
            "is_valid": self.is_valid,
            "source_json": self.source_json,
            "error": self.error,
        }


@dataclass
class RuleEvalResult:
    """Result of evaluating a single rule."""
    generated_rule_id: Optional[int]
    reference_rule_id: Optional[int]
    action_type: str
    action_type_match: bool
    source_ids_match: bool
    destination_ids_match: bool
    condition_match: bool
    conditional_values_match: bool
    params_match: bool
    post_trigger_rules_match: bool
    is_match: bool
    discrepancies: List[Discrepancy] = field(default_factory=list)

    # Detailed resolution info
    source_id_resolutions: List[Tuple[IdResolution, IdResolution]] = field(default_factory=list)
    destination_id_resolutions: List[Tuple[IdResolution, IdResolution]] = field(default_factory=list)
    post_trigger_rule_checks: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_rule_id": self.generated_rule_id,
            "reference_rule_id": self.reference_rule_id,
            "action_type": self.action_type,
            "action_type_match": self.action_type_match,
            "source_ids_match": self.source_ids_match,
            "destination_ids_match": self.destination_ids_match,
            "condition_match": self.condition_match,
            "conditional_values_match": self.conditional_values_match,
            "params_match": self.params_match,
            "post_trigger_rules_match": self.post_trigger_rules_match,
            "is_match": self.is_match,
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "source_id_resolutions": [
                (gen.to_dict(), ref.to_dict())
                for gen, ref in self.source_id_resolutions
            ],
            "destination_id_resolutions": [
                (gen.to_dict(), ref.to_dict())
                for gen, ref in self.destination_id_resolutions
            ],
            "post_trigger_rule_checks": self.post_trigger_rule_checks,
        }


@dataclass
class RuleComparison:
    """Result of comparing rules between two fields."""
    field_name: str
    total_generated_rules: int
    total_reference_rules: int
    matched_rules: int
    missing_rules: int  # In reference but not in generated
    extra_rules: int  # In generated but not in reference
    rule_evaluations: List[RuleEvalResult] = field(default_factory=list)
    discrepancies: List[Discrepancy] = field(default_factory=list)

    @property
    def coverage_rate(self) -> float:
        if self.total_reference_rules == 0:
            return 1.0
        return self.matched_rules / self.total_reference_rules

    @property
    def accuracy_rate(self) -> float:
        if self.total_generated_rules == 0:
            return 1.0 if self.total_reference_rules == 0 else 0.0
        return self.matched_rules / self.total_generated_rules

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "total_generated_rules": self.total_generated_rules,
            "total_reference_rules": self.total_reference_rules,
            "matched_rules": self.matched_rules,
            "missing_rules": self.missing_rules,
            "extra_rules": self.extra_rules,
            "coverage_rate": self.coverage_rate,
            "accuracy_rate": self.accuracy_rate,
            "rule_evaluations": [r.to_dict() for r in self.rule_evaluations],
            "discrepancies": [d.to_dict() for d in self.discrepancies],
        }


@dataclass
class FieldEvalResult:
    """Complete evaluation result for a single field."""
    field_id: int
    field_name: str
    field_type: str
    is_matched: bool
    matched_reference_field_id: Optional[int]
    matched_reference_field_name: Optional[str]
    name_match_type: str  # "exact", "llm", "not_found"
    type_match: bool
    rule_comparison: Optional[RuleComparison]
    discrepancies: List[Discrepancy] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_name": self.field_name,
            "field_type": self.field_type,
            "is_matched": self.is_matched,
            "matched_reference_field_id": self.matched_reference_field_id,
            "matched_reference_field_name": self.matched_reference_field_name,
            "name_match_type": self.name_match_type,
            "type_match": self.type_match,
            "rule_comparison": self.rule_comparison.to_dict() if self.rule_comparison else None,
            "discrepancies": [d.to_dict() for d in self.discrepancies],
        }


@dataclass
class EvalResult:
    """Overall evaluation result."""
    passed: bool
    overall_score: float
    field_coverage: float
    rule_coverage: float
    rule_accuracy: float

    total_generated_fields: int
    total_reference_fields: int
    matched_fields: int

    total_generated_rules: int
    total_reference_rules: int
    matched_rules: int

    field_evaluations: List[FieldEvalResult] = field(default_factory=list)
    all_discrepancies: List[Discrepancy] = field(default_factory=list)

    # Rule type breakdown
    rule_type_comparison: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "overall_score": self.overall_score,
            "field_coverage": self.field_coverage,
            "rule_coverage": self.rule_coverage,
            "rule_accuracy": self.rule_accuracy,
            "total_generated_fields": self.total_generated_fields,
            "total_reference_fields": self.total_reference_fields,
            "matched_fields": self.matched_fields,
            "total_generated_rules": self.total_generated_rules,
            "total_reference_rules": self.total_reference_rules,
            "matched_rules": self.matched_rules,
            "field_evaluations": [f.to_dict() for f in self.field_evaluations],
            "all_discrepancies": [d.to_dict() for d in self.all_discrepancies],
            "rule_type_comparison": self.rule_type_comparison,
        }


@dataclass
class SelfHealInstruction:
    """A single instruction for self-healing."""
    priority: int  # 1 = highest
    category: str  # e.g., "missing_rule", "id_mismatch", "type_error"
    action: str  # What to do
    field_name: Optional[str]
    rule_type: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority": self.priority,
            "category": self.category,
            "action": self.action,
            "field_name": self.field_name,
            "rule_type": self.rule_type,
            "details": self.details,
        }


@dataclass
class EvalReport:
    """Complete evaluation report with self-heal instructions."""
    eval_result: EvalResult
    timestamp: str
    generated_path: str
    reference_path: str
    threshold: float

    # Self-healing
    self_heal_instructions: List[SelfHealInstruction] = field(default_factory=list)
    priority_fixes: List[Dict[str, Any]] = field(default_factory=list)

    # Summary sections
    evaluation_summary: Dict[str, Any] = field(default_factory=dict)
    missing_rules_by_type: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    critical_checks: Dict[str, Any] = field(default_factory=dict)

    # LLM analysis
    llm_analysis: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eval_result": self.eval_result.to_dict(),
            "timestamp": self.timestamp,
            "generated_path": self.generated_path,
            "reference_path": self.reference_path,
            "threshold": self.threshold,
            "self_heal_instructions": [i.to_dict() for i in self.self_heal_instructions],
            "priority_fixes": self.priority_fixes,
            "evaluation_summary": self.evaluation_summary,
            "missing_rules_by_type": self.missing_rules_by_type,
            "critical_checks": self.critical_checks,
            "llm_analysis": self.llm_analysis,
        }

    @classmethod
    def create_from_eval_result(
        cls,
        eval_result: EvalResult,
        generated_path: str,
        reference_path: str,
        threshold: float
    ) -> "EvalReport":
        """Create an EvalReport from an EvalResult."""
        report = cls(
            eval_result=eval_result,
            timestamp=datetime.now().isoformat(),
            generated_path=generated_path,
            reference_path=reference_path,
            threshold=threshold,
        )

        # Build evaluation summary
        report.evaluation_summary = {
            "passed": eval_result.passed,
            "overall_score": eval_result.overall_score,
            "threshold": threshold,
            "field_coverage": eval_result.field_coverage,
            "rule_coverage": eval_result.rule_coverage,
            "rule_accuracy": eval_result.rule_accuracy,
            "total_discrepancies": len(eval_result.all_discrepancies),
            "critical_discrepancies": sum(
                1 for d in eval_result.all_discrepancies
                if d.severity == DiscrepancySeverity.CRITICAL
            ),
            "high_discrepancies": sum(
                1 for d in eval_result.all_discrepancies
                if d.severity == DiscrepancySeverity.HIGH
            ),
        }

        return report
