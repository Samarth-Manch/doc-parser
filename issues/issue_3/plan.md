# Issue 3 — Implementation Plan

Detailed plan for fixes derived from `todo.md`. Organized into pipeline fixes (changes to code and prompts) and BUD fixes (flagged to BUD author).

---

## Pipeline Fix 1: Group Phase 2 Refs by Source Field

**TODO ref:** #1
**Files:** `inter_panel_utils.py`, `inter_panel_dispatcher.py`

### Current behavior

`group_complex_refs_by_source_panel()` in `inter_panel_utils.py:45` groups all complex refs by `ref.get('referenced_panel')` — the panel the source field lives in. In the Block/Unblock BUD, the field `Which function you would like to Update?` lives in the Vendor Details panel. Six sub-panels all reference this same field, producing 7 separate groups (one per target panel + one for Vendor Details itself). Each group gets its own Phase 2 agent call, and each agent independently creates visibility + clearing rules on the same source field. Result: 16 rules where ~4 are needed.

### What changes

**`inter_panel_utils.py`** — Replace `group_complex_refs_by_source_panel()` with a new function `group_complex_refs_by_source_field()`. The grouping key should be the `referenced_field_variableName` (the field where rules will be placed), not the `referenced_panel`.

The current function:
```
Groups by: ref['referenced_panel']
Result: {"Vendor Details": [refs...], "posting all": [refs...], "payment all": [refs...], ...}
```

Should become:
```
Groups by: ref['referenced_field_variableName']
Result: {"_whichfunctionyouwouldliketoupdatevendordetails_": [all refs from all 6 panels...]}
```

When multiple refs from different target panels all point to the same source field, they end up in one group. One agent call sees all 6 target panels at once and produces one consolidated visibility rule and one clearing rule.

**`inter_panel_dispatcher.py`** — Update the Phase 2 loop (lines 876–917) to use the new grouping function. The `group_label` changes from a panel name to a field variableName (or field name for readability). The `involved_panels` collection logic stays the same — collect the source panel plus all panels containing the ref's `field_variableName`.

### Involved panel collection adjustment

Currently, for each group the dispatcher collects involved panels by:
1. Adding the source panel (the group key)
2. Adding panels containing each ref's `field_variableName`

With the new grouping, the source panel is no longer the group key. Instead:
1. Look up the source field's panel from `var_index` using the group key (the source field variableName)
2. Add that panel
3. Add panels containing each ref's `field_variableName` (same as before)

### Edge case: multiple source fields in the same panel

If a panel has two different source fields that are each referenced cross-panel, they become two separate groups — which is correct. Each source field gets its own agent call with its own consolidated rule.

---

## Pipeline Fix 2: Child Fields in Panel Visibility Rules

**TODO ref:** #2
**File:** `.claude/agents/mini/expression_rule_agent.md`

### Current behavior

The expression rule agent has no instruction about panel-type fields. When it creates `mvi`/`minvi` targeting a PANEL variable, it inconsistently includes child fields — sometimes listing all 6-7 children, sometimes only the panel variable itself. Agents that skip the reasoning steps (empty log files) are the ones that produce panel-only rules.

### What changes

Add a new section to `expression_rule_agent.md` under the "RULES (FOLLOW STRICTLY)" section, after the existing rules. The instruction should state:

**Panel Visibility Rule:**
When creating `mvi`/`minvi` rules that target a field with `type: "PANEL"`, always include ALL fields that belong to that panel in the same `mvi`/`minvi` call. A field "belongs to" a panel if it appears after that PANEL field and before the next PANEL field (or end of the fields list) in FIELDS_JSON. The `mvi`/`minvi` call must list the PANEL variable first, followed by every child field's variableName.

Example: If the panel field is `_vendordetails_` (type: PANEL) and it has children `_vendorname_`, `_vendorcode_`, `_vendoremail_`:
```
mvi(condition, "_vendordetails_", "_vendorname_", "_vendorcode_", "_vendoremail_")
```

Never target only the PANEL variable without its children — the children must be explicitly listed or they won't be shown/hidden along with the panel.

### Where to place in the prompt

After the current rule 15 (party-scoped logic). Add as rule 16.

---

## Pipeline Fix 3: Handle Nested `source_field`/`referenced_field` Detection Format

**TODO ref:** #3, #4
**File:** `inter_panel_dispatcher.py`

### Current behavior

`_normalize_single_ref()` (line 211) expects flat keys like `referenced_panel`, `field_variableName`, etc. The Phase 1 detection agent for `posting all company code` returned a nested format:

```json
{
  "source_field": { "field_name": "...", "variableName": "...", "panel": "..." },
  "referenced_field": { "field_name": "...", "variableName": "...", "panel": "..." }
}
```

The normalizer finds no `referenced_panel` at the top level and returns `None` for all 3 refs.

### What changes

**In `_normalize_single_ref()`**, add early detection for the nested object format before the existing key lookups. If `ref.get('source_field')` or `ref.get('referenced_field')` is a dict, flatten the nested structure into the existing flat key expectations:

