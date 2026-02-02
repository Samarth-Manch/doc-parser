"""
Rule Extraction Agent Module

This module provides automatic extraction of rules from BUD documents
and populates formFillRules arrays in the JSON schema.
"""

from .models import (
    IdGenerator,
    ParsedLogic,
    RuleSelection,
    FieldInfo,
    GeneratedRule
)
from .logic_parser import LogicParser
from .field_matcher import FieldMatcher
from .schema_lookup import RuleSchemaLookup
from .id_mapper import DestinationIdMapper
from .rule_builders import (
    BaseRuleBuilder,
    VerifyRuleBuilder,
    OcrRuleBuilder,
    VisibilityRuleBuilder,
    StandardRuleBuilder
)

__version__ = "1.0.0"
__all__ = [
    "IdGenerator",
    "ParsedLogic",
    "RuleSelection",
    "FieldInfo",
    "GeneratedRule",
    "LogicParser",
    "FieldMatcher",
    "RuleSchemaLookup",
    "DestinationIdMapper",
    "BaseRuleBuilder",
    "VerifyRuleBuilder",
    "OcrRuleBuilder",
    "VisibilityRuleBuilder",
    "StandardRuleBuilder"
]
