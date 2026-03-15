import json

# Read input
with open('output/vendor_extension/runs/1/expression_rules/temp/Adhoc_Approvers_expr_input.json') as f:
    fields = json.load(f)

# Variable names
DYW = '_doyouwanttosendtherequesttoadhocapproveradhocapprovers_'
PCA = '_pleasechoosenumberofapproveradhocapprovers_'

# Approver groups with their variable names
groups = {}
for g in range(1, 6):
    groups[g] = {
        'details': '_adhocapprover%ddetailsadhocapprovers_' % g,
        'approver': '_adhocapprover%dadhocapprovers_' % g,
        'name': '_adhocapprovername%dadhocapprovers_' % g,
        'email': '_adhocapprovereamil%dadhocapprovers_' % g,
        'mobile': '_adhocapprovermobilenumber%dadhocapprovers_' % g
    }

# Which values make each group visible
group_values = {
    1: ['1','2','3','4','5'],
    2: ['2','3','4','5'],
    3: ['3','4','5'],
    4: ['4','5'],
    5: ['5']
}

def make_cond(vals):
    parts = ['vo("%s")=="%s"' % (PCA, v) for v in vals]
    return ' or '.join(parts)

def make_neg(vals):
    if len(vals) == 1:
        return 'vo("%s")!="%s"' % (PCA, vals[0])
    return 'not(%s)' % make_cond(vals)

def all_fields(g):
    return [groups[g]['details'], groups[g]['approver'], groups[g]['name'], groups[g]['email'], groups[g]['mobile']]

def fstr(flist):
    return ','.join('"%s"' % f for f in flist)

# ============ Phase A Rule 1: DYW -> PCA visibility+mandatory ============
rule1_expr = (
    'mvi(vo("%s")=="Yes","%s");' % (DYW, PCA) +
    'minvi(vo("%s")!="Yes","%s");' % (DYW, PCA) +
    'mm(vo("%s")=="Yes","%s");' % (DYW, PCA) +
    'mnm(vo("%s")!="Yes","%s")' % (DYW, PCA)
)

# ============ Phase A Rule 2: PCA -> all groups visibility+mandatory ============
parts = []
for g in range(1, 6):
    c = make_cond(group_values[g])
    nc = make_neg(group_values[g])
    fs = fstr(all_fields(g))
    parts.append('mvi(%s,%s)' % (c, fs))
    parts.append('minvi(%s,%s)' % (nc, fs))
    parts.append('mm(%s,"%s")' % (c, groups[g]["approver"]))
    parts.append('mnm(%s,"%s")' % (nc, groups[g]["approver"]))

rule2_expr = ';'.join(parts)

# ============ Phase B: Clearing rules ============
# All approver fields (children of PCA)
all_approver = []
for g in range(1, 6):
    all_approver.extend(all_fields(g))

# DYW children = PCA + all approver fields
all_dyw_children = [PCA] + all_approver

# Rule 3: clearing on DYW (condition=true per BUD "on change clear and refresh")
rule3_expr = 'on("change") and (cf(true,%s);asdff(true,%s);rffdd(true,%s))' % (
    fstr(all_dyw_children), fstr(all_dyw_children), fstr(all_dyw_children)
)

# Rule 4: clearing on PCA (condition=true per BUD "on change clear and refresh")
rule4_expr = 'on("change") and (cf(true,%s);asdff(true,%s);rffdd(true,%s))' % (
    fstr(all_approver), fstr(all_approver), fstr(all_approver)
)

# ============ Build output ============
for field in fields:
    vn = field['variableName']
    if vn == DYW:
        field['rules'] = [
            {
                "rule_name": "Expression (Client)",
                "source_fields": [DYW],
                "destination_fields": [],
                "conditionalValues": [rule1_expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "visibility",
                "_reasoning": "Please choose number of Approver: visible and mandatory when Do you want to send the request to Adhoc Approver = Yes; invisible and non-mandatory otherwise."
            },
            {
                "rule_name": "Expression (Client)",
                "source_fields": [DYW],
                "destination_fields": [],
                "conditionalValues": [rule3_expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "clear_field",
                "_reasoning": "On change of Do you want to send the request to Adhoc Approver, clear and refresh Please choose number of Approver and all Adhoc Approver 1-5 fields."
            }
        ]
    elif vn == PCA:
        field['rules'] = [
            {
                "rule_name": "Expression (Client)",
                "source_fields": [PCA],
                "destination_fields": [],
                "conditionalValues": [rule2_expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "visibility",
                "_reasoning": "Approver group visibility and mandatory based on number selected: Group 1 visible for 1-5, Group 2 for 2-5, Group 3 for 3-5, Group 4 for 4-5, Group 5 for 5 only. Each groups dropdown field is mandatory when visible."
            },
            {
                "rule_name": "Expression (Client)",
                "source_fields": [PCA],
                "destination_fields": [],
                "conditionalValues": [rule4_expr],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "clear_field",
                "_reasoning": "On change of number of approvers, clear and refresh all Adhoc Approver 1-5 fields."
            }
        ]

# Write output
with open('output/vendor_extension/runs/1/expression_rules/temp/Adhoc_Approvers_expr_output.json', 'w') as f:
    json.dump(fields, f, indent=2)

# Write log
log_lines = [
    "Step 1: Read expression_rules.md",
    "Step 2: Read all field logic (25 fields in Adhoc Approvers panel)",
    "Step 3: Qualifying fields: Do you want to send the request to Adhoc Approver (trigger for visibility/mandatory of Please choose number of Approver), Please choose number of Approver (trigger for visibility/mandatory of all 5 approver groups). Skipped: Adhoc Approvers panel visibility (MDC approver - unclear trigger, no matching field in panel). EDV population logic (auto-fetch from VENDORFLOWAPPROVERLOGICUPDATE) handled by EDV rules, not expressions.",
    "Step 4: Built and placed 2 expression rules (visibility+mandatory)",
    "Step 5: Built parent->children map: 2 parents (DYW->26 children, PCA->25 children)",
    "Step 6: Resolved chains - 2 parents retained (both have explicit on change clear and refresh in BUD)",
    "Step 7: Determined conditions: true for all (BUD explicitly says On change clear and refresh the fields)",
    "Step 8: Placed 2 clearing rules, skipped 0 (already exist)",
    "Step 9 complete: total 4 rules placed (2 visibility+mandatory, 2 clearing)",
]
with open('output/vendor_extension/runs/1/expression_rules/temp/Adhoc_Approvers_expr_log.txt', 'w') as f:
    f.write('\n'.join(log_lines) + '\n')

print("Done! Output written to Adhoc_Approvers_expr_output.json")
print("Rule 1 (DYW visibility) length: %d" % len(rule1_expr))
print("Rule 2 (PCA visibility) length: %d" % len(rule2_expr))
print("Rule 3 (DYW clearing) length: %d" % len(rule3_expr))
print("Rule 4 (PCA clearing) length: %d" % len(rule4_expr))
print("Total fields with rules: %d" % sum(1 for f in fields if f['rules']))
print("Total fields without rules: %d" % sum(1 for f in fields if not f['rules']))
