#!/usr/bin/env python3
"""
EDV Output to API Format Converter

This script converts the EDV dispatcher output (panel-based structure) to the
API-compatible vendor_creation.json format with formFillMetadatas and formFillRules.

Input: output/edv_rules/all_panels_edv.json
Output: documents/json_output/vendor_creation.json (or custom path)
"""

import argparse
import json
import uuid
import sys
import re
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


def sanitize_variable_name(field_name: str) -> str:
    """
    Convert field name to variableName format.

    Example: "Search term / Reference Number(Transaction ID)" -> "__search_term_/_reference_number(transaction_id)__"
    """
    # Convert to lowercase
    var_name = field_name.lower()
    # Replace spaces with underscores
    var_name = var_name.replace(" ", "_")
    # Wrap in double underscores
    return f"__{var_name}__"


def generate_short_variable_name(field_name: str, field_id: int) -> str:
    """
    Generate short variable name like "_created68_" or "_transac49_"

    Takes first 7 chars of sanitized name + last 2 digits of ID
    """
    # Get base name (remove special chars)
    base = re.sub(r'[^a-zA-Z]', '', field_name.lower())
    if len(base) > 7:
        base = base[:7]
    elif len(base) < 7:
        base = base.ljust(7, 'x')

    # Get last 2 digits of ID
    id_suffix = str(field_id)[-2:]

    return f"_{base}{id_suffix}_"


def map_field_type_to_form_tag_type(field_type: str) -> str:
    """Map our field types to API formTag types"""
    type_mapping = {
        'TEXT': 'TEXT',
        'TEXTAREA': 'TEXT',
        'EMAIL': 'EMAIL',
        'MOBILE': 'MOBILE',
        'NUMBER': 'NUMBER',
        'DATE': 'DATE',
        'DROPDOWN': 'DROPDOWN',
        'EXTERNAL_DROP_DOWN_VALUE': 'EXTERNAL_DROP_DOWN_VALUE',
        'EXTERNAL_DROP_DOWN_MULTISELECT': 'EXTERNAL_DROP_DOWN_MULTISELECT',
        'CHECK_BOX': 'CHECK_BOX',
        'STATIC_CHECK_BOX': 'STATIC_CHECK_BOX',
        'FILE': 'FILE',
        'MULTIPLE_FILE': 'MULTIPLE_FILE',
        'PANEL': 'PANEL',
        'LABEL': 'LABEL',
        'BUTTON': 'BUTTON'
    }
    return type_mapping.get(field_type, 'TEXT')


def map_rule_name_to_action_type(rule_name: str) -> str:
    """Map rule names to actionType"""
    # Direct mapping for most rules
    action_mapping = {
        'EDV Dropdown (Client)': 'EXT_VALUE',
        'EXT_DROP_DOWN': 'EXT_DROP_DOWN',
        'EXT_VALUE': 'EXT_VALUE',
        'EDV VALIDATION': 'EDV_VALIDATION',
        'Disable Field (Client)': 'MAKE_DISABLED',
        'Make Invisible (Client)': 'MAKE_INVISIBLE',
        'Copy To (Client)': 'COPY_TO',
        'Set Value (Client)': 'SET_VALUE',
        'PAN Validation': 'PAN_VALIDATION',
        'MSME Validation': 'MSME_VALIDATION',
        'GST Validation': 'GST_VALIDATION',
        'Copy Transaction ID': 'COPY_TXNID_TO_FORM_FILL',
        'Set Date': 'SET_DATE',
        'Make Mandatory (Client)': 'MAKE_MANDATORY',
        'Make Optional (Client)': 'MAKE_OPTIONAL',
        'Show Field (Client)': 'SHOW_FIELD',
        'DUMMY_ACTION': 'DUMMY_ACTION'
    }

    return action_mapping.get(rule_name, rule_name.upper().replace(' ', '_'))


