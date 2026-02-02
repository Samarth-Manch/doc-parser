"""
Rule Extraction Agent

A complete rule extraction system that automatically extracts rules from BUD
logic/rules sections and populates formFillRules arrays in the JSON schema.

Uses a hybrid approach: deterministic pattern-based extraction for common cases
with LLM fallback for complex logic statements.
"""

from .models import (
    ParsedLogic,
    Condition,
    RuleMatch,
    GeneratedRule,
    FieldInfo,
    ExtractionResult,
)
from .logic_parser import LogicParser
from .schema_lookup import RuleSchemaLookup
from .id_mapper import DestinationIdMapper
from .field_matcher import FieldMatcher
from .rule_tree import RuleSelectionTree

__version__ = "1.0.0"
__all__ = [
    "ParsedLogic",
    "Condition",
    "RuleMatch",
    "GeneratedRule",
    "FieldInfo",
    "ExtractionResult",
    "LogicParser",
    "RuleSchemaLookup",
    "DestinationIdMapper",
    "FieldMatcher",
    "RuleSelectionTree",
]
