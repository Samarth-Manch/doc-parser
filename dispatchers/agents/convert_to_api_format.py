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
        'BUTTON': 'BUTTON',
        'ARRAY_HDR': 'ARRAY_HDR',
        'ARRAY_END': 'ARRAY_END'
    }
    return type_mapping.get(field_type, 'TEXT')


def set_header_metadata_ids(metadatas: List[Dict]) -> int:
    """
    Set headerMetadataId on fields between ARRAY_HDR and ARRAY_END.

    Fields between an ARRAY_HDR and its matching ARRAY_END (inclusive of
    ARRAY_END) get headerMetadataId set to the ARRAY_HDR's id.

    Returns:
        Number of fields updated
    """
    updated = 0
    array_hdr_id = None

    for meta in metadatas:
        ftype = meta.get('formTag', {}).get('type', '')

        if ftype == 'ARRAY_HDR':
            array_hdr_id = meta['id']
        elif ftype == 'ARRAY_END':
            if array_hdr_id is not None:
                meta['headerMetadataId'] = array_hdr_id
                updated += 1
            array_hdr_id = None
        elif array_hdr_id is not None:
            meta['headerMetadataId'] = array_hdr_id
            updated += 1

    return updated


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


def _has_yes_no_params(rules: List[Dict]) -> bool:
    """
    Check if any rule in the list has YES_NO or YES_NO_OPTIONS in its params.

    Args:
        rules: List of rule dicts from EDV data

    Returns:
        True if any rule has YES_NO or YES_NO_OPTIONS in params
    """
    for rule in rules:
        params = rule.get('params', '')
        if isinstance(params, str):
            if 'YES_NO' in params or 'YES_NO_OPTIONS' in params:
                return True
        elif isinstance(params, dict):
            params_str = str(params)
            if 'YES_NO' in params_str or 'YES_NO_OPTIONS' in params_str:
                return True
    return False


def _resolve_variable_to_id(variable_name: str, current_panel: str, panel_field_map: Dict[str, Dict[str, List[int]]],
                           metadatas: List[Dict], global_id_map: Dict[str, int], field_id: int,
                           edv_data: Dict = None) -> int:
    """
    Resolve a variable name to a field ID with panel-scoped priority.

    Resolution order:
    1. Check if variable is in the current panel (panel-scoped lookup by field name)
    2. Check global ID map (cross-panel lookup)
    3. Fall back to current field ID

    Args:
        variable_name: The variable name to resolve (e.g., "__street__")
        current_panel: The name of the panel containing the current field
        panel_field_map: Dict mapping panel_name -> {field_name -> metadata_index}
        metadatas: List of all metadata entries
        global_id_map: Global variable name -> ID map (fallback)
        field_id: Current field ID (last resort fallback)
        edv_data: EDV data dict (optional, for better field name matching)

    Returns:
        The resolved field ID
    """
    # Special case: -1 passes through
    if variable_name == "-1":
        return -1

    # First, try to find in current panel
    # Strategy: Look up the field_name from EDV data that corresponds to this variable_name,
    # then find that field_name in the schema panel
    if current_panel in panel_field_map and edv_data and current_panel in edv_data:
        # Find the field_name in EDV data that has this variable_name
        target_field_name = None
        for field in edv_data[current_panel]:
            field_var = field.get('variableName', '')
            if field_var == variable_name:
                target_field_name = field.get('field_name', '')
                break

        # If found, look up this field_name in the schema panel
        if target_field_name and target_field_name in panel_field_map[current_panel]:
            idx_list = panel_field_map[current_panel][target_field_name]
            # Use the first occurrence; for duplicates the variableName-based
            # fallback below will match the correct one after injection has
            # already written the input variableNames onto the metadatas.
            return metadatas[idx_list[0]]['id']

    # Fallback: Check all fields in current panel by variableName matching
    if current_panel in panel_field_map:
        for field_name, idx_list in panel_field_map[current_panel].items():
            for meta_idx in idx_list:
                meta = metadatas[meta_idx]
                meta_var_name = meta.get('variableName', '')
                if meta_var_name == variable_name:
                    return meta['id']

    # Second, check global ID map (cross-panel lookup)
    if variable_name in global_id_map:
        return global_id_map[variable_name]

    # Last resort: use current field ID
    print(f"  Warning: Variable '{variable_name}' not found in panel '{current_panel}' or globally, using current field ID")
    return field_id


