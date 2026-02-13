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
from pathlib import Path
from typing import Dict, List, Optional


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
                   panel_name: str, temp_dir: Path) -> Optional[List[Dict]]:
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

    prompt = f"""Process fields for panel "{panel_name}" and populate source/destination fields for each rule.

## Input Data
Read the input from: {input_file}

The input contains:
- fields_with_rules: Array of fields with their logic and assigned rule names
- rule_schemas: Full schemas for all rules mentioned in the fields

## Task
For each field in fields_with_rules:
1. Read and understand the field's logic text
2. For each rule assigned to that field:
   a. Find the rule's schema in rule_schemas
   b. Analyze sourceFields and destinationFields from the schema
   c. Based on the logic and schema, determine:
      - source_fields: Array of variableNames that provide input to this rule
      - destination_fields: Array of variableNames that receive output from this rule
   d. Add the field's own variableName where appropriate

## Important Notes
- Use variableName format (e.g., "__fieldname__") for source/destination fields
- Source fields are inputs to the rule (what the rule reads from)
- Destination fields are outputs of the rule (what the rule writes to)
- A field can be both a source and destination
- Multiple fields can be sources or destinations for a single rule

## RULES (FOLLOW THESE RULES VERY STRICTLY)
1) **ALL** the fields which will be extracted for populating source and destination fields, after analysis of logic and the rule schema, should exist in the field list. **NO** extra fields should be invented to satisfy the RULES_SCHEMA or logic section of that particular field. Even if logic section mentions some other field, it is possible that it is another PANEL altogether which you **SHOULD** ignore.(**STRICTLY** follow this)
2) If some logic section mention another panel or field that doesn't exist in the given list for logic (input or output), then you may ignore those fields after analysis of the logic section.
3) When you analyze the schema, you may notice that not all of fields might be required that the rule is offering, in that case those fields, which are not required, you will have to put "-1", in that to let the system know that this output doesn't need to be populated in any field. The destination fields output need to be serially as per the destination fields in the schema.
4) Analyze in that panel what all fields can be populated using that rule, most of the times this will not be mentioned in the logic section of that field.
5) There will be cases when there might be multiple option for populating fields, you will need fill all the source and destination fields for all the rules, don't assume that it will be copied from other rules/fields.
6) Validate EDV (Verify) rules will have empty source and destination fields.
7) For rules like Make Mandatory, Make Non Mandatory, Make Visible, Make Invisible, Make Enabled and Make Disabled that require conditions (e.g., "if X then make Y visible"), **leave source and destination fields EMPTY**. The Conditional Logic Agent will populate these fields later when it analyzes the conditional logic. 

## Output
Write a JSON array to: {output_file}

Format:
```json
[
  {{
    "field_name": "Field Name",
    "type": "TEXT",
    "mandatory": true,
    "logic": "original logic text",
    "rules": [
      {{
        "id": 1,
        "rule_name": "RULE_NAME_1",
        "source_fields": ["__field1__", "__field2__"],
        "destination_fields": ["__field3__"],
        "_reasoning": "Reasoning for chosen source fields and destination fields."
      }}
    ],
    "variableName": "__fieldname__"
  }}
]
```

Each field must preserve:
- field_name, type, mandatory, logic, variableName from input
- rules: now as array of objects (not strings) with id, rule_name, source_fields, destination_fields
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name} ({len(panel_fields)} fields)")
        print('='*70)

        # Call claude -p with the mini agent
        process = subprocess.Popen(
            [
                "claude",
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
            print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"✗ Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Read output file
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
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

    successful_panels = 0
    failed_panels = 0
    total_fields_processed = 0
    all_results = {}

    for panel_name, panel_fields in panels_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            continue

        # Get relevant rule schemas for this panel
        relevant_schemas = get_relevant_rule_schemas(panel_fields, name_to_schema)

        total_rules_in_panel = sum(len(f.get('rules', [])) for f in panel_fields)
        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {total_rules_in_panel} total rules, {len(relevant_schemas)} unique rule schemas")

        result = call_mini_agent(
            panel_fields,
            relevant_schemas,
            panel_name,
            temp_dir
        )

        if result:
            successful_panels += 1
            total_fields_processed += len(result)
            all_results[panel_name] = result
        else:
            failed_panels += 1
            print(f"✗ Panel '{panel_name}' failed", file=sys.stderr)

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
