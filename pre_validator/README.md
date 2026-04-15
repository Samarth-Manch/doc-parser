# BUD Pre-Validator

A validation module within the [doc-parser](../README.md) project that validates Business Understanding Document (`.docx`) files used in vendor management workflows (Vendor Creation, Vendor Extension, Block/Unblock). It runs 13 validation checks against parsed BUD documents and outputs dual-format reports (Excel + HTML) with color-coded results.

## Setup

### Prerequisites

- Python 3.8+
- Parent `doc_parser` package (this module imports `DocumentParser` and `FieldDefinition` from it)

### Installation

```bash
# From the project root (doc-parser/)
pip install -r requirements.txt
```

## Usage

```bash
# Validate a specific BUD document
python pre_validator/bud_validator.py "path/to/your-bud-file.docx"

# Run with the default file
python pre_validator/bud_validator.py
```

## Output

Reports are generated in two formats:

- `validation_output/excel_output/<filename>_validation.xlsx` — Workbook with one sheet per validator
- `validation_output/html_output/<filename>_validation.html` — Single-file HTML with sidebar navigation, scroll-spy, and embedded CSS/JS

Both reports use severity-based color coding:

| Color | Severity | Meaning |
|-------|----------|---------|
| Red | ERROR | Must be fixed |
| Yellow | WARNING | Should be reviewed |
| Green | PASS | Check passed |
| Blue | INFO | Informational note |
| Gray | N/A | Not applicable |

## Validation Checks

| # | Check | Description |
|---|-------|-------------|
| 1 | **Table Structure** | Sections 4.4, 4.5.1, 4.5.2 exist and contain properly formatted field tables |
| 2 | **Field Consistency** | Fields in 4.5.1/4.5.2 exist in 4.4; visible fields in 4.4 appear in sub-tables; invisible mandatory fields have derivation logic |
| 3 | **EDV Logic** | `EXTERNAL_DROP_DOWN_VALUE` / `DROPDOWN` fields reference a table and column in their logic |
| 4 | **Field Uniqueness** | No duplicate field names within a panel; no duplicate panel names within a section |
| 5 | **Field Types** | Field types match the allowed list (50+ types); fuzzy-suggests corrections for typos |
| 6 | **Clear Field Logic** | Fields derived from other fields specify clear-on-change behavior |
| 7 | **Cross-Panel References** | Logic referencing fields in other panels includes the panel name |
| 8 | **Non-Editable** | Fields marked non-editable in logic have type TEXT or DATE |
| 9 | **Array Brackets** | ARRAY_HDR/ARRAY_END pairs are properly matched and not nested |
| 10 | **Rule Duplicates** | Detects duplicate rules across sections using 3-tier matching: exact, fuzzy (`rapidfuzz`), and LLM-based (Claude) |
| 11 | **Reference Table** | Reference tables cited in field logic exist in section 4.6; validates OLE-embedded Excel links |
| 12 | **Field Outside Panel** | Every field belongs to a panel; flags orphan fields before the first PANEL |
| 13 | **Record List View** | Section 4.7 Record List View fields validated against expected sample list |

## BUD Document Structure

The validator expects a standard BUD layout:

- **Section 4.4** — Master field definitions (all fields with types, logic, rules)
- **Section 4.5.1** — Initiator behaviour table
- **Section 4.5.2** — SPOC behaviour table
- **Section 4.6** — Reference tables (lookup data for EDV fields)
- **Section 4.7** — Record List View (fields shown in list view)

## Architecture

### Data Flow

```
BUD (.docx)
    |
    v
document_reader.py            Uses doc_parser.DocumentParser from parent project
    |
    v
ValidationContext              master_fields, sub_tables, raw_fields, doc
    |
    v
ValidatorRegistry.run_all()    Executes all 13 registered validators
    |
    v
{validator_name: [results]}
    |
    +---> excel_writer.py      Workbook with 13 sheets
    +---> html_writer.py       Single HTML file with sidebar + sections
```

### Key Design Patterns

- **Registry pattern** — `@ValidatorRegistry.register` decorator auto-registers validators; no central coupling
- **Adapter pattern** — `document_reader.py` bridges `doc_parser.DocumentParser` output to the validator's data format
- **Template method** — All validators inherit `BaseValidator` and implement `validate(ctx)` + `write_sheet(wb, results)`
- **Dataclass introspection** — `html_writer.py` generically converts result dataclasses to HTML tables

### Integration with Parent Project

`pre_validator` depends on the parent `doc_parser` package (one-way dependency):

- `DocumentParser` — Parses `.docx` into structured `ParsedDocument` objects
- `FieldDefinition` — Dataclass representing a field with type, logic, section, mandatory flag
- `ParsedDocument` — Container with `all_fields`, `initiator_fields`, `spoc_fields`, `reference_tables`

## Project Structure

```
pre_validator/
├── bud_validator.py        # Entry point — orchestrates the validation pipeline
├── document_reader.py      # Adapter: doc_parser output -> validator format
├── models.py               # 12+ result dataclasses (one per validation type)
├── excel_writer.py         # Excel report writer with severity-based styling
├── html_writer.py          # Single-file HTML report with sidebar navigation
├── BUD_Writing_Rules.md    # Documentation for BUD authors
├── validators/             # All validation modules
│   ├── __init__.py         # Imports validators to trigger registration
│   ├── registry.py         # ValidatorRegistry, BaseValidator, ValidationContext
│   ├── doc_utils.py        # Shared document-traversal helpers
│   ├── tables.py           # Section existence and table format checks
│   ├── field_consistency.py # Field presence, visibility, mandatory logic
│   ├── edv_logic.py        # EDV dropdown reference validation
│   ├── field_uniqueness.py # Duplicate field/panel detection
│   ├── field_types.py      # Field type validation with fuzzy suggestions
│   ├── cross_panel_references.py # Cross-panel field reference tracking
│   ├── non_editable.py     # Non-editable field type enforcement
│   ├── array_brackets.py   # ARRAY_HDR/ARRAY_END pairing validation
│   ├── clear_field_logic.py # Derivation dependency clear-on-change checks
│   ├── rules.py            # Rule duplicate detection (exact/fuzzy/LLM)
│   ├── reference_table.py  # EDV table reference existence checks
│   ├── field_outside_panel.py # Panel membership validation
│   └── record_list_view.py # Section 4.7 field validation
└── validation_output/      # Generated reports
    ├── excel_output/
    └── html_output/
```

## Adding a New Validator

1. Add a result dataclass to `models.py`
2. Create `validators/<name>.py` with a `@ValidatorRegistry.register` class implementing `validate(ctx)` and `write_sheet(wb, results)`
3. Import the new module in `validators/__init__.py`

No changes needed to `bud_validator.py` or the report writers — the registry handles discovery automatically.
