#!/usr/bin/env python3
"""
Session-Based Rules Dispatcher

This script:
1. Parses the BUD document using DocumentParser to extract tables from:
   - Section 4.5.1 (Initiator Behaviour) → FIRST_PARTY session
   - Section 4.5.2 (Vendor Behaviour) → SECOND_PARTY session
2. Builds a "RuleCheck" field with deterministic visible/invisible rules
   based on whether fields appear in each BUD table
3. For each panel, replaces field logic with BUD table logic and calls
   the Session Based mini agent for conditional/static rules
4. Outputs single JSON file containing all panels with session-based rules added
"""

import argparse
import copy
import json
import subprocess
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from stream_utils import stream_and_print

# Add project root so we can import doc_parser
PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, PROJECT_ROOT)
from doc_parser import DocumentParser
from context_optimization import (
    strip_all_rules, restore_all_rules, log_strip_savings, print_context_report
)


RULE_CHECK_VARIABLE = "__rulecheck__"


def _normalize_field_name(name: str) -> str:
    """Normalize field name for case-insensitive matching with common variations."""
    return name.lower().replace("organisation", "organization").strip()


def extract_session_table_data(bud_path: str) -> Dict[str, Dict[str, Dict]]:
    """
    Parse the BUD document using DocumentParser and extract full field data
    from section 4.5.2 (Vendor Behaviour).

    Returns:
        Dict mapping panel_name -> {normalized_field_name -> {logic, mandatory, field_type}}
    """
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    vendor_data: Dict[str, Dict[str, Dict]] = {}

    for table in parsed.raw_tables:
        context_lower = table.context.lower()

        # Only process 4.5.2 Vendor Behaviour tables
        if not (table.table_type == "spoc_fields" and
                ("4.5.2" in table.context or "vendor" in context_lower)):
            continue

        # Extract field data grouped by panel
        current_panel = None
        for row in table.rows:
            if not row or not row[0].strip():
                continue

            field_name = row[0].strip()
            field_type = row[1].strip().upper() if len(row) > 1 else ""
            mandatory = row[2].strip() if len(row) > 2 else ""
            logic = row[3].strip() if len(row) > 3 else ""

            if field_type == "PANEL":
                current_panel = field_name
                if current_panel not in vendor_data:
                    vendor_data[current_panel] = {}
            elif current_panel:
                normalized = _normalize_field_name(field_name)
                vendor_data[current_panel][normalized] = {
                    "logic": logic,
                    "mandatory": mandatory,
                    "field_type": field_type,
                    "original_name": field_name
                }

    return vendor_data


def extract_session_field_names(bud_path: str) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """
    Parse the BUD document and extract field names grouped by panel
    from sections 4.5.1 (Initiator Behaviour) and 4.5.2 (Vendor Behaviour).
    Used for building consolidated RuleCheck rules.

    Returns:
        Tuple of (initiator_fields_by_panel, vendor_fields_by_panel)
        Each is a dict: panel_name -> set of normalized field names
    """
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    initiator_fields: Dict[str, Set[str]] = {}
    vendor_fields: Dict[str, Set[str]] = {}

    for table in parsed.raw_tables:
        context_lower = table.context.lower()

        if table.table_type == "initiator_fields" and ("4.5.1" in table.context or "initiator" in context_lower):
            target = initiator_fields
        elif table.table_type == "spoc_fields" and ("4.5.2" in table.context or "vendor" in context_lower):
            target = vendor_fields
        else:
            continue

        current_panel = None
        for row in table.rows:
            if not row or not row[0].strip():
                continue

            field_name = row[0].strip()
            field_type = row[1].strip().upper() if len(row) > 1 else ""

            if field_type == "PANEL":
                current_panel = field_name
                if current_panel not in target:
                    target[current_panel] = set()
            elif current_panel:
                target[current_panel].add(_normalize_field_name(field_name))

    return initiator_fields, vendor_fields


def _panel_variable_name(panel_name: str) -> str:
    """Convert panel name to variable name format: 'Basic Details' -> '__basic_details__'"""
    return f"__{panel_name.lower().replace(' ', '_')}__"


def query_context_usage(panel_name: str, agent_name: str) -> Optional[str]:
    """Query the last claude agent session for context/token usage."""
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


