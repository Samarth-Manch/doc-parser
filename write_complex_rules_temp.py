import json

# Read inputs
with open("output/vendor_extension/runs/20/inter_panel/temp/complex_incoterms___incotermspurchaseorganizationdetails___panels.json") as f:
    panels = json.load(f)

with open("output/vendor_extension/runs/20/inter_panel/temp/complex_incoterms___incotermspurchaseorganizationdetails___refs.json") as f:
    refs = json.load(f)

# Build the clearing rule to place on the trigger field in Basic Details
# The ref says: clear _incotermspurchaseorganizationdetails_ whenever _vendornameandcodebasicdetails_ changes
# Incoterms is TEXT type, so use rffd (not rffdd)
# Condition is true since BUD says "whenever... values change" and derivation is server-side (GENERATE_ARRAY_FORM_GROUPS)
clearing_rule = {
    "rule_name": "Expression (Client)",
    "source_fields": ["_vendornameandcodebasicdetails_"],
    "destination_fields": [],
    "conditionalValues": [
        'on("change") and (cf(true,"_incotermspurchaseorganizationdetails_");asdff(true,"_incotermspurchaseorganizationdetails_");rffd(true,"_incotermspurchaseorganizationdetails_"))'
    ],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Cross-panel clearing: Clear Incoterms in Purchase Organization Details whenever Vendor Name and Code in Basic Details changes. Derivation is via GENERATE_ARRAY_FORM_GROUPS server-side rule."
}

# Add the rule to the Vendor Name and Code field in Basic Details
added = False
for field in panels["Basic Details"]:
    if field["variableName"] == "_vendornameandcodebasicdetails_":
        field["rules"].append(clearing_rule)
        added = True
        break

if not added:
    print("WARNING: Could not find _vendornameandcodebasicdetails_ in Basic Details panel")

# Write output
output_path = "output/vendor_extension/runs/20/inter_panel/temp/complex_incoterms___incotermspurchaseorganizationdetails___rules.json"
with open(output_path, "w") as f:
    json.dump(panels, f, indent=2)

print(f"Done. Rule added: {added}. Output written to {output_path}")

# Write log
log_path = "output/vendor_extension/runs/20/inter_panel/temp/complex_incoterms___incotermspurchaseorganizationdetails___log.txt"
with open(log_path, "a") as f:
    f.write("Step 1: Read complex refs - 1 clearing reference found\n")
    f.write("Step 2: Read involved panels - Basic Details (23 fields), Purchase Organization Details (18 fields)\n")
    f.write("Step 3: Analyzed ref: clear _incotermspurchaseorganizationdetails_ (TEXT) when _vendornameandcodebasicdetails_ (DROPDOWN) changes\n")
    f.write("Step 4: Built Expression (Client) clearing rule with cf+asdff+rffd on trigger field _vendornameandcodebasicdetails_\n")
    f.write("Step 5: Output written with 1 new rule placed on Basic Details panel\n")
