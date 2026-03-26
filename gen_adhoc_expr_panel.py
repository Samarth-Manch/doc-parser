#!/usr/bin/env python3
"""Generate expression rules for Adhoc Approvers panel."""
import json

INPUT = "output/vendor_extension/runs/18/expression_rules/temp/Adhoc_Approvers_expr_input.json"
OUTPUT = "output/vendor_extension/runs/18/expression_rules/temp/Adhoc_Approvers_expr_output.json"
LOG = "output/vendor_extension/runs/18/expression_rules/temp/Adhoc_Approvers_expr_log.txt"

with open(INPUT, "r") as f:
    fields = json.load(f)

log_lines = [
    "Step 1: Read expression_rules.md",
    "Step 2: Read all field logic",
]

var_to_idx = {}
for i, field in enumerate(fields):
    var_to_idx[field["variableName"]] = i


def make_rule(source_var, expr, rtype, reasoning):
    return {
        "rule_name": "Expression (Client)",
        "source_fields": [source_var],
        "destination_fields": [],
        "conditionalValues": [expr],
        "condition": "IN",
        "conditionValueType": "EXPR",
        "_expressionRuleType": rtype,
        "_reasoning": reasoning,
    }


# Variable names
DOYOU = "_doyouwanttosendtherequesttoadhocapproveradhocapprovers_"
PLEASE = "_pleasechoosenumberofapproveradhocapprovers_"

# Group field variable names
groups = {}
for n in range(1, 6):
    groups[n] = {
        "details": "_adhocapprover%ddetailsadhocapprovers_" % n,
        "dropdown": "_adhocapprover%dadhocapprovers_" % n,
        "name": "_adhocapprovername%dadhocapprovers_" % n,
        "email": "_adhocapprovereamil%dadhocapprovers_" % n,
        "mobile": "_adhocapprovermobilenumber%dadhocapprovers_" % n,
    }

# Verify all exist
for n in range(1, 6):
    for k, v in groups[n].items():
        assert v in var_to_idx, "Missing: %s" % v

# Values that make each group visible
GROUP_VALS = {
    1: ["1", "2", "3", "4", "5"],
    2: ["2", "3", "4", "5"],
    3: ["3", "4", "5"],
    4: ["4", "5"],
    5: ["5"],
}


def or_cond(var, vals):
    """Build OR condition: vo("var")=="v1" or vo("var")=="v2" ..."""
    return " or ".join('vo("%s")=="%s"' % (var, v) for v in vals)


def and_not_cond(var, vals):
    """Build AND-NOT condition: vo("var")!="v1" and vo("var")!="v2" ..."""
    return " and ".join('vo("%s")!="%s"' % (var, v) for v in vals)


def qq(varname):
    """Quote a variable name for use inside expression string."""
    return '"%s"' % varname


# ================================================================
# PHASE A: Expression rules from logic text
# ================================================================

# Rule A1: On DOYOU -> visibility + mandatory for PLEASE
expr_a1 = ";".join([
    'mvi(vo("%s")=="Yes","%s")' % (DOYOU, PLEASE),
    'mm(vo("%s")=="Yes","%s")' % (DOYOU, PLEASE),
    'minvi(vo("%s")!="Yes","%s")' % (DOYOU, PLEASE),
    'mnm(vo("%s")!="Yes","%s")' % (DOYOU, PLEASE),
])
rule_a1 = make_rule(
    DOYOU, expr_a1, "visibility",
    "Please choose number of Approver: visible+mandatory when Yes, invisible+non-mandatory otherwise.",
)

# Rule A2: On PLEASE -> visibility + mandatory for all 5 groups
a2_parts = []
for n in range(1, 6):
    g = groups[n]
    vis = or_cond(PLEASE, GROUP_VALS[n])
    inv = and_not_cond(PLEASE, GROUP_VALS[n])
    all5 = ",".join(qq(g[k]) for k in ["details", "dropdown", "name", "email", "mobile"])

    a2_parts.append("mvi(%s,%s)" % (vis, all5))
    a2_parts.append("mm(%s,%s)" % (vis, qq(g["dropdown"])))
    a2_parts.append("minvi(%s,%s)" % (inv, all5))
    a2_parts.append("mnm(%s,%s)" % (inv, qq(g["dropdown"])))

expr_a2 = ";".join(a2_parts)
rule_a2 = make_rule(
    PLEASE, expr_a2, "visibility",
    "Visibility+mandatory for all 5 approver groups based on number of approvers selected.",
)

log_lines.append(
    "Step 3: Qualifying: visibility on DOYOU->PLEASE, visibility on PLEASE->groups1-5. "
    "Skipped: MDC approver (session-based), EDV auto-fetch (EDV stage)"
)
log_lines.append("Step 4: Built and placed 2 expression rules (Phase A)")

# ================================================================
# PHASE B: Clearing rules
# ================================================================

# Collect child field lists
vis_dropdowns = [PLEASE] + [groups[n]["dropdown"] for n in range(1, 6)]
text_fields = []
for n in range(1, 6):
    text_fields.extend([groups[n]["name"], groups[n]["email"], groups[n]["mobile"]])
all_c1 = vis_dropdowns + text_fields

# C1: On DOYOU change
hide = 'vo("%s")!="Yes"' % DOYOU
vds = ",".join(qq(v) for v in vis_dropdowns)
ts = ",".join(qq(v) for v in text_fields)
ac1 = ",".join(qq(v) for v in all_c1)

expr_c1 = 'on("change") and (cf(%s,%s);rffdd(%s,%s);cf(true,%s);asdff(true,%s))' % (
    hide, vds, hide, vds, ts, ac1
)
rule_c1 = make_rule(
    DOYOU, expr_c1, "clear_field",
    "Mixed clearing: dropdowns cleared when not Yes (visibility); text fields cleared on any change (explicit BUD). Chain includes all descendants.",
)

# C2: On PLEASE change
c2_dd = [groups[n]["dropdown"] for n in range(1, 6)]
all_c2 = c2_dd + text_fields
ac2 = ",".join(qq(v) for v in all_c2)
c2d = ",".join(qq(v) for v in c2_dd)

expr_c2 = 'on("change") and (cf(true,%s);asdff(true,%s);rffdd(true,%s))' % (ac2, ac2, c2d)
rule_c2 = make_rule(
    PLEASE, expr_c2, "clear_field",
    "Clear+refresh all approver dropdowns and text fields on number change. Explicit BUD clear logic.",
)

log_lines.append("Step 5: Built parent->children map: 2 parents")
log_lines.append("Step 6: Resolved chains - 2 parents")
log_lines.append("Step 7: Determined conditions")
log_lines.append("Step 8: Placed 2 clearing rules, skipped 0")

# ================================================================
# Add rules to fields
# ================================================================
fields[var_to_idx[DOYOU]]["rules"].append(rule_a1)
fields[var_to_idx[DOYOU]]["rules"].append(rule_c1)
fields[var_to_idx[PLEASE]]["rules"].append(rule_a2)
fields[var_to_idx[PLEASE]]["rules"].append(rule_c2)

total = sum(len(f["rules"]) for f in fields)
log_lines.append("Step 9 complete: total %d rules placed (2 visibility + 2 clearing)" % total)

with open(OUTPUT, "w") as f:
    json.dump(fields, f, indent=2)

with open(LOG, "w") as f:
    f.write("\n".join(log_lines) + "\n")

print("Done. %d rules placed. Output: %s" % (total, OUTPUT))
