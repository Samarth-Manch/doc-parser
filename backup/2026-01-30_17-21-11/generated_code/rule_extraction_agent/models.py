"""
Data models for rule extraction agent.

Defines all data structures used throughout the rule extraction pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum


class ActionType(Enum):
    """Supported action types for formFillRules."""
    # Visibility rules
    MAKE_VISIBLE = "MAKE_VISIBLE"
    MAKE_INVISIBLE = "MAKE_INVISIBLE"
    SESSION_BASED_MAKE_VISIBLE = "SESSION_BASED_MAKE_VISIBLE"
    SESSION_BASED_MAKE_INVISIBLE = "SESSION_BASED_MAKE_INVISIBLE"

    # Mandatory rules
    MAKE_MANDATORY = "MAKE_MANDATORY"
    MAKE_NON_MANDATORY = "MAKE_NON_MANDATORY"
    SESSION_BASED_MAKE_MANDATORY = "SESSION_BASED_MAKE_MANDATORY"
    SESSION_BASED_MAKE_NON_MANDATORY = "SESSION_BASED_MAKE_NON_MANDATORY"

    # Editability rules
    MAKE_DISABLED = "MAKE_DISABLED"
    MAKE_ENABLED = "MAKE_ENABLED"

    # Validation rules
    VERIFY = "VERIFY"
    OCR = "OCR"

    # Data operations
    COPY_TO = "COPY_TO"
    CLEAR_FIELD = "CLEAR_FIELD"
    EXECUTE = "EXECUTE"
    SET_DATE = "SET_DATE"
    CONVERT_TO = "CONVERT_TO"

    # External data
    EXT_VALUE = "EXT_VALUE"
    EXT_DROP_DOWN = "EXT_DROP_DOWN"

    # Special
    DUMMY_ACTION = "DUMMY_ACTION"
    COPY_TXNID_TO_FORM_FILL = "COPY_TXNID_TO_FORM_FILL"
    COPY_TO_TRANSACTION_ATTR3 = "COPY_TO_TRANSACTION_ATTR3"


class ConditionType(Enum):
    """Condition types for rule evaluation."""
    IN = "IN"
    NOT_IN = "NOT_IN"
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"


class DependencyType(Enum):
    """Types of field dependencies."""
    VISIBILITY = "visibility"
    MANDATORY = "mandatory"
    VISIBILITY_AND_MANDATORY = "visibility_and_mandatory"
    EDITABILITY = "editability"
    DATA_POPULATION = "data_population"
    VALIDATION = "validation"
    DROPDOWN_CASCADE = "dropdown_cascade"
    VALUE_DERIVATION = "value_derivation"
    CONDITIONAL_DEFAULT = "conditional_default"


@dataclass
class Condition:
    """Represents a parsed conditional expression."""
    field_name: str
    operator: str  # IN, NOT_IN, ==, !=, etc.
    value: str
    value_type: str = "TEXT"  # TEXT, NUMBER, EXPR

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "operator": self.operator,
            "value": self.value,
            "value_type": self.value_type,
        }


@dataclass
class ParsedLogic:
    """Represents parsed logic text with extracted components."""
    original_text: str
    keywords: List[str] = field(default_factory=list)
    action_types: List[str] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    field_references: List[str] = field(default_factory=list)
    document_type: Optional[str] = None  # PAN, GSTIN, etc.
    is_conditional: bool = False
    has_else_branch: bool = False
    positive_actions: List[str] = field(default_factory=list)  # Actions when condition is true
    negative_actions: List[str] = field(default_factory=list)  # Actions when condition is false
    confidence: float = 0.0
    skip_reason: Optional[str] = None  # If logic should be skipped

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "keywords": self.keywords,
            "action_types": self.action_types,
            "conditions": [c.to_dict() for c in self.conditions],
            "field_references": self.field_references,
            "document_type": self.document_type,
            "is_conditional": self.is_conditional,
            "has_else_branch": self.has_else_branch,
            "positive_actions": self.positive_actions,
            "negative_actions": self.negative_actions,
            "confidence": self.confidence,
            "skip_reason": self.skip_reason,
        }


@dataclass
class FieldInfo:
    """Information about a field in the schema."""
    id: int
    name: str
    variable_name: str
    field_type: str
    panel_name: Optional[str] = None
    mandatory: bool = False
    editable: bool = True
    visible: bool = True
    form_order: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "variable_name": self.variable_name,
            "field_type": self.field_type,
            "panel_name": self.panel_name,
            "mandatory": self.mandatory,
            "editable": self.editable,
            "visible": self.visible,
            "form_order": self.form_order,
        }


@dataclass
class RuleMatch:
    """Result of matching logic to a rule type."""
    action_type: str
    source_type: Optional[str] = None
    schema_id: Optional[int] = None
    confidence: float = 0.0
    matched_pattern: Optional[str] = None
    requires_llm: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "source_type": self.source_type,
            "schema_id": self.schema_id,
            "confidence": self.confidence,
            "matched_pattern": self.matched_pattern,
            "requires_llm": self.requires_llm,
        }


@dataclass
class GeneratedRule:
    """A generated formFillRule ready for JSON output."""
    action_type: str
    processing_type: str = "CLIENT"
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    condition: str = "IN"
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    source_type: Optional[str] = None
    params: Optional[str] = None
    button: str = ""
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False
    searchable: bool = False
    rule_id: Optional[int] = None  # Generated rule ID

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict matching formFillRules format."""
        result = {
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

        # Add rule ID if present
        if self.rule_id is not None:
            result["id"] = self.rule_id

        if self.conditional_values:
            result["conditionalValues"] = self.conditional_values
            result["condition"] = self.condition
            result["conditionValueType"] = self.condition_value_type

        if self.source_type:
            result["sourceType"] = self.source_type

        if self.params:
            result["params"] = self.params

        return result


@dataclass
class ExtractionResult:
    """Result of rule extraction for a single field."""
    field_id: int
    field_name: str
    logic_text: str
    parsed_logic: Optional[ParsedLogic] = None
    generated_rules: List[GeneratedRule] = field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None
    confidence: float = 0.0
    used_llm: bool = False
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_name": self.field_name,
            "logic_text": self.logic_text,
            "parsed_logic": self.parsed_logic.to_dict() if self.parsed_logic else None,
            "generated_rules": [r.to_dict() for r in self.generated_rules],
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "confidence": self.confidence,
            "used_llm": self.used_llm,
            "errors": self.errors,
        }


