"""Main rule extraction pipeline - Enhanced version with comprehensive rule extraction."""

import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from datetime import datetime

from .models import id_generator, FieldInfo
from .schema_lookup import RuleSchemaLookup, OCR_VERIFY_CHAINS, VERIFY_SCHEMAS, OCR_SCHEMAS
from .id_mapper import DestinationIdMapper
from .field_matcher import FieldMatcher
from .logic_parser import LogicParser
from .rule_tree import RuleTree, VisibilityGrouper
from .matchers.pipeline import MatchingPipeline, VisibilityRuleGrouper
from .rule_builders.standard_builder import StandardRuleBuilder
from .rule_builders.verify_builder import VerifyRuleBuilder
from .rule_builders.ocr_builder import OcrRuleBuilder
from .rule_builders.validation_builder import ValidationRuleBuilder
from .rule_builders.copy_to_builder import CopyToRuleBuilder
from .rule_consolidator import RuleConsolidator
from .llm_fallback import LLMFallback, RuleValidator


# OCR field patterns - maps field name patterns to OCR source type
OCR_FIELD_PATTERNS = [
    (r"upload\s*pan|pan\s*(?:image|upload|file|copy)", "PAN_IMAGE"),
    (r"gstin\s*image|upload\s*gstin|gst\s*image", "GSTIN_IMAGE"),
    (r"aadhaa?r\s*front|front\s*aadhaa?r|aadhaa?r\s*image", "AADHAR_IMAGE"),
    (r"aadhaa?r\s*back|back\s*aadhaa?r|aadhaa?r\s*back\s*image", "AADHAR_BACK_IMAGE"),
    (r"cancelled?\s*cheque|cheque\s*(?:image|copy)", "CHEQUEE"),
    (r"cin\s*(?:certificate|image|copy|upload)", "CIN"),
    (r"msme\s*(?:image|certificate|copy|upload)", "MSME"),
]

# VERIFY field patterns - maps field name patterns to VERIFY source type
# These are STRICT patterns that only match the actual data input fields, not panels or labels
VERIFY_FIELD_PATTERNS = [
    (r"^pan$", "PAN_NUMBER"),  # Exact match for PAN field (not "PAN Type", "Upload PAN", etc.)
    (r"^gstin$", "GSTIN"),  # Exact match for GSTIN field
    (r"^bank\s*account\s*number$", "BANK_ACCOUNT_NUMBER"),  # Exact match
    (r"^msme\s*registration\s*number$", "MSME_UDYAM_REG_NUMBER"),  # Exact match
]

# Fields that should have CONVERT_TO UPPER_CASE rule
UPPERCASE_FIELD_PATTERNS = [
    r"^pan$",
    r"^gstin$",
    r"ifsc\s*code",
    r"street",
    r"^e\d$",  # E4, E5, E6
    r"email",
    r"name.*holder|holder.*name",
    r"bank\s*(?:name|branch|address)",
    r"registration\s*number",
    r"vendor\s*contact\s*(?:name|email)",
    r"city.*import|district.*import",
    r"fda\s*registration",
    r"central\s*enrolment",
    r"ifsc.*swift.*bank",
]

# Fields with OCR that should be disabled after OCR
OCR_DISABLED_FIELDS = [
    "GSTIN IMAGE",
    "MSME Image",
    "MSME Registration Number",
]