def create_form_fill_rule(rule: Dict, field_id: int, id_map: Dict[str, int], rule_id_counter: int) -> Dict:
    """Convert EDV rule to formFillRule format"""
    rule_name = rule.get('rule_name', '')
    action_type = map_rule_name_to_action_type(rule_name)

    # Map source and destination variable names to IDs
    source_fields = rule.get('source_fields', [])
    destination_fields = rule.get('destination_fields', [])

    # Convert variableNames to field IDs
    source_ids = []
    for sf in source_fields:
        if sf in id_map:
            source_ids.append(id_map[sf])
        else:
            # Try to find by looking for the variable name
            print(f"  Warning: Source field '{sf}' not found in ID map, using current field ID")
            source_ids.append(field_id)

    destination_ids = []
    for df in destination_fields:
        if df in id_map:
            destination_ids.append(id_map[df])
        else:
            # Try to find by looking for the variable name
            print(f"  Warning: Destination field '{df}' not found in ID map, using current field ID")
            destination_ids.append(field_id)

    # If no sources, use field itself
    if not source_ids:
        source_ids = [field_id]

    # If no destinations, use empty list
    if not destination_ids:
        destination_ids = []

    # Build base rule with unique rule ID
    form_fill_rule = {
        "id": rule_id_counter,
        "createUser": "FIRST_PARTY",
        "updateUser": "FIRST_PARTY",
        "actionType": action_type,
        "processingType": "CLIENT",
        "sourceIds": source_ids,
        "destinationIds": destination_ids,
        "postTriggerRuleIds": [],
        "button": "",
        "searchable": action_type in ['EXT_DROP_DOWN', 'EXT_VALUE'],
        "executeOnFill": True,
        "executeOnRead": False,
        "executeOnEsign": False,
        "executePostEsign": False,
        "runPostConditionFail": False
    }

    # Add params if present
    if 'params' in rule and rule['params']:
        params = rule['params']

        # If params has conditionList (EDV rules)
        if isinstance(params, dict) and 'conditionList' in params:
            # Remove __reasoning from params before stringifying
            # Also convert variableNames in criterias to field IDs
            condition_list = []
            for cond in params['conditionList']:
                cond_clean = {
                    'ddType': cond.get('ddType', []),
                    'criterias': [],
                    'da': cond.get('da', []),
                    'criteriaSearchAttr': cond.get('criteriaSearchAttr', []),
                    'additionalOptions': cond.get('additionalOptions'),
                    'emptyAddOptionCheck': cond.get('emptyAddOptionCheck'),
                    'ddProperties': cond.get('ddProperties')
                }

                # Convert variableNames in criterias to field IDs
                for criteria in cond.get('criterias', []):
                    criteria_clean = {}
                    for key, value in criteria.items():
                        # value might be a variableName like "__field_name__"
                        if isinstance(value, str) and value.startswith('__') and value.endswith('__'):
                            # It's a variable name, convert to ID
                            if value in id_map:
                                criteria_clean[key] = id_map[value]
                            else:
                                print(f"  Warning: Variable '{value}' in criteria not found in ID map")
                                criteria_clean[key] = value
                        else:
                            criteria_clean[key] = value
                    cond_clean['criterias'].append(criteria_clean)

                condition_list.append(cond_clean)

            params_clean = {'conditionList': condition_list}
            # Stringify the params as JSON for API
            form_fill_rule['params'] = json.dumps([params_clean])
        elif isinstance(params, str):
            # Already a string
            form_fill_rule['params'] = params
        else:
            # Convert to string
            form_fill_rule['params'] = str(params)

    # Add sourceType for EDV rules
    if action_type in ['EXT_DROP_DOWN', 'EXT_VALUE']:
        form_fill_rule['sourceType'] = 'EXTERNAL_DATA_VALUE'

    return form_fill_rule


