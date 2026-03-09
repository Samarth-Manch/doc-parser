# Inter-Panel Dispatcher — Fix Plan (v2)

Updated plan reflecting the current state of `inter_panel_dispatcher.py` as of 2026-03-06.
Changes from v1: Phase 1 critical fixes (1.1, 1.2, 1.3) are confirmed implemented. Phase 2a (deterministic copy-to) is obsolete. Phase 4 (cross-panel EDV) is now documented. Grouping strategy updated from source-panel to source-field.

---

## Completed (from v1 plan)

These items from the original plan are confirmed implemented in the current codebase.

### 1.1 Capture CLI failure output — DONE
- Phase 1 worker (lines 464-470): stdout/stderr captured and logged on non-zero exit.
- Phase 2 worker (lines 668-688): Uses `Popen` with stdout piped to both terminal and per-panel log file.

### 1.2 Recover partial output on CLI failure — DONE
- Phase 1 (lines 464-481): `returncode != 0` logs the failure but falls through (`# Fall through to check if output file was still written`). Output file is checked at line 474 and recovered if present.
- Phase 2 (lines 690-702): Same pattern — logs failure, falls through, recovers valid output from disk.

### 1.3 Fix `logic_excerpt` key mismatch in normalizer — DONE
- `_normalize_single_ref()` line 337 now includes `logic_excerpt` in the fallback chain:
  ```python
  'logic_snippet': ref.get('logic_snippet', ref.get('logic_excerpt', ref.get('reference_text', ref.get('logic', ''))))
  ```

### 2.2 Populate empty logic snippets from destination field — DEFERRED (unchanged)
- All empty-snippet refs had valid `logic_excerpt` in detection output. Fix 1.3 resolved 100% of them. Only revisit if a future run produces genuinely empty snippets after 1.3.

---

## Phase 1: Rule Completeness

These address rules that were detected but not generated.

### 1.1 Add clearing-pair instruction to Phase 2 prompt
- **Problem:** The Phase 2 agent generates derivation rules (`ctfd`) but inconsistently omits paired clearing rules (`cf` + `asdff` + `rffdd`). Run 6 lost the Company Code -> House Bank clearing rule this way.
- **Scope:** Expression rule agent prompt (`.claude/agents/mini/expression_rule_agent.md`).
- **Status:** Needs verification — check whether the prompt now includes clearing-pair instructions.
- **Goal:** Explicitly instruct the agent: for every cross-panel derivation, also generate a clearing rule that clears the destination when the source is emptied.

**What is a clearing pair?**

Every cross-panel derivation needs two rules working together on the same source field:

1. **Derivation rule** — fills the destination when the source has a value:
   ```
   ctfd(vo("_companycodebasicdetails_")=="1000", "CIT01", "_housebankpaymentdetails_");
   ctfd(vo("_companycodebasicdetails_")=="2000", "HDF01", "_housebankpaymentdetails_");
   ...
   asdff(true, "_housebankpaymentdetails_")
   ```

2. **Clearing rule** — clears the destination when the source is emptied:
   ```
   on("change") and (
     cf(vo("_companycodebasicdetails_")=="", "_housebankpaymentdetails_");
     asdff(true, "_housebankpaymentdetails_");
     rffdd(vo("_companycodebasicdetails_")=="", "_housebankpaymentdetails_")
   )
   ```

The two rules never conflict because they have **opposite conditions** — derivation fires when the source matches a specific value (`=="1000"`), clearing fires only when the source is empty (`==""`). They are mutually exclusive:

| User action | Derivation condition | Clearing condition | Result |
|---|---|---|---|
| Selects Company Code = "1000" | `=="1000"` -> true -> sets "CIT01" | `==""` -> false -> no-op | House Bank filled |
| Changes to "2000" | `=="2000"` -> true -> sets "HDF01" | `==""` -> false -> no-op | House Bank updated |
| Clears Company Code | all `==` checks -> false -> no-op | `==""` -> true -> clears | House Bank cleared |

