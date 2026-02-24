#!/usr/bin/env python3
"""
Inter-Panel Cross-Panel Rules Dispatcher

This script:
1. Reads output from Clear Child Fields agent (stage 7)
2. For each panel, detects cross-panel references in field logic
3. Calls Inter-Panel mini agent to create simple cross-panel rules (Copy To, visibility)
4. Collects delegation records for complex rules (derivation, EDV, clearing)
5. Phase 2: dispatches delegated rules to specialized agents (06, 03/04, 07)
6. Merges all results and outputs single JSON file
"""

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from inter_panel_utils import (
    detect_referenced_panels,
    get_referenced_panel_fields,
    merge_inter_panel_rules_immediate,
    apply_deferred_rules,
    write_referenced_panels_file,
    read_inter_panel_output,
    _merge_rules_into_panel,
)


PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


def query_context_usage(panel_name: str, agent_name: str) -> Optional[str]:
    """
    Query the last claude agent session for context/token usage.
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


def detect_cross_panel_refs_with_llm(panel_fields: List[Dict],
                                      panel_name: str,
                                      all_panel_names: List[str],
                                      temp_dir: Path) -> Optional[List[str]]:
    """
    Use a lightweight claude -p call to detect cross-panel references in field logic.
    More reliable than regex — catches variations like:
      - (from 'Basic Details' panel)
      - from Basic Details Panel
      - "if Process Type from Basic Details is..."
      - implicit references by field name context

    Args:
        panel_fields: Fields for the current panel
        panel_name: Current panel name
        all_panel_names: All panel names in the dataset
        temp_dir: Directory for temp files

    Returns:
        List of referenced panel names, or None on failure.
        Empty list means no cross-panel references detected.
    """
    # Collect field names + logic text (compact format to minimize tokens)
    field_summaries = []
    has_any_logic = False
    for field in panel_fields:
        logic = field.get('logic', '')
        if logic:
            has_any_logic = True
            field_summaries.append(f"- {field.get('field_name', '?')}: {logic}")

    if not has_any_logic:
        return []

    other_panels = [p for p in all_panel_names if p.lower() != panel_name.lower()]
    if not other_panels:
        return []

    fields_text = '\n'.join(field_summaries)
    panels_text = ', '.join(other_panels)

    prompt = f"""You are analyzing field logic text for cross-panel references.

Current panel: "{panel_name}"
Other panels in this form: [{panels_text}]

Field logic text:
{fields_text}

TASK: Identify which OTHER panels are referenced in ANY field's logic above.
Cross-panel references include:
- Explicit: "(from Basic Details panel)", "(from 'PAN and GST Details')", "from Basic Details Panel"
- Conditional: "if Process Type from Basic Details is...", "visible when field in X Panel is..."
- Copy/derive: "copy from X panel", "derived from field in X panel"
- Any mention of another panel's name in the context of reading/using a value from it

Respond with ONLY a JSON array of referenced panel names. Use the exact panel names from the list above.
If NO cross-panel references exist, respond with an empty array: []

