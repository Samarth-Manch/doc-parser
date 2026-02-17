#!/usr/bin/env python3
"""
Conditional Logic Mini Agent Dispatcher

This script:
1. Reads output from Validate EDV agent (panel by panel)
2. For each panel, calls Conditional Logic mini agent to add conditional fields
3. Outputs single JSON file containing all panels with conditional logic populated
"""

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional


def count_rules_needing_conditions(panel_fields: List[Dict]) -> int:
    """
    Count rules that likely need conditional logic based on field logic.

    Args:
        panel_fields: List of fields in the panel

    Returns:
        Estimated count of rules needing conditions
    """
    count = 0
    condition_keywords = [
        'if ', 'when ', 'based on',
        'always invisible', 'always disabled', 'always mandatory',
        'always non-mandatory', 'always enabled', 'always visible',
        'by default invisible', 'by default disabled', 'by default mandatory',
        'by default non-mandatory', 'by default enabled', 'by default visible',
        'non-editable', 'hidden', 'visible only when', 'mandatory if'
    ]

    for field in panel_fields:
        logic = field.get('logic', '').lower()
        rules = field.get('rules', [])

        if any(keyword in logic for keyword in condition_keywords) and rules:
            count += len(rules)

    return count


def call_conditional_logic_mini_agent(panel_fields: List[Dict],
                                      panel_name: str, temp_dir: Path) -> Optional[List[Dict]]:
    """
    Call the Conditional Logic mini agent via claude -p

    Args:
        panel_fields: Fields from Validate EDV agent output
        panel_name: Name of the panel
        temp_dir: Directory for temp files

    Returns:
        List of fields with conditional logic added, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    output_file = temp_dir / f"{safe_panel_name}_conditional_logic_output.json"
    log_file = temp_dir / f"{safe_panel_name}_conditional_logic_log.txt"

    # Write fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(panel_fields, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input Data
1. Fields with rules: {fields_input_file}
2. Log file: {log_file}

## Instructions
Follow the step-by-step approach defined in the agent prompt (05_condition_agent_v2).
- FIELDS_JSON = {fields_input_file}
- LOG_FILE = {log_file}

## Output
Write a JSON array to: {output_file}
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name}")
        print(f"  Fields: {len(panel_fields)}")
        print(f"  Rules likely needing conditions: ~{count_rules_needing_conditions(panel_fields)}")
        print('='*70)

        # Call claude -p with the Conditional Logic mini agent
        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--agent", "mini/05_condition_agent_v2",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path(__file__).parent.parent.parent)
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
        print(f"  Error calling Conditional Logic mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Conditional Logic Dispatcher - Add conditional logic to rules panel-by-panel"
    )
    parser.add_argument(
        "--validate-edv-output",
        required=True,
        help="Path to Validate EDV agent output JSON (panels with validate EDV rules)"
    )
    parser.add_argument(
        "--output",
        default="output/conditional_logic/all_panels_conditional_logic.json",
        help="Output file for all panels (default: output/conditional_logic/all_panels_conditional_logic.json)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.validate_edv_output).exists():
        print(f"Error: Validate EDV output file not found: {args.validate_edv_output}", file=sys.stderr)
        sys.exit(1)

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Load Validate EDV agent output
    print(f"Loading Validate EDV agent output: {args.validate_edv_output}")
    with open(args.validate_edv_output, 'r') as f:
        validate_edv_data = json.load(f)

    print(f"Found {len(validate_edv_data)} panels in input")

    # Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS WITH CONDITIONAL LOGIC AGENT")
    print("="*70)

    successful_panels = 0
    failed_panels = 0
    skipped_panels = 0
    total_fields_processed = 0
    all_results = {}

    for panel_name, panel_fields in validate_edv_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue

        total_rules = sum(len(field.get('rules', [])) for field in panel_fields)
        estimated_conditions = count_rules_needing_conditions(panel_fields)

        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {total_rules} rules, ~{estimated_conditions} may need conditions")

        # Call Conditional Logic mini agent
        result = call_conditional_logic_mini_agent(
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
    print("CONDITIONAL LOGIC DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(validate_edv_data)}")
    print(f"Successfully Processed: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Skipped (empty): {skipped_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
