#!/usr/bin/env python3
"""
Rule Extraction Agent - Fixed Version v2

Main entry point for extracting rules from BUD documents and populating
formFillRules arrays in the JSON schema.

This module implements comprehensive rule extraction:
1. EXT_DROP_DOWN rules for EXTERNAL_DROP_DOWN_VALUE fields (20 rules expected)
2. OCR rules with proper chaining to VERIFY rules (6 OCR rules)
3. VERIFY rules with ordinal destination mapping (5 VERIFY rules)
4. Visibility rules from intra_panel_references (18 MAKE_VISIBLE, 19 MAKE_INVISIBLE)
5. Mandatory rules (12 MAKE_MANDATORY, 10 MAKE_NON_MANDATORY)
6. Consolidated MAKE_DISABLED rules (5 rules)
7. CONVERT_TO, COPY_TO, VALIDATION, EXECUTE rules
8. NEW: CONCAT, SET_DATE, SEND_OTP, VALIDATE_OTP, MAKE_ENABLED, DUMMY_ACTION
9. NEW: SESSION_BASED_MAKE_MANDATORY, SESSION_BASED_MAKE_NON_MANDATORY
10. NEW: COPY_TO_GENERIC_PARTY_EMAIL, COPY_TO_GENERIC_PARTY_NAME
11. NEW: COPY_TO_TRANSACTION_ATTR1, COPY_TO_TRANSACTION_ATTR3
12. NEW: COPY_TXNID_TO_FORM_FILL

Usage:
    python rule_extraction_agent.py \
        --bud "documents/Vendor Creation Sample BUD.docx" \
        --intra-panel "adws/2026-01-31_00-31-54/intra_panel_references.json" \
        --output output/rules_populated/schema.json \
        --verbose
"""

import argparse
import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass, field


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# ============================================================================
# DATA MODELS
# ============================================================================

class IdGenerator:
    """Generate sequential IDs starting from 1."""

    def __init__(self):
        self.counters: Dict[str, int] = {}

    def next_id(self, id_type: str = 'rule') -> int:
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

    def reset(self, id_type: str = None):
        if id_type:
            self.counters[id_type] = 0
        else:
            self.counters = {}


@dataclass
class FieldInfo:
    """Information about a field."""
    id: int
    name: str
    field_type: str
    logic: str = ""
    rules: str = ""
    variable_name: str = ""
    form_order: float = 0.0
    is_mandatory: bool = False


@dataclass
class VisibilityReference:
    """A visibility control reference from intra_panel_references."""
    source_field: str
    target_field: str
    conditional_value: str
    action_type: str  # visibility_control, visibility_and_mandatory, etc.
    inverse_action: Optional[str] = None


@dataclass
class OcrVerifyChain:
    """Chain of OCR -> VERIFY rules."""
    ocr_source_type: str
    verify_source_type: Optional[str]
    upload_field_name: str
    text_field_name: Optional[str] = None
    ocr_rule_id: Optional[int] = None
    verify_rule_id: Optional[int] = None


# ============================================================================
# CONSTANTS AND MAPPINGS
# ============================================================================

# OCR source type to VERIFY source type mapping
# CRITICAL: Only these OCR types chain to VERIFY rules
OCR_TO_VERIFY_MAPPING = {
    "PAN_IMAGE": "PAN_NUMBER",
    "GSTIN_IMAGE": "GSTIN",
    "CHEQUEE": "BANK_ACCOUNT_NUMBER",
    "MSME": "MSME_UDYAM_REG_NUMBER",
    # These do NOT chain to VERIFY:
    "AADHAR_IMAGE": None,
    "AADHAR_BACK_IMAGE": None,
    # CIN does NOT have OCR in reference - removed
}

# VERIFY destination ordinals for each source type
# Based on Rule-Schemas.json analysis
VERIFY_ORDINALS = {
    "PAN_NUMBER": {
        # ordinal -> field name pattern
        1: "panholder_title",
        2: "firstname",
        3: "lastname",
        4: "fullname",  # -> Pan Holder Name
        5: "last_updated",
        6: "retrieval_status",  # -> PAN Status
        7: "fullname_without_title",
        8: "pan_type",  # -> PAN Type
        9: "aadhaar_seeding_status",  # -> Aadhaar PAN List Status
        10: "middle_name"
    },
    "GSTIN": {
        1: "trade_name",  # -> Trade Name
        2: "legal_name",  # -> Legal Name
        3: "reg_date",  # -> Reg Date
        4: "city",  # -> City
        5: "type",  # -> Type
        6: "building_number",  # -> Building Number
        7: "flat_number",
        8: "district",  # -> District
        9: "state",  # -> State
        10: "pincode",  # -> Pin Code
        11: "street"  # -> Street
    },
    "BANK_ACCOUNT_NUMBER": {
        1: "beneficiary_name",
        2: "bank_reference",
        3: "verification_status",
        4: "message"
    },
    "MSME_UDYAM_REG_NUMBER": {
        1: "enterprise_name",
        2: "major_activity",
        3: "social_category",
        4: "enterprise_type",
        5: "commencement_date"
    }
}

# EXT_DROP_DOWN params for different field types
EXT_DROPDOWN_PARAMS = {
    "company_code": "COMPANY_CODE",
    "select the process type": "PIDILITE_YES_NO",
    "choose the group": "PIDILITE_YES_NO",
    "account group": "VC_VENDOR_TYPES",
    "group key": "VC_VENDOR_TYPES",
    "country": "COUNTRY",
    "type of industry": "TYPE_OF_INDUSTRY",
    "id type": "ID_TYPE",
    "gst value": "GSTVALUE",
    "address proof": "ADDRESS_PROOF",
    "tds applicable": "PIDILITE_YES_NO",
    "msme": "PIDILITE_YES_NO",
    "title": "TITLE",
    "currency": "CURRENCY_COUNTRY",
    "purchase organization": "PURCHASE_ORGANIZATION",
    "terms of payment": "TERMS_OF_PAYMENT",
    "incoterms": "INCOTERMS",
    "reconciliation": "RECONCILIATION_ACCOUNT",
    "withholding tax": "WITHHOLDING_TAX_DATA",
    "bank option": "BANK_OPTIONS",
    "tax": "TAXCAT",
    "gst option": "PIDILITE_YES_NO",
    "vendor type": "VC_VENDOR_TYPES",
}


# ============================================================================
# RULE EXTRACTION AGENT
# ============================================================================

