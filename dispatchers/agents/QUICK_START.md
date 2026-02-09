# Quick Start Guide

## Complete BUD to API Conversion Pipeline

This guide shows you how to convert a BUD document to API-compatible JSON in just a few commands.

## TL;DR - One Command

```bash
./dispatchers/agents/run_complete_workflow.sh
```

This runs all 4 steps automatically:
1. Rule Placement
2. Source-Destination
3. EDV Rules
4. API Format Conversion

## Step-by-Step Commands

### Prerequisites
```bash
# Ensure you have the BUD document
ls documents/Vendor\ Creation\ Sample\ BUD.docx

# Ensure dependencies are ready
ls rule_extractor/static/keyword_tree.json
ls rules/Rule-Schemas.json
```

### Run Individual Steps

```bash
# Step 1: Rule Placement (identifies which rules apply to fields)
python3 dispatchers/agents/rule_placement_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --output "output/rule_placement/all_panels_rules.json"

# Step 2: Source-Destination (populates source/destination field IDs)
python3 dispatchers/agents/source_destination_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --rule-placement-output "output/rule_placement/all_panels_rules.json" \
  --output "output/source_destination/all_panels_source_dest.json"

# Step 3: EDV Rules (populates EDV params for dropdowns)
python3 dispatchers/agents/edv_rule_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --source-dest-output "output/source_destination/all_panels_source_dest.json" \
  --output "output/edv_rules/all_panels_edv.json"

# Step 4: API Conversion (converts to API-compatible format)
python3 dispatchers/agents/convert_to_api_format.py \
  --input "output/edv_rules/all_panels_edv.json" \
  --output "documents/json_output/vendor_creation.json" \
  --bud-name "Vendor Creation" \
  --pretty
```

## What Gets Generated

```
output/
├── rule_placement/
│   └── all_panels_rules.json              # Step 1 output
├── source_destination/
│   └── all_panels_source_dest.json        # Step 2 output
└── edv_rules/
    └── all_panels_edv.json                # Step 3 output

documents/json_output/
└── vendor_creation_generated.json         # Step 4 output (FINAL)
```

## Key Features of Final Output

### Unique IDs
- **Rule IDs**: Start from 1, unique across all rules
- **Field IDs**: Start from 275490, unique for each field
- **Template ID**: Deterministically generated from BUD name

### Field ID Mapping
All variableNames converted to field IDs:
```json
// Before (EDV output)
"source_fields": ["__vendor_type__"]

// After (API format)
"sourceIds": [275493]
```

### EDV Params
Properly JSON-stringified with field ID mapping:
```json
{
  "params": "[{\"conditionList\":[{\"ddType\":[\"TABLE\"],\"criterias\":[{\"a1\":275490}],\"da\":[\"a2\"]}]}]"
}
```

## Validation Commands

```bash
# Check template info
jq '.template | {id, templateName, code}' documents/json_output/vendor_creation_generated.json

# Count fields
jq '.template.documentTypes[0].formFillMetadatas | length' documents/json_output/vendor_creation_generated.json

# Count rules
jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[]] | length' documents/json_output/vendor_creation_generated.json

# Check EDV params exist
jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[] | select(.params | contains("conditionList"))] | length' documents/json_output/vendor_creation_generated.json

# Verify rule IDs are unique
jq '[.template.documentTypes[0].formFillMetadatas[].formFillRules[].id] | sort | unique | length' documents/json_output/vendor_creation_generated.json
```

## Typical Execution Time

| Step | Time | What It Does |
|------|------|--------------|
| 1. Rule Placement | 1-2 min | Keyword matching to find relevant rules |
| 2. Source-Destination | 3-5 min | LLM analysis of source/dest fields |
| 3. EDV Rules | 3-5 min | LLM analysis of EDV params |
| 4. API Conversion | < 1 sec | Deterministic JSON transformation |
| **Total** | **7-12 min** | Full pipeline for medium BUD |

