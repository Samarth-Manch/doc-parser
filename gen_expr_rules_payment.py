#!/usr/bin/env python3
"""Generate expression rules for Block / Unblock Payment panel."""
import json
import os

INPUT_PATH = "output/block_unblock/runs/42/expression_rules/temp/Block___Unblock_Payment_expr_input.json"
OUTPUT_PATH = "output/block_unblock/runs/42/expression_rules/temp/Block___Unblock_Payment_expr_output.json"
LOG_PATH = "output/block_unblock/runs/42/expression_rules/temp/Block___Unblock_Payment_expr_log.txt"

# Read input
with open(INPUT_PATH, "r") as f:
    fields = json.load(f)

# Variable name constants
CCT = "_companycodetypeblockunblockpayment_"
ALL_HDR = "_paymentblockallcompanycodedetailsblockunblockpayment_"
CC1 = "_companycode1blockunblockpayment_"
OLD1 = "_paymentblockold1blockunblockpayment_"
NEW1 = "_paymentblocknew1blockunblockpayment_"
SEL_HDR = "_paymentblockselectedcompanycodedetailsblockunblockpayment_"
CC2 = "_companycode2blockunblockpayment_"
OLD2 = "_paymentblockold2blockunblockpayment_"
NEW2 = "_paymentblocknew2blockunblockpayment_"

def q(v):
    """Quote a variable name for expression strings."""
    return '"' + v + '"'

def vlist(*vars):
    """Comma-separated quoted variable list."""
    return ",".join(q(v) for v in vars)

def vo(v):
    """vo() call for a variable."""
    return 'vo(' + q(v) + ')'

log_lines = []
def log(msg):
    log_lines.append(msg)

log("Step 1: Read expression_rules.md")
log("Step 2: Read all field logic")

# --- Phase A: Classify fields ---
# Cross-panel references (skipped):
#   - Company Code 1: "Based on Vendor Number (from Vendor Details panel)" -> cross-panel
#   - Payment block old 1: "based on Vendor Number field from Vendor Details Panel" -> cross-panel
#   - Payment block New 1: "if field Which function you would like to Update?" -> cross-panel mandatory
#   - Company Code 2: "depends on Vendor Number Field (from Vendor Details panel)" -> cross-panel
#   - Payment block old 2: "based on Vendor Number field from Vendor Details Panel" -> cross-panel
#   - Payment block New 2: "if field Which function you would like to Update?" -> cross-panel mandatory

log("Step 3: Qualifying fields: Company Code Type (visibility+mandatory+load+clear), "
    "Company Code 1 (disable), Payment block New 1 (error), Payment block New 2 (error). "
    "Skipped cross-panel: Vendor Number refs (Company Code 1, old 1, Company Code 2, old 2), "
    "Which function you would like to Update refs (New 1 mandatory, New 2 mandatory)")

# All Company group fields
all_group = [ALL_HDR, CC1, OLD1, NEW1]
all_grp = vlist(*all_group)

# Selected Company group fields
sel_group = [SEL_HDR, CC2, OLD2, NEW2]
sel_grp = vlist(*sel_group)

# All array fields combined
all_array = all_group + sel_group
all_arr = vlist(*all_array)

# Data fields only (for clearing, no ARRAY_HDRs)
data_fields = [CC1, OLD1, NEW1, CC2, OLD2, NEW2]
data_str = vlist(*data_fields)

# Disabled fields
disabled = [CC1, OLD1, OLD2]
dis_str = vlist(*disabled)

cct = vo(CCT)

# --- Rule 1: Visibility + Mandatory toggle on Company Code Type ---
rule1_parts = [
    'mvi(' + cct + '=="All Companies",' + all_grp + ')',
    'mm(' + cct + '=="All Companies",' + all_grp + ')',
    'minvi(' + cct + '!="All Companies",' + all_grp + ')',
    'mnm(' + cct + '!="All Companies",' + all_grp + ')',
    'mvi(' + cct + '=="Selected Companies",' + sel_grp + ')',
    'mm(' + cct + '=="Selected Companies",' + sel_grp + ')',
    'minvi(' + cct + '!="Selected Companies",' + sel_grp + ')',
    'mnm(' + cct + '!="Selected Companies",' + sel_grp + ')',
]
rule1_expr = ";".join(rule1_parts)

rule1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [CCT],
    "destination_fields": [],
    "conditionalValues": [rule1_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "When Company Code Type = 'All Companies', show and make mandatory All Company Code array fields, hide and make non-mandatory Selected. When 'Selected Companies', vice versa."
}

# --- Rule 2: Default invisible + non-mandatory on load ---
rule2_expr = 'on("load") and (minvi(true,' + all_arr + ');mnm(true,' + all_arr + '))'

