#!/usr/bin/env python3
"""
Process Bank Details panel and add conditional logic to rules.
"""

import json
from typing import List, Dict, Any
from datetime import datetime

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

        # Skip if no source fields (can't have conditions without source)
        if not source_fields:
            # Check for "Always Disabled" / "Non editable" cases
            if "non editable" in logic.lower() or "non-editable" in logic.lower():
                if rule_name == "Disable Field (Client)":
                    rule["conditionalValues"] = ["Disable"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    log_message(log_file, f"  ✓ Added: Always disabled condition")
                    log_message(log_file, f"    conditionalValues: {rule['conditionalValues']}")
                    log_message(log_file, f"    condition: {rule['condition']}")
                else:
                    log_message(log_file, f"  ⊘ No conditional logic needed (no source fields)")
            else:
                log_message(log_file, f"  ⊘ No conditional logic needed (no source fields)")
            continue

        # Determine conditional logic based on rule type and logic text
        conditional_added = False

        # --- "Please choose the option" source field conditions ---
        if "__please_choose_the_option__" in source_fields:

            # Cancelled Cheque Image field
            if field_name == "Cancelled Cheque Image":
                if rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Cancelled Cheque"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Cancelled Cheque condition")

            # Passbook/Bank Letter field
            elif field_name == "Passbook/Bank Letter":
                if rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Passbook Front Page (India Domestic and International)"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Passbook Front Page condition")

            # IFSC and Account Number manual entry label
            elif field_name == "Please enter IFSC and Account Number manually":
                if rule_name == "Make Visible (Client)":
                    rule["conditionalValues"] = ["Passbook Front Page (India Domestic and International)"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Passbook Front Page condition")

            # IFSC Code field
            elif field_name == "IFSC Code":
                if rule_name == "Disable Field (Client)":
                    # Non-editable if cancelled cheque is selected
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Cancelled Cheque disable condition")
                elif rule_name == "Enable Field (Client)":
                    # Editable for other options
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: NOT Cancelled Cheque enable condition")
                elif rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    # Visible/mandatory for Cancelled Cheque or Passbook
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)", "Passbook Front Page (India Domestic and International)"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Cancelled Cheque OR Passbook condition")
                elif rule_name in ["Make Invisible (Client)", "Make Non Mandatory (Client)"]:
                    # Invisible/non-mandatory for other options
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)", "Passbook Front Page (India Domestic and International)"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: NOT (Cancelled Cheque OR Passbook) condition")

            # Bank Account Number field (same logic as IFSC)
            elif field_name == "Bank Account Number":
                if rule_name == "Disable Field (Client)":
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Cancelled Cheque disable condition")
                elif rule_name == "Enable Field (Client)":
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: NOT Cancelled Cheque enable condition")
                elif rule_name in ["Make Visible (Client)", "Make Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)", "Passbook Front Page (India Domestic and International)"]
                    rule["condition"] = "IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: Cancelled Cheque OR Passbook condition")
                elif rule_name in ["Make Invisible (Client)", "Make Non Mandatory (Client)"]:
                    rule["conditionalValues"] = ["Cancelled Cheque (India Domestic)", "Passbook Front Page (India Domestic and International)"]
                    rule["condition"] = "NOT_IN"
                    rule["conditionValueType"] = "TEXT"
                    conditional_added = True
                    log_message(log_file, f"  ✓ Added: NOT (Cancelled Cheque OR Passbook) condition")

        # Rules without conditions (e.g., OCR, Validate Bank Account, etc.)
        if not conditional_added:
            # Check if it's a validation/OCR rule that doesn't need conditions
            if rule_name in ["Cheque OCR", "Validate Bank Account", "Validate External Data Value (Client)"]:
                log_message(log_file, f"  ⊘ No conditional logic needed (validation/OCR rule)")
            else:
                log_message(log_file, f"  ⊘ No conditional logic added (no matching pattern)")

        if conditional_added:
            log_message(log_file, f"    conditionalValues: {rule.get('conditionalValues', [])}")
            log_message(log_file, f"    condition: {rule.get('condition', '')}")

    return field

def main():
    """Main processing function."""
    input_file = "output/conditional_logic/temp/Bank_Details_fields_input.json"
    output_file = "output/conditional_logic/temp/Bank_Details_conditional_logic_output.json"
    log_file = "output/conditional_logic/temp/Bank_Details_conditional_logic_log.txt"

    # Initialize log file
    with open(log_file, 'w') as f:
        f.write(f"Bank Details - Conditional Logic Processing Log\n")
        f.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*80}\n")

    log_message(log_file, f"Reading input from: {input_file}")

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
