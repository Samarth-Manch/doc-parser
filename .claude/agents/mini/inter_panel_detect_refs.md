---
name: Inter-Panel Reference Detection Agent
allowed-tools: Read
description: Lightweight per-panel agent that detects cross-panel references in field logic. Receives ONE panel's fields plus a compact index of ALL panels' fields, outputs structured JSON of detected references with classification.
---

# Inter-Panel Reference Detection Agent

## Objective
Analyze a SINGLE panel's fields to detect any cross-panel references in their logic text. Classify each reference as simple (Copy To) or complex (visibility, derivation, EDV, clearing). Do NOT create rules — only detect and classify.

## Output Schema (STRICT — read this before anything else)

Each entry in `cross_panel_references` MUST have EXACTLY these 9 keys. No more, no fewer, no aliases, no renames:

```
field_variableName, field_name, referenced_panel,
referenced_field_variableName, referenced_field_name,
type, classification, logic_snippet, description
```

FORBIDDEN top-level keys per ref — never emit these. If the natural phrasing in your head produces one, rename it to the canonical key above BEFORE writing:

```
source_field, source_field_name, source_variable_name, source_variableName,
source_panel, source_field_type, target_field, target_variableName,
target_field_name, referenced_variable_name, referenced_variableName,
reference_type, reference_details, references, detected_references, refs
```

Common renames:
- `source_variable_name` → `field_variableName`
- `source_field_name` → `field_name`
- `referenced_variable_name` → `referenced_field_variableName`
- `reference_type` → `classification`

The per-ref schema has NO `source`/`target` split. The "source" of a cross-panel reference is always the field in THIS panel (→ `field_variableName`). The "target" is always the field in the OTHER panel (→ `referenced_field_variableName`). Full example and required-field details are in the `Output Structure — MANDATORY FORMAT` section below.

## Input
- PANEL_FIELDS_FILE: $PANEL_FIELDS_FILE — JSON array of fields for one panel (compact format, rules stripped)
- PANEL_NAME: $PANEL_NAME — Name of the current panel being analyzed
- ALL_PANELS_INDEX_FILE: $ALL_PANELS_INDEX_FILE — JSON object mapping every panel name to its array of `{field_name, variableName}` pairs. Use this to resolve referenced field variableNames.

## Output
Output a JSON object as your final response. Emit nothing before or after it. The CLI enforces the shape via JSON Schema. The top-level object has exactly two keys — `panel_name` and `cross_panel_references`.

---

## Detection Rules

1) **ONLY detect references to OTHER panels** — skip any logic that only references fields within the current panel.
2) **Use field names and variableNames exactly as they appear** in ALL_PANELS_INDEX_FILE. Do NOT invent field names or variableNames.
3) **Be thorough** — check every field's logic for any mention of other panel names.
4) **Classify accurately** — the classification determines how the reference will be processed downstream.
5) **ALWAYS resolve variableNames** — use ALL_PANELS_INDEX_FILE to look up the variableName of the referenced field. Match by field name (case-insensitive, partial match OK). Only use `"unknown"` if absolutely no match can be found.

---

## How to Detect Cross-Panel References

For each field in the panel, check its `logic` text for:

1. **Explicit panel mentions**: "(from X Panel)", "(from X)", "from X Panel", "X Panel"
2. **Panel name substrings**: Any mention of another panel's name (case-insensitive)
3. **Cross-panel keywords**: "copy from", "copied from", "same as in", "derived from", "populated from", "based on ... from", "filtered by ... from"

When a reference is found:
1. Identify which panel is referenced
2. Look up the referenced field in ALL_PANELS_INDEX_FILE under that panel to get its variableName
3. Classify the reference type

---

## Classification Guide

### Simple — `type: "simple"`

- **copy_to**: Logic says "Copy from X Panel", "Same as X Panel", "Copied from X". A direct value copy with no conditions or transformations.

### Complex — `type: "complex"`

