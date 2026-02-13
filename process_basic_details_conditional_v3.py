#!/usr/bin/env python3
"""
Process Basic Details panel fields and add conditional logic to rules.
"""

import json
from typing import List, Dict, Any
from datetime import datetime

def log_message(log_file: str, message: str):
    """Append a message to the log file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")

def analyze_dependencies(fields: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """
    Analyze all fields to build a dependency map.
    Returns a dict mapping field_name to its dependency info.
    """
    dependencies = {}

    for field in fields:
        field_name = field['field_name']
        logic = field.get('logic', '')
        variable_name = field['variableName']

        dep_info = {
            'variable_name': variable_name,
            'logic': logic,
            'triggers': [],  # Fields this field depends on
            'affects': [],   # Fields this field affects
            'patterns': []   # Detected patterns
        }

        # Detect patterns in logic
        if any(keyword in logic for keyword in ['System-generated', 'Non-Editable', 'Non-editable', 'auto-derived']):
            dep_info['patterns'].append('ALWAYS_DISABLED')

        if 'Not visible' in logic and 'If' not in logic:
            dep_info['patterns'].append('ALWAYS_INVISIBLE')

        # Detect conditional visibility/mandatory
        if 'If' in logic or 'if' in logic or 'based on' in logic:
            dep_info['patterns'].append('CONDITIONAL')

        dependencies[field_name] = dep_info

    return dependencies

def add_conditional_logic_to_rule(rule: Dict, log_file: str, field_name: str,
                                   logic: str, dependencies: Dict) -> Dict:
    """
    Add conditional logic fields to a rule based on its type and the field's logic.
    """
    rule_name = rule['rule_name']

    # Handle Disable Field rules for always-disabled fields
    if rule_name == 'Disable Field (Client)':
        if any(keyword in logic for keyword in ['System-generated', 'Non-Editable', 'Non-editable', 'auto-derived']):
            rule['conditionalValues'] = ["Disable"]
            rule['condition'] = "NOT_IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: ALWAYS_DISABLED (detected: System-generated/Non-editable)")
            log_message(log_file, f"    Added: conditionalValues=['Disable'], condition='NOT_IN', conditionValueType='TEXT'")
            log_message(log_file, f"    Logic: {logic}")
            log_message(log_file, "")

    # Handle Make Invisible rules
    elif rule_name == 'Make Invisible (Client)':
        # Process Type field
        if field_name == 'Process Type':
            rule['source_fields'] = ["__select_the_process_type__"]
            rule['destination_fields'] = ["__process_type__"]
            rule['conditionalValues'] = ["India", "International"]
            rule['condition'] = "IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: CONDITIONAL_INVISIBLE (derived from Select the process type)")
            log_message(log_file, f"    Added: source_fields=['__select_the_process_type__'], destination_fields=['__process_type__']")
            log_message(log_file, f"    Added: conditionalValues=['India', 'International'], condition='IN', conditionValueType='TEXT'")
            log_message(log_file, f"    Logic: {logic}")
            log_message(log_file, "")

        # Vendor Domestic or Import field
        elif field_name == 'Vendor Domestic or Import':
            rule['source_fields'] = ["__account_group/vendor_type__"]
            rule['destination_fields'] = ["__vendor_domestic_or_import__"]
            rule['conditionalValues'] = ["ZDES", "ZDOM", "ZRPV", "ZONE", "ZIMP", "ZSTV", "ZDAS"]
            rule['condition'] = "IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: CONDITIONAL_INVISIBLE (derived from Account group/vendor type)")
            log_message(log_file, f"    Added: source_fields=['__account_group/vendor_type__'], destination_fields=['__vendor_domestic_or_import__']")
            log_message(log_file, f"    Added: conditionalValues=['ZDES', 'ZDOM', 'ZRPV', 'ZONE', 'ZIMP', 'ZSTV', 'ZDAS'], condition='IN'")
            log_message(log_file, f"    Logic: {logic}")
            log_message(log_file, "")

        # Country Name field
        elif field_name == 'Country Name':
            rule['conditionalValues'] = ["Invisible"]
            rule['condition'] = "NOT_IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: ALWAYS_INVISIBLE (Not visible, auto-derived from Country selection)")
            log_message(log_file, f"    Added: conditionalValues=['Invisible'], condition='NOT_IN', conditionValueType='TEXT'")
            log_message(log_file, f"    Logic: {logic}")
            log_message(log_file, "")

        # Country Code field
        elif field_name == 'Country Code':
            rule['conditionalValues'] = ["Invisible"]
            rule['condition'] = "NOT_IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: ALWAYS_INVISIBLE (Not visible, auto-derived from Country selection)")
            log_message(log_file, f"    Added: conditionalValues=['Invisible'], condition='NOT_IN', conditionValueType='TEXT'")
            log_message(log_file, f"    Logic: {logic}")
            log_message(log_file, "")

    # Handle Make Visible rules
    elif rule_name == 'Make Visible (Client)':
        # Do you wish to add additional mobile numbers (India)?
        if field_name == 'Do you wish to add additional mobile numbers (India)?':
            # This field itself should be visible when process type is India
            rule['source_fields'] = ["__select_the_process_type__"]
            rule['destination_fields'] = ["__do_you_wish_to_add_additional_mobile_numbers_(india)?__"]
            rule['conditionalValues'] = ["India"]
            rule['condition'] = "IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: CONDITIONAL_VISIBLE (visible when process type is India)")
            log_message(log_file, f"    Added: source_fields=['__select_the_process_type__'], destination_fields=['__do_you_wish_to_add_additional_mobile_numbers_(india)?__']")
            log_message(log_file, f"    Added: conditionalValues=['India'], condition='IN', conditionValueType='TEXT'")
            log_message(log_file, "")

        # Do you wish to add additional mobile numbers (Non-India)?
        elif field_name == 'Do you wish to add additional mobile numbers (Non-India)?':
            # This field itself should be visible when process type is International
            rule['source_fields'] = ["__select_the_process_type__"]
            rule['destination_fields'] = ["__do_you_wish_to_add_additional_mobile_numbers_(non-india)?__"]
            rule['conditionalValues'] = ["International"]
            rule['condition'] = "IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: CONDITIONAL_VISIBLE (visible when process type is International)")
            log_message(log_file, f"    Added: source_fields=['__select_the_process_type__'], destination_fields=['__do_you_wish_to_add_additional_mobile_numbers_(non-india)?__']")
            log_message(log_file, f"    Added: conditionalValues=['International'], condition='IN', conditionValueType='TEXT'")
            log_message(log_file, "")

        # Do you wish to add additional email addresses?
        elif field_name == 'Do you wish to add additional email addresses?':
            # Assuming this is always visible, but we could add conditional logic if needed
            # Based on the logic, this doesn't specify a condition for visibility
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: NO_CONDITION (logic doesn't specify when field is visible)")
            log_message(log_file, f"    Action: Keeping rule as-is, may need manual review")
            log_message(log_file, "")

        # Concerned email addresses?
        elif field_name == 'Concerned email addresses?':
            # Assuming this is always visible, but we could add conditional logic if needed
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: NO_CONDITION (logic doesn't specify when field is visible)")
            log_message(log_file, f"    Action: Keeping rule as-is, may need manual review")
            log_message(log_file, "")

    # Handle Make Mandatory rules
    elif rule_name == 'Make Mandatory (Client)':
        # Do you wish to add additional mobile numbers (India)?
        if field_name == 'Do you wish to add additional mobile numbers (India)?':
            # Mandatory when visible (when process type is India)
            rule['source_fields'] = ["__select_the_process_type__"]
            rule['destination_fields'] = ["__do_you_wish_to_add_additional_mobile_numbers_(india)?__"]
            rule['conditionalValues'] = ["India"]
            rule['condition'] = "IN"
            rule['conditionValueType'] = "TEXT"
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: CONDITIONAL_MANDATORY (mandatory when process type is India)")
            log_message(log_file, f"    Added: source_fields=['__select_the_process_type__'], destination_fields=['__do_you_wish_to_add_additional_mobile_numbers_(india)?__']")
            log_message(log_file, f"    Added: conditionalValues=['India'], condition='IN', conditionValueType='TEXT'")
            log_message(log_file, "")

        # Do you wish to add additional email addresses?
        elif field_name == 'Do you wish to add additional email addresses?':
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: NO_CONDITION (logic doesn't specify when field is mandatory)")
            log_message(log_file, f"    Action: Keeping rule as-is, may need manual review")
            log_message(log_file, "")

        # Concerned email addresses?
        elif field_name == 'Concerned email addresses?':
            log_message(log_file, f"  Field: {field_name}")
            log_message(log_file, f"    Rule: {rule_name}")
            log_message(log_file, f"    Pattern: NO_CONDITION (logic doesn't specify when field is mandatory)")
            log_message(log_file, f"    Action: Keeping rule as-is, may need manual review")
            log_message(log_file, "")

    return rule

def check_missing_rules(fields: List[Dict], log_file: str):
    """
    Check for fields that should have rules based on their logic but don't.
    """
    log_message(log_file, "\n=== CHECKING FOR MISSING RULES ===\n")

    for field in fields:
        field_name = field['field_name']
        logic = field.get('logic', '')
        rules = field.get('rules', [])

        # Mobile Number 2-5 (Domestic) - should have Make Visible rules
        if 'Mobile Number' in field_name and '(Domestic)' in field_name and field_name != 'Mobile Number':
            if not any(r['rule_name'] in ['Make Visible (Client)', 'Make Invisible (Client)'] for r in rules):
                log_message(log_file, f"  MISSING RULE: {field_name}")
                log_message(log_file, f"    Logic: {logic}")
                log_message(log_file, f"    Expected: Make Visible (Client) rule")
                log_message(log_file, f"    Trigger: __do_you_wish_to_add_additional_mobile_numbers_(india)?__")
                log_message(log_file, f"    Condition: conditionalValues=['Yes'], condition='IN'")
                if 'Mobile Number 2 (Domestic)' in field_name:
                    log_message(log_file, f"    Also needs: Make Mandatory (Client) rule")
                log_message(log_file, "")

        # Mobile Number 2-5 (Import) - should have Make Visible rules
        if 'Mobile Number' in field_name and '(Import)' in field_name:
            if not any(r['rule_name'] in ['Make Visible (Client)', 'Make Invisible (Client)'] for r in rules):
                log_message(log_file, f"  MISSING RULE: {field_name}")
                log_message(log_file, f"    Logic: {logic}")
                log_message(log_file, f"    Expected: Make Visible (Client) rule")
                log_message(log_file, f"    Trigger: __do_you_wish_to_add_additional_mobile_numbers_(non-india)?__")
                log_message(log_file, f"    Condition: conditionalValues=['Yes'], condition='IN'")
                log_message(log_file, "")

        # Email 2 - should have Make Visible and Make Mandatory rules
        if field_name == 'Email 2':
            if not any(r['rule_name'] in ['Make Visible (Client)', 'Make Invisible (Client)'] for r in rules):
                log_message(log_file, f"  MISSING RULE: {field_name}")
                log_message(log_file, f"    Logic: {logic}")
                log_message(log_file, f"    Expected: Make Visible (Client) rule")
                log_message(log_file, f"    Trigger: __do_you_wish_to_add_additional_email_addresses?__")
                log_message(log_file, f"    Condition: conditionalValues=['Yes'], condition='IN'")
                log_message(log_file, f"    Also needs: Make Mandatory (Client) rule")
                log_message(log_file, "")

        # Email ID - should have Make Visible and Make Mandatory rules
        if field_name == 'Email ID':
            if not any(r['rule_name'] in ['Make Visible (Client)', 'Make Invisible (Client)'] for r in rules):
                log_message(log_file, f"  MISSING RULE: {field_name}")
                log_message(log_file, f"    Logic: {logic}")
                log_message(log_file, f"    Expected: Make Visible (Client) rule")
                log_message(log_file, f"    Trigger: __concerned_email_addresses?__")
                log_message(log_file, f"    Condition: conditionalValues=['Yes'], condition='IN'")
                log_message(log_file, f"    Also needs: Make Mandatory (Client) rule")
                log_message(log_file, "")

def process_fields(input_file: str, output_file: str, log_file: str):
    """
    Main processing function to add conditional logic to fields.
    """
    # Initialize log file
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("=== BASIC DETAILS CONDITIONAL LOGIC PROCESSING LOG ===\n")
        f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    # Read input
    with open(input_file, 'r', encoding='utf-8') as f:
        fields = json.load(f)

    log_message(log_file, f"Loaded {len(fields)} fields from {input_file}\n")

    # Analyze dependencies
    log_message(log_file, "=== ANALYZING FIELD DEPENDENCIES ===\n")
    dependencies = analyze_dependencies(fields)

    for field_name, dep_info in dependencies.items():
        if dep_info['patterns']:
            log_message(log_file, f"  {field_name}: {', '.join(dep_info['patterns'])}")
    log_message(log_file, "")

    # Process each field
    log_message(log_file, "=== ADDING CONDITIONAL LOGIC TO RULES ===\n")

    processed_count = 0
    for field in fields:
        field_name = field['field_name']
        logic = field.get('logic', '')
        rules = field.get('rules', [])

        if rules:
            for rule in rules:
                original_rule = json.dumps(rule, indent=2)
                rule = add_conditional_logic_to_rule(rule, log_file, field_name, logic, dependencies)
                new_rule = json.dumps(rule, indent=2)

                if original_rule != new_rule:
                    processed_count += 1

    log_message(log_file, f"Processed {processed_count} rules with conditional logic\n")

    # Check for missing rules
    check_missing_rules(fields, log_file)

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(fields, f, indent=2, ensure_ascii=False)

    log_message(log_file, f"\n=== PROCESSING COMPLETE ===")
    log_message(log_file, f"Output written to: {output_file}")
    log_message(log_file, f"Total fields: {len(fields)}")
    log_message(log_file, f"Fields with rules: {sum(1 for f in fields if f.get('rules'))}")
    log_message(log_file, f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    input_file = '/home/samart/project/doc-parser/output/conditional_logic/temp/Basic_Details_fields_input.json'
    output_file = '/home/samart/project/doc-parser/output/conditional_logic/temp/Basic_Details_conditional_logic_output.json'
    log_file = '/home/samart/project/doc-parser/output/conditional_logic/temp/Basic_Details_conditional_logic_log.txt'

    process_fields(input_file, output_file, log_file)

    print(f"Processing complete!")
    print(f"Output: {output_file}")
    print(f"Log: {log_file}")
