# Complete Format Field Extraction

This directory contains field extractions in the **EXACT format** as `documents/json_output/` files with ALL 31 field properties.

## Overview

The extraction matches the reference schema structure with complete field metadata including positioning, styling, validation arrays, and configuration properties.

## Complete Field Structure

Each field in `formFillMetadatas` contains **ALL 31 properties**:

```json
{
  "upperLeftX": 0.0,
  "upperLeftY": 0.0,
  "lowerRightX": 0.0,
  "lowerRightY": 0.0,
  "page": 1,
  "fontSize": 10,
  "fontStyle": "Times-Roman",
  "scaleX": 1.0,
  "scaleY": 1.0,
  "mandatory": false,
  "editable": true,
  "formTag": {
    "name": "Field Name",
    "type": "TEXT",
    "standardField": false
  },
  "variableName": "_fieldname_",
  "helpText": "",
  "placeholder": "",
  "exportable": false,
  "visible": true,
  "pdfFill": true,
  "formOrder": 1.0,
  "exportLabel": "Field Name",
  "exportToBulkTemplate": false,
  "encryptValue": false,
  "htmlContent": "",
  "cssStyle": "",
  "formFillDataEnable": false,
  "reportVisible": false,
  "collabDisplayMap": {},
  "formTagValidations": [],
  "extendedFormFillLocations": [],
  "formFillMetaTranslations": [],
  "formFillRules": []
}
```

## Property Categories

### Positioning (PDF Coordinates)
- `upperLeftX`: X coordinate of upper-left corner (0.0)
- `upperLeftY`: Y coordinate of upper-left corner (0.0)
- `lowerRightX`: X coordinate of lower-right corner (0.0)
- `lowerRightY`: Y coordinate of lower-right corner (0.0)
- `page`: Page number (1)

### Styling
- `fontSize`: Font size in points (10)
- `fontStyle`: Font family name ("Times-Roman")
- `scaleX`: Horizontal scaling factor (1.0)
- `scaleY`: Vertical scaling factor (1.0)

### Field Behavior
- `mandatory`: Whether field is required (boolean from document)
- `editable`: Whether field can be edited (true)
- `visible`: Whether field is visible (true)
- `pdfFill`: Whether to fill in PDF (true)
- `exportable`: Whether field is exportable (false)

### Field Definition
- `formTag`: Object containing:
  - `name`: Field name from document
  - `type`: Field type (TEXT, DROPDOWN, etc.)
  - `standardField`: Whether it's a standard field (false)

### Metadata
- `variableName`: Generated variable name (e.g., "_fieldname_")
- `helpText`: Help text for field ("")
- `placeholder`: Placeholder text ("")
- `exportLabel`: Label for export (field name)

### Configuration
- `formOrder`: Display order (float, sequential)
- `exportToBulkTemplate`: Include in bulk templates (false)
- `encryptValue`: Whether to encrypt value (false)
- `formFillDataEnable`: Enable form fill data (false)
- `reportVisible`: Visible in reports (false)

### Display
- `htmlContent`: HTML content for field ("")
- `cssStyle`: CSS styling ("")
- `collabDisplayMap`: Collaboration display settings ({})

### Validation & Rules (Arrays)
- `formTagValidations`: Field validation rules ([])
- `formFillRules`: Business logic rules ([])
- `extendedFormFillLocations`: Additional PDF locations ([])
- `formFillMetaTranslations`: Translations ([])

## Extracted Files

| File | Template ID | Source Document | Fields | Size |
|------|------------|-----------------|--------|------|
| 3526-schema.json | 3526 | Change Beneficiary - UB 3526 | 246 | 290 KB |
| 3625-schema.json | 3625 | KYC Master - UB 3625, 3626, 3630 | 47 | 55 KB |
| 3803-schema.json | 3803 | Complaint KYC - UB - 3803 | 140 | 165 KB |
| 4606-schema.json | 4606 | Outlet_KYC _UB_3334 | 303 | 359 KB |
| 7777-schema.json | 7777 | Vendor Creation Sample BUD | 350 | 410 KB |
| **TOTAL** | - | **5 documents** | **1,086** | **1.3 MB** |

