# EDV Rule Dispatcher

## Overview

The EDV Rule Dispatcher orchestrates the population of EDV (External Data Value) parameters for dropdown rules. It processes panels sequentially, calling the EDV mini agent for each panel with:
- Fields and their rules (from source_destination_agent output)
- Only the reference tables mentioned in that panel's fields' logic

## Purpose

**Populates `params` field for EDV-related rules** (EXT_DROP_DOWN, EXT_VALUE) by:
1. Analyzing field logic to identify table references
2. Filtering reference tables to only those mentioned
3. Mapping table columns to EDV params structure
4. Handling parent-child dropdown relationships (cascading dropdowns)

## Input Requirements

### 1. BUD Document (.docx)
The original Business Understanding Document containing:
- Field definitions with logic sections
- Embedded Excel reference tables

### 2. Source-Destination Agent Output (JSON)
Output from `source_destination_agent` with structure:
```json
{
  "Panel Name": [
    {
      "field_name": "Field 1",
      "type": "DROPDOWN",
      "mandatory": true,
      "logic": "Select from reference table 1.3, column 2",
      "rules": [
        {
          "id": 1,
          "rule_name": "EXT_DROP_DOWN",
          "source_fields": ["__parent_field__"],
          "destination_fields": ["__current_field__"],
          "_reasoning": "..."
        }
      ],
      "variableName": "__field_1__"
    }
  ]
}
```

## Output

JSON file with EDV params populated for dropdown rules:
```json
{
  "Panel Name": [
    {
      "field_name": "Field 1",
      "type": "DROPDOWN",
      "mandatory": true,
      "logic": "Select from reference table 1.3, column 2",
      "rules": [
        {
          "id": 1,
          "rule_name": "EXT_DROP_DOWN",
          "source_fields": ["__parent_field__"],
          "destination_fields": ["__current_field__"],
          "params": {
            "conditionList": [
              {
                "ddType": ["REFERENCE_TABLE_1_3"],
                "criterias": [{"a1": "__parent_field__"}],
                "da": ["a2"],
                "criteriaSearchAttr": [],
                "additionalOptions": null,
                "emptyAddOptionCheck": null,
                "ddProperties": null
              }
            ],
            "__reasoning": "Cascading dropdown based on parent field..."
          },
          "_reasoning": "..."
        }
      ],
      "variableName": "__field_1__"
    }
  ]
}
```

## Usage

### Basic Usage

```bash
python3 dispatchers/agents/edv_rule_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --source-dest-output "output/source_destination/all_panels_source_dest.json" \
  --output "output/edv_rules/all_panels_edv.json"
```

### Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `--bud` | Yes | Path to BUD document (.docx) | - |
| `--source-dest-output` | Yes | Path to source_destination_agent output JSON | - |
| `--output` | No | Output file path | `output/edv_rules/all_panels_edv.json` |

## How It Works

### 1. Parse BUD Document
```python
parser = DocumentParser()
parsed_doc = parser.parse(bud_path)
reference_tables = extract_reference_tables_from_parser(parsed_doc)
```

### 2. Load Source-Destination Output
Reads the JSON output from source_destination_agent containing panels with fields and rules.

### 3. For Each Panel:

#### a. Filter Reference Tables
```python
# Detect table references in all fields' logic
referenced_ids = set()
for field in panel_fields:
    logic = field.get('logic', '')
    table_refs = detect_table_references_in_logic(logic)  # e.g., ["1.3", "2.1"]
    referenced_ids.update(table_refs)

# Filter tables to only those referenced
filtered_tables = [t for t in all_tables if t['reference_id'] in referenced_ids]
```

#### b. Convert Tables to EDV Format
```python
{
  "attributes/columns": {
    "a1": "Language Key",
    "a2": "Country/Region Key",
    "a3": "Country/Region Name"
  },
  "sample_data": [
    ["EN", "AD", "Andorran"],
    ["EN", "AE", "Utd.Arab Emir."],
    ["EN", "AF", "Afghanistan"]
  ],
  "source_file": "oleObject2.xlsx",
  "sheet_name": "Sheet1",
  "table_type": "reference",
  "source": "excel",
  "reference_id": "1.3"
}
```

#### c. Call EDV Mini Agent
```bash
claude -p "<prompt>" \
  --agent mini/03_edv_rule_agent_v2 \
  --allowedTools Read,Write
```

### 4. Collect Results
Combines all panel outputs into a single JSON file.

