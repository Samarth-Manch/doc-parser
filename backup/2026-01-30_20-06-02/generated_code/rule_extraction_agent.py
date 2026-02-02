#!/usr/bin/env python3
"""
Rule Extraction Agent - Complete implementation.

Extracts rules from BUD document and populates formFillRules in schema JSON.
Uses real field IDs from reference schema for accurate rule generation.

Usage:
    python rule_extraction_agent.py \
        --bud "documents/Vendor Creation Sample BUD.docx" \
        --reference "documents/json_output/vendor_creation_sample_bud.json" \
        --output "adws/2026-01-30_20-06-02/populated_schema.json"
"""

import argparse
import json
import logging
import sys
import re
import copy
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Set
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add paths for imports
_script_dir = Path(__file__).parent.resolve()
_project_root = _script_dir.parent.parent.parent
sys.path.insert(0, str(_project_root))

from doc_parser import DocumentParser
from doc_parser.models import FieldDefinition


# ==============================================================================
# Data Models
# ==============================================================================

@dataclass
class FieldInfo:
    """Field information extracted from schema."""
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
class GeneratedRule:
    """Generated formFillRule."""
    id: int
    create_user: str = "FIRST_PARTY"
    update_user: str = "FIRST_PARTY"
    action_type: str = ""
    source_type: str = ""
    processing_type: str = "CLIENT"
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    condition: str = ""
    condition_value_type: str = ""
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    params: str = ""
    on_status_fail: str = ""
    button: str = ""
    searchable: bool = False
    execute_on_fill: bool = True
    execute_on_read: bool = False
    execute_on_esign: bool = False
    execute_post_esign: bool = False
    run_post_condition_fail: bool = False
    conditional_value_id: int = None

    def to_dict(self) -> Dict:
        """Convert to JSON-compatible dictionary."""
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
        if self.conditional_value_id is not None:
            result["conditionalValueId"] = self.conditional_value_id

        return result


# ==============================================================================
# Rule ID Generator
# ==============================================================================

_rule_id_counter = 200000

def get_rule_id() -> int:
    """Get next unique rule ID."""
    global _rule_id_counter
    _rule_id_counter += 1
    return _rule_id_counter

def reset_rule_ids(start: int = 200000):
    """Reset rule ID counter."""
    global _rule_id_counter
    _rule_id_counter = start


# ==============================================================================
# Field Matcher
# ==============================================================================