@dataclass
class RuleSchemaInfo:
    """Information about a rule schema from Rule-Schemas.json."""
    id: int
    name: str
    source: str
    action: str
    processing_type: str = "SERVER"
    source_fields: List[Dict[str, Any]] = field(default_factory=list)
    destination_fields: List[Dict[str, Any]] = field(default_factory=list)
    num_destination_items: int = 0
    button: str = ""
    params: Optional[Dict[str, Any]] = None

    def get_destination_ordinal_map(self) -> Dict[str, int]:
        """Get mapping of destination field names to ordinal positions."""
        return {f["name"]: f["ordinal"] for f in self.destination_fields}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "action": self.action,
            "processing_type": self.processing_type,
            "source_fields": self.source_fields,
            "destination_fields": self.destination_fields,
            "num_destination_items": self.num_destination_items,
            "button": self.button,
        }


@dataclass
class ExtractionSummary:
    """Summary statistics for rule extraction run."""
    total_fields: int = 0
    fields_with_logic: int = 0
    fields_processed: int = 0
    fields_skipped: int = 0
    total_rules_generated: int = 0
    rules_by_action_type: Dict[str, int] = field(default_factory=dict)
    deterministic_matches: int = 0
    llm_fallback_used: int = 0
    average_confidence: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_fields": self.total_fields,
            "fields_with_logic": self.fields_with_logic,
            "fields_processed": self.fields_processed,
            "fields_skipped": self.fields_skipped,
            "total_rules_generated": self.total_rules_generated,
            "rules_by_action_type": self.rules_by_action_type,
            "deterministic_matches": self.deterministic_matches,
            "llm_fallback_used": self.llm_fallback_used,
            "average_confidence": self.average_confidence,
            "errors": self.errors,
        }
