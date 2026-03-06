---
name: Inter-Panel Global Analysis Agent (Pass 1)
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Global analysis of ALL panels to detect cross-panel references. Creates fully-specified Copy To rules for simple cases, and flags complex references (visibility/state, derivation, EDV, clearing) for Pass 2.
---


# Inter-Panel Global Analysis Agent (Pass 1)

## Objective
Analyze ALL panels at once (global view) to detect cross-panel references in field logic. Create fully-specified rules for simple cases (Copy To only) and flag complex references (visibility/state, derivation, EDV, clearing) for Pass 2 processing via the expression rule agent.

## Input
COMPACT_PANELS_FILE: $COMPACT_PANELS_FILE
DIRECT_RULES_FILE: $DIRECT_RULES_FILE
COMPLEX_REFS_FILE: $COMPLEX_REFS_FILE
LOG_FILE: $LOG_FILE

## Real-Time Logging (MANDATORY)
You MUST write progress to LOG_FILE at EVERY step so the user can monitor via `tail -f`.
Use the Write tool to append to LOG_FILE BEFORE and AFTER each step.
Format each line clearly:
```
Step 1 START: Reading compact panels file...
Step 1 DONE: Read 5 panels, 87 fields. Panels: Basic Details, Address Details, ...
Step 2 START: Scanning all fields for cross-panel references...
Step 2 PROGRESS: Panel "Address Details" — found 3 cross-panel refs
Step 2 DONE: Found 12 cross-panel references across 3 panels
Step 3 START: Classifying references (simple vs complex)...
Step 3 DONE: Simple: 8, Complex: 4
Step 4 START: Creating rules for 3 simple references...
Step 4 PROGRESS: Created Copy To rule — __companycode__ (Basic Details) -> Purchase Org Details
Step 4 DONE: Created 3 simple rules (3 copy-to)
Step 5 START: Flagging 9 complex references for Pass 2...
Step 5 DONE: Flagged 9 complex refs (5 visibility, 2 derivation, 1 clearing, 1 edv)
Step 6 START: Writing output files...
Step 6 DONE: Wrote direct_rules.json (10 rules), complex_refs.json (4 refs)
COMPLETE: Pass 1 finished successfully
```
This is NOT optional — the user needs to see what you are doing in real-time.

## Output
Two output files:
1. **DIRECT_RULES_FILE** — Fully-specified rules for simple cross-panel cases (Copy To, visibility/state)
2. **COMPLEX_REFS_FILE** — Complex references flagged for Pass 2 (derivation, EDV, clearing)

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

> **Note:** Visibility/state rules (Make Visible, Make Invisible, Enable, Disable, Make Mandatory, Make Non Mandatory) are **NOT** created here. They are flagged as complex and handled by the expression rule agent in Pass 2.

---

## Compact Input Format

The COMPACT_PANELS_FILE contains ALL panels in a condensed format — one line per field:
```
=== Panel: Basic Details ===
Company Code | DROPDOWN | __companycode__ | Dropdown for company selection
Process Type | DROPDOWN | __processtype__ | India-Domestic / International / SEZ
Vendor Name | TEXT | __vendorname__ | Name of the vendor

=== Panel: Address Details ===
Address Proof | FILE_UPLOAD | __addressproof__ | Visible if Process Type (from Basic Details Panel) is India-Domestic
City | TEXT | __city__ | Auto-populated from Pincode validation
```

Each field line: `field_name | type | variableName | logic`

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)

1) **ONLY handle CROSS-PANEL logic** — logic that references fields or values from OTHER panels (detected by phrases like "from Basic Details Panel", "from PAN and GST Details", etc.). Do NOT create rules for intra-panel logic (the condition agent 05 already handled those).
2) **Use ONLY variableNames** that exist in COMPACT_PANELS_FILE. Do NOT invent fields.
3) **Mark all cross-panel rules** with `_inter_panel_source: "cross-panel"` for traceability.
4) **CONSOLIDATE** rules: group fields affected by the same controller + condition into ONE rule with multiple destination_fields (same pattern as condition agent 05).
5) **OPPOSITE RULES**: When logic implies both directions (e.g., "If X=Yes make visible, otherwise invisible"), use `NOT_IN` with the **original** value for the opposite — NEVER `IN` with the opposite value.
6) Condition operator is ALWAYS one of: `IN`, `NOT_IN`, or `BETWEEN`.
7) `conditionalValues` is ALWAYS an array of strings.
8) **RULE PLACEMENT — THE MOST CRITICAL DECISION**:
   For every rule you create, you must identify:
   - **Host field**: The field the rule is placed ON (its `rules` array gets the new rule)
   - **Host panel**: The panel containing the host field
   - Copy To → host = source field (field being copied FROM)
   - Visibility/State → host = controller field (field whose VALUE determines the state change)

