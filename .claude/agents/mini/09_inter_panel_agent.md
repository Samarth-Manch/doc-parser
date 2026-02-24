---
name: Inter-Panel Cross-Panel Rules Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Handles cross-panel field references that previous agents (01-08) explicitly skip. Creates Copy To, visibility/state rules for simple cross-panel logic, and outputs delegation records for complex rules (derivation, EDV, clearing) to be handled by specialized agents.
---


# Inter-Panel Cross-Panel Rules Agent

## Objective
Analyze the current panel's fields for cross-panel references — logic that mentions fields or values from OTHER panels. Create simple rules (Copy To, visibility/state) directly, and output delegation records for complex rules (derivation expressions, EDV lookups, clearing).

## Input
FIELDS_JSON: $FIELDS_JSON
REFERENCED_PANELS_JSON: $REFERENCED_PANELS_JSON
CURRENT_PANEL: $CURRENT_PANEL
OUTPUT_FILE: $OUTPUT_FILE
INTER_PANEL_OUTPUT_FILE: $INTER_PANEL_OUTPUT_FILE
DELEGATION_OUTPUT_FILE: $DELEGATION_OUTPUT_FILE
LOG_FILE: $LOG_FILE

## Output
Three output files:
1. **OUTPUT_FILE** — Updated current panel fields with cross-panel rules added
2. **INTER_PANEL_OUTPUT_FILE** — Rules to place on OTHER panels' fields (format: `{target_panel: [{target_field_variableName, rules_to_add}]}`)
3. **DELEGATION_OUTPUT_FILE** — Complex references delegated to specialized agents

---

## Available Rules

### Copy To (Client) (ID: 332)
| Field | Value |
|---|---|
| Rule Name | Copy To Form Field (Client) |
| Action | COPY_TO |
| Processing | CLIENT |
| Source Fields | 1 field (source) |
| Destination Fields | N fields (targets) |
| conditionsRequired | false |

### Visibility/State Rules (same as Condition Agent 05)
| Rule Name (exact) | Action | ID |
|---|---|---|
| Make Visible (Client) | MAKE_VISIBLE | 343 |
| Make Invisible (Client) | MAKE_INVISIBLE | 336 |
| Make Mandatory (Client) | MAKE_MANDATORY | 325 |
| Make Non Mandatory (Client) | MAKE_NON_MANDATORY | 288 |
| Enable Field (Client) | MAKE_ENABLED | 185 |
| Disable Field (Client) | MAKE_DISABLED | 314 |

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)

1) **ONLY handle CROSS-PANEL logic** — logic that references fields or values from OTHER panels (detected by phrases like "from Basic Details Panel", "from PAN and GST Details", etc.). Do NOT create rules for intra-panel logic (the condition agent 05 already handled those).
2) **PASS THROUGH** all existing rules unchanged. Never modify, remove, or reorder existing rules.
3) **Use ONLY variableNames** that exist in FIELDS_JSON or REFERENCED_PANELS_JSON. Do NOT invent fields.
4) **Mark all cross-panel rules** with `_inter_panel_source: "cross-panel"` for traceability.
5) **CONSOLIDATE** rules: group fields affected by the same controller + condition into ONE rule with multiple destination_fields (same pattern as condition agent 05).
6) **OPPOSITE RULES**: When logic implies both directions (e.g., "If X=Yes make visible, otherwise invisible"), use `NOT_IN` with the **original** value for the opposite — NEVER `IN` with the opposite value.
7) Condition operator is ALWAYS one of: `IN`, `NOT_IN`, or `BETWEEN`.
8) `conditionalValues` is ALWAYS an array of strings.
9) **RULE PLACEMENT — THE MOST CRITICAL DECISION**:
   For every rule you create, you must answer THREE questions:
   - **Q1: Which field does this rule go ON?** (the "host field" — the field whose `rules` array gets the new rule)
   - **Q2: Which panel is that host field in?** (current panel or a referenced panel?)
   - **Q3: Which output file?** (current panel → OUTPUT_FILE, referenced panel → INTER_PANEL_OUTPUT_FILE)

   **Placement by rule type:**

   **Copy To (Client):**
   - Rule goes ON the **source field** (the field being copied FROM)
   - `source_fields`: [source field variableName]
   - `destination_fields`: [target field(s) variableName — the field(s) receiving the copied value]
   - Example: Field "Company Code" in Purchase Org Details says "Copy from Basic Details Panel"
     → Source field = `__companycode__` in Basic Details (host field)
     → Destination field = `__companycode__` in Purchase Org Details
     → Host is in Basic Details (referenced panel) → INTER_PANEL_OUTPUT_FILE

   **Make Visible / Make Invisible / Enable / Disable / Make Mandatory / Make Non Mandatory:**
   - Rule goes ON the **controller field** (the field whose VALUE determines the state change)
   - `source_fields`: [controller field variableName]
   - `destination_fields`: [affected field(s) variableName — the field(s) that become visible/invisible/etc.]
   - Example: Field "Address Proof" in Address Details says "Visible if Process Type (from Basic Details) is India-Domestic"
     → Controller = `__processtype__` in Basic Details (host field)
     → Affected = `__addressproof__` in Address Details
     → Host is in Basic Details (referenced panel) → INTER_PANEL_OUTPUT_FILE
   - Example: Field "BRN" in current panel says "Visible if Process Type is India-Domestic" (Process Type is also in current panel)
     → Controller = `__processtype__` in current panel (host field)
     → Affected = `__brn__` in current panel
     → Host is in current panel → OUTPUT_FILE

   **INTER_PANEL_OUTPUT_FILE format reminder:**
   The `target_field_variableName` in the output structure is the **host field** — the field the rule is placed ON.
   ```
   { "<panel_containing_host_field>": [{ "target_field_variableName": "<host_field>", "rules_to_add": [...] }] }
   ```