The three clearing functions:
- `cf(condition, field)` — clears the field value when condition is true
- `asdff(true, field)` — auto-saves so the cleared value persists
- `rffdd(condition, field)` — resets dropdown UI state

---

## Phase 2: Verification & Observability

These don't fix rules directly but catch future regressions.

### 2.1 Ref-to-rule reconciliation report
- **Problem:** No automated check for whether detected refs resulted in actual rules. Silent losses go unnoticed.
- **Goal:** After Phase 2, compare every Phase 1 ref against generated rules. Log unmatched refs as warnings and write them to `temp/unmatched_refs.json`.

### 2.2 Post-run coverage summary
- **Goal:** Add a summary line like "39 refs detected -> 18 rules created -> 21 unhandled" with breakdown by classification type (copy_to, derivation, visibility, etc.).
- **Current state:** The final summary (lines 1192-1221) has total counts but lacks the explicit refs-to-rules reconciliation format.

### 2.3 Log failed panels in final summary
- **Goal:** Currently failures are only logged inline during Phase 1/2. Add a warning block in the final summary listing which panels failed and how many fields were affected.

### 2.4 Per-rule-type stats in final summary
- **Goal:** Break down generated rules by type (visibility, derivation, mandatory, clear_field, etc.) and compare against Phase 1 classification distribution to spot imbalances.
- **Current state:** Phase 1 has a classification breakdown (lines 901-907) but the final summary doesn't break down generated rules by type.

---

## Phase 3: Normalization Hardening

Lower priority — correctness improvements to the normalizer.

### 3.1 Add `"visibility/state"` to classification mapping (explicit)
- **Problem:** Bank Details returns `"classification": "visibility/state"` which falls through to the catch-all default instead of mapping explicitly.
- **Current state:** Line 273 maps `'visibility_state'` (underscore) but not `'visibility/state'` (slash). The slash variant falls to the default at line 283 -> `'visibility'`, so it works by accident but isn't explicit.
- **Goal:** Add `'visibility/state'` to the explicit mapping tuple at line 272-273.

### 3.2 Preserve original classification as metadata
- **Problem:** The normalizer collapses `visibility_state` into `visibility`, losing the distinction between visibility and state rules.
- **Goal:** Keep the original classification as `_original_classification` metadata so the Phase 2 agent has the full context.

---

## Phase 4: Verify Rule Coverage (Run 6 vs Run 5)

After Phases 1-3 are complete, re-run the pipeline and verify the following.

### 4.1 Rules already present in run 6 (verify they survive re-run)

These were initially flagged as "missing vs run 5" but are confirmed present in the run 6 output as Expression (Client) rules. They use a different rule format than run 5 (expression `ctfd` instead of Copy To) but achieve the same functionality.

| # | Rule | Status in Run 6 | Evidence |
|---|------|-----------------|----------|
| 1 | Company Code -> Copy To Purchase Org | Present | `ctfd(true, vo("_companycodebasicdetails_"), "_companycodepurchaseorganizationdetails_")` on Company Code field |
| 2 | Company Code -> House Bank derivation (1000->CIT01) | Present | Full 11-entry mapping table (`ctfd(vo(...)=="1000", "CIT01", ...)`) on Company Code field |
| 4 | Group Key -> Minority Indicator derivation | Present | `ctfd(rgxtst(tolc(vo("_groupkeycorporategroupbasicdetails_")), "/utility\|government\|director/"), "2", "_minorityindicatorpaymentdetails_")` on Group Key field |
| 5 | Process Type -> Currency derivation | Present | Combined rule: `ctfd(vo(...)=="India", "INR", "_currencypaymentdetails_")` on Select the process type field |

### 4.2 Rules genuinely missing from run 6 (expect recovery from fixes)

| # | Missing Rule | Root Cause | Fixed By |
|---|-------------|------------|----------|
| 3 | Company Code -> House Bank clearing (`cf` + `rffdd`) | Missing clearing pair — derivation exists but no clearing counterpart | 1.1 |
| 6 | Process Type -> Currency/Bank Country clearing (`cf` + `rffdd`) | Clearing pair omitted — derivation+disable exists but no clearing | 1.1 |
| 8 | SSI/MSME Applicable -> Minority Indicator derivation | MSME Phase 2 CLI failure — valid rule written to disk but discarded | Completed (old 1.1, 1.2) |

