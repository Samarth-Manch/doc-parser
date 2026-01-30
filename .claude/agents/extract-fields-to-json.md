# Extract Fields to JSON Agent

This agent creates a deterministic field extractor that parses BUD (Business Understanding Documents) and outputs a JSON schema matching the format in `documents/json_output/`.

## Task Overview

Create a Python script that:
1. Uses the existing `doc_parser` package to parse DOCX files
2. Extracts fields from section 4.4 "Field Level Information" (or similar field definition sections)
3. Maps BUD field types to FormTagType enum values
4. Generates variable names in format `_fieldname_` with duplicate handling
5. Outputs JSON matching the exact structure in `documents/json_output/*.json`

## Input Requirements

- Input: BUD document (.docx file)
- The doc_parser package is already available via `from doc_parser import DocumentParser`
- Field definitions are available via `parsed.all_fields` after parsing

## Output JSON Structure

The output must match this exact structure (see `documents/json_output/3334-schema.json` for reference):

```json
{
  "template": {
    "id": <extracted_from_filename_or_generated>,
    "createUser": "FIRST_PARTY",
    "templateName": "<extracted_from_document>",
    "key": "TMPTS<id_padded_to_5_digits>",
    "companyCode": "ubgroup",
    "templateType": "DUAL",
    "workFlowStepId": 360,
    "formFillEnabled": true,
    "reminderInterval": 1,
    "noOfReminders": 1,
    "expiryDays": 90,
    "remindBeforeDays": 1,
    "remindOnLastDay": true,
    "previewEnabled": true,
    "state": "PUBLISHED",
    "firstPartyAccess": true,
    "bulkValidation": false,
    "bulkOperation": true,
    "reportQueueEnabled": false,
    "code": "<template_name>",
    "accessViewports": "[[desktop, mobile]]",
    "templateTranslations": [],
    "firstPartyPdfMergeEnabled": false,
    "secondPartyPdfMergeEnabled": false,
    "autoCreated": false,
    "documentTypes": [
      {
        "id": 1,
        "createUser": "FIRST_PARTY",
        "updateUser": "FIRST_PARTY",
        "documentType": "<template_name> Process",
        "displayName": "bind this",
        "partyType": "SECOND_PARTY",
        "baseDocumentType": "PDF",
        "desktopLayout": "VERTICAL_TABS",
        "mobileLayout": "HORIZONTAL_TABS",
        "fileAccept": "image/x-png,image/jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "maxNumberOfFilesToCollate": 1,
        "saveAs": "application/pdf",
        "formFillEnabled": true,
        "signAllPages": false,
        "mustBeUploadedBy": ["GENERIC_PARTY"],
        "canBeReUploadedBy": ["GENERIC_PARTY"],
        "enabledForBulk": true,
        "minSizeInBytes": 1024,
        "maxSizeInBytes": 5000000,
        "code": "<template_name>",
        "createSampleBaseDocument": true,
        "uploadMandatory": false,
        "signMandatory": false,
        "pdfMergeEnabledDocumentType": false,
        "formFillMetadatas": [<array_of_field_metadata>]
      }
    ]
  }
}
```

## formFillMetadata Structure

Each field must be converted to this structure:

```json
{
  "id": <sequential_starting_from_1>,
  "upperLeftX": 0.0,
  "upperLeftY": 0.0,
  "lowerRightX": 0.0,
  "lowerRightY": 0.0,
  "page": 1,
  "fontSize": 10,
  "fontStyle": "Times-Roman",
  "scaleX": 1.0,
  "scaleY": 1.0,
  "mandatory": <from_field.is_mandatory>,
  "editable": true,
  "formTag": {
    "id": <same_as_parent_id>,
    "name": "<field_name>",
    "type": "<mapped_form_tag_type>",
    "standardField": false
  },
  "variableName": "<generated_variable_name>",
  "helpText": "",
  "placeholder": "",
  "exportable": false,
  "visible": true,
  "pdfFill": true,
  "formOrder": <float_of_id>,
  "exportLabel": "<field_name>",
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

## CRITICAL: Field Type Mapping

BUD documents may use various field type names that must be mapped to the official FormTagType values. The mapping is crucial:

```python
FIELD_TYPE_TO_FORM_TAG_TYPE = {
    # Basic Input Types
    FieldType.TEXT: "TEXT",
    FieldType.TEXTAREA: "TEXTAREA",
    FieldType.NUMBER: "NUMBER",
    FieldType.DATE: "DATE",
    FieldType.TIME: "TIME",
    FieldType.PASSWORD: "PASSWORD",
    FieldType.MASKED_FIELD: "MASKED_FIELD",
    FieldType.FOUR_DIGITS: "FOUR_DIGITS",

    # Dropdown Types - IMPORTANT: BUD "Dropdown" maps to EXTERNAL_DROP_DOWN_VALUE
    FieldType.DROPDOWN: "EXTERNAL_DROP_DOWN_VALUE",
    FieldType.OPTION: "OPTION",
    FieldType.EXTERNAL_DROP_DOWN_VALUE: "EXTERNAL_DROP_DOWN_VALUE",
    FieldType.EXTERNAL_DROP_DOWN_MULTISELECT: "EXTERNAL_DROP_DOWN_MULTISELECT",
    FieldType.MULTISELECT_EXTERNAL_DROPDOWN: "MULTISELECT_EXTERNAL_DROPDOWN",
    FieldType.EXTERNAL_DROP_DOWN_RADIOBUTTON: "EXTERNAL_DROP_DOWN_RADIOBUTTON",

    # Selection Types
    FieldType.STATIC_CHECK_BOX: "STATIC_CHECK_BOX",
    FieldType.RADIAL_BUTTON: "RADIAL_BUTTON",

    # File Types
    FieldType.FILE: "FILE",
    FieldType.MULTIPLE_FILE: "MULTIPLE_FILE",
    FieldType.IMAGE: "IMAGE",
    FieldType.IMAGE_DISPLAY: "IMAGE_DISPLAY",
    FieldType.IMAGE_VIEW: "IMAGE_VIEW",
    FieldType.PDF: "PDF",
    FieldType.VIDEO: "VIDEO",
    FieldType.VIDEO_NATIVE: "VIDEO_NATIVE",

    # Layout/Grouping Types
    FieldType.PANEL: "PANEL",
    FieldType.GRP_HDR: "GRP_HDR",
    FieldType.GRP_END: "GRP_END",
    FieldType.ROW_HDR: "ROW_HDR",
    FieldType.ROW_END: "ROW_END",
    FieldType.ARRAY_HDR: "ARRAY_HDR",
    FieldType.ARRAY_END: "ARRAY_END",
    FieldType.CARD_HDR: "CARD_HDR",
    FieldType.CARD_END: "CARD_END",

    # Button Types
    FieldType.BUTTON_HDR: "BUTTON_HDR",
    FieldType.BUTTON_END: "BUTTON_END",
    FieldType.BUTTON_ICON: "BUTTON_ICON",
    FieldType.DYNAMIC_BUTTON: "DYNAMIC_BUTTON",
    FieldType.EXECUTE_BUTTON: "EXECUTE_BUTTON",

    # Display Types
    FieldType.LABEL: "LABEL",
    FieldType.COMMENT: "COMMENT",
    FieldType.PREVIEW: "PREVIEW",
    FieldType.HTML_PREVIEW: "HTML_PREVIEW",
    FieldType.TABLE_VIEW: "TABLE_VIEW",
    FieldType.BASE_DOC_VIEW: "BASE_DOC_VIEW",
    FieldType.IFRAME: "IFRAME",

    # Verification Types
    FieldType.PAN: "PAN",
    FieldType.PAN_NUMBER: "PAN_NUMBER",
    FieldType.VOTER_ID: "VOTER_ID",
    FieldType.OTP: "OTP",
    FieldType.OTP_BOX: "OTP_BOX",

    # Video KYC Types
    FieldType.VIDEO_KYC: "VIDEO_KYC",
    FieldType.VIDEO_KYC_RECORD: "VIDEO_KYC_RECORD",
    FieldType.VIDEO_AGENT_KYC: "VIDEO_AGENT_KYC",

    # Audio Types
    FieldType.AUDIO: "AUDIO",
    FieldType.AUDIO_OTP: "AUDIO_OTP",
    FieldType.AUDIO_FORM_FILL: "AUDIO_FORM_FILL",
    FieldType.AUDIO_RECORD: "AUDIO_RECORD",

    # Location Types
    FieldType.STATIC_LOCATION: "STATIC_LOCATION",
    FieldType.DYNAMIC_LOCATION: "DYNAMIC_LOCATION",
    FieldType.COMPASS_DIRECTION: "COMPASS_DIRECTION",
    FieldType.ADVANCE_MAP: "ADVANCE_MAP",

    # Special Types
    FieldType.FORMULA: "FORMULA",
    FieldType.VARIABLE: "VARIABLE",
    FieldType.ACTION: "ACTION",
    FieldType.QR_SCANNER: "QR_SCANNER",
    FieldType.CONTENT_VALUE_INFO: "CONTENT_VALUE_INFO",

    # Payment Types
    FieldType.MAKE_PAYMENT: "MAKE_PAYMENT",
    FieldType.CHECK_PAYMENT: "CHECK_PAYMENT",
    FieldType.MAKE_ESTAMP: "MAKE_ESTAMP",

    # Notes Types
    FieldType.NOTES: "NOTES",
    FieldType.NOTE_HISTORY: "NOTE_HISTORY",

    # Legacy types - map to closest FormTagType equivalent
    FieldType.MOBILE: "NUMBER",
    FieldType.EMAIL: "TEXT",

    # Fallback
    FieldType.UNKNOWN: "TEXT",
}
```

## Variable Name Generation Rules

1. Convert field name to lowercase
2. Remove all non-alphanumeric characters
3. Wrap with underscores: `_fieldname_`
4. For duplicates, append incrementing numbers before the trailing underscore:
   - First occurrence: `_fieldname_`
   - Second occurrence: `_fieldname1_`
   - Third occurrence: `_fieldname2_`

Example:
- "Pan Status" -> `_panstatus_`
- "Pan Status" (duplicate) -> `_panstatus1_`
- "PAN Number" -> `_pannumber_`

## Template ID Extraction

1. Try to extract a 4-digit ID from the filename (e.g., "3625" from "KYC Master - UB 3625.docx")
2. If not found, generate using: `abs(hash(doc_name)) % 10000`

## Template Name Extraction

1. Remove file extension
2. Remove ID patterns like "UB 3625" or "- 3625"
3. Clean up extra spaces and trailing dashes

## Implementation Steps

1. Read `doc_parser/models.py` to understand `FieldType` enum and `FieldDefinition` dataclass
2. Read sample outputs in `documents/json_output/*.json` to understand exact format
3. Create the field extractor script with:
   - Field type mapping dictionary
   - Variable name generator with duplicate handling
   - Template ID/name extractors
   - formFillMetadata creator
   - Main extraction function
4. The script should accept a docx path as argument and output to `output/complete_format/`

## Files to Reference

- `doc_parser/models.py` - FieldType enum and FieldDefinition class
- `doc_parser/parser.py` - DocumentParser class
- `documents/json_output/3334-schema.json` - Sample output format
- `documents/json_output/3625-schema.json` - Another sample output

## Key Constraints

1. **Deterministic**: No AI/ML, only pattern matching and mapping
2. **No Rules**: Only extract fields with text descriptions, no formFillRules processing
3. **Exact Format**: JSON must match the sample outputs exactly
4. **IDs Start from 1**: All IDs (id, formTag.id) start from 1 and increment
5. **FormTagType Only**: Field types must be from the official FormTagType enum, not raw BUD values
