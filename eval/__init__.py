"""
Eval Framework for Document Parser

This framework provides comprehensive evaluation of generated JSON against reference JSON,
with intelligent field and rule comparison using a deterministic-first approach with LLM fallback.

Main components:
- models.py: Data classes for evaluation results
- field_comparator.py: Field name and type comparison
- rule_comparator.py: Rule comparison with ID resolution
- evaluator.py: Main evaluation orchestrator
- report_generator.py: LLM-based report generation
- llm_client.py: LLM client wrapper
"""

from .models import (
    EvalResult,
    FieldMatch,
    FieldComparison,
    RuleComparison,
    IdResolution,
    EvalReport,
    FieldEvalResult,
    RuleEvalResult,
    DiscrepancyType,
    DiscrepancySeverity,
    Discrepancy,
)
from .evaluator import FormFillEvaluator
from .field_comparator import FieldComparator
from .rule_comparator import RuleComparator
from .report_generator import ReportGenerator

__all__ = [
    # Models
    "EvalResult",
    "FieldMatch",
    "FieldComparison",
    "RuleComparison",
    "IdResolution",
    "EvalReport",
    "FieldEvalResult",
    "RuleEvalResult",
    "DiscrepancyType",
    "DiscrepancySeverity",
    "Discrepancy",
    # Components
    "FormFillEvaluator",
    "FieldComparator",
    "RuleComparator",
    "ReportGenerator",
]
