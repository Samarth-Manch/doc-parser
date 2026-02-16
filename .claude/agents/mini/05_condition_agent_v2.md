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
1) **CRITICAL**: This agent populates source_fields and destination_fields for visibility/mandatory rules (Make Visible, Make Invisible, Make Mandatory, Make Non Mandatory, Make Enabled, Make Disabled).
2) **CHECK PLACEMENT FIRST**: Before consolidating, check if rules are ALREADY on the controller field (correct) or on affected fields (wrong).
3) **IF ALREADY ON CONTROLLER**: Just populate source_fields and destination_fields - do NOT create new rules or consolidate.
4) **IF ON AFFECTED FIELDS**: Consolidate them onto the controller field with multiple destinations.
5) **KEEP EXISTING**: Do NOT remove existing rules from fields.
6) To find affected fields: read **ALL OTHER** fields' logic to find which fields mention the controller field.
7) Group rules by rule_name and conditionalValues, then combine destinations into ONE rule per condition.
8) Condition operators: **ONLY** `IN`, `NOT_IN`, or `BETWEEN`.
9) Always/By default Invisible → `condition: "NOT_IN"`, `conditionalValues: ["Invisible"]`
10) Always/By default Disabled → `condition: "NOT_IN"`, `conditionalValues: ["Disable"]`
11) Always/By default Mandatory → `condition: "NOT_IN"`, `conditionalValues: ["Mandatory"]`
12) Always/By default Non-Mandatory → `condition: "NOT_IN"`, `conditionalValues: ["Non Mandatory"]`
13) Always/By default Enabled → `condition: "NOT_IN"`, `conditionalValues: ["Enable"]`
14) Always/By default Visible → `condition: "NOT_IN"`, `conditionalValues: ["Visible"]`
15) `conditionalValues` is **ALWAYS** an array of strings.
16) "Always" and "By default" are **equivalent** keywords — both mean the rule fires unconditionally using `NOT_IN`.

---

## Approach

<field_loop>

### 1. Read logic of ALL fields in panel
Read the logic of **every** field in $FIELDS_JSON. Build a map of which fields mention which other fields. For example:
- Field X: "Dropdown with values A/B"
- Field Y: "If Field X is A, make visible"
- Field Z: "If Field X is A, make mandatory"
→ Field X affects Field Y and Field Z

### 2. Detect where visibility/mandatory rules are placed
**CRITICAL**: Check if rules are on controller fields (correct) or affected fields (wrong).

**Case A: Rules ALREADY on controller (correct placement)**
```
Field A (dropdown): Has Make Visible, Make Invisible rules
Field B logic: "If Field A is Yes, make visible"
Field C logic: "If Field A is Yes, make visible"
→ Rules are ALREADY on Field A (controller) - CORRECT
→ Just populate source/destination, don't create new rules
```

**Case B: Rules on affected fields (wrong placement)**
```
Field B: Make Visible rule (references Field A)
Field C: Make Visible rule (references Field A)
Field D: Make Visible rule (references Field A)
→ Rules are on wrong fields - need consolidation
→ Create consolidated rule on Field A with dest=["Field B","Field C","Field D"]
```

