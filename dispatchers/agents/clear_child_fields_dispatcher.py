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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional


from context_optimization import slim_rules_for_relationship_analysis, restore_rules_after_slim, log_strip_savings

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
                                        panel_name: str, temp_dir: Path,
                                        context_usage: bool = False,
                                        verbose: bool = True,
                                        model: str = "opus") -> Optional[List[Dict]]:
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

    # Slim rules — agent needs rule_name/source/destination to identify
    # parent-child relationships, but doesn't need full params/conditions
    slimmed_fields, stored_rules = slim_rules_for_relationship_analysis(panel_fields)
    if verbose:
        log_strip_savings(panel_fields, slimmed_fields, panel_name)

    # Write slimmed fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(slimmed_fields, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input
- FIELDS_JSON: {fields_input_file}
- LOG_FILE: {log_file}

## Output
Write JSON array to: {output_file}

Follow the agent prompt instructions (07_clear_child_fields_agent).
"""

    try:
        if verbose:
            print(f"\n{'='*70}")
            print(f"PROCESSING PANEL: {panel_name}")
            print(f"  Fields: {len(panel_fields)}")
            print(f"  Fields with likely parent-child relationships: ~{count_fields_with_children(panel_fields)}")
            print('='*70)

        # Call claude -p with the Clear Child Fields mini agent
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
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
            if verbose:
                print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"  Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Query context usage from the agent session (opt-in)
        if context_usage:
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
                result = restore_rules_after_slim(result, stored_rules)
                if verbose:
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
    parser.add_argument(
        "--context-usage",
        action="store_true",
        default=False,
        help="Query and display context window usage after each panel (adds ~30s per panel)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel panels to process (default: 4, use 1 for sequential)"
    )
    parser.add_argument(
        "--model",
        default="opus",
        help="Claude model to use (default: opus)"
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

    max_workers = args.max_workers

    # Prepare jobs
    jobs = []
    skipped_panels = 0
    for panel_name, panel_fields in derivation_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue

        total_rules = sum(len(field.get('rules', [])) for field in panel_fields)
        estimated_parents = count_fields_with_children(panel_fields)
        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {total_rules} existing rules, ~{estimated_parents} may be parent fields")
        jobs.append((panel_name, panel_fields))

    successful_panels = 0
    failed_panels = 0
    total_fields_processed = 0
    all_results = {}

    if max_workers <= 1:
        # Sequential processing
        for panel_name, panel_fields in jobs:
            result = call_clear_child_fields_mini_agent(
                panel_fields, panel_name, temp_dir,
                context_usage=args.context_usage, verbose=True, model=args.model
            )
            if result:
                successful_panels += 1
                total_fields_processed += len(result)
                all_results[panel_name] = result
            else:
                failed_panels += 1
                all_results[panel_name] = panel_fields
                total_fields_processed += len(panel_fields)
                print(f"  Panel '{panel_name}' failed - using original data", file=sys.stderr)
    else:
        # Parallel processing
        print(f"\nProcessing {len(jobs)} panels in parallel (max_workers={max_workers})")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_panel = {}
            for panel_name, panel_fields in jobs:
                future = executor.submit(
                    call_clear_child_fields_mini_agent,
                    panel_fields, panel_name, temp_dir,
                    context_usage=args.context_usage, verbose=False, model=args.model
                )
                future_to_panel[future] = (panel_name, panel_fields)

            for future in as_completed(future_to_panel):
                panel_name, original_fields = future_to_panel[future]
                try:
                    result = future.result()
                    if result:
                        successful_panels += 1
                        total_fields_processed += len(result)
                        all_results[panel_name] = result
                        print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
                    else:
                        failed_panels += 1
                        all_results[panel_name] = original_fields
                        total_fields_processed += len(original_fields)
                        print(f"✗ Panel '{panel_name}' failed - using original data", file=sys.stderr)
                except Exception as e:
                    failed_panels += 1
                    all_results[panel_name] = original_fields
                    total_fields_processed += len(original_fields)
                    print(f"✗ Panel '{panel_name}' error: {e}", file=sys.stderr)

    # Reorder results to match original panel sequence
    ordered_results = {}
    for panel_name in derivation_data:
        if panel_name in all_results:
            ordered_results[panel_name] = all_results[panel_name]
    all_results = ordered_results

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
