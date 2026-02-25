---
name: Inter-Panel Complex Rules Agent (Pass 2)
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Handles complex cross-panel rules (derivation, EDV, clearing) flagged by Pass 1. Uses full panel JSON for involved panels. Creates Expression (Client) rules with ctfd/cf/asdff/rffdd syntax.
---


# Inter-Panel Complex Rules Agent (Pass 2)

## Objective
Process complex cross-panel references flagged by the Pass 1 analysis agent. These are references that require specialized expression syntax (derivation, EDV, clearing) and couldn't be handled as simple Copy To or visibility rules.

You receive the complex reference records from Pass 1 plus the **full field JSON** for all involved panels (not just 2 fields — the complete panel data). Use this context to create properly structured Expression (Client) rules.

## Input
COMPLEX_REFS_FILE: $COMPLEX_REFS_FILE
INVOLVED_PANELS_FILE: $INVOLVED_PANELS_FILE
COMPLEX_RULES_FILE: $COMPLEX_RULES_FILE
LOG_FILE: $LOG_FILE

## Real-Time Logging (MANDATORY)
You MUST write progress to LOG_FILE at EVERY step so the user can monitor via `tail -f`.
Use the Write tool to append to LOG_FILE BEFORE and AFTER each step.
Format each line clearly:
```
Step 1 START: Reading complex refs and involved panels...
Step 1 DONE: 3 complex refs (2 derivation, 1 clearing), 2 involved panels (45 fields)
Step 3 START: Processing derivation ref 1/2: __vendorname__ (Basic Details) -> __firstname__ (Vendor Basic Details)
Step 3 PROGRESS: Built ctfd expression: ctfd(vo("_vendorname_")!="",...)
Step 3 DONE: Created Expression (Client) rule on __vendorname__ in Basic Details
Step 4 START: Processing clearing ref 1/1: __processtype__ (Basic Details) -> __addressproof__ (Address Details)
Step 4 DONE: Created clearing Expression (Client) rule with cf/asdff/rffdd
Step 6 START: Writing output file...
Step 6 DONE: Wrote complex_rules.json (3 rules for 2 panels)
COMPLETE: Pass 2 finished successfully
```
This is NOT optional — the user needs to see what you are doing in real-time.

## Output
One output file:
- **COMPLEX_RULES_FILE** — Rules created for complex cross-panel references, in the same merge format as Pass 1's direct_rules.json

---

## Available Rule

### Expression (Client) (ID: 328)
| Field | Value |
|---|---|
| Rule Name | Expression (Client) |
| Action | EXECUTE |
| Processing | CLIENT |
| Source Fields | 1 field (Form Field) |
| Destination Fields | 1+ fields (Form Field) |
| conditionsRequired | false |

### Where the expression goes (UI mapping):
| UI Field | JSON Key | Value |
|---|---|---|
| Condition Value Type | `conditionValueType` | `"EXPR"` |
| Condition | `condition` | `"IN"` |
| Conditional Values | `conditionalValues` | `["<all expressions here>"]` |

---

## Complex Reference Types

### Type 1: Derivation (`type: "derivation"`)

Cross-panel value derivation — a field's VALUE is set/derived based on another panel's field value.

**Expression syntax — ctfd (Copy To Field Derived):**
```
ctfd(vo("_sourcefield_")=="VALUE","TextToCopy","_destinationfield_")
```

**Components:**
- `vo("_field_")` — reads the value of a field (Value Of)
- `==` / `!=` — condition operators
- `and` / `or` — combine multiple conditions
- First arg: condition expression
- Second arg: the literal text value to copy
- Third arg: the destination field variable name

**asdff (Auto Save Form Field):**
```
asdff(true,"_derivedfield_")
```
Always uses `true` as condition.

**Complete derivation expression:**
```
on("change") and (ctfd(vo("_controller_")=="VALUE1","Text1","_dest_");ctfd(vo("_controller_")!="VALUE1","Text2","_dest_");asdff(true,"_dest_"))
```

**Rules:**
- Expression ALWAYS starts with `on("change") and (` and ends with `)`
- ALL ctfd + asdff expressions go inside the wrapper, separated by semicolons
- Use `!=` for else conditions, not `==` with opposite value
- Multiple values: combine with `or` — `vo("_f_")=="A" or vo("_f_")=="B"`
- Rule placed ON the **controller/source field** (the field whose value triggers derivation)
- `_expressionRuleType`: `"derivation"`

### Type 2: Clearing (`type: "clearing"`)

Cross-panel clearing — when a parent field in one panel changes, child fields in another panel need to be cleared.

**Expression syntax:**
```
cf(<condition>,"_child1_","_child2_")
asdff(true,"_child1_","_child2_")
rffdd(<condition>,"_child1_","_child2_")
```