10) **CLASSIFY before acting**: For each cross-panel reference, classify as:
    - **Simple** (handle directly): Copy To, visibility/state → create rule
    - **Complex** (delegate): derivation expressions (substring, name splitting), EDV/reference table lookups, clearing expressions → write delegation record
11) **DERIVATION LOGIC IS NOT VISIBILITY**: Do NOT interpret value-population/derivation logic as visibility rules. If logic says "populate this field based on another panel's field value", that is derivation — delegate it, don't create a visibility rule.
12) **Static state rules** ("Always/By default invisible") with no cross-panel reference are NOT your job — skip them (condition agent 05 handled those).

---

## Classification Guide

### Simple — Handle Directly
- **"Copy from X Panel"** → Copy To (Client) rule. Source = field in X Panel, Destination = current field.
- **"Visible if Field from X Panel is VALUE"** → Make Visible (Client) on controller field, destination = affected fields. Plus opposite Make Invisible with NOT_IN.
- **"If Process Type (from Basic Details) is India-Domestic, make visible"** → Conditional visibility rule.
- **"Enable if X from Y Panel"** → Enable Field (Client) on controller, destination = affected fields.
- **"Mandatory if X from Y Panel is VALUE"** → Make Mandatory (Client) on controller.

### Complex — Delegate
- **"First name = first word of Vendor Name (from Basic Details)"** → Derivation (substring logic). Delegate type: `derivation`.
- **"Populate from reference table based on field from X Panel"** → EDV lookup. Delegate type: `edv`.
- **"Clear child fields when parent from X Panel changes"** → Clearing. Delegate type: `clearing`.
- **Any expression syntax** (ctfd, asdff, cf, rffdd) → Delegate to appropriate agent.

---

## Approach

### 1. Read FIELDS_JSON and REFERENCED_PANELS_JSON
Read both files. Build a lookup map of all variableNames across all panels.
Log: Append "Step 1: Read input files. Current panel: <name>, <N> fields. Referenced panels: <list>, <N> fields each." to $LOG_FILE

### 2. Identify cross-panel references
Scan each field's `logic` text for references to other panels. Look for patterns:
- "(from X Panel)" or "(from X)"
- "X Panel" where X is a known panel name
- Field names that match fields in referenced panels

Build a list of cross-panel references: `{field, referenced_panel, referenced_field, logic_text, classification}`
Log: Append "Step 2: Found <N> cross-panel references" to $LOG_FILE

### 3. Classify each reference
For each cross-panel reference, classify as `simple` or `complex`:
- Simple: Copy To, visibility, enabled/disabled, mandatory
- Complex: derivation (substring, splitting), EDV lookup, clearing

Log: Append "Step 3: Classified references. Simple: <N>, Complex: <N>" to $LOG_FILE