class RuleExtractionAgent:
    """Main agent for extracting rules from BUD documents."""

    def __init__(
        self,
        schema_path: str = None,
        llm_threshold: float = 0.7,
        verbose: bool = False,
        validate: bool = False,
        edv_tables_path: str = None,
        field_edv_mapping_path: str = None
    ):
        # Initialize components
        self.schema_lookup = RuleSchemaLookup(schema_path)
        self.id_mapper = DestinationIdMapper(self.schema_lookup)
        self.field_matcher = FieldMatcher()
        self.logic_parser = LogicParser()
        self.rule_tree = RuleTree()
        self.pipeline = MatchingPipeline(self.schema_lookup, self.field_matcher, llm_threshold)

        # Builders
        self.standard_builder = StandardRuleBuilder()
        self.verify_builder = VerifyRuleBuilder(self.schema_lookup, self.id_mapper)
        self.ocr_builder = OcrRuleBuilder(self.schema_lookup)
        self.validation_builder = ValidationRuleBuilder(verbose)
        self.copy_to_builder = CopyToRuleBuilder(verbose)

        # Consolidator
        self.consolidator = RuleConsolidator(verbose)

        # LLM fallback
        self.llm_fallback = LLMFallback()
        self.llm_threshold = llm_threshold

        # Validator
        self.validator = RuleValidator(self.schema_lookup)

        # Options
        self.verbose = verbose
        self.validate = validate

        # EDV tables and mappings
        self.edv_tables = {}
        self.field_edv_mappings = {}
        if edv_tables_path:
            with open(edv_tables_path, 'r') as f:
                edv_data = json.load(f)
                self.edv_tables = edv_data
        if field_edv_mapping_path:
            with open(field_edv_mapping_path, 'r') as f:
                edv_mapping_data = json.load(f)
                self.field_edv_mappings = {
                    m['field_name'].lower(): m
                    for m in edv_mapping_data.get('field_edv_mappings', [])
                }

        # Statistics
        self.stats = {
            "total_fields": 0,
            "fields_with_rules": 0,
            "total_rules_generated": 0,
            "rules_by_type": defaultdict(int),
            "llm_fallback_used": 0,
            "validation_errors": 0,
        }

    def process(
        self,
        schema_json_path: str,
        intra_panel_path: str,
        output_path: str = None
    ) -> Dict:
        """
        Process schema and intra-panel references to generate rules.

        Args:
            schema_json_path: Path to schema JSON from extract_fields_complete.py
            intra_panel_path: Path to intra-panel references JSON
            output_path: Output path for populated schema (optional)

        Returns:
            Dict with populated schema and statistics
        """
        # Reset ID generator and stats
        id_generator.reset()
        self.stats = {
            "total_fields": 0,
            "fields_with_rules": 0,
            "total_rules_generated": 0,
            "rules_by_type": defaultdict(int),
            "llm_fallback_used": 0,
            "validation_errors": 0,
        }

        # Load inputs
        with open(schema_json_path, 'r') as f:
            schema = json.load(f)

        with open(intra_panel_path, 'r') as f:
            intra_panel = json.load(f)

        # Extract fields from schema
        all_fields = self._extract_fields_from_schema(schema)
        self.field_matcher.load_fields(all_fields)
        self.stats["total_fields"] = len(all_fields)

        if self.verbose:
            print(f"Loaded {len(all_fields)} fields from schema")

        # Find or create RuleCheck control field
        rulecheck_field_id = self._find_or_create_rulecheck_field(all_fields)
        if rulecheck_field_id:
            self.consolidator.set_rulecheck_field_id(rulecheck_field_id)
            if self.verbose:
                print(f"RuleCheck field ID: {rulecheck_field_id}")

        # Extract intra-panel references
        intra_refs = self._extract_intra_refs(intra_panel)

        if self.verbose:
            print(f"Loaded {len(intra_refs)} intra-panel references")

        # Phase 1: Parse BUD document to get field logic
        print("\n=== Phase 1: Parsing BUD document ===")
        bud_field_logic = self._parse_bud_document()

        # Phase 1.5: Identify visibility controlling fields from BUD logic
        visibility_groups_from_bud = self._extract_visibility_from_bud_logic(all_fields, bud_field_logic)

        # Phase 1.6: Identify visibility controlling fields from intra-panel refs
        visibility_groups_from_refs = self._identify_visibility_groups(all_fields, intra_refs)

        # Merge both sources
        visibility_groups = self._merge_visibility_groups(visibility_groups_from_bud, visibility_groups_from_refs)

        if self.verbose:
            print(f"Found {len(visibility_groups)} controlling fields with {sum(len(v) for v in visibility_groups.values())} dependencies")

        # Phase 2: Generate rules for each field
        all_generated_rules = []
        field_rules_map = {}  # field_id -> list of rules

        for field in all_fields:
            field_id = field.get('id')
            field_name = field.get('formTag', {}).get('name', '')

            # Get logic from BUD document (priority) or intra-panel refs (fallback)
            logic_text = bud_field_logic.get(field_name.lower(), '') or self._get_field_logic(field_name, intra_refs)

            # Check if this field is a controlling field (visibility source)
            controlling_key = field_name.lower()
            is_controlling_field = controlling_key in visibility_groups

            # Skip fields with no logic AND that don't control other fields
            if not logic_text and not is_controlling_field:
                continue

            # Generate rules
            rules = self._generate_rules_for_field(
                field, logic_text, visibility_groups, all_fields, intra_refs
            )

            if rules:
                field_rules_map[field_id] = rules
                all_generated_rules.extend(rules)
                self.stats["fields_with_rules"] += 1

        # Phase 3: Generate OCR and VERIFY rules from data_population references
        data_pop_rules = self._generate_ocr_verify_from_refs(intra_refs, field_rules_map)
        all_generated_rules.extend(data_pop_rules)

        # Phase 3b: Generate ALL OCR rules based on field names (comprehensive scan)
        ocr_rules = self._generate_all_ocr_rules(all_fields, field_rules_map)
        all_generated_rules.extend(ocr_rules)

        # Phase 3c: Generate ALL VERIFY rules based on field names (comprehensive scan)
        verify_rules = self._generate_all_verify_rules(all_fields, intra_refs, field_rules_map)
        all_generated_rules.extend(verify_rules)

        # Phase 3d: Generate CONVERT_TO rules for uppercase fields
        convert_rules = self._generate_convert_to_rules(all_fields, field_rules_map)
        all_generated_rules.extend(convert_rules)

        # Phase 3e: Generate EDV rules (EXT_DROP_DOWN and EXT_VALUE)
        if self.field_edv_mappings:
            edv_rules = self._generate_edv_rules(all_fields, field_rules_map)
            all_generated_rules.extend(edv_rules)

        # Phase 3f: Generate VALIDATION rules
        validation_rules = self._generate_validation_rules(all_fields, intra_refs, field_rules_map)
        all_generated_rules.extend(validation_rules)

        # Phase 3g: Generate COPY_TO rules
        copy_to_rules = self._generate_copy_to_rules(all_fields, intra_refs, field_rules_map)
        all_generated_rules.extend(copy_to_rules)

        # Phase 4: Link OCR -> VERIFY chains
        self._link_ocr_verify_chains(all_generated_rules)

        # Phase 5: Consolidate rules
        consolidated_rules = self._consolidate_rules(all_generated_rules)
        self.stats["total_rules_generated"] = len(consolidated_rules)

        # Count rules by type
        for rule in consolidated_rules:
            action = rule.get('actionType', 'UNKNOWN')
            self.stats["rules_by_type"][action] += 1

        # Phase 5.5: Rebuild field_rules_map from consolidated rules
        # CRITICAL: After consolidation, we need to update the field_rules_map
        # because some rules may have been merged or their IDs changed
        field_rules_map = self._rebuild_field_rules_map(consolidated_rules)

        # Phase 6: Validate if requested
        if self.validate:
            issues = self.validator.validate_rules(consolidated_rules)
            self.stats["validation_errors"] = len(issues)

        # Update schema with rules
        self._populate_schema_with_rules(schema, field_rules_map)

        # Save output
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(schema, f, indent=2)

            if self.verbose:
                print(f"Saved populated schema to {output_path}")

        return {
            "schema": schema,
            "stats": dict(self.stats),
            "rules": consolidated_rules,
        }

    def _extract_fields_from_schema(self, schema: Dict) -> List[Dict]:
        """Extract formFillMetadatas from schema."""
        fields = []

        doc_types = schema.get('template', {}).get('documentTypes', [])
        for doc_type in doc_types:
            ffms = doc_type.get('formFillMetadatas', [])
            fields.extend(ffms)

        return fields

    def _extract_intra_refs(self, intra_panel: Dict) -> List[Dict]:
        """Extract all intra-panel references."""
        refs = []

        panel_results = intra_panel.get('panel_results', [])
        for panel in panel_results:
            panel_refs = panel.get('intra_panel_references', [])
            refs.extend(panel_refs)

        return refs

    def _get_field_logic(self, field_name: str, intra_refs: List[Dict]) -> str:
        """Get combined logic text for a field from intra-panel references."""
        logic_parts = []
        field_name_lower = field_name.lower().strip()

        for ref in intra_refs:
            # Check if this field is the dependent field
            dependent = ref.get('dependent_field', '')
            if isinstance(dependent, str) and dependent.lower().strip() == field_name_lower:
                desc = ref.get('rule_description', '')
                if desc and isinstance(desc, str):
                    logic_parts.append(desc)

            # Check if this field is the source field
            source = ref.get('source_field', '')
            if isinstance(source, str) and source.lower().strip() == field_name_lower:
                desc = ref.get('dependency_description', '') or ref.get('logic_excerpt', '')
                if desc and isinstance(desc, str):
                    logic_parts.append(desc)

            # Check if this field is the target field
            target = ref.get('target_field', '')
            if isinstance(target, str) and target.lower().strip() == field_name_lower:
                desc = ref.get('dependency_description', '')
                if desc and isinstance(desc, str):
                    logic_parts.append(desc)

            # Check if this field is the referenced field
            referenced = ref.get('referenced_field', '')
            if isinstance(referenced, str) and referenced.lower().strip() == field_name_lower:
                desc = ref.get('rule_description', '')
                if desc and isinstance(desc, str):
                    logic_parts.append(desc)

        return ' '.join(logic_parts)

    def _identify_visibility_groups(
        self,
        all_fields: List[Dict],
        intra_refs: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Identify fields grouped by their controlling field - ENHANCED to parse unknown deps."""
        groups = defaultdict(list)

        for ref in intra_refs:
            dep_type = ref.get('dependency_type', ref.get('reference_type', ''))
            rule_desc = ref.get('rule_description', '')

            # Also check reference_details for relationship_type
            ref_details = ref.get('reference_details', {})
            if isinstance(ref_details, dict):
                detail_type = ref_details.get('relationship_type', '')
                if detail_type in ['visibility_control', 'mandatory_control']:
                    dep_type = detail_type

            # ENHANCEMENT: If dependency type is unknown, try to infer from rule description
            if dep_type == 'unknown' and rule_desc:
                rule_lower = rule_desc.lower()
                if 'visible' in rule_lower or 'invisible' in rule_lower:
                    if 'mandatory' in rule_lower:
                        dep_type = 'visibility_mandatory'
                    else:
                        dep_type = 'visibility'
                elif 'mandatory' in rule_lower and 'non-mandatory' in rule_lower:
                    dep_type = 'mandatory'
                elif 'editable' in rule_lower or 'non-editable' in rule_lower:
                    dep_type = 'conditional_behavior'

            # Check for visibility/mandatory dependencies
            if dep_type in ['visibility', 'visibility_mandatory', 'mandatory', 'conditional_behavior', 'visibility_control', 'mandatory_control', 'visibility_dependency']:
                # Handle different reference structures
                referenced_field = ref.get('referenced_field', '')
                dependent_field = ref.get('dependent_field', '')
                rule_desc = ref.get('rule_description', ref.get('dependency_description', ref.get('logic_excerpt', '')))

                # Check for source_field/target_field as dicts (MSME panel style)
                source_obj = ref.get('source_field', {})
                if isinstance(source_obj, dict) and source_obj.get('field_name'):
                    referenced_field = source_obj.get('field_name', '')
                elif isinstance(source_obj, str) and not referenced_field:
                    referenced_field = source_obj

                target_obj = ref.get('target_field', {})
                if isinstance(target_obj, dict) and target_obj.get('field_name'):
                    dependent_field = target_obj.get('field_name', '')
                elif isinstance(target_obj, str) and not dependent_field:
                    dependent_field = target_obj

                # Get rule description from reference_details if available
                if not rule_desc and ref_details:
                    rule_desc = ref_details.get('raw_expression', '')

                if referenced_field and dependent_field:
                    # Find dependent field ID
                    dep_field_info = self.field_matcher.match_field(dependent_field)

                    groups[referenced_field.lower()].append({
                        'dependent_field': dependent_field,
                        'dependent_field_id': dep_field_info.id if dep_field_info else None,
                        'dependency_type': dep_type,
                        'rule_description': rule_desc,
                    })

        return dict(groups)

    def _generate_ocr_verify_from_refs(
        self,
        intra_refs: List[Dict],
        field_rules_map: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Generate OCR and VERIFY rules from data_population references."""
        rules = []
        processed_ocr = set()  # Track processed OCR source fields
        processed_verify = set()  # Track processed VERIFY source fields

        for ref in intra_refs:
            ref_type = ref.get('reference_type', ref.get('dependency_type', ''))
            logic = ref.get('logic_excerpt', ref.get('rule_description', ref.get('dependency_description', '')))

            if not logic:
                continue

            logic_lower = logic.lower()

            # Check for OCR rules - both data_population type and ocr_extraction trigger type
            is_ocr = (ref_type == 'data_population' and 'ocr' in logic_lower)
            # Also check for trigger type patterns
            triggers = ref.get('triggers', [])
            for trigger in triggers:
                if trigger.get('trigger_type') == 'ocr_extraction':
                    is_ocr = True
                    break

            if is_ocr:
                source_name = ref.get('source_field', '')
                target_name = ref.get('target_field', '')

                # Handle different ref structures
                if isinstance(source_name, dict):
                    source_name = source_name.get('field_name', '')
                if isinstance(target_name, dict):
                    target_name = target_name.get('field_name', '')

                # Also check triggers for targets
                if not target_name and triggers:
                    for trigger in triggers:
                        if trigger.get('trigger_type') == 'ocr_extraction':
                            target_name = trigger.get('target_field', '')
                            break

                if source_name and target_name and source_name not in processed_ocr:
                    source_field = self.field_matcher.match_field(source_name)
                    target_field = self.field_matcher.match_field(target_name)

                    if source_field and target_field:
                        # Detect OCR source type
                        ocr_source = self._detect_ocr_type_from_name(source_name)
                        if ocr_source:
                            ocr_rule = self.ocr_builder.build(
                                source_type=ocr_source,
                                upload_field_id=source_field.id,
                                destination_field_ids=[target_field.id]
                            )
                            if ocr_rule:
                                rules.append(ocr_rule)

                                # Add to field rules map
                                if source_field.id not in field_rules_map:
                                    field_rules_map[source_field.id] = []
                                field_rules_map[source_field.id].append(ocr_rule)

                                processed_ocr.add(source_name)
                                self.stats["fields_with_rules"] += 1

            # Check for VERIFY rules (from source field that does validation)
            is_verify = ref_type == 'data_population' and ('validation' in logic_lower or 'verification' in logic_lower)
            # Also check cross_validation type
            if ref_type == 'cross_validation':
                is_verify = True

            if is_verify:
                source_name = ref.get('source_field', '')
                target_name = ref.get('target_field', '')

                if isinstance(source_name, dict):
                    source_name = source_name.get('field_name', '')
                if isinstance(target_name, dict):
                    target_name = target_name.get('field_name', '')

                # Special case: GSTIN_WITH_PAN cross-validation
                if ref_type == 'cross_validation':
                    source_lower = source_name.lower() if source_name else ''
                    target_lower = target_name.lower() if target_name else ''
                    is_gstin_pan_cross = (
                        ('pan' in source_lower and 'gstin' in target_lower) or
                        ('gstin' in source_lower and 'pan' in target_lower) or
                        ('pan with gst' in logic_lower) or
                        ('gstin' in logic_lower and 'pan' in logic_lower)
                    )

                    if is_gstin_pan_cross and 'GSTIN_WITH_PAN' not in processed_verify:
                        # Find PAN and GSTIN fields
                        pan_field = self.field_matcher.match_field('PAN')
                        gstin_field = self.field_matcher.match_field('GSTIN')

                        if pan_field and gstin_field:
                            # GSTIN_WITH_PAN: sourceIds = [GSTIN, PAN] - use specialized builder
                            verify_rule = self.verify_builder.build_gstin_with_pan(
                                pan_field_id=pan_field.id,
                                gstin_field_id=gstin_field.id,
                                error_message="GSTIN and PAN doesn't match."
                            )
                            if verify_rule:
                                rules.append(verify_rule)

                                # Add to field rules map for GSTIN field
                                if gstin_field.id not in field_rules_map:
                                    field_rules_map[gstin_field.id] = []
                                field_rules_map[gstin_field.id].append(verify_rule)

                                processed_verify.add('GSTIN_WITH_PAN')
                                self.stats["fields_with_rules"] += 1

                                if self.verbose:
                                    print(f"  Generated VERIFY rule: GSTIN_WITH_PAN (cross-validation)")
                        continue

                if source_name and source_name not in processed_verify:
                    source_field = self.field_matcher.match_field(source_name)

                    if source_field:
                        # Detect VERIFY source type
                        verify_source = self._detect_verify_type_from_name(source_name)
                        if verify_source:
                            # Find all destination fields for this verification
                            dest_mappings = self._find_verify_destinations(source_name, intra_refs)

                            verify_rule = self.verify_builder.build(
                                source_type=verify_source,
                                source_field_ids=[source_field.id],
                                field_mappings=dest_mappings
                            )
                            if verify_rule:
                                rules.append(verify_rule)

                                # Add to field rules map
                                if source_field.id not in field_rules_map:
                                    field_rules_map[source_field.id] = []
                                field_rules_map[source_field.id].append(verify_rule)

                                processed_verify.add(source_name)
                                self.stats["fields_with_rules"] += 1

        return rules

    def _detect_ocr_type_from_name(self, field_name: str) -> Optional[str]:
        """Detect OCR source type from field name."""
        name_lower = field_name.lower()

        patterns = [
            (r"upload\s*pan|pan\s*image", "PAN_IMAGE"),
            (r"gstin\s*image|upload\s*gstin", "GSTIN_IMAGE"),
            (r"aadhaa?r\s*front|front\s*aadhaa?r", "AADHAR_IMAGE"),
            (r"aadhaa?r\s*back|back\s*aadhaa?r", "AADHAR_BACK_IMAGE"),
            (r"cheque|cancelled\s*cheque", "CHEQUEE"),
            (r"cin\s*image|upload\s*cin", "CIN"),
            (r"msme\s*image|upload\s*msme|udyam", "MSME"),
        ]

        for pattern, source_type in patterns:
            if re.search(pattern, name_lower):
                return source_type

        return None

    def _detect_verify_type_from_name(self, field_name: str) -> Optional[str]:
        """Detect VERIFY source type from field name."""
        name_lower = field_name.lower()

        mappings = [
            (r"^pan$|pan\s+number", "PAN_NUMBER"),
            (r"^gstin$|gst\s*in", "GSTIN"),
            (r"bank\s*account|account\s*number", "BANK_ACCOUNT_NUMBER"),
            (r"msme|udyam", "MSME_UDYAM_REG_NUMBER"),
            (r"^cin$|cin\s*number", "CIN_ID"),
            (r"^tan$|tan\s*number", "TAN_NUMBER"),
            (r"fssai", "FSSAI"),
        ]

        for pattern, source_type in mappings:
            if re.search(pattern, name_lower):
                return source_type

        return None

    def _find_verify_destinations(
        self,
        source_field_name: str,
        intra_refs: List[Dict]
    ) -> Dict[str, int]:
        """Find destination field mappings for a VERIFY rule."""
        mappings = {}

        for ref in intra_refs:
            ref_type = ref.get('reference_type', ref.get('dependency_type', ''))
            src = ref.get('source_field', '')

            # Handle dict source_field
            if isinstance(src, dict):
                src = src.get('field_name', '')

            if ref_type == 'data_population' and src.lower().strip() == source_field_name.lower().strip():
                target_name = ref.get('target_field', '')

                # Handle dict target_field
                if isinstance(target_name, dict):
                    target_name = target_name.get('field_name', '')

                if target_name:
                    target_field = self.field_matcher.match_field(target_name)
                    if target_field:
                        # Map using target field name - try to match to schema destination names
                        # The schema has standard names like "Fullname", "Pan type" etc.
                        # BUD fields might have names like "Pan Holder Name", "PAN Type"
                        mappings[target_name] = target_field.id

        return mappings

    def _generate_rules_for_field(
        self,
        field: Dict,
        logic_text: str,
        visibility_groups: Dict,
        all_fields: List[Dict],
        intra_refs: List[Dict]
    ) -> List[Dict]:
        """Generate rules for a single field."""
        rules = []

        field_id = field.get('id')
        field_name = field.get('formTag', {}).get('name', '')
        field_type = field.get('formTag', {}).get('type', 'TEXT')

        # Check if this field controls other fields (visibility source)
        # This check is done BEFORE logic parsing to ensure controlling fields generate rules
        # even if they have no direct logic text
        controlling_key = field_name.lower()
        if controlling_key in visibility_groups:
            controlled = visibility_groups[controlling_key]
            rules.extend(self._generate_visibility_rules(field_id, controlled))

        # Parse logic for additional rule types
        parsed = self.logic_parser.parse(logic_text)

        if parsed.should_skip:
            # Even if should_skip, return any visibility rules we generated
            return rules

        # NOTE: OCR and VERIFY rules are now generated in _generate_ocr_verify_from_refs
        # to avoid duplicates and ensure proper destination field mapping

        # Check for MAKE_DISABLED
        if 'MAKE_DISABLED' in parsed.actions:
            # Create disabled rule with this field as destination
            # Source is typically a control field (RuleCheck)
            disabled_rule = self.standard_builder.create_disabled_rule(
                source_id=field_id,  # Self-referencing for now
                destination_ids=[field_id]
            )
            rules.append(disabled_rule)

        # Check for CONVERT_TO
        if 'CONVERT_TO_UPPER' in parsed.actions:
            convert_rule = self.standard_builder.build_convert_to_rule(field_id, "UPPER_CASE")
            rules.append(convert_rule)

        return rules

    def _generate_visibility_rules(
        self,
        source_field_id: int,
        controlled_fields: List[Dict]
    ) -> List[Dict]:
        """Generate visibility rules for a controlling field."""
        rules = []

        # Group by conditional value
        by_condition = defaultdict(list)

        for cf in controlled_fields:
            rule_desc = cf.get('rule_description', '')
            dep_type = cf.get('dependency_type', '')
            dest_id = cf.get('dependent_field_id')

            if not dest_id:
                continue

            # Check if actions are already extracted (from BUD logic parsing)
            if 'actions' in cf and 'condition_value' in cf:
                cond_value = cf['condition_value']
                actions = cf['actions']
                by_condition[cond_value].append({
                    'dest_id': dest_id,
                    'actions': actions
                })
                continue

            # Otherwise, extract from rule description (legacy path for intra-panel refs)
            # Extract conditional value from rule description
            cond_value = "Yes"  # Default

            # Pattern 1: Simple "If yes" or "If no" at start of string (most common)
            match1 = re.search(r"^if\s+(yes|no)\b", rule_desc, re.I)
            if match1:
                cond_value = match1.group(1).capitalize()  # "Yes" or "No"
            else:
                # Pattern 2: "if 'X' is Y then visible"
                match2 = re.search(
                    r"(?:if|when)\s+['\"]?([^'\"]+?)['\"]?\s+(?:value\s+)?is\s+['\"]?([^'\"]+?)['\"]?\s+then",
                    rule_desc, re.I
                )
                if match2:
                    cond_value = match2.group(2).strip()
                else:
                    # Pattern 3: "Visible and Mandatory if ... is Yes/No" (more specific)
                    match3 = re.search(r"if\s+['\"]?[^'\"]+?['\"]?\s+is\s+['\"]?(yes|no)['\"]?", rule_desc, re.I)
                    if match3:
                        cond_value = match3.group(1).capitalize()

            # Determine action type from dependency type
            # Check if rule describes mandatory (but exclude "not mandatory")
            rule_lower = rule_desc.lower()
            is_mandatory = 'mandatory' in rule_lower and 'not mandatory' not in rule_lower

            if dep_type in ['visibility_mandatory', 'visibility_control']:
                if is_mandatory:
                    by_condition[cond_value].append({
                        'dest_id': dest_id,
                        'actions': ['MAKE_VISIBLE', 'MAKE_MANDATORY']
                    })
                else:
                    by_condition[cond_value].append({
                        'dest_id': dest_id,
                        'actions': ['MAKE_VISIBLE']
                    })
            elif dep_type in ['visibility', 'visibility_dependency']:
                by_condition[cond_value].append({
                    'dest_id': dest_id,
                    'actions': ['MAKE_VISIBLE']
                })
            elif dep_type in ['mandatory', 'mandatory_control']:
                # mandatory_control usually implies visibility too (editable = visible)
                # Check if rule mentions visibility/editable
                if 'editable' in rule_lower or 'visible' in rule_lower:
                    by_condition[cond_value].append({
                        'dest_id': dest_id,
                        'actions': ['MAKE_VISIBLE', 'MAKE_MANDATORY']
                    })
                else:
                    by_condition[cond_value].append({
                        'dest_id': dest_id,
                        'actions': ['MAKE_MANDATORY']
                    })
            elif dep_type == 'conditional_behavior':
                # Check rule description for specific behaviors
                actions = []
                if 'visible' in rule_lower:
                    actions.append('MAKE_VISIBLE')
                if is_mandatory:
                    actions.append('MAKE_MANDATORY')
                if actions:
                    by_condition[cond_value].append({
                        'dest_id': dest_id,
                        'actions': actions
                    })

        # Build rules - group by (cond_value, action_type) to avoid applying wrong actions to fields
        # First, group destination IDs by (cond_value, action) combination
        action_groups = defaultdict(set)  # (cond_value, action) -> set of dest_ids
        for cond_value, items in by_condition.items():
            for item in items:
                dest_id = item['dest_id']
                for action in item['actions']:
                    action_groups[(cond_value, action)].add(dest_id)

        # Now build rules for each action group
        for (cond_value, action), dest_ids in action_groups.items():
            dest_ids_list = sorted(list(dest_ids))

            if action == 'MAKE_VISIBLE':
                rules.append(self.standard_builder.create_conditional_rule(
                    action_type="MAKE_VISIBLE",
                    source_ids=[source_field_id],
                    destination_ids=dest_ids_list,
                    conditional_values=[cond_value],
                    condition="IN"
                ))
                rules.append(self.standard_builder.create_conditional_rule(
                    action_type="MAKE_INVISIBLE",
                    source_ids=[source_field_id],
                    destination_ids=dest_ids_list,
                    conditional_values=[cond_value],
                    condition="NOT_IN"
                ))
            elif action == 'MAKE_INVISIBLE':
                # Generate explicit MAKE_INVISIBLE rule
                rules.append(self.standard_builder.create_conditional_rule(
                    action_type="MAKE_INVISIBLE",
                    source_ids=[source_field_id],
                    destination_ids=dest_ids_list,
                    conditional_values=[cond_value],
                    condition="IN"
                ))
            elif action == 'MAKE_MANDATORY':
                rules.append(self.standard_builder.create_conditional_rule(
                    action_type="MAKE_MANDATORY",
                    source_ids=[source_field_id],
                    destination_ids=dest_ids_list,
                    conditional_values=[cond_value],
                    condition="IN"
                ))
                rules.append(self.standard_builder.create_conditional_rule(
                    action_type="MAKE_NON_MANDATORY",
                    source_ids=[source_field_id],
                    destination_ids=dest_ids_list,
                    conditional_values=[cond_value],
                    condition="NOT_IN"
                ))
            elif action == 'MAKE_NON_MANDATORY':
                # Generate explicit MAKE_NON_MANDATORY rule
                rules.append(self.standard_builder.create_conditional_rule(
                    action_type="MAKE_NON_MANDATORY",
                    source_ids=[source_field_id],
                    destination_ids=dest_ids_list,
                    conditional_values=[cond_value],
                    condition="IN"
                ))

        return rules

    def _link_ocr_verify_chains(self, all_rules: List[Dict]):
        """Link OCR rules to corresponding VERIFY rules via postTriggerRuleIds."""
        # Index VERIFY rules by source field
        verify_by_source = {}
        for rule in all_rules:
            if rule.get('actionType') == 'VERIFY':
                for src_id in rule.get('sourceIds', []):
                    verify_by_source[src_id] = rule

        # Link OCR to VERIFY
        for rule in all_rules:
            if rule.get('actionType') == 'OCR':
                source_type = rule.get('sourceType', '')

                # Check if this OCR type needs a VERIFY chain
                verify_source = OCR_VERIFY_CHAINS.get(source_type)
                if not verify_source:
                    continue

                # Find the destination field of OCR
                dest_ids = rule.get('destinationIds', [])
                if not dest_ids:
                    continue

                dest_id = dest_ids[0]

                # Find VERIFY rule that uses this field as source
                if dest_id in verify_by_source:
                    verify_rule = verify_by_source[dest_id]
                    if verify_rule.get('id'):
                        rule['postTriggerRuleIds'] = [verify_rule['id']]

    def _consolidate_rules(self, all_rules: List[Dict]) -> List[Dict]:
        """Consolidate and deduplicate rules using RuleConsolidator."""
        return self.consolidator.consolidate(all_rules)

    def _generate_all_ocr_rules(
        self,
        all_fields: List[Dict],
        field_rules_map: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Generate OCR rules for all file upload fields that match OCR patterns."""
        rules = []
        processed_sources = set()

        # Build field name to ID mapping
        field_by_name: Dict[str, Dict] = {}
        for f in all_fields:
            name = f.get('formTag', {}).get('name', '')
            if name:
                field_by_name[name.lower()] = f

        for field in all_fields:
            field_id = field.get('id')
            field_name = field.get('formTag', {}).get('name', '')
            field_type = field.get('formTag', {}).get('type', '')

            # Skip if already processed
            if field_id in processed_sources:
                continue

            # Check if field matches OCR source patterns
            name_lower = field_name.lower()
            ocr_source_type = None

            for pattern, source_type in OCR_FIELD_PATTERNS:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    ocr_source_type = source_type
                    break

            if not ocr_source_type:
                continue

            # Find destination field (the text field that will be populated)
            dest_field = self._find_ocr_destination(field_name, all_fields, field_by_name)
            if not dest_field:
                continue

            dest_field_id = dest_field.get('id')

            # Check if OCR rule already exists for this source
            existing_ocr = False
            for existing_rules in field_rules_map.values():
                for r in existing_rules:
                    if r.get('actionType') == 'OCR' and field_id in r.get('sourceIds', []):
                        existing_ocr = True
                        break
                if existing_ocr:
                    break

            if existing_ocr:
                processed_sources.add(field_id)
                continue

            # Build OCR rule
            ocr_rule = self.ocr_builder.build(
                source_type=ocr_source_type,
                upload_field_id=field_id,
                destination_field_ids=[dest_field_id]
            )

            if ocr_rule:
                rules.append(ocr_rule)

                # Add to field rules map
                if field_id not in field_rules_map:
                    field_rules_map[field_id] = []
                field_rules_map[field_id].append(ocr_rule)

                processed_sources.add(field_id)
                self.stats["fields_with_rules"] += 1

                if self.verbose:
                    print(f"  Generated OCR rule: {field_name} -> {dest_field.get('formTag', {}).get('name', '')}")

        return rules

    def _find_ocr_destination(
        self,
        source_field_name: str,
        all_fields: List[Dict],
        field_by_name: Dict[str, Dict]
    ) -> Optional[Dict]:
        """Find the destination field for an OCR rule."""
        name_lower = source_field_name.lower()

        # Special cases FIRST - these are known mappings
        # MSME Image -> MSME Registration Number
        if 'msme' in name_lower and ('image' in name_lower or 'upload' in name_lower):
            for target_name in ['msme registration number', 'msme number', 'msme reg']:
                if target_name in field_by_name:
                    return field_by_name[target_name]
            # Try partial match
            for fname, fobj in field_by_name.items():
                if 'msme' in fname and 'registration' in fname:
                    f_type = fobj.get('formTag', {}).get('type', '')
                    if f_type == 'TEXT':
                        return fobj

        # Cheque OCR populates IFSC and Bank Account
        if 'cheque' in name_lower or 'cancelled' in name_lower:
            for target_name in ['ifsc code', 'bank account number']:
                if target_name in field_by_name:
                    return field_by_name[target_name]

        # CIN Certificate -> CIN (the text field)
        if 'cin' in name_lower and 'certificate' in name_lower:
            for target_name in ['cin', 'cin number']:
                if target_name in field_by_name:
                    f = field_by_name[target_name]
                    f_type = f.get('formTag', {}).get('type', '')
                    if f_type == 'TEXT':
                        return f

        # Aadhaar Back Image -> look for address fields
        if 'aadhaar' in name_lower or 'aadhar' in name_lower:
            if 'back' in name_lower:
                # Aadhaar back populates address fields
                for target_name in ['postal code', 'pin code', 'pincode']:
                    if target_name in field_by_name:
                        return field_by_name[target_name]

        # Pattern matching for common OCR field pairs
        # "Upload PAN" -> "PAN"
        # "GSTIN IMAGE" -> "GSTIN"
        patterns = [
            # (source pattern, destination pattern or exact name)
            (r"upload\s*(.+)", r"\1"),  # "Upload PAN" -> "PAN"
            (r"(.+)\s*image", r"\1"),   # "GSTIN IMAGE" -> "GSTIN"
            (r"(.+)\s*copy", r"\1"),    # "Electricity bill copy" -> "Electricity bill"
        ]

        for src_pattern, dest_pattern in patterns:
            match = re.match(src_pattern, name_lower, re.IGNORECASE)
            if match:
                dest_name = re.sub(src_pattern, dest_pattern, name_lower, flags=re.IGNORECASE).strip()

                # Look for exact match first
                if dest_name in field_by_name:
                    dest_field = field_by_name[dest_name]
                    # Ensure it's not a file field (we want the text field)
                    f_type = dest_field.get('formTag', {}).get('type', '')
                    if f_type not in ['FILE', 'PANEL', 'LABEL']:
                        return dest_field

                # Try variations
                for fname, fobj in field_by_name.items():
                    if dest_name in fname or fname in dest_name:
                        f_type = fobj.get('formTag', {}).get('type', '')
                        if f_type not in ['FILE', 'PANEL', 'LABEL', 'DROPDOWN', 'EXTERNAL_DROP_DOWN_VALUE']:
                            return fobj

        return None

    def _generate_all_verify_rules(
        self,
        all_fields: List[Dict],
        intra_refs: List[Dict],
        field_rules_map: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Generate VERIFY rules for all fields that match verification patterns."""
        rules = []
        processed_sources: Set[int] = set()

        # Build field name to field mapping
        field_by_name: Dict[str, Dict] = {}
        for f in all_fields:
            name = f.get('formTag', {}).get('name', '')
            if name:
                field_by_name[name.lower()] = f

        for field in all_fields:
            field_id = field.get('id')
            field_name = field.get('formTag', {}).get('name', '')

            # Skip if already processed
            if field_id in processed_sources:
                continue

            # Check if field matches VERIFY source patterns
            name_lower = field_name.lower()
            verify_source_type = None

            for pattern, source_type in VERIFY_FIELD_PATTERNS:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    verify_source_type = source_type
                    break

            if not verify_source_type:
                continue

            # Check if VERIFY rule already exists for this source
            existing_verify = False
            for existing_rules in field_rules_map.values():
                for r in existing_rules:
                    if r.get('actionType') == 'VERIFY' and r.get('sourceType') == verify_source_type:
                        if field_id in r.get('sourceIds', []):
                            existing_verify = True
                            break
                if existing_verify:
                    break

            if existing_verify:
                processed_sources.add(field_id)
                continue

            # Find destination fields from intra-panel references
            dest_mappings = self._find_verify_destinations(field_name, intra_refs)

            # Build VERIFY rule
            source_ids = [field_id]

            # Handle multi-source VERIFY types (e.g., BANK_ACCOUNT_NUMBER needs IFSC + Account)
            if verify_source_type == 'BANK_ACCOUNT_NUMBER':
                # Find IFSC Code field
                ifsc_field = None
                for fname, fobj in field_by_name.items():
                    if 'ifsc' in fname and 'code' in fname:
                        ifsc_field = fobj
                        break
                if ifsc_field:
                    source_ids = [ifsc_field.get('id'), field_id]  # IFSC first, then account number

            verify_rule = self.verify_builder.build(
                source_type=verify_source_type,
                source_field_ids=source_ids,
                field_mappings=dest_mappings
            )

            if verify_rule:
                rules.append(verify_rule)

                # Add to field rules map
                if field_id not in field_rules_map:
                    field_rules_map[field_id] = []
                field_rules_map[field_id].append(verify_rule)

                processed_sources.add(field_id)
                self.stats["fields_with_rules"] += 1

                if self.verbose:
                    print(f"  Generated VERIFY rule: {field_name} ({verify_source_type})")

        return rules

    def _generate_convert_to_rules(
        self,
        all_fields: List[Dict],
        field_rules_map: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Generate CONVERT_TO rules for fields that should be uppercase."""
        rules = []
        processed = set()

        for field in all_fields:
            field_id = field.get('id')
            field_name = field.get('formTag', {}).get('name', '')
            field_type = field.get('formTag', {}).get('type', '')

            # Skip non-text fields
            if field_type not in ['TEXT', 'DROPDOWN', 'EXTERNAL_DROP_DOWN_VALUE']:
                continue

            # Skip if already processed
            if field_id in processed:
                continue

            # Check if field should have CONVERT_TO rule
            name_lower = field_name.lower()
            should_convert = False

            for pattern in UPPERCASE_FIELD_PATTERNS:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    should_convert = True
                    break

            if not should_convert:
                continue

            # Check if CONVERT_TO rule already exists
            existing_convert = False
            if field_id in field_rules_map:
                for r in field_rules_map[field_id]:
                    if r.get('actionType') == 'CONVERT_TO':
                        existing_convert = True
                        break

            if existing_convert:
                processed.add(field_id)
                continue

            # Build CONVERT_TO rule
            convert_rule = self.standard_builder.build_convert_to_rule(field_id, "UPPER_CASE")

            if convert_rule:
                rules.append(convert_rule)

                # Add to field rules map
                if field_id not in field_rules_map:
                    field_rules_map[field_id] = []
                field_rules_map[field_id].append(convert_rule)

                processed.add(field_id)
                self.stats["fields_with_rules"] += 1

                if self.verbose:
                    print(f"  Generated CONVERT_TO rule: {field_name}")

        return rules

    def _generate_edv_rules(
        self,
        all_fields: List[Dict],
        field_rules_map: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Generate EDV rules (EXT_DROP_DOWN and EXT_VALUE) from field-EDV mappings."""
        rules = []
        processed = set()

        if self.verbose:
            print(f"\n=== Generating EDV Rules ===")
            print(f"  Loaded {len(self.field_edv_mappings)} field-EDV mappings")

        for field in all_fields:
            field_id = field.get('id')
            field_name = field.get('formTag', {}).get('name', '')
            field_type = field.get('formTag', {}).get('type', '')

            # Skip if already processed
            if field_id in processed:
                continue

            # Check if this field has an EDV mapping
            field_name_lower = field_name.lower()
            if field_name_lower not in self.field_edv_mappings:
                continue

            mapping = self.field_edv_mappings[field_name_lower]
            edv_config = mapping.get('edv_config', {})
            rule_type = edv_config.get('rule_type')

            if not rule_type:
                continue

            # Check if EDV rule already exists
            existing_edv = False
            if field_id in field_rules_map:
                for r in field_rules_map[field_id]:
                    if r.get('actionType') in ['EXT_DROP_DOWN', 'EXT_VALUE']:
                        existing_edv = True
                        break

            if existing_edv:
                processed.add(field_id)
                continue

            # Generate EXT_DROP_DOWN rule (simple dropdown)
            if rule_type == 'EXT_DROP_DOWN':
                params = edv_config.get('params_template', '')

                ext_dropdown_rule = {
                    "id": id_generator.next_id('rule'),
                    "createUser": "FIRST_PARTY",
                    "updateUser": "FIRST_PARTY",
                    "actionType": "EXT_DROP_DOWN",
                    "sourceType": "FORM_FILL_DROP_DOWN",
                    "processingType": "CLIENT",
                    "sourceIds": [field_id],
                    "destinationIds": [],
                    "postTriggerRuleIds": [],
                    "params": params,
                    "button": "",
                    "searchable": True,
                    "executeOnFill": True,
                    "executeOnRead": False,
                    "executeOnEsign": False,
                    "executePostEsign": False,
                    "runPostConditionFail": False
                }

                rules.append(ext_dropdown_rule)

                # Add to field rules map
                if field_id not in field_rules_map:
                    field_rules_map[field_id] = []
                field_rules_map[field_id].append(ext_dropdown_rule)

                processed.add(field_id)

                if self.verbose:
                    print(f"  Generated EXT_DROP_DOWN rule: {field_name} -> {params}")

            # Generate EXT_VALUE rule (cascading dropdown)
            elif rule_type == 'EXT_VALUE':
                params_template = edv_config.get('params_template', {})
                relationship = mapping.get('relationship', {})
                parent_field_name = relationship.get('parent')

                if not parent_field_name:
                    continue

                # Find parent field ID
                parent_field_info = self.field_matcher.match_field(parent_field_name)
                if not parent_field_info:
                    continue

                parent_field_id = parent_field_info.id

                # Build params JSON by replacing {{parent_field_id}} placeholder
                params_str = json.dumps(params_template)
                params_str = params_str.replace('"{{parent_field_id}}"', str(parent_field_id))
                params_str = params_str.replace('{{parent_field_id}}', str(parent_field_id))

                ext_value_rule = {
                    "id": id_generator.next_id('rule'),
                    "createUser": "FIRST_PARTY",
                    "updateUser": "FIRST_PARTY",
                    "actionType": "EXT_VALUE",
                    "sourceType": "EXTERNAL_DATA_VALUE",
                    "processingType": "CLIENT",
                    "sourceIds": [field_id],
                    "destinationIds": [],
                    "postTriggerRuleIds": [],
                    "params": params_str,
                    "button": "",
                    "searchable": True,
                    "executeOnFill": True,
                    "executeOnRead": False,
                    "executeOnEsign": False,
                    "executePostEsign": False,
                    "runPostConditionFail": False
                }

                rules.append(ext_value_rule)

                # Add to field rules map
                if field_id not in field_rules_map:
                    field_rules_map[field_id] = []
                field_rules_map[field_id].append(ext_value_rule)

                processed.add(field_id)

                if self.verbose:
                    print(f"  Generated EXT_VALUE rule: {field_name} (parent: {parent_field_name})")

        return rules

    def _generate_validation_rules(
        self,
        all_fields: List[Dict],
        intra_refs: List[Dict],
        field_rules_map: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Generate VALIDATION rules for fields with validation constraints."""
        rules = []
        processed = set()

        if self.verbose:
            print(f"\n=== Generating VALIDATION Rules ===")

        # Strategy 1: From intra-panel references (validation dependency type)
        for ref in intra_refs:
            dep_type = ref.get('dependency_type', '')

            # Look for validation dependencies
            if dep_type == 'validation':
                dependent_field = ref.get('dependent_field', '')
                rule_desc = ref.get('rule_description', '')

                if not dependent_field:
                    continue

                # Find field ID
                field_info = self.field_matcher.match_field(dependent_field)
                if not field_info:
                    continue

                field_id = field_info.id

                # Skip if already processed
                if field_id in processed:
                    continue

                # Check if VALIDATION rule already exists
                if self._has_rule_type(field_id, 'VALIDATION', field_rules_map):
                    processed.add(field_id)
                    continue

                # Build VALIDATION rule
                validation_rule = self.validation_builder.build(
                    source_ids=[field_id],
                    destination_ids=[],
                    params=None
                )

                if validation_rule:
                    rules.append(validation_rule)
                    if field_id not in field_rules_map:
                        field_rules_map[field_id] = []
                    field_rules_map[field_id].append(validation_rule)
                    processed.add(field_id)

                    if self.verbose:
                        print(f"  Generated VALIDATION rule (from ref): {dependent_field}")

        # Strategy 2: From EDV mappings
        if self.field_edv_mappings:
            for field in all_fields:
                field_id = field.get('id')
                field_name = field.get('formTag', {}).get('name', '')
                field_name_key = field_name.lower()

                # Skip if already processed
                if field_id in processed:
                    continue

                # Check if field has EDV validation mapping
                if field_name_key in self.field_edv_mappings:
                    edv_mapping = self.field_edv_mappings[field_name_key]

                    # Check if this requires VALIDATION rule (not just dropdown)
                    if edv_mapping.get('requires_validation', False):
                        # Check if VALIDATION rule already exists
                        if self._has_rule_type(field_id, 'VALIDATION', field_rules_map):
                            processed.add(field_id)
                            continue

                        # Build VALIDATION rule from EDV mapping
                        validation_rule = self.validation_builder.build_from_edv_mapping(
                            field_id=field_id,
                            edv_mapping=edv_mapping,
                            all_fields=all_fields
                        )

                        if validation_rule:
                            rules.append(validation_rule)
                            if field_id not in field_rules_map:
                                field_rules_map[field_id] = []
                            field_rules_map[field_id].append(validation_rule)
                            processed.add(field_id)

                            if self.verbose:
                                print(f"  Generated VALIDATION rule (from EDV): {field_name}")

        if self.verbose:
            print(f"Total VALIDATION rules generated: {len(rules)}")

        return rules

    def _generate_copy_to_rules(
        self,
        all_fields: List[Dict],
        intra_refs: List[Dict],
        field_rules_map: Dict[int, List[Dict]]
    ) -> List[Dict]:
        """Generate COPY_TO rules for field value propagation."""
        rules = []
        processed = set()

        if self.verbose:
            print(f"\n=== Generating COPY_TO Rules ===")

        for ref in intra_refs:
            dep_type = ref.get('dependency_type', '')
            rule_desc = ref.get('rule_description', '')

            # Look for value_derivation that indicates copying
            if dep_type == 'value_derivation':
                # Check if this is a simple copy (not complex derivation)
                if rule_desc and ('derived from' in rule_desc.lower() or 'copy' in rule_desc.lower()):
                    # Parse source and destination fields
                    source_field = ref.get('referenced_field', '')
                    dest_field = ref.get('dependent_field', '')

                    if not source_field or not dest_field:
                        continue

                    # Find field IDs
                    source_info = self.field_matcher.match_field(source_field)
                    dest_info = self.field_matcher.match_field(dest_field)

                    if not source_info or not dest_info:
                        continue

                    source_id = source_info.id
                    dest_id = dest_info.id

                    # Use source_id as key for processed tracking
                    copy_key = (source_id, dest_id)
                    if copy_key in processed:
                        continue

                    # Check if COPY_TO rule already exists on source field
                    if self._has_copy_to_destination(source_id, dest_id, field_rules_map):
                        processed.add(copy_key)
                        continue

                    # Build COPY_TO rule using builder
                    copy_to_rule = self.copy_to_builder.build(
                        source_ids=[source_id],
                        destination_ids=[dest_id]
                    )

                    if copy_to_rule:
                        rules.append(copy_to_rule)

                        # Add to field rules map
                        if source_id not in field_rules_map:
                            field_rules_map[source_id] = []
                        field_rules_map[source_id].append(copy_to_rule)

                        processed.add(copy_key)

                        if self.verbose:
                            print(f"  Generated COPY_TO rule: {source_field} -> {dest_field}")

        if self.verbose:
            print(f"Total COPY_TO rules generated: {len(rules)}")

        return rules

    def _has_rule_type(self, field_id: int, action_type: str, field_rules_map: Dict[int, List[Dict]]) -> bool:
        """Check if field already has a rule of given type."""
        if field_id not in field_rules_map:
            return False
        for r in field_rules_map[field_id]:
            if r.get('actionType') == action_type:
                return True
        return False

    def _has_copy_to_destination(self, source_id: int, dest_id: int, field_rules_map: Dict[int, List[Dict]]) -> bool:
        """Check if COPY_TO rule already exists for this source->dest pair."""
        if source_id not in field_rules_map:
            return False
        for r in field_rules_map[source_id]:
            if r.get('actionType') == 'COPY_TO' and dest_id in r.get('destinationIds', []):
                return True
        return False

    def _find_or_create_rulecheck_field(self, all_fields: List[Dict]) -> Optional[int]:
        """
        Find the RuleCheck control field ID.

        The RuleCheck field is a hidden TEXT field used to control MAKE_DISABLED rules.
        Pattern from reference: field with name "RuleCheck" or similar.
        """
        # Try to find existing RuleCheck field
        for field in all_fields:
            name = field.get('formTag', {}).get('name', '').lower()
            if 'rulecheck' in name or name == 'rule check':
                return field.get('id')

        # If not found, return the first field ID (usually a control field)
        # In production, we'd create one, but for now use first field
        if all_fields:
            return all_fields[0].get('id')

        return None

    def _parse_bud_document(self) -> Dict[str, str]:
        """
        Parse the BUD document to extract field logic text.
        Returns dict mapping field_name (lowercase) -> logic text.
        """
        try:
            from doc_parser import DocumentParser

            # Find the BUD document (assume it's in documents/ folder)
            bud_path = None
            for path in Path("documents").glob("*.docx"):
                if "Vendor Creation" in path.name and "Sample BUD" in path.name:
                    bud_path = str(path)
                    break

            if not bud_path:
                print("Warning: Could not find BUD document, skipping BUD-based extraction")
                return {}

            parser = DocumentParser()
            parsed = parser.parse(bud_path)

            # Build field logic map
            field_logic = {}
            for field in parsed.all_fields:
                logic = (field.logic or '') + ' ' + (field.rules or '')
                if logic.strip():
                    field_logic[field.name.lower()] = logic.strip()

            return field_logic
        except Exception as e:
            print(f"Warning: Failed to parse BUD document: {e}")
            return {}

    def _extract_visibility_from_bud_logic(
        self,
        all_fields: List[Dict],
        bud_field_logic: Dict[str, str]
    ) -> Dict[str, List[Dict]]:
        """
        Extract visibility/mandatory dependencies by scanning ALL field logic.

        This is the KEY fix - we look at DEPENDENT fields' logic to find their
        controlling fields, then group by controlling field.
        """
        groups = defaultdict(list)

        # Build field list for finding preceding fields
        field_list = [(f.get('formTag', {}).get('name', ''), f.get('id'), f.get('formTag', {}).get('type', ''))
                      for f in all_fields]

        # Pattern to match "If 'FieldName' is X then..." or "If FieldName is X then..."
        # Also match variations like "when", "if field", etc.
        patterns = [
            r"(?:if|when)\s+.*?field.*?['\"](.+?)['\"].*?(?:is|=|equals?|value\s+is)\s+['\"]?(\w+)['\"]?\s+then\s+(.*?)(?:\.|$)",
            r"(?:if|when)\s+['\"](.+?)['\"].*?(?:is|=|equals?|value\s+is)\s+['\"]?(\w+)['\"]?\s+then\s+(.*?)(?:\.|$)",
        ]

        # Pattern for unqualified conditionals like "If Yes then..." or "If 'No' then..."
        # These need to infer the controlling field from context (usually previous field)
        unqualified_pattern = r"(?:if|when)\s+['\"]?(yes|no)['\"]?\s*[,;]?\s+then\s+(.*?)(?:\.|,|$)"

        for idx, field in enumerate(all_fields):
            field_name = field.get('formTag', {}).get('name', '')
            field_id = field.get('id')
            logic = bud_field_logic.get(field_name.lower(), '')

            if not logic:
                continue

            logic_lower = logic.lower()
            found_match = False

            # Try qualified patterns first (with field name)
            for pattern in patterns:
                matches = re.finditer(pattern, logic_lower, re.IGNORECASE)
                for match in matches:
                    controlling_field = match.group(1).strip().strip('\'"')
                    condition_value = match.group(2).strip().strip('\'"')
                    action_text = match.group(3).strip()

                    # Determine action types from action text
                    actions = []
                    if 'mandatory' in action_text and 'non-mandatory' not in action_text:
                        actions.append('MAKE_MANDATORY')
                    if 'visible' in action_text and 'invisible' not in action_text:
                        actions.append('MAKE_VISIBLE')
                    if 'hidden' in action_text or 'invisible' in action_text:
                        actions.append('MAKE_INVISIBLE')
                    if 'non-mandatory' in action_text or 'optional' in action_text:
                        actions.append('MAKE_NON_MANDATORY')

                    if actions:
                        groups[controlling_field.lower()].append({
                            'dependent_field': field_name,
                            'dependent_field_id': field_id,
                            'condition_value': condition_value.capitalize(),
                            'actions': actions,
                            'rule_description': logic
                        })
                        found_match = True

            # If no qualified match, try unqualified pattern
            if not found_match:
                matches = re.finditer(unqualified_pattern, logic_lower, re.IGNORECASE)
                for match in matches:
                    condition_value = match.group(1).strip().capitalize()  # "Yes" or "No"
                    action_text = match.group(2).strip()

                    # Determine actions
                    actions = []
                    if 'mandatory' in action_text and 'non-mandatory' not in action_text:
                        actions.append('MAKE_MANDATORY')
                    if 'visible' in action_text and 'invisible' not in action_text:
                        actions.append('MAKE_VISIBLE')
                    if 'hidden' in action_text or 'invisible' in action_text:
                        actions.append('MAKE_INVISIBLE')
                    if 'non-mandatory' in action_text or 'optional' in action_text:
                        actions.append('MAKE_NON_MANDATORY')

                    if actions:
                        # Find preceding dropdown/checkbox field (likely the controlling field)
                        controlling_field_name = None
                        for i in range(idx - 1, max(0, idx - 10), -1):  # Look back up to 10 fields
                            prev_name, prev_id, prev_type = field_list[i]
                            if prev_type in ['DROPDOWN', 'EXTERNAL_DROP_DOWN_VALUE', 'CHECKBOX', 'MULTI_DROPDOWN']:
                                controlling_field_name = prev_name
                                break

                        if controlling_field_name:
                            groups[controlling_field_name.lower()].append({
                                'dependent_field': field_name,
                                'dependent_field_id': field_id,
                                'condition_value': condition_value,
                                'actions': actions,
                                'rule_description': logic
                            })

        return dict(groups)

    def _merge_visibility_groups(
        self,
        groups1: Dict[str, List[Dict]],
        groups2: Dict[str, List[Dict]]
    ) -> Dict[str, List[Dict]]:
        """Merge two visibility groups dicts, preferring groups1."""
        merged = defaultdict(list)

        # Add all from groups1
        for key, deps in groups1.items():
            merged[key].extend(deps)

        # Add from groups2 if not already present
        for key, deps in groups2.items():
            existing_dep_ids = {d.get('dependent_field_id') for d in merged[key]}
            for dep in deps:
                if dep.get('dependent_field_id') not in existing_dep_ids:
                    merged[key].append(dep)

        return dict(merged)

    def _rebuild_field_rules_map(self, consolidated_rules: List[Dict]) -> Dict[int, List[Dict]]:
        """
        Rebuild field_rules_map from consolidated rules.

        After consolidation, rules may have been merged or moved to different fields.
        We need to rebuild the field->rules mapping.
        """
        field_rules_map = defaultdict(list)

        for rule in consolidated_rules:
            # Rules are placed on their SOURCE field(s)
            source_ids = rule.get('sourceIds', [])
            for source_id in source_ids:
                field_rules_map[source_id].append(rule)

        return dict(field_rules_map)

    def _populate_schema_with_rules(self, schema: Dict, field_rules_map: Dict[int, List[Dict]]):
        """Populate schema formFillMetadatas with generated rules."""
        doc_types = schema.get('template', {}).get('documentTypes', [])

        for doc_type in doc_types:
            ffms = doc_type.get('formFillMetadatas', [])

            for ffm in ffms:
                field_id = ffm.get('id')
                if field_id in field_rules_map:
                    ffm['formFillRules'] = field_rules_map[field_id]


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Rule Extraction Agent - Extract formFillRules from BUD documents"
    )

    parser.add_argument(
        '--schema',
        required=True,
        help='Path to schema JSON from extract_fields_complete.py'
    )
    parser.add_argument(
        '--intra-panel',
        required=True,
        help='Path to intra-panel references JSON'
    )
    parser.add_argument(
        '--output',
        help='Output path for populated schema'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate generated rules'
    )
    parser.add_argument(
        '--llm-threshold',
        type=float,
        default=0.7,
        help='Confidence threshold for LLM fallback (default: 0.7)'
    )
    parser.add_argument(
        '--report',
        help='Path to save summary report'
    )
    parser.add_argument(
        '--edv-tables',
        help='Path to EDV tables JSON'
    )
    parser.add_argument(
        '--field-edv-mapping',
        help='Path to field-EDV mapping JSON'
    )

    args = parser.parse_args()

    # Generate output path if not provided
    if not args.output:
        schema_path = Path(args.schema)
        args.output = str(schema_path.parent / f"{schema_path.stem}_populated.json")

    # Create agent and process
    agent = RuleExtractionAgent(
        llm_threshold=args.llm_threshold,
        verbose=args.verbose,
        validate=args.validate,
        edv_tables_path=args.edv_tables,
        field_edv_mapping_path=args.field_edv_mapping
    )

    result = agent.process(
        schema_json_path=args.schema,
        intra_panel_path=args.intra_panel,
        output_path=args.output
    )

    # Print summary
    stats = result['stats']
    print(f"\n=== Rule Extraction Summary ===")
    print(f"Total fields: {stats['total_fields']}")
    print(f"Fields with rules: {stats['fields_with_rules']}")
    print(f"Total rules generated: {stats['total_rules_generated']}")
    print(f"\nRules by type:")
    for action_type, count in sorted(stats['rules_by_type'].items()):
        print(f"  {action_type}: {count}")

    if stats['llm_fallback_used'] > 0:
        print(f"\nLLM fallback used: {stats['llm_fallback_used']} times")

    if stats['validation_errors'] > 0:
        print(f"\nValidation errors: {stats['validation_errors']}")

    print(f"\nOutput saved to: {args.output}")

    # Save report if requested
    if args.report:
        report = {
            "timestamp": datetime.now().isoformat(),
            "input_schema": args.schema,
            "input_intra_panel": args.intra_panel,
            "output": args.output,
            "statistics": stats,
        }
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {args.report}")


if __name__ == '__main__':
    main()
