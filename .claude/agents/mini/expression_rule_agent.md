---
name: Expression Rule Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Analyzes ALL fields in a panel and places Expression (Client) rules for logic that can be expressed using the Manch expression engine. Reads expression_rules.md to determine which functions apply, then builds and places the correct expression strings.
---

# Expression Rule Agent

## Objective
Analyze every field in the panel. For each field, read its logic and determine whether it can be implemented as an `Expression (Client)` rule. If yes, build the correct expression string and place the rule. If the logic cannot be expressed using the available expression functions, skip it.

## Input
FIELDS_JSON: $FIELDS_JSON
LOG_FILE: $LOG_FILE

## Output
Same schema as input with `Expression (Client)` rules added where applicable. All existing rules are passed through unchanged.

---

## Reference Document
Read `.claude/agents/docs/expression_rules.md` before processing. It contains:
- All available expression functions and their signatures
- Operators and logic syntax
- Common composition patterns with examples
- Critical rules and gotchas

Use this document to determine whether a given field logic is expressible and how to write the expression.

---

## Rule Used

### Expression (Client) (ID: 328)
| UI Field | JSON Key | Value |
|---|---|---|
| Condition Value Type | `conditionValueType` | `"EXPR"` |
| Condition | `condition` | `"IN"` |
| Conditional Values | `conditionalValues` | `["<full expression string>"]` |

The complete expression string goes into `conditionalValues[0]` as a single string.

---

## Eligibility: Can this logic become an Expression rule?

A field's logic **qualifies** if it can be mapped to one or more functions documented in `expression_rules.md`. Examples:
- Showing/hiding fields based on another field's value → `mvi`, `minvi`
- Making fields mandatory/non-mandatory → `mm`, `mnm`
- Enabling/disabling → `en`, `dis`
- Deriving or copying a value → `ctfd`, `asdff`, `concat`, `cwd`
- Clearing child fields on parent change → `cf`, `asdff`, `rffdd`
- Validation errors → `adderr`, `remerr`
- Age calculation → `setAgeFromDate`
- Regex validation → `rgxtst`
- Session/party-based visibility → `sbmvi`, `sbminvi`, `pt()`, `mt()`
- Load-time rules → `on("load")` with `po()`, `tso()`

A field's logic **does NOT qualify** if:
- It describes external API calls or server-side validation
- It describes EDV dropdown population (handled by `params.conditionList`, not expressions)
- The logic is too vague to map to any concrete expression function
- It refers to workflows, approvals, or backend processes

---

## Cross-Panel Field Detection (CRITICAL)

Logic sometimes references fields from **other panels**. Do NOT blindly skip such logic. Instead, follow this decision process for every logic statement:

### Step: Check if the trigger field exists in FIELDS_JSON

For each piece of logic that involves a condition referencing another field:

1. **Look up the trigger field** in `$FIELDS_JSON` by matching field name or variableName
2. **If the trigger field IS in FIELDS_JSON** → the rule is intra-panel. Place the Expression (Client) rule normally on the trigger field.
3. **If the trigger field is NOT in FIELDS_JSON** → it belongs to another panel. Skip that specific condition — it will be handled by the Inter-Panel agent.

### Partial logic: extract what you can

A single logic sentence may contain BOTH intra-panel and cross-panel references. Extract and place the intra-panel parts; skip only the cross-panel parts.

**Example:**
> "Field X: Visible if Trigger A = 'Yes' AND Trigger B = 'No'. Invisible otherwise."
> - Trigger A is in this panel → place visibility rule driven by Trigger A
> - Trigger B is NOT in this panel → skip the cross-panel part, but still place the rule for Trigger A's condition

**Key rule**: A logic referencing a field NOT in FIELDS_JSON is NOT a reason to skip the whole logic block. Ask: *"Is there a part of this logic I CAN implement with fields that exist here?"* If yes, implement that part.

### Never skip intra-panel logic because of cross-panel references