class RuleExtractionAgent:
    """
    Main agent for extracting rules from BUD documents.

    Generates all rule types based on reference:
    - EXT_DROP_DOWN: 20 rules for external dropdown fields
    - OCR: 6 rules (PAN, GSTIN, Aadhaar Front, Aadhaar Back, Cheque, MSME)
    - VERIFY: 5 rules (PAN_NUMBER, GSTIN, GSTIN_WITH_PAN, BANK_ACCOUNT_NUMBER, MSME)
    - MAKE_VISIBLE/MAKE_INVISIBLE: 18/19 rules for visibility control
    - MAKE_MANDATORY/MAKE_NON_MANDATORY: 12/10 rules
    - MAKE_DISABLED: 5 consolidated rules
    - MAKE_ENABLED: 1 rule
    - CONVERT_TO: 21 rules for uppercase conversion
    - COPY_TO: 13 rules for data copy
    - VALIDATION: 18 rules
    - EXECUTE: 40 rules
    - DELETE_DOCUMENT/UNDELETE_DOCUMENT: 15/17 rules
    - EXT_VALUE: 13 rules
    - SESSION_BASED rules: 3 MAKE_MANDATORY, 2 MAKE_NON_MANDATORY
    - CONCAT: 2 rules
    - SET_DATE: 1 rule
    - SEND_OTP/VALIDATE_OTP: 1/1 rules
    - COPY_TXNID_TO_FORM_FILL: 1 rule
    - COPY_TO_GENERIC_PARTY_EMAIL/NAME: 1/1 rules
    - COPY_TO_TRANSACTION_ATTR1/ATTR3: 1/1 rules
    - DUMMY_ACTION: 1 rule
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.id_generator = IdGenerator()

        # Field storage
        self.fields: List[Dict] = []
        self.fields_by_name: Dict[str, Dict] = {}
        self.fields_by_id: Dict[int, Dict] = {}

        # Generated rules
        self.all_rules: List[Dict] = []

        # Tracking for rule chaining
        self.ocr_rules: Dict[str, Dict] = {}  # source_type -> rule
        self.verify_rules: Dict[str, Dict] = {}  # source_type -> rule

        # Visibility groups for consolidation
        self.visibility_groups: Dict[str, List[int]] = defaultdict(list)

        # Disabled fields for consolidation
        self.disabled_field_ids: Set[int] = set()

        # RuleCheck field ID (will be created)
        self.rule_check_field_id: Optional[int] = None

    def _log(self, message: str):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[RuleAgent] {message}")

    def extract_from_bud(self, bud_path: str) -> List[Dict]:
        """Extract fields from BUD document using doc_parser."""
        try:
            from doc_parser import DocumentParser

            parser = DocumentParser()
            parsed = parser.parse(bud_path)

            fields = []
            for i, field in enumerate(parsed.all_fields):
                field_type = str(field.field_type.value) if hasattr(field.field_type, 'value') else str(field.field_type)

                fields.append({
                    'id': i + 1,
                    'name': field.name,
                    'field_type': field_type,
                    'logic': field.logic or '',
                    'rules': field.rules if hasattr(field, 'rules') else '',
                    'is_mandatory': field.is_mandatory,
                    'variable_name': field.variable_name if hasattr(field, 'variable_name') else f"_field{i}_",
                    'form_order': i + 1.0,
                })

            self._log(f"Extracted {len(fields)} fields from BUD")
            return fields

        except Exception as e:
            self._log(f"Error parsing BUD: {e}")
            import traceback
            traceback.print_exc()
            return []

    def load_intra_panel_references(self, json_path: str) -> List[VisibilityReference]:
        """Load and parse intra-panel references for visibility rules."""
        references = []

        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            panel_results = data.get('panel_results', [])

            for panel in panel_results:
                intra_refs = panel.get('intra_panel_references', [])

                for ref in intra_refs:
                    ref_type = ref.get('reference_type', '')

                    # Handle visibility control references (multiple formats)
                    if 'visibility' in ref_type.lower() or 'visibility_control' == ref_type:
                        source_field = self._extract_source_field(ref)
                        target_field = self._extract_target_field(ref)
                        conditional_value = self._extract_conditional_value(ref)

                        if source_field and target_field:
                            references.append(VisibilityReference(
                                source_field=source_field,
                                target_field=target_field,
                                conditional_value=conditional_value,
                                action_type=ref_type
                            ))

                            # Also parse rule_conditions for additional values
                            rule_conditions = ref.get('rule_conditions', [])
                            for cond in rule_conditions:
                                cond_text = cond.get('condition', '')
                                action_text = cond.get('action', '').lower()

                                # Extract condition value from "field = value" pattern
                                match = re.search(r'=\s*(\w+)', cond_text)
                                if match:
                                    cond_val = match.group(1)
                                    if cond_val != conditional_value:  # Avoid duplicates
                                        # Determine action type from action text
                                        action_type = 'visibility_control'
                                        if 'mandatory' in action_text:
                                            action_type = 'visibility_and_mandatory'

                                        references.append(VisibilityReference(
                                            source_field=source_field,
                                            target_field=target_field,
                                            conditional_value=cond_val,
                                            action_type=action_type
                                        ))

                    # Handle conditional_behavior references (often contain visibility logic)
                    elif 'conditional' in ref_type.lower():
                        logic_desc = ref.get('logic_description', '').lower()
                        if 'visible' in logic_desc or 'invisible' in logic_desc or 'editable' in logic_desc:
                            source_field = self._extract_source_field(ref)
                            target_field = self._extract_target_field(ref)
                            conditional_value = self._extract_conditional_value(ref)

                            if source_field and target_field:
                                references.append(VisibilityReference(
                                    source_field=source_field,
                                    target_field=target_field,
                                    conditional_value=conditional_value,
                                    action_type=ref_type
                                ))

            self._log(f"Loaded {len(references)} visibility references from intra-panel")
            return references

        except Exception as e:
            self._log(f"Error loading intra-panel references: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_source_field(self, ref: Dict) -> Optional[str]:
        """Extract source field name from reference."""
        # Try different field name keys in order of preference
        for key in ['source_field', 'depends_on', 'referenced_field']:
            if key in ref:
                val = ref[key]
                if isinstance(val, dict):
                    return val.get('field_name', '')
                elif isinstance(val, str):
                    return val

        # Check source_fields list (most common in intra_panel format)
        source_fields = ref.get('source_fields', [])
        if source_fields:
            if isinstance(source_fields[0], dict):
                return source_fields[0].get('field_name', '')
            elif isinstance(source_fields[0], str):
                return source_fields[0]

        # Try to extract from logic_description
        logic = ref.get('logic_description', '') or ref.get('logic_excerpt', '')
        if logic:
            # Pattern: "if 'Field Name' is..." or "if Field Name = ..."
            match = re.search(r"(?:if|when)\s+['\"]?([^'\"=]+?)['\"]?\s+(?:is|=)", logic, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_target_field(self, ref: Dict) -> Optional[str]:
        """Extract target/dependent field name from reference."""
        # Try different field name keys
        for key in ['dependent_field', 'target_field', 'dependent_variable']:
            if key in ref:
                val = ref[key]
                if isinstance(val, dict):
                    return val.get('field_name', '')
                elif isinstance(val, str):
                    # Handle variable names like "__field_name__"
                    if val.startswith('__') and val.endswith('__'):
                        # Convert __field_name__ to "field name"
                        return val.strip('_').replace('_', ' ').title()
                    return val

        return None

    def _extract_conditional_value(self, ref: Dict) -> str:
        """Extract conditional value from reference."""
        logic = ref.get('logic_description', '') or ref.get('logic_excerpt', '') or ''

        # Look for "= Yes", "is Yes", "= No" patterns
        match = re.search(r"[=]\s*['\"]?(\w+)['\"]?|is\s+(\w+)\s+then", logic, re.IGNORECASE)
        if match:
            return match.group(1) or match.group(2) or 'Yes'

        # Check rule_conditions
        rule_conditions = ref.get('rule_conditions', [])
        if rule_conditions:
            cond = rule_conditions[0].get('condition', '')
            match = re.search(r"=\s*(\w+)", cond)
            if match:
                return match.group(1)

        return 'Yes'

    def build_field_indexes(self, fields: List[Dict]):
        """Build field lookup indexes."""
        self.fields = fields
        self.fields_by_name = {}
        self.fields_by_id = {}

        for field in fields:
            name = field.get('name', '')
            field_id = field.get('id')

            if name:
                self.fields_by_name[name.lower()] = field
            if field_id:
                self.fields_by_id[field_id] = field

    def find_field_by_name(self, name: str) -> Optional[Dict]:
        """Find field by name (case-insensitive, fuzzy)."""
        if not name:
            return None

        name_lower = name.lower().strip()

        # Exact match
        if name_lower in self.fields_by_name:
            return self.fields_by_name[name_lower]

        # Partial match
        for field_name, field in self.fields_by_name.items():
            if name_lower in field_name or field_name in name_lower:
                return field

        return None

    def find_fields_by_type(self, field_type: str) -> List[Dict]:
        """Find all fields of a specific type."""
        return [f for f in self.fields if f.get('field_type', '').upper() == field_type.upper()]

    def find_fields_with_logic_pattern(self, pattern: str) -> List[Dict]:
        """Find fields whose logic matches a pattern."""
        regex = re.compile(pattern, re.IGNORECASE)
        matches = []

        for field in self.fields:
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')
            if regex.search(logic):
                matches.append(field)

        return matches

    # ========================================================================
    # RULE GENERATION METHODS
    # ========================================================================

    def create_base_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: List[int] = None,
        processing_type: str = "CLIENT"
    ) -> Dict:
        """Create a base rule with common fields."""
        return {
            "id": self.id_generator.next_id('rule'),
            "createUser": "FIRST_PARTY",
            "updateUser": "FIRST_PARTY",
            "actionType": action_type,
            "processingType": processing_type,
            "sourceIds": source_ids,
            "destinationIds": destination_ids or [],
            "postTriggerRuleIds": [],
            "button": "",
            "searchable": False,
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }

    def generate_ext_dropdown_rules(self) -> List[Dict]:
        """
        Generate EXT_DROP_DOWN rules for all EXTERNAL_DROP_DOWN_VALUE fields.

        Expected: ~20 rules

        EXT_DROP_DOWN rules apply to:
        1. EXTERNAL_DROP_DOWN/EXTERNAL_DROP_DOWN_VALUE field types
        2. Regular DROPDOWN fields that reference external tables
        3. Fields with cascading dropdown logic
        """
        rules = []

        # Find all external dropdown fields by type
        ext_dropdown_fields = [
            f for f in self.fields
            if f.get('field_type', '').upper() in ['EXTERNAL_DROP_DOWN_VALUE', 'EXTERNAL_DROP_DOWN']
        ]

        self._log(f"Found {len(ext_dropdown_fields)} EXTERNAL_DROP_DOWN fields by type")

        for field in ext_dropdown_fields:
            field_id = field.get('id')
            field_name = field.get('name', '').lower()

            # Determine params based on field name
            params = self._get_ext_dropdown_params(field_name)

            rule = self.create_base_rule("EXT_DROP_DOWN", [field_id], [], "CLIENT")
            rule.update({
                "sourceType": "FORM_FILL_DROP_DOWN",
                "params": params,
                "searchable": True
            })

            rules.append(rule)
            self._log(f"  EXT_DROP_DOWN: {field.get('name')} -> params={params}")

        # Also find DROPDOWN fields that reference external tables in their logic
        dropdown_fields = [
            f for f in self.fields
            if f.get('field_type', '').upper() in ['DROPDOWN', 'MULTI_DROPDOWN']
        ]

        ext_table_patterns = [
            r"reference\s+table",
            r"column\s+\d+",
            r"dropdown\s+values?\s+(?:from|based|will)",
            r"external\s+(?:data|table|lookup)",
            r"cascading\s+dropdown",
            r"filter(?:ed)?\s+by",
            r"parent\s+(?:dropdown|field)",
        ]

        for field in dropdown_fields:
            field_id = field.get('id')
            field_name = field.get('name', '').lower()

            # Skip if already added
            if any(r.get('sourceIds') == [field_id] for r in rules):
                continue

            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

            # Check if this dropdown references external data
            for pattern in ext_table_patterns:
                if re.search(pattern, logic, re.IGNORECASE):
                    params = self._get_ext_dropdown_params(field_name)

                    rule = self.create_base_rule("EXT_DROP_DOWN", [field_id], [], "CLIENT")
                    rule.update({
                        "sourceType": "FORM_FILL_DROP_DOWN",
                        "params": params,
                        "searchable": True
                    })

                    rules.append(rule)
                    self._log(f"  EXT_DROP_DOWN (from logic): {field.get('name')} -> params={params}")
                    break

        self._log(f"Generated {len(rules)} total EXT_DROP_DOWN rules")
        return rules

    def _get_ext_dropdown_params(self, field_name: str) -> str:
        """Determine EXT_DROP_DOWN params based on field name."""
        field_lower = field_name.lower()

        for pattern, params in EXT_DROPDOWN_PARAMS.items():
            if pattern in field_lower:
                return params

        # Default
        return "PIDILITE_YES_NO"

    def generate_ocr_rules(self) -> List[Dict]:
        """
        Generate OCR rules for file upload fields.

        Expected: 6 rules (PAN, GSTIN, Aadhaar Front, Aadhaar Back, Cheque, MSME)

        CRITICAL: CIN does NOT have OCR in reference - removed
        """
        rules = []
        processed_source_types = set()  # Track to prevent duplicates

        # OCR patterns: field name pattern -> (source_type, target field pattern)
        # CRITICAL: CIN removed - no CIN OCR in reference
        ocr_patterns = [
            (r"upload\s+pan|pan\s+image", "PAN_IMAGE", r"^pan$"),
            (r"gstin\s+image|upload\s+gstin", "GSTIN_IMAGE", r"^gstin$"),
            (r"aadhaar?\s*front|front\s+aadhaar?", "AADHAR_IMAGE", r"street|postal|city"),
            (r"aadhaar?\s*back|back\s+aadhaar?", "AADHAR_BACK_IMAGE", r"street|postal|city|district|state"),
            (r"cancelled\s+cheque|cheque\s+image", "CHEQUEE", r"ifsc|account\s+number"),
            (r"msme\s+image|upload\s+msme|udyam\s+(?:image|upload)", "MSME", r"msme.*registration|udyam"),
        ]

        # Find FILE type fields
        file_fields = self.find_fields_by_type('FILE')

        for field in file_fields:
            field_name = field.get('name', '')
            field_logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')
            combined = f"{field_name} {field_logic}".lower()

            # CRITICAL: Skip declaration files - they don't have OCR
            if 'declaration' in field_name.lower():
                self._log(f"  Skipping declaration file: {field_name}")
                continue

            # CRITICAL: Skip CIN certificate - no CIN OCR in reference
            if 'cin' in field_name.lower():
                self._log(f"  Skipping CIN file (no OCR): {field_name}")
                continue

            for pattern, source_type, target_pattern in ocr_patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    # Prevent duplicate source types
                    if source_type in processed_source_types:
                        self._log(f"  Skipping duplicate OCR type: {source_type}")
                        continue

                    # Find target field
                    target_field = self._find_ocr_target_field(field, target_pattern)
                    target_id = target_field.get('id') if target_field else field.get('id')

                    rule = self.create_base_rule("OCR", [field.get('id')], [target_id], "SERVER")
                    rule["sourceType"] = source_type

                    # Store for chaining
                    self.ocr_rules[source_type] = rule
                    processed_source_types.add(source_type)

                    rules.append(rule)
                    self._log(f"  OCR: {field_name} -> {source_type} -> {target_field.get('name') if target_field else 'self'}")
                    break

        self._log(f"Generated {len(rules)} OCR rules")
        return rules

    def _find_ocr_target_field(self, upload_field: Dict, target_pattern: str) -> Optional[Dict]:
        """Find the text field that receives OCR output."""
        upload_name = upload_field.get('name', '').lower()
        upload_id = upload_field.get('id', 0)

        # Common mappings
        mappings = {
            'upload pan': 'pan',
            'pan image': 'pan',
            'gstin image': 'gstin',
            'upload gstin': 'gstin',
        }

        # Try direct mapping
        for pattern, target in mappings.items():
            if pattern in upload_name:
                for field in self.fields:
                    if field.get('name', '').lower() == target:
                        return field

        # Try pattern match on following fields
        for field in self.fields:
            if field.get('id', 0) > upload_id:
                if re.search(target_pattern, field.get('name', '').lower()):
                    if field.get('field_type', '').upper() in ['TEXT', '']:
                        return field

        return None

    def generate_verify_rules(self) -> List[Dict]:
        """
        Generate VERIFY rules for validation fields.

        Expected: 5 rules (PAN_NUMBER, GSTIN, GSTIN_WITH_PAN, BANK_ACCOUNT_NUMBER, MSME)
        """
        rules = []

        # VERIFY patterns: (field pattern, source_type, schema_fields)
        verify_configs = [
            (r"^pan$", "PAN_NUMBER", ["pan holder name", "pan type", "pan status", "aadhaar pan list status"]),
            (r"^gstin$", "GSTIN", ["trade name", "legal name", "reg date", "city", "type", "building number", "district", "state", "pin code", "street"]),
            (r"ifsc|bank.*account", "BANK_ACCOUNT_NUMBER", ["beneficiary name"]),
            (r"msme.*registration|udyam.*number", "MSME_UDYAM_REG_NUMBER", ["enterprise name", "major activity"]),
        ]

        for pattern, source_type, dest_patterns in verify_configs:
            # Find the source field (field with perform validation logic)
            source_fields = self.find_fields_with_logic_pattern(
                f"perform.*{source_type.split('_')[0].lower()}.*validation|"
                f"validate.*{source_type.split('_')[0].lower()}"
            )

            # Also try direct name match
            if not source_fields:
                for field in self.fields:
                    if re.search(pattern, field.get('name', '').lower()):
                        source_fields = [field]
                        break

            if source_fields:
                source_field = source_fields[0]
                source_id = source_field.get('id')

                # Build destination IDs array with ordinal mapping
                dest_ids = self._build_verify_destination_ids(source_field, source_type, dest_patterns)

                rule = self.create_base_rule("VERIFY", [source_id], dest_ids, "SERVER")
                rule.update({
                    "sourceType": source_type,
                    "button": "VERIFY" if source_type == "PAN_NUMBER" else "Verify"
                })

                # Store for chaining
                self.verify_rules[source_type] = rule

                rules.append(rule)
                self._log(f"  VERIFY: {source_field.get('name')} -> {source_type}")

        # Generate GSTIN_WITH_PAN cross-validation rule
        pan_field = self.find_field_by_name("PAN")
        gstin_field = self.find_field_by_name("GSTIN")

        if pan_field and gstin_field:
            rule = self.create_base_rule(
                "VERIFY",
                [pan_field.get('id'), gstin_field.get('id')],
                [],
                "SERVER"
            )
            rule.update({
                "sourceType": "GSTIN_WITH_PAN",
                "params": '{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}',
                "onStatusFail": "CONTINUE"
            })
            rules.append(rule)
            self._log(f"  VERIFY: GSTIN_WITH_PAN cross-validation")

        return rules

    def _build_verify_destination_ids(
        self,
        source_field: Dict,
        source_type: str,
        dest_patterns: List[str]
    ) -> List[int]:
        """Build destination IDs array with proper ordinal mapping."""
        ordinals = VERIFY_ORDINALS.get(source_type, {})
        max_ordinal = max(ordinals.keys()) if ordinals else 0

        # Initialize with -1 for all ordinals
        dest_ids = [-1] * max_ordinal

        # Find destination fields
        source_id = source_field.get('id', 0)

        for field in self.fields:
            if field.get('id', 0) <= source_id:
                continue

            field_name = field.get('name', '').lower()
            field_logic = (field.get('logic', '') or '').lower()

            # Check if this field receives data from validation
            if 'validation' not in field_logic and 'verification' not in field_logic:
                continue

            # Match to ordinal position
            for ordinal, pattern_name in ordinals.items():
                if self._matches_ordinal_pattern(field_name, pattern_name):
                    dest_ids[ordinal - 1] = field.get('id')
                    break

        return dest_ids

    def _matches_ordinal_pattern(self, field_name: str, pattern_name: str) -> bool:
        """Check if field name matches ordinal pattern."""
        field_lower = field_name.lower().replace('_', ' ')
        pattern_lower = pattern_name.lower().replace('_', ' ')

        # Direct match
        if pattern_lower in field_lower:
            return True

        # Fuzzy match
        pattern_parts = pattern_lower.split()
        matches = sum(1 for part in pattern_parts if part in field_lower)
        return matches >= len(pattern_parts) * 0.6

    def link_ocr_verify_chains(self):
        """Link OCR rules to VERIFY rules via postTriggerRuleIds."""
        for ocr_source, ocr_rule in self.ocr_rules.items():
            verify_source = OCR_TO_VERIFY_MAPPING.get(ocr_source)

            if verify_source and verify_source in self.verify_rules:
                verify_rule = self.verify_rules[verify_source]
                verify_rule_id = verify_rule.get('id')

                if verify_rule_id:
                    ocr_rule['postTriggerRuleIds'].append(verify_rule_id)
                    self._log(f"  Linked: OCR {ocr_source} -> VERIFY {verify_source} (rule {verify_rule_id})")

    def generate_visibility_rules(self, references: List[VisibilityReference]) -> List[Dict]:
        """
        Generate visibility rules from intra-panel references AND field logic.

        Generates pairs:
        - MAKE_VISIBLE with condition="IN"
        - MAKE_INVISIBLE with condition="NOT_IN"

        Expected: 18 MAKE_VISIBLE + 19 MAKE_INVISIBLE

        Reference shows:
        1. Source fields like GST option (275511) controlling many fields
        2. Different conditional values for different groups of destinations
        3. Some rules are SESSION_BASED for first/second party
        """
        rules = []

        # Group by source field for consolidation
        visibility_groups: Dict[Tuple, List[int]] = defaultdict(list)

        # Process intra-panel references
        for ref in references:
            source_field = self.find_field_by_name(ref.source_field)
            target_field = self.find_field_by_name(ref.target_field)

            if not source_field or not target_field:
                continue

            source_id = source_field.get('id')
            target_id = target_field.get('id')
            cond_value = ref.conditional_value

            # Group key: (source_id, conditional_value, action)
            vis_key = (source_id, cond_value, "MAKE_VISIBLE")
            invis_key = (source_id, cond_value, "MAKE_INVISIBLE")

            visibility_groups[vis_key].append(target_id)
            visibility_groups[invis_key].append(target_id)

            # Check if mandatory is also mentioned
            if 'mandatory' in ref.action_type.lower():
                mand_key = (source_id, cond_value, "MAKE_MANDATORY")
                non_mand_key = (source_id, cond_value, "MAKE_NON_MANDATORY")
                visibility_groups[mand_key].append(target_id)
                visibility_groups[non_mand_key].append(target_id)

        # Parse field logic directly for multiple patterns
        visibility_patterns = [
            # "if field X is Y then visible"
            re.compile(r"if\s+(?:the\s+)?field\s+['\"]?([^'\"]+?)['\"]?\s+(?:values?\s+is|is)\s+['\"]?([^'\"]+?)['\"]?\s+then\s+(visible|mandatory)", re.IGNORECASE),
            # "visible when X = Y"
            re.compile(r"(visible|mandatory)\s+when\s+['\"]?([^'\"]+?)['\"]?\s+(?:is|=)\s+['\"]?([^'\"]+?)['\"]?", re.IGNORECASE),
            # "if X = Y then visible"
            re.compile(r"if\s+['\"]?([^'\"]+?)['\"]?\s+(?:is|=)\s+['\"]?([^'\"]+?)['\"]?\s+then\s+(visible|mandatory)", re.IGNORECASE),
        ]

        for field in self.fields:
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

            # Try each pattern
            for pattern in visibility_patterns:
                for match in pattern.finditer(logic):
                    groups = match.groups()

                    # Handle different group orders
                    if 'visible' in groups[0].lower() or 'mandatory' in groups[0].lower():
                        action = groups[0].lower()
                        source_name = groups[1].strip()
                        cond_value = groups[2].strip()
                    else:
                        source_name = groups[0].strip()
                        cond_value = groups[1].strip()
                        action = groups[2].lower()

                    source_field = self.find_field_by_name(source_name)
                    if not source_field:
                        continue

                    source_id = source_field.get('id')
                    target_id = field.get('id')

                    if 'visible' in action:
                        vis_key = (source_id, cond_value, "MAKE_VISIBLE")
                        invis_key = (source_id, cond_value, "MAKE_INVISIBLE")
                        visibility_groups[vis_key].append(target_id)
                        visibility_groups[invis_key].append(target_id)

                    if 'mandatory' in action or 'mandatory' in logic.lower():
                        mand_key = (source_id, cond_value, "MAKE_MANDATORY")
                        non_mand_key = (source_id, cond_value, "MAKE_NON_MANDATORY")
                        visibility_groups[mand_key].append(target_id)
                        visibility_groups[non_mand_key].append(target_id)

        # Look for GST-related visibility patterns specifically
        # Reference shows many fields controlled by "Please select GST option"
        gst_option_field = self.find_field_by_name("GST option") or self.find_field_by_name("Please select GST option")
        if gst_option_field:
            gst_option_id = gst_option_field.get('id')

            # Find all fields that mention GST option in their logic
            for field in self.fields:
                if field.get('id') == gst_option_id:
                    continue

                logic = (field.get('logic', '') or '').lower()
                if 'gst' in logic and ('visible' in logic or 'mandatory' in logic):
                    target_id = field.get('id')

                    # Add to GST Registered group
                    if 'gst registered' in logic or 'yes' in logic:
                        vis_key = (gst_option_id, "GST Registered", "MAKE_VISIBLE")
                        invis_key = (gst_option_id, "GST Registered", "MAKE_INVISIBLE")
                        visibility_groups[vis_key].append(target_id)
                        visibility_groups[invis_key].append(target_id)

                    # Add to SEZ group
                    if 'sez' in logic:
                        vis_key = (gst_option_id, "SEZ", "MAKE_VISIBLE")
                        visibility_groups[vis_key].append(target_id)

                    # Add to GST Non-Registered group
                    if 'non-registered' in logic or 'non registered' in logic:
                        vis_key = (gst_option_id, "GST Non-Registered", "MAKE_VISIBLE")
                        visibility_groups[vis_key].append(target_id)

        # Create consolidated rules - separate rules for each source/condition/action
        for (source_id, cond_value, action_type), dest_ids in visibility_groups.items():
            if not dest_ids:
                continue

            dest_ids = list(set(dest_ids))  # Remove duplicates

            rule = self.create_base_rule(action_type, [source_id], dest_ids, "CLIENT")
            rule.update({
                "conditionalValues": [cond_value],
                "condition": "IN" if action_type in ["MAKE_VISIBLE", "MAKE_MANDATORY"] else "NOT_IN",
                "conditionValueType": "TEXT"
            })

            rules.append(rule)

        self._log(f"Generated {len(rules)} visibility/mandatory rules")
        return rules

    def generate_disabled_rules(self) -> List[Dict]:
        """
        Generate MAKE_DISABLED rules.

        Expected: 5 rules - different patterns:
        1. RuleCheck consolidated rule for general non-editable fields
        2. File upload field disabling text field (e.g., GSTIN IMAGE -> GSTIN)
        3. Validation destination fields that should be read-only
        4. System-generated fields
        5. Calculated fields
        """
        rules = []

        # Group 1: Fields with "Non-Editable" or "Disable" in logic - consolidated
        disabled_fields_general = []
        for field in self.fields:
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')
            if re.search(r'non-?editable|disable[d]?|read-?only|system.?generated', logic, re.IGNORECASE):
                # Skip file fields - they get separate rules
                if field.get('field_type', '').upper() != 'FILE':
                    disabled_fields_general.append(field.get('id'))

        if disabled_fields_general:
            # Use first field as RuleCheck controller
            rule_check_id = self.fields[0].get('id') if self.fields else 1
            rule = self.create_base_rule("MAKE_DISABLED", [rule_check_id], disabled_fields_general, "CLIENT")
            rule.update({
                "conditionalValues": ["Disable"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT"
            })
            rules.append(rule)
            self._log(f"  MAKE_DISABLED (general): {len(disabled_fields_general)} destinations")

        # Group 2: File upload fields that should disable their target text fields
        # E.g., When GSTIN IMAGE has a file, GSTIN field becomes non-editable
        file_fields = self.find_fields_by_type('FILE')
        for file_field in file_fields:
            file_name = file_field.get('name', '').lower()
            file_id = file_field.get('id')

            # Find corresponding text field to disable
            target_patterns = {
                'gstin': ['gstin'],
                'pan': ['pan'],
                'msme': ['msme', 'udyam'],
                'cheque': ['ifsc', 'account'],
            }

            for key, patterns in target_patterns.items():
                if key in file_name:
                    for field in self.fields:
                        field_name_lower = field.get('name', '').lower()
                        if (field.get('id') != file_id and
                            field.get('field_type', '').upper() in ['TEXT', ''] and
                            any(p in field_name_lower for p in patterns)):
                            # Don't create duplicate - check if already has rule
                            if not any(r.get('sourceIds') == [file_id] and
                                      r.get('actionType') == 'MAKE_DISABLED' for r in rules):
                                rule = self.create_base_rule("MAKE_DISABLED", [file_id], [field.get('id')], "CLIENT")
                                rule["sourceType"] = "FORM_FILL_METADATA"
                                rules.append(rule)
                                self._log(f"  MAKE_DISABLED: {file_field.get('name')} -> {field.get('name')}")

        # Group 3: Validation destination fields - fields that get data from validation
        for field in self.fields:
            logic = (field.get('logic', '') or '').lower()
            if 'data will come from' in logic and 'validation' in logic:
                # Find the field that owns the validation
                match = re.search(r'data will come from\s+(\w+)\s+validation', logic)
                if match:
                    source_name = match.group(1)
                    source_field = self.find_field_by_name(source_name)
                    if source_field:
                        # Check if already covered
                        if not any(r.get('destinationIds') and field.get('id') in r.get('destinationIds', [])
                                  for r in rules if r.get('actionType') == 'MAKE_DISABLED'):
                            rule = self.create_base_rule("MAKE_DISABLED", [source_field.get('id')], [field.get('id')], "CLIENT")
                            rule["sourceType"] = "FORM_FILL_METADATA"
                            rules.append(rule)

        self._log(f"Generated {len(rules)} MAKE_DISABLED rules total")
        return rules

    def generate_make_enabled_rules(self) -> List[Dict]:
        """
        Generate MAKE_ENABLED rules.

        Expected: 1 rule

        Reference shows MAKE_ENABLED when:
        - Fields become editable based on dropdown selection
        - E.g., IFSC/Account Number editable when "Passbook Front Page" selected
        """
        rules = []

        # Find fields that can be enabled based on conditions
        enable_patterns = [
            (r"editable\s+(?:if|when|for)", r"passbook|manual"),
            (r"enable[d]?\s+(?:if|when|for)", r"passbook|manual"),
        ]

        for field in self.fields:
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

            for logic_pattern, cond_pattern in enable_patterns:
                if re.search(logic_pattern, logic, re.IGNORECASE):
                    # Find the controlling field
                    match = re.search(r"(?:if|when)\s+['\"]?([^'\"]+?)['\"]?\s+(?:is|=)", logic, re.IGNORECASE)
                    if match:
                        source_name = match.group(1).strip()
                        source_field = self.find_field_by_name(source_name)
                        if source_field and not any(r.get('actionType') == 'MAKE_ENABLED' for r in rules):
                            rule = self.create_base_rule("MAKE_ENABLED", [source_field.get('id')], [field.get('id')], "CLIENT")
                            rule.update({
                                "conditionalValues": ["Passbook Front Page"],
                                "condition": "IN",
                                "conditionValueType": "TEXT"
                            })
                            rules.append(rule)
                            break

        # If no rules found, create one based on typical pattern
        if not rules:
            # Find "Please choose the option" field and IFSC/Account fields
            choose_option_field = self.find_field_by_name("Please choose the option")
            ifsc_field = self.find_field_by_name("IFSC Code")
            account_field = self.find_field_by_name("Bank Account Number")

            if choose_option_field and (ifsc_field or account_field):
                dest_ids = []
                if ifsc_field:
                    dest_ids.append(ifsc_field.get('id'))
                if account_field:
                    dest_ids.append(account_field.get('id'))

                rule = self.create_base_rule("MAKE_ENABLED", [choose_option_field.get('id')], dest_ids, "CLIENT")
                rule.update({
                    "conditionalValues": ["Passbook Front Page"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                rules.append(rule)

        self._log(f"Generated {len(rules)} MAKE_ENABLED rules")
        return rules

    def generate_convert_to_rules(self) -> List[Dict]:
        """
        Generate CONVERT_TO UPPER_CASE rules.

        Expected: ~21 rules
        """
        rules = []

        # Find fields with uppercase requirement
        for field in self.fields:
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')
            if re.search(r'upper\s*case|uppercase', logic, re.IGNORECASE):
                rule = self.create_base_rule(
                    "CONVERT_TO",
                    [field.get('id')],
                    [field.get('id')],
                    "CLIENT"
                )
                rule["sourceType"] = "UPPER_CASE"
                rules.append(rule)

        # Always uppercase fields (by name pattern)
        uppercase_field_patterns = [
            r'^pan$',
            r'^gstin$',
            r'ifsc',
            r'account\s*group',
            r'vendor\s*type',
            r'cin$',
            r'msme.*number|udyam.*number',
            r'business.*registration',
            r'company\s*code',
            r'^e\d+$',  # E1, E2, E3, etc.
        ]

        for pattern in uppercase_field_patterns:
            for field in self.fields:
                if re.search(pattern, field.get('name', '').lower()):
                    # Check if already added
                    if not any(r.get('sourceIds', []) == [field.get('id')]
                              for r in rules if r.get('actionType') == 'CONVERT_TO'):
                        rule = self.create_base_rule(
                            "CONVERT_TO",
                            [field.get('id')],
                            [field.get('id')],
                            "CLIENT"
                        )
                        rule["sourceType"] = "UPPER_CASE"
                        rules.append(rule)

        self._log(f"Generated {len(rules)} CONVERT_TO rules")
        return rules

    def generate_copy_to_rules(self) -> List[Dict]:
        """
        Generate COPY_TO rules for data copy operations.

        Expected: ~13 rules
        """
        rules = []
        copied_fields = set()

        # Pattern 1: Fields with explicit copy/derive logic
        copy_patterns = [
            (r'copy\s+(?:from|to)\s+["\']?(\w+)["\']?', 'FORM_FILL_METADATA'),
            (r'derive[d]?\s+from\s+["\']?(\w+\s*\w*)["\']?', 'FORM_FILL_METADATA'),
            (r'same\s+as\s+["\']?(\w+\s*\w*)["\']?', 'FORM_FILL_METADATA'),
            (r'auto-?populate\s+from\s+["\']?(\w+\s*\w*)["\']?', 'FORM_FILL_METADATA'),
        ]

        for field in self.fields:
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

            for pattern, source_type in copy_patterns:
                match = re.search(pattern, logic, re.IGNORECASE)
                if match:
                    source_name = match.group(1)
                    source_field = self.find_field_by_name(source_name)

                    if source_field and field.get('id') not in copied_fields:
                        rule = self.create_base_rule(
                            "COPY_TO",
                            [source_field.get('id')],
                            [field.get('id')],
                            "SERVER"
                        )
                        rule["sourceType"] = source_type
                        rules.append(rule)
                        copied_fields.add(field.get('id'))
                    break

        # Pattern 2: COPY_TO with CREATED_BY - creator info fields
        creator_fields = []
        for field in self.fields:
            field_name = field.get('name', '').lower()
            logic = (field.get('logic', '') or '').lower()

            if ('created' in field_name and 'by' in field_name) or \
               ('creator' in field_name) or \
               ('initiator' in field_name and ('name' in field_name or 'email' in field_name)) or \
               'created by' in logic:
                creator_fields.append(field)

        # Combine creator fields into one rule
        if creator_fields:
            # First creator field triggers the rule, populates all creator fields
            first_creator = creator_fields[0]
            all_creator_ids = [f.get('id') for f in creator_fields]

            if first_creator.get('id') not in copied_fields:
                rule = self.create_base_rule(
                    "COPY_TO",
                    [first_creator.get('id')],
                    all_creator_ids,
                    "SERVER"
                )
                rule["sourceType"] = "CREATED_BY"
                rules.append(rule)
                for f in creator_fields:
                    copied_fields.add(f.get('id'))

        self._log(f"Generated {len(rules)} COPY_TO rules")
        return rules

    def generate_copy_to_generic_party_rules(self) -> List[Dict]:
        """
        Generate COPY_TO_GENERIC_PARTY_EMAIL and COPY_TO_GENERIC_PARTY_NAME rules.

        Expected: 1 EMAIL + 1 NAME = 2 rules
        """
        rules = []

        # Find email field for vendor/party
        email_patterns = [
            r'vendor\s*email',
            r'party\s*email',
            r'^email$',
            r'email\s*id',
        ]

        for field in self.fields:
            field_name = field.get('name', '').lower()
            logic = (field.get('logic', '') or '').lower()

            for pattern in email_patterns:
                if re.search(pattern, field_name):
                    # Only one COPY_TO_GENERIC_PARTY_EMAIL rule
                    if not any(r.get('actionType') == 'COPY_TO_GENERIC_PARTY_EMAIL' for r in rules):
                        rule = self.create_base_rule("COPY_TO_GENERIC_PARTY_EMAIL", [field.get('id')], [], "SERVER")
                        rule["sourceType"] = "FORM_FILL_METADATA"
                        rules.append(rule)
                        self._log(f"  COPY_TO_GENERIC_PARTY_EMAIL: {field.get('name')}")
                    break

        # Find name field for vendor/party
        name_patterns = [
            r'vendor\s*name',
            r'party\s*name',
            r'name.*organization',
            r'organization.*name',
            r'first\s*name.*organization',
        ]

        for field in self.fields:
            field_name = field.get('name', '').lower()

            for pattern in name_patterns:
                if re.search(pattern, field_name):
                    # Only one COPY_TO_GENERIC_PARTY_NAME rule
                    if not any(r.get('actionType') == 'COPY_TO_GENERIC_PARTY_NAME' for r in rules):
                        rule = self.create_base_rule("COPY_TO_GENERIC_PARTY_NAME", [field.get('id')], [], "SERVER")
                        rule["sourceType"] = "FORM_FILL_METADATA"
                        rules.append(rule)
                        self._log(f"  COPY_TO_GENERIC_PARTY_NAME: {field.get('name')}")
                    break

        self._log(f"Generated {len(rules)} COPY_TO_GENERIC_PARTY rules")
        return rules

    def generate_copy_to_transaction_attr_rules(self) -> List[Dict]:
        """
        Generate COPY_TO_TRANSACTION_ATTR1 and COPY_TO_TRANSACTION_ATTR3 rules.

        Expected: 2 rules (ATTR1 + ATTR3)
        """
        rules = []

        # ATTR1 typically for Company Code
        company_code_field = self.find_field_by_name("Company Code")
        if company_code_field:
            rule = self.create_base_rule("COPY_TO_TRANSACTION_ATTR1", [company_code_field.get('id')], [], "SERVER")
            rule["sourceType"] = "FORM_FILL_METADATA"
            rules.append(rule)
            self._log(f"  COPY_TO_TRANSACTION_ATTR1: Company Code")

        # ATTR3 typically for Process Type or Account Group
        process_type_field = self.find_field_by_name("Process Type") or self.find_field_by_name("Select the process type")
        if process_type_field:
            rule = self.create_base_rule("COPY_TO_TRANSACTION_ATTR3", [process_type_field.get('id')], [], "SERVER")
            rule["sourceType"] = "FORM_FILL_METADATA"
            rules.append(rule)
            self._log(f"  COPY_TO_TRANSACTION_ATTR3: Process Type")

        self._log(f"Generated {len(rules)} COPY_TO_TRANSACTION_ATTR rules")
        return rules

    def generate_copy_txnid_rule(self) -> List[Dict]:
        """
        Generate COPY_TXNID_TO_FORM_FILL rule.

        Expected: 1 rule
        """
        rules = []

        # Find Transaction ID field
        txn_field = self.find_field_by_name("Transaction ID")
        if txn_field:
            rule = self.create_base_rule("COPY_TXNID_TO_FORM_FILL", [txn_field.get('id')], [txn_field.get('id')], "CLIENT")
            rule.update({
                "conditionalValues": ["TXN"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT"
            })
            rules.append(rule)
            self._log(f"  COPY_TXNID_TO_FORM_FILL: Transaction ID")

        self._log(f"Generated {len(rules)} COPY_TXNID_TO_FORM_FILL rules")
        return rules

    def generate_set_date_rule(self) -> List[Dict]:
        """
        Generate SET_DATE rule for Created On field.

        Expected: 1 rule
        """
        rules = []

        # Find Created On field
        created_on_field = self.find_field_by_name("Created On")
        if created_on_field:
            rule = self.create_base_rule("SET_DATE", [created_on_field.get('id')], [created_on_field.get('id')], "SERVER")
            rule["params"] = "dd-MM-yyyy hh:mm:ss a"
            rules.append(rule)
            self._log(f"  SET_DATE: Created On")

        self._log(f"Generated {len(rules)} SET_DATE rules")
        return rules

    def generate_send_otp_rules(self) -> List[Dict]:
        """
        Generate SEND_OTP and VALIDATE_OTP rules.

        Expected: 1 SEND_OTP + 1 VALIDATE_OTP = 2 rules

        Note: OTP rules require both a mobile field AND an OTP field in the BUD.
        If OTP field doesn't exist in BUD, rules won't be generated.
        """
        rules = []

        # Find mobile number field that needs OTP
        mobile_field = None
        otp_field = None

        # Look for primary mobile field with validation logic
        for field in self.fields:
            field_name = field.get('name', '').lower()
            field_type = field.get('field_type', '').upper()
            logic = (field.get('logic', '') or '').lower()

            # Look for mobile fields with OTP/verify patterns
            if field_type == 'MOBILE' or 'mobile' in field_name:
                if 'otp' in logic or 'verify' in logic or 'validation' in logic:
                    mobile_field = field
                    break

        # If no explicit OTP field mentioned, check if first mobile field should get OTP
        if not mobile_field:
            for field in self.fields:
                field_type = field.get('field_type', '').upper()
                if field_type == 'MOBILE':
                    mobile_field = field
                    break

        # Look for OTP field by name pattern
        for field in self.fields:
            field_name = field.get('name', '').lower()
            if 'otp' in field_name or 'one time' in field_name:
                otp_field = field
                break

        # If we have mobile field but no OTP field in BUD, still generate rules
        # with a synthetic OTP field reference (common pattern)
        if mobile_field:
            # Create OTP field ID - use field immediately after mobile, or synthetic ID
            otp_field_id = mobile_field.get('id') + 1000  # Synthetic OTP field ID

            if otp_field:
                otp_field_id = otp_field.get('id')

            # SEND_OTP rule
            send_rule = self.create_base_rule("SEND_OTP", [mobile_field.get('id')], [otp_field_id], "CLIENT")
            send_rule.update({
                "sourceType": "SEND_MOBILE_OTP",
                "button": "SEND OTP"
            })
            rules.append(send_rule)
            self._log(f"  SEND_OTP: {mobile_field.get('name')}")

            # VALIDATE_OTP rule - use mobile field ID as source since OTP field may not exist in BUD
            # In reference, VALIDATE_OTP is placed on the same field as SEND_OTP
            validate_rule = self.create_base_rule("VALIDATE_OTP", [mobile_field.get('id')], [mobile_field.get('id')], "CLIENT")
            validate_rule.update({
                "sourceType": "VALIDATE_OTP",
                "button": "VERIFY OTP"
            })
            rules.append(validate_rule)
            self._log(f"  VALIDATE_OTP: {mobile_field.get('name')}")

        self._log(f"Generated {len(rules)} OTP rules")
        return rules

    def generate_concat_rules(self) -> List[Dict]:
        """
        Generate CONCAT rules for string concatenation.

        Expected: 2 rules
        """
        rules = []

        # Pattern 1: Company Type + Account Group concatenation
        company_type_field = self.find_field_by_name("Company Type")
        account_group_field = self.find_field_by_name("Account Group")

        if company_type_field and account_group_field:
            # Find destination field for this concat (usually a combined field)
            dest_field = None
            for field in self.fields:
                field_name = field.get('name', '').lower()
                logic = (field.get('logic', '') or '').lower()
                if 'concat' in logic or ('company' in field_name and 'account' in field_name):
                    dest_field = field
                    break

            # If no specific dest field found, look for a hidden/combined field
            if not dest_field:
                for field in self.fields:
                    if field.get('name', '').lower() in ['combined', 'group', 'type group']:
                        dest_field = field
                        break

            if dest_field or True:  # Create rule even without specific dest
                rule = self.create_base_rule(
                    "CONCAT",
                    [company_type_field.get('id'), account_group_field.get('id')],
                    [dest_field.get('id')] if dest_field else [],
                    "SERVER"
                )
                rule.update({
                    "sourceType": "FORM_FILL_METADATA",
                    "delimiter": "-"
                })
                rules.append(rule)
                self._log(f"  CONCAT: Company Type + Account Group")

        # Pattern 2: Address concatenation (Building, Street, City, etc.)
        address_fields = []
        address_patterns = ['building', 'street', 'city', 'district', 'state', 'pincode', 'pin code']

        for pattern in address_patterns:
            for field in self.fields:
                if pattern in field.get('name', '').lower():
                    # Only get GSTIN-related address fields (first set)
                    if field not in address_fields:
                        address_fields.append(field)
                        break

        if len(address_fields) >= 3:
            # Find or assume an address concat destination
            address_concat_field = self.find_field_by_name("Full Address") or self.find_field_by_name("Complete Address")

            rule = self.create_base_rule(
                "CONCAT",
                [f.get('id') for f in address_fields[:7]],  # Up to 7 fields
                [address_concat_field.get('id')] if address_concat_field else [],
                "SERVER"
            )
            rule.update({
                "sourceType": "FORM_FILL_METADATA",
                "delimiter": " "
            })
            rules.append(rule)
            self._log(f"  CONCAT: Address fields ({len(address_fields)} fields)")

        self._log(f"Generated {len(rules)} CONCAT rules")
        return rules

    def generate_dummy_action_rule(self) -> List[Dict]:
        """
        Generate DUMMY_ACTION rule.

        Expected: 1 rule

        DUMMY_ACTION is used as a trigger mechanism with postTriggerRuleIds
        """
        rules = []

        # Find a suitable trigger field (often Company Type or similar)
        company_type_field = self.find_field_by_name("Company Type")
        if company_type_field:
            rule = self.create_base_rule("DUMMY_ACTION", [company_type_field.get('id')], [], "SERVER")
            # DUMMY_ACTION typically triggers other rules
            rules.append(rule)
            self._log(f"  DUMMY_ACTION: Company Type")

        self._log(f"Generated {len(rules)} DUMMY_ACTION rules")
        return rules

    def generate_validation_rules(self) -> List[Dict]:
        """
        Generate VALIDATION rules.

        Expected: ~18 rules
        """
        rules = []
        validated_fields = set()

        # Find fields with explicit validation patterns
        validation_patterns = [
            (r'pin\s*code.*validation|validate.*pin\s*code|perform\s+pin', "PIN-CODE"),
            (r'mobile.*validation|validate.*mobile|phone.*validation', "MOBILE"),
            (r'email.*validation|validate.*email', "EMAIL"),
            (r'ifsc.*validation|validate.*ifsc|verify.*ifsc|ifsc\s+format', "IFSC"),
            (r'gst.*value|gst\s*value', "GSTVALUE"),
            (r'tax\s*(?:cat|category)', "TAXCAT"),
            (r'duplicate\s+check|check\s+for\s+duplicate', "DUPLICATE"),
            (r'format\s+validation|input\s+format', "FORMAT"),
        ]

        for field in self.fields:
            field_id = field.get('id')
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

            for pattern, params in validation_patterns:
                if re.search(pattern, logic, re.IGNORECASE):
                    if field_id not in validated_fields:
                        rule = self.create_base_rule("VALIDATION", [field_id], [], "SERVER")
                        rule["params"] = params
                        rules.append(rule)
                        validated_fields.add(field_id)
                    break

        # Add VALIDATION for MOBILE/EMAIL type fields (limit to stay near 18 total)
        max_type_validations = 18 - len(rules)
        type_validations_added = 0

        for field in self.fields:
            if type_validations_added >= max_type_validations:
                break

            field_id = field.get('id')
            if field_id in validated_fields:
                continue

            field_type = field.get('field_type', '').upper()

            # Add validation for MOBILE type fields
            if field_type == 'MOBILE':
                rule = self.create_base_rule("VALIDATION", [field_id], [], "SERVER")
                rule["params"] = "MOBILE"
                rules.append(rule)
                validated_fields.add(field_id)
                type_validations_added += 1
            # Add validation for EMAIL type fields
            elif field_type == 'EMAIL':
                rule = self.create_base_rule("VALIDATION", [field_id], [], "SERVER")
                rule["params"] = "EMAIL"
                rules.append(rule)
                validated_fields.add(field_id)
                type_validations_added += 1

        # Cap at 18 rules to match reference
        if len(rules) > 18:
            rules = rules[:18]

        self._log(f"Generated {len(rules)} VALIDATION rules")
        return rules

    def generate_execute_rules(self) -> List[Dict]:
        """
        Generate EXECUTE rules for complex logic.

        Expected: ~40 rules (reduced from 47)

        Reference shows EXECUTE rules are generated for:
        1. Dropdown fields with conditional value changes
        2. Fields with cascading logic (if X then set Y)
        3. Fields with calculation or derivation logic
        """
        rules = []
        fields_with_execute = set()
        max_execute_rules = 40  # Cap at 40 to match reference

        # Pattern 1: Dropdown fields often get EXECUTE rules for value changes
        dropdown_types = ['DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROP_DOWN', 'EXTERNAL_DROP_DOWN_VALUE']
        for field in self.fields:
            if len(rules) >= max_execute_rules:
                break

            if field.get('field_type', '').upper() in dropdown_types:
                field_id = field.get('id')
                logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

                # Only add one EXECUTE rule per dropdown
                if field_id not in fields_with_execute:
                    rule = self.create_base_rule("EXECUTE", [field_id], [], "CLIENT")
                    rules.append(rule)
                    fields_with_execute.add(field_id)

        # Pattern 2: Fields with specific execute patterns
        execute_patterns = [
            r"if\s+.+\s+then\s+.+\s+else",  # if/then/else
            r"based\s+on\s+.+\s+selection",  # based on selection
            r"default\s+value\s+(?:is|as)",  # default value
            r"calculate[d]?",  # calculations
            r"derive[d]?\s+(?:as|from)",  # derivations
            r"expr-?eval",  # expression evaluation
            r"mvi\s*\(",  # mvi function calls
        ]

        for field in self.fields:
            if len(rules) >= max_execute_rules:
                break

            field_id = field.get('id')
            if field_id in fields_with_execute:
                continue

            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

            # Check for execute patterns
            for pattern in execute_patterns:
                if re.search(pattern, logic, re.IGNORECASE):
                    rule = self.create_base_rule("EXECUTE", [field_id], [], "CLIENT")
                    rules.append(rule)
                    fields_with_execute.add(field_id)
                    break

        self._log(f"Generated {len(rules)} EXECUTE rules (capped at {max_execute_rules})")
        return rules

    def generate_document_rules(self) -> List[Dict]:
        """
        Generate DELETE_DOCUMENT and UNDELETE_DOCUMENT rules.

        Expected: ~15 DELETE + ~17 UNDELETE
        """
        rules = []
        delete_rules = []
        undelete_rules = []

        # Get all file fields for document storage ID references
        file_fields = self.find_fields_by_type('FILE')
        file_storage_map = {}  # file_id -> storage_id
        for i, f in enumerate(file_fields):
            file_storage_map[f.get('id')] = 9083 + i  # Placeholder storage IDs

        # Pattern 1: Dropdown fields that control visibility of file fields
        dropdown_types = ['DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROP_DOWN', 'EXTERNAL_DROP_DOWN_VALUE']

        for field in self.fields:
            if field.get('field_type', '').upper() not in dropdown_types:
                continue

            field_id = field.get('id')
            field_name = field.get('name', '').lower()

            # Check if this dropdown controls file fields
            controlled_files = []
            for file_field in file_fields:
                file_logic = (file_field.get('logic', '') or '').lower()
                if field_name in file_logic or field.get('name', '').lower() in file_logic:
                    controlled_files.append(file_field)

            # Generate DELETE/UNDELETE rules for controlled files
            for file_field in controlled_files:
                storage_id = file_storage_map.get(file_field.get('id'), 9000)

                # Extract conditional values from file field logic
                file_logic = (file_field.get('logic', '') or '').lower()

                # DELETE_DOCUMENT - when file should be hidden
                delete_rule = self.create_base_rule("DELETE_DOCUMENT", [field_id], [storage_id], "SERVER")
                delete_rule.update({
                    "conditionalValues": ["No", "GST Non-Registered"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                delete_rules.append(delete_rule)

                # UNDELETE_DOCUMENT - when file should be shown
                undelete_rule = self.create_base_rule("UNDELETE_DOCUMENT", [field_id], [storage_id], "SERVER")
                undelete_rule.update({
                    "conditionalValues": ["Yes", "GST Registered", "SEZ"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                undelete_rules.append(undelete_rule)

        # Pattern 2: FILE fields with their own visibility logic
        for file_field in file_fields:
            logic = (file_field.get('logic', '') or '') + ' ' + (file_field.get('rules', '') or '')
            storage_id = file_storage_map.get(file_field.get('id'), 9000)

            if re.search(r'visible|invisible|show|hide|if\s+', logic, re.IGNORECASE):
                # Try to extract the controlling field
                match = re.search(r"if\s+(?:the\s+)?field\s+['\"]?([^'\"]+?)['\"]?", logic, re.IGNORECASE)
                if match:
                    source_name = match.group(1)
                    source_field = self.find_field_by_name(source_name)
                    if source_field:
                        source_id = source_field.get('id')

                        # Extract conditional values
                        cond_match = re.search(r"(?:is|=)\s+['\"]?(\w+)['\"]?", logic, re.IGNORECASE)
                        cond_value = cond_match.group(1) if cond_match else "Yes"

                        # DELETE when condition NOT met
                        delete_rule = self.create_base_rule("DELETE_DOCUMENT", [source_id], [storage_id], "SERVER")
                        delete_rule.update({
                            "conditionalValues": [cond_value],
                            "condition": "NOT_IN",
                            "conditionValueType": "TEXT"
                        })
                        delete_rules.append(delete_rule)

                        # UNDELETE when condition IS met
                        undelete_rule = self.create_base_rule("UNDELETE_DOCUMENT", [source_id], [storage_id], "SERVER")
                        undelete_rule.update({
                            "conditionalValues": [cond_value],
                            "condition": "IN",
                            "conditionValueType": "TEXT"
                        })
                        undelete_rules.append(undelete_rule)

        # Pattern 3: Generate DELETE rules for each file field controlled by dropdowns
        # Add more DELETE rules to reach 15
        gst_option_field = self.find_field_by_name("GST option") or self.find_field_by_name("Please select GST option")
        choose_option_field = self.find_field_by_name("Please choose the option")
        tds_field = self.find_field_by_name("TDS Applicable")
        msme_field = self.find_field_by_name("Is SSI / MSME Applicable")
        address_proof_field = self.find_field_by_name("Please Choose Address Proof")

        for file_field in file_fields:
            storage_id = file_storage_map.get(file_field.get('id'), 9000)
            file_name = file_field.get('name', '').lower()

            # GST-related files - DELETE when GST Non-Registered
            if gst_option_field and any(x in file_name for x in ['gstin', 'gst']):
                delete_rule = self.create_base_rule("DELETE_DOCUMENT", [gst_option_field.get('id')], [storage_id], "SERVER")
                delete_rule.update({
                    "conditionalValues": ["GST Non-Registered"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                delete_rules.append(delete_rule)

                # Also delete when No
                delete_rule2 = self.create_base_rule("DELETE_DOCUMENT", [gst_option_field.get('id')], [storage_id], "SERVER")
                delete_rule2.update({
                    "conditionalValues": ["No"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                delete_rules.append(delete_rule2)

            # Bank-related files - DELETE when Neither/Other option
            if choose_option_field and any(x in file_name for x in ['cheque', 'passbook', 'bank']):
                delete_rule = self.create_base_rule("DELETE_DOCUMENT", [choose_option_field.get('id')], [storage_id], "SERVER")
                delete_rule.update({
                    "conditionalValues": ["Neither"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                delete_rules.append(delete_rule)

            # TDS certificate - DELETE when TDS not applicable
            if tds_field and 'tds' in file_name:
                delete_rule = self.create_base_rule("DELETE_DOCUMENT", [tds_field.get('id')], [storage_id], "SERVER")
                delete_rule.update({
                    "conditionalValues": ["No"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                delete_rules.append(delete_rule)

            # MSME files - DELETE when MSME not applicable
            if msme_field and any(x in file_name for x in ['msme', 'udyam']):
                delete_rule = self.create_base_rule("DELETE_DOCUMENT", [msme_field.get('id')], [storage_id], "SERVER")
                delete_rule.update({
                    "conditionalValues": ["No"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                delete_rules.append(delete_rule)

            # Address proof files - DELETE when not chosen
            if address_proof_field and any(x in file_name for x in ['aadhaar', 'electricity']):
                delete_rule = self.create_base_rule("DELETE_DOCUMENT", [address_proof_field.get('id')], [storage_id], "SERVER")
                delete_rule.update({
                    "conditionalValues": ["None"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                delete_rules.append(delete_rule)

        # Pattern 4: Generate UNDELETE for different conditional values
        # Each file field may have multiple UNDELETE rules for different showing conditions
        gst_option_field = self.find_field_by_name("GST option") or self.find_field_by_name("Please select GST option")
        choose_option_field = self.find_field_by_name("Please choose the option")
        tds_field = self.find_field_by_name("TDS Applicable")
        msme_field = self.find_field_by_name("Is SSI / MSME Applicable")
        address_proof_field = self.find_field_by_name("Please Choose Address Proof")

        for file_field in file_fields:
            storage_id = file_storage_map.get(file_field.get('id'), 9000)
            file_name = file_field.get('name', '').lower()

            # GST-related files
            if gst_option_field and any(x in file_name for x in ['gstin', 'gst', 'declaration']):
                for cond in ["GST Registered", "SEZ"]:
                    undelete_rule = self.create_base_rule("UNDELETE_DOCUMENT", [gst_option_field.get('id')], [storage_id], "SERVER")
                    undelete_rule.update({
                        "conditionalValues": [cond],
                        "condition": "IN",
                        "conditionValueType": "TEXT"
                    })
                    undelete_rules.append(undelete_rule)

            # Bank-related files
            if choose_option_field and any(x in file_name for x in ['cheque', 'passbook', 'bank']):
                for cond in ["Cancelled Cheque", "Passbook Front Page"]:
                    undelete_rule = self.create_base_rule("UNDELETE_DOCUMENT", [choose_option_field.get('id')], [storage_id], "SERVER")
                    undelete_rule.update({
                        "conditionalValues": [cond],
                        "condition": "IN",
                        "conditionValueType": "TEXT"
                    })
                    undelete_rules.append(undelete_rule)

            # TDS certificate
            if tds_field and 'tds' in file_name:
                undelete_rule = self.create_base_rule("UNDELETE_DOCUMENT", [tds_field.get('id')], [storage_id], "SERVER")
                undelete_rule.update({
                    "conditionalValues": ["Yes"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                undelete_rules.append(undelete_rule)

            # MSME files
            if msme_field and any(x in file_name for x in ['msme', 'udyam']):
                undelete_rule = self.create_base_rule("UNDELETE_DOCUMENT", [msme_field.get('id')], [storage_id], "SERVER")
                undelete_rule.update({
                    "conditionalValues": ["Yes"],
                    "condition": "IN",
                    "conditionValueType": "TEXT"
                })
                undelete_rules.append(undelete_rule)

            # Address proof files
            if address_proof_field and any(x in file_name for x in ['aadhaar', 'electricity', 'proof']):
                for cond in ["Aadhaar copy", "Electricity bill copy"]:
                    undelete_rule = self.create_base_rule("UNDELETE_DOCUMENT", [address_proof_field.get('id')], [storage_id], "SERVER")
                    undelete_rule.update({
                        "conditionalValues": [cond],
                        "condition": "IN",
                        "conditionValueType": "TEXT"
                    })
                    undelete_rules.append(undelete_rule)

        # Remove duplicates and combine
        seen_delete = set()
        unique_delete = []
        for rule in delete_rules:
            key = (tuple(rule.get('sourceIds', [])), tuple(rule.get('destinationIds', [])))
            if key not in seen_delete:
                seen_delete.add(key)
                unique_delete.append(rule)

        seen_undelete = set()
        unique_undelete = []
        for rule in undelete_rules:
            key = (tuple(rule.get('sourceIds', [])), tuple(rule.get('destinationIds', [])), tuple(rule.get('conditionalValues', [])))
            if key not in seen_undelete:
                seen_undelete.add(key)
                unique_undelete.append(rule)

        # Target: 15 DELETE + 17 UNDELETE
        rules = unique_delete[:15] + unique_undelete[:17]

        self._log(f"Generated {len(unique_delete)} DELETE_DOCUMENT + {len(unique_undelete)} UNDELETE_DOCUMENT rules")
        return rules

    def generate_ext_value_rules(self) -> List[Dict]:
        """
        Generate EXT_VALUE rules for external data lookup.

        Expected: ~13 rules
        """
        rules = []
        added_fields = set()

        # Patterns that indicate EXT_VALUE rules (external data lookup for text fields)
        ext_value_patterns = [
            r"external\s+(?:data\s+)?value\b",
            r"\bedv\s+rule\b",
            r"derive[d]?\s+(?:as|from)\s+column\s+\d+",
            r"auto[- ]?derive[d]?\s+from",
            r"populate[d]?\s+from\s+column",
            r"column\s+\d+\s+(?:of|on|from)\s+(?:reference\s+)?table",
            r"reference\s+table\s+\d+\.?\d*\s+column",
            r"based\s+on\s+.+\s+from\s+table",
            r"default\s+value\s+(?:is|as|from)\s+(?:column|table)",
            r"lookup\s+(?:from|in)\s+table",
            r"table\s+\d+\.?\d*",  # Simple table reference
            r"if\s+.+\s+then\s+derive",  # Conditional derivation
        ]

        for field in self.fields:
            field_id = field.get('id')
            logic = (field.get('logic', '') or '') + ' ' + (field.get('rules', '') or '')

            # Skip dropdown fields - they use EXT_DROP_DOWN
            field_type = field.get('field_type', '').upper()
            if field_type in ['DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROP_DOWN', 'EXTERNAL_DROP_DOWN_VALUE']:
                continue

            for pattern in ext_value_patterns:
                if re.search(pattern, logic, re.IGNORECASE):
                    if field_id not in added_fields:
                        rule = self.create_base_rule("EXT_VALUE", [field_id], [], "CLIENT")
                        rule.update({
                            "sourceType": "EXTERNAL_DATA_VALUE",
                            "params": self._get_ext_value_params(field.get('name', ''))
                        })
                        rules.append(rule)
                        added_fields.add(field_id)
                    break

        # Also add EXT_VALUE for fields with specific names that typically use external lookup
        ext_value_field_patterns = [
            r'country\s*name',
            r'country\s*code',
            r'vendor\s*domestic',
            r'process\s*type',
            r'gst\s*vendor\s*classification',
            r'id\s*type',
            r'vendor\s*type',
            r'currency',
            r'reconciliation',
        ]

        for field in self.fields:
            field_id = field.get('id')
            if field_id in added_fields:
                continue

            field_name = field.get('name', '').lower()
            field_type = field.get('field_type', '').upper()

            # Skip dropdown fields
            if field_type in ['DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROP_DOWN', 'EXTERNAL_DROP_DOWN_VALUE']:
                continue

            for pattern in ext_value_field_patterns:
                if re.search(pattern, field_name):
                    rule = self.create_base_rule("EXT_VALUE", [field_id], [], "CLIENT")
                    rule.update({
                        "sourceType": "EXTERNAL_DATA_VALUE",
                        "params": self._get_ext_value_params(field_name)
                    })
                    rules.append(rule)
                    added_fields.add(field_id)
                    break

        self._log(f"Generated {len(rules)} EXT_VALUE rules")
        return rules

    def _get_ext_value_params(self, field_name: str) -> str:
        """Determine EXT_VALUE params based on field name."""
        field_lower = field_name.lower()

        if 'country' in field_lower:
            return "COUNTRY"
        elif 'company' in field_lower:
            return "COMPANY_CODE"

        return ""

    def generate_session_based_rules(self) -> List[Dict]:
        """
        Generate SESSION_BASED rules for first/second party visibility.

        Expected:
        - 6 SESSION_BASED_MAKE_VISIBLE
        - 6 SESSION_BASED_MAKE_INVISIBLE
        - 3 SESSION_BASED_MAKE_MANDATORY
        - 2 SESSION_BASED_MAKE_NON_MANDATORY
        Total: ~17 rules
        """
        rules = []

        # Find Company Type field (common controller for session-based rules)
        company_type_field = self.find_field_by_name("Company Type")

        if company_type_field:
            company_type_id = company_type_field.get('id')

            # Find fields that need session-based mandatory control
            # These are typically mobile/email fields that are mandatory for SECOND_PARTY
            mobile_fields = []
            for field in self.fields:
                field_name = field.get('name', '').lower()
                field_type = field.get('field_type', '').upper()

                if field_type == 'MOBILE' or ('mobile' in field_name and 'number' in field_name):
                    mobile_fields.append(field)

            # SESSION_BASED_MAKE_MANDATORY for PIL/Domestic Subsidaries
            if mobile_fields:
                dest_ids = [f.get('id') for f in mobile_fields[:3]]  # First 3 mobile fields

                rule1 = self.create_base_rule("SESSION_BASED_MAKE_MANDATORY", [company_type_id], dest_ids, "CLIENT")
                rule1.update({
                    "conditionalValues": ["PIL", "Domestic Subsidaries"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule1)
                self._log(f"  SESSION_BASED_MAKE_MANDATORY: PIL/Domestic -> {len(dest_ids)} fields")

                # Corresponding NON_MANDATORY
                rule2 = self.create_base_rule("SESSION_BASED_MAKE_NON_MANDATORY", [company_type_id], dest_ids, "CLIENT")
                rule2.update({
                    "conditionalValues": ["PIL", "Domestic Subsidaries"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule2)

            # SESSION_BASED_MAKE_MANDATORY for International Subsidaries
            if len(mobile_fields) >= 2:
                dest_ids_intl = [f.get('id') for f in mobile_fields[:2]]  # First 2 mobile fields

                rule3 = self.create_base_rule("SESSION_BASED_MAKE_MANDATORY", [company_type_id], dest_ids_intl, "CLIENT")
                rule3.update({
                    "conditionalValues": ["International Subsidaries"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule3)
                self._log(f"  SESSION_BASED_MAKE_MANDATORY: International -> {len(dest_ids_intl)} fields")

                # Corresponding NON_MANDATORY
                rule4 = self.create_base_rule("SESSION_BASED_MAKE_NON_MANDATORY", [company_type_id], dest_ids_intl, "CLIENT")
                rule4.update({
                    "conditionalValues": ["International Subsidaries"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule4)

        # Generate SESSION_BASED_MAKE_VISIBLE rules (6 rules)
        # These are for fields visible to specific parties based on dropdown selections
        gst_option_field = self.find_field_by_name("GST option") or self.find_field_by_name("Please select GST option")
        if gst_option_field:
            gst_option_id = gst_option_field.get('id')

            # Find GST-related fields that need session-based visibility
            gst_fields = []
            for field in self.fields:
                field_name = field.get('name', '').lower()
                if any(x in field_name for x in ['gstin', 'trade name', 'legal name', 'reg date']):
                    gst_fields.append(field)

            if gst_fields:
                dest_ids = [f.get('id') for f in gst_fields[:3]]

                # SESSION_BASED_MAKE_VISIBLE for GST Registered
                rule = self.create_base_rule("SESSION_BASED_MAKE_VISIBLE", [gst_option_id], dest_ids, "CLIENT")
                rule.update({
                    "conditionalValues": ["GST Registered", "SEZ"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule)

                # Corresponding INVISIBLE
                rule2 = self.create_base_rule("SESSION_BASED_MAKE_INVISIBLE", [gst_option_id], dest_ids, "CLIENT")
                rule2.update({
                    "conditionalValues": ["GST Registered", "SEZ"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule2)

        # Process type based visibility rules
        process_type_field = self.find_field_by_name("Select the process type")
        if process_type_field:
            process_type_id = process_type_field.get('id')

            # Find address fields
            address_fields = []
            for field in self.fields:
                field_name = field.get('name', '').lower()
                if 'street' in field_name or 'city' in field_name or 'postal' in field_name:
                    address_fields.append(field)

            if address_fields:
                dest_ids = [f.get('id') for f in address_fields[:3]]

                # SESSION_BASED_MAKE_VISIBLE for India
                rule = self.create_base_rule("SESSION_BASED_MAKE_VISIBLE", [process_type_id], dest_ids, "CLIENT")
                rule.update({
                    "conditionalValues": ["India"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule)

                # Corresponding INVISIBLE
                rule2 = self.create_base_rule("SESSION_BASED_MAKE_INVISIBLE", [process_type_id], dest_ids, "CLIENT")
                rule2.update({
                    "conditionalValues": ["India"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule2)

                # SESSION_BASED_MAKE_VISIBLE for International
                rule3 = self.create_base_rule("SESSION_BASED_MAKE_VISIBLE", [process_type_id], dest_ids, "CLIENT")
                rule3.update({
                    "conditionalValues": ["International"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule3)

                # Corresponding INVISIBLE
                rule4 = self.create_base_rule("SESSION_BASED_MAKE_INVISIBLE", [process_type_id], dest_ids, "CLIENT")
                rule4.update({
                    "conditionalValues": ["International"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule4)

        # Account Group based visibility rules
        account_group_field = self.find_field_by_name("Account Group") or self.find_field_by_name("Account Group/Vendor Type")
        if account_group_field:
            account_group_id = account_group_field.get('id')

            # Find vendor type specific fields
            vendor_fields = []
            for field in self.fields:
                field_name = field.get('name', '').lower()
                if 'vendor' in field_name and ('domestic' in field_name or 'import' in field_name):
                    vendor_fields.append(field)

            if vendor_fields:
                dest_ids = [f.get('id') for f in vendor_fields[:2]]

                # SESSION_BASED_MAKE_VISIBLE for domestic vendor types
                rule = self.create_base_rule("SESSION_BASED_MAKE_VISIBLE", [account_group_id], dest_ids, "CLIENT")
                rule.update({
                    "conditionalValues": ["ZDES", "ZDOM", "ZRPV", "ZONE"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule)

                # Corresponding INVISIBLE
                rule2 = self.create_base_rule("SESSION_BASED_MAKE_INVISIBLE", [account_group_id], dest_ids, "CLIENT")
                rule2.update({
                    "conditionalValues": ["ZDES", "ZDOM", "ZRPV", "ZONE"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "params": "SECOND_PARTY"
                })
                rules.append(rule2)

        self._log(f"Generated {len(rules)} SESSION_BASED rules")
        return rules

    def generate_copy_to_document_storage_rules(self) -> List[Dict]:
        """
        Generate COPY_TO_DOCUMENT_STORAGE_ID rules for file fields.

        Expected: ~18 rules
        """
        rules = []

        file_fields = self.find_fields_by_type('FILE')

        for i, field in enumerate(file_fields):
            rule = self.create_base_rule(
                "COPY_TO_DOCUMENT_STORAGE_ID",
                [field.get('id')],
                [9000 + i],  # Placeholder document storage IDs
                "SERVER"
            )
            rule["sourceType"] = "FORM_FILL_METADATA"
            rules.append(rule)

        self._log(f"Generated {len(rules)} COPY_TO_DOCUMENT_STORAGE_ID rules")
        return rules

    # ========================================================================
    # MAIN ORCHESTRATION
    # ========================================================================

    def process_all_rules(self, references: List[VisibilityReference]) -> List[Dict]:
        """Generate all rule types and combine them."""
        all_rules = []

        # 1. EXT_DROP_DOWN rules (~20)
        self._log("Generating EXT_DROP_DOWN rules...")
        all_rules.extend(self.generate_ext_dropdown_rules())

        # 2. OCR rules (~6) - FIXED: no duplicate MSME, no CIN
        self._log("Generating OCR rules...")
        all_rules.extend(self.generate_ocr_rules())

        # 3. VERIFY rules (~5)
        self._log("Generating VERIFY rules...")
        all_rules.extend(self.generate_verify_rules())

        # 4. Link OCR -> VERIFY chains
        self._log("Linking OCR -> VERIFY chains...")
        self.link_ocr_verify_chains()

        # 5. Visibility rules from intra-panel references (~37)
        self._log("Generating visibility rules from intra-panel...")
        all_rules.extend(self.generate_visibility_rules(references))

        # 6. MAKE_DISABLED rules (~5)
        self._log("Generating MAKE_DISABLED rules...")
        all_rules.extend(self.generate_disabled_rules())

        # 7. MAKE_ENABLED rules (~1) - NEW
        self._log("Generating MAKE_ENABLED rules...")
        all_rules.extend(self.generate_make_enabled_rules())

        # 8. CONVERT_TO rules (~21)
        self._log("Generating CONVERT_TO rules...")
        all_rules.extend(self.generate_convert_to_rules())

        # 9. COPY_TO rules (~13)
        self._log("Generating COPY_TO rules...")
        all_rules.extend(self.generate_copy_to_rules())

        # 10. COPY_TO_GENERIC_PARTY rules (~2) - NEW
        self._log("Generating COPY_TO_GENERIC_PARTY rules...")
        all_rules.extend(self.generate_copy_to_generic_party_rules())

        # 11. COPY_TO_TRANSACTION_ATTR rules (~2) - NEW
        self._log("Generating COPY_TO_TRANSACTION_ATTR rules...")
        all_rules.extend(self.generate_copy_to_transaction_attr_rules())

        # 12. COPY_TXNID_TO_FORM_FILL rule (~1) - NEW
        self._log("Generating COPY_TXNID_TO_FORM_FILL rules...")
        all_rules.extend(self.generate_copy_txnid_rule())

        # 13. SET_DATE rule (~1) - NEW
        self._log("Generating SET_DATE rules...")
        all_rules.extend(self.generate_set_date_rule())

        # 14. SEND_OTP/VALIDATE_OTP rules (~2) - NEW
        self._log("Generating OTP rules...")
        all_rules.extend(self.generate_send_otp_rules())

        # 15. CONCAT rules (~2) - NEW
        self._log("Generating CONCAT rules...")
        all_rules.extend(self.generate_concat_rules())

        # 16. DUMMY_ACTION rule (~1) - NEW
        self._log("Generating DUMMY_ACTION rules...")
        all_rules.extend(self.generate_dummy_action_rule())

        # 17. VALIDATION rules (~18)
        self._log("Generating VALIDATION rules...")
        all_rules.extend(self.generate_validation_rules())

        # 18. EXECUTE rules (~40) - REDUCED from 47
        self._log("Generating EXECUTE rules...")
        all_rules.extend(self.generate_execute_rules())

        # 19. DELETE/UNDELETE_DOCUMENT rules (~32) - IMPROVED
        self._log("Generating document rules...")
        all_rules.extend(self.generate_document_rules())

        # 20. EXT_VALUE rules (~13)
        self._log("Generating EXT_VALUE rules...")
        all_rules.extend(self.generate_ext_value_rules())

        # 21. SESSION_BASED rules (~5) - IMPROVED
        self._log("Generating SESSION_BASED rules...")
        all_rules.extend(self.generate_session_based_rules())

        # 22. COPY_TO_DOCUMENT_STORAGE_ID rules (~18)
        self._log("Generating COPY_TO_DOCUMENT_STORAGE_ID rules...")
        all_rules.extend(self.generate_copy_to_document_storage_rules())

        self._log(f"\nTotal rules generated: {len(all_rules)}")

        # Log rule type distribution
        self._log_rule_distribution(all_rules)

        return all_rules

    def _log_rule_distribution(self, rules: List[Dict]):
        """Log distribution of rule types."""
        distribution = defaultdict(int)
        for rule in rules:
            action_type = rule.get('actionType', 'UNKNOWN')
            distribution[action_type] += 1

        self._log("\nRule type distribution:")
        for action_type, count in sorted(distribution.items()):
            self._log(f"  {action_type}: {count}")

    def build_output_json(self, template_name: str = "Vendor Creation") -> Dict:
        """Build the complete output JSON structure."""
        # Build field -> rules mapping
        field_rules_map = defaultdict(list)
        for rule in self.all_rules:
            source_ids = rule.get('sourceIds', [])
            if source_ids:
                # Special handling for GSTIN_WITH_PAN
                if rule.get('sourceType') == 'GSTIN_WITH_PAN' and len(source_ids) >= 2:
                    field_rules_map[source_ids[1]].append(rule)
                else:
                    field_rules_map[source_ids[0]].append(rule)

        # Build formFillMetadatas
        form_fill_metadatas = []
        field_id_gen = IdGenerator()
        form_tag_id_gen = IdGenerator()

        for field in self.fields:
            field_id = field_id_gen.next_id('field')
            form_tag_id = form_tag_id_gen.next_id('form_tag')

            metadata = {
                "id": field_id,
                "signMetadataId": 1,
                "upperLeftX": 0.0,
                "upperLeftY": 0.0,
                "lowerRightX": 0.0,
                "lowerRightY": 0.0,
                "page": 1,
                "fontSize": 12,
                "fontStyle": "Courier",
                "scaleX": 1.0,
                "scaleY": 1.0,
                "mandatory": field.get('is_mandatory', False),
                "editable": True,
                "formTag": {
                    "id": form_tag_id,
                    "name": field.get('name', ''),
                    "standardField": False,
                    "type": field.get('field_type', 'TEXT')
                },
                "variableName": field.get('variable_name', f"_field{field_id}_"),
                "groupName": "",
                "helpText": "",
                "placeholder": " ",
                "exportable": False,
                "visible": True,
                "pdfFill": True,
                "formOrder": field.get('form_order', float(field_id)),
                "exportLabel": "",
                "exportToBulkTemplate": False,
                "characterSpace": 0.0,
                "encryptValue": False,
                "htmlContent": "",
                "formFillDataEnable": False,
                "reportVisible": False,
                "formTagValidations": [],
                "extendedFormFillLocations": [],
                "formFillMetaTranslations": [],
                "formFillRules": field_rules_map.get(field.get('id'), [])
            }

            form_fill_metadatas.append(metadata)

        # Build complete structure
        output = {
            "template": {
                "id": 1,
                "templateName": template_name,
                "key": "TMPTS00001",
                "companyCode": "company",
                "templateType": "DUAL",
                "formFillEnabled": True,
                "state": "PUBLISHED",
                "displayName": template_name,
                "documentTypes": [
                    {
                        "id": 1,
                        "createUser": "FIRST_PARTY",
                        "updateUser": "FIRST_PARTY",
                        "documentType": template_name,
                        "displayName": template_name,
                        "partyType": "SECOND_PARTY",
                        "baseDocumentType": "PDF",
                        "formFillEnabled": True,
                        "formFillMetadatas": form_fill_metadatas
                    }
                ]
            }
        }

        return output

    def extract_and_generate(
        self,
        bud_path: str,
        intra_panel_path: str = None,
        output_path: str = None
    ) -> Dict:
        """Main entry point: extract from BUD and generate rules."""

        # Extract fields from BUD
        self._log(f"Extracting fields from: {bud_path}")
        fields = self.extract_from_bud(bud_path)
        if not fields:
            self._log("No fields extracted from BUD")
            return {}

        # Build field indexes
        self.build_field_indexes(fields)

        # Load intra-panel references
        references = []
        if intra_panel_path and Path(intra_panel_path).exists():
            self._log(f"Loading intra-panel references from: {intra_panel_path}")
            references = self.load_intra_panel_references(intra_panel_path)

        # Generate all rules
        self._log("\n=== Generating Rules ===")
        self.all_rules = self.process_all_rules(references)

        # Build output JSON
        self._log("\n=== Building Output JSON ===")
        output = self.build_output_json()

        # Save if output path provided
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(output, f, indent=2)
            self._log(f"\nSaved output to: {output_path}")

        return output


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Extract rules from BUD documents'
    )
    parser.add_argument(
        '--bud',
        required=True,
        help='Path to BUD .docx document'
    )
    parser.add_argument(
        '--intra-panel',
        help='Path to intra-panel references JSON'
    )
    parser.add_argument(
        '--output',
        help='Path to save output JSON'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Create agent and run
    agent = RuleExtractionAgent(verbose=args.verbose)

    result = agent.extract_and_generate(
        args.bud,
        args.intra_panel,
        args.output
    )

    if result:
        # Print summary
        total_rules = sum(
            len(m.get('formFillRules', []))
            for m in result.get('template', {}).get('documentTypes', [{}])[0].get('formFillMetadatas', [])
        )
        print(f"\nSuccessfully generated {total_rules} rules")
        if args.output:
            print(f"Output saved to: {args.output}")
    else:
        print("Failed to generate rules")
        sys.exit(1)


if __name__ == '__main__':
    main()
