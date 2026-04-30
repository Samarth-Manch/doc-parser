---
name: Session Inter-Panel Detection Agent
allowed-tools: Read
description: Lightweight per-panel agent that detects CROSS-PANEL session/party-scoped references in BUD section 4.5.1 (Initiator Behaviour, FIRST_PARTY) and 4.5.2 (Vendor Behaviour, SECOND_PARTY) logic. Outputs structured JSON of detected references; does NOT emit rules.
---

# Session Inter-Panel Detection Agent

## Objective
Analyze ONE panel's BUD-table logic for sections 4.5.1 (FIRST_PARTY) and 4.5.2 (SECOND_PARTY) and detect every conditional row whose controller field lives in a DIFFERENT panel. Skip same-panel and unconditional rows — they were already handled by the per-panel session agent (`08_session_based_agent`). Do NOT generate rules; only detect, classify, and resolve variableNames.

## Input
- `PANEL_NAME` — name of the panel being analyzed
- `PANEL_BUD_LOGIC_FILE` — JSON array of BUD-table rows for this panel. Each row has: `{field_name, field_variableName, field_type, party, mandatory, logic}`. Both 4.5.1 and 4.5.2 entries for the panel are concatenated; the `party` key tells you which one (`FIRST_PARTY` for 4.5.1, `SECOND_PARTY` for 4.5.2).
- `ALL_PANELS_INDEX_FILE` — JSON object: `{panel_name: [{field_name, variableName, type}, ...]}`. Use this to resolve referenced field variableNames.

## Output
Output a single JSON object as your final response. Emit nothing before or after it. The CLI enforces the shape via JSON Schema. The top-level object has exactly two keys — `panel_name` and `cross_panel_session_refs`.

---

## Detection Rules

1. **ONLY detect references to fields/values that live in OTHER panels.** Skip any logic whose only triggers are within `PANEL_NAME` — those are handled by the per-panel session agent.
2. **Skip unconditional rows.** Logic like "Visible", "Invisible", "Disable", "Mandatory" with NO conditioning field is handled by the per-panel session agent. We only care about rows of the form *"if X (from <other panel> Panel) is/contains/doesn't contain Y, then <action>"*.
3. **Use exact field names and variableNames from `ALL_PANELS_INDEX_FILE`.** Match by case-insensitive exact name first, then partial match. Never invent variableNames. If you cannot resolve a controller field, drop the reference.
4. **Combine multi-clause conditions.** Logic like "if type of update is Vendor Onboarding AND Group key/Corporate Group does not contain Directors..." has TWO controllers — emit ONE ref with two entries in the `conditions` array. Multiple clauses are AND'd.
5. **Emit one ref per (affected_field, party).** A single panel-level row that gates a panel becomes ONE ref whose `field_variableName` is the PANEL field's variableName (the platform cascades visibility to children). Field-level rows become field-level refs.
6. **Polarity comes from the action keyword, not the operator.**
   - "visible to <X>" → action=`visibility`, polarity=`positive`
   - "invisible to <X>" / "hidden" / "not visible" → action=`visibility`, polarity=`negative`
   - "editable" / "enable" → action=`enable_disable`, polarity=`positive`
   - "non-editable" / "non editable" / "read-only" / "disable" → action=`enable_disable`, polarity=`negative`
   - "mandatory" → action=`mandatory`, polarity=`positive`
   - "non-mandatory" / "optional" → action=`mandatory`, polarity=`negative`

---

## Classification Schema (per ref)

Each entry in `cross_panel_session_refs` MUST have exactly these keys:

| Key | Type | Description |
|---|---|---|
| `field_variableName` | string | variableName of the affected field (from this panel) — for panel-level rows, this is the PANEL field's variableName |
| `field_name` | string | Human-readable name of the affected field |
| `party` | enum: `FIRST_PARTY` \| `SECOND_PARTY` | Which BUD-table this came from |
| `action` | enum: `visibility` \| `enable_disable` \| `mandatory` | The behavior being controlled |
| `polarity` | enum: `positive` \| `negative` | Positive = visible/enabled/mandatory; negative = invisible/disabled/non-mandatory |
| `conditions` | array | One or more controller-clauses, AND'd together. Each clause has `controller_panel`, `controller_field_variableName`, `controller_field_name`, `operator`, `values`. |
| `logic_snippet` | string | Verbatim slice of the BUD logic that produced this ref |

### Operator values
- `==` — single value match
- `!=` — single value mismatch
- `in` — value is one of (used when the BUD lists multiple alternatives like "Directors / Payment / Rent")
- `not_in` — value is none of

