# EDV Table Mapping Dispatcher

This dispatcher extracts EDV (External Data Value) table metadata and field-to-EDV mappings from BUD documents.

## Purpose

The EDV Mapping Dispatcher:
1. **Extracts reference tables** - Identifies embedded Excel tables in BUD
2. **Generates EDV metadata** - For each table, extracts structure, columns, sample data
3. **Maps fields to tables** - Panel by panel, identifies which fields use which EDV tables
4. **Detects cascading** - Identifies parent-child dropdown relationships

This is critical for generating correct `EXT_DROP_DOWN` and `EXT_VALUE` rule params.

## Pipeline Position

This is a supplementary tool that can run independently or before the main rule extraction pipeline:

```
BUD Document
    ↓
[EDV Mapping Dispatcher]
    ↓
    Outputs:
    - EDV Tables Metadata
    - Field-to-EDV Mappings
    ↓
[Can be used by EDV Rule Agent (Stage 3)]
```

## Usage

### Basic Usage

```bash
python3 dispatchers/agents/edv_mapping_dispatcher.py \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --output output/edv_mapping
```

### Arguments

- `--bud` (required): Path to BUD document (.docx)
- `--output` (optional): Output directory (default: `output/edv_mapping`)

Output files are placed in timestamped subdirectory: `output/edv_mapping/YYYY-MM-DD_HH-MM-SS/`

## Process Flow

### Step 1: Parse BUD Document
- Uses `doc_parser.DocumentParser` to extract fields and embedded tables
- Extracts all dropdown/external data fields

### Step 2: Extract Reference Tables
- Identifies embedded Excel tables in document
- For each table, captures:
  - Table ID and reference number
  - Number of rows and columns
  - Column headers
  - Sample data (first 5 rows)

### Step 3: Generate Table Metadata
For each reference table, extracts:
- **EDV Name**: Generated from headers (UPPERCASE, underscores)
- **Column Metadata**: Maps columns to EDV attributes (a1, a2, a3...)
- **Purpose**: Infers table usage (dropdowns, validation, lookup)
- **Sample Data**: Converts to EDV format

### Step 4: Group Fields by Panel
- Groups dropdown/EDV fields by their panel
- Only includes fields with types: DROPDOWN, EXTERNAL_DROP_DOWN_VALUE

### Step 5: Map Fields to EDV Tables
For each panel:
- Analyzes field logic to identify table references
- Detects cascading relationships (keywords: "based on", "depends on", etc.)
- Maps fields to EDV tables
- Determines rule type: EXT_DROP_DOWN vs EXT_VALUE
- Identifies parent-child relationships

### Step 6: Output Files
Generates two JSON files:
1. `<doc_name>_edv_tables.json` - Table metadata
2. `<doc_name>_field_edv_mapping.json` - Field mappings by panel

## Output Format

### File 1: EDV Tables Metadata

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-02-07T21:30:00"
  },
  "edv_tables": [
    {
      "table_id": "table_1",
      "reference_id": "1",
      "edv_name": "VENDOR_TYPE_GROUP_KEY",
      "purpose": "dropdown_values",
      "columns": [
        {
          "index": 1,
          "attribute": "a1",
          "header": "Vendor Type",
          "data_type": "string"
        },
        {
          "index": 2,
          "attribute": "a2",
          "header": "Group Key",
          "data_type": "string"
        }
      ],
      "row_count": 15,
      "sample_data": [
        {"a1": "ZDES", "a2": "CORP01"},
        {"a1": "ZIMP", "a2": "CORP02"}
      ]
    }
  ],
  "summary": {
    "total_reference_tables": 6,
    "total_edv_tables_generated": 6
  }
}
```

### File 2: Field-to-EDV Mappings

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-02-07T21:30:00"
  },
  "field_edv_mappings_by_panel": {
    "Basic Details": [
      {
        "field_name": "Account Group/Vendor Type",
        "type": "EXTERNAL_DROP_DOWN_VALUE",
        "panel_name": "Basic Details",
        "edv_table": "VENDOR_TYPE_GROUP_KEY",
        "rule_type": "EXT_DROP_DOWN",
        "is_cascading": false,
        "parent_field": null,
        "filter_column": null,
        "display_columns": ["a1"],
        "logic_reference": "Dropdown values are first and second columns of reference table 1.3"
      },
      {
        "field_name": "Group key/Corporate Group",
        "type": "EXTERNAL_DROP_DOWN_VALUE",
        "panel_name": "Basic Details",
        "edv_table": "VENDOR_TYPE_GROUP_KEY",
        "rule_type": "EXT_VALUE",
        "is_cascading": true,
        "parent_field": "Account Group/Vendor Type",
        "filter_column": "a1",
        "display_columns": ["a2"],
        "logic_reference": "Dropdown values will come based on the account group/vendor type selection"
      }
    ]
  },
  "summary": {
    "total_panels": 10,
    "successful_panels": 10,
    "failed_panels": 0,
    "total_fields_mapped": 28
  }
}
```

