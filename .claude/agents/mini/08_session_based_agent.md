---
name: Session Based Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Handles session-based visibility/state rules from field logic. Analyzes ALL fields in panel to determine rule placement, source/destination fields, and conditional logic using session-based rule variants. Does NOT touch existing session-based rules.
---


# Session Based Agent

## Objective
Analyze the entire panel to determine which fields need session-based visibility/state rules based on their logic text. Place rules on the correct controller fields, populate source/destination fields, and add conditional logic (conditionalValues, condition, conditionValueType). If a session-based rule already exists on a field (same rule_name + params), skip it. Do NOT add rules for fields with empty logic — the deterministic visible/invisible is handled separately.

## Input
FIELDS_JSON: $FIELDS_JSON
SESSION_PARAMS: $SESSION_PARAMS
LOG_FILE: $LOG_FILE

## Output
Same schema as input with session-based rules correctly placed, consolidated, and populated with conditional logic. All other rules (EDV, validation, COPY_TO, derivation, clearing, etc.) are passed through unchanged.

---

## Available Rules (from Rule-Schemas.json)
Use ONLY these exact rule names.

| Rule Name (exact) | Action | ID |
|---|---|---|
| Make Visible - Session Based (Client) | SESSION_BASED_MAKE_VISIBLE | 191 |
| Make Invisible - Session Based (Client) | SESSION_BASED_MAKE_INVISIBLE | 217 |
| Enable Field - Session Based (Client) | SESSION_BASED_MAKE_ENABLED | 272 |
| Make Disable - Session Based (Client) | SESSION_BASED_MAKE_DISABLED | 193 |
| Make Mandatory - Session Based (Client) | SESSION_BASED_MAKE_MANDATORY | 252 |
| Make NonMandatory - Session Based (Client) | SESSION_BASED_MAKE_NON_MANDATORY | 197 |

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)
1) **ONLY** handle session-based rules. Do NOT touch any other rules (EDV, validation, COPY_TO, visibility client rules, derivation, clearing, etc.).
2) **DO NOT DISCARD** existing session-based rules. If a rule with the same `rule_name` + `params` already exists on a field, skip it.
3) **ANALYZE** the logic of **ALL** fields in the panel before placing any rules.
4) **CONTROLLER PLACEMENT**: Conditional session-based rules go ON the controller field (the field whose value determines the state of others).
5) **STATIC STATE PLACEMENT**: "Disable", "Non-Editable", "Invisible" etc. rules go ON the affected field itself with `source_fields: []`.
6) **CONSOLIDATE**: Group all fields affected by the same controller + condition into ONE rule with multiple `destination_fields`.
7) **OPPOSITE RULES**: When logic implies both directions (e.g., "If X=Yes make visible, otherwise invisible"), the opposite rule must use `NOT_IN` with the **original** value — NOT `IN` with the opposite value. Example: if the rule is `IN ["Yes"]` → Make Visible, the vice versa is `NOT_IN ["Yes"]` → Make Invisible. **NEVER** use `IN ["No"]` for the opposite — always negate the original condition.
8) Condition operator is ALWAYS one of: `IN`, `NOT_IN`, or `BETWEEN`.
9) `conditionalValues` is ALWAYS an array of strings.
10) `params` is ALWAYS `$SESSION_PARAMS` for every session-based rule.
11) Do **NOT** touch non-session rules. Pass them through unchanged.
12) All source and destination fields must exist in $FIELDS_JSON. Do **NOT** invent fields.
13) **SKIP PANEL fields** (type = `"PANEL"`) — do not place session-based rules on panel-type fields.
14) **STATIC RULES ARE ALWAYS SEPARATE**: "Disable", "Invisible", etc. must be individual rules placed on EACH affected field independently. **NEVER** combine static state rules across multiple fields into one rule. Each field gets its OWN static rule. Only CONDITIONAL rules (controlled by another field) can be consolidated with multiple `destination_fields`.
15) **MIXED LOGIC**: When a field has BOTH a static default state AND a conditional override (e.g., "By default disabled, enable if Field A is Yes"), create TWO separate rules:
    - One static rule on the field itself (e.g., Make Disable - Session Based with `source_fields: []`)
    - One conditional rule on the controller field (e.g., Enable Field - Session Based with `source_fields: ["__field_a__"]`)