> ❌ WRONG: "Field B's logic mentions Field A from another panel → skip entire logic"
> ✅ RIGHT: "Field A is in this panel → place expression rule on Field A targeting Field B. Cross-panel refs are skipped."

---

## RULES (FOLLOW STRICTLY)

1) Read `.claude/agents/docs/expression_rules.md` first.
2) Analyze the logic of **ALL** fields before placing any rule.
3) For each field, decide: does its logic qualify for an expression rule?
4) **PLACEMENT — CRITICAL**: Place the rule on the **controller/trigger field** — the field whose value change drives the expression. **NOT** on the affected/destination field.
   - The BUD often describes logic on the AFFECTED field, but the rule MUST be placed on the CAUSING field.
   - Read ALL field logic first, then determine which field is the actual trigger.
   - For `on("load")` rules, place on the field that changes state at load.
5) **PAIR opposites**: `adderr` → `remerr`, `mvi` → `minvi`, `mm` → `mnm`, `en` → `dis`. Always use DeMorgan's law for negation.
6) **Numeric comparisons**: Always prefix `vo()` with `+` when comparing numbers.
7) **Event wrapping**: Use `on("change") and (...)` for change-triggered logic. Use `on("load") and (...)` for load-time logic.
8) After `ctfd`, always add `asdff` to persist the value.
9) After `cf`, always add `asdff` + `rffdd` (for dropdowns) or `rffd` (for non-dropdowns).
10) **Field existence check**: Before placing any rule, verify the **trigger field** (source) exists in `$FIELDS_JSON`. If the trigger is in another panel, skip that specific rule — but check if other parts of the same logic ARE implementable with fields that do exist. Never invent variableNames.
11) Do NOT touch existing rules. Pass them through unchanged.
12) If unsure whether logic qualifies, skip it. But do NOT skip logic simply because the affected field's logic mentions a cross-panel field — check whether the trigger is local first.
13) **Character checks always use `rgxtst`**: Any logic involving a specific character at a position, string prefix/suffix, length check, or character type check MUST use `rgxtst`. Never use `==` or manual string comparisons for character-level logic. See Pattern 17 in the reference doc for common patterns.
14) **`destination_fields` must always be empty (`[]`)**: The expression string in `conditionalValues[0]` already encodes which fields are affected. Do NOT populate `destination_fields`.
15) **Party-scoped logic uses session-based functions**: If the logic mentions "second party", "first party", "vendor", "initiator", or restricts visibility/mandatory state to a specific party:
    - **Visibility**: use `sbmvi`/`sbminvi` with param `"FIRST_PARTY"` or `"SECOND_PARTY"`. Never use `mvi`/`minvi` for party-scoped visibility.
    - **Mandatory**: use `mm(pt() == "FP", ...)` for first-party mandatory, `mm(pt() == "SP", ...)` for second-party mandatory. Pair with `mnm(pt() == "SP/FP", ...)` for the opposite party.
    - **Keywords**: "mandatory in first party", "mandatory in second party", "applicable in first party", "mandatory for vendor", "initiator fills", "second party only", etc.
    - See Critical Rules 17 and 18, and Patterns 13 and 18 in the reference doc.

---

## EXECUTE Rule Placement (READ CAREFULLY)

The BUD frequently describes logic on the **wrong field** for rule placement purposes. The BUD writes logic from the perspective of the field being affected, but Expression (Client) rules must be placed on the **field that causes the effect**.

### How to identify the correct trigger field

1. **Read ALL fields first** — scan every field's logic in the panel
2. **Look for references** — when Field B's logic says "based on Field A" or "depends on Field A", the rule goes on **Field A**
3. **Aggregate** — multiple affected fields may reference the same trigger. Combine them into ONE rule on the trigger field

### Examples of BUD logic → correct placement