- **visibility**: Logic says "Visible if/when [field] from X Panel is [value]", "Invisible if...", "Enable if...", "Disable if...", "Mandatory if...". Any conditional show/hide/enable/disable/mandatory based on another panel's field.
- **derivation**: Logic describes value transformation, substring extraction, concatenation, or conditional value population from another panel's field, with **NO mention of EDV, reference table, validation, or attribute lookup**. E.g., "First name = first word of Vendor Name (from X Panel)".
- **edv**: The field is a **dropdown** (DROPDOWN, EXTERNAL_DROP_DOWN_VALUE, MULTI_DROPDOWN) whose dropdown options/values are populated or filtered from a reference table / EDV table using a field from another panel as a filter criteria. This is about configuring **what appears in the dropdown list**. E.g., "Dropdown values from EDV table VC_COMPANY_DETAILS filtered by Vendor Number (from X Panel)", "Company Code dropdown populated from reference table using Vendor Number (from X Panel) as criteria". The downstream agent for this classification is the **EDV Dropdown (Client)** rule agent — it configures `ddType`, `criterias`, `da` params for the dropdown.
- **validate_edv**: A field's value is **auto-fetched / derived / validated from a reference table** using a field from another panel as the lookup key. The field itself is NOT necessarily a dropdown — it can be TEXT, NUMBER, or any type. The value is populated server-side via attribute lookup. E.g., "Company code derived from VC_COMPANY_DETAILS reference table attribute 2, dependent on Vendor Number (attribute 1) from X Panel", "Email fetched from VC_EMAIL_DETAILS attribute 9 using Address Number (from X Panel)", "derived automatically through Validation from reference table using field from X Panel". The downstream agent for this classification is the **Validate EDV (Server)** rule agent — it maps positional attribute columns to destination fields.
- **clearing**: Logic says fields should be cleared when a field from another panel changes. E.g., "Clear when X (from Y Panel) changes".

### How to distinguish `edv` vs `validate_edv` vs `derivation`

| Signal in logic | Classification |
|---|---|
| Dropdown filtered/populated from reference table using cross-panel field as **criteria** | `edv` |
| Value auto-fetched from reference table **attribute N** using cross-panel field as lookup key (NOT a dropdown filter) | `validate_edv` |
| "derived through validation from reference table" using cross-panel field | `validate_edv` |
| Value transformation (substring, concat, arithmetic) from cross-panel field, **no reference table mentioned** | `derivation` |

**IMPORTANT**: Do NOT use any other classification values. Only use: `copy_to`, `visibility`, `derivation`, `edv`, `validate_edv`, `clearing`. If a reference involves multiple types (e.g., visibility + derivation), use the primary one. If it's mainly about visibility/mandatory, use `visibility`. If the logic mentions ANY of: EDV, reference table, validation table, attribute lookup — ALWAYS classify as `edv` or `validate_edv` (never `derivation`).

---

## Approach

### Step 1: Read inputs
Read PANEL_FIELDS_FILE (JSON array of fields for this panel) and ALL_PANELS_INDEX_FILE (JSON object: panel name → field list with variableNames).

### Step 2: Build panel name lookup
Create a set of all panel names EXCEPT the current panel (PANEL_NAME). These are the panels to look for references to. Also build a field name → variableName lookup from ALL_PANELS_INDEX_FILE for each other panel.

### Step 3: Scan each field's logic
For every field in the panel:
- Read its `logic` text
- Check if any other panel name appears in the logic (case-insensitive)
- Check for cross-panel keyword patterns
- If a reference is found, look up the referenced field's variableName in ALL_PANELS_INDEX_FILE
- Classify and record the reference

### Step 4: Self-validate before writing
Walk the in-memory `cross_panel_references` array. For each entry:

1. Check that it has all 9 required keys from the Output Schema and NO other top-level keys.
2. If any forbidden key is present, rename it to the canonical key:
   - `source_variable_name` / `source_variableName` → `field_variableName`
   - `source_field_name` → `field_name`
   - `referenced_variable_name` / `referenced_variableName` / `target_variableName` → `referenced_field_variableName`
   - `reference_type` → `classification`
   - Drop: `source_field`, `source_panel`, `source_field_type`, `target_field`, `target_field_name`, `reference_details`
3. If `field_variableName` or `referenced_field_variableName` is empty or `"unknown"` after rename, drop the entry and append a short note to `errors[]`.
4. Verify `type` ∈ `{"simple","complex"}` and `classification` ∈ `{"copy_to","visibility","derivation","edv","validate_edv","clearing"}`. Fix or drop on mismatch.

Only after this pass, proceed to Step 5.

### Step 5: Output
Output the JSON object as your final response. Emit nothing before or after it.

---

## Output Structure — MANDATORY FORMAT

The output MUST be a JSON object (NOT an array) with exactly these two keys:

```json
{
  "panel_name": "Address Details",
  "cross_panel_references": [
    {
      "field_variableName": "_addressproof_",
      "field_name": "Address Proof",
      "referenced_panel": "Basic Details",
      "referenced_field_variableName": "_processtype_",
      "referenced_field_name": "Process Type",
      "type": "complex",
      "classification": "visibility",
      "logic_snippet": "Visible if Process Type (from Basic Details Panel) is India-Domestic",
      "description": "Address Proof visible when Process Type is India-Domestic"
    },
    {
      "field_variableName": "_companycode_",
      "field_name": "Company Code",
      "referenced_panel": "Basic Details",
      "referenced_field_variableName": "_companycode_",
      "referenced_field_name": "Company Code",
      "type": "simple",
      "classification": "copy_to",
      "logic_snippet": "Copy from Basic Details Panel",
      "description": "Copy Company Code from Basic Details"
    }
  ]
}
```

