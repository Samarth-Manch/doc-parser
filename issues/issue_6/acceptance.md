# Issue 6 — Acceptance Record

**Date:** 2026-04-20
**BUD:** `documents/Vendor update BUD - Pidilite v4.docx` (15 panels)
**Model:** opus (`--detect-model opus`)

## Primary criterion

**4 consecutive runs of Phase 1 (detect refs) must produce shape-valid 9-key output on every panel.**

Ran detection-only via `/tmp/ip_detect_test/run_detect_only.py` (calls `detect_cross_panel_refs` directly, parallelized over all 15 panels, validates the `structured_output` envelope at the CLI boundary before normalization).

| Run | Shape-valid panels | Total refs | Duration |
|-----|--------------------|-----------:|----------|
|  1  | 15 / 15            | 85         | 184 s    |
|  2  | 15 / 15            | 88         | 202 s    |
|  3  | 15 / 15            | 87         | 194 s    |
|  4  | 15 / 15            | 84         | 187 s    |

Ref-count variance (84–88) is expected sampling noise on `description` / `logic_snippet` text and on borderline "copy-from" classifications; shape conformance is 100% deterministic.

## Observability criterion

The dispatcher now emits `Phase 1 SCHEMA: N/N panels returned shape-valid output` near the existing `Phase 1 COMPLETE` log line. The metric counts panels whose *raw* `structured_output` envelope had exactly the 9 canonical keys per ref — this is the measurement before the normalizer adds its `_original_classification` tracking field.

## Notes / follow-ups

1. **0-ref panels.** Three panels (Basic Details, Approver Mapping, Addition Of Approver) consistently return 0 refs. These are still counted as shape-valid since an empty `cross_panel_references` array is schema-valid. Whether those panels *should* have refs is a semantic question orthogonal to this fix.
2. **Acceptance was run via Phase 1 only**, not the full pipeline. Phase 2 (complex-ref rule generation) and subsequent stages are unchanged by this fix and their cost (10+ minutes per run × 4) was not justified for a shape-enforcement gate.
3. **Normalizer retained** as a semantic safety net per `fix_issue_1.md` Part 4.
4. **Schema file gotcha** captured in `tasks.md`: the Claude CLI silently drops `structured_output` when the schema JSON contains a `$schema` meta-field. Removed from `detect_refs.schema.json`.
