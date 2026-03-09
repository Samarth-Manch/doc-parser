# Inter-Panel Dispatcher — Detailed Implementation Plan

Based on `plan_v2.md` and `review_v2.md`. Organized into sequential phases with concrete steps, file locations, and acceptance criteria.

---

## Phase 0: Pre-Work (Baseline & Investigation)

Before making any code changes, establish a baseline and investigate root causes raised in the review.

### 0.1 Save Run 6 Output as Baseline Snapshot
- **Action:** Copy the current run 6 output directory to a timestamped baseline.
- **Files:** `output/inter_panel/` → `output/inter_panel_baseline_run6/`
- **Why:** Enables programmatic diffing after fixes (review item: rollback strategy). Phase 4.1 survival checks require this.

### 0.2 Investigate Why Clearing Rules Were Missed in Run 6
- **Action:** Before modifying the prompt (Phase 1.1), determine the root cause. The expression rule agent prompt already has Phase B clearing logic (lines 263-313 of `expression_rule_agent.md`). The review flags three possible causes:
  1. Cross-panel derivation placed on source field in a different panel — Phase B in the destination panel didn't see the parent-child relationship
  2. Agent hit output length limits and truncated Phase B
  3. Agent treated cross-panel `ctfd` differently from intra-panel in dependency scan
- **Investigation steps:**
  - Read the Phase 2 temp output files for the groups that should have produced clearing rules (Company Code group, Process Type group)
  - Check if the derivation rules exist in the Phase 2 output but clearing rules are absent
  - Check the log file for those groups for truncation warnings or output size
  - Check whether the source field's clearing rule was expected from the inter-panel expression agent or the intra-panel expression agent (Stage 5)
- **Files to inspect:**
  - `output/inter_panel/temp/` — per-group Phase 2 output files
  - `output/inter_panel/master.log` — look for truncation or failure messages
- **Outcome:** Document the root cause. This determines whether Phase 1.1 is a prompt fix, a dispatcher fix, or unnecessary.

### 0.3 Reproduce Garbage Refs for Normalization Debugging
- **Action:** Locate the 7 filtered refs from run 6 (the ones with empty `field_variableName`).
- **Steps:**
  1. Search `master.log` for the "Filtered out 7 refs" message to identify which panels produced them
  2. Find the raw Phase 1 agent output in `temp/` for those panels
  3. Extract the 7 problematic refs and save to `temp/garbage_refs_run6.json` for isolated debugging
- **Why:** Avoids needing a full pipeline re-run just to debug normalization (review item 4.4).

---

## Phase 1: Rule Completeness

### 1.1 Fix Clearing-Pair Generation for Cross-Panel Derivations

**Depends on:** Phase 0.2 investigation results.

