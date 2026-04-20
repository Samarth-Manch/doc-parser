---
name: Cross-Panel Reference Detection Agent
allowed-tools: Read, Write
description: Per-panel agent that detects cross-panel field references in logic text. Receives one panel's fields plus a global index of all panels' fields, and emits structured JSON of references with explicit/inferred/ambiguous panel resolution.
---

# Cross-Panel Reference Detection Agent

## Objective

Analyze a SINGLE panel's fields to detect any cross-panel references in their `logic` text. Resolve the referenced field's panel using either an explicit mention in the logic or by inference against the global field index. Classify each reference by `relationship_type` and `operation_type`. Do NOT create rules.

## Input variables

- `$PANEL_NAME` — name of the current panel being analyzed
- `$PANEL_FIELDS_FILE` — path to a JSON file with this panel's fields
  - shape: `{"panel_name": "<name>", "fields": [{"field_name", "variable_name", "field_type", "logic", "mandatory"}, ...]}`
- `$ALL_PANELS_INDEX_FILE` — path to a JSON file mapping every panel name to its fields
  - shape: `{"<panel>": [{"field_name", "variable_name", "field_type"}, ...], ...}`
- `$OUTPUT_FILE` — path to write the per-panel detection JSON
- `$LOG_FILE` — append progress lines here

## Hard constraints

1. Analyze **only** the `logic` field of each field in the current panel.
2. **Never invent references** where logic is silent about a cross-panel link.
3. Only emit refs where `source_field.panel != target_field.panel` (never emit intra-panel refs).
4. Use exact `field_name` and `variable_name` values from `$ALL_PANELS_INDEX_FILE` — do not fabricate.
5. If inputs are malformed, write `{"panel_name": "$PANEL_NAME", "cross_panel_references": [], "errors": ["<msg>"]}` and exit.
6. Output MUST be a JSON object with exactly keys `panel_name`, `cross_panel_references`, `errors`. No extra top-level keys.

## Approach

### Step 1 — Read inputs
Read `$PANEL_FIELDS_FILE` and `$ALL_PANELS_INDEX_FILE`. Log: `"Step 1: inputs loaded for panel <name>"`.

### Step 2 — Build lookups
- A set of **other panel names** (every panel in the index except `$PANEL_NAME`).
- A map `panel_name → {field_name_lower → {variable_name, field_type, field_name_exact}}` for every OTHER panel.
- A flat reverse map `field_name_lower → [{panel, variable_name, field_type, field_name_exact}, ...]` across ALL OTHER panels (for unnamed-panel inference).

### Step 3 — Field loop

<field_loop>

For each field in this panel's `fields` array:

**3.1 Read logic.** If empty or trivially static ("N/A", "-", "NA"), skip and log.

**3.2 Scan for reference markers** using the trigger table below. If no marker and no cross-panel keyword or name is found in the text, skip.

| Trigger keywords | Relationship type |
|---|---|
| copy from, copied from, same as, populated from, get from, derived from, based on | `copy_operation` |
| visible if, visible when, hide if, hide when, show when, applicable when | `visibility_control` |
| mandatory if, mandatory when, required when, non-mandatory when | `mandatory_control` |
| validate against, verify with, check against | `validation` |
| enable when, disable when, editable when, non-editable when | `enable_disable` |
| default value, by default, auto-derived, auto-filled | `default_value` |
| clear when, reset when, blank when | `clear_operation` |
| if ... then (conditional behavior referencing another field) | `conditional` |

If multiple markers fire, pick the primary one; prefer the most specific (e.g. `visibility_control` > `conditional`).

**3.3 Extract the referenced field phrase** — the noun phrase after the marker. Examples:
- "Copy from **Name/ First Name** field of basic detail panel" → referenced field = "Name/ First Name"; explicit panel hint = "basic detail panel"
- "Visible if **Process Type** is India-Domestic" → referenced field = "Process Type"; no panel hint
- "Title derived from **PAN** Card" → referenced field = "PAN"; no panel hint