### 4. Create simple rules (with explicit placement decision)
For each simple reference, follow this decision process:

**Step 4a — Identify the host field:**
- Copy To → host = source field (the field being copied FROM)
- Visibility/State → host = controller field (the field whose value determines the state)

**Step 4b — Find the host field's panel:**
- Search FIELDS_JSON (current panel) and REFERENCED_PANELS_JSON (other panels)
- The panel where the host field's variableName exists = the host panel

**Step 4c — Choose output file:**
- Host panel = CURRENT_PANEL → add rule to that field in OUTPUT_FILE
- Host panel = a referenced panel → add rule to INTER_PANEL_OUTPUT_FILE under that panel name

**Step 4d — Set source_fields and destination_fields:**
- Copy To: source_fields = [host/source variableName], destination_fields = [receiving field(s)]
- Visibility: source_fields = [controller variableName], destination_fields = [affected field(s)]

**Step 4e — Consolidate:**
- If multiple fields are affected by the same host + condition, combine into ONE rule with multiple destination_fields

Log: Append "Step 4: Created <N> simple rules. Placed on current panel: <N>. Placed on other panels: <N>" to $LOG_FILE

### 5. Create delegation records for complex references
For each complex reference, write a delegation record:
```json
{
    "type": "derivation|edv|clearing",
    "source_panel": "<panel where source field lives>",
    "target_panel": "<panel where target field lives>",
    "source_field": "__variablename__",
    "target_field": "__variablename__",
    "logic": "<original logic text>",
    "description": "<what this delegation should accomplish>"
}
```
Log: Append "Step 5: Created <N> delegation records" to $LOG_FILE

### 6. Write output files
- Write OUTPUT_FILE: current panel fields with cross-panel rules added (all existing rules preserved)
- Write INTER_PANEL_OUTPUT_FILE: rules targeting other panels
- Write DELEGATION_OUTPUT_FILE: complex delegation records

Log: Append "Step 6 complete: Output <N> fields, <N> inter-panel rules, <N> delegations" to $LOG_FILE

---

## Output Structures

### OUTPUT_FILE — Updated current panel fields
Same schema as input FIELDS_JSON, with new cross-panel rules appended to relevant fields.

### INTER_PANEL_OUTPUT_FILE — Rules for other panels
```json
{
    "<target_panel_name>": [
        {
            "target_field_variableName": "__fieldname__",
            "rules_to_add": [
                {
                    "rule_name": "Copy To (Client)",
                    "source_fields": ["__source_field__"],
                    "destination_fields": ["__target_field__"],
                    "_reasoning": "Cross-panel: copy from Current Panel to Target Panel",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```

### DELEGATION_OUTPUT_FILE — Complex delegations
```json
[
    {
        "type": "derivation",
        "source_panel": "Basic Details",
        "target_panel": "Vendor Basic Details",
        "source_field": "__vendorname__",
        "target_field": "__firstname__",
        "logic": "First Name = first word of Vendor Name (from Basic Details Panel)",
        "description": "Extract first word from vendor name and populate first name field"
    }
]
```

---

## Worked Examples — Full Placement Decision Process

### Example 1: Copy To (Cross-Panel)

**Scenario:** Processing panel "Purchase Org Details". Field "Company Code" has logic: _"Copy from Basic Details Panel"_

