# Inter-Panel Dispatcher — Detailed Implementation Plan (v2)

Based on `plan_v2.md`, `review_v2.md`, and `implementation_plan.md`. Incorporates review feedback: section markers instead of line numbers, finer-grained reconciliation design, corrected Phase 1.1 scope, batch guard as standalone step, dead code removal, and rollback decision point.

**Changes from v1:**
- All code locations use section markers / function names instead of brittle line numbers
- Phase 1.1: Updated investigation scope — source field IS in context (both panels included via `involved_panel_names`); real issue is Phase B's parent-child detection relying on empty `destination_fields`
- Phase 1.2: Batch size guard moved out of conditional into its own step
- Phase 2.1: Finer-grained reconciliation matching by `(source_field, destination_field)` pairs with expression parsing
- Phase 2.2: Notes that existing summary lines need adjustment (`complex_refs` count is post-filter/post-merge)
- Phase 3.2: Clarified as debug/logging only (no downstream prompt change)
- Phase 3.3: Dead code removal of `build_simple_copy_to_rules()` — moved from "optional" to included
- Phase 4.2: Fixed diff script f-string syntax
- Phase 4.6: Added rollback decision point

---

## Phase 0: Pre-Work (Baseline & Investigation)

Before making any code changes, establish a baseline and investigate root causes raised in the review.

### 0.1 Save Run 6 Output as Baseline Snapshot
- **Action:** Copy the current run 6 output directory to a timestamped baseline.
- **Files:** `output/inter_panel/` -> `output/inter_panel_baseline_run6/`
- **Why:** Enables programmatic diffing after fixes. Phase 4.1 survival checks require this.

### 0.2 Investigate Why Clearing Rules Were Missed in Run 6
- **Action:** Before modifying the prompt (Phase 1.1), determine the root cause. The expression rule agent prompt already has Phase B clearing logic (section `Phase B -- Clearing Rules (Dependency Graph)` in `expression_rule_agent.md`). Three possible causes:
  1. Phase B's parent-child detection relies on `source_fields`/`destination_fields` metadata, but Expression (Client) rules have `destination_fields: []` — destinations are embedded in `conditionalValues` expressions
  2. Agent hit output length limits and truncated Phase B
  3. Agent treated cross-panel `ctfd` differently from intra-panel in dependency scan

