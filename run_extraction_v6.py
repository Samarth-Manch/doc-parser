#!/usr/bin/env python3
"""
Rule Extraction Script v6
Extracts rules from BUD logic sections and populates formFillRules arrays.
"""

import sys
import json
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent.main import RuleExtractionAgent


def main():
    # Configuration
    schema_path = "output/complete_format/6421-schema.json"
    intra_panel_path = "adws/2026-01-31_14-23-02/templates_output/Vendor Creation Sample BUD_intra_panel_references.json"
    output_schema_path = "adws/2026-01-31_14-23-02/populated_schema_v6.json"
    output_report_path = "adws/2026-01-31_14-23-02/extraction_report_v6.json"

    verbose = True
    llm_threshold = 0.7

    print("=" * 60)
    print("Rule Extraction Agent v6")
    print("=" * 60)
    print(f"Schema: {schema_path}")
    print(f"Intra-panel refs: {intra_panel_path}")
    print(f"Output schema: {output_schema_path}")
    print(f"Output report: {output_report_path}")
    print(f"Verbose: {verbose}")
    print(f"LLM threshold: {llm_threshold}")
    print("=" * 60)

    # Initialize the agent
    print("\nInitializing Rule Extraction Agent...")
    agent = RuleExtractionAgent(
        schema_path=schema_path,
        intra_panel_path=intra_panel_path,
        llm_threshold=llm_threshold,
        verbose=verbose
    )

    # Process and extract rules
    print("\nProcessing fields and extracting rules...")
    result = agent.process()

    # Print summary
    print("\n" + result.summary())

    # Save outputs
    print(f"\nSaving populated schema to {output_schema_path}...")
    agent.save_schema(output_schema_path)

    print(f"Saving extraction report to {output_report_path}...")
    agent.save_report(output_report_path)

    print("\n✓ Rule extraction completed successfully!")

    # Return result for further processing
    return result


if __name__ == "__main__":
    main()