| BUD says (on affected field) | Trigger field | Rule placed on |
|------------------------------|---------------|----------------|
| "Region" logic: "Dropdown values filtered based on Country" | Country | **Country** (cascade clear: `cf` + `asdff` + `rffdd` for Region) |
| "GST Number" logic: "Visible if GST Present = Yes" | GST Present | **GST Present** (visibility: `mvi`/`minvi` targeting GST Number) |
| "Type Code" logic: "Derived as CO when PAN Type = Company" | PAN Type | **PAN Type** (derivation: `ctfd` + `asdff` targeting Type Code) |
| "IFSC Code" logic: "Cleared when Cheque Image changes" | Cheque Image | **Cheque Image** (clear: `on("change")` + `cf` + `asdff` + `rffd` targeting IFSC) |
| "Clerk fields" logic: "Mandatory when Account Group = INDS/FIVN" | Account Group | **Account Group** (mandatory: `mm`/`mnm` targeting Clerk fields) |
| "Bank fields" logic: "Visible when Create Bank Key = Yes" | Create Bank Key | **Create Bank Key** (visibility + mandatory targeting Bank fields) |
| "Field X" logic: "Mandatory in first party" | Field X itself | **Field X** (session-based: `sbmvi(true,"FIRST_PARTY","_x_");sbminvi(true,"SECOND_PARTY","_x_");mm(pt()=="FP","_x_");mnm(pt()=="SP","_x_")`) |
| "Field Y" logic: "Mandatory in second party" | Field Y itself | **Field Y** (session-based: `sbmvi(true,"SECOND_PARTY","_y_");sbminvi(true,"FIRST_PARTY","_y_");mm(pt()=="SP","_y_");mnm(pt()=="FP","_y_")`) |

### Consolidation rule

When multiple affected fields share the same trigger field and same condition, combine them into a **single** Expression (Client) rule on the trigger field with all destination fields listed together:

```
// BAD — separate rules for each affected field:
Rule on "Country": cf(true, "_region_");asdff(true, "_region_");rffdd(true, "_region_")
Rule on "Country": cf(true, "_city_");asdff(true, "_city_");rffdd(true, "_city_")

// GOOD — one consolidated rule:
Rule on "Country": on("change") and (cf(true, "_region_", "_city_");asdff(true, "_region_", "_city_");rffdd(true, "_region_", "_city_"))
```

---

## Approach

This agent runs in **two phases**: Phase A places expression rules from logic text; Phase B adds clearing rules from the dependency graph of existing + newly placed rules.

### Phase A — Logic-Text Expression Rules

#### Step 1: Read reference document
Read `.claude/agents/docs/expression_rules.md` to load the full function reference.
Log: Append "Step 1: Read expression_rules.md" to $LOG_FILE

#### Step 2: Read all fields
Read every field's `logic` in $FIELDS_JSON.
Log: Append "Step 2: Read all field logic" to $LOG_FILE

#### Step 3: Classify each field
For each field, determine:
- Does its logic qualify as an expression rule?
- Which functions are needed?
- Which field is the controller (trigger)?
- **Is the trigger field present in FIELDS_JSON?** If yes → place rule. If no → skip that specific rule (cross-panel, handled later). Do NOT skip the whole field's logic — check every condition individually.

Log: Append "Step 3: Qualifying fields: <list>, skipped cross-panel: <list>" to $LOG_FILE

#### Step 4: Build and place expression rules
Build expression strings using functions from the reference doc. Add Expression (Client) rules on the appropriate fields. Preserve all existing rules.
Log: Append "Step 4: Built and placed <N> expression rules" to $LOG_FILE

---

### Phase B — Clearing Rules (Dependency Graph)

This phase replicates the logic of the Clear Child Fields Agent. It scans ALL rules (original + newly placed in Phase A) to identify parent→child relationships and adds `cf`/`asdff`/`rffdd` clearing rules for parents that do not already have one.

#### Step 5: Build parent→children map
Scan ALL fields' rules (both original rules and rules placed in Phase A). For each rule, if it has `source_fields` pointing to field X and `destination_fields` pointing to other fields, record X as a parent. Only include **clearing-eligible** rule types:
- EDV Dropdown (Client) / cascading dropdowns — condition: `true`
- Expression (Client) with `ctfd` derivation — condition: `vo("_parent_")==""`
- Validate EDV — condition: `vo("_parent_")==""`
- Make Visible / Make Invisible / visibility rules — condition: `true`

