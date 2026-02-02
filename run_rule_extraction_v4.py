#!/usr/bin/env python3
"""
Rule Extraction CLI - Extract rules from BUD logic and populate schema.

Usage:
    python run_rule_extraction_v4.py \\
        --schema output/complete_format/6421-schema.json \\
        --intra-panel adws/2026-01-31_14-23-02/templates_output/Vendor_Creation_Sample_BUD_intra_panel_references.json \\
        --output adws/2026-01-31_14-23-02/populated_schema_v1.json \\
        --report adws/2026-01-31_14-23-02/extraction_report_v1.json \\
        --verbose
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rule_extraction_agent import RuleExtractionAgent


def main():
    parser = argparse.ArgumentParser(
        description="Extract rules from BUD logic and populate schema JSON."
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
        help="Output path for populated schema (auto-generated if not provided)"
    )
    parser.add_argument(
        "--report",
        help="Path to save extraction report"
    )
    parser.add_argument(
        "--rule-schemas",
        default="rules/Rule-Schemas.json",
        help="Path to Rule-Schemas.json"
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

    # Generate output paths if not provided
    if not args.output:
        schema_path = Path(args.schema)
        output_dir = schema_path.parent.parent / "rules_populated"
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(output_dir / schema_path.name)

    if not args.report:
        output_path = Path(args.output)
        args.report = str(output_path.with_suffix('.report.json'))

    print(f"Schema: {args.schema}")
    print(f"Intra-panel: {args.intra_panel}")
    print(f"Output: {args.output}")
    print(f"Report: {args.report}")
    print(f"LLM Threshold: {args.llm_threshold}")
    print()

    # Initialize and run the agent
    try:
        agent = RuleExtractionAgent(
            schema_path=args.schema,
            intra_panel_path=args.intra_panel,
            rule_schemas_path=args.rule_schemas,
            llm_threshold=args.llm_threshold,
            verbose=args.verbose
        )

        # Run extraction
        result = agent.process()

        # Print summary
        print(result.summary())

        # Save outputs
        agent.save_schema(args.output)
        agent.save_report(args.report)

        print(f"\nPopulated schema saved to: {args.output}")
        print(f"Extraction report saved to: {args.report}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