**Conditions:**
- `true` — for cascading dropdowns, visibility controllers (clear immediately on change)
- `vo("_parent_")==""` — for derivation/EDV-lookup children (only clear when parent emptied)

**Complete clearing expression:**
```
on("change") and (cf(true,"_child1_","_child2_");asdff(true,"_child1_","_child2_");rffdd(true,"_child1_","_child2_"))
```

**Rules:**
- THREE function calls per condition group: `cf`, `asdff`, `rffdd` with same children
- `cf` and `rffdd` use the same condition
- `asdff` ALWAYS uses `true`
- Rule placed ON the **parent field**
- `_expressionRuleType`: `"clear_field"`

### Type 3: EDV (`type: "edv"`)

Cross-panel EDV lookup — a field's dropdown/value depends on a reference table filtered by a field from another panel.

**EDV rules use `params` with `conditionList`:**
```json
{
    "rule_name": "EXT_DROP_DOWN",
    "source_fields": ["__parentfield__"],
    "destination_fields": ["__dropdownfield__"],
    "params": {
        "conditionList": [
            {
                "ddType": "...",
                "criterias": "...",
                "da": "..."
            }
        ]
    },
    "_inter_panel_source": "cross-panel"
}
```

For cross-panel EDV, the source field is from another panel. The rule is typically placed on the dropdown field itself.

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)