9) **CLASSIFY before acting**: For each cross-panel reference, classify as:
    - **Simple** (handle directly): Copy To only → create complete rule in DIRECT_RULES_FILE
    - **Complex** (flag for Pass 2): visibility/state (Make Visible, Make Invisible, Enable, Disable, Make Mandatory, Make Non Mandatory), derivation expressions (substring, name splitting), EDV/reference table lookups, clearing expressions → write to COMPLEX_REFS_FILE

10) **DERIVATION LOGIC IS NOT VISIBILITY**: Do NOT interpret value-population/derivation logic as visibility rules. If logic says "populate this field based on another panel's field value", that is derivation — flag it as complex, don't create a visibility rule.
11) **Static state rules** ("Always/By default invisible") with no cross-panel reference are NOT your job — skip them (condition agent 05 handled those).
12) **GLOBAL VIEW**: You see ALL panels at once. Use this to verify that referenced variableNames actually exist and are in the correct panel.

---

## Classification Guide

### Simple — Handle Directly (write to DIRECT_RULES_FILE)
- **"Copy from X Panel"** → Copy To (Client) rule. Source = field in X Panel, Destination = current field.

### Complex — Flag for Pass 2 (write to COMPLEX_REFS_FILE)
- **"Visible if Field from X Panel is VALUE"** → Visibility expression. Type: `visibility`.
- **"If Process Type (from Basic Details) is India-Domestic, make visible"** → Visibility expression. Type: `visibility`.
- **"Enable if X from Y Panel"** → State expression. Type: `visibility`.
- **"Mandatory if X from Y Panel is VALUE"** → State expression. Type: `visibility`.
- **"First name = first word of Vendor Name (from Basic Details)"** → Derivation (substring logic). Type: `derivation`.
- **"Populate from reference table based on field from X Panel"** → EDV lookup. Type: `edv`.
- **"Clear child fields when parent from X Panel changes"** → Clearing. Type: `clearing`.
- **Any expression syntax** (ctfd, asdff, cf, rffdd) → Type: appropriate specialized type.

---

## Approach

### 1. Read COMPACT_PANELS_FILE
**LOG** → Append "Step 1 START: Reading compact panels file..." to $LOG_FILE
Read the compact panels file. Parse all panels and fields. Build a variableName → (panel_name, field_name, type) lookup map.
**LOG** → Append "Step 1 DONE: Read <N> panels, <M> total fields. Panels: <list>" to $LOG_FILE

### 2. Scan ALL fields for cross-panel references
**LOG** → Append "Step 2 START: Scanning all fields for cross-panel references..." to $LOG_FILE
For every field across ALL panels, check if its logic references another panel. Look for patterns:
- "(from X Panel)" or "(from X)" or "(from 'X')"
- "X Panel" where X is a known panel name
- "if Field from X is..." or "copy from X"

Build a list of cross-panel references: `{field_variableName, field_panel, referenced_panel, referenced_field_variableName, logic_text, classification}`
**LOG** → For each panel with refs found, append "Step 2 PROGRESS: Panel '<name>' — found <N> cross-panel refs" to $LOG_FILE
**LOG** → Append "Step 2 DONE: Found <N> cross-panel references across <M> panels" to $LOG_FILE

### 3. Classify each reference
**LOG** → Append "Step 3 START: Classifying references (simple vs complex)..." to $LOG_FILE
For each cross-panel reference, classify as `simple` or `complex`.
**LOG** → Append "Step 3 DONE: Simple: <N>, Complex: <N>" to $LOG_FILE

### 4. Create simple rules (with explicit placement decisions)
**LOG** → Append "Step 4 START: Creating rules for <N> simple references..." to $LOG_FILE
For each simple reference, follow this decision process:

**Step 4a — Identify the host field:**
- Copy To → host = source field (the field being copied FROM)
- Visibility/State → host = controller field (the field whose value determines the state)

**Step 4b — Find the host field's panel:**
- Use the variableName lookup map to find which panel the host field is in

**Step 4c — Set source_fields and destination_fields:**
- Copy To: source_fields = [host/source variableName], destination_fields = [receiving field(s)]
- Visibility: source_fields = [controller variableName], destination_fields = [affected field(s)]

**Step 4d — Consolidate:**
- If multiple fields are affected by the same host + condition, combine into ONE rule with multiple destination_fields

**LOG** → For each rule created, append "Step 4 PROGRESS: Created <rule_type> — <host_field> (<host_panel>) -> <dest_fields>" to $LOG_FILE
**LOG** → Append "Step 4 DONE: Created <N> simple rules (<breakdown by type>)" to $LOG_FILE

### 5. Create complex reference records
**LOG** → Append "Step 5 START: Flagging <N> complex references for Pass 2..." to $LOG_FILE
For each complex reference, write a flag record.
**LOG** → For each ref, append "Step 5 PROGRESS: Flagged <type> — <source_field> (<source_panel>) -> <target_field> (<target_panel>)" to $LOG_FILE
**LOG** → Append "Step 5 DONE: Flagged <N> complex refs (<breakdown by type>)" to $LOG_FILE

