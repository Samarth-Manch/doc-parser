"""
Data models for rule extraction agent.

This module defines the core data structures used throughout the rule extraction process.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class IdGenerator:
    """
    Generate sequential IDs starting from 1 for each object type.

    All IDs in the generated JSON MUST be sequential integers starting from 1.
    This applies to rule IDs, field IDs, template IDs, etc.
    """

    def __init__(self):
        self.counters: Dict[str, int] = {}

    def next_id(self, id_type: str = 'rule') -> int:
        """Get next sequential ID for given type."""
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

    def current_id(self, id_type: str = 'rule') -> int:
        """Get current ID without incrementing."""
        return self.counters.get(id_type, 0)

    def reset(self, id_type: str = None):
        """Reset counter(s) to 0."""
        if id_type:
            self.counters[id_type] = 0
        else:
            self.counters = {}


class ActionType(str, Enum):
    """Enum of rule action types."""
    MAKE_VISIBLE = "MAKE_VISIBLE"
    MAKE_INVISIBLE = "MAKE_INVISIBLE"
    MAKE_MANDATORY = "MAKE_MANDATORY"
    MAKE_NON_MANDATORY = "MAKE_NON_MANDATORY"
    MAKE_DISABLED = "MAKE_DISABLED"
    MAKE_ENABLED = "MAKE_ENABLED"
    VERIFY = "VERIFY"
    OCR = "OCR"
    COPY_TO = "COPY_TO"
    CONVERT_TO = "CONVERT_TO"
    CLEAR_FIELD = "CLEAR_FIELD"
    EXT_DROP_DOWN = "EXT_DROP_DOWN"
    EXT_VALUE = "EXT_VALUE"
    EXECUTE = "EXECUTE"
    SESSION_BASED_MAKE_VISIBLE = "SESSION_BASED_MAKE_VISIBLE"
    SESSION_BASED_MAKE_INVISIBLE = "SESSION_BASED_MAKE_INVISIBLE"
    SESSION_BASED_MAKE_MANDATORY = "SESSION_BASED_MAKE_MANDATORY"
    SESSION_BASED_MAKE_NON_MANDATORY = "SESSION_BASED_MAKE_NON_MANDATORY"
    SESSION_BASED_MAKE_DISABLED = "SESSION_BASED_MAKE_DISABLED"
    SESSION_BASED_MAKE_ENABLED = "SESSION_BASED_MAKE_ENABLED"


class ProcessingType(str, Enum):
    """Rule processing type."""
    CLIENT = "CLIENT"
    SERVER = "SERVER"


class ConditionType(str, Enum):
    """Condition operators."""
    IN = "IN"
    NOT_IN = "NOT_IN"


@dataclass
class FieldInfo:
    """Information about a field in the schema."""
    id: int
    name: str
    variable_name: str
    field_type: str
    logic: Optional[str] = None
    rules: Optional[str] = None
    panel_name: Optional[str] = None
    is_mandatory: bool = False
    form_order: float = 0.0


@dataclass
class ParsedLogic:
    """Parsed representation of a logic statement."""
    original_text: str
    keywords: List[str] = field(default_factory=list)
    action_types: List[str] = field(default_factory=list)
    source_field_name: Optional[str] = None
    destination_field_names: List[str] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # "IN" or "NOT_IN"
    document_type: Optional[str] = None  # PAN, GSTIN, etc.
    confidence: float = 0.0
    is_verify_destination: bool = False  # True if field receives data from validation
    should_skip: bool = False  # True for expression/execute rules


@dataclass
class RuleSelection:
    """Selected rule type and configuration."""
    action_type: str
    source_type: Optional[str] = None
    schema_id: Optional[int] = None
    confidence: float = 0.0
    processing_type: str = "CLIENT"
    requires_ordinal_mapping: bool = False
    destination_ordinals: Optional[Dict[str, int]] = None


@dataclass
class GeneratedRule:
    """A fully generated rule ready for JSON output."""
    id: int
    action_type: str
    source_ids: List[int]
    destination_ids: List[int] = field(default_factory=list)
    processing_type: str = "CLIENT"
    source_type: Optional[str] = None
    conditional_values: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    condition_value_type: Optional[str] = None
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
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
            "runPostConditionFail": self.run_post_condition_fail
        }

        if self.source_type:
            result["sourceType"] = self.source_type

        if self.conditional_values:
            result["conditionalValues"] = self.conditional_values

        if self.condition:
            result["condition"] = self.condition

        if self.condition_value_type:
            result["conditionValueType"] = self.condition_value_type

        if self.params:
            result["params"] = self.params

        if self.on_status_fail:
            result["onStatusFail"] = self.on_status_fail

        return result


@dataclass
class VisibilityGroup:
    """Group of fields controlled by a single source field."""
    source_field_name: str
    source_field_id: Optional[int] = None
    destinations: List[Dict[str, Any]] = field(default_factory=list)
    # Each destination has: field_name, field_id, conditional_value, action_type


@dataclass
class OcrVerifyChain:
    """Chain of OCR -> VERIFY rules."""
    ocr_source_type: str
    verify_source_type: Optional[str]
    upload_field_id: int
    upload_field_name: str
    text_field_id: Optional[int] = None
    text_field_name: Optional[str] = None
    ocr_rule_id: Optional[int] = None
    verify_rule_id: Optional[int] = None


# Mapping of OCR source types to VERIFY source types
OCR_TO_VERIFY_MAPPING = {
    "PAN_IMAGE": "PAN_NUMBER",
    "GSTIN_IMAGE": "GSTIN",
    "CHEQUEE": "BANK_ACCOUNT_NUMBER",
    "MSME": "MSME_UDYAM_REG_NUMBER",
    "CIN": "CIN_ID",
    "AADHAR_IMAGE": None,  # Aadhaar Front - no VERIFY chain
    "AADHAR_BACK_IMAGE": None,  # Aadhaar Back - no VERIFY chain
}

# Mapping of document types to VERIFY source types
DOCUMENT_TO_VERIFY_SOURCE = {
    "pan": "PAN_NUMBER",
    "gstin": "GSTIN",
    "gst": "GSTIN",
    "bank": "BANK_ACCOUNT_NUMBER",
    "ifsc": "BANK_ACCOUNT_NUMBER",
    "msme": "MSME_UDYAM_REG_NUMBER",
    "udyam": "MSME_UDYAM_REG_NUMBER",
    "cin": "CIN_ID",
    "tan": "TAN_NUMBER",
    "fssai": "FSSAI",
}

# Mapping of document types to OCR source types
DOCUMENT_TO_OCR_SOURCE = {
    "pan": "PAN_IMAGE",
    "gstin": "GSTIN_IMAGE",
    "gst": "GSTIN_IMAGE",
    "aadhaar_front": "AADHAR_IMAGE",
    "aadhaar_back": "AADHAR_BACK_IMAGE",
    "aadhaar": "AADHAR_IMAGE",
    "aadhar": "AADHAR_IMAGE",
    "cheque": "CHEQUEE",
    "cancelled_cheque": "CHEQUEE",
    "cin": "CIN",
    "msme": "MSME",
    "udyam": "MSME",
}

# Schema IDs for VERIFY rules
VERIFY_SCHEMA_IDS = {
    "PAN_NUMBER": 360,
    "GSTIN": 355,
    "BANK_ACCOUNT_NUMBER": 361,
    "MSME_UDYAM_REG_NUMBER": 337,
    "CIN_ID": 349,
    "TAN_NUMBER": 322,
    "FSSAI": 356,
}

# Schema IDs for OCR rules
OCR_SCHEMA_IDS = {
    "PAN_IMAGE": 344,
    "GSTIN_IMAGE": 347,
    "AADHAR_IMAGE": 359,
    "AADHAR_BACK_IMAGE": 348,
    "CHEQUEE": 269,
    "MSME": 214,
    "CIN": None,  # Not in schemas
}
