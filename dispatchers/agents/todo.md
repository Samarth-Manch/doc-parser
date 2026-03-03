# Inter-Panel Dispatcher — Post-Fix TODO

Observations and action items from the third-person review of the normalizer fix (run 6).

---

## Major

### Failure Handling (mislabeled as "Timeout")

  **Key finding:** There are no Python-level timeouts in the dispatcher. Neither the Phase 1 `subprocess.run` (line 395) nor the Phase 2 `subprocess.Popen` (line 604) have a `timeout` parameter. The only `timeout=30` (line 90) is on a quick usage check, not on agent calls. The `claude` CLI has no `--timeout` or `--max-turns` flag either.

  What was called "timeouts" are actually the `claude` CLI exiting with a non-zero return code (exit code 1) for unknown reasons — API error, context limit, rate limit, or internal error. The dispatcher logs `FAILED (exit code N)` but **never captures why** it failed.

  **Claude Code hooks cannot help here** — hooks fire on tool calls *within* a Claude Code session. The dispatchers run `claude` as external subprocesses, which are entirely separate processes invisible to hooks.

- [ ] **Capture and log `claude` CLI failure output**
  - Phase 1 (`subprocess.run` line 395): uses `capture_output=True` but on failure (line 408–411) only logs the exit code — never logs `process.stdout` or `process.stderr`
  - Phase 2 (`subprocess.Popen` line 604): pipes stdout to `print()` (line 620) which goes to the terminal and is lost after the run. The per-group log file (e.g., `complex_msme_details_log.txt`) only has a header line — none of the CLI output is written to it
  - **Fix:** On non-zero exit code, write the captured stdout/stderr to the log file and to the master log. This gives visibility into *why* the CLI failed (API error, rate limit, context overflow, etc.)
  - File: `inter_panel_dispatcher.py` — Phase 1 worker (line 408) and Phase 2 worker (line 624)

- [ ] **Check for output file regardless of exit code**
  - Phase 1 (line 408): if `returncode != 0`, immediately returns `None` without checking if the output file exists on disk
  - Run 6 example: Vendor Duplicity Details — the `claude` process exited non-zero but had already written 7 valid refs to `detect_vendor_duplicity_details_output.json` before failing. The dispatcher discarded them.
  - **Fix:** Move the `returncode != 0` check *after* the output file check. If the file exists and contains valid JSON, use it regardless of exit code. Only return `None` if both the exit code is non-zero AND no output file exists.
  - Same pattern applies to Phase 2 (line 624–627)
  - File: `inter_panel_dispatcher.py` — reorder logic in both Phase 1 and Phase 2 workers

### v2 → v3 Architecture Rule Loss Prevention

- [ ] **Add ref-to-rule reconciliation report (Phase 2 → Phase 3)**
  - After Phase 2 completes, compare every Phase 1 ref against generated rules
  - For each ref, check: does at least one rule exist on the destination field whose `source_fields` includes the referenced variableName?
  - Log unmatched refs as warnings: `"UNMATCHED REF: _streetaddressdetails_ -> PAN and GST Details:Building Number [derivation] — no rule found"`
  - Write unmatched refs to `temp/unmatched_refs.json` for debugging
  - This catches silent losses regardless of cause (timeout, agent omission, grouping gaps)

- [ ] ~~**Expand copy_to refs into derivation chains before Phase 2**~~ **DOWNGRADED — fixing timeouts is sufficient**

  **Original concern:** If a panel's Phase 1 detection times out, downstream derivation refs living in that panel are silently lost. The proposed fix was a deterministic text-scan "chain expansion" step to discover these refs independently of Phase 1.

  **What actually happened in run 6:**

  Payment Details did NOT time out (finished in 1m 8s). Phase 1 successfully detected all 8 refs from Payment Details, including House Bank → Company Code (derivation). The chain expansion enhancement is **not needed** as long as timeouts are fixed — the per-panel detection agents are capable of finding these refs when they have enough time.

  **However, run 6 still has a separate problem — Phase 2 agent omission:**

  Even though the House Bank derivation ref was correctly detected and passed to Phase 2, the agent generated the derivation rule but **did not generate the paired clearing rule**. Compare:

  | Rule | Run 5 (v2) | Run 6 (v3) |
  |------|-----------|-----------|
  | Company Code → House Bank derivation (`ctfd` mapping) | Yes | Yes |
  | Company Code → House Bank clearing (`cf` + `rffdd`) | **Yes** | **No** |
  | Process type → House Bank visibility (`mvi`/`minvi`) | Yes | Yes |

  The clearing rule from v2:
  ```
  on("change") and (cf(vo("_companycodebasicdetails_")=="","_housebankpaymentdetails_");
  asdff(true,"_housebankpaymentdetails_");
  rffdd(vo("_companycodebasicdetails_")=="","_housebankpaymentdetails_"))
  ```
  This was never generated in v3 run 6 — the refs were detected, the derivation was produced, but the clearing counterpart was omitted.

  **Root cause:** The Phase 2 agent doesn't consistently pair derivation rules with their clearing counterparts. This is an agent prompt issue, not a detection or timeout issue.

  **Fix (two parts):**
  1. **Fix timeouts** (see timeout items above) — ensures refs are always detected. This alone addresses the original concern about lost refs.
  2. **Update Phase 2 prompt** to explicitly instruct: "For every cross-panel derivation rule (`ctfd`), also generate a clearing rule (`cf` + `rffdd`) that clears the destination field when the source field is emptied or changed." This addresses the agent omission.

  File: `.claude/agents/mini/expression_rule_agent.md` — add clearing-pair instruction to the inter-panel expression rules section

