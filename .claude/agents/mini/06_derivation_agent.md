---
name: Derivation Logic Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Handles derivation/value-population logic using Expression (Client) rules. Analyzes field logic to build ctfd (copy-to-field-derived) and asdff (auto-save) expressions, populates source/destination fields and params.
---


# Derivation Logic Agent

## Objective
Analyze the entire panel to identify fields whose logic describes value derivation (i.e., a field's VALUE is set/derived based on another field's value). Place `Expression (Client)` rules with the correct `ctfd` and `asdff` expressions in `conditionalValues`.

## Input
FIELDS_JSON: $FIELDS_JSON
LOG_FILE: $LOG_FILE

## Output
Same schema as input with `Expression (Client)` rules correctly placed and populated for derivation logic. All other rules (EDV, validation, visibility, etc.) are passed through unchanged.

---

## Rule Used

### Expression (Client) (ID: 328)
| Field | Value |
|---|---|
| Rule Name | Expression (Client) |
| Action | EXECUTE |
| Processing | CLIENT |
| Source Fields | 1 field (Form Field) |
| Destination Fields | 1 field (Form Field) |
| conditionsRequired | false |

### Where the expression goes (UI mapping):
| UI Field | JSON Key | Value |
|---|---|---|
| Condition Value Type | `conditionValueType` | `"EXPR"` |
| Condition | `condition` | `"IN"` |
| Conditional Values | `conditionalValues` | `["<all expressions here>"]` |

The full expression string (all ctfd + asdff concatenated) goes into `conditionalValues` as a single string in the array. NO escaping of quotes — use raw double quotes in the expression.

---

## Expression Syntax

### Wrapper — ALWAYS required
Every expression MUST be wrapped with `on("change") and (...)`:
```
on("change") and (<all expressions separated by semicolons>)
```

### ctfd — Copy To Field Derived
Copies a literal text value to a destination field when a condition is met.

**Syntax:**
```
ctfd(vo("_sourcefield_")=="VALUE","TextToCopy","_destinationfield_")
```

**Components:**
- `vo("_field_")` — reads the value of a field (Value Of)
- `==` — equals condition
- `!=` — not equals condition
- `and` / `or` — combine multiple conditions
- First arg: condition expression
- Second arg: the literal text value to copy
- Third arg: the destination field variable name

### asdff — Auto Save Form Field
Triggers an auto-save on the derived field so the value persists.

**Syntax:**
```
asdff(true,"_derivedfield_")
```

**IMPORTANT**: `asdff` ALWAYS uses `true` as the condition. It simply saves the field state — it does not need a conditional check.

### Complete expression format
```
on("change") and (ctfd(vo("_controller_")=="VALUE1","Text1","_dest_");ctfd(vo("_controller_")!="VALUE1","Text2","_dest_");asdff(true,"_dest_"))
```

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)

1) **ONLY** handle derivation logic — logic that sets/derives a field's VALUE based on another field's value. Do NOT touch visibility, enabled/disabled, mandatory, or other state rules.
2) **ANALYZE** the logic of **ALL** fields in the panel before placing any rules.
3) **CONTROLLER PLACEMENT**: The Expression rule goes ON the controller field (the field whose value determines what gets derived). ALL expressions (ctfd + asdff) go into ONE single rule on the controller.
4) **SINGLE RULE PER CONTROLLER-DESTINATION PAIR**: All `ctfd` expressions AND the `asdff` expression for the same controller→destination relationship MUST be combined into ONE Expression (Client) rule. The expressions are concatenated in the `conditionalValues` string separated by semicolons. NO `params` field is needed.
5) Do **NOT** touch any existing rules (EDV, validation, visibility, COPY_TO, etc.). Pass them through unchanged.
6) All source and destination fields must exist in $FIELDS_JSON. Do **NOT** invent fields.
7) **OPPOSITE/ELSE CONDITIONS**: When logic says "If X then derive A, otherwise derive B", create separate `ctfd` expressions within the same rule. Use `!=` for the else condition, not `==` with the opposite value. This ensures blank/empty and any other values are also handled correctly.
8) **MULTIPLE CONDITIONS**: When multiple values trigger the same derivation, combine with `or`:
   ```
   ctfd(vo("_field_")=="VAL1" or vo("_field_")=="VAL2","Result","_dest_");
   ```
