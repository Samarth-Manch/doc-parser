#!/usr/bin/env python3
"""
Run rule extraction v7 - Complete rule extraction with all phases.

Input Files:
- Schema JSON: output/complete_format/6421-schema.json
- Intra-Panel References: adws/2026-01-31_14-23-02/templates_output/Vendor Creation Sample BUD_intra_panel_references.json

Output Files:
- Populated Schema: adws/2026-01-31_14-23-02/populated_schema_v7.json
- Summary Report: adws/2026-01-31_14-23-02/extraction_report_v7.json
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent import RuleExtractionAgent


def main():
    # Configuration
    schema_path = "output/complete_format/6421-schema.json"
    intra_panel_path = "adws/2026-01-31_14-23-02/templates_output/Vendor Creation Sample BUD_intra_panel_references.json"
    output_schema_path = "adws/2026-01-31_14-23-02/populated_schema_v7.json"
    output_report_path = "adws/2026-01-31_14-23-02/extraction_report_v7.json"

    verbose = True
    llm_threshold = 0.7

    print("=" * 60)
    print("Rule Extraction v7 - Complete Pipeline")
    print("=" * 60)
    print(f"\nInput Schema: {schema_path}")
    print(f"Input Intra-Panel: {intra_panel_path}")
    print(f"Output Schema: {output_schema_path}")
    print(f"Output Report: {output_report_path}")
    print(f"\nLLM Threshold: {llm_threshold}")
    print(f"Verbose: {verbose}")
    print("=" * 60)

    # Verify input files exist
    if not os.path.exists(schema_path):
        print(f"ERROR: Schema file not found: {schema_path}")
        return 1

    if not os.path.exists(intra_panel_path):
        print(f"ERROR: Intra-panel file not found: {intra_panel_path}")
        return 1

    # Initialize the agent
    print("\n[1/4] Initializing Rule Extraction Agent...")
    try:
        agent = RuleExtractionAgent(
            schema_path=schema_path,
            intra_panel_path=intra_panel_path,
            llm_threshold=llm_threshold,
            verbose=verbose
        )
        print(f"  - Loaded {len(agent.fields)} fields from schema")
    except Exception as e:
        print(f"ERROR: Failed to initialize agent: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Run extraction
    print("\n[2/4] Running rule extraction...")
    try:
        result = agent.process()
        print(f"  - Processed {result.total_fields_processed} fields")
        print(f"  - Generated {result.total_rules_generated} rules")
        print(f"  - Deterministic matches: {result.deterministic_matches}")
        print(f"  - LLM fallbacks: {result.llm_fallbacks}")
        print(f"  - Skipped fields: {result.skipped_fields}")
    except Exception as e:
        print(f"ERROR: Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Save populated schema
    print("\n[3/4] Saving populated schema...")
    try:
        agent.save_schema(output_schema_path)
        print(f"  - Saved to: {output_schema_path}")
    except Exception as e:
        print(f"ERROR: Failed to save schema: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Save report
    print("\n[4/4] Saving extraction report...")
    try:
        agent.save_report(output_report_path)
        print(f"  - Saved to: {output_report_path}")
    except Exception as e:
        print(f"ERROR: Failed to save report: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Print summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(result.summary())

    # Print rules by type
    print("\nRules by Type:")
    for rule_type, count in sorted(result.rules_by_type.items()):
        print(f"  {rule_type}: {count}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for error in result.errors[:5]:
            print(f"  - {error}")

    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for warning in result.warnings[:5]:
            print(f"  - {warning}")

    if result.unmatched_fields:
        print(f"\nUnmatched Fields ({len(result.unmatched_fields)}):")
        for field in result.unmatched_fields[:10]:
            print(f"  - {field}")

    print("\n" + "=" * 60)
    print("Output Files:")
    print(f"  - Populated Schema: {output_schema_path}")
    print(f"  - Extraction Report: {output_report_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
