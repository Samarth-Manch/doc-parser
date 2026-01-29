#!/usr/bin/env python3
"""
Field extractor that outputs in EXACT format matching documents/json_output.
Includes all properties: positioning, styling, validation arrays, etc.
"""

import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Any
from doc_parser import DocumentParser
from doc_parser.models import FieldType


# Mapping from internal FieldType to FormTagType enum values
# FormTagType is the target Java enum that the output JSON must use
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

    # Dropdown Types - KEY MAPPINGS
    FieldType.DROPDOWN: "EXTERNAL_DROP_DOWN_VALUE",  # BUD "Dropdown" -> FormTagType
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
    FieldType.MOBILE: "NUMBER",  # Mobile numbers are numeric
    FieldType.EMAIL: "TEXT",     # Email is text input

    # Fallback
    FieldType.UNKNOWN: "TEXT",   # Default to TEXT for unknown types
}


def get_form_tag_type(field_type: FieldType) -> str:
    """
    Convert internal FieldType to FormTagType enum string.

    Args:
        field_type: The internal FieldType enum value

    Returns:
        String matching the FormTagType Java enum
    """
    return FIELD_TYPE_TO_FORM_TAG_TYPE.get(field_type, "TEXT")


def generate_variable_name(field_name: str) -> str:
    """
    Generate variable name from field name in the format: _fieldname_
    Examples:
    - "Pan Status" -> "_panstatus_"
    - "PAN Number" -> "_pannumber_"
    - "Upload PAN of licensee" -> "_uploadpanoflicensee_"
    """
    # Convert to lowercase
    var_name = field_name.lower()
    # Remove special characters, keep only alphanumeric
    var_name = re.sub(r'[^a-z0-9]', '', var_name)
    # Add underscores
    return f"_{var_name}_"


def generate_template_id(doc_name: str) -> int:
    """Generate a template ID from document name (extract existing ID if present)."""
    # Try to extract existing template ID from filename (e.g., "3625" from "KYC Master - UB 3625")
    match = re.search(r'\b(\d{4})\b', doc_name)
    if match:
        return int(match.group(1))
    # Otherwise generate a hash-based ID
    return abs(hash(doc_name)) % 10000


def extract_template_name(doc_name: str) -> str:
    """Extract template name from document filename."""
    # Remove file extension
    name = Path(doc_name).stem
    # Remove ID patterns like "UB 3625, 3626, 3630" or "- 3625"
    name = re.sub(r'\s*-?\s*UB\s*[\d,\s]+', '', name)
    name = re.sub(r'\s*-?\s*[\d,\s]+$', '', name)
    # Clean up extra spaces, commas, and dashes
    name = re.sub(r'\s*-\s*$', '', name)
    name = re.sub(r',+', ',', name)  # Multiple commas to single
    name = re.sub(r',\s*$', '', name)  # Trailing commas
    name = re.sub(r'\s+', ' ', name).strip()
    return name if name else Path(doc_name).stem


def create_form_fill_metadata(field, field_index: int, variable_name: str) -> Dict[str, Any]:
    """
    Create a complete formFillMetadata object with ALL properties including IDs.
    Matches exact structure from documents/json_output/*.json
    IDs start from 1 and increment sequentially.

    Args:
        field: FieldDefinition object
        field_index: Field index (1-based)
        variable_name: Pre-generated variable name (may include number suffix for duplicates)
    """
    return {
        "id": field_index,  # ID starts from 1
        "upperLeftX": 0.0,
        "upperLeftY": 0.0,
        "lowerRightX": 0.0,
        "lowerRightY": 0.0,
        "page": 1,
        "fontSize": 10,
        "fontStyle": "Times-Roman",
        "scaleX": 1.0,
        "scaleY": 1.0,
        "mandatory": field.is_mandatory,
        "editable": True,  # Default to editable
        "formTag": {
            "id": field_index,  # FormTag ID matches field index
            "name": field.name,
            "type": get_form_tag_type(field.field_type),  # Map to FormTagType enum
            "standardField": False
        },
        "variableName": variable_name,  # Use pre-generated variable name with duplicate handling
        "helpText": "",
        "placeholder": "",
        "exportable": False,
        "visible": True,
        "pdfFill": True,
        "formOrder": float(field_index),
        "exportLabel": field.name,
        "exportToBulkTemplate": False,
        "encryptValue": False,
        "htmlContent": "",
        "cssStyle": "",
        "formFillDataEnable": False,
        "reportVisible": False,
        "collabDisplayMap": {},
        "formTagValidations": [],
        "extendedFormFillLocations": [],
        "formFillMetaTranslations": [],
        "formFillRules": []
    }