Examples:
["Basic Details", "PAN and GST Details"]
[]
["Basic Details"]"""

    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)
    detect_output_file = temp_dir / f"{safe_panel_name}_detect_refs.json"

    try:
        process = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", ""],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT
        )

        if process.returncode != 0:
            print(f"  LLM detection failed (exit {process.returncode}), falling back to regex", file=sys.stderr)
            return None

        output = process.stdout.strip()

        # Extract JSON array from response (may have markdown fencing)
        json_match = re.search(r'\[.*?\]', output, re.DOTALL)
        if not json_match:
            print(f"  LLM detection returned no JSON array, falling back to regex", file=sys.stderr)
            return None

        referenced = json.loads(json_match.group())

        if not isinstance(referenced, list):
            return None

        # Normalize: only keep panels that actually exist
        valid_refs = []
        for ref in referenced:
            if not isinstance(ref, str):
                continue
            for actual_name in all_panel_names:
                if ref.lower() == actual_name.lower() and actual_name.lower() != panel_name.lower():
                    valid_refs.append(actual_name)
                    break

        # Save detection result for debugging
        with open(detect_output_file, 'w') as f:
            json.dump({"panel": panel_name, "llm_raw": referenced, "validated": valid_refs}, f, indent=2)

        return valid_refs

    except json.JSONDecodeError as e:
        print(f"  LLM detection JSON parse error: {e}, falling back to regex", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  LLM detection error: {e}, falling back to regex", file=sys.stderr)
        return None


def call_inter_panel_mini_agent(panel_fields: List[Dict],
                                 panel_name: str,
                                 referenced_data: Dict[str, List[Dict]],
                                 temp_dir: Path) -> Tuple[Optional[List[Dict]],
                                                           Optional[Dict[str, List[Dict]]],
                                                           Optional[List[Dict]]]:
    """
    Call the Inter-Panel mini agent via claude -p

    Args:
        panel_fields: Fields from Clear Child Fields output
        panel_name: Name of the current panel
        referenced_data: Fields from referenced panels
        temp_dir: Directory for temp files

    Returns:
        Tuple of (result_fields, inter_panel_rules, delegation_records)
        Any can be None on failure
    """
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    referenced_file = temp_dir / f"{safe_panel_name}_referenced_panels.json"
    output_file = temp_dir / f"{safe_panel_name}_inter_panel_output.json"
    inter_panel_output_file = temp_dir / f"{safe_panel_name}_inter_panel_rules.json"
    delegation_output_file = temp_dir / f"{safe_panel_name}_delegations.json"
    log_file = temp_dir / f"{safe_panel_name}_inter_panel_log.txt"

    # Write input files
    with open(fields_input_file, 'w') as f:
        json.dump(panel_fields, f, indent=2)

    write_referenced_panels_file(referenced_data, referenced_file)

    referenced_panel_list = ', '.join(sorted(referenced_data.keys()))
    referenced_field_counts = ', '.join(
        f"{p}: {len(fs)} fields" for p, fs in sorted(referenced_data.items())
    )

    prompt = f"""Process fields for panel "{panel_name}" to extract cross-panel rules.

## Input Data
1. Current panel fields: {fields_input_file}
2. Referenced panel fields: {referenced_file}
3. Log file: {log_file}

## Instructions
Follow the step-by-step approach defined in the agent prompt (09_inter_panel_agent).
- FIELDS_JSON = {fields_input_file}
- REFERENCED_PANELS_JSON = {referenced_file}
- CURRENT_PANEL = {panel_name}
- OUTPUT_FILE = {output_file}
- INTER_PANEL_OUTPUT_FILE = {inter_panel_output_file}
- DELEGATION_OUTPUT_FILE = {delegation_output_file}
- LOG_FILE = {log_file}

## Context
Referenced panels detected: [{referenced_panel_list}]
Referenced panel field counts: {referenced_field_counts}

## CRITICAL
- ONLY handle cross-panel logic (references to fields/values from OTHER panels)
- PASS THROUGH all existing rules unchanged
- Write THREE output files:
  1. {output_file} — updated current panel fields
  2. {inter_panel_output_file} — rules for OTHER panels (only if needed)
  3. {delegation_output_file} — complex delegations (only if needed)
- If no cross-panel rules needed, still write {output_file} with unchanged fields
- If no inter-panel rules, write empty dict {{}} to {inter_panel_output_file}
- If no delegations, write empty list [] to {delegation_output_file}

