---
name: Clear Child Fields Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Analyzes parent-child field relationships across the entire panel and places Expression (Client) rules on parent fields to clear all affected child fields on change. Uses cf, asdff, and rffdd expressions with intelligent condition selection.
---


# Clear Child Fields Agent

## Objective
Analyze the entire panel to identify ALL parent→child field relationships. For each parent field, place an `Expression (Client)` rule with `cf`, `asdff`, and `rffdd` expressions to clear child fields — using the correct condition based on the relationship type.

## Input
FIELDS_JSON: $FIELDS_JSON
LOG_FILE: $LOG_FILE

## Output
Same schema as input with `Expression (Client)` clearing rules correctly placed on parent fields. All other rules are passed through unchanged.

---

## Rule Used

### Expression (Client) (ID: 328)
| Field | Value |
|---|---|
| Rule Name | Expression (Client) |
| Action | EXECUTE |
| Processing | CLIENT |
| Source Fields | 1 field (Form Field) |
| Destination Fields | N fields (all child fields being cleared) |
| conditionsRequired | false |

### Where the expression goes (UI mapping):
| UI Field | JSON Key | Value |
|---|---|---|
| Condition Value Type | `conditionValueType` | `"EXPR"` |
| Condition | `condition` | `"IN"` |
| Conditional Values | `conditionalValues` | `["<all expressions here>"]` |

---

## Expression Syntax

### Wrapper — ALWAYS required
```
on("change") and (<expressions separated by semicolons>)
```

### cf — Clear Field
```
cf(<condition>,"_child1_","_child2_")
```

### asdff — Auto Save Form Field
```
asdff(true,"_child1_","_child2_")
```
**IMPORTANT**: `asdff` ALWAYS uses `true` as the condition, regardless of the relationship type. It simply saves the cleared state — it does not need a conditional check.

### rffdd — Reset Form Field Dropdown Display
```
rffdd(<condition>,"_child1_","_child2_")
```

`cf` and `rffdd` use the **same condition**. `asdff` always uses `true`. All three use the **same child fields**.

---

## When to Create Clearing Rules (CRITICAL)

Not every parent-child relationship needs a clearing rule. Think from the **UI perspective** — does the user need stale child values to be reset?

### DO create clearing rules for:
- **Cascading dropdowns**: Parent dropdown changes → child dropdown options are now wrong → must clear. Condition: `true`
- **Expression (Client) derivation rules (ctfd)**: Parent value changes → derived value is stale → clear when parent is emptied. Condition: `vo("_parent_")==""`
- **Validate EDV rules**: Lookup source changes → looked-up values are stale → clear when source is emptied. Condition: `vo("_parent_")==""`
- **Visibility/state rules**: Parent dropdown changes → hidden fields may have stale data → clear. Condition: `true`

### DO NOT create clearing rules for:
These are **specific-purpose rules** that handle their own data population. They overwrite child fields automatically on each trigger — clearing is redundant and unnecessary:
- **OCR rules**: PAN OCR, GSTIN OCR, Aadhaar Front OCR, Aadhaar Back OCR — these extract data from uploaded files and populate fields directly. The fields are typically non-editable.
- **Validation rules with API calls**: Validate PAN, Validate GSTIN, MSME Validation, Validate Pincode — these call external APIs and overwrite destination fields each time. No clearing needed.
- **Copy To rules**: These copy data from one field to another. The copy overwrites the destination on each trigger.
- **Any rule that auto-populates fields as a one-shot side effect** of a specific action (file upload, API validation, etc.)

### Use your judgment:
Ask yourself: "If I don't add a clearing rule here, will the user see stale/wrong data?" If the answer is no (because the rule overwrites data anyway), skip it. If the answer is yes (because the user selected a different dropdown option and the old child values are now invalid), add it.

## Condition Logic

The first argument to cf/asdff/rffdd is the **condition**:

- **`true`** — for cascading dropdowns, visibility controllers. Parent value changed → old children are invalid → clear immediately.
- **`vo("_parent_")==""`** — for derivation/EDV-lookup children. Only clear when parent becomes empty, otherwise derived values get wiped the moment they're set.
- **Explicit logic** — if the field's logic states when to clear, use that condition.

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)

1) **ONLY** handle clearing logic. Do NOT touch visibility, enabled/disabled, mandatory, derivation, or any other rules.
2) **ANALYZE** the rules of **ALL** fields in the panel before placing any clearing rules.
3) **PARENT FIELD = source field of a rule that affects OTHER fields**. Identify parents by scanning ALL existing rules.
4) **CHILD FIELD = any field affected by a parent through a clearing-eligible rule**. Only consider rules listed in the "DO create clearing rules for" section: cascading dropdowns, Expression (Client) derivation (ctfd), Validate EDV, and visibility/state rules. Skip children from specific-purpose rules (OCR, Validate PAN/GSTIN/MSME/Pincode, Copy To). Skip `-1` entries.
5) **PLACEMENT ON ULTIMATE PARENT**: Trace dependency chains to the root. If A→B→C (A affects B, B affects C), the clearing rule for BOTH B and C goes on **A** (the ultimate parent), not on B. Walk the chain upward: if a parent is itself a child of another field, move the rule to that grandparent. The rule is always placed on the field that has NO parent above it in the chain.
6) **ONE RULE PER ULTIMATE PARENT**: One `cf`, one `asdff`, one `rffdd` — each with ALL descendant fields (children, grandchildren, etc.). THREE function calls total.
7) **CORRECT CONDITION**: Use `true` for dropdown/selection parents. Use `vo("_parent_")==""` for populate/derive parents. Think UI.
8) Do **NOT** touch any existing rules. Pass them through unchanged.
9) All fields must exist in $FIELDS_JSON. Do **NOT** invent fields. Skip `-1` entries.
10) **DO NOT DUPLICATE**: If a parent already has a clearing Expression (Client) rule (cf/asdff/rffdd), skip it.
11) **DO NOT** create clearing rules for fields that only affect themselves.
12) **DEDUPLICATE CHILDREN**: Each child appears only ONCE per parent.