def extract_fields_complete(docx_path: str) -> Dict[str, Any]:
    """
    Extract fields in the EXACT format of documents/json_output/*.json files.
    Includes all properties: positioning, styling, validation arrays, etc.

    Args:
        docx_path: Path to the DOCX file

    Returns:
        Dictionary matching the complete template schema with all properties
    """
    parser = DocumentParser()
    parsed = parser.parse(docx_path)

    doc_name = Path(docx_path).name
    template_id = generate_template_id(doc_name)
    template_name = extract_template_name(doc_name)

    # Build formFillMetadatas array with ALL properties
    # Track variable names to handle duplicates
    variable_name_counts = {}  # Track count per base name
    used_variable_names = set()  # Track all used variable names to prevent collisions
    form_fill_metadatas = []

    for idx, field in enumerate(parsed.all_fields, start=1):
        # Generate base variable name
        base_var_name = generate_variable_name(field.name)

        # Handle duplicates by adding incrementing numbers
        if base_var_name in variable_name_counts:
            # This is a duplicate - find next available number
            count = variable_name_counts[base_var_name]
            # Try incrementing numbers until we find one that's not used
            while True:
                # Remove trailing underscore, add number, add underscore back
                final_var_name = f"{base_var_name[:-1]}{count}_"
                if final_var_name not in used_variable_names:
                    break
                count += 1
            variable_name_counts[base_var_name] = count + 1
        else:
            # First occurrence - but check if it's already used (collision with numbered variant)
            final_var_name = base_var_name
            if final_var_name in used_variable_names:
                # Collision! Start numbering from 1
                count = 1
                while True:
                    final_var_name = f"{base_var_name[:-1]}{count}_"
                    if final_var_name not in used_variable_names:
                        break
                    count += 1
                variable_name_counts[base_var_name] = count + 1
            else:
                variable_name_counts[base_var_name] = 1

        # Mark this variable name as used
        used_variable_names.add(final_var_name)

        metadata = create_form_fill_metadata(field, idx, final_var_name)
        form_fill_metadatas.append(metadata)

    # Build the complete schema structure with all properties
    schema = {
        "template": {
            "id": template_id,
            "createUser": "FIRST_PARTY",
            "templateName": template_name,
            "key": f"TMPTS{template_id:05d}",
            "companyCode": "ubgroup",
            "templateType": "DUAL",
            "workFlowStepId": 360,
            "formFillEnabled": True,
            "reminderInterval": 1,
            "noOfReminders": 1,
            "expiryDays": 90,
            "remindBeforeDays": 1,
            "remindOnLastDay": True,
            "previewEnabled": True,
            "state": "PUBLISHED",
            "firstPartyAccess": True,
            "bulkValidation": False,
            "bulkOperation": True,
            "reportQueueEnabled": False,
            "code": template_name,
            "accessViewports": "[[desktop, mobile]]",
            "templateTranslations": [],
            "firstPartyPdfMergeEnabled": False,
            "secondPartyPdfMergeEnabled": False,
            "autoCreated": False,
            "documentTypes": [
                {
                    "id": 1,
                    "createUser": "FIRST_PARTY",
                    "updateUser": "FIRST_PARTY",
                    "documentType": f"{template_name} Process",
                    "displayName": "bind this",
                    "partyType": "SECOND_PARTY",
                    "baseDocumentType": "PDF",
                    "desktopLayout": "VERTICAL_TABS",
                    "mobileLayout": "HORIZONTAL_TABS",
                    "fileAccept": "image/x-png,image/jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "maxNumberOfFilesToCollate": 1,
                    "saveAs": "application/pdf",
                    "formFillEnabled": True,
                    "signAllPages": False,
                    "mustBeUploadedBy": ["GENERIC_PARTY"],
                    "canBeReUploadedBy": ["GENERIC_PARTY"],
                    "enabledForBulk": True,
                    "minSizeInBytes": 1024,
                    "maxSizeInBytes": 5000000,
                    "code": template_name,
                    "createSampleBaseDocument": True,
                    "uploadMandatory": False,
                    "signMandatory": False,
                    "pdfMergeEnabledDocumentType": False,
                    "formFillMetadatas": form_fill_metadatas
                }
            ]
        }
    }

    return schema


def process_document(docx_path: str, output_dir: str = "output/complete_format") -> str:
    """
    Process a single document and save the output in complete schema format.

    Args:
        docx_path: Path to the DOCX file
        output_dir: Directory to save output JSON

    Returns:
        Path to the output JSON file
    """
    docx_path_obj = Path(docx_path)

    if not docx_path_obj.exists():
        raise FileNotFoundError(f"Document not found: {docx_path}")

    print(f"Processing: {docx_path_obj.name}")

    # Extract fields in complete schema format
    schema = extract_fields_complete(str(docx_path_obj))

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate output filename matching the pattern: <id>-schema.json
    template_id = schema['template']['id']
    output_file = output_path / f"{template_id}-schema.json"

    # Save output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    num_fields = len(schema['template']['documentTypes'][0]['formFillMetadatas'])
    print(f"  ✓ Extracted {num_fields} fields")
    print(f"  ✓ Template ID: {template_id}")
    print(f"  ✓ Saved to: {output_file}")

    return str(output_file)


def process_all_documents(
    input_dir: str = "documents",
    output_dir: str = "output/complete_format",
    pattern: str = "*.docx"
) -> List[str]:
    """
    Process all DOCX documents in a directory.

    Args:
        input_dir: Directory containing DOCX files
        output_dir: Directory to save output JSON files
        pattern: File pattern to match (default: *.docx)

    Returns:
        List of output file paths
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Find all DOCX files
    docx_files = list(input_path.glob(pattern))

    if not docx_files:
        print(f"No DOCX files found in {input_dir}")
        return []

    print(f"Found {len(docx_files)} document(s) to process\n")

    output_files = []
    for docx_file in sorted(docx_files):
        try:
            output_file = process_document(str(docx_file), output_dir)
            output_files.append(output_file)
            print()
        except Exception as e:
            print(f"  ✗ Error processing {docx_file.name}: {e}")
            print()

    return output_files


def main():
    """Main entry point for the script."""
    if len(sys.argv) > 1:
        # Process specific file
        docx_path = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "output/complete_format"
        process_document(docx_path, output_dir)
    else:
        # Process all documents in the documents directory
        output_files = process_all_documents()

        if output_files:
            print("=" * 60)
            print(f"Successfully processed {len(output_files)} document(s)")
            print(f"Output saved to: output/complete_format/")


if __name__ == "__main__":
    main()
