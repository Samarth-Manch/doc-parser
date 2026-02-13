#!/usr/bin/env python3
"""
Process Vendor Duplicity Details panel fields and add conditional logic.
"""

import json
from pathlib import Path
from datetime import datetime

def add_conditional_logic():
    """Add conditional logic to rules for Vendor Duplicity Details panel."""

    # File paths
    input_file = Path("output/conditional_logic/temp/Vendor_Duplicity_Details_fields_input.json")
    output_file = Path("output/conditional_logic/temp/Vendor_Duplicity_Details_conditional_logic_output.json")
    log_file = Path("output/conditional_logic/temp/Vendor_Duplicity_Details_conditional_logic_log.txt")

    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Initialize log
    log_messages = []

    def log(message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        log_messages.append(log_msg)
        print(log_msg)

    log("=" * 80)
    log("Processing Vendor Duplicity Details Panel - Conditional Logic")
    log("=" * 80)

    # Read input
    log(f"Reading input from: {input_file}")
    with open(input_file, 'r') as f:
        fields = json.load(f)

    log(f"Found {len(fields)} fields to process")

    # Process each field
    processed_fields = []

    for field in fields:
        field_name = field.get("field_name", "Unknown")
        field_type = field.get("type", "Unknown")
        logic = field.get("logic", "")
        rules = field.get("rules", [])

        log("")
        log("-" * 80)
        log(f"Processing field: {field_name}")
        log(f"  Type: {field_type}")
        log(f"  Logic: {logic}")
        log(f"  Existing rules: {len(rules)}")

        # Analyze logic for conditional requirements
        if not rules:
            log(f"  ⚠ No existing rules to add conditional logic to")

            # For Vendor Duplicity Details, these are typically system-generated fields
            # that appear based on duplicate detection results
            if "duplicate" in logic.lower():
                log(f"  ℹ Field logic indicates duplicate-based visibility")
                log(f"  ℹ This field likely requires visibility rules (not present in input)")
        else:
            # Process each rule
            for idx, rule in enumerate(rules, 1):
                rule_name = rule.get("rule_name", "Unknown")
                log(f"  Processing rule {idx}: {rule_name}")

                # Check if rule already has conditional logic
                if "conditionalValues" in rule:
                    log(f"    ✓ Rule already has conditional logic")
                    continue

                # Determine if conditional logic is needed based on field logic
                needs_conditional = False
                conditional_data = None

                # Check for "Always Invisible" patterns
                if any(keyword in logic.lower() for keyword in ["always invisible", "hidden", "never visible"]):
                    needs_conditional = True
                    conditional_data = {
                        "conditionalValues": ["Invisible"],
                        "condition": "NOT_IN",
                        "conditionValueType": "TEXT"
                    }
                    log(f"    → Detected 'Always Invisible' pattern")

                # Check for "Always Disabled" patterns
                elif any(keyword in logic.lower() for keyword in ["always disabled", "non-editable", "read-only", "system-generated"]):
                    needs_conditional = True
                    conditional_data = {
                        "conditionalValues": ["Disable"],
                        "condition": "NOT_IN",
                        "conditionValueType": "TEXT"
                    }
                    log(f"    → Detected 'Always Disabled' pattern")

                # Check for conditional visibility based on duplicate status
                elif "true if duplicate" in logic.lower():
                    # This indicates field should be visible when duplicate is detected
                    # The rule would need a source field (e.g., duplicate_detected)
                    # But we need the rule to specify what it does
                    if "make visible" in rule_name.lower() or "visibility" in rule_name.lower():
                        needs_conditional = True
                        conditional_data = {
                            "conditionalValues": ["true", "True"],
                            "condition": "IN",
                            "conditionValueType": "TEXT"
                        }
                        log(f"    → Detected duplicate-based visibility condition")

                # Add conditional logic if needed
                if needs_conditional and conditional_data:
                    rule.update(conditional_data)
                    log(f"    ✓ Added conditional logic: {conditional_data['condition']} {conditional_data['conditionalValues']}")
                else:
                    log(f"    ℹ No conditional logic needed for this rule")

        # Add processed field to output
        processed_fields.append(field)

    # Write output
    log("")
    log("=" * 80)
    log(f"Writing output to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(processed_fields, f, indent=2)

    log(f"✓ Processed {len(processed_fields)} fields")

    # Write log
    log(f"Writing log to: {log_file}")
    with open(log_file, 'w') as f:
        f.write('\n'.join(log_messages))

    log("=" * 80)
    log("Processing complete!")
    log("=" * 80)

if __name__ == "__main__":
    add_conditional_logic()
