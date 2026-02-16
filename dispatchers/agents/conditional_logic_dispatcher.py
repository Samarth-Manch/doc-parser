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

    prompt = f"""Process fields for panel "{panel_name}" and add conditional logic to rules that need it.

## Input Data
1. Fields with rules: {fields_input_file}
2. Log file: {log_file}

## Task
**YOUR RESPONSIBILITY**: Populate source_fields and destination_fields for visibility/mandatory rules AND add conditional logic.

### Step 1: Read ALL fields' logic
Read the logic text of **ALL** fields in the panel to understand field relationships.

### Step 2: Check where visibility/mandatory rules are placed
**CHECK FIRST** - determine if rules are ALREADY on controller (correct) or on affected fields (wrong):

**CASE A: Rules ALREADY on controller (correct placement)**
```
Controller field already has: Make Visible, Make Invisible rules
Affected fields' logic: "If controller is Yes, make visible"
→ Rules are CORRECTLY placed - just populate source/dest
→ Do NOT create new rules
```

**CASE B: Rules on affected fields (wrong placement)**
```
Affected fields have: Make Visible rules (each referencing controller)
→ Rules are on WRONG fields - need consolidation
```

### Step 3: Take appropriate action
**For CASE A (rules already on controller):**
1. Read logic of all affected fields (fields that mention this controller)
2. Populate source_fields = controller variable name
3. Populate destination_fields = all affected field variable names
4. Add conditional logic (conditionalValues, condition, conditionValueType)
5. **Do NOT create new rules - just update existing ones**

**For CASE B (rules on affected fields):**
1. Group rules by source field (the controller)
2. Combine destinations into ONE rule per condition
3. Create consolidated rule on controller field
4. Keep existing rules on affected fields

### Step 4: Add conditional logic to ALL rules
For each rule:
   a. Determine the condition operator (IN, NOT_IN, or BETWEEN)
   b. Extract the conditional values from the logic
   c. Determine the condition value type (typically TEXT)
   d. Add conditionalValues, condition, and conditionValueType fields

**Critical**: Check placement FIRST. If rules are already on controller, just populate fields - don't create duplicates!

## Key Rules
- **NO DUPLICATES**: If rules are ALREADY on controller field, just populate source/dest - do NOT create new rules
- **CHECK PLACEMENT FIRST**: Determine if rules are on controller (correct) or affected fields (wrong)
- **If on controller**: Just add source_fields, destination_fields, and conditional logic to existing rules
- **If on affected fields**: Consolidate onto controller while keeping originals on affected fields
- Group rules by rule_name and conditionalValues, combine destinations into ONE rule
- Controller field gets ONE rule per condition with multiple destinations
- The condition operator is ALWAYS one of: IN, NOT_IN, or BETWEEN
- For "Always/By default Invisible": use condition: "NOT_IN", conditionalValues: ["Invisible"]
- For "Always/By default Disabled": use condition: "NOT_IN", conditionalValues: ["Disable"]
- For "Always/By default Mandatory": use condition: "NOT_IN", conditionalValues: ["Mandatory"]
- For "Always/By default Non-Mandatory": use condition: "NOT_IN", conditionalValues: ["Non Mandatory"]
- For "Always/By default Enabled": use condition: "NOT_IN", conditionalValues: ["Enable"]
- For "Always/By default Visible": use condition: "NOT_IN", conditionalValues: ["Visible"]
- "Always" and "By default" are equivalent keywords — both mean the rule fires unconditionally using NOT_IN
- conditionalValues is ALWAYS an array of strings

## Example 1: Rules ALREADY on Controller (Correct - No Consolidation Needed)
**Input:**
```
Field A (controller): Has Make Visible, Make Invisible rules (source/dest empty)
Field B logic: "If Field A is Yes, make visible"
Field C logic: "If Field A is Yes, make visible"
Field D logic: "If Field A is Yes, make visible"
Field B, C, D: rules=[] (no visibility rules on affected fields)
```

**Output (just populate source/dest, no new rules):**
```
Field A:
  - Make Visible with source="Field A", dest=["Field B","Field C","Field D"], values=["Yes"], condition="IN"
  - Make Invisible with source="Field A", dest=["Field B","Field C","Field D"], values=["No"], condition="IN"
Field B, C, D: rules=[] (still empty - no rules to add)
```

## Example 2: Rules on Affected Fields (Wrong - Needs Consolidation)
**Input:**
```
Field A (controller): rules=[]
Field B: Make Visible, Make Invisible rules (referencing Field A)
Field C: Make Visible, Make Invisible rules (referencing Field A)
Field D: Make Visible, Make Invisible rules (referencing Field A)
```

**Output (consolidated on controller, keeping originals):**
```
Field A:
  - Make Visible with source="Field A", dest=["Field B","Field C","Field D"], values=["Yes"]
  - Make Invisible with source="Field A", dest=["Field B","Field C","Field D"], values=["No"]
Field B, C, D: Original Make Visible and Make Invisible rules KEPT
```

## Special Cases

### Always/By Default Invisible / Hidden
Logic: "Always invisible", "By default invisible", "Hidden", "Never visible"
Add:
```json
{{
    "conditionalValues": ["Invisible"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}}
```

### Always/By Default Disabled / Non-Editable
Logic: "Always disabled", "By default disabled", "Non-editable", "Read-only", "System-generated"
Add:
```json
{{
    "conditionalValues": ["Disable"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}}
```

### Always/By Default Mandatory
Logic: "Always mandatory", "By default mandatory"
Add:
```json
{{
    "conditionalValues": ["Mandatory"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}}
```

### Always/By Default Non-Mandatory
Logic: "Always non-mandatory", "By default non-mandatory"
Add:
```json
{{
    "conditionalValues": ["Non Mandatory"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}}
```

### Always/By Default Enabled
Logic: "Always enabled", "By default enabled"
Add:
```json
{{
    "conditionalValues": ["Enable"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}}
```

### Always/By Default Visible
Logic: "Always visible", "By default visible"
Add:
```json
{{
    "conditionalValues": ["Visible"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}}
```

### Conditional Based on Value
Logic: "If dropdown is 'X', make visible", "If field value is A, B, C"
Add:
```json
{{
    "conditionalValues": ["X"],
    "condition": "IN",
    "conditionValueType": "TEXT"
}}
```

## Output
Write a JSON array to: {output_file}

The output should have the same structure as input, but with:
1. **If rules ALREADY on controller**: Source/dest/conditional fields POPULATED on existing rules (no new rules)
2. **If rules on affected fields**: Consolidated rules ADDED to controller, originals KEPT on affected fields
3. Conditional logic fields ADDED to all rules (conditionalValues, condition, conditionValueType)

**Example: Rules already on controller (most common case):**
```json
[
  {{
    "field_name": "Field A",
    "type": "EXTERNAL_DROP_DOWN_VALUE",
    "logic": "Dropdown with values Yes/No",
    "rules": [
      {{
        "id": 1,
        "rule_name": "EDV Dropdown (Client)",
        "source_fields": [],
        "destination_fields": ["__field_a__"],
        ...
      }},
      {{
        "id": 2,
        "rule_name": "Make Visible (Client)",
        "source_fields": ["__field_a__"],
        "destination_fields": ["__field_b__", "__field_c__", "__field_d__"],
        "conditionalValues": ["Yes"],
        "condition": "IN",
        "conditionValueType": "TEXT",
        "_reasoning": "Shows Fields B, C, D when Field A is Yes. Source/dest populated by analyzing affected fields' logic."
      }},
      {{
        "id": 3,
        "rule_name": "Make Invisible (Client)",
        "source_fields": ["__field_a__"],
        "destination_fields": ["__field_b__", "__field_c__", "__field_d__"],
        "conditionalValues": ["No"],
        "condition": "IN",
        "conditionValueType": "TEXT",
        "_reasoning": "Hides Fields B, C, D when Field A is No. Source/dest populated by analyzing affected fields' logic."
      }},
      {{
        "id": 4,
        "rule_name": "Make Mandatory (Client)",
        "source_fields": ["__field_a__"],
        "destination_fields": ["__field_b__"],
        "conditionalValues": ["Yes"],
        "condition": "IN",
        "conditionValueType": "TEXT",
        "_reasoning": "Makes Field B mandatory when Field A is Yes."
      }},
      {{
        "id": 5,
        "rule_name": "Make Non Mandatory (Client)",
        "source_fields": ["__field_a__"],
        "destination_fields": ["__field_b__"],
        "conditionalValues": ["No"],
        "condition": "IN",
        "conditionValueType": "TEXT",
        "_reasoning": "Makes Field B non-mandatory when Field A is No."
      }}
    ],
    "variableName": "__field_a__"
  }},
  {{
    "field_name": "Field B",
    "type": "TEXT",
    "logic": "If Field A is 'Yes', show and make mandatory, otherwise hide and non-mandatory",
    "rules": [],
    "variableName": "__field_b__"
  }},
  {{
    "field_name": "Field C",
    "type": "TEXT",
    "logic": "If Field A is 'Yes', show",
    "rules": [],
    "variableName": "__field_c__"
  }}
]
```

### Always Invisible Example (No Trigger Field)
```json
{{
  "field_name": "Field Z",
  "rules": [
    {{
      "id": 1,
      "rule_name": "Make Invisible (Client)",
      "source_fields": [],
      "destination_fields": ["__field_z__"],
      "conditionalValues": ["Invisible"],
      "condition": "NOT_IN",
      "conditionValueType": "TEXT",
      "_reasoning": "Always hidden. No source field as it's unconditional."
    }}
  ]
}}
```

IMPORTANT:
- **CHECK PLACEMENT FIRST**: Determine if rules are ALREADY on controller or on affected fields
- **If on controller**: Just populate source_fields and destination_fields - do NOT create new rules
- **If on affected fields**: Consolidate onto controller while keeping originals
- For "always/by default" rules (invisible/disabled/mandatory/non-mandatory/enabled/visible), source_fields remains empty, destination is the field itself
- **NO DUPLICATES**: Do not create duplicate rules if they already exist on controller field
- ADD the three conditional fields where needed: conditionalValues, condition, conditionValueType
- Group rules by rule_name and conditionalValues before combining destinations
- Log each step to the log file

## Implementation Steps:
1. Read all fields' logic to build relationship map
2. Identify controller fields (mentioned in other fields' logic)
3. **Check if visibility/mandatory rules are ALREADY on controller fields**
4. **If YES**: Just populate source/dest/conditional - skip to step 6
5. **If NO** (rules on affected fields): Group and consolidate onto controller
6. Add conditional logic to all rules
7. Write output preserving all existing rules
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