- [ ] **Inject destination field logic into Phase 2 ref records**
  - v2's global call had all 158 fields with logic in context; v3's per-group call only has involved panel fields
  - The Phase 2 agent can miss derivation chains when the ref record has an empty `logic_snippet` but the destination field's `logic` has the actual rule
  - Run 6: 6 of the 19 Basic Details group refs had empty `logic_snippet` (Payment Details fields)
  - Enhancement: before Phase 2, populate each ref's `logic_snippet` from the destination field's `logic` if the ref's snippet is empty
  - This gives the Phase 2 agent the same context v2 had without sending all 158 fields

  **Root cause found — most empty snippets are a key name mismatch bug, not missing data:**

  The Phase 1 detection agent outputs `logic_excerpt` as the key name, but the normalizer (`_normalize_single_ref` line 289) only checks `logic_snippet`, `reference_text`, and `logic` — it never checks `logic_excerpt`. So the snippet is present in the detection output but silently dropped during normalization.

  Evidence from run 6:
  ```
  detect_payment_details_output.json:
    House Bank → Company Code:  "logic_excerpt": "Select value-based company code as follows: If company - 1000 - CIT01..."

  complex_basic_details_refs.json (after normalization):
    House Bank → Company Code:  "logic_snippet": ""
  ```

  **Fix (one-line):** Add `logic_excerpt` to the fallback chain on line 289 of `inter_panel_dispatcher.py`:
  ```python
  # Before:
  'logic_snippet': ref.get('logic_snippet', ref.get('reference_text', ref.get('logic', ''))),
  # After:
  'logic_snippet': ref.get('logic_snippet', ref.get('logic_excerpt', ref.get('reference_text', ref.get('logic', '')))),
  ```

  This fixes the immediate bug. The "populate from destination field logic" enhancement above is still valuable as a fallback for cases where the detection agent genuinely produces no snippet, but fixing the key mismatch will resolve the majority of empty snippets seen in run 6.

  File: `inter_panel_dispatcher.py` — `_normalize_single_ref()` line 289

- [ ] **Cross-validate source-panel groups for multi-source derivation chains**
  - v3 groups refs by source panel, but some fields depend on TWO different source panels — their refs get split across separate Phase 2 agent calls that don't see each other's context
  - Real example from run 6 — **Title** (Vendor Basic Details) has two refs:
    - `Title → PAN:PAN [derivation]` — grouped under **PAN and GST Details** group (19 refs)
    - `Title → Basic Details:Vendor Domestic or Import [visibility]` — grouped under **Basic Details** group (19 refs)
    - Title's full logic: "Derived from PAN 4th char (C=Company, T=Trust, F=Firm)... applicable only for India-Domestic (from Basic Details)"
    - The PAN group agent sees the derivation but not the India-Domestic visibility condition
    - The Basic Details group agent sees the visibility condition but not the PAN derivation
    - Neither agent has the full picture to produce one correct combined rule
  - **Resolution: No change needed.** Separate rules work correctly. Visibility and derivation are independent rule types on the Manch platform — they stack on the same field and fire independently. The PAN group agent produces a derivation rule (`ctfd`), the Basic Details group agent produces a visibility rule (`cf`), and both rules coexist on the Title field. The visibility rule hides the field when not India-Domestic, making the derivation result irrelevant when hidden. No group merging or cross-reference injection required.

---

## BUD Updates Required

The following fields have ambiguous cross-panel references in their logic — they mention field names without specifying which panel they come from. Adding explicit `(from <Panel Name> Panel)` annotations (the same pattern the BUD already uses for fields like Currency and Is Vendor Your Customer) would make Phase 1 detection reliable and eliminate the need for the chain expansion enhancement above.

### Payment Details Panel

- [ ] **House Bank**
  - Current: `"Select value-based company code as follows: If company - 1000 - CIT01..."`
  - Update to: `"Select value based on Company Code **(from Basic Details Panel)** as follows: If company - 1000 - CIT01..."`
  - Impact: Phase 1 agent would detect House Bank → Company Code (Basic Details) as a derivation ref

