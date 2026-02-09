---
name: EDV Table Mapping
allowed-tools: Read, Write, Bash
description: Maps BUD reference tables to EDV (External Data Value) configurations for dropdown fields and parent-child relationships.
---


# EDV (External Data Value) Table Mapping

## Objective

Extract **EDV table mappings** from reference tables and field logic:
1. **Analyze table structure** - Extract column metadata, sample data, and EDV configuration
2. **Map fields to tables** - Identify which fields use which reference tables
3. **Detect cascading dropdowns** - Identify parent-child relationships from field logic
4. **Generate EDV metadata** - Create EDV-compatible table and field mappings

This output is **implementation-critical** for generating correct `EXT_VALUE` and `EXT_DROP_DOWN` rules with proper `params` structure.

---

## What is EDV?

**EDV (External Data Value)** is an external table system used for:
- **Dropdown values**: Populating dropdown options from external tables
- **Cascading/Parent-child dropdowns**: Filtering child dropdown based on parent selection
- **EDV Validation**: Validating field values against EDV tables (VALIDATION with EXTERNAL_DATA_VALUE)
- **Auto-population**: Filling fields based on external lookups

**NOTE**: API-based verifications (PAN, GSTIN, Bank Account, MSME) use **VERIFY rules**, NOT EDV!

### EDV Rule Types (sourceType: EXTERNAL_DATA_VALUE or FORM_FILL_DROP_DOWN)
- **EXT_DROP_DOWN**: Populates dropdown options from external table (`sourceType: FORM_FILL_DROP_DOWN`)
- **EXT_VALUE**: Auto-fills values based on external table lookup (`sourceType: EXTERNAL_DATA_VALUE`)
- **VALIDATION**: Validates field values against EDV table (`sourceType: EXTERNAL_DATA_VALUE`)

### API-Based Verification (NOT EDV!)
- **VERIFY**: Calls external APIs (PAN, GSTIN, Bank, MSME) - uses `sourceType` like `PAN_NUMBER`, `GSTIN`, etc.

---

## Input

You will be provided with:
1. **BUD Document Path**: Path to the .docx file
2. **Output Directory**: Directory to save the mapping results
3. **Parsed Fields JSON** (optional): Pre-extracted fields with logic

**First action**: Parse the BUD document to extract reference tables and field definitions.

---

## Input

You will receive:
1. **Reference table data** - Table structure, headers, rows
2. **Field data** - Field name, type, logic, panel name
3. **Output file path** - Where to write the result

## Task

Analyze the provided reference table or field set and extract EDV metadata.

### For Reference Tables:
1. Generate appropriate EDV table name (UPPERCASE, underscores)
2. Map columns to EDV attributes (a1, a2, a3...)
3. Identify table purpose (dropdown_values, validation, lookup)
4. Convert sample data to EDV format

### For Field Mappings:
1. Analyze field logic to identify table references
2. Detect cascading relationships (keywords: "based on", "depends on", "filtered by")
3. Determine rule type (EXT_DROP_DOWN vs EXT_VALUE)
4. Identify parent field for cascading dropdowns
5. Specify filter columns and display columns

## Hard Constraints (Mandatory)

* Do **not** create permanent scripts
* Use only provided input data
* Output **exactly one JSON file** per invocation
* Follow exact output format specified below
* Abort immediately if input is invalid

Any deviation = incorrect behavior.

---

## EDV params Structure (Critical Reference)

### EXT_VALUE params (for auto-populated values)

```json
{
  "params": "[{\"conditionList\":[{\"ddType\":[\"TABLE_NAME\"],\"criterias\":[{\"a7\":275496}],\"da\":[\"a3\"],\"criteriaSearchAttr\":[],\"additionalOptions\":null,\"emptyAddOptionCheck\":null,\"ddProperties\":null}]}]"
}
```