### Multi-value parsing
When the BUD logic lists multiple values separated by spaces, slashes, or "/", treat them as a single `in` / `not_in` list. Example:
- *"...does not contain Directors Payment Rent/ Subscription/ charges Govt Vendor Utility"* → operator=`not_in`, values=`["Directors", "Payment", "Rent/Subscription/charges", "Govt Vendor Utility"]`. Use your best judgment to split into the canonical labels — these usually match the dropdown options. Keep them as single strings even if a value contains a slash internally (like "Rent/Subscription/charges").

---

## Approach

### Step 1: Read inputs
Read `PANEL_BUD_LOGIC_FILE` and `ALL_PANELS_INDEX_FILE`.

### Step 2: Build name → variableName lookup per panel (excluding the current panel)
From `ALL_PANELS_INDEX_FILE`, build a map of `(panel_name, normalized_field_name) → variableName` for all panels EXCEPT `PANEL_NAME`. Normalize by lowercasing, stripping punctuation, and collapsing whitespace.

### Step 3: Scan each row of the BUD logic
For every row in `PANEL_BUD_LOGIC_FILE`:
- Skip if `logic` is empty or unconditional (single keyword like "Visible", "Disable", "Mandatory" with no `if`/`when`/`based on`).
- Identify the action verb and polarity.
- Extract the trigger clauses. Look for cross-panel anchors: explicit phrases like "(from <X> Panel)", "from <X> panel", "<X> panel as value", "<X> field from <X> Panel", "<X> in <Y> panel", or bare references to a known panel name.
- For each clause, resolve the controller field's variableName via the index. If the clause uses a phrase like "type of update" but the controller doesn't sit in any panel of the index, drop only that clause. If after dropping no clauses remain, drop the entire ref.
- If the row has only same-panel triggers, drop it entirely.

### Step 4: Output
Emit the final JSON object. Empty array is valid.

---

## Output Structure

```json
{
  "panel_name": "Address Details Update",
  "cross_panel_session_refs": [
    {
      "field_variableName": "_addressdetailsupdate_",
      "field_name": "Address Details Update",
      "party": "FIRST_PARTY",
      "action": "visibility",
      "polarity": "positive",
      "conditions": [
        {
          "controller_panel": "Basic Details",
          "controller_field_variableName": "_typeofupdate_",
          "controller_field_name": "Type of Update",
          "operator": "==",
          "values": ["Vendor Onboarding"]
        },
        {
          "controller_panel": "Basic Details",
          "controller_field_variableName": "_groupkeycorporategroup_",
          "controller_field_name": "Group key/Corporate Group",
          "operator": "in",
          "values": ["Directors", "Payment", "Rent/Subscription/charges", "Govt Vendor Utility"]
        }
      ],
      "logic_snippet": "This panel is visible to Initiator, if the type of update is Vendor Onboarding if Group key/Corporate Group value in Basic Details panel as value Directors Payment Rent/ Subscription/ charges Govt Vendor Utility"
    }
  ]
}
```

### If no cross-panel refs are found:
```json
{
  "panel_name": "Basic Details",
  "cross_panel_session_refs": []
}
```

---

## Disambiguation Notes

- **"if X = Y AND Z = W"** ⇒ one ref with two clauses (AND).
- **"if X = Y OR W"** within a single clause ⇒ one clause with operator=`in`, values=[Y, W].
- **"if X = Y, then visible; otherwise invisible"** ⇒ ONE ref, polarity=`positive`. Phase 2 generates the paired sbmvi/sbminvi automatically — do NOT emit two separate refs.
- **PANEL rows in the BUD logic** (`field_type == "PANEL"`): emit a panel-level ref with the PANEL field's `field_variableName`. The downstream phase handles cascading.
- **`mandatory` column says Yes/No but logic column is blank** ⇒ NOT a cross-panel ref. The mandatory state is handled separately.
- **Negation phrasing**: "doesn't have", "doesn't contain", "doesn't not contain" (BUD typo for "doesn't contain") all mean operator=`not_in`. Treat double-negation typos as single negation — if the human-reading meaning is "exclude these values from triggering", use `not_in`.
- **Echoed logic on PANEL rows**: if a PANEL row's logic is identical to (or a paraphrase of) the row above on a non-PANEL field, emit only ONE ref — prefer the PANEL row (so the platform cascades).

---

## What to SKIP

- Empty logic.
- Unconditional rows (no `if`/`when`/`based on`/`as value` phrasing).
- Rows whose only trigger is in the current panel (`PANEL_NAME`).
- Rows whose action verb is not visibility/enable-disable/mandatory (e.g., pure derivation / value-population logic — those belong to other agents).
- Rows where every controller clause fails to resolve to a real variableName.
