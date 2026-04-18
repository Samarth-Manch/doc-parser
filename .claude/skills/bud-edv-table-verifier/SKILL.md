---
name: bud-edv-table-verifier
description: Use when auditing a BUD .docx to verify that every EDV reference table name cited in field logic (e.g., VC_BANK_DETAILS) actually exists as an embedded Excel object under the document's section 4.6. Emits a self-contained HTML report classifying each referenced name as present, outside-4.6, or missing.
---

# BUD EDV Reference Table Verifier

Audit a BUD .docx for EDV reference-table integrity: confirm every named table cited in field logic exists as an embedded Excel object under section 4.6.

## When to use

- User asks to "check / verify / audit" EDV reference tables in a BUD.
- User names a BUD docx and mentions table names like `VC_BANK_DETAILS`, `TERMS_OF_PAYMENT`, or "4.6 section".
- Before running the rule-extraction pipeline on a new BUD — missing 4.6 tables cause silent failures downstream.

## How to run

1. Identify the BUD .docx path. If the user has not supplied one, ask.
2. Run the bundled script:

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/verify_edv_tables.py" "<bud.docx>" --output output/edv_table_audit
   ```

   Fallback if `$CLAUDE_PLUGIN_ROOT` is not set, use the absolute path to the skill directory where this `SKILL.md` lives.

3. The script exits `0` when every referenced name is present under 4.6, `1` when anything is missing or outside-4.6, `2` on malformed input. Report path is printed to stdout.

4. Open the HTML in a browser or relay its contents. Summarize for the user:
   - total referenced names,
   - how many are present in 4.6,
   - how many are missing,
   - how many were found outside 4.6 (indicating they should be moved into 4.6).

## Direct CLI usage (no Claude)

Users can bypass the assistant:

```bash
python3 ~/.claude/skills/bud-edv-table-verifier/verify_edv_tables.py \
    "documents/Vendor update BUD - Pidilite v2.docx"
# report -> output/edv_table_audit/<doc-stem>.html
```

## Dependencies

- Python 3.8+
- `openpyxl` (optional; degrades gracefully if absent — sheet names become "unavailable")
- The project's own `doc_parser` package is NOT required; the script is self-contained and reads the docx directly via `zipfile` + stdlib XML.
