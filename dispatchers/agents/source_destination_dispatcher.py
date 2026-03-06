#!/usr/bin/env python3
"""
Source Destination Mini Agent Dispatcher

This script:
1. Reads output from Rule Type Placement agent (panel by panel)
2. For each panel, filters Rule-Schemas.json to get schemas for rules mentioned
3. Calls Source Destination mini agent with fields and filtered rule schemas
4. Outputs single JSON file containing all panels with source/destination populated
"""

import argparse
import json
import subprocess
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def load_rule_schemas(rule_schemas_path: str) -> Dict[str, Dict]:
    """
    Load Rule-Schemas.json and create name->schema mapping

    Returns:
        Dict mapping rule names to full rule schemas
    """
    with open(rule_schemas_path, 'r') as f:
        data = json.load(f)

    # Create mapping of rule name to full schema
    name_to_schema = {}

    for rule in data.get('content', []):
        name = rule.get('name', '')
        if name:
            name_to_schema[name] = rule

    return name_to_schema


def get_relevant_rule_schemas(panel_fields: List[Dict],
                               name_to_schema: Dict[str, Dict]) -> List[Dict]:
    """
    Get relevant rule schemas for fields in a panel

    Args:
        panel_fields: List of fields with their rules
        name_to_schema: Mapping of rule name to schema

    Returns:
        List of filtered rule schemas needed for this panel
    """
    # Collect all unique rule names mentioned in the panel
    rule_names_in_panel = set()

    for field in panel_fields:
        rules = field.get('rules', [])
        rule_names_in_panel.update(rules)

    # Filter schemas - get full schema for each rule name
    filtered_schemas = []
    missing_rules = []

    for rule_name in rule_names_in_panel:
        if rule_name in name_to_schema:
            filtered_schemas.append(name_to_schema[rule_name])
        else:
            missing_rules.append(rule_name)

    if missing_rules:
        print(f"  ⚠ Warning: {len(missing_rules)} rules not found in Rule-Schemas.json: {missing_rules[:5]}")

    return filtered_schemas


def call_mini_agent(panel_fields: List[Dict], rule_schemas: List[Dict],
                   panel_name: str, temp_dir: Path,
                   context_usage: bool = False,
                   verbose: bool = True,
                   model: str = "opus") -> Optional[List[Dict]]:
    """
    Call the Source Destination mini agent via claude -p

    Returns:
        List of fields with source/destination populated, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    input_file = temp_dir / f"{safe_panel_name}_input.json"
    output_file = temp_dir / f"{safe_panel_name}_source_dest.json"

    # Prepare input data
    input_data = {
        'fields_with_rules': panel_fields,
        'rule_schemas': rule_schemas
    }

    # Write input to temp file
    with open(input_file, 'w') as f:
        json.dump(input_data, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input
- FIELDS_WITH_RULES: {input_file} (contains fields_with_rules array and rule_schemas)
- LOG_FILE: {temp_dir / f"{re.sub(r'[^\\w\\-]', '_', panel_name)}_log.txt"}

## Output
Write JSON array to: {output_file}

Follow the agent prompt instructions to populate source and destination fields for each rule.
"""

    try:
        if verbose:
            print(f"\n{'='*70}")
            print(f"PROCESSING PANEL: {panel_name} ({len(panel_fields)} fields)")
            print('='*70)

        # Call claude -p with the mini agent
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--agent", "mini/02_source_destination_agent_v2",
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
            if verbose:
                print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"✗ Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Query context usage from the agent session (opt-in)
        if context_usage:
            print(f"\n--- Context Usage ({panel_name}) ---")
            usage = query_context_usage(panel_name, "Source Destination")
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
                if verbose:
                    print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
                return result
            except json.JSONDecodeError as e:
                print(f"✗ Failed to parse output JSON: {e}", file=sys.stderr)
                return None
        else:
            print(f"✗ Output file not found: {output_file}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("✗ Error: 'claude' command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"✗ Error calling mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Source Destination Dispatcher - Panel-by-panel processing"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to output from Rule Type Placement agent (JSON file with panels)"
    )
    parser.add_argument(
        "--rule-schemas",
        default="rules/Rule-Schemas.json",
        help="Path to Rule-Schemas.json (default: rules/Rule-Schemas.json)"
    )
    parser.add_argument(
        "--output",
        default="output/source_destination/all_panels_source_dest.json",
        help="Output file for all panels (default: output/source_destination/all_panels_source_dest.json)"
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

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load input from Rule Type Placement agent
    print(f"Loading input from: {args.input}")
    with open(args.input, 'r') as f:
        panels_data = json.load(f)

    print(f"Found {len(panels_data)} panels in input")

    # Step 2: Load rule schemas
    print(f"Loading rule schemas: {args.rule_schemas}")
    name_to_schema = load_rule_schemas(args.rule_schemas)
    print(f"Loaded {len(name_to_schema)} rule schemas")

    # Step 3: Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS")
    print("="*70)

    max_workers = args.max_workers

    # Prepare jobs
    jobs = []
    for panel_name, panel_fields in panels_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            continue

        relevant_schemas = get_relevant_rule_schemas(panel_fields, name_to_schema)
        total_rules_in_panel = sum(len(f.get('rules', [])) for f in panel_fields)
        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {total_rules_in_panel} total rules, {len(relevant_schemas)} unique rule schemas")
        jobs.append((panel_name, panel_fields, relevant_schemas))

    successful_panels = 0
    failed_panels = 0
    total_fields_processed = 0
    all_results = {}

    if max_workers <= 1:
        # Sequential processing
        for panel_name, panel_fields, relevant_schemas in jobs:
            result = call_mini_agent(
                panel_fields, relevant_schemas, panel_name, temp_dir,
                context_usage=args.context_usage, verbose=True, model=args.model
            )
            if result:
                successful_panels += 1
                total_fields_processed += len(result)
                all_results[panel_name] = result
            else:
                failed_panels += 1
                print(f"✗ Panel '{panel_name}' failed", file=sys.stderr)
    else:
        # Parallel processing
        print(f"\nProcessing {len(jobs)} panels in parallel (max_workers={max_workers})")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_panel = {}
            for panel_name, panel_fields, relevant_schemas in jobs:
                future = executor.submit(
                    call_mini_agent,
                    panel_fields, relevant_schemas, panel_name, temp_dir,
                    context_usage=args.context_usage, verbose=False, model=args.model
                )
                future_to_panel[future] = panel_name

            for future in as_completed(future_to_panel):
                panel_name = future_to_panel[future]
                try:
                    result = future.result()
                    if result:
                        successful_panels += 1
                        total_fields_processed += len(result)
                        all_results[panel_name] = result
                        print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
                    else:
                        failed_panels += 1
                        print(f"✗ Panel '{panel_name}' failed", file=sys.stderr)
                except Exception as e:
                    failed_panels += 1
                    print(f"✗ Panel '{panel_name}' error: {e}", file=sys.stderr)

    # Reorder results to match original panel sequence
    ordered_results = {}
    for panel_name in panels_data:
        if panel_name in all_results:
            ordered_results[panel_name] = all_results[panel_name]
    all_results = ordered_results

    # Step 4: Write all results to single output file
    if all_results:
        print(f"\nWriting all results to: {output_file}")
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"✓ Successfully wrote {len(all_results)} panels to output file")

    # Print final summary
    print("\n" + "="*70)
    print("DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(panels_data)}")
    print(f"Successful: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