**3.4 Panel Resolution Ladder** (this is the core of this agent — execute in order):

- **(a) Explicit panel in phrase** — logic names a panel ("from basic detail panel", "in PAN and GST panel", "from Basic Details"). Map the spoken name to a canonical panel using the Panel Name Variations Table below.
  - If exactly one canonical match → use it. Set `panel_resolution: "explicit"`.
  - If the mapped name matches `$PANEL_NAME` (i.e., intra-panel) → SKIP.
  - If the spoken panel name cannot be mapped to any panel in the index → fall through to (b).

- **(b) No panel named** — only the referenced field name appears. Search the flat reverse map for the referenced field name, case-insensitive, allowing partial match on multi-word names (e.g., "Name" matches "Name/ First Name"):
  - Match exists in **exactly one** OTHER panel → use it. Set `panel_resolution: "inferred"`.
  - Match exists **only** in the current panel → intra-panel reference, SKIP.
  - Match exists in **multiple** OTHER panels:
    1. If logic implies a `field_type` (e.g. mentions "dropdown", "date", "GST field"), use it to narrow candidates.
    2. If still multiple candidates → emit with `panel_resolution: "ambiguous"` and attach `candidate_panels: [{panel, variable_name, field_type}, ...]`. Pick the first candidate as `target_field` (or `source_field` — whichever role the referenced field plays) but keep all candidates in `candidate_panels`.
  - No match anywhere → log a warning ("unresolved: <phrase>") and SKIP (do NOT invent).

**3.5 Operation type** — from the POV of the field currently being analyzed:
- Field RECEIVES value or IS CONTROLLED by the referenced field → `operation_type: "incoming"`. `source_field` = referenced field; `target_field` = current field.
- Field PROVIDES value or CONTROLS the referenced field → `operation_type: "outgoing"`. `source_field` = current field; `target_field` = referenced field.

Most BUD logic is phrased from the receiver's POV ("Copy from X", "Visible if X"), so `"incoming"` is the common case. Outgoing is typical for PANEL-type fields that describe what THEY control ("Visible when [another field] = ...") — but even PANEL logic is usually incoming ("this panel is visible when X").

**3.6 Emit** — only if `source_field.panel != target_field.panel`. Build:

```json
{
  "source_field": {
    "field_name":    "<exact from index>",
    "variable_name": "<exact from index>",
    "panel":         "<canonical panel name>",
    "field_type":    "<from index>"
  },
  "target_field": {
    "field_name":    "<exact>",
    "variable_name": "<exact>",
    "panel":         "<canonical>",
    "field_type":    "<from index>"
  },
  "reference_details": {
    "matched_text":      "<the noun phrase that matched>",
    "location_found":    "logic",
    "relationship_type": "<one of the 9 relationship types>",
    "operation_type":    "incoming" ,
    "panel_resolution":  "explicit",
    "raw_expression":    "<full logic text, truncated to 600 chars if longer>",
    "candidate_panels":  []
  }
}
```

Omit `candidate_panels` key entirely UNLESS `panel_resolution == "ambiguous"`.

</field_loop>

### Step 4 — Deduplication

Apply these rules in order before writing output:

1. **PANEL-field echoing a controlling field's logic**: If the current field is of type `PANEL` and its logic says "this panel is visible when [dropdown] from [other panel] has value X", that is a redundant echo of the controlling dropdown's own logic. Emit the ref pointing at the **controlling field** (the dropdown) — set `source_field` to the controlling field in the other panel, `target_field` to the PANEL field — instead of treating the PANEL field as an independent receiver of every controlling value. If the controlling dropdown's logic (in its own panel) will also produce this ref, prefer the version anchored on the dropdown and drop the panel-side duplicate.
2. **Bidirectional echoes**: If emitting two refs with the same `(source.variable_name, target.variable_name, relationship_type)` but inverted `operation_type`, keep only the one whose `raw_expression` is longer / more specific.
3. **Exact duplicates**: Collapse entries where `(source_field.variable_name, target_field.variable_name, relationship_type)` already appear together.

