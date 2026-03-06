# Inter-Panel Dispatcher — Fix Plan

Prioritized action plan derived from the post-fix review of v3 run 6.

---

## Phase 1: Critical Reliability Fixes

These directly cause silent rule loss and must be fixed first.

### 1.1 Capture CLI failure output
- **Problem:** When the `claude` CLI exits non-zero, the dispatcher logs the exit code but discards stdout/stderr. No visibility into *why* it failed (API error, rate limit, context overflow, etc.).
- **Scope:** Phase 1 worker and Phase 2 worker in `inter_panel_dispatcher.py`.
- **Goal:** On failure, write captured stdout/stderr to both the per-panel log file and the master log.

### 1.2 Recover partial output on CLI failure
- **Problem:** If the CLI exits non-zero, the dispatcher immediately returns `None`/`{}` — even if the agent already wrote valid output to disk before failing.
- **Evidence (Run 6):**
  - **Phase 1:** Vendor Duplicity Details had 7 valid refs written but all were discarded.
  - **Phase 2:** MSME Details agent wrote a valid SSI → Minority Indicator derivation rule to `complex_msme_details_rules.json` (timestamp 13:04), then the CLI crashed at 13:05 with exit code 1. The dispatcher saw the non-zero exit code at line 624 and returned `{}`, never checking the output file at line 630. The rule on disk:
    ```
    ctfd(vo("_isssimsmeapplicablemsmedetails_")=="Yes","1","_minorityindicatorpaymentdetails_")
    ```
    This is a perfectly valid rule that was silently discarded.
  - **Why the CLI crashed is unknowable** — `complex_msme_details_log.txt` has only a header line because stdout is `print()`-ed to terminal (line 620) but never written to the log file. Fix 1.1 is a prerequisite for diagnosing future failures.
- **Scope:** Phase 1 and Phase 2 workers in `inter_panel_dispatcher.py`.
- **Code fix:** Move the `returncode != 0` check (line 624) *after* the output file check (line 630). If the file exists and contains valid JSON, use it regardless of exit code. Only return `None`/`{}` if both the exit code is non-zero AND no output file exists. Same pattern for both Phase 1 (line 408) and Phase 2 (line 624).

### 1.3 Fix `logic_excerpt` key mismatch in normalizer
- **Problem:** The Phase 1 agent outputs `logic_excerpt` but the normalizer only checks `logic_snippet`, `reference_text`, and `logic` — so the snippet is silently dropped. This caused 6 of 25 Basic Details group refs to have empty logic in run 6.
- **Evidence:** All 6 empty-snippet refs are Payment Details destination fields: House Bank (x2), Minority Indicator (x2), Currency, Is Vendor Your Customer. The detection output (`detect_payment_details_output.json`) has the data under `logic_excerpt`, e.g. House Bank: `"logic_excerpt": "Select value-based company code as follows: If company - 1000 - CIT01..."` — but after normalization it becomes `"logic_snippet": ""`.
- **Scope:** `_normalize_single_ref()` in `inter_panel_dispatcher.py`.
- **Goal:** Include `logic_excerpt` in the normalizer's fallback chain so snippets are preserved.

---

## Phase 2: Rule Completeness

These address rules that were detected but not generated.

### 2.1 Add clearing-pair instruction to Phase 2 prompt
- **Problem:** The Phase 2 agent generates derivation rules (`ctfd`) but inconsistently omits paired clearing rules (`cf` + `asdff` + `rffdd`). Run 6 lost the Company Code → House Bank clearing rule this way.
- **Scope:** Expression rule agent prompt (`.claude/agents/mini/expression_rule_agent.md`).
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
| Selects Company Code = "1000" | `=="1000"` → true → sets "CIT01" | `==""` → false → no-op | House Bank filled |
| Changes to "2000" | `=="2000"` → true → sets "HDF01" | `==""` → false → no-op | House Bank updated |
| Clears Company Code | all `==` checks → false → no-op | `==""` → true → clears | House Bank cleared |

The three clearing functions:
- `cf(condition, field)` — clears the field value when condition is true
- `asdff(true, field)` — auto-saves so the cleared value persists
- `rffdd(condition, field)` — resets dropdown UI state

**Run 6 evidence:** The derivation rule exists (Rule 4 on Company Code, 11-entry mapping table) but the clearing counterpart is missing. Same for Process Type → Currency/Bank Country. Intra-panel rules in the same output DO have clearing pairs (e.g., `Select the process type` clears `Process Type` and `Country`), so the agent knows the pattern — it just doesn't consistently apply it to cross-panel derivations.

### 2.2 Populate empty logic snippets from destination field — DOWNGRADED

- **Original concern:** When a ref has an empty `logic_snippet`, the Phase 2 agent lacks context.
- **Finding:** All 7 empty-snippet refs in run 6 have valid `logic_excerpt` in the detection output. Fix 1.3 resolves 100% of them — after 1.3, zero refs would have empty snippets. This fix has nothing to act on.
- **BUD fixes (todo.md) are orthogonal:** The recommended BUD annotations (`(from Basic Details Panel)` etc.) improve Phase 1 detection reliability, not snippet content. They don't affect whether 2.2 is needed.
- **Status:** Deferred. Only revisit if a future run produces genuinely empty snippets (no `logic_excerpt`, no `logic_snippet`, no `reference_text`) after fix 1.3 is applied.

---

## Phase 3: Verification & Observability

These don't fix rules directly but catch future regressions.

