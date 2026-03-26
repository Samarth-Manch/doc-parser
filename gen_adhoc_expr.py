#!/usr/bin/env python3
"""Generate Expression (Client) rules for Adhoc Approvers panel (vendor_extension run 17)."""
import json
import os

INPUT  = "output/vendor_extension/runs/17/expression_rules/temp/Adhoc_Approvers_expr_input.json"
OUTPUT = "output/vendor_extension/runs/17/expression_rules/temp/Adhoc_Approvers_expr_output.json"
LOG    = "output/vendor_extension/runs/17/expression_rules/temp/Adhoc_Approvers_expr_log.txt"

fields = json.load(open(INPUT))

# Variable name aliases
SEND = "_doyouwanttosendtherequesttoadhocapproveradhocapprovers_"
NUM  = "_pleasechoosenumberofapproveradhocapprovers_"

# Build groups from actual input field variableNames
# Each group N: visible when number of approvers includes N
# Group 1: vals 1,2,3,4,5  Group 2: vals 2,3,4,5  etc.
groups = []
for n in range(1, 6):
    vals = [str(i) for i in range(n, 6)]
    groups.append({
        "num": n,
        "vals": vals,
        "label": f"_adhocapprover{n}detailsadhocapprovers_",
        "dropdown": f"_adhocapprover{n}adhocapprovers_",
        "name": f"_adhocapprovername{n}adhocapprovers_",
        "email": f"_adhocapprovereamil{n}adhocapprovers_",    # note: "eamil" per BUD
        "mobile": f"_adhocapprovermobilenumber{n}adhocapprovers_",
    })

DQ = '"'
SEP = ";"


def q(s):
    """Quote a string for expression."""
    return DQ + s + DQ


def in_cond(var, vals):
    """Build vo(var)=='v1' or vo(var)=='v2' ... condition."""
    parts = ["vo(" + q(var) + ")==" + q(v) for v in vals]
    return " or ".join(parts)


def not_in_cond(var, vals):
    """Build negated in-condition."""
    if len(vals) == 1:
        return "vo(" + q(var) + ")!=" + q(vals[0])
    return "not(" + in_cond(var, vals) + ")"


# ============================================================
# PHASE A: Logic-Text Expression Rules
# ============================================================

# Rule A1: visibility + mandatory on SEND controlling NUM
# Logic: "visible and mandatory if 'Yes' is selected, otherwise invisible and non-mandatory"
expr_a1 = SEP.join([
    "mvi(vo(" + q(SEND) + ")==" + q("Yes") + "," + q(NUM) + ")",
    "minvi(vo(" + q(SEND) + ")!=" + q("Yes") + "," + q(NUM) + ")",
    "mm(vo(" + q(SEND) + ")==" + q("Yes") + "," + q(NUM) + ")",
    "mnm(vo(" + q(SEND) + ")!=" + q("Yes") + "," + q(NUM) + ")",
])

rule_a1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [SEND],
    "destination_fields": [],
    "conditionalValues": [expr_a1],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Please choose number of Approver: visible and mandatory when 'Do you want to send the request to Adhoc Approver?' = Yes, invisible and non-mandatory otherwise."
}

# Rule A2: visibility + mandatory on NUM controlling all 5 approver groups
# Each group N visible when value in {N, N+1, ..., 5}
a2_parts = []
for g in groups:
    cond = in_cond(NUM, g["vals"])
    ncond = not_in_cond(NUM, g["vals"])
    all_fields = [g["label"], g["dropdown"], g["name"], g["email"], g["mobile"]]
    vis_str = ",".join(q(f) for f in all_fields)
    dd_str = q(g["dropdown"])

    a2_parts.append("mvi(" + cond + "," + vis_str + ")")
    a2_parts.append("minvi(" + ncond + "," + vis_str + ")")
    a2_parts.append("mm(" + cond + "," + dd_str + ")")
    a2_parts.append("mnm(" + ncond + "," + dd_str + ")")

expr_a2 = SEP.join(a2_parts)

rule_a2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [NUM],
    "destination_fields": [],
    "conditionalValues": [expr_a2],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Controls visibility and mandatory state of all 5 Adhoc Approver groups based on number of approvers. Group N visible when selected number is in {N..5}. Approver dropdown in each group is mandatory when visible."
}

# ============================================================
# PHASE B: Clearing Rules
# ============================================================

