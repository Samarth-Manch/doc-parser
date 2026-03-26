import json
import sys

# Read input
input_path = "output/block_unblock/runs/41/inter_panel/temp/complex____whichfunctionyouwouldliketoupdatevendordetails___panels.json"
with open(input_path) as f:
    panels = json.load(f)

source_var = "_whichfunctionyouwouldliketoupdatevendordetails_"

# Panel variableNames (from PANEL-type fields)
posting_panel_var = "_blockunblockposting_"
payment_panel_var = "_blockunblockpayment_"
purchase_panel_var = "_blockunblockpurchaseorg_"

# --- Rule 1: Load event - default panel invisibility ---
load_expr = (
    'on("load") and (minvi(true, "'
    + posting_panel_var + '", "'
    + payment_panel_var + '", "'
    + purchase_panel_var + '"))'
)
load_rule = {
    "rule_name": "Expression (Client)",
    "source_fields": [source_var],
    "destination_fields": [],
    "conditionalValues": [load_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "load_event",
    "_reasoning": "By default, all three Block/Unblock panels (Posting, Payment, Purchase Org) are invisible on form load."
}

# --- Rule 2: Visibility toggle based on multiselect using cntns() ---
panel_options = [
    ("Block / Unblock Posting", posting_panel_var),
    ("Block / Unblock Payment", payment_panel_var),
    ("Block / Unblock Purchase Org", purchase_panel_var),
]

vis_parts = []
for option, pv in panel_options:
    vis_parts.append(
        'mvi(cntns("' + option + '", vo("' + source_var + '")), "' + pv + '")'
    )
    vis_parts.append(
        'minvi(not(cntns("' + option + '", vo("' + source_var + '"))), "' + pv + '")'
    )

vis_rule = {
    "rule_name": "Expression (Client)",
    "source_fields": [source_var],
    "destination_fields": [],
    "conditionalValues": [";".join(vis_parts)],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Cross-panel visibility: Show/hide Block/Unblock Posting, Payment, and Purchase Org panels based on multiselect dropdown selections using cntns()."
}

# --- Rule 3: Clearing rule - clear fields when panel is hidden ---
dropdown_types = {"DROPDOWN", "EXTERNAL_DROP_DOWN_VALUE", "MULTISELECT_EXTERNAL_DROPDOWN"}

def get_clearable_fields(panel_fields):
    dd = []
    non_dd = []
    for f in panel_fields:
        if f["type"] == "PANEL":
            continue
        v = f["variableName"]
        if f["type"] in dropdown_types:
            dd.append(v)
        else:
            non_dd.append(v)
    return dd, non_dd

def q(fields):
    return ", ".join('"' + f + '"' for f in fields)

posting_dd, posting_ndd = get_clearable_fields(panels["Block / Unblock Posting"])
payment_dd, payment_ndd = get_clearable_fields(panels["Block / Unblock Payment"])
purchase_dd, purchase_ndd = get_clearable_fields(panels["Block / Unblock Purchase Org"])

panel_field_groups = [
    ("Block / Unblock Posting", posting_dd, posting_ndd),
    ("Block / Unblock Payment", payment_dd, payment_ndd),
    ("Block / Unblock Purchase Org", purchase_dd, purchase_ndd),
]

clear_parts = []
for option, dd, ndd in panel_field_groups:
    cond = 'not(cntns("' + option + '", vo("' + source_var + '")))'
    all_grp = dd + ndd
    if all_grp:
        clear_parts.append("cf(" + cond + ", " + q(all_grp) + ")")
    if dd:
        clear_parts.append("rffdd(" + cond + ", " + q(dd) + ")")
    if ndd:
        clear_parts.append("rffd(" + cond + ", " + q(ndd) + ")")

all_clearable = (posting_dd + posting_ndd + payment_dd + payment_ndd + purchase_dd + purchase_ndd)
clear_parts.append("asdff(true, " + q(all_clearable) + ")")

clear_expr = 'on("change") and (' + ";".join(clear_parts) + ")"

clear_rule = {
    "rule_name": "Expression (Client)",
    "source_fields": [source_var],
    "destination_fields": [],
    "conditionalValues": [clear_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Cross-panel clearing: When multiselect changes, clear all fields in deselected Block/Unblock panels. Uses visibility-controlled condition (minvi condition) per panel group."
}

# Add rules to the source field in Vendor Details
for field in panels["Vendor Details"]:
    if field["variableName"] == source_var:
        field["rules"].extend([load_rule, vis_rule, clear_rule])
        break

# Write output
output_path = "output/block_unblock/runs/41/inter_panel/temp/complex____whichfunctionyouwouldliketoupdatevendordetails___rules.json"
with open(output_path, 'w') as f:
    json.dump(panels, f, indent=2)

# Write log
log_path = "output/block_unblock/runs/41/inter_panel/temp/complex____whichfunctionyouwouldliketoupdatevendordetails___log.txt"
with open(log_path, 'a') as f:
    f.write("\n--- Complex Cross-Panel Rules Agent ---\n")
    f.write("Source field: " + source_var + " (Vendor Details panel)\n")
    f.write("Rule 1: Load event - default invisibility for 3 panels\n")
    f.write("Rule 2: Visibility toggle using cntns() for multiselect - 3 panels\n")
    f.write("Rule 3: Clearing rule - visibility-controlled clearing for " + str(len(all_clearable)) + " fields across 3 panels\n")
    f.write("  Posting: " + str(len(posting_dd)) + " dropdown + " + str(len(posting_ndd)) + " non-dropdown\n")
    f.write("  Payment: " + str(len(payment_dd)) + " dropdown + " + str(len(payment_ndd)) + " non-dropdown\n")
    f.write("  Purchase Org: " + str(len(purchase_dd)) + " dropdown + " + str(len(purchase_ndd)) + " non-dropdown\n")
    f.write("Total rules placed: 3\n")

print("SUCCESS: 3 Expression (Client) rules placed on " + source_var)
print("  - load_event: default invisibility for 3 panels")
print("  - visibility: cntns()-based toggle for 3 panels")
print("  - clear_field: visibility-controlled clearing for " + str(len(all_clearable)) + " fields")

# Verify output
with open(output_path) as f:
    out = json.load(f)
    src_field = [fld for fld in out["Vendor Details"] if fld["variableName"] == source_var][0]
    print("\nVerification: " + str(len(src_field["rules"])) + " rules on source field")
    for r in src_field["rules"]:
        cv = r["conditionalValues"][0]
        print("  - " + r["_expressionRuleType"] + ": " + cv[:100] + "...")