**Key fields in conditionList**:
| Field | Description | Example |
|-------|-------------|---------|
| `ddType` | EDV table name (uppercase, underscores) | `["VC_VENDOR_TYPES"]` |
| `criterias` | Filter criteria: column → parent field ID | `[{"a7": 275496}]` |
| `da` | Display attribute/column to show | `["a3"]` |
| `criteriaSearchAttr` | Search attributes (usually empty) | `[]` |

### EXT_DROP_DOWN params (simple)

```json
{
  "params": "TABLE_NAME"
}
```

For simple dropdowns without filtering, params is just the table name string.

**Common EXT_DROP_DOWN params values found in production**:
- `YES_NO`, `CB_YES_NO`, `PIDILITE_YES_NO` - Yes/No dropdowns
- `INDIVIDUAL_GROUP`, `CB_IND_GROUP` - Individual/Group selection
- `LINK`, `LINK_EST_PRO` - Link type dropdowns
- `IND_ESTA` - Individual/Establishment
- `INACTIVE` - Active/Inactive status
- `COMPANY_CODE` - Company codes
- `COUNTRY` - Country list
- `CURRENCY_COUNTRY` - Currency codes
- `TITLE` - Salutation (Mr/Mrs/Ms)
- `WITHHOLDING_TAX_DATA` - Tax codes

### EXT_VALUE params patterns

**Pattern 1: Simple lookup (no filtering)**
```json
[{"conditionList":[{"ddType":["TABLE_NAME"]},{"da":["a1"]}]}]
```

**Pattern 2: With ddProperties (group property)**
```json
[{"conditionList":[{"ddType":["TABLE_NAME"]},{"ddProperties":"GROUP_NAME"},{"da":["a1"]}]}]
```

**Pattern 3: Single parent filtering (cascading)**
```json
[{"conditionList":[{"ddType":["TABLE_NAME"]},{"criterias":[{"a1":PARENT_FIELD_ID}]},{"da":["a2"]}]}]
```

**Pattern 4: Multi-parent filtering**
```json
[{"conditionList":[{"ddType":["TABLE_NAME"]},{"criterias":[{"a1":FIELD1_ID,"a2":FIELD2_ID}]},{"da":["a3"]}]}]
```

### Column Notation

EDV uses `a1`, `a2`, `a3`, etc. for columns:
- `a1` = Column 1 of the EDV table
- `a2` = Column 2 of the EDV table
- `a7` = Column 7 of the EDV table

---

## Step 1: Read Input Data

Read the input JSON file containing either:
- **Table data**: table_id, headers, rows, sample_data
- **Field data**: panel_name, fields array, reference_tables

### For Table Metadata Extraction

Input structure:
```json
{
  "table_id": "table_1",
  "reference_id": "1",
  "rows": 246,
  "columns": 6,
  "headers": ["Language Key", "Country/Region Key", ...],
  "sample_data": [["EN", "AD", "Andorran", ...], ...]
}
```

### For Field Mapping

Input structure:
```json
{
  "panel_name": "Basic Details",
  "fields": [
    {
      "field_name": "Country",
      "type": "EXTERNAL_DROP_DOWN_VALUE",
      "logic": "Dropdown values from table 1.1..."
    }
  ],
  "reference_tables": [
    {
      "edv_name": "COUNTRY",
      "columns": [{"index": 1, "attribute": "a1", ...}]
    }
  ]
}
```

---

## Step 2: Generate EDV Table Names

**Naming Convention**: Convert reference table identifier and purpose into EDV-compatible name.

### Rules for EDV Table Name Generation:

1. Use UPPERCASE letters
2. Use underscores for spaces
3. Include descriptive prefix based on content
4. Keep reasonably short but descriptive

### Examples:

| Reference | Content/Headers | Generated EDV Name |
|-----------|-----------------|-------------------|
| Table 1.3 | Vendor Type, Group | `VC_VENDOR_TYPES` |
| Table 1.2 | Company Code, Purchase Org | `COMPANY_CODE_PURCHASE_ORGANIZATION` |
| Table 2.1 | Country, Country Code | `COUNTRY` |
| Table 3.1 | Bank, IFSC Pattern | `BANK_OPTIONS` |
| Table 4.1 | Currency, Country | `CURRENCY_COUNTRY` |
| Table 5.1 | Title, Gender | `TITLE` |
| Table 6.1 | Withholding Tax Code | `WITHHOLDING_TAX_DATA` |