## Common Options

### Custom BUD File
```bash
./dispatchers/agents/run_complete_workflow.sh \
  --bud "documents/MyCustomBUD.docx"
```

### Clean Temp Files
```bash
./dispatchers/agents/run_complete_workflow.sh --clean-temp
```

### Verbose Output
```bash
./dispatchers/agents/run_complete_workflow.sh --verbose
```

## Output Structure

### Template Metadata
```json
{
  "template": {
    "id": 12345,                    // Deterministic from BUD name
    "templateName": "Vendor Creation",
    "code": "vendor_creation",      // Slugified BUD name
    "key": "TMPTS12345",
    "documentTypes": [...]
  }
}
```

### Form Fill Metadatas (Fields)
```json
{
  "id": 275491,                     // Unique field ID
  "formTag": {
    "id": 402491,                   // Form tag ID
    "name": "Transaction ID",
    "type": "TEXT"
  },
  "variableName": "_transac91_",   // Short variable name
  "formFillRules": [...]
}
```

### Form Fill Rules
```json
{
  "id": 1,                          // Unique rule ID
  "actionType": "EXT_DROP_DOWN",
  "sourceIds": [275490],            // Field IDs (not variableNames)
  "destinationIds": [275491],       // Field IDs
  "params": "[{...}]"               // JSON-stringified
}
```

## Troubleshooting

### Issue: "BUD file not found"
```bash
# Check file exists
ls -l "documents/Vendor Creation Sample BUD.docx"
```

### Issue: "Source-dest output not found"
```bash
# Run steps in order
./dispatchers/agents/run_complete_workflow.sh
```

### Issue: "Rule IDs not unique"
```bash
# Check conversion script
python3 dispatchers/agents/convert_to_api_format.py --help
```

### Issue: "Variable not found in ID map"
```bash
# Check EDV output has all referenced fields
jq 'keys' output/edv_rules/all_panels_edv.json
```

## Next Steps After Conversion

1. **Validate JSON**
   ```bash
   jq '.' documents/json_output/vendor_creation_generated.json > /dev/null
   echo "JSON is valid!"
   ```

2. **Compare with Reference**
   ```bash
   # Compare structure
   diff <(jq 'keys' documents/json_output/vendor_creation.json) \
        <(jq 'keys' documents/json_output/vendor_creation_generated.json)
   ```

3. **Test with API**
   ```bash
   # Upload to API endpoint (example)
   curl -X POST https://api.example.com/templates \
     -H "Content-Type: application/json" \
     -d @documents/json_output/vendor_creation_generated.json
   ```

## File Descriptions

| File | Purpose |
|------|---------|
| `run_complete_workflow.sh` | Runs all 4 steps in sequence |
| `rule_placement_dispatcher.py` | Step 1: Identifies rules |
| `source_destination_dispatcher.py` | Step 2: Populates source/dest |
| `edv_rule_dispatcher.py` | Step 3: Populates EDV params |
| `convert_to_api_format.py` | Step 4: Converts to API format |
| `run_conversion.sh` | Helper for Step 4 only |

## Documentation

- `README.md` - Overview of all dispatchers
- `README_EDV_RULE_DISPATCHER.md` - EDV dispatcher details
- `README_CONVERSION.md` - API conversion details
- `WORKFLOW.md` - Complete workflow documentation
- `QUICK_START.md` - This file

## Support

For issues or questions:
1. Check temp files in `output/*/temp/` for debugging
2. Review agent markdown files in `.claude/agents/mini/`
3. Validate input data structure
4. Check logs for specific error messages

## Summary

**To convert a BUD to API format:**
```bash
./dispatchers/agents/run_complete_workflow.sh
```

**Output:**
```
documents/json_output/vendor_creation_generated.json
```

**Time:**
~7-12 minutes for complete pipeline

**Result:**
Production-ready API-compatible JSON! 🎉