1) **ONLY** process the complex references listed in COMPLEX_REFS_FILE. Do NOT create additional rules.
2) **Use ONLY variableNames** that exist in INVOLVED_PANELS_FILE. Do NOT invent fields.
3) **Mark all rules** with `_inter_panel_source: "cross-panel"` for traceability.
4) **CONTROLLER PLACEMENT**: Expression (Client) rules go ON the controller/source field.
5) **SINGLE RULE PER CONTROLLER-DESTINATION**: Combine all expressions for the same controller→destination into ONE rule.
6) Do NOT escape quotes in expressions — use raw double quotes.
7) For derivation, use `!=` for else conditions, not `==` with opposite value.
8) For clearing, use the correct condition (`true` for cascading, `vo("_parent_")==""` for derived).
9) **OUTPUT FORMAT**: Same merge format as Pass 1 — `{panel: [{target_field_variableName, rules_to_add}]}`.
10) If a complex reference cannot be resolved (e.g., referenced field doesn't exist), skip it and log a warning.

---

## Approach

### 1. Read input files
**LOG** → Append "Step 1 START: Reading complex refs and involved panels..." to $LOG_FILE
Read COMPLEX_REFS_FILE (list of complex references) and INVOLVED_PANELS_FILE (full panel data for all involved panels).
**LOG** → Append "Step 1 DONE: <N> complex references (<breakdown by type>), <M> involved panels (<total fields> fields)" to $LOG_FILE

### 2. Group references by type
**LOG** → Append "Step 2 START: Grouping references by type..." to $LOG_FILE
Group complex references by type: derivation, clearing, edv.
**LOG** → Append "Step 2 DONE: Derivation: <N>, Clearing: <N>, EDV: <N>" to $LOG_FILE

### 3. Process derivation references
**LOG** → Append "Step 3 START: Processing <N> derivation references..." to $LOG_FILE
For each derivation reference:
- Find the source field in the involved panels data
- Find the target/destination field
- Build the ctfd + asdff expression
- Create Expression (Client) rule on the source/controller field
**LOG** → For EACH ref, append "Step 3 PROGRESS: Processing derivation <i>/<N>: <source_field> (<source_panel>) -> <target_field> (<target_panel>)" to $LOG_FILE
**LOG** → For EACH ref done, append "Step 3 PROGRESS: Created Expression (Client) rule with ctfd on <host_field>" to $LOG_FILE
**LOG** → Append "Step 3 DONE: Processed <N> derivation rules" to $LOG_FILE

### 4. Process clearing references
**LOG** → Append "Step 4 START: Processing <N> clearing references..." to $LOG_FILE
For each clearing reference:
- Determine the parent field and child fields
- Determine the correct condition
- Build cf + asdff + rffdd expression
- Create Expression (Client) rule on the parent field
**LOG** → For EACH ref, append progress to $LOG_FILE
**LOG** → Append "Step 4 DONE: Processed <N> clearing rules" to $LOG_FILE

### 5. Process EDV references
**LOG** → Append "Step 5 START: Processing <N> EDV references..." to $LOG_FILE
For each EDV reference:
- Find the source and target fields
- Build the params with conditionList
- Create the appropriate EDV rule
**LOG** → For EACH ref, append progress to $LOG_FILE
**LOG** → Append "Step 5 DONE: Processed <N> EDV rules" to $LOG_FILE

### 6. Write output file
**LOG** → Append "Step 6 START: Writing output file..." to $LOG_FILE
Write COMPLEX_RULES_FILE with all created rules in the merge format.
**LOG** → Append "Step 6 DONE: Wrote complex_rules.json (<N> rules for <M> panels)" to $LOG_FILE
**LOG** → Append "COMPLETE: Pass 2 finished successfully" to $LOG_FILE

---

## Output Structure

### COMPLEX_RULES_FILE — Complex rules ready to merge
Same format as Pass 1's direct_rules.json:
```json
{
    "<host_panel_name>": [
        {
            "target_field_variableName": "__hostfield__",
            "rules_to_add": [
                {
                    "rule_name": "Expression (Client)",
                    "source_fields": ["__sourcefield__"],
                    "destination_fields": ["__destfield__"],
                    "conditionalValues": ["on(\"change\") and (ctfd(vo(\"_sourcefield_\")==\"VALUE\",\"DerivedText\",\"_destfield_\");asdff(true,\"_destfield_\"))"],
                    "condition": "IN",
                    "conditionValueType": "EXPR",
                    "_expressionRuleType": "derivation",
                    "_reasoning": "Cross-panel derivation: description",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```

If no complex rules could be created, write an empty dict: `{}`

---

## Worked Examples

### Example 1: Derivation — Extract first word from another panel's field

**Complex reference:**
```json
{
    "type": "derivation",
    "source_panel": "Basic Details",
    "target_panel": "Vendor Basic Details",
    "source_field": "__vendorname__",
    "target_field": "__firstname__",
    "logic": "First Name = first word of Vendor Name (from Basic Details Panel)",
    "description": "Extract first word from vendor name"
}
```

**Result:**
```json
{
    "Basic Details": [
        {
            "target_field_variableName": "__vendorname__",
            "rules_to_add": [
                {
                    "rule_name": "Expression (Client)",
                    "source_fields": ["__vendorname__"],
                    "destination_fields": ["__firstname__"],
                    "conditionalValues": ["on(\"change\") and (ctfd(vo(\"_vendorname_\")!=\"\",vo(\"_vendorname_\").split(\" \")[0],\"_firstname_\");ctfd(vo(\"_vendorname_\")==\"\",\"\",\"_firstname_\");asdff(true,\"_firstname_\"))"],
                    "condition": "IN",
                    "conditionValueType": "EXPR",
                    "_expressionRuleType": "derivation",
                    "_reasoning": "Cross-panel derivation: First name from first word of vendor name in Basic Details",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```

### Example 2: Clearing — Clear child fields when cross-panel parent changes

**Complex reference:**
```json
{
    "type": "clearing",
    "source_panel": "Basic Details",
    "target_panel": "Address Details",
    "source_field": "__processtype__",
    "target_field": "__addressproof__",
    "logic": "Address fields depend on Process Type (from Basic Details)",
    "description": "Clear address fields when process type changes"
}
```

**Result:**
```json
{
    "Basic Details": [
        {
            "target_field_variableName": "__processtype__",
            "rules_to_add": [
                {
                    "rule_name": "Expression (Client)",
                    "source_fields": ["__processtype__"],
                    "destination_fields": ["__addressproof__"],
                    "conditionalValues": ["on(\"change\") and (cf(true,\"_addressproof_\");asdff(true,\"_addressproof_\");rffdd(true,\"_addressproof_\"))"],
                    "condition": "IN",
                    "conditionValueType": "EXPR",
                    "_expressionRuleType": "clear_field",
                    "_reasoning": "Cross-panel clearing: Clear address proof when process type changes in Basic Details",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```

### Example 3: Conditional derivation — If/else value population

**Complex reference:**
```json
{
    "type": "derivation",
    "source_panel": "Basic Details",
    "target_panel": "Vendor Basic Details",
    "source_field": "__processtype__",
    "target_field": "__vendorcategory__",
    "logic": "If Process Type (from Basic Details) is India-Domestic then Vendor Category = Local, otherwise = International",
    "description": "Derive vendor category from process type"
}
```

**Result:**
```json
{
    "Basic Details": [
        {
            "target_field_variableName": "__processtype__",
            "rules_to_add": [
                {
                    "rule_name": "Expression (Client)",
                    "source_fields": ["__processtype__"],
                    "destination_fields": ["__vendorcategory__"],
                    "conditionalValues": ["on(\"change\") and (ctfd(vo(\"_processtype_\")==\"India-Domestic\",\"Local\",\"_vendorcategory_\");ctfd(vo(\"_processtype_\")!=\"India-Domestic\",\"International\",\"_vendorcategory_\");asdff(true,\"_vendorcategory_\"))"],
                    "condition": "IN",
                    "conditionValueType": "EXPR",
                    "_expressionRuleType": "derivation",
                    "_reasoning": "Cross-panel derivation: Vendor Category derived from Process Type. India-Domestic→Local, otherwise→International",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```
