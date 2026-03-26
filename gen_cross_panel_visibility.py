#!/usr/bin/env python3
"""Generate cross-panel expression rules for multiselect visibility/clearing."""
import json

INPUT_PANELS = "output/block_unblock/runs/50/inter_panel/temp/complex_which_function_you_would_like_to_update____whichfunctionyouwouldliketoupdatevendordetails___panels.json"
OUTPUT_RULES = "output/block_unblock/runs/50/inter_panel/temp/complex_which_function_you_would_like_to_update____whichfunctionyouwouldliketoupdatevendordetails___rules.json"
LOG_FILE = "output/block_unblock/runs/50/inter_panel/temp/complex_which_function_you_would_like_to_update____whichfunctionyouwouldliketoupdatevendordetails___log.txt"

def main():
    with open(INPUT_PANELS) as f:
        panels = json.load(f)

    trigger_var = "_whichfunctionyouwouldliketoupdatevendordetails_"

    # Panel name -> panel variableName mapping (from PANEL-type fields in target panels)
    panel_map = {}
    for panel_name, fields in panels.items():
        if panel_name == "Vendor Details":
            continue
        for field in fields:
            if field["type"] == "PANEL":
                panel_map[panel_name] = field["variableName"]
                break

    print("Panel map:", json.dumps(panel_map, indent=2))

    # Collect child fields (non-PANEL, non-ARRAY_HDR) from target panels
    all_child_fields = []
    dropdown_fields = []
    text_fields = []
    dropdown_types = {"EXTERNAL_DROP_DOWN_VALUE", "MULTISELECT_EXTERNAL_DROPDOWN", "DROP_DOWN", "EXT_DROP_DOWN"}

    for panel_name in panel_map:
        for field in panels[panel_name]:
            if field["type"] in ("PANEL", "ARRAY_HDR", "ARRAY_END"):
                continue
            var = field["variableName"]
            all_child_fields.append(var)
            if field["type"] in dropdown_types:
                dropdown_fields.append(var)
            else:
                text_fields.append(var)

    print("Total child fields:", len(all_child_fields))
    print("Dropdown fields:", len(dropdown_fields))
    print("Text fields:", len(text_fields))

    # RULE 1: Visibility toggle based on multiselect selection
    # mvi/minvi without event wrapper runs on both load and change,
    # so panels start invisible (empty multiselect -> cntns returns false)
    vis_parts = []
    for panel_name, panel_var in panel_map.items():
        cntns_check = 'cntns("' + panel_name + '",vo("' + trigger_var + '"))'
        vis_parts.append('mvi(' + cntns_check + ',"' + panel_var + '")')
        vis_parts.append('minvi(not(' + cntns_check + '),"' + panel_var + '")')

    vis_expr = ";".join(vis_parts)

    rule_visibility = {
        "rule_name": "Expression (Client)",
        "source_fields": [trigger_var],
        "destination_fields": [],
        "conditionalValues": [vis_expr],
        "condition": "IN",
        "conditionValueType": "EXPR",
        "_expressionRuleType": "visibility",
        "_reasoning": "Cross-panel multiselect visibility: each Block/Unblock panel is shown when its name is selected in the multiselect dropdown, hidden otherwise. Uses cntns() for multiselect value checking. Panels are invisible by default when nothing is selected."
    }

    # RULE 2: Clearing rule on change
    all_q = ",".join('"' + v + '"' for v in all_child_fields)
    dd_q = ",".join('"' + v + '"' for v in dropdown_fields)
    txt_q = ",".join('"' + v + '"' for v in text_fields)

    clear_parts = ["cf(true," + all_q + ")", "asdff(true," + all_q + ")"]
    if dropdown_fields:
        clear_parts.append("rffdd(true," + dd_q + ")")
    if text_fields:
        clear_parts.append("rffd(true," + txt_q + ")")

    clear_expr = 'on("change") and (' + ";".join(clear_parts) + ")"

    rule_clearing = {
        "rule_name": "Expression (Client)",
        "source_fields": [trigger_var],
        "destination_fields": [],
        "conditionalValues": [clear_expr],
        "condition": "IN",
        "conditionValueType": "EXPR",
        "_expressionRuleType": "clear_field",
        "_reasoning": "Cross-panel clearing: when multiselect value changes, clear all editable fields in the 6 Block/Unblock panels, autosave and refresh. Dropdowns refreshed via rffdd, text fields via rffd."
    }

    # Build output: copy all panels, add rules to trigger field in Vendor Details
    output = {}
    for panel_name, fields in panels.items():
        new_fields = []
        for field in fields:
            field_copy = dict(field)
            if field_copy["variableName"] == trigger_var and panel_name == "Vendor Details":
                field_copy["rules"] = list(field_copy.get("rules", [])) + [
                    rule_visibility, rule_clearing
                ]
            new_fields.append(field_copy)
        output[panel_name] = new_fields

    with open(OUTPUT_RULES, "w") as f:
        json.dump(output, f, indent=2)

    # Update log
    with open(LOG_FILE, "a") as f:
        f.write("Cross-panel complex rules processing\n")
        f.write("Source field: " + trigger_var + " (MULTISELECT_EXTERNAL_DROPDOWN in Vendor Details)\n")
        f.write("Generated 2 Expression (Client) rules:\n")
        f.write("  Rule 1: visibility - multiselect-driven panel show/hide with cntns() for " + str(len(panel_map)) + " panels\n")
        f.write("  Rule 2: clear_field - clear " + str(len(all_child_fields)) + " child fields on change (" + str(len(dropdown_fields)) + " dropdowns, " + str(len(text_fields)) + " text)\n")
        f.write("Output: " + str(len(output)) + " panels written\n")

    print("\nOutput written to", OUTPUT_RULES)
    print("Rules added: 2 (visibility, clear_field)")

    # Verify
    for pn, pfields in output.items():
        for field in pfields:
            if field.get("rules"):
                print("\n  Panel '" + pn + "', Field '" + field['field_name'] + "': " + str(len(field['rules'])) + " rules")
                for r in field["rules"]:
                    expr_preview = r["conditionalValues"][0][:150] + "..."
                    print("    - " + r["_expressionRuleType"] + ": " + expr_preview)

if __name__ == "__main__":
    main()
