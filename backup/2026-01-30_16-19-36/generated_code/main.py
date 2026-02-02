"""
Main RuleExtractionAgent for extracting and populating formFillRules.
"""

import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# Handle both relative and absolute imports
try:
    from .models import IntraPanelReference, ParsedLogic, RuleSelection, GeneratedRule, FieldInfo
    from .logic_parser import LogicParser
    from .field_matcher import FieldMatcher
    from .rule_tree import RuleTree
    from .rule_builders import StandardRuleBuilder
except ImportError:
    from models import IntraPanelReference, ParsedLogic, RuleSelection, GeneratedRule, FieldInfo
    from logic_parser import LogicParser
    from field_matcher import FieldMatcher
    from rule_tree import RuleTree
    from rule_builders import StandardRuleBuilder


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RuleExtractionAgent:
    """Main agent for extracting rules from BUD logic and populating schema."""

    def __init__(
        self,
        schema_path: str,
        intra_panel_path: str,
        start_rule_id: int = 119617
    ):
        """
        Initialize Rule Extraction Agent.

        Args:
            schema_path: Path to schema JSON (vendor_creation_schema.json)
            intra_panel_path: Path to intra_panel_references.json
            start_rule_id: Starting ID for generated rules
        """
        self.schema_path = Path(schema_path)
        self.intra_panel_path = Path(intra_panel_path)
        self.start_rule_id = start_rule_id

        # Load data
        logger.info(f"Loading schema from {self.schema_path}")
        with open(self.schema_path, 'r') as f:
            self.schema = json.load(f)

        logger.info(f"Loading intra-panel references from {self.intra_panel_path}")
        with open(self.intra_panel_path, 'r') as f:
            self.intra_panel_data = json.load(f)

        # Initialize components
        self.logic_parser = LogicParser()
        self.field_matcher = FieldMatcher(self.schema)
        self.rule_tree = RuleTree()
        self.rule_builder = StandardRuleBuilder(start_rule_id=start_rule_id)

        # Statistics
        self.stats = {
            'total_references': 0,
            'rules_generated': 0,
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'unmatched_fields': []
        }

    def extract_rules(self) -> Dict[str, Any]:
        """
        Extract rules from intra-panel references and populate schema.

        Returns:
            Updated schema with formFillRules populated
        """
        logger.info("Starting rule extraction...")

        # Process all panel results
        panel_results = self.intra_panel_data.get('panel_results', [])

        for panel_result in panel_results:
            panel_name = panel_result.get('panel_name', 'Unknown')
            logger.info(f"Processing panel: {panel_name}")

            intra_panel_refs = panel_result.get('intra_panel_references', [])
            self.stats['total_references'] += len(intra_panel_refs)

            for ref_data in intra_panel_refs:
                self._process_reference(ref_data)

        # Update schema with generated rules
        self._update_schema()

        logger.info(f"Rule extraction complete. Generated {self.stats['rules_generated']} rules.")
        self._print_statistics()

        return self.schema

    def _process_reference(self, ref_data: Dict[str, Any]) -> None:
        """Process a single intra-panel reference."""
        try:
            # Parse reference
            ref = IntraPanelReference.from_dict(ref_data)

            # Parse logic text
            parsed_logic = self.logic_parser.parse(
                ref.raw_expression,
                ref.relationship_type
            )

            # Match source and target fields
            source_field = self.field_matcher.match_field(ref.source_field_name)
            target_field = self.field_matcher.match_field(ref.target_field_name)

            if not target_field:
                logger.warning(f"Could not match target field: {ref.target_field_name}")
                self.stats['unmatched_fields'].append(ref.target_field_name)
                return

            target_fields = [target_field]

            # Select rules using rule tree
            rule_selections = self.rule_tree.select_rules(
                parsed_logic,
                source_field,
                target_fields
            )

            # Build and add rules
            for rule_selection in rule_selections:
                generated_rules = self.rule_builder.build(rule_selection)

                for rule in generated_rules:
                    self._add_rule_to_schema(rule, target_field)
                    self.stats['rules_generated'] += 1

                    # Track confidence
                    if rule_selection.confidence >= 0.8:
                        self.stats['high_confidence'] += 1
                    elif rule_selection.confidence >= 0.5:
                        self.stats['medium_confidence'] += 1
                    else:
                        self.stats['low_confidence'] += 1

        except Exception as e:
            logger.error(f"Error processing reference: {e}")
            logger.debug(f"Reference data: {ref_data}")

    def _add_rule_to_schema(self, rule: GeneratedRule, target_field: FieldInfo) -> None:
        """Add generated rule to the appropriate field in schema."""
        # Find the formFillMetadata for the target field
        template = self.schema.get('template', {})
        doc_types = template.get('documentTypes', [])

        for doc_type in doc_types:
            metadata_list = doc_type.get('formFillMetadatas', [])

            for metadata in metadata_list:
                if metadata.get('id') == target_field.field_id:
                    # Add rule to formFillRules array
                    if 'formFillRules' not in metadata:
                        metadata['formFillRules'] = []

                    metadata['formFillRules'].append(rule.to_dict())
                    return

        logger.warning(f"Could not find metadata for field ID: {target_field.field_id}")

    def _update_schema(self) -> None:
        """Final schema updates after all rules are generated."""
        # Remove duplicate rules (same actionType, sourceIds, destinationIds)
        self._deduplicate_rules()

    def _deduplicate_rules(self) -> None:
        """Remove duplicate rules from schema."""
        template = self.schema.get('template', {})
        doc_types = template.get('documentTypes', [])

        duplicates_removed = 0

        for doc_type in doc_types:
            metadata_list = doc_type.get('formFillMetadatas', [])

            for metadata in metadata_list:
                rules = metadata.get('formFillRules', [])
                if not rules:
                    continue

                # Create signature for each rule
                seen = set()
                unique_rules = []

                for rule in rules:
                    signature = (
                        rule.get('actionType'),
                        tuple(sorted(rule.get('sourceIds', []))),
                        tuple(sorted(rule.get('destinationIds', []))),
                        tuple(rule.get('conditionalValues', [])),
                        rule.get('condition')
                    )

                    if signature not in seen:
                        seen.add(signature)
                        unique_rules.append(rule)
                    else:
                        duplicates_removed += 1

                metadata['formFillRules'] = unique_rules

        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate rules")

    def _print_statistics(self) -> None:
        """Print extraction statistics."""
        logger.info("=" * 60)
        logger.info("RULE EXTRACTION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total references processed: {self.stats['total_references']}")
        logger.info(f"Rules generated: {self.stats['rules_generated']}")
        logger.info(f"High confidence (>80%): {self.stats['high_confidence']}")
        logger.info(f"Medium confidence (50-80%): {self.stats['medium_confidence']}")
        logger.info(f"Low confidence (<50%): {self.stats['low_confidence']}")
        logger.info(f"Unmatched fields: {len(self.stats['unmatched_fields'])}")

        if self.stats['unmatched_fields']:
            logger.warning("Unmatched field names:")
            for field_name in self.stats['unmatched_fields'][:10]:
                logger.warning(f"  - {field_name}")
            if len(self.stats['unmatched_fields']) > 10:
                logger.warning(f"  ... and {len(self.stats['unmatched_fields']) - 10} more")
        logger.info("=" * 60)

    def save_schema(self, output_path: str) -> None:
        """
        Save populated schema to file.

        Args:
            output_path: Path to save populated schema
        """
        output_path = Path(output_path)
        logger.info(f"Saving populated schema to {output_path}")

        with open(output_path, 'w') as f:
            json.dump(self.schema, f, indent=2)

        logger.info("Schema saved successfully")

    def generate_report(self, report_path: str) -> None:
        """
        Generate summary report.

        Args:
            report_path: Path to save report JSON
        """
        report = {
            'statistics': self.stats,
            'timestamp': str(Path(self.intra_panel_path).stat().st_mtime),
            'schema_path': str(self.schema_path),
            'intra_panel_path': str(self.intra_panel_path)
        }

        report_path = Path(report_path)
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report saved to {report_path}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Rule Extraction Agent')
    parser.add_argument(
        '--schema',
        required=True,
        help='Path to schema JSON (vendor_creation_schema.json)'
    )
    parser.add_argument(
        '--intra-panel',
        required=True,
        help='Path to intra_panel_references.json'
    )
    parser.add_argument(
        '--output',
        help='Output path for populated schema (default: populated_schema.json)'
    )
    parser.add_argument(
        '--report',
        help='Output path for summary report JSON'
    )
    parser.add_argument(
        '--start-rule-id',
        type=int,
        default=119617,
        help='Starting ID for generated rules (default: 119617)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize agent
    agent = RuleExtractionAgent(
        schema_path=args.schema,
        intra_panel_path=args.intra_panel,
        start_rule_id=args.start_rule_id
    )

    # Extract rules
    populated_schema = agent.extract_rules()

    # Save output
    output_path = args.output or 'populated_schema.json'
    agent.save_schema(output_path)

    # Generate report if requested
    if args.report:
        agent.generate_report(args.report)


if __name__ == '__main__':
    main()
