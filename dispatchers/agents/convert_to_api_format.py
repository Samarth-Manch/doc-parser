#!/usr/bin/env python3
"""
EDV Output to API Format Converter

This script converts the EDV dispatcher output (panel-based structure) to the
API-compatible vendor_creation.json format with formFillMetadatas and formFillRules.

Supports two modes:
  1. Inject mode (--schema): Takes an existing API schema with empty formFillRules
     and injects EDV rules into matching fields.
  2. Legacy mode (no --schema): Builds the entire API template from scratch.

Input: output/edv_rules/all_panels_edv.json
Output: documents/json_output/vendor_creation.json (or custom path)
"""

import argparse
import copy
import json
import uuid
import sys
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
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


def load_rule_schemas(schema_path: str = None) -> Dict[str, Dict]:
    """
    Load Rule-Schemas.json and build a lookup by rule name.

    Returns:
        Dict mapping rule name -> {id, actionType, processingType}
    """
    if schema_path is None:
        # Default: rules/Rule-Schemas.json relative to project root
        candidates = [
            Path(__file__).parent.parent.parent / "rules" / "Rule-Schemas.json",
            Path("rules/Rule-Schemas.json"),
        ]
        for p in candidates:
            if p.exists():
                schema_path = str(p)
                break
        else:
            print("  Warning: Rule-Schemas.json not found, using fallback mapping")
            return {}

    with open(schema_path, 'r') as f:
        raw = json.load(f)

    # Handle paginated format ({"content": [...]}) or flat array
    if isinstance(raw, dict) and 'content' in raw:
        schemas = raw['content']
    elif isinstance(raw, list):
        schemas = raw
    else:
        print(f"  Warning: Unexpected Rule-Schemas.json format")
        return {}

    rule_map = {}
    action_map = {}  # actionType -> first matching schema entry (fallback)
    for entry in schemas:
        name = entry.get('name', '')
        action = entry.get('action', '')
        if name:
            info = {
                'id': entry.get('id'),
                'actionType': action,
                'processingType': entry.get('processingType', 'CLIENT'),
                'sourceType': entry.get('source', ''),
                'button': entry.get('button', ''),
            }
            rule_map[name] = info
            # Build reverse lookup: actionType -> schema entry (first match wins)
            if action and action not in action_map:
                action_map[action] = info

    # Store the action_map for fallback lookups
    rule_map['__action_map__'] = action_map

    return rule_map


# Module-level cache so we only load once
_rule_schemas_cache = None


def get_rule_schemas() -> Dict[str, Dict]:
    """Get cached rule schemas, loading on first call."""
    global _rule_schemas_cache
    if _rule_schemas_cache is None:
        _rule_schemas_cache = load_rule_schemas()
        if _rule_schemas_cache:
            print(f"Loaded {len(_rule_schemas_cache)} rule definitions from Rule-Schemas.json")
    return _rule_schemas_cache


