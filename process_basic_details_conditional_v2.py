#!/usr/bin/env python3
"""
Process Basic Details panel fields and add conditional logic to rules.
Enhanced version with better cross-field analysis.
"""

import json
import re
from typing import List, Dict, Any, Tuple, Optional
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
    return field_name.lower().strip().replace('"', '').replace("'", '')

def find_field_by_name(name_to_find: str, all_fields: List[Dict]) -> Optional[Dict]:
    """Find a field by its name (fuzzy match)"""
    normalized = normalize_field_name(name_to_find)

    for field in all_fields:
        field_name = normalize_field_name(field.get("field_name", ""))
        if normalized == field_name or normalized in field_name or field_name in normalized:
            return field

    return None

def find_dependent_fields(source_field_name: str, all_fields: List[Dict]) -> List[str]:
    """
    Find all fields whose logic mentions the source field.
    Returns list of variableNames.
    """
    normalized_source = normalize_field_name(source_field_name)
    dependent_vars = []

    for field in all_fields:
        logic = field.get("logic", "").lower()
        field_name = normalize_field_name(field.get("field_name", ""))

        # Skip self-reference
        if field_name == normalized_source:
            continue

        # Check if logic mentions the source field
        # Look for patterns like "if [field]", "based on [field]", etc.
        if normalized_source in logic:
            dependent_vars.append(field.get("variableName"))

    return dependent_vars

def extract_source_field_from_logic(logic: str, all_fields: List[Dict], current_field_name: str) -> Optional[str]:
    """
    Extract the source field name from logic text.
    Returns the variableName of the source field.
    """
    logic_lower = logic.lower()
    current_normalized = normalize_field_name(current_field_name)

    # Common patterns indicating field reference
    patterns = [
        r'if\s+["\']?([^"\']+?)["\']?\s+(?:is|value|field)',
        r'based on\s+(?:the\s+)?["\']?([^"\']+?)["\']?\s+(?:field|selection)',
        r'when\s+["\']?([^"\']+?)["\']?\s+(?:is|value)',
        r'if\s+(?:the\s+)?["\']?([^"\']+?)["\']?\s+value',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, logic_lower)
        for match in matches:
            # Try to find this field
            found_field = find_field_by_name(match, all_fields)
            if found_field:
                found_name = normalize_field_name(found_field.get("field_name", ""))
                # Make sure it's not self-reference
                if found_name != current_normalized:
                    return found_field.get("variableName")

    # Fallback: look for any field name mentioned in the logic
    for field in all_fields:
        field_name = field.get("field_name", "")
        field_normalized = normalize_field_name(field_name)

        # Skip self
        if field_normalized == current_normalized:
            continue

        # Check if this field is mentioned
        if field_normalized in logic_lower and len(field_normalized) > 5:  # Avoid short false matches
            return field.get("variableName")

    return None

def extract_conditional_values(logic: str, field_name: str) -> Optional[Tuple[List[str], str, str]]:
    """
    Extract conditional values from logic text.
    Returns: (conditional_values, condition, condition_value_type) or None
    """
    logic_lower = logic.lower()

    # Pattern 1: Always invisible/hidden
    if any(phrase in logic_lower for phrase in [
        "not visible,",
        "default behaviour is invisible",
        "always invisible",
        "never visible",
        "hidden"
    ]):
        return (["Invisible"], "NOT_IN", "TEXT")

    # Pattern 2: Always disabled/non-editable/read-only
    if any(phrase in logic_lower for phrase in [
        "non-editable",
        "system-generated",
        "auto-derived",
        "read-only",
        "always disabled"
    ]):
        return (["Disable"], "NOT_IN", "TEXT")

    # Pattern 3: "if ... is Yes" or "value is Yes"
    if re.search(r'(?:is|value is|=)\s*["\']?yes["\']?', logic_lower):
        return (["Yes"], "IN", "TEXT")

    # Pattern 4: "if ... is No" or "value is No"
    if re.search(r'(?:is|value is|=)\s*["\']?no["\']?', logic_lower):
        return (["No"], "IN", "TEXT")

    # Pattern 5: Multiple specific values (vendor types)
    if "zdes" in logic_lower or "zdom" in logic_lower:
        if "domestic" in logic_lower:
            return (["ZDES", "ZDOM", "ZRPV", "ZONE"], "IN", "TEXT")

    if "zimp" in logic_lower or "zstv" in logic_lower or "zdas" in logic_lower:
        if "import" in logic_lower:
            return (["ZIMP", "ZSTV", "ZDAS"], "IN", "TEXT")

    # Pattern 6: India vs International
    if "india is selected" in logic_lower or re.search(r'value is\s*["\']?india["\']?', logic_lower):
        return (["India"], "IN", "TEXT")

    if "international is selected" in logic_lower or re.search(r'value is\s*["\']?international["\']?', logic_lower):
        return (["International"], "IN", "TEXT")

    return None

