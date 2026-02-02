#!/usr/bin/env python3
"""
Run Rule Extraction Agent v8 - Test with specified inputs.
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent import RuleExtractionAgent
from rule_extraction_agent.utils import save_json


def main():
    # Configuration from user request
    schema_path = "output/complete_format/6421-schema.json"
    intra_panel_path = "adws/2026-01-31_14-23-02/templates_output/Vendor Creation Sample BUD_intra_panel_references.json"
    output_path = "adws/2026-01-31_14-23-02/populated_schema_v8.json"
    report_path = "adws/2026-01-31_14-23-02/extraction_report_v8.json"

    # Verify input files exist
    if not Path(schema_path).exists():
        print(f"Error: Schema file not found: {schema_path}")
        sys.exit(1)

    if not Path(intra_panel_path).exists():
        print(f"Error: Intra-panel references file not found: {intra_panel_path}")
        sys.exit(1)

    print("=" * 60)
    print("Rule Extraction Agent v8")
    print("=" * 60)
    print(f"Schema: {schema_path}")
    print(f"Intra-Panel: {intra_panel_path}")
    print(f"Output: {output_path}")
    print(f"Report: {report_path}")
    print("=" * 60)

    # Initialize agent
    try:
        agent = RuleExtractionAgent(
            schema_path=schema_path,
            intra_panel_path=intra_panel_path,
            bud_document_path=None,  # Not required for this run
            rule_schemas_path="rules/Rule-Schemas.json",
            llm_threshold=0.7,
            verbose=True
        )
    except Exception as e:
        print(f"Error initializing agent: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Run extraction
    print("\nRunning extraction...")
    try:
        result = agent.process()
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print summary
    print("\n" + result.summary())

    # Save populated schema
    if result.populated_schema:
        save_json(result.populated_schema, output_path)
        print(f"\nPopulated schema saved to: {output_path}")
    else:
        print("\nWarning: No populated schema generated")

    # Save report
    from rule_extraction_agent.utils import create_report
    report = create_report(result, output_path, schema_path, None)
    save_json(report, report_path)
    print(f"Report saved to: {report_path}")

    # Print some stats
    print("\n" + "=" * 60)
    print("Extraction Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
