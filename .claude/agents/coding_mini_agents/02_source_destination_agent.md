---
name: Source Destination Coding Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Stage 2 - Generates Python code for populating sourceIds and destinationIds.
---

# Source Destination Coding Agent (Stage 2)

## Objective

Generate a Python script that populates `sourceIds` and `destinationIds` arrays for all skeleton rules from Stage 1.

## Input Files

- `--schema`: Schema with skeleton rules (from Stage 1)
- `--rule-schemas`: `rules/Rule-Schemas.json` for ordinal mapping
- `--intra-panel`: Intra-panel references JSON
- `--inter-panel`: Inter-panel references JSON
- `--keyword-tree`: Keyword tree JSON
- `--output`: Output path

## Output

Python script that populates sourceIds/destinationIds with deterministic-first approach.

---

## Approach

### 1. Build Field Index

Create fast lookup maps:
- `name_to_id`: field name (lowercase) → field ID
- `id_to_field`: field ID → field object
- `name_to_field`: field name → field object
- `panel_fields`: panel name → list of fields

Support fuzzy matching with `difflib.SequenceMatcher` (threshold 0.8).

### 2. Rule-Schemas Integration

Load `rules/Rule-Schemas.json` for ordinal mapping:
- `numberOfItems` - determines destinationIds array length
- `fields` - maps ordinal positions to field names
- Index schemas by sourceType for quick lookup

### 3. Population by Rule Type

**VERIFY Rules:**
- `sourceIds` = [field being verified]
- `destinationIds` = ordinal array from Rule-Schemas
- Map field names to ordinal positions
- Use -1 for unmapped ordinals

**OCR Rules:**
- `sourceIds` = [FILE upload field]
- `destinationIds` = fields receiving OCR data
- Look for "Data will come from OCR" in other fields' logic

**Visibility Rules (MAKE_VISIBLE, MAKE_INVISIBLE, MAKE_MANDATORY, MAKE_OPTIONAL):**
- `sourceIds` = [controlling field]
- `destinationIds` = ALL fields controlled by this field
- Search for pattern: "if field 'X' is Y then visible"

**MAKE_DISABLED Rules:**
- `sourceIds` = [field itself]
- `destinationIds` = [field itself]
- Used for RULE_CHECK sourceType

**Dropdown Rules (EXT_DROP_DOWN, EXT_VALUE):**
- `sourceIds` = [dropdown field itself]
- `destinationIds` = [] (empty for simple dropdowns)
- Cascading dropdowns have parent-child relationship

**EDV VALIDATION Rules (VALIDATION + EXTERNAL_DATA_VALUE):**
- **CRITICAL:** These rules are created ONLY on the source dropdown field (Stage 1)
- `sourceIds` = [source dropdown field ID]
- `destinationIds` = Column-to-field mapping array (Stage 2 responsibility)
- Array length = number of columns in EDV table
- Array position corresponds to table column order
- Use `-1` for columns NOT mapped to any field
- Use `field_id` for columns that populate specific fields
- See `documentations/STAGE2_EDV_VALIDATE_FIX.md` for details

### 4. Reference Extraction

**From intra-panel references:**
- Source field → destination fields mappings
- Within same panel

**From inter-panel references:**
- Cross-panel field dependencies
- May need to resolve panel names to field IDs

### 5. Special Cases

**Multi-source VERIFY:**
- BANK_ACCOUNT_NUMBER needs [IFSC_ID, Account_ID]
- GSTIN_WITH_PAN needs [PAN_ID, GSTIN_ID]

**OCR destinations:**
- Find all fields with "Data will come from OCR"
- Also check intra-panel references

**Aggregated visibility rules:**
- One controlling field may affect many destination fields
- Collect ALL dependent fields into single destinationIds array

### 6. Ordinal Mapping Algorithm

For VERIFY rules with Rule-Schemas:
```
1. Get numberOfItems from schema
2. Initialize destinationIds = [-1] * numberOfItems
3. For each field in schema.fields:
   a. Get ordinal position (1-indexed)
   b. Find matching field by name (fuzzy)
   c. If found: destinationIds[ordinal-1] = field_id
4. Return destinationIds
```

### 7. EDV VALIDATE destinationIds Mapping Algorithm

**CRITICAL:** EDV VALIDATE rules (VALIDATION + EXTERNAL_DATA_VALUE) have special destinationIds mapping.

**Algorithm:**
```
1. Identify EDV VALIDATE rule on source dropdown field
2. Load corresponding EDV table structure
3. Get number of columns: num_columns = len(edv_table['columns'])
4. Initialize destinationIds = [-1] * num_columns
5. Find all destination fields that receive data from this dropdown:
   a. Parse field logic for "derive...from column X"
   b. Use intra-panel/inter-panel references
   c. Use EDV mapping metadata (_edv_config, _destination_field_names)
6. For each destination field:
   a. Determine which column it maps to (parse "column N" from logic)
   b. Convert to 0-based index: column_index = N - 1
   c. Set destinationIds[column_index] = destination_field_id
7. Columns used for cascading dropdowns: keep as -1
8. Columns not referenced anywhere: keep as -1
9. Return destinationIds array
```