rule2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [CCT],
    "destination_fields": [],
    "conditionalValues": [rule2_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "load_event",
    "_reasoning": "By default on form load, all fields in both Payment Block array groups are invisible and non-mandatory."
}

# --- Rule 3: Always disabled (load) for Company Code 1, old 1, old 2 ---
rule3_expr = 'on("load") and (dis(true,' + dis_str + '))'

rule3 = {
    "rule_name": "Expression (Client)",
    "source_fields": [CC1],
    "destination_fields": [],
    "conditionalValues": [rule3_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "load_event",
    "_reasoning": "Company Code 1, Payment block old 1, and Payment block old 2 are always disabled (read-only derived fields)."
}

# --- Rule 4: Error validation New 1 vs Old 1 ---
n1 = vo(NEW1)
o1 = vo(OLD1)
rule4_expr = (
    'adderr(' + n1 + '!="" and ' + o1 + '!="" and ' + n1 + '==' + o1 + ','
    '"Payment block New value cannot be the same as Payment block Old value",' + q(NEW1) + ');'
    'remerr(' + n1 + '=="" or ' + o1 + '=="" or ' + n1 + '!=' + o1 + ',' + q(NEW1) + ')'
)

rule4 = {
    "rule_name": "Expression (Client)",
    "source_fields": [NEW1],
    "destination_fields": [],
    "conditionalValues": [rule4_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "error",
    "_reasoning": "Payment block New 1 must not have the same value as Payment block old 1. Error shown when values match."
}

# --- Rule 5: Error validation New 2 vs Old 2 ---
n2 = vo(NEW2)
o2 = vo(OLD2)
rule5_expr = (
    'adderr(' + n2 + '!="" and ' + o2 + '!="" and ' + n2 + '==' + o2 + ','
    '"Payment block New value cannot be the same as Payment block Old value",' + q(NEW2) + ');'
    'remerr(' + n2 + '=="" or ' + o2 + '=="" or ' + n2 + '!=' + o2 + ',' + q(NEW2) + ')'
)

rule5 = {
    "rule_name": "Expression (Client)",
    "source_fields": [NEW2],
    "destination_fields": [],
    "conditionalValues": [rule5_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "error",
    "_reasoning": "Payment block New 2 must not have the same value as Payment block old 2. Error shown when values match."
}

log("Step 4: Built and placed 5 expression rules")

# --- Phase B: Clearing Rules ---
# Parent->children map from Phase A rules:
# Company Code Type -> visibility-controlled: all 8 array fields
# BUD explicitly says: "If Company Code Type changes, clear Company Code 1/2, old 1/2, New 1/2"
# Condition = true (BUD says clear on any change)

log("Step 5: Built parent->children map: 1 parent (Company Code Type -> 6 data children)")
log("Step 6: Resolved chains - 1 ultimate parent (Company Code Type)")
log("Step 7: Determined conditions: true (BUD explicitly says clear on any Company Code Type change)")

# --- Rule 6 (Phase B): Clearing on Company Code Type change ---
rule6_expr = (
    'on("change") and ('
    'cf(true,' + data_str + ');'
    'asdff(true,' + data_str + ');'
    'rffdd(true,' + data_str + ')'
    ')'
)

rule6 = {
    "rule_name": "Expression (Client)",
    "source_fields": [CCT],
    "destination_fields": [],
    "conditionalValues": [rule6_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "When Company Code Type changes, clear all data fields in both arrays (Company Code 1/2, Payment block old 1/2, Payment block New 1/2) as BUD specifies."
}

log("Step 8: Placed 1 clearing rule, skipped 0 (none already exist)")

# --- Assign rules to fields ---
for f in fields:
    vn = f["variableName"]
    if vn == CCT:
        f["rules"] = [rule1, rule2, rule6]  # visibility, load_event, clear_field
    elif vn == CC1:
        f["rules"] = [rule3]  # always disabled
    elif vn == NEW1:
        f["rules"] = [rule4]  # error validation
    elif vn == NEW2:
        f["rules"] = [rule5]  # error validation
    # All other fields keep empty rules

total_rules = sum(len(f["rules"]) for f in fields)
log("Step 9 complete: total 6 rules placed")

# Write output
with open(OUTPUT_PATH, "w") as f:
    json.dump(fields, f, indent=2)

# Write log
with open(LOG_PATH, "w") as f:
    f.write("\n".join(log_lines) + "\n")

print("Output written to:", OUTPUT_PATH)
print("Log written to:", LOG_PATH)
print("Total rules placed:", total_rules)
print()

# Verify and print summary
for f in fields:
    if f["rules"]:
        print(f"  {f['field_name']}: {len(f['rules'])} rule(s)")
        for r in f["rules"]:
            print(f"    - {r['_expressionRuleType']}: {r['_reasoning'][:80]}...")
