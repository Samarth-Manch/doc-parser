"""Data models for rule extraction agent."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class DependencyType(str, Enum):
    """Types of field dependencies."""
    VISIBILITY = "visibility"
    VISIBILITY_MANDATORY = "visibility_mandatory"
    MANDATORY = "mandatory"
    VALUE_DERIVATION = "value_derivation"
    DROPDOWN_CASCADE = "dropdown_cascade"
    DATA_POPULATION = "data_population"
    VALIDATION = "validation"
    CONDITIONAL_BEHAVIOR = "conditional_behavior"


class ActionType(str, Enum):
    """Rule action types."""
    MAKE_VISIBLE = "MAKE_VISIBLE"
    MAKE_INVISIBLE = "MAKE_INVISIBLE"
    MAKE_MANDATORY = "MAKE_MANDATORY"
    MAKE_NON_MANDATORY = "MAKE_NON_MANDATORY"
    MAKE_DISABLED = "MAKE_DISABLED"
    MAKE_ENABLED = "MAKE_ENABLED"
    VERIFY = "VERIFY"
    OCR = "OCR"
    COPY_TO = "COPY_TO"
    EXT_DROP_DOWN = "EXT_DROP_DOWN"
    EXT_VALUE = "EXT_VALUE"
    VALIDATION = "VALIDATION"
    CONVERT_TO = "CONVERT_TO"
    CLEAR_FIELD = "CLEAR_FIELD"


@dataclass
class Condition:
    """Represents a conditional expression."""
    field: str
    operator: str  # '==', '!=', 'IN', 'NOT_IN'
    value: Any
    raw_text: str = ""

    def to_dict(self) -> Dict:
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
            "raw_text": self.raw_text,
        }


@dataclass
class ParsedLogic:
    """Result of parsing a logic statement."""
    raw_text: str
    keywords: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    condition: Optional[Condition] = None
    field_refs: List[str] = field(default_factory=list)
    doc_type: Optional[str] = None  # PAN, GSTIN, etc.
    confidence: float = 0.0
    should_skip: bool = False
    skip_reason: str = ""

    def to_dict(self) -> Dict:
        return {
            "raw_text": self.raw_text,
            "keywords": self.keywords,
            "actions": self.actions,
            "condition": self.condition.to_dict() if self.condition else None,
            "field_refs": self.field_refs,
            "doc_type": self.doc_type,
            "confidence": self.confidence,
            "should_skip": self.should_skip,
            "skip_reason": self.skip_reason,
        }


@dataclass
class FieldInfo:
    """Information about a field in the schema."""
    id: int
    name: str
    variable_name: str
    field_type: str
    panel_name: str = ""
    logic: str = ""
    rules: str = ""
    editable: bool = True
    mandatory: bool = False
    visible: bool = True

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "variable_name": self.variable_name,
            "field_type": self.field_type,
            "panel_name": self.panel_name,
            "logic": self.logic,
            "rules": self.rules,
            "editable": self.editable,
            "mandatory": self.mandatory,
            "visible": self.visible,
        }


@dataclass
class RuleSelection:
    """Result of rule selection from decision tree."""
    action_type: str
    source_type: Optional[str] = None
    schema_id: Optional[int] = None
    confidence: float = 0.0
    pattern_matched: str = ""
    needs_llm_fallback: bool = False

    def to_dict(self) -> Dict:
        return {
            "action_type": self.action_type,
            "source_type": self.source_type,
            "schema_id": self.schema_id,
            "confidence": self.confidence,
            "pattern_matched": self.pattern_matched,
            "needs_llm_fallback": self.needs_llm_fallback,
        }


@dataclass
class GeneratedRule:
    """A generated formFillRule."""
    id: int
    action_type: str
    processing_type: str = "CLIENT"
    source_type: Optional[str] = None
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    condition: str = ""
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    button: str = ""
    params: str = ""
    searchable: bool = False
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False

    def to_dict(self) -> Dict:
        """Convert to formFillRule JSON format."""
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

        if self.source_type:
            result["sourceType"] = self.source_type

        if self.conditional_values:
            result["conditionalValues"] = self.conditional_values
            result["condition"] = self.condition
            result["conditionValueType"] = self.condition_value_type

        if self.params:
            result["params"] = self.params

        return result


class IdGenerator:
    """Generate sequential IDs starting from 1 for each object type."""

    def __init__(self):
        self.counters: Dict[str, int] = {}

    def next_id(self, id_type: str = "rule") -> int:
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

    def current(self, id_type: str = "rule") -> int:
        """Get current ID without incrementing."""
        return self.counters.get(id_type, 0)


# Global ID generator instance
id_generator = IdGenerator()