def process_visibility_mandatory_rule(rule: Dict, field: Dict, all_fields: List[Dict], log_lines: List[str]):
    """
    Process Make Visible/Make Mandatory rules to populate source_fields and destination_fields.

    For these trigger-type rules on a field:
    - source_fields: the current field (this is the trigger)
    - destination_fields: all other fields that mention this field in their logic
    """
    field_name = field.get("field_name")
    var_name = field.get("variableName")
    rule_name = rule.get("rule_name", "")

    # Find all fields that depend on this field
    dependent_fields = find_dependent_fields(field_name, all_fields)

    log(f"    → Cross-field analysis for '{field_name}':", log_lines)
    log(f"       Found {len(dependent_fields)} dependent fields: {dependent_fields}", log_lines)

    # For visibility/mandatory rules on a trigger field:
    # - This field is the source (trigger)
    # - Dependent fields are destinations
    if dependent_fields:
        rule["source_fields"] = [var_name]
        rule["destination_fields"] = dependent_fields
    else:
        # No dependent fields found - might be self-referencing or incorrectly specified
        rule["source_fields"] = []
        rule["destination_fields"] = [var_name]

def process_conditional_rule(rule: Dict, field: Dict, all_fields: List[Dict], log_lines: List[str]):
    """
    Process a rule that needs conditional logic.
    Adds conditionalValues, condition, conditionValueType fields.
    Also populates source_fields and destination_fields appropriately.
    """
    field_name = field.get("field_name")
    var_name = field.get("variableName")
    logic = field.get("logic", "")
    rule_name = rule.get("rule_name", "")

    log(f"  Rule: {rule_name}", log_lines)

    # Extract conditional values
    conditional_data = extract_conditional_values(logic, field_name)

    if not conditional_data:
        log(f"    → No conditional pattern matched", log_lines)
        return

    cond_values, condition, cond_type = conditional_data

    # Add conditional fields
    rule["conditionalValues"] = cond_values
    rule["condition"] = condition
    rule["conditionValueType"] = cond_type

    log(f"    → Conditional logic: condition={condition}, values={cond_values}", log_lines)

    # Now handle source_fields and destination_fields based on rule type
    if rule_name == "Disable Field (Client)":
        # Disable field: check if it's "always disabled" or conditional
        if condition == "NOT_IN" and "Disable" in cond_values:
            # Always disabled - no source field
            rule["source_fields"] = []
            rule["destination_fields"] = [var_name]
            log(f"    → Always disabled: source=[], destination=[{var_name}]", log_lines)
        else:
            # Conditional disable - find source
            source = extract_source_field_from_logic(logic, all_fields, field_name)
            rule["source_fields"] = [source] if source else []
            rule["destination_fields"] = [var_name]
            log(f"    → Conditional disable: source=[{source}], destination=[{var_name}]", log_lines)

    elif rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
        # Visibility/Mandatory rules on trigger fields
        process_visibility_mandatory_rule(rule, field, all_fields, log_lines)

    elif rule_name in ["Make Invisible (Client)", "Make Non-Mandatory (Client)"]:
        # Invisible/Non-mandatory rules
        if condition == "NOT_IN" and "Invisible" in cond_values:
            # Check if there's a source field mentioned
            source = extract_source_field_from_logic(logic, all_fields, field_name)
            if source:
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
            # Other conditional cases
            source = extract_source_field_from_logic(logic, all_fields, field_name)
            rule["source_fields"] = [source] if source else []
            rule["destination_fields"] = [var_name]
            log(f"    → Conditional: source=[{source}], destination=[{var_name}]", log_lines)

    # Update reasoning
    rule["_reasoning"] = f"{rule_name} with condition={condition}, values={cond_values}. " \
                        f"Source: {rule.get('source_fields', [])}, Destination: {rule.get('destination_fields', [])}"

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
    log(f"Variable: {var_name}", log_lines)
    log(f"Logic: {logic[:100]}{'...' if len(logic) > 100 else ''}", log_lines)

    # Process each rule
    for rule in rules:
        rule_name = rule.get("rule_name", "")

        # Check if this rule needs conditional logic
        conditional_rules = [
            "Make Visible (Client)",
            "Make Invisible (Client)",
            "Make Mandatory (Client)",
            "Make Non-Mandatory (Client)",
            "Disable Field (Client)"
        ]

        if rule_name in conditional_rules:
            process_conditional_rule(rule, field, all_fields, log_lines)
        else:
            log(f"  Rule: {rule_name} → No conditional processing needed", log_lines)

    return field

def main():
    log_lines = []

    log("="*80, log_lines)
    log("Basic Details Panel - Conditional Logic Processing (Enhanced)", log_lines)
    log("="*80, log_lines)

    # Read input
    log(f"\nReading input: {INPUT_FILE}", log_lines)
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        fields = json.load(f)

    log(f"Loaded {len(fields)} fields", log_lines)

    # Build field index for cross-reference
    log(f"\nBuilding field index for cross-field analysis...", log_lines)
    field_index = {normalize_field_name(f.get("field_name", "")): f for f in fields}
    log(f"Indexed {len(field_index)} fields", log_lines)

    # Process each field
    processed_fields = []
    for field in fields:
        processed_field = process_field(field, fields, log_lines)
        processed_fields.append(processed_field)

    # Write output
    log(f"\n{'='*80}", log_lines)
    log(f"Writing output: {OUTPUT_FILE}", log_lines)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(processed_fields, f, indent=2, ensure_ascii=False)

    log(f"Successfully processed {len(processed_fields)} fields", log_lines)

    # Write log
    log(f"\nWriting log: {LOG_FILE}", log_lines)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))

    log("="*80, log_lines)
    log("PROCESSING COMPLETE", log_lines)
    log("="*80, log_lines)

if __name__ == "__main__":
    main()
