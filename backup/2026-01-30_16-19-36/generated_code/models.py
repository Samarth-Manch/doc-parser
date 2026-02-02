"""
Data models for rule extraction system.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ActionType(Enum):
    """Supported action types for formFillRules."""
    MAKE_VISIBLE = "MAKE_VISIBLE"
    MAKE_INVISIBLE = "MAKE_INVISIBLE"
    MAKE_MANDATORY = "MAKE_MANDATORY"
    MAKE_NON_MANDATORY = "MAKE_NON_MANDATORY"
    MAKE_DISABLED = "MAKE_DISABLED"
    MAKE_ENABLED = "MAKE_ENABLED"
    COPY_TO = "COPY_TO"
    CLEAR_FIELD = "CLEAR_FIELD"
    VERIFY_PAN = "VERIFY_PAN"
    VERIFY_GSTIN = "VERIFY_GSTIN"
    VERIFY_BANK = "VERIFY_BANK"
    VERIFY_MSME = "VERIFY_MSME"
    VERIFY_PINCODE = "VERIFY_PINCODE"
    OCR_PAN = "OCR_PAN"
    OCR_GSTIN = "OCR_GSTIN"
    OCR_AADHAAR = "OCR_AADHAAR"
    OCR_MSME = "OCR_MSME"


class ConditionOperator(Enum):
    """Condition operators for rule evaluation."""
    IN = "IN"
    NOT_IN = "NOT_IN"
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    CONTAINS = "CONTAINS"


class RelationshipType(Enum):
    """Types of field relationships from intra_panel_references."""
    VISIBILITY_CONTROL = "visibility_control"
    MANDATORY_CONTROL = "mandatory_control"
    VALUE_DERIVATION = "value_derivation"
    DATA_DEPENDENCY = "data_dependency"
    VALIDATION = "validation"
    ENABLE_DISABLE = "enable_disable"
    CONDITIONAL = "conditional"
    CLEAR_OPERATION = "clear_operation"
    OTHER = "other"


@dataclass
class Condition:
    """Represents a conditional expression in logic."""
    field_ref: str  # Field name or reference
    operator: ConditionOperator
    value: Any  # Can be string, number, list, etc.
    negated: bool = False  # For "NOT" conditions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_ref": self.field_ref,
            "operator": self.operator.value,
            "value": self.value,
            "negated": self.negated
        }


@dataclass
class ParsedLogic:
    """Structured representation of parsed logic text."""
    original_text: str
    keywords: List[str] = field(default_factory=list)
    action_types: List[ActionType] = field(default_factory=list)
    field_references: List[str] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    relationship_type: Optional[RelationshipType] = None

    # Extracted values
    conditional_values: List[str] = field(default_factory=list)
    has_if_else: bool = False
    is_ocr: bool = False
    is_validation: bool = False
    is_derivation: bool = False
    is_visibility: bool = False
    is_mandatory: bool = False
    is_editable: bool = False

    # Document/entity types mentioned
    document_types: List[str] = field(default_factory=list)  # PAN, GSTIN, MSME, etc.

    # Confidence score
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "keywords": self.keywords,
            "action_types": [a.value for a in self.action_types],
            "field_references": self.field_references,
            "conditions": [c.to_dict() for c in self.conditions],
            "relationship_type": self.relationship_type.value if self.relationship_type else None,
            "conditional_values": self.conditional_values,
            "has_if_else": self.has_if_else,
            "is_ocr": self.is_ocr,
            "is_validation": self.is_validation,
            "is_derivation": self.is_derivation,
            "is_visibility": self.is_visibility,
            "is_mandatory": self.is_mandatory,
            "is_editable": self.is_editable,
            "document_types": self.document_types,
            "confidence": self.confidence
        }


@dataclass
class FieldInfo:
    """Information about a field in the schema."""
    field_id: int
    field_name: str
    variable_name: str
    field_type: str
    panel_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "field_name": self.field_name,
            "variable_name": self.variable_name,
            "field_type": self.field_type,
            "panel_name": self.panel_name
        }


@dataclass
class RuleSelection:
    """Represents a selected rule to be generated."""
    action_type: ActionType
    source_field: Optional[FieldInfo]
    destination_fields: List[FieldInfo]
    conditional_values: List[str] = field(default_factory=list)
    condition_operator: ConditionOperator = ConditionOperator.IN
    processing_type: str = "CLIENT"  # CLIENT or SERVER
    confidence: float = 1.0

    # Additional metadata
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "source_field": self.source_field.to_dict() if self.source_field else None,
            "destination_fields": [f.to_dict() for f in self.destination_fields],
            "conditional_values": self.conditional_values,
            "condition_operator": self.condition_operator.value,
            "processing_type": self.processing_type,
            "confidence": self.confidence,
            "execute_on_fill": self.execute_on_fill,
            "execute_on_read": self.execute_on_read,
            "execute_on_esign": self.execute_on_esign
        }


@dataclass
class GeneratedRule:
    """A complete formFillRule ready to be inserted into schema."""
    rule_id: int
    action_type: str
    processing_type: str
    source_ids: List[int]
    destination_ids: List[int]
    conditional_values: List[str]
    condition: str
    condition_value_type: str = "TEXT"
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False
    searchable: bool = False
    button: str = ""
    post_trigger_rule_ids: List[int] = field(default_factory=list)

    # Metadata
    create_user: str = "FIRST_PARTY"
    update_user: str = "FIRST_PARTY"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to formFillRule JSON format."""
        return {
            "id": self.rule_id,
            "createUser": self.create_user,
            "updateUser": self.update_user,
            "actionType": self.action_type,
            "processingType": self.processing_type,
            "sourceIds": self.source_ids,
            "destinationIds": self.destination_ids,
            "conditionalValues": self.conditional_values,
            "condition": self.condition,
            "conditionValueType": self.condition_value_type,
            "postTriggerRuleIds": self.post_trigger_rule_ids,
            "button": self.button,
            "searchable": self.searchable,
            "executeOnFill": self.execute_on_fill,
            "executeOnRead": self.execute_on_read,
            "executeOnEsign": self.execute_on_esign,
            "executePostEsign": self.execute_post_esign,
            "runPostConditionFail": self.run_post_condition_fail
        }


@dataclass
class IntraPanelReference:
    """Represents a field dependency from intra_panel_references.json."""
    source_field_name: str
    source_variable_name: str
    source_field_type: str
    target_field_name: str
    target_variable_name: str
    target_field_type: str
    relationship_type: str
    operation_type: str
    raw_expression: str
    matched_text: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntraPanelReference':
        """Create from intra_panel_references.json structure."""
        source = data.get('source_field', {})
        target = data.get('target_field', {})
        ref_details = data.get('reference_details', {})

        return cls(
            source_field_name=source.get('field_name', ''),
            source_variable_name=source.get('variable_name', ''),
            source_field_type=source.get('field_type', ''),
            target_field_name=target.get('field_name', ''),
            target_variable_name=target.get('variable_name', ''),
            target_field_type=target.get('field_type', ''),
            relationship_type=ref_details.get('relationship_type', ''),
            operation_type=ref_details.get('operation_type', ''),
            raw_expression=ref_details.get('raw_expression', ''),
            matched_text=ref_details.get('matched_text', '')
        )
