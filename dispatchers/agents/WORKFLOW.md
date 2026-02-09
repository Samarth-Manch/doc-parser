# Agent Dispatcher Workflow

This document describes the complete workflow for processing BUD documents through multiple agent dispatchers to generate fully-populated rule structures.

## Overview

```
BUD Document (.docx)
        ↓
┌──────────────────────────────────────┐
│  Step 1: Rule Placement Dispatcher   │
│  - Identifies which rules apply      │
│  - Panel-by-panel processing         │
└──────────────────────────────────────┘
        ↓
┌──────────────────────────────────────┐
│ Step 2: Source-Destination Dispatcher│
│  - Determines source/dest fields     │
│  - Populates field IDs               │
└──────────────────────────────────────┘
        ↓
┌──────────────────────────────────────┐
│     Step 3: EDV Rule Dispatcher      │
│  - Populates EDV params              │
│  - Handles cascading dropdowns       │
│  - Maps reference tables             │
└──────────────────────────────────────┘
        ↓
┌──────────────────────────────────────┐
│  Step 4: API Format Converter        │
│  - Converts to API-compatible JSON   │
│  - Unique IDs for fields & rules     │
│  - Maps variableNames to field IDs   │
│  - Stringifies EDV params            │
└──────────────────────────────────────┘
        ↓
   Final API Output
```

## Step-by-Step Execution

### Step 1: Rule Placement Dispatcher

**Purpose**: Identify which rules should be applied to each field based on logic analysis.

**Command**:
```bash
python3 dispatchers/agents/rule_placement_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --keyword-tree "rule_extractor/static/keyword_tree.json" \
  --rule-schemas "rules/Rule-Schemas.json" \
  --output "output/rule_placement/all_panels_rules.json"
```

**Input**:
- BUD document (.docx)
- Keyword tree (for matching logic to rules)
- Rule schemas (all available rules)

**Output**:
```json
{
  "Panel Name": [
    {
      "field_name": "Vendor Type",
      "type": "DROPDOWN",
      "mandatory": true,
      "logic": "Select vendor type from reference table 1.1",
      "rules": ["EXT_DROP_DOWN"],
      "variableName": "__vendor_type__"
    }
  ]
}
```

**Agent Used**: `mini/01_rule_type_placement_agent_v2`

---

### Step 2: Source-Destination Dispatcher

**Purpose**: Determine source and destination fields for each rule.

**Command**:
```bash
python3 dispatchers/agents/source_destination_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --rule-placement-output "output/rule_placement/all_panels_rules.json" \
  --rule-schemas "rules/Rule-Schemas.json" \
  --output "output/source_destination/all_panels_source_dest.json"
```

**Input**:
- BUD document (.docx)
- Rule placement output (from Step 1)
- Rule schemas

**Output**:
```json
{
  "Panel Name": [
    {
      "field_name": "Vendor Type",
      "type": "DROPDOWN",
      "mandatory": true,
      "logic": "Select vendor type from reference table 1.1",
      "rules": [
        {
          "id": 1,
          "rule_name": "EXT_DROP_DOWN",
          "source_fields": [],
          "destination_fields": ["__vendor_type__"],
          "_reasoning": "Independent dropdown with no parent dependencies"
        }
      ],
      "variableName": "__vendor_type__"
    }
  ]
}
```

**Agent Used**: `mini/02_source_destination_agent_v2`

---

### Step 3: EDV Rule Dispatcher

**Purpose**: Populate EDV params for dropdown and validation rules.

**Command**:
```bash
python3 dispatchers/agents/edv_rule_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --source-dest-output "output/source_destination/all_panels_source_dest.json" \
  --output "output/edv_rules/all_panels_edv.json"
```

**Input**:
- BUD document (.docx) - for reference tables
- Source-destination output (from Step 2)

**Output**:
```json
{
  "Panel Name": [
    {
      "field_name": "Vendor Type",
      "type": "DROPDOWN",
      "mandatory": true,
      "logic": "Select vendor type from reference table 1.1",
      "rules": [
        {
          "id": 1,
          "rule_name": "EXT_DROP_DOWN",
          "source_fields": [],
          "destination_fields": ["__vendor_type__"],
          "params": {
            "conditionList": [
              {
                "ddType": ["REFERENCE_TABLE_1_1"],
                "criterias": [],
                "da": ["a2"],
                "criteriaSearchAttr": [],
                "additionalOptions": null,
                "emptyAddOptionCheck": null,
                "ddProperties": null
              }
            ],
            "__reasoning": "Independent dropdown showing column 2 from table 1.1"
          },
          "_reasoning": "Independent dropdown with no parent dependencies"
        }
      ],
      "variableName": "__vendor_type__"
    }
  ]
}
```

**Agent Used**: `mini/03_edv_rule_agent_v2`

---

### Step 4: API Format Converter

**Purpose**: Convert EDV output to API-compatible JSON format.

**Command**:
```bash
python3 dispatchers/agents/convert_to_api_format.py \
  --input "output/edv_rules/all_panels_edv.json" \
  --output "documents/json_output/vendor_creation.json" \
  --bud-name "Vendor Creation" \
  --pretty
```

Or use the wrapper:
```bash
./dispatchers/agents/run_conversion.sh --pretty
```

**Input**:
- EDV rules output (from Step 3)

**Output**:
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
                "params": "[{\"conditionList\":[...]}]"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

**Features**:
- Unique rule IDs starting from 1
- Unique field IDs starting from 275490
- Variable names converted to field IDs in source/destination
- EDV params JSON-stringified
- Template ID deterministically generated from BUD name

---

## Complete Workflow Script

