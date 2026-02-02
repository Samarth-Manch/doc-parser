#!/usr/bin/env python3
"""
Rule Extraction Agent - Main Entry Point

Extracts rules from BUD logic/rules sections and populates formFillRules arrays.

Usage:
    python rule_extraction_agent.py --bud BUD_FILE --output OUTPUT_JSON

    python rule_extraction_agent.py \
        --bud "documents/Vendor Creation Sample BUD.docx" \
        --intra-panel intra_panel_references.json \
        --output populated_schema.json \
        --verbose
"""

import argparse
import json
import logging
import os
import re
import sys
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rule_extraction_agent.models import (
    FieldInfo, GeneratedRule, ExtractionResult, ExtractionSummary
)
from rule_extraction_agent.logic_parser import LogicParser
from rule_extraction_agent.schema_lookup import RuleSchemaLookup
from rule_extraction_agent.field_matcher import FieldMatcher, PanelFieldMatcher, fields_from_schema
from rule_extraction_agent.rule_tree import RuleSelectionTree
from rule_extraction_agent.matchers.pipeline import MatchingPipeline, PipelineConfig, SimplifiedPipeline
from rule_extraction_agent.rule_builders import StandardRuleBuilder, VerifyRuleBuilder, OcrRuleBuilder
from rule_extraction_agent.id_mapper import DestinationIdMapper
from rule_extraction_agent.validators import RuleValidator, validate_generated_rules
from rule_extraction_agent.utils import (
    load_json, save_json, format_timestamp, extract_panel_structure, count_rules_by_type
)


