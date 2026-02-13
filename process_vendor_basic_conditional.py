import json
import sys
from datetime import datetime

# Read input
with open('output/conditional_logic/temp/Vendor_Basic_Details_fields_input.json', 'r') as f:
    fields = json.load(f)

log_lines = []

def log(message):
    log_lines.append(message)
    print(message)

log(f"\n=== Processing {len(fields)} fields ===\n")

# Process each field
for field_idx, field in enumerate(fields, 1):
    field_name = field.get('field_name', 'Unknown')
    logic = field.get('logic', '')
    rules = field.get('rules', [])

    log(f"\n[Field {field_idx}/{len(fields)}] {field_name}")
    log(f"Type: {field.get('type', 'Unknown')}")
    log(f"Logic: {logic}")
    log(f"Number of rules: {len(rules)}")

    if not rules:
        log("  → No rules to process, skipping")
        continue

    # Analyze logic for conditional patterns
    logic_lower = logic.lower()

    # Process each rule
    for rule_idx, rule in enumerate(rules, 1):
        rule_name = rule.get('rule_name', 'Unknown')
        log(f"\n  Rule {rule_idx}: {rule_name}")

        # Determine if this rule needs conditional logic
        needs_conditional = False
        conditional_values = []
        condition_operator = None
        condition_value_type = "TEXT"

        # Field: Business Registration Number Available?
        if field_name == "Business Registration Number Available?":
            if rule_name == "Make Invisible (Client)":
                # Hidden for India-Domestic
                log("    → Detecting: Hidden for India-Domestic context")
                # This appears to be context-based, not field-value based
                # Skip adding conditional logic for now
                log("    → Skipping: Context-based condition (not field-value based)")
            elif rule_name == "Make Visible (Client)":
                # Visible for India-Import, International-Domestic, International-Import
                log("    → Detecting: Visible for specific contexts")
                log("    → Skipping: Context-based condition (not field-value based)")
            elif rule_name == "Make Non Mandatory (Client)":
                log("    → Detecting: Non-mandatory for India-Domestic")
                log("    → Skipping: Context-based condition (not field-value based)")

        # Field: Business Registration Number
        elif field_name == "Business Registration Number":
            if rule_name == "Make Visible (Client)":
                # If "Additional Registration Number Applicable?" value is YES
                log("    → Detecting: Visible when source field = 'YES'")
                needs_conditional = True
                conditional_values = ["YES"]
                condition_operator = "IN"
                log(f"    → Adding: condition=IN, conditionalValues={conditional_values}")

            elif rule_name == "Make Invisible (Client)":
                # Hidden when not YES or for India-Domestic
                log("    → Detecting: Hidden when source field != 'YES'")
                needs_conditional = True
                conditional_values = ["YES"]
                condition_operator = "NOT_IN"
                log(f"    → Adding: condition=NOT_IN, conditionalValues={conditional_values}")

            elif rule_name == "Make Mandatory (Client)":
                # Mandatory when source field = YES
                log("    → Detecting: Mandatory when source field = 'YES'")
                needs_conditional = True
                conditional_values = ["YES"]
                condition_operator = "IN"
                log(f"    → Adding: condition=IN, conditionalValues={conditional_values}")

            elif rule_name == "Make Non Mandatory (Client)":
                # Non-mandatory when not YES
                log("    → Detecting: Non-mandatory when source field != 'YES'")
                needs_conditional = True
                conditional_values = ["YES"]
                condition_operator = "NOT_IN"
                log(f"    → Adding: condition=NOT_IN, conditionalValues={conditional_values}")

        # Field: Title
        elif field_name == "Title":
            if rule_name == "EDV Dropdown (Client)":
                # Derived from PAN - logic describes derivation rules, not conditions
                log("    → Detecting: EDV dropdown with derivation logic")
                log("    → Skipping: Derivation logic, not conditional visibility/behavior")

        # Add conditional fields if needed
        if needs_conditional:
            rule['conditionalValues'] = conditional_values
            rule['condition'] = condition_operator
            rule['conditionValueType'] = condition_value_type
            log(f"    ✓ Added conditional logic to rule")
        else:
            log(f"    → No conditional logic needed for this rule")

log(f"\n\n=== Processing Complete ===")
log(f"Total fields processed: {len(fields)}")
log(f"Completed at: {datetime.now().isoformat()}")

# Write output
output_path = 'output/conditional_logic/temp/Vendor_Basic_Details_conditional_logic_output.json'
with open(output_path, 'w') as f:
    json.dump(fields, f, indent=2)

log(f"\nOutput written to: {output_path}")

# Append to log file
with open('output/conditional_logic/temp/Vendor_Basic_Details_conditional_logic_log.txt', 'a') as f:
    f.write('\n'.join(log_lines))
    f.write('\n')

print(f"\n✓ Successfully processed {len(fields)} fields")
print(f"✓ Output saved to: {output_path}")
print(f"✓ Log saved to: output/conditional_logic/temp/Vendor_Basic_Details_conditional_logic_log.txt")