**If root cause is prompt-related (agent doesn't generate clearing pairs for cross-panel derivations):**

- **File:** `.claude/agents/mini/expression_rule_agent.md`
- **Change:** Add explicit instruction in Phase B (after line ~265) that cross-panel derivation rules (`ctfd` with cross-panel variable names) must also produce clearing counterparts. The current Phase B scans for parent→child relationships, but cross-panel `ctfd` rules placed by the inter-panel dispatcher may not register as parent→child if the destination field isn't in the same FIELDS_JSON.
- **Specific addition to Phase B Step 5:**
  ```
  When scanning rules for parent→child relationships, include ALL Expression (Client)
  rules with `ctfd` in conditionalValues — including cross-panel derivations placed by
  the inter-panel dispatcher. If a rule derives a value into field Y based on field X's
  value, X is a parent of Y regardless of which panel Y belongs to. The clearing rule
  goes on X (the source/trigger field).
  ```
- **Acceptance criteria:**
  - Company Code → House Bank clearing rule (`cf` + `rffdd` on `_companycodebasicdetails_` targeting `_housebankpaymentdetails_`) is generated
  - Process Type → Currency/Bank Country clearing rule is generated

**If root cause is dispatcher-related (Phase 2 output is correct but clearing rules are lost during merge):**

- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Change:** Fix the merge logic to preserve clearing rules from Phase 2 output.

**If root cause is context/truncation:**

- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Change:** Add a max-refs-per-call guard (review item: timeout/token limit). Split large groups into batches of N refs (e.g., 15-20) to prevent prompt truncation.
- **Location:** Around line 970-974, after `group_complex_refs_by_source_field()`, add batch splitting logic.

---

## Phase 2: Verification & Observability

### 2.1 Ref-to-Rule Reconciliation Report
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** After Phase 2 completes (after the group loop ending around line ~1050), before Phase 3.
- **Implementation:**
  1. Build a set of all Phase 1 ref identifiers: `(source_field_var, destination_field_var, classification)` from `all_refs`
  2. Build a set of all generated rule identifiers from `complex_rules`: extract source/destination from rule's `conditionalValues` or `source_fields`
  3. Compute unmatched = Phase 1 refs not covered by any generated rule
  4. Log unmatched as warnings
  5. Write unmatched to `temp/unmatched_refs.json`
- **Format of unmatched_refs.json:**
  ```json
  [
    {
      "source_field": "_companycodebasicdetails_",
      "destination_field": "_housebankpaymentdetails_",
      "classification": "derivation",
      "source_panel": "Basic Details",
      "reason": "No matching rule found in Phase 2 output"
    }
  ]
  ```
- **Scope:** Report is informational for manual investigation (per review clarification — no auto-retry in this phase).
- **Acceptance criteria:** After a pipeline run, `temp/unmatched_refs.json` exists and correctly identifies refs that didn't produce rules.

### 2.2 Post-Run Coverage Summary
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** Final summary block (lines 1192-1221).
- **Change:** Add a reconciliation line to the summary:
  ```python
  Reconciliation:
    Refs detected: {len(all_refs)}
    Rules created: {complex_rule_count + phase4_rule_delta}
    Unmatched refs: {len(unmatched_refs)}
    Coverage: {coverage_pct}%
  ```
- **Acceptance criteria:** Summary includes refs→rules→unmatched breakdown with percentage.

### 2.3 Log Failed Panels in Final Summary
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Implementation:**
  1. Track failed panels during Phase 1 and Phase 2 loops. Add a `failed_panels` list:
     ```python
     failed_panels: List[Dict] = []  # {panel_name, phase, field_count, error}
     ```
  2. When a panel fails in Phase 1 (line ~895) or a group fails in Phase 2, append to `failed_panels`
  3. In the final summary (line ~1192), add a warning block:
     ```
     Failed Panels:
       Phase 1: Panel "MSME Details" (12 fields) — CLI exit code 1
       Phase 2: Group "_companycodebasicdetails_" (3 refs) — empty output
     ```
- **Acceptance criteria:** If any panel/group fails, the final summary explicitly lists them. If none fail, show "No failures".

### 2.4 Per-Rule-Type Stats in Final Summary
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** Final summary block (lines 1192-1221).
- **Implementation:**
  1. After Phase 3 merge (or Phase 4), iterate all cross-panel rules and group by `_expressionRuleType`
  2. Add to summary:
     ```
     Cross-Panel Rules by Type:
       copy_to: 5
       derivation: 3
       visibility: 2
       clear_field: 4
       edv: 2
     ```
  3. Compare against Phase 1 classification distribution (already logged at line 901-907) to spot imbalances
- **Acceptance criteria:** Summary includes rule-type breakdown. If a classification has refs but zero rules, a warning is logged.

---

## Phase 3: Normalization Hardening

### 3.1 Add `"visibility/state"` to Classification Mapping
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** Line 272-273, the classification mapping tuple.
- **Change:** Add `'visibility/state'` to the tuple:
  ```python
  if classification in ('multiple', 'visibility_condition', 'visibility_and_derivation',
                        'visibility_state', 'visibility/state', 'panel_visibility'):
      classification = 'visibility'
  ```
- **Risk:** Minimal — one-line change, and the slash variant already falls to the same default.
- **Acceptance criteria:** `"visibility/state"` maps explicitly to `"visibility"` instead of falling through to the catch-all default.

### 3.2 Preserve Original Classification as Metadata
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** In `_normalize_single_ref()`, after the classification mapping block (after line ~284).
- **Change:** Before overwriting `classification`, save the original:
  ```python
  original_classification = raw_classification
  # ... existing mapping logic ...
  normalized['_original_classification'] = original_classification
  ```
- **Why:** Preserves the distinction between `visibility_state` and `visibility` so the Phase 2 agent has full context for generating the correct rule type (visibility vs. enable/disable).
- **Acceptance criteria:** Normalized refs include `_original_classification` field with the pre-mapping value.

---

## Phase 4: Verification Run & Diff

### 4.0 Pre-Run Checklist
- [ ] Phase 0 baseline saved
- [ ] Phase 1.1 fix applied (based on investigation)
- [ ] Phase 2 observability additions in place
- [ ] Phase 3 normalization fixes applied
- [ ] Dead code `build_simple_copy_to_rules()` removed (optional cleanup, line 511)

### 4.1 Re-Run Pipeline
- **Command:**
  ```bash
  python3 dispatchers/agents/inter_panel_dispatcher.py \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --input output/expression_rules/all_panels_expression_rules.json \
    --output output/inter_panel/all_panels_inter_panel.json
  ```
- **Verify rules survive (from plan 4.1):**
  | Rule | Expected |
  |------|----------|
  | Company Code → Copy To Purchase Org | Present (ctfd + on("change")) |
  | Company Code → House Bank derivation (11 mappings) | Present (ctfd mapping table) |
  | Group Key → Minority Indicator derivation | Present (ctfd + rgxtst) |
  | Process Type → Currency derivation | Present (ctfd) |

### 4.2 Verify Recovered Rules
- **Diff against baseline:**
  ```bash
  python3 -c "
  import json
  old = json.load(open('output/inter_panel_baseline_run6/all_panels_inter_panel.json'))
  new = json.load(open('output/inter_panel/all_panels_inter_panel.json'))
  # Compare rule counts per panel
  for panel in sorted(set(list(old.keys()) + list(new.keys()))):
      old_rules = sum(len(f.get('rules',[])) for f in old.get(panel,[]))
      new_rules = sum(len(f.get('rules',[])) for f in new.get(panel,[]))
      delta = new_rules - old_rules
      if delta != 0:
          print(f'{panel}: {old_rules} -> {new_rules} ({'+' if delta > 0 else ''}{delta})')
  "
  ```
- **Expected recoveries (from plan 4.2):**
  | Rule | Expected After Fix |
  |------|-------------------|
  | Company Code → House Bank clearing (cf + rffdd) | NEW — was missing |
  | Process Type → Currency/Bank Country clearing | NEW — was missing |

### 4.3 Check Reconciliation Report
- **File:** `output/inter_panel/temp/unmatched_refs.json`
- **Expected:** Fewer unmatched refs than run 6. Ideally 0 for non-EDV refs.

### 4.4 Check Garbage Ref Count
- **Search log:** Look for "Filtered out N refs with empty field_variableName"
- **Expected:** N should be lower than 7 (ideally 0) if Phase 3 normalization fixes work.

### 4.5 Manual Verification: ID Type → FDA Registration Number
- **From plan 4.3:** Run 5 has visibility rule (mvi/minvi), Run 6 has mandatory rule (mm/mnm). BUD says "Derived if ID Type is ZCUCIN".
- **Action:** Read the BUD section for FDA Registration Number and determine correct rule type. This may require BUD clarification from the business team — not a code fix.

---

## Phase Summary & Dependencies

```
Phase 0 (Baseline & Investigation)
  ├── 0.1 Save baseline         [no deps]
  ├── 0.2 Investigate root cause [no deps]
  └── 0.3 Reproduce garbage refs [no deps]
       │
Phase 1 (Rule Completeness)
  └── 1.1 Fix clearing pairs     [depends on 0.2]
       │
Phase 2 (Observability)          [no deps on Phase 1 — can parallel]
  ├── 2.1 Reconciliation report
  ├── 2.2 Coverage summary       [depends on 2.1]
  ├── 2.3 Failed panels logging
  └── 2.4 Per-rule-type stats
       │
Phase 3 (Normalization)          [no deps on Phase 1/2 — can parallel]
  ├── 3.1 visibility/state mapping
  └── 3.2 Preserve original classification
       │
Phase 4 (Verification)           [depends on ALL above]
  ├── 4.1 Re-run pipeline
  ├── 4.2 Diff against baseline
  ├── 4.3 Check reconciliation
  ├── 4.4 Check garbage refs
  └── 4.5 Manual BUD verification
```

**Parallelization:** Phases 1, 2, and 3 are independent of each other and can be developed in parallel. Phase 4 requires all prior phases to be complete.

---

## Out of Scope (Deferred)

Carried forward from plan_v2.md — not addressed in this implementation:

- Auto-retry for unmatched refs (2.1 report is informational only)
- Copy-to chain expansion
- Cross-group merging for multi-source derivation chains
- Unit test for `_build_normalized_ref()`
- BUD amendments (source-side annotations)
- Remove dead `build_simple_copy_to_rules()` (line 511) — trivial cleanup, do if convenient