### 4.3 Rules requiring BUD clarification

| # | Rule | Issue |
|---|------|-------|
| 7 | ID Type -> FDA Registration Number | Run 5: visibility rule (`mvi`/`minvi`). Run 6: mandatory rule (`mm`/`mnm`). BUD says "FDA Registration Number: Derived if ID Type is ZCUCIN" — verify whether the intent is visibility or mandatory. |

### 4.4 Garbage refs to investigate

Run 6 detected 49 refs but filtered 7 with empty `field_variableName` (49 -> 42). These represent detection agent output format variants the normalizer still cannot parse. After applying fixes, check whether the normalizer handles these 7, and if not, identify which panels produced them and what format they used.

**Strategy:** Re-run after Phases 1-3, then diff against run 5 output. Verify 4.1 rules survive, 4.2 rules are recovered, and 4.4 garbage count drops to 0.

---

## Architecture Changes Since v1 Plan (for reference)

These are structural changes already in the codebase that the v1 plan did not reflect.

### A1. Phase 2a (deterministic copy-to) is obsolete
- **v1 plan:** Described Phase 2a as deterministic `build_simple_copy_to_rules()` for simple copy_to refs.
- **Current code:** `build_simple_copy_to_rules()` still exists (line 511) but is **never called**. At lines 959-962, simple copy_to refs are merged into complex refs and sent to the expression agent, which handles them via `ctfd` + `on("change")`. Line 1059 passes `{}` for copy_to_rules:
  ```python
  all_results = merge_all_rules_into_output(input_data, {}, complex_rules)
  ```
- **Note:** The dead `build_simple_copy_to_rules()` function could be removed.

### A2. Grouping changed from source-panel to source-field
- **v1 plan:** Implied grouping by source panel.
- **Current code:** Groups by source field (`group_complex_refs_by_source_field` at line 970). This is more granular — consolidates rules when multiple panels reference the same source field, reducing agent calls and improving context coherence.

### A3. Phase 4: Cross-Panel EDV Processing (new)
- **Not in v1 plan.** The current code has a full Phase 4 (lines 1088-1180) that:
  1. Identifies panels with EDV-classified cross-panel refs (tracked during Phase 1 filtering, lines 928-942).
  2. Filters EDV refs out of Phase 2 (lines 944-949) — they're handled here instead.
  3. Phase 4a: Runs `call_edv_mini_agent()` on each EDV panel to populate dropdown params.
  4. Phase 4b: Runs `call_validate_edv_mini_agent()` on the same panels for Validate EDV rules.
  5. Parses the BUD document for reference tables (via `DocumentParser`).
- This phase reuses the `all_panels_index_file` from Phase 1 and imports `call_edv_mini_agent` / `call_validate_edv_mini_agent` from existing dispatchers.

---

## Out of Scope (Deferred)

- **Copy-to chain expansion** — Downgraded. Fixing CLI failure handling (completed) is sufficient since Phase 1 agents can detect these refs when they run to completion.
- **Cross-group merging for multi-source derivation chains** — Not needed. Separate visibility and derivation rules on the same field coexist correctly on the Manch platform.
- **Unit test for `_build_normalized_ref()`** — Defensive code that wasn't triggered in run 6. Nice-to-have, not blocking.
- **BUD amendments** (explicit panel annotations on Payment Details fields) — Preferred long-term fix but depends on whether the BUD is client-editable.
- **Source-side BUD annotations** — Currently, all cross-panel derivation logic lives exclusively on the destination field. If the BUD also annotated source fields with their downstream effects, the Phase 1 agent analyzing the source panel would detect refs with full context directly — eliminating the empty-snippet problem at its root. Trade-off: maintaining derivation logic in two places creates a consistency risk.
- **Remove dead `build_simple_copy_to_rules()`** — Function at line 511 is unused since copy_to refs are now handled by the expression agent. Low priority cleanup.