## Table Reference Detection

The dispatcher detects table references in logic using patterns:
- `"reference table 1.3"` → `1.3`
- `"table 2.1"` → `2.1`
- `"ref. table 1.2"` → `1.2`

**Only tables mentioned in logic are included** in the input to the EDV agent.

## EDV Params Structure

### Independent/Parent Dropdown
```json
{
  "params": {
    "conditionList": [
      {
        "ddType": ["TABLE_NAME"],
        "criterias": [],  // Empty for independent dropdowns
        "da": ["a2"],     // Display column 2
        "criteriaSearchAttr": [],
        "additionalOptions": null,
        "emptyAddOptionCheck": null,
        "ddProperties": null
      }
    ],
    "__reasoning": "Independent dropdown showing column 2 from TABLE_NAME"
  }
}
```

### Dependent/Child Dropdown (Cascading)
```json
{
  "params": {
    "conditionList": [
      {
        "ddType": ["TABLE_NAME"],
        "criterias": [
          {"a1": "__parent_field__"}  // Filter by parent field value
        ],
        "da": ["a2", "a3"],  // Display columns 2 and 3
        "criteriaSearchAttr": [],
        "additionalOptions": null,
        "emptyAddOptionCheck": null,
        "ddProperties": null
      }
    ],
    "__reasoning": "Cascading dropdown filtered by parent field, showing columns 2 and 3"
  }
}
```

## Workflow Integration

```
BUD Document (.docx)
        ↓
    doc_parser → reference_tables
        ↓
[Rule Placement Dispatcher] → fields with rule names
        ↓
[Source-Destination Dispatcher] → fields with source/dest
        ↓
[EDV Rule Dispatcher] → fields with EDV params ← reference_tables (filtered)
        ↓
    Final Output
```

## Output Structure

```
output/
  edv_rules/
    all_panels_edv.json          # Final output
    temp/
      Panel_Name_fields_input.json   # Fields input for panel
      Panel_Name_tables_input.json   # Tables input for panel
      Panel_Name_edv_output.json     # Output from EDV agent
```

## Error Handling

- **BUD file not found**: Exit with error
- **Source-dest output not found**: Exit with error
- **No reference tables found**: Continues with empty tables list
- **Panel processing fails**: Logs error, continues with next panel
- **Invalid JSON output**: Logs error, marks panel as failed

## Examples

### Example 1: Simple Dropdown
**Logic**: "Select country from reference table 1.2, column 3"

**Input reference table**:
```json
{
  "reference_id": "1.2",
  "attributes/columns": {
    "a1": "Code",
    "a2": "Key",
    "a3": "Country Name"
  },
  "sample_data": [["IN", "IND", "India"], ["US", "USA", "United States"]]
}
```

**Generated params**:
```json
{
  "ddType": ["REFERENCE_TABLE_1_2"],
  "criterias": [],
  "da": ["a3"]
}
```

### Example 2: Cascading Dropdown
**Logic**: "Based on country selected, show cities from table 1.4, column 2"

**Generated params**:
```json
{
  "ddType": ["REFERENCE_TABLE_1_4"],
  "criterias": [{"a1": "__country__"}],
  "da": ["a2"]
}
```

## Notes

- **Sample Data**: Limited to 3-4 rows to keep input manageable
- **Column Mapping**: Columns are mapped as a1, a2, a3, etc. based on order
- **Table Filtering**: Critical for performance - only sends relevant tables to agent
- **Panel-by-Panel**: Each panel is processed independently for parallel potential
- **Reasoning Fields**: Both `params.__reasoning` and rule `_reasoning` are preserved

## Troubleshooting

### No tables detected
- Check if logic mentions "table X.Y" format
- Verify reference tables exist in BUD document
- Check table extraction in doc_parser output

### Wrong params generated
- Review field logic text for clarity
- Check if table reference ID matches actual table
- Verify source_fields contain correct parent references

### Agent fails
- Check Claude CLI is installed and accessible
- Verify mini agent path: `.claude/agents/mini/03_edv_rule_agent_v2.md`
- Check temp file permissions

## See Also

- `.claude/agents/mini/03_edv_rule_agent_v2.md` - EDV mini agent definition
- `.claude/agents/mini/02_source_destination_agent_v2.md` - Source-destination agent
- `dispatchers/agents/rule_placement_dispatcher.py` - Rule placement dispatcher
- `dispatchers/edv_table_mapping.py` - Original EDV table mapping utility