def create_form_fill_rule(rule: Dict, field_id: int, id_map: Dict[str, int], rule_id_counter: int) -> Dict:
    """
    Convert EDV rule to formFillRule format.

    Looks up rule_name in Rule-Schemas.json for correct actionType and processingType.
    Output structure matches the reference vendor_creation.json exactly.
    """
    rule_name = rule.get('rule_name', '')
    rule_schemas = get_rule_schemas()

    # Look up rule in Rule-Schemas.json by name first, then by action type
    schema_entry = rule_schemas.get(rule_name)
    if not schema_entry:
        action_map = rule_schemas.get('__action_map__', {})
        schema_entry = action_map.get(rule_name)

    if schema_entry:
        action_type = schema_entry['actionType']
        processing_type = schema_entry['processingType']
        source_type = schema_entry.get('sourceType', '')
        button = schema_entry.get('button', '')
    else:
        print(f"  Warning: Rule '{rule_name}' not found in Rule-Schemas.json")
        action_type = rule_name.upper().replace(' ', '_')
        processing_type = 'CLIENT'
        source_type = ''
        button = ''

    # Map source and destination variable names to IDs
    source_fields = rule.get('source_fields', [])
    destination_fields = rule.get('destination_fields', [])

    source_ids = []
    for sf in source_fields:
        if sf in id_map:
            source_ids.append(id_map[sf])
        else:
            print(f"  Warning: Source field '{sf}' not found in ID map, using current field ID")
            source_ids.append(field_id)

    destination_ids = []
    for df in destination_fields:
        if df in id_map:
            destination_ids.append(id_map[df])
        else:
            print(f"  Warning: Destination field '{df}' not found in ID map, using current field ID")
            destination_ids.append(field_id)

    # If no sources, use field itself
    if not source_ids:
        source_ids = [field_id]

    # Build rule matching reference vendor_creation.json structure
    form_fill_rule = {
        "id": rule_id_counter,
        "createUser": "FIRST_PARTY",
        "updateUser": "FIRST_PARTY",
        "actionType": action_type,
        "processingType": processing_type,
        "sourceIds": source_ids,
        "destinationIds": destination_ids,
        "postTriggerRuleIds": [],
        "button": button if button else "",
        "searchable": action_type in ['EXT_DROP_DOWN', 'EXT_VALUE'],
        "executeOnFill": True,
        "executeOnRead": False,
        "executeOnEsign": False,
        "executePostEsign": False,
        "runPostConditionFail": False,
    }

    # Add sourceType from Rule-Schemas (maps schema "source" -> API "sourceType")
    # Only add when the schema defines a source (None means not applicable)
    if source_type and source_type != 'N/A':
        form_fill_rule['sourceType'] = source_type

    # Add conditional fields only when they have values
    conditional_values = rule.get('conditional_values', [])
    condition = rule.get('condition', '')
    if conditional_values or condition:
        form_fill_rule["conditionalValues"] = conditional_values if conditional_values else []
        form_fill_rule["condition"] = condition if condition else "IN"
        form_fill_rule["conditionValueType"] = "TEXT"

    # Add params if present
    if 'params' in rule and rule['params']:
        params = rule['params']

        if isinstance(params, dict) and 'conditionList' in params:
            condition_list = []
            for cond in params['conditionList']:
                cond_clean = {
                    'ddType': cond.get('ddType', []),
                    'criterias': [],
                    'da': cond.get('da', []),
                    'criteriaSearchAttr': cond.get('criteriaSearchAttr', []),
                    'additionalOptions': cond.get('additionalOptions'),
                    'emptyAddOptionCheck': cond.get('emptyAddOptionCheck'),
                    'ddProperties': cond.get('ddProperties'),
                }

                # Convert variableNames in criterias to field IDs
                for criteria in cond.get('criterias', []):
                    criteria_clean = {}
                    for key, value in criteria.items():
                        if isinstance(value, str) and value.startswith('__') and value.endswith('__'):
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
            form_fill_rule['params'] = json.dumps([params_clean])
        elif isinstance(params, str):
            form_fill_rule['params'] = params
        else:
            form_fill_rule['params'] = json.dumps(params)

    return form_fill_rule


def _build_schema_panel_map(metadatas: List[Dict]) -> Dict[str, Dict[str, int]]:
    """
    Build (panel_name, field_name) -> metadata index from schema.

    Schema fields are ordered: PANEL, then its children, then next PANEL, etc.
    Returns nested dict: panel_name -> {field_name -> metadata_index}
    Also returns a flat dict for unique field names (no duplicates).
    """
    panel_field_map = {}   # panel_name -> {field_name -> index}
    current_panel = None

    for idx, meta in enumerate(metadatas):
        ft = meta.get('formTag', {})
        name = ft.get('name', '')
        ftype = ft.get('type', '')

        if ftype == 'PANEL':
            current_panel = name
            if current_panel not in panel_field_map:
                panel_field_map[current_panel] = {}
        elif current_panel and name:
            panel_field_map[current_panel][name] = idx

    return panel_field_map