**Example - Country Dropdown:**
```python
# Table 1.1 (COLUMN_NAME) has 5 columns: a1, a2, a3, a4, a5
# Country uses columns 2-5 for dropdown display
# Country Code (field 11) derives from column 2
# Country Name (field 10) derives from column 5
# Columns 1, 3, 4 are not used for population

destinationIds = [-1, 11, -1, -1, 10]
# Position 0 (column a1): -1 (not populated)
# Position 1 (column a2): 11 (Country Code field)
# Position 2 (column a3): -1 (not populated)
# Position 3 (column a4): -1 (not populated)
# Position 4 (column a5): 10 (Country Name field)
```

**Key Points:**
- ONE EDV VALIDATE rule per source dropdown (created in Stage 1)
- destinationIds array maps TABLE COLUMNS to FIELDS
- Array order matches EDV table column order
- -1 means "column not mapped to any field"
- field_id means "column populates this field"
- Cascading dropdown columns always use -1 (they don't populate fields)

**Reference:** See `documentations/STAGE2_EDV_VALIDATE_FIX.md` for comprehensive explanation and examples.

---

## Code Requirements

### CLI Interface
```
python stage_2_source_dest.py \
    --schema input.json \
    --rule-schemas Rule-Schemas.json \
    --intra-panel intra_refs.json \
    --inter-panel inter_refs.json \
    --keyword-tree keyword_tree.json \
    --output output.json \
    --verbose
```

### Required Classes/Functions

1. **FieldIndex** - Fast field lookups
   - `_build_index(schema)` - Build all lookup maps
   - `find_by_name(name, threshold=0.8)` - Fuzzy match field
   - `get_field(field_id)` - Get field by ID

2. **RuleSchemasLoader** - Rule-Schemas integration
   - `_index_by_source_type()` - Index for quick lookup
   - `get_destination_schema(source_type)` - Get dest field schema
   - `get_num_items(source_type)` - Get numberOfItems

3. **EDVTableLoader** - Load and manage EDV table structures
   - `load_edv_tables(edv_tables_path)` - Load EDV table configs
   - `get_table_by_name(table_name)` - Get EDV table config
   - `get_column_count(table_name)` - Get number of columns
   - `get_column_order(table_name)` - Get ordered list of column names

4. **SourceDestPopulator** - Main processing class
   - `populate_verify_rule(rule, field)` - Handle VERIFY
   - `populate_ocr_rule(rule, field)` - Handle OCR
   - `populate_visibility_rule(rule, field)` - Handle visibility
   - `populate_dropdown_rule(rule, field)` - Handle dropdowns
   - `populate_make_disabled_rule(rule, field)` - Handle disabled
   - `populate_edv_validate_rule(rule, field)` - Handle EDV VALIDATION (NEW)
   - `_map_destination_ordinals()` - Map to ordinal positions
   - `_map_edv_columns_to_fields()` - Map EDV table columns to destination fields (NEW)
   - `_parse_column_reference()` - Extract column number from logic text (NEW)
   - `_find_visibility_destinations()` - Find dependent fields
   - `_find_ocr_destinations()` - Find OCR target fields
   - `process_schema(schema)` - Process entire schema
   - `print_stats()` - Print statistics

### Statistics to Track
- `rules_processed`: Total rules processed
- `source_ids_set`: Rules with sourceIds populated
- `dest_ids_set`: Rules with destinationIds populated
- `deterministic`: Matches via pattern/reference
- `llm_fallback`: Matches via LLM
- `failed`: Rules that couldn't be populated

### Logging Requirements

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Indexed {count} fields across {panels} panels")
logger.debug(f"Fuzzy matched '{name}' -> ID {id} (score: {score:.2f})")
logger.info(f"Processing panel: {panel_name}")
logger.warning(f"Unknown actionType: {action_type}")
```

---

## Eval Check

- All sourceIds reference valid field IDs
- destinationIds arrays have correct length
- Multi-source rules have all required IDs
- Ordinal positions match Rule-Schemas
- **EDV VALIDATE rules:**
  - Only ONE VALIDATE rule per source dropdown (not on destination fields)
  - destinationIds array length matches EDV table column count
  - Unmapped columns have -1 in destinationIds
  - Mapped columns have correct field_id in destinationIds
  - Column order in destinationIds matches EDV table column order
  - Cascading dropdown columns use -1 (not populated to fields)
