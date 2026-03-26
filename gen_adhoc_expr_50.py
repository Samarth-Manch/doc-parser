import json
import os

# Read input
with open("output/block_unblock/runs/50/expression_rules/temp/Adhoc_Approvers_expr_input.json") as f:
    fields = json.load(f)

# Shorthand variable names
doyou = "_doyouwanttosendtherequesttoadhocapproveradhocapprovers_"
num = "_pleasechoosenumberofapproveradhocapprovers_"

# Approver group fields with visibility logic (from BUD)
groups_visible = {
    1: [
        "_adhocapprover1detailsadhocapprovers_",
        "_adhocapprover1adhocapprovers_",
        "_adhocapprovername1adhocapprovers_",
        "_adhocapproveremail1adhocapprovers_",
    ],
    2: [
        "_adhocapprover2detailsadhocapprovers_",
        "_adhocapprover2adhocapprovers_",
        "_adhocapprovername2adhocapprovers_",
        "_adhocapproveremail2adhocapprovers_",
        "_adhocapprovermobilenumber2adhocapprovers_",
    ],
    3: [
        "_adhocapprover3detailsadhocapprovers_",
        "_adhocapprover3adhocapprovers_",
        "_adhocapprovername3adhocapprovers_",
        "_adhocapprovermobilenumber3adhocapprovers_",
    ],
    4: [
        "_adhocapprover4detailsadhocapprovers_",
        "_adhocapprover4adhocapprovers_",
    ],
    5: [
        "_adhocapprover5detailsadhocapprovers_",
        "_adhocapprover5adhocapprovers_",
    ],
}

# Mandatory fields per group (exclude LABELs)
groups_mandatory = {
    1: [
        "_adhocapprover1adhocapprovers_",
        "_adhocapprovername1adhocapprovers_",
        "_adhocapproveremail1adhocapprovers_",
    ],
    2: [
        "_adhocapprover2adhocapprovers_",
        "_adhocapprovername2adhocapprovers_",
        "_adhocapproveremail2adhocapprovers_",
        "_adhocapprovermobilenumber2adhocapprovers_",
    ],
    3: [
        "_adhocapprover3adhocapprovers_",
        "_adhocapprovername3adhocapprovers_",
        "_adhocapprovermobilenumber3adhocapprovers_",
    ],
    4: [
        "_adhocapprover4adhocapprovers_",
    ],
    5: [
        "_adhocapprover5adhocapprovers_",
    ],
}

def q(s):
    return '"' + s + '"'

def vof(var):
    return 'vo("' + var + '")'

# ============================================================
# RULE A1: Visibility + Mandatory on "Do you want to send..."
# ============================================================
rule_a1_parts = []
rule_a1_parts.append('mvi(' + vof(doyou) + '=="Yes",' + q(num) + ')')
rule_a1_parts.append('minvi(' + vof(doyou) + '!="Yes",' + q(num) + ')')
rule_a1_parts.append('mm(' + vof(doyou) + '=="Yes",' + q(num) + ')')
rule_a1_parts.append('mnm(' + vof(doyou) + '!="Yes",' + q(num) + ')')
rule_a1_expr = ";".join(rule_a1_parts)

rule_a1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [doyou],
    "destination_fields": [],
    "conditionalValues": [rule_a1_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Please choose number of Approver visible and mandatory when Do you want to send = Yes, otherwise invisible and non-mandatory."
}

# ============================================================
# RULE B1: Clearing on "Do you want to send..." (explicit BUD)
# ============================================================
rule_b1_expr = 'on("change") and (cf(true,' + q(num) + ');asdff(true,' + q(num) + ');rffdd(true,' + q(num) + '))'

rule_b1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [doyou],
    "destination_fields": [],
    "conditionalValues": [rule_b1_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "BUD explicit: on any change to Adhoc Approver question, clear and refresh Please choose number of Approver."
}

# ============================================================
# RULE A2: Visibility of all Approver groups on "Please choose number"
# Uses not() function for negation per agent prompt rules
# ============================================================
rule_a2_parts = []
for n in range(1, 6):
    vis_fields = ",".join(q(v) for v in groups_visible[n])
    mand_fields = ",".join(q(v) for v in groups_mandatory[n])

    show_cond = '+' + vof(num) + '>=' + str(n)
    hide_cond = 'not(+' + vof(num) + '>=' + str(n) + ')'

    rule_a2_parts.append('mvi(' + show_cond + ',' + vis_fields + ')')
    rule_a2_parts.append('minvi(' + hide_cond + ',' + vis_fields + ')')
    rule_a2_parts.append('mm(' + show_cond + ',' + mand_fields + ')')
    rule_a2_parts.append('mnm(' + hide_cond + ',' + mand_fields + ')')

