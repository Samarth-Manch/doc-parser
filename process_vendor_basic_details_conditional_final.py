#!/usr/bin/env python3
"""
Conditional Logic Agent for Vendor Basic Details Panel
Adds conditional logic to rules and populates source/destination fields.
"""

import json
from datetime import datetime

def log_message(log_file, message):
    """Write a timestamped message to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)

def analyze_field_dependencies(fields):
    """
    Analyze ALL fields' logic to find dependencies.
    Returns: {source_variable: [dest_variable1, dest_variable2, ...]}
    """
    dependencies = {}

    for field in fields:
        field_name = field.get('field_name', '')
        variable_name = field.get('variableName', '')
        logic = field.get('logic', '').lower()

        # Check if this field's logic references other fields
        for other_field in fields:
            if other_field['field_name'] == field_name:
                continue

            other_name = other_field.get('field_name', '').lower()
            other_var = other_field.get('variableName', '')

            # Check if other_field is mentioned in this field's logic
            if other_name and other_name in logic:
                # other_field is SOURCE, this field is DESTINATION
                if other_var not in dependencies:
                    dependencies[other_var] = []
                if variable_name not in dependencies[other_var]:
                    dependencies[other_var].append(variable_name)

    return dependencies

def process_fields(fields, log_file):
    """Main processing function."""

    log_message(log_file, "=" * 80)
    log_message(log_file, "Vendor Basic Details - Conditional Logic Processing")
    log_message(log_file, "=" * 80)

    # Step 1: Analyze all field dependencies
    log_message(log_file, "\nSTEP 1: Cross-field dependency analysis")
    log_message(log_file, "-" * 80)
    dependencies = analyze_field_dependencies(fields)

    log_message(log_file, f"\nFound {len(dependencies)} fields with dependencies:")
    for source, destinations in dependencies.items():
        log_message(log_file, f"  {source} triggers: {', '.join(destinations)}")

    # Step 2: Process each field
    log_message(log_file, "\n\nSTEP 2: Processing each field")
    log_message(log_file, "-" * 80)

    for field in fields:
        field_name = field.get('field_name', '')
        variable_name = field.get('variableName', '')
        logic = field.get('logic', '')
        rules = field.get('rules', [])

        log_message(log_file, f"\n\nField: {field_name}")
        log_message(log_file, f"Variable: {variable_name}")
        log_message(log_file, f"Logic: {logic}")
        log_message(log_file, f"Rules: {len(rules)}")

        if not rules:
            log_message(log_file, "  → No rules, skipping")
            continue

        # Process each rule
        for rule in rules:
            rule_name = rule.get('rule_name', '')
            log_message(log_file, f"\n  Processing rule: {rule_name}")

            # Handle specific fields
            if field_name == "Business Registration Number Available?":
                # This field's visibility depends on vendor type from Basic Details panel
                # Logic: "Visible and editable for India-Import, International-Domestic, International-Import.
                #         Hidden and non-mandatory for India-Domestic"

                if rule_name == "Make Visible (Client)":
                    log_message(log_file, "    → Visible for Import vendors (cross-panel dependency)")
                    rule['source_fields'] = ["__vendor_domestic_or_import__"]
                    rule['destination_fields'] = [variable_name]
                    rule['conditionalValues'] = ["Import"]
                    rule['condition'] = "IN"
                    rule['conditionValueType'] = "TEXT"
                    rule['_reasoning'] = "Visible when vendor is Import type. Source: __vendor_domestic_or_import__ from Basic Details panel. Destination: this field."
                    log_message(log_file, f"    ✓ Added conditional: {rule['condition']} {rule['conditionalValues']}")

                elif rule_name == "Make Invisible (Client)":
                    log_message(log_file, "    → Hidden for Domestic vendors")
                    rule['source_fields'] = ["__vendor_domestic_or_import__"]
                    rule['destination_fields'] = [variable_name]
                    rule['conditionalValues'] = ["Domestic"]
                    rule['condition'] = "IN"
                    rule['conditionValueType'] = "TEXT"
                    rule['_reasoning'] = "Hidden when vendor is Domestic type (India-Domestic). Source: __vendor_domestic_or_import__ from Basic Details panel. Destination: this field."
                    log_message(log_file, f"    ✓ Added conditional: {rule['condition']} {rule['conditionalValues']}")

                elif rule_name == "Make Mandatory (Client)":
                    log_message(log_file, "    → Mandatory for Import vendors")
                    rule['source_fields'] = ["__vendor_domestic_or_import__"]
                    rule['destination_fields'] = [variable_name]
                    rule['conditionalValues'] = ["Import"]
                    rule['condition'] = "IN"
                    rule['conditionValueType'] = "TEXT"
                    rule['_reasoning'] = "Mandatory when vendor is Import type. Source: __vendor_domestic_or_import__ from Basic Details panel. Destination: this field."
                    log_message(log_file, f"    ✓ Added conditional: {rule['condition']} {rule['conditionalValues']}")

                elif rule_name == "Make Non Mandatory (Client)":
                    log_message(log_file, "    → Non-mandatory for Domestic vendors")
                    rule['source_fields'] = ["__vendor_domestic_or_import__"]
                    rule['destination_fields'] = [variable_name]
                    rule['conditionalValues'] = ["Domestic"]
                    rule['condition'] = "IN"
                    rule['conditionValueType'] = "TEXT"
                    rule['_reasoning'] = "Non-mandatory when vendor is Domestic type. Source: __vendor_domestic_or_import__ from Basic Details panel. Destination: this field."
                    log_message(log_file, f"    ✓ Added conditional: {rule['condition']} {rule['conditionalValues']}")

            elif field_name == "Business Registration Number":
                # Logic: "If the field 'Additional Registration Number Applicable?' value is YES then Visible,
                #         mandatory and editable for India-Import, International-Domestic, International-Import
                #         otherwise Hidden and non-mandatory for India-Domestic"
                # Note: The field name in logic says "Additional Registration Number Applicable?" but in the panel
                # it's "Business Registration Number Available?"

                # This field needs rules to be added by Rule Type Placement Agent first
                # Since it has no rules in the input, we just log it
                log_message(log_file, "    → No rules present. This field needs rules from Rule Type Placement Agent.")
                log_message(log_file, "    → Logic indicates dependency on 'Business Registration Number Available?' field")

    log_message(log_file, "\n\n" + "=" * 80)
    log_message(log_file, "Processing Complete")
    log_message(log_file, "=" * 80)

    return fields

def main():
    input_file = "output/conditional_logic/temp/Vendor_Basic_Details_fields_input.json"
    output_file = "output/conditional_logic/temp/Vendor_Basic_Details_conditional_logic_output.json"
    log_file = "output/conditional_logic/temp/Vendor_Basic_Details_conditional_logic_log.txt"

    # Clear log file
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("")

    # Load input
    with open(input_file, 'r', encoding='utf-8') as f:
        fields = json.load(f)

    # Process
    processed_fields = process_fields(fields, log_file)

    # Save output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_fields, f, indent=2, ensure_ascii=False)

    log_message(log_file, f"\n✓ Output written to: {output_file}")
    print(f"\n✓ Successfully processed {len(processed_fields)} fields")
    print(f"✓ Output: {output_file}")
    print(f"✓ Log: {log_file}")

if __name__ == "__main__":
    main()