For each field with visibility/mandatory rules:
1. Check if this field is a controller (mentioned in other fields' logic)
2. If YES and field already has visibility/mandatory rules → **Case A: Just populate source/dest**
3. If rules are on affected fields → **Case B: Consolidate onto controller**

### 3. Process current field
For the current field being processed, read its logic and rules.

<rule_loop>

### 4. Check if rule needs conditional logic
Check if this rule needs conditions based on logic keywords: "if", "when", "based on", "always invisible", "always disabled", "always mandatory", "always non-mandatory", "always enabled", "always visible", "by default invisible", "by default disabled", "by default mandatory", "by default non-mandatory", "by default enabled", "by default visible".

### 5. For visibility/mandatory rules: Populate source/destination (and consolidate if needed)
**IMPORTANT**: These rules should be placed **ON** the source field (the controlling field).

If rule is Make Visible, Make Invisible, Make Mandatory, Make Non Mandatory, Make Enabled, or Make Disabled:

**Step A: Determine if consolidation is needed**

**CASE 1: Rules ALREADY on controller field (correct placement)**
```
Current field: "Field A" (dropdown)
Field A has: Make Visible, Make Invisible rules (already present)
Other fields' logic: "If Field A is Yes, make visible"
→ Rules are CORRECTLY placed on controller
→ Just populate source_fields and destination_fields
→ Do NOT create new rules
```
Actions:
1. Read logic of ALL other fields to find which mention Field A
2. Populate source_fields = ["__field_a__"]
3. Populate destination_fields = ["__field_b__", "__field_c__", ...] (all fields that mention Field A)
4. Add conditional logic (conditionalValues, condition, conditionValueType)
5. **Do NOT create new rules - just update existing ones**

**CASE 2: Rules on affected fields (wrong placement - needs consolidation)**
```
Field B: Make Visible rule (references Field A)
Field C: Make Visible rule (references Field A)
Field D: Make Visible rule (references Field A)
→ Rules are on WRONG fields
→ Need to consolidate onto Field A
```
Actions:
1. Group rules by source field (Field A)
2. Combine destinations into ONE rule
3. Create consolidated rule on Field A
4. Keep existing rules on affected fields

## Common Patterns

### Pattern 1a: Always Invisible / By Default Invisible
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

### Pattern 1b: Always Disabled / By Default Disabled
```json
{
    "rule_name": "Make Disabled (Client)",
    "source_fields": [],
    "destination_fields": ["__field__"],
    "conditionalValues": ["Disable"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 1c: Always Mandatory / By Default Mandatory
```json
{
    "rule_name": "Make Mandatory (Client)",
    "source_fields": [],
    "destination_fields": ["__field__"],
    "conditionalValues": ["Mandatory"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 1d: Always Non-Mandatory / By Default Non-Mandatory
```json
{
    "rule_name": "Make Non Mandatory (Client)",
    "source_fields": [],
    "destination_fields": ["__field__"],
    "conditionalValues": ["Non Mandatory"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 1e: Always Enabled / By Default Enabled
```json
{
    "rule_name": "Make Enabled (Client)",
    "source_fields": [],
    "destination_fields": ["__field__"],
    "conditionalValues": ["Enable"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 1f: Always Visible / By Default Visible
```json
{
    "rule_name": "Make Visible (Client)",
    "source_fields": [],
    "destination_fields": ["__field__"],
    "conditionalValues": ["Visible"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 2: Controller Dropdown (Correct - Consolidated)
```json
// Field: "Field A" (Yes/No dropdown)
// Other fields' logic: "If Field A is Yes, show this field"
// This rule should be ON Field A with multiple destinations
{
    "rule_name": "Make Visible (Client)",
    "source_fields": ["__field_a__"],
    "destination_fields": ["__field_b__", "__field_c__", "__field_d__"],
    "conditionalValues": ["Yes"],
    "condition": "IN",
    "conditionValueType": "TEXT"
}
```

### Pattern 3: Consolidation Example
```
INPUT (rules on wrong fields - opposites already exist):
Field B: Make Visible with source="Field A", dest="Field B", values=["Yes"]
Field C: Make Visible with source="Field A", dest="Field C", values=["Yes"]
Field D: Make Visible with source="Field A", dest="Field D", values=["Yes"]
Field B: Make Invisible with source="Field A", dest="Field B", values=["No"]
Field C: Make Invisible with source="Field A", dest="Field C", values=["No"]
Field D: Make Invisible with source="Field A", dest="Field D", values=["No"]

OUTPUT (consolidated on controller, keeping original rules on affected fields):
Field A:
  - Make Visible with source="Field A", dest=["Field B","Field C","Field D"], values=["Yes"]
  - Make Invisible with source="Field A", dest=["Field B","Field C","Field D"], values=["No"]
Field B: Both Make Visible and Make Invisible rules KEPT (original rules preserved)
Field C: Both Make Visible and Make Invisible rules KEPT (original rules preserved)
Field D: Both Make Visible and Make Invisible rules KEPT (original rules preserved)
```

### Pattern 4: Opposite Rules for Mandatory/Non-Mandatory (Already in Input)
```json
// Input has both Make Mandatory and Make Non Mandatory rules - consolidate each separately
// If Field A="Yes", Fields B,C become mandatory, otherwise non-mandatory
[
  {
    "rule_name": "Make Mandatory (Client)",
    "source_fields": ["__field_a__"],
    "destination_fields": ["__field_b__", "__field_c__"],
    "conditionalValues": ["Yes"],
    "condition": "IN",
    "conditionValueType": "TEXT"
  },
  {
    "rule_name": "Make Non Mandatory (Client)",
    "source_fields": ["__field_a__"],
    "destination_fields": ["__field_b__", "__field_c__"],
    "conditionalValues": ["No"],
    "condition": "IN",
    "conditionValueType": "TEXT"
  }
]
```

### Pattern 5: Multiple Different Conditions
```json
// If Field A="X" show Fields B,C and if Field A="Y" show Fields D,E
// Each condition gets its own pair of opposite rules
[
  {
    "rule_name": "Make Visible (Client)",
    "source_fields": ["__field_a__"],
    "destination_fields": ["__field_b__", "__field_c__"],
    "conditionalValues": ["X"],
    "condition": "IN",
    "conditionValueType": "TEXT"
  },
  {
    "rule_name": "Make Visible (Client)",
    "source_fields": ["__field_a__"],
    "destination_fields": ["__field_d__", "__field_e__"],
    "conditionalValues": ["Y"],
    "condition": "IN",
    "conditionValueType": "TEXT"
  }
]
```

### 6. Extract condition operator
- "Always/By default invisible/disabled/mandatory/non-mandatory/enabled/visible" → `NOT_IN`
- "If value is X", "When equals Y" → `IN`
- "If NOT X" → `NOT_IN`
- "Between X and Y" → `BETWEEN`

### 7. Extract conditional values
From logic:
- "If dropdown is X" → `["X"]`
- "If field value is A, B, C" → `["A", "B", "C"]`
- "Always/By default invisible" → `["Invisible"]`
- "Always/By default disabled" → `["Disable"]`
- "Always/By default mandatory" → `["Mandatory"]`
- "Always/By default non-mandatory" → `["Non Mandatory"]`
- "Always/By default enabled" → `["Enable"]`
- "Always/By default visible" → `["Visible"]`

### 8. Add conditional fields to rule
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

### 9. After processing all fields: Build final output
1. For each field, include ALL existing rules with conditional logic added
2. **If rules were ALREADY on controller**: No new rules created - just source/dest/conditional populated
3. **If rules were on affected fields**: Consolidated rules ADDED to controller, originals KEPT on affected fields
4. All rules get conditional logic fields added (conditionalValues, condition, conditionValueType)

**IMPORTANT**: Do NOT create duplicate rules! If a controller field already has Make Visible/Invisible rules, just populate their source/destination fields - don't create new ones.

</field_loop>

---

## Key Points
- **CRITICAL**: This agent is responsible for populating source_fields and destination_fields for visibility/mandatory rules
- **NO DUPLICATES**: If rules are ALREADY on controller field, just populate source/dest - do NOT create new rules
- **CHECK FIRST**: Determine if rules are on controller (correct) or affected fields (wrong) before taking action
- **If on controller**: Just add source_fields, destination_fields, and conditional logic to existing rules
- **If on affected fields**: Consolidate onto controller while keeping originals on affected fields
- To find destinations: search **ALL OTHER** fields' logic for mentions of the source field
- Read **EVERY** field's logic in the panel to build the complete relationship map
- When consolidating, group rules by rule_name and conditionalValues, then combine destinations
- Controller field gets ONE rule per condition with multiple destinations
- Keep all existing rule types (EDV, validations, visibility/mandatory) on their original fields