rule_a2_expr = ";".join(rule_a2_parts)

rule_a2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [num],
    "destination_fields": [],
    "conditionalValues": [rule_a2_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Cumulative visibility: group 1 when >=1, group 2 when >=2, group 3 when >=3, group 4 when >=4, group 5 when >=5. Mandatory paired with visibility for non-LABEL fields. Uses not() for negated conditions."
}

# ============================================================
# RULE B2: Clearing on "Please choose number" (Phase B)
# Per-group visibility conditions using extracted minvi condition
# LABEL fields excluded from clearing (no value to clear)
# ============================================================
clear_groups = {
    1: ["_adhocapprover1adhocapprovers_", "_adhocapprovername1adhocapprovers_", "_adhocapproveremail1adhocapprovers_"],
    2: ["_adhocapprover2adhocapprovers_", "_adhocapprovername2adhocapprovers_", "_adhocapproveremail2adhocapprovers_", "_adhocapprovermobilenumber2adhocapprovers_"],
    3: ["_adhocapprover3adhocapprovers_", "_adhocapprovername3adhocapprovers_", "_adhocapprovermobilenumber3adhocapprovers_"],
    4: ["_adhocapprover4adhocapprovers_"],
    5: ["_adhocapprover5adhocapprovers_"],
}

b2_parts = []
all_clear = []
for g, children in clear_groups.items():
    neg = 'not(+' + vof(num) + '>=' + str(g) + ')'
    cstr = ",".join(q(c) for c in children)
    b2_parts.append('cf(' + neg + ',' + cstr + ')')
    b2_parts.append('rffdd(' + neg + ',' + cstr + ')')
    all_clear.extend(children)

b2_parts.append('asdff(true,' + ",".join(q(c) for c in all_clear) + ')')
b2_expr = 'on("change") and (' + ";".join(b2_parts) + ')'

rule_b2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [num],
    "destination_fields": [],
    "conditionalValues": [b2_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Visibility-controlled clearing: each group cleared when number drops below threshold (extracted minvi condition). LABEL fields excluded. asdff(true) covers all."
}

# ============================================================
# Build output: add rules to appropriate fields
# ============================================================
for field in fields:
    if field["variableName"] == doyou:
        field["rules"] = [rule_a1, rule_b1]
    elif field["variableName"] == num:
        field["rules"] = [rule_a2, rule_b2]

# Write output
outpath = "output/block_unblock/runs/50/expression_rules/temp/Adhoc_Approvers_expr_output.json"
os.makedirs(os.path.dirname(outpath), exist_ok=True)
with open(outpath, "w") as f:
    json.dump(fields, f, indent=2)

# Write log file
logpath = "output/block_unblock/runs/50/expression_rules/temp/Adhoc_Approvers_expr_log.txt"
log_lines = [
    "Step 1: Read expression_rules.md",
    "Step 2: Read all field logic (25 fields in Adhoc Approvers panel)",
    "Step 3: Qualifying fields: Do you want to send the request to Adhoc Approver? (visibility+clearing trigger for number dropdown), Please choose number of Approver (visibility+clearing trigger for all approver groups). Skipped cross-panel: none. Skipped non-qualifying: 23 fields (EDV auto-fetch only, PANEL, LABEL without logic, or affected-only fields whose rules are placed on trigger fields).",
    "Step 4: Built and placed 2 expression rules (Phase A: 1 visibility on doyou-field, 1 visibility on number-field)",
    "Step 5: Built parent->children map: 2 parents (doyou->number, number->12 approver fields)",
    "Step 6: Resolved chains - 2 parents with clearing rules (both need independent clearing since number changes independently of doyou)",
    "Step 7: Determined conditions - doyou: true (BUD explicit clean on change), number: per-group minvi conditions (visibility-controlled clearing)",
    "Step 8: Placed 2 clearing rules, skipped 0 (already exist)",
    "Step 9 complete: total 4 rules placed (2 visibility + 2 clearing on 2 trigger fields)",
]
with open(logpath, "w") as f:
    f.write("\n".join(log_lines) + "\n")

print("Output written to " + outpath)
print("Log written to " + logpath)
print("Total rules placed: 4")

# Verify output
with open(outpath) as f:
    output = json.load(f)
rules_count = sum(len(f["rules"]) for f in output)
print("Verified: " + str(len(output)) + " fields, " + str(rules_count) + " total rules in output")