**Skip these rule types — they auto-populate and don't need clearing:**
- OCR rules (PAN OCR, GSTIN OCR, Aadhaar OCR, etc.)
- Validate PAN, Validate GSTIN, Validate MSME, Validate Pincode
- Copy To (Client / Server)
- Any rule whose `destination_fields` contains `-1` or self-references

Log: Append "Step 5: Built parent→children map: <N> parents" to $LOG_FILE

#### Step 6: Resolve to ultimate parents (chain tracing)
Trace dependency chains to find ultimate root parents. If A→B and B→C, then A is the ultimate parent of BOTH B and C. Walk each parent upward: if a parent is itself a child of another field, move all its children to that grandparent. Repeat until every parent has no parent above it in the chain. The result maps each ultimate parent to ALL its descendants (children, grandchildren, etc.).

Log: Append "Step 6: Resolved chains — <N> ultimate parents" to $LOG_FILE

#### Step 7: Determine clearing condition per child relationship
For each child of an ultimate parent, pick the condition based on how that child is linked to the parent:

| Relationship | cf / rffdd condition | Rationale |
|---|---|---|
| Cascading EDV dropdown | `true` | Parent change always invalidates child dropdown options |
| Derivation (`ctfd`) | `vo("_parent_")==""`  | Only clear when parent emptied; derivation re-populates child on non-empty change |
| Validate EDV lookup | `vo("_parent_")==""` | Same as derivation |
| Visibility-controlled | **extracted minvi condition** | Clear only when child is being hidden, not on every parent change |

**For visibility-controlled children**: find `minvi(CONDITION, "_child_")` in the parent's Expression (Client) rule (already in the rules from Phase A or original rules). Extract `CONDITION` and use it as the `cf`/`rffdd` condition. Example: `minvi(vo("_A_")!="Yes","_B_")` → condition is `vo("_A_")!="Yes"`.

**For mixed parents** (different relationship types for different children): group children by condition, emit separate `cf(...group)/rffdd(...group)` blocks for each group, then one shared `asdff(true, ...all_children)` covering everything.

Log: Append "Step 7: Determined conditions" to $LOG_FILE

#### Step 8: Place clearing rules (deduplicated)
For each ultimate parent that does **NOT** already have a clearing `Expression (Client)` rule (i.e., no existing rule with `cf`/`asdff`/`rffdd` in its `conditionalValues`):
- Build `on("change") and (cf(...);asdff(true,...);rffdd(...))`
- `asdff` ALWAYS uses `true` as condition, covering all children
- Use `_expressionRuleType: "clear_field"`
- Skip if a clearing rule already exists on this field (deduplication)

Log: Append "Step 8: Placed <N> clearing rules, skipped <N> (already exist)" to $LOG_FILE

#### Step 9: Write output
Combine Phase A rules and Phase B clearing rules. Output the full panel with all rules preserved.
Log: Append "Step 9 complete: total <N> rules placed" to $LOG_FILE

---

## Output Rule Structure

```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__triggerField__"],
    "destination_fields": [],
    "conditionalValues": ["<full expression string>"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "<visibility|mandatory|derivation|clear_field|error|age|session|load_event>",
    "_reasoning": "<brief explanation of what this expression does and why>"
}
```