def convert_edv_to_api_format(edv_data: Dict, bud_filename: str) -> Dict:
    """Convert EDV output to API format"""

    # Start all IDs from 1
    template_id = 1
    template_code = re.sub(r'[^a-zA-Z0-9_]', '_', bud_filename.replace('.docx', '').lower())
    template_name = bud_filename.replace('.docx', '').replace('_', ' ').title()

    # Create base template structure
    template = {
        "id": template_id,
        "templateName": template_name,
        "key": f"TMPTS{template_id:05d}",
        "companyCode": "generated",
        "templateType": "DUAL",
        "workFlowStepId": 1,
        "formFillEnabled": True,
        "expiryDays": 3,
        "previewEnabled": True,
        "state": "PUBLISHED",
        "firstPartyAccess": True,
        "bulkValidation": False,
        "bulkOperation": False,
        "reportQueueEnabled": False,
        "code": template_code,
        "description": f"Generated from {bud_filename}",
        "processNote": "",
        "displayName": template_name,
        "accessViewports": "[desktop, mobile, mobile_app]",
        "workFlowDataNodeData": "{}",  # Simplified workflow
        "documentTypes": []
    }

    # Create document type
    doc_type_id = 1
    doc_type = {
        "id": doc_type_id,
        "createUser": "FIRST_PARTY",
        "updateUser": "FIRST_PARTY",
        "documentType": template_name,
        "displayName": template_name,
        "partyType": "SECOND_PARTY",
        "baseDocumentType": "PDF",
        "desktopLayout": "VERTICAL_TABS",
        "mobileLayout": "VERTICAL_TABS",
        "fileAccept": "image/x-png,image/jpeg,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "maxNumberOfFilesToCollate": -1,
        "saveAs": "application/pdf",
        "formFillEnabled": True,
        "signAllPages": False,
        "mustBeUploadedBy": ["GENERIC_PARTY"],
        "canBeReUploadedBy": ["GENERIC_PARTY"],
        "enabledForBulk": False,
        "maxSizeInBytes": 15728640,
        "code": template_name,
        "baseDocumentStorageType": "AWS_S3",
        "baseDocumentStorageId": str(uuid.uuid4()).replace('-', ''),
        "baseDocumentDownloadable": False,
        "main": True,
        "createSampleBaseDocument": True,
        "uploadMandatory": False,
        "signMandatory": False,
        "formFillMetadatas": []
    }

    # Track variable name to ID mapping - all IDs start from 1
    id_map = {}

    # All ID counters start from 1
    metadata_counter = 1  # formFillMetadata IDs
    form_tag_counter = 1  # formTag IDs
    rule_id_counter = 1  # formFillRule IDs
    sign_metadata_id = 1  # signMetadata ID
    prefill_data_counter = 1  # preFillData IDs
    validation_counter = 1  # formTagValidation IDs
    location_counter = 1  # extendedFormFillLocation IDs
    translation_counter = 1  # formFillMetaTranslation IDs

    form_order = 1.0

    # First pass: Create ID map for all fields
    temp_metadata_counter = metadata_counter
    for panel_name, fields in edv_data.items():
        # Panel gets an ID
        panel_var_name = sanitize_variable_name(panel_name)
        id_map[panel_var_name] = temp_metadata_counter
        temp_metadata_counter += 1

        # Each field gets an ID
        for field in fields:
            variable_name = field.get('variableName', sanitize_variable_name(field.get('field_name', '')))
            id_map[variable_name] = temp_metadata_counter
            temp_metadata_counter += 1

    print(f"Created ID map for {len(id_map)} variables")

    # Process each panel
    for panel_name, fields in edv_data.items():
        # Add panel field first
        panel_id = metadata_counter
        metadata_counter += 1

        panel_form_tag_id = form_tag_counter
        form_tag_counter += 1

        panel_prefill_id = prefill_data_counter
        prefill_data_counter += 1

        panel_var_name = generate_short_variable_name(panel_name, panel_id)

        panel_metadata = {
            "id": panel_id,
            "signMetadataId": sign_metadata_id,
            "upperLeftX": 0.0,
            "upperLeftY": 0.0,
            "lowerRightX": 0.0,
            "lowerRightY": 0.0,
            "page": 1,
            "fontSize": 12,
            "fontStyle": "Courier",
            "mandatory": False,
            "editable": False,
            "formTag": {
                "id": panel_form_tag_id,
                "name": panel_name,
                "standardField": False,
                "type": "PANEL"
            },
            "variableName": panel_var_name,
            "preFillData": {
                "id": panel_prefill_id,
                "name": panel_name,
                "value": ""
            },
            "exportable": False,
            "visible": True,
            "pdfFill": True,
            "formOrder": form_order,
            "exportToBulkTemplate": False,
            "encryptValue": False,
            "formFillDataEnable": False,
            "reportVisible": False,
            "formTagValidations": [],
            "extendedFormFillLocations": [],
            "formFillMetaTranslations": [],
            "formFillRules": []
        }
        doc_type["formFillMetadatas"].append(panel_metadata)
        form_order += 0.0001

        # Process fields in panel
        for field in fields:
            field_metadata_id = metadata_counter
            metadata_counter += 1

            field_form_tag_id = form_tag_counter
            form_tag_counter += 1

            field_prefill_id = prefill_data_counter
            prefill_data_counter += 1

            field_name = field.get('field_name', 'Unknown Field')
            field_type = field.get('type', 'TEXT')
            mandatory = field.get('mandatory', False)
            variable_name = field.get('variableName', sanitize_variable_name(field_name))

            # Map variable name to ID (use the actual metadata ID)
            id_map[variable_name] = field_metadata_id

            # Generate short variable name
            short_var_name = generate_short_variable_name(field_name, field_metadata_id)

            # Create formFillMetadata
            metadata = {
                "id": field_metadata_id,
                "signMetadataId": sign_metadata_id,
                "upperLeftX": 0.0,
                "upperLeftY": 0.0,
                "lowerRightX": 0.0,
                "lowerRightY": 0.0,
                "page": 1,
                "fontSize": 12,
                "fontStyle": "Courier",
                "scaleX": 1.0,
                "scaleY": 1.0,
                "mandatory": mandatory,
                "editable": False,
                "formTag": {
                    "id": field_form_tag_id,
                    "name": field_name,
                    "standardField": False,
                    "type": map_field_type_to_form_tag_type(field_type)
                },
                "variableName": short_var_name,
                "preFillData": {
                    "id": field_prefill_id,
                    "name": field_name,
                    "value": ""
                },
                "groupName": "",
                "helpText": "",
                "placeholder": " ",
                "exportable": False,
                "visible": True,
                "pdfFill": False,
                "formOrder": form_order,
                "exportLabel": "",
                "exportToBulkTemplate": False,
                "characterSpace": 0.0,
                "encryptValue": False,
                "htmlContent": "",
                "formFillDataEnable": False,
                "reportVisible": False,
                "formTagValidations": [],
                "extendedFormFillLocations": [],
                "formFillMetaTranslations": [],
                "formFillRules": []
            }

            # Add rules
            rules = field.get('rules', [])
            for rule in rules:
                form_fill_rule = create_form_fill_rule(rule, field_metadata_id, id_map, rule_id_counter)
                metadata["formFillRules"].append(form_fill_rule)
                rule_id_counter += 1  # Increment rule ID for next rule

            doc_type["formFillMetadatas"].append(metadata)
            form_order += 0.0001

    template["documentTypes"].append(doc_type)

    return {"template": template}


