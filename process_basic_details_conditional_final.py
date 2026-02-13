#!/usr/bin/env python3
"""
Process Basic Details panel fields and add conditional logic to rules.
This script performs cross-field analysis to populate source_fields and destination_fields
for visibility/mandatory rules.
"""

import json
from typing import List, Dict, Any
from datetime import datetime

# File paths
INPUT_FILE = "output/conditional_logic/temp/Basic_Details_fields_input.json"
OUTPUT_FILE = "output/conditional_logic/temp/Basic_Details_conditional_logic_output.json"
LOG_FILE = "output/conditional_logic/temp/Basic_Details_conditional_logic_log.txt"

def log(message: str, log_lines: List[str]):
    """Add message to log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    log_lines.append(line)
    print(line)

def normalize_field_name(field_name: str) -> str:
    """Normalize field name for comparison"""
    return field_name.lower().strip()

def find_field_mentions(field_name: str, all_fields: List[Dict]) -> List[str]:
    """
    Find all fields whose logic mentions the given field_name.
    Returns list of variableNames of fields that reference this field.
    """
    normalized_name = normalize_field_name(field_name)
    mentioned_in = []

    for field in all_fields:
        logic = field.get("logic", "").lower()
        other_name = normalize_field_name(field.get("field_name", ""))

        # Skip self-reference
        if other_name == normalized_name:
            continue

        # Check if logic mentions this field
        if normalized_name in logic:
            mentioned_in.append(field.get("variableName"))

    return mentioned_in

def extract_conditional_values(logic: str, field_name: str) -> tuple:
    """
    Extract conditional values from logic text.
    Returns: (conditional_values, condition, condition_value_type)
    """
    logic_lower = logic.lower()

    # Check for "always invisible" or "not visible"
    if any(phrase in logic_lower for phrase in ["always invisible", "not visible,", "default behaviour is invisible"]):
        return (["Invisible"], "NOT_IN", "TEXT")

    # Check for "always disabled" or "non-editable"
    if any(phrase in logic_lower for phrase in ["always disabled", "non-editable", "system-generated", "auto-derived"]):
        return (["Disable"], "NOT_IN", "TEXT")

    # Check for specific value conditions
    # Pattern: "if X is 'value'" or "if X is value"
    if "is yes" in logic_lower or "value is yes" in logic_lower:
        return (["Yes"], "IN", "TEXT")

    if "is no" in logic_lower or "value is no" in logic_lower:
        return (["No"], "IN", "TEXT")

    # Check for multiple values: "ZDES, ZDOM, ZRPV, ZONE"
    if "zdes" in logic_lower or "zdom" in logic_lower:
        # Extract the domestic vendor types
        if "domestic" in logic_lower:
            return (["ZDES", "ZDOM", "ZRPV", "ZONE"], "IN", "TEXT")

    if "zimp" in logic_lower or "zstv" in logic_lower or "zdas" in logic_lower:
        # Extract the import vendor types
        if "import" in logic_lower:
            return (["ZIMP", "ZSTV", "ZDAS"], "IN", "TEXT")

    # Check for process type conditions
    if "india is selected" in logic_lower or "value is india" in logic_lower:
        return (["India"], "IN", "TEXT")

    if "international is selected" in logic_lower or "value is international" in logic_lower:
        return (["International"], "IN", "TEXT")

    return None

def find_source_field_from_logic(logic: str, all_fields: List[Dict]) -> str:
    """
    Determine the source field from logic text.
    Returns the variableName of the source field.
    """
    logic_lower = logic.lower()

    # Map common phrases to field names
    field_mappings = []
    for field in all_fields:
        field_name = field.get("field_name", "")
        var_name = field.get("variableName", "")
        field_mappings.append((normalize_field_name(field_name), var_name))

    # Check for mentions in logic
    for normalized_name, var_name in field_mappings:
        if normalized_name in logic_lower:
            # Make sure it's a reference, not the field's own name
            return var_name

    return ""

def process_field(field: Dict, all_fields: List[Dict], log_lines: List[str]) -> Dict:
    """
    Process a single field and add conditional logic to its rules.
    """
    field_name = field.get("field_name")
    var_name = field.get("variableName")
    logic = field.get("logic", "")
    rules = field.get("rules", [])

    log(f"\n{'='*80}", log_lines)
    log(f"Processing field: {field_name}", log_lines)
    log(f"Variable name: {var_name}", log_lines)
    log(f"Logic: {logic}", log_lines)

    # Process each rule
    for rule in rules:
        rule_name = rule.get("rule_name", "")
        log(f"\n  Rule: {rule_name}", log_lines)

        # Check if this rule needs conditional logic
        needs_conditional = rule_name in [
            "Make Visible (Client)",
            "Make Invisible (Client)",
            "Make Mandatory (Client)",
            "Make Non-Mandatory (Client)",
            "Disable Field (Client)"
        ]

        if not needs_conditional:
            log(f"    → No conditional logic needed for {rule_name}", log_lines)
            continue

        # Extract conditional values from logic
        conditional_data = extract_conditional_values(logic, field_name)

        if conditional_data:
            cond_values, condition, cond_type = conditional_data

            # Add conditional fields
            rule["conditionalValues"] = cond_values
            rule["condition"] = condition
            rule["conditionValueType"] = cond_type

            log(f"    → Added conditional logic:", log_lines)
            log(f"       conditionalValues: {cond_values}", log_lines)
            log(f"       condition: {condition}", log_lines)
            log(f"       conditionValueType: {cond_type}", log_lines)

            # Populate source_fields and destination_fields
            if rule_name == "Disable Field (Client)":
                # For disable field, check if it's "always disabled"
                if condition == "NOT_IN" and cond_values == ["Disable"]:
                    # Always disabled - no source field
                    rule["source_fields"] = []
                    rule["destination_fields"] = [var_name]
                    log(f"    → Always disabled: source=[], destination=[{var_name}]", log_lines)
                else:
                    # Conditional disable
                    source = find_source_field_from_logic(logic, all_fields)
                    rule["source_fields"] = [source] if source and source != var_name else []
                    rule["destination_fields"] = [var_name]
                    log(f"    → Conditional disable: source=[{source}], destination=[{var_name}]", log_lines)

            elif rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                # For visibility/mandatory rules on the trigger field:
                # - source_fields: the current field (trigger)
                # - destination_fields: fields that depend on this field

                # Find fields that mention this field in their logic
                dependent_fields = find_field_mentions(field_name, all_fields)

                if dependent_fields:
                    rule["source_fields"] = [var_name]
                    rule["destination_fields"] = dependent_fields
                    log(f"    → Trigger field: source=[{var_name}], destination={dependent_fields}", log_lines)
                else:
                    # No dependent fields found, might be self-referencing
                    rule["source_fields"] = []
                    rule["destination_fields"] = [var_name]
                    log(f"    → No dependents found: source=[], destination=[{var_name}]", log_lines)

            elif rule_name in ["Make Invisible (Client)", "Make Non-Mandatory (Client)"]:
                # For invisible/non-mandatory rules:
                # Check if it's "always invisible" or conditional

                if condition == "NOT_IN" and cond_values == ["Invisible"]:
                    # Always invisible - check if there's a source field
                    source = find_source_field_from_logic(logic, all_fields)
                    if source and source != var_name:
                        # Conditional on another field
                        rule["source_fields"] = [source]
                        rule["destination_fields"] = [var_name]
                        log(f"    → Conditional invisible: source=[{source}], destination=[{var_name}]", log_lines)
                    else:
                        # Always invisible
                        rule["source_fields"] = []
                        rule["destination_fields"] = [var_name]
                        log(f"    → Always invisible: source=[], destination=[{var_name}]", log_lines)
                else:
                    # Conditional based on another field
                    source = find_source_field_from_logic(logic, all_fields)
                    rule["source_fields"] = [source] if source and source != var_name else []
                    rule["destination_fields"] = [var_name]
                    log(f"    → Conditional: source=[{source}], destination=[{var_name}]", log_lines)

            # Add reasoning
            rule["_reasoning"] = f"{rule_name} with condition={condition}, values={cond_values}. " \
                                f"Source: {rule.get('source_fields', [])}, Destination: {rule.get('destination_fields', [])}"
        else:
            log(f"    → No conditional pattern matched in logic", log_lines)

    return field

def main():
    log_lines = []

    log("="*80, log_lines)
    log("Basic Details Panel - Conditional Logic Processing", log_lines)
    log("="*80, log_lines)

    # Read input
    log(f"\nReading input from: {INPUT_FILE}", log_lines)
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        fields = json.load(f)

    log(f"Loaded {len(fields)} fields", log_lines)

    # Process each field
    processed_fields = []
    for field in fields:
        processed_field = process_field(field, fields, log_lines)
        processed_fields.append(processed_field)

    # Write output
    log(f"\n{'='*80}", log_lines)
    log(f"Writing output to: {OUTPUT_FILE}", log_lines)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_fields, f, indent=2, ensure_ascii=False)

    log(f"Successfully processed {len(processed_fields)} fields", log_lines)

    # Write log
    log(f"\nWriting log to: {LOG_FILE}", log_lines)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))

    log("="*80, log_lines)
    log("PROCESSING COMPLETE", log_lines)
    log("="*80, log_lines)

if __name__ == "__main__":
    main()
