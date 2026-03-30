import json
import re

# Read input
with open("output/ph/runs/8/rule_placement/temp/Basic_Details_input.json") as f:
    data = json.load(f)

fields = data["fields_with_logic"]
panel_name = "Basic Details"

def normalize(name):
    """Remove all non-alphanumeric chars, lowercase."""
    return re.sub(r"[^a-z0-9]", "", name.lower())

panel_norm = normalize(panel_name)

seen = {}
result = []
log_lines = []

for field in fields:
    fname = field["field_name"]
    ftype = field["type"]
    mandatory = field["mandatory"]
    logic = field["logic"]

    # Skip PANEL type fields
    if ftype == "PANEL":
        continue

    # Step 1: Read logic
    log_lines.append('Step 1: Read logic for field "' + fname + '"')

    # Determine rules
    rules = []

    # Rule 1: All dropdowns get EDV Dropdown (Client)
    if ftype == "DROPDOWN":
        rules.append("EDV Dropdown (Client)")

    # Rule: Upper Case mentioned in logic
    if re.search(r"upper\s*case", logic, re.IGNORECASE):
        rules.append("Convert to UPPER (Client)")

    # Rule: Lower Case mentioned in logic
    if re.search(r"lower\s*case", logic, re.IGNORECASE):
        rules.append("Convert To Lower Case (Client)")

    # Step 2: Log extracted rules
    if rules:
        log_lines.append('Step 2 complete: Extracted rules for field "' + fname + '": ' + ", ".join(rules))
    else:
        if re.search(r"derived|derivation", logic, re.IGNORECASE):
            log_lines.append('Step 2 complete: Extracted rules for field "' + fname + '": (none - derivation handled by later stages)')
        elif re.search(r"non[\s-]*editable", logic, re.IGNORECASE) and not re.search(r"(make\s+visible|make\s+invisible)", logic, re.IGNORECASE):
            log_lines.append('Step 2 complete: Extracted rules for field "' + fname + '": (none - Non-Editable state handled by Condition Agent)')
        elif re.search(r"(make\s+visible|make\s+invisible|mandatory|visible|invisible)", logic, re.IGNORECASE):
            log_lines.append('Step 2 complete: Extracted rules for field "' + fname + '": (none - visibility/state handled by Condition Agent)')
        else:
            log_lines.append('Step 2 complete: Extracted rules for field "' + fname + '": (none)')

    # Generate variable name
    base = normalize(fname) + panel_norm
    if base in seen:
        seen[base] += 1
        varname = "_" + base + str(seen[base]) + "_"
    else:
        seen[base] = 0
        varname = "_" + base + "_"

    result.append({
        "field_name": fname,
        "type": ftype,
        "mandatory": mandatory,
        "logic": logic,
        "rules": rules,
        "variableName": varname
    })

log_lines.append("Step 3 complete: Created skeleton rule structure for all fields")

# Write output
with open("output/ph/runs/8/rule_placement/temp/Basic_Details_rules.json", "w") as f:
    json.dump(result, f, indent=2)

# Append to log file
with open("output/ph/runs/8/rule_placement/temp/______________log.txt", "a") as f:
    f.write("\n".join(log_lines) + "\n")

# Summary
dropdown_count = sum(1 for r in result if r["type"] == "DROPDOWN")
upper_count = sum(1 for r in result if "Convert to UPPER (Client)" in r["rules"])
no_rules = sum(1 for r in result if not r["rules"])
print("Total fields:", len(result))
print("Dropdowns (EDV Dropdown Client):", dropdown_count)
print("Upper Case fields:", upper_count)
print("Fields with no rules:", no_rules)

# Show duplicate variable names for verification
dupes = {k: v for k, v in seen.items() if v > 0}
print("\nDuplicate field names requiring numbering:", len(dupes))
for k, count in sorted(dupes.items()):
    print("  " + k + ": " + str(count + 1) + " occurrences")