def main():
    parser = argparse.ArgumentParser(
        description="Convert EDV output to API-compatible format"
    )
    parser.add_argument(
        "--input",
        default="output/edv_rules/all_panels_edv.json",
        help="Input EDV JSON file (default: output/edv_rules/all_panels_edv.json)"
    )
    parser.add_argument(
        "--output",
        default="documents/json_output/vendor_creation_generated.json",
        help="Output API JSON file (default: documents/json_output/vendor_creation_generated.json)"
    )
    parser.add_argument(
        "--bud-name",
        default="Vendor Creation",
        help="BUD document name for template naming"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output"
    )

    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"✗ Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Read EDV output
    print(f"Reading EDV output: {args.input}")
    with open(args.input, 'r') as f:
        edv_data = json.load(f)

    print(f"Found {len(edv_data)} panels")
    total_fields = sum(len(fields) for fields in edv_data.values())
    print(f"Total fields: {total_fields}")

    # Convert to API format
    print("\nConverting to API format...")
    api_data = convert_edv_to_api_format(edv_data, args.bud_name)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing output: {args.output}")
    with open(args.output, 'w') as f:
        if args.pretty:
            json.dump(api_data, f, indent=2)
        else:
            json.dump(api_data, f)

    # Print summary
    print("\n" + "="*70)
    print("CONVERSION COMPLETE")
    print("="*70)
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    print(f"\nTemplate Details:")
    print(f"  Name: {api_data['template']['templateName']}")
    print(f"  Code: {api_data['template']['code']}")
    print(f"  ID:   {api_data['template']['id']}")
    print(f"\nDocument Type:")
    doc_type = api_data['template']['documentTypes'][0]
    print(f"  FormFillMetadatas: {len(doc_type['formFillMetadatas'])}")

    # Count rules
    total_rules = sum(
        len(fm['formFillRules'])
        for fm in doc_type['formFillMetadatas']
    )
    print(f"  Total Rules:       {total_rules}")

    # Count EDV rules with params
    edv_rules = sum(
        1 for fm in doc_type['formFillMetadatas']
        for rule in fm['formFillRules']
        if 'params' in rule and 'conditionList' in rule.get('params', '')
    )
    print(f"  EDV Rules w/ Params: {edv_rules}")

    print("="*70)
    print("\n✅ Conversion successful!")


if __name__ == "__main__":
    main()