---

## Step 3: Detect Cascading Relationships (For Field Mapping)

### Pattern Detection in Field Logic

Identify cascading dropdowns by detecting these keywords:

```text
"based on"           → parent dependency
"depends on"         → parent dependency
"filtered by"        → parent filtering
"selection"          → parent selection
"if [field] then"    → conditional cascading
"column X based on column Y" → cascading lookup
```

### Parent-Child Relationship Structure

For each relationship, capture:
```json
{
  "parent_field": "Account Group/Vendor Type",
  "parent_field_id": 275496,
  "child_field": "Group key/Corporate Group",
  "child_field_id": 275498,
  "edv_table": "VC_VENDOR_TYPES",
  "filter_column": "a4",
  "display_column": "a1",
  "relationship_type": "cascading_dropdown"
}
```

### Column Mapping for Parent-Child

When BUD says:
- "first and second columns" → Parent gets `a1`, Child filters by `a1` shows `a2`
- "column N based on column M" → Filter by `aM`, display `aN`
- "second column based on first column selection" → Filter by `a1`, display `a2`

---

## Step 4: Generate Output

### For Table Metadata (Single Table)

Write JSON to output file:

```json
{
  "table_id": "table_1",
  "reference_id": "1",
  "edv_name": "COUNTRY_REGION",
  "purpose": "dropdown_values",
  "columns": [
    {
      "index": 1,
      "attribute": "a1",
      "header": "Country/Region Key",
      "data_type": "string"
    },
    {
      "index": 2,
      "attribute": "a2",
      "header": "Country/Region Name",
      "data_type": "string"
    }
  ],
  "row_count": 246,
  "sample_data": [
    {"a1": "AD", "a2": "Andorra"},
    {"a1": "AE", "a2": "United Arab Emirates"}
  ]
}
```

### For Field Mappings (Single Panel)

Write JSON array to output file:

```json
[
  {
    "field_name": "Account Group/Vendor Type",
    "type": "EXTERNAL_DROP_DOWN_VALUE",
    "panel_name": "Basic Details",
    "edv_table": "VC_VENDOR_TYPES",
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
    "edv_table": "VC_VENDOR_TYPES",
    "rule_type": "EXT_VALUE",
    "is_cascading": true,
    "parent_field": "Account Group/Vendor Type",
    "filter_column": "a1",
    "display_columns": ["a2"],
    "logic_reference": "Dropdown values will come based on the account group/vendor type selection"
  }
]
```

---

## Step 5: Understanding Rule Types - EDV vs API Verification

### CRITICAL: EDV Rules vs VERIFY Rules (API-Based)

**EDV rules** use `sourceType: "EXTERNAL_DATA_VALUE"` for table lookups:
- **EXT_VALUE** - Auto-populate/cascading dropdowns from EDV tables
- **VALIDATION** with EDV - Validate field values against EDV tables

**VERIFY rules** use API-based verification (NOT EDV!):
- `sourceType: "PAN_NUMBER"` - PAN API verification
- `sourceType: "GSTIN"` - GSTIN API verification
- `sourceType: "BANK_ACCOUNT_NUMBER"` - Bank account API verification
- `sourceType: "MSME_UDYAM_REG_NUMBER"` - MSME Udyam API verification

---

### EXT_DROP_DOWN (Simple Dropdown from EDV Table)

```json
{
  "actionType": "EXT_DROP_DOWN",
  "sourceType": "FORM_FILL_DROP_DOWN",  // NOT EXTERNAL_DATA_VALUE!
  "processingType": "CLIENT",
  "sourceIds": [275506],
  "params": "COMPANY_CODE",  // Simple string = EDV table name
  "searchable": true,
  "executeOnFill": true
}
```

