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

The first argument to `cf` and `rffdd` determines **when** clearing triggers. `asdff` always uses `true` regardless. Choose the condition based on the relationship type:

### Cascading dropdown children
Parent is an EDV dropdown that filters child dropdown options.
**Condition: `true`** — whenever the parent changes, the child's options are now wrong and the old selection is invalid. Always clear.

### Derivation children (ctfd) and Validate EDV lookup children
Parent value populates/derives the child value.
**Condition: `vo("_parent_")==""`** — only clear when parent is emptied. If parent changes to a new non-empty value, the derivation rule re-populates the child immediately. Using `true` would wipe the child the instant it's derived.

### Visibility-controlled children
Parent has a visibility rule (mvi/minvi/sbmvi/sbminvi) that shows or hides the child.
**Condition: extract the hiding condition from the existing visibility rule** — do NOT use `true`. Find the `minvi(condition, "_child_")` call in the parent's Expression (Client) rule and use that same `condition` as the clearing condition. This ensures the child is only cleared when it is actually being hidden, not on every parent change.

**How to extract the hiding condition:**
1. Find the parent field's Expression (Client) rule in `conditionalValues`
2. Locate the `minvi(condition, "_child_")` call that targets the child field
3. Extract the `condition` argument (e.g., `vo("_A_") != "Yes"`)
4. Use that exact condition for `cf` and `rffdd`

**Example:** Parent field A has rule `mvi(vo("_A_")=="Yes","_B_");minvi(vo("_A_")!="Yes","_B_")`
→ Clearing condition for child B: `vo("_A_")!="Yes"` (the minvi condition)
→ Result: `on("change") and (cf(vo("_A_")!="Yes","_B_");asdff(true,"_B_");rffdd(vo("_A_")!="Yes","_B_"))`

If the hiding condition is complex or cannot be reliably extracted, fall back to `true` but note it.

### Explicit logic from field text
If the field's own logic text explicitly states when to clear (e.g., "clear B when A changes"), use that stated condition directly.

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)

1) **ONLY** handle clearing logic. Do NOT touch visibility, enabled/disabled, mandatory, derivation, or any other rules.
2) **ANALYZE** the rules of **ALL** fields in the panel before placing any clearing rules.
3) **PARENT FIELD = source field of a rule that affects OTHER fields**. Identify parents by scanning ALL existing rules.
4) **CHILD FIELD = any field affected by a parent through a clearing-eligible rule**. Only consider rules listed in the "DO create clearing rules for" section: cascading dropdowns, Expression (Client) derivation (ctfd), Validate EDV, and visibility/state rules. Skip children from specific-purpose rules (OCR, Validate PAN/GSTIN/MSME/Pincode, Copy To). Skip `-1` entries.
5) **PLACEMENT ON ULTIMATE PARENT**: Trace dependency chains to the root. If A→B→C (A affects B, B affects C), the clearing rule for BOTH B and C goes on **A** (the ultimate parent), not on B. Walk the chain upward: if a parent is itself a child of another field, move the rule to that grandparent. The rule is always placed on the field that has NO parent above it in the chain.
6) **ONE RULE PER ULTIMATE PARENT**: One `cf`, one `asdff`, one `rffdd` — each with ALL descendant fields (children, grandchildren, etc.). THREE function calls total.
7) **CORRECT CONDITION**: Determine per relationship type — `true` for cascading dropdowns, `vo("_parent_")==""` for derivation/EDV-lookup, **extracted minvi condition** for visibility-controlled children. See Condition Logic section. Never blindly use `true` for all types.
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
For each parent, determine the correct clearing condition per child relationship type:

| Relationship type | cf / rffdd condition | How to determine |
|---|---|---|
| Cascading EDV dropdown | `true` | Parent is source of EDV Dropdown rule targeting child |
| Derivation (`ctfd`) | `vo("_parent_")==""` | Parent has ctfd in its conditionalValues targeting child |
| Validate EDV lookup | `vo("_parent_")==""` | Parent is source of Validate EDV rule targeting child |
| Visibility-controlled | **extracted minvi condition** | Find `minvi(condition, "_child_")` in parent's Expression (Client) rule; use that condition |

**For mixed parents** (a single parent has multiple relationship types with different children):
- Group children by their condition type
- Use separate `cf(condition1, ...group1_children);rffdd(condition1, ...group1_children)` blocks for each condition group
- Share a **single** `asdff(true, ...all_children)` across all groups

**Extraction rule for visibility children:** Look in the parent's existing Expression (Client) rule's `conditionalValues[0]` for `minvi(CONDITION, "_childVar_")`. The CONDITION becomes the cf/rffdd condition for that child. If multiple visibility children have the same condition, group them. If different conditions, use separate cf/rffdd blocks.

Log: Append "Step 4: Determined conditions per child group" to $LOG_FILE

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

### Visibility-controlled parent (condition = extracted minvi condition):
Parent field A has an Expression (Client) rule: `mvi(vo("_A_")=="Yes","_B_");minvi(vo("_A_")!="Yes","_B_")`
→ minvi condition for child B is `vo("_A_")!="Yes"` → use as cf/rffdd condition:
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["_A_"],
    "destination_fields": [],
    "conditionalValues": ["on(\"change\") and (cf(vo(\"_A_\")!=\"Yes\",\"_B_\");asdff(true,\"_B_\");rffdd(vo(\"_A_\")!=\"Yes\",\"_B_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Visibility-controlled: B is hidden when A != 'Yes' (from minvi condition). Only clear B when it becomes hidden."
}
```

### Mixed parent (cascading dropdown child + derivation children):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["_region_"],
    "destination_fields": [],
    "conditionalValues": ["on(\"change\") and (cf(true,\"_branch_\");rffdd(true,\"_branch_\");cf(vo(\"_region_\")==\"\",\"_branchmanager_\",\"_branchcode_\");asdff(true,\"_branch_\",\"_branchmanager_\",\"_branchcode_\");rffdd(vo(\"_region_\")==\"\",\"_branchmanager_\",\"_branchcode_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Mixed: branch is a cascading dropdown child (clear always). branchmanager/branchcode are derived (clear only when region emptied). asdff covers all children."
}
```

### Key points:
- Expression ALWAYS starts with `on("change") and (` and ends with `)`
- **`cf` and `rffdd` condition depends on relationship type** — never blindly use `true` for all
  - Cascading dropdown: `true`
  - Derivation/Validate EDV: `vo("_parent_")==""`
  - Visibility-controlled: extracted `minvi` condition from the parent's existing expression rule
- `asdff` ALWAYS uses `true` as the condition, covers ALL children in one call
- For mixed parents: multiple `cf`/`rffdd` blocks with different conditions, one shared `asdff(true,...)` at the end covering all
- `destination_fields` is always `[]` — the expression string encodes which fields are affected
- `_expressionRuleType` is always `"clear_field"`

---

## Input/Output JSON Structure

Same as the Derivation Logic Agent (06_derivation_agent). Input is the output of that agent. All existing rules are passed through unchanged, with Expression (Client) clearing rules added.
