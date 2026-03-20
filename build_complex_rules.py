#!/usr/bin/env python3
"""Build cross-panel Expression (Client) rules for multiselect panel visibility."""
import json
import os

INPUT_PANELS = "output/block_unblock/runs/38/inter_panel/temp/complex_which_function_you_would_like_to_update____whichfunctionyouwouldliketoupdatevendordetails___panels.json"
OUTPUT_RULES = "output/block_unblock/runs/38/inter_panel/temp/complex_which_function_you_would_like_to_update____whichfunctionyouwouldliketoupdatevendordetails___rules.json"
LOG_FILE = "output/block_unblock/runs/38/inter_panel/temp/complex_which_function_you_would_like_to_update____whichfunctionyouwouldliketoupdatevendordetails___log.txt"

SRC_VAR = "_whichfunctionyouwouldliketoupdatevendordetails_"
SRC_PANEL = "Vendor Details"

PANEL_MAP = {
    "Block / Unblock Posting": "_blockunblockposting_",
    "Block / Unblock Payment": "_blockunblockpayment_",
    "Block / Unblock Purchase Org": "_blockunblockpurchaseorg_",
}

DROPDOWN_TYPES = {"DROPDOWN", "EXTERNAL_DROP_DOWN_VALUE", "MULTISELECT_EXTERNAL_DROPDOWN"}
SKIP_TYPES = {"PANEL", "ARRAY_HDR", "ARRAY_END"}

with open(INPUT_PANELS) as f:
    panels = json.load(f)

# Categorize fields in target panels
all_clear_fields = []
dropdown_fields = []
text_fields = []

for panel_name in PANEL_MAP:
    for field in panels[panel_name]:
        if field["type"] in SKIP_TYPES:
            continue
        vn = field["variableName"]
        all_clear_fields.append(vn)
        if field["type"] in DROPDOWN_TYPES:
            dropdown_fields.append(vn)
        else:
            text_fields.append(vn)

# --- Rule 1: Load event (default invisible) ---
panel_vars = list(PANEL_MAP.values())
load_dest = ", ".join('"' + v + '"' for v in panel_vars)
load_expr = 'on("load") and (minvi(true, ' + load_dest + "))"

rule1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [SRC_VAR],
    "destination_fields": [],
    "conditionalValues": [load_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "load_event",
    "_reasoning": "By default, Block / Unblock Posting, Block / Unblock Payment, and Block / Unblock Purchase Org panels are invisible on form load.",
}

# --- Rule 2: Visibility toggle ---
vis_parts = []
for panel_name, panel_var in PANEL_MAP.items():
    vis_cond = 'cntns("' + panel_name + '", vo("' + SRC_VAR + '"))'
    invis_cond = 'not(cntns("' + panel_name + '", vo("' + SRC_VAR + '")))'
    vis_parts.append('mvi(' + vis_cond + ', "' + panel_var + '")')
    vis_parts.append('minvi(' + invis_cond + ', "' + panel_var + '")')

vis_expr = ";".join(vis_parts)

rule2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [SRC_VAR],
    "destination_fields": [],
    "conditionalValues": [vis_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Panel visibility controlled by multiselect dropdown using cntns(). Each panel visible when its option is selected, invisible otherwise.",
}

# --- Rule 3: Clearing on change ---
cf_list = ", ".join('"' + v + '"' for v in all_clear_fields)
asdff_list = cf_list
rffdd_list = ", ".join('"' + v + '"' for v in dropdown_fields)
rffd_list = ", ".join('"' + v + '"' for v in text_fields)

clear_parts = ["cf(true, " + cf_list + ")"]
clear_parts.append("asdff(true, " + asdff_list + ")")
if dropdown_fields:
    clear_parts.append("rffdd(true, " + rffdd_list + ")")
if text_fields:
    clear_parts.append("rffd(true, " + rffd_list + ")")

clear_expr = 'on("change") and (' + ";".join(clear_parts) + ")"

rule3 = {
    "rule_name": "Expression (Client)",
    "source_fields": [SRC_VAR],
    "destination_fields": [],
    "conditionalValues": [clear_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "On multiselect change, clear all fields in the 3 target panels, autosave, and refresh. Panels re-selected will be repopulated through their own rules.",
}

# Add rules to source field
output = json.loads(json.dumps(panels))
for field in output[SRC_PANEL]:
    if field["variableName"] == SRC_VAR:
        field["rules"] = field.get("rules", []) + [rule1, rule2, rule3]
        break

with open(OUTPUT_RULES, "w") as f:
    json.dump(output, f, indent=2)

# Write log
log_lines = [
    "=== Cross-Panel Complex Rules Agent ===",
    "Source field: " + SRC_VAR + " (" + SRC_PANEL + ")",
    "Target panels: " + ", ".join(PANEL_MAP.keys()),
    "",
    "Step 1: Read complex refs - 3 visibility references from multiselect dropdown",
    "Step 2: Read involved panels - 4 panels loaded",
    "Step 3: Analyzed field types - " + str(len(all_clear_fields)) + " data fields across 3 target panels",
    "  Dropdown fields: " + str(len(dropdown_fields)) + ", Text fields: " + str(len(text_fields)),
    "Step 4: Built 3 Expression (Client) rules:",
    "  Rule 1: on(load) + minvi - default invisible for 3 panels",
    "  Rule 2: mvi/minvi with cntns() - visibility toggle per panel based on multiselect selection",
    "  Rule 3: on(change) + cf/asdff/rffdd/rffd - clear all target panel fields on change",
    "Step 5: Output written successfully",
]
with open(LOG_FILE, "w") as f:
    f.write("\n".join(log_lines) + "\n")

print("Done. Output:", OUTPUT_RULES)
print("Rules placed:", len([rule1, rule2, rule3]))
print("Fields categorized:", len(all_clear_fields), "total,", len(dropdown_fields), "dropdown,", len(text_fields), "text")
