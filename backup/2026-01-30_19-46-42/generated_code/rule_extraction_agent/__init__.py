"""
Rule Extraction Agent - Automatically extracts rules from BUD documents.

This module provides a hybrid approach for extracting form fill rules from BUD
(Business Use Documents) by combining deterministic pattern matching with
LLM fallback for complex logic statements.
"""

from .models import (
    ParsedLogic,
    Condition,
    RuleMatch,
    GeneratedRule,
    FieldInfo,
    RuleChain,
)
from .schema_lookup import RuleSchemaLookup
from .id_mapper import DestinationIdMapper
from .logic_parser import LogicParser
from .field_matcher import FieldMatcher
from .pipeline import RuleExtractionPipeline

__all__ = [
    'ParsedLogic',
    'Condition',
    'RuleMatch',
    'GeneratedRule',
    'FieldInfo',
    'RuleChain',
    'RuleSchemaLookup',
    'DestinationIdMapper',
    'LogicParser',
    'FieldMatcher',
    'RuleExtractionPipeline',
]
