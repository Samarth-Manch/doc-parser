# EDV to API Format Converter

## Overview

The converter transforms EDV dispatcher output (panel-based structure with rules) into the API-compatible JSON format required by the Manch platform.

## Purpose

Converts from EDV agent output format to the final API format with:
- Template metadata (ID, name, code)
- Document types
- Form fill metadatas (fields)
- Form fill rules (with proper ID mapping)

## Key Features

### 1. Unique ID Generation
- **Field IDs**: Sequential, starting from 275490
- **Rule IDs**: Unique, starting from 1
- **Form Tag IDs**: Based on field ID + offset
- **Template ID**: Deterministic hash from BUD filename

### 2. Variable Name to ID Mapping
The converter creates a complete ID map in two passes:
1. **First pass**: Create ID map for all fields
2. **Second pass**: Convert all variableNames to field IDs

This ensures:
- Source fields reference actual field IDs
- Destination fields reference actual field IDs
- Criterias in EDV params use field IDs instead of variableNames

### 3. EDV Params Conversion
EDV params with `conditionList` are:
- Cleaned (remove `__reasoning`)
- Variable names in criterias converted to field IDs
- JSON-stringified for API compatibility

Example transformation:
```json
// Input (EDV output)
{
  "params": {
    "conditionList": [{
      "ddType": ["TABLE_NAME"],
      "criterias": [{"a1": "__parent_field__"}],
      "da": ["a2"]
    }]
  }
}

// Output (API format)
{
  "params": "[{\"conditionList\":[{\"ddType\":[\"TABLE_NAME\"],\"criterias\":[{\"a1\":275495}],\"da\":[\"a2\"],\"criteriaSearchAttr\":[],\"additionalOptions\":null,\"emptyAddOptionCheck\":null,\"ddProperties\":null}]}]"
}
```

Note: `__parent_field__` is converted to actual field ID `275495`

## Usage

### Quick Start

```bash
# Use defaults
./dispatchers/agents/run_conversion.sh

# Pretty print output
./dispatchers/agents/run_conversion.sh --pretty

# Custom BUD name
./dispatchers/agents/run_conversion.sh --bud-name "My Custom Process"
```

### Direct Python Script

```bash
python3 dispatchers/agents/convert_to_api_format.py \
  --input "output/edv_rules/all_panels_edv.json" \
  --output "documents/json_output/vendor_creation_generated.json" \
  --bud-name "Vendor Creation" \
  --pretty
```

### Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `--input` | No | Input EDV JSON file | `output/edv_rules/all_panels_edv.json` |
| `--output` | No | Output API JSON file | `documents/json_output/vendor_creation_generated.json` |
| `--bud-name` | No | BUD name for template | `Vendor Creation` |
| `--pretty` | No | Pretty print JSON | False |

## Input Format

EDV dispatcher output (panel-based):
```json
{
  "Panel Name": [
    {
      "field_name": "Field 1",
      "type": "DROPDOWN",
      "mandatory": true,
      "logic": "...",
      "rules": [
        {
          "id": 1,
          "rule_name": "EXT_DROP_DOWN",
          "source_fields": ["__parent__"],
          "destination_fields": ["__current__"],
          "params": {
            "conditionList": [{
              "ddType": ["TABLE"],
              "criterias": [{"a1": "__parent__"}],
              "da": ["a2"]
            }]
          }
        }
      ],
      "variableName": "__field_1__"
    }
  ]
}
```

## Output Format

API-compatible format:
```json
{
  "template": {
    "id": 12345,
    "templateName": "Vendor Creation",
    "code": "vendor_creation",
    "documentTypes": [
      {
        "formFillMetadatas": [
          {
            "id": 275490,
            "formTag": {
              "id": 402490,
              "name": "Panel Name",
              "type": "PANEL"
            },
            "variableName": "_panelna90_",
            "formFillRules": []
          },
          {
            "id": 275491,
            "formTag": {
              "id": 402491,
              "name": "Field 1",
              "type": "DROPDOWN"
            },
            "variableName": "_fieldx91_",
            "formFillRules": [
              {
                "id": 1,
                "actionType": "EXT_DROP_DOWN",
                "sourceIds": [275490],
                "destinationIds": [275491],
                "params": "[{\"conditionList\":[{\"ddType\":[\"TABLE\"],\"criterias\":[{\"a1\":275490}],\"da\":[\"a2\"]}]}]"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

## How It Works

### Step 1: Create ID Map (First Pass)
```python
# Scan all panels and fields
for panel_name, fields in edv_data.items():
    id_map[panel_var_name] = field_id++
    for field in fields:
        id_map[field.variableName] = field_id++
