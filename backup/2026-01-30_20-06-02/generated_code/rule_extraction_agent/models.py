"""
Data models for rule extraction agent.

Defines structures for:
- Parsed logic from BUD fields
- Generated rules (formFillRules)
- Field information
- Rule schemas
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
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
    SESSION_BASED_MAKE_DISABLED = "SESSION_BASED_MAKE_DISABLED"
    SESSION_BASED_MAKE_ENABLED = "SESSION_BASED_MAKE_ENABLED"

    # Validation/Verification rules
    VERIFY = "VERIFY"
    OCR = "OCR"

    # Data rules
    COPY_TO = "COPY_TO"
    CLEAR_FIELD = "CLEAR_FIELD"
    CONVERT_TO = "CONVERT_TO"
    COPY_TXNID_TO_FORM_FILL = "COPY_TXNID_TO_FORM_FILL"
    DATE_FORMAT_CONVERTER = "DATE_FORMAT_CONVERTER"

    # External data rules
    EXT_DROP_DOWN = "EXT_DROP_DOWN"
    EXT_VALUE = "EXT_VALUE"


class SourceType(Enum):
    """Source types for VERIFY/OCR rules."""
    # PAN
    PAN_NUMBER = "PAN_NUMBER"
    PAN_IMAGE = "PAN_IMAGE"

    # GSTIN
    GSTIN = "GSTIN"
    GSTIN_IMAGE = "GSTIN_IMAGE"
    GSTIN_WITH_PAN = "GSTIN_WITH_PAN"

    # Bank
    BANK_ACCOUNT_NUMBER = "BANK_ACCOUNT_NUMBER"

    # Cheque
    CHEQUEE = "CHEQUEE"

    # MSME
    MSME = "MSME"
    MSME_UDYAM_REG_NUMBER = "MSME_UDYAM_REG_NUMBER"

    # CIN
    CIN = "CIN"
    CIN_ID = "CIN_ID"

    # Aadhaar
    AADHAR_IMAGE = "AADHAR_IMAGE"
    AADHAR_BACK_IMAGE = "AADHAR_BACK_IMAGE"

    # PIN Code
    PIN_CODE = "PIN_CODE"

    # Other
    FORM_FILL_DROP_DOWN = "FORM_FILL_DROP_DOWN"
    EXTERNAL_DATA_VALUE = "EXTERNAL_DATA_VALUE"
    UPPER_CASE = "UPPER_CASE"
    LOWER_CASE = "LOWER_CASE"


class ProcessingType(Enum):
    """Processing type for rules."""
    CLIENT = "CLIENT"
    SERVER = "SERVER"


class Condition(Enum):
    """Condition type for conditional rules."""
    IN = "IN"
    NOT_IN = "NOT_IN"


@dataclass
class FieldInfo:
    """Information about a field from the schema."""
    id: int
    name: str
    variable_name: str
    field_type: str
    is_mandatory: bool = False
    logic: str = ""
    rules: str = ""
    panel_name: str = ""
    form_order: float = 0.0


@dataclass
class RuleSchemaDestField:
    """Destination field definition from Rule-Schemas.json."""
    name: str
    ordinal: int
    mandatory: bool = False


@dataclass
class RuleSchemaSourceField:
    """Source field definition from Rule-Schemas.json."""
    name: str
    ordinal: int
    mandatory: bool = False


@dataclass
class RuleSchema:
    """Rule schema from Rule-Schemas.json."""
    id: int
    name: str
    source: str
    action: str
    processing_type: str
    destination_fields: List[RuleSchemaDestField]
    source_fields: List[RuleSchemaSourceField]
    button: str = ""
    num_destination_fields: int = 0


@dataclass
class ParsedCondition:
    """Parsed condition from logic text."""
    source_field_name: str
    operator: str  # 'equals', 'not_equals', 'in', 'not_in'
    values: List[str]

    def to_condition_type(self) -> str:
        """Convert to Condition enum value."""
        if self.operator in ['not_equals', 'not_in']:
            return "NOT_IN"
        return "IN"


@dataclass
class ParsedLogic:
    """Parsed logic statement from BUD field."""
    original_text: str
    action_keywords: List[str] = field(default_factory=list)
    document_type: Optional[str] = None  # PAN, GSTIN, Bank, etc.
    source_field_name: Optional[str] = None
    destination_field_names: List[str] = field(default_factory=list)
    conditions: List[ParsedCondition] = field(default_factory=list)
    is_ocr: bool = False
    is_verify: bool = False
    is_visibility: bool = False
    is_mandatory: bool = False
    is_disabled: bool = False
    is_ext_dropdown: bool = False
    is_ext_value: bool = False
    is_destination_only: bool = False  # "Data will come from X validation"
    confidence: float = 0.0


@dataclass
class GeneratedRule:
    """Generated formFillRule structure."""
    id: int = 0
    create_user: str = "FIRST_PARTY"
    update_user: str = "FIRST_PARTY"
    action_type: str = ""
    processing_type: str = "CLIENT"
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    condition: str = ""
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    params: str = ""
    button: str = ""
    source_type: str = ""
    on_status_fail: str = ""
    searchable: bool = False
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching reference JSON format."""
        result = {
            "id": self.id,
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

        # Add conditional fields only if present
        if self.conditional_values:
            result["conditionalValues"] = self.conditional_values
        if self.condition:
            result["condition"] = self.condition
            result["conditionValueType"] = self.condition_value_type
        if self.source_type:
            result["sourceType"] = self.source_type
        if self.params:
            result["params"] = self.params
        if self.on_status_fail:
            result["onStatusFail"] = self.on_status_fail

        return result


@dataclass
class VisibilityGroup:
    """Group of fields controlled by a single source field."""
    source_field_name: str
    source_field_id: int
    conditions: Dict[str, List[int]]  # conditional_value -> [destination_field_ids]
    actions: List[str]  # MAKE_VISIBLE, MAKE_MANDATORY, etc.


@dataclass
class OcrVerifyChain:
    """Chain linking OCR rule to VERIFY rule."""
    ocr_source_type: str  # e.g., PAN_IMAGE
    verify_source_type: str  # e.g., PAN_NUMBER
    ocr_field_id: int  # File upload field
    verify_field_id: int  # Text field being validated
    ocr_rule_id: int
    verify_rule_id: int


@dataclass
class ExtractionResult:
    """Result of rule extraction for a single field."""
    field_id: int
    field_name: str
    logic_text: str
    parsed_logic: Optional[ParsedLogic]
    generated_rules: List[GeneratedRule]
    extraction_method: str  # 'pattern', 'llm', 'skipped'
    confidence: float
    errors: List[str] = field(default_factory=list)


@dataclass
class ExtractionSummary:
    """Summary of the complete extraction run."""
    total_fields: int
    fields_with_logic: int
    fields_processed: int
    rules_generated: int
    pattern_matches: int
    llm_fallbacks: int
    skipped_fields: int
    errors: List[str]
    rule_type_counts: Dict[str, int]
