# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Document Parser extracts structured data from Word documents (.docx) using OOXML parsing. It's designed for BUD (Business Use Documents) templates, extracting fields, workflows, metadata, and rules into JSON format.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run GUI application
python3 document_parser_gui.py

# Run enhanced GUI with AI Rules extraction
./run_enhanced_gui.sh

# Run tests
python3 test_parser.py
pytest test_parser.py -v
pytest test_parser.py --cov=doc_parser --cov-report=html

# Run single test
python3 -m pytest test_parser.py::TestDocumentParser::test_04_field_extraction_count -v

# Batch process all documents
python3 experiment_parser.py

# Run AI rules extraction demo
python3 run_rules_extraction_demo.py
```

## Architecture

### Core Package (`doc_parser/`)

- **parser.py** - Main `DocumentParser` class with extraction logic
- **models.py** - Dataclasses: `ParsedDocument`, `FieldDefinition`, `WorkflowStep`, `TableData`, `Section`, `ApprovalRule`

### Parsing Pipeline

```
Load DOCX → Extract Metadata → Extract Tables → Classify Tables by Headers
         → Extract Fields (split by actor: initiator/spoc/approver)
         → Extract Workflows → Build ParsedDocument → JSON
```

### Table Classification

Pattern-based header matching (not ML):
- `FIELD_HEADER_PATTERNS` - Detects field definition tables ("field name" + "field type")
- `INITIATOR_KEYWORDS`, `SPOC_KEYWORDS`, `APPROVAL_KEYWORDS` - Actor classification

### Field Types (FieldType enum)

TEXT, DROPDOWN, MULTI_DROPDOWN, DATE, FILE, MOBILE, EMAIL, NUMBER, CHECKBOX, STATIC_CHECKBOX, PANEL, LABEL, EXTERNAL_DROPDOWN, UNKNOWN

### Rules Extraction (Optional)

Uses OpenAI API to convert field logic text into structured expressions:
- `rules_extractor.py` - Main extraction engine
- `rules/Rule-Schemas.json` - 182 pre-defined rule patterns
- Requires `OPENAI_API_KEY` in `.env` file

## Key Patterns

**Basic parsing:**
```python
from doc_parser import DocumentParser, ParsedDocument

parser = DocumentParser()
parsed: ParsedDocument = parser.parse("documents/file.docx")

# Access data
parsed.all_fields          # List[FieldDefinition]
parsed.initiator_fields    # Fields for initiator actor
parsed.spoc_fields         # Fields for SPOC actor
parsed.approver_fields     # Fields for approver actor
parsed.workflows           # Dict[str, List[WorkflowStep]]
parsed.to_dict()           # JSON-serializable dict
```

**All model classes implement `to_dict()` for JSON serialization.**

## Extending the Parser

- **Add field type:** Update `FieldType` enum and `from_string()` in `models.py`
- **Add table pattern:** Update `FIELD_HEADER_PATTERNS` or `*_KEYWORDS` constants in `parser.py`
- **Add table type:** Update `_identify_table_type()` method in `parser.py`

## Environment

- **Python 3.8+** required
- **tkinter** required for GUI (`sudo apt-get install python3-tk` on Ubuntu)
- **OpenAI API key** required only for rules extraction features
