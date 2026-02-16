#!/usr/bin/env python3
"""
Session-Based Rules Dispatcher

This script:
1. Parses the BUD document to extract field names from:
   - Section 4.5.1 (Initiator Behaviour) → FIRST_PARTY fields
   - Section 4.5.2 (Vendor Behaviour) → SECOND_PARTY fields
2. Reads the output from the Conditional Logic dispatcher
3. Inserts a "RuleCheck" field (TEXT, non-mandatory) at the start of the first panel
4. Places ALL session-based rules on that single RuleCheck field:
   - SESSION_BASED_MAKE_VISIBLE  (FIRST_PARTY)  → destination = all fields in 4.5.1
   - SESSION_BASED_MAKE_INVISIBLE (FIRST_PARTY)  → destination = all fields NOT in 4.5.1
   - SESSION_BASED_MAKE_VISIBLE  (SECOND_PARTY) → destination = all fields in 4.5.2
   - SESSION_BASED_MAKE_INVISIBLE (SECOND_PARTY) → destination = all fields NOT in 4.5.2
5. Outputs single JSON file containing all panels with session-based rules added

No LLM agent is needed — this is purely deterministic logic.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Add project root so we can import doc_parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from doc_parser import DocumentParser


RULE_CHECK_VARIABLE = "__rulecheck__"


def _normalize_field_name(name: str) -> str:
    """Normalize field name for case-insensitive matching with common variations."""
    return name.lower().replace("organisation", "organization").strip()


def extract_session_fields(bud_path: str) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """
    Parse the BUD document and extract field names grouped by panel
    from sections 4.5.1 (Initiator Behaviour) and 4.5.2 (Vendor Behaviour).

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

        # Determine which section this table belongs to
        if table.table_type == "initiator_fields" and ("4.5.1" in table.context or "initiator" in context_lower):
            target = initiator_fields
        elif table.table_type == "spoc_fields" and ("4.5.2" in table.context or "vendor" in context_lower):
            target = vendor_fields
        else:
            continue

        # Extract field names grouped by panel
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


def build_session_rules(all_panels: Dict[str, List[Dict]],
                        initiator_fields: Dict[str, Set[str]],
                        vendor_fields: Dict[str, Set[str]]) -> List[Dict]:
    """
    Build the 4 session-based rules for the RuleCheck field.

    Scans all panels and their fields, classifies each (including the panel
    itself) into visible/invisible for FIRST_PARTY and SECOND_PARTY sessions.

    Returns:
        List of 4 rule dicts to place on the RuleCheck field
    """
    first_visible: List[str] = []
    first_invisible: List[str] = []
    second_visible: List[str] = []
    second_invisible: List[str] = []

    for panel_name, panel_fields in all_panels.items():
        initiator_set = initiator_fields.get(panel_name, set())
        vendor_set = vendor_fields.get(panel_name, set())

        panel_var = _panel_variable_name(panel_name)

        # Classify the PANEL itself based on whether it exists in 4.5.1 / 4.5.2
        if panel_name in initiator_fields:
            first_visible.append(panel_var)
        else:
            first_invisible.append(panel_var)

        if panel_name in vendor_fields:
            second_visible.append(panel_var)
        else:
            second_invisible.append(panel_var)

        # Classify individual fields within the panel
        for field in panel_fields:
            field_type = field.get("type", "")
            if field_type == "PANEL":
                continue

            variable_name = field.get("variableName", "")
            if not variable_name:
                continue

            normalized = _normalize_field_name(field.get("field_name", ""))

            # FIRST_PARTY classification
            if normalized in initiator_set:
                first_visible.append(variable_name)
            else:
                first_invisible.append(variable_name)

            # SECOND_PARTY classification
            if normalized in vendor_set:
                second_visible.append(variable_name)
            else:
                second_invisible.append(variable_name)

    rules = []
    rule_id = 1

    if first_visible:
        rules.append({
            "id": rule_id,
            "rule_name": "Make Visible - Session Based (Client)",
            "source_fields": [RULE_CHECK_VARIABLE],
            "destination_fields": first_visible,
            "params": {"value": "FIRST_PARTY"},
            "conditionalValues": ["Visible"],
            "condition": "NOT_IN",
            "conditionValueType": "TEXT",
            "_reasoning": f"Makes {len(first_visible)} fields from 4.5.1 Initiator Behaviour visible to FIRST_PARTY session"
        })
        rule_id += 1

    if first_invisible:
        rules.append({
            "id": rule_id,
            "rule_name": "Make Invisible - Session Based (Client)",
            "source_fields": [RULE_CHECK_VARIABLE],
            "destination_fields": first_invisible,
            "params": {"value": "FIRST_PARTY"},
            "conditionalValues": ["Invisible"],
            "condition": "NOT_IN",
            "conditionValueType": "TEXT",
            "_reasoning": f"Makes {len(first_invisible)} fields NOT in 4.5.1 Initiator Behaviour invisible to FIRST_PARTY session"
        })
        rule_id += 1

    if second_visible:
        rules.append({
            "id": rule_id,
            "rule_name": "Make Visible - Session Based (Client)",
            "source_fields": [RULE_CHECK_VARIABLE],
            "destination_fields": second_visible,
            "params": {"value": "SECOND_PARTY"},
            "conditionalValues": ["Visible"],
            "condition": "NOT_IN",
            "conditionValueType": "TEXT",
            "_reasoning": f"Makes {len(second_visible)} fields from 4.5.2 Vendor Behaviour visible to SECOND_PARTY session"
        })
        rule_id += 1

    if second_invisible:
        rules.append({
            "id": rule_id,
            "rule_name": "Make Invisible - Session Based (Client)",
            "source_fields": [RULE_CHECK_VARIABLE],
            "destination_fields": second_invisible,
            "params": {"value": "SECOND_PARTY"},
            "conditionalValues": ["Invisible"],
            "condition": "NOT_IN",
            "conditionValueType": "TEXT",
            "_reasoning": f"Makes {len(second_invisible)} fields NOT in 4.5.2 Vendor Behaviour invisible to SECOND_PARTY session"
        })
        rule_id += 1

    return rules