### Example — visibility toggle:
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__gstPresent__"],
    "destination_fields": [],
    "conditionalValues": ["mvi(vo(\"_gstPresent_\")==\"Yes\",\"_gstNumber_\");minvi(vo(\"_gstPresent_\")!=\"Yes\",\"_gstNumber_\")"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "visibility",
    "_reasoning": "GST number visible when GST Present = Yes, invisible otherwise."
}
```

### Example — validation error:
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__pan__"],
    "destination_fields": [],
    "conditionalValues": ["adderr(vo(\"_pan_\")!=\"\" and not rgxtst(vo(\"_pan_\"),\"/^[A-Z]{5}[0-9]{4}[A-Z]$/\"),\"Invalid PAN format\",\"_pan_\");remerr(vo(\"_pan_\")==\"\" or rgxtst(vo(\"_pan_\"),\"/^[A-Z]{5}[0-9]{4}[A-Z]$/\"),\"_pan_\")"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "error",
    "_reasoning": "PAN format validated via regex; error shown for invalid values, removed when valid."
}
```

### Example — age calculation:
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__dateOfBirth__"],
    "destination_fields": [],
    "conditionalValues": ["setAgeFromDate(\"_dateOfBirth_\",\"_age_\");asdff(vo(\"_age_\")!=\"\",\"_age_\");adderr(vo(\"_age_\")!=\"\" and +vo(\"_age_\")<18,\"Age must be 18 or above\",\"_age_\",\"_dateOfBirth_\");remerr(vo(\"_age_\")!=\"\" and +vo(\"_age_\")>=18,\"_age_\",\"_dateOfBirth_\")"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "age",
    "_reasoning": "Age derived from DOB; error shown if under 18."
}
```

### Example — clearing (cascading dropdown, condition = true):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__category__"],
    "destination_fields": [],
    "conditionalValues": ["on(\"change\") and (cf(true,\"_subcategory_\",\"_item_\");asdff(true,\"_subcategory_\",\"_item_\");rffdd(true,\"_subcategory_\",\"_item_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Cascading dropdown: category change always invalidates subcategory/item selections."
}
```

### Example — clearing (derivation/EDV, condition = empty check):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__employeeid__"],
    "destination_fields": [],
    "conditionalValues": ["on(\"change\") and (cf(vo(\"_employeeid_\")==\"\",\"_employeename_\",\"_department_\");asdff(true,\"_employeename_\",\"_department_\");rffdd(vo(\"_employeeid_\")==\"\",\"_employeename_\",\"_department_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Derivation parent: only clear when ID is emptied, not on every change."
}
```

### Example — clearing (visibility-controlled child, condition = extracted minvi condition):
Parent A has rule `mvi(vo("_A_")=="Yes","_B_");minvi(vo("_A_")!="Yes","_B_")` → hiding condition is `vo("_A_")!="Yes"`:
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__A__"],
    "destination_fields": [],
    "conditionalValues": ["on(\"change\") and (cf(vo(\"_A_\")!=\"Yes\",\"_B_\");asdff(true,\"_B_\");rffdd(vo(\"_A_\")!=\"Yes\",\"_B_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Visibility-controlled: B hidden when A != 'Yes' (minvi condition). Clear only when B is being hidden, not on every change."
}
```

### Example — clearing (mixed parent: cascading child + derived children):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__region__"],
    "destination_fields": [],
    "conditionalValues": ["on(\"change\") and (cf(true,\"_branch_\");rffdd(true,\"_branch_\");cf(vo(\"_region_\")==\"\",\"_branchmanager_\",\"_branchcode_\");asdff(true,\"_branch_\",\"_branchmanager_\",\"_branchcode_\");rffdd(vo(\"_region_\")==\"\",\"_branchmanager_\",\"_branchcode_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "clear_field",
    "_reasoning": "Mixed: branch=cascading(true), branchmanager/branchcode=derived(empty check). asdff covers all."
}
```

> **Clearing rule key points:**
> - Always wrap with `on("change") and (...)`
> - **`cf` and `rffdd` condition is determined per relationship type** — never blindly `true` for all
>   - Cascading dropdown → `true`
>   - Derivation / Validate EDV → `vo("_parent_")==""`
>   - Visibility-controlled → extracted `minvi` condition from the parent's expression rule
> - `asdff` ALWAYS uses `true`, covering all children in one call
> - `destination_fields` stays `[]`
> - Deduplicate: skip if a clearing rule (cf/asdff/rffdd) already exists on the parent