## Key Features

### 1. Table Metadata Extraction
- Automatically generates EDV table names from headers
- Maps columns to EDV attributes (a1, a2, a3...)
- Preserves sample data for reference

### 2. Cascading Detection
Identifies cascading dropdowns by detecting keywords in logic:
- "based on"
- "depends on"
- "filtered by"
- "selection"
- "cascading"

### 3. Rule Type Determination
- **EXT_DROP_DOWN**: Simple dropdowns (no dependencies)
- **EXT_VALUE**: Cascading dropdowns (filtered by parent field)

### 4. Panel-by-Panel Processing
- Processes each panel independently
- Organizes output by panel structure
- Easy to debug individual panels

## Cascading Dropdown Detection

### Example 1: Simple Dropdown
```
Field: "Country"
Logic: "Dropdown values from table 1.1"

Result:
- rule_type: EXT_DROP_DOWN
- is_cascading: false
- parent_field: null
```

### Example 2: Cascading Dropdown
```
Field: "Group key/Corporate Group"
Logic: "Dropdown values will come based on the account group/vendor type selection field as 2nd column of reference table 1.3"

Result:
- rule_type: EXT_VALUE
- is_cascading: true
- parent_field: "Account Group/Vendor Type"
- filter_column: "a1"
- display_columns: ["a2"]
```

## Integration with Rule Extraction

The output can be used by:
1. **EDV Rule Agent (Stage 3)** - To populate params for EDV rules
2. **Assembly Agent (Stage 5)** - To validate EDV configurations
3. **Manual review** - To verify table mappings are correct

## Temporary Files

Located in `output/edv_mapping/<timestamp>/temp/`:
- `table_<N>_input.json` - Input for table metadata extraction
- `table_<N>_metadata.json` - Extracted table metadata
- `<panel>_edv_input.json` - Input for field mapping
- `<panel>_edv_mapping.json` - Panel field mappings

## Example Run

```bash
$ python3 dispatchers/agents/edv_mapping_dispatcher.py \
    --bud "documents/Vendor Creation Sample BUD.docx"

Parsing BUD document: documents/Vendor Creation Sample BUD.docx
Extracted 140 fields

Extracting reference tables...
Found 9 reference tables

======================================================================
EXTRACTING TABLE METADATA
======================================================================

======================================================================
PROCESSING TABLE 1 (246 rows, 6 cols)
======================================================================
✓ Table 1 metadata extracted

... (8 more tables)

✓ Extracted metadata for 9 tables

Grouping dropdown/EDV fields by panel...
Found 10 panels with EDV fields

======================================================================
MAPPING FIELDS TO EDV TABLES
======================================================================

======================================================================
MAPPING PANEL: Basic Details (8 EDV fields)
======================================================================
✓ Panel 'Basic Details' EDV mapping completed

... (9 more panels)

✓ Wrote table metadata: output/edv_mapping/2026-02-07_21-30-00/Vendor_Creation_Sample_BUD_edv_tables.json
✓ Wrote field mappings: output/edv_mapping/2026-02-07_21-30-00/Vendor_Creation_Sample_BUD_field_edv_mapping.json

======================================================================
EDV MAPPING COMPLETE
======================================================================
Reference Tables: 9
EDV Tables Generated: 9
Panels with EDV Fields: 10
Successful Panels: 10
Failed Panels: 0

Output Directory: output/edv_mapping/2026-02-07_21-30-00
======================================================================
```

## Future Enhancements

- Call mini agent for more sophisticated table metadata extraction
- Use LLM to better identify table purpose and generate EDV names
- Detect multi-level cascading (grandparent → parent → child)
- Validate cascading relationships (verify parent field exists)
- Generate params JSON directly for EXT_VALUE and EXT_DROP_DOWN rules