### EXT_VALUE (Cascading Dropdown / Auto-Populate from EDV)

```json
{
  "actionType": "EXT_VALUE",
  "sourceType": "EXTERNAL_DATA_VALUE",
  "processingType": "CLIENT",
  "sourceIds": [276416],
  "params": "[{\"conditionList\":[{\"ddType\":[\"TABLE_NAME\"],\"criterias\":[{\"a7\":275496}],\"da\":[\"a3\"]}]}]"
}
```

### VALIDATION with EDV (Validate Against EDV Table)

```json
{
  "actionType": "VALIDATION",
  "sourceType": "EXTERNAL_DATA_VALUE",
  "processingType": "SERVER",
  "sourceIds": [275506],
  "destinationIds": [276399, 276400, 276383, 275629],
  "params": "COMPANY_CODE"  // Simple string = EDV table name
}
```

---

### BUD Logic Pattern → Rule Type Mapping

| BUD Logic Pattern | Rule Type | sourceType |
|-------------------|-----------|------------|
| "Dropdown values from table X.Y" | EXT_DROP_DOWN | FORM_FILL_DROP_DOWN |
| "Dropdown values are Yes/No" | EXT_DROP_DOWN | FORM_FILL_DROP_DOWN |
| "Based on {parent} selection" | EXT_VALUE | EXTERNAL_DATA_VALUE |
| "Cascading dropdown" | EXT_VALUE | EXTERNAL_DATA_VALUE |
| "Validate against EDV table" | VALIDATION | EXTERNAL_DATA_VALUE |
| "Perform PAN validation" | VERIFY | PAN_NUMBER |
| "Data will come from PAN validation" | (destination of VERIFY) | - |
| "Verify GSTIN" | VERIFY | GSTIN |
| "Data will come from GSTIN verification" | (destination of VERIFY) | - |
| "Perform Bank account verification" | VERIFY | BANK_ACCOUNT_NUMBER |
| "MSME validation" | VERIFY | MSME_UDYAM_REG_NUMBER |

---

## Output JSON Files

### File 1: EDV Table Registry

