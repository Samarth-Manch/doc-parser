#!/usr/bin/env python3
"""
CLI for the Eval framework.

Usage:
    python -m eval.cli --generated <path> --reference <path> [--output <path>]

Or:
    python eval/cli.py --generated <path> --reference <path> [--output <path>]
"""

import argparse
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evaluator import FormFillEvaluator
from eval.report_generator import generate_console_report


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate generated form fill JSON against reference"
    )
    parser.add_argument(
        "--generated", "-g",
        required=True,
        help="Path to generated JSON file"
    )
    parser.add_argument(
        "--reference", "-r",
        required=True,
        help="Path to reference JSON file"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path to save evaluation report (default: eval_report.json in generated file's directory)"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.90,
        help="Pass threshold (default: 0.90)"
    )
    parser.add_argument(
        "--llm-threshold",
        type=float,
        default=0.8,
        help="LLM confidence threshold for field matching (default: 0.8)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM-based matching (use only exact/normalized matching)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output only JSON report to stdout (for piping)"
    )

    args = parser.parse_args()

    # Validate input files
    if not os.path.exists(args.generated):
        print(f"Error: Generated file not found: {args.generated}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.reference):
        print(f"Error: Reference file not found: {args.reference}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output is None:
        generated_dir = os.path.dirname(args.generated) or "."
        args.output = os.path.join(generated_dir, "eval_report.json")

    # Create evaluator
    evaluator = FormFillEvaluator(
        use_llm=not args.no_llm,
        llm_threshold=args.llm_threshold,
        pass_threshold=args.threshold
    )

    if not args.json_only:
        print(f"Evaluating: {args.generated}")
        print(f"Against: {args.reference}")
        print(f"Output: {args.output}")
        print()

    try:
        # Run evaluation
        passed, report = evaluator.evaluate_and_save_report(
            args.generated,
            args.reference,
            args.output,
            verbose=args.verbose,
            include_llm_analysis=not args.no_llm
        )

        if args.json_only:
            # Output JSON to stdout
            print(json.dumps(report.to_dict(), indent=2))
        else:
            # Print console report
            print(generate_console_report(report.to_dict()))
            print(f"\nFull report saved to: {args.output}")

        # Exit with appropriate code
        sys.exit(0 if passed else 1)

    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"Error during evaluation: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
