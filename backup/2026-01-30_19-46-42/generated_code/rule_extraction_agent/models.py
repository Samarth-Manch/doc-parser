"""
Data models for the rule extraction agent.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


class ActionType(Enum):
    """Rule action types."""
    # Visibility
    MAKE_VISIBLE = "MAKE_VISIBLE"
    MAKE_INVISIBLE = "MAKE_INVISIBLE"
    SESSION_BASED_MAKE_VISIBLE = "SESSION_BASED_MAKE_VISIBLE"
    SESSION_BASED_MAKE_INVISIBLE = "SESSION_BASED_MAKE_INVISIBLE"

    # Mandatory
    MAKE_MANDATORY = "MAKE_MANDATORY"
    MAKE_NON_MANDATORY = "MAKE_NON_MANDATORY"
    SESSION_BASED_MAKE_MANDATORY = "SESSION_BASED_MAKE_MANDATORY"
    SESSION_BASED_MAKE_NON_MANDATORY = "SESSION_BASED_MAKE_NON_MANDATORY"

    # Editability
    MAKE_DISABLED = "MAKE_DISABLED"
    MAKE_ENABLED = "MAKE_ENABLED"

    # Validation
    VERIFY = "VERIFY"

    # OCR
    OCR = "OCR"

    # Data operations
    COPY_TO = "COPY_TO"
    CONVERT_TO = "CONVERT_TO"
    CLEAR_FIELD = "CLEAR_FIELD"
    SET_DATE = "SET_DATE"
    COPY_TXNID_TO_FORM_FILL = "COPY_TXNID_TO_FORM_FILL"
    COPY_TO_TRANSACTION_ATTR3 = "COPY_TO_TRANSACTION_ATTR3"

    # External data
    EXT_DROP_DOWN = "EXT_DROP_DOWN"
    EXT_VALUE = "EXT_VALUE"

    # Execute
    EXECUTE = "EXECUTE"

    # Unknown
    UNKNOWN = "UNKNOWN"


class SourceType(Enum):
    """Source types for rules."""
    # Verification
    PAN_NUMBER = "PAN_NUMBER"
    GSTIN = "GSTIN"
    GSTIN_WITH_PAN = "GSTIN_WITH_PAN"
    BANK_ACCOUNT_NUMBER = "BANK_ACCOUNT_NUMBER"
    MSME_UDYAM_REG_NUMBER = "MSME_UDYAM_REG_NUMBER"
    CIN_ID = "CIN_ID"
    TAN_NUMBER = "TAN_NUMBER"
    FSSAI = "FSSAI"

    # OCR
    PAN_IMAGE = "PAN_IMAGE"
    GSTIN_IMAGE = "GSTIN_IMAGE"
    AADHAR_IMAGE = "AADHAR_IMAGE"
    AADHAR_BACK_IMAGE = "AADHAR_BACK_IMAGE"
    CHEQUEE = "CHEQUEE"
    MSME = "MSME"
    CIN = "CIN"

    # Convert
    UPPER_CASE = "UPPER_CASE"
    LOWER_CASE = "LOWER_CASE"

    # Copy
    CREATED_BY = "CREATED_BY"
    FORM_FILL_METADATA = "FORM_FILL_METADATA"

    # External
    FORM_FILL_DROP_DOWN = "FORM_FILL_DROP_DOWN"
    EXTERNAL_DATA_VALUE = "EXTERNAL_DATA_VALUE"

    # None
    NONE = "NONE"


class ProcessingType(Enum):
    """Rule processing types."""
    CLIENT = "CLIENT"
    SERVER = "SERVER"


class ConditionType(Enum):
    """Condition types for rules."""
    IN = "IN"
    NOT_IN = "NOT_IN"
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"


@dataclass
class Condition:
    """Represents a parsed condition from logic text."""
    source_field_name: str
    operator: str  # e.g., "==", "!=", "in", "not_in"
    value: str
    value_list: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "source_field_name": self.source_field_name,
            "operator": self.operator,
            "value": self.value,
            "value_list": self.value_list,
        }


@dataclass
class ParsedLogic:
    """Result of parsing a logic statement."""
    original_text: str
    keywords: List[str] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)  # e.g., ["visible", "mandatory"]
    field_references: List[str] = field(default_factory=list)
    document_type: Optional[str] = None  # e.g., "PAN", "GSTIN", "Bank"
    is_ocr: bool = False
    is_verify: bool = False
    is_verify_destination: bool = False  # "Data will come from X validation"
    is_non_editable: bool = False
    should_skip: bool = False  # For expression/execute rules
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "original_text": self.original_text,
            "keywords": self.keywords,
            "conditions": [c.to_dict() for c in self.conditions],
            "actions": self.actions,
            "field_references": self.field_references,
            "document_type": self.document_type,
            "is_ocr": self.is_ocr,
            "is_verify": self.is_verify,
            "is_verify_destination": self.is_verify_destination,
            "is_non_editable": self.is_non_editable,
            "should_skip": self.should_skip,
            "confidence": self.confidence,
        }


@dataclass
class FieldInfo:
    """Information about a field."""
    id: int
    name: str
    variable_name: str
    field_type: str
    logic: str = ""
    rules: str = ""
    is_mandatory: bool = False
    section: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "variable_name": self.variable_name,
            "field_type": self.field_type,
            "logic": self.logic,
            "rules": self.rules,
            "is_mandatory": self.is_mandatory,
            "section": self.section,
        }


@dataclass
class RuleMatch:
    """Result of matching logic to a rule type."""
    action_type: ActionType
    source_type: Optional[SourceType] = None
    schema_id: Optional[int] = None
    confidence: float = 0.0
    matched_pattern: str = ""

    def to_dict(self) -> Dict:
        return {
            "action_type": self.action_type.value,
            "source_type": self.source_type.value if self.source_type else None,
            "schema_id": self.schema_id,
            "confidence": self.confidence,
            "matched_pattern": self.matched_pattern,
        }


@dataclass
class GeneratedRule:
    """A generated form fill rule."""
    id: int
    action_type: str
    processing_type: str = "CLIENT"
    source_type: Optional[str] = None
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    condition: Optional[str] = None
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
    on_status_fail: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary matching reference format."""
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

        if self.condition:
            result["condition"] = self.condition
            result["conditionValueType"] = self.condition_value_type

        if self.params:
            result["params"] = self.params

        if self.on_status_fail:
            result["onStatusFail"] = self.on_status_fail

        return result


