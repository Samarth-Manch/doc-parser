import json
import sys

# Paths
input_path = 'output/vendor_extension/runs/5/expression_rules/temp/Adhoc_Approvers_expr_input.json'
output_path = 'output/vendor_extension/runs/5/expression_rules/temp/Adhoc_Approvers_expr_output.json'
log_path = 'output/vendor_extension/runs/5/expression_rules/temp/Adhoc_Approvers_expr_log.txt'

# Read input
with open(input_path) as f:
    fields = json.load(f)

log_lines = []
log_lines.append("Step 1: Read expression_rules.md")
log_lines.append("Step 2: Read all field logic")

# Variable names for trigger fields
t1 = fields[1]['variableName']  # Do you want to send the request to Adhoc Approver?
t2 = fields[2]['variableName']  # Please choose number of Approver

# Group fields (5 groups of 5 fields each, starting at index 3)
groups = {}
for n in range(1, 6):
    start = 3 + (n - 1) * 5
    groups[n] = fields[start:start + 5]

# Collect all group variable names and dropdown variable names
all_group_vars = []
dd_group_vars = []
for n in range(1, 6):
    for f in groups[n]:
        all_group_vars.append(f['variableName'])
        if f['type'] == 'DROPDOWN':
            dd_group_vars.append(f['variableName'])

log_lines.append(
    "Step 3: Qualifying fields: '{}', '{}'. ".format(fields[1]['field_name'], fields[2]['field_name']) +
    "Skipped cross-panel: '{}' (MDC approver reference not in panel). ".format(fields[0]['field_name']) +
    "Skipped EDV-related logic on approver/name/email/mobile fields (handled by params)."
)

# === Phase A - Logic-Text Expression Rules ===

# Rule 1: Visibility/Mandatory on t1 -> t2
rule1_expr = (
    'mvi(vo("{t1}")=="Yes","{t2}");'
    'minvi(vo("{t1}")!="Yes","{t2}");'
    'mm(vo("{t1}")=="Yes","{t2}");'
    'mnm(vo("{t1}")!="Yes","{t2}")'
).format(t1=t1, t2=t2)

rule1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [t1],
    "destination_fields": [],
    "conditionalValues": [rule1_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Please choose number of Approver is visible and mandatory when 'Do you want to send the request to Adhoc Approver?' = Yes, otherwise invisible and non-mandatory."
}

# Rule 2: Visibility/Mandatory on t2 -> all 5 groups
rule2_parts = []
for n in range(1, 6):
    gf = groups[n]
    all_vars_str = ','.join('"' + f['variableName'] + '"' for f in gf)
    dd_var = next(f['variableName'] for f in gf if f['type'] == 'DROPDOWN')

    rule2_parts.append('mvi(+vo("{t2}")>={n},{vars})'.format(t2=t2, n=n, vars=all_vars_str))
    rule2_parts.append('minvi(+vo("{t2}")<{n},{vars})'.format(t2=t2, n=n, vars=all_vars_str))
    rule2_parts.append('mm(+vo("{t2}")>={n},"{dd}")'.format(t2=t2, n=n, dd=dd_var))
    rule2_parts.append('mnm(+vo("{t2}")<{n},"{dd}")'.format(t2=t2, n=n, dd=dd_var))

rule2_expr = ';'.join(rule2_parts)
rule2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [t2],
    "destination_fields": [],
    "conditionalValues": [rule2_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "Controls visibility and mandatory state of Adhoc Approver groups 1-5 based on the number of approvers selected. Group N visible/mandatory when count >= N, invisible/non-mandatory otherwise."
}

fields[1]['rules'].append(rule1)
fields[2]['rules'].append(rule2)

log_lines.append("Step 4: Built and placed 2 expression rules (visibility/mandatory)")

# === Phase B - Clearing Rules ===

log_lines.append("Step 5: Built parent->children map: 2 parents (t1->t2+groups, t2->groups)")
log_lines.append("Step 6: Resolved chains - 2 parents with clearing rules (both have explicit BUD clearing instructions)")
log_lines.append("Step 7: Determined conditions - true for both (BUD explicit 'on change clear and refresh')")

# Clearing Rule 1: On t1 -> clear t2 + all group fields
all_children_1 = [t2] + all_group_vars
dd_children_1 = [t2] + dd_group_vars

cf1_str = ','.join('"' + v + '"' for v in all_children_1)
rffdd1_str = ','.join('"' + v + '"' for v in dd_children_1)

clear1_expr = 'on("change") and (cf(true,{cf});asdff(true,{asdff});rffdd(true,{rffdd}))'.format(
    cf=cf1_str, asdff=cf1_str, rffdd=rffdd1_str
)
clear1 = {
    "rule_name": "Expression (Client)",
    "source_fields": [t1],
    "destination_fields": [],
    "conditionalValues": [clear1_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "On change of 'Do you want to send the request to Adhoc Approver?', clear and refresh 'Please choose number of Approver' and all 25 approver group fields."
}

# Clearing Rule 2: On t2 -> clear all group fields
cf2_str = ','.join('"' + v + '"' for v in all_group_vars)
rffdd2_str = ','.join('"' + v + '"' for v in dd_group_vars)

clear2_expr = 'on("change") and (cf(true,{cf});asdff(true,{asdff});rffdd(true,{rffdd}))'.format(
    cf=cf2_str, asdff=cf2_str, rffdd=rffdd2_str
)
clear2 = {
    "rule_name": "Expression (Client)",
    "source_fields": [t2],
    "destination_fields": [],
    "conditionalValues": [clear2_expr],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "On change of 'Please choose number of Approver', clear and refresh all 25 approver group fields (groups 1-5)."
}

fields[1]['rules'].append(clear1)
fields[2]['rules'].append(clear2)

log_lines.append("Step 8: Placed 2 clearing rules, skipped 0 (already exist)")

# Count total rules
total_rules = sum(len(f['rules']) for f in fields)
log_lines.append("Step 9 complete: total {} rules placed".format(total_rules))

# Write output
with open(output_path, 'w') as f:
    json.dump(fields, f, indent=2, ensure_ascii=False)

# Write log
with open(log_path, 'w') as f:
    f.write('\n'.join(log_lines) + '\n')

print("Done. Wrote {} rules across {} fields.".format(
    total_rules,
    sum(1 for f in fields if f['rules'])
))

# Verify
with open(output_path) as f:
    out = json.load(f)
for f_item in out:
    if f_item['rules']:
        print("\n  {}: {} rules".format(f_item['field_name'], len(f_item['rules'])))
        for r in f_item['rules']:
            expr_preview = r['conditionalValues'][0][:120] + "..."
            print("    - {}: {}".format(r['_expressionRuleType'], expr_preview))