- Extract `referenced_panel` from `ref['referenced_field']['panel']`
- Extract `referenced_field_variableName` from `ref['referenced_field']['variableName']`
- Extract `referenced_field_name` from `ref['referenced_field']['field_name']`
- Extract `field_variableName` from `ref['source_field']['variableName']`
- Extract `field_name` from `ref['source_field']['field_name']`

This flattening should happen at the top of the function, before the existing key-lookup chains. Once flattened, the rest of the function proceeds as normal.

### Also in `normalize_detection_output()`

The outer loop in `normalize_detection_output()` (line 181) iterates `refs_raw` and checks for nested `references` sub-arrays. Add a parallel check: if a ref has `source_field` or `referenced_field` as a dict, pass it through to `_normalize_single_ref()` which will now handle it.

### TODO #4 resolves automatically

Once the posting all panel's refs are recovered, the Phase 2 agent will see the mandatory logic and generate the `mm`/`mnm` rule for `Posting block new`. No separate fix needed.

---

## Pipeline Fix 4: Validate EDV Agent — Consistent "Validation" Keyword Detection

**TODO ref:** #7
**File:** `.claude/agents/mini/04_validate_edv_agent_v2.md`

### Current behavior

All 6 "old" fields are `EXTERNAL_DROP_DOWN_VALUE` type (not TEXT as initially assumed in the todo). The BUD logic for all of them says "Old Status should be derived automatically through Validation from reference table - [TABLE] attribute [N]." Despite identical phrasing, only 1 of 6 fields (Purchase org old in "all" panel) received a Validate EDV rule. The other 5 got `Get Data From EDV` rules but no Validate EDV.

The Validate EDV agent prompt lists these trigger keywords in Step 1: "derive", "fetch", "auto-populate", "lookup", "validate against table", "on validation", "will be populated". The BUD phrasing "through Validation from reference table" is close to these but doesn't exactly match any of them.

### What changes

**In Step 1 of the approach** (line 76), expand the keyword list to explicitly include:
- "through Validation from"
- "derived automatically through Validation"
- "through Validation"

Add these to the same line where the current keywords are listed so the agent checks for them during its logic scan.

**In Step 6** (the decision step, line 98), add a clarifying note: if the logic mentions validation/derivation from a reference table AND auto-population ("derived automatically"), a Validate EDV rule is needed even if the field already has an EDV Dropdown rule. The two rules serve different purposes — EDV Dropdown populates the dropdown options, while Validate EDV performs a lookup and auto-fills related fields on selection.

### Why only 1 of 6 succeeded

The agent is non-deterministic. The keyword "Validation" is close enough to "validate" that the agent sometimes picks it up (Purchase org old) and sometimes doesn't (the other 5). Making the exact BUD phrasing an explicit keyword removes the ambiguity.

---

## Pipeline Fix 5: Capture CLI Failure Output

**TODO ref:** #11
**File:** `inter_panel_dispatcher.py`

### Current behavior

**Phase 1** (line 395-411): `subprocess.run` with `capture_output=True`. On non-zero exit code, logs `FAILED (exit code N)` but never logs `process.stdout` or `process.stderr`.

**Phase 2** (line 604-627): `subprocess.Popen` pipes stdout to `print()` (line 620) which goes to terminal and is lost. The per-group log file only has a header line.

### What changes

**Phase 1 worker** (`detect_cross_panel_refs`, around line 408):
After logging the failure, also log the first ~500 characters of `process.stdout` and `process.stderr` to the master log. This captures the reason for failure (API error, rate limit, context overflow).

**Phase 2 worker** (`call_complex_rules_agent`, around line 619-620):
Instead of just printing each stdout line to terminal, also write it to the per-group log file. Currently line 620 does `print(line, end='', flush=True)` — also append the line to `log_file`. On failure (line 624), log the accumulated output to the master log.

---

## Pipeline Fix 6: Recover Partial Output on CLI Failure

**TODO ref:** #12
**File:** `inter_panel_dispatcher.py`

### Current behavior

**Phase 1** (line 408): If `returncode != 0`, immediately returns `None` without checking if the output file exists.

**Phase 2** (line 624): If `returncode != 0`, immediately returns `{}` without checking if the output file exists.

### What changes

**Phase 1** (`detect_cross_panel_refs`):
Move the `returncode != 0` check (line 408) to AFTER the output file check (line 414). The logic becomes:
1. Check if output file exists and contains valid JSON → use it (regardless of exit code)
2. If no valid output file AND exit code is non-zero → return None
3. If no valid output file AND exit code is zero → return None (no refs detected)

**Phase 2** (`call_complex_rules_agent`):
Same pattern. Move the `returncode != 0` check (line 624) to after the output file check (line 630). If the file exists and is valid JSON, use it. Only return `{}` when both conditions fail.

In both cases, log a warning when recovering output from a failed process:
`"Phase N: '{panel}' CLI failed (exit code N) but output file found — recovering"`

---

## Pipeline Fix 7: Cross-Panel EDV — Design Decision Needed

