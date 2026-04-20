---
name: Annotate Cross-Panel References in BUD
allowed-tools: Bash, Read, Write
description: Produces an annotated copy of a BUD .docx with `(from <Panel> panel)` inserted after every field reference whose target lives in a different panel.
---

# Annotate Cross-Panel References in BUD

## Objective

Given an input BUD `.docx`, produce an annotated copy (a new `.docx`) where every field reference in a field's `logic` text that points to a field in a **different panel** is suffixed with ` (from <Panel Name> panel)`. The original docx formatting (runs, styles, tables) is preserved — annotations are spliced in without rewriting unrelated content.

Reference format style (from `documents/Pidilite Extension BUD-2.docx`):

```
Original:  Value is derived based on field "Vendor Name and code" value as 11th column of VC_BASIC_DETAILS staging.
Annotated: Value is derived based on field "Vendor Name and code" (from Basic Details panel) value as 11th column of VC_BASIC_DETAILS staging.
```

Ambiguous references (not resolvable to a single panel) get `(from ??? panel)`.

---

## Inputs (from the user)

1. **INPUT_BUD** — absolute path to the source `.docx`.
2. **OUTPUT_BUD** (optional) — absolute path for the annotated output. Default: same directory as INPUT_BUD, filename suffixed with ` - annotated.docx`.
3. **MODEL** (optional) — `sonnet` (default) or `opus` or `haiku`. Passed to `claude -p`.
4. **WORKERS** (optional) — parallel panel workers. Default `4`.

If INPUT_BUD is missing, ask the user for it before doing anything else.

---

## Pipeline (three stages)

All stages run sequentially via Bash. Respect the absolute paths given by the user — never relocate files.

### Stage 1 — Build the global field index

```bash
mkdir -p "$WORKDIR"
python3 "$REPO/scripts/build_field_index.py" "$INPUT_BUD" "$WORKDIR/field_index.json"
```

`WORKDIR` = `$REPO/output/cross_panel_annotate/<bud_basename>/`.

`build_field_index.py` already exists. It parses the BUD via `doc_parser`, emits `{panels: [{name, fields: [{name, variable_name, field_type, logic}]}]}`.

### Stage 2 — Run the batched parallel annotator

```bash
python3 "$REPO/scripts/annotate_cross_panel_refs_batched.py" \
  --index "$WORKDIR/field_index.json" \
  --output "$WORKDIR/annotations.json" \
  --model "$MODEL" \
  --max-workers "$WORKERS" \
  --resume
```

The script:
- One `claude -p` call per panel (all fields in that panel in a single prompt).
- Each call returns `{fields: [{field_name, annotated_logic, changed}]}`.
- `--resume` skips entries already present in `annotations.json` so re-runs are cheap.
- Writes a flat map `{"<Panel>::<Field>": {old, new, changed, panel, field_name, [error]}}`.

### Stage 3 — Patch the docx

```bash
python3 "$REPO/scripts/patch_docx_with_annotations.py" \
  --src "$INPUT_BUD" \
  --dst "$OUTPUT_BUD" \
  --annotations "$WORKDIR/annotations.json" \
  --report "$WORKDIR/patch_report.json"
```

The patcher:
- Copies INPUT_BUD → OUTPUT_BUD.
- For every changed field, diffs `old` vs `new` to extract insertions.
- Matches the logic cell in the docx via whitespace-insensitive search (the parser collapses whitespace but the raw cell may have `\n` between paragraphs).
- Splices each insertion into the correct run using a whitespace-aware offset so the result has exactly one space on each side of the annotation.

---

## What to report back to the user

After the pipeline finishes, emit a short summary:

- Path of the annotated `.docx` (OUTPUT_BUD)
- Counts: total fields analyzed / fields with cross-panel refs / total insertions
- Any errors from `annotations.json` (`error` key set) or failed patches from `patch_report.json`
- Top 5 panels by number of annotated fields

---

## Hard Constraints

- Never edit, rename, or delete `INPUT_BUD` — it is the source of truth.
- Never edit files under `scripts/` from within this command; only invoke them.
- Do not produce any intermediate JSON file outside `WORKDIR`.
- If Stage 2 reports non-zero errors, surface them to the user and ask whether to proceed with Stage 3 anyway.
- If Stage 3 reports any `failed` entries, print the first few `old_head` previews so the user can investigate.

---

## Failure modes to handle

| Symptom | Cause | Fix |
|---|---|---|
| `build_field_index.py` errors with `No module named doc_parser` | cwd not repo root | `cd "$REPO"` before running, or pass absolute script path (the script already adds repo root to `sys.path`). |
| Stage 2 errors with `claude: command not found` | `claude` CLI missing | Ask the user to install / authenticate the Claude CLI. |
| Stage 2 panel error `JSONDecodeError` | LLM returned non-JSON | Re-run Stage 2 with `--resume`; only the failed panel retries. |
| Stage 3 `cell not found` for a field | Logic text was heavily rewritten upstream or spans unusual structure | Inspect the field in `annotations.json`, then either skip (delete its entry + re-run) or patch manually. |

---

## Enforcement

- Exactly one annotated docx output.
- All per-panel LLM results cached under `WORKDIR`.
- Zero same-panel annotations (the prompt explicitly forbids them — validate by sampling `annotations.json` if unsure).
- Do not rebuild the annotator or patcher logic inside the command — invoke `scripts/` only.