### REQUIRED fields for each reference:
- `field_variableName`: The variableName of the field in THIS panel whose logic references another panel
- `field_name`: Human-readable name of the field
- `referenced_panel`: The OTHER panel being referenced — MUST be an exact panel name from ALL_PANELS_INDEX_FILE
- `referenced_field_variableName`: The variableName of the referenced field — look this up in ALL_PANELS_INDEX_FILE
- `referenced_field_name`: Human-readable name of the referenced field
- `type`: MUST be `"simple"` or `"complex"` — no other values
- `classification`: MUST be one of: `"copy_to"`, `"visibility"`, `"derivation"`, `"edv"`, `"validate_edv"`, `"clearing"` — no other values
- `logic_snippet`: The relevant portion of the logic text
- `description`: Brief description

### WRONG — DO NOT EMIT THIS SHAPE

Real drift observed in a prior run. Every key below is forbidden:

```json
{
  "panel_name": "Email ID Update",
  "cross_panel_references": [
    {
      "source_field_name": "Email ID Update",
      "source_variable_name": "_emailidupdate_",
      "source_field_type": "PANEL",
      "referenced_field_name": "Type of Update",
      "referenced_variable_name": "_typeofupdatebasicdetails_",
      "referenced_panel": "Basic Details",
      "reference_type": "visibility",
      "classification": "simple"
    }
  ]
}
```

The CORRECT shape for the same reference:

```json
{
  "panel_name": "Email ID Update",
  "cross_panel_references": [
    {
      "field_variableName": "_emailidupdate_",
      "field_name": "Email ID Update",
      "referenced_panel": "Basic Details",
      "referenced_field_variableName": "_typeofupdatebasicdetails_",
      "referenced_field_name": "Type of Update",
      "type": "complex",
      "classification": "visibility",
      "logic_snippet": "If the Type of update field (from Basic Details panel) value in \"Vendor Onboarding\" then this Panel is visible to Initiator and Vendor.",
      "description": "Panel visibility is controlled by Type of Update from Basic Details."
    }
  ]
}
```

### If no cross-panel references are found:
```json
{
  "panel_name": "Basic Details",
  "cross_panel_references": []
}
```

### CRITICAL FORMAT RULES:
- The output MUST be a JSON **object** with keys `panel_name` and `cross_panel_references`
- Do NOT output a JSON array at the top level
- Do NOT use top-level wrapper keys like `references`, `detected_references`, `refs`, etc.
- The key MUST be `cross_panel_references`
- Per-ref keys MUST be EXACTLY the 9 listed in the Output Schema at the top of this file — no others
- Do NOT emit any `source_*` key (`source_field`, `source_field_name`, `source_variable_name`, `source_variableName`, `source_panel`, `source_field_type`) — use `field_variableName` and `field_name` instead
- Do NOT emit `target_field`, `target_variableName`, `target_field_name` — use `referenced_field_variableName` and `referenced_field_name`
- Do NOT emit `referenced_variable_name` or `referenced_variableName` — the canonical key is `referenced_field_variableName`
- Do NOT emit `reference_type` or `reference_details` — the classification key is `classification`
- `referenced_panel` MUST be a valid panel name from ALL_PANELS_INDEX_FILE, never `"unknown"`
- `classification` MUST be one of the 6 allowed values listed above
- `type` MUST be `"simple"` or `"complex"` — nothing else

### DEDUPLICATION RULES (Fix E — Avoid Duplicate Refs):
- **PANEL fields echoing logic from a controlling field**: If a PANEL-type field's logic says "this panel is visible when [dropdown field] from [other panel] has value X", this is a **redundant echo** of the dropdown's own logic. The controlling field (dropdown) is the canonical source. In this case:
  - Set `referenced_field_variableName` to the **controlling field** (the dropdown), NOT the PANEL field itself
  - Set `referenced_panel` to the panel containing the controlling field
  - This ensures all refs for the same logical relationship group together downstream
- **Do NOT emit refs from both directions**: If Field A in Panel 1 controls the visibility of Panel 2, emit ONE ref (on Field A or on a field in Panel 2 pointing to Field A). Do NOT emit a second ref where Panel 2's PANEL field points back to Field A — this creates duplicates.
- **When a PANEL field's logic restates another field's controlling logic verbatim**: Skip it. The controlling field's own logic (or the affected fields within the panel) already captures this relationship.