```bash
#!/bin/bash
# run_complete_workflow.sh - Execute all four steps in sequence

set -e  # Exit on error

BUD_FILE="documents/Vendor Creation Sample BUD.docx"
KEYWORD_TREE="rule_extractor/static/keyword_tree.json"
RULE_SCHEMAS="rules/Rule-Schemas.json"

# Output files
RULE_PLACEMENT_OUTPUT="output/rule_placement/all_panels_rules.json"
SOURCE_DEST_OUTPUT="output/source_destination/all_panels_source_dest.json"
EDV_OUTPUT="output/edv_rules/all_panels_edv.json"

echo "========================================"
echo "Complete BUD Processing Workflow"
echo "========================================"
echo ""

# Step 1: Rule Placement
echo "Step 1/3: Rule Placement..."
python3 dispatchers/agents/rule_placement_dispatcher.py \
  --bud "$BUD_FILE" \
  --keyword-tree "$KEYWORD_TREE" \
  --rule-schemas "$RULE_SCHEMAS" \
  --output "$RULE_PLACEMENT_OUTPUT"

echo ""
echo "✓ Rule placement complete"
echo ""

# Step 2: Source-Destination
echo "Step 2/3: Source-Destination..."
python3 dispatchers/agents/source_destination_dispatcher.py \
  --bud "$BUD_FILE" \
  --rule-placement-output "$RULE_PLACEMENT_OUTPUT" \
  --rule-schemas "$RULE_SCHEMAS" \
  --output "$SOURCE_DEST_OUTPUT"

echo ""
echo "✓ Source-destination complete"
echo ""

# Step 3: EDV Rules
echo "Step 3/4: EDV Rules..."
python3 dispatchers/agents/edv_rule_dispatcher.py \
  --bud "$BUD_FILE" \
  --source-dest-output "$SOURCE_DEST_OUTPUT" \
  --output "$EDV_OUTPUT"

echo ""

# Step 4: API Format Conversion
echo "Step 4/4: API Format Conversion..."
python3 dispatchers/agents/convert_to_api_format.py \
  --input "$EDV_OUTPUT" \
  --output "$API_OUTPUT" \
  --bud-name "Vendor Creation" \
  --pretty

echo ""
echo "========================================"
echo "✅ Complete Workflow Finished!"
echo "========================================"
echo ""
echo "Output Files:"
echo "  1. Rule Placement:      $RULE_PLACEMENT_OUTPUT"
echo "  2. Source-Destination:  $SOURCE_DEST_OUTPUT"
echo "  3. EDV Rules:           $EDV_OUTPUT"
echo "  4. API Format (Final):  $API_OUTPUT"
echo ""
```

## Key Features

### Panel-by-Panel Processing
All dispatchers process panels independently, allowing for:
- Parallel processing potential
- Isolated failures (one panel failure doesn't stop others)
- Easier debugging and validation

### Reference Table Filtering
The EDV dispatcher intelligently filters reference tables:
- Only includes tables mentioned in the panel's fields' logic
- Reduces input size and improves agent performance
- Prevents confusion from irrelevant tables

### Progressive Enhancement
Each step builds on the previous:
1. **Rule Placement**: Identifies relevant rules
2. **Source-Destination**: Adds field relationships
3. **EDV Rules**: Completes with table mappings

## Directory Structure

```
output/
├── rule_placement/
│   ├── all_panels_rules.json
│   └── temp/
│       ├── Panel_Name_input.json
│       └── Panel_Name_rules.json
├── source_destination/
│   ├── all_panels_source_dest.json
│   └── temp/
│       ├── Panel_Name_fields_input.json
│       └── Panel_Name_source_dest.json
└── edv_rules/
    ├── all_panels_edv.json
    └── temp/
        ├── Panel_Name_fields_input.json
        ├── Panel_Name_tables_input.json
        └── Panel_Name_edv_output.json
```

## Error Handling

Each dispatcher:
- Validates input files exist
- Continues processing other panels if one fails
- Provides detailed error messages
- Returns non-zero exit code if any panel fails
- Generates summary statistics

## Performance Considerations

- **Rule Placement**: Fast (keyword matching)
- **Source-Destination**: Medium (LLM inference per panel)
- **EDV Rules**: Medium-Slow (LLM inference + table analysis)

Total time depends on:
- Number of panels
- Number of fields per panel
- Complexity of field logic
- Number of reference tables

## Validation

After running all steps, validate:

1. **All panels processed**
   ```bash
   jq 'keys | length' output/edv_rules/all_panels_edv.json
   ```

2. **EDV params present**
   ```bash
   jq '.[].[] | select(.rules[].rule_name == "EXT_DROP_DOWN") | .rules[] | select(.rule_name == "EXT_DROP_DOWN") | has("params")' output/edv_rules/all_panels_edv.json
   ```

3. **Reference tables mapped**
   ```bash
   jq '.[].[] | .rules[] | select(.params) | .params.conditionList[] | .ddType' output/edv_rules/all_panels_edv.json
   ```

## Troubleshooting

### Step 1 Fails
- Check keyword_tree.json exists
- Verify Rule-Schemas.json is valid
- Ensure BUD document has fields with logic

### Step 2 Fails
- Verify Step 1 output exists
- Check Rule-Schemas.json has proper source/dest fields
- Review field logic for clarity

### Step 3 Fails
- Ensure BUD has reference tables
- Check logic mentions table IDs (e.g., "table 1.3")
- Verify Step 2 output has rules to process

### Temp Files Not Cleaned
Temp files are preserved for debugging. To clean:
```bash
rm -rf output/*/temp/
```

## See Also

- `README_EDV_RULE_DISPATCHER.md` - EDV dispatcher details
- `rule_placement_dispatcher.py` - Rule placement implementation
- `source_destination_dispatcher.py` - Source-destination implementation
- `.claude/agents/mini/` - Mini agent definitions