def prepare_panel_fields_with_bud_logic(panel_fields: List[Dict],
                                         vendor_panel_data: Dict[str, Dict]) -> List[Dict]:
    """
    Replace each field's logic with the logic from the BUD 4.5.2 table.

    - Fields IN the BUD table → logic replaced with BUD table's Logic column
    - Fields NOT in the BUD table → logic set to "Invisible"
    - PANEL-type fields → logic left unchanged

    Args:
        panel_fields: Original fields from clear_child_fields output
        vendor_panel_data: BUD 4.5.2 data for this panel {normalized_name -> {logic, ...}}

    Returns:
        Modified copy of panel_fields with logic replaced
    """
    modified_fields = copy.deepcopy(panel_fields)

    for field in modified_fields:
        if field.get("type", "") == "PANEL":
            continue

        normalized = _normalize_field_name(field.get("field_name", ""))
        bud_entry = vendor_panel_data.get(normalized)

        if bud_entry:
            # Field is in BUD table → use BUD logic
            field["logic"] = bud_entry["logic"]
        else:
            # Field NOT in BUD table → invisible for this session
            field["logic"] = "Invisible"

    return modified_fields


def call_session_based_mini_agent(panel_fields: List[Dict],
                                   panel_name: str,
                                   session_params: str,
                                   temp_dir: Path) -> Optional[List[Dict]]:
    """
    Call the Session Based mini agent via claude -p

    Args:
        panel_fields: Fields with logic replaced by BUD table logic
        panel_name: Name of the panel
        session_params: Session name (e.g., "SECOND_PARTY")
        temp_dir: Directory for temp files

    Returns:
        List of fields with session-based rules added, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    output_file = temp_dir / f"{safe_panel_name}_session_output.json"
    log_file = temp_dir / f"{safe_panel_name}_session_log.txt"

    # ── Context optimization: strip all rules before sending to agent ──
    stripped_fields, stored_rules = strip_all_rules(panel_fields)
    log_strip_savings(panel_fields, stripped_fields, panel_name)

    # Write stripped fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(stripped_fields, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input Data
1. Fields with rules: {fields_input_file}
2. Log file: {log_file}

## Instructions
Follow the step-by-step approach defined in the agent prompt (08_session_based_agent).
- FIELDS_JSON = {fields_input_file}
- SESSION_PARAMS = {session_params}
- LOG_FILE = {log_file}

## CRITICAL: Only Handle Session-Based Rules
Read each field's logic text and determine what session-based rules to place.
Existing rules have been stripped for context optimization — they will be restored automatically.
Only add NEW session-based rules based on each field's logic text.

All rules must use params = "{session_params}".

## Rule Placement (mirrors condition agent pattern):
- **Conditional rules** (logic references another field): place ON the controller field
  - source_fields = [controller field's variableName]
  - destination_fields = [affected field(s) variableName]
- **Static rules** (logic says "Disable", "Invisible", "Non-Editable", etc.):
  - place ON the affected field itself
  - source_fields = []
  - destination_fields = [field's own variableName]
- **Empty logic** = NO session-based rules needed (deterministic visibility handled by RuleCheck separately)
- Consolidate: group fields affected by the same controller + condition into ONE rule
- Opposite rules: use NOT_IN with the original value (never IN with opposite value)
- Skip PANEL-type fields
- If a session-based rule (same rule_name + params) already exists, skip it

## Output
Write a JSON array to: {output_file}
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name} (session: {session_params})")
        print(f"  Fields: {len(panel_fields)}")
        print('='*70)

        # Call claude -p with the Session Based mini agent
        safe_name = re.sub(r'[^\w\-]', '_', panel_name)
        stream_log = temp_dir / f"{safe_name}_stream.log"
        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--agent", "mini/08_session_based_agent",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        # Stream and print real-time output
        output_lines = stream_and_print(process, verbose=True, log_file_path=stream_log)

        process.wait()

        if process.returncode != 0:
            print(f"  Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Query context usage from the agent session
        print(f"\n--- Context Usage ({panel_name}) ---")
        usage = query_context_usage(panel_name, "Session Based")
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

                # Restore stripped rules (prepend originals before agent-added session rules)
                result = restore_all_rules(result, stored_rules)

                # Context report
                agent_prompt_file = Path(PROJECT_ROOT) / ".claude" / "agents" / "mini" / "08_session_based_agent.md"
                input_json_chars = fields_input_file.stat().st_size if fields_input_file.exists() else 0
                print_context_report(
                    label=panel_name,
                    agent_files=[agent_prompt_file],
                    prompt_chars=len(prompt),
                    input_json_chars=input_json_chars,
                    output_file=output_file,
                )

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
        print(f"  Error calling Session Based mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def build_rulecheck_session_rules(all_panels: Dict[str, List[Dict]],
                                   initiator_fields: Dict[str, Set[str]],
                                   vendor_fields: Dict[str, Set[str]]) -> List[Dict]:
    """
    Build consolidated session-based rules for the RuleCheck field.
    Classifies all fields into visible/invisible for FIRST_PARTY and SECOND_PARTY.

    Returns:
        List of rule dicts to place on the RuleCheck field
    """
    first_visible: List[str] = []
    first_invisible: List[str] = []
    second_visible: List[str] = []
    second_invisible: List[str] = []

    for panel_name, panel_fields in all_panels.items():
        initiator_set = initiator_fields.get(panel_name, set())
        vendor_set = vendor_fields.get(panel_name, set())

        panel_var = _panel_variable_name(panel_name)

        if panel_name in initiator_fields:
            first_visible.append(panel_var)
        else:
            first_invisible.append(panel_var)

        if panel_name in vendor_fields:
            second_visible.append(panel_var)
        else:
            second_invisible.append(panel_var)

        for field in panel_fields:
            if field.get("type", "") == "PANEL":
                continue
            variable_name = field.get("variableName", "")
            if not variable_name:
                continue
            normalized = _normalize_field_name(field.get("field_name", ""))

            if normalized in initiator_set:
                first_visible.append(variable_name)
            else:
                first_invisible.append(variable_name)

            if normalized in vendor_set:
                second_visible.append(variable_name)
            else:
                second_invisible.append(variable_name)

    rules = []
    rule_id = 1

    for dest_list, rule_name, params, reasoning in [
        (first_visible, "Make Visible - Session Based (Client)", "FIRST_PARTY",
         "fields from 4.5.1 Initiator Behaviour visible to FIRST_PARTY"),
        (first_invisible, "Make Invisible - Session Based (Client)", "FIRST_PARTY",
         "fields NOT in 4.5.1 Initiator Behaviour invisible to FIRST_PARTY"),
        (second_visible, "Make Visible - Session Based (Client)", "SECOND_PARTY",
         "fields from 4.5.2 Vendor Behaviour visible to SECOND_PARTY"),
        (second_invisible, "Make Invisible - Session Based (Client)", "SECOND_PARTY",
         "fields NOT in 4.5.2 Vendor Behaviour invisible to SECOND_PARTY"),
    ]:
        if dest_list:
            cond_val = "Visible" if "Visible" in rule_name else "Invisible"
            rules.append({
                "id": rule_id,
                "rule_name": rule_name,
                "source_fields": [RULE_CHECK_VARIABLE],
                "destination_fields": dest_list,
                "params": params,
                "conditionalValues": [cond_val],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT",
                "_reasoning": f"Makes {len(dest_list)} {reasoning} session"
            })
            rule_id += 1

    return rules


def main():
    parser = argparse.ArgumentParser(
        description="Session-Based Rules Dispatcher - Add session-based rules based on BUD sections 4.5.1 and 4.5.2"
    )
    parser.add_argument(
        "--clear-child-output",
        required=True,
        help="Path to Clear Child Fields agent output JSON (stage 7)"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to the BUD document (.docx) to extract 4.5.1/4.5.2 fields"
    )
    parser.add_argument(
        "--output",
        default="output/session_based/all_panels_session_based.json",
        help="Output file (default: output/session_based/all_panels_session_based.json)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel panels to process (default: 4, use 1 for sequential)"
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

    # ── Step 1: Parse BUD ─────────────────────────────────────────────────────
    print(f"Parsing BUD document: {args.bud}")
    vendor_table_data = extract_session_table_data(args.bud)

    print(f"\n4.5.2 Vendor Behaviour (SECOND_PARTY) — full table data:")
    for panel, fields in vendor_table_data.items():
        print(f"  {panel}: {len(fields)} fields")

    # Also extract field name sets for RuleCheck consolidation
    initiator_fields, vendor_fields = extract_session_field_names(args.bud)

    initiator_total = sum(len(f) for f in initiator_fields.values())
    vendor_total = sum(len(f) for f in vendor_fields.values())
    print(f"\nField name sets: {initiator_total} initiator fields, {vendor_total} vendor fields")

    # ── Step 2: Load Clear Child Fields agent output ──────────────────────────
    print(f"\nLoading Clear Child Fields output: {args.clear_child_output}")
    with open(args.clear_child_output, 'r') as f:
        input_data = json.load(f)

    print(f"Found {len(input_data)} panels in input")

    # ── Step 3: Build RuleCheck field FIRST (deterministic) ───────────────────
    print("\n" + "=" * 70)
    print("BUILDING RULECHECK FIELD WITH DETERMINISTIC SESSION RULES")
    print("=" * 70)

    session_rules = build_rulecheck_session_rules(input_data, initiator_fields, vendor_fields)

    for rule in session_rules:
        print(f"  {rule['rule_name']} ({rule['params']}): {len(rule['destination_fields'])} destination fields")

    rule_check_field = {
        "field_name": "RuleCheck",
        "type": "TEXT",
        "mandatory": False,
        "logic": "",
        "rules": session_rules,
        "variableName": RULE_CHECK_VARIABLE
    }

    # Insert RuleCheck into the first panel
    panel_names = list(input_data.keys())
    rulecheck_panel = None

    if panel_names:
        input_data[panel_names[0]] = [rule_check_field] + input_data[panel_names[0]]
        rulecheck_panel = panel_names[0]
        print(f"\n  Inserted 'RuleCheck' field at start of panel '{panel_names[0]}' "
              f"with {len(session_rules)} session rules")

    # ── Step 4: Process each panel with Session Based agent ───────────────────
    print("\n" + "=" * 70)
    print("PROCESSING PANELS WITH SESSION BASED AGENT")
    print("=" * 70)

    successful_panels = 0
    failed_panels = 0
    skipped_panels = 0
    total_fields_processed = 0
    all_results = {}

    # Build jobs: prepare modified fields for each panel
    jobs = []
    for panel_name, panel_fields in input_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            all_results[panel_name] = panel_fields
            continue

        # Get BUD 4.5.2 data for this panel
        vendor_panel_data = vendor_table_data.get(panel_name, {})

        # Replace field logic with BUD table logic
        modified_fields = prepare_panel_fields_with_bud_logic(panel_fields, vendor_panel_data)

        fields_in_bud = sum(1 for f in modified_fields
                           if f.get("type") != "PANEL" and f.get("logic") != "Invisible"
                           and f.get("variableName") != RULE_CHECK_VARIABLE)
        fields_not_in_bud = sum(1 for f in modified_fields
                               if f.get("type") != "PANEL" and f.get("logic") == "Invisible"
                               and f.get("variableName") != RULE_CHECK_VARIABLE)

        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields "
              f"({fields_in_bud} in BUD table, {fields_not_in_bud} not in BUD table)")

        jobs.append((panel_name, modified_fields, panel_fields))

    max_workers = args.max_workers

    if max_workers <= 1:
        # Sequential processing
        for panel_name, modified_fields, original_fields in jobs:
            result = call_session_based_mini_agent(
                modified_fields, panel_name, "SECOND_PARTY", temp_dir
            )
            if result:
                successful_panels += 1
                total_fields_processed += len(result)
                all_results[panel_name] = result
            else:
                failed_panels += 1
                all_results[panel_name] = original_fields
                total_fields_processed += len(original_fields)
                print(f"  Panel '{panel_name}' failed - using original data", file=sys.stderr)
    else:
        # Parallel processing
        print(f"\nProcessing {len(jobs)} panels in parallel (max_workers={max_workers})")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    call_session_based_mini_agent,
                    modified_fields, panel_name, "SECOND_PARTY", temp_dir
                ): (panel_name, original_fields)
                for panel_name, modified_fields, original_fields in jobs
            }
            for future in as_completed(future_map):
                panel_name, original_fields = future_map[future]
                try:
                    result = future.result()
                    if result:
                        successful_panels += 1
                        total_fields_processed += len(result)
                        all_results[panel_name] = result
                        print(f"  '{panel_name}' done — {len(result)} fields")
                    else:
                        failed_panels += 1
                        all_results[panel_name] = original_fields
                        total_fields_processed += len(original_fields)
                        print(f"  '{panel_name}' failed — using original", file=sys.stderr)
                except Exception as e:
                    failed_panels += 1
                    all_results[panel_name] = original_fields
                    total_fields_processed += len(original_fields)
                    print(f"  '{panel_name}' error: {e}", file=sys.stderr)

    # Preserve original panel order
    for panel_name in input_data:
        if panel_name not in all_results:
            all_results[panel_name] = input_data[panel_name]
    ordered = {p: all_results[p] for p in input_data}

    # ── Step 5: Write output ──────────────────────────────────────────────────
    print(f"\nWriting output to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(ordered, f, indent=2)

    # Summary
    total_dest = sum(len(r["destination_fields"]) for r in session_rules)
    print("\n" + "=" * 70)
    print("SESSION-BASED DISPATCHER COMPLETE")
    print("=" * 70)
    print(f"Total Panels: {len(input_data)}")
    print(f"Successfully Processed: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Skipped (empty): {skipped_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"RuleCheck field placed in: {rulecheck_panel or 'N/A'}")
    print(f"Session rules on RuleCheck: {len(session_rules)}")
    for rule in session_rules:
        param = rule["params"]
        action = "VISIBLE" if "Visible" in rule["rule_name"] else "INVISIBLE"
        print(f"  {action} ({param}): {len(rule['destination_fields'])} fields")
    print(f"Total destination mappings: {total_dest}")
    print(f"Output File: {output_file}")
    print("=" * 70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
