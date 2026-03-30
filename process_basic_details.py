import json
import re

# Read input
with open('output/ph/runs/7/rule_placement/temp/Basic_Details_input.json', 'r') as f:
    data = json.load(f)

fields = data['fields_with_logic']
panel_name = "Basic Details"
panel_suffix = re.sub(r'[^a-z0-9]', '', panel_name.lower())  # "basicdetails"

def normalize(name):
    """Remove all non-alphanumeric chars, lowercase."""
    return re.sub(r'[^a-z0-9]', '', name.lower())

# Track variable name occurrences for dedup
var_seen = {}  # base_var -> count of times seen

# Parent dropdowns that have dependent DROPDOWN children in same panel
# Based on manual analysis of clearing triggers in field logics
execute_parents = {
    "Company Type",
    "Owner Division",
    "Select the PH level to be created"
}

output = []
log_lines = []

for field in fields:
    fname = field['field_name']
    ftype = field['type']
    mandatory = field['mandatory']
    logic = field['logic']

    # Skip PANEL fields
    if ftype == "PANEL":
        continue

    # Generate variable name with dedup
    base_var = "_{}{}_".format(normalize(fname), panel_suffix)
    if base_var in var_seen:
        var_seen[base_var] += 1
        var_name = "_{}{}{}_".format(normalize(fname), panel_suffix, var_seen[base_var])
    else:
        var_seen[base_var] = 0
        var_name = base_var

    # Determine rules
    rules = []
    reasons = []

    # Rule 1: All DROPDOWNs get EDV Dropdown (Client)
    if ftype == "DROPDOWN":
        rules.append("EDV Dropdown (Client)")
        # Determine if cascading or simple
        logic_lower = logic.lower()
        if any(kw in logic_lower for kw in ["based on", "depends on", "filtered by"]):
            reasons.append("cascading DROPDOWN")
        else:
            reasons.append("DROPDOWN")

    # Rule 2: Parent dropdowns with dependent dropdown children get EXECUTE
    if fname in execute_parents and ftype == "DROPDOWN":
        rules.append("EXECUTE")
        reasons.append("parent with dependent dropdown children needing clearing")

    # Check for "Upper Case" in logic (for TEXT fields)
    if ftype == "TEXT" and "upper case" in logic.lower():
        rules.append("Convert to UPPER (Client)")
        reasons.append("Upper Case conversion specified in logic")

    # Build reason string for log
    if not rules:
        if ftype == "DROPDOWN":
            reason_str = "DROPDOWN, no additional rules"
        elif ftype == "TEXT":
            if "non-editable" in logic.lower() or "non - editable" in logic.lower():
                reason_str = "TEXT field, non-editable/derived, handled by later stages"
            elif "display" in logic.lower() or "column" in logic.lower():
                reason_str = "TEXT field, derivation handled by later stages"
            elif "clear" in logic.lower():
                reason_str = "TEXT field, clearing/visibility handled by later stages"
            else:
                reason_str = "TEXT field, no applicable rules from rule list"
        elif ftype == "LABEL":
            reason_str = "LABEL field, visibility handled by Condition Agent"
        elif ftype == "ARRAY_HDR":
            reason_str = "ARRAY_HDR field, visibility handled by Condition Agent"
        else:
            reason_str = "{} field, no applicable rules".format(ftype)
    else:
        reason_str = ", ".join(reasons)

    log_lines.append("Step 1: Read logic for field {}".format(fname))
    log_lines.append("Step 2 complete: Extracted rules for field {}: {} ({})".format(
        fname, rules if rules else "[]", reason_str))

    output.append({
        "field_name": fname,
        "type": ftype,
        "mandatory": mandatory,
        "logic": logic,
        "rules": rules,
        "variableName": var_name
    })

log_lines.append("Step 3 complete: Created skeleton rule structure for all fields")

# Write output
with open('output/ph/runs/7/rule_placement/temp/Basic_Details_rules.json', 'w') as f:
    json.dump(output, f, indent=4)

# Write log (append mode)
with open('output/ph/runs/7/rule_placement/temp/______________log.txt', 'a') as f:
    f.write('\n'.join(log_lines) + '\n')

# Summary
total = len(output)
with_rules = sum(1 for f in output if f['rules'])
dropdowns = sum(1 for f in output if f['type'] == 'DROPDOWN')
execute_count = sum(1 for f in output if 'EXECUTE' in f.get('rules', []))
upper_count = sum(1 for f in output if 'Convert to UPPER (Client)' in f.get('rules', []))

print("Total fields processed: {}".format(total))
print("Fields with rules: {}".format(with_rules))
print("  - Dropdowns (EDV Dropdown): {}".format(dropdowns))
print("  - EXECUTE rules: {}".format(execute_count))
print("  - Convert to UPPER: {}".format(upper_count))
print("Fields with empty rules: {}".format(total - with_rules))

# Print variable name dedup info
dupes = {k: v for k, v in var_seen.items() if v > 0}
if dupes:
    print("\nDuplicate field names resolved ({} base names):".format(len(dupes)))
    for base, count in sorted(dupes.items()):
        print("  {} -> {} occurrences".format(base, count + 1))