def build_id_map_from_schema(schema_data: Dict, edv_data: Dict) -> Dict[str, int]:
    """
    Build a mapping from EDV variableNames to schema formFillMetadata IDs.

    Uses (panel_name, field_name) for duplicate fields, and formTag.name for unique ones.
    This ensures fields like "Street" in "PAN and GST Details" vs "Address Details"
    map to the correct schema ID.

    Returns:
        Dict mapping variableName (e.g. "__field_name__") -> schema metadata ID
    """
    metadatas = schema_data['template']['documentTypes'][0]['formFillMetadatas']
    panel_field_map = _build_schema_panel_map(metadatas)

    # Also build flat name -> id for panels themselves
    panel_id_map = {}
    for meta in metadatas:
        ft = meta.get('formTag', {})
        if ft.get('type') == 'PANEL' and ft.get('name'):
            panel_id_map[ft['name']] = meta['id']

    id_map = {}
    for panel_name, fields in edv_data.items():
        # Map panel variableName to its schema ID
        panel_var_name = sanitize_variable_name(panel_name)
        if panel_name in panel_id_map:
            id_map[panel_var_name] = panel_id_map[panel_name]

        # Get this panel's field map from schema
        schema_fields_in_panel = panel_field_map.get(panel_name, {})

        for field in fields:
            field_name = field.get('field_name', '')
            variable_name = field.get('variableName', sanitize_variable_name(field_name))

            if field_name in schema_fields_in_panel:
                meta_idx = schema_fields_in_panel[field_name]
                id_map[variable_name] = metadatas[meta_idx]['id']

    return id_map