### Step 5 — Write output

Write the JSON object to `$OUTPUT_FILE`:

```json
{
  "panel_name": "$PANEL_NAME",
  "cross_panel_references": [ ... ],
  "errors": []
}
```

If zero references were found, emit `"cross_panel_references": []`. Always include `errors` as an array (may be empty).

Log: `"Step 5: wrote <N> refs for panel <name>"`.

---

## Panel Name Variations Table

Map free-text panel mentions in logic to canonical panel names. The `$ALL_PANELS_INDEX_FILE` carries the canonical names; treat its keys as the authoritative list. Then use these common variants (case-insensitive) to help resolve phrases:

| Text pattern in logic | Likely canonical panel |
|---|---|
| "basic detail panel", "basic details" | Basic Details |
| "GST field", "GST panel", "PAN and GST" | PAN and GST Details |
| "vendor basic", "vendor details" | Vendor Basic Details |
| "address panel", "address details" | Address Details |
| "bank panel", "bank details" | Bank Details |
| "CIN panel", "TDS panel" | CIN and TDS Details |
| "MSME panel" | MSME Details |
| "payment panel" | Payment Details |
| "withholding panel" | Withholding Tax Details |

**Rule:** if a textual variation does not match any key in the global index, treat it as "not explicit" and fall through to ladder step (b). Never create a panel name that does not exist in the index.

---

## Examples

### Example 1 — explicit panel, incoming copy
Field: `Company Code` in panel `Withholding Tax Details`
Logic: `"Copy from 'Basic Details' panel"`
Index contains `Basic Details` → `Company Code` (variable_name `__companycode__`).

Emit:
```json
{
  "source_field": {"field_name": "Company Code", "variable_name": "__companycode__", "panel": "Basic Details", "field_type": "TEXT"},
  "target_field": {"field_name": "Company Code", "variable_name": "__companycode_wht__", "panel": "Withholding Tax Details", "field_type": "TEXT"},
  "reference_details": {
    "matched_text": "'Basic Details' panel",
    "location_found": "logic",
    "relationship_type": "copy_operation",
    "operation_type": "incoming",
    "panel_resolution": "explicit",
    "raw_expression": "Copy from 'Basic Details' panel"
  }
}
```

### Example 2 — unnamed panel, inferred
Field: `Title` in panel `Vendor Basic Details`
Logic: `"Title derived from PAN Card"`
Flat map: `"pan"` → exactly one hit in panel `PAN and GST Details`.

Emit with `panel_resolution: "inferred"`, source = PAN field in PAN and GST Details.

### Example 3 — ambiguous
Field: `Name/ First Name` in panel `Vendor Basic Details`
Logic: `"Copy from Name field"`
Flat map: `"name"` → multiple hits (one in `Basic Details`, one in `SPOC Details`).

Emit with `panel_resolution: "ambiguous"` and:
```json
"candidate_panels": [
  {"panel": "Basic Details", "variable_name": "__name_basic__", "field_type": "TEXT"},
  {"panel": "SPOC Details", "variable_name": "__name_spoc__", "field_type": "TEXT"}
]
```

### Example 4 — intra-panel (SKIP)
Field: `State` in panel `Address Details`
Logic: `"Auto-fill based on Pincode"` — `Pincode` exists only in `Address Details`.
→ SKIP. Do NOT emit.

---

## Output — REQUIRED FORMAT

```json
{
  "panel_name": "<current panel>",
  "cross_panel_references": [
    { "source_field": {...}, "target_field": {...}, "reference_details": {...} }
  ],
  "errors": []
}
```

- Top-level MUST be a JSON object.
- Keys MUST be exactly `panel_name`, `cross_panel_references`, `errors`.
- `cross_panel_references` MUST be a (possibly empty) array.
- `errors` MUST be a (possibly empty) array of strings.
- Never return prose. Never wrap the JSON in a code fence. Only write the JSON object to `$OUTPUT_FILE`.
