"""
Data models for the Rule Extraction Agent.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class ActionType(Enum):
    """Available rule action types."""
    MAKE_VISIBLE = "MAKE_VISIBLE"
    MAKE_INVISIBLE = "MAKE_INVISIBLE"
    MAKE_MANDATORY = "MAKE_MANDATORY"
    MAKE_NON_MANDATORY = "MAKE_NON_MANDATORY"
    MAKE_DISABLED = "MAKE_DISABLED"
    MAKE_ENABLED = "MAKE_ENABLED"
    VERIFY = "VERIFY"
    OCR = "OCR"
    EXT_DROP_DOWN = "EXT_DROP_DOWN"
    EXT_VALUE = "EXT_VALUE"
    COPY_TO = "COPY_TO"
    CLEAR_FIELD = "CLEAR_FIELD"
    CONVERT_TO = "CONVERT_TO"
    EXECUTE = "EXECUTE"


class ProcessingType(Enum):
    """Rule processing type."""
    CLIENT = "CLIENT"
    SERVER = "SERVER"


class ReferenceType(Enum):
    """Types of field references in logic."""
    VISIBILITY = "visibility_condition"
    MANDATORY = "mandatory_condition"
    DATA_SOURCE = "data_source"
    CROSS_VALIDATION = "cross_validation"
    DROPDOWN_FILTER = "dropdown_filter"
    DERIVATION = "derivation"
    VALIDATION = "validation"
    OCR = "ocr"


class IdGenerator:
    """Generate sequential IDs starting from 1 for each object type."""

    def __init__(self):
        self.counters: Dict[str, int] = {}

    def next_id(self, id_type: str = 'rule') -> int:
        """Get next sequential ID for given type."""
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

    def reset(self, id_type: str = None):
        """Reset counter(s) to 0."""
        if id_type:
            self.counters[id_type] = 0
        else:
            self.counters = {}

    def current(self, id_type: str = 'rule') -> int:
        """Get current counter value without incrementing."""
        return self.counters.get(id_type, 0)


@dataclass
class Condition:
    """Represents a parsed condition from logic text."""
    field_name: str
    operator: str  # '==', '!=', 'IN', 'NOT_IN', '>', '<', '>=', '<='
    value: Any
    original_text: str = ""

    def to_expression(self, field_var: Optional[str] = None) -> str:
        """Convert condition to expression syntax."""
        var = field_var or f"__{self.field_name.lower().replace(' ', '_')}__"

        if self.operator in ['IN', 'NOT_IN']:
            values_str = ", ".join([f"'{v}'" for v in self.value]) if isinstance(self.value, list) else f"'{self.value}'"
            return f"vo({var}) {self.operator} [{values_str}]"
        else:
            return f"vo({var}) {self.operator} '{self.value}'"


@dataclass
class ParsedLogic:
    """Represents parsed logic from a field."""
    original_text: str
    keywords: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    field_refs: List[str] = field(default_factory=list)
    document_types: List[str] = field(default_factory=list)  # PAN, GSTIN, MSME, etc.
    is_visibility_rule: bool = False
    is_mandatory_rule: bool = False
    is_validation_rule: bool = False
    is_ocr_rule: bool = False
    is_disabled_rule: bool = False
    is_ext_dropdown_rule: bool = False
    should_skip: bool = False  # For expression/execute rules
    confidence: float = 0.0


@dataclass
class FieldInfo:
    """Information about a field from the schema."""
    id: int
    name: str
    variable_name: str
    field_type: str
    is_mandatory: bool = False
    logic: Optional[str] = None
    rules_text: Optional[str] = None
    panel_name: Optional[str] = None
    form_order: float = 0.0


@dataclass
class RuleSelection:
    """Result of rule selection from decision tree."""
    action_type: str
    source_type: Optional[str] = None
    schema_id: Optional[int] = None
    confidence: float = 0.0
    match_reason: str = ""
    needs_llm_fallback: bool = False
    possible_action_types: List[str] = field(default_factory=list)


@dataclass
class GeneratedRule:
    """A generated formFillRule."""
    id: int
    action_type: str
    processing_type: str = "CLIENT"
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    source_type: Optional[str] = None
    conditional_values: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # "IN" or "NOT_IN"
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    params: Optional[str] = None
    button: str = ""
    searchable: bool = False
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False
    on_status_fail: Optional[str] = None  # For GSTIN_WITH_PAN

    # Metadata for tracking
    field_name: Optional[str] = None
    confidence: float = 1.0
    match_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching expected JSON output."""
        result = {
            "id": self.id,
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": self.action_type,
            "processingType": self.processing_type,
            "sourceIds": self.source_ids,
            "destinationIds": self.destination_ids,
            "postTriggerRuleIds": self.post_trigger_rule_ids,
            "button": self.button,
            "searchable": self.searchable,
            "executeOnFill": self.execute_on_fill,
            "executeOnRead": self.execute_on_read,
            "executeOnEsign": self.execute_on_esign,
            "executePostEsign": self.execute_post_esign,
            "runPostConditionFail": self.run_post_condition_fail,
        }

        # Add conditional fields
        if self.source_type:
            result["sourceType"] = self.source_type

        if self.conditional_values:
            result["conditionalValues"] = self.conditional_values

        if self.condition:
            result["condition"] = self.condition
            result["conditionValueType"] = self.condition_value_type

        if self.params:
            result["params"] = self.params

        if self.on_status_fail:
            result["onStatusFail"] = self.on_status_fail

        return result


