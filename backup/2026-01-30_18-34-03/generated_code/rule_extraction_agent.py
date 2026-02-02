#!/usr/bin/env python3
"""
Rule Extraction Agent - Main entry point for extracting rules from BUD documents.

This script parses a BUD document, analyzes field logic, and generates formFillRules
for a JSON schema output.

Usage:
    python rule_extraction_agent.py

Output:
    - populated_schema.json with formFillRules for each field
"""

import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from doc_parser import DocumentParser

# Local imports
from models import (
    ParsedLogic, FieldInfo, GeneratedRule, VisibilityGroup, OcrVerifyChain
)
from logic_parser import LogicParser
from field_matcher import FieldMatcher
from schema_lookup import RuleSchemaLookup, DOC_TYPE_TO_VERIFY_SOURCE, DOC_TYPE_TO_OCR_SOURCE
from id_mapper import DestinationIdMapper
from utils import (
    load_json_file, save_json_file, detect_ocr_document_type,
    detect_verify_document_type, is_verify_destination_field, is_disabled_field
)
from rule_builders import (
    StandardRuleBuilder, VisibilityRuleBuilder, VerifyRuleBuilder, OcrRuleBuilder,
    EdvRuleBuilder, CopyRuleBuilder, DocumentRuleBuilder
)


# Configuration
BUD_PATH = "/home/samart/project/doc-parser/documents/Vendor Creation Sample BUD.docx"
INTRA_PANEL_PATH = "/home/samart/project/doc-parser/adws/2026-01-30_18-34-03/intra_panel_references.json"
REFERENCE_OUTPUT_PATH = "/home/samart/project/doc-parser/documents/json_output/vendor_creation_sample_bud.json"
OUTPUT_PATH = "/home/samart/project/doc-parser/adws/2026-01-30_18-34-03/populated_schema.json"


