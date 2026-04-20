# Issue 6: Inter-Panel Agent — Run-to-Run Variance From Detection Schema Drift + Phase 2 Non-Determinism

## Status

- **Issue A (detection schema drift): FIXED (2026-04-20).** Shape enforcement moved from probabilistic prompt guidance to the CLI boundary via `--json-schema`. Agent prompt slimmed from 262 → 139 lines with all forbidden-key prose removed. Four consecutive Pidilite runs produced 15/15 shape-valid panels each (60/60 total), zero drift. Phase 1 now emits `Phase 1 SCHEMA: N/N panels returned shape-valid output` for observability. See `plan_issue_1.md`, `fix_issue_1.md`, and `acceptance.md`.
- **Issue B (Phase 2 non-determinism): OPEN.**
- **Issue C (classification drift): OPEN.**

## BUD Document
`documents/Vendor update BUD - Pidilite v4.docx`

## Run Locations Compared
- `output/vendor_update/runs/3/inter_panel/`    (Run 1 — latest)
- `output/vendor_update/runs/3/inter_panel_2/`  (Run 2 — oldest)
- `output/vendor_update/runs/3/inter_panel_3/`  (Run 3)
- `output/vendor_update/runs/3/inter_panel_4/`  (Run 4 — newer)

## Symptom

Same BUD, four runs, wildly different inter-panel rule counts in `all_panels_inter_panel.json`:

| Run | Total rules | Inter-panel rules |
|-----|--:|--:|
| 1 | 195 | 65 |
| 2 | 150 | **22** |
| 3 | 204 | 75 |
| 4 | 205 | 75 |

3× spread on identical input. Run 2 in particular ships forms missing most cross-panel logic.

## What Is Actually Failing

There are **three live issues** (A, B, C). Two earlier hypotheses turned out to be wrong — see "Not the issue" below.

### Issue A: Detection agent ignores its output schema

`.claude/agents/mini/inter_panel_detect_refs.md` specifies a strict 9-key flat schema with explicit `MUST` language and a `WRONG — DO NOT EMIT THIS SHAPE` example. The agent emits the forbidden shape anyway:

| Run | Raw output schemas observed in `temp/detect_*_output.json` |
|-----|---|
| 1 | mostly `flat(field_variableName)` (canonical) + 4 other shapes |
| 2 | **every panel uses `nested(source_field/target_field/reference_details)` — the exact "WRONG" example from the prompt** |
| 3 | mixed flat + nested + 3 other shapes |
| 4 | 9 distinct shapes across panels |

Reproducible:
```
$ python3 -c "
import json
for run in ['inter_panel','inter_panel_2','inter_panel_3','inter_panel_4']:
    f = f'output/vendor_update/runs/3/{run}/temp/detect_address_details_update_output.json'
    raw = json.load(open(f))['cross_panel_references'][0]
    print(run, '→', 'nested' if 'source_field' in raw else 'flat')
"
inter_panel    → flat
inter_panel_2  → nested
inter_panel_3  → flat
inter_panel_4  → flat
```

The dispatcher's `normalize_detection_output` (`dispatchers/agents/inter_panel_dispatcher.py:143-446`) rescues most variants. Replaying today's normalizer on all four runs successfully extracts 80–90 refs each. So Phase 1 *data* mostly survives — but:

- Each variant takes a different code path through the normalizer, so subtle bugs only fire for some shapes.
- There is no contract. A new variant will be silently misnormalized and never raise an alarm.
- Lines 372 and 480 default unrecognized classifications to `'visibility'`. Wrong but plausible visibility rules silently change form behavior.

### Issue C: Phase 1 classification is ~25% inconsistent across runs

The detection agent assigns one of 6 classifications per ref: `copy_to`, `visibility`, `derivation`, `edv`, `validate_edv`, `clearing`. These determine downstream routing — `copy_to`/`visibility`/`derivation`/`clearing` go to Phase 2 (expression rule agent), `edv` goes to Phase 4a (EDV Dropdown agent), `validate_edv` goes to Phase 4b/4c (Validate EDV agent + cross-panel patching). **A wrong classification routes the ref to the wrong agent → wrong rule type → no rule at all in many cases.**

