# Issue 4: Duplicate Cross-Panel Visibility Rules for Multiselect Dropdown

## BUD
`documents/Pidilite Vendor block-unblock BUD_modified.docx`

## Field
**"Which function you would like to Update?"** — `MULTISELECT_EXTERNAL_DROPDOWN` in panel **Vendor Details**

## Expected Behavior (from BUD)
1. By default, all 6 target panels are **invisible**
2. Whichever panels are selected in the multiselect dropdown become **visible**
3. Unselected panels remain **invisible**
4. On value change: clear + autosave + refresh all associated panel fields

## Observed Behavior
- 11 expression rules generated on this field (should be ~3-4)
- Only one panel's visibility works correctly
- 2 rules have broken `source_fields` with double underscores

---

## Root Cause Analysis

### Problem 1: Duplicate logic in the BUD itself

The panel visibility logic is written in **3 places** in the BUD:

#### A. On the dropdown field (Vendor Details panel) — the canonical source
> "Whichever panels are selected in the multiselect dropdown, those panels should be made visible. By default other panels will be invisible."

#### B. On 6 PANEL-type fields — redundant copies
Each target panel has a PANEL field (often placed inside another panel's section) that repeats the same logic:

| Section in BUD | PANEL Field | Logic |
|----------------|------------|-------|
| Vendor Details | `Block / Unblock posting all company code` | *"If ... selected in 'Which function you would like to Update?', then this panel will be visible..."* |
| Block/Unblock posting all | `Block / Unblock posting selected company code` | Same pattern |
| Block/Unblock posting selected | `Block / Unblock payment all company code` | Same pattern |
| Block/Unblock payment all | `Block / Unblock payment selected company code` | Same pattern |
| Block/Unblock payment selected | `Block / Unblock purchase Org all company code` | Same pattern |
| Block/Unblock purchase Org all | `Block / Unblock purchase Org selected company code` | Same pattern |

#### C. On individual fields within each panel — mandatory logic
Fields like "Posting block new", "Payment block New", "Purchase org new" each also reference the dropdown:
> *"if field 'Which function you would like to Update?' value is '...' then it is mandatory, otherwise non mandatory"*

**Impact**: The BUD states the same visibility rule **7 times** (1 on dropdown + 6 on PANEL fields). This causes the Phase 1 detection agent to emit refs from both directions.

### Problem 2: How duplicates propagate through the pipeline

The inter-panel dispatcher (Stage 6) Phase 1 detection agents emit **two kinds of refs** for the same logical relationship:

1. **From target panel perspective** — `referenced_field_variableName` = `_whichfunctionyouwouldliketoupdatevendordetails_` (the dropdown). 19 such refs exist. They get grouped together under one source field key and produce **1 combined visibility rule** (Rule 1) covering all 6 panels.

2. **From source panel perspective** — `referenced_field_variableName` = `_blockunblockpostingallcompanycode_` (the panel PANEL field itself). 6 such refs exist (one per target panel). Each gets grouped under a **different key** and triggers a **separate agent call**, producing **6 individual per-panel visibility rules** (Rules 4-9).

The `group_complex_refs_by_source_field()` function in `inter_panel_utils.py` groups by `referenced_field_variableName`. Since the two detection directions use different reference targets, they end up in separate groups and generate duplicate rules.

### Problem 3: No `on("load")` default invisibility

The BUD says "by default invisible" but neither the expression agent (Stage 5) nor the inter-panel agent (Stage 6) generates an `on("load")` rule. The agents don't know how to translate "by default" into `on("load") and minvi(...)`. This is an agent/prompt gap — **fixing the BUD will NOT fix this**.

### Problem 4: Double underscore bug in `source_fields`

Rules 6 and 9 have `source_fields: ["__whichfunctionyouwouldliketoupdatevendordetails__"]` (double underscores). This is a code bug in the inter-panel agent output translation, not caused by the BUD. These rules never fire. **Fixing the BUD will NOT fix this**.

### Problem 5: `mm`/`mnm` applied to PANEL variables instead of child fields

The agent generates expressions like `mm(condition, "_blockunblockpaymentallcompanycode_")` — making a PANEL mandatory. This has no effect. The mandatory functions should target individual fields **within** that panel.

**This CAN be fixed deterministically** — see Fix D below.

### Evidence (from `output/block_unblock/runs/24/inter_panel/temp/`)

**Combined group** (correct):
- File: `complex_which_function_you_would_like_to_update_*_refs.json` — 19 refs
- All have `referenced_field_variableName: "_whichfunctionyouwouldliketoupdatevendordetails_"`
- Produces Rules 1-3 (visibility combined, mandatory, clearing)

**Per-panel groups** (duplicates):
- Files: `complex_block___unblock_*_refs.json` — 1-2 refs each
- Each has `referenced_field_variableName` = panel's PANEL field variable
- But `field_variableName` = `_whichfunctionyouwouldliketoupdatevendordetails_` (the dropdown)
- Each produces a separate visibility rule (Rules 4-9) that duplicates part of Rule 1

---

## What fixing the BUD alone will/won't solve

| Problem | Fixed by BUD fix? | Why |
|---------|:-:|-----|
| Duplicate visibility rules (7x) | Yes | Removing redundant PANEL-field logic means Phase 1 only detects refs in one direction |
| No `on("load")` default invisibility | **No** | Agent/prompt gap — doesn't know how to handle "by default" |
| Double underscore `source_fields` bug | **No** | Code bug in inter-panel agent output translation |
| `mm`/`mnm` on PANEL variables | **No** | Agent doesn't distinguish PANEL vs field targets |

---

## Fix Options

### Fix A: Fix the BUD — removes duplication source
Remove the visibility logic from the 6 PANEL-type fields. Keep it only on the dropdown field. The PANEL fields should just be structural markers with no logic.

**Solves**: Duplicate rules
**Does NOT solve**: on("load"), double underscore, mm/mnm on panels

### Fix B: Deduplicate refs before Phase 2 — recommended pipeline fix
After Phase 1 collects all refs and before `group_complex_refs_by_source_field()` runs, normalize refs so that when a ref has:
- `field_variableName` = a controlling field (e.g., the dropdown)
- `referenced_field_variableName` = a PANEL-type field

...it gets re-keyed to use the controlling field as `referenced_field_variableName` instead, merging into the existing group.

**Where**: `inter_panel_dispatcher.py`, between lines ~1000-1024, before `groups = group_complex_refs_by_source_field(complex_refs)`.

**Solves**: Duplicate rules (even if BUD has redundancy)
**Pros**: Prevents duplicate agent calls (saves tokens), handles any BUD style
**Cons**: Needs careful handling to avoid dropping legitimate reverse-direction refs

### Fix C: Deduplicate in Phase 3 (merge step) — safest
In `merge_all_rules_into_output()`, after all rules are collected, deduplicate expression rules on the same field that have the same `_expressionRuleType` and whose target variables are a subset of another rule's targets.

**Solves**: Duplicate rules
**Pros**: No risk to other BUDs, catches any source of duplication
**Cons**: Duplicate agent calls still happen (wasted tokens/time)

### Fix D: Deterministic PANEL variable expansion — new post-processing step
Add a post-processing step (in the dispatcher or `convert_to_api_format.py`) that expands PANEL variable names in expression functions to their child fields:

**Algorithm**:
1. Build a map: PANEL variableName → list of child field variableNames (from panel structure)
2. Scan all `conditionalValues` expressions
3. For any function argument (`mm`, `mnm`, `cf`, `mvi`, `minvi`, `dis`, `en`, etc.) that matches a PANEL variableName, replace it with all child fields of that panel
4. Skip structural types (`ARRAY_HDR`, `ARRAY_END`, `GRP_HDR`, `GRP_END`, `ROW_HDR`, `ROW_END`) from expansion

**Example**:
```
# Before (broken — targets a PANEL)
mm(condition, "_blockunblockpaymentallcompanycode_")

# After (correct — targets all child fields)
mm(condition, "_companycodeblockunblockpaymentallcompanycode_", "_paymentblockoldblockunblockpaymentallcompanycode_", "_paymentblocknewblockunblockpaymentallcompanycode_", "_reasonforblockunblockblockunblockpaymentallcompanycode_", "_requesterremarkblockunblockpaymentallcompanycode_")
```

**Solves**: mm/mnm on panels, and also makes cf/mvi/minvi/dis work correctly when agents target panels
**Pros**: Purely deterministic, no LLM involved, handles any BUD, also useful as a general safety net
**Where**: New function, callable from `inter_panel_dispatcher.py` Phase 3 or as a new pipeline stage

### Fix E: Fix detection agent prompt — prevents duplicate detection
Update `.claude/agents/mini/inter_panel_detect_refs.md` to only emit refs from the **target panel's perspective** — always use the controlling field (dropdown) as `referenced_field_variableName`, never the panel PANEL field.

**Solves**: Duplicate rules
**Pros**: Fixes at the source
**Cons**: LLM prompts are less deterministic; may not fully prevent duplicates

### Fix F: Add `on("load")` support to expression agent prompt
Update `.claude/agents/mini/expression_rule_agent.md` and/or `inter_panel_detect_refs.md` to recognize "by default invisible/visible" phrases and emit `on("load") and minvi(true, ...)` or `on("load") and mvi(true, ...)` rules.

**Solves**: Default invisibility not applied on form load
**Where**: Agent prompt update

### Fix G: Fix double underscore bug
Trace where `__varname__` (double underscore) comes from in the inter-panel output translation. Likely in `translate_expression_agent_output()` in `inter_panel_utils.py` or in the agent prompt itself. Add normalization to strip double underscores to single.

**Solves**: 2 rules with broken source_fields that never fire

---

## Recommended Fix Order

1. **Fix A (BUD)** — Quick win, removes the most visible duplication source
2. **Fix D (PANEL expansion)** — Deterministic, high value, applies broadly
3. **Fix G (double underscore)** — Small bug fix
4. **Fix B or C (dedup refs/rules)** — Pipeline resilience against future BUD redundancy
5. **Fix F (on("load") support)** — Agent prompt improvement
6. **Fix E (detection prompt)** — Nice to have, reduces token waste

---

## Correct Expected Output

The field should have exactly **4 expression rules** (+ the EDV Dropdown rule):

### Rule 1: Default invisibility on load
```
on("load") and (minvi(true, "_blockunblockpostingallcompanycode_", "_blockunblockpostingselectedcompanycode_", "_blockunblockpaymentallcompanycode_", "_blockunblockpaymentselectedcompanycode_", "_blockunblockpurchaseorgallcompanycode_", "_blockunblockpurchaseorgselectedcompanycode_"))
```

### Rule 2: Visibility toggle on selection
```
mvi(cntns(vo("_whichfunctionyouwouldliketoupdatevendordetails_"), "Block / Unblock posting all company code"), "_blockunblockpostingallcompanycode_");
minvi(not(cntns(vo("_whichfunctionyouwouldliketoupdatevendordetails_"), "Block / Unblock posting all company code")), "_blockunblockpostingallcompanycode_");
... (repeated for all 6 panels in one expression)
```

### Rule 3: Conditional mandatory on individual fields (not panels)
```
mm(cntns(vo("_whichfunctionyouwouldliketoupdatevendordetails_"), "Block / Unblock posting all company code"), "_postingblocknewblockunblockpostingallcompanycode_");
mnm(not(cntns(vo("_whichfunctionyouwouldliketoupdatevendordetails_"), "Block / Unblock posting all company code")), "_postingblocknewblockunblockpostingallcompanycode_");
... (repeated for each "block new" / "purchase org new" field)
```

### Rule 4: Clear + autosave + refresh on change
```
on("change") and (cf(true, ...all fields...); asdff(true, ...all fields...); rffdd(true, ...); rffd(true, ...))
```

### Rules to DELETE from current output
- Rules 4-9 (duplicate per-panel visibility)
- Rule 2 (mm/mnm targeting PANEL variables — wrong target)
- Rule 10-11 (duplicate mandatory)

---

## Files Involved
- `documents/Pidilite Vendor block-unblock BUD_modified.docx` — BUD with redundant logic
- `dispatchers/agents/inter_panel_dispatcher.py` — Phase 2 grouping logic (~line 1024)
- `dispatchers/agents/inter_panel_utils.py` — `group_complex_refs_by_source_field()` (line 69), `translate_expression_agent_output()`
- `.claude/agents/mini/inter_panel_detect_refs.md` — Phase 1 detection prompt
- `.claude/agents/mini/expression_rule_agent.md` — Phase 2 rule generation prompt
- `dispatchers/agents/convert_to_api_format.py` — potential location for PANEL expansion post-processing