# Rule B1: clearing on SEND (ultimate parent)
# When SEND != Yes, clear NUM + all approver fields (they become invisible)
b1_children = [NUM]
for g in groups:
    b1_children.extend([g["dropdown"], g["name"], g["email"], g["mobile"]])
# 21 fields total (1 + 5*4)

b1_cond = "vo(" + q(SEND) + ")!=" + q("Yes")
b1_list = ",".join(q(c) for c in b1_children)

expr_b1 = (
    "on(" + q("change") + ") and ("
    + "cf(" + b1_cond + "," + b1_list + ")" + SEP
    + "asdff(true," + b1_list + ")" + SEP
    + "rffdd(" + b1_cond + "," + b1_list + ")"
    + ")"
)

rule_b1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [SEND],
    "destination_fields": [],
    "conditionalValues": [expr_b1],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Visibility-controlled clearing: when 'Do you want to send...' != Yes, clear number-of-approver dropdown and all 20 approver detail fields since they become invisible."
}

# Rule B2: clearing on NUM
# On every change, clear all approver dropdowns (cascading) + name/email/mobile (explicit BUD)
b2_children = []
for g in groups:
    b2_children.extend([g["dropdown"], g["name"], g["email"], g["mobile"]])
# 20 fields total (5*4)

b2_list = ",".join(q(c) for c in b2_children)

expr_b2 = (
    "on(" + q("change") + ") and ("
    + "cf(true," + b2_list + ")" + SEP
    + "asdff(true," + b2_list + ")" + SEP
    + "rffdd(true," + b2_list + ")"
    + ")"
)

rule_b2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [NUM],
    "destination_fields": [],
    "conditionalValues": [expr_b2],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "On number-of-approvers change, clear and refresh all approver dropdowns (cascading) and all name/email/mobile fields (explicit BUD: clear on parent change). Condition true since BUD mandates clearing on every change."
}

# ============================================================
# ASSEMBLE OUTPUT
# ============================================================
for field in fields:
    if field["variableName"] == SEND:
        field["rules"].append(rule_a1)
        field["rules"].append(rule_b1)
    elif field["variableName"] == NUM:
        field["rules"].append(rule_a2)
        field["rules"].append(rule_b2)

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w") as f:
    json.dump(fields, f, indent=2)

# Write log
log_lines = [
    "Step 1: Read expression_rules.md",
    "Step 2: Read all field logic (25 fields in Adhoc Approvers panel)",
    "Step 3: Qualifying fields:",
    "  - _doyouwanttosendtherequesttoadhocapproveradhocapprovers_: trigger for visibility+mandatory of number-of-approver",
    "  - _pleasechoosenumberofapproveradhocapprovers_: trigger for visibility+mandatory of all 5 approver groups",
    "  Skipped cross-panel: _adhocapprovers_ (PANEL visible only for MDC approver - session/role-based, handled by inter-panel agent)",
    "  Skipped cross-panel: _doyouwanttosendtherequesttoadhocapproveradhocapprovers_ self-visibility depends on MDC approver role",
    "  Skipped EDV: Name/Email/Mobile auto-fetch from ADHOC_APPROVER EDV (handled by EDV rules)",
    "Step 4: Built and placed 2 expression rules (Phase A: 1 on SEND field, 1 on NUM field)",
    "Step 5: Built parent->children map: 2 parents",
    "  - SEND -> 21 descendants (NUM + 5*4 non-label fields)",
    "  - NUM -> 20 children (5 dropdowns + 15 text fields)",
    "Step 6: Resolved chains - SEND is ultimate parent, NUM is intermediate parent (both get clearing rules)",
    "Step 7: Determined conditions:",
    "  - SEND clearing: visibility condition vo(SEND)!='Yes' for all descendants",
    "  - NUM clearing: true for all children (cascading dropdown + explicit BUD clear-on-change)",
    "Step 8: Placed 2 clearing rules, skipped 0 (already exist)",
    "Step 9 complete: total 4 rules placed (2 visibility+mandatory, 2 clearing)",
]
os.makedirs(os.path.dirname(LOG), exist_ok=True)
with open(LOG, "w") as f:
    f.write("\n".join(log_lines) + "\n")

print("Done! 4 rules placed on 2 fields")
print(f"Fields with rules: {sum(1 for f in fields if f['rules'])}")
print(f"Output: {OUTPUT}")