@dataclass
class VisibilityGroup:
    """Group of fields controlled by a single controlling field."""
    controlling_field_name: str
    controlling_field_id: Optional[int] = None
    destination_fields: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OCRVerifyChain:
    """Chain linking OCR rule to VERIFY rule."""
    ocr_field_name: str
    verify_field_name: str
    ocr_field_id: Optional[int] = None
    verify_field_id: Optional[int] = None
    ocr_source_type: str = ""
    verify_source_type: str = ""
    ocr_rule_id: Optional[int] = None
    verify_rule_id: Optional[int] = None


@dataclass
class ExtractionResult:
    """Result of the rule extraction process."""
    total_fields_processed: int = 0
    total_rules_generated: int = 0
    rules_by_type: Dict[str, int] = field(default_factory=dict)
    deterministic_matches: int = 0
    llm_fallbacks: int = 0
    skipped_fields: int = 0
    unmatched_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    populated_schema: Optional[Dict] = None

    def summary(self) -> str:
        """Generate a summary report."""
        lines = [
            "=" * 50,
            "Rule Extraction Summary",
            "=" * 50,
            f"Total fields processed: {self.total_fields_processed}",
            f"Total rules generated: {self.total_rules_generated}",
            f"Deterministic matches: {self.deterministic_matches}",
            f"LLM fallbacks: {self.llm_fallbacks}",
            f"Skipped fields: {self.skipped_fields}",
            "",
            "Rules by type:",
        ]

        for rule_type, count in sorted(self.rules_by_type.items()):
            lines.append(f"  {rule_type}: {count}")

        if self.unmatched_fields:
            lines.append(f"\nUnmatched fields: {len(self.unmatched_fields)}")

        if self.errors:
            lines.append(f"\nErrors: {len(self.errors)}")

        if self.warnings:
            lines.append(f"\nWarnings: {len(self.warnings)}")

        lines.append("=" * 50)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "total_fields_processed": self.total_fields_processed,
            "total_rules_generated": self.total_rules_generated,
            "rules_by_type": self.rules_by_type,
            "deterministic_matches": self.deterministic_matches,
            "llm_fallbacks": self.llm_fallbacks,
            "skipped_fields": self.skipped_fields,
            "unmatched_fields": self.unmatched_fields,
            "errors": self.errors,
            "warnings": self.warnings,
        }