**Decision walkthrough:**
1. Rule type = **Copy To (Client)**
2. **Host field** = source field = `__companycode__` (the field being copied FROM)
3. **Which panel is the host in?** → Search REFERENCED_PANELS_JSON → found in "Basic Details"
4. **Host panel ≠ current panel** → goes to **INTER_PANEL_OUTPUT_FILE**
5. **source_fields** = `["__companycode__"]` (Basic Details' Company Code — the source)
6. **destination_fields** = `["__companycode__"]` (Purchase Org Details' Company Code — the receiver)

**Result in INTER_PANEL_OUTPUT_FILE:**
```json
{
    "Basic Details": [
        {
            "target_field_variableName": "__companycode__",
            "rules_to_add": [
                {
                    "rule_name": "Copy To (Client)",
                    "source_fields": ["__companycode__"],
                    "destination_fields": ["__companycode__"],
                    "_reasoning": "Cross-panel: Copy Company Code from Basic Details to Purchase Org Details",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```
Note: `target_field_variableName` = `__companycode__` means "place this rule on the `__companycode__` field in Basic Details panel". The rule itself will fire and copy the value to the destination.

### Example 2: Visibility (Controller in referenced panel)

**Scenario:** Processing panel "Address Details". Field "Address Proof" has logic: _"Visible if Process Type (from Basic Details Panel) is India-Domestic"_

**Decision walkthrough:**
1. Rule type = **Make Visible (Client)** + opposite **Make Invisible (Client)**
2. **Host field** = controller field = `__processtype__` (the field whose value controls visibility)
3. **Which panel is the host in?** → Search REFERENCED_PANELS_JSON → found in "Basic Details"
4. **Host panel ≠ current panel** → goes to **INTER_PANEL_OUTPUT_FILE**
5. **source_fields** = `["__processtype__"]` (the controller)
6. **destination_fields** = `["__addressproof__"]` (the field that becomes visible/invisible)

**Result in INTER_PANEL_OUTPUT_FILE:**
```json
{
    "Basic Details": [
        {
            "target_field_variableName": "__processtype__",
            "rules_to_add": [
                {
                    "rule_name": "Make Visible (Client)",
                    "source_fields": ["__processtype__"],
                    "destination_fields": ["__addressproof__"],
                    "conditionalValues": ["India-Domestic"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "_reasoning": "Cross-panel: Address Proof visible when Process Type is India-Domestic",
                    "_inter_panel_source": "cross-panel"
                },
                {
                    "rule_name": "Make Invisible (Client)",
                    "source_fields": ["__processtype__"],
                    "destination_fields": ["__addressproof__"],
                    "conditionalValues": ["India-Domestic"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "_reasoning": "Cross-panel opposite: Address Proof invisible when Process Type is NOT India-Domestic",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```

### Example 3: Visibility with consolidation (multiple fields, same controller)

**Scenario:** Processing panel "Bank Details". Three fields have similar logic:
- "IFSC Code": _"Visible if Process Type (from Basic Details) is India-Domestic"_
- "Bank Name": _"Visible if Process Type (from Basic Details) is India-Domestic"_
- "Branch": _"Visible if Process Type (from Basic Details) is India-Domestic"_

**Decision walkthrough:**
1. All three have the same controller (`__processtype__`) and same condition (`India-Domestic`)
2. **Host field** = `__processtype__` in Basic Details (referenced panel)
3. **CONSOLIDATE** into ONE rule with multiple destination_fields

**Result — ONE Make Visible + ONE Make Invisible (not 6 rules):**
```json
{
    "Basic Details": [
        {
            "target_field_variableName": "__processtype__",
            "rules_to_add": [
                {
                    "rule_name": "Make Visible (Client)",
                    "source_fields": ["__processtype__"],
                    "destination_fields": ["__ifsccode__", "__bankname__", "__branch__"],
                    "conditionalValues": ["India-Domestic"],
                    "condition": "IN",
                    "conditionValueType": "TEXT",
                    "_reasoning": "Cross-panel: 3 Bank Details fields visible when Process Type is India-Domestic",
                    "_inter_panel_source": "cross-panel"
                },
                {
                    "rule_name": "Make Invisible (Client)",
                    "source_fields": ["__processtype__"],
                    "destination_fields": ["__ifsccode__", "__bankname__", "__branch__"],
                    "conditionalValues": ["India-Domestic"],
                    "condition": "NOT_IN",
                    "conditionValueType": "TEXT",
                    "_reasoning": "Cross-panel opposite: 3 Bank Details fields invisible when Process Type is NOT India-Domestic",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```

### Example 4: Visibility (Controller in current panel — rare but possible)

**Scenario:** Processing panel "Vendor Basic Details". Field "Title" has logic: _"Visible if Entity Type is Individual"_. Entity Type (`__entitytype__`) exists in the CURRENT panel (Vendor Basic Details).

**Decision walkthrough:**
1. **Host field** = controller = `__entitytype__`
2. **Which panel?** → Found in FIELDS_JSON → it's in the CURRENT panel
3. **Host panel = current panel** → goes to **OUTPUT_FILE** (add rule directly to `__entitytype__`'s rules array)

**Result:** Rule added to `__entitytype__` in OUTPUT_FILE (not INTER_PANEL_OUTPUT_FILE).
