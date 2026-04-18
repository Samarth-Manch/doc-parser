# BUD EDV Reference Table Verifier — Design

**Date:** 2026-04-18
**Status:** Approved

## Problem

BUD documents cite EDV reference tables in field logic (e.g., `VC_BANK_DETAILS`, `TERMS_OF_PAYMENT`). Section 4.6 of each BUD is the canonical location where those tables must be embedded as Excel objects (`word/embeddings/*.xlsx`). Today there is no automated way to confirm that every referenced name is actually present as an Excel embedding under section 4.6. Missing tables cause silent failures downstream in the rule-extraction pipeline.

Example: `documents/Vendor update BUD - Pidilite v2.docx` references at least 17 named tables (VC_BANK_DETAILS, VC_BASIC_DETAILS, TERMS_OF_PAYMENT, CURRENCY_COUNTRY, …) but contains 0 embedded Excel files.

## Goal

Provide a skill that, given a BUD .docx, produces an HTML audit report enumerating every referenced table name and classifying each as **present in 4.6**, **present outside 4.6**, or **missing**.

## Scope

- Input: a single .docx BUD file.
- Output: one self-contained HTML file.
- Strictly verifies Excel embeddings located **under the "4.6" heading** (user-confirmed mode B). Word-format tables do not count.
- Non-goal: fixing missing tables or modifying the BUD.

## Components

### 1. Skill package
Installed at `~/.claude/skills/bud-edv-table-verifier/` (global) and symlinked into `<project>/.claude/skills/bud-edv-table-verifier` so it is discoverable in both scopes.

Package contents:
- `SKILL.md` — frontmatter + instructions Claude follows when invoked.
- `verify_edv_tables.py` — standalone Python script performing the audit.
- `report_template.html` — minimal styled template with placeholders.

### 2. Reference extractor
Uses the project's existing `doc_parser.DocumentParser` to obtain fields. For each field whose `logic` or `rules` text contains "EDV" (case-insensitive), extracts uppercase-underscore identifiers matching `[A-Z][A-Z0-9_]{3,}` with at least one underscore. Records `{name → [(panel, field, snippet)]}`.

### 3. Section 4.6 locator
Reads `word/document.xml` directly via `zipfile` + `lxml`. Walks paragraphs in order. The "4.6 window" is the range of body elements between:
- a paragraph whose text matches `^\s*4\.6(\.|\s|$)` (heading for 4.6), and
- the next paragraph whose text matches `^\s*(4\.7|5\.|[5-9]\.)` (next sibling/parent heading).

Fallback: if no `4.6` heading is found, the window is empty and every referenced name reports as missing.

### 4. Embedded Excel inventory
Inside the 4.6 window, finds `<w:object>` / `<o:OLEObject>` elements. For each, resolves its `r:id` via `word/_rels/document.xml.rels` to the embedding path (`word/embeddings/*.xlsx|.xls|.bin`). For each embedding:
- Captures the nearest preceding paragraph text as a human label.
- If `.xlsx` / `.xls`: opens with openpyxl, records sheet names and first-row headers.
- `.bin` (legacy OLE): records filename only, no sheet extraction.

Also builds a second inventory of embeddings **outside** the 4.6 window, for the "present outside 4.6" classification.

### 5. Matcher
For each referenced name, check case-insensitive substring match against:
- preceding label text,
- sheet names,
- embedding filename.

Status:
- `present` — matched inside 4.6 window.
- `outside_4_6` — matched only outside the window.
- `missing` — no match anywhere in the document.

### 6. HTML report
Single self-contained file (inline CSS, no external assets). Sections:
1. Header: doc filename, audit timestamp, counters (total / present / outside / missing).
2. "Referenced Names" table — name, status badge, matched file/sheet, citing panels & fields.
3. "4.6 Excel Inventory" table — filename, label, sheets, headers preview.
4. "Orphan Embeddings" table — 4.6 embeddings that didn't match any referenced name.
5. "Referenced but Missing" callout — prominent list for quick action.

## CLI

```bash
python3 verify_edv_tables.py <doc.docx> [--output DIR]
```

Default output: `output/edv_table_audit/<doc-stem>.html` relative to cwd.
Exit code: 0 if all referenced names are `present`; 1 otherwise.

## Skill invocation

The skill's `SKILL.md` tells Claude: (1) ask for the doc path if not provided, (2) run the script, (3) print the report path, (4) summarize counts. Users can also bypass Claude and run the script directly.

## Error handling

- Malformed docx → exit 2 with clear stderr.
- No EDV references found → still emit report with empty tables and an "OK, nothing to verify" banner.
- Missing openpyxl → degrade gracefully, record sheet names as "unavailable".

## Testing

Run against:
- `documents/Vendor update BUD - Pidilite v2.docx` — expect 17 missing.
- One BUD known to have embedded Excel tables in 4.6 (pick from `documents/` with non-empty `reference_tables`).
- Verify HTML opens standalone in a browser.