Measured across the 4 runs:

| Total ref pairs seen in 2+ runs | Same classification across runs | Different classification |
|--:|--:|--:|
| 88 | 66 (75%) | **22 (25%)** |

Errors cluster on two ambiguous boundaries:

**1. `derivation` vs `validate_edv`** (most common error)

Logic: *"Derived this field value as attribute 2 of VC_PURCHASE_DETAILS Staging based on Vendor code"*

| Field | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| `_existingpurchaseorganization…_` | derivation | validate_edv | validate_edv | validate_edv |
| `_existingordercurrency…_` | derivation | validate_edv | validate_edv | validate_edv |
| `_existingtermsofpayment…_` | derivation | validate_edv | validate_edv | validate_edv |
| `_existingincoterms…_` | derivation | validate_edv | validate_edv | validate_edv |

Correct = `validate_edv` (logic literally says "VC_PURCHASE_DETAILS attribute N"). Run 1 mislabeled all as `derivation`. The field-logic-based reclassifier at `inter_panel_dispatcher.py:1262-1280` failed to catch it because the agent emitted an empty `logic_snippet` for those refs in Run 1, so the reclassifier only had the field's own logic to work with — and that field's logic is also short.

**2. `edv` vs `validate_edv`**

Logic: *"Derived this field value as attribute 12 of VC_EMAIL_DETAILS based on Vendor Code"* (a TEXT field, not a dropdown)

| Field | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| `_existingemailemailidupdate_` | edv | validate_edv | edv | validate_edv |

Correct = `validate_edv` (text field, auto-fetched). `edv` is for dropdown options. Agent flips a coin run-to-run.

**3. Outright wrong calls (rare but unambiguous)**

| Field | Logic | Run 4 says |
|---|---|---|
| `_mobilenumbermobilenumberupdate_` | "**Copy** the Mobile Number from Basic Details" | `visibility` |
| `_countryaddressdetailsupdate_` (Run 2) | "...field value Domestic..." | `derivation` |

The "Copy" → `visibility` flip is unambiguously wrong. The Run 2 `derivation` calls drift because Run 2's nested schema puts the actual condition in `raw_expression` while `logic_snippet` only carries `matched_text` (just the field reference, no condition) — so the agent classified on a stripped-down snippet.

**Why this happens**

1. Agent classifies on empty/partial snippets. When `logic_snippet` is empty (common in Runs 1 & 4), the agent has no text to disambiguate `derivation` from `validate_edv`.
2. Reclassifier in dispatcher is too narrow. `inter_panel_dispatcher.py:1262-1280` only fires when classification == `'derivation'`. Misses the `edv` ↔ `validate_edv` confusion entirely. Misses `visibility` mislabeled as something else.
3. Routing consequences. A `validate_edv` mislabeled as `derivation` goes to Phase 2 (expression rule) instead of Phase 4b (Validate EDV) → no auto-fetch rule gets created at all.

This is a meaningful chunk of the run-to-run variance, separate from the schema-drift and Phase-2-non-determinism issues.

### Issue B: Expression-rule agent (Phase 2) is non-deterministic at 3× scale

For very similar Phase 2 inputs, the agent returns wildly different rule counts:

| Run | Refs into Phase 2 | Rules out of Phase 2 |
|-----|--:|--:|
| 1 | 68 | 1213 |
| 3 | 57 | 882 |
| 4 | 71 | 685 |
| 2 | 18* | 433 |

*Run 2's tiny 18 is itself stale-version artifact — see "Not the issue" below.

After validation/dedup, this collapses to 65 / 75 / 75 final inter-panel rules — better, but the underlying instability is what makes runs feel broken. Two refs in Run 3 (`choose_the_group_of_company`, `vendor_code`) actually got input but produced no `_rules.json` — agent ran, returned empty, dispatcher logged `'empty output'` and moved on without retrying.

## Not The Issue (Hypotheses Ruled Out)

