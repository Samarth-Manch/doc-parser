---
name: Conditional Logic Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Adds conditional logic (conditionalValues, condition, conditionValueType) to rules and populates source/destination fields for visibility/mandatory rules by analyzing all fields' logic in the panel.
---

# Conditional Logic Agent

## Objective
Add conditional logic fields to rules that need conditions AND populate source_fields and destination_fields for visibility/mandatory rules by analyzing the entire panel's logic.

## Input
FIELDS_JSON: $FIELDS_JSON
LOG_FILE: $LOG_FILE

## Output
Same schema as input with conditional logic fields added to rules and source/destination fields populated for visibility/mandatory rules.

---

## RULES
1) **CRITICAL**: For visibility/mandatory rules (Make Visible, Make Invisible, Make Mandatory, Make Non Mandatory, Make Enabled, Make Disabled), the rules are placed **ON the SOURCE field** (the controlling dropdown). To find destinations, you **MUST** read **ALL OTHER** fields' logic to find which fields mention the current field.
2) Condition operators: **ONLY** `IN`, `NOT_IN`, or `BETWEEN`.
3) Always Invisible → `condition: "NOT_IN"`, `conditionalValues: ["Invisible"]`
4) Always Disabled → `condition: "NOT_IN"`, `conditionalValues: ["Disable"]`
5) `conditionalValues` is **ALWAYS** an array of strings.

---

## Approach

<field_loop>

### 1. Read logic of ALL fields in panel
Read the logic of **every** field in $FIELDS_JSON. Build a map of which fields mention which other fields. For example:
- Field X: "Dropdown with values A/B"
- Field Y: "If Field X is A, make visible"
- Field Z: "If Field X is A, make mandatory"
→ Field X affects Field Y and Field Z

### 2. Process current field
For the current field being processed, read its logic and rules.

<rule_loop>

### 3. Check if rule needs conditional logic
Check if this rule needs conditions based on logic keywords: "if", "when", "based on", "always invisible", "always disabled".

### 4. For visibility/mandatory rules: Populate source and destination
**IMPORTANT**: These rules are placed **ON** the source field (the controlling field). When you see a Make Visible/Invisible/Mandatory rule on a field, that field is the SOURCE, and you must find the DESTINATIONs.

If rule is Make Visible, Make Invisible, Make Mandatory, Make Non Mandatory, Make Enabled, or Make Disabled:

**Step A: Identify if current field is a controller**
- Does current field have dropdown values like Yes/No, or is it mentioned in other fields' logic?
- If YES → current field is a CONTROLLER (source field)
- Rule is placed ON this field

**Step B: Find destination fields**
Since rule is placed ON the source field, you must search **ALL OTHER fields' logic** to find which fields this source affects:
1. Search through every other field's logic in the panel
2. Look for mentions of current field name
3. Find logic like "if [current field] is X", "based on [current field]", "when [current field] equals Y"
4. Those fields are the destinations

**Example - Controller dropdown with rule placed ON it:**
```
Current field: "Field A" (dropdown with values X/Y)
Rule on current field: Make Visible (Client)

Search all other fields:
- "Field B" logic: "If Field A is X, show this field" → DESTINATION
- "Field C" logic: "If Field A is X, show this field" → DESTINATION
- "Field D" logic: "If Field A is X, show this field" → DESTINATION
- "Field E" logic: "Always visible" → NOT affected

Result:
→ source: ["__field_a__"] (current field)
→ destination: ["__field_b__", "__field_c__", "__field_d__"] (found by searching)
```

## Common Patterns

### Pattern 1: Always Invisible
```json
{
    "rule_name": "Make Invisible (Client)",
    "source_fields": [],
    "destination_fields": ["__field__"],
    "conditionalValues": ["Invisible"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 2: Controller Dropdown
```json
// Field: "Do you wish to add mobile numbers?" (Yes/No dropdown)
// Other fields' logic: "If mobile dropdown is Yes, show this field"
{
    "rule_name": "Make Visible (Client)",
    "source_fields": ["__mobile_dropdown__"],
    "destination_fields": ["__mobile_2__", "__mobile_3__", "__mobile_4__"],
    "conditionalValues": ["Yes"],
    "condition": "IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 3: Affected Field
```json
// Field: "Mobile Number 2"
// Field logic: "If mobile dropdown is Yes, make visible"
{
    "rule_name": "Make Visible (Client)",
    "source_fields": ["__mobile_dropdown__"],
    "destination_fields": ["__mobile_2__"],
    "conditionalValues": ["Yes"],
    "condition": "IN",
    "conditionValueType": "TEXT"
}
```

### 5. Extract condition operator
- "Always invisible/disabled" → `NOT_IN`
- "If value is X", "When equals Y" → `IN`
- "If NOT X" → `NOT_IN`
- "Between X and Y" → `BETWEEN`

### 6. Extract conditional values
From logic:
- "If dropdown is X" → `["X"]`
- "If field value is A, B, C" → `["A", "B", "C"]`
- "Always invisible" → `["Invisible"]`
- "Always disabled" → `["Disable"]`

### 7. Add conditional fields to rule
```json
{
    "rule_name": "Make Visible (Client)",
    "source_fields": ["__field_a__"],
    "destination_fields": ["__field_b__", "__field_c__"],
    "conditionalValues": ["Value1"],
    "condition": "IN",
    "conditionValueType": "TEXT"
}
```

</rule_loop>
</field_loop>

---

## Key Points
- **CRITICAL**: Visibility/mandatory rules are placed **ON** the source field (the controller)
- When you see Make Visible/Invisible/Mandatory rule on a field, that field IS the source
- To find destinations: search **ALL OTHER** fields' logic for mentions of the source field
- Read **EVERY** field's logic in the panel to build the complete relationship map
- DO NOT assume - always verify by reading other fields' logic