16) **DERIVATION LOGIC IS NOT VISIBILITY**: Do NOT interpret derivation/value-population logic as visibility rules. Only handle logic that explicitly controls visibility (visible/invisible), enabled/disabled state, or mandatory/non-mandatory state.
17) **EMPTY LOGIC = NO RULES**: If a field's logic is empty or has no explicit visibility/state instruction, do NOT place any session-based rules on it. Skip it entirely.
18) **AUTO NON-MANDATORY ON INVISIBLE/DISABLE**: Whenever a field becomes **Invisible** or **Disabled** (whether static or conditional), automatically add a corresponding **Make NonMandatory - Session Based (Client)** rule with the **exact same configuration** (same source_fields, destination_fields, params, conditionalValues, condition, conditionValueType). This is because a field that is invisible or disabled cannot be filled in, so it must not be mandatory. This applies to BOTH static and conditional rules:
    - Static "Disable" → also add static "Make NonMandatory" (same `source_fields: []`, same destination)
    - Static "Invisible" → also add static "Make NonMandatory" (same `source_fields: []`, same destination)
    - Conditional "If X=Y, make disabled" → also add conditional "If X=Y, make non-mandatory" (same source, destination, condition)
    - Conditional "If X=Y, make invisible" → also add conditional "If X=Y, make non-mandatory" (same source, destination, condition)

---

## Static State Patterns
| Logic Pattern | rule_name | conditionalValues | condition | Auto Non-Mandatory? |
|---|---|---|---|---|
| Disable / Non-Editable / Non Editable | Make Disable - Session Based (Client) | `["Disable"]` | `NOT_IN` | YES |
| Invisible | Make Invisible - Session Based (Client) | `["Invisible"]` | `NOT_IN` | YES |
| Mandatory | Make Mandatory - Session Based (Client) | `["Mandatory"]` | `NOT_IN` | No |
| Non Mandatory / Not Mandatory | Make NonMandatory - Session Based (Client) | `["Non Mandatory"]` | `NOT_IN` | No |
| Enable | Enable Field - Session Based (Client) | `["Enable"]` | `NOT_IN` | No |
| Visible | Make Visible - Session Based (Client) | `["Visible"]` | `NOT_IN` | No |

All static state rules have `source_fields: []`, `destination_fields: ["__self__"]`, and `params: $SESSION_PARAMS`.

**Auto Non-Mandatory**: When "Disable" or "Invisible" is placed, also place a `Make NonMandatory - Session Based (Client)` rule with the exact same configuration (same source_fields, destination_fields, params, conditionalValues, condition). See Rule 18.

---

## Approach

### 1. Read logic of ALL fields in panel
Read and understand the logic of **every** field in $FIELDS_JSON before placing any rules.
Log: Append "Step 1: Read logic for all fields" to $LOG_FILE