### 3.1 Ref-to-rule reconciliation report
- **Problem:** No automated check for whether detected refs resulted in actual rules. Silent losses go unnoticed.
- **Goal:** After Phase 2, compare every Phase 1 ref against generated rules. Log unmatched refs as warnings and write them to `temp/unmatched_refs.json`.

### 3.2 Post-run coverage summary
- **Goal:** Add a summary line like "39 refs detected → 18 rules created → 21 unhandled" with breakdown by classification type (copy_to, derivation, visibility, etc.).

### 3.3 Log failed panels in final summary
- **Goal:** Currently failures are only logged inline during Phase 1. Add a warning block in the final summary listing which panels failed and how many fields were affected.

### 3.4 Per-rule-type stats in final summary
- **Goal:** Break down generated rules by type (visibility, derivation, mandatory, clear_field, etc.) and compare against Phase 1 classification distribution to spot imbalances.

---

## Phase 4: Normalization Hardening

Lower priority — correctness improvements to the normalizer.

### 4.1 Add `"visibility/state"` to classification mapping
- **Problem:** Bank Details returns `"classification": "visibility/state"` which falls through to the catch-all default instead of mapping explicitly.
- **Goal:** Add the variant to the explicit mapping in `_normalize_single_ref()`.

### 4.2 Preserve original classification as metadata
- **Problem:** The normalizer collapses `visibility_state` into `visibility`, losing the distinction between visibility and state rules.
- **Goal:** Keep the original classification as `_original_classification` metadata so the Phase 2 agent has the full context.

---

## Phase 5: Verify Rule Coverage (Run 6 vs Run 5)

After Phases 1–3 are complete, re-run the pipeline and verify the following.

### 5.1 Rules already present in run 6 (verify they survive re-run)

These were initially flagged as "missing vs run 5" but are confirmed present in the run 6 output as Expression (Client) rules. They use a different rule format than run 5 (expression `ctfd` instead of Copy To) but achieve the same functionality.

| # | Rule | Status in Run 6 | Evidence |
|---|------|-----------------|----------|
| 1 | Company Code → Copy To Purchase Org | Present | `ctfd(true, vo("_companycodebasicdetails_"), "_companycodepurchaseorganizationdetails_")` on Company Code field |
| 2 | Company Code → House Bank derivation (1000→CIT01) | Present | Full 11-entry mapping table (`ctfd(vo(...)=="1000", "CIT01", ...)`) on Company Code field |
| 4 | Group Key → Minority Indicator derivation | Present | `ctfd(rgxtst(tolc(vo("_groupkeycorporategroupbasicdetails_")), "/utility\|government\|director/"), "2", "_minorityindicatorpaymentdetails_")` on Group Key field |
| 5 | Process Type → Currency derivation | Present | Combined rule: `ctfd(vo(...)=="India", "INR", "_currencypaymentdetails_")` on Select the process type field |

### 5.2 Rules genuinely missing from run 6 (expect recovery from fixes)

| # | Missing Rule | Root Cause | Fixed By |
|---|-------------|------------|----------|
| 3 | Company Code → House Bank clearing (`cf` + `rffdd`) | Missing clearing pair — derivation exists but no clearing counterpart | 2.1 |
| 6 | Process Type → Currency/Bank Country clearing (`cf` + `rffdd`) | Clearing pair omitted — derivation+disable exists but no clearing | 2.1 |
| 8 | SSI/MSME Applicable → Minority Indicator derivation | MSME Phase 2 CLI failure — valid rule written to disk but discarded (see 1.2) | 1.1, 1.2 |

### 5.3 Rules requiring BUD clarification

| # | Rule | Issue |
|---|------|-------|
| 7 | ID Type → FDA Registration Number | Run 5: visibility rule (`mvi`/`minvi`). Run 6: mandatory rule (`mm`/`mnm`). BUD says "FDA Registration Number: Derived if ID Type is ZCUCIN" — verify whether the intent is visibility or mandatory. |

### 5.4 Garbage refs to investigate

Run 6 detected 49 refs but filtered 7 with empty `field_variableName` (49 → 42). These represent detection agent output format variants the normalizer still cannot parse. After applying Phase 1–4 fixes, check whether the normalizer handles these 7, and if not, identify which panels produced them and what format they used.

**Strategy:** Re-run after Phases 1–3, then diff against run 5 output. Verify 5.1 rules survive, 5.2 rules are recovered, and 5.4 garbage count drops to 0.

---

## Out of Scope (Deferred)

- **Copy-to chain expansion** — Downgraded. Fixing CLI failure handling (1.1, 1.2) is sufficient since Phase 1 agents can detect these refs when they run to completion.
- **Cross-group merging for multi-source derivation chains** — Not needed. Separate visibility and derivation rules on the same field coexist correctly on the Manch platform.
- **Unit test for `_build_normalized_ref()`** — Defensive code that wasn't triggered in run 6. Nice-to-have, not blocking.
- **BUD amendments** (explicit panel annotations on Payment Details fields) — Preferred long-term fix but depends on whether the BUD is client-editable.
- **Source-side BUD annotations** — Currently, all cross-panel derivation logic lives exclusively on the destination field (e.g., House Bank says "based on Company Code: 1000→CIT01..." but Company Code says nothing about House Bank). If the BUD also annotated source fields with their downstream effects (e.g., Company Code: "Copies to Purchase Org. Derives House Bank in Payment Details."), the Phase 1 agent analyzing the source panel would detect refs with full context directly — eliminating the empty-snippet problem at its root and making fix 2.2 permanently unnecessary. Trade-off: maintaining derivation logic in two places (source and destination) creates a consistency risk.
