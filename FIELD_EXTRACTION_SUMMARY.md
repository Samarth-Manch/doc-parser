# Field Extraction Summary

## Overview

Created a deterministic field extraction tool that processes Word documents (.docx) and extracts:
- **Field Name**: The name of the field
- **Field Type**: The type (TEXT, DROPDOWN, DATE, FILE, etc.)
- **Mandatory Status**: Whether the field is required

## Implementation

### Script: `extract_fields_simple.py`

A Python script that:
- Uses the existing `DocumentParser` class from the `doc_parser` package
- Extracts fields deterministically from DOCX table structures
- Outputs clean JSON with only essential field information
- No AI/LLM processing required - pure OOXML parsing

### Usage

```bash
# Process all documents in documents/ directory
python3 extract_fields_simple.py

# Process a specific document
python3 extract_fields_simple.py path/to/document.docx

# Process with custom output directory
python3 extract_fields_simple.py path/to/document.docx custom/output/dir
```

## Output Format

Each JSON file contains:

```json
{
  "source_document": "Document Name.docx",
  "extraction_date": "2026-01-27T12:05:33.711918",
  "total_fields": 246,
  "fields": [
    {
      "fieldName": "Region",
      "fieldType": "TEXT",
      "mandatory": true
    }
  ]
}
```

**Key Compatibility**: The output format matches the field structure in `documents/json_output/*.json` files:
- ✓ Same keys: `fieldName`, `fieldType`, `mandatory`
- ✓ Compatible JSON structure
- ✓ Same field type enum values

## Extraction Results

### Documents Processed

| Document | Fields | Mandatory | File Size |
|----------|--------|-----------|-----------|
| Change Beneficiary - UB 3526.docx | 246 | 62 (25.2%) | 27 KB |
| Complaint KYC - UB - 3803.docx | 140 | 53 (37.9%) | 15 KB |
| KYC Master - UB 3625, 3626, 3630.docx | 47 | 7 (14.9%) | 4.9 KB |
| Outlet_KYC _UB_3334.docx | 303 | 92 (30.4%) | 33 KB |
| Vendor Creation Sample BUD.docx | 350 | 50 (14.3%) | 37 KB |
| **TOTAL** | **1,086** | **264 (24.3%)** | **117 KB** |

### Field Type Distribution

| Field Type | Count | Percentage |
|------------|-------|------------|
| TEXT | 695 | 64.0% |
| FILE | 140 | 12.9% |
| DROPDOWN | 78 | 7.2% |
| PANEL | 78 | 7.2% |
| LABEL | 54 | 5.0% |
| EXTERNAL_DROPDOWN | 22 | 2.0% |
| CHECKBOX | 6 | 0.6% |
| DATE | 5 | 0.5% |
| MOBILE | 3 | 0.3% |
| STATIC_CHECKBOX | 2 | 0.2% |
| MULTI_DROPDOWN | 2 | 0.2% |
| EMAIL | 1 | 0.1% |

## Output Location

All extracted field data is saved in:
```
output/simple_fields/
├── Change Beneficiary - UB 3526_fields.json
├── Complaint KYC - UB - 3803_fields.json
├── KYC Master - UB 3625, 3626, 3630_fields.json
├── Outlet_KYC _UB_3334_fields.json
├── Vendor Creation Sample BUD_fields.json
└── README.md
```

## How It Works

### 1. Document Parsing
- Opens .docx file and parses OOXML structure
- Identifies tables with field definitions by header patterns:
  - "Field Name" + "Field Type" columns (required)
  - "Mandatory" column (optional)

### 2. Field Extraction
- Extracts field name from "Field Name" column
- Maps field type string to `FieldType` enum
- Determines mandatory status from "Mandatory" column:
  - Values like "Yes", "Mandatory", "Y", "1", "true" → `true`
  - Values like "No", "Optional", "N", "0", "false" → `false`
  - Missing column or empty value → `false` (default)

### 3. Deterministic Processing
- Pattern-based table classification (no ML)
- Case-insensitive header matching
- Handles common typos ("Filed Name" vs "Field Name")
- Skips empty or whitespace-only field names
- Excludes fields with UNKNOWN type

### 4. Additional Features
- Processes embedded Excel files for reference data
- Extracts fields by actor (initiator, SPOC, approver)
- Handles nested panel structures
- Merges consecutive duplicate fields

## Comparison with Reference JSON

The files in `documents/json_output/` are full system schemas containing:
- PDF document metadata and base64 encoded content
- Form fill coordinates and positioning
- System validation rules and complex logic
- Database IDs and relationships

Our extraction focuses on **source document content only**:
- Field definitions from Word document tables
- Basic properties: name, type, mandatory
- No system metadata or positioning
- Pure deterministic extraction

### Compatibility Notes

- ✓ **Format Compatible**: Same JSON structure for field objects
- ✓ **Field Types Match**: Type values are consistent
- ⚠️ **Mandatory Differences**: Document-level mandatory may differ from system-level mandatory
  - Document extraction: what's written in the DOCX table
  - System JSON: may include additional business rules or overrides
- ℹ️ **Field Count Differences**: Document may have more/fewer fields than system
  - System may combine/split fields
  - System may add generated fields
  - Document may have fields not yet in system

## Use Cases

This extraction is ideal for:

1. **Documentation**: Understanding field requirements from source documents
2. **Comparison**: Comparing document versions to track changes
3. **Analysis**: Generating field reports and statistics
4. **Validation**: Verifying document structure without system complexity
5. **Migration**: Preparing field mappings for system updates
6. **Auditing**: Checking if system matches document specifications

## Technical Details

### Dependencies
- `python-docx`: OOXML parsing
- `openpyxl`: Embedded Excel file processing (via doc_parser)
- No AI/ML libraries required

### Supported Field Types
All field types defined in `doc_parser.models.FieldType` enum:
- TEXT, DROPDOWN, MULTI_DROPDOWN, DATE, FILE
- CHECKBOX, STATIC_CHECKBOX, MOBILE, EMAIL, NUMBER
- PANEL, LABEL, EXTERNAL_DROPDOWN, UNKNOWN

### Performance
- Processing time: ~10-15 seconds per document
- Total processing: ~60 seconds for 5 documents
- Memory efficient: streams OOXML content

### Error Handling
- Skips invalid tables gracefully
- Continues on parse errors
- Logs processing status
- Reports errors per document

## Deterministic Guarantees

The extraction is **100% deterministic**:
- No randomness or probabilistic methods
- Same input document always produces same output
- No AI/LLM calls or model predictions
- Pure rule-based pattern matching
- Reproducible across runs and environments

This makes it suitable for:
- Automated testing and CI/CD pipelines
- Version control and diff tracking
- Regression testing
- Compliance and audit requirements
