#!/usr/bin/env python3
"""
Rule Extraction Runner - Execute rule extraction on the specified schema.

Inputs:
  - Schema JSON: output/complete_format/6421-schema.json
  - Intra-Panel References: adws/2026-01-31_14-23-02/templates_output/Vendor Creation Sample BUD_intra_panel_references.json

Outputs:
  - Populated Schema: adws/2026-01-31_14-23-02/populated_schema_v5.json
  - Summary Report: adws/2026-01-31_14-23-02/extraction_report_v5.json

Configuration:
  - Verbose mode: True
  - Validate rules: False
  - LLM threshold: 0.7
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent import RuleExtractionAgent, ExtractionResult


def main():
    """Run the rule extraction with specified configuration."""

    # Configuration from task
    schema_path = "output/complete_format/6421-schema.json"
    intra_panel_path = "adws/2026-01-31_14-23-02/templates_output/Vendor Creation Sample BUD_intra_panel_references.json"
    output_schema_path = "adws/2026-01-31_14-23-02/populated_schema_v5.json"
    output_report_path = "adws/2026-01-31_14-23-02/extraction_report_v5.json"

    verbose = True
    llm_threshold = 0.7

    print("=" * 60)
    print("Rule Extraction Agent - v5")
    print("=" * 60)
    print(f"\nInput Schema: {schema_path}")
    print(f"Intra-Panel References: {intra_panel_path}")
    print(f"Output Schema: {output_schema_path}")
    print(f"Output Report: {output_report_path}")
    print(f"LLM Threshold: {llm_threshold}")
    print(f"Verbose: {verbose}")
    print("=" * 60)

    # Verify input files exist
    if not Path(schema_path).exists():
        print(f"\nError: Schema file not found: {schema_path}")
        sys.exit(1)

    if not Path(intra_panel_path).exists():
        print(f"\nError: Intra-panel references file not found: {intra_panel_path}")
        sys.exit(1)

    # Create output directory
    output_dir = Path(output_schema_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\nInitializing Rule Extraction Agent...")

    try:
        # Initialize the agent
        agent = RuleExtractionAgent(
            schema_path=schema_path,
            intra_panel_path=intra_panel_path,
            llm_threshold=llm_threshold,
            verbose=verbose
        )

        print(f"Loaded {len(agent.fields)} fields from schema")

        # Run extraction
        print("\nProcessing fields and generating rules...")
        result = agent.process()

        # Print summary
        print("\n" + result.summary())

        # Save populated schema
        print(f"\nSaving populated schema to: {output_schema_path}")
        agent.save_schema(output_schema_path)

        # Save report
        print(f"Saving extraction report to: {output_report_path}")
        agent.save_report(output_report_path)

        # Print additional details
        print("\n" + "=" * 60)
        print("Extraction Complete!")
        print("=" * 60)
        print(f"\nTotal fields processed: {result.total_fields_processed}")
        print(f"Total rules generated: {result.total_rules_generated}")
        print(f"Deterministic matches: {result.deterministic_matches}")
        print(f"LLM fallbacks: {result.llm_fallbacks}")
        print(f"Skipped fields: {result.skipped_fields}")

        if result.rules_by_type:
            print("\nRules by type:")
            for rule_type, count in sorted(result.rules_by_type.items()):
                print(f"  {rule_type}: {count}")

        if result.unmatched_fields:
            print(f"\nUnmatched fields ({len(result.unmatched_fields)}):")
            for field in result.unmatched_fields[:10]:
                print(f"  - {field}")
            if len(result.unmatched_fields) > 10:
                print(f"  ... and {len(result.unmatched_fields) - 10} more")

        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for warning in result.warnings[:5]:
                print(f"  - {warning}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:5]:
                print(f"  - {error}")

        print("\n" + "=" * 60)
        print("Output files created:")
        print(f"  - {output_schema_path}")
        print(f"  - {output_report_path}")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\nError during extraction: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
