# Schema Format Field Extraction

This directory contains field extractions in the **exact same format** as `documents/json_output/` files.

## Overview

The extraction matches the reference schema structure with proper nesting:
```
template
└── documentTypes[]
    └── formFillMetadatas[]
        └── formTag
```

## Output Format

Each JSON file follows this structure (matching `documents/json_output/*.json`):

```json
{
  "template": {
    "id": 3625,
    "templateName": "KYC Master",
    "key": "TMPTS03625",
    "companyCode": "ubgroup",
    "documentTypes": [
      {
        "id": 36250,
        "documentType": "KYC Master Process",
        "formFillMetadatas": [
          {
            "id": 36250001,
            "mandatory": false,
            "formTag": {
              "id": 362501,
              "name": "Group Owner Outlet Code",
              "type": "TEXT"
            }
          }
        ]
      }
    ]
  }
}
```

## Format Verification

✓ **Top-level structure**: `{ "template": {...} }`
✓ **Template level**: `id`, `templateName`, `key`, `companyCode`, `documentTypes[]`
✓ **DocumentType level**: `id`, `documentType`, `formFillMetadatas[]`
✓ **FormFillMetadata level**: `id`, `mandatory`, `formTag{}`
✓ **FormTag level**: `id`, `name`, `type`

### Comparison with Reference Files

| Aspect | Our Output | Reference Files | Match |
|--------|-----------|-----------------|-------|
| Structure | template.documentTypes[].formFillMetadatas[] | Same | ✓ 100% |
| Essential fields | id, mandatory, formTag | Present | ✓ 100% |
| Field keys | name, type, id | Present | ✓ 100% |
| Extra fields | None | PDF coords, styling, validations, etc. | Reference has more |

**Note**: Reference files contain additional system-specific fields for PDF rendering, form positioning, validations, and business logic. Our extraction focuses only on the core field definitions extracted from the source documents.

## Extracted Files

| File | Template ID | Document | Fields |
|------|------------|----------|--------|
| 3526-schema.json | 3526 | Change Beneficiary - UB 3526 | 246 |
| 3625-schema.json | 3625 | KYC Master - UB 3625, 3626, 3630 | 47 |
| 3703-schema.json | 3703 | Vendor Creation Sample BUD | 350 |
| 3803-schema.json | 3803 | Complaint KYC - UB - 3803 | 140 |
| 9618-schema.json | 9618 | Outlet_KYC _UB_3334 | 303 |
| **TOTAL** | - | **5 documents** | **1,086** |

## Field Structure

Each field in `formFillMetadatas` contains:

### Required Properties
- **id** (number): Unique identifier for the form fill metadata
- **mandatory** (boolean): Whether the field is required
- **formTag** (object): Contains the field definition
  - **id** (number): Unique identifier for the form tag
  - **name** (string): Field name as it appears in the document
  - **type** (string): Field type enum value

### Field Types
- TEXT, DROPDOWN, MULTI_DROPDOWN, DATE, FILE
- CHECKBOX, STATIC_CHECKBOX, MOBILE, EMAIL, NUMBER
- PANEL, LABEL, EXTERNAL_DROPDOWN

## ID Generation

IDs are deterministically generated based on template ID:

- **Template ID**: Extracted from document filename (e.g., "3625" from "UB 3625")
- **DocumentType ID**: `templateId * 10` (e.g., 36250)
- **FormFillMetadata ID**: `templateId * 10000 + fieldIndex` (e.g., 36250001)
- **FormTag ID**: `templateId * 100 + fieldIndex` (e.g., 362501)

This ensures:
- Consistent IDs across runs
- No collisions between documents
- Easy traceability back to source document

## Usage

### Processing All Documents
```bash
python3 extract_fields_schema_format.py
```

### Processing Specific Document
```bash
python3 extract_fields_schema_format.py path/to/document.docx
```

### Custom Output Directory
```bash
python3 extract_fields_schema_format.py document.docx custom/output/dir
```

## Use Cases

This format is ideal for:

1. **System Integration**: Direct compatibility with existing schema parsers
2. **API Responses**: Can be consumed by systems expecting this format
3. **Database Import**: Structure matches database table relationships
4. **Validation**: Compare document-derived schemas with system schemas
5. **Migration**: Prepare data for system updates or database migrations

## Technical Notes

### Deterministic Extraction
- 100% reproducible - same input always produces same output
- No randomness or AI/ML processing
- Pure OOXML table parsing

### Template Name Extraction
Cleans document filename to extract template name:
- Removes ID patterns (e.g., "UB 3625, 3626, 3630")
- Cleans extra spaces, commas, dashes
- Preserves meaningful name parts

### Mandatory Detection
Parses mandatory column values:
- "Yes", "Mandatory", "Y", "1", "true" → `true`
- "No", "Optional", "N", "0", "false" → `false`
- Empty or missing → `false` (default)

### Field Type Mapping
Maps document strings to standardized type enums:
- Handles variations (e.g., "Multi Dropdown" → "MULTI_DROPDOWN")
- Case-insensitive matching
- Unknown types are excluded from output

## Differences from Reference Files

Reference files in `documents/json_output/` include additional properties not extracted from documents:

### Template Level
- Access control settings (firstPartyAccess, accessViewports)
- Workflow configuration (workFlowStepId, state)
- Feature flags (formFillEnabled, reportQueueEnabled)
- System configurations and metadata

### DocumentType Level
- PDF settings (baseDocument, signMetadatas)
- Upload constraints (maxSizeInBytes, fileAccept)
- Layout settings (desktopLayout, mobileLayout)
- Rule definitions and validations

### FormFillMetadata Level
- PDF positioning (upperLeftX, upperLeftY, page)
- Font styling (fontSize, fontStyle)
- Form behavior (editable, visible, exportable)
- Variable names and group assignments
- Validation rules and translations

Our extraction focuses on **document-derived field definitions only**, making it:
- Simpler to generate and maintain
- Easier to understand and validate
- Focused on source document content
- Free from system-specific configuration

## Integration Tips

If integrating with a system that expects the full reference format:

1. **Use as Base**: Start with our extracted schema
2. **Add Defaults**: Populate system-specific fields with defaults
3. **Enhance**: Add PDF coordinates, validations, etc. as needed
4. **Validate**: Compare field lists to ensure completeness

Example enhancement:
```python
# Our extraction
base_field = {
    "id": 36250001,
    "mandatory": false,
    "formTag": {"id": 362501, "name": "...", "type": "TEXT"}
}

# Enhanced with system defaults
enhanced_field = {
    **base_field,
    "editable": True,
    "visible": True,
    "exportable": True,
    "fontSize": 12,
    "fontStyle": "Courier",
    # ... etc
}
```