### 2. Identify controllers and affected fields
For each field, determine:
- Is it a **controller**? (Other fields' logic references it for visibility/state changes)
- Is it **affected**? (Its own logic mentions being visible/invisible/disabled/etc. based on another field)
- Does it have a **static state**? ("Disable", "Non-Editable", "Invisible", etc.)
- Does it have **empty logic**? (Skip — no session-based rules needed from this agent)

Build a relationship map:
```
Controller Field → Condition Value → [Affected Fields] → Rule Type
Static States → [Fields with "Disable", "Invisible", etc.]
```
Log: Append "Step 2: Built relationship map. Controllers: <list>. Static states: <list>" to $LOG_FILE

### 3. Plan minimal rule set
For each controller, plan consolidated rules:
- ONE rule per (controller + condition value + rule type) with ALL affected fields as destinations
- Count total rules needed

For static states, plan one rule per field per state.
```
Goal: Minimize total rule count
BAD:  6 rules (1 per affected field x 2 for visible+invisible)
GOOD: 2 rules (1 Make Visible + 1 Make Invisible, each with multiple destinations)
```
Log: Append "Step 3: Planned <N> rules total" to $LOG_FILE

### 4. Create conditional rules on controller fields
For each controller field, add consolidated session-based rules:
```json
{
    "rule_name": "Make Visible - Session Based (Client)",
    "source_fields": ["_controller_field_"],
    "destination_fields": ["_field_a_", "_field_b_"],
    "params": "SECOND_PARTY",
    "conditionalValues": ["Yes"],
    "condition": "IN",
    "conditionValueType": "TEXT"
}
```
Skip if a rule with the same rule_name + params already exists on the controller.
Log: Append "Step 4: Created conditional rules on controller fields" to $LOG_FILE

### 5. Create static state rules on affected fields
For fields with static states ("Disable", "Non-Editable", "Invisible", etc.), add separate rules:
```json
{
    "rule_name": "Make Disable - Session Based (Client)",
    "source_fields": [],
    "destination_fields": ["_field_x_"],
    "params": "SECOND_PARTY",
    "conditionalValues": ["Disable"],
    "condition": "NOT_IN",
    "conditionValueType": "TEXT"
}
```
Skip if a rule with the same rule_name + params already exists on the field.
Log: Append "Step 5: Created static state rules" to $LOG_FILE

### 6. Create output JSON
Assemble final output: all original fields with non-session rules preserved, new session-based rules added.
Log: Append "Step 6 complete: Created output JSON with <N> total session-based rules" to $LOG_FILE

---

## Input JSON Structure

### FIELDS_JSON
```json
[
    {
        "field_name": "Vendor Type",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "",
        "rules": [
            {
                "rule_name": "EDV Dropdown (Client)",
                "source_fields": ["_vendortype_"],
                "destination_fields": [],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "_vendortype_"
    },
    {
        "field_name": "PAN Number",
        "type": "TEXT",
        "mandatory": true,
        "logic": "If Vendor Type is Individual, make visible",
        "rules": [
            {
                "rule_name": "Validate PAN (Client)",
                "source_fields": ["_pannumber_"],
                "destination_fields": ["_pannumber_"],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "_pannumber_"
    },
    {
        "field_name": "Search term / Reference Number",
        "type": "TEXT",
        "mandatory": false,
        "logic": "Disable",
        "rules": [],
        "variableName": "_searchtermreferencenumber_"
    },
    {
        "field_name": "Organization Name",
        "type": "TEXT",
        "mandatory": true,
        "logic": "",
        "rules": [],
        "variableName": "_organizationname_"
    }
]
```

Each field has:
- `field_name`: Display name of the field
- `type`: Field type (TEXT, DROPDOWN, DATE, etc.)
- `mandatory`: Whether the field is mandatory
- `logic`: Session-specific behavior text — this is what you read to determine rules. **Empty logic = no rules needed from this agent.**
- `rules`: Existing rules (pass through unchanged, add session-based rules here)
- `variableName`: The field's variable name (used in source_fields / destination_fields)

---

## Output JSON Structure
```json
[
    {
        "field_name": "Vendor Type",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "",
        "rules": [
            {
                "rule_name": "EDV Dropdown (Client)",
                "source_fields": ["_vendortype_"],
                "destination_fields": [],
                "_reasoning": "Populated by previous agents."
            },
            {
                "rule_name": "Make Visible - Session Based (Client)",
                "source_fields": ["_vendortype_"],
                "destination_fields": ["_pannumber_"],
                "params": "SECOND_PARTY",
                "conditionalValues": ["Individual"],
                "condition": "IN",
                "conditionValueType": "TEXT",
                "_reasoning": "PAN Number logic says visible if Vendor Type is Individual."
            },
            {
                "rule_name": "Make Invisible - Session Based (Client)",
                "source_fields": ["_vendortype_"],
                "destination_fields": ["_pannumber_"],
                "params": "SECOND_PARTY",
                "conditionalValues": ["Individual"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT",
                "_reasoning": "Opposite rule: PAN Number invisible when Vendor Type is NOT Individual."
            },
            {
                "rule_name": "Make NonMandatory - Session Based (Client)",
                "source_fields": ["_vendortype_"],
                "destination_fields": ["_pannumber_"],
                "params": "SECOND_PARTY",
                "conditionalValues": ["Individual"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT",
                "_reasoning": "Auto non-mandatory: PAN Number is invisible when NOT Individual, so must be non-mandatory too (Rule 18)."
            }
        ],
        "variableName": "_vendortype_"
    },
    {
        "field_name": "PAN Number",
        "type": "TEXT",
        "mandatory": true,
        "logic": "If Vendor Type is Individual, make visible",
        "rules": [
            {
                "rule_name": "Validate PAN (Client)",
                "source_fields": ["_pannumber_"],
                "destination_fields": ["_pannumber_"],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "_pannumber_"
    },
    {
        "field_name": "Search term / Reference Number",
        "type": "TEXT",
        "mandatory": false,
        "logic": "Disable",
        "rules": [
            {
                "rule_name": "Make Disable - Session Based (Client)",
                "source_fields": [],
                "destination_fields": ["_searchtermreferencenumber_"],
                "params": "SECOND_PARTY",
                "conditionalValues": ["Disable"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT",
                "_reasoning": "Logic says Disable. Static state rule."
            },
            {
                "rule_name": "Make NonMandatory - Session Based (Client)",
                "source_fields": [],
                "destination_fields": ["_searchtermreferencenumber_"],
                "params": "SECOND_PARTY",
                "conditionalValues": ["Disable"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT",
                "_reasoning": "Auto non-mandatory: field is disabled, so must be non-mandatory too (Rule 18)."
            }
        ],
        "variableName": "_searchtermreferencenumber_"
    },
    {
        "field_name": "Organization Name",
        "type": "TEXT",
        "mandatory": true,
        "logic": "",
        "rules": [],
        "variableName": "_organizationname_"
    }
]
```

### Key observations:
- **Vendor Type** (controller): Gets conditional rules placed ON it because PAN Number's logic references it. `source_fields` = `["_vendortype_"]`. Also gets an auto Non-Mandatory rule matching the Invisible opposite rule (Rule 18).
- **PAN Number** (affected): No new rules on itself — the conditional rules are placed on the controller (Vendor Type).
- **Search term** (static Disable): Gets a static Disable rule ON itself with `source_fields: []`, PLUS an auto Non-Mandatory rule with the same config (Rule 18).
- **Organization Name** (empty logic): Gets NO session-based rules from this agent. Empty logic = skip entirely.
