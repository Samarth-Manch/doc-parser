#!/usr/bin/env python3
"""
Eval Rule Extraction Dispatcher

This script:
1. Takes generated output and reference output paths
2. Calls Claude eval skill to intelligently compare outputs
3. Generates detailed evaluation report with self-heal instructions
"""

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path


def validate_input_files(generated_path: str, reference_path: str) -> tuple:
    """
    Validate that input files exist and are valid JSON.

    Args:
        generated_path: Path to generated output JSON
        reference_path: Path to reference output JSON

    Returns:
        Tuple of (generated_data, reference_data)
    """
    if not os.path.exists(generated_path):
        print(f"Error: Generated output not found: {generated_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(reference_path):
        print(f"Error: Reference output not found: {reference_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(generated_path, 'r') as f:
            generated_data = json.load(f)
    except Exception as e:
        print(f"Error reading generated JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(reference_path, 'r') as f:
            reference_data = json.load(f)
    except Exception as e:
        print(f"Error reading reference JSON: {e}", file=sys.stderr)
        sys.exit(1)

    return generated_data, reference_data


def call_claude_eval(generated_path: str, reference_path: str,
                     eval_report_path: str, threshold: float = 0.90) -> dict:
    """
    Call the Claude eval skill to evaluate the generated output.

    Args:
        generated_path: Path to generated output JSON
        reference_path: Path to reference output JSON
        eval_report_path: Path to save evaluation report
        threshold: Pass threshold (default: 0.90)

    Returns:
        Evaluation report dictionary or None if failed
    """
    prompt = f"""Evaluate the rule extraction output using Claude intelligence.

## Task
Compare the generated rule extraction output against the human-made reference output. Use semantic understanding to identify discrepancies, missing rules, incorrect mappings, and generate actionable feedback.

## Input Files
- Generated Output: {generated_path}
- Reference Output: {reference_path}

## Output File
- Evaluation Report: {eval_report_path}

## Configuration
- Pass Threshold: {threshold}

## Instructions
Use the /eval_rule_extraction skill to:
1. Read both JSON files
2. Find common fields (exist in BOTH outputs)
3. Compare rules semantically (not just structure)
4. Calculate coverage and accuracy metrics
5. Identify discrepancies with severity levels
6. Generate self-heal instructions for code agent
7. Output detailed eval report JSON

Remember:
- Only compare fields present in BOTH outputs
- Understand rule semantics, not just structure
- Provide actionable feedback for self-healing
- Be fair - recognize semantic equivalents
"""

    try:
        result = subprocess.run(
            [
                "claude",
                "-p", prompt,
                "--allowedTools", "Read,Write,Bash"
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        if result.returncode != 0:
            print(f"Claude eval skill failed: {result.stderr}", file=sys.stderr)
            return None

        # Read the generated eval report
        if os.path.exists(eval_report_path):
            try:
                with open(eval_report_path, 'r') as f:
                    eval_report = json.load(f)
                return eval_report
            except Exception as e:
                print(f"Failed to read eval report: {e}", file=sys.stderr)
                return None
        else:
            print(f"Eval report not created: {eval_report_path}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("Error: 'claude' command not found. Ensure Claude CLI is installed.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error calling Claude eval: {e}", file=sys.stderr)
        return None


def print_eval_summary(eval_report: dict):
    """
    Print evaluation summary to console.

    Args:
        eval_report: Evaluation report dictionary
    """
    summary = eval_report.get("evaluation_summary", {})
    coverage = eval_report.get("coverage_metrics", {})
    accuracy = eval_report.get("accuracy_metrics", {})
    discrepancies = eval_report.get("discrepancies", [])

    overall_score = summary.get("overall_score", 0)
    threshold = summary.get("pass_threshold", 0.90)
    passed = summary.get("evaluation_passed", False)

    # Count issues by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for disc in discrepancies:
        severity = disc.get("severity", "info")
        if severity in severity_counts:
            severity_counts[severity] += 1

    print("\n" + "="*70)
    print("RULE EXTRACTION EVALUATION REPORT")
    print("="*70)
    print(f"Generated: {summary.get('generated_output', 'N/A')}")
    print(f"Reference: {summary.get('reference_output', 'N/A')}")
    print()
    status = "PASSED ✓" if passed else "FAILED ✗"
    print(f"Overall Score: {overall_score:.0%} (Threshold: {threshold:.0%}) - {status}")
    print("-"*70)

    print("Coverage Metrics:")
    print(f"  - Field Coverage: {coverage.get('field_coverage', 0):.0%} "
          f"({coverage.get('common_fields', 0)}/{coverage.get('total_fields_in_reference', 0)} fields)")
    print(f"  - Rule Coverage: {coverage.get('rule_coverage', 0):.0%} "
          f"({coverage.get('total_rules_in_generated', 0)}/{coverage.get('total_rules_in_reference', 0)} rules)")
    print()

    print("Accuracy Metrics:")
    print(f"  - Exact Match Rate: {accuracy.get('exact_match_rate', 0):.0%}")
    print(f"  - Semantic Match Rate: {accuracy.get('semantic_match_rate', 0):.0%}")
    print(f"  - False Positive Rate: {accuracy.get('false_positive_rate', 0):.0%}")
    print()

    print("Issues Found:")
    print(f"  - Critical: {severity_counts['critical']}")
    print(f"  - High: {severity_counts['high']}")
    print(f"  - Medium: {severity_counts['medium']}")
    print(f"  - Low: {severity_counts['low']}")
    print(f"  - Info: {severity_counts['info']}")
    print()

    # Show top issues
    if discrepancies:
        print("Top Issues:")
        high_priority = [d for d in discrepancies if d.get("severity") in ["critical", "high"]]
        for i, disc in enumerate(high_priority[:5], 1):
            print(f"  {i}. [{disc.get('severity', 'unknown').upper()}] {disc.get('issue', 'N/A')}")
        print()

    # Show recommendations
    suggestions = eval_report.get("suggestions_for_improvement", [])
    if suggestions:
        print("Recommendations:")
        for i, suggestion in enumerate(suggestions[:5], 1):
            print(f"  {i}. {suggestion}")
        print()

    print("="*70)
    print(f"Detailed report saved to: {eval_report.get('evaluation_summary', {}).get('generated_output', 'N/A').replace('populated_schema.json', 'eval_report.json')}")
    print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate rule extraction output against reference using Claude intelligence"
    )
    parser.add_argument(
        "--generated",
        required=True,
        help="Path to generated output JSON"
    )
    parser.add_argument(
        "--reference",
        required=True,
        help="Path to reference output JSON (human-made)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to save eval report (default: same dir as generated, eval_report.json)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.90,
        help="Pass threshold (default: 0.90)"
    )

    args = parser.parse_args()

    # Validate input files
    print("Validating input files...")
    generated_data, reference_data = validate_input_files(args.generated, args.reference)

    # Determine eval report path
    if args.output:
        eval_report_path = args.output
    else:
        generated_dir = os.path.dirname(args.generated)
        eval_report_path = os.path.join(generated_dir, "eval_report.json")

    # Print summary
    print("\n" + "="*70)
    print("RULE EXTRACTION EVALUATION")
    print("="*70)
    print(f"Generated: {args.generated}")
    print(f"Reference: {args.reference}")
    print(f"Eval Report: {eval_report_path}")
    print(f"Threshold: {args.threshold:.0%}")
    print("="*70)

    # Call Claude eval
    print("\nCalling Claude eval skill...")
    eval_report = call_claude_eval(
        args.generated,
        args.reference,
        eval_report_path,
        threshold=args.threshold
    )

    if not eval_report:
        print("\nEvaluation failed", file=sys.stderr)
        sys.exit(1)

    # Print summary
    print_eval_summary(eval_report)

    # Exit with appropriate code
    passed = eval_report.get("evaluation_summary", {}).get("evaluation_passed", False)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
