#!/usr/bin/env python3
"""
Rule Extraction Coding Agent Dispatcher

This script:
1. Takes schema JSON and intra-panel references JSON as input
2. Calls Claude coding agent to implement the rule extraction system
3. Outputs the populated schema with formFillRules
"""

import argparse
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path


def validate_input_files(schema_path: str, intra_panel_path: str) -> tuple:
    """
    Validate that input files exist and are valid JSON.

    Args:
        schema_path: Path to schema JSON
        intra_panel_path: Path to intra-panel references JSON

    Returns:
        Tuple of (schema_data, intra_panel_data)
    """
    if not os.path.exists(schema_path):
        print(f"Error: Schema file not found: {schema_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(intra_panel_path):
        print(f"Error: Intra-panel references file not found: {intra_panel_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
    except Exception as e:
        print(f"Error reading schema JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(intra_panel_path, 'r') as f:
            intra_panel_data = json.load(f)
    except Exception as e:
        print(f"Error reading intra-panel JSON: {e}", file=sys.stderr)
        sys.exit(1)

    return schema_data, intra_panel_data


def call_claude_agent(schema_path: str, intra_panel_path: str, output_path: str,
                     verbose: bool = False, validate: bool = False,
                     llm_threshold: float = 0.7, report_path: str = None,
                     prev_workspace: str = None, prev_self_heal: str = None,
                     prev_schema: str = None, prev_eval: str = None,
                     prev_extraction: str = None, prev_api_schema: str = None,
                     prev_api_response: str = None,
                     edv_tables: str = None, field_edv_mapping: str = None) -> bool:
    """
    Call the Claude rule extraction coding agent.

    Args:
        schema_path: Path to schema JSON
        intra_panel_path: Path to intra-panel references JSON
        output_path: Path for output schema
        verbose: Enable verbose logging
        validate: Enable rule validation
        llm_threshold: Confidence threshold for LLM fallback
        report_path: Path to save summary report
        prev_workspace: Previous run workspace directory
        prev_self_heal: Path to previous self_heal_instructions JSON
        prev_schema: Path to previous populated_schema JSON
        prev_eval: Path to previous eval_report JSON
        prev_extraction: Path to previous extraction_report JSON
        prev_api_schema: Path to previous api_schema JSON
        prev_api_response: Path to previous api_response JSON
        edv_tables: Path to EDV tables registry JSON
        field_edv_mapping: Path to field-EDV mapping JSON

    Returns:
        True if successful, False otherwise
    """
    # Build previous run context section
    prev_context = ""
    if any([prev_workspace, prev_self_heal, prev_schema, prev_eval, prev_extraction, prev_api_schema, prev_api_response]):
        prev_context = """

## ⚠️ CRITICAL: Previous Run Context (LEARN FROM THESE!)

**Before generating ANY code, you MUST read and analyze files from the previous run.**

The following files contain valuable context from previous iterations that you should learn from:
"""
        if prev_workspace:
            prev_context += f"\n- **Previous Workspace**: {prev_workspace}"
        if prev_self_heal:
            prev_context += f"\n- **Self-Heal Instructions** (READ FIRST!): {prev_self_heal}"
        if prev_schema:
            prev_context += f"\n- **Previous Generated Schema**: {prev_schema}"
        if prev_eval:
            prev_context += f"\n- **Previous Eval Report** (See what failed): {prev_eval}"
        if prev_extraction:
            prev_context += f"\n- **Previous Extraction Report**: {prev_extraction}"
        if prev_api_schema:
            prev_context += f"\n- **Previous API Schema**: {prev_api_schema}"
        if prev_api_response:
            prev_context += f"\n- **Previous API Response** (See API errors): {prev_api_response}"

        prev_context += """

**ACTION REQUIRED:**
1. Use the Read tool to read the self_heal_instructions file FIRST
2. Understand what went wrong in previous iterations
3. Apply the fixes and improvements in your code generation
4. Do NOT repeat the same mistakes from previous runs
"""

    # Build EDV context section
    edv_context = ""
    if edv_tables or field_edv_mapping:
        edv_context = """

## EDV (External Data Value) Mapping Files

**These files contain EDV table mappings for generating EXT_DROP_DOWN and EXT_VALUE rules.**
"""
        if edv_tables:
            edv_context += f"\n- **EDV Tables Registry**: {edv_tables}"
        if field_edv_mapping:
            edv_context += f"\n- **Field-EDV Mapping**: {field_edv_mapping}"

        edv_context += """

**Use these files to:**
1. Resolve "reference table X.Y" to EDV table names
2. Generate correct params for EXT_DROP_DOWN rules (sourceType: FORM_FILL_DROP_DOWN)
3. Generate correct params for EXT_VALUE rules (sourceType: EXTERNAL_DATA_VALUE)
4. Identify parent-child dropdown relationships for cascading dropdowns
"""

    prompt = f"""Implement the rule extraction system according to the plan.

## Task
Implement the complete rule extraction coding agent system that extracts rules from BUD logic/rules sections and populates formFillRules arrays in the JSON schema.

## Input Files
- Schema JSON: {schema_path}
- Intra-Panel References: {intra_panel_path}
{f"- EDV Tables: {edv_tables}" if edv_tables else ""}
{f"- Field-EDV Mapping: {field_edv_mapping}" if field_edv_mapping else ""}

## Output Files
- Populated Schema: {output_path}
{f"- Summary Report: {report_path}" if report_path else ""}

## Configuration
- Verbose mode: {verbose}
- Validate rules: {validate}
- LLM threshold: {llm_threshold}
{prev_context}
{edv_context}

## Instructions
Use the /rule_extraction_coding_agent skill to implement the complete system following the plan in .claude/plans/plan.md.

Implement all phases:
1. Phase 1: Core Infrastructure (models, logic parser, field matcher, rule builders)
2. Phase 2: Rule Selection Tree (decision tree, pattern matching)
3. Phase 3: Complex Rules & LLM Fallback (OpenAI integration, confidence scoring)
4. Phase 4: Integration & Testing (full pipeline integration)

The system should:
- Parse logic statements into structured data
- Match field references to field IDs
- Select rules deterministically using pattern matching
- Fall back to LLM for complex cases (confidence < {llm_threshold})
- Generate formFillRules JSON structures
- Populate the schema with generated rules
"""

    try:
        # Use Popen to stream output in real-time
        print("\n" + "-"*60)
        print("CLAUDE AGENT OUTPUT (streaming)")
        print("-"*60 + "\n")

        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--allowedTools", "Read,Write,Edit,Bash,Glob,Grep"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            cwd=str(Path(__file__).parent.parent)
        )

        # Stream output in real-time
        output_lines = []
        for line in process.stdout:
            print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        print("\n" + "-"*60)
        print(f"CLAUDE AGENT FINISHED (exit code: {process.returncode})")
        print("-"*60 + "\n")

        if process.returncode != 0:
            print(f"Claude agent failed with exit code: {process.returncode}", file=sys.stderr)
            return False

        # Check if output file was created
        if os.path.exists(output_path):
            print(f"✓ Rule extraction completed successfully")
            return True
        else:
            print(f"✗ Output file not created: {output_path}", file=sys.stderr)
            # Print last few lines of output for debugging
            if output_lines:
                print("Last 20 lines of output:", file=sys.stderr)
                for line in output_lines[-20:]:
                    print(f"  {line}", end='', file=sys.stderr)
            return False

    except FileNotFoundError:
        print("Error: 'claude' command not found. Ensure Claude CLI is installed.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error calling Claude agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Rule Extraction Coding Agent Dispatcher"
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
        default=None,
        help="Output path for populated schema (default: auto-generated)"
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
    parser.add_argument(
        "--report",
        default=None,
        help="Path to save summary report"
    )

    # Previous run context arguments (for self-healing / learning from past iterations)
    parser.add_argument(
        "--prev-workspace",
        default=None,
        help="Previous run workspace directory"
    )
    parser.add_argument(
        "--prev-self-heal",
        default=None,
        help="Path to previous self_heal_instructions JSON"
    )
    parser.add_argument(
        "--prev-schema",
        default=None,
        help="Path to previous populated_schema JSON"
    )
    parser.add_argument(
        "--prev-eval",
        default=None,
        help="Path to previous eval_report JSON"
    )
    parser.add_argument(
        "--prev-extraction",
        default=None,
        help="Path to previous extraction_report JSON"
    )
    parser.add_argument(
        "--prev-api-schema",
        default=None,
        help="Path to previous api_schema JSON"
    )
    parser.add_argument(
        "--prev-api-response",
        default=None,
        help="Path to previous api_response JSON"
    )

    # EDV (External Data Value) mapping arguments
    parser.add_argument(
        "--edv-tables",
        default=None,
        help="Path to EDV tables registry JSON (from edv_table_mapping dispatcher)"
    )
    parser.add_argument(
        "--field-edv-mapping",
        default=None,
        help="Path to field-EDV mapping JSON (from edv_table_mapping dispatcher)"
    )

    args = parser.parse_args()

    # Validate input files
    print("Validating input files...")
    schema_data, intra_panel_data = validate_input_files(args.schema, args.intra_panel)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        schema_name = Path(args.schema).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"output/rules_populated/{schema_name}_rules_{timestamp}.json"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Print summary
    print("\n" + "="*60)
    print("RULE EXTRACTION CODING AGENT")
    print("="*60)
    print(f"Schema: {args.schema}")
    print(f"Intra-panel refs: {args.intra_panel}")
    if args.edv_tables:
        print(f"EDV tables: {args.edv_tables}")
    if args.field_edv_mapping:
        print(f"Field-EDV mapping: {args.field_edv_mapping}")
    print(f"Output: {output_path}")
    if args.report:
        print(f"Report: {args.report}")
    print(f"LLM threshold: {args.llm_threshold}")
    print("="*60)

    # Call Claude agent
    print("\nCalling Claude rule extraction coding agent...")

    # Check for previous run context
    if args.prev_workspace or args.prev_self_heal:
        print("\n📚 Previous run context provided - agent will learn from past iterations")

    success = call_claude_agent(
        args.schema,
        args.intra_panel,
        output_path,
        verbose=args.verbose,
        validate=args.validate,
        llm_threshold=args.llm_threshold,
        report_path=args.report,
        prev_workspace=args.prev_workspace,
        prev_self_heal=args.prev_self_heal,
        prev_schema=args.prev_schema,
        prev_eval=args.prev_eval,
        prev_extraction=args.prev_extraction,
        prev_api_schema=args.prev_api_schema,
        prev_api_response=args.prev_api_response,
        edv_tables=args.edv_tables,
        field_edv_mapping=args.field_edv_mapping
    )

    if success:
        print("\n" + "="*60)
        print("RULE EXTRACTION COMPLETE")
        print("="*60)
        print(f"Output: {output_path}")
        if args.report and os.path.exists(args.report):
            print(f"Report: {args.report}")
        print("="*60)
        sys.exit(0)
    else:
        print("\nRule extraction failed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