### Phase 2 does NOT silently drop entire groups
Earlier I claimed Run 2 submitted 47 groups → only 12 returned output. Wrong. `complex_*_refs.json` is written *before* the agent runs (`inter_panel_dispatcher.py:746-753`), so input-file count = number of Phase 2 calls actually made. Counts match exactly:

| Run | refs_files | panels_files | rules_files | log_files | stream_files |
|-----|--:|--:|--:|--:|--:|
| 1 | 41 | 41 | 41 | 41 | 41 |
| 2 | 12 | 12 | 12 | 12 | 12 |
| 3 | 37 | 37 | 35 | 37 | 37 |
| 4 | 39 | 39 | 39 | 39 | 39 |

Only Run 3 has real Phase-2 drops, and it's 2 refs total. Noise.

### Run 2's tiny output is mostly a stale-version artifact
Run 2 only made 12 Phase 2 calls. Replaying today's dispatcher on Run 2's saved `temp/detect_*_output.json` files yields 47 groups. So Run 2 was almost certainly executed against an older dispatcher version with more aggressive EDV reclassification (pushing ~75 refs into Phase 4 instead of Phase 2). Re-running Run 2 today would not reproduce the 22-rule output.

## Decision: Collapse classifications from 6 → 3

To eliminate most of the Issue C inconsistencies and tighten the contract with downstream agents, replace the current 6 classifications with **3 classifications that map 1:1 onto the downstream agents**:

| Old (6) | → | New (3) | Downstream agent |
|---|---|---|---|
| `copy_to` | → | **`expression`** | Expression Rule agent (Phase 2) |
| `visibility` | → | **`expression`** | Expression Rule agent (Phase 2) |
| `derivation` | → | **`expression`** | Expression Rule agent (Phase 2) |
| `clearing` | → | **`expression`** | Expression Rule agent (Phase 2) |
| `edv` | → | **`edv`** | EDV Dropdown agent (Phase 4a) |
| `validate_edv` | → | **`validate_edv`** | Validate EDV agent (Phase 4b/4c) |

**Impact on Issue C inconsistencies:**
- 15 of 22 measured inconsistencies are within-expression confusions (`copy_to` ↔ `visibility`, `derivation` ↔ `visibility`). They collapse to the same class and disappear.
- 7 remain — the genuine `edv` ↔ `validate_edv` boundary, which actually matters for routing.
- Classification accuracy jumps from ~75% → ~92% with no prompt-quality work.

**What stays the same:**
- Phase 2 (expression rule agent) still decides within `expression` whether to build `ctfd("visible_if(...)")`, a copy rule, a derivation rule, or a clearing rule. That decision moves from Phase 1 to Phase 2 where the full logic text is in scope anyway.

**Schema change:**
- Drop the `type: simple|complex` field — it's redundant once `copy_to` is folded into `expression`.
- Per-ref schema goes from 9 keys to 8: `field_variableName, field_name, referenced_panel, referenced_field_variableName, referenced_field_name, classification, logic_snippet, description`.

**Dispatcher changes:**
- `inter_panel_dispatcher.py:1336` filter becomes `classification == 'expression'` instead of `not in ('edv', 'validate_edv')` — same semantics, cleaner intent.
- `simple_refs` / `complex_refs` split at `:1198-1206` collapses to a single `expression_refs` list.
- The deterministic reclassifier at `:1262-1280` still handles the only remaining ambiguous boundary (`expression` → `validate_edv` when field logic mentions `vc_*` + `attribute`).

**New agent prompt drafted at:** `.claude/agents/mini/inter_panel_detect_refs.proposed.md` (see below for swap procedure).

## Fix Plan

### Tier 1 — Stop the bleeding (small, deterministic)

1. **Make Phase 1 enforce its schema.** Switch the detect agent to JSON-mode / structured-output with the 9-key schema, OR post-validate with `jsonschema` and re-prompt up to 2× with the actual error message when validation fails. Today there's zero validation — the dispatcher just normalizes whatever comes back.

2. **Fail loudly on schema drift.** In `normalize_detection_output`, count refs by raw schema shape per panel. If >0 refs use a non-canonical shape, write `temp/phase1_drift.json` with raw + normalized side-by-side so future drift is visible without spelunking.

