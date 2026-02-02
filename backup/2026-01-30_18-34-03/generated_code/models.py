"""
Data models for the rule extraction agent.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class ActionType(Enum):
    """Supported rule action types."""
    # Visibility
    MAKE_VISIBLE = "MAKE_VISIBLE"
    MAKE_INVISIBLE = "MAKE_INVISIBLE"

    # Mandatory
    MAKE_MANDATORY = "MAKE_MANDATORY"
    MAKE_NON_MANDATORY = "MAKE_NON_MANDATORY"

    # Editability
    MAKE_DISABLED = "MAKE_DISABLED"
    MAKE_ENABLED = "MAKE_ENABLED"

    # Session-based
    SESSION_BASED_MAKE_VISIBLE = "SESSION_BASED_MAKE_VISIBLE"
    SESSION_BASED_MAKE_INVISIBLE = "SESSION_BASED_MAKE_INVISIBLE"
    SESSION_BASED_MAKE_MANDATORY = "SESSION_BASED_MAKE_MANDATORY"
    SESSION_BASED_MAKE_NON_MANDATORY = "SESSION_BASED_MAKE_NON_MANDATORY"
    SESSION_BASED_MAKE_DISABLED = "SESSION_BASED_MAKE_DISABLED"
    SESSION_BASED_MAKE_ENABLED = "SESSION_BASED_MAKE_ENABLED"

    # Validation
    VERIFY = "VERIFY"
    OCR = "OCR"

    # Data operations
    COPY_TO = "COPY_TO"
    COPY_TXNID_TO_FORM_FILL = "COPY_TXNID_TO_FORM_FILL"
    CLEAR_FIELD = "CLEAR_FIELD"
    CONVERT_TO = "CONVERT_TO"

    # External data
    EXT_VALUE = "EXT_VALUE"
    EXT_DROP_DOWN = "EXT_DROP_DOWN"


class SourceType(Enum):
    """Source types for verification and OCR rules."""
    # PAN
    PAN_NUMBER = "PAN_NUMBER"
    PAN_IMAGE = "PAN_IMAGE"

    # GSTIN
    GSTIN = "GSTIN"
    GSTIN_IMAGE = "GSTIN_IMAGE"
    GSTIN_WITH_PAN = "GSTIN_WITH_PAN"

    # Bank
    BANK_ACCOUNT_NUMBER = "BANK_ACCOUNT_NUMBER"
    CHEQUEE = "CHEQUEE"

    # MSME
    MSME = "MSME"
    MSME_UDYAM_REG_NUMBER = "MSME_UDYAM_REG_NUMBER"

    # CIN
    CIN = "CIN"
    CIN_ID = "CIN_ID"

    # TAN
    TAN_NUMBER = "TAN_NUMBER"

    # Aadhaar
    AADHAR_IMAGE = "AADHAR_IMAGE"
    AADHAR_BACK_IMAGE = "AADHAR_BACK_IMAGE"

    # Case conversion
    UPPER_CASE = "UPPER_CASE"
    LOWER_CASE = "LOWER_CASE"


class Condition(Enum):
    """Condition operators."""
    IN = "IN"
    NOT_IN = "NOT_IN"
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"


class ProcessingType(Enum):
    """Processing type."""
    CLIENT = "CLIENT"
    SERVER = "SERVER"


@dataclass
class FieldInfo:
    """Information about a field."""
    id: int
    name: str
    variable_name: str
    field_type: str
    is_mandatory: bool = False
    logic: str = ""
    rules: str = ""
    section: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "variable_name": self.variable_name,
            "field_type": self.field_type,
            "is_mandatory": self.is_mandatory,
            "logic": self.logic,
            "rules": self.rules,
            "section": self.section,
        }


@dataclass
class ParsedCondition:
    """Represents a parsed condition from logic text."""
    field_name: str
    operator: str  # "==", "!=", "IN", "NOT_IN"
    values: List[str]

    def to_dict(self) -> Dict:
        return {
            "field_name": self.field_name,
            "operator": self.operator,
            "values": self.values,
        }


@dataclass
class ParsedLogic:
    """Result of parsing a logic statement."""
    original_text: str
    keywords: List[str]
    action_types: List[str]
    conditions: List[ParsedCondition]
    field_references: List[str]
    document_type: Optional[str] = None  # PAN, GSTIN, etc.
    is_ocr: bool = False
    is_verify: bool = False
    is_visibility: bool = False
    is_mandatory: bool = False
    is_disabled: bool = False
    is_ext_dropdown: bool = False  # External dropdown rule
    is_ext_value: bool = False  # External value lookup
    is_copy: bool = False  # Copy/derive rule
    is_session_based: bool = False  # Session-based rule (first/second party)
    is_document_rule: bool = False  # Document delete/undelete rule
    is_skip: bool = False  # True if this should be skipped (expression/execute rules)
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "original_text": self.original_text,
            "keywords": self.keywords,
            "action_types": self.action_types,
            "conditions": [c.to_dict() for c in self.conditions],
            "field_references": self.field_references,
            "document_type": self.document_type,
            "is_ocr": self.is_ocr,
            "is_verify": self.is_verify,
            "is_visibility": self.is_visibility,
            "is_mandatory": self.is_mandatory,
            "is_disabled": self.is_disabled,
            "is_ext_dropdown": self.is_ext_dropdown,
            "is_ext_value": self.is_ext_value,
            "is_copy": self.is_copy,
            "is_session_based": self.is_session_based,
            "is_document_rule": self.is_document_rule,
            "is_skip": self.is_skip,
            "confidence": self.confidence,
        }


@dataclass
class RuleSelection:
    """Selected rule type and configuration."""
    action_type: str
    source_type: Optional[str] = None
    processing_type: str = "CLIENT"
    condition: str = "IN"
    schema_id: Optional[int] = None
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "action_type": self.action_type,
            "source_type": self.source_type,
            "processing_type": self.processing_type,
            "condition": self.condition,
            "schema_id": self.schema_id,
            "confidence": self.confidence,
        }


@dataclass
class GeneratedRule:
    """A generated formFillRule."""
    id: Optional[int] = None
    create_user: str = "FIRST_PARTY"
    update_user: str = "FIRST_PARTY"
    action_type: str = ""
    source_type: Optional[str] = None
    processing_type: str = "CLIENT"
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    conditional_value_id: Optional[int] = None
    condition: str = "IN"
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    params: Optional[str] = None
    button: str = ""
    searchable: bool = False
    on_status_fail: Optional[str] = None
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary matching expected output format."""
        result = {
            "createUser": self.create_user,
            "updateUser": self.update_user,
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

        if self.id is not None:
            result["id"] = self.id

        if self.source_type:
            result["sourceType"] = self.source_type

        if self.conditional_values:
            result["conditionalValues"] = self.conditional_values
            result["condition"] = self.condition
            result["conditionValueType"] = self.condition_value_type

        if self.conditional_value_id is not None:
            result["conditionalValueId"] = self.conditional_value_id

        if self.params:
            result["params"] = self.params

        if self.on_status_fail:
            result["onStatusFail"] = self.on_status_fail

        return result


@dataclass
class MatchResult:
    """Result of matching logic to rules."""
    parsed_logic: ParsedLogic
    rule_selections: List[RuleSelection]
    source_field_id: Optional[int] = None
    destination_field_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    confidence: float = 0.0
    method: str = "deterministic"  # "deterministic" or "llm"

    def to_dict(self) -> Dict:
        return {
            "parsed_logic": self.parsed_logic.to_dict(),
            "rule_selections": [r.to_dict() for r in self.rule_selections],
            "source_field_id": self.source_field_id,
            "destination_field_ids": self.destination_field_ids,
            "conditional_values": self.conditional_values,
            "confidence": self.confidence,
            "method": self.method,
        }


@dataclass
class VisibilityGroup:
    """Group of fields controlled by a single source field for visibility."""
    source_field_name: str
    source_field_id: Optional[int] = None
    destinations: List[Dict] = field(default_factory=list)  # {"field_name", "field_id", "conditional_value", "action"}

    def to_dict(self) -> Dict:
        return {
            "source_field_name": self.source_field_name,
            "source_field_id": self.source_field_id,
            "destinations": self.destinations,
        }


@dataclass
class OcrVerifyChain:
    """Represents an OCR -> VERIFY chain."""
    ocr_source_field_id: int  # File upload field
    ocr_destination_field_id: int  # Text field (e.g., PAN number)
    verify_source_field_id: int  # Same as ocr_destination
    verify_destination_ids: List[int]  # Fields populated by verification
    ocr_source_type: str  # e.g., PAN_IMAGE
    verify_source_type: str  # e.g., PAN_NUMBER

    def to_dict(self) -> Dict:
        return {
            "ocr_source_field_id": self.ocr_source_field_id,
            "ocr_destination_field_id": self.ocr_destination_field_id,
            "verify_source_field_id": self.verify_source_field_id,
            "verify_destination_ids": self.verify_destination_ids,
            "ocr_source_type": self.ocr_source_type,
            "verify_source_type": self.verify_source_type,
        }
