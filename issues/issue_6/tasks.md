# Remaining Tasks — Issue 6 Phase 1 Schema Drift Fix

Plan: `issues/issue_6/plan.md`

## Status so far

- [x] Task 1: Preflight — `--json-schema` verified available; `structured_output` round-trips on simple schema.
  - Finding: the CLI's `structured_output` path silently drops the payload when the schema contains a `$schema` meta field (e.g. `"$schema": "https://json-schema.org/draft-07/schema#"`). That meta-field has been removed from `dispatchers/agents/schemas/detect_refs.schema.json`. If you ever regenerate the schema, do NOT re-add `$schema` at the top.
- [x] Task 2: Schema file created at `dispatchers/agents/schemas/detect_refs.schema.json`.
- [x] Task 3: Agent prompt rewired to stdout output (read-only `allowed-tools`, `OUTPUT_FILE` deleted, Output + Step 5 sections rewritten).
- [x] Task 4: Composition test passes end-to-end — `structured_output` populated with clean 9-key shape on a minimal fixture.
- [x] Task 5: Prompt cleanup complete — all forbidden-key prose removed. `grep -nE "source_field|source_variable|source_panel|source_field_type|target_field|target_variableName|referenced_variable_name|referenced_variableName|reference_type|reference_details|detected_references" .claude/agents/mini/inter_panel_detect_refs.md` returns zero matches.
- [x] Task 6: Dispatcher code changes made (code committed — end-to-end run not yet executed).
- [x] Task 7: Phase 1 SCHEMA aggregate log added (code committed — not yet verified in a real run).

## Remaining

### Task 6 — Step 8: End-to-end dispatcher run (NOT YET DONE)

Run Stage 6 only against the existing Stage 5 output for Pidilite:

```bash
mkdir -p /tmp/ip_test_run
python3 dispatchers/agents/inter_panel_dispatcher.py \
  --clear-child-output output/vendor_update/runs/3/expression_rules/all_panels_expression_rules.json \
  --bud "documents/Vendor update BUD - Pidilite v4.docx" \
  --output /tmp/ip_test_run/all_panels_inter_panel.json \
  --detect-model opus \
  --max-workers 4
```

Expected:
- Exit 0
- Per-panel log lines `Phase 1: '<panel>' — N refs detected`
- Final line `Phase 1 SCHEMA: N/N panels returned shape-valid output` with matching numerator/denominator
- `/tmp/ip_test_run/all_panels_inter_panel.json` written

### Task 6 — Step 9: Validate aggregate output shape

Inspect and validate the per-panel refs inside `/tmp/ip_test_run/all_panels_inter_panel.json` (and the aggregate detection structure in `/tmp/ip_test_run/temp/`) against `dispatchers/agents/schemas/detect_refs.schema.json`. Any non-canonical key in `cross_panel_references` items = failure; stop and diagnose.

### Task 7 — Step 3: Confirm `Phase 1 SCHEMA` log line is emitted during the Step 8 run

Already covered by Task 6 Step 8's expected output — just verify the line appears.

### Task 8: 4 consecutive clean Pidilite runs (NOT YET DONE)

Run full pipeline 4×, validate every Phase 1 output:

```bash
./run_stages_vendor_update.sh output/pidilite_run_1
./run_stages_vendor_update.sh output/pidilite_run_2
./run_stages_vendor_update.sh output/pidilite_run_3
./run_stages_vendor_update.sh output/pidilite_run_4
```

Then validate every per-panel detect output against the schema:

```bash
python3 - <<'PY'
import json, glob, jsonschema
schema = json.load(open('dispatchers/agents/schemas/detect_refs.schema.json'))
failures = []
for run_dir in ['output/pidilite_run_1','output/pidilite_run_2','output/pidilite_run_3','output/pidilite_run_4']:
    for path in glob.glob(f'{run_dir}/**/detect_*_output.json', recursive=True):
        try:
            data = json.load(open(path))
            jsonschema.validate(data, schema)
        except Exception as e:
            failures.append((path, str(e)[:200]))
if not failures:
    print("ALL 4 RUNS CLEAN")
else:
    print(f"{len(failures)} FAILURES:")
    for p, e in failures[:20]:
        print(f"  {p}: {e}")
PY
```

Notes:
- Post-enforcement, per-panel `detect_*_output.json` files may no longer be written (the dispatcher now reads `structured_output` from the CLI envelope instead of a file). If `glob` returns nothing, fall back to iterating `temp/` or the aggregate output and validate each panel's `{"panel_name": ..., "cross_panel_references": [...]}` envelope directly.
- Confirm `Phase 1 SCHEMA: N/N` log line appears for all 4 runs.

### Task 8 — Step 5: Optional audit note

If all 4 runs clean, write a short note under `issues/issue_6/` documenting the result. Optional, no code change.

## Known risks / open questions

1. **Dispatcher no longer writes per-panel detect files.** The plan's acceptance script (Task 8 Step 2) globs for `detect_*_output.json`, which won't exist anymore. Use the aggregate dispatcher output instead — see note above.
2. **Schema coercion, not rejection.** Per `fix_issue_1.md`, forced tool calls coerce content to satisfy the schema. A hallucinated-but-shape-valid ref will pass through; drift surfaces only at downstream variableName resolution. The existing normalizer is retained as a semantic safety net.
3. **Fallback plan is unused.** Task 1 passed, so no fallback needed. The fallback block in `plan.md` is dead weight for this PR.

## Files touched (committed)

- `.claude/agents/mini/inter_panel_detect_refs.md` — Read-only allowed-tools, stdout output, all forbidden-key prose removed (262 → 139 lines).
- `dispatchers/agents/schemas/detect_refs.schema.json` — new; 9-key contract without `$schema` meta-field.
- `dispatchers/agents/inter_panel_dispatcher.py` — `detect_cross_panel_refs` rewired to `--output-format json` + `--json-schema`; `Phase 1 SCHEMA` aggregate log added.

Not touched (kept as safety net): `normalize_detection_output`, `_normalize_single_ref`.