def main():
    parser = argparse.ArgumentParser(
        description="Session-Based Rules Dispatcher - Add session-based visibility rules based on BUD sections 4.5.1 and 4.5.2"
    )
    parser.add_argument(
        "--conditional-logic-output",
        required=True,
        help="Path to Conditional Logic dispatcher output JSON"
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

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.conditional_logic_output).exists():
        print(f"Error: Conditional Logic output not found: {args.conditional_logic_output}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.bud).exists():
        print(f"Error: BUD document not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse BUD to extract fields from 4.5.1 and 4.5.2
    print(f"Parsing BUD document: {args.bud}")
    initiator_fields, vendor_fields = extract_session_fields(args.bud)

    initiator_total = sum(len(fields) for fields in initiator_fields.values())
    vendor_total = sum(len(fields) for fields in vendor_fields.values())

    print(f"\n4.5.1 Initiator Behaviour (FIRST_PARTY):")
    for panel, fields in initiator_fields.items():
        print(f"  {panel}: {len(fields)} fields")

    print(f"\n4.5.2 Vendor Behaviour (SECOND_PARTY):")
    for panel, fields in vendor_fields.items():
        print(f"  {panel}: {len(fields)} fields")

    print(f"\nTotal: {initiator_total} initiator fields, {vendor_total} vendor fields")

    # Step 2: Load conditional logic output
    print(f"\nLoading Conditional Logic output: {args.conditional_logic_output}")
    with open(args.conditional_logic_output, 'r') as f:
        conditional_data = json.load(f)

    print(f"Found {len(conditional_data)} panels in input")

    # Step 3: Build session rules across all panels
    print("\n" + "=" * 70)
    print("BUILDING SESSION-BASED VISIBILITY RULES")
    print("=" * 70)

    session_rules = build_session_rules(conditional_data, initiator_fields, vendor_fields)

    for rule in session_rules:
        print(f"  {rule['rule_name']} ({rule['params']['value']}): {len(rule['destination_fields'])} destination fields")

    # Step 4: Create the RuleCheck field and inject into first panel
    rule_check_field = {
        "field_name": "RuleCheck",
        "type": "TEXT",
        "mandatory": False,
        "logic": "",
        "rules": session_rules,
        "variableName": RULE_CHECK_VARIABLE
    }

    all_results = {}
    first_panel = True

    for panel_name, panel_fields in conditional_data.items():
        if first_panel:
            # Insert RuleCheck at the start of the first panel
            all_results[panel_name] = [rule_check_field] + panel_fields
            print(f"\n  Inserted 'RuleCheck' field at start of panel '{panel_name}' with {len(session_rules)} session rules")
            first_panel = False
        else:
            all_results[panel_name] = panel_fields

    # Step 5: Write output
    print(f"\nWriting output to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    # Summary
    total_dest = sum(len(r["destination_fields"]) for r in session_rules)
    print("\n" + "=" * 70)
    print("SESSION-BASED DISPATCHER COMPLETE")
    print("=" * 70)
    print(f"Panels:                    {len(all_results)}")
    print(f"RuleCheck field placed in: {list(conditional_data.keys())[0]}")
    print(f"Session rules on RuleCheck: {len(session_rules)}")
    for rule in session_rules:
        param = rule["params"]["value"]
        action = "VISIBLE" if "Visible" in rule["rule_name"] else "INVISIBLE"
        print(f"  {action} ({param}): {len(rule['destination_fields'])} fields")
    print(f"Total destination mappings: {total_dest}")
    print(f"Output File: {output_file}")
    print("=" * 70)

    sys.exit(0)


if __name__ == "__main__":
    main()
