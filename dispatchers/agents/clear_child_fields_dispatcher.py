#!/usr/bin/env python3
"""
Clear Child Fields Mini Agent Dispatcher

This script:
1. Reads output from Derivation Logic agent (panel by panel)
2. For each panel, calls Clear Child Fields mini agent to add clearing Expression (Client) rules
3. Outputs single JSON file containing all panels with clearing logic populated
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


def count_fields_with_children(panel_fields: List[Dict]) -> int:
    """
    Count fields that likely have parent-child relationships (fields with
    destination_fields pointing to other fields).

    Args:
        panel_fields: List of fields in the panel

    Returns:
        Estimated count of parent fields
    """
    parent_count = 0
    all_var_names = {f.get('variableName', '') for f in panel_fields}

    for field in panel_fields:
        has_children = False
        for rule in field.get('rules', []):
            dest_fields = rule.get('destination_fields', [])
            for dest in dest_fields:
                if dest != '-1' and dest != field.get('variableName', '') and dest in all_var_names:
                    has_children = True
                    break
            if has_children:
                break
        if has_children:
            parent_count += 1

    return parent_count


def call_clear_child_fields_mini_agent(panel_fields: List[Dict],
                                        panel_name: str, temp_dir: Path) -> Optional[List[Dict]]:
    """
    Call the Clear Child Fields mini agent via claude -p

    Args:
        panel_fields: Fields from Derivation Logic agent output
        panel_name: Name of the panel
        temp_dir: Directory for temp files

    Returns:
        List of fields with clearing Expression rules added, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    output_file = temp_dir / f"{safe_panel_name}_clear_child_output.json"
    log_file = temp_dir / f"{safe_panel_name}_clear_child_log.txt"

    # Write fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(panel_fields, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input Data
1. Fields with rules: {fields_input_file}
2. Log file: {log_file}

## Instructions
Follow the step-by-step approach defined in the agent prompt (07_clear_child_fields_agent).
- FIELDS_JSON = {fields_input_file}
- LOG_FILE = {log_file}

## CRITICAL: Only Handle Clearing Logic
This agent ONLY handles clearing child fields when a parent field changes.
Do NOT touch visibility, enabled/disabled, mandatory, derivation, or any other rules.

Scan ALL existing rules in the panel to find parent→child relationships.

IMPORTANT — NOT every parent-child relationship needs a clearing rule. Think from the UI
perspective: does the user need stale child values to be reset?

DO create clearing rules for these relationship types:
- Cascading dropdowns: Parent dropdown changes → child dropdown options are now wrong → must clear. Condition: true
- Expression (Client) derivation rules (ctfd): Parent value changes → derived value is stale → clear when parent is emptied. Condition: vo("_parent_")==""
- Validate EDV rules: Lookup source changes → looked-up values are stale → clear when source is emptied. Condition: vo("_parent_")==""
- Visibility/state rules (Make Visible, Make Invisible, Enable, Disable, Mandatory, Non-Mandatory): Parent changes → hidden fields may have stale data → clear. Condition: true

DO NOT create clearing rules for these (they handle their own data, clearing is redundant):
- OCR rules (PAN OCR, GSTIN OCR, Aadhaar Front OCR, Aadhaar Back OCR) — extract data from uploads, overwrite fields each time
- Validation rules with API calls (Validate PAN, Validate GSTIN, MSME Validation, Validate Pincode) — call external APIs and overwrite destinations each trigger
- Copy To rules — copy overwrites destination on each trigger
- Any rule that auto-populates fields as a one-shot side effect of a specific action

Ask yourself: "If I don't add a clearing rule here, will the user see stale/wrong data?"
If no (because the rule overwrites data anyway), skip it.
If yes (because the user changed a dropdown and old child values are now invalid), add it.

ULTIMATE PARENT PLACEMENT: Trace dependency chains to the root.
If A→B→C (A affects B, B affects C), the clearing for BOTH B and C goes on A (not B).
Walk chains upward until you find the field with no parent above it.

For each ultimate parent, place ONE Expression (Client) rule with cf, asdff, rffdd calls
covering ALL descendants (children, grandchildren, etc.).

CRITICAL — Choose the correct CONDITION for clearing (first arg of cf/asdff/rffdd):
- Use `true` when parent is a dropdown/selection and changing it invalidates children
  (cascading dropdowns, visibility controllers)
  Example: cf(true,"_state_","_city_")
- Use `vo("_parent_")==""` when parent populates/derives child values
  (derivation, EDV lookup)
  Only clear when parent becomes empty, otherwise derived values get wiped immediately.
  Example: cf(vo("_pan_")=="","_panholdername_","_pantype_")

Key rules:
1. Expression ALWAYS starts with on("change") and ( and ends with )
2. THREE function calls per condition group: cf, asdff, rffdd — same condition, same children
3. ONE rule per ULTIMATE PARENT — includes all descendants
4. Expression goes in conditionalValues, NOT in params — NO params field needed
5. Do NOT escape quotes — use raw double quotes in the expression
6. Skip destination_fields that are "-1" (cross-panel references)
7. Deduplicate children — each child appears only once
8. Add _expressionRuleType: "clear_field" to each rule

## Output
Write a JSON array to: {output_file}
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name}")
        print(f"  Fields: {len(panel_fields)}")
        print(f"  Fields with likely parent-child relationships: ~{count_fields_with_children(panel_fields)}")
        print('='*70)

        # Call claude -p with the Clear Child Fields mini agent
        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--agent", "mini/07_clear_child_fields_agent",
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
        usage = query_context_usage(panel_name, "Clear Child Fields")
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
        print(f"  Error calling Clear Child Fields mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Clear Child Fields Dispatcher - Add Expression (Client) rules for clearing child fields panel-by-panel"
    )
    parser.add_argument(
        "--derivation-output",
        required=True,
        help="Path to Derivation Logic agent output JSON (panels with derivation rules)"
    )
    parser.add_argument(
        "--output",
        default="output/clear_child_fields/all_panels_clear_child.json",
        help="Output file for all panels (default: output/clear_child_fields/all_panels_clear_child.json)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.derivation_output).exists():
        print(f"Error: Derivation Logic output file not found: {args.derivation_output}", file=sys.stderr)
        sys.exit(1)

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Load Derivation Logic agent output
    print(f"Loading Derivation Logic agent output: {args.derivation_output}")
    with open(args.derivation_output, 'r') as f:
        derivation_data = json.load(f)

    print(f"Found {len(derivation_data)} panels in input")

    # Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS WITH CLEAR CHILD FIELDS AGENT")
    print("="*70)

    successful_panels = 0
    failed_panels = 0
    skipped_panels = 0
    total_fields_processed = 0
    all_results = {}

    for panel_name, panel_fields in derivation_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue

        total_rules = sum(len(field.get('rules', [])) for field in panel_fields)
        estimated_parents = count_fields_with_children(panel_fields)

        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {total_rules} existing rules, ~{estimated_parents} may be parent fields")

        # Call Clear Child Fields mini agent
        result = call_clear_child_fields_mini_agent(
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
    print("CLEAR CHILD FIELDS DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(derivation_data)}")
    print(f"Successfully Processed: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Skipped (empty): {skipped_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
