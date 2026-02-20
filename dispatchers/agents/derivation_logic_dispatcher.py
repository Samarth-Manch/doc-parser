#!/usr/bin/env python3
"""
Derivation Logic Mini Agent Dispatcher

This script:
1. Reads output from Conditional Logic agent (panel by panel)
2. For each panel, calls Derivation Logic mini agent to add Expression (Client) rules
3. Outputs single JSON file containing all panels with derivation logic populated
"""

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional


PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


def query_context_usage(panel_name: str, agent_name: str) -> Optional[str]:
    """
    Query the last claude agent session for context/token usage.
    Uses --continue to resume the last conversation and ask for usage stats.

    Returns:
        Usage report string, or None if failed
    """
    usage_prompt = (
        "Report the context window usage for this conversation. "
        "Include: (1) number of input tokens used, "
        "(2) number of output tokens used, "
        "(3) total tokens used, and "
        "(4) percentage of the context window (200K tokens) that is filled. "
        "Format as a brief one-line summary."
    )

    try:
        process = subprocess.run(
            ["claude", "--continue", "-p", usage_prompt],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )

        if process.returncode == 0 and process.stdout.strip():
            return process.stdout.strip()
        return None
    except Exception:
        return None


def count_fields_with_derivation_logic(panel_fields: List[Dict]) -> int:
    """
    Count fields that likely have derivation logic based on keywords.

    Args:
        panel_fields: List of fields in the panel

    Returns:
        Estimated count of fields with derivation logic
    """
    count = 0
    derivation_keywords = [
        'derived', 'derive', 'derivation',
        'value is ', 'value should be',
        'populated as', 'populate as',
        'default value', 'set as', 'set to',
        'copied as', 'copy as',
        'then value', 'then it is',
    ]

    for field in panel_fields:
        logic = field.get('logic', '').lower()
        if any(keyword in logic for keyword in derivation_keywords):
            count += 1

    return count


def call_derivation_logic_mini_agent(panel_fields: List[Dict],
                                      panel_name: str, temp_dir: Path) -> Optional[List[Dict]]:
    """
    Call the Derivation Logic mini agent via claude -p

    Args:
        panel_fields: Fields from Conditional Logic agent output
        panel_name: Name of the panel
        temp_dir: Directory for temp files

    Returns:
        List of fields with derivation Expression rules added, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    output_file = temp_dir / f"{safe_panel_name}_derivation_output.json"
    log_file = temp_dir / f"{safe_panel_name}_derivation_log.txt"

    # Write fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(panel_fields, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input Data
1. Fields with rules: {fields_input_file}
2. Log file: {log_file}

## Instructions
Follow the step-by-step approach defined in the agent prompt (06_derivation_agent).
- FIELDS_JSON = {fields_input_file}
- LOG_FILE = {log_file}

## CRITICAL: Only Handle Derivation Logic
This agent ONLY handles value derivation — logic that sets/derives/populates a field's VALUE
based on another field's selection. Do NOT touch visibility, enabled/disabled, or mandatory rules.

Look for logic patterns like:
- "If X is selected then value is Y / derived as Y / populated as Y"
- "If X then derive A, otherwise derive B"
- Conditional value assignment based on another field

For each derivation found, place ONE Expression (Client) rule on the CONTROLLER field containing
ALL ctfd + asdff expressions concatenated with semicolons in conditionalValues (NOT params).

The expression goes in conditionalValues as a single string, ALWAYS wrapped with on("change") and (...):
  conditionValueType: "EXPR"
  condition: "IN"
  conditionalValues: ["on("change") and (ctfd(vo("_ctrl_")=="VAL1","Text1","_dest_");ctfd(vo("_ctrl_")!="VAL1","Text2","_dest_");asdff(vo("_dest_")!="","_dest_"))"]

Key rules:
1. Expression ALWAYS starts with on("change") and ( and ends with )
2. ALL expressions go into ONE rule on the CONTROLLER field — never separate rules
3. Expression goes in conditionalValues, NOT in params — NO params field needed
4. Do NOT escape quotes — use raw double quotes in the expression
5. Use != for opposite/else conditions (never == with the opposite value)
6. asdff goes at the end, before the closing parenthesis
7. Add _expressionRuleType: "derivation" to each Expression (Client) rule

## Output
Write a JSON array to: {output_file}
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name}")
        print(f"  Fields: {len(panel_fields)}")
        print(f"  Fields with likely derivation logic: ~{count_fields_with_derivation_logic(panel_fields)}")
        print('='*70)

        # Call claude -p with the Derivation Logic mini agent
        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--agent", "mini/06_derivation_agent",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        # Collect output
        output_lines = []
        for line in process.stdout:
            print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"  Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Query context usage from the agent session
        print(f"\n--- Context Usage ({panel_name}) ---")
        usage = query_context_usage(panel_name, "Derivation Logic")
        if usage:
            print(usage)
        else:
            print("(Could not retrieve context usage)")
        print("---")

        # Read output file
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
                print(f"  Panel '{panel_name}' completed - {len(result)} fields processed")
                return result
            except json.JSONDecodeError as e:
                print(f"  Failed to parse output JSON: {e}", file=sys.stderr)
                return None
        else:
            print(f"  Output file not found: {output_file}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("  Error: 'claude' command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Error calling Derivation Logic mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Derivation Logic Dispatcher - Add Expression (Client) rules for value derivation panel-by-panel"
    )
    parser.add_argument(
        "--conditional-logic-output",
        required=True,
        help="Path to Conditional Logic agent output JSON (panels with conditional rules)"
    )
    parser.add_argument(
        "--output",
        default="output/derivation_logic/all_panels_derivation.json",
        help="Output file for all panels (default: output/derivation_logic/all_panels_derivation.json)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.conditional_logic_output).exists():
        print(f"Error: Conditional Logic output file not found: {args.conditional_logic_output}", file=sys.stderr)
        sys.exit(1)

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Load Conditional Logic agent output
    print(f"Loading Conditional Logic agent output: {args.conditional_logic_output}")
    with open(args.conditional_logic_output, 'r') as f:
        conditional_data = json.load(f)

    print(f"Found {len(conditional_data)} panels in input")

    # Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS WITH DERIVATION LOGIC AGENT")
    print("="*70)

    successful_panels = 0
    failed_panels = 0
    skipped_panels = 0
    total_fields_processed = 0
    all_results = {}

    for panel_name, panel_fields in conditional_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue

        total_rules = sum(len(field.get('rules', [])) for field in panel_fields)
        estimated_derivations = count_fields_with_derivation_logic(panel_fields)

        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {total_rules} existing rules, ~{estimated_derivations} may have derivation logic")

        # Call Derivation Logic mini agent
        result = call_derivation_logic_mini_agent(
            panel_fields,
            panel_name,
            temp_dir
        )

        if result:
            successful_panels += 1
            total_fields_processed += len(result)
            all_results[panel_name] = result
        else:
            failed_panels += 1
            # On failure, pass through original data
            all_results[panel_name] = panel_fields
            total_fields_processed += len(panel_fields)
            print(f"  Panel '{panel_name}' failed - using original data", file=sys.stderr)

    # Write all results to single output file
    if all_results:
        print(f"\nWriting all results to: {output_file}")
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"Successfully wrote {len(all_results)} panels to output file")

    # Print final summary
    print("\n" + "="*70)
    print("DERIVATION LOGIC DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(conditional_data)}")
    print(f"Successfully Processed: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Skipped (empty): {skipped_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
