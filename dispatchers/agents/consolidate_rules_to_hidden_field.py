#!/usr/bin/env python3
"""
Consolidate Rules to Hidden Field

Final-stage deterministic script that moves every formFillRule attached to a
PANEL-type field into a single new hidden (invisible) field inserted under the
first panel. Rules on regular (non-PANEL) fields are left in place.

The original PANEL fields keep their metadata but end up with empty
formFillRules. The moved rules retain their existing ids and their
sourceIds/destinationIds, which still point at the original fields — only the
host field changes.

Usage:
  python3 dispatchers/agents/consolidate_rules_to_hidden_field.py \
      --json /path/to/test_merged.json

  # Write to a different file instead of overwriting:
  python3 dispatchers/agents/consolidate_rules_to_hidden_field.py \
      --json input.json --output output.json
"""

import argparse
import json
import sys


HIDDEN_FIELD_NAME = "Rules Holder"
HIDDEN_FIELD_VARIABLE = "_rulesholder_"


def consolidate_rules(json_path: str, output_path: str) -> None:
    print(f"Loading JSON: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    doc_types = data.get("template", {}).get("documentTypes", [])
    if not doc_types:
        print("ERROR: No documentTypes found in JSON.")
        sys.exit(1)

    metadatas = doc_types[0].get("formFillMetadatas", [])
    if not metadatas:
        print("ERROR: No formFillMetadatas found in first documentType.")
        sys.exit(1)

    # Locate the first PANEL field — new hidden field is inserted right after it.
    first_panel_idx = None
    for i, m in enumerate(metadatas):
        if m.get("formTag", {}).get("type") == "PANEL":
            first_panel_idx = i
            break

    if first_panel_idx is None:
        print("ERROR: No PANEL field found in first documentType.")
        sys.exit(1)

    first_panel = metadatas[first_panel_idx]
    first_panel_name = first_panel.get("formTag", {}).get("name", "Panel 1")

    # Collect rules only from PANEL-type fields, then clear them.
    collected_rules = []
    fields_cleared = 0
    for m in metadatas:
        if m.get("formTag", {}).get("type") != "PANEL":
            continue
        rules = m.get("formFillRules", [])
        if rules:
            collected_rules.extend(rules)
            m["formFillRules"] = []
            fields_cleared += 1

    if not collected_rules:
        print("No PANEL-level rules found — nothing to consolidate.")
        if output_path != json_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        return

    # Pick unique ids for the new field.
    max_meta_id = max((m.get("id", 0) for m in metadatas), default=0)
    max_formtag_id = max(
        (m.get("formTag", {}).get("id", 0) for m in metadatas), default=0
    )
    max_rule_id = max(
        (r.get("id", 0) for m in metadatas for r in m.get("formFillRules", [])),
        default=0,
    )
    # collected_rules already includes rules with existing ids; include them.
    max_rule_id = max(
        max_rule_id,
        max((r.get("id", 0) for r in collected_rules), default=0),
    )
    new_meta_id = max_meta_id + 1
    new_formtag_id = max_formtag_id + 1
    self_hide_rule_id = max_rule_id + 1

    # Slot between the first PANEL and the field that follows it.
    first_panel_order = first_panel.get("formOrder", 1.0)
    if first_panel_idx + 1 < len(metadatas):
        next_order = metadatas[first_panel_idx + 1].get(
            "formOrder", first_panel_order + 1.0
        )
        new_order = (first_panel_order + next_order) / 2.0
    else:
        new_order = first_panel_order + 0.5

    # Self-hide rule: keeps the Rules Holder field invisible on load.
    self_hide_rule = {
        "id": self_hide_rule_id,
        "createUser": "FIRST_PARTY",
        "updateUser": "FIRST_PARTY",
        "actionType": "EXECUTE",
        "processingType": "CLIENT",
        "sourceIds": [new_meta_id],
        "destinationIds": [],
        "postTriggerRuleIds": [],
        "button": "",
        "searchable": False,
        "executeOnFill": True,
        "executeOnRead": False,
        "executeOnEsign": False,
        "executePostEsign": False,
        "runPostConditionFail": False,
        "conditionalValues": [
            f'on("load") and (minvi(true, "{HIDDEN_FIELD_VARIABLE}"))'
        ],
        "condition": "IN",
        "conditionValueType": "EXPR",
    }

    hidden_field = {
        "id": new_meta_id,
        "upperLeftX": 0.0,
        "upperLeftY": 0.0,
        "lowerRightX": 0.0,
        "lowerRightY": 0.0,
        "page": 1,
        "fontSize": 10,
        "fontStyle": "Times-Roman",
        "scaleX": 1.0,
        "scaleY": 1.0,
        "mandatory": False,
        "editable": False,
        "formTag": {
            "id": new_formtag_id,
            "name": HIDDEN_FIELD_NAME,
            "type": "TEXT",
            "standardField": False,
        },
        "variableName": HIDDEN_FIELD_VARIABLE,
        "helpText": "",
        "placeholder": "",
        "exportable": False,
        "visible": True,
        "pdfFill": False,
        "formOrder": new_order,
        "exportLabel": HIDDEN_FIELD_NAME,
        "exportToBulkTemplate": False,
        "encryptValue": False,
        "htmlContent": "",
        "cssStyle": "",
        "formFillDataEnable": False,
        "reportVisible": False,
        "collabDisplayMap": {},
        "formTagValidations": [],
        "extendedFormFillLocations": [],
        "formFillMetaTranslations": [],
        "formFillRules": [self_hide_rule] + collected_rules,
    }

    metadatas.insert(first_panel_idx + 1, hidden_field)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(
        f"  Moved {len(collected_rules)} PANEL-level rule(s) from "
        f"{fields_cleared} panel(s) into hidden field id={new_meta_id} "
        f"under panel '{first_panel_name}'."
    )
    print(f"  Wrote: {output_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", required=True, help="Path to API-format JSON")
    ap.add_argument(
        "--output",
        help="Output path (defaults to overwriting --json in place)",
    )
    args = ap.parse_args()
    consolidate_rules(args.json, args.output or args.json)


if __name__ == "__main__":
    main()