```

### Step 2: Generate Template Structure
```python
template = {
    "id": hash(bud_name),  # Deterministic
    "templateName": bud_name,
    "code": slugify(bud_name),
    "documentTypes": [...]
}
```

### Step 3: Process Panels and Fields (Second Pass)
```python
for panel_name, fields in edv_data.items():
    # Create panel metadata
    panel_id = id_map[panel_var_name]

    for field in fields:
        field_id = id_map[field.variableName]

        # Convert rules
        for rule in field.rules:
            # Map source/dest variableNames to IDs
            source_ids = [id_map[v] for v in rule.source_fields]
            dest_ids = [id_map[v] for v in rule.destination_fields]

            # Convert criterias variableNames to IDs
            for criteria in rule.params.conditionList.criterias:
                for key, value in criteria.items():
                    if value in id_map:
                        criteria[key] = id_map[value]
```

### Step 4: Generate Short Variable Names
```python
# Example: "Created On" with ID 275492 -> "_created92_"
def generate_short_variable_name(name, field_id):
    base = re.sub(r'[^a-zA-Z]', '', name.lower())[:7]
    suffix = str(field_id)[-2:]
    return f"_{base}{suffix}_"
```

## ID Mapping Example

```
Input EDV Output:
  __search_term__      -> 275490
  __created_on__       -> 275491
  __created_by__       -> 275492
  __vendor_type__      -> 275493
  __process_type__     -> 275494

Rule with source_fields: ["__vendor_type__"]
  ↓ Conversion
Rule with sourceIds: [275493]

Criterias with: {"a1": "__vendor_type__"}
  ↓ Conversion
Criterias with: {"a1": 275493}
```

## Variable Name Conversion

| Original Field Name | Long Variable Name | ID | Short Variable Name |
|---------------------|-------------------|-----|-------------------|
| Transaction ID | `__transaction_id__` | 275491 | `_transac91_` |
| Created On | `__created_on__` | 275492 | `_created92_` |
| Vendor Type | `__vendor_type__` | 275493 | `_vendort93_` |
| Country Code | `__country_code__` | 275494 | `_country94_` |

## Template Metadata Generation

- **Template ID**: `hash(bud_name) % 90000 + 10000` (deterministic)
- **Template Code**: `slugify(bud_name)` (e.g., "vendor_creation")
- **Template Name**: Title case BUD name
- **UUID**: Generated for baseDocumentStorageId

## Validation

After conversion, validate:

```bash
# Check template structure
jq '.template | keys' output.json

# Count fields
jq '.template.documentTypes[0].formFillMetadatas | length' output.json

# Count rules
jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[]] | length' output.json

# Check EDV params
jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[] | select(.params | contains("conditionList"))] | length' output.json

# Verify IDs are unique
jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[].id] | group_by(.) | map(length) | max' output.json
# Should be 1 (all unique)
```

## Complete Workflow

```bash
# Step 1: Run all dispatchers
./dispatchers/agents/run_complete_workflow.sh

# Step 2: Convert to API format
./dispatchers/agents/run_conversion.sh --pretty

# Step 3: Validate output
jq '.template.templateName' documents/json_output/vendor_creation_generated.json
```

## Troubleshooting

### Issue: "Variable not found in ID map"
**Cause**: Field referenced in source/destination doesn't exist
**Solution**: Check that all referenced fields are in the same panel or accessible

### Issue: "Rule IDs not starting from 1"
**Cause**: Script not resetting rule_id_counter
**Solution**: Check script initialization of `rule_id_counter = 1`

### Issue: "Params not JSON stringified"
**Cause**: conditionList params not being converted
**Solution**: Verify EDV output has `params.conditionList` structure

### Issue: "Field IDs duplicated"
**Cause**: ID map not created in first pass
**Solution**: Ensure first pass creates complete ID map before second pass

## Performance

- Typical conversion: < 1 second
- Large documents (200+ fields): 1-2 seconds
- Memory usage: Minimal (< 50MB)

## Output File Size

- Small BUD (50 fields): ~100KB
- Medium BUD (150 fields): ~300KB
- Large BUD (300 fields): ~600KB

## See Also

- `edv_rule_dispatcher.py` - Creates input for this converter
- `WORKFLOW.md` - Complete processing pipeline
- `run_complete_workflow.sh` - End-to-end automation