@dataclass
class RuleChain:
    """Represents a chain of rules (e.g., OCR -> VERIFY)."""
    ocr_rule: Optional[GeneratedRule] = None
    verify_rule: Optional[GeneratedRule] = None
    cross_validation_rule: Optional[GeneratedRule] = None
    visibility_rules: List[GeneratedRule] = field(default_factory=list)

    def all_rules(self) -> List[GeneratedRule]:
        """Get all rules in the chain."""
        rules = []
        if self.ocr_rule:
            rules.append(self.ocr_rule)
        if self.verify_rule:
            rules.append(self.verify_rule)
        if self.cross_validation_rule:
            rules.append(self.cross_validation_rule)
        rules.extend(self.visibility_rules)
        return rules


@dataclass
class VisibilityGroup:
    """Group of fields controlled by a single source field."""
    source_field_name: str
    source_field_id: Optional[int] = None
    destinations: List[Dict] = field(default_factory=list)
    # Each destination: {field_name, field_id, conditional_value, action_type}

    def to_dict(self) -> Dict:
        return {
            "source_field_name": self.source_field_name,
            "source_field_id": self.source_field_id,
            "destinations": self.destinations,
        }


@dataclass
class RuleExtractionResult:
    """Complete result of rule extraction."""
    total_fields: int = 0
    fields_with_logic: int = 0
    rules_generated: int = 0
    skipped_expressions: int = 0
    ocr_rules: int = 0
    verify_rules: int = 0
    visibility_rules: int = 0
    mandatory_rules: int = 0
    disabled_rules: int = 0
    ext_dropdown_rules: int = 0
    other_rules: int = 0
    unmatched_fields: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total_fields": self.total_fields,
            "fields_with_logic": self.fields_with_logic,
            "rules_generated": self.rules_generated,
            "skipped_expressions": self.skipped_expressions,
            "ocr_rules": self.ocr_rules,
            "verify_rules": self.verify_rules,
            "visibility_rules": self.visibility_rules,
            "mandatory_rules": self.mandatory_rules,
            "disabled_rules": self.disabled_rules,
            "ext_dropdown_rules": self.ext_dropdown_rules,
            "other_rules": self.other_rules,
            "unmatched_fields": self.unmatched_fields,
            "errors": self.errors,
        }
