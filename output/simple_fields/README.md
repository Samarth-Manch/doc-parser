# Simple Field Extraction Output

This directory contains deterministic field extractions from Word documents (.docx).

## Overview

The extraction focuses on three core properties for each field:
- **fieldName**: The name of the field as defined in the document
- **fieldType**: The type of field (TEXT, DROPDOWN, DATE, FILE, etc.)
- **mandatory**: Whether the field is required (true/false)

## Output Format

Each JSON file follows this structure:

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
    },
    {
      "fieldName": "Outlet Code",
      "fieldType": "DROPDOWN",
      "mandatory": true
    }
  ]
}
```

## Extraction Summary

| Document | Fields Extracted | Output File |
|----------|-----------------|-------------|
| Change Beneficiary - UB 3526.docx | 246 | Change Beneficiary - UB 3526_fields.json |
| Complaint KYC - UB - 3803.docx | 140 | Complaint KYC - UB - 3803_fields.json |
| KYC Master - UB 3625, 3626, 3630.docx | 47 | KYC Master - UB 3625, 3626, 3630_fields.json |
| Outlet_KYC _UB_3334.docx | 303 | Outlet_KYC _UB_3334_fields.json |
| Vendor Creation Sample BUD.docx | 350 | Vendor Creation Sample BUD_fields.json |
| **TOTAL** | **1,086** | **5 files** |

## Field Types

The following field types are detected:

- **TEXT** - Single line text input
- **DROPDOWN** - Single selection dropdown
- **MULTI_DROPDOWN** - Multiple selection dropdown
- **DATE** - Date picker
- **FILE** - File upload
- **CHECKBOX** - Checkbox
- **STATIC_CHECKBOX** - Read-only checkbox
- **MOBILE** - Mobile number
- **EMAIL** - Email address
- **NUMBER** - Numeric input
- **PANEL** - Grouping container
- **LABEL** - Display-only label
- **EXTERNAL_DROPDOWN** - Dropdown with external data source
- **UNKNOWN** - Unrecognized type

## Deterministic Extraction

This extraction is **fully deterministic** and requires **no AI/LLM processing**:

- Parses OOXML structure directly from .docx files
- Identifies field definition tables by header patterns
- Extracts field properties from table columns
- Handles embedded Excel files for reference data
- No rules generation (rules require separate AI processing)

## How It Works

The extraction uses the existing `DocumentParser` class which:

1. Opens the .docx file and parses OOXML structure
2. Identifies tables with field definitions by matching header patterns:
   - "Field Name" + "Field Type" columns
   - Optional "Mandatory" column
3. Extracts field properties deterministically:
   - Name from "Field Name" column
   - Type from "Field Type" column (mapped to enum)
   - Mandatory status from "Mandatory" column (if present)
4. Processes embedded Excel files for dropdown reference data
5. Outputs clean JSON with only essential field information

## Usage

To regenerate or process new documents:

```bash
# Process all documents in documents/ directory
python3 extract_fields_simple.py

# Process a specific document
python3 extract_fields_simple.py path/to/document.docx

# Process a specific document with custom output directory
python3 extract_fields_simple.py path/to/document.docx custom/output/dir
```

## Notes

- Mandatory status is only extracted when a "Mandatory" column exists in the table
- If no mandatory column is present, all fields default to `mandatory: false`
- The extraction is case-insensitive for header matching
- Handles common header variations and typos (e.g., "Filed Name" vs "Field Name")
- Empty or whitespace-only field names are skipped
- Fields with UNKNOWN type are excluded from output

## Comparison with documents/json_output

The files in `documents/json_output/` contain full system schemas with:
- PDF document metadata and base64 encoded content
- Form fill coordinates and positioning
- Validation rules and complex logic
- System-level configurations
- Database IDs and relationships

This extraction focuses only on the **source document content**:
- Field definitions as written in the Word document
- Basic properties: name, type, mandatory
- No system metadata or PDF positioning
- Pure deterministic extraction from DOCX tables

This makes it ideal for:
- Documenting field requirements
- Comparing document versions
- Generating field reports
- Understanding document structure without system complexity
