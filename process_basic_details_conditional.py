#!/usr/bin/env python3
"""
Process Basic Details panel fields and add conditional logic to rules.
"""

import json
from typing import Dict, List, Any
from datetime import datetime


def determine_conditional_logic(field: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine if a rule needs conditional logic based on field logic text.
    Returns the conditional fields to add (or empty dict if none needed).
    """
    logic = field.get("logic", "").lower()
    rule_name = rule.get("rule_name", "")

    # Pattern matching for conditional logic
    conditional = {}

    # Case 1: Always invisible/hidden
    if rule_name == "Make Invisible (Client)":
        if "not visible" in logic or "invisible" in logic or "hidden" in logic:
            # Check if it's always invisible (no conditions)
            if "always" in logic or ("not visible" in logic and "if" not in logic.split("not visible")[0].lower()):
                # Always invisible - use NOT_IN with "Invisible" value
                conditional = {
                    "conditionalValues": ["Invisible"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT"
                }
            else:
                # Conditionally invisible - depends on source field value
                # The field should be invisible when condition is NOT met
                # So we use NOT_IN or IN depending on the logic

                # Look for specific value patterns in logic
                if "if" in logic:
                    # Extract the condition value
                    if "'yes'" in logic or "is yes" in logic or "= yes" in logic:
                        # Field becomes visible when source is Yes, so invisible when NOT Yes
                        conditional = {
                            "conditionalValues": ["Yes"],
                            "condition": "NOT_IN",
                            "conditionValueType": "TEXT"
                        }
                    elif "'no'" in logic or "is no" in logic or "= no" in logic:
                        # Field becomes visible when source is No, so invisible when NOT No
                        conditional = {
                            "conditionalValues": ["No"],
                            "condition": "NOT_IN",
                            "conditionValueType": "TEXT"
                        }
                    elif "india" in logic and "international" in logic:
                        # Special case for process type
                        if "if india" in logic or "if the select the process type field value is india" in logic:
                            # When India is selected, it becomes visible/locked
                            # So invisible when NOT India (i.e., when International)
                            conditional = {
                                "conditionalValues": ["International"],
                                "condition": "IN",
                                "conditionValueType": "TEXT"
                            }
                    elif "zdes" in logic or "zdom" in logic or "zimp" in logic:
                        # Vendor type conditions - default invisible, visible for specific types
                        # This means invisible when NOT in the list of specific types
                        # Will handle this as always invisible for now
                        conditional = {
                            "conditionalValues": ["Invisible"],
                            "condition": "NOT_IN",
                            "conditionValueType": "TEXT"
                        }

    # Case 2: Always disabled/non-editable
    elif rule_name == "Disable Field (Client)":
        if "non-editable" in logic or "system-generated" in logic or "auto-derived" in logic:
            # Always disabled
            conditional = {
                "conditionalValues": ["Disable"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT"
            }

    # Case 3: Make Non Mandatory
    elif rule_name == "Make Non Mandatory (Client)":
        # Check if there's a condition for mandatory status
        if "if" in logic and ("yes" in logic or "no" in logic):
            # Extract the value that makes it mandatory
            if "'yes'" in logic or "is yes" in logic:
                if "mandatory" in logic.split("yes")[1]:
                    # When Yes, becomes mandatory, so non-mandatory when NOT Yes
                    conditional = {
                        "conditionalValues": ["Yes"],
                        "condition": "NOT_IN",
                        "conditionValueType": "TEXT"
                    }
                else:
                    # When Yes, becomes non-mandatory
                    conditional = {
                        "conditionalValues": ["Yes"],
                        "condition": "IN",
                        "conditionValueType": "TEXT"
                    }
            elif "'no'" in logic or "is no" in logic:
                # When No, behavior changes
                if "mandatory" in logic.split("no")[1]:
                    conditional = {
                        "conditionalValues": ["No"],
                        "condition": "NOT_IN",
                        "conditionValueType": "TEXT"
                    }
        elif "non-mandatory in all the cases" in logic or "should be non-mandatory" in logic:
            # Always non-mandatory - no conditional needed
            pass

    return conditional


def process_fields(input_file: str, output_file: str, log_file: str):
    """
    Process fields and add conditional logic to rules.
    """
    # Read input
    with open(input_file, 'r') as f:
        fields = json.load(f)

    # Open log file for writing
    log_entries = []
    log_entries.append(f"\n=== Processing started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    processed_count = 0
    rules_modified = 0

    # Process each field
    for field in fields:
        field_name = field.get("field_name", "")
        logic = field.get("logic", "")
        rules = field.get("rules", [])

        log_entries.append(f"\nField: {field_name}")
        log_entries.append(f"  Logic: {logic}")
        log_entries.append(f"  Rules count: {len(rules)}")

        if not rules:
            log_entries.append("  -> No rules to process")
            processed_count += 1
            continue

        # Process each rule
        for i, rule in enumerate(rules):
            rule_name = rule.get("rule_name", "")
            log_entries.append(f"\n  Rule {i+1}: {rule_name}")

            # Skip EDV Dropdown and Validate EDV rules - they don't need conditional logic
            if "EDV" in rule_name:
                log_entries.append(f"    -> Skipped (EDV rule)")
                continue

            # Check if rule already has conditional logic
            if "conditionalValues" in rule or "condition" in rule or "conditionValueType" in rule:
                log_entries.append(f"    -> Already has conditional logic, skipping")
                continue

            # Determine conditional logic
            conditional = determine_conditional_logic(field, rule)

            if conditional:
                # Add conditional fields to the rule
                rule.update(conditional)
                log_entries.append(f"    -> Added conditional logic:")
                log_entries.append(f"       conditionalValues: {conditional['conditionalValues']}")
                log_entries.append(f"       condition: {conditional['condition']}")
                log_entries.append(f"       conditionValueType: {conditional['conditionValueType']}")
                rules_modified += 1
            else:
                log_entries.append(f"    -> No conditional logic needed")

        processed_count += 1

    # Write output
    with open(output_file, 'w') as f:
        json.dump(fields, f, indent=2)

    # Write log
    log_entries.append(f"\n\n=== Summary ===")
    log_entries.append(f"Total fields processed: {processed_count}")
    log_entries.append(f"Total rules modified: {rules_modified}")
    log_entries.append(f"Output written to: {output_file}")
    log_entries.append(f"\n=== Processing completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    with open(log_file, 'a') as f:
        f.write('\n'.join(log_entries))

    print(f"Processing complete!")
    print(f"Fields processed: {processed_count}")
    print(f"Rules modified: {rules_modified}")
    print(f"Output: {output_file}")
    print(f"Log: {log_file}")


if __name__ == "__main__":
    input_file = "output/conditional_logic/temp/Basic_Details_fields_input.json"
    output_file = "output/conditional_logic/temp/Basic_Details_conditional_logic_output.json"
    log_file = "output/conditional_logic/temp/Basic_Details_conditional_logic_log.txt"

    process_fields(input_file, output_file, log_file)
