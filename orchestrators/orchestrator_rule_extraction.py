#!/usr/bin/env python3
"""
Rule Extraction Orchestrator

This orchestrator:
1. Calls intra_panel_rule_field_references dispatcher to extract field dependencies
2. Creates timestamped directory in adws/
3. Saves templates_output in the timestamped folder
4. Calls the rule extraction coding agent with the outputs
"""

import argparse
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path


def create_timestamped_workspace(base_dir: str = "adws") -> tuple:
    """
    Create timestamped directory structure in adws/.

    Args:
        base_dir: Base directory for workspaces (default: adws)

    Returns:
        Tuple of (workspace_dir, templates_output_dir)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    workspace_dir = os.path.join(base_dir, timestamp)
    templates_output_dir = os.path.join(workspace_dir, "templates_output")

    os.makedirs(templates_output_dir, exist_ok=True)

    return workspace_dir, templates_output_dir


def run_intra_panel_extraction(document_path: str, output_dir: str) -> str:
    """
    Run the intra-panel field references dispatcher.

    Args:
        document_path: Path to the BUD document
        output_dir: Output directory for templates

    Returns:
        Path to the consolidated intra-panel references JSON
    """
    print("\n" + "="*60)
    print("STEP 1: INTRA-PANEL FIELD REFERENCES EXTRACTION")
    print("="*60)
    print(f"Document: {document_path}")
    print(f"Output directory: {output_dir}")

    try:
        result = subprocess.run(
            [
                "python3",
                "dispatchers/intra_panel_rule_field_references.py",
                document_path,
                "--output-dir", output_dir
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )

        if result.returncode != 0:
            print(f"✗ Intra-panel extraction failed:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return None

        print(result.stdout)

        # Find the consolidated JSON file
        doc_name = Path(document_path).stem
        consolidated_path = os.path.join(output_dir, f"{doc_name}_intra_panel_references.json")

        if os.path.exists(consolidated_path):
            print(f"✓ Intra-panel references extracted: {consolidated_path}")
            return consolidated_path
        else:
            print(f"✗ Consolidated file not found: {consolidated_path}", file=sys.stderr)
            return None

    except Exception as e:
        print(f"✗ Error running intra-panel extraction: {e}", file=sys.stderr)
        return None


def run_rule_extraction_agent(schema_path: str, intra_panel_path: str,
                              workspace_dir: str, verbose: bool = False,
                              validate: bool = False, llm_threshold: float = 0.7) -> tuple:
    """
    Run the rule extraction coding agent.

    Args:
        schema_path: Path to schema JSON
        intra_panel_path: Path to intra-panel references JSON
        workspace_dir: Workspace directory for outputs
        verbose: Enable verbose logging
        validate: Enable rule validation
        llm_threshold: Confidence threshold for LLM fallback

    Returns:
        Tuple of (output_path, report_path)
    """
    print("\n" + "="*60)
    print("STEP 2: RULE EXTRACTION CODING AGENT")
    print("="*60)
    print(f"Schema: {schema_path}")
    print(f"Intra-panel refs: {intra_panel_path}")

    # Set output paths
    output_path = os.path.join(workspace_dir, "populated_schema.json")
    report_path = os.path.join(workspace_dir, "extraction_report.json")

    try:
        cmd = [
            "python3",
            "dispatchers/rule_extraction_coding_agent.py",
            "--schema", schema_path,
            "--intra-panel", intra_panel_path,
            "--output", output_path,
            "--report", report_path,
            "--llm-threshold", str(llm_threshold)
        ]

        if verbose:
            cmd.append("--verbose")

        if validate:
            cmd.append("--validate")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )

        if result.returncode != 0:
            print(f"✗ Rule extraction agent failed:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return None, None

        print(result.stdout)

        if os.path.exists(output_path):
            print(f"✓ Rules extracted and populated: {output_path}")
            return output_path, report_path
        else:
            print(f"✗ Output file not created: {output_path}", file=sys.stderr)
            return None, None

    except Exception as e:
        print(f"✗ Error running rule extraction agent: {e}", file=sys.stderr)
        return None, None


def print_summary(workspace_dir: str, intra_panel_path: str, output_path: str, report_path: str):
    """
    Print final summary of the orchestration.

    Args:
        workspace_dir: Workspace directory
        intra_panel_path: Path to intra-panel references JSON
        output_path: Path to populated schema JSON
        report_path: Path to extraction report JSON
    """
    print("\n" + "="*60)
    print("ORCHESTRATION COMPLETE")
    print("="*60)
    print(f"Workspace: {workspace_dir}")
    print("\nGenerated Files:")
    print(f"  1. Intra-panel references: {intra_panel_path}")
    print(f"  2. Populated schema: {output_path}")
    if os.path.exists(report_path):
        print(f"  3. Extraction report: {report_path}")

    # Load and display report summary if available
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r') as f:
                report = json.load(f)

            print("\nExtraction Summary:")
            if "total_rules_generated" in report:
                print(f"  - Total rules generated: {report['total_rules_generated']}")
            if "deterministic_coverage" in report:
                print(f"  - Deterministic coverage: {report['deterministic_coverage']:.1%}")
            if "llm_fallback_count" in report:
                print(f"  - LLM fallback used: {report['llm_fallback_count']} times")
        except:
            pass

    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate rule extraction pipeline: intra-panel extraction → rule extraction agent"
    )
    parser.add_argument(
        "document_path",
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "--schema",
        required=True,
        help="Path to schema JSON from extract_fields_complete.py"
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace directory (default: adws/<timestamp>/)"
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
    parser.add_argument(
        "--llm-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for LLM fallback (default: 0.7)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.document_path):
        print(f"Error: Document not found: {args.document_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.schema):
        print(f"Error: Schema file not found: {args.schema}", file=sys.stderr)
        sys.exit(1)

    # Create timestamped workspace
    if args.workspace:
        workspace_dir = args.workspace
        templates_output_dir = os.path.join(workspace_dir, "templates_output")
        os.makedirs(templates_output_dir, exist_ok=True)
    else:
        workspace_dir, templates_output_dir = create_timestamped_workspace()

    print("="*60)
    print("RULE EXTRACTION ORCHESTRATOR")
    print("="*60)
    print(f"Document: {args.document_path}")
    print(f"Schema: {args.schema}")
    print(f"Workspace: {workspace_dir}")
    print("="*60)

    # Step 1: Run intra-panel extraction
    intra_panel_path = run_intra_panel_extraction(args.document_path, templates_output_dir)

    if not intra_panel_path:
        print("\n✗ Orchestration failed at Step 1", file=sys.stderr)
        sys.exit(1)

    # Step 2: Run rule extraction agent
    output_path, report_path = run_rule_extraction_agent(
        args.schema,
        intra_panel_path,
        workspace_dir,
        verbose=args.verbose,
        validate=args.validate,
        llm_threshold=args.llm_threshold
    )

    if not output_path:
        print("\n✗ Orchestration failed at Step 2", file=sys.stderr)
        sys.exit(1)

    # Print final summary
    print_summary(workspace_dir, intra_panel_path, output_path, report_path)

    sys.exit(0)


if __name__ == "__main__":
    main()
