#!/usr/bin/env python3
"""
Rule Type Placement Agent (Stage 1)
===================================
Determines which rules (actionType + sourceType) each field needs using keyword tree traversal
and places skeleton rules on the CORRECT fields.

Input:
- Schema JSON from extract_fields_complete.py
- BUD Document parsed fields with logic
- Keyword tree: rule_extractor/static/keyword_tree.json
- Intra-panel references JSON (from dispatcher)
- Inter-panel references JSON (from dispatcher)

Output:
- Schema with skeleton rules (actionType, sourceType set; sourceIds/destinationIds empty)
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@dataclass
class SkeletonRule:
    """Represents a skeleton rule to be placed on a field"""
    action_type: str
    source_type: Optional[str] = None
    processing_type: str = "CLIENT"
    schema_id: Optional[int] = None
    source_ids: List[int] = field(default_factory=list)
    destination_ids: List[int] = field(default_factory=list)
    conditional_values: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    condition_value_type: str = "TEXT"
    post_trigger_rule_ids: List[int] = field(default_factory=list)
    params: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output"""
        rule = {
            "actionType": self.action_type,
            "processingType": self.processing_type,
            "sourceIds": self.source_ids,
            "destinationIds": self.destination_ids,
            "conditionalValues": self.conditional_values,
            "conditionValueType": self.condition_value_type,
            "postTriggerRuleIds": self.post_trigger_rule_ids,
            "button": "",
            "searchable": False,
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }
        if self.source_type:
            rule["sourceType"] = self.source_type
        if self.condition:
            rule["condition"] = self.condition
        if self.params:
            rule["params"] = self.params
        if self.schema_id:
            rule["_schema_id"] = self.schema_id
        if self.notes:
            rule["_notes"] = self.notes
        return rule