def create_form_fill_rule(rule: Dict, field_id: int, id_map: Dict[str, int], rule_id_counter: int,
                          current_panel: str = None, panel_field_map: Dict = None, metadatas: List[Dict] = None,
                          edv_data: Dict = None):
    """
    Convert EDV rule to formFillRule format.

    Looks up rule_name in Rule-Schemas.json for correct actionType and processingType.
    Output structure matches the reference vendor_creation.json exactly.

    Args:
        rule: The rule dict from EDV data
        field_id: The current field's metadata ID
        id_map: Global variable name -> ID mapping (fallback)
        rule_id_counter: The rule ID to assign
        current_panel: Name of the panel containing this field (for panel-scoped resolution)
        panel_field_map: Panel-scoped field lookup (panel_name -> {field_name -> meta_idx})
        metadatas: List of all metadata entries (for panel-scoped resolution)
        edv_data: EDV data dict (for better field name matching in panel-scoped resolution)

    Returns:
        Dict containing the rule, or None if the rule doesn't exist in Rule-Schemas.json
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
        print(f"  Warning: Rule '{rule_name}' not found in Rule-Schemas.json - skipping")
        return None

    # Map source and destination variable names to IDs
    source_fields = rule.get('source_fields', [])
    destination_fields = rule.get('destination_fields', [])

    # Use panel-aware resolution if panel context is available
    use_panel_aware = (current_panel is not None and panel_field_map is not None and metadatas is not None)

    source_ids = []
    for sf in source_fields:
        if use_panel_aware:
            resolved_id = _resolve_variable_to_id(sf, current_panel, panel_field_map, metadatas, id_map, field_id, edv_data)
            source_ids.append(resolved_id)
        else:
            # Fallback to simple lookup
            if sf == "-1":
                source_ids.append(-1)
            elif sf in id_map:
                source_ids.append(id_map[sf])
            else:
                print(f"  Warning: Source field '{sf}' not found in ID map, using current field ID")
                source_ids.append(field_id)

    destination_ids = []
    for df in destination_fields:
        if use_panel_aware:
            resolved_id = _resolve_variable_to_id(df, current_panel, panel_field_map, metadatas, id_map, field_id, edv_data)
            destination_ids.append(resolved_id)
        else:
            # Fallback to simple lookup
            if df == "-1":
                destination_ids.append(-1)
            elif df in id_map:
                destination_ids.append(id_map[df])
            else:
                print(f"  Warning: Destination field '{df}' not found in ID map, using current field ID")
                destination_ids.append(field_id)

    # If no sources, use field itself
    if not source_ids:
        source_ids = [field_id]

    # Handle special cases for -1 source fields
    if -1 in source_ids:
        # 1. For COPY_TO rules: if source is -1, remove the rule
        if action_type == 'COPY_TO':
            print(f"  Warning: Rule '{rule_name}' (COPY_TO) has source field -1, removing rule")
            return None
        # 2. For VERIFY with sourceType EXTERNAL_DATA_VALUE: if source is -1, remove the rule
        elif action_type == 'VERIFY' and source_type == 'EXTERNAL_DATA_VALUE':
            print(f"  Warning: Rule '{rule_name}' (VERIFY with EXTERNAL_DATA_VALUE) has source field -1, removing rule")
            return None
        # 3. For Make Disabled rules: if source is -1, use destination fields as source
        elif 'DISABLED' in action_type or 'DISABLE' in action_type:
            print(f"  Info: Rule '{rule_name}' ({action_type}) has source field -1, using destination fields as source")
            source_ids = destination_ids if destination_ids else [field_id]

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
    # Support both camelCase (from agent output) and snake_case keys
    conditional_values = rule.get('conditionalValues', rule.get('conditional_values', []))
    condition = rule.get('condition', '')
    condition_value_type = rule.get('conditionValueType', 'TEXT')
    if conditional_values or condition:
        form_fill_rule["conditionalValues"] = conditional_values if conditional_values else []
        form_fill_rule["condition"] = condition if condition else "IN"
        form_fill_rule["conditionValueType"] = condition_value_type

    # Add params if present
    if 'params' in rule and rule['params']:
        params = rule['params']

        if isinstance(params, dict) and 'param' in params and 'conditionList' in params:
            # Validate EDV (Server) params format:
            # {"param": "TABLE_NAME", "conditionList": [{"conditionNumber": 2, "conditionType": "IN", ...}]}
            # Pass through as-is (already in correct structure), just JSON-stringify
            params_clean = {
                'param': params['param'],
                'conditionList': params['conditionList']
            }
            form_fill_rule['params'] = json.dumps(params_clean)
        elif isinstance(params, dict) and 'conditionList' in params:
            # EDV Dropdown (Client) params format:
            # {"conditionList": [{"ddType": [...], "criterias": [...], "da": [...], ...}]}
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
                raw_criterias = cond.get('criterias', [])
                if isinstance(raw_criterias, str):
                    # Agent wrote criterias as a raw string (e.g. "TABLE$$col$$__var__")
                    # Pass through as-is; replace any variableName tokens with IDs
                    parts = raw_criterias.split('$$')
                    resolved = []
                    for part in parts:
                        if part.startswith('__') and part.endswith('__') and part in id_map:
                            resolved.append(str(id_map[part]))
                        else:
                            resolved.append(part)
                    cond_clean['criterias'] = '$$'.join(resolved)
                else:
                    for criteria in raw_criterias:
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

    # Remove all fields starting with underscore (internal/debug fields like _reasoning, _dropdown_type)
    form_fill_rule = {k: v for k, v in form_fill_rule.items() if not k.startswith('_')}

    return form_fill_rule


def _build_schema_panel_map(metadatas: List[Dict]) -> Dict[str, Dict[str, List[int]]]:
    """
    Build (panel_name, field_name) -> list of metadata indices from schema.

    Schema fields are ordered: PANEL, then its children, then next PANEL, etc.
    Returns nested dict: panel_name -> {field_name -> [index, ...]}
    Duplicate field names within a panel produce multiple indices in order.
    """
    panel_field_map = {}   # panel_name -> {field_name -> [indices]}
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
            panel_field_map[current_panel].setdefault(name, []).append(idx)

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
        # Map panel variableName to its schema ID (panels don't have variableName in input, derive it)
        panel_var_name = sanitize_variable_name(panel_name)
        if panel_name in panel_id_map:
            id_map[panel_var_name] = panel_id_map[panel_name]

        # Get this panel's field map from schema
        schema_fields_in_panel = panel_field_map.get(panel_name, {})

        # Track how many times we've seen each field_name to match Nth input
        # occurrence to Nth schema occurrence
        seen_counts = {}
        for field in fields:
            field_name = field.get('field_name', '')
            variable_name = field.get('variableName', '')

            if field_name in schema_fields_in_panel:
                idx_list = schema_fields_in_panel[field_name]
                occurrence = seen_counts.get(field_name, 0)
                if occurrence < len(idx_list):
                    meta_idx = idx_list[occurrence]
                    id_map[variable_name] = metadatas[meta_idx]['id']
                seen_counts[field_name] = occurrence + 1

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

    # Find max existing IDs in the schema to continue from
    max_metadata_id = max((m['id'] for m in metadatas), default=0)
    max_form_tag_id = max((m.get('formTag', {}).get('id', 0) for m in metadatas), default=0)
    max_prefill_id = 0
    for m in metadatas:
        pf = m.get('preFillData', {})
        if isinstance(pf, dict) and pf.get('id', 0) > max_prefill_id:
            max_prefill_id = pf['id']

    new_metadata_counter = max_metadata_id + 1
    new_form_tag_counter = max_form_tag_id + 1
    new_prefill_counter = max_prefill_id + 1

    # Stats tracking
    fields_matched = 0
    fields_with_rules = 0
    fields_unmatched = []
    total_rules_injected = 0

    # Inject rules into matching fields (panel-scoped)
    for panel_name, fields in edv_data.items():
        schema_fields_in_panel = panel_field_map.get(panel_name, {})

        # Track how many times we've seen each field_name to match Nth input
        # occurrence to Nth schema occurrence (handles duplicate field names)
        seen_counts = {}
        for field in fields:
            field_name = field.get('field_name', '')
            rules = field.get('rules', [])
            variable_name = field.get('variableName', '')

            if field_name not in schema_fields_in_panel:
                # RuleCheck is a session-based control field added by the
                # session_based_dispatcher — create a new metadata entry for it
                if field_name == 'RuleCheck' and rules:
                    new_field_id = new_metadata_counter
                    new_metadata_counter += 1
                    new_ftag_id = new_form_tag_counter
                    new_form_tag_counter += 1
                    new_pf_id = new_prefill_counter
                    new_prefill_counter += 1

                    id_map[variable_name] = new_field_id

                    new_meta = {
                        "id": new_field_id,
                        "signMetadataId": metadatas[0].get('signMetadataId', 1) if metadatas else 1,
                        "upperLeftX": 0.0, "upperLeftY": 0.0,
                        "lowerRightX": 0.0, "lowerRightY": 0.0,
                        "page": 1, "fontSize": 12, "fontStyle": "Courier",
                        "scaleX": 1.0, "scaleY": 1.0,
                        "mandatory": False, "editable": False,
                        "formTag": {
                            "id": new_ftag_id,
                            "name": field_name,
                            "standardField": False,
                            "type": "TEXT"
                        },
                        "variableName": variable_name,
                        "preFillData": {"id": new_pf_id, "name": field_name, "value": ""},
                        "groupName": "", "helpText": "", "placeholder": " ",
                        "exportable": False, "visible": True, "pdfFill": False,
                        "formOrder": 0.0, "exportLabel": "",
                        "exportToBulkTemplate": False, "characterSpace": 0.0,
                        "encryptValue": False, "htmlContent": "",
                        "formFillDataEnable": False, "reportVisible": False,
                        "formTagValidations": [], "extendedFormFillLocations": [],
                        "formFillMetaTranslations": [], "formFillRules": []
                    }

                    for rule in rules:
                        form_fill_rule = create_form_fill_rule(rule, new_field_id, id_map, rule_id_counter,
                                                               current_panel=panel_name, panel_field_map=panel_field_map,
                                                               metadatas=metadatas, edv_data=edv_data)
                        if form_fill_rule is not None:
                            new_meta['formFillRules'].append(form_fill_rule)
                            rule_id_counter += 1
                            total_rules_injected += 1

                    # Insert right after the panel header
                    panel_idx = next(
                        (i for i, m in enumerate(metadatas)
                         if m.get('formTag', {}).get('name') == panel_name
                         and m.get('formTag', {}).get('type') == 'PANEL'),
                        None
                    )
                    if panel_idx is not None:
                        metadatas.insert(panel_idx + 1, new_meta)
                        panel_field_map = _build_schema_panel_map(metadatas)
                    else:
                        metadatas.append(new_meta)

                    fields_matched += 1
                    fields_with_rules += 1
                    print(f"  Created RuleCheck field (id={new_field_id}) in panel '{panel_name}' with {len(rules)} session rules")
                    continue

                if rules:
                    fields_unmatched.append(f"{field_name} (panel: {panel_name})")
                continue

            fields_matched += 1
            idx_list = schema_fields_in_panel[field_name]
            occurrence = seen_counts.get(field_name, 0)
            seen_counts[field_name] = occurrence + 1
            if occurrence < len(idx_list):
                meta_idx = idx_list[occurrence]
            else:
                # More input occurrences than schema — fall back to last
                meta_idx = idx_list[-1]
            field_id = metadatas[meta_idx]['id']

            # Always update variableName from input (overwrite whatever the schema had)
            if variable_name:
                metadatas[meta_idx]['variableName'] = variable_name
                # Keep id_map in sync with updated variableName
                id_map[variable_name] = field_id

            # Inject existing rules
            if rules:
                fields_with_rules += 1
                for rule in rules:
                    form_fill_rule = create_form_fill_rule(rule, field_id, id_map, rule_id_counter,
                                                           current_panel=panel_name, panel_field_map=panel_field_map,
                                                           metadatas=metadatas, edv_data=edv_data)
                    if form_fill_rule is not None:
                        metadatas[meta_idx]['formFillRules'].append(form_fill_rule)
                        rule_id_counter += 1
                        total_rules_injected += 1

                # Check if any rule has YES_NO params and update prefill value
                if _has_yes_no_params(rules):
                    if 'preFillData' in metadatas[meta_idx] and metadatas[meta_idx]['preFillData']:
                        metadatas[meta_idx]['preFillData']['value'] = 'No'
                        print(f"  Set prefill value to 'No' for field '{field_name}' (has YES_NO params)")

    # Set headerMetadataId on fields between ARRAY_HDR and ARRAY_END
    array_fields_updated = set_header_metadata_ids(metadatas)
    if array_fields_updated:
        print(f"  Set headerMetadataId on {array_fields_updated} fields inside ARRAY sections")

    # Sync ARRAY_END variableNames from their paired ARRAY_HDR (ARRAY_END
    # entries don't exist in the input, so they keep stale schema values)
    array_hdr_var = None
    array_ends_synced = 0
    for meta in metadatas:
        ftype = meta.get('formTag', {}).get('type', '')
        if ftype == 'ARRAY_HDR':
            array_hdr_var = meta.get('variableName', '')
        elif ftype == 'ARRAY_END':
            if array_hdr_var and meta.get('variableName', '') != array_hdr_var:
                meta['variableName'] = array_hdr_var
                array_ends_synced += 1
            array_hdr_var = None
    if array_ends_synced:
        print(f"  Synced variableName on {array_ends_synced} ARRAY_END fields from their ARRAY_HDR")

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
        # Panel gets an ID (panels don't have variableName in input, derive it)
        panel_var_name = sanitize_variable_name(panel_name)
        id_map[panel_var_name] = temp_metadata_counter
        temp_metadata_counter += 1

        # Each field gets an ID — always use variableName from input
        for field in fields:
            variable_name = field.get('variableName', '')
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

        panel_var_name = sanitize_variable_name(panel_name)

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
            variable_name = field.get('variableName', '')

            # Map variable name to ID (use the actual metadata ID)
            id_map[variable_name] = field_metadata_id

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
                "variableName": variable_name,
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
            # Note: panel context not available in legacy mode, will use global lookup
            rules = field.get('rules', [])
            for rule in rules:
                form_fill_rule = create_form_fill_rule(rule, field_metadata_id, id_map, rule_id_counter,
                                                       current_panel=None, panel_field_map=None, metadatas=None)
                if form_fill_rule is not None:
                    metadata["formFillRules"].append(form_fill_rule)
                    rule_id_counter += 1  # Increment rule ID for next rule

            # Check if any rule has YES_NO params and update prefill value
            if _has_yes_no_params(rules):
                metadata['preFillData']['value'] = 'No'

            doc_type["formFillMetadatas"].append(metadata)
            form_order += 0.0001

    template["documentTypes"].append(doc_type)

    # Set headerMetadataId on fields between ARRAY_HDR and ARRAY_END
    array_fields_updated = set_header_metadata_ids(doc_type["formFillMetadatas"])
    if array_fields_updated:
        print(f"  Set headerMetadataId on {array_fields_updated} fields inside ARRAY sections")

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
