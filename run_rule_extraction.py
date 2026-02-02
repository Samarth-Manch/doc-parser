#!/usr/bin/env python3
"""
CLI entry point for the Rule Extraction Agent.

Usage:
    python run_rule_extraction.py \\
        --schema output/complete_format/6421-schema.json \\
        --intra-panel "adws/.../intra_panel_references.json" \\
        --output "adws/.../populated_schema.json" \\
        --report "adws/.../extraction_report.json" \\
        --verbose
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent import RuleExtractionAgent


def main():
    parser = argparse.ArgumentParser(
        description="Extract rules from BUD logic and populate schema"
    )
    parser.add_argument(
        "--schema",
        required=True,
        help="Path to schema JSON from extract_fields_complete.py"
    )
    parser.add_argument(
        "--intra-panel",
        required=True,
        help="Path to intra-panel references JSON"
    )
    parser.add_argument(
        "--output",
        help="Output path for populated schema (optional)"
    )
    parser.add_argument(
        "--report",
        help="Path to save extraction report (optional)"
    )
    parser.add_argument(
        "--rule-schemas",
        default="rules/Rule-Schemas.json",
        help="Path to Rule-Schemas.json (default: rules/Rule-Schemas.json)"
    )
    parser.add_argument(
        "--llm-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for LLM fallback (default: 0.7)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated rules"
    )

    args = parser.parse_args()

    # Validate input files
    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"Error: Schema file not found: {args.schema}")
        sys.exit(1)

    intra_panel_path = Path(args.intra_panel)
    if not intra_panel_path.exists():
        print(f"Error: Intra-panel file not found: {args.intra_panel}")
        sys.exit(1)

    rule_schemas_path = Path(args.rule_schemas)
    if not rule_schemas_path.exists():
        print(f"Warning: Rule-Schemas.json not found at {args.rule_schemas}")
        print("VERIFY and OCR rules may not be generated correctly.")

    # Generate output paths if not provided
    if not args.output:
        output_dir = schema_path.parent.parent / "rules_populated"
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(output_dir / schema_path.name)

    if not args.report:
        args.report = str(Path(args.output).with_suffix('.report.json'))

    print("=" * 60)
    print("Rule Extraction Agent")
    print("=" * 60)
    print(f"Schema:       {args.schema}")
    print(f"Intra-panel:  {args.intra_panel}")
    print(f"Output:       {args.output}")
    print(f"Report:       {args.report}")
    print(f"LLM Threshold: {args.llm_threshold}")
    print(f"Verbose:      {args.verbose}")
    print("=" * 60)

    # Initialize the agent
    try:
        agent = RuleExtractionAgent(
            schema_path=str(schema_path),
            intra_panel_path=str(intra_panel_path),
            rule_schemas_path=str(rule_schemas_path),
            llm_threshold=args.llm_threshold,
            verbose=args.verbose
        )
    except Exception as e:
        print(f"Error initializing agent: {e}")
        sys.exit(1)

    # Process rules
    print("\nProcessing...")
    try:
        result = agent.process()
    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print summary
    print("\n" + result.summary())

    # Save outputs
    print(f"\nSaving populated schema to: {args.output}")
    try:
        agent.save_schema(args.output)
    except Exception as e:
        print(f"Error saving schema: {e}")

    print(f"Saving report to: {args.report}")
    try:
        agent.save_report(args.report)
    except Exception as e:
        print(f"Error saving report: {e}")

    print("\nDone!")

    # Return exit code based on result
    if result.errors:
        print(f"\n{len(result.errors)} errors occurred during processing.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