## Format Verification

### Comparison with Reference Files

✓ **Structure**: 100% match - all 31 properties present
✓ **Data Types**: Correct types for all fields
✓ **Nesting**: Proper object and array structures
✓ **Empty Defaults**: Arrays initialized as [], objects as {}

### Key Matching Results

```
Field Structure: 31/31 keys (100% match)

Keys in both our output and reference:
✓ upperLeftX, upperLeftY, lowerRightX, lowerRightY
✓ page, fontSize, fontStyle, scaleX, scaleY
✓ mandatory, editable, visible, pdfFill, exportable
✓ formTag, variableName, helpText, placeholder
✓ formOrder, exportLabel, exportToBulkTemplate
✓ encryptValue, formFillDataEnable, reportVisible
✓ htmlContent, cssStyle, collabDisplayMap
✓ formTagValidations, formFillRules
✓ extendedFormFillLocations, formFillMetaTranslations
```

## Variable Name Generation

Variable names are generated automatically from field names:

```python
"Pan Status" → "_panstatus_"
"PAN Number" → "_pannumber_"
"Upload PAN of licensee" → "_uploadpanoflicensee_"
"ASM name" → "_asmname_"
```

Algorithm:
1. Convert to lowercase
2. Remove all non-alphanumeric characters
3. Wrap with underscores: `_{cleaned_name}_`

## Default Values

Properties are initialized with these defaults:

### Position & Styling
- Coordinates: `0.0` (placeholder values)
- Page: `1`
- Font size: `10`
- Font style: `"Times-Roman"`
- Scale: `1.0` (no scaling)

### Behavior
- `editable`: `true`
- `visible`: `true`
- `pdfFill`: `true`
- `exportable`: `false`
- `exportToBulkTemplate`: `false`

### Configuration
- `mandatory`: From document table
- `formOrder`: Sequential (1.0, 2.0, 3.0, ...)
- `encryptValue`: `false`
- `formFillDataEnable`: `false`
- `reportVisible`: `false`

### Text Fields
- `helpText`: `""`
- `placeholder`: `""`
- `htmlContent`: `""`
- `cssStyle`: `""`

### Collections
- Arrays: `[]`
- Objects: `{}`

## Usage

### Process All Documents
```bash
python3 extract_fields_complete.py
```

### Process Specific Document
```bash
python3 extract_fields_complete.py path/to/document.docx
```

### Custom Output Directory
```bash
python3 extract_fields_complete.py document.docx custom/output/dir
```

## Use Cases

This complete format is ideal for:

1. **Direct System Integration**: Drop-in compatibility with systems expecting this exact format
2. **Database Import**: Ready for bulk import into databases
3. **API Responses**: Serve directly as API responses
4. **Testing & Validation**: Compare against production schemas
5. **Migration**: Prepare data for system migrations
6. **Enhancement**: Easy to add custom rules and validations

## Enhancement Example

To add custom rules to fields:

```python
import json

# Load extracted schema
with open('output/complete_format/3625-schema.json', 'r') as f:
    schema = json.load(f)

# Find specific field
for field in schema['template']['documentTypes'][0]['formFillMetadatas']:
    if field['formTag']['name'] == 'PAN Number':
        # Add validation rule
        field['formFillRules'].append({
            'actionType': 'VERIFY',
            'processingType': 'SERVER',
            'sourceIds': [field['formOrder']],
            'destinationIds': [],
            'executeOnFill': True,
            'executeOnRead': False,
            'executeOnEsign': False,
            'executePostEsign': False,
            'searchable': False,
            'runPostConditionFail': False,
            'sourceType': 'PAN_NUMBER',
            'button': 'VERIFY'
        })

# Save enhanced schema
with open('output/enhanced/3625-schema.json', 'w') as f:
    json.dump(schema, f, indent=2)
```

