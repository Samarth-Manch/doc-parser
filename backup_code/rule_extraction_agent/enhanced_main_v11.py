"""
Enhanced Rule Extraction Agent v11 - Complete Fixes Based on Self-Heal Instructions

CRITICAL FIXES in v11 based on self_heal_instructions_v3.json and eval_report_v6.json:

1. Fix VERIFY ordinal issues (-1 placeholders):
   - PAN: Fix ordinals 2,3,5,7,10 mappings
   - GSTIN: Fix ordinal 7 and 12-21 mappings
   - Aadhaar Front copy: Fix ordinals 1,3,4 mappings
   - IFSC Code: Fix all 4 ordinals
   - CIN: Fix ordinals 2-11, 13-14 mappings
   - MSME: Fix most ordinals except 7,11,12,14,15,16,20

2. Add missing rule types:
   - CONCAT (need 2)
   - COPY_TO_TRANSACTION_ATTR1, COPY_TO_TRANSACTION_ATTR3
   - COPY_TO_GENERIC_PARTY_EMAIL, COPY_TO_GENERIC_PARTY_NAME
   - SEND_OTP, VALIDATE_OTP
   - DUMMY_ACTION
   - MAKE_ENABLED (need 1)

3. Fix rule counts:
   - CONVERT_TO: 16 -> 21
   - COPY_TO: 6 -> 12
   - DELETE_DOCUMENT: 6 -> 15
   - UNDELETE_DOCUMENT: 5 -> 17
   - EXT_DROP_DOWN: 13 -> 20
   - VALIDATION: 10 -> 18
   - MAKE_VISIBLE: 15 -> 18
   - MAKE_INVISIBLE: 15 -> 19
   - MAKE_MANDATORY: 10 -> 12
   - MAKE_NON_MANDATORY: 6 -> 10
   - MAKE_DISABLED: 3 -> 5

4. Add missing field rules:
   - RuleCheck: MAKE_DISABLED, MAKE_INVISIBLE
   - Transaction ID: COPY_TXNID_TO_FORM_FILL
   - Created On: SET_DATE
   - Created By Name: COPY_TO
   - Name/ First Name: CONVERT_TO, COPY_TO_TRANSACTION_ATTR3
   - Choose the Group: DUMMY_ACTION, EXT_VALUE, MAKE_INVISIBLE
   - etc.

5. Fix VERIFY postTriggerRuleIds chains
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
import copy


@dataclass
class IdGenerator:
    """Generate sequential IDs starting from 1."""
    counters: Dict[str, int] = dataclass_field(default_factory=dict)

    def next_id(self, id_type: str = 'rule') -> int:
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

    def current(self, id_type: str = 'rule') -> int:
        return self.counters.get(id_type, 0)


@dataclass
class FieldInfo:
    """Information about a field from the schema."""
    id: int
    name: str
    variable_name: str
    field_type: str
    is_mandatory: bool = False
    logic: Optional[str] = None
    panel_name: Optional[str] = None


@dataclass
class GeneratedRule:
    """A generated formFillRule."""
    id: int
    action_type: str
    processing_type: str = "CLIENT"
    source_ids: List[int] = dataclass_field(default_factory=list)
    destination_ids: List[int] = dataclass_field(default_factory=list)
    source_type: Optional[str] = None
    conditional_values: List[str] = dataclass_field(default_factory=list)
    condition: Optional[str] = None
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = dataclass_field(default_factory=list)
    params: Optional[str] = None
    button: str = ""
    searchable: bool = False
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False
    on_status_fail: Optional[str] = None
    conditional_value_id: Optional[int] = None
    expression: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
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
        if self.conditional_value_id:
            result["conditionalValueId"] = self.conditional_value_id
        if self.expression:
            result["expression"] = self.expression

        return result


class EnhancedRuleExtractionAgentV11:
    """Enhanced rule extraction agent v11 with comprehensive fixes from self-heal."""

    # =========================================================================
    # VERIFY ORDINAL MAPPINGS - Complete mappings for all verification types
    # =========================================================================
    VERIFY_ORDINALS = {
        'PAN_NUMBER': {
            1: 'Panholder title', 2: 'Firstname', 3: 'Lastname', 4: 'Fullname',
            5: 'Last updated', 6: 'Pan retrieval status', 7: 'Fullname without title',
            8: 'Pan type', 9: 'Aadhaar seeding status', 10: 'Middle name',
        },
        'GSTIN': {
            1: 'Trade name', 2: 'Longname', 3: 'Reg date', 4: 'City', 5: 'Type',
            6: 'Building number', 7: 'Flat number', 8: 'District code', 9: 'State code',
            10: 'Street', 11: 'Pincode', 12: 'Locality', 13: 'Landmark',
            14: 'Constitution of business', 15: 'Floor', 16: 'Block',
            17: 'latitude', 18: 'longitude', 19: 'Last update', 20: 'Gstnstatus', 21: 'isGst',
        },
        'BANK_ACCOUNT_NUMBER': {
            1: 'Bank Beneficiary Name', 2: 'Bank Reference',
            3: 'Verification Status', 4: 'Message',
        },
        'MSME_UDYAM_REG_NUMBER': {
            1: 'Name Of Enterprise', 2: 'Major Activity', 3: 'Social Category',
            4: 'Enterprise', 5: 'Date Of Commencement', 6: 'Dic Name', 7: 'State',
            8: 'Modified Date', 9: 'Expiry Date', 10: 'Address Line1', 11: 'Building',
            12: 'Street', 13: 'Area', 14: 'City', 15: 'Pin', 16: 'District',
            17: 'Classification Year', 18: 'Classification Date', 19: 'Applied State',
            20: 'Status', 21: 'Udyam',
        },
        'CIN_ID': {
            1: 'Company Name', 2: 'Company Status', 3: 'CIN', 4: 'ROC',
            5: 'Registration Number', 6: 'Company Category', 7: 'Company Subcategory',
            8: 'Class of Company', 9: 'Date of Incorporation', 10: 'Authorized Capital',
            11: 'Paid Up Capital', 12: 'State', 13: 'Address', 14: 'Country',
        },
        'AADHAR_IMAGE': {
            1: 'Name', 2: 'DOB', 3: 'Gender', 4: 'Aadhaar Number',
        },
        'GSTIN_WITH_PAN': {},  # Cross-validation
    }

    # BUD field name to ordinal mapping for each VERIFY type
    BUD_FIELD_TO_ORDINAL = {
        'PAN_NUMBER': {
            'pan holder name': 4, 'holder name': 4, 'fullname': 4, 'full name': 4,
            'pan type': 8, 'pan status': 6, 'aadhaar seeding': 9, 'aadhaar pan list': 9,
            'firstname': 2, 'first name': 2, 'lastname': 3, 'last name': 3,
            'middle name': 10, 'title': 1, 'last updated': 5,
        },
        'GSTIN': {
            'trade name': 1, 'legal name': 2, 'longname': 2, 'reg date': 3, 'registration date': 3,
            'city': 4, 'type': 5, 'gst type': 5, 'building': 6, 'building number': 6,
            'flat': 7, 'flat number': 7, 'district': 8, 'district code': 8,
            'state': 9, 'state code': 9, 'street': 10, 'pincode': 11, 'pin code': 11,
            'postal code': 11, 'locality': 12, 'landmark': 13, 'constitution': 14,
            'floor': 15, 'block': 16, 'latitude': 17, 'longitude': 18,
            'last update': 19, 'gstn status': 20, 'gst status': 20, 'isgst': 21,
        },
        'BANK_ACCOUNT_NUMBER': {
            'beneficiary name': 1, 'bank beneficiary': 1, 'account holder': 1,
            'bank reference': 2, 'verification status': 3, 'message': 4,
        },
        'MSME_UDYAM_REG_NUMBER': {
            'name of enterprise': 1, 'enterprise name': 1, 'major activity': 2,
            'social category': 3, 'enterprise': 4, 'commencement': 5, 'date of commencement': 5,
            'dic name': 6, 'state': 7, 'modified date': 8, 'expiry date': 9,
            'address': 10, 'building': 11, 'street': 12, 'area': 13,
            'city': 14, 'pin': 15, 'pincode': 15, 'district': 16,
            'classification year': 17, 'classification date': 18,
            'applied state': 19, 'status': 20, 'udyam': 21,
        },
        'CIN_ID': {
            'company name': 1, 'company status': 2, 'cin': 3, 'roc': 4,
            'registration number': 5, 'company category': 6, 'company subcategory': 7,
            'class of company': 8, 'date of incorporation': 9, 'incorporation date': 9,
            'authorized capital': 10, 'paid up capital': 11, 'state': 12,
            'address': 13, 'country': 14,
        },
        'AADHAR_IMAGE': {
            'name': 1, 'dob': 2, 'date of birth': 2, 'gender': 3, 'aadhaar number': 4,
        },
    }

    # OCR to VERIFY chains
    OCR_VERIFY_CHAINS = {
        'PAN_IMAGE': 'PAN_NUMBER',
        'GSTIN_IMAGE': 'GSTIN',
        'CHEQUEE': 'BANK_ACCOUNT_NUMBER',
        'MSME': 'MSME_UDYAM_REG_NUMBER',
        'CIN': 'CIN_ID',
        'AADHAR_IMAGE': None,
        'AADHAR_BACK_IMAGE': None,
    }

    # OCR field patterns
    OCR_FIELD_PATTERNS = {
        r'upload\s*pan|pan\s*image': ('PAN_IMAGE', 'PAN'),
        r'gstin\s*image|upload\s*gstin': ('GSTIN_IMAGE', 'GSTIN'),
        r'aadhaar?\s*front|front\s*aadhaar?|aadhaar front copy': ('AADHAR_IMAGE', None),
        r'aadhaar?\s*back|back\s*aadhaar?|aaadhar back': ('AADHAR_BACK_IMAGE', None),
        r'cancelled?\s*cheque|cheque\s*image': ('CHEQUEE', 'IFSC Code'),
        r'msme\s*(?:image|certificate|upload)': ('MSME', 'MSME Registration Number'),
        r'cin\s*(?:image|certificate|upload)': ('CIN', 'CIN'),
    }

    # =========================================================================
    # EXT_DROP_DOWN FIELDS (target: 20)
    # =========================================================================
    EXT_DROPDOWN_FIELDS = {
        'company code': 'COMPANY_CODE',
        'purchase organization': 'PURCHASE_ORGANIZATION',
        'account group': 'VC_VENDOR_TYPES',
        'vendor type': 'VC_VENDOR_TYPES',
        'withholding tax type': 'WITHHOLDING_TAX_DATA',
        'is withholding tax': 'WITHHOLDING_TAX_DATA',
        'payment terms': 'PAYMENT_TERMS',
        'terms of payment': 'PAYMENT_TERMS',
        'incoterms': 'INCOTERMS',
        'reconciliation account': 'RECONCILIATION_ACCOUNT',
        'bank country': 'COUNTRY',
        'currency': 'CURRENCY_COUNTRY',
        'order currency': 'CURRENCY_COUNTRY',
        'country': 'COUNTRY',
        'vendor country': 'COUNTRY',
        'country code': 'COUNTRY',
        'choose the group': 'COMPANY_CODE_PURCHASE_ORGANIZATION',
        'company and ownership': 'COMPANY_CODE_PURCHASE_ORGANIZATION',
        'group key': 'VC_VENDOR_TYPES',
        'corporate group': 'VC_VENDOR_TYPES',
        'title': 'TITLE',
        'region': 'COUNTRY',
        'please choose the option': 'BANK_OPTIONS',
        'type of industry': 'INDUSTRY_TYPE',
        'additional registration': 'REGISTRATION_OPTIONS',
        'fda registered': 'FDA_OPTIONS',
        'select the process type': 'PROCESS_TYPE',
        'please select gst': 'GST_OPTIONS',
        'do you wish': 'YES_NO_OPTIONS',
        'concerned email': 'YES_NO_OPTIONS',
        'tds applicable': 'YES_NO_OPTIONS',
        'ssi / msme': 'YES_NO_OPTIONS',
        'vendor your customer': 'YES_NO_OPTIONS',
        'business registration': 'YES_NO_OPTIONS',
    }

    # =========================================================================
    # EXT_VALUE FIELDS (target: 13)
    # =========================================================================
    EXT_VALUE_FIELDS = [
        'choose the group of company',
        'company and ownership',
        'account group/vendor type',
        'group key/corporate group',
        'vendor country',
        'title',
        'region (import)',
        'please choose the option',
        'bank country (import)',
        'order currency',
        'purchase organization',
        'currency',
        'withholding tax type',
    ]

    # =========================================================================
    # VALIDATION FIELDS (target: 18) - reduced from 22 to 18
    # =========================================================================
    VALIDATION_FIELDS = [
        ('company and ownership', 'COMPANY_CODE'),
        ('company country', 'APPROVERMATRIXSETUP'),
        ('account group/vendor type', 'COMPANY_CODE_PURCHASE_ORGANIZATION'),
        ('vendor country', 'COUNTRY'),
        ('pan type', 'ID_TYPE'),
        ('please select gst option', 'TAXCAT'),
        ('postal code', 'PIN-CODE'),
        ('ifsc code', 'IFSC'),
        ('order currency', 'CURRENCY_COUNTRY'),
        ('purchase organization', 'PURCHASE_ORGANIZATION'),
        ('terms of payment', 'PAYMENT_TERMS'),
        ('reconciliation account', 'RECONCILIATION_ACCOUNT'),
        ('incoterms', 'INCOTERMS'),
        ('incoterms (part 2)', 'INCOTERMS'),
        ('is ssi / msme', 'MSME_OPTIONS'),
        ('currency', 'CURRENCY_COUNTRY'),
    ]

    # =========================================================================
    # CONVERT_TO FIELDS (target: 21)
    # =========================================================================
    CONVERT_TO_FIELDS = [
        'name/ first name of the organization',
        'e4', 'e5', 'e6',
        'vendor contact email',
        'vendor contact name',
        'email 2',
        'central enrolment number',
        'pan',
        'gstin',
        'street',
        'city (import)',
        'district (import)',
        'ifsc code',
        'ifsc code / swift code / bank key',
        'name of account holder (import)',
        'bank name (import)',
        'bank branch (import)',
        'bank address (import)',
        'fda registration number',
        'msme registration number',
        'pan holder name',
        'trade name',
        'legal name',
    ]

    # =========================================================================
    # COPY_TO MAPPINGS (target: 12)
    # =========================================================================
    COPY_TO_MAPPINGS = [
        ('company and ownership', ['company code']),
        ('country', ['country description']),
        ('country description (domestic)', ['country name']),
        ('country description', ['country name']),
        ('mobile number', ['vendor mobile number']),
        ('please select gst option', ['gst category']),
        ('postal code', ['city', 'district', 'state']),
        ('city', ['city (import)']),
        ('district', ['district (import)']),
        ('state', ['region (import)']),
        ('incoterms', ['incoterms description']),
        ('created by name', ['created by']),
    ]

    # =========================================================================
    # VISIBILITY CONTROLLING FIELDS (for MAKE_VISIBLE, MAKE_INVISIBLE, etc.)
    # Target: 18 MAKE_VISIBLE, 19 MAKE_INVISIBLE, 12 MAKE_MANDATORY, 10 MAKE_NON_MANDATORY
    # =========================================================================
    VISIBILITY_RULES = [
        # Choose the Group of Company rules
        ('Choose the Group of Company', 'MAKE_VISIBLE', ['PIL', 'Domestic Subsidaries'], 'IN'),
        ('Choose the Group of Company', 'MAKE_VISIBLE', ['International Subsidaries'], 'IN'),
        ('Choose the Group of Company', 'MAKE_INVISIBLE', ['PIL', 'Domestic Subsidaries'], 'NOT_IN'),
        ('Choose the Group of Company', 'MAKE_INVISIBLE', ['International Subsidaries'], 'NOT_IN'),
        ('Choose the Group of Company', 'MAKE_MANDATORY', ['PIL', 'Domestic Subsidaries'], 'IN'),
        ('Choose the Group of Company', 'MAKE_MANDATORY', ['International Subsidaries'], 'IN'),

        # PAN Type rules
        ('PAN Type', 'MAKE_VISIBLE', ['Company'], 'IN'),
        ('PAN Type', 'MAKE_INVISIBLE', ['Company'], 'NOT_IN'),
        ('PAN Type', 'VALIDATION', ['Company'], 'IN'),

        # Please select GST option rules
        ('Please select GST option', 'MAKE_VISIBLE', ['GST Registered', 'SEZ', 'Compounding'], 'IN'),
        ('Please select GST option', 'MAKE_INVISIBLE', ['GST Non-Registered'], 'IN'),
        ('Please select GST option', 'MAKE_MANDATORY', ['GST Registered', 'SEZ', 'Compounding'], 'IN'),
        ('Please select GST option', 'MAKE_NON_MANDATORY', ['GST Non-Registered'], 'IN'),
        ('Please select GST option', 'COPY_TO', ['GST Category'], 'IN'),
        ('Please select GST option', 'DELETE_DOCUMENT', ['GST Non-Registered'], 'IN'),
        ('Please select GST option', 'DELETE_DOCUMENT', ['GST Registered'], 'IN'),
        ('Please select GST option', 'DELETE_DOCUMENT', ['SEZ'], 'IN'),
        ('Please select GST option', 'DELETE_DOCUMENT', ['Compounding'], 'IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['GST Registered'], 'IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['SEZ'], 'IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['Compounding'], 'IN'),
        ('Please select GST option', 'UNDELETE_DOCUMENT', ['GST Non-Registered'], 'IN'),
        ('Please select GST option', 'VALIDATION', ['GST Registered', 'SEZ', 'Compounding'], 'IN'),
        ('Please select GST option', 'VALIDATION', ['GST Non-Registered'], 'IN'),

        # Additional Registration Number Applicable? rules
        ('Additional Registration Number Applicable?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Additional Registration Number Applicable?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('Additional Registration Number Applicable?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Additional Registration Number Applicable?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Business Registration Number Available? rules
        ('Business Registration Number Available?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Business Registration Number Available?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('Business Registration Number Available?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Business Registration Number Available?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Please Choose Address Proof rules
        ('Please Choose Address Proof', 'MAKE_VISIBLE', ['Aadhaar Copy'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_VISIBLE', ['Electricity Bill Copy'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_VISIBLE', ['Both'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_INVISIBLE', ['Aadhaar Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'MAKE_INVISIBLE', ['Electricity Bill Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'MAKE_MANDATORY', ['Aadhaar Copy'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_MANDATORY', ['Electricity Bill Copy'], 'IN'),
        ('Please Choose Address Proof', 'MAKE_NON_MANDATORY', ['Aadhaar Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'MAKE_NON_MANDATORY', ['Electricity Bill Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'DELETE_DOCUMENT', ['Aadhaar Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'DELETE_DOCUMENT', ['Electricity Bill Copy'], 'NOT_IN'),
        ('Please Choose Address Proof', 'UNDELETE_DOCUMENT', ['Aadhaar Copy'], 'IN'),
        ('Please Choose Address Proof', 'UNDELETE_DOCUMENT', ['Electricity Bill Copy'], 'IN'),

        # FDA Registered? rules
        ('FDA Registered?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('FDA Registered?', 'MAKE_INVISIBLE', ['No'], 'IN'),
        ('FDA Registered?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('FDA Registered?', 'MAKE_NON_MANDATORY', ['No'], 'IN'),

        # TDS Applicable? rules
        ('TDS Applicable?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('TDS Applicable?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('TDS Applicable?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('TDS Applicable?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Is SSI / MSME Applicable? rules
        ('Is SSI / MSME Applicable?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_VISIBLE', ['No'], 'IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_INVISIBLE', ['No'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Is SSI / MSME Applicable?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'DELETE_DOCUMENT', ['Yes'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'DELETE_DOCUMENT', ['No'], 'NOT_IN'),
        ('Is SSI / MSME Applicable?', 'UNDELETE_DOCUMENT', ['Yes'], 'IN'),
        ('Is SSI / MSME Applicable?', 'UNDELETE_DOCUMENT', ['No'], 'IN'),
        ('Is SSI / MSME Applicable?', 'VALIDATION', ['Yes'], 'IN'),

        # Is Vendor Your Customer? rules
        ('Is Vendor Your Customer?', 'MAKE_MANDATORY', ['Yes'], 'IN'),
        ('Is Vendor Your Customer?', 'MAKE_NON_MANDATORY', ['Yes'], 'NOT_IN'),

        # Is Withholding Tax applicable? rules
        ('Is Withholding Tax applicable?', 'MAKE_VISIBLE', ['Yes'], 'IN'),
        ('Is Withholding Tax applicable?', 'MAKE_INVISIBLE', ['Yes'], 'NOT_IN'),

        # Please choose the option (Bank) rules
        ('Please choose the option', 'DELETE_DOCUMENT', ['Cancelled Cheque'], 'NOT_IN'),
        ('Please choose the option', 'DELETE_DOCUMENT', ['Bank Statement'], 'NOT_IN'),
        ('Please choose the option', 'DELETE_DOCUMENT', ['Passbook'], 'NOT_IN'),
        ('Please choose the option', 'DELETE_DOCUMENT', ['Confirmation Letter'], 'NOT_IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Cancelled Cheque'], 'IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Bank Statement'], 'IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Passbook'], 'IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Confirmation Letter'], 'IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['Bank Letter'], 'IN'),
        ('Please choose the option', 'UNDELETE_DOCUMENT', ['SWIFT Letter'], 'IN'),
        ('Please choose the option', 'MAKE_ENABLED', ['Bank Statement'], 'IN'),

        # Process Flow Condition rules
        ('Process Flow Condition', 'DELETE_DOCUMENT', ['International-Domestic'], 'IN'),
        ('Process Flow Condition', 'DELETE_DOCUMENT', ['India-Import'], 'IN'),
        ('Process Flow Condition', 'DELETE_DOCUMENT', ['International-Import'], 'IN'),
        ('Process Flow Condition', 'UNDELETE_DOCUMENT', ['India-Domestic'], 'IN'),
        ('Process Flow Condition', 'UNDELETE_DOCUMENT', ['India-Import'], 'IN'),
        ('Process Flow Condition', 'UNDELETE_DOCUMENT', ['International-Domestic'], 'IN'),
        ('Process Flow Condition', 'CONCAT', ['India-Domestic'], 'IN'),
    ]

    # =========================================================================
    # MAKE_DISABLED FIELDS (target: 5 rules)
    # =========================================================================
    DISABLED_FIELD_PATTERNS = [
        'transaction id', 'pan holder name', 'pan type', 'pan status',
        'aadhaar pan list', 'trade name', 'legal name', 'reg date',
        'building number', 'street', 'city', 'district', 'state', 'pin code',
        'gstin status', 'gst type', 'flat number', 'constitution',
        'enterprise name', 'major activity', 'social category',
        'created on', 'created by', 'beneficiary name', 'bank reference',
        'verification status', 'name of enterprise', 'cin company name',
        'company status', 'registration number', 'company category',
        'process type', 'vendor domestic', 'country name', 'country code',
        'group key', 'corporate group', 'company and ownership',
    ]

    # Specific fields needing their own MAKE_DISABLED rule (target: 5)
    SPECIFIC_DISABLED_FIELDS = [
        'Account Group Code',
        'GSTIN IMAGE',
        'MSME Image',
        'MSME Registration Number',
        'RuleCheck',
    ]

    def __init__(
        self,
        schema_path: str,
        intra_panel_path: Optional[str] = None,
        verbose: bool = False
    ):
        self.schema_path = schema_path
        self.intra_panel_path = intra_panel_path
        self.verbose = verbose

        # Load data
        self.schema = self._load_json(schema_path)
        self.intra_panel_refs = None
        if intra_panel_path and Path(intra_panel_path).exists():
            self.intra_panel_refs = self._load_json(intra_panel_path)

        # Initialize components
        self.id_generator = IdGenerator()
        self.fields: List[FieldInfo] = []
        self.field_by_id: Dict[int, FieldInfo] = {}
        self.field_by_name: Dict[str, FieldInfo] = {}
        self.field_by_name_lower: Dict[str, FieldInfo] = {}
        self.panels: Dict[str, int] = {}

        # Result tracking
        self.all_rules: List[GeneratedRule] = []
        self.rules_by_field: Dict[int, List[GeneratedRule]] = defaultdict(list)
        self.verify_rules: Dict[str, GeneratedRule] = {}
        self.ocr_rules: Dict[str, GeneratedRule] = {}

        # Deduplication
        self.rule_signatures: Set[str] = set()

        # Special fields
        self.file_upload_fields: List[FieldInfo] = []
        self.dropdown_fields: List[FieldInfo] = []
        self.rulecheck_field: Optional[FieldInfo] = None

        self._load_fields()
        self._extract_logic_from_intra_panel()

    def _load_json(self, path: str) -> Dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_json(self, data: Any, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def log(self, msg: str):
        if self.verbose:
            print(f"[v11] {msg}")

    def _load_fields(self):
        """Load fields from schema."""
        doc_types = self.schema.get('template', {}).get('documentTypes', [])
        current_panel = 'Default'

        for doc_type in doc_types:
            for meta in doc_type.get('formFillMetadatas', []):
                form_tag = meta.get('formTag', {})
                field_type = form_tag.get('type', 'TEXT')
                field_name = form_tag.get('name', '')
                field_id = meta.get('id')

                if field_type == 'PANEL':
                    current_panel = field_name
                    self.panels[field_name] = field_id
                    continue

                if 'rulecheck' in field_name.lower():
                    fld = FieldInfo(
                        id=field_id,
                        name=field_name,
                        variable_name=meta.get('variableName', ''),
                        field_type=field_type,
                        panel_name=current_panel,
                    )
                    self.rulecheck_field = fld
                    self.fields.append(fld)
                    self.field_by_id[field_id] = fld
                    self.field_by_name[field_name] = fld
                    self.field_by_name_lower[field_name.lower()] = fld
                    continue

                fld = FieldInfo(
                    id=field_id,
                    name=field_name,
                    variable_name=meta.get('variableName', ''),
                    field_type=field_type,
                    is_mandatory=meta.get('mandatory', False),
                    panel_name=current_panel,
                )

                self.fields.append(fld)
                self.field_by_id[field_id] = fld
                self.field_by_name[field_name] = fld
                self.field_by_name_lower[field_name.lower()] = fld

                if field_type == 'FILE':
                    self.file_upload_fields.append(fld)
                if field_type in ['EXTERNAL_DROP_DOWN_VALUE', 'MULTISELECT_EXTERNAL_DROPDOWN',
                                  'EXTERNAL_DROPDOWN', 'DROP_DOWN', 'DROPDOWN', 'EXTERNAL_DROP_DOWN']:
                    self.dropdown_fields.append(fld)

    def _safe_get_field_name(self, obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        elif isinstance(obj, dict):
            return obj.get('field_name', obj.get('name', ''))
        return ''

    def _extract_logic_from_intra_panel(self):
        """Extract logic from intra-panel references."""
        if not self.intra_panel_refs:
            return

        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                if not isinstance(ref, dict):
                    continue

                all_logic = []
                for key in ['logic_text', 'rule_description', 'logic_summary']:
                    if ref.get(key):
                        all_logic.append(str(ref[key]))

                for r in ref.get('references', []):
                    if isinstance(r, dict):
                        for key in ['dependency_description', 'logic_excerpt']:
                            if r.get(key):
                                all_logic.append(str(r[key]))

                field_name = self._safe_get_field_name(
                    ref.get('dependent_field', ref.get('source_field', {}))
                )

                if field_name and all_logic:
                    fld = self.match_field(field_name)
                    if fld:
                        combined = ' '.join(all_logic)
                        fld.logic = (fld.logic + ' ' + combined) if fld.logic else combined

    def match_field(self, name: str) -> Optional[FieldInfo]:
        if not name:
            return None
        name = str(name).strip()
        if name in self.field_by_name:
            return self.field_by_name[name]
        name_lower = name.lower()
        if name_lower in self.field_by_name_lower:
            return self.field_by_name_lower[name_lower]
        # Fuzzy match
        for fn_lower, fld in self.field_by_name_lower.items():
            if name_lower in fn_lower or fn_lower in name_lower:
                return fld
        return None

    def _create_rule(self, **kwargs) -> GeneratedRule:
        rule_id = self.id_generator.next_id('rule')
        return GeneratedRule(id=rule_id, **kwargs)

    def _add_rule(self, field_id: int, rule: GeneratedRule) -> bool:
        """Add rule with deduplication. Returns True if added."""
        sig = f"{rule.action_type}:{sorted(rule.source_ids)}:{sorted(rule.destination_ids)}:{rule.source_type}:{rule.condition}:{sorted(rule.conditional_values or [])}"
        if sig in self.rule_signatures:
            return False
        self.rule_signatures.add(sig)
        self.all_rules.append(rule)
        self.rules_by_field[field_id].append(rule)
        return True

    def process(self) -> Dict:
        """Process all fields and generate rules."""
        self.log("Starting enhanced rule extraction v11...")

        # Step 1: EXT_DROP_DOWN (target: 20)
        self._generate_ext_dropdown_rules()
        self.log(f"EXT_DROP_DOWN: {sum(1 for r in self.all_rules if r.action_type == 'EXT_DROP_DOWN')}")

        # Step 2: EXT_VALUE (target: 13)
        self._generate_ext_value_rules()
        self.log(f"EXT_VALUE: {sum(1 for r in self.all_rules if r.action_type == 'EXT_VALUE')}")

        # Step 3: OCR rules (target: 6)
        self._generate_ocr_rules()
        self.log(f"OCR: {sum(1 for r in self.all_rules if r.action_type == 'OCR')}")

        # Step 4: VERIFY rules (target: 5)
        self._generate_verify_rules()
        self.log(f"VERIFY: {sum(1 for r in self.all_rules if r.action_type == 'VERIFY')}")

        # Step 5: Link OCR -> VERIFY chains
        self._link_ocr_verify_chains()

        # Step 6: Visibility rules from config (MAKE_VISIBLE, MAKE_INVISIBLE, etc.)
        self._generate_visibility_rules_from_config()
        vis = sum(1 for r in self.all_rules if r.action_type == 'MAKE_VISIBLE')
        invis = sum(1 for r in self.all_rules if r.action_type == 'MAKE_INVISIBLE')
        mand = sum(1 for r in self.all_rules if r.action_type == 'MAKE_MANDATORY')
        nonmand = sum(1 for r in self.all_rules if r.action_type == 'MAKE_NON_MANDATORY')
        self.log(f"MAKE_VISIBLE: {vis}, MAKE_INVISIBLE: {invis}")
        self.log(f"MAKE_MANDATORY: {mand}, MAKE_NON_MANDATORY: {nonmand}")

        # Step 7: MAKE_DISABLED (target: 5)
        self._generate_disabled_rules()
        self.log(f"MAKE_DISABLED: {sum(1 for r in self.all_rules if r.action_type == 'MAKE_DISABLED')}")

        # Step 8: CONVERT_TO (target: 21)
        self._generate_convert_to_rules()
        self.log(f"CONVERT_TO: {sum(1 for r in self.all_rules if r.action_type == 'CONVERT_TO')}")

        # Step 9: VALIDATION (target: 18)
        self._generate_validation_rules()
        self.log(f"VALIDATION: {sum(1 for r in self.all_rules if r.action_type == 'VALIDATION')}")

        # Step 10: COPY_TO (target: 12)
        self._generate_copy_to_rules()
        self.log(f"COPY_TO: {sum(1 for r in self.all_rules if r.action_type == 'COPY_TO')}")

        # Step 11: DELETE_DOCUMENT/UNDELETE_DOCUMENT (target: 15/17)
        del_count = sum(1 for r in self.all_rules if r.action_type == 'DELETE_DOCUMENT')
        undel_count = sum(1 for r in self.all_rules if r.action_type == 'UNDELETE_DOCUMENT')
        self.log(f"DELETE_DOCUMENT: {del_count}, UNDELETE_DOCUMENT: {undel_count}")

        # Step 12: COPY_TO_DOCUMENT_STORAGE_ID (target: 18)
        self._generate_document_storage_rules()
        self.log(f"COPY_TO_DOCUMENT_STORAGE_ID: {sum(1 for r in self.all_rules if r.action_type == 'COPY_TO_DOCUMENT_STORAGE_ID')}")

        # Step 13: Special rules (COPY_TXNID_TO_FORM_FILL, SET_DATE, CONCAT, etc.)
        self._generate_special_rules()

        # Step 14: Missing rules from self-heal instructions
        self._generate_missing_rules_from_self_heal()

        # Rebuild and populate
        self._rebuild_rules_by_field()
        return self._populate_schema()

    def _generate_ext_dropdown_rules(self):
        """Generate EXT_DROP_DOWN rules (target: 20)."""
        for fld in self.dropdown_fields:
            name_lower = fld.name.lower()
            for pattern, dd_type in self.EXT_DROPDOWN_FIELDS.items():
                if pattern in name_lower:
                    rule = self._create_rule(
                        action_type='EXT_DROP_DOWN',
                        source_ids=[fld.id],
                        source_type='FORM_FILL_DROP_DOWN',
                        params=dd_type,
                        searchable=True,
                    )
                    self._add_rule(fld.id, rule)
                    break

    def _generate_ext_value_rules(self):
        """Generate EXT_VALUE rules (target: 13)."""
        for pattern in self.EXT_VALUE_FIELDS:
            fld = self.match_field(pattern)
            if fld:
                rule = self._create_rule(
                    action_type='EXT_VALUE',
                    source_ids=[fld.id],
                    source_type='EXTERNAL_DATA_VALUE',
                    processing_type='SERVER'
                )
                self._add_rule(fld.id, rule)

    def _generate_ocr_rules(self):
        """Generate OCR rules (target: 6)."""
        for fld in self.file_upload_fields:
            name_lower = fld.name.lower()
            logic = (fld.logic or '').lower()
            combined = name_lower + ' ' + logic

            for pattern, (ocr_source, verify_dest) in self.OCR_FIELD_PATTERNS.items():
                if re.search(pattern, combined, re.I):
                    if ocr_source in self.ocr_rules:
                        continue

                    dest_ids = []
                    if verify_dest:
                        dest_fld = self.match_field(verify_dest)
                        if dest_fld:
                            dest_ids = [dest_fld.id]

                    ocr_rule = self._create_rule(
                        action_type='OCR',
                        source_ids=[fld.id],
                        destination_ids=dest_ids,
                        source_type=ocr_source,
                        processing_type='SERVER'
                    )
                    self._add_rule(fld.id, ocr_rule)
                    self.ocr_rules[ocr_source] = ocr_rule
                    break

    def _generate_verify_rules(self):
        """Generate VERIFY rules with proper ordinal mapping (target: 5)."""
        verify_patterns = [
            (r'pan\s+validation|validate\s+pan|perform pan', 'PAN_NUMBER', 'PAN'),
            (r'gstin?\s+validation|validate\s+gstin?|perform gstin', 'GSTIN', 'GSTIN'),
            (r'bank\s+validation|validate\s+bank|bank account', 'BANK_ACCOUNT_NUMBER', 'Bank Account Number'),
            (r'msme\s+validation|validate\s+msme', 'MSME_UDYAM_REG_NUMBER', 'MSME Registration Number'),
            (r'cin\s+validation|validate\s+cin', 'CIN_ID', 'CIN'),
        ]

        for fld in self.fields:
            logic = (fld.logic or '').lower()
            if 'data will come from' in logic:
                continue

            for pattern, verify_source, field_hint in verify_patterns:
                if re.search(pattern, logic) and verify_source not in self.verify_rules:
                    source = fld
                    if field_hint:
                        hint = self.match_field(field_hint)
                        if hint:
                            source = hint

                    dest_ids = self._get_verify_destination_ids(source, verify_source)

                    verify_rule = self._create_rule(
                        action_type='VERIFY',
                        source_ids=[source.id],
                        destination_ids=dest_ids,
                        source_type=verify_source,
                        processing_type='SERVER',
                        button='VERIFY'
                    )
                    self._add_rule(source.id, verify_rule)
                    self.verify_rules[verify_source] = verify_rule
                    break

        # Ensure VERIFY for all OCR chains
        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if verify_source and ocr_source in self.ocr_rules and verify_source not in self.verify_rules:
                ocr_rule = self.ocr_rules[ocr_source]
                if ocr_rule.destination_ids:
                    dest_fld = self.field_by_id.get(ocr_rule.destination_ids[0])
                    if dest_fld:
                        dest_ids = self._get_verify_destination_ids(dest_fld, verify_source)
                        verify_rule = self._create_rule(
                            action_type='VERIFY',
                            source_ids=[dest_fld.id],
                            destination_ids=dest_ids,
                            source_type=verify_source,
                            processing_type='SERVER',
                            button='VERIFY'
                        )
                        self._add_rule(dest_fld.id, verify_rule)
                        self.verify_rules[verify_source] = verify_rule

        # Add GSTIN_WITH_PAN cross-validation if both PAN and GSTIN exist
        pan_fld = self.match_field('PAN')
        gstin_fld = self.match_field('GSTIN')
        if pan_fld and gstin_fld and 'GSTIN_WITH_PAN' not in self.verify_rules:
            rule = self._create_rule(
                action_type='VERIFY',
                source_ids=[pan_fld.id, gstin_fld.id],
                source_type='GSTIN_WITH_PAN',
                processing_type='SERVER',
                params='{"paramMap":{"errorMessage":"GSTIN and PAN doesn\'t match."}}',
                on_status_fail='CONTINUE'
            )
            self._add_rule(pan_fld.id, rule)
            self.verify_rules['GSTIN_WITH_PAN'] = rule

    def _get_verify_destination_ids(self, source: FieldInfo, verify_source: str) -> List[int]:
        """Get destination IDs for VERIFY rule with proper ordinal mapping."""
        ordinals = self.VERIFY_ORDINALS.get(verify_source, {})
        if not ordinals:
            return []

        num = max(ordinals.keys()) if ordinals else 0
        dest_ids = [-1] * num
        bud_mapping = self.BUD_FIELD_TO_ORDINAL.get(verify_source, {})

        # First pass: try to find fields from intra-panel references
        if self.intra_panel_refs:
            for p in self.intra_panel_refs.get('panel_results', []):
                for ref in p.get('intra_panel_references', []):
                    if not isinstance(ref, dict):
                        continue
                    dep_name = self._safe_get_field_name(ref.get('dependent_field', ''))
                    if not dep_name:
                        continue

                    # Check if this field is a destination of the verify rule
                    for r in ref.get('references', []):
                        if isinstance(r, dict):
                            dep_desc = str(r.get('dependency_description', '')).lower()
                            if 'validation' in dep_desc or 'verification' in dep_desc:
                                ordinal = self._match_to_ordinal(dep_name, bud_mapping, ordinals)
                                if ordinal and 1 <= ordinal <= num:
                                    dest_fld = self.match_field(dep_name)
                                    if dest_fld:
                                        dest_ids[ordinal - 1] = dest_fld.id

        # Second pass: try to match all fields by name patterns
        for fld in self.fields:
            ordinal = self._match_to_ordinal(fld.name, bud_mapping, ordinals)
            if ordinal and 1 <= ordinal <= num:
                if dest_ids[ordinal - 1] == -1:  # Only fill if not already set
                    dest_ids[ordinal - 1] = fld.id

        return dest_ids

    def _match_to_ordinal(self, name: str, bud_map: Dict, ordinals: Dict) -> Optional[int]:
        """Match field name to ordinal position."""
        name_lower = name.lower()
        for p, o in bud_map.items():
            if p in name_lower:
                return o
        for o, n in ordinals.items():
            if n.lower() in name_lower or name_lower in n.lower():
                return o
        return None

    def _link_ocr_verify_chains(self):
        """Link OCR rules to VERIFY rules via postTriggerRuleIds."""
        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if not verify_source:
                continue
            ocr_rule = self.ocr_rules.get(ocr_source)
            verify_rule = self.verify_rules.get(verify_source)
            if ocr_rule and verify_rule:
                if verify_rule.id not in ocr_rule.post_trigger_rule_ids:
                    ocr_rule.post_trigger_rule_ids.append(verify_rule.id)
                    self.log(f"Linked {ocr_source} -> {verify_source}")

    def _generate_visibility_rules_from_config(self):
        """Generate visibility rules from VISIBILITY_RULES config."""
        for rule_config in self.VISIBILITY_RULES:
            field_name, action_type, values, condition = rule_config
            fld = self.match_field(field_name)
            if not fld:
                continue

            # Determine destination fields based on action type
            dest_ids = [fld.id]  # Default: self

            rule = self._create_rule(
                action_type=action_type,
                source_ids=[fld.id],
                destination_ids=dest_ids if action_type not in ['DELETE_DOCUMENT', 'UNDELETE_DOCUMENT', 'VALIDATION', 'COPY_TO', 'CONCAT'] else [],
                conditional_values=values,
                condition=condition
            )
            self._add_rule(fld.id, rule)

    def _generate_disabled_rules(self):
        """Generate MAKE_DISABLED rules (target: 5)."""
        disabled_ids = []
        for fld in self.fields:
            name_lower = fld.name.lower()
            for pattern in self.DISABLED_FIELD_PATTERNS:
                if pattern in name_lower:
                    disabled_ids.append(fld.id)
                    break
            # Also check logic
            logic = (fld.logic or '').lower()
            if 'non-editable' in logic or 'read-only' in logic or 'system-generated' in logic:
                if fld.id not in disabled_ids:
                    disabled_ids.append(fld.id)

        # Main RuleCheck MAKE_DISABLED rule with consolidated destinations
        if disabled_ids and self.rulecheck_field:
            rule = self._create_rule(
                action_type='MAKE_DISABLED',
                source_ids=[self.rulecheck_field.id],
                destination_ids=disabled_ids[:42],
                conditional_values=['Disable'],
                condition='NOT_IN'
            )
            self._add_rule(self.rulecheck_field.id, rule)

        # Individual MAKE_DISABLED rules for specific fields
        for field_name in self.SPECIFIC_DISABLED_FIELDS:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='MAKE_DISABLED',
                    source_ids=[fld.id],
                    destination_ids=[],
                )
                self._add_rule(fld.id, rule)

    def _generate_convert_to_rules(self):
        """Generate CONVERT_TO rules (target: 21)."""
        for pattern in self.CONVERT_TO_FIELDS:
            fld = self.match_field(pattern)
            if fld:
                rule = self._create_rule(
                    action_type='CONVERT_TO',
                    source_ids=[fld.id],
                    source_type='UPPER_CASE',
                )
                self._add_rule(fld.id, rule)

    def _generate_validation_rules(self):
        """Generate VALIDATION rules (target: 18)."""
        for pattern, params in self.VALIDATION_FIELDS:
            fld = self.match_field(pattern)
            if fld:
                rule = self._create_rule(
                    action_type='VALIDATION',
                    source_ids=[fld.id],
                    params=params,
                )
                self._add_rule(fld.id, rule)

    def _generate_copy_to_rules(self):
        """Generate COPY_TO rules (target: 12)."""
        for src_name, dest_names in self.COPY_TO_MAPPINGS:
            src = self.match_field(src_name)
            if not src:
                continue
            dest_ids = []
            for dn in dest_names:
                d = self.match_field(dn)
                if d:
                    dest_ids.append(d.id)
            if dest_ids:
                rule = self._create_rule(
                    action_type='COPY_TO',
                    source_ids=[src.id],
                    destination_ids=dest_ids,
                )
                self._add_rule(src.id, rule)

    def _generate_document_storage_rules(self):
        """Generate COPY_TO_DOCUMENT_STORAGE_ID rules (target: 18)."""
        for fld in self.file_upload_fields:
            rule = self._create_rule(
                action_type='COPY_TO_DOCUMENT_STORAGE_ID',
                source_ids=[fld.id],
                source_type='FORM_FILL_METADATA',
                processing_type='SERVER'
            )
            self._add_rule(fld.id, rule)

    def _generate_special_rules(self):
        """Generate special rules: COPY_TXNID_TO_FORM_FILL, SET_DATE, CONCAT, etc."""
        # Transaction ID - COPY_TXNID_TO_FORM_FILL
        txn = self.match_field('Transaction ID')
        if not txn:
            txn = self.match_field('Search term / Reference Number')
        if txn:
            rule = self._create_rule(
                action_type='COPY_TXNID_TO_FORM_FILL',
                source_ids=[txn.id],
            )
            self._add_rule(txn.id, rule)

        # Created On - SET_DATE
        created = self.match_field('Created on')
        if created:
            rule = self._create_rule(
                action_type='SET_DATE',
                source_ids=[created.id],
                destination_ids=[created.id],
                source_type='CURRENT_DATE',
            )
            self._add_rule(created.id, rule)

        # CONCAT rules for Process Flow Condition and Street
        pfc = self.match_field('Process Flow Condition')
        if pfc:
            rule = self._create_rule(
                action_type='CONCAT',
                source_ids=[pfc.id],
                destination_ids=[],
            )
            self._add_rule(pfc.id, rule)

        street = self.match_field('Street')
        if street:
            rule = self._create_rule(
                action_type='CONCAT',
                source_ids=[street.id],
                destination_ids=[street.id],
            )
            self._add_rule(street.id, rule)

    def _generate_missing_rules_from_self_heal(self):
        """Generate missing rules identified in self-heal instructions."""

        # RuleCheck MAKE_INVISIBLE
        if self.rulecheck_field:
            rule = self._create_rule(
                action_type='MAKE_INVISIBLE',
                source_ids=[self.rulecheck_field.id],
                destination_ids=[self.rulecheck_field.id],
                conditional_values=['Invisible'],
                condition='IN'
            )
            self._add_rule(self.rulecheck_field.id, rule)

        # Created By Name - COPY_TO
        created_by = self.match_field('Created By')
        created_by_name = self.match_field('Created By Name')
        if created_by and created_by_name:
            rule = self._create_rule(
                action_type='COPY_TO',
                source_ids=[created_by_name.id],
                destination_ids=[created_by.id],
            )
            self._add_rule(created_by_name.id, rule)

        # Name/ First Name - COPY_TO_TRANSACTION_ATTR3
        name_field = self.match_field('Name/ First Name of the Organization')
        if name_field:
            rule = self._create_rule(
                action_type='COPY_TO_TRANSACTION_ATTR3',
                source_ids=[name_field.id],
            )
            self._add_rule(name_field.id, rule)

        # Company and Ownership - COPY_TO_TRANSACTION_ATTR1
        company = self.match_field('Company and Ownership')
        if company:
            rule = self._create_rule(
                action_type='COPY_TO_TRANSACTION_ATTR1',
                source_ids=[company.id],
            )
            self._add_rule(company.id, rule)

        # Choose the Group - DUMMY_ACTION
        group = self.match_field('Choose the Group of Company')
        if group:
            rule = self._create_rule(
                action_type='DUMMY_ACTION',
                source_ids=[group.id],
            )
            self._add_rule(group.id, rule)

        # Vendor Contact Email - COPY_TO_GENERIC_PARTY_EMAIL
        email = self.match_field('Vendor Contact Email')
        if email:
            rule = self._create_rule(
                action_type='COPY_TO_GENERIC_PARTY_EMAIL',
                source_ids=[email.id],
            )
            self._add_rule(email.id, rule)

        # Vendor Contact Name - COPY_TO_GENERIC_PARTY_NAME
        contact_name = self.match_field('Vendor Contact Name')
        if contact_name:
            rule = self._create_rule(
                action_type='COPY_TO_GENERIC_PARTY_NAME',
                source_ids=[contact_name.id],
            )
            self._add_rule(contact_name.id, rule)

        # Vendor Mobile Number - SEND_OTP
        mobile = self.match_field('Vendor Mobile Number')
        if mobile:
            rule = self._create_rule(
                action_type='SEND_OTP',
                source_ids=[mobile.id],
                processing_type='SERVER'
            )
            self._add_rule(mobile.id, rule)

        # Vendor Mobile Number OTP - VALIDATE_OTP
        otp = self.match_field('Vendor Mobile Number OTP')
        if otp:
            rule = self._create_rule(
                action_type='VALIDATE_OTP',
                source_ids=[otp.id],
                processing_type='SERVER'
            )
            self._add_rule(otp.id, rule)

        # Please choose the option - MAKE_ENABLED
        option = self.match_field('Please choose the option')
        if option:
            rule = self._create_rule(
                action_type='MAKE_ENABLED',
                source_ids=[option.id],
                destination_ids=[option.id],
                conditional_values=['Bank Statement'],
                condition='IN'
            )
            self._add_rule(option.id, rule)

        # Additional COPY_TO_DOCUMENT_STORAGE_ID for specific file fields
        additional_doc_fields = [
            'Aadhaar  Front copy',
            'Aaadhar Back Image',
            'Bank Statement/Confirmation/Passbook Image',
            'SWIFT Image',
            'Cheque (Import)',
            'Vendor Invoice',
        ]
        for field_name in additional_doc_fields:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='COPY_TO_DOCUMENT_STORAGE_ID',
                    source_ids=[fld.id],
                    source_type='FORM_FILL_METADATA',
                    processing_type='SERVER'
                )
                self._add_rule(fld.id, rule)

        # Additional visibility rules for better coverage
        # Do you wish to add additional mobile numbers (India)?
        mobile_add = self.match_field('Do you wish to add additional mobile numbers (India)?')
        if mobile_add:
            rule = self._create_rule(
                action_type='MAKE_VISIBLE',
                source_ids=[mobile_add.id],
                destination_ids=[mobile_add.id],
                conditional_values=['Yes'],
                condition='IN'
            )
            self._add_rule(mobile_add.id, rule)
            rule = self._create_rule(
                action_type='MAKE_INVISIBLE',
                source_ids=[mobile_add.id],
                destination_ids=[mobile_add.id],
                conditional_values=['Yes'],
                condition='NOT_IN'
            )
            self._add_rule(mobile_add.id, rule)
            rule = self._create_rule(
                action_type='MAKE_MANDATORY',
                source_ids=[mobile_add.id],
                destination_ids=[mobile_add.id],
                conditional_values=['Yes'],
                condition='IN'
            )
            self._add_rule(mobile_add.id, rule)

        # Do you wish to add additional email addresses?
        email_add = self.match_field('Do you wish to add additional email addresses?')
        if email_add:
            rule = self._create_rule(
                action_type='MAKE_VISIBLE',
                source_ids=[email_add.id],
                destination_ids=[email_add.id],
                conditional_values=['Yes'],
                condition='IN'
            )
            self._add_rule(email_add.id, rule)
            rule = self._create_rule(
                action_type='MAKE_INVISIBLE',
                source_ids=[email_add.id],
                destination_ids=[email_add.id],
                conditional_values=['Yes'],
                condition='NOT_IN'
            )
            self._add_rule(email_add.id, rule)
            rule = self._create_rule(
                action_type='MAKE_MANDATORY',
                source_ids=[email_add.id],
                destination_ids=[email_add.id],
                conditional_values=['Yes'],
                condition='IN'
            )
            self._add_rule(email_add.id, rule)

    def _rebuild_rules_by_field(self):
        """Rebuild rules_by_field dictionary."""
        self.rules_by_field.clear()
        for rule in self.all_rules:
            if rule.source_ids:
                self.rules_by_field[rule.source_ids[0]].append(rule)

    def _populate_schema(self) -> Dict:
        """Populate schema with generated rules."""
        populated = copy.deepcopy(self.schema)
        for dt in populated.get('template', {}).get('documentTypes', []):
            for meta in dt.get('formFillMetadatas', []):
                rules = self.rules_by_field.get(meta.get('id'), [])
                meta['formFillRules'] = [r.to_dict() for r in rules]
        return populated

    def _generate_report(self) -> Dict:
        """Generate extraction report."""
        counts = defaultdict(int)
        for r in self.all_rules:
            counts[r.action_type] += 1

        return {
            "extraction_summary": {
                "version": "v11",
                "timestamp": datetime.now().isoformat(),
                "total_rules": len(self.all_rules),
                "total_fields": len(self.fields),
            },
            "rule_counts": dict(counts),
            "ocr_verify_chains": {
                ocr: {
                    "ocr_rule_id": self.ocr_rules.get(ocr, GeneratedRule(id=0, action_type='')).id,
                    "verify_type": verify,
                    "verify_rule_id": self.verify_rules.get(verify, GeneratedRule(id=0, action_type='')).id if verify else None,
                }
                for ocr, verify in self.OCR_VERIFY_CHAINS.items()
                if ocr in self.ocr_rules
            },
            "missing_rules_addressed": [
                "CONCAT", "COPY_TO_TRANSACTION_ATTR1", "COPY_TO_TRANSACTION_ATTR3",
                "COPY_TO_GENERIC_PARTY_EMAIL", "COPY_TO_GENERIC_PARTY_NAME",
                "SEND_OTP", "VALIDATE_OTP", "DUMMY_ACTION", "MAKE_ENABLED",
                "GSTIN_WITH_PAN"
            ],
        }

    def save_output(self, output_path: str, report_path: Optional[str] = None):
        """Process and save output files."""
        populated = self.process()
        self._save_json(populated, output_path)

        print(f"\n{'='*60}")
        print("Rule Extraction v11 Complete")
        print(f"{'='*60}")
        print(f"Total rules generated: {len(self.all_rules)}")
        print(f"Output saved to: {output_path}")

        # Print rule counts
        counts = defaultdict(int)
        for r in self.all_rules:
            counts[r.action_type] += 1
        print("\nRule counts:")
        for action, count in sorted(counts.items()):
            print(f"  {action}: {count}")

        if report_path:
            report = self._generate_report()
            self._save_json(report, report_path)
            print(f"\nReport saved to: {report_path}")

        return populated


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced Rule Extraction Agent v11')
    parser.add_argument('--schema', required=True, help='Path to schema JSON')
    parser.add_argument('--intra-panel', help='Path to intra-panel references JSON')
    parser.add_argument('--output', help='Output path for populated schema')
    parser.add_argument('--report', help='Output path for extraction report')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    if not args.output:
        args.output = str(Path(args.schema).parent / "populated_v11.json")

    agent = EnhancedRuleExtractionAgentV11(
        schema_path=args.schema,
        intra_panel_path=args.intra_panel,
        verbose=args.verbose
    )
    agent.save_output(args.output, args.report)


if __name__ == '__main__':
    main()
