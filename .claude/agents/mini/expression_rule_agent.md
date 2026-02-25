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

## RULES (FOLLOW STRICTLY)

1) Read `.claude/agents/docs/expression_rules.md` first.
2) Analyze the logic of **ALL** fields before placing any rule.
3) For each field, decide: does its logic qualify for an expression rule?
4) **PLACEMENT**: Place the rule on the **controller/trigger field** — the field whose value drives the expression. For `on("load")` rules, place on the field that changes state at load.
5) **PAIR opposites**: `adderr` → `remerr`, `mvi` → `minvi`, `mm` → `mnm`, `en` → `dis`. Always use DeMorgan's law for negation.
6) **Numeric comparisons**: Always prefix `vo()` with `+` when comparing numbers.
7) **Event wrapping**: Use `on("change") and (...)` for change-triggered logic. Use `on("load") and (...)` for load-time logic.
8) After `ctfd`, always add `asdff` to persist the value.
9) After `cf`, always add `asdff` + `rffdd` (for dropdowns) or `rffd` (for non-dropdowns).
10) All fields referenced must exist in `$FIELDS_JSON`. Do NOT invent fields.
11) Do NOT touch existing rules. Pass them through unchanged.
12) If unsure whether logic qualifies, skip it.

---

## Approach

### 1. Read reference document
Read `.claude/agents/docs/expression_rules.md` to load the full function reference.
Log: Append "Step 1: Read expression_rules.md" to $LOG_FILE

### 2. Read all fields
Read every field's `logic` in $FIELDS_JSON.
Log: Append "Step 2: Read all field logic" to $LOG_FILE

### 3. Classify each field
For each field, determine:
- Does its logic qualify as an expression rule?
- Which functions are needed?
- Which field is the controller?

Log: Append "Step 3: Qualifying fields: <list>" to $LOG_FILE

### 4. Build expressions
For each qualifying field, build the full expression string using functions from the reference doc.
Log: Append "Step 4: Built <N> expressions" to $LOG_FILE

### 5. Place rules and output
Add Expression (Client) rules on the appropriate fields. Preserve all existing rules.
Log: Append "Step 5 complete: placed <N> Expression (Client) rules" to $LOG_FILE

---

## Output Rule Structure

```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["__triggerField__"],
    "destination_fields": ["__affectedField__"],
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
    "destination_fields": ["__gstNumber__"],
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
    "destination_fields": ["__pan__"],
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
    "destination_fields": ["__age__"],
    "conditionalValues": ["setAgeFromDate(\"_dateOfBirth_\",\"_age_\");asdff(vo(\"_age_\")!=\"\",\"_age_\");adderr(vo(\"_age_\")!=\"\" and +vo(\"_age_\")<18,\"Age must be 18 or above\",\"_age_\",\"_dateOfBirth_\");remerr(vo(\"_age_\")!=\"\" and +vo(\"_age_\")>=18,\"_age_\",\"_dateOfBirth_\")"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "age",
    "_reasoning": "Age derived from DOB; error shown if under 18."
}
```