3. **Replace classification fallback `else: 'visibility'`** at `:372` and `:480` with `else: log + drop` (or assign `'unknown'` and exclude from Phase 2). A wrong visibility rule is worse than a missing one.

4. **Retry on Phase 2 empty output.** At `:1444-1454`, when `group_rules` is empty, call `call_complex_rules_agent` once more before recording failure. Costs nothing on success, recovers the Run-3-style drops.

5. **Broaden the deterministic reclassifier.** `inter_panel_dispatcher.py:1262-1280` only checks `classification == 'derivation'`. Extend to also reclassify `edv` → `validate_edv` when the destination field is NOT a dropdown type (TEXT, NUMBER, DATE, etc.) but the logic mentions `attribute N`. And reclassify any classification (including `visibility`) → `validate_edv` when both the field's logic AND the logic_snippet contain `vc_*` + `attribute`. This catches the 22 inconsistencies measured in Issue C.

### Tier 2 — Make variance debuggable

5. **Per-stage ref counters in master log:** raw → normalized → field_var-filtered → EDV-filtered → deduplicated → grouped → submitted to Phase 2 → returned → validated → deduped → merged. Today you see "80 detected" and "65 final" with no breakdown.

6. **Always persist `unmatched_refs.json`** (today only when non-empty, `:1515`). Include per-rule reason for *every* validation/dedup drop, not just reconciliation misses.

7. **Fix misleading group label.** `group_label = f"{source_field_name} ({source_field_var})"` at `:1424` uses `batch[0].field_name` which is the *destination* field name, not the source. Use `var_index[source_field_var]`'s actual field name.

### Tier 3 — Phase 2 stays an LLM call; tighten its orchestration instead

**Decision:** Phase 2 (expression rule generation) **remains a Claude call**. A deterministic Python builder for visibility / copy / clearing was considered and rejected: BUD logic is human-written, irregular, and contains too many edge cases (mixed visibility-and-derivation, conditional triggers, inferred field links) for a templated builder to handle reliably. The cost of a deterministic builder missing edge cases is silently-wrong rules; the cost of LLM variance is recoverable with retries.

Levers to use instead, attacking variance through orchestration not replacement:

8. **Wire reconciliation into a targeted retry.** `reconcile_refs_to_rules` (`inter_panel_dispatcher.py:682-710`) already computes which refs Phase 2 failed to cover. Today it only logs them. Make it drive a retry: for any group whose rules don't cover all its input refs, call `call_complex_rules_agent` again with a focused prompt — *"you previously missed these N refs from this group, build rules for them only."* Bounded (1 retry max), targeted (only the missed refs, not the whole group), converts silent variance into recoverable failure. Likely closes most of the 3× rule-count gap.

9. **Lower `MAX_REFS_PER_CALL` from 20 → ~5** at `:1369`. Smaller batches give the LLM less to juggle in a single response, reducing truncation and skipped refs. Costs more parallel calls but each call has clearer scope. Output stability improves with little latency cost since calls run in parallel.

10. **Schema-validate Phase 2 output and retry on invalid.** Same pattern as the Phase 1 strict-schema fix (Tier-1 item 1) but for the rule output. If the LLM returns malformed `rules_to_add`, retry once before recording failure. Replaces the silent `'empty output'` failure path at `:1448-1454`.

11. **Pin the Phase 2 model snapshot.** Currently `--model opus`. Pin to a specific version string so model upgrades don't shift output. If the `claude` CLI exposes a temperature / seed flag, set them too.

12. **Golden-file regression test.** Save `Vendor Update runs/3/inter_panel/all_panels_inter_panel.json` as a baseline. After each pipeline change, diff against the golden. Catches "we silently lost 30 rules" regressions automatically. Doesn't reduce variance, but makes variance visible in CI instead of in production.

## Recommended First Step
Implement Tier-1 items 1, 4, and 5. They target the two real failure modes (schema drift + the one real Phase 2 drop case) and add the diagnostics needed to validate any further fix. Then layer Tier-3 items 8 and 10 (reconciliation-driven retry + Phase 2 schema validation) to compress the Phase 2 variance without replacing the LLM call.
