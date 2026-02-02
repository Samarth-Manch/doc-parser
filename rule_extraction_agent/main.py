"""Main rule extraction pipeline."""

import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime

from .models import id_generator, FieldInfo
from .schema_lookup import RuleSchemaLookup, OCR_VERIFY_CHAINS
from .id_mapper import DestinationIdMapper
from .field_matcher import FieldMatcher
from .logic_parser import LogicParser
from .rule_tree import RuleTree, VisibilityGrouper
from .matchers.pipeline import MatchingPipeline, VisibilityRuleGrouper
from .rule_builders.standard_builder import StandardRuleBuilder
from .rule_builders.verify_builder import VerifyRuleBuilder
from .rule_builders.ocr_builder import OcrRuleBuilder
from .llm_fallback import LLMFallback, RuleValidator


class RuleExtractionAgent:
    """Main agent for extracting rules from BUD documents."""

    def __init__(
        self,
        schema_path: str = None,
        llm_threshold: float = 0.7,
        verbose: bool = False,
        validate: bool = False
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

        # LLM fallback
        self.llm_fallback = LLMFallback()
        self.llm_threshold = llm_threshold

        # Validator
        self.validator = RuleValidator(self.schema_lookup)

        # Options
        self.verbose = verbose
        self.validate = validate

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

        # Extract intra-panel references
        intra_refs = self._extract_intra_refs(intra_panel)

        if self.verbose:
            print(f"Loaded {len(intra_refs)} intra-panel references")

        # Phase 1: Identify visibility controlling fields
        visibility_groups = self._identify_visibility_groups(all_fields, intra_refs)

        # Phase 2: Generate rules for each field
        all_generated_rules = []
        field_rules_map = {}  # field_id -> list of rules

        for field in all_fields:
            field_id = field.get('id')
            field_name = field.get('formTag', {}).get('name', '')

            # Get logic from intra-panel refs
            logic_text = self._get_field_logic(field_name, intra_refs)

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

        # Phase 4: Link OCR -> VERIFY chains
        self._link_ocr_verify_chains(all_generated_rules)

        # Phase 5: Consolidate rules
        consolidated_rules = self._consolidate_rules(all_generated_rules)
        self.stats["total_rules_generated"] = len(consolidated_rules)

        # Count rules by type
        for rule in consolidated_rules:
            action = rule.get('actionType', 'UNKNOWN')
            self.stats["rules_by_type"][action] += 1

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
        """Identify fields grouped by their controlling field."""
        groups = defaultdict(list)

        for ref in intra_refs:
            dep_type = ref.get('dependency_type', ref.get('reference_type', ''))

            # Also check reference_details for relationship_type
            ref_details = ref.get('reference_details', {})
            if isinstance(ref_details, dict):
                detail_type = ref_details.get('relationship_type', '')
                if detail_type in ['visibility_control', 'mandatory_control']:
                    dep_type = detail_type

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

                if isinstance(source_name, dict):
                    source_name = source_name.get('field_name', '')

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
        """Consolidate and deduplicate rules."""
        # Group rules by (actionType, sourceIds, condition, conditionalValues)
        GROUPABLE_ACTIONS = [
            'MAKE_DISABLED', 'MAKE_VISIBLE', 'MAKE_INVISIBLE',
            'MAKE_MANDATORY', 'MAKE_NON_MANDATORY'
        ]

        groups = defaultdict(list)
        non_groupable = []

        for rule in all_rules:
            action = rule.get('actionType')
            if action in GROUPABLE_ACTIONS:
                key = (
                    action,
                    tuple(sorted(rule.get('sourceIds', []))),
                    rule.get('condition'),
                    tuple(sorted(rule.get('conditionalValues', [])))
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
                # Merge: combine all destinationIds
                merged = rules[0].copy()
                all_dest_ids = set()
                for r in rules:
                    all_dest_ids.update(r.get('destinationIds', []))
                merged['destinationIds'] = sorted(list(all_dest_ids))
                consolidated.append(merged)

        consolidated.extend(non_groupable)

        # Remove exact duplicates
        seen = set()
        deduplicated = []
        for rule in consolidated:
            key = (
                rule.get('actionType'),
                tuple(sorted(rule.get('sourceIds', []))),
                tuple(sorted(rule.get('destinationIds', []))),
                rule.get('condition'),
                tuple(sorted(rule.get('conditionalValues', [])))
            )
            if key not in seen:
                seen.add(key)
                deduplicated.append(rule)

        return deduplicated

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

    args = parser.parse_args()

    # Generate output path if not provided
    if not args.output:
        schema_path = Path(args.schema)
        args.output = str(schema_path.parent / f"{schema_path.stem}_populated.json")

    # Create agent and process
    agent = RuleExtractionAgent(
        llm_threshold=args.llm_threshold,
        verbose=args.verbose,
        validate=args.validate
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