**TODO ref:** #6, #8

### Problem

Seven fields across the "all company code" and "selected company code" panels have cross-panel EDV dependencies on `Vendor Number` from Vendor Details. The intra-panel EDV agent (stage 3) creates self-referencing rules (`source=self, dest=self`) or empty `criterias` because it cannot reference fields from other panels. The inter-panel agent (stage 6) only handles expression rules, not EDV params.

### Two options

**Option A — Post-processing step in inter-panel dispatcher:**
After Phase 2, add a deterministic step that scans the output for EDV rules with:
- `source_fields == destination_fields` (self-referencing), or
- `criterias: []` where the BUD logic mentions a field from another panel

For each such rule, look up the cross-panel field's variableName from `var_index` and populate the missing `criterias` or fix the `source_fields`.

Pros: No agent prompt changes. Deterministic — no LLM non-determinism.
Cons: Need to parse BUD logic text to identify which cross-panel field to use. Hard to do reliably without LLM.

**Option B — Give EDV agent cross-panel context:**
Modify the EDV dispatcher to provide a compact all-panels index (same as inter-panel Phase 1 gets) alongside the panel fields and reference tables. Update the EDV agent prompt to say: "If the logic references a field from another panel, look it up in ALL_PANELS_INDEX to get its variableName and use it in criterias/source_fields."

Pros: The agent already identifies these dependencies correctly in its reasoning. Just needs the variableName.
Cons: Changes the EDV agent's interface. Increases context size for all panels, not just cross-panel ones.

**Option C — Handle in inter-panel Phase 2:**
Extend the inter-panel Phase 2 agent prompt to handle EDV param population (criterias, source_fields) for cross-panel dependencies, in addition to expression rules. The refs for these fields would be classified as `edv` in Phase 1 and routed to the agent.

Pros: Inter-panel agent already has cross-panel context.
Cons: Adds EDV-specific logic to the expression rule agent, which is currently focused only on Expression (Client) rules.

**Recommendation:** Option B is cleanest. The EDV agent already does the right analysis — it just lacks the cross-panel variableName. Giving it the index is minimal change and solves both TODO #6 (TEXT fields) and #8 (cascading dropdowns) in one shot.

### Decision needed before implementation
Which option to proceed with. This affects the EDV dispatcher, EDV agent prompt, and potentially the inter-panel dispatcher.

---

## BUD Fixes — Flag to BUD Author

These cannot be fixed in the pipeline. They need BUD document updates.

### BUD Fix 1: TRUE_FALSE Reference Table Name (TODO #5)

**All 6 "block new" fields** across the sub-panels say `"Dropdown Values - True False"` without mentioning any reference table. The agent has no way to know `TRUE_FALSE` is a platform EDV table.

**Requested change:** Update the logic for all 6 fields to:
> `"Dropdown values from TRUE_FALSE reference table, attribute 1. If field 'Which function you would like to Update?' value is '[panel name]' then it is mandatory, otherwise non-mandatory."`

**Affected fields:**
- Posting block new (posting all, posting selected)
- Payment block New (payment all, payment selected)
- Purchase org new (purchase org all, purchase org selected)

### BUD Fix 2: Approver Setup — Undefined Source Field (TODO #9)

**9 fields** in Approver Setup reference `"Choose the Group of Company"` which does not exist in this BUD.

**Requested change:** Either:
1. Define "Choose the Group of Company" as a field in this form, or
2. Specify the exact variableName from the parent process

### BUD Fix 3: Purchase Org Old — Attribute Mismatch (TODO #10)

`Purchase org old` in "selected" panel says `VC_PURCHASE_DETAILS attribute 2` (Purchase Org value) while the "all" panel correctly says `attribute 7` (block status).

**Requested change:** Update "selected" panel's `Purchase org old` logic to reference `attribute 7`.

---

## Implementation Order

```
Phase 1 — Independent fixes (can be done in parallel):
├── Fix 1: Group by source field (inter_panel_utils.py, inter_panel_dispatcher.py)
├── Fix 2: Panel visibility child fields (expression_rule_agent.md)
├── Fix 4: Validate EDV keywords (04_validate_edv_agent_v2.md)
├── Fix 5: Capture CLI failure output (inter_panel_dispatcher.py)
└── Fix 6: Recover partial output (inter_panel_dispatcher.py)

Phase 2 — Depends on Phase 1:
├── Fix 3: Nested format normalization (inter_panel_dispatcher.py)
│   └── TODO #4 resolves automatically after this
└── BUD fixes flagged to author

Phase 3 — Requires design decision:
└── Fix 7: Cross-panel EDV (decide Option A/B/C, then implement)

Verification run after Phase 1+2:
- Re-run the Block/Unblock BUD pipeline
- Check: "Which function" field has ~4 rules, not 16
- Check: All mvi/minvi calls include child fields
- Check: posting all panel produces refs (not 0)
- Check: Posting block new has mandatory rule
- Check: 5 additional "old" fields have Validate EDV rules
- Check: CLI failures produce diagnostic logs
```