- [ ] **Minority Indicator**
  - Current: `"1. IF SSI indicator is 1 or 2 then default value should be 1 • 2. IF Vendor Group Key is utility or Government vendor or director's vendor then default value 2, else default value is 5"`
  - Update to: `"1. IF SSI indicator **(from MSME Details Panel)** is 1 or 2 then default value should be 1 • 2. IF Group key/Corporate Group **(from Basic Details Panel)** is utility or Government vendor or director's vendor then default value 2, else default value is 5"`
  - Impact: Phase 1 agent would detect two derivation refs — one to MSME Details, one to Basic Details

- [ ] **Payment Methods**
  - Current: `"If bank verified then N, else C"`
  - Update to: `"If bank verified **(from Bank Details Panel)** then N, else C"`
  - Impact: Phase 1 agent would detect Payment Methods → Bank Details as a derivation ref

### Why This Matters

These 3 BUD updates are the **preferred fix** over the chain expansion enhancement. With explicit panel references:
- Phase 1 detection becomes deterministic — no ambiguity for the LLM to misinterpret
- Timeout fix alone would be sufficient to catch all rules (no need for synthetic ref generation)
- Consistent with the pattern already used elsewhere in the BUD (Currency, Is Vendor Your Customer, Address Details fields)

If BUD updates are not feasible (e.g., BUD is client-owned and cannot be modified), then the chain expansion enhancement in the Major section above serves as the fallback.

---

## Medium

### Normalization Improvements

- [ ] **Add `"visibility/state"` to explicit classification mapping**
  - Bank Details returns `"classification": "visibility/state"` which falls through to catch-all default
  - Add to the explicit mapping in `_normalize_single_ref()` alongside `visibility_state`, `visibility_condition`, etc.

- [ ] **`visibility_state` → `visibility` is lossy normalization**
  - Detection agent distinguishes visibility_state from derivation, but normalizer collapses both under `visibility`
  - Consider preserving original classification as `_original_classification` metadata for Phase 2 agent context

### Coverage Reporting

- [ ] **Add post-run coverage check**
  - Compare detected refs vs generated rules to flag gaps
  - Log something like: "39 refs detected, 18 rules created — 21 refs unhandled" with breakdown by classification
  - Helps catch silent rule loss in future runs

- [ ] **Log timed-out panels in final summary**
  - Currently only logged inline during Phase 1; add a warning line in the final summary block listing which panels timed out and how many fields they had

- [ ] **Emit per-rule-type stats in final summary**
  - Break down the 18 rules by `_expressionRuleType`: visibility, derivation, mandatory, clear_field, error, etc.
  - Compare against Phase 1 classification distribution (copy_to: 1, derivation: 14, visibility: 24) to spot imbalances
  - Example: 24 visibility refs but only N visibility rules → flag for investigation

### Specific Rule Losses to Investigate

The following 7 rules were present in run 5 (v2) but missing from run 6 (v3). Each needs a root cause and a fix:

- [ ] **Company Code → Copy To Purchase Org**
  - Ref detected as `copy_to` and converted to `ctfd`, but Phase 2 agent treated it as a simple copy without generating the rule
  - Root cause: agent may need explicit `copy_to` handling instructions in the Phase 2 prompt

- [ ] **Company Code → House Bank derivation (1000→CIT01 mapping)**
  - Lost because the derivation chain starts at Company Code but the mapping logic lives in House Bank's field logic
  - Root cause: copy_to ref doesn't carry downstream derivation context (see Major item above)

- [ ] **Company Code → House Bank clearing**
  - Clearing rule paired with the derivation above — lost for the same reason

- [ ] **Group Key/Corporate Group → Minority Indicator derivation**
  - Group Key ref was not detected in run 6 Phase 1 — likely because Payment Details timed out and no other panel detected this ref
  - Root cause: timeout (see Major timeout items)

- [ ] **Select the process type → Currency derivation**
  - Partially subsumed by `Process Type → Bank Country/Currency derivation` rule in run 6, but the explicit currency-only derivation was lost
  - Root cause: agent consolidated into a broader rule — verify the consolidated rule covers all currency cases

- [ ] **Select the process type → Currency/Bank Country clearing**
  - Clearing counterpart to the derivation above — not generated in run 6
  - Root cause: agent omitted clearing when it consolidated the derivation rule

- [ ] **ID Type → FDA visibility (replaced by mandatory in run 6)**
  - Run 5: visibility rule. Run 6: mandatory rule. These are different behaviors
  - Root cause: classification changed from `visibility` to `mandatory` — verify which is correct per BUD logic

---

## Minor

- [ ] **`_build_normalized_ref()` helper is untested in run 6**
  - Handles array-format detection output, but no panel produced that format in this run
  - Not harmful (defensive code), but consider adding a unit test to verify it works