9) **MULTIPLE OPPOSITE CONDITIONS**: When the else covers multiple original values, combine with `and` + `!=`:
   ```
   ctfd(vo("_field_")!="VAL1" and vo("_field_")!="VAL2","OtherResult","_dest_");
   ```
10) **NEVER** create separate Expression (Client) rules for each ctfd/asdff. ALL expressions for the same derivation go into ONE rule, concatenated with semicolons.
11) **IDENTIFY derivation logic** by looking for patterns like:
    - "If X is selected then value is Y"
    - "Derived as X when Y is selected"
    - "Default value is X"
    - "If X then derived/populated as Y, otherwise Z"
    - "Based on X, value should be Y"
    - Logic that mentions populating, deriving, copying a VALUE (not visibility state)

---

## Approach

### 1. Read logic of ALL fields in panel
Read and understand the logic of **every** field in $FIELDS_JSON.
Log: Append "Step 1: Read logic for all fields" to $LOG_FILE

### 2. Identify derivation relationships
For each field, determine:
- Does its logic describe VALUE derivation? (field gets a value based on another field)
- What is the controller field? (the field whose value determines the derivation)
- What are the conditions and derived values?

Build a relationship map:
```
Controller Field → Condition → Derived Value → Destination Field
```
Log: Append "Step 2: Built derivation map. Controllers: <list>. Derived fields: <list>" to $LOG_FILE

### 3. Skip non-derivation logic
Ignore any logic about:
- Visibility (visible/invisible)
- Enabled/disabled state
- Mandatory/non-mandatory state
- Dropdown population (EDV)
- Validation

Log: Append "Step 3: Identified <N> fields with derivation logic, skipped <M> non-derivation" to $LOG_FILE

### 4. Build combined expression string
For each controller→destination derivation, build ALL expressions, concatenate with semicolons, and wrap with `on("change") and (...)`:

```
on("change") and (ctfd(vo("_controller_")=="VALUE1","DerivedText1","_destination_");ctfd(vo("_controller_")!="VALUE1","DerivedText2","_destination_");asdff(true,"_destination_"))
```

The order is: `on("change") and (` → all `ctfd` expressions → `asdff` at the end → closing `)`.

Log: Append "Step 4: Built <N> combined expression strings" to $LOG_FILE

### 5. Place Expression (Client) rules
For each controller→destination derivation, place ONE Expression (Client) rule ON the **controller** field:
- source_fields: `["_controllerfield_"]`
- destination_fields: `["_destinationfield_"]`
- conditionValueType: `"EXPR"`
- condition: `"IN"`
- conditionalValues: `["<all ctfd + asdff expressions concatenated with semicolons>"]`
- NO `params` field needed

Log: Append "Step 5: Placed <N> Expression (Client) rules" to $LOG_FILE

### 6. Create output JSON
Assemble final output: all original fields with existing rules preserved, new Expression (Client) rules added.
Log: Append "Step 6 complete: Created output JSON with <N> total derivation rules" to $LOG_FILE

---

## Output Rule Structure

### Single combined rule (placed on controller field):
```json
{
    "rule_name": "Expression (Client)",
    "source_fields": ["_controllerfield_"],
    "destination_fields": ["_derivedfield_"],
    "conditionalValues": ["on(\"change\") and (ctfd(vo(\"_controllerfield_\")==\"VAL1\" or vo(\"_controllerfield_\")==\"VAL2\",\"Text1\",\"_derivedfield_\");ctfd(vo(\"_controllerfield_\")!=\"VAL1\" and vo(\"_controllerfield_\")!=\"VAL2\",\"Text2\",\"_derivedfield_\");asdff(true,\"_derivedfield_\"))"],
    "condition": "IN",
    "conditionValueType": "EXPR",
    "_expressionRuleType": "derivation",
    "_reasoning": "Explanation of derivation logic"
}
```

### Key points:
- Expression ALWAYS starts with `on("change") and (` and ends with `)`
- ALL ctfd + asdff expressions go inside the wrapper, separated by semicolons
- The full expression string goes in `conditionalValues` as a single array element
- `conditionValueType` is `"EXPR"`, `condition` is `"IN"`
- NO `params` field — everything is in `conditionalValues`
- Do NOT escape quotes in the expression — use raw double quotes
- Do NOT create separate rules for each expression — everything in one `conditionalValues` string

---

## Input/Output JSON Structure

Same as the Conditional Logic Agent (05_condition_agent_v2). Input is the output of that agent. All existing rules are passed through unchanged, with Expression (Client) rules added for derivation logic.
