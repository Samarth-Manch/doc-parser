---
name: cross-panel-references
description: Use when extracting cross-panel field references from a BUD .docx. Runs a per-panel LLM detection pass that resolves both explicit panel mentions (e.g., "Copy from Basic Details") and unnamed references (e.g., "Copy from Name field") against a global field index. Emits a JSON result and a self-contained HTML report.
---

# Cross-Panel References

Detect every cross-panel field reference in a BUD .docx by running a per-panel LLM pass against a global field index. Produces both machine-readable JSON and a standalone HTML report.

## When to use

- User asks to "extract / detect / list / audit cross-panel references" in a BUD.
- User wants to understand how fields in one panel control or derive values in another.
- Reviewing a BUD before running the rule-extraction pipeline — unresolved cross-panel logic shows up here cleanly.

This skill is **standalone**. It does NOT modify the rule-extraction pipeline (Stages 1–8) or mutate any existing dispatcher output.

## How to run

1. Identify the BUD .docx path. If the user has not supplied one, ask.
2. Run the bundled driver:

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/detect_cross_panel_refs.py" \
       --bud "<bud.docx>" \
       --output output/cross_panel_references
   ```

   Fallback if `$CLAUDE_PLUGIN_ROOT` is not set, use the absolute path to the skill directory where this `SKILL.md` lives.

3. The driver exits `0` on success, `1` if every panel failed LLM detection, `2` on malformed input (.docx not found / unreadable). Report paths are printed to stdout.

4. Surface the HTML path to the user. Summarize:
   - total fields / total panels / total cross-panel refs
   - count by `relationship_type`
   - count by `panel_resolution` (explicit / inferred / ambiguous)
   - any `errors[]` from per-panel LLM failures

## CLI options

| Flag | Default | Description |
|---|---|---|
| `--bud <path>` | *required* | .docx path |
| `--output <dir>` | `output/cross_panel_references` | Output root; artifacts are written under `<output>/<bud_basename>/` |
| `--max-workers <int>` | `4` | Parallel per-panel LLM calls |
| `--model <name>` | `haiku` | Claude model passed to `claude -p` |
| `--skip-empty-logic` | off | Skip fields whose `logic` is empty before sending to LLM (saves tokens) |

## Output layout

```
output/cross_panel_references/<bud_basename>/
├── <bud_basename>_cross_panel_references.json
├── <bud_basename>_cross_panel_references.html
├── run.log
└── temp/
    ├── all_panels_index.json
    ├── panel_<slug>_input.json
    └── panel_<slug>_output.json
```

### JSON schema (aggregated)

```json
{
  "document_info": {"file_name", "file_path", "extraction_timestamp", "total_fields", "total_panels"},
  "panel_summary": [{"panel_name", "field_count", "fields_with_cross_panel_refs", "references_emitted_here"}],
  "cross_panel_references": [
    {
      "source_field": {"field_name", "variable_name", "panel", "field_type"},
      "target_field": {"field_name", "variable_name", "panel", "field_type"},
      "reference_details": {
        "matched_text", "location_found", "relationship_type", "operation_type",
        "panel_resolution",      /* "explicit" | "inferred" | "ambiguous" */
        "raw_expression",
        "candidate_panels"       /* only when ambiguous */
      }
    }
  ],
  "relationship_summary": {...counts by type...},
  "dependency_graph": {"source_panels": {...}, "target_panels": {...}},
  "errors": [{"panel": "...", "message": "..."}]
}
```

### HTML report

Single file, inline CSS and vanilla JS only (no network fetches). Sections:
1. Document header + totals
2. Summary cards (relationship types, panel resolutions)
3. Dependency graph (source panels → affected panels)
4. Main reference table with client-side filter
5. Errors section (if any)

## Validation criteria

- Zero intra-panel refs: for every emitted ref, `source_field.panel != target_field.panel`.
- Every referenced `variable_name` exists in the panel declared in the ref (verified against the global index).
- `panel_resolution` is always one of `explicit`, `inferred`, `ambiguous`.
- Per-panel LLM failures are logged to `errors[]` and do NOT abort the whole run.

## Dependencies

- Python 3.8+
- The project's `doc_parser` package must be importable (added to `sys.path` automatically by the driver).
- `claude` CLI authenticated and on `$PATH`.