Filename: `<document_name>_edv_tables.json`

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-02-02T10:00:00Z"
  },
  "edv_tables": [
    {
      "reference_id": "1.3",
      "edv_name": "VC_VENDOR_TYPES",
      "original_title": "Reference Table 1.3",
      "columns": [
        {"index": 1, "attribute": "a1", "header": "Vendor Type"},
        {"index": 2, "attribute": "a2", "header": "Group Key"},
        {"index": 3, "attribute": "a3", "header": "Description"},
        {"index": 4, "attribute": "a4", "header": "Category Code"}
      ],
      "row_count": 15,
      "sample_data": [
        {"a1": "ZDES", "a2": "ZDES01", "a3": "Domestic Vendor"},
        {"a1": "ZIMP", "a2": "ZIMP01", "a3": "Import Vendor"}
      ],
      "used_by_fields": ["Account Group/Vendor Type", "Group key/Corporate Group"]
    }
  ],
  "table_name_mapping": {
    "1.3": "VC_VENDOR_TYPES",
    "1.2": "COMPANY_CODE_PURCHASE_ORGANIZATION",
    "2.1": "COUNTRY"
  },
  "summary": {
    "total_reference_tables": 6,
    "total_edv_tables_generated": 6
  }
}
```

### File 2: Field-EDV Mapping

Filename: `<document_name>_field_edv_mapping.json`

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-02-02T10:00:00Z"
  },
  "field_edv_mappings": [
    {
      "field_name": "Account Group/Vendor Type",
      "field_id": null,
      "panel_name": "Basic Details",
      "field_type": "DROPDOWN",
      "edv_config": {
        "rule_type": "EXT_DROP_DOWN",
        "edv_table": "VC_VENDOR_TYPES",
        "params_template": "VC_VENDOR_TYPES",
        "is_simple": true
      },
      "relationship": {
        "is_parent": true,
        "is_child": false,
        "children": ["Group key/Corporate Group"],
        "parent": null
      },
      "logic_excerpt": "Dropdown values are first and second columns of reference table 1.3"
    },
    {
      "field_name": "Group key/Corporate Group",
      "field_id": null,
      "panel_name": "Basic Details",
      "field_type": "DROPDOWN",
      "edv_config": {
        "rule_type": "EXT_VALUE",
        "edv_table": "VC_VENDOR_TYPES",
        "params_template": {
          "conditionList": [{
            "ddType": ["VC_VENDOR_TYPES"],
            "criterias": [{"a1": "{{parent_field_id}}"}],
            "da": ["a2"],
            "criteriaSearchAttr": [],
            "additionalOptions": null,
            "emptyAddOptionCheck": null,
            "ddProperties": null
          }]
        },
        "is_simple": false,
        "filter_column": "a1",
        "display_column": "a2"
      },
      "relationship": {
        "is_parent": false,
        "is_child": true,
        "children": [],
        "parent": "Account Group/Vendor Type"
      },
      "logic_excerpt": "Dropdown values will come based on the account group/vendor type selection"
    }
  ],
  "parent_child_chains": [
    {
      "chain_id": 1,
      "edv_table": "VC_VENDOR_TYPES",
      "chain": [
        {"field": "Account Group/Vendor Type", "role": "parent", "column": "a1"},
        {"field": "Group key/Corporate Group", "role": "child", "filter_by": "a1", "display": "a2"}
      ]
    }
  ],
  "validation_edv_fields": [
    {
      "field_name": "IFSC Code",
      "validation_type": "IFSC",
      "edv_table": "BANK_IFSC",
      "auto_populate_fields": ["Bank Name", "Bank Branch"]
    }
  ],
  "summary": {
    "total_fields_with_edv": 15,
    "parent_fields": 5,
    "child_fields": 8,
    "validation_fields": 2,
    "ext_dropdown_rules_needed": 10,
    "ext_value_rules_needed": 8
  }
}
```

---

## Step 6: Final Console Summary

Print:

```
=== EDV Table Mapping Complete ===

Document: Vendor Creation Sample BUD.docx

Reference Tables Found: 6
EDV Tables Generated: 6

Table Mappings:
  - 1.3 → VC_VENDOR_TYPES
  - 1.2 → COMPANY_CODE_PURCHASE_ORGANIZATION
  - 2.1 → COUNTRY
  ...

Fields with EDV Configuration: 15
  - Parent dropdowns: 5
  - Child dropdowns (cascading): 8
  - Validation fields: 2

Parent-Child Relationships: 3
  - Account Group/Vendor Type → Group key/Corporate Group
  - Country → State
  - Company Code → Purchase Organization

Output Files:
  - EDV Tables: extraction/edv_mapping_output/<date>/Vendor_Creation_Sample_BUD_edv_tables.json
  - Field Mapping: extraction/edv_mapping_output/<date>/Vendor_Creation_Sample_BUD_field_edv_mapping.json

IMPORTANT: The coding agent should use these mappings to generate correct EXT_VALUE and EXT_DROP_DOWN params.
```

---

## Integration with Rule Extraction Coding Agent

The output files should be passed to the coding agent as input:

```
--edv-tables extraction/edv_mapping_output/<date>/xxx_edv_tables.json
--field-edv-mapping extraction/edv_mapping_output/<date>/xxx_field_edv_mapping.json
```

The coding agent will use:
1. `table_name_mapping` to resolve "reference table X.Y" to EDV table name
2. `field_edv_mappings` to generate correct params structure
3. `parent_child_chains` to link EXT_VALUE rules correctly

---

## Enforcement

* Exactly one BUD document processed
* Exactly two output JSON files
* All reference tables must have generated EDV names
* All parent-child relationships must be detected
* No workflow deviations

This is a **deterministic extraction and mapping command**.