---

## Approach

### 1. Read rules of ALL fields in panel
Read every field's rules. Focus on `source_fields`, `destination_fields`, `rule_name`.
Log: Append "Step 1: Read rules for all fields" to $LOG_FILE

### 2. Build parent→children map
Scan rules that are clearing-eligible (cascading dropdowns, Expression (Client) derivation with ctfd, Validate EDV, visibility/state rules). For each such rule with destination_fields pointing to OTHER fields, record the parent→child relationship. Skip specific-purpose rules (OCR, Validate PAN/GSTIN/MSME/Pincode, Copy To). Exclude `-1` and self-references.
Log: Append "Step 2: Built parent→children map" to $LOG_FILE

### 3. Resolve to ultimate parents
Trace chains: if A→B and B→C, merge into A→[B, C]. Walk each parent upward — if a parent is itself a child of another field, move all its children to the grandparent. Repeat until every parent has no parent above it. The result is a map of ultimate parents to ALL their descendants (children, grandchildren, etc.).
Log: Append "Step 3: Resolved chains to ultimate parents" to $LOG_FILE

### 4. Determine condition per parent
For each parent, determine the correct clearing condition:
- If the parent affects children via **cascading dropdowns or visibility/state rules** → `true`
- If the parent affects children via **Validate EDV lookup or Expression (Client) derivation** → `vo("_parent_")==""`
- If a parent has BOTH types of children, create the rule with `true` for the dropdown/visibility children and `vo("_parent_")==""` for the EDV/derivation children — using separate cf/asdff/rffdd groups within the same expression.

Log: Append "Step 4: Determined conditions" to $LOG_FILE

### 5. Build clearing expression
Build the expression with THREE function calls per condition group, wrapped in `on("change") and (...)`.
Log: Append "Step 5: Built expressions" to $LOG_FILE

### 6. Place Expression (Client) rules
For each ultimate parent, place ONE rule with `_expressionRuleType: "clear_field"`.
Log: Append "Step 6: Placed rules" to $LOG_FILE

### 7. Create output JSON
Log: Append "Step 7 complete" to $LOG_FILE

---

## Output Rule Structure

### Cascading dropdown parent (condition = true):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["_category_"],
    "destination_fields": ["_subcategory_", "_item_"],
    "conditionalValues": ["on(\"change\") and (cf(true,\"_subcategory_\",\"_item_\");asdff(true,\"_subcategory_\",\"_item_\");rffdd(true,\"_subcategory_\",\"_item_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Cascading dropdown: category change invalidates subcategory/item selections."
}
```

### Validation/populate parent (condition = empty check):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["_employeeid_"],
    "destination_fields": ["_employeename_", "_department_", "_designation_"],
    "conditionalValues": ["on(\"change\") and (cf(vo(\"_employeeid_\")==\"\",\"_employeename_\",\"_department_\",\"_designation_\");asdff(true,\"_employeename_\",\"_department_\",\"_designation_\");rffdd(vo(\"_employeeid_\")==\"\",\"_employeename_\",\"_department_\",\"_designation_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Employee ID validates and populates children. Only clear when ID is emptied, otherwise derived values get wiped immediately."
}
```

### Mixed parent (both types of children):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["_region_"],
    "destination_fields": ["_branch_", "_branchmanager_", "_branchcode_"],
    "conditionalValues": ["on(\"change\") and (cf(true,\"_branch_\");asdff(true,\"_branch_\",\"_branchmanager_\",\"_branchcode_\");rffdd(true,\"_branch_\");cf(vo(\"_region_\")==\"\",\"_branchmanager_\",\"_branchcode_\");rffdd(vo(\"_region_\")==\"\",\"_branchmanager_\",\"_branchcode_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Mixed: branch is a cascading child (clear immediately). branchmanager/branchcode are populated by lookup (clear only when empty)."
}
```

### Key points:
- Expression ALWAYS starts with `on("change") and (` and ends with `)`
- THREE function calls per condition group: `cf`, `asdff`, `rffdd` with same children
- `cf` and `rffdd` condition is either `true` or `vo("_parent_")==""` depending on relationship type
- `asdff` ALWAYS uses `true` as the condition, regardless of relationship type
- `_expressionRuleType` is always `"clear_field"`
- Do NOT escape quotes — use raw double quotes

---

## Input/Output JSON Structure

Same as the Derivation Logic Agent (06_derivation_agent). Input is the output of that agent. All existing rules are passed through unchanged, with Expression (Client) clearing rules added.
