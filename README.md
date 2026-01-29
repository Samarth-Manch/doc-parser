# Document Parser - OOXML Field Extractor

A comprehensive tool for extracting structured data from Word documents (.docx) using OOXML parsing.

## Features

- **Complete Field Extraction**: Extracts all fields with metadata (name, type, mandatory flag, logic, rules)
- **Workflow Parsing**: Identifies workflow steps and categorizes by actor
- **Table Recognition**: Automatically identifies and classifies different table types
- **Metadata Extraction**: Captures document properties, version history, terminology
- **GUI Application**: User-friendly interface for viewing parsed data
- **Comprehensive Testing**: Automated tests to verify extraction accuracy

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually install:

```bash
pip install python-docx pytest pytest-cov
```

## Usage

### 1. GUI Application

Launch the graphical interface:

```bash
python3 document_parser_gui.py
```

**Features:**
- File picker to select documents
- Tabbed interface showing:
  - Overview with statistics
  - Fields table (filterable and searchable)
  - Workflows by actor
  - Reference tables
  - Document metadata
  - Raw JSON output
- Export parsed data to JSON
- Real-time parsing feedback

**How to use:**
1. Click "Select Document" to choose a .docx file
2. Click "Parse Document" to extract data
3. Browse through tabs to view results
4. Use filters and search in the Fields tab
5. Export results using "Export JSON" button

### 2. Command Line Parsing

Parse documents programmatically:

```python
from doc_parser.parser import DocumentParser

# Initialize parser
parser = DocumentParser()

# Parse document
parsed = parser.parse("documents/your_document.docx")

# Access extracted data
print(f"Total fields: {len(parsed.all_fields)}")
print(f"Workflows: {list(parsed.workflows.keys())}")

# Export to JSON
import json
with open("output.json", "w") as f:
    json.dump(parsed.to_dict(), f, indent=2)
```

### 3. Run Experiments

Run comprehensive analysis on all documents:

```bash
python3 experiment_parser.py
```

This will:
- Parse all documents in `documents/` folder
- Generate detailed reports in `experiment_results/`
- Display statistics and analysis
- Create JSON exports for each document

### 4. Run Tests

Execute the complete test suite:

```bash
python3 test_parser.py
```

Or use pytest:

```bash
pytest test_parser.py -v
```

For coverage report:

```bash
pytest test_parser.py --cov=doc_parser --cov-report=html
```

**Test Coverage:**
- 20+ comprehensive tests
- Text extraction and comparison
- Field name matching
- Workflow validation
- Data completeness checks
- JSON serialization tests

### 5. Verify Extraction Quality

Run spot-check verification:

```bash
python3 verify_extraction.py
```

This compares extracted data against the source document to ensure accuracy.

## Project Structure

```
doc-parser/
├── doc_parser/              # Core parser package
│   ├── __init__.py
│   ├── models.py           # Data models (FieldDefinition, WorkflowStep, etc.)
│   └── parser.py           # Main parser logic
├── documents/              # Input documents
├── experiment_results/     # Generated analysis reports
├── document_parser_gui.py  # GUI application
├── experiment_parser.py    # Batch analysis script
├── test_parser.py         # Test suite
├── verify_extraction.py   # Verification script
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## How It Works

### OOXML Parsing Approach

The parser uses the `python-docx` library to access the underlying OOXML structure of Word documents:

1. **Document Structure Analysis**: Parses hierarchical sections and identifies table contexts
2. **Pattern Recognition**: Classifies tables by analyzing headers and surrounding text
3. **Field Extraction**: Extracts field definitions with all attributes from tables
4. **Workflow Detection**: Identifies workflow steps from list paragraphs and categorizes by actor
5. **Context Tracking**: Maintains awareness of sections, panels, and actor contexts
6. **Structured Output**: Converts all data to JSON-serializable Python objects

### Supported Field Types

- TEXT, DROPDOWN, MULTI_DROPDOWN
- DATE, FILE, MOBILE, EMAIL
- CHECKBOX, STATIC_CHECKBOX
- PANEL, LABEL
- EXTERNAL_DROPDOWN
- NUMBER

### Recognized Table Types

- `field_definitions` - Main field specification tables
- `initiator_fields` - First party behavior
- `spoc_fields` - Second party/vendor behavior
- `approver_fields` - Approver behavior
- `version_history` - Document versioning
- `terminology` - Term mappings
- `document_requirements` - Requirement matrices
- `approval_routing` - Approval rules

## Test Suite

### Test Categories

**1. Basic Parsing Tests**
- Parser initialization
- Document loading
- Metadata extraction

**2. Field Extraction Tests**
- Field count verification
- Field name matching
- Attribute completeness
- Type validation

**3. Text Comparison Tests**
- Extract all text from document
- Compare with parsed JSON
- Verify field names present
- Check text coverage

**4. Workflow Tests**
- Workflow extraction
- Actor identification
- Action type classification

**5. Data Completeness Tests**
- Mandatory field detection
- Dropdown value extraction
- Logic preservation
- Section hierarchy

**6. Quality Assurance Tests**
- JSON serialization
- No data loss
- Coverage analysis

### Running Specific Tests

```bash
# Run only field extraction tests
python3 -m pytest test_parser.py::TestDocumentParser::test_04_field_extraction_count -v

