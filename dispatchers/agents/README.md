# Agent Dispatchers

This directory contains dispatchers that orchestrate mini agents for BUD document processing.

## Overview

Agent dispatchers coordinate the execution of specialized mini agents to extract and populate rule data from Business Understanding Documents (BUDs). Each dispatcher handles a specific stage of the processing pipeline.

## Available Dispatchers

### 1. Rule Placement Dispatcher
**File**: `rule_placement_dispatcher.py`
**Agent**: `.claude/agents/mini/01_rule_type_placement_agent_v2.md`
**Purpose**: Identifies which rules apply to each field based on logic analysis

**Input**:
- BUD document (.docx)
- Keyword tree (keyword_tree.json)
- Rule schemas (Rule-Schemas.json)

**Output**: Fields with rule names assigned
```json
{
  "Panel Name": [
    {
      "field_name": "Field 1",
      "type": "DROPDOWN",
      "logic": "...",
      "rules": ["RULE_NAME_1", "RULE_NAME_2"],
      "variableName": "__field_1__"
    }
  ]
}
```

### 2. Source-Destination Dispatcher
**File**: `source_destination_dispatcher.py`
**Agent**: `.claude/agents/mini/02_source_destination_agent_v2.md`
**Purpose**: Determines source and destination fields for each rule

**Input**:
- BUD document (.docx)
- Rule placement output (from dispatcher 1)
- Rule schemas (Rule-Schemas.json)

**Output**: Fields with rules containing source/destination field IDs
```json
{
  "Panel Name": [
    {
      "field_name": "Field 1",
      "rules": [
        {
          "id": 1,
          "rule_name": "RULE_NAME",
          "source_fields": ["__field_a__"],
          "destination_fields": ["__field_b__"],
          "_reasoning": "..."
        }
      ]
    }
  ]
}
```

### 3. EDV Rule Dispatcher
**File**: `edv_rule_dispatcher.py`
**Agent**: `.claude/agents/mini/03_edv_rule_agent_v2.md`
**Purpose**: Populates EDV params for dropdown and validation rules

**Input**:
- BUD document (.docx) - for reference tables
- Source-destination output (from dispatcher 2)

**Output**: Fields with EDV rules containing params
```json
{
  "Panel Name": [
    {
      "field_name": "Field 1",
      "rules": [
        {
          "id": 1,
          "rule_name": "EXT_DROP_DOWN",
          "source_fields": ["__parent__"],
          "destination_fields": ["__current__"],
          "params": {
            "conditionList": [{
              "ddType": ["TABLE_NAME"],
              "criterias": [{"a1": "__parent__"}],
              "da": ["a2"],
              "criteriaSearchAttr": [],
              "additionalOptions": null,
              "emptyAddOptionCheck": null,
              "ddProperties": null
            }],
            "__reasoning": "..."
          }
        }
      ]
    }
  ]
}
```

## Quick Start

### Individual Dispatcher

```bash
# Step 1: Rule Placement
python3 dispatchers/agents/rule_placement_dispatcher.py \
  --bud "documents/Sample.docx" \
  --output "output/rule_placement/all_panels_rules.json"

# Step 2: Source-Destination
python3 dispatchers/agents/source_destination_dispatcher.py \
  --bud "documents/Sample.docx" \
  --rule-placement-output "output/rule_placement/all_panels_rules.json" \
  --output "output/source_destination/all_panels_source_dest.json"

# Step 3: EDV Rules
python3 dispatchers/agents/edv_rule_dispatcher.py \
  --bud "documents/Sample.docx" \
  --source-dest-output "output/source_destination/all_panels_source_dest.json" \
  --output "output/edv_rules/all_panels_edv.json"
```

### Complete Workflow

Run all three dispatchers in sequence:

```bash
./dispatchers/agents/run_complete_workflow.sh
```

With options:
```bash
./dispatchers/agents/run_complete_workflow.sh \
  --bud "documents/Sample.docx" \
  --clean-temp \
  --verbose
```

## Architecture

### Panel-by-Panel Processing

All dispatchers process panels independently:
- Each panel is sent to the mini agent separately
- Failures are isolated to individual panels
- Results are collected and combined into a single output file

### Reference Table Filtering (EDV Dispatcher)

The EDV dispatcher intelligently filters reference tables:
1. Scans all fields' logic in a panel
2. Detects table references (e.g., "table 1.3", "reference table 2.1")
3. Includes only referenced tables in the agent input
4. Converts tables to EDV-compatible format with sample data (3-4 rows)

### Data Flow

```
BUD.docx
   ├─→ doc_parser.parse()
   │     ├─→ all_fields (with logic)
   │     └─→ reference_tables
   │
   ├─→ [Dispatcher 1: Rule Placement]
   │     └─→ fields + rule_names
   │
   ├─→ [Dispatcher 2: Source-Destination]
   │     └─→ fields + rules {source_fields, destination_fields}
   │
   └─→ [Dispatcher 3: EDV Rules]
         └─→ fields + rules {params}
```