class FieldMatcher:
    """Match field name references to field IDs."""

    def __init__(self, fields: List[FieldInfo]):
        self.fields = fields
        self._exact_index: Dict[str, FieldInfo] = {}
        self._normalized_index: Dict[str, FieldInfo] = {}
        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes."""
        for field in self.fields:
            self._exact_index[field.name] = field
            self._exact_index[field.name.lower()] = field
            normalized = self._normalize_name(field.name)
            self._normalized_index[normalized] = field

    def _normalize_name(self, name: str) -> str:
        """Normalize field name."""
        if not name:
            return ""
        normalized = name.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def match_field(self, name: str) -> Optional[FieldInfo]:
        """Find field by name."""
        if not name:
            return None

        # Exact match
        if name in self._exact_index:
            return self._exact_index[name]
        if name.lower() in self._exact_index:
            return self._exact_index[name.lower()]

        # Normalized match
        normalized = self._normalize_name(name)
        if normalized in self._normalized_index:
            return self._normalized_index[normalized]

        # Fuzzy match
        best_match = None
        best_score = 0.0
        for field in self.fields:
            score = SequenceMatcher(None, normalized, self._normalize_name(field.name)).ratio()
            if score > best_score and score >= 0.7:
                best_score = score
                best_match = field

        return best_match

    def find_by_partial_name(self, partial: str) -> List[FieldInfo]:
        """Find fields containing partial name."""
        partial_lower = partial.lower()
        return [f for f in self.fields if partial_lower in f.name.lower()]

    def find_by_type(self, field_type: str) -> List[FieldInfo]:
        """Find fields by type."""
        return [f for f in self.fields if f.field_type.upper() == field_type.upper()]

    def find_nearby(self, field_id: int, count: int = 20) -> List[FieldInfo]:
        """Find nearby fields by form order."""
        ref_idx = None
        for i, f in enumerate(self.fields):
            if f.id == field_id:
                ref_idx = i
                break
        if ref_idx is None:
            return []

        start = max(0, ref_idx - count // 2)
        end = min(len(self.fields), ref_idx + count // 2)
        return self.fields[start:end]


# ==============================================================================
# Schema Lookup
# ==============================================================================

class RuleSchemaLookup:
    """Query interface for Rule-Schemas.json."""

    SCHEMA_IDS = {
        # OCR
        "PAN_IMAGE": 344,
        "GSTIN_IMAGE": 347,
        "CHEQUEE": 269,
        "MSME": 214,
        "CIN": 357,
        "AADHAR_IMAGE": 359,
        "AADHAR_BACK_IMAGE": 348,
        # VERIFY
        "PAN_NUMBER": 360,
        "GSTIN": 355,
        "BANK_ACCOUNT_NUMBER": 361,
        "MSME_UDYAM_REG_NUMBER": 337,
        "CIN_ID": 349,
    }

    OCR_VERIFY_CHAINS = {
        "PAN_IMAGE": "PAN_NUMBER",
        "GSTIN_IMAGE": "GSTIN",
        "CHEQUEE": "BANK_ACCOUNT_NUMBER",
        "MSME": "MSME_UDYAM_REG_NUMBER",
        "CIN": "CIN_ID",
    }

    def __init__(self, path: str = None):
        if path is None:
            path = str(_project_root / "rules" / "Rule-Schemas.json")

        with open(path) as f:
            data = json.load(f)

        self.schemas = data.get('content', [])
        self.by_id = {s['id']: s for s in self.schemas}

    def get_destination_count(self, source_type: str) -> int:
        """Get number of destination fields for a source type."""
        schema_id = self.SCHEMA_IDS.get(source_type)
        if schema_id and schema_id in self.by_id:
            return self.by_id[schema_id].get('destinationFields', {}).get('numberOfItems', 0)
        return 0

    def get_destination_fields(self, source_type: str) -> List[Dict]:
        """Get destination field info for a source type."""
        schema_id = self.SCHEMA_IDS.get(source_type)
        if schema_id and schema_id in self.by_id:
            return self.by_id[schema_id].get('destinationFields', {}).get('fields', [])
        return []

    def build_destination_ids(self, source_type: str, field_mappings: Dict[str, int]) -> List[int]:
        """Build destinationIds array with -1 for unmapped ordinals."""
        schema_id = self.SCHEMA_IDS.get(source_type)
        if not schema_id or schema_id not in self.by_id:
            return list(field_mappings.values()) if field_mappings else []

        schema = self.by_id[schema_id]
        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        # Build name -> ordinal mapping
        name_to_ordinal = {f['name'].lower(): f['ordinal'] for f in dest_fields}

        # Initialize with -1
        destination_ids = [-1] * num_items

        # Fill in mapped values
        for name, field_id in field_mappings.items():
            ordinal = name_to_ordinal.get(name.lower())
            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id

        return destination_ids


# ==============================================================================
# Rule Extraction Agent
# ==============================================================================

class RuleExtractionAgent:
    """
    Main agent for extracting rules from BUD documents.

    Uses reference JSON for field ID mapping to ensure accuracy.
    """

    def __init__(
        self,
        bud_path: str,
        reference_path: str,
        intra_panel_path: str = None,
        verbose: bool = False
    ):
        self.bud_path = bud_path
        self.reference_path = reference_path
        self.intra_panel_path = intra_panel_path
        self.verbose = verbose

        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Components
        self.doc_parser = DocumentParser()
        self.schema_lookup = RuleSchemaLookup()

        # Data
        self.parsed_doc = None
        self.reference_data = None
        self.fields: List[FieldInfo] = []
        self.field_matcher: FieldMatcher = None
        self.field_by_id: Dict[int, FieldInfo] = {}
        self.field_by_name: Dict[str, FieldInfo] = {}

        # Rules
        self.all_rules: List[GeneratedRule] = []
        self.rules_by_field_id: Dict[int, List[GeneratedRule]] = defaultdict(list)

        # Special fields
        self.rulecheck_field_id: Optional[int] = None

    def extract(self) -> Dict[str, Any]:
        """Extract rules from BUD document."""
        logger.info(f"Loading reference schema from {self.reference_path}")
        self._load_reference_schema()

        logger.info(f"Parsing BUD document: {self.bud_path}")
        self._parse_bud_document()

        logger.info(f"Building field index from {len(self.fields)} fields")
        self._build_field_index()

        # Load intra-panel references
        intra_refs = None
        if self.intra_panel_path and Path(self.intra_panel_path).exists():
            with open(self.intra_panel_path) as f:
                intra_refs = json.load(f)

        # Reset rule IDs
        reset_rule_ids(200000)

        # Extract rules in phases
        logger.info("Phase 1: Extracting OCR rules")
        self._extract_ocr_rules()

        logger.info("Phase 2: Extracting VERIFY rules")
        self._extract_verify_rules()

        logger.info("Phase 3: Linking OCR -> VERIFY chains")
        self._link_ocr_verify_chains()

        logger.info("Phase 4: Extracting visibility rules")
        self._extract_visibility_rules(intra_refs)

        logger.info("Phase 5: Extracting mandatory rules")
        self._extract_mandatory_rules(intra_refs)

        logger.info("Phase 6: Extracting MAKE_DISABLED rules")
        self._extract_disabled_rules()

        logger.info("Phase 7: Extracting EXT_DROP_DOWN rules")
        self._extract_ext_dropdown_rules(intra_refs)

        logger.info("Phase 8: Extracting VALIDATION rules")
        self._extract_validation_rules()

        logger.info("Phase 9: Extracting other rules")
        self._extract_other_rules()

        # Build output
        return self._build_output()

    def _load_reference_schema(self):
        """Load reference schema for field IDs."""
        with open(self.reference_path) as f:
            self.reference_data = json.load(f)

        # Extract fields from formFillMetadatas
        doc_types = self.reference_data.get('template', {}).get('documentTypes', [])
        for doc_type in doc_types:
            metadatas = doc_type.get('formFillMetadatas', [])
            for meta in metadatas:
                form_tag = meta.get('formTag', {})
                field = FieldInfo(
                    id=meta.get('id', 0),
                    name=form_tag.get('name', ''),
                    variable_name=meta.get('variableName', ''),
                    field_type=form_tag.get('type', 'TEXT'),
                    is_mandatory=meta.get('mandatory', False),
                    form_order=meta.get('formOrder', 0.0),
                )
                self.fields.append(field)

        logger.info(f"Loaded {len(self.fields)} fields from reference schema")

    def _parse_bud_document(self):
        """Parse BUD document to extract field logic."""
        self.parsed_doc = self.doc_parser.parse(self.bud_path)

        # Map BUD fields to reference fields by name
        bud_field_logic = {}
        for f in self.parsed_doc.all_fields:
            bud_field_logic[f.name.lower()] = {
                'logic': getattr(f, 'logic', ''),
                'rules': getattr(f, 'rules', ''),
                'field_type': str(f.field_type.value) if hasattr(f.field_type, 'value') else str(f.field_type),
            }

        # Attach logic to reference fields
        for field in self.fields:
            bud_info = bud_field_logic.get(field.name.lower())
            if bud_info:
                field.logic = bud_info['logic']
                field.rules = bud_info['rules']

    def _build_field_index(self):
        """Build field lookup indexes."""
        self.field_by_id = {f.id: f for f in self.fields}
        self.field_by_name = {f.name.lower(): f for f in self.fields}
        self.field_matcher = FieldMatcher(self.fields)

        # Find RuleCheck field
        for f in self.fields:
            if 'rulecheck' in f.name.lower():
                self.rulecheck_field_id = f.id
                logger.debug(f"Found RuleCheck field: {f.name} (ID: {f.id})")
                break

    # --------------------------------------------------------------------------
    # OCR Rules
    # --------------------------------------------------------------------------

    OCR_PATTERNS = {
        # Pattern -> (source_type, destination_name_pattern)
        r"upload\s*pan|pan\s*image": ("PAN_IMAGE", "pan"),
        r"gstin\s*image|upload\s*gstin": ("GSTIN_IMAGE", "gstin"),
        r"cancel.*cheque|cheque\s*image": ("CHEQUEE", "ifsc"),
        r"aadhaar?\s*back|back\s*aadhaar?": ("AADHAR_BACK_IMAGE", "street"),
        r"aadhaar?\s*front|front\s*aadhaar?": ("AADHAR_IMAGE", "aadhaar"),
        r"msme\s*image|upload\s*msme": ("MSME", "msme registration"),
        r"cin\s*image|upload\s*cin": ("CIN", "cin"),
    }

    def _extract_ocr_rules(self):
        """Extract OCR rules from file upload fields."""
        for field in self.fields:
            if field.field_type.upper() != 'FILE':
                continue

            name_lower = field.name.lower()
            logic_lower = (field.logic or '').lower()
            combined = f"{name_lower} {logic_lower}"

            # Check if this is an OCR source
            for pattern, (source_type, dest_pattern) in self.OCR_PATTERNS.items():
                if re.search(pattern, combined):
                    # Find destination field
                    dest_field = self._find_ocr_destination(field, source_type, dest_pattern)
                    if dest_field:
                        rule = self._build_ocr_rule(source_type, field.id, dest_field.id)
                        self.all_rules.append(rule)
                        self.rules_by_field_id[field.id].append(rule)
                        logger.debug(f"OCR: {field.name} ({source_type}) -> {dest_field.name}")
                    break

    def _find_ocr_destination(self, upload_field: FieldInfo, source_type: str, dest_pattern: str) -> Optional[FieldInfo]:
        """Find the text field that OCR will populate."""
        # For CHEQUEE, need special handling
        if source_type == "CHEQUEE":
            # Find IFSC Code field
            for f in self.fields:
                if 'ifsc' in f.name.lower() and f.field_type.upper() in ['TEXT', 'NUMBER', 'MASKED_FIELD']:
                    return f
            return None

        # For AADHAR_BACK_IMAGE, find Pin Code field
        if source_type == "AADHAR_BACK_IMAGE":
            for f in self.fields:
                if 'postal code' in f.name.lower() or 'pin code' in f.name.lower():
                    return f
            return None

        # Standard pattern: find nearby text field matching pattern
        nearby = self.field_matcher.find_nearby(upload_field.id, count=10)
        for f in nearby:
            if f.id == upload_field.id:
                continue
            if f.field_type.upper() in ['TEXT', 'NUMBER', 'MASKED_FIELD']:
                if dest_pattern in f.name.lower():
                    return f

        # Fallback: find any field matching pattern
        for f in self.fields:
            if f.field_type.upper() in ['TEXT', 'NUMBER', 'MASKED_FIELD']:
                if dest_pattern in f.name.lower():
                    return f

        return None

    def _build_ocr_rule(self, source_type: str, upload_id: int, dest_id: int) -> GeneratedRule:
        """Build OCR rule."""
        # For CHEQUEE, build ordinal-mapped destinations
        if source_type == "CHEQUEE":
            # CHEQUEE schema: ordinal 2 = ifscCode, ordinal 4 = accountNumber
            ifsc_field = self.field_by_id.get(dest_id)
            account_field = None
            for f in self.fields:
                if 'account' in f.name.lower() and 'number' in f.name.lower():
                    account_field = f
                    break

            dest_ids = [-1, -1, -1, -1]
            if ifsc_field:
                dest_ids[1] = ifsc_field.id  # ordinal 2
            if account_field:
                dest_ids[3] = account_field.id  # ordinal 4
        elif source_type == "AADHAR_BACK_IMAGE":
            # Build ordinal mapping for address fields
            dest_ids = self._build_aadhaar_back_destinations()
        else:
            dest_ids = [dest_id]

        return GeneratedRule(
            id=get_rule_id(),
            action_type="OCR",
            source_type=source_type,
            processing_type="SERVER",
            source_ids=[upload_id],
            destination_ids=dest_ids,
            execute_on_fill=True,
        )

    def _build_aadhaar_back_destinations(self) -> List[int]:
        """Build AADHAR_BACK_IMAGE destination IDs."""
        # Schema ordinals: 1-aadharAddress1, 2-aadharAddress2, 3-aadharPin, 4-aadharCity,
        # 5-aadharDist, 6-aadharState, 7-aadharFatherName, 8-aadharCountry, 9-aadharCoords
        dest_ids = [-1] * 8

        field_mapping = {
            2: ['postal code', 'pin code'],  # ordinal 3
            3: ['city'],  # ordinal 4
            4: ['district'],  # ordinal 5
            5: ['state'],  # ordinal 6
        }

        for ordinal_idx, patterns in field_mapping.items():
            for f in self.fields:
                name_lower = f.name.lower()
                for pattern in patterns:
                    if pattern in name_lower and f.field_type.upper() == 'TEXT':
                        dest_ids[ordinal_idx] = f.id
                        break
                if dest_ids[ordinal_idx] != -1:
                    break

        return dest_ids

    # --------------------------------------------------------------------------
    # VERIFY Rules - Only on SOURCE fields, not destinations!
    # --------------------------------------------------------------------------

    # Fields that trigger validation (SOURCE fields) - exact name match
    VERIFY_SOURCE_FIELDS = {
        "PAN": "PAN_NUMBER",
        "GSTIN": "GSTIN",
        "MSME Registration Number": "MSME_UDYAM_REG_NUMBER",
        "Bank Account Number": "BANK_ACCOUNT_NUMBER",
        "CIN": "CIN_ID",
    }

    # Pattern in logic indicating this is a SOURCE of validation
    VERIFY_SOURCE_PATTERNS = [
        r"perform\s+\w+\s+validation",
        r"validate\s+and\s+store",
        r"validation\s+and\s+store",
    ]

    def _extract_verify_rules(self):
        """Extract VERIFY rules - ONLY on source fields, not destinations."""
        # Track which verify types we've already created
        created_verify_types = set()

        # First pass: Find specific source fields by name
        for field in self.fields:
            field_name = field.name.strip()
            logic = field.logic or ''
            logic_lower = logic.lower()

            # Check if this is a known verify source field (exact match)
            source_type = self.VERIFY_SOURCE_FIELDS.get(field_name)

            # Also check by logic pattern - must explicitly mention "perform validation"
            if not source_type:
                is_source = any(re.search(p, logic_lower) for p in self.VERIFY_SOURCE_PATTERNS)
                if is_source:
                    # Determine source type from field name/logic
                    if field_name.lower() == 'pan':
                        source_type = "PAN_NUMBER"
                    elif field_name.lower() == 'gstin':
                        source_type = "GSTIN"
                    elif 'msme registration' in field_name.lower():
                        source_type = "MSME_UDYAM_REG_NUMBER"
                    elif field_name.lower() == 'cin':
                        source_type = "CIN_ID"

            if source_type and source_type not in created_verify_types:
                rule = self._build_verify_rule(source_type, field)
                if rule:
                    self.all_rules.append(rule)
                    self.rules_by_field_id[field.id].append(rule)
                    created_verify_types.add(source_type)
                    logger.debug(f"VERIFY: {field.name} ({source_type})")

                    # Add GSTIN_WITH_PAN cross-validation after GSTIN verify
                    if source_type == "GSTIN":
                        self._add_gstin_with_pan_rule(field)

        # Ensure we have BANK_ACCOUNT_NUMBER verify if not found by pattern
        if "BANK_ACCOUNT_NUMBER" not in created_verify_types:
            ifsc_field = self.field_matcher.match_field("IFSC Code")
            account_field = self.field_matcher.match_field("Bank Account Number")
            if ifsc_field and account_field:
                rule = self._build_bank_verify_rule(ifsc_field, account_field)
                if rule:
                    self.all_rules.append(rule)
                    self.rules_by_field_id[account_field.id].append(rule)
                    created_verify_types.add("BANK_ACCOUNT_NUMBER")
                    logger.debug(f"VERIFY: Bank Account (BANK_ACCOUNT_NUMBER)")

    def _build_verify_rule(self, source_type: str, source_field: FieldInfo) -> Optional[GeneratedRule]:
        """Build VERIFY rule with proper destination mapping."""
        # Skip if this is BANK_ACCOUNT_NUMBER - handled separately
        if source_type == "BANK_ACCOUNT_NUMBER":
            return None  # Handled by _build_bank_verify_rule

        # Find destination fields based on logic patterns
        dest_mappings = self._find_verify_destinations(source_type, source_field)
        dest_ids = self.schema_lookup.build_destination_ids(source_type, dest_mappings)

        return GeneratedRule(
            id=get_rule_id(),
            action_type="VERIFY",
            source_type=source_type,
            processing_type="SERVER",
            source_ids=[source_field.id],
            destination_ids=dest_ids,
            button="VERIFY" if source_type != "GSTIN" else "Verify",
            execute_on_fill=True,
        )

    def _build_bank_verify_rule(self, ifsc_field: FieldInfo, account_field: FieldInfo) -> Optional[GeneratedRule]:
        """Build Bank Account VERIFY rule (requires IFSC + Account Number)."""
        # Find Name of Account Holder for destination
        holder_field = None
        for f in self.fields:
            if 'name of account holder' in f.name.lower():
                holder_field = f
                break

        return GeneratedRule(
            id=get_rule_id(),
            action_type="VERIFY",
            source_type="BANK_ACCOUNT_NUMBER",
            processing_type="SERVER",
            source_ids=[ifsc_field.id, account_field.id],
            destination_ids=[holder_field.id] if holder_field else [],
            button="VERIFY",
            execute_on_fill=True,
        )

    def _find_verify_destinations(self, source_type: str, source_field: FieldInfo) -> Dict[str, int]:
        """Find destination fields for VERIFY rule."""
        mappings = {}

        # Get schema destination field names
        dest_fields = self.schema_lookup.get_destination_fields(source_type)
        dest_names = [f['name'].lower() for f in dest_fields]

        # Find nearby fields that might be destinations
        for f in self.fields:
            if f.id == source_field.id:
                continue

            logic = f.logic or ''

            # Check if this field receives data from validation
            if 'data will come from' in logic.lower():
                # Try to match to schema destination names
                name_lower = f.name.lower()
                for schema_name in dest_names:
                    # Fuzzy match
                    if SequenceMatcher(None, name_lower, schema_name).ratio() > 0.5:
                        # Find the original case name
                        orig_name = next((d['name'] for d in dest_fields if d['name'].lower() == schema_name), schema_name)
                        mappings[orig_name] = f.id
                        break

        return mappings

    def _add_gstin_with_pan_rule(self, gstin_field: FieldInfo):
        """Add GSTIN_WITH_PAN cross-validation rule."""
        pan_field = self.field_matcher.match_field("PAN")
        if not pan_field:
            return

        rule = GeneratedRule(
            id=get_rule_id(),
            action_type="VERIFY",
            source_type="GSTIN_WITH_PAN",
            processing_type="SERVER",
            source_ids=[pan_field.id, gstin_field.id],
            destination_ids=[],
            params='{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}',
            on_status_fail="CONTINUE",
            execute_on_fill=True,
        )
        self.all_rules.append(rule)
        logger.debug("VERIFY: GSTIN_WITH_PAN cross-validation")

    # --------------------------------------------------------------------------
    # Link OCR -> VERIFY Chains
    # --------------------------------------------------------------------------

    def _link_ocr_verify_chains(self):
        """Link OCR rules to VERIFY rules via postTriggerRuleIds."""
        # Build VERIFY rules index by source field
        verify_by_source = {}
        for rule in self.all_rules:
            if rule.action_type == "VERIFY":
                for src_id in rule.source_ids:
                    verify_by_source[src_id] = rule

        # Link OCR -> VERIFY
        for rule in self.all_rules:
            if rule.action_type != "OCR":
                continue

            # OCR destination is the field that gets populated
            # This field should be the source for VERIFY
            for dest_id in rule.destination_ids:
                if dest_id == -1:
                    continue
                if dest_id in verify_by_source:
                    verify_rule = verify_by_source[dest_id]
                    if verify_rule.id not in rule.post_trigger_rule_ids:
                        rule.post_trigger_rule_ids.append(verify_rule.id)
                        logger.debug(f"Linked OCR {rule.id} -> VERIFY {verify_rule.id}")

    # --------------------------------------------------------------------------
    # Visibility Rules - Improved pattern matching
    # --------------------------------------------------------------------------

    # Multiple patterns for extracting controlling field and value
    VISIBILITY_PATTERNS = [
        # "if the field 'X' values is Y then visible"
        (r'if.*field\s*["\'](.+?)["\']\s*values?\s+is\s+(\w+)\s+then\s+(visible|invisible)', 'fva'),
        # "Make visible if 'X' is Yes"
        (r'make\s+(visible|invisible)\s+(?:and\s+\w+\s+)?if\s*["\'](.+?)["\']\s+is\s+(\w+)', 'avf'),
        # "If the field 'X' value is Yes then it is visible"
        (r'if.*field\s*["\'](.+?)["\']\s*value\s+is\s+(\w+)\s+then\s+it\s+is\s+(visible|mandatory)', 'fva'),
        # "visible and mandatory if 'X' is Yes"
        (r'(visible|invisible).*if\s*["\'](.+?)["\']\s+is\s+(\w+)', 'afv'),
        # "If X is selected then visible" (without field keyword)
        (r'if\s+["\']?(.+?)["\']?\s+is\s+(?:selected\s+)?(?:as\s+)?["\']?(\w+)["\']?\s+then\s+(visible|invisible|mandatory)', 'fva'),
        # "Show this fields if X is Y"
        (r'show\s+(?:this|the)?\s*fields?\s+if\s+["\']?(.+?)["\']?\s+is\s+["\']?(\w+)["\']?', 'fvshow'),
    ]

    # GST option values - when BUD says "yes" for GST option, it can mean these values
    GST_OPTION_VALUES = {
        'registered': ['GST Registered'],
        'sez': ['SEZ'],
        'compounding': ['Compounding'],
        'non-registered': ['GST Non-Registered'],
        'yes': ['GST Registered', 'SEZ', 'Compounding'],  # "yes" means any registered type
    }

    # Controlling fields that need special value mapping
    SPECIAL_VALUE_MAPPINGS = {
        'please select gst option': {
            'yes': ['GST Registered', 'SEZ', 'Compounding'],
            'no': ['GST Non-Registered'],
        },
        'choose the group of company': {
            'pil': ['PIL', 'Domestic Subsidaries'],
            'domestic': ['PIL', 'Domestic Subsidaries'],
            'international': ['International Subsidaries'],
        },
    }

    def _extract_visibility_rules(self, intra_refs: Dict = None):
        """Extract MAKE_VISIBLE and MAKE_INVISIBLE rules."""
        # Group visibility relationships by (controlling field, conditional value)
        # This allows different rules for different values of the same controlling field
        visibility_groups: Dict[str, Dict] = defaultdict(lambda: {
            'visible_fields': [],
            'invisible_fields': [],
            'mandatory_fields': [],
            'non_mandatory_fields': [],
            'original_value': None,
        })

        for field in self.fields:
            logic = field.logic or ''
            logic_lower = logic.lower()

            if 'visible' not in logic_lower and 'invisible' not in logic_lower:
                continue

            # Try multiple patterns
            matched = False
            for pattern, order in self.VISIBILITY_PATTERNS:
                match = re.search(pattern, logic, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if order == 'fva':  # field, value, action
                        controlling_name, value, action = groups[0], groups[1], groups[2]
                    elif order == 'avf':  # action, value, field
                        action, controlling_name, value = groups[0], groups[1], groups[2]
                    elif order == 'afv':  # action, field, value
                        action, controlling_name, value = groups[0], groups[1], groups[2]
                    elif order == 'fvshow':  # field, value, show -> visible
                        controlling_name, value = groups[0], groups[1]
                        action = 'visible'
                    else:
                        continue

                    ctrl_key = controlling_name.lower().strip()
                    value_lower = value.lower()

                    # Check for special value mappings
                    mapped_values = [value.capitalize()]
                    if ctrl_key in self.SPECIAL_VALUE_MAPPINGS:
                        for pattern_key, mapped in self.SPECIAL_VALUE_MAPPINGS[ctrl_key].items():
                            if pattern_key in value_lower:
                                mapped_values = mapped
                                break

                    # Create a key for this controlling field + values combination
                    group_key = f"{ctrl_key}|{','.join(sorted(mapped_values))}"
                    visibility_groups[group_key]['original_value'] = mapped_values
                    visibility_groups[group_key]['ctrl_name'] = ctrl_key

                    if action.lower() == 'visible':
                        visibility_groups[group_key]['visible_fields'].append(field.id)
                        # Also handle "otherwise invisible" case
                        if 'otherwise invisible' in logic_lower or 'otherwise non-mandatory' in logic_lower:
                            visibility_groups[group_key]['needs_opposite'] = True
                    elif action.lower() == 'invisible':
                        visibility_groups[group_key]['invisible_fields'].append(field.id)

                    matched = True
                    break

            # Handle "not visible" pattern for fields that should be in global INVISIBLE rule
            if not matched and 'not visible' in logic_lower:
                if self.rulecheck_field_id:
                    group_key = "rulecheck_global|Invisible"
                    visibility_groups[group_key]['invisible_fields'].append(field.id)
                    visibility_groups[group_key]['original_value'] = ['Invisible']
                    visibility_groups[group_key]['ctrl_name'] = 'rulecheck_global'

        # Also extract from intra-panel references
        if intra_refs:
            for panel in intra_refs.get('panel_results', []):
                for ref in panel.get('intra_panel_references', []):
                    ref_type = ref.get('reference_type', '') or ref.get('dependency_type', '')
                    if 'visibility' in ref_type.lower():
                        controlling = ref.get('referenced_field') or ref.get('depends_on_field')
                        dependent = ref.get('dependent_field') or ref.get('source_field', {}).get('field_name')

                        if controlling and dependent:
                            dep_field = self.field_matcher.match_field(str(dependent))
                            ctrl_key = str(controlling).lower().strip()
                            group_key = f"{ctrl_key}|Yes"
                            if dep_field and dep_field.id not in visibility_groups[group_key]['visible_fields']:
                                visibility_groups[group_key]['visible_fields'].append(dep_field.id)
                                visibility_groups[group_key]['original_value'] = ['Yes']
                                visibility_groups[group_key]['ctrl_name'] = ctrl_key
                                visibility_groups[group_key]['needs_opposite'] = True

        # Generate rules for each group
        for group_key, group in visibility_groups.items():
            ctrl_name = group.get('ctrl_name', '')

            # Handle special RuleCheck global invisible rule
            if ctrl_name == 'rulecheck_global':
                controlling_field = self.field_by_id.get(self.rulecheck_field_id) if self.rulecheck_field_id else None
            else:
                controlling_field = self.field_matcher.match_field(ctrl_name)

            if not controlling_field:
                continue

            values = group.get('original_value', ['Yes'])
            visible_ids = list(set(group.get('visible_fields', [])))
            invisible_ids = list(set(group.get('invisible_fields', [])))
            needs_opposite = group.get('needs_opposite', False)

            # Generate MAKE_VISIBLE rule
            if visible_ids:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="MAKE_VISIBLE",
                    processing_type="CLIENT",
                    source_ids=[controlling_field.id],
                    destination_ids=visible_ids,
                    conditional_values=values,
                    condition="IN",
                    condition_value_type="TEXT",
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[controlling_field.id].append(rule)
                logger.debug(f"MAKE_VISIBLE: {ctrl_name} [{values}] -> {len(visible_ids)} fields")

                # Generate opposite MAKE_INVISIBLE rule if needed
                if needs_opposite:
                    rule = GeneratedRule(
                        id=get_rule_id(),
                        action_type="MAKE_INVISIBLE",
                        processing_type="CLIENT",
                        source_ids=[controlling_field.id],
                        destination_ids=visible_ids,
                        conditional_values=values,
                        condition="NOT_IN",
                        condition_value_type="TEXT",
                        execute_on_fill=True,
                    )
                    self.all_rules.append(rule)
                    self.rules_by_field_id[controlling_field.id].append(rule)
                    logger.debug(f"MAKE_INVISIBLE (opposite): {ctrl_name} NOT IN {values} -> {len(visible_ids)} fields")

            # Generate explicit MAKE_INVISIBLE rule
            if invisible_ids:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="MAKE_INVISIBLE",
                    processing_type="CLIENT",
                    source_ids=[controlling_field.id],
                    destination_ids=invisible_ids,
                    conditional_values=values,
                    condition="NOT_IN",
                    condition_value_type="TEXT",
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[controlling_field.id].append(rule)
                logger.debug(f"MAKE_INVISIBLE: {ctrl_name} NOT IN {values} -> {len(invisible_ids)} fields")

    # --------------------------------------------------------------------------
    # Mandatory Rules
    # --------------------------------------------------------------------------

    def _extract_mandatory_rules(self, intra_refs: Dict = None):
        """Extract MAKE_MANDATORY and MAKE_NON_MANDATORY rules."""
        # Group by (controlling field, conditional values)
        mandatory_groups: Dict[str, Dict] = defaultdict(lambda: {
            'mandatory_fields': [],
            'non_mandatory_fields': [],
            'values': [],
            'ctrl_name': '',
            'needs_opposite': False,
        })

        # Pattern: "mandatory" in logic along with visibility
        pattern = r"if.*field.*['\"](.+?)['\"].*values?\s+is\s+(\w+).*then.*mandatory"

        for field in self.fields:
            logic = field.logic or ''
            logic_lower = logic.lower()

            if 'mandatory' not in logic_lower:
                continue

            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                controlling_name = match.group(1)
                value = match.group(2)
                ctrl_key = controlling_name.lower().strip()
                value_lower = value.lower()

                # Apply special value mappings (same as visibility)
                mapped_values = [value.capitalize()]
                if ctrl_key in self.SPECIAL_VALUE_MAPPINGS:
                    for pattern_key, mapped in self.SPECIAL_VALUE_MAPPINGS[ctrl_key].items():
                        if pattern_key in value_lower:
                            mapped_values = mapped
                            break

                group_key = f"{ctrl_key}|{','.join(sorted(mapped_values))}"
                mandatory_groups[group_key]['ctrl_name'] = ctrl_key
                mandatory_groups[group_key]['values'] = mapped_values
                mandatory_groups[group_key]['mandatory_fields'].append(field.id)

                # Check for opposite pattern
                if 'non-mandatory' in logic_lower or 'otherwise' in logic_lower:
                    mandatory_groups[group_key]['needs_opposite'] = True

        # Generate rules
        for group_key, group in mandatory_groups.items():
            ctrl_name = group.get('ctrl_name', '')
            controlling_field = self.field_matcher.match_field(ctrl_name)
            if not controlling_field:
                continue

            values = group.get('values', ['Yes'])
            mandatory_ids = list(set(group.get('mandatory_fields', [])))
            needs_opposite = group.get('needs_opposite', False)

            if mandatory_ids:
                # Generate MAKE_MANDATORY
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="MAKE_MANDATORY",
                    processing_type="CLIENT",
                    source_ids=[controlling_field.id],
                    destination_ids=mandatory_ids,
                    conditional_values=values,
                    condition="IN",
                    condition_value_type="TEXT",
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[controlling_field.id].append(rule)
                logger.debug(f"MAKE_MANDATORY: {ctrl_name} [{values}] -> {len(mandatory_ids)} fields")

                # Generate opposite MAKE_NON_MANDATORY if needed
                if needs_opposite:
                    rule = GeneratedRule(
                        id=get_rule_id(),
                        action_type="MAKE_NON_MANDATORY",
                        processing_type="CLIENT",
                        source_ids=[controlling_field.id],
                        destination_ids=mandatory_ids,
                        conditional_values=values,
                        condition="NOT_IN",
                        condition_value_type="TEXT",
                        execute_on_fill=True,
                    )
                    self.all_rules.append(rule)
                    self.rules_by_field_id[controlling_field.id].append(rule)
                    logger.debug(f"MAKE_NON_MANDATORY (opposite): {ctrl_name} NOT IN {values} -> {len(mandatory_ids)} fields")

    # --------------------------------------------------------------------------
    # Disabled Rules and RuleCheck-based Invisible Rules
    # --------------------------------------------------------------------------

    def _extract_disabled_rules(self):
        """Extract consolidated MAKE_DISABLED and global MAKE_INVISIBLE rules."""
        disabled_ids = []
        invisible_ids = []

        for field in self.fields:
            logic = field.logic or ''
            logic_lower = logic.lower()

            # Check for non-editable (disabled) fields
            if 'non-editable' in logic_lower or 'non editable' in logic_lower:
                disabled_ids.append(field.id)

            # Check for initially invisible fields (most fields start invisible)
            # Logic patterns: "not visible", "invisible by default", "hide"
            # Also, output fields from validation are often initially invisible
            if ('not visible' in logic_lower or
                'invisible' in logic_lower or
                'initially hidden' in logic_lower or
                'data will come from' in logic_lower):
                invisible_ids.append(field.id)

        if self.rulecheck_field_id:
            # Create consolidated MAKE_DISABLED rule
            if disabled_ids:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="MAKE_DISABLED",
                    processing_type="CLIENT",
                    source_ids=[self.rulecheck_field_id],
                    destination_ids=list(set(disabled_ids)),
                    conditional_values=["Disable"],
                    condition="NOT_IN",
                    condition_value_type="TEXT",
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[self.rulecheck_field_id].append(rule)
                logger.debug(f"MAKE_DISABLED: {len(disabled_ids)} fields consolidated")

            # Create consolidated global MAKE_INVISIBLE rule for all initially hidden fields
            if invisible_ids:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="MAKE_INVISIBLE",
                    processing_type="CLIENT",
                    source_ids=[self.rulecheck_field_id],
                    destination_ids=list(set(invisible_ids)),
                    conditional_values=["Invisible"],
                    condition="NOT_IN",
                    condition_value_type="TEXT",
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[self.rulecheck_field_id].append(rule)
                logger.debug(f"MAKE_INVISIBLE (global): {len(invisible_ids)} fields")

    # --------------------------------------------------------------------------
    # EXT_DROP_DOWN Rules
    # --------------------------------------------------------------------------

    # Known fields that should have EXT_DROP_DOWN rules (from reference analysis)
    EXT_DROPDOWN_FIELDS = {
        # field_name_pattern: params_value
        "country code": "COMPANY_CODE",
        "do you wish to add additional mobile numbers (india)": "PIDILITE_YES_NO",
        "do you wish to add additional mobile numbers (non-india)": "PIDILITE_YES_NO",
        "do you wish to add additional email addresses": "PIDILITE_YES_NO",
        "concerned email addresses": "PIDILITE_YES_NO",
        "type of industry": "TYPE_OF_INDUSTRY",
        "please select gst option": "GSTVALUE",
        "additional registration number applicable": "PIDILITE_YES_NO",
        "business registration number available": "PIDILITE_YES_NO",
        "please choose address proof": "ADDRESS_PROOF",
        "fda registered": "PIDILITE_YES_NO",
        "tds applicable": "PIDILITE_YES_NO",
        "is ssi / msme applicable": "PIDILITE_YES_NO",
        "is ssi/msme applicable": "PIDILITE_YES_NO",
        "terms of payment": "TERMS_OF_PAYMENT",
        "incoterms": "INCOTERMS",
        "is vendor your customer": "PIDILITE_YES_NO",
        "reconciliation account": "RECONCILIATION_ACCOUNT",
        "is withholding tax applicable": "PIDILITE_YES_NO",
        "withholding tax code": "RECONCILIATION_ACCOUNT",
    }

    def _extract_ext_dropdown_rules(self, intra_refs: Dict = None):
        """Extract EXT_DROP_DOWN rules only for known external dropdown fields."""
        created_ext_dropdown_ids = set()

        for field in self.fields:
            # Only process fields that are external dropdowns
            if field.field_type.upper() not in ['EXTERNAL_DROP_DOWN', 'EXTERNAL_DROP_DOWN_VALUE', 'EXTERNAL_DROP_DOWN_MULTISELECT']:
                continue

            if field.id in created_ext_dropdown_ids:
                continue

            # Check if this is a known EXT_DROP_DOWN field
            field_name_lower = field.name.lower().strip()
            params = None

            for pattern, param_value in self.EXT_DROPDOWN_FIELDS.items():
                if pattern in field_name_lower or field_name_lower in pattern:
                    params = param_value
                    break

            # Only create rule if we found a matching pattern
            if params:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="EXT_DROP_DOWN",
                    source_type="FORM_FILL_DROP_DOWN",
                    processing_type="CLIENT",
                    source_ids=[field.id],
                    params=params,
                    searchable=True,
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[field.id].append(rule)
                created_ext_dropdown_ids.add(field.id)
                logger.debug(f"EXT_DROP_DOWN: {field.name} -> {params}")

    def _extract_dropdown_params(self, logic: str, field_name: str = "") -> str:
        """Extract params value from logic text."""
        # Known params mapping from reference
        param_mappings = {
            "company code": "COMPANY_CODE",
            "type of industry": "TYPE_OF_INDUSTRY",
            "account group": "ACCOUNT_GROUP",
            "vendor type": "VENDOR_TYPE",
            "gst option": "GSTVALUE",
            "yes no": "PIDILITE_YES_NO",
            "tds applicable": "PIDILITE_YES_NO",
            "msme applicable": "PIDILITE_YES_NO",
            "ssi": "PIDILITE_YES_NO",
            "country": "COUNTRY",
            "state": "STATE",
            "city": "CITY",
            "payment terms": "TERMS_OF_PAYMENT",
            "incoterms": "INCOTERMS",
            "reconciliation account": "RECONCILIATION_ACCOUNT",
            "address proof": "ADDRESS_PROOF",
        }

        combined = f"{logic} {field_name}".lower()

        for pattern, param_value in param_mappings.items():
            if pattern in combined:
                return param_value

        return ""

    # --------------------------------------------------------------------------
    # VALIDATION Rules
    # --------------------------------------------------------------------------

    # Known VALIDATION rules mapping (from reference analysis)
    # These are fields that populate/validate other fields using external data
    VALIDATION_RULES = {
        # source_field_name: (params, destination_patterns)
        "company and ownership": ("COMPANY_CODE", ["company code", "company ownership", "company country"]),
        "account group/vendor type": ("VC_VENDOR_TYPES", ["vendor domestic or import", "account group code", "account group description"]),
        "vendor country": ("COUNTRY", ["country code", "country name"]),
        "pan type": ("ID_TYPE", ["id type"]),
        "please select gst option": ("TAXCAT", ["tax category"]),
        "postal code": ("PIN-CODE", ["city", "state", "district", "country name"]),
        "ifsc code": ("IFSC", ["bank name", "branch name", "branch address"]),
    }

    def _extract_validation_rules(self):
        """Extract VALIDATION rules for fields that populate/validate other fields."""
        created_validation_ids = set()

        for field in self.fields:
            if field.id in created_validation_ids:
                continue

            name_lower = field.name.lower().strip()
            logic_lower = (field.logic or '').lower()

            # Check if this is a known VALIDATION source field
            params = None
            dest_patterns = []
            for src_pattern, (param_value, destinations) in self.VALIDATION_RULES.items():
                if src_pattern in name_lower or name_lower in src_pattern:
                    params = param_value
                    dest_patterns = destinations
                    break

            if not params:
                continue

            # Find destination fields
            dest_ids = []
            for dest_pattern in dest_patterns:
                dest_field = self.field_matcher.match_field(dest_pattern)
                if dest_field and dest_field.id != field.id:
                    dest_ids.append(dest_field.id)

            if dest_ids:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="VALIDATION",
                    source_type="EXTERNAL_DATA_VALUE",
                    processing_type="SERVER",
                    source_ids=[field.id],
                    destination_ids=dest_ids,
                    params=params,
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[field.id].append(rule)
                created_validation_ids.add(field.id)
                logger.debug(f"VALIDATION: {field.name} -> {len(dest_ids)} destinations")

    # --------------------------------------------------------------------------
    # Other Rules
    # --------------------------------------------------------------------------

    def _extract_other_rules(self):
        """Extract other rule types (CONVERT_TO, COPY_TO, EXT_VALUE, etc.)."""
        self._extract_convert_to_rules()
        self._extract_ext_value_rules()
        self._extract_session_based_rules()
        self._extract_copy_to_rules()

    # Fields that need CONVERT_TO UPPER_CASE rule
    UPPER_CASE_FIELDS = [
        'pan', 'gstin', 'msme registration number', 'cin', 'ifsc code',
        'bank account number', 'name/ first name of the organization',
        'name/first name of the organization', 'e4', 'e5',
        'name of account holder', 'vendor code'
    ]

    def _extract_convert_to_rules(self):
        """Extract CONVERT_TO UPPER_CASE rules."""
        created_convert_rules = set()

        for field in self.fields:
            name_lower = field.name.lower().strip()
            logic_lower = (field.logic or '').lower()

            # Skip if this is a destination/output field (data coming from validation)
            if 'data will come from' in logic_lower:
                continue

            # Check for explicit upper case requirement or known upper case fields
            needs_upper = (
                'upper case' in logic_lower or
                'uppercase' in logic_lower or
                name_lower in self.UPPER_CASE_FIELDS
            )

            if needs_upper and field.id not in created_convert_rules:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="CONVERT_TO",
                    source_type="UPPER_CASE",
                    processing_type="CLIENT",
                    source_ids=[field.id],
                    destination_ids=[field.id],
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[field.id].append(rule)
                created_convert_rules.add(field.id)
                logger.debug(f"CONVERT_TO: {field.name} -> UPPER_CASE")

    # EXT_VALUE fields - fields that get external data values (from reference)
    EXT_VALUE_FIELDS = {
        # field_name_pattern: params_value
        "choose the group of company": '[{"conditionList":[{"ddType":["COMPANY_CODE_PURCHASE_ORGANIZATION"],"criterias":[{"a7":275496}],"da":["a3"],"criteriaSearchAttr":[],"additionalOptions":null,"emptyAddOptionCheck":null,"ddProperties":null}]}]',
        "company and ownership": '[{"conditionList":[{"ddType":["COMPANY_CODE_PURCHASE_ORGANIZATION"],"criterias":[{"a3":276416}],"da":["a1"],"criteriaSearchAttr":[],"additionalOptions":null,"emptyAddOptionCheck":null,"ddProperties":null}]}]',
        "account group/vendor type": '[{"conditionList":[{"ddType":["VC_VENDOR_TYPES"],"criterias":[{"a4":275496}],"da":["a1"],"criteriaSearchAttr":[],"additionalOptions":null,"emptyAddOptionCheck":null,"ddProperties":null}]}]',
        "vendor domestic or import": "VENDOR_DOMESTIC_IMPORT",
        "group key": "GROUP_KEY",
        "id type": "ID_TYPE",
        "recipient type": "RECIPIENT_TYPE",
        "gst vendor classification": "GST_VENDOR_CLASSIFICATION",
        "process type": "PROCESS_TYPE",
        "country name": "COUNTRY_NAME",
        "company description": "COMPANY_DESCRIPTION",
    }

    def _extract_ext_value_rules(self):
        """Extract EXT_VALUE rules for fields populated from external data."""
        created_ext_value_ids = set()

        for field in self.fields:
            if field.id in created_ext_value_ids:
                continue

            name_lower = field.name.lower().strip()
            logic_lower = (field.logic or '').lower()

            # Check if this is a known EXT_VALUE field by name
            params = None
            for pattern, param_value in self.EXT_VALUE_FIELDS.items():
                if pattern in name_lower or name_lower in pattern:
                    params = param_value
                    break

            # Also check by logic pattern
            if not params and field.field_type.upper() in ['EXTERNAL_DROP_DOWN_VALUE', 'EXTERNAL_DROP_DOWN']:
                # Check if logic mentions deriving from external table
                if ('external' in logic_lower or 'reference table' in logic_lower or
                    'derive' in logic_lower or 'column' in logic_lower or
                    'edv' in logic_lower):
                    # Use a generic params value based on field type
                    params = "EXTERNAL_DATA_VALUE"

            if params:
                rule = GeneratedRule(
                    id=get_rule_id(),
                    action_type="EXT_VALUE",
                    source_type="EXTERNAL_DATA_VALUE",
                    processing_type="SERVER",
                    source_ids=[field.id],
                    destination_ids=[],
                    params=params,
                    execute_on_fill=True,
                )
                self.all_rules.append(rule)
                self.rules_by_field_id[field.id].append(rule)
                created_ext_value_ids.add(field.id)
                logger.debug(f"EXT_VALUE: {field.name}")

    # Known SESSION_BASED rules (from reference analysis)
    # These are fields where visibility/mandatory depends on who is viewing (first vs second party)
    SESSION_BASED_RULES = [
        # (source_field_pattern, action_type, params, conditional_values, condition, destination_patterns)
        ("transaction id", "SESSION_BASED_MAKE_VISIBLE", "FIRST_PARTY", ["Invisible"], "NOT_IN", ["account group"]),
        ("created by mobile", "SESSION_BASED_MAKE_VISIBLE", "SECOND_PARTY", ["Invisible"], "NOT_IN", ["basic details", "kyc", "bank"]),
        ("choose the group of company", "SESSION_BASED_MAKE_VISIBLE", "SECOND_PARTY", ["International Subsidaries"], "IN", ["name", "e4", "e5"]),
        ("choose the group of company", "SESSION_BASED_MAKE_INVISIBLE", "SECOND_PARTY", ["International Subsidaries"], "IN", ["pan", "upload pan"]),
        ("choose the group of company", "SESSION_BASED_MAKE_INVISIBLE", "SECOND_PARTY", ["PIL", "Domestic Subsidaries"], "IN", ["name", "e4", "e5"]),
        ("choose the group of company", "SESSION_BASED_MAKE_MANDATORY", "SECOND_PARTY", ["PIL", "Domestic Subsidaries"], "IN", ["pan"]),
        ("choose the group of company", "SESSION_BASED_MAKE_MANDATORY", "SECOND_PARTY", ["International Subsidaries"], "IN", ["name"]),
        ("choose the group of company", "SESSION_BASED_MAKE_NON_MANDATORY", "SECOND_PARTY", ["International Subsidaries"], "NOT_IN", ["name"]),
        ("choose the group of company", "SESSION_BASED_MAKE_NON_MANDATORY", "SECOND_PARTY", ["PIL", "Domestic Subsidaries"], "NOT_IN", ["pan"]),
    ]

    def _extract_session_based_rules(self):
        """Extract SESSION_BASED visibility/mandatory rules for first/second party differences."""
        created_rules = set()

        for field in self.fields:
            logic = field.logic or ''
            logic_lower = logic.lower()

            # Skip if no session-based keywords
            if 'first party' not in logic_lower and 'second party' not in logic_lower:
                continue

            # Determine params (who this applies to)
            if 'first party' in logic_lower:
                params = "FIRST_PARTY"
            elif 'second party' in logic_lower:
                params = "SECOND_PARTY"
            else:
                continue

            # Determine action type
            action_type = None
            if 'visible' in logic_lower and 'invisible' not in logic_lower:
                action_type = "SESSION_BASED_MAKE_VISIBLE"
            elif 'invisible' in logic_lower:
                action_type = "SESSION_BASED_MAKE_INVISIBLE"
            elif 'mandatory' in logic_lower and 'non-mandatory' not in logic_lower:
                action_type = "SESSION_BASED_MAKE_MANDATORY"
            elif 'non-mandatory' in logic_lower:
                action_type = "SESSION_BASED_MAKE_NON_MANDATORY"
            else:
                action_type = "SESSION_BASED_MAKE_VISIBLE"

            # Generate unique key to avoid duplicates
            rule_key = (field.id, action_type, params)
            if rule_key in created_rules:
                continue

            rule = GeneratedRule(
                id=get_rule_id(),
                action_type=action_type,
                processing_type="CLIENT",
                source_ids=[field.id],
                destination_ids=[],
                params=params,
                conditional_values=["Invisible"],
                condition="NOT_IN",
                condition_value_type="TEXT",
                execute_on_fill=True,
            )
            self.all_rules.append(rule)
            self.rules_by_field_id[field.id].append(rule)
            created_rules.add(rule_key)
            logger.debug(f"{action_type}: {field.name} ({params})")

    # Known COPY_TO rules patterns (from reference)
    COPY_TO_PATTERNS = [
        # (source_pattern, destinations_patterns, source_type)
        ("created by name", ["created by name", "created by email", "created by mobile"], "CREATED_BY"),
        ("company and ownership", ["company code", "company ownership", "company country"], "FORM_FILL_METADATA"),
        ("basic details", ["company code", "company description"], "FORM_FILL_METADATA"),
    ]

    def _extract_copy_to_rules(self):
        """Extract COPY_TO rules for field value copying."""
        created_copy_rules = set()

        # First, handle known COPY_TO patterns from reference
        for src_pattern, dest_patterns, source_type in self.COPY_TO_PATTERNS:
            source_field = self.field_matcher.match_field(src_pattern)
            if not source_field:
                continue

            for dest_pattern in dest_patterns:
                dest_field = self.field_matcher.match_field(dest_pattern)
                if dest_field and dest_field.id != source_field.id:
                    rule_key = (source_field.id, dest_field.id)
                    if rule_key in created_copy_rules:
                        continue

                    rule = GeneratedRule(
                        id=get_rule_id(),
                        action_type="COPY_TO",
                        source_type=source_type,
                        processing_type="CLIENT",
                        source_ids=[source_field.id],
                        destination_ids=[dest_field.id],
                        execute_on_fill=True,
                    )
                    self.all_rules.append(rule)
                    self.rules_by_field_id[source_field.id].append(rule)
                    created_copy_rules.add(rule_key)
                    logger.debug(f"COPY_TO: {source_field.name} -> {dest_field.name}")

        # Also extract from logic patterns
        for field in self.fields:
            logic = field.logic or ''
            logic_lower = logic.lower()

            # Pattern: "copy from field X" or "derived from field X"
            copy_match = re.search(r"copy\s+(?:from|to)\s+['\"]?([^'\"]+)['\"]?", logic, re.IGNORECASE)
            if copy_match:
                source_name = copy_match.group(1).strip()
                source_field = self.field_matcher.match_field(source_name)
                if source_field:
                    rule_key = (source_field.id, field.id)
                    if rule_key in created_copy_rules:
                        continue

                    rule = GeneratedRule(
                        id=get_rule_id(),
                        action_type="COPY_TO",
                        source_type="FORM_FILL_METADATA",
                        processing_type="CLIENT",
                        source_ids=[source_field.id],
                        destination_ids=[field.id],
                        execute_on_fill=True,
                    )
                    self.all_rules.append(rule)
                    self.rules_by_field_id[source_field.id].append(rule)
                    created_copy_rules.add(rule_key)
                    logger.debug(f"COPY_TO: {source_field.name} -> {field.name}")

    # --------------------------------------------------------------------------
    # Output
    # --------------------------------------------------------------------------

    def _build_output(self) -> Dict[str, Any]:
        """Build final output dictionary."""
        # Count rules by type
        rule_counts = defaultdict(int)
        for rule in self.all_rules:
            rule_counts[rule.action_type] += 1

        # Build formFillMetadatas with rules
        metadatas = []
        for field in self.fields:
            rules = self.rules_by_field_id.get(field.id, [])
            metadata = {
                "id": field.id,
                "formTag": {
                    "id": field.id,
                    "name": field.name,
                    "type": field.field_type,
                },
                "variableName": field.variable_name,
                "mandatory": field.is_mandatory,
                "editable": True,
                "visible": True,
                "formFillRules": [r.to_dict() for r in rules],
            }
            metadatas.append(metadata)

        output = {
            "template": {
                "id": self.reference_data.get('template', {}).get('id', 1),
                "templateName": self.reference_data.get('template', {}).get('templateName', ''),
                "documentTypes": [{
                    "id": 1,
                    "formFillMetadatas": metadatas,
                }],
            },
            "extraction_info": {
                "bud_document": self.bud_path,
                "reference_schema": self.reference_path,
                "total_fields": len(self.fields),
                "total_rules_generated": len(self.all_rules),
                "rule_type_distribution": dict(rule_counts),
            },
        }

        return output


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Extract rules from BUD document")
    parser.add_argument("--bud", required=True, help="Path to BUD .docx document")
    parser.add_argument("--reference", required=True, help="Path to reference schema JSON")
    parser.add_argument("--intra-panel", help="Path to intra-panel references JSON")
    parser.add_argument("--output", help="Output path for populated schema JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    agent = RuleExtractionAgent(
        bud_path=args.bud,
        reference_path=args.reference,
        intra_panel_path=args.intra_panel,
        verbose=args.verbose,
    )

    result = agent.extract()

    # Save output
    output_path = args.output or "populated_schema.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("RULE EXTRACTION SUMMARY")
    print("=" * 60)
    info = result['extraction_info']
    print(f"BUD Document: {info['bud_document']}")
    print(f"Reference Schema: {info['reference_schema']}")
    print(f"Total Fields: {info['total_fields']}")
    print(f"Total Rules Generated: {info['total_rules_generated']}")
    print("\nRule Type Distribution:")
    for rule_type, count in sorted(info['rule_type_distribution'].items()):
        print(f"  {rule_type}: {count}")
    print("=" * 60)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
