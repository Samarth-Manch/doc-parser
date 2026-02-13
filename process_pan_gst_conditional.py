#!/usr/bin/env python3
"""
Process PAN and GST Details panel and add conditional logic to rules.
"""

import json
from typing import List, Dict, Any
from datetime import datetime
import os

def log_message(log_file, message):
    """Write a timestamped message to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

def add_conditional_logic(field: Dict[str, Any], log_file: str) -> Dict[str, Any]:
    """
    Add conditional logic to rules based on field logic text.

    Args:
        field: Field dictionary with rules
        log_file: Path to log file

    Returns:
        Updated field dictionary with conditional logic added to rules
    """
    field_name = field.get("field_name", "Unknown")
    logic = field.get("logic", "")
    rules = field.get("rules", [])

    log_message(log_file, f"\n{'='*80}")
    log_message(log_file, f"Processing field: {field_name}")
    log_message(log_file, f"Logic: {logic}")
    log_message(log_file, f"Number of rules: {len(rules)}")

    # Process each rule
    for rule in rules:
        rule_name = rule.get("rule_name", "Unknown")
        source_fields = rule.get("source_fields", [])

        log_message(log_file, f"\n  Rule: {rule_name}")
        log_message(log_file, f"  Source fields: {source_fields}")

        conditional_added = False

        # --- Handle "Non-editable" / "Non editable" fields ---
        if "non-editable" in logic.lower() or "non editable" in logic.lower():
            if rule_name == "Disable Field (Client)":
                rule["conditionalValues"] = ["Disable"]
                rule["condition"] = "NOT_IN"
                rule["conditionValueType"] = "TEXT"
                conditional_added = True
                log_message(log_file, f"  ✓ Added: Always disabled condition (non-editable field)")

        # --- Fields conditional on "Please select GST option" ---
        if "__please_select_gst_option__" in str(source_fields):

            # GSTIN IMAGE - visible/mandatory when "Yes"
            if field_name == "GSTIN IMAGE":
                if rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Yes"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option = 'Yes' condition")
                elif rule_name in ["Make Invisible (Client)", "Make Non Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Yes"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option != 'Yes' condition")

            # GSTIN - visible/mandatory when "Yes"
            elif field_name == "GSTIN":
                if rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Yes"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option = 'Yes' condition")
                elif rule_name in ["Make Invisible (Client)", "Make Non Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Yes"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option != 'Yes' condition")

            # GST-related fields (Trade Name, Legal Name, etc.) - visible when "Yes"
            elif field_name in ["Trade Name", "Legal Name", "Reg Date", "Type", "Building Number",
                               "Street", "City", "District", "State", "Pin Code"]:
                if rule_name == "Make Visible (Client)":
                    rule["conditionalValues"] = ["Yes"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option = 'Yes' condition")
                elif rule_name == "Make Invisible (Client)":
                    rule["conditionalValues"] = ["Yes"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option != 'Yes' condition")

            # Upload Declaration - visible/mandatory when "No"
            elif field_name == "Upload Declaration":
                if rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    rule["conditionalValues"] = ["No"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option = 'No' condition")
                elif rule_name in ["Make Invisible (Client)", "Make Non Mandatory (Client)"]:
                    rule["conditionalValues"] = ["No"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: GST option != 'No' condition")

        # --- Check logic text for conditional patterns ---
        logic_lower = logic.lower()

        # "if the field ... values is yes then visible and mandatory"
        if "if the field" in logic_lower and "yes" in logic_lower:
            if "visible and mandatory" in logic_lower or "mandatory and visible" in logic_lower:
                if rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    if not conditional_added:  # Only add if not already added
                        rule["conditionalValues"] = ["Yes"]
                        rule["condition"] = "IN"
                        rule["conditionValueType"] = "TEXT"
                        conditional_added = True
                        log_message(log_file, f"  ✓ Added: Field = 'Yes' condition (from logic text)")
                elif rule_name in ["Make Invisible (Client)", "Make Non Mandatory (Client)"]:
                    if not conditional_added:
                        rule["conditionalValues"] = ["Yes"]
                        rule["condition"] = "NOT_IN"
                        rule["conditionValueType"] = "TEXT"
                        conditional_added = True
                        log_message(log_file, f"  ✓ Added: Field != 'Yes' condition (from logic text)")

        # "if the field ... values is no then visible and mandatory"
        if "if the field" in logic_lower and "no" in logic_lower and "then visible" in logic_lower:
            if rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                if not conditional_added:
                    rule["conditionalValues"] = ["No"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Field = 'No' condition (from logic text)")
            elif rule_name in ["Make Invisible (Client)", "Make Non Mandatory (Client)"]:
                if not conditional_added:
                    rule["conditionalValues"] = ["No"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Field != 'No' condition (from logic text)")

        # Rules without conditions (OCR, Validation, etc.)
        if not conditional_added:
            # Check if it's a validation/OCR/conversion rule that doesn't need conditions
            if rule_name in ["PAN OCR", "GSTIN OCR", "Validate PAN", "Validate GSTIN",
                           "Validate GSTIN With PAN", "Convert to UPPER (Client)",
                           "Validate External Data Value (Client)"]:
                log_message(log_file, f"  ⊘ No conditional logic needed (validation/OCR/conversion rule)")
            elif not source_fields or all(sf == "-1" for sf in source_fields):
                log_message(log_file, f"  ⊘ No conditional logic needed (no valid source fields)")
            else:
                log_message(log_file, f"  ⊘ No conditional logic added (no matching pattern)")

        if conditional_added:
            log_message(log_file, f"    conditionalValues: {rule.get('conditionalValues', [])}")
            log_message(log_file, f"    condition: {rule.get('condition', '')}")
            log_message(log_file, f"    conditionValueType: {rule.get('conditionValueType', '')}")

    return field

def main():
    """Main processing function."""
    # Create output directory if it doesn't exist
    os.makedirs("output/conditional_logic/temp", exist_ok=True)

    input_file = "output/conditional_logic/temp/PAN_and_GST_Details_fields_input.json"
    output_file = "output/conditional_logic/temp/PAN_and_GST_Details_conditional_logic_output.json"
    log_file = "output/conditional_logic/temp/PAN_and_GST_Details_conditional_logic_log.txt"

    # Initialize log file
    with open(log_file, 'w') as f:
        f.write(f"PAN and GST Details - Conditional Logic Processing Log\n")
        f.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*80}\n")

    log_message(log_file, f"Reading input from: {input_file}")

    # Check if input file exists
    if not os.path.exists(input_file):
        # Use the validate_edv output as input
        alt_input = "output/validate_edv/temp/PAN_and_GST_Details_validate_edv_output.json"
        if os.path.exists(alt_input):
            log_message(log_file, f"Input file not found, using: {alt_input}")
            input_file = alt_input
        else:
            error_msg = f"ERROR: Input file not found: {input_file}"
            log_message(log_file, error_msg)
            print(error_msg)
            return

    # Read input
    with open(input_file, 'r') as f:
        fields = json.load(f)

    log_message(log_file, f"Total fields to process: {len(fields)}")

    # Process each field
    processed_fields = []
    for field in fields:
        processed_field = add_conditional_logic(field, log_file)
        processed_fields.append(processed_field)

    # Write output
    log_message(log_file, f"\n{'='*80}")
    log_message(log_file, f"Writing output to: {output_file}")

    with open(output_file, 'w') as f:
        json.dump(processed_fields, f, indent=2)

    log_message(log_file, f"✓ Processing complete!")
    log_message(log_file, f"Processed {len(processed_fields)} fields")

    print(f"✓ Processing complete!")
    print(f"  Input:  {input_file}")
    print(f"  Output: {output_file}")
    print(f"  Log:    {log_file}")

if __name__ == "__main__":
    main()
