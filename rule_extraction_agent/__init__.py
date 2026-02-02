"""Rule Extraction Agent - Extracts formFillRules from BUD logic/rules sections."""

from .models import (
    ParsedLogic,
    Condition,
    RuleSelection,
    GeneratedRule,
    FieldInfo,
)
from .schema_lookup import RuleSchemaLookup
from .id_mapper import DestinationIdMapper
from .field_matcher import FieldMatcher
from .logic_parser import LogicParser
from .main import RuleExtractionAgent
from .enhanced_main import EnhancedRuleExtractionAgent

# Alias for backward compatibility - USE ENHANCED VERSION BY DEFAULT
RuleExtractionPipeline = EnhancedRuleExtractionAgent

__all__ = [
    "ParsedLogic",
    "Condition",
    "RuleSelection",
    "GeneratedRule",
    "FieldInfo",
    "RuleSchemaLookup",
    "DestinationIdMapper",
    "FieldMatcher",
    "LogicParser",
    "RuleExtractionAgent",
    "EnhancedRuleExtractionAgent",
    "RuleExtractionPipeline",
]