## Output
Write JSON to the three output files listed above.
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name}")
        print(f"  Fields: {len(panel_fields)}")
        print(f"  Referenced panels: {referenced_panel_list}")
        print(f"  Referenced fields: {referenced_field_counts}")
        print('='*70)

        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--agent", "mini/09_inter_panel_agent",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        output_lines = []
        for line in process.stdout:
            print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"  Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None, None, None

        # Query context usage
        print(f"\n--- Context Usage ({panel_name}) ---")
        usage = query_context_usage(panel_name, "Inter-Panel")
        if usage:
            print(usage)
        else:
            print("(Could not retrieve context usage)")
        print("---")

        # Read main output
        result = None
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
                print(f"  Main output: {len(result)} fields")
            except json.JSONDecodeError as e:
                print(f"  Failed to parse main output JSON: {e}", file=sys.stderr)

        # Read inter-panel rules
        inter_rules = read_inter_panel_output(inter_panel_output_file)
        if inter_rules:
            total = sum(
                sum(len(e.get('rules_to_add', [])) for e in entries)
                for entries in inter_rules.values()
            )
            print(f"  Inter-panel rules: {total} rules for {len(inter_rules)} panels")
        else:
            inter_rules = {}

        # Read delegation records
        delegations = None
        if delegation_output_file.exists():
            try:
                with open(delegation_output_file, 'r') as f:
                    delegations = json.load(f)
                if isinstance(delegations, list) and delegations:
                    print(f"  Delegations: {len(delegations)} complex references")
                else:
                    delegations = []
            except json.JSONDecodeError:
                delegations = []
        else:
            delegations = []

        return result, inter_rules, delegations

    except FileNotFoundError:
        print("  Error: 'claude' command not found", file=sys.stderr)
        return None, None, None
    except Exception as e:
        print(f"  Error calling Inter-Panel mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None, None, None


def call_specialized_agent(delegation: Dict,
                            all_results: Dict[str, List[Dict]],
                            input_data: Dict[str, List[Dict]],
                            temp_dir: Path) -> Optional[Tuple[str, List[Dict]]]:
    """
    Call a specialized agent (derivation, EDV, clearing) for a delegated cross-panel reference.

    Args:
        delegation: Delegation record from Phase 1
        all_results: Current pipeline results (panel -> fields)
        input_data: Original input data
        temp_dir: Directory for temp files

    Returns:
        Tuple of (target_panel, inter_panel_rules_list) or None on failure
    """
    delegation_type = delegation.get('type', '')
    source_panel = delegation.get('source_panel', '')
    target_panel = delegation.get('target_panel', '')
    source_field = delegation.get('source_field', '')
    target_field = delegation.get('target_field', '')
    logic = delegation.get('logic', '')
    description = delegation.get('description', '')

    if not delegation_type or not target_panel:
        print(f"  Skipping invalid delegation: {delegation}", file=sys.stderr)
        return None

    # Build minimal field subset for the specialized agent
    target_fields = all_results.get(target_panel, input_data.get(target_panel, []))
    source_fields = all_results.get(source_panel, input_data.get(source_panel, []))

    # Find the specific target and source field entries
    target_field_entry = None
    source_field_entry = None

    for f in target_fields:
        if f.get('variableName') == target_field:
            target_field_entry = f
            break

    for f in source_fields:
        if f.get('variableName') == source_field:
            source_field_entry = f
            break

    if not target_field_entry:
        print(f"  Delegation target field '{target_field}' not found in panel '{target_panel}'", file=sys.stderr)
        return None

    safe_name = re.sub(r'[^\w\-]', '_', f"{source_panel}_{target_panel}_{delegation_type}")
    delegation_input = temp_dir / f"delegation_{safe_name}_input.json"
    delegation_output = temp_dir / f"delegation_{safe_name}_output.json"
    delegation_log = temp_dir / f"delegation_{safe_name}_log.txt"

    # Build targeted field list (just source + target)
    targeted_fields = []
    if source_field_entry:
        targeted_fields.append(source_field_entry)
    targeted_fields.append(target_field_entry)

    with open(delegation_input, 'w') as f_out:
        json.dump(targeted_fields, f_out, indent=2)

    # Select agent based on delegation type
    if delegation_type == 'derivation':
        agent_file = "mini/06_derivation_agent"
        agent_label = "Derivation"
        prompt = f"""Process a cross-panel derivation rule.

## Context
Source panel: {source_panel}
Target panel: {target_panel}
Source field: {source_field}
Target field: {target_field}
Logic: {logic}
Description: {description}

## Input
Fields: {delegation_input}
Log file: {delegation_log}

## Instructions
Follow the derivation agent approach (06_derivation_agent).
- FIELDS_JSON = {delegation_input}
- LOG_FILE = {delegation_log}

Create an Expression (Client) rule with ctfd/asdff expressions for this cross-panel derivation.
The source field is from another panel — use its variableName as-is.

## Output
Write JSON array to: {delegation_output}
"""
    elif delegation_type == 'edv':
        agent_file = "mini/03_edv_rule_agent_v2"
        agent_label = "EDV"
        prompt = f"""Process a cross-panel EDV rule.

## Context
Source panel: {source_panel}
Target panel: {target_panel}
Source field: {source_field}
Target field: {target_field}
Logic: {logic}
Description: {description}

## Input
Fields: {delegation_input}
Log file: {delegation_log}

## Instructions
Follow the EDV agent approach (03_edv_rule_agent_v2).
- FIELDS_JSON = {delegation_input}
- LOG_FILE = {delegation_log}

## Output
Write JSON array to: {delegation_output}
"""
    elif delegation_type == 'clearing':
        agent_file = "mini/07_clear_child_fields_agent"
        agent_label = "Clear Child"
        prompt = f"""Process a cross-panel clearing rule.

## Context
Source panel: {source_panel}
Target panel: {target_panel}
Source field: {source_field}
Target field: {target_field}
Logic: {logic}
Description: {description}

## Input
Fields: {delegation_input}
Log file: {delegation_log}

## Instructions
Follow the clear child fields agent approach (07_clear_child_fields_agent).
- FIELDS_JSON = {delegation_input}
- LOG_FILE = {delegation_log}

## Output
Write JSON array to: {delegation_output}
"""
    else:
        print(f"  Unknown delegation type: {delegation_type}", file=sys.stderr)
        return None

    try:
        print(f"\n  --- Delegation: {agent_label} ({source_panel} -> {target_panel}) ---")
        print(f"  Source: {source_field}, Target: {target_field}")

        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--agent", agent_file,
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        for line in process.stdout:
            print(line, end='', flush=True)

        process.wait()

        if process.returncode != 0:
            print(f"  Delegation agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        if delegation_output.exists():
            try:
                with open(delegation_output, 'r') as f_in:
                    result_fields = json.load(f_in)

                # Extract new rules from the result (rules not in original)
                new_rules = []
                for rf in result_fields:
                    if rf.get('variableName') == target_field:
                        original_rule_count = len(target_field_entry.get('rules', []))
                        all_rules = rf.get('rules', [])
                        if len(all_rules) > original_rule_count:
                            new_rules = all_rules[original_rule_count:]

                if new_rules:
                    # Mark as cross-panel
                    for rule in new_rules:
                        rule['_inter_panel_source'] = 'cross-panel'

                    inter_panel_entry = {
                        'target_field_variableName': target_field,
                        'rules_to_add': new_rules
                    }
                    print(f"  Delegation produced {len(new_rules)} rules for {target_field}")
                    return target_panel, [inter_panel_entry]
                else:
                    print(f"  Delegation produced no new rules")
                    return None

            except json.JSONDecodeError as e:
                print(f"  Failed to parse delegation output: {e}", file=sys.stderr)
                return None
        else:
            print(f"  Delegation output file not found", file=sys.stderr)
            return None

    except Exception as e:
        print(f"  Error in delegation: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Inter-Panel Cross-Panel Rules Dispatcher - Handle cross-panel field references"
    )
    parser.add_argument(
        "--clear-child-output",
        required=True,
        help="Path to Clear Child Fields agent output JSON (stage 7)"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "--output",
        default="output/inter_panel/all_panels_inter_panel.json",
        help="Output file (default: output/inter_panel/all_panels_inter_panel.json)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.clear_child_output).exists():
        print(f"Error: Clear Child Fields output not found: {args.clear_child_output}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.bud).exists():
        print(f"Error: BUD document not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Load input data
    print(f"Loading Clear Child Fields output: {args.clear_child_output}")
    with open(args.clear_child_output, 'r') as f:
        input_data = json.load(f)

    all_panel_names = list(input_data.keys())
    print(f"Found {len(input_data)} panels: {', '.join(all_panel_names)}")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1: Process each panel with inter-panel agent
    # ══════════════════════════════════════════════════════════════════════
    print("\n" + "="*70)
    print("PHASE 1: PROCESSING PANELS WITH INTER-PANEL AGENT")
    print("="*70)

    successful_panels = 0
    failed_panels = 0
    skipped_panels = 0
    total_fields_processed = 0
    all_results = {}
    all_delegations = []
    deferred_rules: Dict[str, List[Dict]] = {}

    for panel_name, panel_fields in input_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            all_results[panel_name] = panel_fields
            continue

        # Detect cross-panel references using LLM pre-scan (with regex fallback)
        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields — scanning for cross-panel references...")

        llm_refs = detect_cross_panel_refs_with_llm(panel_fields, panel_name, all_panel_names, temp_dir)

        if llm_refs is not None:
            # LLM detection succeeded
            referenced_panels = set(llm_refs)
            detection_method = "LLM"
        else:
            # Fallback to regex detection
            referenced_panels = detect_referenced_panels(panel_fields, all_panel_names, panel_name)
            detection_method = "regex (fallback)"

        if not referenced_panels:
            print(f"  No cross-panel references detected ({detection_method}), passing through")
            skipped_panels += 1
            all_results[panel_name] = panel_fields
            # Apply any deferred rules from earlier panels
            apply_deferred_rules(deferred_rules, panel_name, all_results[panel_name])
            total_fields_processed += len(panel_fields)
            continue

        print(f"  Cross-panel references detected ({detection_method}): "
              f"{', '.join(sorted(referenced_panels))}")

        # Get referenced panel data
        referenced_data = get_referenced_panel_fields(referenced_panels, input_data, all_results)

        # Call inter-panel mini agent
        result, inter_rules, delegations = call_inter_panel_mini_agent(
            panel_fields, panel_name, referenced_data, temp_dir
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

        # Apply deferred rules from earlier panels
        apply_deferred_rules(deferred_rules, panel_name, all_results[panel_name])

        # Merge inter-panel rules (immediate or deferred)
        if inter_rules:
            merge_inter_panel_rules_immediate(inter_rules, all_results, deferred_rules)

        # Collect delegations
        if delegations:
            all_delegations.extend(delegations)

    # Apply any remaining deferred rules
    for panel_name in list(deferred_rules.keys()):
        if panel_name in all_results:
            apply_deferred_rules(deferred_rules, panel_name, all_results[panel_name])

    if deferred_rules:
        print(f"\nWarning: {len(deferred_rules)} panels have unresolved deferred rules: "
              f"{', '.join(deferred_rules.keys())}", file=sys.stderr)

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2: Handle complex delegations
    # ══════════════════════════════════════════════════════════════════════
    delegation_count = len(all_delegations)
    delegation_success = 0
    delegation_fail = 0

    if all_delegations:
        print("\n" + "="*70)
        print(f"PHASE 2: PROCESSING {delegation_count} COMPLEX DELEGATIONS")
        print("="*70)

        for i, delegation in enumerate(all_delegations, 1):
            print(f"\n  Delegation {i}/{delegation_count}: "
                  f"{delegation.get('type', '?')} — "
                  f"{delegation.get('source_panel', '?')} -> {delegation.get('target_panel', '?')}")

            result = call_specialized_agent(delegation, all_results, input_data, temp_dir)

            if result:
                target_panel, inter_panel_entries = result
                # Merge into all_results
                if target_panel in all_results:
                    count = _merge_rules_into_panel(
                        all_results[target_panel], inter_panel_entries, target_panel
                    )
                    if count > 0:
                        print(f"  Merged {count} delegated rules into panel '{target_panel}'")
                    delegation_success += 1
                else:
                    print(f"  Target panel '{target_panel}' not found in results", file=sys.stderr)
                    delegation_fail += 1
            else:
                delegation_fail += 1
    else:
        print("\nNo complex delegations to process (Phase 2 skipped)")

    # ══════════════════════════════════════════════════════════════════════
    # Write output
    # ══════════════════════════════════════════════════════════════════════
    print(f"\nWriting all results to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    # Verify field counts
    input_field_count = sum(len(fields) for fields in input_data.values())
    output_field_count = sum(len(fields) for fields in all_results.values())

    # Count new cross-panel rules
    cross_panel_rule_count = 0
    for panel_fields in all_results.values():
        for field in panel_fields:
            for rule in field.get('rules', []):
                if isinstance(rule, dict) and rule.get('_inter_panel_source') == 'cross-panel':
                    cross_panel_rule_count += 1

    # Summary
    print("\n" + "="*70)
    print("INTER-PANEL DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(input_data)}")
    print(f"Phase 1 — Panel Processing:")
    print(f"  Successfully Processed: {successful_panels}")
    print(f"  Failed: {failed_panels}")
    print(f"  Skipped (no cross-panel refs): {skipped_panels}")
    if delegation_count > 0:
        print(f"Phase 2 — Delegations:")
        print(f"  Total Delegations: {delegation_count}")
        print(f"  Successful: {delegation_success}")
        print(f"  Failed: {delegation_fail}")
    print(f"Field Counts:")
    print(f"  Input: {input_field_count}")
    print(f"  Output: {output_field_count}")
    if input_field_count != output_field_count:
        print(f"  WARNING: Field count mismatch!")
    else:
        print(f"  OK: Field counts match")
    print(f"Cross-Panel Rules Added: {cross_panel_rule_count}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
