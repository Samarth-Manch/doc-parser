#!/usr/bin/env python3
"""
Rule Extraction Agent - Main entry point.

Extracts rules from BUD document and populates formFillRules in schema JSON.

Usage:
    python rule_extraction_agent.py \
        --bud "documents/Vendor Creation Sample BUD.docx" \
        --intra-panel "adws/2026-01-30_20-06-02/intra_panel_references.json" \
        --output "adws/2026-01-30_20-06-02/populated_schema.json" \
        --verbose
"""

import argparse
import json
import logging
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass, field

# Add paths for imports
_script_dir = Path(__file__).parent.resolve()
_project_root = _script_dir.parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_script_dir))

from doc_parser import DocumentParser
from doc_parser.models import FieldDefinition

# Import from local rule_extraction_agent package (not the one in project root)
import rule_extraction_agent as rea
from rule_extraction_agent.schema_lookup import RuleSchemaLookup
from rule_extraction_agent.logic_parser import LogicParser, extract_controlling_field_name
from rule_extraction_agent.field_matcher import FieldMatcher, build_field_index_from_parsed
from rule_extraction_agent.models import (
    FieldInfo,
    GeneratedRule,
    ParsedLogic,
)
from rule_extraction_agent.rule_builders import (
    BaseRuleBuilder,
    VisibilityRuleBuilder,
    VerifyRuleBuilder,
    OcrRuleBuilder,
    ExtDropdownRuleBuilder,
)
from rule_extraction_agent.rule_builders.base_builder import get_rule_id, reset_rule_ids
from rule_extraction_agent.rule_builders.ocr_builder import link_ocr_to_verify_rules
from rule_extraction_agent.rule_builders.visibility_builder import VisibilityGroupCollector
from rule_extraction_agent.rule_builders.ext_dropdown_builder import (
    detect_cascading_relationships,
    extract_params_from_logic,
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ExtractionContext:
    """Context for rule extraction."""
    fields: List[FieldInfo]
    field_by_name: Dict[str, FieldInfo]
    field_by_id: Dict[int, FieldInfo]
    schema_lookup: RuleSchemaLookup
    logic_parser: LogicParser
    field_matcher: FieldMatcher

    # Collected rules by type
    ocr_rules: List[GeneratedRule] = field(default_factory=list)
    verify_rules: List[GeneratedRule] = field(default_factory=list)
    visibility_rules: List[GeneratedRule] = field(default_factory=list)
    mandatory_rules: List[GeneratedRule] = field(default_factory=list)
    disabled_rules: List[GeneratedRule] = field(default_factory=list)
    ext_dropdown_rules: List[GeneratedRule] = field(default_factory=list)
    other_rules: List[GeneratedRule] = field(default_factory=list)

    # Track rule assignments to fields
    rules_by_field_id: Dict[int, List[GeneratedRule]] = field(default_factory=lambda: defaultdict(list))

    # Track visibility controlling fields
    visibility_groups: VisibilityGroupCollector = field(default_factory=VisibilityGroupCollector)

    # Track disabled fields for consolidation
    disabled_field_ids: List[int] = field(default_factory=list)

    # RuleCheck field ID (for consolidated disabled rules)
    rulecheck_field_id: Optional[int] = None


class RuleExtractionAgent:
    """
    Main agent for extracting rules from BUD documents.

    Implements a multi-pass approach:
    1. Parse BUD document
    2. First pass: Identify controlling fields (visibility sources)
    3. Second pass: Generate rules for each field
    4. Third pass: Link OCR -> VERIFY chains
    5. Fourth pass: Consolidate and deduplicate
    """

    def __init__(
        self,
        bud_path: str,
        schema_path: str = None,
        intra_panel_path: str = None,
        verbose: bool = False
    ):
        """
        Initialize the rule extraction agent.

        Args:
            bud_path: Path to the BUD .docx document
            schema_path: Path to Rule-Schemas.json (optional)
            intra_panel_path: Path to intra-panel references JSON (optional)
            verbose: Enable verbose logging
        """
        self.bud_path = bud_path
        self.schema_path = schema_path
        self.intra_panel_path = intra_panel_path
        self.verbose = verbose

        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Initialize components
        self.doc_parser = DocumentParser()
        self.schema_lookup = RuleSchemaLookup(schema_path) if schema_path else RuleSchemaLookup()
        self.logic_parser = LogicParser()

        # Rule builders
        self.visibility_builder = VisibilityRuleBuilder()
        self.verify_builder = VerifyRuleBuilder(self.schema_lookup)
        self.ocr_builder = OcrRuleBuilder(self.schema_lookup)
        self.ext_dropdown_builder = ExtDropdownRuleBuilder()

        # Parsed data
        self.parsed_doc = None
        self.intra_panel_refs = None
        self.context: Optional[ExtractionContext] = None

    def extract(self) -> Dict[str, Any]:
        """
        Extract rules from BUD document.

        Returns:
            Dictionary with extraction results and generated rules
        """
        logger.info(f"Parsing BUD document: {self.bud_path}")

        # Step 1: Parse BUD document
        self.parsed_doc = self.doc_parser.parse(self.bud_path)

        # Load intra-panel references if available
        if self.intra_panel_path and Path(self.intra_panel_path).exists():
            with open(self.intra_panel_path) as f:
                self.intra_panel_refs = json.load(f)
            logger.info(f"Loaded intra-panel references from {self.intra_panel_path}")

        # Step 2: Build field index
        fields = build_field_index_from_parsed(self.parsed_doc.all_fields)
        field_by_name = {f.name.lower(): f for f in fields}
        field_by_id = {f.id: f for f in fields}

        self.field_matcher = FieldMatcher(fields)

        # Initialize extraction context
        self.context = ExtractionContext(
            fields=fields,
            field_by_name=field_by_name,
            field_by_id=field_by_id,
            schema_lookup=self.schema_lookup,
            logic_parser=self.logic_parser,
            field_matcher=self.field_matcher,
        )

        # Find or create RuleCheck field for consolidated disabled rules
        self._find_or_create_rulecheck_field()

        logger.info(f"Extracted {len(fields)} fields from BUD")

        # Step 3: First pass - Identify visibility controlling fields
        self._identify_visibility_sources()

        # Step 4: Second pass - Generate rules for each field
        self._generate_field_rules()

        # Step 5: Third pass - Link OCR -> VERIFY chains
        self._link_rule_chains()

        # Step 6: Fourth pass - Consolidate visibility rules
        self._consolidate_visibility_rules()

        # Step 7: Fifth pass - Consolidate disabled rules
        self._consolidate_disabled_rules()

        # Step 8: Generate EXT_DROP_DOWN rules
        self._generate_ext_dropdown_rules()

        # Step 9: Build final output
        return self._build_output()

    def _find_or_create_rulecheck_field(self):
        """Find existing RuleCheck field or use first field as control."""
        for field in self.context.fields:
            if 'rulecheck' in field.name.lower():
                self.context.rulecheck_field_id = field.id
                logger.debug(f"Found RuleCheck field: {field.name} (ID: {field.id})")
                return

        # Use first field as control if no RuleCheck found
        if self.context.fields:
            self.context.rulecheck_field_id = self.context.fields[0].id
            logger.debug(f"Using first field as control: {self.context.fields[0].name}")

    def _identify_visibility_sources(self):
        """First pass: Identify fields that control visibility of others."""
        logger.info("Pass 1: Identifying visibility controlling fields")

        for field in self.context.fields:
            logic = field.logic or ''
            if not logic:
                continue

            # Extract controlling field name from logic
            controlling_name = extract_controlling_field_name(logic)
            if controlling_name:
                # Find the controlling field
                controlling_field = self.field_matcher.match_field(controlling_name)
                if controlling_field:
                    # Extract conditional values
                    parsed = self.logic_parser.parse(logic, field.name, field.field_type)

                    # Determine what values trigger visibility
                    conditional_values = []
                    for cond in parsed.conditions:
                        conditional_values.extend(cond.values)

                    if not conditional_values:
                        # Try to extract from common patterns
                        values, _ = self.logic_parser.extract_conditional_values(logic)
                        conditional_values = values if values else ["yes"]

                    # Add to visibility group
                    is_mandatory = parsed.is_mandatory or "mandatory" in logic.lower()
                    self.context.visibility_groups.add_visibility_reference(
                        controlling_field_name=controlling_name,
                        destination_field_id=field.id,
                        conditional_values=conditional_values,
                        is_mandatory=is_mandatory
                    )

                    logger.debug(f"  {field.name} controlled by '{controlling_name}' when = {conditional_values}")

    def _generate_field_rules(self):
        """Second pass: Generate rules for each field based on logic."""
        logger.info("Pass 2: Generating rules for each field")

        for field in self.context.fields:
            logic = field.logic or ''

            # Skip if no logic or should skip (expression rules)
            if not logic or self.logic_parser.should_skip(logic):
                continue

            # Parse the logic
            parsed = self.logic_parser.parse(logic, field.name, field.field_type)

            # Generate rules based on parsed logic
            self._generate_rules_for_field(field, parsed)

    def _generate_rules_for_field(self, field: FieldInfo, parsed: ParsedLogic):
        """Generate rules for a single field based on parsed logic."""

        # 1. Check for OCR
        if parsed.is_ocr or self._is_file_upload_with_ocr(field, parsed):
            self._generate_ocr_rule(field, parsed)

        # 2. Check for VERIFY (but NOT destination fields)
        if parsed.is_verify and not parsed.is_destination_only:
            self._generate_verify_rule(field, parsed)

        # 3. Check for MAKE_DISABLED
        if parsed.is_disabled:
            self.context.disabled_field_ids.append(field.id)
            logger.debug(f"  {field.name}: marked for MAKE_DISABLED")

        # Note: Visibility rules are handled in _consolidate_visibility_rules

    def _is_file_upload_with_ocr(self, field: FieldInfo, parsed: ParsedLogic) -> bool:
        """Check if this is a file upload field that should have OCR."""
        if field.field_type.upper() != 'FILE':
            return False

        # Check field name patterns
        ocr_source = self.logic_parser.detect_ocr_source_type(parsed.original_text, field.name)
        return ocr_source is not None

    def _generate_ocr_rule(self, field: FieldInfo, parsed: ParsedLogic):
        """Generate OCR rule for a file upload field."""
        source_type = self.logic_parser.detect_ocr_source_type(parsed.original_text, field.name)
        if not source_type:
            return

        # Find destination field (the text field to populate)
        dest_field = self._find_ocr_destination(field, source_type)
        if not dest_field:
            logger.warning(f"  {field.name}: Could not find OCR destination field")
            return

        # Build OCR rule
        rule = self.ocr_builder.build_ocr_rule(
            source_type=source_type,
            upload_field_id=field.id,
            output_field_id=dest_field.id,
            post_trigger_ids=[]  # Will be linked later
        )

        self.context.ocr_rules.append(rule)
        self.context.rules_by_field_id[field.id].append(rule)
        logger.debug(f"  {field.name}: Generated OCR rule ({source_type}) -> {dest_field.name}")

    def _find_ocr_destination(self, upload_field: FieldInfo, source_type: str) -> Optional[FieldInfo]:
        """Find the text field that OCR will populate."""
        # Pattern: "Upload PAN" -> "PAN"
        name_lower = upload_field.name.lower()

        # Extract target name
        target_patterns = [
            (r"upload\s+(.+)", 1),
            (r"(.+)\s+image", 1),
            (r"(.+)\s+upload", 1),
            (r"(.+)\s+copy", 1),
        ]

        target_name = None
        for pattern, group in target_patterns:
            match = re.match(pattern, name_lower, re.IGNORECASE)
            if match:
                target_name = match.group(group).strip()
                break

        if not target_name:
            # Use source type to infer target
            type_to_name = {
                "PAN_IMAGE": "pan",
                "GSTIN_IMAGE": "gstin",
                "CHEQUEE": "ifsc",
                "MSME": "msme registration number",
                "CIN": "cin",
            }
            target_name = type_to_name.get(source_type)

        if not target_name:
            return None

        # Find matching field
        match = self.field_matcher.match_field(target_name)
        if match and match.field_type.upper() in ['TEXT', 'NUMBER', 'MASKED_FIELD']:
            return match

        # Try nearby fields
        nearby = self.field_matcher.find_nearby_fields(upload_field.id, count=10, direction="after")
        for field in nearby:
            if target_name in field.name.lower() and field.field_type.upper() in ['TEXT', 'NUMBER', 'MASKED_FIELD']:
                return field

        return None

    def _generate_verify_rule(self, field: FieldInfo, parsed: ParsedLogic):
        """Generate VERIFY rule for a validation field."""
        source_type = self.logic_parser.detect_verify_source_type(parsed.original_text, field.name)
        if not source_type:
            return

        # Find destination fields for this verify rule
        field_mappings = self._find_verify_destinations(field, source_type)

        # Special case for BANK_ACCOUNT_NUMBER (needs IFSC + Account Number)
        if source_type == "BANK_ACCOUNT_NUMBER":
            rule = self._generate_bank_verify_rule(field, field_mappings)
        else:
            rule = self.verify_builder.build_verify_rule(
                source_type=source_type,
                source_field_id=field.id,
                field_mappings=field_mappings,
                post_trigger_ids=[]
            )

        if rule:
            self.context.verify_rules.append(rule)
            self.context.rules_by_field_id[field.id].append(rule)
            logger.debug(f"  {field.name}: Generated VERIFY rule ({source_type})")

            # Check for GSTIN_WITH_PAN cross-validation
            if source_type == "GSTIN" and self._should_add_gstin_pan_rule(field):
                self._generate_gstin_pan_rule(field)

    def _find_verify_destinations(self, source_field: FieldInfo, source_type: str) -> Dict[str, int]:
        """Find destination fields for VERIFY rule based on schema."""
        schema_info = self.schema_lookup.get_schema_info(source_type)
        if not schema_info:
            return {}

        # Get nearby fields
        nearby = self.field_matcher.find_nearby_fields(source_field.id, count=30, direction="after")

        # Map schema field names to BUD field IDs
        mappings = {}
        for dest_field in schema_info.destination_fields:
            # Try to find matching BUD field
            for field in nearby:
                # Check if field logic indicates it's a destination
                if field.logic and "data will come from" in field.logic.lower():
                    similarity = self.field_matcher._calculate_similarity(
                        self.field_matcher._normalize_name(dest_field.name),
                        self.field_matcher._normalize_name(field.name)
                    )
                    if similarity >= 0.5:
                        mappings[dest_field.name] = field.id
                        break

        return mappings

    def _generate_bank_verify_rule(self, field: FieldInfo, field_mappings: Dict[str, int]) -> Optional[GeneratedRule]:
        """Generate Bank Account VERIFY rule which requires both IFSC and Account Number."""
        # Find IFSC and Account Number fields
        ifsc_field = None
        account_field = None

        for f in self.context.fields:
            name_lower = f.name.lower()
            if 'ifsc' in name_lower:
                ifsc_field = f
            elif 'account' in name_lower and 'number' in name_lower:
                account_field = f

        if not ifsc_field or not account_field:
            logger.warning(f"  {field.name}: Could not find IFSC/Account Number fields for Bank VERIFY")
            return None

        return self.verify_builder.build_bank_verify_rule(
            ifsc_field_id=ifsc_field.id,
            account_field_id=account_field.id,
            field_mappings=field_mappings
        )

    def _should_add_gstin_pan_rule(self, gstin_field: FieldInfo) -> bool:
        """Check if GSTIN_WITH_PAN cross-validation should be added."""
        logic = gstin_field.logic or ''
        return 'pan with gst' in logic.lower() or 'pan' in logic.lower()

    def _generate_gstin_pan_rule(self, gstin_field: FieldInfo):
        """Generate GSTIN_WITH_PAN cross-validation rule."""
        # Find PAN field
        pan_field = self.field_matcher.match_field("PAN")
        if not pan_field:
            return

        rule = self.verify_builder.build_gstin_with_pan_rule(
            pan_field_id=pan_field.id,
            gstin_field_id=gstin_field.id
        )

        self.context.verify_rules.append(rule)
        logger.debug(f"  Generated GSTIN_WITH_PAN cross-validation rule")

    def _link_rule_chains(self):
        """Third pass: Link OCR rules to VERIFY rules via postTriggerRuleIds."""
        logger.info("Pass 3: Linking OCR -> VERIFY rule chains")

        link_ocr_to_verify_rules(
            self.context.ocr_rules,
            self.context.verify_rules
        )

        # Log the links
        for rule in self.context.ocr_rules:
            if rule.post_trigger_rule_ids:
                logger.debug(f"  OCR rule {rule.id} ({rule.source_type}) -> VERIFY rules {rule.post_trigger_rule_ids}")

    def _consolidate_visibility_rules(self):
        """Fourth pass: Consolidate visibility rules by controlling field."""
        logger.info("Pass 4: Consolidating visibility rules")

        # Build field name to ID mapping
        field_name_to_id = {}
        for field in self.context.fields:
            field_name_to_id[field.name.lower()] = field.id
            field_name_to_id[field.name] = field.id

        # Generate consolidated visibility rules
        rules = self.context.visibility_groups.get_grouped_rules(field_name_to_id)

        for rule in rules:
            if rule.action_type in ["MAKE_VISIBLE", "MAKE_INVISIBLE"]:
                self.context.visibility_rules.append(rule)
            elif rule.action_type in ["MAKE_MANDATORY", "MAKE_NON_MANDATORY"]:
                self.context.mandatory_rules.append(rule)

            # Add to the controlling field's rules
            if rule.source_ids:
                self.context.rules_by_field_id[rule.source_ids[0]].append(rule)

        logger.debug(f"  Generated {len(self.context.visibility_rules)} visibility rules")
        logger.debug(f"  Generated {len(self.context.mandatory_rules)} mandatory rules")

    def _consolidate_disabled_rules(self):
        """Fifth pass: Create consolidated MAKE_DISABLED rule."""
        logger.info("Pass 5: Consolidating MAKE_DISABLED rules")

        if not self.context.disabled_field_ids:
            return

        if not self.context.rulecheck_field_id:
            logger.warning("  No RuleCheck field found, skipping disabled rule consolidation")
            return

        # Create single consolidated rule
        rule = self.visibility_builder.build_disabled_rule_consolidated(
            rulecheck_field_id=self.context.rulecheck_field_id,
            destination_ids=list(set(self.context.disabled_field_ids))
        )

        self.context.disabled_rules.append(rule)
        self.context.rules_by_field_id[self.context.rulecheck_field_id].append(rule)

        logger.debug(f"  Created consolidated MAKE_DISABLED rule with {len(self.context.disabled_field_ids)} destinations")

    def _generate_ext_dropdown_rules(self):
        """Generate EXT_DROP_DOWN rules for external/cascading dropdowns."""
        logger.info("Pass 6: Generating EXT_DROP_DOWN rules")

        # Detect cascading relationships from intra-panel references
        if self.intra_panel_refs:
            self._process_intra_panel_dropdowns()

        # Detect from field logic
        fields_with_logic = [
            {'name': f.name, 'logic': f.logic, 'field_type': f.field_type}
            for f in self.context.fields
        ]
        cascades = detect_cascading_relationships(fields_with_logic)

        for parent_name, child_name in cascades:
            parent_field = self.field_matcher.match_field(parent_name)
            child_field = self.field_matcher.match_field(child_name)

            if parent_field and child_field:
                # Extract params from child logic
                child_logic = next(
                    (f.logic for f in self.context.fields if f.id == child_field.id),
                    ""
                )
                params = extract_params_from_logic(child_logic or "")

                rule = self.ext_dropdown_builder.build_cascading_dropdown_rule(
                    parent_field_id=parent_field.id,
                    child_field_id=child_field.id,
                    params=params
                )
                self.context.ext_dropdown_rules.append(rule)
                self.context.rules_by_field_id[parent_field.id].append(rule)
                logger.debug(f"  Generated cascading dropdown: {parent_name} -> {child_name}")

        # Generate standalone EXT_DROP_DOWN rules for external dropdown fields
        for field in self.context.fields:
            if field.field_type.upper() in ['EXTERNAL_DROP_DOWN_VALUE', 'EXTERNAL_DROP_DOWN_MULTISELECT']:
                # Check if already has a rule
                existing = [r for r in self.context.ext_dropdown_rules if field.id in r.source_ids]
                if not existing:
                    params = extract_params_from_logic(field.logic or "")
                    rule = self.ext_dropdown_builder.build_ext_dropdown_rule(
                        field_id=field.id,
                        params=params
                    )
                    self.context.ext_dropdown_rules.append(rule)
                    self.context.rules_by_field_id[field.id].append(rule)

        logger.debug(f"  Generated {len(self.context.ext_dropdown_rules)} EXT_DROP_DOWN rules")

    def _process_intra_panel_dropdowns(self):
        """Process intra-panel references for dropdown relationships."""
        if not self.intra_panel_refs:
            return

        panels = self.intra_panel_refs.get('panel_results', [])
        for panel in panels:
            refs = panel.get('intra_panel_references', [])
            for ref in refs:
                # Check for dropdown filter relationships
                ref_type = ref.get('reference_type', '') or ref.get('dependency_type', '')
                if 'dropdown' in ref_type.lower() or 'filter' in ref_type.lower():
                    # Extract field names
                    dep_field = ref.get('dependent_field') or ref.get('source_field', {}).get('field_name')
                    ref_field = ref.get('referenced_field') or ref.get('depends_on_field')

                    if dep_field and ref_field:
                        parent = self.field_matcher.match_field(str(ref_field))
                        child = self.field_matcher.match_field(str(dep_field))

                        if parent and child:
                            params = extract_params_from_logic(ref.get('logic_description', ''))
                            rule = self.ext_dropdown_builder.build_cascading_dropdown_rule(
                                parent_field_id=parent.id,
                                child_field_id=child.id,
                                params=params
                            )
                            self.context.ext_dropdown_rules.append(rule)

    def _build_output(self) -> Dict[str, Any]:
        """Build the final output dictionary in reference-compatible format."""
        # Collect all rules
        all_rules = []
        all_rules.extend(self.context.ocr_rules)
        all_rules.extend(self.context.verify_rules)
        all_rules.extend(self.context.visibility_rules)
        all_rules.extend(self.context.mandatory_rules)
        all_rules.extend(self.context.disabled_rules)
        all_rules.extend(self.context.ext_dropdown_rules)
        all_rules.extend(self.context.other_rules)

        # Build rule type counts
        rule_type_counts = defaultdict(int)
        for rule in all_rules:
            rule_type_counts[rule.action_type] += 1

        # Build formFillMetadatas array with rules embedded
        form_fill_metadatas = []
        for field in self.context.fields:
            field_rules = self.context.rules_by_field_id.get(field.id, [])

            metadata = {
                "id": field.id,
                "formTag": {
                    "id": field.id,  # Use field ID as formTag ID
                    "name": field.name,
                    "standardField": False,
                    "type": field.field_type.upper() if field.field_type else "TEXT"
                },
                "variableName": f"_{field.name.lower().replace(' ', '_')[:8]}_{field.id % 100}_",
                "mandatory": False,
                "editable": True,
                "visible": True,
                "formFillRules": [r.to_dict() for r in field_rules]
            }
            form_fill_metadatas.append(metadata)

        # Build reference-compatible output structure
        output = {
            "template": {
                "id": 1,  # Placeholder template ID
                "templateName": Path(self.bud_path).stem.replace("_", " ").title(),
                "documentTypes": [
                    {
                        "id": 1,
                        "formFillMetadatas": form_fill_metadatas
                    }
                ]
            },
            "extraction_info": {
                "bud_document": self.bud_path,
                "total_fields": len(self.context.fields),
                "fields_with_logic": sum(1 for f in self.context.fields if f.logic),
                "total_rules_generated": len(all_rules),
                "rule_type_distribution": dict(rule_type_counts),
            },
            "rules_by_field": {},
            "all_rules": [r.to_dict() for r in all_rules],
        }

        # Group rules by field name for easy lookup
        for field_id, rules in self.context.rules_by_field_id.items():
            field = self.context.field_by_id.get(field_id)
            if field and rules:
                output["rules_by_field"][field.name] = [r.to_dict() for r in rules]

        return output

    def populate_schema(self, base_schema: Dict) -> Dict:
        """
        Populate a base schema JSON with extracted rules.

        Args:
            base_schema: Base schema JSON structure

        Returns:
            Schema with formFillRules populated
        """
        # Extract rules first
        extraction_result = self.extract()

        # Deep copy the schema
        import copy
        populated = copy.deepcopy(base_schema)

        # Find formFillMetadatas
        doc_types = populated.get('template', {}).get('documentTypes', [])
        if not doc_types:
            logger.warning("No documentTypes found in schema")
            return populated

        metadatas = doc_types[0].get('formFillMetadatas', [])

        # Build metadata ID -> index mapping
        meta_by_id = {m.get('id'): i for i, m in enumerate(metadatas)}

        # Populate rules
        for field_id, rules in self.context.rules_by_field_id.items():
            if field_id in meta_by_id:
                idx = meta_by_id[field_id]
                metadatas[idx]['formFillRules'] = [r.to_dict() for r in rules]

        return populated


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract rules from BUD document and populate formFillRules"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to BUD .docx document"
    )
    parser.add_argument(
        "--schema-rules",
        default=None,
        help="Path to Rule-Schemas.json"
    )
    parser.add_argument(
        "--intra-panel",
        default=None,
        help="Path to intra-panel references JSON"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for populated schema JSON"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Path to save extraction report"
    )

    args = parser.parse_args()

    # Reset rule IDs for fresh extraction
    reset_rule_ids(200000)

    # Create agent
    agent = RuleExtractionAgent(
        bud_path=args.bud,
        schema_path=args.schema_rules,
        intra_panel_path=args.intra_panel,
        verbose=args.verbose
    )

    # Extract rules
    result = agent.extract()

    # Save output
    output_path = args.output
    if not output_path:
        output_path = Path(args.bud).stem + "_rules.json"

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    logger.info(f"Saved extraction results to {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("RULE EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"BUD Document: {args.bud}")
    print(f"Total Fields: {result['extraction_info']['total_fields']}")
    print(f"Fields with Logic: {result['extraction_info']['fields_with_logic']}")
    print(f"Total Rules Generated: {result['extraction_info']['total_rules_generated']}")
    print("\nRule Type Distribution:")
    for rule_type, count in sorted(result['extraction_info']['rule_type_distribution'].items()):
        print(f"  {rule_type}: {count}")
    print("=" * 60)

    # Save report if requested
    if args.report:
        with open(args.report, 'w') as f:
            json.dump({
                "summary": result['extraction_info'],
                "rules_by_field_count": {k: len(v) for k, v in result['rules_by_field'].items()},
            }, f, indent=2)
        logger.info(f"Saved report to {args.report}")


if __name__ == "__main__":
    main()
