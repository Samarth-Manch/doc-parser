#!/usr/bin/env python3
"""
Run Rule Extraction Agent - Version 3

Extracts rules from BUD logic/rules sections and populates formFillRules arrays
in the JSON schema using a hybrid pattern-based + LLM approach.

Input Files:
- Schema JSON: output/complete_format/6421-schema.json
- Intra-Panel References: adws/2026-01-31_12-58-30/templates_output/Vendor Creation Sample BUD_intra_panel_references.json

Output Files:
- Populated Schema: adws/2026-01-31_12-58-30/populated_schema_v3.json
- Summary Report: adws/2026-01-31_12-58-30/extraction_report_v3.json

Configuration:
- Verbose mode: True
- Validate rules: False
- LLM threshold: 0.7
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent import RuleExtractionAgent


def main():
    # Input files
    schema_path = "output/complete_format/6421-schema.json"
    intra_panel_path = "adws/2026-01-31_12-58-30/templates_output/Vendor Creation Sample BUD_intra_panel_references.json"
    rule_schemas_path = "rules/Rule-Schemas.json"

    # Output files
    output_schema_path = "adws/2026-01-31_12-58-30/populated_schema_v3.json"
    output_report_path = "adws/2026-01-31_12-58-30/extraction_report_v3.json"

    # Configuration
    verbose = True
    llm_threshold = 0.7

    print("=" * 60)
    print("Rule Extraction Agent - Version 3")
    print("=" * 60)
    print(f"Start time: {datetime.now().isoformat()}")
    print()

    # Validate input files exist
    if not Path(schema_path).exists():
        print(f"ERROR: Schema file not found: {schema_path}")
        sys.exit(1)

    if not Path(intra_panel_path).exists():
        print(f"ERROR: Intra-panel references file not found: {intra_panel_path}")
        sys.exit(1)

    print("Input Files:")
    print(f"  Schema: {schema_path}")
    print(f"  Intra-panel refs: {intra_panel_path}")
    print(f"  Rule schemas: {rule_schemas_path}")
    print()
    print("Output Files:")
    print(f"  Populated schema: {output_schema_path}")
    print(f"  Extraction report: {output_report_path}")
    print()
    print("Configuration:")
    print(f"  Verbose: {verbose}")
    print(f"  LLM threshold: {llm_threshold}")
    print()

    # Initialize the agent
    print("Initializing Rule Extraction Agent...")
    agent = RuleExtractionAgent(
        schema_path=schema_path,
        intra_panel_path=intra_panel_path,
        rule_schemas_path=rule_schemas_path,
        llm_threshold=llm_threshold,
        verbose=verbose
    )

    # Process and extract rules
    print()
    print("Processing fields and extracting rules...")
    print("-" * 40)
    result = agent.process()
    print("-" * 40)

    # Print summary
    print()
    print(result.summary())

    # Save outputs
    print()
    print("Saving outputs...")

    # Save populated schema
    agent.save_schema(output_schema_path)
    print(f"  Saved populated schema to: {output_schema_path}")

    # Save report
    agent.save_report(output_report_path)
    print(f"  Saved extraction report to: {output_report_path}")

    print()
    print(f"End time: {datetime.now().isoformat()}")
    print("=" * 60)
    print("Rule extraction completed successfully!")
    print("=" * 60)

    return result


if __name__ == "__main__":
    main()