def inject_rules_into_schema(schema_data: Dict, edv_data: Dict) -> Tuple[Dict, Dict]:
    """
    Inject EDV rules into an existing API schema.

    Takes a schema with empty formFillRules arrays and populates them
    with rules from the EDV data, matching fields by (panel_name, field_name).

    Returns:
        Tuple of (modified schema dict, stats dict)
    """
    result = copy.deepcopy(schema_data)
    metadatas = result['template']['documentTypes'][0]['formFillMetadatas']

    # Build panel-scoped lookup from schema
    panel_field_map = _build_schema_panel_map(metadatas)

    # Build ID map for variable name -> schema ID resolution (panel-aware)
    id_map = build_id_map_from_schema(schema_data, edv_data)
    print(f"Built ID map: {len(id_map)} variable names mapped to schema IDs")

    # Find the max existing rule ID in the schema to continue from
    rule_id_counter = 1
    for meta in metadatas:
        for rule in meta.get('formFillRules', []):
            if rule.get('id', 0) >= rule_id_counter:
                rule_id_counter = rule['id'] + 1

    # Stats tracking
    fields_matched = 0
    fields_with_rules = 0
    fields_unmatched = []
    total_rules_injected = 0

    # Inject rules into matching fields (panel-scoped)
    for panel_name, fields in edv_data.items():
        schema_fields_in_panel = panel_field_map.get(panel_name, {})

        for field in fields:
            field_name = field.get('field_name', '')
            rules = field.get('rules', [])

            if field_name not in schema_fields_in_panel:
                if rules:
                    fields_unmatched.append(f"{field_name} (panel: {panel_name})")
                continue

            fields_matched += 1
            if not rules:
                continue

            fields_with_rules += 1
            meta_idx = schema_fields_in_panel[field_name]
            field_id = metadatas[meta_idx]['id']

            for rule in rules:
                form_fill_rule = create_form_fill_rule(rule, field_id, id_map, rule_id_counter)
                metadatas[meta_idx]['formFillRules'].append(form_fill_rule)
                rule_id_counter += 1
                total_rules_injected += 1

    stats = {
        'fields_matched': fields_matched,
        'fields_with_rules': fields_with_rules,
        'fields_unmatched': fields_unmatched,
        'total_rules_injected': total_rules_injected,
        'total_schema_fields': len(metadatas),
        'fields_with_empty_rules': sum(
            1 for m in metadatas if not m.get('formFillRules')
        ),
    }

    return result, stats


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
        "autoCreated": False,
        "firstPartyPdfMergeEnabled": False,
        "secondPartyPdfMergeEnabled": False,
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
        "pdfMergeEnabledDocumentType": False,
        "ruleDefinitions": [],
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

            # Create formFillMetadata (fields have preFillData, panels don't)
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
        description="Convert EDV output to API-compatible format. "
                    "Use --schema to inject rules into an existing schema, "
                    "or omit it for legacy full-build mode."
    )
    parser.add_argument(
        "--schema",
        help="Existing API schema JSON with empty formFillRules (inject mode)"
    )
    parser.add_argument(
        "--rules", "--input",
        dest="input",
        default="output/edv_rules/all_panels_edv.json",
        help="Input EDV rules JSON file (default: output/edv_rules/all_panels_edv.json)"
    )
    parser.add_argument(
        "--output",
        default="documents/json_output/vendor_creation_generated.json",
        help="Output API JSON file (default: documents/json_output/vendor_creation_generated.json)"
    )
    parser.add_argument(
        "--bud-name",
        default="Vendor Creation",
        help="BUD document name for template naming (legacy mode only)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output"
    )

    args = parser.parse_args()

    # Validate EDV rules input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Read EDV rules
    print(f"Reading EDV rules: {args.input}")
    with open(args.input, 'r') as f:
        edv_data = json.load(f)

    print(f"Found {len(edv_data)} panels")
    total_fields = sum(len(fields) for fields in edv_data.values())
    total_edv_rules = sum(
        len(field.get('rules', []))
        for fields in edv_data.values()
        for field in fields
    )
    print(f"Total fields: {total_fields}, Total rules: {total_edv_rules}")

    if args.schema:
        # --- Inject mode: merge rules into existing schema ---
        schema_path = Path(args.schema)
        if not schema_path.exists():
            print(f"Error: Schema file not found: {args.schema}", file=sys.stderr)
            sys.exit(1)

        print(f"Reading schema: {args.schema}")
        with open(args.schema, 'r') as f:
            schema_data = json.load(f)

        schema_fields = len(schema_data['template']['documentTypes'][0]['formFillMetadatas'])
        print(f"Schema fields: {schema_fields}")

        print("\nInjecting rules into schema...")
        api_data, stats = inject_rules_into_schema(schema_data, edv_data)

        # Print inject-mode summary
        print("\n" + "="*70)
        print("INJECTION COMPLETE")
        print("="*70)
        print(f"Schema:  {args.schema}")
        print(f"Rules:   {args.input}")
        print(f"Output:  {args.output}")
        print(f"\nResults:")
        print(f"  Schema fields:          {stats['total_schema_fields']}")
        print(f"  EDV fields matched:     {stats['fields_matched']}")
        print(f"  Fields with rules:      {stats['fields_with_rules']}")
        print(f"  Rules injected:         {stats['total_rules_injected']}")
        print(f"  Fields still empty:     {stats['fields_with_empty_rules']}")
        if stats['fields_unmatched']:
            print(f"  Unmatched EDV fields:   {len(stats['fields_unmatched'])}")
            for name in stats['fields_unmatched']:
                print(f"    - {name}")
        print("="*70)
    else:
        # --- Legacy mode: build from scratch ---
        print("\nConverting to API format (legacy mode)...")
        api_data = convert_edv_to_api_format(edv_data, args.bud_name)

        # Print legacy-mode summary
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

        total_rules = sum(
            len(fm['formFillRules'])
            for fm in doc_type['formFillMetadatas']
        )
        print(f"  Total Rules:       {total_rules}")

        edv_rules = sum(
            1 for fm in doc_type['formFillMetadatas']
            for rule in fm['formFillRules']
            if 'params' in rule and 'conditionList' in rule.get('params', '')
        )
        print(f"  EDV Rules w/ Params: {edv_rules}")
        print("="*70)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting output: {args.output}")
    with open(args.output, 'w') as f:
        if args.pretty:
            json.dump(api_data, f, indent=2)
        else:
            json.dump(api_data, f)

    print("Done!")


if __name__ == "__main__":
    main()