### 6. Write output files
**LOG** → Append "Step 6 START: Writing output files..." to $LOG_FILE
- Write DIRECT_RULES_FILE with all simple rules
- Write COMPLEX_REFS_FILE with all complex reference records
**LOG** → Append "Step 6 DONE: Wrote direct_rules.json (<N> rules), complex_refs.json (<N> refs)" to $LOG_FILE
**LOG** → Append "COMPLETE: Pass 1 finished successfully" to $LOG_FILE

---

## Output Structures

### DIRECT_RULES_FILE — Simple rules ready to merge
```json
{
    "<host_panel_name>": [
        {
            "target_field_variableName": "__hostfield__",
            "rules_to_add": [
                {
                    "rule_name": "Copy To Form Field (Client)",
                    "source_fields": ["__sourcefield__"],
                    "destination_fields": ["__destfield1__", "__destfield2__"],
                    "_reasoning": "Cross-panel: copy from Panel A to Panel B",
                    "_inter_panel_source": "cross-panel"
                }
            ]
        }
    ]
}
```

Note: `target_field_variableName` is the **host field** — the field the rule is placed ON.

### COMPLEX_REFS_FILE — Complex references for Pass 2
```json
[
    {
        "type": "visibility",
        "source_panel": "Basic Details",
        "target_panel": "Address Details",
        "source_field": "__processtype__",
        "target_field": "__addressproof__",
        "logic": "Visible if Process Type (from Basic Details Panel) is India-Domestic",
        "description": "Address Proof visible when Process Type is India-Domestic; invisible otherwise"
    },
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

**Valid `type` values:** `visibility`, `derivation`, `edv`, `clearing`

If no complex references, write an empty array: `[]`

---

## Worked Examples — Full Placement Decision Process

### Example 1: Copy To (Cross-Panel)

**Scenario:** Panel "Purchase Org Details" has field "Company Code" with logic: _"Copy from Basic Details Panel"_

**Decision walkthrough:**
1. Rule type = **Copy To Form Field (Client)**
2. **Host field** = source field = `__companycode__` (the field being copied FROM)
3. **Host panel** = "Basic Details" (where the source field lives)
4. **source_fields** = `["__companycode__"]`
5. **destination_fields** = `["__companycode__"]` (Purchase Org Details' Company Code — the receiver)

**Result in DIRECT_RULES_FILE:**
```json
{
    "Basic Details": [
        {
            "target_field_variableName": "__companycode__",
            "rules_to_add": [
                {
                    "rule_name": "Copy To Form Field (Client)",
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

### Example 2: Visibility (cross-panel — flag for Pass 2)

**Scenario:** Panel "Address Details" has field "Address Proof" with logic: _"Visible if Process Type (from Basic Details Panel) is India-Domestic"_

**Decision walkthrough:**
1. This is cross-panel visibility — **flag as complex**, do NOT create a direct rule.
2. The expression rule agent in Pass 2 will handle this using `cf`/`rffdd` expression syntax.

**Result in COMPLEX_REFS_FILE:**
```json
[
    {
        "type": "visibility",
        "source_panel": "Basic Details",
        "target_panel": "Address Details",
        "source_field": "__processtype__",
        "target_field": "__addressproof__",
        "logic": "Visible if Process Type (from Basic Details Panel) is India-Domestic",
        "description": "Address Proof visible when Process Type is India-Domestic; invisible otherwise"
    }
]
```

### Example 3: Visibility with multiple affected fields (cross-panel — flag for Pass 2)

**Scenario:** Panel "Bank Details" has three fields all with logic referencing the same controller:
- "IFSC Code": _"Visible if Process Type (from Basic Details) is India-Domestic"_
- "Bank Name": _"Visible if Process Type (from Basic Details) is India-Domestic"_
- "Branch": _"Visible if Process Type (from Basic Details) is India-Domestic"_

**Decision:** All are cross-panel visibility — flag each as complex for Pass 2. The expression rule agent will consolidate them.

**Result in COMPLEX_REFS_FILE:**
```json
[
    {
        "type": "visibility",
        "source_panel": "Basic Details",
        "target_panel": "Bank Details",
        "source_field": "__processtype__",
        "target_fields": ["__ifsccode__", "__bankname__", "__branch__"],
        "logic": "Visible if Process Type (from Basic Details) is India-Domestic",
        "description": "3 Bank Details fields visible when Process Type is India-Domestic; invisible otherwise"
    }
]
```

### Example 4: Complex reference (derivation — flag for Pass 2)

**Scenario:** Panel "Vendor Basic Details" has field "First Name" with logic: _"First Name = first word of Vendor Name (from Basic Details Panel)"_

**Decision:** This is derivation (substring/splitting), NOT visibility. Flag for Pass 2.

**Result in COMPLEX_REFS_FILE:**
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