class IdGenerator:
    """Generates incremental IDs for fields and rules."""

    def __init__(self, field_start: int = 100000, rule_start: int = 100000):
        """
        Initialize the ID generator.

        Args:
            field_start: Starting ID for fields
            rule_start: Starting ID for rules
        """
        self._field_counter = field_start
        self._rule_counter = rule_start

    def next_field_id(self) -> int:
        """Get next field ID."""
        field_id = self._field_counter
        self._field_counter += 1
        return field_id

    def next_rule_id(self) -> int:
        """Get next rule ID."""
        rule_id = self._rule_counter
        self._rule_counter += 1
        return rule_id

    def get_current_field_id(self) -> int:
        """Get current field ID without incrementing."""
        return self._field_counter

    def get_current_rule_id(self) -> int:
        """Get current rule ID without incrementing."""
        return self._rule_counter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RuleExtractionAgent:
    """
    Main agent for extracting rules from BUD documents.

    Coordinates the entire rule extraction pipeline:
    1. Load BUD document and parse fields
    2. Load intra-panel references for field dependencies
    3. Process logic text for each field
    4. Generate formFillRules
    5. Populate schema JSON
    """

    def __init__(
        self,
        schema_path: Optional[str] = None,
        use_llm: bool = True,
        llm_threshold: float = 0.7,
        verbose: bool = False,
        field_id_start: int = 100000,
        rule_id_start: int = 100000,
    ):
        """
        Initialize the rule extraction agent.

        Args:
            schema_path: Path to Rule-Schemas.json
            use_llm: Enable LLM fallback for complex rules
            llm_threshold: Confidence threshold for LLM fallback
            verbose: Enable verbose logging
            field_id_start: Starting ID for generated field IDs
            rule_id_start: Starting ID for generated rule IDs
        """
        self.verbose = verbose
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Initialize ID generators
        self.id_gen = IdGenerator(field_id_start, rule_id_start)

        # Initialize schema lookup
        try:
            self.schema_lookup = RuleSchemaLookup(schema_path)
            logger.info(f"Loaded {len(self.schema_lookup.raw_schemas)} rule schemas")
        except FileNotFoundError as e:
            logger.warning(f"Could not load Rule-Schemas.json: {e}")
            self.schema_lookup = None

        # Initialize pipeline
        config = PipelineConfig(
            llm_threshold=llm_threshold,
            use_llm=use_llm,
            verbose=verbose,
        )

        if self.schema_lookup:
            self.pipeline = MatchingPipeline(self.schema_lookup, config)
        else:
            self.pipeline = None
            self.simple_pipeline = SimplifiedPipeline()

        # Initialize components
        self.logic_parser = LogicParser()
        self.rule_tree = RuleSelectionTree(self.schema_lookup) if self.schema_lookup else None
        self.field_matcher: Optional[FieldMatcher] = None
        self.standard_builder = StandardRuleBuilder()

        # Statistics
        self.summary = ExtractionSummary()

    def load_bud(self, bud_path: str) -> Dict:
        """
        Load and parse BUD document.

        Args:
            bud_path: Path to BUD document (.docx or .json)

        Returns:
            Parsed BUD data as dict
        """
        if bud_path.endswith('.json'):
            return load_json(bud_path)
        elif bud_path.endswith('.docx'):
            # Use doc_parser to parse BUD
            try:
                # Add project root to path for doc_parser
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                sys.path.insert(0, project_root)
                from doc_parser import DocumentParser
                parser = DocumentParser()
                parsed = parser.parse(bud_path)
                return parsed.to_dict()
            except ImportError:
                logger.error("doc_parser not available. Please provide JSON input.")
                raise
        else:
            raise ValueError(f"Unsupported file type: {bud_path}")

    def load_intra_panel_references(self, path: str) -> Dict:
        """Load intra-panel references JSON."""
        return load_json(path)

    def extract_fields_from_bud(self, bud_data: Dict) -> List[FieldInfo]:
        """
        Extract field information from BUD data.

        Args:
            bud_data: Parsed BUD data

        Returns:
            List of FieldInfo objects
        """
        fields = []

        # Handle different BUD formats
        if 'template' in bud_data:
            # formBuilder export format
            fields = fields_from_schema(bud_data)
        elif 'all_fields' in bud_data:
            # doc_parser output format - uses 'name' key
            current_panel = None
            for idx, f in enumerate(bud_data['all_fields']):
                field_name = f.get('name', '') or f.get('field_name', '')
                field_type = str(f.get('field_type', 'TEXT'))

                # Track current panel
                if field_type == 'PANEL':
                    current_panel = field_name

                # Generate incremental field ID
                field_id = self.id_gen.next_field_id()

                field_info = FieldInfo(
                    id=field_id,
                    name=field_name,
                    variable_name=f.get('variable_name', '') or self._generate_variable_name(field_name),
                    field_type=field_type,
                    panel_name=f.get('section') or f.get('panel_name') or current_panel,
                    mandatory=f.get('is_mandatory', False) or f.get('mandatory', False),
                    editable=f.get('editable', True),
                    visible=f.get('visible', True),
                    form_order=float(idx),
                )
                fields.append(field_info)
        elif 'fields' in bud_data:
            # Simple fields list
            for idx, f in enumerate(bud_data['fields']):
                field_id = f.get('id') if f.get('id') else self.id_gen.next_field_id()
                field_info = FieldInfo(
                    id=field_id,
                    name=f.get('name', ''),
                    variable_name=f.get('variable_name', ''),
                    field_type=f.get('type', 'TEXT'),
                    form_order=float(idx),
                )
                fields.append(field_info)

        self.summary.total_fields = len(fields)
        logger.info(f"Extracted {len(fields)} fields from BUD")

        return fields

    def _generate_variable_name(self, field_name: str) -> str:
        """Generate a variable name from field name."""
        if not field_name:
            return ""
        # Convert to variable-friendly format
        # e.g., "Please select GST option" -> "_pleaseSelectGstOption_"
        words = re.sub(r'[^\w\s]', '', field_name).split()
        if not words:
            return ""
        # camelCase with underscores
        camel = words[0].lower() + ''.join(w.capitalize() for w in words[1:])
        return f"_{camel[:8]}_{self.id_gen.get_current_field_id() % 100}_"

    def extract_logic_statements(
        self,
        bud_data: Dict,
        intra_panel_refs: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Extract logic statements for fields.

        Args:
            bud_data: Parsed BUD data
            intra_panel_refs: Intra-panel references

        Returns:
            List of dicts with field info and logic text
        """
        logic_entries = []

        # Extract from intra-panel references
        if intra_panel_refs:
            for panel_result in intra_panel_refs.get('panel_results', []):
                for ref_entry in panel_result.get('intra_panel_references', []):
                    # Get dependent field name
                    field_name = ref_entry.get('dependent_field', '')

                    # Extract from nested references array
                    for ref in ref_entry.get('references', []):
                        if 'logic_excerpt' in ref:
                            logic_text = ref['logic_excerpt']
                            if field_name and logic_text:
                                logic_entries.append({
                                    'field_name': field_name,
                                    'logic_text': logic_text,
                                    'reference': ref,
                                    'source_field': ref.get('referenced_field'),
                                })

                    # Also handle flat format (fallback)
                    if 'logic_excerpt' in ref_entry:
                        logic_text = ref_entry['logic_excerpt']
                        if field_name and logic_text:
                            logic_entries.append({
                                'field_name': field_name,
                                'logic_text': logic_text,
                                'reference': ref_entry,
                            })
                    elif 'original_logic' in ref_entry:
                        logic_text = ref_entry['original_logic']
                        field_name = ref_entry.get('field_name', field_name)
                        if field_name and logic_text:
                            logic_entries.append({
                                'field_name': field_name,
                                'logic_text': logic_text,
                                'reference': ref_entry,
                            })

        # Also check BUD fields for logic
        all_fields = bud_data.get('all_fields', [])
        for field in all_fields:
            logic = field.get('logic') or field.get('rules')
            if logic:
                # Use 'name' as key (doc_parser format) or 'field_name'
                field_name = field.get('name', '') or field.get('field_name', '')
                logic_entries.append({
                    'field_name': field_name,
                    'logic_text': str(logic),  # Ensure string
                    'field': field,
                })

        # Deduplicate by field name + logic prefix
        seen = set()
        unique_entries = []
        for entry in logic_entries:
            # Ensure field_name is a string
            field_name = str(entry.get('field_name', ''))
            logic_text = str(entry.get('logic_text', ''))[:50]
            key = (field_name, logic_text)
            if key not in seen:
                seen.add(key)
                unique_entries.append(entry)

        self.summary.fields_with_logic = len(unique_entries)
        logger.info(f"Found {len(unique_entries)} logic statements")

        return unique_entries

    def process_logic(
        self,
        logic_entries: List[Dict],
        fields: List[FieldInfo],
    ) -> List[ExtractionResult]:
        """
        Process logic statements and generate rules.

        Args:
            logic_entries: List of logic statement dicts
            fields: List of FieldInfo objects

        Returns:
            List of ExtractionResult objects
        """
        results = []

        # Setup field matcher
        self.field_matcher = PanelFieldMatcher(fields)
        if self.pipeline:
            self.pipeline.set_fields(fields)

        for entry in logic_entries:
            logic_text = str(entry.get('logic_text', ''))
            field_name = entry.get('field_name', '')
            source_field_name = entry.get('source_field', '')

            # Ensure field_name is a string
            if isinstance(field_name, dict):
                field_name = field_name.get('name', '') or str(field_name)
            field_name = str(field_name)

            # Find field info for destination (the field being controlled)
            match = self.field_matcher.match(field_name)
            if not match.field_info:
                # Create placeholder field info with incremental ID
                field_info = FieldInfo(
                    id=self.id_gen.next_field_id(),
                    name=field_name,
                    variable_name='',
                    field_type='TEXT',
                )
            else:
                field_info = match.field_info

            # Find source field (the controlling field)
            source_id = field_info.id
            if source_field_name:
                src_match = self.field_matcher.match(source_field_name)
                if src_match.field_info:
                    source_id = src_match.field_info.id

            # Process through pipeline
            if self.pipeline:
                pipeline_result = self.pipeline.process(logic_text, field_info)

                # Assign rule IDs
                for rule in pipeline_result.generated_rules:
                    rule.rule_id = self.id_gen.next_rule_id()

                result = ExtractionResult(
                    field_id=pipeline_result.field_id,
                    field_name=pipeline_result.field_name,
                    logic_text=pipeline_result.logic_text,
                    parsed_logic=pipeline_result.parsed_logic,
                    generated_rules=pipeline_result.generated_rules,
                    confidence=pipeline_result.confidence,
                    used_llm=pipeline_result.used_llm,
                    errors=pipeline_result.errors,
                )
            else:
                # Use simple pipeline
                parsed = self.logic_parser.parse(logic_text)

                if parsed.skip_reason:
                    result = ExtractionResult(
                        field_id=field_info.id,
                        field_name=field_name,
                        logic_text=logic_text,
                        parsed_logic=parsed,
                        skipped=True,
                        skip_reason=parsed.skip_reason,
                    )
                else:
                    # Find source field from conditions if not already found
                    if source_id == field_info.id:
                        for cond in parsed.conditions:
                            if cond.field_name:
                                src_match = self.field_matcher.match(cond.field_name)
                                if src_match.field_info:
                                    source_id = src_match.field_info.id
                                    break

                    rules = self.simple_pipeline.extract_rules(
                        logic_text, source_id, field_info.id
                    )

                    # Assign rule IDs
                    for rule in rules:
                        rule.rule_id = self.id_gen.next_rule_id()

                    result = ExtractionResult(
                        field_id=field_info.id,
                        field_name=field_name,
                        logic_text=logic_text,
                        parsed_logic=parsed,
                        generated_rules=rules,
                        confidence=parsed.confidence,
                    )

            results.append(result)

            # Update statistics
            if result.skipped:
                self.summary.fields_skipped += 1
            else:
                self.summary.fields_processed += 1
                self.summary.total_rules_generated += len(result.generated_rules)

                if result.used_llm:
                    self.summary.llm_fallback_used += 1
                else:
                    self.summary.deterministic_matches += 1

                # Count by action type
                for rule in result.generated_rules:
                    action = rule.action_type
                    self.summary.rules_by_action_type[action] = \
                        self.summary.rules_by_action_type.get(action, 0) + 1

        logger.info(f"Processed {len(results)} logic statements")
        logger.info(f"Generated {self.summary.total_rules_generated} rules")

        return results

    def populate_schema(
        self,
        schema: Dict,
        extraction_results: List[ExtractionResult],
    ) -> Dict:
        """
        Populate schema JSON with generated rules.

        Args:
            schema: Schema dict to populate
            extraction_results: Extraction results with rules

        Returns:
            Updated schema dict
        """
        # Build index of results by field name
        results_by_name = {}
        for result in extraction_results:
            if result.field_name:
                results_by_name[result.field_name.lower()] = result

        # Navigate to formFillMetadatas
        doc_types = schema.get('template', {}).get('documentTypes', [])
        if not doc_types:
            doc_types = schema.get('documentTypes', [])

        rules_added = 0

        for doc_type in doc_types:
            for meta in doc_type.get('formFillMetadatas', []):
                form_tag = meta.get('formTag', {})
                field_name = form_tag.get('name', '').lower()

                if field_name in results_by_name:
                    result = results_by_name[field_name]
                    if result.generated_rules:
                        # Initialize formFillRules if needed
                        if 'formFillRules' not in meta:
                            meta['formFillRules'] = []

                        # Add generated rules
                        for rule in result.generated_rules:
                            rule_dict = rule.to_dict()
                            meta['formFillRules'].append(rule_dict)
                            rules_added += 1

        logger.info(f"Added {rules_added} rules to schema")

        return schema

    def run(
        self,
        bud_path: str,
        intra_panel_path: Optional[str] = None,
        output_path: Optional[str] = None,
        schema_path: Optional[str] = None,
        report_path: Optional[str] = None,
    ) -> Dict:
        """
        Run the complete extraction pipeline.

        Args:
            bud_path: Path to BUD document
            intra_panel_path: Path to intra-panel references JSON
            output_path: Path to save populated schema
            schema_path: Path to base schema to populate
            report_path: Path to save summary report

        Returns:
            Extraction results and populated schema
        """
        start_time = datetime.now()
        logger.info(f"Starting rule extraction from {bud_path}")

        # Load inputs
        bud_data = self.load_bud(bud_path)

        intra_panel_refs = None
        if intra_panel_path:
            intra_panel_refs = self.load_intra_panel_references(intra_panel_path)

        # Extract fields
        fields = self.extract_fields_from_bud(bud_data)

        # Extract logic statements
        logic_entries = self.extract_logic_statements(bud_data, intra_panel_refs)

        # Process logic and generate rules
        results = self.process_logic(logic_entries, fields)

        # Load or create output schema
        if schema_path and os.path.exists(schema_path):
            output_schema = load_json(schema_path)
        else:
            # Create minimal schema structure
            output_schema = {
                "template": {
                    "documentTypes": [{
                        "formFillMetadatas": [
                            {
                                "formTag": {"name": f.name, "type": f.field_type},
                                "id": f.id,
                                "variableName": f.variable_name,
                                "formFillRules": [],
                            }
                            for f in fields
                        ]
                    }]
                }
            }

        # Populate schema with rules
        populated_schema = self.populate_schema(output_schema, results)

        # Calculate average confidence
        confidences = [r.confidence for r in results if r.confidence > 0]
        self.summary.average_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Save outputs
        if output_path:
            save_json(populated_schema, output_path)
            logger.info(f"Saved populated schema to {output_path}")

        if report_path:
            report = {
                "summary": self.summary.to_dict(),
                "extraction_timestamp": format_timestamp(),
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "input_bud": bud_path,
                "input_intra_panel": intra_panel_path,
                "output_schema": output_path,
            }
            save_json(report, report_path)
            logger.info(f"Saved report to {report_path}")

        # Print summary
        self._print_summary()

        return {
            "schema": populated_schema,
            "results": [r.to_dict() for r in results],
            "summary": self.summary.to_dict(),
        }

    def _print_summary(self) -> None:
        """Print extraction summary."""
        print("\n" + "=" * 60)
        print("RULE EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Total fields:          {self.summary.total_fields}")
        print(f"Fields with logic:     {self.summary.fields_with_logic}")
        print(f"Fields processed:      {self.summary.fields_processed}")
        print(f"Fields skipped:        {self.summary.fields_skipped}")
        print(f"Total rules generated: {self.summary.total_rules_generated}")
        print(f"Deterministic matches: {self.summary.deterministic_matches}")
        print(f"LLM fallback used:     {self.summary.llm_fallback_used}")
        print(f"Average confidence:    {self.summary.average_confidence:.2f}")
        print()
        print("Rules by action type:")
        for action, count in sorted(self.summary.rules_by_action_type.items()):
            print(f"  {action}: {count}")
        print("=" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract rules from BUD documents and populate formFillRules."
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to BUD document (.docx or .json)"
    )
    parser.add_argument(
        "--intra-panel",
        help="Path to intra-panel references JSON"
    )
    parser.add_argument(
        "--output",
        help="Path to save populated schema JSON"
    )
    parser.add_argument(
        "--schema",
        help="Path to base schema JSON to populate"
    )
    parser.add_argument(
        "--rule-schemas",
        help="Path to Rule-Schemas.json"
    )
    parser.add_argument(
        "--report",
        help="Path to save summary report JSON"
    )
    parser.add_argument(
        "--llm-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for LLM fallback (default: 0.7)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM fallback"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated rules"
    )

    args = parser.parse_args()

    # Initialize agent
    agent = RuleExtractionAgent(
        schema_path=args.rule_schemas,
        use_llm=not args.no_llm,
        llm_threshold=args.llm_threshold,
        verbose=args.verbose,
    )

    # Run extraction
    result = agent.run(
        bud_path=args.bud,
        intra_panel_path=args.intra_panel,
        output_path=args.output,
        schema_path=args.schema,
        report_path=args.report,
    )

    # Validate if requested
    if args.validate:
        print("\nValidating generated rules...")
        all_rules = []
        for r in result.get('results', []):
            all_rules.extend(r.get('generated_rules', []))

        validator = RuleValidator()
        validation = validator.validate_batch(all_rules)

        if validation.errors:
            print(f"Validation errors: {len(validation.errors)}")
            for error in validation.errors[:10]:
                print(f"  - {error}")
        else:
            print("All rules validated successfully!")

        if validation.warnings:
            print(f"Warnings: {len(validation.warnings)}")


if __name__ == "__main__":
    main()