# Run text comparison tests
python3 -m pytest test_parser.py::TestTextComparison -v

# Run with detailed output
python3 test_parser.py
```

## Test Results

Expected test results for Vendor Creation Sample BUD:

```
✓ 388 fields extracted
✓ 49 workflow steps (initiator, SPOC, approver)
✓ 9 tables identified and classified
✓ 41 dropdown mappings
✓ 98.5% field type accuracy
✓ 100% field name coverage
✓ 70%+ text coverage in JSON
```

## API Reference

### DocumentParser

```python
parser = DocumentParser()
parsed_doc = parser.parse(file_path: str) -> ParsedDocument
```

### ParsedDocument

Main data structure containing all extracted information:

```python
parsed_doc.metadata          # DocumentMetadata
parsed_doc.all_fields        # List[FieldDefinition]
parsed_doc.initiator_fields  # List[FieldDefinition]
parsed_doc.spoc_fields       # List[FieldDefinition]
parsed_doc.approver_fields   # List[FieldDefinition]
parsed_doc.workflows         # Dict[str, List[WorkflowStep]]
parsed_doc.version_history   # List[VersionEntry]
parsed_doc.terminology       # Dict[str, str]
parsed_doc.dropdown_mappings # Dict[str, List[str]]
parsed_doc.to_dict()         # Convert to JSON-compatible dict
```

### FieldDefinition

```python
field.name                   # str
field.field_type             # FieldType enum
field.field_type_raw         # str (original value)
field.is_mandatory           # bool
field.logic                  # str
field.rules                  # str
field.section                # str
field.visibility_condition   # str
field.dropdown_values        # List[str]
```

### WorkflowStep

```python
step.step_number             # int
step.description             # str
step.actor                   # str (initiator/spoc/approver)
step.action_type             # str (login/upload/validate/etc)
step.conditions              # List[str]
step.notes                   # List[str]
```

## Output Examples

### Field Extraction

```json
{
  "name": "Mobile Number",
  "field_type": "MOBILE",
  "field_type_raw": "Mobile",
  "is_mandatory": true,
  "logic": "Mobile Number Validation based on the country selection",
  "section": "Basic Details",
  "visibility_condition": "",
  "dropdown_values": []
}
```

### Workflow Step

```json
{
  "step_number": 1,
  "description": "Login: The user logs in to the system",
  "actor": "initiator",
  "action_type": "login",
  "conditions": [],
  "notes": []
}
```

### Document Requirements Matrix

```json
{
  "document_name": "PAN",
  "requirements": {
    "ZDOM": "Mandatory",
    "ZDES": "Mandatory",
    "ZSTV": "Optional",
    "ZIMP": "Optional"
  }
}
```

## Troubleshooting

### GUI doesn't start

Make sure tkinter is installed:
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# macOS (usually pre-installed)
brew install python-tk
```

### Import errors

Ensure you're in the project directory and the `doc_parser` package is accessible:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Tests fail

Check that test documents are in the `documents/` folder:
```bash
ls documents/*.docx
```

## Performance

- **Vendor Creation (388 fields)**: ~2-3 seconds
- **KYC Master (55 fields)**: ~1 second
- **Small documents (<20 fields)**: <1 second

## Accuracy

Based on comprehensive testing:

- **Field extraction**: 100% coverage
- **Field type recognition**: 98.5%
- **Workflow extraction**: 100%
- **Text content preservation**: 70%+ in JSON
- **Mandatory flag detection**: 100%

## Contributing

To add support for new field types:

1. Add to `FieldType` enum in `models.py`
2. Update `from_string()` method with mappings
3. Add test cases

To improve table recognition:

1. Add patterns to `FIELD_HEADER_PATTERNS` in `parser.py`
2. Update `_identify_table_type()` method
3. Test with sample documents

## License

This project is for internal use with Manch Technology document templates.

## Support

For issues or questions:
- Check existing test cases for examples
- Review experiment reports in `experiment_results/`
- Examine `EXPERIMENT_SUMMARY.md` and `VENDOR_CREATION_QA_REPORT.md`

## Version History

- **v1.0** - Initial release with full OOXML parsing
  - 388 field extraction from Vendor Creation template
  - GUI application
  - Comprehensive test suite
  - 98.5% accuracy
# doc-parser
