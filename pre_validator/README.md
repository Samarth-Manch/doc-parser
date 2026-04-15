# BUD Pre-Validator

A Python tool that validates Business Understanding Document (`.docx`) files used in vendor management workflows (Vendor Creation, Vendor Extension, Block/Unblock). It parses structured BUD documents, runs 13 validation checks, and outputs both Excel and HTML reports with color-coded results.

## Setup

### Prerequisites

- Python 3.10+

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd BUD-pre-validator

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Validate a specific BUD document
python bud_validator.py "path/to/your-bud-file.docx"

# Run with the default file
python bud_validator.py
```

## Output

Reports are generated in two formats:

- `validation_output/excel_output/<filename>_validation.xlsx`
- `validation_output/html_output/<filename>_validation.html`

Both reports use severity-based color coding:

- **Red** — ERROR: must be fixed
- **Yellow** — WARNING: should be reviewed
- **Green** — PASS: check passed
- **Blue** — INFO: informational note

## Validation Checks

| Check | Description |
|---|---|
| **Table Structure** | Tables exist and are properly formatted in each section |
| **Field Consistency** | Fields in section 4.4 appear in 4.5.1/4.5.2; mandatory+invisible logic |
| **EDV Logic** | External Dropdown fields have reference tables and attribute columns |
| **Field Uniqueness** | No duplicate field names within a panel/section; panel names are unique |
| **Field Types** | Field types match valid BUD types |
| **Cross-Panel References** | Logic referencing fields in other panels includes the panel name |
| **Non-Editable** | Fields with non-editable logic have type TEXT |
| **Array Brackets** | ARRAY_HDR/ARRAY_END pairs are properly matched |
| **Clear Field Logic** | Conditional logic referencing other fields includes a clear/inverse clause |
| **Rule Duplicates** | Detects duplicate rules across sections (exact, fuzzy, and semantic matching) |
| **Reference Table** | Reference tables cited in field logic exist in section 4.6 |
| **Field Outside Panel** | Every field belongs to a panel; flags fields outside any panel |
| **Record List View** | Section 4.7 Record List View fields validated against expected sample list |

## BUD Document Structure

The validator expects a standard BUD layout:

- **Section 4.4** — Master field definitions (all fields with types, logic, rules)
- **Section 4.5.1** — Initiator behaviour table
- **Section 4.5.2** — SPOC behaviour table
- **Section 4.6** — Reference tables (lookup data for EDV fields)
- **Section 4.7** — Record List View (fields shown in list view)

## Project Structure

```
BUD-pre-validator/
├── bud_validator.py        # Entry point — orchestrates the pipeline
├── document_reader.py      # Adapter: converts parsed doc to validator format
├── models.py               # Result dataclasses for each validation type
├── excel_writer.py         # Shared Excel report helpers
├── html_writer.py          # HTML report generator
├── docs_parser/            # Document parsing package (reads .docx)
├── validators/             # All validation modules
│   ├── __init__.py         # Imports validators to trigger registration
│   ├── registry.py         # ValidatorRegistry, BaseValidator, ValidationContext
│   ├── doc_utils.py        # Shared document-traversal helpers
│   ├── tables.py
│   ├── field_consistency.py
│   ├── edv_logic.py
│   ├── field_uniqueness.py
│   ├── field_types.py
│   ├── cross_panel_references.py
│   ├── non_editable.py
│   ├── array_brackets.py
│   ├── clear_field_logic.py
│   ├── rules.py
│   ├── reference_table.py
│   ├── field_outside_panel.py
│   └── record_list_view.py
└── validation_output/      # Generated reports
    ├── excel_output/
    └── html_output/
```

## Adding a New Validator

1. Add a result dataclass to `models.py`
2. Create `validators/<name>.py` with a `@ValidatorRegistry.register` class implementing `validate(ctx)` and `write_sheet(wb, results)`
3. Import the new module in `validators/__init__.py`

No changes needed to `bud_validator.py` or `excel_writer.py`.