class RuleTypePlacementAgent:
    """Stage 1 Agent: Determines rule types and places skeleton rules"""

    def __init__(self, keyword_tree_path: str):
        """Initialize with keyword tree"""
        logger.info(f"Initializing RuleTypePlacementAgent with keyword tree: {keyword_tree_path}")
        self.keyword_tree = self._load_keyword_tree(keyword_tree_path)
        self.skip_patterns = self._compile_skip_patterns()
        self.destination_patterns = self._compile_destination_patterns()
        self.visibility_source_patterns = self._compile_visibility_patterns()

        # Tracking for aggregated visibility rules
        self.visibility_rules_by_source: Dict[str, Dict[str, Set[str]]] = {}

        # Field name to ID mapping (to be populated from schema)
        self.field_name_to_id: Dict[str, int] = {}
        self.field_id_to_name: Dict[int, str] = {}

    def _load_keyword_tree(self, path: str) -> Dict:
        """Load keyword tree from JSON file"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded keyword tree with {len(data.get('tree', {}))} action types")
        return data

    def _compile_skip_patterns(self) -> List[re.Pattern]:
        """Compile skip patterns from keyword tree"""
        patterns = self.keyword_tree.get('skip_patterns', {}).get('patterns', [])
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        logger.debug(f"Compiled {len(compiled)} skip patterns")
        return compiled

    def _compile_destination_patterns(self) -> List[re.Pattern]:
        """Compile destination field patterns from keyword tree"""
        patterns = self.keyword_tree.get('destination_field_patterns', {}).get('patterns', [])
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        logger.debug(f"Compiled {len(compiled)} destination patterns")
        return compiled

    def _compile_visibility_patterns(self) -> List[re.Pattern]:
        """Compile visibility source extraction patterns"""
        patterns = self.keyword_tree.get('visibility_source_extraction', {}).get('patterns', [])
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        logger.debug(f"Compiled {len(compiled)} visibility source patterns")
        return compiled

    def _should_skip(self, logic: str) -> bool:
        """Check if logic should be skipped (EXECUTE patterns)"""
        for pattern in self.skip_patterns:
            if pattern.search(logic):
                logger.debug(f"Skipping logic due to pattern match: {pattern.pattern}")
                return True
        return False

    def _is_destination_field(self, logic: str) -> bool:
        """Check if field is a destination field (receives data from validation/OCR)"""
        for pattern in self.destination_patterns:
            if pattern.search(logic):
                return True
        return False

    def _extract_visibility_source(self, logic: str) -> Optional[str]:
        """Extract the controlling field name from visibility logic"""
        for pattern in self.visibility_source_patterns:
            match = pattern.search(logic)
            if match:
                return match.group(1)

        # Additional patterns for common BUD formats
        additional_patterns = [
            r'if\s+(?:the\s+)?(?:field\s+)?["\']([^"\']+)["\']',
            r'based\s+on\s+["\']?([^"\']+)["\']?\s+selection',
            r'if\s+["\']([^"\']+)["\']?\s+is',
        ]
        for pattern in additional_patterns:
            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_conditional_value(self, logic: str) -> Optional[str]:
        """Extract conditional value from logic (e.g., 'yes', 'no')"""
        patterns = [
            r'values?\s+is\s+["\']?([^"\']+?)["\']?\s+then',
            r'is\s+selected\s+as\s+["\']?([^"\']+?)["\']?',
            r'=\s*["\']?([^"\']+?)["\']?(?:\s+then|\s*$)',
            r'is\s+["\']?([yY]es|[nN]o)["\']?',
        ]
        for pattern in patterns:
            match = re.search(pattern, logic, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _match_l1_keywords(self, logic: str) -> List[Tuple[str, Dict]]:
        """Match L1 (action type) keywords against logic text"""
        matches = []
        tree = self.keyword_tree.get('tree', {})

        logic_lower = logic.lower()

        for action_type, action_config in tree.items():
            # Check negative phrases first
            negative_phrases = action_config.get('negative_phrases', [])
            skip = False
            for neg_phrase in negative_phrases:
                if neg_phrase.lower() in logic_lower:
                    skip = True
                    break
            if skip:
                continue

            # Check BUD phrases (most specific)
            bud_phrases = action_config.get('bud_phrases', [])
            for phrase in bud_phrases:
                if phrase.lower() in logic_lower:
                    matches.append((action_type, action_config))
                    break
            else:
                # Check keywords (more general)
                keywords = action_config.get('keywords', [])
                for keyword in keywords:
                    if keyword.lower() in logic_lower:
                        matches.append((action_type, action_config))
                        break

        return matches

    def _match_l2_keywords(self, logic: str, action_config: Dict, return_all: bool = False) -> List[Tuple[str, Dict]]:
        """Match L2 (source type) keywords for a given action type

        Args:
            logic: The field logic text
            action_config: The action type configuration
            return_all: If True, return all matches; if False, return only best match

        Returns:
            List of (source_type, source_config) tuples
        """
        children = action_config.get('children', {})
        if not children:
            return []

        logic_lower = logic.lower()
        matches = []

        for source_type, source_config in children.items():
            score = 0

            # Check exclude phrases
            exclude_phrases = source_config.get('exclude_phrases', [])
            skip = False
            for phrase in exclude_phrases:
                if phrase.lower() in logic_lower:
                    skip = True
                    break
            if skip:
                continue

            # Check BUD phrases (highest priority)
            bud_phrases = source_config.get('bud_phrases', [])
            for phrase in bud_phrases:
                if phrase.lower() in logic_lower:
                    score += 10
                    break

            # Check keywords
            keywords = source_config.get('keywords', [])
            for keyword in keywords:
                if keyword.lower() in logic_lower:
                    score += 1

            if score > 0:
                matches.append((source_type, source_config, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[2], reverse=True)

        if return_all:
            return [(st, sc) for st, sc, _ in matches]
        elif matches:
            return [(matches[0][0], matches[0][1])]
        return []

    def _determine_rules_for_field(
        self,
        field_name: str,
        field_type: str,
        logic: str,
        panel: str,
        intra_refs: List[Dict] = None
    ) -> List[SkeletonRule]:
        """Determine which rules a field needs based on its logic"""
        rules = []

        if not logic:
            return rules

        # Check skip patterns
        if self._should_skip(logic):
            logger.info(f"Skipping field '{field_name}' due to EXECUTE pattern")
            return rules

        # Check if this is a destination field
        is_destination = self._is_destination_field(logic)

        if is_destination:
            # Destination fields only get MAKE_DISABLED if they mention non-editable
            if 'non-editable' in logic.lower() or 'non editable' in logic.lower():
                rule = SkeletonRule(
                    action_type="MAKE_DISABLED",
                    source_type="FORM_FILL_METADATA",
                    processing_type="CLIENT",
                    schema_id=314,
                    notes=f"Destination field (receives data from validation/OCR)"
                )
                rules.append(rule)
            logger.debug(f"Field '{field_name}' is destination field, skipping rule generation")
            return rules

        # Match L1 keywords
        l1_matches = self._match_l1_keywords(logic)

        for action_type, action_config in l1_matches:
            # Handle action types that don't have children
            if action_type in ['MAKE_VISIBLE', 'MAKE_INVISIBLE', 'MAKE_MANDATORY',
                               'MAKE_NON_MANDATORY', 'MAKE_DISABLED', 'MAKE_ENABLED']:
                # These are handled separately via visibility source extraction
                continue

            # Skip strict rules unless explicit
            if action_config.get('strict_rule'):
                logger.debug(f"Skipping strict rule {action_type} for field '{field_name}'")
                continue

            # Match L2 keywords - for VERIFY action, return all matches (PAN validation + GSTIN_WITH_PAN cross-validation)
            return_all = action_type == "VERIFY"
            l2_matches = self._match_l2_keywords(logic, action_config, return_all=return_all)

            for l2_match in l2_matches:
                source_type, source_config = l2_match
                rule = SkeletonRule(
                    action_type=action_type,
                    source_type=source_type,
                    processing_type=source_config.get('processing_type', 'CLIENT'),
                    schema_id=source_config.get('schema_id'),
                    notes=f"Matched from logic: {logic[:100]}..."
                )
                rules.append(rule)
                logger.info(f"Field '{field_name}': {action_type}/{source_type}")

            if not action_config.get('children') and not l2_matches:
                # Action type without children (e.g., MAKE_VISIBLE has schema_id at root)
                schema_id = action_config.get('schema_id')
                rule = SkeletonRule(
                    action_type=action_type,
                    processing_type=action_config.get('processing_type', 'CLIENT'),
                    schema_id=schema_id,
                    notes=f"Matched from logic (no source type): {logic[:100]}..."
                )
                rules.append(rule)
                logger.info(f"Field '{field_name}': {action_type}")

        # Special handling: If "perform pan validation" is present, add PAN_NUMBER rule
        # even if GSTIN_WITH_PAN was matched (the exclude_phrases would normally block it)
        if 'perform pan validation' in logic.lower() or 'pan validation' in logic.lower():
            # Check if we haven't already added a VERIFY/PAN_NUMBER rule
            has_pan_number = any(r.action_type == 'VERIFY' and r.source_type == 'PAN_NUMBER' for r in rules)
            if not has_pan_number:
                tree = self.keyword_tree.get('tree', {})
                verify_config = tree.get('VERIFY', {}).get('children', {}).get('PAN_NUMBER', {})
                rule = SkeletonRule(
                    action_type="VERIFY",
                    source_type="PAN_NUMBER",
                    processing_type=verify_config.get('processing_type', 'SERVER'),
                    schema_id=verify_config.get('schema_id', 360),
                    notes=f"PAN validation rule"
                )
                rules.append(rule)
                logger.info(f"Field '{field_name}': VERIFY/PAN_NUMBER (special case)")

        # Special handling: If "gstin validation" is present, add GSTIN rule
        if 'gstin validation' in logic.lower() or 'perform gstin validation' in logic.lower():
            has_gstin = any(r.action_type == 'VERIFY' and r.source_type == 'GSTIN' for r in rules)
            if not has_gstin:
                tree = self.keyword_tree.get('tree', {})
                verify_config = tree.get('VERIFY', {}).get('children', {}).get('GSTIN', {})
                rule = SkeletonRule(
                    action_type="VERIFY",
                    source_type="GSTIN",
                    processing_type=verify_config.get('processing_type', 'SERVER'),
                    schema_id=verify_config.get('schema_id', 355),
                    notes=f"GSTIN validation rule"
                )
                rules.append(rule)
                logger.info(f"Field '{field_name}': VERIFY/GSTIN (special case)")

        # Check for CONVERT_TO (upper case) - avoid duplicates
        if 'upper case' in logic.lower() or 'uppercase' in logic.lower():
            has_upper_case = any(r.action_type == 'CONVERT_TO' and r.source_type == 'UPPER_CASE' for r in rules)
            if not has_upper_case:
                rule = SkeletonRule(
                    action_type="CONVERT_TO",
                    source_type="UPPER_CASE",
                    processing_type="CLIENT",
                    schema_id=345,
                    notes="Upper case conversion"
                )
                rules.append(rule)
                logger.info(f"Field '{field_name}': CONVERT_TO/UPPER_CASE")

        # Check for FILE fields - add COPY_TO_DOCUMENT_STORAGE_ID
        if field_type == "FILE":
            rule = SkeletonRule(
                action_type="COPY_TO_DOCUMENT_STORAGE_ID",
                source_type="FORM_FILL_METADATA",
                processing_type="CLIENT",
                notes="Auto-generated for FILE field"
            )
            rules.append(rule)

        return rules

    def _process_visibility_rules(
        self,
        fields: List[Dict],
        intra_panel_refs: Dict[str, List[Dict]],
        inter_panel_refs: List[Dict]
    ) -> Dict[str, List[SkeletonRule]]:
        """
        Process visibility/mandatory rules - place on CONTROLLING field, not destination.
        Returns a mapping of controlling field name to rules with destinations.
        """
        visibility_rules: Dict[str, List[Dict]] = {}  # source_field -> list of {action_type, destinations, condition_value}

        # Process intra-panel references
        for panel_name, refs in intra_panel_refs.items():
            for ref in refs:
                relationship = ref.get('source_fields', [{}])[0].get('relationship_type', '')

                if relationship in ['VISIBILITY', 'VISIBILITY_AND_MANDATORY']:
                    source_field = ref['source_fields'][0]['field_name']
                    dest_field = ref['dependent_field']
                    condition_desc = ref['source_fields'][0].get('condition_description', '')

                    # Extract condition value
                    cond_value = self._extract_conditional_value(condition_desc)

                    if source_field not in visibility_rules:
                        visibility_rules[source_field] = []

                    # MAKE_VISIBLE when condition is met
                    visibility_rules[source_field].append({
                        'action_type': 'MAKE_VISIBLE',
                        'destination': dest_field,
                        'condition_value': cond_value or 'Yes',
                        'condition': 'IN'
                    })

                    # MAKE_INVISIBLE when condition is NOT met
                    visibility_rules[source_field].append({
                        'action_type': 'MAKE_INVISIBLE',
                        'destination': dest_field,
                        'condition_value': cond_value or 'Yes',
                        'condition': 'NOT_IN'
                    })

                    # Add MAKE_MANDATORY if visibility_and_mandatory
                    if relationship == 'VISIBILITY_AND_MANDATORY':
                        visibility_rules[source_field].append({
                            'action_type': 'MAKE_MANDATORY',
                            'destination': dest_field,
                            'condition_value': cond_value or 'Yes',
                            'condition': 'IN'
                        })
                        visibility_rules[source_field].append({
                            'action_type': 'MAKE_NON_MANDATORY',
                            'destination': dest_field,
                            'condition_value': cond_value or 'Yes',
                            'condition': 'NOT_IN'
                        })

        # Aggregate rules by source field and action type
        aggregated_rules: Dict[str, List[SkeletonRule]] = {}

        for source_field, rule_list in visibility_rules.items():
            if source_field not in aggregated_rules:
                aggregated_rules[source_field] = []

            # Group by action_type and condition_value
            grouped: Dict[Tuple[str, str, str], List[str]] = {}
            for rule_info in rule_list:
                key = (rule_info['action_type'], rule_info['condition_value'], rule_info['condition'])
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(rule_info['destination'])

            # Create aggregated rules
            for (action_type, cond_value, condition), destinations in grouped.items():
                tree = self.keyword_tree.get('tree', {})
                action_config = tree.get(action_type, {})
                schema_id = action_config.get('schema_id')

                rule = SkeletonRule(
                    action_type=action_type,
                    processing_type="CLIENT",
                    schema_id=schema_id,
                    conditional_values=[cond_value],
                    condition=condition,
                    notes=f"Aggregated visibility rule for destinations: {', '.join(destinations[:3])}..."
                )
                # Note: destination_ids will be populated in Stage 2
                rule._destination_names = destinations  # Store for later resolution
                aggregated_rules[source_field].append(rule)

        return aggregated_rules

    def _build_field_index(self, schema: Dict) -> None:
        """Build field name to ID mapping from schema"""
        self.field_name_to_id = {}
        self.field_id_to_name = {}

        doc_types = schema.get('template', {}).get('documentTypes', [])
        for doc_type in doc_types:
            for field in doc_type.get('formFillMetadatas', []):
                field_id = field.get('id')
                field_name = field.get('formTag', {}).get('name', '')
                if field_id and field_name:
                    self.field_name_to_id[field_name] = field_id
                    self.field_id_to_name[field_id] = field_name

        logger.info(f"Built field index with {len(self.field_name_to_id)} fields")

    def process_schema(
        self,
        schema_path: str,
        extracted_fields_path: str,
        intra_panel_refs_dir: str,
        inter_panel_refs_path: str,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Main processing function - determine rules for all fields

        Args:
            schema_path: Path to the input schema JSON
            extracted_fields_path: Path to extracted fields JSON with logic
            intra_panel_refs_dir: Directory containing intra-panel reference files
            inter_panel_refs_path: Path to inter-panel references JSON
            output_path: Path to write output JSON
        """
        logger.info("=" * 60)
        logger.info("Stage 1: Rule Type Placement Agent")
        logger.info("=" * 60)

        # Load inputs
        logger.info(f"Loading schema from: {schema_path}")
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        logger.info(f"Loading extracted fields from: {extracted_fields_path}")
        with open(extracted_fields_path, 'r', encoding='utf-8') as f:
            extracted_fields = json.load(f)

        # Build field index
        self._build_field_index(schema)

        # Load intra-panel references
        intra_panel_refs: Dict[str, List[Dict]] = {}
        intra_panel_dir = Path(intra_panel_refs_dir)
        for ref_file in intra_panel_dir.glob("*_intra_panel_references.json"):
            logger.info(f"Loading intra-panel refs: {ref_file.name}")
            with open(ref_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                panel_name = data.get('document_info', {}).get('panel_name', '')
                if panel_name:
                    intra_panel_refs[panel_name] = data.get('intra_panel_references', [])

        # Load inter-panel references
        logger.info(f"Loading inter-panel refs from: {inter_panel_refs_path}")
        with open(inter_panel_refs_path, 'r', encoding='utf-8') as f:
            inter_panel_data = json.load(f)
        inter_panel_refs = inter_panel_data.get('cross_panel_references', [])

        # Process visibility rules first (to place on controlling fields)
        visibility_rules = self._process_visibility_rules(
            extracted_fields.get('fields_by_panel', {}),
            intra_panel_refs,
            inter_panel_refs
        )
        logger.info(f"Processed visibility rules for {len(visibility_rules)} controlling fields")

        # Build a mapping of field name to its logic
        field_logic_map: Dict[str, Tuple[str, str, str]] = {}  # name -> (logic, panel, field_type)
        for panel_name, fields in extracted_fields.get('fields_by_panel', {}).items():
            for field in fields:
                field_name = field.get('field_name', '')
                logic = field.get('logic', '')
                field_type = field.get('field_type', '')
                if field_name:
                    field_logic_map[field_name] = (logic, panel_name, field_type)

        # Process schema and add rules
        doc_types = schema.get('template', {}).get('documentTypes', [])

        total_rules_added = 0
        fields_with_rules = 0

        for doc_type in doc_types:
            for field in doc_type.get('formFillMetadatas', []):
                field_name = field.get('formTag', {}).get('name', '')
                field_id = field.get('id')

                if not field_name:
                    continue

                # Get logic for this field
                logic_info = field_logic_map.get(field_name, ('', '', ''))
                logic, panel, field_type = logic_info

                rules_to_add = []

                # 1. Add rules based on field's own logic
                if logic:
                    field_rules = self._determine_rules_for_field(
                        field_name, field_type, logic, panel
                    )
                    rules_to_add.extend(field_rules)

                # 2. Add visibility rules if this field is a controlling field
                if field_name in visibility_rules:
                    vis_rules = visibility_rules[field_name]
                    rules_to_add.extend(vis_rules)
                    logger.info(f"Added {len(vis_rules)} visibility rules to controlling field '{field_name}'")

                # Add rules to field
                if rules_to_add:
                    if 'formFillRules' not in field:
                        field['formFillRules'] = []

                    for rule in rules_to_add:
                        rule_dict = rule.to_dict()
                        rule_dict['sourceIds'] = [field_id] if field_id else []
                        field['formFillRules'].append(rule_dict)
                        total_rules_added += 1

                    fields_with_rules += 1

        # Add metadata
        schema['_stage_1_metadata'] = {
            'processed_at': datetime.now().isoformat(),
            'total_fields': len(self.field_name_to_id),
            'fields_with_rules': fields_with_rules,
            'total_rules_added': total_rules_added,
            'visibility_controlling_fields': len(visibility_rules)
        }

        # Write output
        logger.info(f"Writing output to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2)

        # Summary
        logger.info("=" * 60)
        logger.info("Stage 1 Complete - Summary")
        logger.info("=" * 60)
        logger.info(f"Total fields processed: {len(self.field_name_to_id)}")
        logger.info(f"Fields with rules: {fields_with_rules}")
        logger.info(f"Total skeleton rules added: {total_rules_added}")
        logger.info(f"Visibility controlling fields: {len(visibility_rules)}")
        logger.info(f"Output written to: {output_path}")

        return schema


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Stage 1: Rule Type Placement Agent')
    parser.add_argument('--schema', required=True, help='Path to input schema JSON')
    parser.add_argument('--extracted-fields', required=True, help='Path to extracted fields JSON')
    parser.add_argument('--intra-panel-refs', required=True, help='Directory with intra-panel reference files')
    parser.add_argument('--inter-panel-refs', required=True, help='Path to inter-panel references JSON')
    parser.add_argument('--output', required=True, help='Path for output JSON')
    parser.add_argument('--keyword-tree', default='rule_extractor/static/keyword_tree.json',
                        help='Path to keyword tree JSON')

    args = parser.parse_args()

    agent = RuleTypePlacementAgent(args.keyword_tree)
    agent.process_schema(
        schema_path=args.schema,
        extracted_fields_path=args.extracted_fields,
        intra_panel_refs_dir=args.intra_panel_refs,
        inter_panel_refs_path=args.inter_panel_refs,
        output_path=args.output
    )


if __name__ == '__main__':
    main()