class RuleExtractionAgent:
    """
    Main agent for extracting rules from BUD documents.

    This agent:
    1. Parses the BUD document to get field definitions with logic
    2. Analyzes logic text to determine rule types
    3. Uses intra-panel references for field dependencies
    4. Generates formFillRules for each field
    """

    def __init__(
        self,
        bud_path: str = BUD_PATH,
        intra_panel_path: str = INTRA_PANEL_PATH,
        reference_path: str = REFERENCE_OUTPUT_PATH,
    ):
        """
        Initialize the rule extraction agent.

        Args:
            bud_path: Path to the BUD .docx document
            intra_panel_path: Path to intra-panel references JSON
            reference_path: Path to reference output JSON (for field IDs)
        """
        self.bud_path = bud_path
        self.intra_panel_path = intra_panel_path
        self.reference_path = reference_path

        # Initialize components
        self.logic_parser = LogicParser()
        self.schema_lookup = RuleSchemaLookup()
        self.id_mapper = DestinationIdMapper(self.schema_lookup)

        # Rule builders
        self.standard_builder = StandardRuleBuilder()
        self.visibility_builder = VisibilityRuleBuilder()
        self.verify_builder = VerifyRuleBuilder(self.schema_lookup, self.id_mapper)
        self.ocr_builder = OcrRuleBuilder(self.schema_lookup)
        self.edv_builder = EdvRuleBuilder()
        self.copy_builder = CopyRuleBuilder()
        self.document_builder = DocumentRuleBuilder()

        # Data storage
        self.parsed_bud = None
        self.intra_panel_refs = None
        self.reference_schema = None
        self.field_matcher = None

        # Field mappings
        self.field_name_to_id: Dict[str, int] = {}
        self.field_id_to_info: Dict[int, Dict] = {}
        self.field_name_to_logic: Dict[str, str] = {}

        # Rule tracking
        self.visibility_groups: Dict[str, List[Dict]] = defaultdict(list)
        self.ocr_verify_chains: List[OcrVerifyChain] = []
        self.generated_rules: Dict[int, List[Dict]] = defaultdict(list)

        # Statistics
        self.stats = {
            "total_fields": 0,
            "fields_with_logic": 0,
            "rules_generated": 0,
            "skipped_expression_rules": 0,
            "ocr_rules": 0,
            "verify_rules": 0,
            "visibility_rules": 0,
            "mandatory_rules": 0,
            "disabled_rules": 0,
            "ext_dropdown_rules": 0,
            "copy_rules": 0,
            "convert_rules": 0,
        }

    def load_data(self):
        """Load all required data sources."""
        print("Loading data sources...")

        # 1. Parse BUD document
        print(f"  Parsing BUD document: {self.bud_path}")
        parser = DocumentParser()
        self.parsed_bud = parser.parse(self.bud_path)
        print(f"    Found {len(self.parsed_bud.all_fields)} fields")

        # 2. Load intra-panel references
        print(f"  Loading intra-panel references: {self.intra_panel_path}")
        self.intra_panel_refs = load_json_file(self.intra_panel_path)
        panel_count = len(self.intra_panel_refs.get("panel_results", []))
        print(f"    Found {panel_count} panels")

        # 3. Load reference schema (for field IDs)
        print(f"  Loading reference schema: {self.reference_path}")
        self.reference_schema = load_json_file(self.reference_path)

        # Build field mappings from reference schema
        self._build_field_mappings()

    def _build_field_mappings(self):
        """Build field name to ID mappings from reference schema."""
        print("Building field mappings...")

        doc_types = self.reference_schema.get("template", {}).get("documentTypes", [])
        for doc_type in doc_types:
            for meta in doc_type.get("formFillMetadatas", []):
                field_id = meta.get("id")
                form_tag = meta.get("formTag", {})
                field_name = form_tag.get("name", "")
                field_type = form_tag.get("type", "")

                if field_id and field_name:
                    # Store mapping
                    self.field_name_to_id[field_name] = field_id
                    self.field_name_to_id[field_name.lower()] = field_id

                    # Store full info
                    self.field_id_to_info[field_id] = {
                        "id": field_id,
                        "name": field_name,
                        "type": field_type,
                        "variable_name": meta.get("variableName", ""),
                        "form_order": meta.get("formOrder", 0),
                        "existing_rules": meta.get("formFillRules", []),
                    }

        # Map BUD field logic
        for field in self.parsed_bud.all_fields:
            self.field_name_to_logic[field.name] = field.logic or ""
            self.field_name_to_logic[field.name.lower()] = field.logic or ""

        # Initialize field matcher
        fields_list = list(self.field_id_to_info.values())
        self.field_matcher = FieldMatcher(fields_list)

        print(f"  Mapped {len(self.field_name_to_id)} field names to IDs")
        self.stats["total_fields"] = len(self.field_id_to_info)

    def get_field_id(self, field_name: str) -> Optional[int]:
        """Get field ID by name with fuzzy matching fallback."""
        # Try exact match first
        if field_name in self.field_name_to_id:
            return self.field_name_to_id[field_name]
        if field_name.lower() in self.field_name_to_id:
            return self.field_name_to_id[field_name.lower()]

        # Try fuzzy match
        return self.field_matcher.get_field_id(field_name)

    def analyze_visibility_patterns(self):
        """
        First pass: Identify visibility controlling fields.

        Groups destination fields by their controlling field to generate
        efficient rules with multiple destinations.
        """
        print("\nAnalyzing visibility patterns...")

        for field in self.parsed_bud.all_fields:
            logic = field.logic or ""
            if not logic:
                continue

            # Check for visibility pattern
            visibility_info = self.visibility_builder.analyze_logic_for_visibility(logic)
            if visibility_info and visibility_info.get("controlling_field"):
                controlling_field = visibility_info["controlling_field"]
                conditional_value = visibility_info.get("conditional_value")
                is_mandatory = visibility_info.get("is_mandatory_when_true", False)

                dest_id = self.get_field_id(field.name)
                if dest_id:
                    self.visibility_groups[controlling_field].append({
                        "destination_field": field.name,
                        "destination_id": dest_id,
                        "conditional_value": conditional_value,
                        "is_mandatory": is_mandatory,
                    })

        print(f"  Found {len(self.visibility_groups)} controlling fields")
        for ctrl, dests in self.visibility_groups.items():
            print(f"    '{ctrl}' controls {len(dests)} fields")

    def analyze_ocr_verify_chains(self):
        """
        Identify OCR -> VERIFY chains from intra-panel references.
        """
        print("\nAnalyzing OCR -> VERIFY chains...")

        # Look for data_flow references indicating OCR -> VERIFY chains
        for panel in self.intra_panel_refs.get("panel_results", []):
            refs = panel.get("intra_panel_references", [])

            for ref in refs:
                ref_type = ref.get("reference_type", "")
                logic = ref.get("logic_excerpt", "") or ref.get("description", "")

                # Check for OCR pattern
                if "ocr" in ref_type.lower() or "ocr" in logic.lower():
                    source_field = ref.get("source_field")
                    target_field = ref.get("target_field")

                    if source_field and target_field:
                        source_id = self.get_field_id(source_field)
                        target_id = self.get_field_id(target_field)

                        if source_id and target_id:
                            doc_type = detect_ocr_document_type(logic)
                            if doc_type:
                                print(f"  Found OCR chain: {source_field} -> {target_field} ({doc_type})")

    def process_field(self, field_name: str, field_id: int) -> List[Dict]:
        """
        Process a single field and generate rules.

        Args:
            field_name: Field name
            field_id: Field ID

        Returns:
            List of generated rules
        """
        rules = []

        # Get logic from BUD
        logic = self.field_name_to_logic.get(field_name, "")
        if not logic:
            logic = self.field_name_to_logic.get(field_name.lower(), "")

        if not logic:
            return rules

        self.stats["fields_with_logic"] += 1

        # Parse the logic
        parsed = self.logic_parser.parse(logic)

        # Skip expression/execute rules
        if parsed.is_skip:
            self.stats["skipped_expression_rules"] += 1
            return rules

        # 1. Check for OCR rules
        if parsed.is_ocr:
            ocr_rule = self._build_ocr_rule(field_name, field_id, logic)
            if ocr_rule:
                rules.append(ocr_rule)
                self.stats["ocr_rules"] += 1

        # 2. Check for VERIFY rules (but not destination fields)
        if parsed.is_verify and not is_verify_destination_field(logic):
            verify_rule = self._build_verify_rule(field_name, field_id, logic)
            if verify_rule:
                rules.append(verify_rule)
                self.stats["verify_rules"] += 1

        # 3. Check for MAKE_DISABLED
        if parsed.is_disabled or is_disabled_field(logic):
            disabled_rule = self._build_disabled_rule(field_id)
            if disabled_rule:
                rules.append(disabled_rule)
                self.stats["disabled_rules"] += 1

        # 4. Check for uppercase conversion
        if "upper" in logic.lower() and "case" in logic.lower():
            convert_rule = self.standard_builder.build_convert_to_uppercase([field_id])
            rules.append(convert_rule)
            self.stats["convert_rules"] += 1

        # 5. Check for external dropdown rules
        if parsed.is_ext_dropdown:
            edv_rule = self._build_ext_dropdown_rule(field_name, field_id, logic)
            if edv_rule:
                rules.append(edv_rule)
                self.stats["ext_dropdown_rules"] += 1

        # 6. Check for copy/derive rules
        if parsed.is_copy:
            copy_rule = self._build_copy_rule(field_name, field_id, logic)
            if copy_rule:
                rules.append(copy_rule)
                self.stats["copy_rules"] += 1

        return rules

    def _build_ocr_rule(self, field_name: str, field_id: int, logic: str) -> Optional[Dict]:
        """Build an OCR rule for a field."""
        # OCR rules only apply to file upload fields (SOURCE of OCR)
        # Fields with "Data will come from OCR" are DESTINATIONS, not sources
        name_lower = field_name.lower()

        # Check if this is an OCR source (file upload field) vs destination
        is_ocr_source = (
            ("upload" in name_lower or "image" in name_lower or "copy" in name_lower) and
            not is_verify_destination_field(logic) and  # Not "Data will come from..."
            not re.search(r"data\s+will\s+come\s+from", logic, re.IGNORECASE)
        )

        # Also check if the logic explicitly says this field is for uploading
        if not is_ocr_source:
            if re.search(r"get\s+\w+\s+from\s+ocr\s+rule", logic, re.IGNORECASE):
                # This says "Get X from OCR rule" which is on the upload field
                is_ocr_source = True

        if not is_ocr_source:
            return None

        doc_type = detect_ocr_document_type(logic)
        if not doc_type:
            # Try to detect from field name
            if "pan" in name_lower and ("upload" in name_lower or "image" in name_lower):
                doc_type = "PAN"
            elif "gstin" in name_lower and "image" in name_lower:
                doc_type = "GSTIN"
            elif "aadhaar" in name_lower or "aadhar" in name_lower:
                if "back" in name_lower:
                    doc_type = "AADHAAR_BACK"
                else:
                    doc_type = "AADHAAR_FRONT"
            elif "cheque" in name_lower:
                doc_type = "CHEQUE"
            elif "msme" in name_lower and "image" in name_lower:
                doc_type = "MSME"

        if not doc_type:
            return None

        # Find destination field (the text field populated by OCR)
        destination_id = self._find_ocr_destination(field_name, doc_type)
        if not destination_id:
            return None

        try:
            return self.ocr_builder.build(
                doc_type=doc_type,
                upload_field_id=field_id,
                destination_ids=[destination_id],
            )
        except ValueError:
            return None

    def _find_ocr_destination(self, upload_field_name: str, doc_type: str) -> Optional[int]:
        """Find the destination field for an OCR rule."""
        # Look for text field with similar name
        name_lower = upload_field_name.lower()

        # For "Upload PAN" -> "PAN"
        if "upload" in name_lower:
            base_name = upload_field_name.replace("Upload ", "").replace("upload ", "")
            base_name = base_name.replace(" IMAGE", "").replace(" image", "")
            dest_id = self.get_field_id(base_name)
            if dest_id:
                return dest_id

        # For "GSTIN IMAGE" -> "GSTIN"
        if "image" in name_lower:
            base_name = upload_field_name.replace(" IMAGE", "").replace(" Image", "").replace(" image", "")
            dest_id = self.get_field_id(base_name)
            if dest_id:
                return dest_id

        # Doc type specific patterns
        if doc_type == "PAN":
            return self.get_field_id("PAN")
        elif doc_type == "GSTIN":
            return self.get_field_id("GSTIN")
        elif doc_type in ["AADHAAR_FRONT", "AADHAAR_BACK"]:
            return self.get_field_id("Aadhaar Number")

        return None

    def _build_verify_rule(self, field_name: str, field_id: int, logic: str) -> Optional[Dict]:
        """Build a VERIFY rule for a field."""
        doc_type = detect_verify_document_type(logic)
        if not doc_type:
            # Try to detect from field name
            name_lower = field_name.lower()
            if "pan" in name_lower and "upload" not in name_lower:
                doc_type = "PAN"
            elif "gstin" in name_lower and "image" not in name_lower:
                doc_type = "GSTIN"
            elif "bank" in name_lower or "account" in name_lower:
                doc_type = "BANK"
            elif "msme" in name_lower and "registration" in name_lower:
                doc_type = "MSME"

        if not doc_type:
            return None

        # Find destination fields (populated by verification)
        destination_ids = self._find_verify_destinations(field_name, doc_type)

        try:
            return self.verify_builder.build(
                doc_type=doc_type,
                source_field_id=field_id,
                destination_ids=destination_ids,
            )
        except ValueError:
            return None

    def _find_verify_destinations(self, source_field_name: str, doc_type: str) -> List[int]:
        """Find destination fields for a VERIFY rule."""
        # Look for fields that say "Data will come from X validation"
        destinations = []

        for name, logic in self.field_name_to_logic.items():
            if is_verify_destination_field(logic):
                # Check if this references our doc type
                if doc_type.lower() in logic.lower():
                    dest_id = self.get_field_id(name)
                    if dest_id:
                        destinations.append(dest_id)

        # If using schema, we need ordinal-indexed array
        if doc_type == "PAN":
            # PAN verify has 9 ordinals
            ordinal_destinations = [-1] * 9
            # Map known fields
            pan_holder_id = self.get_field_id("Pan Holder Name")
            pan_type_id = self.get_field_id("PAN Type")
            pan_status_id = self.get_field_id("PAN Status")
            aadhaar_status_id = self.get_field_id("Aadhaar PAN List Status")

            if pan_holder_id:
                ordinal_destinations[3] = pan_holder_id  # ordinal 4
            if pan_status_id:
                ordinal_destinations[5] = pan_status_id  # ordinal 6
            if pan_type_id:
                ordinal_destinations[7] = pan_type_id  # ordinal 8
            if aadhaar_status_id:
                ordinal_destinations[8] = aadhaar_status_id  # ordinal 9

            return ordinal_destinations

        elif doc_type == "GSTIN":
            # GSTIN verify has 11+ ordinals
            ordinal_destinations = [-1] * 11
            # Map known fields
            trade_name_id = self.get_field_id("Trade Name")
            legal_name_id = self.get_field_id("Legal Name")
            reg_date_id = self.get_field_id("Reg Date")
            city_id = self.get_field_id("City")
            type_id = self.get_field_id("Type")
            building_id = self.get_field_id("Building Number")
            district_id = self.get_field_id("District")
            state_id = self.get_field_id("State")
            street_id = self.get_field_id("Street")
            pincode_id = self.get_field_id("Pin Code")

            if trade_name_id:
                ordinal_destinations[0] = trade_name_id  # ordinal 1
            if legal_name_id:
                ordinal_destinations[1] = legal_name_id  # ordinal 2
            if reg_date_id:
                ordinal_destinations[2] = reg_date_id  # ordinal 3
            if city_id:
                ordinal_destinations[3] = city_id  # ordinal 4
            if type_id:
                ordinal_destinations[4] = type_id  # ordinal 5
            if building_id:
                ordinal_destinations[5] = building_id  # ordinal 6
            if district_id:
                ordinal_destinations[7] = district_id  # ordinal 8
            if state_id:
                ordinal_destinations[8] = state_id  # ordinal 9
            if street_id:
                ordinal_destinations[9] = street_id  # ordinal 10
            if pincode_id:
                ordinal_destinations[10] = pincode_id  # ordinal 11

            return ordinal_destinations

        return destinations

    def _build_disabled_rule(self, field_id: int) -> Dict:
        """Build a MAKE_DISABLED rule."""
        # Use a RuleCheck control field if available, otherwise use the field itself
        rule_check_id = self.get_field_id("RuleCheck")
        source_id = rule_check_id if rule_check_id else field_id

        return self.standard_builder.build_disabled(
            source_ids=[source_id],
            destination_ids=[field_id],
        )

    def _build_ext_dropdown_rule(self, field_name: str, field_id: int, logic: str) -> Optional[Dict]:
        """Build an EXT_DROP_DOWN rule for a dropdown field."""
        # Try to find reference table info from logic
        params = self._extract_dropdown_params(field_name, logic)
        if not params:
            return None

        # Check if this is a cascading dropdown (dependent on another field)
        parent_field = self._find_parent_dropdown(field_name, logic)

        if parent_field:
            parent_id = self.get_field_id(parent_field)
            if parent_id:
                return self.edv_builder.build_cascading_dropdown(
                    field_id=field_id,
                    parent_field_id=parent_id,
                    params=params,
                )

        # Self-referencing dropdown
        return self.edv_builder.build_ext_dropdown(
            field_id=field_id,
            params=params,
        )

    def _extract_dropdown_params(self, field_name: str, logic: str) -> Optional[str]:
        """Extract dropdown lookup parameters from logic text."""
        # Common patterns
        name_lower = field_name.lower()
        logic_lower = logic.lower()

        # Map common field names to params
        param_mappings = {
            "country": "COUNTRY",
            "state": "STATE",
            "city": "CITY",
            "company code": "COMPANY_CODE",
            "currency": "CURRENCY",
            "account group": "ACCOUNT_GROUP",
            "vendor type": "VENDOR_TYPE",
            "yes": "PIDILITE_YES_NO",
            "no": "PIDILITE_YES_NO",
        }

        for pattern, param in param_mappings.items():
            if pattern in name_lower:
                return param

        # Check for reference table mentions
        ref_table_match = re.search(r"reference\s+table\s+(\d+\.?\d*)", logic_lower)
        if ref_table_match:
            # Generic param based on reference table
            return f"REF_TABLE_{ref_table_match.group(1).replace('.', '_')}"

        return None

    def _find_parent_dropdown(self, field_name: str, logic: str) -> Optional[str]:
        """Find the parent dropdown field for cascading dropdowns."""
        # Look for patterns like "based on X" or "filtered by X"
        patterns = [
            r"based\s+on\s+(?:the\s+)?['\"]?([^'\"]+?)['\"]?\s+(?:selection|field)",
            r"filtered\s+by\s+['\"]?([^'\"]+?)['\"]?",
            r"parent\s+dropdown\s+field:\s*['\"]?([^'\"]+?)['\"]?",
            r"depends\s+on\s+['\"]?([^'\"]+?)['\"]?",
        ]

        for pattern in patterns:
            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _build_copy_rule(self, field_name: str, field_id: int, logic: str) -> Optional[Dict]:
        """Build a COPY_TO rule for copying/deriving field values."""
        # Find the source field for copying
        source_field = self._find_copy_source(logic)
        if not source_field:
            return None

        source_id = self.get_field_id(source_field)
        if not source_id:
            return None

        return self.copy_builder.build_copy_to(
            source_field_id=source_id,
            destination_ids=[field_id],
        )

    def _find_copy_source(self, logic: str) -> Optional[str]:
        """Find the source field for a copy operation."""
        patterns = [
            r"copy\s+from\s+['\"]?([^'\"]+?)['\"]?",
            r"derived?\s+from\s+['\"]?([^'\"]+?)['\"]?",
            r"populated\s+by\s+['\"]?([^'\"]+?)['\"]?",
            r"auto-fill(?:ed)?\s+from\s+['\"]?([^'\"]+?)['\"]?",
            r"value\s+comes?\s+from\s+['\"]?([^'\"]+?)['\"]?",
        ]

        for pattern in patterns:
            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def generate_visibility_rules(self):
        """Generate visibility rules from grouped visibility patterns."""
        print("\nGenerating visibility rules...")

        for controlling_field, destinations in self.visibility_groups.items():
            source_id = self.get_field_id(controlling_field)
            if not source_id:
                print(f"  Warning: Could not find ID for controlling field '{controlling_field}'")
                continue

            # Group by conditional value and mandatory flag
            groups = defaultdict(list)
            for dest in destinations:
                key = (dest.get("conditional_value", ""), dest.get("is_mandatory", False))
                groups[key].append(dest["destination_id"])

            for (conditional_value, is_mandatory), dest_ids in groups.items():
                if not conditional_value:
                    continue

                # Generate visibility rules
                rules = self.visibility_builder.build_visibility_rules_from_group(
                    source_field_id=source_id,
                    destination_field_ids=dest_ids,
                    conditional_value=conditional_value,
                    include_mandatory=is_mandatory,
                )

                # Add rules to the source field
                self.generated_rules[source_id].extend(rules)
                self.stats["visibility_rules"] += len([r for r in rules if "VISIBLE" in r.get("actionType", "")])
                self.stats["mandatory_rules"] += len([r for r in rules if "MANDATORY" in r.get("actionType", "")])

                print(f"  Generated {len(rules)} rules for '{controlling_field}' -> {len(dest_ids)} fields")

    def process_intra_panel_references(self):
        """Process intra-panel references to generate additional rules."""
        print("\nProcessing intra-panel references...")

        for panel in self.intra_panel_refs.get("panel_results", []):
            refs = panel.get("intra_panel_references", [])

            # Use visibility builder to process references
            rules_by_source = self.visibility_builder.build_from_intra_panel_references(
                refs, self.field_name_to_id
            )

            for source_id, rules in rules_by_source.items():
                self.generated_rules[source_id].extend(rules)
                print(f"  Generated {len(rules)} rules from panel references for field {source_id}")

    def run(self) -> Dict:
        """
        Run the complete rule extraction process.

        Returns:
            Dict containing the populated schema
        """
        print("=" * 60)
        print("Rule Extraction Agent")
        print("=" * 60)

        # 1. Load data
        self.load_data()

        # 2. Analyze visibility patterns
        self.analyze_visibility_patterns()

        # 3. Analyze OCR -> VERIFY chains
        self.analyze_ocr_verify_chains()

        # 4. Process intra-panel references
        self.process_intra_panel_references()

        # 5. Generate visibility rules from groups
        self.generate_visibility_rules()

        # 6. Process each field
        print("\nProcessing fields...")
        for field in self.parsed_bud.all_fields:
            field_id = self.get_field_id(field.name)
            if not field_id:
                continue

            rules = self.process_field(field.name, field_id)
            if rules:
                self.generated_rules[field_id].extend(rules)

        # 7. Build output schema
        output_schema = self._build_output_schema()

        # 8. Print statistics
        self._print_stats()

        return output_schema

    def _build_output_schema(self) -> Dict:
        """Build the output schema with generated rules."""
        print("\nBuilding output schema...")

        # Clone the reference schema structure
        output = {
            "extraction_timestamp": datetime.now().isoformat(),
            "source_bud": self.bud_path,
            "statistics": self.stats,
            "fields_with_rules": [],
        }

        # Add rules to each field
        for field_id, rules in self.generated_rules.items():
            if rules:
                field_info = self.field_id_to_info.get(field_id, {})
                output["fields_with_rules"].append({
                    "field_id": field_id,
                    "field_name": field_info.get("name", ""),
                    "formFillRules": rules,
                })
                self.stats["rules_generated"] += len(rules)

        return output

    def _print_stats(self):
        """Print extraction statistics."""
        print("\n" + "=" * 60)
        print("Extraction Statistics")
        print("=" * 60)
        print(f"  Total fields:              {self.stats['total_fields']}")
        print(f"  Fields with logic:         {self.stats['fields_with_logic']}")
        print(f"  Skipped expression rules:  {self.stats['skipped_expression_rules']}")
        print(f"  Rules generated:           {self.stats['rules_generated']}")
        print(f"    - OCR rules:             {self.stats['ocr_rules']}")
        print(f"    - VERIFY rules:          {self.stats['verify_rules']}")
        print(f"    - Visibility rules:      {self.stats['visibility_rules']}")
        print(f"    - Mandatory rules:       {self.stats['mandatory_rules']}")
        print(f"    - Disabled rules:        {self.stats['disabled_rules']}")
        print(f"    - EXT_DROP_DOWN rules:   {self.stats['ext_dropdown_rules']}")
        print(f"    - COPY_TO rules:         {self.stats['copy_rules']}")
        print(f"    - CONVERT_TO rules:      {self.stats['convert_rules']}")
        print("=" * 60)


def main():
    """Main entry point."""
    agent = RuleExtractionAgent()

    # Run extraction
    result = agent.run()

    # Save output
    print(f"\nSaving output to: {OUTPUT_PATH}")
    save_json_file(OUTPUT_PATH, result)

    print("\nDone!")
    return result


if __name__ == "__main__":
    main()
