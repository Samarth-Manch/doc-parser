#!/usr/bin/env python3
"""
Rule Extraction Agent - CLI Entry Point

Automatically extracts rules from BUD logic/rules sections and populates formFillRules arrays.

Usage:
    python rule_extraction_agent.py \
      --schema output/complete_format/2581-schema.json \
      --bud "documents/Vendor Creation Sample BUD.docx" \
      --output output/rules_populated/2581-schema.json \
      --verbose

    python rule_extraction_agent.py \
      --schema output/complete_format/2581-schema.json \
      --bud "documents/Vendor Creation Sample BUD.docx" \
      --intra-panel extraction/intra_panel_output/vendor_basic_details.json \
      --output output/rules_populated/2581-schema.json \
      --validate \
      --llm-threshold 0.7 \
      --report summary_report.json
"""

import argparse
import sys
from pathlib import Path

from rule_extraction_agent.main import RuleExtractionAgent
from rule_extraction_agent.utils import generate_output_path


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Rule Extraction Agent - Automatic rule extraction from BUD logic sections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python rule_extraction_agent.py --schema output/complete_format/2581-schema.json

  # With all options
  python rule_extraction_agent.py \\
    --schema output/complete_format/2581-schema.json \\
    --intra-panel extraction/intra_panel_output/vendor_basic_details.json \\
    --output output/rules_populated/2581-schema.json \\
    --verbose \\
    --validate \\
    --llm-threshold 0.7 \\
    --report summary_report.json

  # Test run without saving
  python rule_extraction_agent.py \\
    --schema output/complete_format/2581-schema.json \\
    --dry-run \\
    --verbose
        """
    )

    # Required arguments
    parser.add_argument(
        '--schema',
        type=str,
        required=True,
        help='Path to schema JSON from extract_fields_complete.py'
    )

    # Optional arguments
    parser.add_argument(
        '--bud',
        type=str,
        help='Path to original BUD .docx file (required for logic extraction)'
    )

    parser.add_argument(
        '--intra-panel',
        type=str,
        help='Path to intra-panel references JSON (optional)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Output path for populated schema (default: auto-generated)'
    )

    parser.add_argument(
        '--rule-schemas',
        type=str,
        default='rules/Rule-Schemas.json',
        help='Path to Rule-Schemas.json (default: rules/Rule-Schemas.json)'
    )

    parser.add_argument(
        '--llm-threshold',
        type=float,
        default=0.7,
        help='Confidence threshold for LLM fallback (default: 0.7)'
    )

    parser.add_argument(
        '--report',
        type=str,
        help='Path to save summary report JSON (optional)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate generated rules (checks for unmatched fields, etc.)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without saving output (useful for testing)'
    )

    args = parser.parse_args()

    # Validate input file exists
    if not Path(args.schema).exists():
        print(f"Error: Schema file not found: {args.schema}", file=sys.stderr)
        return 1

    # Generate output path if not provided
    if not args.output:
        args.output = generate_output_path(args.schema, "rules_populated")

    # Validate BUD file if provided
    if args.bud and not Path(args.bud).exists():
        print(f"Error: BUD file not found: {args.bud}", file=sys.stderr)
        return 1

    # Display configuration
    print("Rule Extraction Agent")
    print("=" * 50)
    print(f"Schema: {args.schema}")
    if args.bud:
        print(f"BUD document: {args.bud}")
    if args.intra_panel:
        print(f"Intra-panel references: {args.intra_panel}")
    print(f"Output: {args.output}")
    print(f"LLM threshold: {args.llm_threshold}")
    if args.dry_run:
        print("Mode: DRY RUN (will not save output)")
    print("=" * 50)
    print()

    try:
        # Initialize agent
        agent = RuleExtractionAgent(
            schema_path=args.schema,
            bud_document_path=args.bud,
            intra_panel_path=args.intra_panel,
            rule_schemas_path=args.rule_schemas,
            llm_threshold=args.llm_threshold,
            verbose=args.verbose
        )

        # Process fields and generate rules
        result = agent.process()

        # Display results
        print()
        print(result.summary())
        print()

        # Validate if requested
        if args.validate:
            print("Validation:")
            print("-" * 50)
            if result.unmatched_fields:
                print(f"Warning: {len(result.unmatched_fields)} unmatched field references:")
                for field_ref in result.unmatched_fields[:10]:  # Show first 10
                    print(f"  - {field_ref}")
                if len(result.unmatched_fields) > 10:
                    print(f"  ... and {len(result.unmatched_fields) - 10} more")
            else:
                print("All field references matched successfully")

            if result.errors:
                print(f"\nErrors encountered: {len(result.errors)}")
                for error in result.errors[:5]:  # Show first 5
                    print(f"  - {error}")
            else:
                print("No errors encountered")

            print()

        # Save output unless dry run
        if not args.dry_run:
            agent.save_schema(args.output)
            print(f"Populated schema saved to: {args.output}")

            if args.report:
                agent.save_report(args.report)
                print(f"Summary report saved to: {args.report}")
        else:
            print("Dry run complete - no files saved")

        # Return success
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
