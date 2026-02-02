"""
Rule Extraction Agent - Main module for rule extraction.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

from .models import (
    IdGenerator, GeneratedRule, FieldInfo, ExtractionResult,
    ParsedLogic, RuleSelection, VisibilityGroup, OCRVerifyChain
)
from .logic_parser import LogicParser, should_skip_logic, detect_document_type
from .field_matcher import FieldMatcher
from .schema_lookup import RuleSchemaLookup
from .id_mapper import DestinationIdMapper
from .rule_tree import RuleTree, DeterministicMatcher, is_destination_field_logic
from .llm_fallback import LLMFallback, MatchingPipeline
from .rule_builders import (
    StandardRuleBuilder, VerifyRuleBuilder, OcrRuleBuilder, VisibilityRuleBuilder
)
from .utils import (
    consolidate_rules, link_ocr_to_verify_rules, populate_schema_with_rules,
    extract_conditional_values, save_json, load_json, create_report
)


class RuleExtractionAgent:
    """Main agent for extracting rules from BUD logic sections."""

    def __init__(
        self,
        schema_path: str,
        bud_document_path: Optional[str] = None,
        intra_panel_path: Optional[str] = None,
        rule_schemas_path: str = "rules/Rule-Schemas.json",
        llm_threshold: float = 0.7,
        verbose: bool = False
    ):
        """
        Initialize the Rule Extraction Agent.

        Args:
            schema_path: Path to schema JSON from extract_fields_complete.py.
            bud_document_path: Path to original BUD .docx file.
            intra_panel_path: Path to intra-panel references JSON.
            rule_schemas_path: Path to Rule-Schemas.json.
            llm_threshold: Confidence threshold for LLM fallback.
            verbose: Enable verbose logging.
        """
        self.schema_path = schema_path
        self.bud_document_path = bud_document_path
        self.intra_panel_path = intra_panel_path
        self.llm_threshold = llm_threshold
        self.verbose = verbose

        # Load schema
        self.schema = load_json(schema_path)

        # Load intra-panel references
        self.intra_panel_refs = None
        if intra_panel_path and Path(intra_panel_path).exists():
            self.intra_panel_refs = load_json(intra_panel_path)

        # Initialize components
        self.id_generator = IdGenerator()
        self.logic_parser = LogicParser()
        self.field_matcher = FieldMatcher()
        self.schema_lookup = RuleSchemaLookup(rule_schemas_path)
        self.id_mapper = DestinationIdMapper(self.schema_lookup, self.field_matcher)

        # Initialize builders
        self.standard_builder = StandardRuleBuilder(self.id_generator)
        self.verify_builder = VerifyRuleBuilder(
            self.id_generator, self.schema_lookup, self.id_mapper
        )
        self.ocr_builder = OcrRuleBuilder(self.id_generator, self.schema_lookup)
        self.visibility_builder = VisibilityRuleBuilder(self.id_generator)

        # Initialize matching pipeline
        self.matcher = MatchingPipeline(
            self.schema_lookup,
            self.field_matcher,
            llm_threshold
        )

        # Load fields from schema
        self.fields = self.field_matcher.load_from_schema(self.schema)

        # Result tracking
        self.result = ExtractionResult()
        self.rules_by_field: Dict[int, List[GeneratedRule]] = defaultdict(list)
        self.all_rules: List[GeneratedRule] = []

    def log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def process(self) -> ExtractionResult:
        """
        Process all fields and generate rules.

        Returns:
            ExtractionResult with generated rules and statistics.
        """
        self.log("Starting rule extraction...")

        # Step 1: Extract logic from intra-panel references and attach to fields
        self._extract_logic_from_intra_panel()
        self.log(f"Extracted logic for {sum(1 for f in self.fields if f.logic)} fields")

        # Step 2: Identify visibility controlling fields
        visibility_groups = self._identify_visibility_groups()
        self.log(f"Found {len(visibility_groups)} visibility controlling fields")

        # Step 3: Identify OCR -> VERIFY chains
        ocr_verify_chains = self._identify_ocr_verify_chains()
        self.log(f"Found {len(ocr_verify_chains)} OCR -> VERIFY chains")

        # Step 4: Generate EXT_DROP_DOWN rules for all external dropdown fields
        self._generate_ext_dropdown_rules()
        self.log(f"Generated EXT_DROP_DOWN rules")

        # Step 5: Generate EXT_VALUE rules for external data value fields
        self._generate_ext_value_rules()
        self.log(f"Generated EXT_VALUE rules")

        # Step 6: Generate rules from visibility groups
        for controlling_name, group in visibility_groups.items():
            controlling_field = self.field_matcher.match_field(controlling_name)
            if controlling_field and group.destination_fields:
                rules = self._generate_visibility_rules(controlling_field, group)
                for rule in rules:
                    self._add_rule(controlling_field.id, rule)

        # Step 7: Process each field for other rules
        for field in self.fields:
            self._process_field(field, visibility_groups)
            self.result.total_fields_processed += 1

        # Step 8: Process OCR -> VERIFY chains
        for chain in ocr_verify_chains:
            self._process_ocr_verify_chain(chain)

        # Step 9: Link OCR -> VERIFY rules
        link_ocr_to_verify_rules(self.all_rules)
        self.log("Linked OCR to VERIFY rules")

        # Step 10: Consolidate rules
        self.all_rules = consolidate_rules(self.all_rules)
        self.log(f"Consolidated to {len(self.all_rules)} rules")

        # Step 11: Rebuild rules_by_field after consolidation
        self._rebuild_rules_by_field()

        # Step 12: Populate schema
        self.result.populated_schema = populate_schema_with_rules(
            self.schema, self.rules_by_field
        )

        # Calculate statistics
        self.result.total_rules_generated = len(self.all_rules)
        self._calculate_rule_stats()

        return self.result

    def _extract_logic_from_intra_panel(self):
        """Extract logic from intra-panel references and attach to fields."""
        if not self.intra_panel_refs:
            return

        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                if not isinstance(ref, dict):
                    continue

                # Collect all possible logic texts from the reference
                all_logic = []

                # Direct logic fields
                for logic_key in ['logic_text', 'rule_description', 'logic_summary',
                                  'dependency_notes', 'logic_excerpt', 'raw_logic']:
                    logic = ref.get(logic_key, '')
                    if logic:
                        all_logic.append(logic)

                # References list
                refs = ref.get('references', [])
                for r in refs:
                    if isinstance(r, dict):
                        for logic_key in ['dependency_description', 'logic_excerpt',
                                          'condition_description', 'raw_logic_excerpt',
                                          'reference_context', 'source_logic', 'rule_description']:
                            logic = r.get(logic_key, '')
                            if logic:
                                all_logic.append(logic)

                # depends_on list
                depends_on = ref.get('depends_on', [])
                for dep in depends_on:
                    if isinstance(dep, dict):
                        for logic_key in ['logic_excerpt', 'condition']:
                            logic = dep.get(logic_key, '')
                            if logic:
                                all_logic.append(logic)

                # Determine the field name
                field_name = None

                # Structure 1: source_field (string or dict)
                source_field = ref.get('source_field')
                if source_field:
                    if isinstance(source_field, str):
                        field_name = source_field
                    elif isinstance(source_field, dict):
                        field_name = source_field.get('field_name', '')

                # Structure 2: dependent_field (string or dict)
                if not field_name:
                    dep_field = ref.get('dependent_field')
                    if dep_field:
                        if isinstance(dep_field, str):
                            field_name = dep_field
                        elif isinstance(dep_field, dict):
                            field_name = dep_field.get('field_name', '')

                # Structure 3: field_name directly
                if not field_name:
                    field_name = ref.get('field_name', '')

                # Attach logic to field
                if field_name and all_logic:
                    field = self.field_matcher.match_field(field_name)
                    if field:
                        combined_logic = ' '.join(all_logic)
                        if field.logic:
                            field.logic += ' ' + combined_logic
                        else:
                            field.logic = combined_logic

    def _generate_ext_dropdown_rules(self):
        """Generate EXT_DROP_DOWN rules for all external dropdown type fields."""
        # Track which fields have EXT_DROP_DOWN rules to avoid duplicates
        ext_dropdown_field_ids = set()

        # Find all fields with EXTERNAL_DROP_DOWN_VALUE or MULTISELECT_EXTERNAL_DROPDOWN type
        ext_dropdown_types = ['EXTERNAL_DROP_DOWN_VALUE', 'MULTISELECT_EXTERNAL_DROPDOWN', 'EXTERNAL_DROPDOWN']

        for field in self.fields:
            if field.field_type in ext_dropdown_types:
                if field.id not in ext_dropdown_field_ids:
                    # Check if field has a parent field (cascading dropdown)
                    parent_field_id = self._find_parent_dropdown(field)

                    # Build EXT_DROP_DOWN rule
                    rule = self.standard_builder.build_ext_dropdown_rule(
                        field_id=field.id,
                        params=self._get_ext_dropdown_params(field),
                        parent_field_id=parent_field_id
                    )
                    self._add_rule(field.id, rule)
                    ext_dropdown_field_ids.add(field.id)
                    self.log(f"Generated EXT_DROP_DOWN for {field.name} (id={field.id})")

    def _find_parent_dropdown(self, field: FieldInfo) -> Optional[int]:
        """Find parent field ID for cascading dropdowns."""
        if not self.intra_panel_refs:
            return None

        field_name_lower = field.name.lower()

        # Common parent-child relationships
        cascading_patterns = [
            ('state', 'country'),  # State depends on Country
            ('district', 'state'),  # District depends on State
            ('city', 'state'),  # City depends on State
            ('city', 'district'),  # City might depend on District
            ('pincode', 'city'),  # Pincode depends on City
            ('sub-category', 'category'),
            ('sub category', 'category'),
        ]

        for child_pattern, parent_pattern in cascading_patterns:
            if child_pattern in field_name_lower:
                # Find parent field
                for f in self.fields:
                    if parent_pattern in f.name.lower() and f.field_type in ['EXTERNAL_DROP_DOWN_VALUE', 'MULTISELECT_EXTERNAL_DROPDOWN', 'EXTERNAL_DROPDOWN']:
                        return f.id

        # Also check intra-panel references for cascading relationships
        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                dep_field = ref.get('dependent_field', {})
                dep_name = dep_field.get('field_name', '') if isinstance(dep_field, dict) else str(dep_field)

                if dep_name.lower() == field_name_lower or self._fuzzy_match(dep_name, field.name):
                    # Check depends_on for cascading dropdown relationship
                    depends_on = ref.get('depends_on', [])
                    for dep in depends_on:
                        if isinstance(dep, dict):
                            dep_type = dep.get('dependency_type', '')
                            if 'cascading' in dep_type.lower() or 'filter' in dep_type.lower() or 'parent' in dep_type.lower():
                                target_name = dep.get('target_field', '')
                                parent_field = self.field_matcher.match_field(target_name)
                                if parent_field:
                                    return parent_field.id

                    # Check references for parent-child relationships
                    for r in ref.get('references', []):
                        if isinstance(r, dict):
                            ref_type = r.get('reference_type', '')
                            logic = r.get('logic_excerpt', '') or r.get('dependency_description', '') or ''

                            if 'filter' in logic.lower() or 'parent' in logic.lower() or 'cascad' in logic.lower():
                                parent_name = r.get('referenced_field_name', '') or r.get('referenced_field', '')
                                parent_field = self.field_matcher.match_field(parent_name)
                                if parent_field:
                                    return parent_field.id

        return None

    def _fuzzy_match(self, name1: str, name2: str) -> bool:
        """Check if two field names are similar enough."""
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        return n1 == n2 or n1 in n2 or n2 in n1

    def _get_ext_dropdown_params(self, field: FieldInfo) -> str:
        """Get params for EXT_DROP_DOWN rule based on field name."""
        name_lower = field.name.lower()

        # Common parameter mappings
        param_mappings = {
            'company': 'COMPANY_CODE',
            'country': 'COUNTRY',
            'state': 'STATE',
            'district': 'DISTRICT',
            'city': 'CITY',
            'currency': 'CURRENCY',
            'payment': 'PAYMENT_TERMS',
            'incoterms': 'INCOTERMS',
            'account group': 'ACCOUNT_GROUP',
            'vendor type': 'VENDOR_TYPE',
            'process type': 'PROCESS_TYPE',
            'corporate group': 'CORPORATE_GROUP',
            'group key': 'GROUP_KEY',
            'purchasing org': 'PURCHASING_ORG',
            'purchase org': 'PURCHASING_ORG',
            'plant': 'PLANT',
            'vendor class': 'VENDOR_CLASS',
            'title': 'TITLE',
            'category': 'CATEGORY',
            'scheme': 'SCHEME',
            'gst registration status': 'GST_REG_STATUS',
            'business type': 'BUSINESS_TYPE',
            'constitution': 'CONSTITUTION',
        }

        for pattern, param in param_mappings.items():
            if pattern in name_lower:
                return param

        # Default: use sanitized field name
        return field.variable_name.upper() if field.variable_name else ''

    def _generate_ext_value_rules(self):
        """Generate EXT_VALUE rules for fields that get external data values."""
        # Track which fields have EXT_VALUE rules to avoid duplicates
        ext_value_field_ids = set()

        if not self.intra_panel_refs:
            return

        # Find fields that have "Data will come from" in their logic
        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                # Get field info
                dep_field = ref.get('dependent_field', {})
                if not dep_field:
                    continue

                field_name = dep_field.get('field_name', '') if isinstance(dep_field, dict) else str(dep_field)
                if not field_name:
                    continue

                field = self.field_matcher.match_field(field_name)
                if not field or field.id in ext_value_field_ids:
                    continue

                # Check logic for external value patterns
                logic_text = ref.get('logic_text', '') or ''
                logic_lower = logic_text.lower()

                # Also check references
                refs = ref.get('references', [])
                for r in refs:
                    if isinstance(r, dict):
                        dep_desc = r.get('dependency_description', '') or ''
                        ref_type = r.get('reference_type', '')

                        # Check for external data value patterns
                        is_ext_value = (
                            'data will come from' in dep_desc.lower() or
                            ref_type == 'data_source' or
                            'auto-populated' in dep_desc.lower() or
                            'auto populated' in dep_desc.lower() or
                            'will be populated' in dep_desc.lower() or
                            'fetched from' in dep_desc.lower()
                        )

                        # Exclude verification destinations (they get VERIFY rules, not EXT_VALUE)
                        is_verify_dest = (
                            'verification' in dep_desc.lower() or
                            'validation' in dep_desc.lower()
                        )

                        if is_ext_value and not is_verify_dest:
                            # Determine params based on source
                            params = self._get_ext_value_params(field, r, dep_desc)
                            rule = self.standard_builder.build_ext_value_rule(
                                field_id=field.id,
                                params=params
                            )
                            self._add_rule(field.id, rule)
                            ext_value_field_ids.add(field.id)
                            self.log(f"Generated EXT_VALUE for {field.name} (id={field.id})")
                            break

    def _get_ext_value_params(self, field: FieldInfo, ref: Dict, dep_desc: str) -> str:
        """Get params for EXT_VALUE rule based on field and reference."""
        name_lower = field.name.lower()
        desc_lower = dep_desc.lower()

        # Common patterns
        if 'company code' in desc_lower or 'company code' in name_lower:
            return 'COMPANY_CODE'
        if 'company name' in desc_lower or 'company name' in name_lower:
            return 'COMPANY_NAME'
        if 'gst' in desc_lower and 'state' in name_lower:
            return 'GST_STATE'
        if 'pan' in desc_lower:
            return 'PAN'
        if 'email' in name_lower:
            return 'EMAIL'
        if 'mobile' in name_lower or 'phone' in name_lower:
            return 'MOBILE'

        # Default to empty
        return ''

    def _process_ocr_verify_chain(self, chain: OCRVerifyChain):
        """Process an OCR -> VERIFY chain and generate rules."""
        # Generate OCR rule
        if chain.ocr_field_id and chain.verify_field_id:
            ocr_rule = self.ocr_builder.build(
                source_type=chain.ocr_source_type,
                upload_field_id=chain.ocr_field_id,
                output_field_id=chain.verify_field_id
            )
            self._add_rule(chain.ocr_field_id, ocr_rule)

            # Generate VERIFY rule
            verify_rule = self.verify_builder.build(
                source_type=chain.verify_source_type,
                source_field_id=chain.verify_field_id
            )
            self._add_rule(chain.verify_field_id, verify_rule)

            # Link OCR -> VERIFY
            ocr_rule.post_trigger_rule_ids.append(verify_rule.id)

    def _process_field(
        self,
        field: FieldInfo,
        visibility_groups: Dict[str, VisibilityGroup]
    ):
        """Process a single field and generate rules."""
        logic = field.logic or ""

        # Check if should skip
        if should_skip_logic(logic):
            self.result.skipped_fields += 1
            return

        # Parse logic
        parsed = self.logic_parser.parse(logic)

        if parsed.should_skip:
            self.result.skipped_fields += 1
            return

        # Check if this field is a visibility source
        if field.name in visibility_groups:
            group = visibility_groups[field.name]
            rules = self._generate_visibility_rules(field, group)
            for rule in rules:
                self._add_rule(field.id, rule)

        # Check if destination field (don't generate source rules for it)
        if is_destination_field_logic(logic):
            # Generate MAKE_DISABLED if non-editable
            if parsed.is_disabled_rule:
                rule = self.standard_builder.build_enabled_rule(
                    [field.id], [field.id], ["Disable"], make_enabled=False
                )
                self._add_rule(field.id, rule)
            return

        # Generate rules based on parsed logic
        self._generate_rules_for_field(field, parsed)

    def _generate_rules_for_field(self, field: FieldInfo, parsed: ParsedLogic):
        """Generate rules for a field based on parsed logic."""
        # Get rule selections from matcher
        selections = self.matcher.match_all(
            parsed.original_text,
            {'name': field.name, 'field_type': field.field_type, 'variable_name': field.variable_name},
            use_llm=True
        )

        for selection in selections:
            if selection.confidence >= self.llm_threshold:
                self.result.deterministic_matches += 1
            else:
                self.result.llm_fallbacks += 1

            rule = self._build_rule_from_selection(field, parsed, selection)
            if rule:
                self._add_rule(field.id, rule)

        # Handle special cases not covered by selections
        self._handle_special_cases(field, parsed)

    def _build_rule_from_selection(
        self,
        field: FieldInfo,
        parsed: ParsedLogic,
        selection: RuleSelection
    ) -> Optional[GeneratedRule]:
        """Build a rule from a selection."""
        action = selection.action_type

        if action == "SKIP" or action == "UNKNOWN":
            return None

        # VERIFY rules
        if action == "VERIFY" and selection.source_type:
            return self._build_verify_rule(field, selection, parsed)

        # OCR rules
        if action == "OCR" and selection.source_type:
            return self._build_ocr_rule(field, selection)

        # Visibility rules (handled separately via visibility groups)
        if action in ["MAKE_VISIBLE", "MAKE_INVISIBLE"]:
            return None  # Handled in visibility groups

        # Mandatory rules
        if action in ["MAKE_MANDATORY", "MAKE_NON_MANDATORY"]:
            return None  # Handled with visibility

        # Disabled rules
        if action == "MAKE_DISABLED":
            return self.standard_builder.create_disabled_rule(
                field.id, field.id
            )

        # EXT_DROP_DOWN
        if action == "EXT_DROP_DOWN":
            return self.standard_builder.build_ext_dropdown_rule(field.id)

        # CONVERT_TO (uppercase)
        if action == "CONVERT_TO":
            return self.standard_builder.build_convert_to_rule(field.id, "UPPER_CASE")

        return None

    def _build_verify_rule(
        self,
        field: FieldInfo,
        selection: RuleSelection,
        parsed: ParsedLogic
    ) -> GeneratedRule:
        """Build a VERIFY rule."""
        # Find destination fields from intra-panel refs
        field_mappings = {}

        if self.intra_panel_refs:
            field_mappings = self._find_verify_destinations(
                field.name,
                selection.source_type
            )

        return self.verify_builder.build(
            source_type=selection.source_type,
            source_field_id=field.id,
            field_mappings=field_mappings if field_mappings else None
        )

    def _build_ocr_rule(
        self,
        field: FieldInfo,
        selection: RuleSelection
    ) -> Optional[GeneratedRule]:
        """Build an OCR rule."""
        # Find destination field
        dest_field = self.field_matcher.find_ocr_destination(field.name)

        if dest_field:
            return self.ocr_builder.build(
                source_type=selection.source_type,
                upload_field_id=field.id,
                output_field_id=dest_field.id
            )

        return None

    def _handle_special_cases(self, field: FieldInfo, parsed: ParsedLogic):
        """Handle special rule cases."""
        logic = parsed.original_text.lower()

        # GSTIN_WITH_PAN cross-validation
        if 'pan with gst' in logic or 'gstin and pan' in logic:
            pan_field = self.field_matcher.match_field('PAN')
            gstin_field = self.field_matcher.match_field('GSTIN')

            if pan_field and gstin_field:
                rule = self.verify_builder.build_gstin_with_pan(
                    pan_field.id, gstin_field.id
                )
                self._add_rule(field.id, rule)

        # Uppercase conversion
        if 'upper case' in logic or 'uppercase' in logic:
            rule = self.standard_builder.build_convert_to_rule(field.id, "UPPER_CASE")
            self._add_rule(field.id, rule)

    def _generate_visibility_rules(
        self,
        field: FieldInfo,
        group: VisibilityGroup
    ) -> List[GeneratedRule]:
        """Generate visibility rules for a controlling field."""
        rules = []

        # Group destinations by conditional value, action, and whether it's inverse
        by_condition: Dict[Tuple[str, str, bool], List[int]] = defaultdict(list)

        for dest in group.destination_fields:
            action = dest.get('action', 'MAKE_VISIBLE')
            is_inverse = dest.get('is_inverse', False)
            for value in dest.get('conditional_values', []):
                key = (action, value, is_inverse)
                dest_id = dest.get('field_id')
                if dest_id:
                    by_condition[key].append(dest_id)

        # Create consolidated rules
        for (action, value, is_inverse), dest_ids in by_condition.items():
            # Use NOT_IN condition for inverse rules (MAKE_INVISIBLE, MAKE_NON_MANDATORY)
            condition = "NOT_IN" if is_inverse else "IN"
            rule = self.standard_builder.create_conditional_rule(
                action,
                [field.id],
                list(set(dest_ids)),
                [value],
                condition
            )
            rules.append(rule)

        return rules

    def _identify_visibility_groups(self) -> Dict[str, VisibilityGroup]:
        """Identify fields that control visibility of other fields."""
        groups: Dict[str, VisibilityGroup] = {}

        # Use intra-panel references
        if self.intra_panel_refs:
            for panel in self.intra_panel_refs.get('panel_results', []):
                for ref in panel.get('intra_panel_references', []):
                    self._extract_visibility_from_ref(ref, groups)

        # Also scan field logic
        for field in self.fields:
            if field.logic:
                self._extract_visibility_from_logic(field, groups)

        return groups

    def _extract_visibility_from_ref(
        self,
        ref: Dict,
        groups: Dict[str, VisibilityGroup]
    ):
        """Extract visibility relationships from intra-panel reference."""
        # Get the dependent field name (the field that will have visibility controlled)
        dep_field_name = ref.get('field_name', '')
        if not dep_field_name:
            dep_field = ref.get('dependent_field', {})
            if isinstance(dep_field, dict):
                dep_field_name = dep_field.get('field_name', '')
            elif isinstance(dep_field, str):
                dep_field_name = dep_field

        # Get source field name (alternative structure)
        source_field_name = ref.get('source_field', '')
        if isinstance(source_field_name, dict):
            source_field_name = source_field_name.get('field_name', '')

        # Check for direct visibility/visibility_and_mandatory dependency_type
        dependency_type = ref.get('dependency_type', '')
        rule_description = ref.get('rule_description', '')

        if dependency_type in ['visibility', 'visibility_and_mandatory']:
            # This is a visibility rule - source_field controls dependent_field
            controlling_name = source_field_name
            target_field = dep_field_name

            if controlling_name and target_field:
                if controlling_name not in groups:
                    groups[controlling_name] = VisibilityGroup(
                        controlling_field_name=controlling_name,
                        controlling_field_id=self.field_matcher.match_field_id(controlling_name)
                    )

                target_id = self.field_matcher.match_field_id(target_field)
                values = extract_conditional_values(rule_description) or ['Yes']

                # For visibility type, add MAKE_VISIBLE and MAKE_INVISIBLE
                groups[controlling_name].destination_fields.append({
                    'field_name': target_field,
                    'field_id': target_id,
                    'action': 'MAKE_VISIBLE',
                    'conditional_values': values
                })
                groups[controlling_name].destination_fields.append({
                    'field_name': target_field,
                    'field_id': target_id,
                    'action': 'MAKE_INVISIBLE',
                    'conditional_values': values,
                    'is_inverse': True  # Mark as inverse rule
                })

                # For visibility_and_mandatory, also add mandatory rules
                if dependency_type == 'visibility_and_mandatory':
                    groups[controlling_name].destination_fields.append({
                        'field_name': target_field,
                        'field_id': target_id,
                        'action': 'MAKE_MANDATORY',
                        'conditional_values': values
                    })
                    groups[controlling_name].destination_fields.append({
                        'field_name': target_field,
                        'field_id': target_id,
                        'action': 'MAKE_NON_MANDATORY',
                        'conditional_values': values,
                        'is_inverse': True
                    })

        # Extract logic text from various locations
        logic_text = (
            ref.get('logic_text', '') or
            ref.get('rule_description', '') or
            ref.get('logic_summary', '') or
            ref.get('dependency_notes', '') or
            ''
        )

        # Get references list
        refs = ref.get('references', [])

        # Also check for depends_on structure
        depends_on = ref.get('depends_on', [])
        if depends_on:
            for dep in depends_on:
                if not isinstance(dep, dict):
                    continue

                dep_type = dep.get('dependency_type', '')
                controlling_name = dep.get('target_field', '')
                logic = dep.get('logic_excerpt', '') or dep.get('condition', '') or ''

                if 'visibility' in dep_type or 'visible' in logic.lower():
                    if controlling_name and source_field_name:
                        if controlling_name not in groups:
                            groups[controlling_name] = VisibilityGroup(
                                controlling_field_name=controlling_name,
                                controlling_field_id=self.field_matcher.match_field_id(controlling_name)
                            )

                        source_id = self.field_matcher.match_field_id(source_field_name)
                        values = extract_conditional_values(logic)

                        actions = self._extract_actions_from_logic(logic)
                        for action in actions:
                            groups[controlling_name].destination_fields.append({
                                'field_name': source_field_name,
                                'field_id': source_id,
                                'action': action,
                                'conditional_values': values or ['Yes']
                            })

        # Process references list
        for r in refs:
            if not isinstance(r, dict):
                continue

            ref_type = r.get('reference_type', '') or r.get('dependency_type', '')
            logic = (
                r.get('logic_excerpt', '') or
                r.get('description', '') or
                r.get('dependency_description', '') or
                r.get('condition_description', '') or
                r.get('raw_logic_excerpt', '') or
                ''
            )

            # Check for visibility or mandatory references
            if 'visibility' in ref_type.lower() or 'mandatory' in ref_type.lower():
                # Get the controlling field name
                controlling_name = (
                    r.get('referenced_field', '') or
                    r.get('referenced_field_name', '') or
                    r.get('target_field', '')
                )
                if not controlling_name:
                    continue

                # Initialize group if needed
                if controlling_name not in groups:
                    groups[controlling_name] = VisibilityGroup(
                        controlling_field_name=controlling_name,
                        controlling_field_id=self.field_matcher.match_field_id(controlling_name)
                    )

                # Determine which field is the destination
                target_field = dep_field_name or source_field_name
                if not target_field:
                    continue

                dep_id = self.field_matcher.match_field_id(target_field)
                values = extract_conditional_values(logic)

                # Determine action types from logic
                actions = self._extract_actions_from_logic(logic)

                for action in actions:
                    groups[controlling_name].destination_fields.append({
                        'field_name': target_field,
                        'field_id': dep_id,
                        'action': action,
                        'conditional_values': values or ['Yes']
                    })

        # Also check logic_text for visibility patterns
        if logic_text and (dep_field_name or source_field_name):
            self._extract_visibility_from_logic_text(
                logic_text,
                dep_field_name or source_field_name,
                groups
            )

    def _extract_actions_from_logic(self, logic: str) -> List[str]:
        """Extract action types from logic text."""
        actions = []
        logic_lower = logic.lower()

        if 'visible' in logic_lower and 'invisible' not in logic_lower:
            actions.append('MAKE_VISIBLE')
        if 'invisible' in logic_lower:
            actions.append('MAKE_INVISIBLE')
        if 'mandatory' in logic_lower and 'non-mandatory' not in logic_lower:
            actions.append('MAKE_MANDATORY')
        if 'non-mandatory' in logic_lower:
            actions.append('MAKE_NON_MANDATORY')

        if not actions:
            actions = ['MAKE_VISIBLE']  # Default

        return actions

    def _extract_visibility_from_logic_text(
        self,
        logic_text: str,
        field_name: str,
        groups: Dict[str, VisibilityGroup]
    ):
        """Extract visibility rules from logic_text field."""
        # Pattern: if field 'X' values is Y then visible
        pattern = r"if\s+(?:the\s+)?field\s*['\"]([^'\"]+)['\"]\s+values?\s+is\s+([^\s,\.]+)\s+then\s+(visible|invisible|mandatory)"

        for match in re.finditer(pattern, logic_text, re.IGNORECASE):
            controlling_name = match.group(1)
            value = match.group(2)
            action_word = match.group(3).upper()

            if controlling_name not in groups:
                groups[controlling_name] = VisibilityGroup(
                    controlling_field_name=controlling_name,
                    controlling_field_id=self.field_matcher.match_field_id(controlling_name)
                )

            action_type = f"MAKE_{action_word}" if action_word != 'MANDATORY' else 'MAKE_MANDATORY'
            field_id = self.field_matcher.match_field_id(field_name)

            groups[controlling_name].destination_fields.append({
                'field_name': field_name,
                'field_id': field_id,
                'action': action_type,
                'conditional_values': [value]
            })

    def _extract_visibility_from_logic(
        self,
        field: FieldInfo,
        groups: Dict[str, VisibilityGroup]
    ):
        """Extract visibility relationships from field logic."""
        logic = field.logic or ""

        # Pattern: if field 'X' value is Y then visible
        pattern = r"if\s+(?:the\s+)?field\s+['\"]([^'\"]+)['\"]\s+values?\s+is\s+([^\s,]+)\s+then\s+(visible|invisible|mandatory)"

        for match in re.finditer(pattern, logic, re.IGNORECASE):
            controlling_name = match.group(1)
            value = match.group(2)
            action = match.group(3).upper()

            if controlling_name not in groups:
                groups[controlling_name] = VisibilityGroup(
                    controlling_field_name=controlling_name,
                    controlling_field_id=self.field_matcher.match_field_id(controlling_name)
                )

            action_type = f"MAKE_{action}" if action != 'MANDATORY' else 'MAKE_MANDATORY'

            groups[controlling_name].destination_fields.append({
                'field_name': field.name,
                'field_id': field.id,
                'action': action_type,
                'conditional_values': [value]
            })

    def _identify_ocr_verify_chains(self) -> List[OCRVerifyChain]:
        """Identify OCR -> VERIFY rule chains."""
        chains = []

        # Common patterns
        ocr_verify_patterns = [
            ('Upload PAN', 'PAN', 'PAN_IMAGE', 'PAN_NUMBER'),
            ('GSTIN IMAGE', 'GSTIN', 'GSTIN_IMAGE', 'GSTIN'),
            ('Cancelled Cheque', 'IFSC', 'CHEQUEE', 'BANK_ACCOUNT_NUMBER'),
            ('MSME Image', 'MSME Registration Number', 'MSME', 'MSME_UDYAM_REG_NUMBER'),
        ]

        for ocr_name, verify_name, ocr_type, verify_type in ocr_verify_patterns:
            ocr_field = self.field_matcher.match_field(ocr_name)
            verify_field = self.field_matcher.match_field(verify_name)

            if ocr_field and verify_field:
                chains.append(OCRVerifyChain(
                    ocr_field_name=ocr_name,
                    ocr_field_id=ocr_field.id,
                    verify_field_name=verify_name,
                    verify_field_id=verify_field.id,
                    ocr_source_type=ocr_type,
                    verify_source_type=verify_type
                ))

        return chains

    def _find_verify_destinations(
        self,
        source_field_name: str,
        source_type: str
    ) -> Dict[str, int]:
        """Find destination field mappings for VERIFY rule."""
        mappings = {}

        if not self.intra_panel_refs:
            return mappings

        source_lower = source_field_name.lower()

        # Also look for verification keywords
        verify_keywords = ['verification', 'validation', source_lower]

        for panel in self.intra_panel_refs.get('panel_results', []):
            for ref in panel.get('intra_panel_references', []):
                # Check dependent_field structure
                dep_field = ref.get('dependent_field', {})
                if dep_field:
                    refs = ref.get('references', [])
                    logic_text = ref.get('logic_text', '')

                    for r in refs:
                        ref_type = r.get('reference_type', '')
                        ref_name = r.get('referenced_field_name', '').lower()
                        dep_desc = r.get('dependency_description', '').lower()

                        # Check if this field gets data from verification
                        is_verify_dest = (
                            ref_type == 'data_source' or
                            'verification' in dep_desc or
                            'validation' in dep_desc or
                            'will come from' in dep_desc
                        )

                        if is_verify_dest:
                            # Check if the reference is to our source field
                            if any(kw in ref_name or kw in dep_desc for kw in verify_keywords):
                                dep_name = dep_field.get('field_name', '')
                                field = self.field_matcher.match_field(dep_name)
                                if field:
                                    # Try to match to ordinal name
                                    ordinal_name = self._guess_ordinal_name(dep_name, source_type)
                                    if ordinal_name:
                                        mappings[ordinal_name] = field.id

                    # Also check logic_text for "Data will come from X verification"
                    if logic_text and ('verification' in logic_text.lower() or 'validation' in logic_text.lower()):
                        if source_lower in logic_text.lower():
                            dep_name = dep_field.get('field_name', '')
                            field = self.field_matcher.match_field(dep_name)
                            if field:
                                ordinal_name = self._guess_ordinal_name(dep_name, source_type)
                                if ordinal_name and ordinal_name not in mappings:
                                    mappings[ordinal_name] = field.id

        return mappings

    def _guess_ordinal_name(self, field_name: str, source_type: str) -> Optional[str]:
        """Guess the ordinal name for a destination field."""
        name_lower = field_name.lower()

        # PAN ordinals (schema 360 - 10 destination fields)
        if source_type == 'PAN_NUMBER':
            if 'holder name' in name_lower or 'pan name' in name_lower:
                return 'Fullname'
            if 'type' in name_lower and 'pan' in name_lower:
                return 'Pan type'
            if 'status' in name_lower and 'aadhaar' not in name_lower:
                return 'Pan retrieval status'
            if 'aadhaar' in name_lower:
                return 'Aadhaar seeding status'

        # GSTIN ordinals (schema 355 - 21 destination fields)
        if source_type == 'GSTIN':
            if 'trade name' in name_lower or 'tradename' in name_lower:
                return 'Trade name'
            if 'legal name' in name_lower or 'longname' in name_lower:
                return 'Longname'
            if 'reg date' in name_lower or 'registration date' in name_lower:
                return 'Reg date'
            if name_lower == 'city':
                return 'City'
            if name_lower == 'type':
                return 'Type'
            if 'building' in name_lower:
                return 'Building number'
            if 'flat' in name_lower:
                return 'Flat number'
            if name_lower == 'district' or 'district' in name_lower:
                return 'District code'
            if name_lower == 'state' or (name_lower.endswith('state') and 'state' in name_lower):
                return 'State code'
            if name_lower == 'street':
                return 'Street'
            if 'pin' in name_lower or 'pincode' in name_lower:
                return 'Pincode'
            if 'locality' in name_lower:
                return 'Locality'
            if 'landmark' in name_lower:
                return 'Landmark'
            if 'constitution' in name_lower:
                return 'Constitution of business'

        # BANK_ACCOUNT_NUMBER ordinals (schema 361 - 4 destination fields)
        if source_type == 'BANK_ACCOUNT_NUMBER':
            if 'beneficiary' in name_lower or 'account holder' in name_lower:
                return 'Bank Beneficiary Name'
            if 'reference' in name_lower:
                return 'Bank Reference'
            if 'verification status' in name_lower or 'verify status' in name_lower:
                return 'Verification Status'
            if 'message' in name_lower:
                return 'Message'

        # MSME_UDYAM_REG_NUMBER ordinals (schema 337 - 21 destination fields)
        if source_type == 'MSME_UDYAM_REG_NUMBER':
            if 'enterprise name' in name_lower or 'name of enterprise' in name_lower:
                return 'Name Of Enterprise'
            if 'major activity' in name_lower:
                return 'Major Activity'
            if 'social category' in name_lower:
                return 'Social Category'
            if 'enterprise type' in name_lower or name_lower == 'enterprise':
                return 'Enterprise'
            if 'commencement' in name_lower or 'date of commencement' in name_lower:
                return 'Date Of Commencement'
            if 'dic' in name_lower:
                return 'Dic Name'
            if name_lower == 'state' or 'msme state' in name_lower:
                return 'State'
            if 'modified' in name_lower:
                return 'Modified Date'
            if 'expiry' in name_lower:
                return 'Expiry Date'
            if 'address' in name_lower:
                return 'Address Line1'
            if 'building' in name_lower:
                return 'Building'
            if 'street' in name_lower:
                return 'Street'
            if 'area' in name_lower:
                return 'Area'
            if name_lower == 'city' or 'msme city' in name_lower:
                return 'City'
            if 'pin' in name_lower and 'msme' in name_lower:
                return 'Pin'
            if 'district' in name_lower:
                return 'Disrtict'
            if 'classification year' in name_lower:
                return 'Classification Year'
            if 'classification date' in name_lower:
                return 'Classification Date'

        return None

    def _add_rule(self, field_id: int, rule: GeneratedRule):
        """Add a rule to the collection."""
        rule.field_name = self.field_matcher.get_field_by_id(field_id).name if field_id else None
        self.rules_by_field[field_id].append(rule)
        self.all_rules.append(rule)

    def _rebuild_rules_by_field(self):
        """Rebuild rules_by_field mapping after consolidation."""
        self.rules_by_field = defaultdict(list)

        for rule in self.all_rules:
            # Rules are placed on source fields
            if rule.source_ids:
                for source_id in rule.source_ids:
                    self.rules_by_field[source_id].append(rule)

    def _calculate_rule_stats(self):
        """Calculate rule statistics."""
        for rule in self.all_rules:
            action = rule.action_type
            if action not in self.result.rules_by_type:
                self.result.rules_by_type[action] = 0
            self.result.rules_by_type[action] += 1

    def save_schema(self, output_path: str):
        """Save populated schema to file."""
        if self.result.populated_schema:
            save_json(self.result.populated_schema, output_path)

    def save_report(self, report_path: str):
        """Save extraction report to file."""
        report = create_report(
            self.result,
            report_path,
            self.schema_path,
            self.bud_document_path
        )
        save_json(report, report_path)

    def get_populated_schema(self) -> Dict:
        """Get the populated schema."""
        return self.result.populated_schema