- **Clarification from code review:** The concern that "source field is not in context" is **NOT valid**. The dispatcher at `call_complex_rules_agent()` builds `involved_panel_names` from three sources:
  1. Source field's panel (looked up via `var_index`)
  2. Destination field's panel (from each ref's `field_variableName`)
  3. Referenced panel directly (from ref's `referenced_panel`)

  Both source and destination panels are always included in `$FIELDS_JSON`. The real question is whether Phase B can discover parent-child relationships when `destination_fields` is `[]`.

- **Investigation steps:**
  - Read the Phase 2 temp output files for the groups that should have produced clearing rules (Company Code group, Process Type group)
  - Check if derivation rules exist in Phase 2 output but clearing rules are absent
  - If derivation rules exist, check their `destination_fields` — if `[]`, that confirms Phase B couldn't build the parent-child map
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

**If root cause is prompt-related (Phase B can't detect parent-child from expression strings):**

- **File:** `.claude/agents/mini/expression_rule_agent.md`
- **Location:** Section `Phase B -- Clearing Rules (Dependency Graph)`, Step 5 (`Build parent->children map`)
- **Change:** Add explicit instruction that when scanning for parent-child relationships, the agent must also parse `conditionalValues` expression strings — not just check `source_fields`/`destination_fields` metadata. Expression (Client) rules have `destination_fields: []` with real destinations embedded in `ctfd(...)`, `mvi(...)`, etc.
- **Specific addition to Step 5:**
  ```
  When scanning rules for parent->child relationships, do NOT rely solely on
  source_fields/destination_fields metadata. Expression (Client) rules have
  destination_fields: [] — the actual destinations are inside conditionalValues.

  For each Expression (Client) rule, parse the conditionalValues string to find
  all variable names referenced by ctfd(), cf(), mvi(), minvi(), mm(), mnm(),
  asdff(), rffdd(). Any variable name that is NOT the source/trigger field is
  a child. This applies to ALL Expression (Client) rules — including cross-panel
  derivations placed by the inter-panel dispatcher.

  Example: if Company Code has a rule with
    ctfd(vo("_companycodebasicdetails_")=="1000", "CIT01", "_housebankpaymentdetails_")
  then _companycodebasicdetails_ is the parent and _housebankpaymentdetails_ is the child,
  even though destination_fields is [].
  ```
- **Acceptance criteria:**
  - Company Code -> House Bank clearing rule (`cf` + `rffdd` on `_companycodebasicdetails_` targeting `_housebankpaymentdetails_`) is generated
  - Process Type -> Currency/Bank Country clearing rule is generated

**If root cause is dispatcher-related (Phase 2 output is correct but clearing rules are lost during merge):**

- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** `merge_all_rules_into_output()` call and `validate_inter_panel_rules()` — in the `# PHASE 3: Validate + Merge` section
- **Change:** Fix the merge/validation logic to preserve clearing rules from Phase 2 output.

**If root cause is context/truncation:**

- Handled by Phase 1.2 below.

### 1.2 Batch Size Guard for Phase 2 Agent Calls

**Independent of Phase 0.2 results — defensive measure against future regressions.**

- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** In the `# PHASE 2: All Rules via Expression Agent` section, after `group_complex_refs_by_source_field()` returns groups, before the group loop.
- **Change:** Add a max-refs-per-call guard. If a group has more than N refs (e.g., 15-20), split it into batches. Each batch gets its own `call_complex_rules_agent()` call and results are merged.
- **Implementation:**
  ```python
  MAX_REFS_PER_CALL = 20

  for source_field_var, refs_group in groups.items():
      if len(refs_group) > MAX_REFS_PER_CALL:
          batches = [refs_group[i:i+MAX_REFS_PER_CALL]
                     for i in range(0, len(refs_group), MAX_REFS_PER_CALL)]
          log(f"  Phase 2: Splitting '{source_field_var}' into {len(batches)} batches "
              f"({len(refs_group)} refs, max {MAX_REFS_PER_CALL} per call)")
      else:
          batches = [refs_group]

      for batch_idx, batch in enumerate(batches):
          # ... existing call_complex_rules_agent() logic ...
  ```
- **Why:** Output truncation is a known LLM failure mode. Even if truncation isn't the root cause for run 6, this prevents it from becoming a problem as BUDs grow more complex.
- **Acceptance criteria:** Groups with >20 refs are split into batches. All batches' rules are merged correctly.

---

## Phase 2: Verification & Observability

### 2.1 Ref-to-Rule Reconciliation Report (Fine-Grained)

- **File:** `dispatchers/agents/inter_panel_dispatcher.py` (new functions) and `dispatchers/agents/inter_panel_utils.py` (extraction helper)
- **Location:** In `inter_panel_dispatcher.py`, insert after Phase 2 completes (after `complex_rule_count` is calculated, before the `# PHASE 3: Validate + Merge` section marker).

#### 2.1.1 Rule Coverage Extraction

Extract all `(source_field, destination_field)` pairs from generated rules, handling all three rule formats produced by the inter-panel dispatcher:

| Rule Format | How destinations are found |
|---|---|
| Expression (Client) with `conditionValueType: "EXPR"` | `destination_fields` is always `[]`. Parse `conditionalValues` strings for variable names. |
| Copy To Form Field (Client) | `destination_fields` is populated (e.g., `["_companycodepurchaseorganizationdetails_"]`). |
| Make Mandatory / Make Non Mandatory (Client) | `destination_fields` is populated. `conditionalValues` has plain text values, not expressions. |

**Implementation — `extract_rule_coverage()`:**

```python
def extract_rule_coverage(
    complex_rules: Dict[str, List[Dict]],
) -> Set[Tuple[str, str]]:
    """
    Extract (source_field, destination_field) pairs from all generated rules.
    Handles Expression (Client), Copy To, and Make Mandatory rule formats.
    """
    covered = set()

    for panel_name, entries in complex_rules.items():
        for entry in entries:
            placement_field = _norm_var(entry.get('target_field_variableName', ''))

            for rule in entry.get('rules_to_add', []):
                source = placement_field
                if rule.get('source_fields'):
                    source = _norm_var(rule['source_fields'][0])

                # Method 1: destination_fields is populated (Copy To, Make Mandatory)
                for dest in rule.get('destination_fields', []):
                    norm_dest = _norm_var(dest)
                    if norm_dest and norm_dest != source:
                        covered.add((source, norm_dest))

                # Method 2: parse conditionalValues for Expression (Client)
                if rule.get('conditionValueType') == 'EXPR':
                    for expr in rule.get('conditionalValues', []):
                        # Extract ALL _variablename_ patterns from expression string
                        all_vars = set(re.findall(r'"(_[a-z0-9_]+_)"', expr))
                        for var in all_vars:
                            norm = _norm_var(var)
                            if norm and norm != source:
                                covered.add((source, norm))

    return covered
```

**Why `re.findall(r'"(_[a-z0-9_]+_)"', expr)` works:**
- Variable names in expressions always appear as `"_lowercase_underscored_"` strings
- Literal values like `"CIT01"`, `"INR"`, `"Yes"`, `"1000"` never match the `_..._` pattern
- This catches all function arguments: `ctfd(..., "_dest_")`, `mvi(..., "_f1_", "_f2_")`, `cf(..., "_dest_")`, `asdff(..., "_f1_", "_f2_")`, etc.
- Simpler and more robust than function-specific regex (no need to handle variable argument counts)

#### 2.1.2 Reconciliation Logic

```python
def reconcile_refs_to_rules(
    all_refs: List[Dict],
    complex_rules: Dict[str, List[Dict]],
) -> List[Dict]:
    """
    Compare Phase 1 refs against Phase 2 generated rules.
    Returns list of unmatched refs with reasons.
    """
    covered_pairs = extract_rule_coverage(complex_rules)

    unmatched = []
    for ref in all_refs:
        # EDV refs are handled by Phase 4, skip
        if ref.get('classification') == 'edv':
            continue

        source = _norm_var(ref.get('referenced_field_variableName', ''))
        dest = _norm_var(ref.get('field_variableName', ''))

        if not source or not dest:
            unmatched.append({**ref, 'reason': 'Missing source or destination variableName'})
            continue

        if (source, dest) not in covered_pairs:
            unmatched.append({**ref, 'reason': 'No matching rule found in Phase 2 output'})

    return unmatched
```

**Edge case handling:**
- **One rule covers multiple refs:** A single `ctfd` rule on Company Code with 11 mappings targeting `_housebankpaymentdetails_` registers the pair `(companycodebasicdetails, housebankpaymentdetails)` once. If Phase 1 has one derivation ref and one clearing ref for the same pair, the derivation ref matches but the clearing ref only matches if a separate clearing rule was generated — which is the exact signal we want.
- **Double-underscore format:** `source_fields` sometimes uses `__var__` while refs use `_var_`. Both pass through `_norm_var()` which strips to `_var_`, so this is a non-issue.
- **`_norm_var()` behavior:** Strips leading/trailing underscores, then wraps with single underscores: `__varname__ -> _varname_`, `_varname_ -> _varname_`.

#### 2.1.3 Integration Point

Insert in `inter_panel_dispatcher.py` between the `Phase 2b COMPLETE` log line and the `# PHASE 3: Validate + Merge` section marker:

```python
    # ── Ref-to-Rule Reconciliation ──────────────────────────────────────
    unmatched_refs = reconcile_refs_to_rules(all_refs, complex_rules)
    if unmatched_refs:
        log(f"  Reconciliation WARNING: {len(unmatched_refs)}/{len(all_refs)} refs "
            f"did not produce rules:")
        for ref in unmatched_refs:
            log(f"    - {ref.get('referenced_field_variableName')} -> "
                f"{ref.get('field_variableName')} ({ref.get('classification')}) "
                f"-- {ref.get('reason')}")
        unmatched_file = temp_dir / "unmatched_refs.json"
        with open(unmatched_file, 'w') as f:
            json.dump(unmatched_refs, f, indent=2)
        log(f"  Written to: {unmatched_file}")
    else:
        log(f"  Reconciliation: all {len(all_refs)} refs covered by generated rules")
```

- **Scope:** Report is informational for manual investigation (no auto-retry).
- **Acceptance criteria:** After a pipeline run, `temp/unmatched_refs.json` exists and correctly identifies refs that didn't produce rules. Matching uses `(source_field, destination_field)` pairs, not just classification.

### 2.2 Post-Run Coverage Summary
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** Final summary block — the `INTER-PANEL DISPATCHER (v3) COMPLETE` f-string at the end of `main()`.
- **Change:** Add a reconciliation section to the summary:
  ```python
  Reconciliation:
    Refs detected: {len(all_refs)}
    Covered by rules: {len(all_refs) - len(unmatched_refs)}
    Unmatched refs: {len(unmatched_refs)}
    Coverage: {coverage_pct}%
  ```
- **Also fix:** The existing summary line `Total refs processed: {len(complex_refs)}` is misleading because `complex_refs` has been filtered (EDV refs removed) and extended (simple refs merged in) by the time the summary runs. Change to:
  ```python
  Phase 2 -- Expression Rules via Agent (model={args.model}):
    Input refs: {pre_edv_filter + len(simple_refs)} (complex: {pre_edv_filter}, copy_to: {len(simple_refs)})
    EDV-filtered (Phase 4): {edv_filtered}
    Processed: {len(complex_refs)}
    Rules created: {complex_rule_count}
  ```
  This requires saving `pre_edv_filter` count before the EDV filter step (it's already computed but not stored past the filter block).
- **Acceptance criteria:** Summary includes refs-to-rules-to-unmatched breakdown with percentage. Existing Phase 2 counts are accurate.

### 2.3 Log Failed Panels in Final Summary
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Implementation:**
  1. Track failed panels during Phase 1 and Phase 2 loops. Add a `failed_panels` list before the Phase 1 executor block:
     ```python
     failed_panels: List[Dict] = []  # {panel_name, phase, field_count, error}
     ```
  2. When a panel fails in Phase 1 (the `except Exception` block inside the `as_completed` loop) or a group fails in Phase 2 (when `call_complex_rules_agent()` returns `{}`), append to `failed_panels`
  3. In the final summary, add a warning block:
     ```
     Failed Panels:
       Phase 1: Panel "MSME Details" (12 fields) -- CLI exit code 1
       Phase 2: Group "_companycodebasicdetails_" (3 refs) -- empty output
     ```
- **Acceptance criteria:** If any panel/group fails, the final summary explicitly lists them. If none fail, show "No failures".

### 2.4 Per-Rule-Type Stats in Final Summary
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** Final summary block, after the cross-panel rule count loop (the `_inter_panel_source == 'cross-panel'` iteration in the `# PHASE 3` section).
- **Implementation:**
  1. After Phase 3 merge (or Phase 4), iterate all cross-panel rules and group by rule type. For Expression (Client) rules, use `_expressionRuleType`. For other rules, use `rule_name`.
  2. Add to summary:
     ```
     Cross-Panel Rules by Type:
       copy_to: 5
       derivation: 3
       visibility: 2
       clear_field: 4
       mandatory: 2
     ```
  3. Compare against Phase 1 classification distribution (already logged after Phase 1 completes, the `Breakdown:` log line) to spot imbalances. If a classification has refs but zero rules, log a warning.
- **Acceptance criteria:** Summary includes rule-type breakdown. Classification-to-rule-type imbalances are flagged.

---

## Phase 3: Normalization Hardening

### 3.1 Add `"visibility/state"` to Classification Mapping
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** In `_normalize_single_ref()`, the classification mapping block — the `if classification in (...)` tuple that maps to `'visibility'`.
- **Change:** Add `'visibility/state'` to the tuple:
  ```python
  if classification in ('multiple', 'visibility_condition', 'visibility_and_derivation',
                        'visibility_state', 'visibility/state', 'panel_visibility'):
      classification = 'visibility'
  ```
- **Risk:** Minimal — one-line change, and the slash variant already falls to the same default via the `else` branch.
- **Acceptance criteria:** `"visibility/state"` maps explicitly to `"visibility"` instead of falling through to the catch-all default.

### 3.2 Preserve Original Classification as Metadata (Debug Only)
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** In `_normalize_single_ref()`, after the classification mapping block, before the `return` dict.
- **Change:** Save the raw classification before mapping:
  ```python
  original_classification = raw_classification
  # ... existing mapping logic ...
  normalized['_original_classification'] = original_classification
  ```
- **Purpose:** Debug and logging only. Preserves the distinction between `visibility_state` and `visibility` in the ref metadata for investigation. No downstream prompt change is included in this phase — the Phase 2 agent prompt is not modified to consume `_original_classification`.
- **Acceptance criteria:** Normalized refs include `_original_classification` field with the pre-mapping value.

### 3.3 Remove Dead `build_simple_copy_to_rules()` Function
- **File:** `dispatchers/agents/inter_panel_dispatcher.py`
- **Location:** The `# Phase 2a: Simple Copy To Rules (Deterministic)` section — the `build_simple_copy_to_rules()` function definition and its section banner.
- **Change:** Delete the function and section banner entirely. It is confirmed dead code:
  - Never called — simple refs are merged into complex refs at the `# Merge simple refs into complex refs` block
  - `merge_all_rules_into_output()` is always called with `{}` for the `copy_to_rules` parameter
- **Risk:** Zero — function is unreachable. Leaving it is actively misleading (implies copy-to has a deterministic path when it doesn't).
- **Acceptance criteria:** Function and section banner removed. No other code references it.

---

## Phase 4: Verification Run & Diff

### 4.0 Pre-Run Checklist
- [ ] Phase 0 baseline saved
- [ ] Phase 1.1 fix applied (based on investigation)
- [ ] Phase 1.2 batch guard in place
- [ ] Phase 2 observability additions in place (2.1-2.4)
- [ ] Phase 3 normalization fixes applied (3.1-3.3)

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
  | Company Code -> Copy To Purchase Org | Present (ctfd + on("change")) |
  | Company Code -> House Bank derivation (11 mappings) | Present (ctfd mapping table) |
  | Group Key -> Minority Indicator derivation | Present (ctfd + rgxtst) |
  | Process Type -> Currency derivation | Present (ctfd) |

### 4.2 Verify Recovered Rules
- **Diff against baseline:**
  ```bash
  python3 -c "
  import json
  old = json.load(open('output/inter_panel_baseline_run6/all_panels_inter_panel.json'))
  new = json.load(open('output/inter_panel/all_panels_inter_panel.json'))
  for panel in sorted(set(list(old.keys()) + list(new.keys()))):
      old_rules = sum(len(f.get('rules',[])) for f in old.get(panel,[]))
      new_rules = sum(len(f.get('rules',[])) for f in new.get(panel,[]))
      delta = new_rules - old_rules
      if delta != 0:
          sign = '+' if delta > 0 else ''
          print(f'{panel}: {old_rules} -> {new_rules} ({sign}{delta})')
  "
  ```
- **Expected recoveries (from plan 4.2):**
  | Rule | Expected After Fix |
  |------|-------------------|
  | Company Code -> House Bank clearing (cf + rffdd) | NEW -- was missing |
  | Process Type -> Currency/Bank Country clearing | NEW -- was missing |

### 4.3 Check Reconciliation Report
- **File:** `output/inter_panel/temp/unmatched_refs.json`
- **Expected:** Fewer unmatched refs than run 6. Ideally 0 for non-EDV refs.
- **Verify:** Each unmatched ref has a valid `(source, destination)` pair and a meaningful `reason`.

### 4.4 Check Garbage Ref Count
- **Search log:** Look for "Filtered out N refs with empty field_variableName"
- **Expected:** N should be lower than 7 (ideally 0) if Phase 3 normalization fixes work.

### 4.5 Manual Verification: ID Type -> FDA Registration Number
- **From plan 4.3:** Run 5 has visibility rule (mvi/minvi), Run 6 has mandatory rule (mm/mnm). BUD says "Derived if ID Type is ZCUCIN".
- **Action:** Read the BUD section for FDA Registration Number and determine correct rule type. This may require BUD clarification from the business team -- not a code fix.

### 4.6 Rollback Decision Point
- **After Phase 4.2 diff:** If any rules that were present in run 6 baseline are **missing** in the new output (regression), do NOT proceed.
- **Action:**
  1. Identify which Phase 1/2/3 change caused the regression
  2. Revert that specific change
  3. Re-run and re-diff
- **Only proceed to commit** when: all run 6 rules survive AND new rules (clearing pairs) are present.

---

## Phase Summary & Dependencies

```
Phase 0 (Baseline & Investigation)
  |-- 0.1 Save baseline              [no deps]
  |-- 0.2 Investigate root cause     [no deps]
  +-- 0.3 Reproduce garbage refs     [no deps]
       |
Phase 1 (Rule Completeness)
  |-- 1.1 Fix clearing pairs         [depends on 0.2]
  +-- 1.2 Batch size guard           [no deps -- can parallel with 1.1]
       |
Phase 2 (Observability)             [no deps on Phase 1 -- can parallel]
  |-- 2.1 Reconciliation report      [no deps]
  |     |-- extract_rule_coverage()
  |     |-- reconcile_refs_to_rules()
  |     +-- integration in dispatcher
  |-- 2.2 Coverage summary           [depends on 2.1]
  |-- 2.3 Failed panels logging      [no deps]
  +-- 2.4 Per-rule-type stats        [no deps]
       |
Phase 3 (Normalization)             [no deps on Phase 1/2 -- can parallel]
  |-- 3.1 visibility/state mapping
  |-- 3.2 Preserve original classification (debug only)
  +-- 3.3 Remove dead build_simple_copy_to_rules()
       |
Phase 4 (Verification)              [depends on ALL above]
  |-- 4.1 Re-run pipeline
  |-- 4.2 Diff against baseline
  |-- 4.3 Check reconciliation
  |-- 4.4 Check garbage refs
  |-- 4.5 Manual BUD verification
  +-- 4.6 Rollback decision point
```

**Parallelization:** Phases 1, 2, and 3 are independent of each other and can be developed in parallel. Phase 4 requires all prior phases to be complete.

---

## Out of Scope (Deferred)

Carried forward from plan_v2.md -- not addressed in this implementation:

- Auto-retry for unmatched refs (2.1 report is informational only)
- Copy-to chain expansion
- Cross-group merging for multi-source derivation chains
- Unit test for `_build_normalized_ref()`
- BUD amendments (source-side annotations)
- Updating Phase 2 agent prompt to consume `_original_classification` (3.2 is debug-only for now)