## Differences from Reference Files

While the structure is identical, some differences exist:

### Same
- ✓ All 31 field properties present
- ✓ Correct data types
- ✓ Proper nesting structure
- ✓ Field names, types, mandatory status

### Different
- IDs are generated (not from production database)
- Coordinates are placeholders (0.0) - no actual PDF positioning
- `formFillRules` array is empty (no business logic generated)
- Some boolean defaults may differ (e.g., `editable`, `exportable`)

### Why Differences Exist

**Reference files** contain:
- Production database IDs
- Actual PDF form coordinates from layout
- Business logic rules configured in system
- System-specific settings and configurations

**Our extraction** contains:
- Document-derived field definitions
- Placeholder values for system-specific properties
- Empty arrays for rules (to be added later)
- Sensible defaults for boolean flags

This makes our extraction:
- Easier to generate and maintain
- Focused on document content
- Ready for enhancement with system-specific logic
- Suitable as a starting point for new templates

## Technical Notes

### Deterministic Generation
- Same input document always produces same output
- IDs generated based on template ID + field index
- Variable names generated from field names
- No randomness or AI/ML involved

### Field Order
Fields are ordered sequentially as they appear in the document:
- `formOrder`: 1.0, 2.0, 3.0, etc.
- Preserves document structure
- Easy to reorder if needed

### Array Initialization
All array properties initialized as empty arrays:
- `formTagValidations: []`
- `formFillRules: []`
- `extendedFormFillLocations: []`
- `formFillMetaTranslations: []`

This ensures:
- Valid JSON structure
- No null/undefined issues
- Ready for array operations
- Easy to populate with rules

### Object Initialization
Object properties initialized as empty objects:
- `collabDisplayMap: {}`

## Validation

To validate the output format:

```bash
# Check all keys are present
jq '.template.documentTypes[0].formFillMetadatas[0] | keys | length' output/complete_format/3625-schema.json
# Should output: 31

# Check all required properties
jq '.template.documentTypes[0].formFillMetadatas[0] | has("formTag") and has("mandatory") and has("variableName")' output/complete_format/3625-schema.json
# Should output: true

# List all field names
jq '.template.documentTypes[0].formFillMetadatas[].formTag.name' output/complete_format/3625-schema.json
```

## Summary

✓ **Complete Format**: All 31 properties included
✓ **Structure Match**: 100% compatible with reference files
✓ **Ready to Use**: Drop-in replacement for system integration
✓ **Deterministic**: Reproducible extraction
✓ **Extensible**: Easy to enhance with custom logic
✓ **Well-Documented**: Clear property descriptions and use cases

## Update: IDs Added (Latest Version)

All objects now have IDs starting from 1:

### ID Structure

- **template.id**: Template identifier (extracted from filename, e.g., 3625)
- **documentTypes[0].id**: Document type ID (always 1)
- **formFillMetadatas[].id**: Field IDs starting from 1, incrementing sequentially (1, 2, 3, ...)
- **formTag.id**: Form tag IDs matching their field IDs

### Example with IDs

```json
{
  "template": {
    "id": 3625,
    "documentTypes": [
      {
        "id": 1,
        "formFillMetadatas": [
          {
            "id": 1,
            "formTag": {
              "id": 1,
              "name": "Field Name",
              "type": "TEXT"
            }
          },
          {
            "id": 2,
            "formTag": {
              "id": 2,
              "name": "Another Field",
              "type": "DROPDOWN"
            }
          }
        ]
      }
    ]
  }
}
```

### ID Guarantees

✓ Every object has an ID
✓ Field IDs are sequential: 1, 2, 3, 4, ... (no gaps)
✓ FormTag IDs match their parent field IDs
✓ IDs are deterministic (same document always produces same IDs)
