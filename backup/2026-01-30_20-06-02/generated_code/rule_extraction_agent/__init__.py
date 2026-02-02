"""
Rule Extraction Agent - Extract rules from BUD logic and populate formFillRules.

This module provides a complete rule extraction system that:
1. Parses BUD document using doc_parser
2. Extracts natural language logic from each field
3. Uses deterministic pattern matching for common rule types
4. Falls back to LLM for complex logic
5. Generates formFillRules JSON matching the reference format

Usage:
    from rule_extraction_agent import RuleExtractionAgent

    agent = RuleExtractionAgent(
        bud_path="documents/Vendor Creation Sample BUD.docx",
        schema_path="rules/Rule-Schemas.json"
    )
    populated_schema = agent.extract_and_populate()
"""

from .models import (
    ActionType,
    SourceType,
    ProcessingType,
    Condition,
    FieldInfo,
    RuleSchema,
    ParsedLogic,
    ParsedCondition,
    GeneratedRule,
    ExtractionResult,
    ExtractionSummary,
)

from .schema_lookup import RuleSchemaLookup, get_verify_source_for_ocr
from .logic_parser import LogicParser, extract_controlling_field_name
from .field_matcher import FieldMatcher, build_field_index_from_parsed

from .rule_builders import (
    BaseRuleBuilder,
    RuleIdGenerator,
    VisibilityRuleBuilder,
    VerifyRuleBuilder,
    OcrRuleBuilder,
    ExtDropdownRuleBuilder,
)

__version__ = "1.0.0"

__all__ = [
    # Models
    'ActionType',
    'SourceType',
    'ProcessingType',
    'Condition',
    'FieldInfo',
    'RuleSchema',
    'ParsedLogic',
    'ParsedCondition',
    'GeneratedRule',
    'ExtractionResult',
    'ExtractionSummary',

    # Components
    'RuleSchemaLookup',
    'LogicParser',
    'FieldMatcher',

    # Builders
    'BaseRuleBuilder',
    'RuleIdGenerator',
    'VisibilityRuleBuilder',
    'VerifyRuleBuilder',
    'OcrRuleBuilder',
    'ExtDropdownRuleBuilder',

    # Utilities
    'get_verify_source_for_ocr',
    'extract_controlling_field_name',
    'build_field_index_from_parsed',
]
