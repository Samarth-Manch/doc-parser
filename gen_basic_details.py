import json

# Read input
with open("output/ph/runs/6/rule_placement/temp/Basic_Details_input.json") as f:
    data = json.load(f)

fields = data["fields_with_logic"]
panel = "Basic Details"
panel_norm = "basicdetails"

def normalize_varname(field_name):
    result = []
    for ch in field_name.lower():
        if ch.isalnum():
            result.append(ch)
    return "".join(result)

# Track variable name counts for dedup
varname_counts = {}
output = []
log_lines = []

for field in fields:
    fname = field["field_name"]
    ftype = field["type"]
    mandatory = field["mandatory"]
    logic = field["logic"]

    # Generate base variable name
    base = normalize_varname(fname) + panel_norm

    # Handle dedup
    if base not in varname_counts:
        varname_counts[base] = 0
        varname = "_{}_".format(base)
    else:
        varname_counts[base] += 1
        varname = "_{}{}_".format(base, varname_counts[base])

    # Determine rules
    rules = []

    # Rule 1: All DROPDOWN fields get EDV Dropdown (Client)
    if ftype == "DROPDOWN":
        rules.append("EDV Dropdown (Client)")

    # Check for Convert to UPPER (Client)
    if "upper case" in logic.lower():
        rules.append("Convert to UPPER (Client)")

    # Log
    log_lines.append("Step 1: Read logic for field {}".format(fname))
    if rules:
        rule_desc = ", ".join(rules)
        log_lines.append("Step 2 complete: Extracted rules for field {}: {}".format(fname, rule_desc))
    else:
        if "display" in logic.lower() and ("column" in logic.lower() or "value selected" in logic.lower()):
            reason = "(none - derivation/display from dropdown, handled by later stages)"
        elif "validate" in logic.lower() and ("edv" in logic.lower() or "attribute" in logic.lower()):
            reason = "(none - Validate EDV handled by Stage 4)"
        elif ftype == "LABEL":
            reason = "(none - LABEL field, visibility handled by Condition Agent)"
        elif ftype == "ARRAY_HDR":
            reason = "(none - ARRAY_HDR container, visibility handled by Condition Agent)"
        elif logic.strip() in ["(Non-Editable)", "Non mandatory and invisible"]:
            reason = "(none - static field, no matching rules)"
        elif "field length" in logic.lower() and "clear" in logic.lower():
            reason = "(none - field length/clearing, handled by other stages)"
        elif "clear" in logic.lower() and "make" not in logic.lower():
            reason = "(none - clearing logic, handled by Expression Rules stage)"
        else:
            reason = "(none - visibility/state/clearing handled by other stages)"
        log_lines.append("Step 2 complete: Extracted rules for field {}: {}".format(fname, reason))

    entry = {
        "field_name": fname,
        "type": ftype,
        "mandatory": mandatory,
        "logic": logic,
        "rules": rules,
        "variableName": varname
    }
    output.append(entry)

log_lines.append("Step 3 complete: Created skeleton rule structure for all fields")

# Write output JSON
with open("output/ph/runs/6/rule_placement/temp/Basic_Details_rules.json", "w") as f:
    json.dump(output, f, indent=4)

# Append to log file
with open("output/ph/runs/6/rule_placement/temp/______________log.txt", "a") as f:
    f.write("\n".join(log_lines) + "\n")

# Print summary
dropdown_count = sum(1 for e in output if "EDV Dropdown (Client)" in e["rules"])
upper_count = sum(1 for e in output if "Convert to UPPER (Client)" in e["rules"])
no_rules = sum(1 for e in output if len(e["rules"]) == 0)
print("Total fields: {}".format(len(output)))
print("Fields with EDV Dropdown (Client): {}".format(dropdown_count))
print("Fields with Convert to UPPER (Client): {}".format(upper_count))
print("Fields with no rules: {}".format(no_rules))

dupes = {k: v for k, v in varname_counts.items() if v > 0}
print("\nDuplicate field names (with dedup counts): {}".format(len(dupes)))
for k, v in dupes.items():
    print("  {}: {} occurrences".format(k, v+1))