## Directory Structure

```
dispatchers/agents/
├── rule_placement_dispatcher.py          # Dispatcher 1
├── source_destination_dispatcher.py      # Dispatcher 2
├── edv_rule_dispatcher.py               # Dispatcher 3
├── run_complete_workflow.sh             # Run all three
├── example_edv_dispatcher_usage.sh      # EDV dispatcher example
├── README.md                            # This file
├── README_EDV_RULE_DISPATCHER.md        # EDV dispatcher details
├── README_EDV_MAPPING.md                # EDV mapping utility
└── WORKFLOW.md                          # Complete workflow guide
```

## Output Structure

```
output/
├── rule_placement/
│   ├── all_panels_rules.json           # Step 1 output
│   └── temp/                           # Temp files (preserved for debugging)
│
├── source_destination/
│   ├── all_panels_source_dest.json     # Step 2 output
│   └── temp/
│
└── edv_rules/
    ├── all_panels_edv.json             # Step 3 output (FINAL)
    └── temp/
```

## Key Features

### 1. Progressive Data Enrichment
Each dispatcher adds more information:
- **Dispatcher 1**: Adds rule names
- **Dispatcher 2**: Adds source/destination fields
- **Dispatcher 3**: Adds EDV params

### 2. Reference Table Intelligence
The EDV dispatcher only includes tables that are:
- Mentioned in the panel's fields' logic
- Available in the BUD document
- Properly formatted with attributes/columns mapping

### 3. Sample Data Optimization
Reference tables include only 3-4 sample rows to:
- Keep input size manageable
- Reduce LLM processing time
- Provide enough context for mapping

### 4. Error Resilience
All dispatchers:
- Validate inputs before processing
- Continue processing other panels if one fails
- Provide detailed error messages
- Generate summary statistics

## Requirements

### System Requirements
- Python 3.8+
- Claude CLI installed and configured
- doc_parser package

### File Requirements
- BUD document (.docx) with:
  - Fields with logic sections
  - Embedded reference tables (for EDV dispatcher)
- keyword_tree.json (for rule placement)
- Rule-Schemas.json (for all dispatchers)

## Troubleshooting

### Common Issues

**Issue**: "claude command not found"
- **Solution**: Install Claude CLI or ensure it's in PATH

**Issue**: "No reference tables found"
- **Solution**: Check BUD document has embedded Excel tables

**Issue**: "Panel processing failed"
- **Solution**: Check temp files in `output/*/temp/` for agent output

**Issue**: "Wrong EDV params generated"
- **Solution**: Review field logic for table references and column mentions

### Debug Mode

Check temp files for debugging:
```bash
# View input sent to agent
cat output/edv_rules/temp/Panel_Name_fields_input.json
cat output/edv_rules/temp/Panel_Name_tables_input.json

# View agent output
cat output/edv_rules/temp/Panel_Name_edv_output.json
```

### Validation

Validate final output:
```bash
# Count panels processed
jq 'keys | length' output/edv_rules/all_panels_edv.json

# Count fields with EDV params
jq '[.[]] | flatten | [.[] | .rules[] | select(.params)] | length' output/edv_rules/all_panels_edv.json

# List all referenced tables
jq '[.[]] | flatten | [.[] | .rules[] | select(.params) | .params.conditionList[] | .ddType[]] | unique' output/edv_rules/all_panels_edv.json
```

## Related Documentation

- **Mini Agents**: `.claude/agents/mini/`
  - `01_rule_type_placement_agent_v2.md`
  - `02_source_destination_agent_v2.md`
  - `03_edv_rule_agent_v2.md`

- **Doc Parser**: `doc_parser/`
  - `parser.py` - Main parser
  - `models.py` - Data models

- **Rules**: `rules/`
  - `Rule-Schemas.json` - All rule definitions

- **Utilities**: `dispatchers/`
  - `edv_table_mapping.py` - EDV table mapping utility

## Performance

Typical execution times (example):
- **Rule Placement**: 1-2 minutes
- **Source-Destination**: 3-5 minutes
- **EDV Rules**: 3-5 minutes
- **Total**: 7-12 minutes for a medium-sized BUD

Factors affecting performance:
- Number of panels
- Number of fields per panel
- Complexity of field logic
- Number of reference tables

## Best Practices

1. **Run sequentially**: Each dispatcher depends on the previous one
2. **Preserve temp files**: Useful for debugging and validation
3. **Validate between steps**: Check outputs before proceeding
4. **Clean test data**: Ensure BUD has clear table references in logic
5. **Review agent outputs**: Verify reasoning in `_reasoning` fields

## Support

For issues or questions:
- Check temp files for agent outputs
- Review agent markdown files in `.claude/agents/mini/`
- Validate input data structure
- Check logs for specific error messages
