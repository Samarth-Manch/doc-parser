"""
Enhanced Rule Extraction Agent v4 - Fixes from self-heal analysis.

Key improvements in v4 based on eval report:
1. Fix OCR → VERIFY chains (4 missing in v3)
2. Add all visibility rules from intra-panel references
3. Add MAKE_DISABLED rules for all non-editable fields
4. Add MAKE_MANDATORY/MAKE_NON_MANDATORY paired rules
5. Fix data type issues (str vs dict handling)
6. Better field matching with panel context
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
    form_order: float = 0.0


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

        return result


class EnhancedRuleExtractionAgentV4:
    """Enhanced rule extraction agent v4 with fixes from self-heal analysis."""

    # VERIFY ordinal mappings from Rule-Schemas.json
    VERIFY_ORDINALS = {
        'PAN_NUMBER': {
            1: 'Panholder title',
            2: 'Firstname',
            3: 'Lastname',
            4: 'Fullname',
            5: 'Last updated',
            6: 'Pan retrieval status',
            7: 'Fullname without title',
            8: 'Pan type',
            9: 'Aadhaar seeding status',
            10: 'Middle name',
        },
        'GSTIN': {
            1: 'Trade name',
            2: 'Longname',
            3: 'Reg date',
            4: 'City',
            5: 'Type',
            6: 'Building number',
            7: 'Flat number',
            8: 'District code',
            9: 'State code',
            10: 'Street',
            11: 'Pincode',
            12: 'Locality',
            13: 'Landmark',
            14: 'Constitution of business',
            15: 'Floor',
            16: 'Block',
            17: 'latitude',
            18: 'longitude',
            19: 'Last update',
            20: 'Gstnstatus',
            21: 'isGst',
        },
        'BANK_ACCOUNT_NUMBER': {
            1: 'Bank Beneficiary Name',
            2: 'Bank Reference',
            3: 'Verification Status',
            4: 'Message',
        },
        'MSME_UDYAM_REG_NUMBER': {
            1: 'Name Of Enterprise',
            2: 'Major Activity',
            3: 'Social Category',
            4: 'Enterprise',
            5: 'Date Of Commencement',
            6: 'Dic Name',
            7: 'State',
            8: 'Modified Date',
            9: 'Expiry Date',
            10: 'Address Line1',
            11: 'Building',
            12: 'Street',
            13: 'Area',
            14: 'City',
            15: 'Pin',
            16: 'District',
            17: 'Classification Year',
            18: 'Classification Date',
            19: 'Applied State',
            20: 'Status',
            21: 'Udyam',
        },
        'CHEQUEE': {
            1: 'bankName',
            2: 'ifscCode',
            3: 'beneficiaryName',
            4: 'accountNumber',
            5: 'address',
            6: 'micrCode',
            7: 'branch',
        },
        'AADHAR_BACK_IMAGE': {
            1: 'aadharAddress1',
            2: 'aadharAddress2',
            3: 'aadharPin',
            4: 'aadharCity',
            5: 'aadharDist',
            6: 'aadharState',
            7: 'aadharFatherName',
            8: 'aadharCountry',
            9: 'aadharCoords',
        },
    }

    # OCR to VERIFY chain mappings - ALL chains must be linked
    OCR_VERIFY_CHAINS = {
        'PAN_IMAGE': 'PAN_NUMBER',
        'GSTIN_IMAGE': 'GSTIN',
        'CHEQUEE': 'BANK_ACCOUNT_NUMBER',
        'MSME': 'MSME_UDYAM_REG_NUMBER',
        'CIN': None,
        'AADHAR_IMAGE': None,
        'AADHAR_BACK_IMAGE': None,
    }

    # Field name patterns for OCR detection
    OCR_FIELD_PATTERNS = {
        r'upload\s*pan|pan\s*image|pan\s*upload': ('PAN_IMAGE', 'PAN'),
        r'gstin\s*image|upload\s*gstin|gstin\s*upload': ('GSTIN_IMAGE', 'GSTIN'),
        r'aadhaar?\s*front|front\s*aadhaar?|aadhaar?\s*front\s*copy': ('AADHAR_IMAGE', None),
        r'aadhaar?\s*back|back\s*aadhaar?|aadhaar?\s*back\s*image': ('AADHAR_BACK_IMAGE', None),
        r'cancelled?\s*cheque|cheque\s*image': ('CHEQUEE', 'IFSC Code'),
        r'msme\s*image|upload\s*msme|msme\s*registration': ('MSME', 'MSME Registration Number'),
        r'cin\s*(?:image|certificate|upload)|upload\s*cin': ('CIN', 'CIN'),
        r'passbook|bank\s*letter': ('CHEQUEE', 'Bank Account Number'),
    }

    # EXT_VALUE field patterns
    EXT_VALUE_FIELDS = {
        'choose the group of company': {'ddType': 'COMPANY_CODE_PURCHASE_ORGANIZATION'},
        'company and ownership': {'ddType': 'COMPANY_CODE_PURCHASE_ORGANIZATION'},
        'account group/vendor type': {'ddType': 'VC_VENDOR_TYPES'},
        'group key/corporate group': {'ddType': 'VC_VENDOR_TYPES'},
        'vendor country': {'ddType': 'COUNTRY'},
        'title': {'ddType': 'TITLE'},
        'region (import)': {'ddType': 'COUNTRY'},
        'please choose the option': {'ddType': 'BANK_OPTIONS'},
        'bank country (import)': {'ddType': 'COUNTRY'},
        'order currency': {'ddType': 'CURRENCY_COUNTRY'},
        'purchase organization': {'ddType': 'COMPANY_CODE_PURCHASE_ORGANIZATION'},
        'currency': {'ddType': 'CURRENCY_COUNTRY'},
        'withholding tax type': {'ddType': 'WITHHOLDING_TAX_DATA'},
    }

    # Patterns for fields that should be disabled
    DISABLED_FIELD_PATTERNS = [
        r'non-?editable',
        r'read[\s-]?only',
        r'system[\s-]?generated',
        r'auto[\s-]?derived',
        r'auto[\s-]?populate',
        r'data\s+will\s+come\s+from',
        r'derived\s+from',
        r'\(non[\s-]?editable\)',
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
        self.fields_by_panel: Dict[str, List[FieldInfo]] = defaultdict(list)

        # Result tracking
        self.all_rules: List[GeneratedRule] = []
        self.rules_by_field: Dict[int, List[GeneratedRule]] = defaultdict(list)
        self.verify_rules: Dict[str, GeneratedRule] = {}
        self.ocr_rules: Dict[str, GeneratedRule] = {}

        # Track which visibility rules are generated to avoid duplicates
        self.visibility_generated: Set[Tuple] = set()

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
            print(msg)

    def _load_fields(self):
        """Load fields from schema."""
        doc_types = self.schema.get('template', {}).get('documentTypes', [])
        current_panel = 'Default'

        for doc_type in doc_types:
            metadatas = doc_type.get('formFillMetadatas', [])
            for meta in metadatas:
                form_tag = meta.get('formTag', {})
                field_type = form_tag.get('type', 'TEXT')

                # Track current panel
                if field_type == 'PANEL':
                    current_panel = form_tag.get('name', 'Default')
                    continue

                field = FieldInfo(
                    id=meta.get('id'),
                    name=form_tag.get('name', ''),
                    variable_name=meta.get('variableName', ''),
                    field_type=field_type,
                    is_mandatory=meta.get('mandatory', False),
                    panel_name=current_panel,
                    form_order=meta.get('formOrder', 0.0)
                )

                self.fields.append(field)
                self.field_by_id[field.id] = field
                self.field_by_name[field.name] = field
                self.field_by_name_lower[field.name.lower()] = field
                self.fields_by_panel[current_panel].append(field)

    def _safe_get_field_name(self, obj: Any) -> str:
        """Safely extract field name from object (handles str vs dict)."""
        if isinstance(obj, str):
            return obj
        elif isinstance(obj, dict):
            return obj.get('field_name', obj.get('name', ''))
        return ''

    def _extract_logic_from_intra_panel(self):
        """Extract logic from intra-panel references and attach to fields."""
        if not self.intra_panel_refs:
            return

        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                if not isinstance(ref, dict):
                    continue

                # Collect all possible logic texts
                all_logic = []

                for key in ['logic_text', 'rule_description', 'logic_summary',
                           'dependency_notes', 'logic_excerpt', 'raw_logic']:
                    if ref.get(key):
                        all_logic.append(str(ref[key]))

                # Check references - handle both dict and str
                for r in ref.get('references', []):
                    if isinstance(r, dict):
                        for key in ['dependency_description', 'logic_excerpt',
                                   'condition_description', 'raw_logic_excerpt']:
                            if r.get(key):
                                all_logic.append(str(r[key]))
                    elif isinstance(r, str):
                        all_logic.append(r)

                # Check depends_on
                for dep in ref.get('depends_on', []):
                    if isinstance(dep, dict):
                        for key in ['logic_excerpt', 'condition']:
                            if dep.get(key):
                                all_logic.append(str(dep[key]))
                    elif isinstance(dep, str):
                        all_logic.append(dep)

                # Get field name - handle both str and dict
                field_name = self._safe_get_field_name(
                    ref.get('dependent_field', ref.get('source_field', {}))
                )
                if not field_name:
                    field_name = ref.get('field_name', '')

                # Attach logic
                if field_name and all_logic:
                    field = self.match_field(field_name)
                    if field:
                        combined = ' '.join(all_logic)
                        field.logic = (field.logic + ' ' + combined) if field.logic else combined

    def match_field(self, name: str, panel: Optional[str] = None) -> Optional[FieldInfo]:
        """Match field by name with optional panel context."""
        if not name:
            return None

        name = str(name).strip()  # Ensure string

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
                if name_lower in f.name.lower() or f.name.lower() in name_lower:
                    return f

        # Partial match across all fields
        for field_name, field in self.field_by_name_lower.items():
            if name_lower in field_name or field_name in name_lower:
                return field

        return None

    def process(self) -> Dict:
        """Process all fields and generate rules."""
        self.log("Starting enhanced rule extraction v4...")

        # Step 1: Generate EXT_DROP_DOWN rules first (foundational)
        self._generate_ext_dropdown_rules()
        self.log(f"Generated EXT_DROP_DOWN rules: {sum(1 for r in self.all_rules if r.action_type == 'EXT_DROP_DOWN')}")

        # Step 2: Generate EXT_VALUE rules
        self._generate_ext_value_rules()
        self.log(f"Generated EXT_VALUE rules: {sum(1 for r in self.all_rules if r.action_type == 'EXT_VALUE')}")

        # Step 3: Generate visibility rules from intra-panel references
        self._generate_visibility_rules()
        self.log(f"Generated visibility/mandatory rules: {sum(1 for r in self.all_rules if 'VISIBLE' in r.action_type or 'MANDATORY' in r.action_type)}")

        # Step 4: Generate OCR rules
        self._generate_ocr_rules()
        self.log(f"Generated OCR rules: {sum(1 for r in self.all_rules if r.action_type == 'OCR')}")

        # Step 5: Generate VERIFY rules
        self._generate_verify_rules()
        self.log(f"Generated VERIFY rules: {sum(1 for r in self.all_rules if r.action_type == 'VERIFY')}")

        # Step 6: Link OCR → VERIFY chains (CRITICAL FIX from self-heal)
        self._link_ocr_verify_chains()
        self.log("Linked OCR → VERIFY chains")

        # Step 7: Generate MAKE_DISABLED rules (consolidated)
        self._generate_disabled_rules()
        self.log(f"Generated MAKE_DISABLED rules: {sum(1 for r in self.all_rules if r.action_type == 'MAKE_DISABLED')}")

        # Step 8: Generate CONVERT_TO rules
        self._generate_convert_to_rules()
        self.log(f"Generated CONVERT_TO rules: {sum(1 for r in self.all_rules if r.action_type == 'CONVERT_TO')}")

        # Step 9: Consolidate and deduplicate rules
        self._consolidate_rules()
        self.log(f"Total rules after consolidation: {len(self.all_rules)}")

        # Step 10: Rebuild rules_by_field mapping
        self._rebuild_rules_by_field()

        # Step 11: Populate schema
        populated = self._populate_schema()

        return populated

    def _generate_visibility_rules(self):
        """Generate visibility rules from intra-panel references - IMPROVED."""
        if not self.intra_panel_refs:
            return

        # Group destinations by controlling field and values
        visibility_groups: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))

        for panel in self.intra_panel_refs.get('panel_results', []):
            panel_name = panel.get('panel_name', 'Unknown')

            for ref in panel.get('intra_panel_references', []):
                if not isinstance(ref, dict):
                    continue

                dep_type = ref.get('dependency_type', '')

                # Handle various dependency types
                if dep_type in ['visibility', 'visibility_and_mandatory', 'conditional_behavior']:
                    self._process_visibility_reference(ref, visibility_groups, panel_name)

                # Also check references for visibility conditions
                for r in ref.get('references', []):
                    if not isinstance(r, dict):
                        continue
                    ref_type = r.get('reference_type', '')
                    if 'visibility' in ref_type.lower():
                        self._process_visibility_from_ref(ref, r, visibility_groups, panel_name)

                # Check logic_text for visibility patterns
                logic_text = ref.get('logic_text', ref.get('rule_description', ''))
                if logic_text:
                    self._extract_visibility_from_logic(ref, str(logic_text), visibility_groups, panel_name)

        # Generate rules from groups
        self._generate_visibility_rules_from_groups(visibility_groups)

    def _process_visibility_reference(self, ref: Dict, visibility_groups: Dict, panel_name: str):
        """Process a visibility reference."""
        source_field = self._safe_get_field_name(ref.get('source_field', ''))
        dep_field = self._safe_get_field_name(ref.get('dependent_field', ''))
        rule_desc = str(ref.get('rule_description', ''))

        if source_field and dep_field:
            values = self._extract_conditional_values(rule_desc)
            values_key = ','.join(sorted(values)) if values else 'Yes'

            visibility_groups[source_field][values_key].append({
                'field_name': dep_field,
                'include_mandatory': 'mandatory' in ref.get('dependency_type', '').lower() or 'mandatory' in rule_desc.lower(),
                'rule_description': rule_desc,
                'panel': panel_name
            })

    def _process_visibility_from_ref(self, ref: Dict, r: Dict, visibility_groups: Dict, panel_name: str):
        """Process visibility from a reference object."""
        controlling = r.get('referenced_field_name', '')
        dep_desc = str(r.get('dependency_description', ''))

        # Get target field
        target = self._safe_get_field_name(ref.get('dependent_field', ref.get('source_field', '')))

        if controlling and target:
            values = self._extract_conditional_values(dep_desc)
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
            # "if field 'X' value is Y then visible"
            r"if\s+(?:the\s+)?field\s*['\"]([^'\"]+)['\"]\s+values?\s+is\s+([^\s,\.]+)\s+then\s+(visible|invisible|mandatory)",
            # "Make visible if 'X' is Y"
            r"make\s+(visible|invisible|mandatory)\s+if\s+['\"]?([^'\"]+)['\"]?\s+is\s+['\"]?([^'\"]+)['\"]?",
            # "visible and mandatory if X is Y"
            r"(visible|invisible)\s+and\s+(mandatory|non-?mandatory)\s+if\s+['\"]?([^'\"]+)['\"]?\s+is\s+['\"]?([^'\"]+)['\"]?",
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
                        action = groups[2].lower()
                    else:
                        action = groups[0].lower()
                        controlling = groups[1] if len(groups) > 1 else ''
                        value = groups[2] if len(groups) > 2 else 'Yes'

                    if controlling and target:
                        include_mandatory = 'mandatory' in action or (len(groups) > 3 and 'mandatory' in str(groups[3]).lower())
                        visibility_groups[controlling][(value,)].append({
                            'field_name': target,
                            'include_mandatory': include_mandatory,
                            'rule_description': logic_text,
                            'panel': panel_name
                        })

    def _generate_visibility_rules_from_groups(self, visibility_groups: Dict):
        """Generate visibility rules from grouped references."""
        for controlling_name, value_groups in visibility_groups.items():
            controlling_field = self.match_field(controlling_name)
            if not controlling_field:
                continue

            for values_key, destinations in value_groups.items():
                # Parse values from key
                if isinstance(values_key, tuple):
                    values = list(values_key)
                else:
                    values = values_key.split(',') if values_key else ['Yes']

                # Normalize values
                values = [v.strip() for v in values if v.strip()]
                if not values:
                    values = ['Yes']

                dest_ids = []
                include_mandatory = False

                for dest in destinations:
                    field_name = dest.get('field_name', '')
                    if not field_name:
                        continue
                    field = self.match_field(field_name, dest.get('panel'))
                    if field and field.id not in dest_ids:
                        dest_ids.append(field.id)
                    if dest.get('include_mandatory'):
                        include_mandatory = True

                if not dest_ids:
                    continue

                # Create a unique key to avoid duplicates
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

                # Generate MAKE_INVISIBLE rule (NOT_IN)
                invisible_rule = self._create_rule(
                    action_type='MAKE_INVISIBLE',
                    source_ids=[controlling_field.id],
                    destination_ids=dest_ids,
                    conditional_values=values,
                    condition='NOT_IN'
                )
                self._add_rule(controlling_field.id, invisible_rule)

                if include_mandatory:
                    # Generate MAKE_MANDATORY rule
                    mandatory_rule = self._create_rule(
                        action_type='MAKE_MANDATORY',
                        source_ids=[controlling_field.id],
                        destination_ids=dest_ids,
                        conditional_values=values,
                        condition='IN'
                    )
                    self._add_rule(controlling_field.id, mandatory_rule)

                    # Generate MAKE_NON_MANDATORY rule
                    non_mandatory_rule = self._create_rule(
                        action_type='MAKE_NON_MANDATORY',
                        source_ids=[controlling_field.id],
                        destination_ids=dest_ids,
                        conditional_values=values,
                        condition='NOT_IN'
                    )
                    self._add_rule(controlling_field.id, non_mandatory_rule)

    def _extract_conditional_values(self, text: str) -> List[str]:
        """Extract conditional values from text."""
        values = []
        text = str(text)

        # Pattern: value is X
        for match in re.finditer(r"values?\s+is\s+['\"]?([^'\"\s,\.]+)['\"]?", text, re.I):
            values.append(match.group(1))

        # Pattern: selected as X
        for match in re.finditer(r"selected\s+as\s+['\"]?([^'\"\s,\.]+)['\"]?", text, re.I):
            values.append(match.group(1))

        # Pattern: "Yes" or "No"
        for match in re.finditer(r"['\"]?(Yes|No|TRUE|FALSE)['\"]?", text, re.I):
            values.append(match.group(1))

        # Pattern: chosen as X
        for match in re.finditer(r"chosen\s+as\s+['\"]?([^'\"\s,\.]+)['\"]?", text, re.I):
            values.append(match.group(1))

        return list(set(values)) if values else ['Yes']

    def _generate_ocr_rules(self):
        """Generate OCR rules for file upload fields."""
        for field in self.fields:
            if field.field_type != 'FILE':
                continue

            name_lower = field.name.lower()
            logic = (field.logic or '').lower()
            combined = name_lower + ' ' + logic

            # Check OCR patterns
            for pattern, (ocr_source, verify_dest_pattern) in self.OCR_FIELD_PATTERNS.items():
                if re.search(pattern, combined, re.I) and ocr_source not in self.ocr_rules:
                    # Find destination field
                    dest_ids = []
                    dest_field = None

                    if verify_dest_pattern:
                        dest_field = self.match_field(verify_dest_pattern, field.panel_name)

                        # Try alternative patterns
                        if not dest_field:
                            alt_name = re.sub(r'^upload\s+', '', field.name, flags=re.I)
                            dest_field = self.match_field(alt_name, field.panel_name)

                        if dest_field:
                            dest_ids = [dest_field.id]

                    # Create OCR rule
                    ocr_rule = self._create_rule(
                        action_type='OCR',
                        source_ids=[field.id],
                        destination_ids=dest_ids,
                        source_type=ocr_source,
                        processing_type='SERVER'
                    )
                    self._add_rule(field.id, ocr_rule)
                    self.ocr_rules[ocr_source] = ocr_rule
                    break

    def _generate_verify_rules(self):
        """Generate VERIFY rules for validation fields."""
        verify_patterns = [
            (r'perform\s+pan\s+validation|pan\s+validation|validate\s+pan', 'PAN_NUMBER', 'PAN'),
            (r'perform\s+gstin?\s+validation|gstin?\s+validation|validate\s+gstin?', 'GSTIN', 'GSTIN'),
            (r'bank\s+(?:account\s+)?validation|validate\s+bank|ifsc\s+validation', 'BANK_ACCOUNT_NUMBER', 'IFSC Code'),
            (r'msme\s+validation|validate\s+msme|udyam\s+validation', 'MSME_UDYAM_REG_NUMBER', 'MSME Registration Number'),
        ]

        for field in self.fields:
            logic = (field.logic or '').lower()

            # Skip if this is a destination field
            if 'data will come from' in logic or 'derived from' in logic:
                continue

            for pattern, verify_source, field_hint in verify_patterns:
                if re.search(pattern, logic) and verify_source not in self.verify_rules:
                    # Try to find the source field
                    source_field = field
                    if field_hint:
                        hint_field = self.match_field(field_hint, field.panel_name)
                        if hint_field:
                            source_field = hint_field

                    self._generate_verify_rule(source_field, verify_source)
                    break

        # Also ensure VERIFY rules for all OCR chains
        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if verify_source and ocr_source in self.ocr_rules and verify_source not in self.verify_rules:
                ocr_rule = self.ocr_rules[ocr_source]
                if ocr_rule.destination_ids:
                    dest_field = self.field_by_id.get(ocr_rule.destination_ids[0])
                    if dest_field:
                        self._generate_verify_rule(dest_field, verify_source)

    def _generate_verify_rule(self, source_field: FieldInfo, verify_source: str):
        """Generate a VERIFY rule with proper ordinal mapping."""
        if verify_source in self.verify_rules:
            return

        # Get destination mappings
        dest_ids = self._get_verify_destination_ids(source_field.name, verify_source, source_field.panel_name)

        # Create VERIFY rule
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

        # Generate GSTIN_WITH_PAN cross-validation if both PAN and GSTIN exist
        if verify_source == 'GSTIN':
            pan_field = self.match_field('PAN')
            if pan_field:
                self._generate_gstin_with_pan_rule(pan_field, source_field)

    def _get_verify_destination_ids(self, source_name: str, verify_source: str, panel: Optional[str] = None) -> List[int]:
        """Get destination IDs for VERIFY rule with ordinal mapping."""
        ordinals = self.VERIFY_ORDINALS.get(verify_source, {})
        if not ordinals:
            return []

        num_ordinals = max(ordinals.keys()) if ordinals else 0
        dest_ids = [-1] * num_ordinals

        # Find matching fields from intra-panel references
        source_lower = source_name.lower()

        if self.intra_panel_refs:
            for p in self.intra_panel_refs.get('panel_results', []):
                for ref in p.get('intra_panel_references', []):
                    if not isinstance(ref, dict):
                        continue

                    dep_name = self._safe_get_field_name(ref.get('dependent_field', ''))
                    if not dep_name:
                        continue

                    # Check references
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
                            source_lower in ref_name or
                            source_lower in dep_desc
                        )

                        if is_verify_dest:
                            field = self.match_field(dep_name, panel)
                            if field:
                                ordinal = self._match_field_to_ordinal(dep_name, ordinals)
                                if ordinal and 1 <= ordinal <= num_ordinals:
                                    dest_ids[ordinal - 1] = field.id

        return dest_ids

    def _match_field_to_ordinal(self, field_name: str, ordinals: Dict[int, str]) -> Optional[int]:
        """Match a field name to an ordinal position."""
        name_lower = field_name.lower()

        # Direct matching patterns
        mapping = {
            # PAN
            'pan holder name': 4, 'holder name': 4, 'pan type': 8,
            'pan status': 6, 'aadhaar pan list': 9, 'aadhaar seeding': 9,
            # GSTIN
            'trade name': 1, 'legal name': 2, 'longname': 2,
            'reg date': 3, 'registration date': 3, 'building number': 6,
            'building': 6, 'street': 10, 'city': 4,
            'district': 8, 'state': 9, 'pin code': 11, 'pincode': 11,
            # MSME
            'name of enterprise': 1, 'enterprise name': 1, 'major activity': 2,
            'social category': 3, 'date of commencement': 5, 'commencement': 5,
            'dic name': 6, 'dice name': 6, 'classification year': 17,
            'classification date': 18, 'applied state': 19, 'area': 13, 'address line': 10,
            # Bank
            'bank name': 1, 'beneficiary name': 1, 'ifsc': 2, 'account number': 4,
        }

        for pattern, ordinal in mapping.items():
            if pattern in name_lower:
                return ordinal

        # Try exact match with ordinal names
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
            params='{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}'
        )
        rule.on_status_fail = 'CONTINUE'
        rule.button = ''

        self._add_rule(gstin_field.id, rule)

    def _link_ocr_verify_chains(self):
        """Link OCR rules to VERIFY rules via postTriggerRuleIds - CRITICAL FIX."""
        linked_count = 0

        for ocr_source, verify_source in self.OCR_VERIFY_CHAINS.items():
            if not verify_source:
                continue

            ocr_rule = self.ocr_rules.get(ocr_source)
            verify_rule = self.verify_rules.get(verify_source)

            if ocr_rule and verify_rule:
                if verify_rule.id not in ocr_rule.post_trigger_rule_ids:
                    ocr_rule.post_trigger_rule_ids.append(verify_rule.id)
                    linked_count += 1
                    self.log(f"  Linked {ocr_source} OCR (rule {ocr_rule.id}) → {verify_source} VERIFY (rule {verify_rule.id})")

        self.log(f"  Total chains linked: {linked_count}")

    def _generate_ext_dropdown_rules(self):
        """Generate EXT_DROP_DOWN rules for external dropdown fields."""
        ext_types = ['EXTERNAL_DROP_DOWN_VALUE', 'MULTISELECT_EXTERNAL_DROPDOWN', 'EXTERNAL_DROPDOWN']

        for field in self.fields:
            if field.field_type not in ext_types:
                continue

            # Skip if this field should be EXT_VALUE instead
            if field.name.lower().strip() in self.EXT_VALUE_FIELDS:
                continue

            params = self._get_ext_dropdown_params(field)
            parent_id = self._find_parent_dropdown(field)

            rule = self._create_rule(
                action_type='EXT_DROP_DOWN',
                source_ids=[parent_id] if parent_id else [field.id],
                destination_ids=[field.id] if parent_id else [],
                source_type='FORM_FILL_DROP_DOWN',
                processing_type='SERVER',
                params=params
            )
            rule.searchable = True

            self._add_rule(field.id, rule)

    def _generate_ext_value_rules(self):
        """Generate EXT_VALUE rules for external data value fields."""
        for field in self.fields:
            name_lower = field.name.lower().strip()

            for pattern, config in self.EXT_VALUE_FIELDS.items():
                if pattern in name_lower or name_lower in pattern:
                    params = self._build_ext_value_params(field, config)

                    rule = self._create_rule(
                        action_type='EXT_VALUE',
                        source_ids=[field.id],
                        destination_ids=[],
                        source_type='EXTERNAL_DATA_VALUE',
                        processing_type='SERVER',
                        params=params
                    )

                    self._add_rule(field.id, rule)
                    break

    def _build_ext_value_params(self, field: FieldInfo, config: Dict) -> str:
        """Build params JSON for EXT_VALUE rule."""
        dd_type = config.get('ddType', '')
        params_obj = [{"conditionList": [{"ddType": [dd_type], "criterias": [], "da": ["a1"]}]}]
        return json.dumps(params_obj)

    def _get_ext_dropdown_params(self, field: FieldInfo) -> str:
        """Get params for EXT_DROP_DOWN rule."""
        name_lower = field.name.lower()

        mappings = {
            'company': 'COMPANY_CODE', 'country': 'COUNTRY', 'state': 'STATE',
            'district': 'DISTRICT', 'city': 'CITY', 'currency': 'CURRENCY',
            'payment': 'PAYMENT_TERMS', 'incoterms': 'INCOTERMS',
            'account group': 'ACCOUNT_GROUP', 'vendor type': 'VENDOR_TYPE',
            'process type': 'PROCESS_TYPE', 'corporate group': 'CORPORATE_GROUP',
            'group key': 'GROUP_KEY', 'purchasing': 'PURCHASING_ORG',
            'plant': 'PLANT', 'title': 'TITLE', 'category': 'CATEGORY',
            'msme': 'MSME', 'yes/no': 'YES_NO',
        }

        for pattern, param in mappings.items():
            if pattern in name_lower:
                return param
        return ''

    def _find_parent_dropdown(self, field: FieldInfo) -> Optional[int]:
        """Find parent field for cascading dropdown."""
        name_lower = field.name.lower()

        cascading = [
            ('state', 'country'),
            ('district', 'state'),
            ('city', 'state'),
        ]

        for child, parent in cascading:
            if child in name_lower:
                for f in self.fields:
                    if parent in f.name.lower() and f.field_type in [
                        'EXTERNAL_DROP_DOWN_VALUE', 'MULTISELECT_EXTERNAL_DROPDOWN'
                    ]:
                        return f.id
        return None

    def _generate_disabled_rules(self):
        """Generate MAKE_DISABLED rules for non-editable fields - IMPROVED."""
        disabled_fields = []

        for field in self.fields:
            logic = (field.logic or '').lower()

            # Check all disabled patterns
            for pattern in self.DISABLED_FIELD_PATTERNS:
                if re.search(pattern, logic, re.I):
                    disabled_fields.append(field.id)
                    break

        if disabled_fields:
            # Try to find a RuleCheck field for source
            rule_check_field = self.match_field('RuleCheck')
            source_id = rule_check_field.id if rule_check_field else disabled_fields[0]

            # Create consolidated MAKE_DISABLED rule
            rule = self._create_rule(
                action_type='MAKE_DISABLED',
                source_ids=[source_id],
                destination_ids=disabled_fields,
                conditional_values=['Disable'],
                condition='NOT_IN'
            )
            self._add_rule(source_id, rule)

    def _generate_convert_to_rules(self):
        """Generate CONVERT_TO rules for uppercase fields."""
        for field in self.fields:
            logic = (field.logic or '').lower()
            if 'upper case' in logic or 'uppercase' in logic:
                rule = self._create_rule(
                    action_type='CONVERT_TO',
                    source_ids=[field.id],
                    destination_ids=[],
                    source_type='UPPER_CASE'
                )
                self._add_rule(field.id, rule)

    def _consolidate_rules(self):
        """Consolidate and deduplicate rules."""
        groupable = ['MAKE_DISABLED', 'MAKE_VISIBLE', 'MAKE_INVISIBLE',
                     'MAKE_MANDATORY', 'MAKE_NON_MANDATORY']

        groups: Dict[tuple, List[GeneratedRule]] = defaultdict(list)
        non_groupable: List[GeneratedRule] = []

        for rule in self.all_rules:
            if rule.action_type in groupable:
                key = (
                    rule.action_type,
                    tuple(sorted(rule.source_ids)),
                    rule.condition or '',
                    tuple(sorted(rule.conditional_values))
                )
                groups[key].append(rule)
            else:
                non_groupable.append(rule)

        # Merge grouped rules
        consolidated = []
        for key, rules in groups.items():
            if len(rules) == 1:
                consolidated.append(rules[0])
            else:
                merged = rules[0]
                all_dests = set()
                for r in rules:
                    all_dests.update(r.destination_ids)
                merged.destination_ids = sorted(list(all_dests))
                consolidated.append(merged)

        # Deduplicate non-groupable
        seen = {}
        for rule in non_groupable:
            key = (
                rule.action_type,
                rule.source_type or '',
                tuple(sorted(rule.source_ids))
            )
            if key not in seen:
                seen[key] = rule
            elif len(rule.destination_ids) > len(seen[key].destination_ids):
                seen[key] = rule

        consolidated.extend(seen.values())

        # Remove exact duplicates
        final = []
        final_keys = set()
        for rule in consolidated:
            key = (
                rule.action_type,
                rule.source_type or '',
                tuple(sorted(rule.source_ids)),
                tuple(sorted(rule.destination_ids)),
                rule.condition or '',
                tuple(sorted(rule.conditional_values))
            )
            if key not in final_keys:
                final_keys.add(key)
                final.append(rule)

        self.all_rules = final

    def _rebuild_rules_by_field(self):
        """Rebuild rules_by_field mapping after consolidation."""
        self.rules_by_field = defaultdict(list)
        for rule in self.all_rules:
            for source_id in rule.source_ids:
                self.rules_by_field[source_id].append(rule)

    def _create_rule(
        self,
        action_type: str,
        source_ids: List[int],
        destination_ids: Optional[List[int]] = None,
        source_type: Optional[str] = None,
        conditional_values: Optional[List[str]] = None,
        condition: Optional[str] = None,
        processing_type: str = 'CLIENT',
        params: Optional[str] = None,
        button: str = ''
    ) -> GeneratedRule:
        """Create a new rule."""
        return GeneratedRule(
            id=self.id_generator.next_id('rule'),
            action_type=action_type,
            source_ids=source_ids,
            destination_ids=destination_ids or [],
            source_type=source_type,
            conditional_values=conditional_values or [],
            condition=condition,
            processing_type=processing_type,
            params=params,
            button=button
        )

    def _add_rule(self, field_id: int, rule: GeneratedRule):
        """Add a rule to the collections."""
        self.all_rules.append(rule)
        self.rules_by_field[field_id].append(rule)

    def _populate_schema(self) -> Dict:
        """Populate schema with generated rules."""
        schema = copy.deepcopy(self.schema)

        doc_types = schema.get('template', {}).get('documentTypes', [])
        for doc_type in doc_types:
            metadatas = doc_type.get('formFillMetadatas', [])
            for meta in metadatas:
                field_id = meta.get('id')
                if field_id in self.rules_by_field:
                    rules = self.rules_by_field[field_id]
                    meta['formFillRules'] = [r.to_dict() for r in rules]

        return schema

    def save_output(self, output_path: str, report_path: Optional[str] = None):
        """Save the populated schema and report."""
        populated = self.process()
        self._save_json(populated, output_path)

        if report_path:
            report = self._create_report()
            self._save_json(report, report_path)

        return populated

    def _create_report(self) -> Dict:
        """Create extraction report."""
        rules_by_type = defaultdict(int)
        for rule in self.all_rules:
            rules_by_type[rule.action_type] += 1

        return {
            'extraction_timestamp': datetime.now().isoformat(),
            'version': 'v4',
            'input_schema': self.schema_path,
            'intra_panel_refs': self.intra_panel_path,
            'summary': {
                'total_fields': len(self.fields),
                'total_rules': len(self.all_rules),
                'rules_by_type': dict(rules_by_type),
                'fields_with_rules': len(self.rules_by_field),
            },
            'ocr_chains': {
                source: {
                    'rule_id': rule.id,
                    'destination_ids': rule.destination_ids,
                    'post_trigger': rule.post_trigger_rule_ids,
                    'chained': len(rule.post_trigger_rule_ids) > 0
                }
                for source, rule in self.ocr_rules.items()
            },
            'verify_rules': {
                source: {
                    'rule_id': rule.id,
                    'destination_ids': rule.destination_ids,
                    'dest_count': sum(1 for d in rule.destination_ids if d != -1)
                }
                for source, rule in self.verify_rules.items()
            }
        }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Enhanced Rule Extraction Agent v4')
    parser.add_argument('--schema', required=True, help='Path to schema JSON')
    parser.add_argument('--intra-panel', help='Path to intra-panel references JSON')
    parser.add_argument('--output', required=True, help='Output path for populated schema')
    parser.add_argument('--report', help='Output path for extraction report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    agent = EnhancedRuleExtractionAgentV4(
        schema_path=args.schema,
        intra_panel_path=args.intra_panel,
        verbose=args.verbose
    )

    populated = agent.save_output(args.output, args.report)

    print(f"Saved populated schema to: {args.output}")
    if args.report:
        print(f"Saved report to: {args.report}")
    print(f"Total rules generated: {len(agent.all_rules)}")


if __name__ == '__main__':
    main()
