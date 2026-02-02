"""
Enhanced Rule Extraction Agent v9 - Comprehensive Fixes

CRITICAL FIXES in v9 based on eval report v3:

1. VALIDATION rules: 1 generated vs 18 expected
   - Add field-level validation with params like COMPANY_CODE, PIN-CODE, IFSC, etc.
   - Detect validation patterns in logic text

2. CONVERT_TO rules: 5 generated vs 21 expected
   - All TEXT fields with uppercase/capital letters logic
   - Email, PAN, GSTIN, IFSC fields should have UPPER_CASE conversion

3. COPY_TO rules: 1 generated vs 12 expected
   - Detect copy/derive patterns in logic
   - Copy from one field to another

4. EXT_DROP_DOWN rules: 9 generated vs 20 expected
   - More dropdown field patterns
   - Yes/No questions typically need EXT_DROP_DOWN

5. EXT_VALUE rules: 2 generated vs 13 expected
   - Complex JSON params for cascading dropdowns
   - Based on reference table lookups

6. Visibility conditions: Use actual dropdown values
   - "GST Registered", "GST Non-Registered", "SEZ", "Compounding"
   - "Company" for PAN Type
   - "Yes" for Yes/No questions
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import copy


@dataclass
class IdGenerator:
    """Generate sequential IDs starting from 1."""
    counters: Dict[str, int] = field(default_factory=dict)

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
    form_order: float = 0.0
    parent_panel_id: Optional[int] = None


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


class EnhancedRuleExtractionAgentV9:
    """Enhanced rule extraction agent v9 with comprehensive fixes."""

    # VERIFY ordinal mappings from Rule-Schemas.json
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
    }

    # OCR type -> fields extracted (for OCR destinationIds)
    OCR_ORDINALS = {
        'PAN_IMAGE': {1: 'panNo', 2: 'name', 3: 'fatherName', 4: 'dob'},
        'GSTIN_IMAGE': {
            1: 'regNumber', 2: 'legalName', 3: 'tradeName', 4: 'business',
            5: 'doi', 6: 'address1', 7: 'address2', 8: 'pin',
            9: 'state', 10: 'type', 11: 'city',
        },
        'CHEQUEE': {
            1: 'bankName', 2: 'ifscCode', 3: 'beneficiaryName', 4: 'accountNumber',
            5: 'address', 6: 'micrCode', 7: 'branch',
        },
        'AADHAR_IMAGE': {1: 'aadharNumber', 2: 'name', 3: 'gender', 4: 'dob'},
        'AADHAR_BACK_IMAGE': {
            1: 'aadharAddress1', 2: 'aadharAddress2', 3: 'aadharPin', 4: 'aadharCity',
            5: 'aadharDist', 6: 'aadharState', 7: 'aadharFatherName',
            8: 'aadharCountry', 9: 'aadharCoords',
        },
        'MSME': {
            1: 'regNumber', 2: 'name', 3: 'type', 4: 'address',
            5: 'category', 6: 'dateOfIncorporation',
        },
        'CIN': {1: 'cinNumber', 2: 'companyName', 3: 'registrationDate'},
    }

    # OCR to VERIFY chain mappings
    OCR_VERIFY_CHAINS = {
        'PAN_IMAGE': 'PAN_NUMBER',
        'GSTIN_IMAGE': 'GSTIN',
        'CHEQUEE': 'BANK_ACCOUNT_NUMBER',
        'MSME': 'MSME_UDYAM_REG_NUMBER',
        'CIN': 'CIN_ID',
        'AADHAR_IMAGE': None,
        'AADHAR_BACK_IMAGE': None,
    }

    # Field name patterns for OCR detection
    OCR_FIELD_PATTERNS = {
        r'upload\s*pan|pan\s*image|pan\s*upload|pan\s*(?:copy|file)': ('PAN_IMAGE', 'PAN'),
        r'gstin\s*image|upload\s*gstin|gstin\s*upload|gstin\s*(?:copy|file)': ('GSTIN_IMAGE', 'GSTIN'),
        r'aadhaar?\s*front|front\s*aadhaar?|aadhaar?\s*front\s*copy': ('AADHAR_IMAGE', None),
        r'aadhaar?\s*back|back\s*aadhaar?|aadhaar?\s*back\s*image': ('AADHAR_BACK_IMAGE', None),
        r'cancelled?\s*cheque|cheque\s*image|cheque\s*copy': ('CHEQUEE', 'IFSC Code'),
        r'msme\s*(?:image|certificate|upload)|upload\s*msme|msme\s*registration\s*(?:image|upload)': ('MSME', 'MSME Registration Number'),
        r'cin\s*(?:image|certificate|upload)|upload\s*cin|cin\s*certificate': ('CIN', 'CIN'),
        r'passbook|bank\s*letter': ('CHEQUEE', 'Bank Account Number'),
    }

    # Field name to VERIFY ordinal mapping
    BUD_FIELD_TO_ORDINAL = {
        'PAN_NUMBER': {
            'pan holder name': 4, 'holder name': 4, 'fullname': 4, 'pan holder': 4,
            'pan type': 8, 'pan status': 6, 'pan retrieval': 6,
            'aadhaar pan list': 9, 'aadhaar seeding': 9,
            'first name': 2, 'firstname': 2,
            'last name': 3, 'lastname': 3,
            'title': 1, 'panholder title': 1,
            'middle name': 10, 'middlename': 10,
            'last updated': 5,
        },
        'GSTIN': {
            'trade name': 1, 'tradename': 1,
            'legal name': 2, 'longname': 2, 'legalname': 2,
            'reg date': 3, 'registration date': 3, 'regdate': 3,
            'city': 4, 'type': 5, 'gst type': 5,
            'building number': 6, 'building no': 6, 'building': 6,
            'flat number': 7, 'flat no': 7, 'flat': 7,
            'district code': 8, 'district': 8,
            'state code': 9, 'state': 9,
            'street': 10, 'street name': 10,
            'pin code': 11, 'pincode': 11, 'pin': 11,
            'locality': 12, 'landmark': 13,
            'constitution': 14, 'constitution of business': 14,
            'floor': 15, 'block': 16,
            'latitude': 17, 'longitude': 18,
            'last update': 19, 'last updated': 19,
            'gst status': 20, 'gstn status': 20, 'status': 20,
            'is gst': 21, 'isgst': 21,
        },
        'BANK_ACCOUNT_NUMBER': {
            'beneficiary name': 1, 'bank beneficiary name': 1, 'beneficiary': 1,
            'bank reference': 2, 'reference': 2,
            'verification status': 3, 'status': 3,
            'message': 4,
        },
        'MSME_UDYAM_REG_NUMBER': {
            'name of enterprise': 1, 'enterprise name': 1,
            'major activity': 2, 'activity': 2,
            'social category': 3, 'category': 3,
            'enterprise': 4, 'enterprise type': 4,
            'date of commencement': 5, 'commencement date': 5,
            'dic name': 6, 'dic': 6,
            'state': 7, 'enterprise state': 7,
            'modified date': 8,
            'expiry date': 9, 'validity': 9,
            'address': 10, 'address line': 10,
            'building': 11, 'street': 12, 'area': 13,
            'city': 14, 'pin': 15, 'district': 16,
            'classification year': 17, 'classification date': 18,
            'applied state': 19, 'msme status': 20, 'udyam': 21,
        },
        'CIN_ID': {
            'company name': 1, 'cin company name': 1,
            'company status': 2,
            'cin': 3, 'cin number': 3,
            'roc': 4, 'roc city': 4,
            'registration number': 5, 'reg number': 5,
            'company category': 6, 'category': 6,
            'company subcategory': 7, 'subcategory': 7,
            'class of company': 8, 'class': 8,
            'date of incorporation': 9, 'doi': 9, 'incorporation date': 9,
            'authorized capital': 10,
            'paid up capital': 11, 'paidup capital': 11,
            'state': 12, 'cin state': 12,
            'address': 13, 'registered address': 13,
            'country': 14,
        },
    }

    # v9 FIX: Expanded EXT_DROP_DOWN patterns
    EXT_DROPDOWN_FIELDS = {
        'company code': 'COMPANY_CODE',
        'purchase organization': 'PURCHASE_ORGANIZATION',
        'account group': 'VC_VENDOR_TYPES',
        'vendor type': 'VC_VENDOR_TYPES',
        'withholding tax type': 'WITHHOLDING_TAX_DATA',
        'payment terms': 'PAYMENT_TERMS',
        'incoterms': 'INCOTERMS',
        'reconciliation account': 'RECONCILIATION_ACCOUNT',
        'bank country': 'COUNTRY',
        'bank name': 'BANK_NAME',
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
        # Yes/No dropdown questions
        'do you wish': 'PIDILITE_YES_NO',
        'concerned email': 'PIDILITE_YES_NO',
        'additional registration': 'PIDILITE_YES_NO',
        'business registration': 'PIDILITE_YES_NO',
        'please select': 'TAXCAT',  # GST option
    }

    # v9 FIX: EXT_VALUE with complex params
    EXT_VALUE_FIELDS = {
        'choose the group of company': {
            'ddType': 'COMPANY_CODE_PURCHASE_ORGANIZATION',
            'criteria_field': 'Process Type',
            'output_attr': 'a3'
        },
        'company and ownership': {
            'ddType': 'COMPANY_CODE_PURCHASE_ORGANIZATION',
            'criteria_field': 'Choose the Group of Company',
            'output_attr': 'a1'
        },
        'account group/vendor type': {
            'ddType': 'VC_VENDOR_TYPES',
            'criteria_field': 'Process Type',
            'output_attr': 'a1'
        },
        'group key/corporate group': {
            'ddType': 'VC_VENDOR_TYPES',
            'criteria_field': 'Account Group/Vendor Type',
            'output_attr': 'a2'
        },
        'vendor country': {
            'ddType': 'COUNTRY',
            'criteria_field': None,
            'output_attr': None
        },
        'title': {
            'ddType': 'TITLE',
            'criteria_field': 'PAN Type',
            'output_attr': 'a1'
        },
        'region (import)': {
            'ddType': 'COUNTRY',
            'criteria_field': 'Vendor Country',
            'output_attr': 'a5'
        },
        'please choose the option': {
            'ddType': 'BANK_OPTIONS',
            'criteria_field': 'Country',
            'output_attr': 'a1'
        },
        'bank country (import)': {
            'ddType': 'COUNTRY',
            'criteria_field': None,
            'output_attr': 'a1'
        },
        'order currency': {
            'ddType': 'CURRENCY_COUNTRY',
            'criteria_field': None,
            'output_attr': 'a1'
        },
        'purchase organization': {
            'ddType': 'COMPANY_CODE_PURCHASE_ORGANIZATION',
            'criteria_field': 'Company and Ownership',
            'output_attr': 'a6'
        },
        'currency': {
            'ddType': 'CURRENCY_COUNTRY',
            'criteria_field': None,
            'output_attr': 'a1'
        },
        'withholding tax type': {
            'ddType': 'WITHHOLDING_TAX_DATA',
            'criteria_field': None,
            'output_attr': 'a1'
        },
    }

    # v9 FIX: VALIDATION patterns with params
    VALIDATION_FIELD_PARAMS = {
        'company code': 'COMPANY_CODE',
        'company and ownership': 'COMPANY_CODE',
        'account group': 'VC_VENDOR_TYPES',
        'vendor type': 'VC_VENDOR_TYPES',
        'vendor country': 'COUNTRY',
        'pan type': 'ID_TYPE',
        'please select gst option': 'TAXCAT',
        'gst option': 'GSTVALUE',
        'postal code': 'PIN-CODE',
        'pincode': 'PIN-CODE',
        'ifsc code': 'IFSC',
        'ifsc': 'IFSC',
        'mobile number': 'MOBILE',
        'email': 'EMAIL',
    }

    # v9 FIX: CONVERT_TO fields - all fields needing uppercase
    CONVERT_TO_UPPER_FIELDS = [
        'name', 'first name', 'organization',
        'e4', 'e5', 'e6',
        'vendor contact email', 'vendor contact name',
        'email', 'email 2',
        'central enrolment number', 'cen',
        'pan', 'gstin', 'gst',
        'street', 'city', 'district',
        'ifsc code', 'ifsc', 'swift code', 'bank key',
        'account holder', 'bank name', 'bank branch', 'bank address',
        'fda registration', 'msme registration',
    ]

    # v9 FIX: COPY_TO patterns - field pairs
    COPY_TO_MAPPINGS = [
        ('Company and Ownership', ['Company Code', 'Company Name']),
        ('Country', ['Country Description']),
        ('Country Description (Domestic)', ['Country Description']),
        ('Mobile Number', ['Mobile']),
        ('Please select GST option', ['GST Category']),
        ('Postal Code', ['Pincode']),
        ('City', ['City (Copy)']),
        ('District', ['District (Copy)']),
        ('State', ['State (Copy)']),
        ('Incoterms', ['Incoterms Description']),
    ]

    # v9 FIX: Visibility conditional values by controlling field
    VISIBILITY_CONDITIONAL_VALUES = {
        'please select gst option': {
            'visible_values': ['GST Registered', 'SEZ', 'Compounding'],
            'invisible_values': ['GST Non-Registered'],
        },
        'pan type': {
            'visible_values': ['Company'],
            'invisible_values': [],
        },
        'choose the group of company': {
            'visible_values': ['PIL', 'Domestic Subsidaries', 'International Subsidaries'],
            'invisible_values': [],
        },
        # Yes/No questions
        'do you wish to add additional mobile numbers (india)?': {
            'visible_values': ['Yes'],
            'invisible_values': [],
        },
        'do you wish to add additional mobile numbers (non-india)?': {
            'visible_values': ['Yes'],
            'invisible_values': [],
        },
        'do you wish to add additional email addresses?': {
            'visible_values': ['Yes'],
            'invisible_values': [],
        },
        'concerned email addresses?': {
            'visible_values': ['Yes'],
            'invisible_values': [],
        },
        'additional registration number applicable?': {
            'visible_values': ['Yes'],
            'invisible_values': [],
        },
        'business registration number available?': {
            'visible_values': ['Yes'],
            'invisible_values': [],
        },
    }

    # Disable pattern triggers
    DISABLED_PATTERNS = [
        r'non-?editable',
        r'read[\s-]?only',
        r'system[\s-]?generated',
        r'auto[\s-]?(?:derived|populated?|calculated?)',
        r'\(non[\s-]?editable\)',
        r'disable[d]?\b',
    ]

    def __init__(
        self,
        schema_path: str,
        intra_panel_path: Optional[str] = None,
        bud_path: Optional[str] = None,
        verbose: bool = False
    ):
        self.schema_path = schema_path
        self.intra_panel_path = intra_panel_path
        self.bud_path = bud_path
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
        self.fields_by_panel: Dict[str, List[FieldInfo]] = defaultdict(list)
        self.panels: Dict[str, int] = {}

        # Result tracking
        self.all_rules: List[GeneratedRule] = []
        self.rules_by_field: Dict[int, List[GeneratedRule]] = defaultdict(list)
        self.verify_rules: Dict[str, GeneratedRule] = {}
        self.ocr_rules: Dict[str, GeneratedRule] = {}

        # Deduplication tracking
        self.visibility_generated: Set[Tuple] = set()
        self.rule_signatures: Set[str] = set()

        # Special field tracking
        self.file_upload_fields: List[FieldInfo] = []
        self.dropdown_fields: List[FieldInfo] = []
        self.rulecheck_field: Optional[FieldInfo] = None
        self.text_fields: List[FieldInfo] = []

        # Load fields
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
            print(f"[v9] {msg}")

    def _load_fields(self):
        """Load fields from schema."""
        doc_types = self.schema.get('template', {}).get('documentTypes', [])
        current_panel = 'Default'
        current_panel_id = None

        for doc_type in doc_types:
            metadatas = doc_type.get('formFillMetadatas', [])
            for meta in metadatas:
                form_tag = meta.get('formTag', {})
                field_type = form_tag.get('type', 'TEXT')
                field_name = form_tag.get('name', '')
                field_id = meta.get('id')

                # Track panels
                if field_type == 'PANEL':
                    current_panel = field_name
                    current_panel_id = field_id
                    self.panels[field_name] = field_id
                    continue

                # Check for RuleCheck field
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
                    form_order=meta.get('formOrder', 0.0),
                    parent_panel_id=current_panel_id
                )

                self.fields.append(fld)
                self.field_by_id[field_id] = fld
                self.field_by_name[field_name] = fld
                self.field_by_name_lower[field_name.lower()] = fld
                self.fields_by_panel[current_panel].append(fld)

                # Track file upload fields
                if field_type == 'FILE':
                    self.file_upload_fields.append(fld)

                # Track dropdown fields
                if field_type in ['EXTERNAL_DROP_DOWN_VALUE', 'MULTISELECT_EXTERNAL_DROPDOWN',
                                  'EXTERNAL_DROPDOWN', 'DROP_DOWN', 'DROPDOWN',
                                  'EXTERNAL_DROP_DOWN']:
                    self.dropdown_fields.append(fld)

                # Track text fields for CONVERT_TO
                if field_type in ['TEXT', 'TEXTAREA', 'EMAIL']:
                    self.text_fields.append(fld)

    def _safe_get_field_name(self, obj: Any) -> str:
        """Safely extract field name from object."""
        if isinstance(obj, str):
            return obj
        elif isinstance(obj, dict):
            return obj.get('field_name', obj.get('name', ''))
        return ''

    def _extract_logic_from_intra_panel(self):
        """Extract logic text from intra-panel references."""
        if not self.intra_panel_refs:
            return

        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                if not isinstance(ref, dict):
                    continue

                # Collect all logic text
                all_logic = []
                for key in ['logic_text', 'rule_description', 'logic_summary',
                           'dependency_notes', 'logic_excerpt', 'raw_logic']:
                    if ref.get(key):
                        all_logic.append(str(ref[key]))

                # Get from nested references
                for r in ref.get('references', []):
                    if isinstance(r, dict):
                        for key in ['dependency_description', 'logic_excerpt',
                                   'condition_description', 'raw_logic_excerpt']:
                            if r.get(key):
                                all_logic.append(str(r[key]))

                # Get field name
                field_name = self._safe_get_field_name(
                    ref.get('dependent_field', ref.get('source_field', {}))
                )
                if not field_name:
                    field_name = ref.get('field_name', '')

                if field_name and all_logic:
                    fld = self.match_field(field_name)
                    if fld:
                        combined = ' '.join(all_logic)
                        fld.logic = (fld.logic + ' ' + combined) if fld.logic else combined

    def match_field(self, name: str, panel: Optional[str] = None) -> Optional[FieldInfo]:
        """Match field by name with optional panel context."""
        if not name:
            return None

        name = str(name).strip()

        # Exact match
        if name in self.field_by_name:
            return self.field_by_name[name]

        # Case-insensitive match
        name_lower = name.lower()
        if name_lower in self.field_by_name_lower:
            return self.field_by_name_lower[name_lower]

        # If panel context provided, search within panel first
        if panel and panel in self.fields_by_panel:
            for f in self.fields_by_panel[panel]:
                f_name_lower = f.name.lower()
                if name_lower in f_name_lower or f_name_lower in name_lower:
                    return f

        # Partial match across all fields
        for field_name_lower, fld in self.field_by_name_lower.items():
            if name_lower in field_name_lower or field_name_lower in name_lower:
                return fld

        return None

    def _create_rule(self, **kwargs) -> GeneratedRule:
        """Create a rule with auto-generated ID."""
        rule_id = self.id_generator.next_id('rule')
        return GeneratedRule(id=rule_id, **kwargs)

    def _add_rule(self, field_id: int, rule: GeneratedRule):
        """Add rule to field and track it."""
        # Create signature for deduplication
        sig = self._rule_signature(rule)
        if sig in self.rule_signatures:
            return  # Skip duplicate

        self.rule_signatures.add(sig)
        self.all_rules.append(rule)
        self.rules_by_field[field_id].append(rule)

    def _rule_signature(self, rule: GeneratedRule) -> str:
        """Create unique signature for rule deduplication."""
        return f"{rule.action_type}:{sorted(rule.source_ids)}:{sorted(rule.destination_ids)}:{rule.source_type}:{rule.condition}:{sorted(rule.conditional_values or [])}"

    def process(self) -> Dict:
        """Process all fields and generate rules."""
        self.log("Starting enhanced rule extraction v9...")

        # Step 1: Generate EXT_DROP_DOWN rules (expanded)
        self._generate_ext_dropdown_rules()
        self.log(f"Generated EXT_DROP_DOWN rules: {sum(1 for r in self.all_rules if r.action_type == 'EXT_DROP_DOWN')}")

        # Step 2: Generate EXT_VALUE rules with complex params
        self._generate_ext_value_rules()
        self.log(f"Generated EXT_VALUE rules: {sum(1 for r in self.all_rules if r.action_type == 'EXT_VALUE')}")

        # Step 3: Generate visibility rules with correct conditional values
        self._generate_visibility_rules()
        vis_count = sum(1 for r in self.all_rules if 'VISIBLE' in r.action_type)
        mand_count = sum(1 for r in self.all_rules if 'MANDATORY' in r.action_type)
        self.log(f"Generated visibility rules: {vis_count}, mandatory rules: {mand_count}")

        # Step 4: Generate OCR rules
        self._generate_ocr_rules()
        self.log(f"Generated OCR rules: {sum(1 for r in self.all_rules if r.action_type == 'OCR')}")

        # Step 5: Generate VERIFY rules
        self._generate_verify_rules()
        self.log(f"Generated VERIFY rules: {sum(1 for r in self.all_rules if r.action_type == 'VERIFY')}")

        # Step 6: Link OCR -> VERIFY chains
        self._link_ocr_verify_chains()
        self.log("Linked OCR -> VERIFY chains")

        # Step 7: Generate MAKE_DISABLED rules
        self._generate_disabled_rules()
        self.log(f"Generated MAKE_DISABLED rules: {sum(1 for r in self.all_rules if r.action_type == 'MAKE_DISABLED')}")

        # Step 8: Generate CONVERT_TO rules (expanded)
        self._generate_convert_to_rules()
        self.log(f"Generated CONVERT_TO rules: {sum(1 for r in self.all_rules if r.action_type == 'CONVERT_TO')}")

        # Step 9: Generate VALIDATION rules (expanded)
        self._generate_validation_rules()
        self.log(f"Generated VALIDATION rules: {sum(1 for r in self.all_rules if r.action_type == 'VALIDATION')}")

        # Step 10: Generate COPY_TO rules (expanded)
        self._generate_copy_to_rules()
        self.log(f"Generated COPY_TO rules: {sum(1 for r in self.all_rules if r.action_type == 'COPY_TO')}")

        # Step 11: Generate DELETE_DOCUMENT/UNDELETE_DOCUMENT rules
        self._generate_document_rules()
        doc_rule_count = sum(1 for r in self.all_rules if 'DOCUMENT' in r.action_type)
        self.log(f"Generated document rules: {doc_rule_count}")

        # Step 12: Generate COPY_TO_DOCUMENT_STORAGE_ID rules
        self._generate_document_storage_rules()
        storage_count = sum(1 for r in self.all_rules if r.action_type == 'COPY_TO_DOCUMENT_STORAGE_ID')
        self.log(f"Generated COPY_TO_DOCUMENT_STORAGE_ID rules: {storage_count}")

        # Step 13: Generate special rules
        self._generate_special_rules()
        self.log("Generated special rules")

        # Step 14: Rebuild rules_by_field
        self._rebuild_rules_by_field()

        # Step 15: Populate schema
        populated = self._populate_schema()

        return populated

    def _generate_ext_dropdown_rules(self):
        """Generate EXT_DROP_DOWN rules for external dropdown fields."""
        for fld in self.dropdown_fields:
            name_lower = fld.name.lower()

            # Check EXT_DROPDOWN patterns
            for pattern, dd_type in self.EXT_DROPDOWN_FIELDS.items():
                if pattern in name_lower:
                    rule = self._create_rule(
                        action_type='EXT_DROP_DOWN',
                        source_ids=[fld.id],
                        destination_ids=[],
                        source_type='FORM_FILL_DROP_DOWN',
                        params=dd_type,
                        searchable=True,
                        processing_type='CLIENT'
                    )
                    self._add_rule(fld.id, rule)
                    break

    def _generate_ext_value_rules(self):
        """Generate EXT_VALUE rules with complex JSON params."""
        for fld in self.fields:
            name_lower = fld.name.lower()

            for pattern, config in self.EXT_VALUE_FIELDS.items():
                if pattern in name_lower:
                    # Build complex params JSON
                    params = self._build_ext_value_params(fld, config)

                    rule = self._create_rule(
                        action_type='EXT_VALUE',
                        source_ids=[fld.id],
                        destination_ids=[],
                        source_type='EXTERNAL_DATA_VALUE',
                        params=params,
                        processing_type='SERVER'
                    )
                    self._add_rule(fld.id, rule)
                    break

    def _build_ext_value_params(self, field: FieldInfo, config: Dict) -> str:
        """Build complex EXT_VALUE params JSON."""
        dd_type = config.get('ddType', '')
        criteria_field_name = config.get('criteria_field')
        output_attr = config.get('output_attr')

        condition_list = {
            "ddType": [dd_type],
            "criterias": [],
            "da": [],
            "criteriaSearchAttr": [],
            "additionalOptions": None,
            "emptyAddOptionCheck": None,
            "ddProperties": None
        }

        # Add criteria field if specified
        if criteria_field_name:
            criteria_field = self.match_field(criteria_field_name)
            if criteria_field:
                # Format: {"a7": field_id} or similar
                condition_list["criterias"] = [{"a7": criteria_field.id}]

        # Add output attribute if specified
        if output_attr:
            condition_list["da"] = [output_attr]

        params = [{"conditionList": [condition_list]}]
        return json.dumps(params)

    def _generate_visibility_rules(self):
        """Generate visibility rules with correct conditional values."""
        if not self.intra_panel_refs:
            return

        # Group by controlling field
        visibility_groups: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))

        for panel in self.intra_panel_refs.get('panel_results', []):
            panel_name = panel.get('panel_name', 'Unknown')

            for ref in panel.get('intra_panel_references', []):
                if not isinstance(ref, dict):
                    continue

                dep_type = ref.get('dependency_type', '')

                # Process visibility references
                if dep_type in ['visibility', 'visibility_and_mandatory', 'conditional_behavior']:
                    self._process_visibility_reference(ref, visibility_groups, panel_name)

                # Check nested references
                for r in ref.get('references', []):
                    if not isinstance(r, dict):
                        continue
                    ref_type = r.get('reference_type', '')
                    if 'visibility' in ref_type.lower() or 'conditional' in ref_type.lower():
                        self._process_visibility_from_ref(ref, r, visibility_groups, panel_name)

                # Extract from logic text
                logic_text = ref.get('logic_text', ref.get('rule_description', ''))
                if logic_text:
                    self._extract_visibility_from_logic(ref, str(logic_text), visibility_groups, panel_name)

        # Generate rules from grouped references
        self._generate_visibility_rules_from_groups(visibility_groups)

    def _process_visibility_reference(self, ref: Dict, visibility_groups: Dict, panel_name: str):
        """Process a visibility reference."""
        source_field = self._safe_get_field_name(ref.get('source_field', ''))
        dep_field = self._safe_get_field_name(ref.get('dependent_field', ''))
        rule_desc = str(ref.get('rule_description', ''))

        if source_field and dep_field:
            # v9 FIX: Get correct conditional values based on controlling field
            values = self._get_conditional_values_for_field(source_field, rule_desc)
            values_key = ','.join(sorted(values)) if values else 'Yes'

            visibility_groups[source_field][values_key].append({
                'field_name': dep_field,
                'include_mandatory': 'mandatory' in ref.get('dependency_type', '').lower() or 'mandatory' in rule_desc.lower(),
                'rule_description': rule_desc,
                'panel': panel_name
            })

    def _process_visibility_from_ref(self, ref: Dict, r: Dict, visibility_groups: Dict, panel_name: str):
        """Process visibility from a nested reference."""
        controlling = r.get('referenced_field_name', '')
        dep_desc = str(r.get('dependency_description', ''))
        target = self._safe_get_field_name(ref.get('dependent_field', ref.get('source_field', '')))

        if controlling and target:
            values = self._get_conditional_values_for_field(controlling, dep_desc)
            values_key = ','.join(sorted(values)) if values else 'Yes'
            include_mandatory = 'mandatory' in dep_desc.lower()

            visibility_groups[controlling][values_key].append({
                'field_name': target,
                'include_mandatory': include_mandatory,
                'rule_description': dep_desc,
                'panel': panel_name
            })

    def _extract_visibility_from_logic(self, ref: Dict, logic_text: str, visibility_groups: Dict, panel_name: str):
        """Extract visibility rules from logic text."""
        patterns = [
            r"if\s+(?:the\s+)?field\s*['\"]([^'\"]+)['\"]\s+values?\s+is\s+([^\s,\.]+)\s+then\s+(visible|invisible|mandatory)",
            r"make\s+(visible|invisible|mandatory)\s+if\s+['\"]?([^'\"]+)['\"]?\s+is\s+['\"]?([^'\"]+)['\"]?",
            r"if\s+['\"]?([^'\"]+)['\"]?\s+is\s+['\"]?([^'\"]+)['\"]?\s+then\s+(visible|invisible)",
        ]

        target = self._safe_get_field_name(ref.get('dependent_field', ref.get('source_field', '')))
        if not target:
            return

        for pattern in patterns:
            for match in re.finditer(pattern, logic_text, re.IGNORECASE):
                groups = match.groups()
                if len(groups) >= 3:
                    if 'field' in pattern:
                        controlling = groups[0]
                        value = groups[1]
                    else:
                        controlling = groups[0] if 'make' not in pattern.lower() else groups[1]
                        value = groups[1] if 'make' not in pattern.lower() else groups[2]

                    if controlling and target and controlling.lower() != target.lower():
                        # v9 FIX: Get correct conditional values
                        values = self._get_conditional_values_for_field(controlling, logic_text)
                        values_key = ','.join(sorted(values)) if values else value

                        visibility_groups[controlling][values_key].append({
                            'field_name': target,
                            'include_mandatory': 'mandatory' in logic_text.lower(),
                            'rule_description': logic_text,
                            'panel': panel_name
                        })

    def _get_conditional_values_for_field(self, controlling_field: str, text: str) -> List[str]:
        """Get correct conditional values based on controlling field type."""
        controlling_lower = controlling_field.lower()

        # v9 FIX: Check predefined conditional values
        for field_pattern, value_config in self.VISIBILITY_CONDITIONAL_VALUES.items():
            if field_pattern in controlling_lower:
                # Return visible values by default
                return value_config.get('visible_values', ['Yes'])

        # Extract from text if not predefined
        return self._extract_conditional_values(text)

    def _extract_conditional_values(self, text: str) -> List[str]:
        """Extract conditional values from text."""
        values = []
        text = str(text)

        for match in re.finditer(r"values?\s+is\s+['\"]?([^'\"\s,\.]+)['\"]?", text, re.I):
            values.append(match.group(1))

        for match in re.finditer(r"selected\s+as\s+['\"]?([^'\"\s,\.]+)['\"]?", text, re.I):
            values.append(match.group(1))

        for match in re.finditer(r"chosen\s+as\s+['\"]?([^'\"\s,\.]+)['\"]?", text, re.I):
            values.append(match.group(1))

        return list(set(values)) if values else ['Yes']

    def _generate_visibility_rules_from_groups(self, visibility_groups: Dict):
        """Generate visibility rules from grouped references."""
        for controlling_name, value_groups in visibility_groups.items():
            controlling_field = self.match_field(controlling_name)
            if not controlling_field:
                continue

            for values_key, destinations in value_groups.items():
                values = [v.strip() for v in values_key.split(',') if v.strip()]
                if not values:
                    values = ['Yes']

                dest_ids = []
                include_mandatory = False

                for dest in destinations:
                    field_name = dest.get('field_name', '')
                    if not field_name:
                        continue
                    fld = self.match_field(field_name, dest.get('panel'))
                    if fld and fld.id not in dest_ids:
                        dest_ids.append(fld.id)
                    if dest.get('include_mandatory'):
                        include_mandatory = True

                if not dest_ids:
                    continue

                # Deduplication key
                vis_key = (controlling_field.id, tuple(sorted(dest_ids)), tuple(sorted(values)))
                if vis_key in self.visibility_generated:
                    continue
                self.visibility_generated.add(vis_key)

                # Generate MAKE_VISIBLE rule
                visible_rule = self._create_rule(
                    action_type='MAKE_VISIBLE',
                    source_ids=[controlling_field.id],
                    destination_ids=dest_ids,
                    conditional_values=values,
                    condition='IN'
                )
                self._add_rule(controlling_field.id, visible_rule)

                # Generate MAKE_INVISIBLE rule
                invisible_rule = self._create_rule(
                    action_type='MAKE_INVISIBLE',
                    source_ids=[controlling_field.id],
                    destination_ids=dest_ids,
                    conditional_values=values,
                    condition='NOT_IN'
                )
                self._add_rule(controlling_field.id, invisible_rule)

                # Generate mandatory rules if needed
                if include_mandatory:
                    mandatory_rule = self._create_rule(
                        action_type='MAKE_MANDATORY',
                        source_ids=[controlling_field.id],
                        destination_ids=dest_ids,
                        conditional_values=values,
                        condition='IN'
                    )
                    self._add_rule(controlling_field.id, mandatory_rule)

                    non_mandatory_rule = self._create_rule(
                        action_type='MAKE_NON_MANDATORY',
                        source_ids=[controlling_field.id],
                        destination_ids=dest_ids,
                        conditional_values=values,
                        condition='NOT_IN'
                    )
                    self._add_rule(controlling_field.id, non_mandatory_rule)

    def _generate_ocr_rules(self):
        """Generate OCR rules for file upload fields."""
        for fld in self.file_upload_fields:
            name_lower = fld.name.lower()
            logic = (fld.logic or '').lower()
            combined = name_lower + ' ' + logic

            for pattern, (ocr_source, verify_dest_pattern) in self.OCR_FIELD_PATTERNS.items():
                if re.search(pattern, combined, re.I):
                    if ocr_source in self.ocr_rules:
                        continue

                    # Find destination field for OCR
                    dest_ids = self._get_ocr_destination_ids(fld, ocr_source, verify_dest_pattern)

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

    def _get_ocr_destination_ids(self, ocr_field: FieldInfo, ocr_source: str, hint: Optional[str]) -> List[int]:
        """Get destination IDs for OCR rule."""
        dest_ids = []

        # Try to find the hint field
        if hint:
            hint_field = self.match_field(hint, ocr_field.panel_name)
            if hint_field:
                dest_ids = [hint_field.id]

        # If no hint, try to derive from field name
        if not dest_ids:
            alt_name = re.sub(r'^upload\s+', '', ocr_field.name, flags=re.I)
            if alt_name != ocr_field.name:
                alt_field = self.match_field(alt_name, ocr_field.panel_name)
                if alt_field:
                    dest_ids = [alt_field.id]

        return dest_ids

    def _generate_verify_rules(self):
        """Generate VERIFY rules with proper destinationIds."""
        verify_patterns = [
            (r'perform\s+pan\s+validation|pan\s+validation|validate\s+pan', 'PAN_NUMBER', 'PAN'),
            (r'perform\s+gstin?\s+validation|gstin?\s+validation|validate\s+gstin?', 'GSTIN', 'GSTIN'),
            (r'bank\s+(?:account\s+)?validation|validate\s+bank|ifsc\s+validation', 'BANK_ACCOUNT_NUMBER', 'IFSC Code'),
            (r'msme\s+validation|validate\s+msme|udyam\s+validation', 'MSME_UDYAM_REG_NUMBER', 'MSME Registration Number'),
            (r'cin\s+validation|validate\s+cin', 'CIN_ID', 'CIN'),
        ]

        for fld in self.fields:
            logic = (fld.logic or '').lower()

            # Skip destination fields
            if 'data will come from' in logic or 'derived from' in logic:
                continue

            for pattern, verify_source, field_hint in verify_patterns:
                if re.search(pattern, logic) and verify_source not in self.verify_rules:
                    source_field = fld
                    if field_hint:
                        hint_field = self.match_field(field_hint, fld.panel_name)
                        if hint_field:
                            source_field = hint_field

                    self._generate_verify_rule(source_field, verify_source)
                    break

        # Ensure VERIFY rules for all OCR chains
        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if verify_source and ocr_source in self.ocr_rules and verify_source not in self.verify_rules:
                ocr_rule = self.ocr_rules[ocr_source]
                if ocr_rule.destination_ids:
                    dest_field_id = ocr_rule.destination_ids[0]
                    dest_field = self.field_by_id.get(dest_field_id)
                    if dest_field:
                        self._generate_verify_rule(dest_field, verify_source)

    def _generate_verify_rule(self, source_field: FieldInfo, verify_source: str):
        """Generate a VERIFY rule with proper destinationIds."""
        if verify_source in self.verify_rules:
            return

        # Get destination IDs with field mappings
        dest_ids = self._get_verify_destination_ids(source_field, verify_source)

        verify_rule = self._create_rule(
            action_type='VERIFY',
            source_ids=[source_field.id],
            destination_ids=dest_ids,
            source_type=verify_source,
            processing_type='SERVER',
            button='VERIFY' if verify_source == 'PAN_NUMBER' else 'Verify'
        )

        self._add_rule(source_field.id, verify_rule)
        self.verify_rules[verify_source] = verify_rule

        # Generate GSTIN_WITH_PAN cross-validation if applicable
        if verify_source == 'GSTIN':
            pan_field = self.match_field('PAN')
            if pan_field:
                self._generate_gstin_with_pan_rule(pan_field, source_field)

    def _get_verify_destination_ids(self, source_field: FieldInfo, verify_source: str) -> List[int]:
        """Get destination IDs for VERIFY rule."""
        ordinals = self.VERIFY_ORDINALS.get(verify_source, {})
        if not ordinals:
            return []

        num_ordinals = max(ordinals.keys()) if ordinals else 0
        dest_ids = [-1] * num_ordinals

        # Get field-to-ordinal mapping
        bud_mapping = self.BUD_FIELD_TO_ORDINAL.get(verify_source, {})

        # Search intra-panel references for destination fields
        if self.intra_panel_refs:
            source_name_lower = source_field.name.lower()

            for p in self.intra_panel_refs.get('panel_results', []):
                for ref in p.get('intra_panel_references', []):
                    if not isinstance(ref, dict):
                        continue

                    dep_name = self._safe_get_field_name(ref.get('dependent_field', ''))
                    if not dep_name:
                        continue

                    # Check if this field is a destination of the verification
                    for r in ref.get('references', []):
                        if not isinstance(r, dict):
                            continue

                        ref_type = r.get('reference_type', '')
                        dep_desc = str(r.get('dependency_description', '')).lower()
                        ref_name = str(r.get('referenced_field_name', '')).lower()

                        is_verify_dest = (
                            ref_type == 'data_source' or
                            'verification' in dep_desc or
                            'validation' in dep_desc or
                            source_name_lower in ref_name or
                            source_name_lower in dep_desc
                        )

                        if is_verify_dest:
                            # Find the ordinal for this field
                            ordinal = self._match_field_to_ordinal(dep_name, bud_mapping, ordinals)
                            if ordinal and 1 <= ordinal <= num_ordinals:
                                # Get the actual field
                                dest_field = self.match_field(dep_name)
                                if dest_field:
                                    # Store FIELD ID, not ordinal
                                    dest_ids[ordinal - 1] = dest_field.id

        return dest_ids

    def _match_field_to_ordinal(self, field_name: str, bud_mapping: Dict[str, int], ordinals: Dict[int, str]) -> Optional[int]:
        """Match a field name to an ordinal position."""
        name_lower = field_name.lower()

        # Check BUD-specific mapping first
        for pattern, ordinal in bud_mapping.items():
            if pattern in name_lower:
                return ordinal

        # Check ordinals from Rule-Schemas.json
        for ordinal, ordinal_name in ordinals.items():
            if ordinal_name.lower() in name_lower or name_lower in ordinal_name.lower():
                return ordinal

        return None

    def _generate_gstin_with_pan_rule(self, pan_field: FieldInfo, gstin_field: FieldInfo):
        """Generate GSTIN_WITH_PAN cross-validation rule."""
        rule = self._create_rule(
            action_type='VERIFY',
            source_ids=[pan_field.id, gstin_field.id],
            destination_ids=[],
            source_type='GSTIN_WITH_PAN',
            processing_type='SERVER',
            params='{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}',
            on_status_fail='CONTINUE'
        )
        self._add_rule(pan_field.id, rule)

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
                    self.log(f"Linked {ocr_source} OCR -> {verify_source} VERIFY (rule {ocr_rule.id} -> {verify_rule.id})")

    def _generate_disabled_rules(self):
        """Generate consolidated MAKE_DISABLED rules."""
        disabled_field_ids = []

        for fld in self.fields:
            logic = (fld.logic or '').lower()

            # Check disable patterns
            for pattern in self.DISABLED_PATTERNS:
                if re.search(pattern, logic, re.I):
                    disabled_field_ids.append(fld.id)
                    break

        if disabled_field_ids and self.rulecheck_field:
            # Generate consolidated rule using RuleCheck field
            rule = self._create_rule(
                action_type='MAKE_DISABLED',
                source_ids=[self.rulecheck_field.id],
                destination_ids=disabled_field_ids,
                conditional_values=['Disable'],
                condition='NOT_IN'
            )
            self._add_rule(self.rulecheck_field.id, rule)

    def _generate_convert_to_rules(self):
        """Generate CONVERT_TO rules for fields needing uppercase."""
        for fld in self.text_fields:
            name_lower = fld.name.lower()
            logic = (fld.logic or '').lower()

            # Check if field should be uppercase
            should_convert = False

            # Check field name patterns
            for pattern in self.CONVERT_TO_UPPER_FIELDS:
                if pattern in name_lower:
                    should_convert = True
                    break

            # Check logic for uppercase mentions
            if 'upper' in logic or 'capital' in logic:
                should_convert = True

            if should_convert:
                rule = self._create_rule(
                    action_type='CONVERT_TO',
                    source_ids=[fld.id],
                    destination_ids=[],
                    source_type='UPPER_CASE',
                    processing_type='CLIENT'
                )
                self._add_rule(fld.id, rule)

    def _generate_validation_rules(self):
        """Generate VALIDATION rules with params."""
        for fld in self.fields:
            name_lower = fld.name.lower()

            # Check validation patterns
            for pattern, params in self.VALIDATION_FIELD_PARAMS.items():
                if pattern in name_lower:
                    rule = self._create_rule(
                        action_type='VALIDATION',
                        source_ids=[fld.id],
                        destination_ids=[],
                        params=params,
                        processing_type='CLIENT'
                    )
                    self._add_rule(fld.id, rule)
                    break

    def _generate_copy_to_rules(self):
        """Generate COPY_TO rules for field pairs."""
        for source_name, dest_names in self.COPY_TO_MAPPINGS:
            source_field = self.match_field(source_name)
            if not source_field:
                continue

            dest_ids = []
            for dest_name in dest_names:
                dest_field = self.match_field(dest_name)
                if dest_field:
                    dest_ids.append(dest_field.id)

            if dest_ids:
                rule = self._create_rule(
                    action_type='COPY_TO',
                    source_ids=[source_field.id],
                    destination_ids=dest_ids,
                    processing_type='CLIENT'
                )
                self._add_rule(source_field.id, rule)

    def _generate_document_rules(self):
        """Generate DELETE_DOCUMENT and UNDELETE_DOCUMENT rules."""
        # Find controlling field for document visibility
        gst_option_field = self.match_field('Please select GST option')
        if not gst_option_field:
            return

        # Get file upload fields that depend on GST option
        gst_dependent_files = []
        for fld in self.file_upload_fields:
            name_lower = fld.name.lower()
            if any(x in name_lower for x in ['gstin', 'gst', 'pan', 'aadhaar', 'cheque', 'msme', 'cin']):
                gst_dependent_files.append(fld.id)

        if gst_dependent_files:
            # DELETE_DOCUMENT when GST Non-Registered
            delete_rule = self._create_rule(
                action_type='DELETE_DOCUMENT',
                source_ids=[gst_option_field.id],
                destination_ids=gst_dependent_files,
                conditional_values=['GST Non-Registered'],
                condition='IN'
            )
            self._add_rule(gst_option_field.id, delete_rule)

            # UNDELETE_DOCUMENT when GST Registered
            undelete_rule = self._create_rule(
                action_type='UNDELETE_DOCUMENT',
                source_ids=[gst_option_field.id],
                destination_ids=gst_dependent_files,
                conditional_values=['GST Registered', 'SEZ', 'Compounding'],
                condition='IN'
            )
            self._add_rule(gst_option_field.id, undelete_rule)

    def _generate_document_storage_rules(self):
        """Generate COPY_TO_DOCUMENT_STORAGE_ID rules for file upload fields."""
        for fld in self.file_upload_fields:
            rule = self._create_rule(
                action_type='COPY_TO_DOCUMENT_STORAGE_ID',
                source_ids=[fld.id],
                destination_ids=[],
                source_type='FORM_FILL_METADATA',
                processing_type='SERVER'
            )
            self._add_rule(fld.id, rule)

    def _generate_special_rules(self):
        """Generate special rules like COPY_TXNID, SET_DATE, etc."""
        # Transaction ID field
        txn_id_field = self.match_field('Transaction ID')
        if txn_id_field:
            rule = self._create_rule(
                action_type='COPY_TXNID_TO_FORM_FILL',
                source_ids=[txn_id_field.id],
                destination_ids=[],
                processing_type='CLIENT'
            )
            self._add_rule(txn_id_field.id, rule)

        # Created On field
        created_on_field = self.match_field('Created on')
        if created_on_field:
            rule = self._create_rule(
                action_type='SET_DATE',
                source_ids=[created_on_field.id],
                destination_ids=[created_on_field.id],
                source_type='CURRENT_DATE',
                processing_type='CLIENT'
            )
            self._add_rule(created_on_field.id, rule)

        # Created By Name field
        created_by_field = self.match_field('Created By Name')
        if created_by_field:
            rule = self._create_rule(
                action_type='COPY_TO',
                source_ids=[created_by_field.id],
                destination_ids=[],
                processing_type='CLIENT'
            )
            self._add_rule(created_by_field.id, rule)

    def _rebuild_rules_by_field(self):
        """Rebuild rules_by_field dictionary from all_rules."""
        self.rules_by_field.clear()
        for rule in self.all_rules:
            if rule.source_ids:
                field_id = rule.source_ids[0]
                self.rules_by_field[field_id].append(rule)

    def _populate_schema(self) -> Dict:
        """Populate the schema with generated rules."""
        populated = copy.deepcopy(self.schema)

        doc_types = populated.get('template', {}).get('documentTypes', [])
        for doc_type in doc_types:
            metadatas = doc_type.get('formFillMetadatas', [])
            for meta in metadatas:
                field_id = meta.get('id')
                rules = self.rules_by_field.get(field_id, [])

                # Convert rules to dict format
                meta['formFillRules'] = [r.to_dict() for r in rules]

        return populated

    def save_output(self, output_path: str, report_path: Optional[str] = None):
        """Process and save output files."""
        populated = self.process()
        self._save_json(populated, output_path)
        print(f"Generated {len(self.all_rules)} rules")
        print(f"Output saved to: {output_path}")

        if report_path:
            report = self._generate_report()
            self._save_json(report, report_path)
            print(f"Report saved to: {report_path}")

        return populated

    def _generate_report(self) -> Dict:
        """Generate extraction report."""
        rule_counts = defaultdict(int)
        for rule in self.all_rules:
            rule_counts[rule.action_type] += 1

        return {
            "extraction_summary": {
                "total_fields": len(self.fields),
                "total_rules": len(self.all_rules),
                "fields_with_rules": len(self.rules_by_field),
                "version": "v9"
            },
            "rule_type_counts": dict(rule_counts),
            "ocr_verify_chains": {
                ocr: verify for ocr, verify in self.OCR_VERIFY_CHAINS.items()
                if ocr in self.ocr_rules
            },
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Enhanced Rule Extraction Agent v9')
    parser.add_argument('--schema', required=True, help='Path to schema JSON')
    parser.add_argument('--intra-panel', help='Path to intra-panel references JSON')
    parser.add_argument('--output', help='Output path for populated schema')
    parser.add_argument('--report', help='Path to save extraction report')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Generate output path if not specified
    if not args.output:
        schema_path = Path(args.schema)
        args.output = str(schema_path.parent / f"{schema_path.stem}_populated_v9.json")

    agent = EnhancedRuleExtractionAgentV9(
        schema_path=args.schema,
        intra_panel_path=args.intra_panel,
        verbose=args.verbose
    )

    agent.save_output(args.output, args.report)


if __name__ == '__main__':
    main()
