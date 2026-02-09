---
name: EDV Rule Coding Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Stage 3 - Generates Python code for EDV rule params (EXT_DROP_DOWN, EXT_VALUE, VALIDATION).
---

# EDV Rule Coding Agent (Stage 3)

## Objective

Generate a Python script that populates `params` for EDV-related rules:
- EXT_DROP_DOWN (simple dropdown)
- EXT_VALUE (cascading/dependent dropdown)
- VALIDATION with EXTERNAL_DATA_VALUE sourceType

## Input Files

- `--schema`: Schema with rules (from Stage 2)
- `--edv-tables`: EDV tables mapping JSON (from dispatcher)
- `--field-edv-mapping`: Field-EDV mapping JSON (from dispatcher)
- `--keyword-tree`: Keyword tree JSON
- `--output`: Output path

## Output

Python script that populates params with deterministic table name extraction.

---

## Approach

### 1. EDV Table Mapping

Build lookup indexes from dispatcher outputs:
- `table_by_ref`: "table 1.3" → "VC_VENDOR_TYPES"
- `table_by_field`: "Company Code" → "COMPANY_CODE"

### 2. Table Reference Extraction

Extract table references from BUD logic text:

**Pattern: "reference table X.Y"**
```regex
reference\s+table\s+(\d+\.\d+)
table\s+(\d+\.\d+)
refer\s+table\s+(\d+\.\d+)
```

### 3. Params Formats by Rule Type

**EXT_DROP_DOWN (simple string):**
```
params = "TABLE_NAME"
```

**EXT_VALUE (JSON string with conditionList):**
```json
[{
  "conditionList": [{
    "ddType": ["TABLE_NAME"],
    "criterias": [{"a1": parent_field_id}],
    "da": ["a2"],
    "criteriaSearchAttr": [],
    "additionalOptions": null,
    "emptyAddOptionCheck": null,
    "ddProperties": null
  }]
}]
```

**VALIDATION with EXTERNAL_DATA_VALUE:**
- Simple: `params = "TABLE_NAME"`
- Complex: JSON with conditionList for multi-attribute validation

### 4. Cascading Dropdown Detection

Detect parent field from logic:
```regex
based\s+on\s+['"]?([^'"]+)['"]?\s+selection
depends\s+on\s+['"]?([^'"]+)['"]?
```

Find parent field ID from field index.

### 5. Table Name Extraction Algorithm

```
1. Check field-EDV mapping first
2. Extract table reference from logic (pattern matching)
3. Look up reference in table_by_ref index
4. Check for YES/NO pattern → YES_NO table
5. Fallback: Generate table name from field name (uppercase, underscores)
```

### 6. Special Cases

**YES/NO fields:**
- Logic contains "yes" and "no"
- Map to YES_NO or similar table

**Multi-attribute validation:**
- Logic mentions "condition", "attribute", "multiple"
- Build conditionList structure

**Searchable dropdown:**
- Set `searchable = True` for EXT_DROP_DOWN rules

---

## Code Requirements

### CLI Interface
```
python stage_3_edv_rules.py \
    --schema input.json \
    --edv-tables edv_tables.json \
    --field-edv-mapping field_mapping.json \
    --keyword-tree keyword_tree.json \
    --output output.json \
    --verbose
```

### Required Classes/Functions

1. **EDVTableMapper** - Maps BUD references to EDV tables
   - `_build_indexes()` - Build lookup maps
   - `extract_table_reference(logic)` - Extract "table X.Y" from logic
   - `get_table_name(field_name, logic)` - Get EDV table name

2. **EDVParamsBuilder** - Builds params for EDV rules
   - `_build_field_index()` - Build field ID lookup
   - `build_ext_dropdown_params(rule, field)` - Simple dropdown
   - `build_ext_value_params(rule, field)` - Cascading dropdown
   - `build_edv_validation_params(rule, field)` - Validation
   - `_find_parent_field(logic)` - Find parent field ID
   - `_needs_condition_list(logic)` - Check if complex validation
   - `_build_condition_list(logic)` - Build validation conditions
   - `process_rule(rule, field)` - Process single rule
   - `process_schema(schema)` - Process entire schema
   - `print_stats()` - Print statistics

### Statistics to Track
- `ext_dropdown`: EXT_DROP_DOWN rules processed
- `ext_value`: EXT_VALUE rules processed
- `edv_validation`: EDV VALIDATION rules processed
- `deterministic`: Table names found via patterns
- `llm_fallback`: Table names via LLM
- `failed`: Rules without table mapping

### Logging Requirements

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Loaded {count} table references, {count} field mappings")
logger.debug(f"Table from field mapping: {field_name} -> {table}")
logger.debug(f"Table from reference: {ref} -> {table}")
logger.warning(f"No table found for {field_name}, using fallback")
```

---

## Eval Check

- EXT_DROP_DOWN has string params (table name)
- EXT_VALUE has valid JSON params
- Table names extracted correctly (not hardcoded)
- Cascading dropdowns have parent field reference
