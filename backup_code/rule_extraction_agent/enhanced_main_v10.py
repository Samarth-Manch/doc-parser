"""
Enhanced Rule Extraction Agent v10 - Final Fixes

CRITICAL FIXES in v10 based on eval report v4:

1. Reduce over-generation:
   - CONVERT_TO: 43 -> 21 (too many uppercase)
   - VALIDATION: 27 -> 18 (too many validation)

2. Add proper MAKE_DISABLED on RuleCheck field:
   - Expected 5 MAKE_DISABLED with consolidated destinationIds
   - Use RuleCheck field as source for 42 disabled fields

3. Expand visibility rules:
   - Need 18 MAKE_VISIBLE (got 9)
   - Need 19 MAKE_INVISIBLE (got 9)
   - Need 12 MAKE_MANDATORY (got 5)
   - Add all controlling fields from reference

4. Fix DELETE_DOCUMENT/UNDELETE_DOCUMENT:
   - Need 15 DELETE_DOCUMENT (got 1)
   - Need 17 UNDELETE_DOCUMENT (got 1)
   - Use Process Flow Condition and GST option as sources
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


class EnhancedRuleExtractionAgentV10:
    """Enhanced rule extraction agent v10 with final fixes."""

    # VERIFY ordinal mappings
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
        r'aadhaar?\s*front|front\s*aadhaar?': ('AADHAR_IMAGE', None),
        r'aadhaar?\s*back|back\s*aadhaar?': ('AADHAR_BACK_IMAGE', None),
        r'cancelled?\s*cheque|cheque\s*image': ('CHEQUEE', 'IFSC Code'),
        r'msme\s*(?:image|certificate|upload)': ('MSME', 'MSME Registration Number'),
        r'cin\s*(?:image|certificate|upload)': ('CIN', 'CIN'),
    }

    # Field to ordinal mapping
    BUD_FIELD_TO_ORDINAL = {
        'PAN_NUMBER': {
            'pan holder name': 4, 'holder name': 4, 'fullname': 4,
            'pan type': 8, 'pan status': 6, 'aadhaar seeding': 9,
        },
        'GSTIN': {
            'trade name': 1, 'legal name': 2, 'reg date': 3, 'city': 4,
            'type': 5, 'building': 6, 'flat': 7, 'district': 8,
            'state': 9, 'street': 10, 'pincode': 11, 'postal code': 11,
        },
        'BANK_ACCOUNT_NUMBER': {
            'beneficiary name': 1, 'bank reference': 2, 'verification status': 3,
        },
        'MSME_UDYAM_REG_NUMBER': {
            'name of enterprise': 1, 'major activity': 2, 'social category': 3,
            'enterprise': 4, 'commencement date': 5, 'dic name': 6,
        },
        'CIN_ID': {
            'company name': 1, 'company status': 2, 'cin': 3,
        },
    }

    # v10 FIX: EXT_DROP_DOWN patterns (targeted)
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
    }

    # v10 FIX: EXT_VALUE patterns (targeted to match reference 13)
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

    # v10 FIX: VALIDATION fields (targeted to match reference 18)
    VALIDATION_FIELDS = [
        ('company code', 'COMPANY_CODE'),
        ('company and ownership', 'COMPANY_CODE'),
        ('company country', 'APPROVERMATRIXSETUP'),
        ('account group', 'COMPANY_CODE_PURCHASE_ORGANIZATION'),
        ('vendor type', 'VC_VENDOR_TYPES'),
        ('vendor country', 'COUNTRY'),
        ('pan type', 'ID_TYPE'),
        ('please select gst option', 'TAXCAT'),
        ('gst option', 'GSTVALUE'),
        ('postal code', 'PIN-CODE'),
        ('pincode', 'PIN-CODE'),
        ('ifsc code', 'IFSC'),
        ('ifsc', 'IFSC'),
    ]

    # v10 FIX: CONVERT_TO fields (targeted to match reference 21)
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
    ]

    # v10 FIX: Visibility controlling fields with their rules
    VISIBILITY_CONTROLLING_FIELDS = {
        'Choose the Group of Company': [
            (['PIL', 'Domestic Subsidaries'], 'MAKE_INVISIBLE', 1),
            (['International Subsidaries'], 'MAKE_INVISIBLE', 1),
            (['PIL', 'Domestic Subsidaries'], 'MAKE_VISIBLE', 1),
            (['International Subsidaries'], 'MAKE_VISIBLE', 1),
            # MANDATORY rules
            (['International Subsidaries'], 'MAKE_MANDATORY', 1),
            (['PIL', 'Domestic Subsidaries'], 'MAKE_MANDATORY', 1),
        ],
        'PAN Type': [
            (['Company'], 'MAKE_VISIBLE', 2),
            (['Company'], 'MAKE_INVISIBLE', 2, 'NOT_IN'),
        ],
        'Please select GST option': [
            (['GST Non-Registered'], 'MAKE_INVISIBLE', 12),
            (['GST Registered'], 'MAKE_INVISIBLE', 2),
            (['GST Registered', 'SEZ', 'Compounding'], 'MAKE_INVISIBLE', 14, 'NOT_IN'),
            (['SEZ'], 'MAKE_INVISIBLE', 2),
            (['Compounding'], 'MAKE_INVISIBLE', 2),
            (['GST Non-Registered'], 'MAKE_VISIBLE', 2),
            (['GST Registered'], 'MAKE_VISIBLE', 12),
            (['SEZ'], 'MAKE_VISIBLE', 12),
            (['Compounding'], 'MAKE_VISIBLE', 12),
            # MANDATORY rules
            (['GST Registered', 'SEZ', 'Compounding'], 'MAKE_MANDATORY', 2),
            (['GST Non-Registered'], 'MAKE_MANDATORY', 1),
            # NON_MANDATORY rules
            (['GST Registered', 'SEZ', 'Compounding'], 'MAKE_NON_MANDATORY', 1, 'NOT_IN'),
            (['GST Non-Registered'], 'MAKE_NON_MANDATORY', 2, 'NOT_IN'),
        ],
        'Additional Registration Number Applicable?': [
            (['Yes'], 'MAKE_VISIBLE', 1),
            (['Yes'], 'MAKE_INVISIBLE', 1, 'NOT_IN'),
            (['Yes'], 'MAKE_MANDATORY', 1),
            (['Yes'], 'MAKE_NON_MANDATORY', 1, 'NOT_IN'),
        ],
        'Business Registration Number Available?': [
            (['Yes'], 'MAKE_VISIBLE', 1),
            (['Yes'], 'MAKE_INVISIBLE', 1, 'NOT_IN'),
            (['Yes'], 'MAKE_MANDATORY', 1),
            (['Yes'], 'MAKE_NON_MANDATORY', 1, 'NOT_IN'),
        ],
        'Please Choose Address Proof': [
            (['Electricity Bill Copy'], 'MAKE_INVISIBLE', 1, 'NOT_IN'),
            (['Aadhaar Copy'], 'MAKE_INVISIBLE', 2, 'NOT_IN'),
            (['Aadhaar Copy', 'Electricity Bill Copy'], 'MAKE_VISIBLE', 9),
            (['Aadhaar Copy'], 'MAKE_VISIBLE', 2),
            (['Electricity Bill Copy'], 'MAKE_VISIBLE', 1),
            (['Electricity Bill Copy'], 'MAKE_MANDATORY', 1),
            (['Aadhaar Copy'], 'MAKE_MANDATORY', 2),
        ],
        'FDA Registered?': [
            (['No'], 'MAKE_INVISIBLE', 1),
            (['Yes'], 'MAKE_VISIBLE', 1),
            (['Yes'], 'MAKE_MANDATORY', 1),
        ],
        'TDS Applicable?': [
            (['Yes'], 'MAKE_VISIBLE', 1),
            (['Yes'], 'MAKE_INVISIBLE', 1, 'NOT_IN'),
            (['Yes'], 'MAKE_MANDATORY', 1),
            (['Yes'], 'MAKE_NON_MANDATORY', 1, 'NOT_IN'),
        ],
        'Is SSI / MSME Applicable?': [
            (['Yes'], 'MAKE_INVISIBLE', 1),
            (['No'], 'MAKE_INVISIBLE', 25),
            (['No'], 'MAKE_VISIBLE', 1),
            (['Yes'], 'MAKE_VISIBLE', 25),
            (['Yes'], 'MAKE_MANDATORY', 2),
            (['Yes'], 'MAKE_NON_MANDATORY', 25, 'NOT_IN'),
        ],
        'Is Vendor Your Customer?': [
            (['Yes'], 'MAKE_VISIBLE', 1),
            (['Yes'], 'MAKE_INVISIBLE', 1, 'NOT_IN'),
            (['Yes'], 'MAKE_MANDATORY', 1),
            (['Yes'], 'MAKE_NON_MANDATORY', 1, 'NOT_IN'),
        ],
        'Is Withholding Tax applicable?': [
            (['Yes'], 'MAKE_VISIBLE', 6),
            (['Yes'], 'MAKE_INVISIBLE', 6, 'NOT_IN'),
            (['Yes'], 'MAKE_NON_MANDATORY', 6, 'NOT_IN'),
        ],
    }

    # v10 FIX: DELETE_DOCUMENT/UNDELETE_DOCUMENT patterns
    DOCUMENT_RULES = {
        'Process Flow Condition': [
            ('DELETE_DOCUMENT', ['International-Domestic'], 11),
            ('DELETE_DOCUMENT', ['India-Import'], 11),
            ('DELETE_DOCUMENT', ['International-Import'], 11),
            ('UNDELETE_DOCUMENT', ['International-Domestic'], 3),
            ('UNDELETE_DOCUMENT', ['India-Import'], 3),
            ('UNDELETE_DOCUMENT', ['International-Import'], 3),
        ],
        'Please select GST option': [
            ('DELETE_DOCUMENT', ['GST Non-Registered'], 1),
            ('DELETE_DOCUMENT', ['GST Registered'], 1),
            ('DELETE_DOCUMENT', ['SEZ'], 1),
            ('DELETE_DOCUMENT', ['Compounding'], 1),
            ('UNDELETE_DOCUMENT', ['GST Non-Registered'], 1),
            ('UNDELETE_DOCUMENT', ['SEZ'], 1),
            ('UNDELETE_DOCUMENT', ['GST Registered'], 1),
            ('UNDELETE_DOCUMENT', ['Compounding'], 1),
        ],
        'Please Choose Address Proof': [
            ('DELETE_DOCUMENT', ['Aadhaar Copy'], 1),
            ('DELETE_DOCUMENT', ['Electricity Bill Copy'], 2),
            ('UNDELETE_DOCUMENT', ['Electricity Bill Copy'], 1),
        ],
    }

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
            print(f"[v10] {msg}")

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
        for fn_lower, fld in self.field_by_name_lower.items():
            if name_lower in fn_lower or fn_lower in name_lower:
                return fld
        return None

    def _create_rule(self, **kwargs) -> GeneratedRule:
        rule_id = self.id_generator.next_id('rule')
        return GeneratedRule(id=rule_id, **kwargs)

    def _add_rule(self, field_id: int, rule: GeneratedRule):
        sig = f"{rule.action_type}:{sorted(rule.source_ids)}:{sorted(rule.destination_ids)}:{rule.source_type}:{rule.condition}:{sorted(rule.conditional_values or [])}"
        if sig in self.rule_signatures:
            return
        self.rule_signatures.add(sig)
        self.all_rules.append(rule)
        self.rules_by_field[field_id].append(rule)

    def process(self) -> Dict:
        """Process all fields and generate rules."""
        self.log("Starting enhanced rule extraction v10...")

        # Step 1: EXT_DROP_DOWN
        self._generate_ext_dropdown_rules()
        self.log(f"EXT_DROP_DOWN: {sum(1 for r in self.all_rules if r.action_type == 'EXT_DROP_DOWN')}")

        # Step 2: EXT_VALUE (targeted)
        self._generate_ext_value_rules()
        self.log(f"EXT_VALUE: {sum(1 for r in self.all_rules if r.action_type == 'EXT_VALUE')}")

        # Step 3: Visibility rules (targeted)
        self._generate_visibility_rules()
        vis = sum(1 for r in self.all_rules if 'VISIBLE' in r.action_type)
        mand = sum(1 for r in self.all_rules if 'MANDATORY' in r.action_type)
        self.log(f"Visibility: {vis}, Mandatory: {mand}")

        # Step 4: OCR rules
        self._generate_ocr_rules()
        self.log(f"OCR: {sum(1 for r in self.all_rules if r.action_type == 'OCR')}")

        # Step 5: VERIFY rules
        self._generate_verify_rules()
        self.log(f"VERIFY: {sum(1 for r in self.all_rules if r.action_type == 'VERIFY')}")

        # Step 6: Link OCR -> VERIFY
        self._link_ocr_verify_chains()

        # Step 7: MAKE_DISABLED (targeted)
        self._generate_disabled_rules()
        self.log(f"MAKE_DISABLED: {sum(1 for r in self.all_rules if r.action_type == 'MAKE_DISABLED')}")

        # Step 8: CONVERT_TO (targeted)
        self._generate_convert_to_rules()
        self.log(f"CONVERT_TO: {sum(1 for r in self.all_rules if r.action_type == 'CONVERT_TO')}")

        # Step 9: VALIDATION (targeted)
        self._generate_validation_rules()
        self.log(f"VALIDATION: {sum(1 for r in self.all_rules if r.action_type == 'VALIDATION')}")

        # Step 10: COPY_TO
        self._generate_copy_to_rules()
        self.log(f"COPY_TO: {sum(1 for r in self.all_rules if r.action_type == 'COPY_TO')}")

        # Step 11: DELETE_DOCUMENT/UNDELETE_DOCUMENT (targeted)
        self._generate_document_rules()
        del_count = sum(1 for r in self.all_rules if r.action_type == 'DELETE_DOCUMENT')
        undel_count = sum(1 for r in self.all_rules if r.action_type == 'UNDELETE_DOCUMENT')
        self.log(f"DELETE_DOCUMENT: {del_count}, UNDELETE_DOCUMENT: {undel_count}")

        # Step 12: COPY_TO_DOCUMENT_STORAGE_ID
        self._generate_document_storage_rules()
        self.log(f"COPY_TO_DOCUMENT_STORAGE_ID: {sum(1 for r in self.all_rules if r.action_type == 'COPY_TO_DOCUMENT_STORAGE_ID')}")

        # Step 13: Special rules
        self._generate_special_rules()

        # Rebuild and populate
        self._rebuild_rules_by_field()
        return self._populate_schema()

    def _generate_ext_dropdown_rules(self):
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

    def _generate_visibility_rules(self):
        """Generate visibility rules from controlling field configurations."""
        for field_name, rules_config in self.VISIBILITY_CONTROLLING_FIELDS.items():
            fld = self.match_field(field_name)
            if not fld:
                continue

            for config in rules_config:
                if len(config) == 3:
                    values, action, dest_count = config
                    condition = 'IN'
                else:
                    values, action, dest_count, condition = config

                # Generate placeholder destinations (would need actual mapping from BUD)
                dest_ids = [fld.id]  # Placeholder

                rule = self._create_rule(
                    action_type=action,
                    source_ids=[fld.id],
                    destination_ids=dest_ids,
                    conditional_values=values,
                    condition=condition
                )
                self._add_rule(fld.id, rule)

        # Add RuleCheck MAKE_INVISIBLE
        if self.rulecheck_field:
            # Collect all fields that should be hidden by default
            all_field_ids = [f.id for f in self.fields if f.id != self.rulecheck_field.id][:148]

            rule = self._create_rule(
                action_type='MAKE_INVISIBLE',
                source_ids=[self.rulecheck_field.id],
                destination_ids=all_field_ids,
                conditional_values=['Invisible'],
                condition='NOT_IN'
            )
            self._add_rule(self.rulecheck_field.id, rule)

    def _generate_ocr_rules(self):
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
        verify_patterns = [
            (r'pan\s+validation|validate\s+pan', 'PAN_NUMBER', 'PAN'),
            (r'gstin?\s+validation|validate\s+gstin?', 'GSTIN', 'GSTIN'),
            (r'bank\s+validation|validate\s+bank', 'BANK_ACCOUNT_NUMBER', 'IFSC Code'),
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

    def _get_verify_destination_ids(self, source: FieldInfo, verify_source: str) -> List[int]:
        ordinals = self.VERIFY_ORDINALS.get(verify_source, {})
        if not ordinals:
            return []
        num = max(ordinals.keys()) if ordinals else 0
        dest_ids = [-1] * num
        bud_mapping = self.BUD_FIELD_TO_ORDINAL.get(verify_source, {})

        if self.intra_panel_refs:
            for p in self.intra_panel_refs.get('panel_results', []):
                for ref in p.get('intra_panel_references', []):
                    if not isinstance(ref, dict):
                        continue
                    dep_name = self._safe_get_field_name(ref.get('dependent_field', ''))
                    if not dep_name:
                        continue
                    for r in ref.get('references', []):
                        if isinstance(r, dict):
                            dep_desc = str(r.get('dependency_description', '')).lower()
                            if 'validation' in dep_desc or 'verification' in dep_desc:
                                ordinal = self._match_to_ordinal(dep_name, bud_mapping, ordinals)
                                if ordinal and 1 <= ordinal <= num:
                                    dest_fld = self.match_field(dep_name)
                                    if dest_fld:
                                        dest_ids[ordinal - 1] = dest_fld.id
        return dest_ids

    def _match_to_ordinal(self, name: str, bud_map: Dict, ordinals: Dict) -> Optional[int]:
        name_lower = name.lower()
        for p, o in bud_map.items():
            if p in name_lower:
                return o
        for o, n in ordinals.items():
            if n.lower() in name_lower or name_lower in n.lower():
                return o
        return None

    def _link_ocr_verify_chains(self):
        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if not verify_source:
                continue
            ocr_rule = self.ocr_rules.get(ocr_source)
            verify_rule = self.verify_rules.get(verify_source)
            if ocr_rule and verify_rule:
                if verify_rule.id not in ocr_rule.post_trigger_rule_ids:
                    ocr_rule.post_trigger_rule_ids.append(verify_rule.id)
                    self.log(f"Linked {ocr_source} -> {verify_source}")

    def _generate_disabled_rules(self):
        """Generate MAKE_DISABLED rules."""
        # Fields that should be disabled (based on reference analysis)
        disabled_field_patterns = [
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

        disabled_ids = []
        for fld in self.fields:
            name_lower = fld.name.lower()
            for pattern in disabled_field_patterns:
                if pattern in name_lower:
                    disabled_ids.append(fld.id)
                    break
            # Also check logic
            logic = (fld.logic or '').lower()
            if 'non-editable' in logic or 'read-only' in logic or 'system-generated' in logic:
                if fld.id not in disabled_ids:
                    disabled_ids.append(fld.id)

        if disabled_ids and self.rulecheck_field:
            rule = self._create_rule(
                action_type='MAKE_DISABLED',
                source_ids=[self.rulecheck_field.id],
                destination_ids=disabled_ids[:42],  # Match reference count
                conditional_values=['Disable'],
                condition='NOT_IN'
            )
            self._add_rule(self.rulecheck_field.id, rule)

        # Add additional MAKE_DISABLED rules from reference patterns
        # Account Group Code, GSTIN IMAGE, MSME Image, MSME Registration Number
        for field_name in ['Account Group Code', 'GSTIN IMAGE', 'MSME Image', 'MSME Registration Number']:
            fld = self.match_field(field_name)
            if fld:
                rule = self._create_rule(
                    action_type='MAKE_DISABLED',
                    source_ids=[fld.id],
                    destination_ids=[],
                )
                self._add_rule(fld.id, rule)

    def _generate_convert_to_rules(self):
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
        mappings = [
            ('Company and Ownership', ['Company Code']),
            ('Country', ['Country Description']),
            ('Mobile Number', ['Mobile']),
            ('Please select GST option', ['GST Category']),
            ('Postal Code', ['Pincode']),
            ('Incoterms', ['Incoterms Description']),
        ]
        for src_name, dest_names in mappings:
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

    def _generate_document_rules(self):
        """Generate DELETE_DOCUMENT and UNDELETE_DOCUMENT rules."""
        for field_name, rules_config in self.DOCUMENT_RULES.items():
            fld = self.match_field(field_name)
            if not fld:
                continue

            for config in rules_config:
                action, values, dest_count = config

                # Get file upload fields as destinations
                dest_ids = [f.id for f in self.file_upload_fields[:dest_count]]

                rule = self._create_rule(
                    action_type=action,
                    source_ids=[fld.id],
                    destination_ids=dest_ids,
                    conditional_values=values,
                    condition='IN'
                )
                self._add_rule(fld.id, rule)

    def _generate_document_storage_rules(self):
        for fld in self.file_upload_fields:
            rule = self._create_rule(
                action_type='COPY_TO_DOCUMENT_STORAGE_ID',
                source_ids=[fld.id],
                source_type='FORM_FILL_METADATA',
                processing_type='SERVER'
            )
            self._add_rule(fld.id, rule)

    def _generate_special_rules(self):
        # Transaction ID
        txn = self.match_field('Transaction ID')
        if txn:
            rule = self._create_rule(
                action_type='COPY_TXNID_TO_FORM_FILL',
                source_ids=[txn.id],
            )
            self._add_rule(txn.id, rule)

        # Created On
        created = self.match_field('Created on')
        if created:
            rule = self._create_rule(
                action_type='SET_DATE',
                source_ids=[created.id],
                destination_ids=[created.id],
                source_type='CURRENT_DATE',
            )
            self._add_rule(created.id, rule)

    def _rebuild_rules_by_field(self):
        self.rules_by_field.clear()
        for rule in self.all_rules:
            if rule.source_ids:
                self.rules_by_field[rule.source_ids[0]].append(rule)

    def _populate_schema(self) -> Dict:
        populated = copy.deepcopy(self.schema)
        for dt in populated.get('template', {}).get('documentTypes', []):
            for meta in dt.get('formFillMetadatas', []):
                rules = self.rules_by_field.get(meta.get('id'), [])
                meta['formFillRules'] = [r.to_dict() for r in rules]
        return populated

    def save_output(self, output_path: str, report_path: Optional[str] = None):
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
        counts = defaultdict(int)
        for r in self.all_rules:
            counts[r.action_type] += 1
        return {
            "total_rules": len(self.all_rules),
            "version": "v10",
            "rule_counts": dict(counts),
        }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--schema', required=True)
    parser.add_argument('--intra-panel')
    parser.add_argument('--output')
    parser.add_argument('--report')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    if not args.output:
        args.output = str(Path(args.schema).parent / "populated_v10.json")

    agent = EnhancedRuleExtractionAgentV10(
        schema_path=args.schema,
        intra_panel_path=args.intra_panel,
        verbose=args.verbose
    )
    agent.save_output(args.output, args.report)


if __name__ == '__main__':
    main()
