---
name: Rule Type Placement Coding Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Stage 1 - Generates Python code for rule type detection using deterministic-first approach.
---

# Rule Type Placement Coding Agent (Stage 1)

## Objective

Generate a Python script that determines which rule types (actionType + sourceType) each field needs and places skeleton rules on the correct fields.

**Pipeline Context**: This is Step 3 of the workflow:
1. Parse BUD document → field logic extraction
2. Merge logic into schema → `preFillData.value` population
3. **Rule placement** (this script) → skeleton rules with actionType + sourceType

## Input Files

- `--schema`: Schema JSON from extract_fields_complete.py
- `--keyword-tree`: `rule_extractor/static/keyword_tree.json`
- `--rule-schemas`: `rules/Rule-Schemas.json` (182 predefined rule definitions)
- `--edv-tables`: EDV tables JSON (maps reference table IDs like "1.1" to EDV table names)
- `--edv-mapping`: Field-to-EDV mapping JSON (field_name → rule_type, edv_table, parent/child relationships)
- `--intra-panel`: Intra-panel references JSON
- `--inter-panel`: Inter-panel references JSON
- `--rule-info`: Rule info meta-rules JSON
- `--output`: Output path for generated JSON

### EDV Input Files Structure

**edv-tables JSON** (e.g., `Vendor_Creation_Sample_BUD_edv_tables.json`):
```json
{
  "table_name_mapping": {
    "1.1": "COLUMN_NAME",
    "1.2": "COUNTRY",
    "1.3": "VC_VENDOR_TYPES"
  },
  "edv_tables": [
    {
      "reference_id": "1.1",
      "edv_name": "COLUMN_NAME",
      "columns": [{"index": 1, "attribute": "a1", "header": "Column Name"}],
      "used_by_fields": ["Country", "Country Name", "Country Code"]
    }
  ]
}
```

**edv-mapping JSON** (e.g., `Vendor_Creation_Sample_BUD_field_edv_mapping.json`):
```json
{
  "field_edv_mappings": [
    {
      "field_name": "Country",
      "field_type": "DROPDOWN",
      "edv_config": {
        "rule_type": "EXT_VALUE",
        "edv_table": "COLUMN_NAME",
        "is_simple": false
      },
      "relationship": {
        "is_parent": true,
        "children": ["Country Name", "Country Code"]
      },
      "table_refs": ["1.1"],
      "column_refs": {"columns": [2, 5]}
    },
    {
      "field_name": "Country Name",
      "field_type": "TEXT",
      "edv_config": {
        "rule_type": "VALIDATION",
        "edv_table": "COLUMN_NAME"
      },
      "relationship": {
        "is_child": true,
        "parent": "Country"
      },
      "logic_excerpt": "derive the country name as column 5 on table 1.1"
    }
  ],
  "parent_child_chains": [
    {
      "chain_id": 1,
      "edv_table": "VC_VENDOR_TYPES",
      "chain": [
        {"field": "Account Group/Vendor Type", "role": "parent"},
        {"field": "Group key/Corporate Group", "role": "child", "filter_by": "a2"}
      ]
    }
  ]
}
```

## Output

Python script that produces schema with skeleton rules placed on fields.

**IMPORTANT Schema Structure**: The schema follows this format:
```
schema['template']['documentTypes'][0]['formFillMetadatas']
```
Each field in `formFillMetadatas` has:
- `formTag`: Contains `id`, `name`, `type`
- `preFillData.value`: Contains the logic/rules text
- `formFillRules`: Array to populate with skeleton rules (clear existing before processing)

**NOT** `schema['panels'][].formTags[]` format!

---

## Approach

### 1. Keyword Tree Structure

Read `keyword_tree.json` which contains:
- `l1_action_types`: Maps keywords to actionTypes (VERIFY, OCR, EXT_DROP_DOWN, etc.)
- Each actionType has `source_types` mapping keywords to sourceTypes
- `skip_patterns`: Fields to skip (mvi, mm, expr-eval)
- `destination_field_patterns`: Fields that receive data from other rules

### 2. Two-Level Pattern Matching

**L1 Detection (actionType):**
- Compile regex patterns from `l1_action_types` keywords
- Match field logic against all L1 patterns
- **Skip negated matches** (e.g., "editable" in "Non-Editable")
- Collect ALL matched actionTypes (field can have multiple rules)

**L2 Detection (sourceType):**
- For each matched actionType, look up its `source_types`
- Match field logic against L2 patterns to determine sourceType
- If no L2 match, use default sourceType for that actionType

### 3. Rule Schema Lookup (Rule-Schemas.json)

Once actionType + sourceType is determined, **lookup the full rule definition** from `rules/Rule-Schemas.json` to enrich the skeleton rule. The schema contains 182 predefined rules with 100 unique actionTypes and 82 unique sourceTypes.

**Available fields per rule in Rule-Schemas.json:**

| Field | Description |
|-------|-------------|
| `id` | Unique rule identifier (e.g., 348) |
| `name` | Human-readable rule name (e.g., "Aadhaar Back OCR") |
| `source` | sourceType value (e.g., "AADHAR_BACK_IMAGE") |
| `action` | actionType value (e.g., "OCR", "VERIFY") |
| `processingType` | SERVER or CLIENT - use this instead of hardcoding |
| `applicableTypes` | Field types this rule applies to |
| `destinationFields` | Expected destination fields with ordinals and mandatory flags |
| `params` | JSON schema defining required parameters |
| `conditionsRequired` | Whether conditions must be specified |
| `validatable` | Whether the rule is validatable |
| `button` | Button text (e.g., "Verify") |

**Lookup by action + source:**
```python
def lookup_rule(action_type: str, source_type: str) -> dict | None:
    for rule in rule_schemas['content']:
        if rule['action'] == action_type and rule.get('source') == source_type:
            return rule
    return None
```

**Key benefit:** The agent does NOT need to hardcode processingType, params schema, or destinationFields - these come directly from Rule-Schemas.json.

### 4. Field Processing Logic

For each field in schema:
1. **Skip fields with no logic** - If `preFillData.value` is empty/missing, skip the field (not in BUD)
2. **Check skip patterns** - Skip if logic matches skip patterns
3. **Check destination patterns** - If field receives data (e.g., "Data will come from OCR"), only add MAKE_DISABLED if "non-editable"
4. **Match actionTypes** - Run L1 matching on field logic
5. **Match sourceTypes** - For each actionType, run L2 matching
6. **Create skeleton rules** - Create rule structures with actionType, sourceType, processingType

### 5. Skeleton Rule Structure

After matching and schema lookup, create enriched skeleton rules:

```json
{
  "actionType": "VERIFY",
  "sourceType": "PAN_NUMBER",
  "processingType": "SERVER",
  "sourceIds": [],
  "destinationIds": [],
  "postTriggerRuleIds": [],
  "params": null,
  "condition": null,
  "conditionalValues": null,
  "_field_id": 123,
  "_schema_rule_id": 123,
  "_schema_rule_name": "Validate PAN",
  "_destination_fields_schema": {
    "numberOfItems": 4,
    "fields": [
      {"name": "name", "ordinal": 1, "mandatory": false},
      {"name": "panStatus", "ordinal": 2, "mandatory": false}
    ]
  },
  "_params_schema": {"paramType": "json", "jsonSchema": {...}},
  "_conditions_required": true
}
```

**Note:** Fields prefixed with `_` are metadata for downstream stages. The `processingType` is retrieved from Rule-Schemas.json rather than hardcoded.

### 6. Processing Type Determination (Fallback)

If no matching rule found in Rule-Schemas.json, use these defaults:
- **SERVER**: VERIFY, OCR, VALIDATION (requires backend processing)
- **CLIENT**: MAKE_VISIBLE, MAKE_DISABLED, MAKE_MANDATORY, EXT_DROP_DOWN (UI-only)

### 7. Default Source Types

When no L2 pattern matches:
- MAKE_VISIBLE → RULE_CHECK
- MAKE_DISABLED → RULE_CHECK
- MAKE_MANDATORY → RULE_CHECK
- SET_VALUE → FORM_FILL

---

## CRITICAL: EDV (External Data Value) Rules

### Understanding Reference Tables and EDV

When BUD logic mentions **"reference table X.X"** or **"table X.X"**, it refers to an **EDV (External Data Value) table**. The reference number (1.1, 1.2, etc.) maps to an actual EDV table name.

**IMPORTANT:** Do NOT use `EXT_DROP_DOWN` + `FORM_FILL_DROP_DOWN` for dropdowns with reference tables. Instead use:
- **`EXT_VALUE`** + **`EXTERNAL_DATA_VALUE`** for cascading/dependent dropdowns
- **`VALIDATION`** + **`EXTERNAL_DATA_VALUE`** for deriving field values from table lookups

**CRITICAL RULE - Only ONE EDV VALIDATE per Source Field:**
When a dropdown field populates multiple destination TEXT fields from an EDV table:
- ✅ **DO** create ONE `VALIDATION` + `EXTERNAL_DATA_VALUE` rule on the SOURCE dropdown field
- ❌ **DO NOT** create separate VALIDATION rules on each destination TEXT field
- The single VALIDATION rule will have a `destinationIds` array mapping table columns to destination fields (populated in Stage 2)

**Example:**
```
Source: Country (DROPDOWN) → uses table 1.1
Destinations: Country Name (TEXT), Country Code (TEXT)

CORRECT (Stage 1):
- Country field: EXT_VALUE + EXTERNAL_DATA_VALUE (for dropdown options)
- Country field: VALIDATION + EXTERNAL_DATA_VALUE (ONE rule, destinationIds populated in Stage 2)
- Country Name: NO VALIDATION rule (receives data via Country's destinationIds)
- Country Code: NO VALIDATION rule (receives data via Country's destinationIds)

WRONG:
- Country Name: VALIDATION + EXTERNAL_DATA_VALUE ❌
- Country Code: VALIDATION + EXTERNAL_DATA_VALUE ❌
```

See `documentations/STAGE2_EDV_VALIDATE_FIX.md` for complete details.

### Rule Type Selection for EDV Fields

| BUD Pattern | actionType | sourceType | processingType |
|-------------|------------|------------|----------------|
| "dropdown values refer table X.X" | `EXT_VALUE` | `EXTERNAL_DATA_VALUE` | CLIENT |
| "based on selection...column of table" | `EXT_VALUE` | `EXTERNAL_DATA_VALUE` | CLIENT |
| "derive X from column Y of table" | `VALIDATION` | `EXTERNAL_DATA_VALUE` | SERVER |
| "derive value from selection" | `VALIDATION` | `EXTERNAL_DATA_VALUE` | SERVER |
| "column X will come from table Y" | `VALIDATION` | `EXTERNAL_DATA_VALUE` | SERVER |

### Keyword Detection for EDV Rules

**EXT_VALUE (Cascading Dropdown) - CLIENT:**
```
Keywords: "based on", "selection", "cascading", "dependent", "parent", "column of reference table"
BUD phrases:
- "dropdown values will come based on"
- "based on the X selection field as column Y of reference table"
- "dropdown values refer table X.X"
- "first and second columns of reference table"
- "column 2 - column 5 of reference table"
```

**VALIDATION with EXTERNAL_DATA_VALUE (Derive/Fetch) - SERVER:**
```
Keywords: "derive", "derived from", "fetch from", "populate from", "come from table"
BUD phrases:
- "derive the X as column Y on table Z"
- "if X is selected then derive Y from table"
- "value will be fetched from table"
- "auto-derived from reference table"
```

### Example: Country/Country Code/Country Name Pattern

BUD text example:
```
Country       DROPDOWN  Yes  If Select process type is India then country is India and
                             Noneditable. For dropdown values will be Column 2-5 of
                             reference table 1.1.
Country Name  TEXT      No   Not visible. If Country is selected then derive the country
                             name as column 5 on table 1.1
Country Code  TEXT      No   Not visible. If Country is selected then derive the country
                             code as column 2 on table 1.1
```

**Generated rules (Stage 1):**

1. **Country field** (DROPDOWN/TEXT with "selectable" in logic):
   - `actionType: "EXT_VALUE"`, `sourceType: "EXTERNAL_DATA_VALUE"` - for dropdown options
   - `actionType: "VALIDATION"`, `sourceType: "EXTERNAL_DATA_VALUE"` - ONE rule to populate destinations
   - `actionType: "MAKE_DISABLED"` - when process type is India

2. **Country Name field** (TEXT - destination):
   - **SKIPPED** (0 rules) - receives data via Country field's destinationIds array (populated in Stage 2)

3. **Country Code field** (TEXT - destination):
   - **SKIPPED** (0 rules) - receives data via Country field's destinationIds array (populated in Stage 2)

### Parent-Child Dropdown Relationships

When a dropdown's values depend on another field's selection:

```
Field: Account Group/Vendor Type
Logic: "Dropdown values are first and second columns of reference table 1.3"
Rule: actionType="EXT_VALUE", sourceType="EXTERNAL_DATA_VALUE"

Field: Group key/Corporate Group
Logic: "Dropdown values will come based on account group/vendor type selection as 2nd column of table 1.3"
Rule: actionType="EXT_VALUE", sourceType="EXTERNAL_DATA_VALUE"
      (with params containing conditionList referencing parent field)
```

### Reference Table Detection Helper

Add a method to detect if logic mentions reference tables:

```python
def _has_reference_table_pattern(self, logic: str) -> bool:
    """Detect if logic mentions reference tables (e.g., 'table 1.1', 'reference table')"""
    patterns = [
        r'\breference\s+table\s+\d+\.\d+',
        r'\btable\s+\d+\.\d+',
        r'\bcolumn\s+\d+.*\btable\s+\d+',
        r'\bcolumn\s+\d+\s*-\s*column\s+\d+\s+of\s+(reference\s+)?table',
    ]
    for pattern in patterns:
        if re.search(pattern, logic.lower()):
            return True
    return False
```

### Logic-Based Dropdown Detection

Some fields have type TEXT but logic says "dropdown" or "selectable". Detect these:

```python
# Check both field type AND logic for dropdown patterns
is_dropdown_by_type = field_type in ['DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROPDOWN']
is_dropdown_by_logic = re.search(r'\b(dropdown|drop\s*down|selectable)\b', logic.lower())

if self._has_reference_table_pattern(logic) and (is_dropdown_by_type or is_dropdown_by_logic):
    # Create EXT_VALUE + EXTERNAL_DATA_VALUE
    pass
```

### Skip TEXT Fields Deriving from EDV

TEXT fields that receive derived values from EDV tables should be **skipped** (they receive data via parent field's destinationIds):

```python
# Skip TEXT fields that derive from EDV tables
if field_type == 'TEXT' and self._has_reference_table_pattern(logic):
    if re.search(r'\b(derive|fetch|populated?|will come)\b', logic.lower()):
        logger.debug(f"Skipping TEXT field {field_name} - derives from EDV")
        self.stats.skipped += 1
        return
```

### Key Pattern Recognition

**Pattern 1: Simple EDV Dropdown**
- "dropdown values refer table X.X"
- "refer Table X.X for dropdown values"
→ `EXT_VALUE` + `EXTERNAL_DATA_VALUE`

**Pattern 2: Cascading/Dependent Dropdown**
- "based on X selection"
- "will come from column Y based on Z"
→ `EXT_VALUE` + `EXTERNAL_DATA_VALUE` with parent reference

**Pattern 3: Derived/Fetched Value (Non-dropdown)**
- "derive X from table"
- "fetch from table"
- "if X selected then Y comes from table column Z"
→ **SKIP** (receives data via parent's destinationIds in Stage 2)

### DO NOT USE

- ❌ `EXT_DROP_DOWN` + `FORM_FILL_DROP_DOWN` for reference table dropdowns
- ❌ Hardcoded yes/no values when reference table is mentioned

### Input Files for EDV Mapping

If available, use these additional input files for EDV context:
- `--edv-tables`: EDV tables JSON (maps reference_id to edv_name)
- `--edv-mapping`: Field-to-EDV mapping JSON (field_name → rule_type, edv_table)

---

### 8. LLM Modes (Optional)

**Mode 1: LLM Fallback** (--enable-llm)
- Use LLM only when L2 sourceType matching fails
- Get candidate sourceTypes for the actionType
- Call LLM with field logic and candidates
- Track LLM usage in stats

**Mode 2: LLM-Only** (--use-llm-only)
- Bypass pattern matching entirely
- Extract ALL rules directly from logic via LLM
- Returns list of (actionType, sourceType) pairs

---

## Code Requirements

### CLI Interface
```
python stage_1_rule_placement.py \
    --schema input.json \
    --keyword-tree keyword_tree.json \
    --rule-schemas rules/Rule-Schemas.json \
    --edv-tables edv_tables.json \
    --edv-mapping field_edv_mapping.json \
    --output output.json \
    [--enable-llm | --use-llm-only] \
    [--verbose]
```

### Required Classes/Functions

1. **KeywordTreeMatcher** - Loads and compiles patterns from keyword_tree.json
   - `_compile_l1_patterns()` - Compile actionType patterns
   - `_compile_l2_patterns()` - Compile sourceType patterns
   - `_is_negated(logic, keyword, match_pos)` - Check if match is negated (e.g., "editable" in "Non-Editable")
   - `should_skip(logic)` - Check skip patterns
   - `is_destination_field(logic)` - Check destination patterns
   - `match_action_type(logic)` - Return list of matched actionTypes (skip negated)
   - `match_source_type(logic, action_type)` - Return sourceType

   **Negation Detection**: Look back 20 chars before match for: `non-`, `not `, `un-`, `in-`, `dis-`

2. **RuleSchemaLookup** - Loads and queries Rule-Schemas.json
   - `__init__(schema_path)` - Load and index the 182 predefined rules
   - `_build_index()` - Build lookup index by (action, source) tuple
   - `lookup(action_type, source_type)` - Return full rule definition or None
   - `get_processing_type(action_type, source_type)` - Return SERVER/CLIENT
   - `get_destination_fields(action_type, source_type)` - Return expected destinations
   - `get_params_schema(action_type, source_type)` - Return params JSON schema
   - `get_rule_id(action_type, source_type)` - Return rule id for reference

3. **EDVMappingHandler** - Loads and queries EDV mapping files
   - `__init__(edv_tables_path, edv_mapping_path)` - Load EDV configuration
   - `get_field_edv_config(field_name)` - Return EDV config for field or None
   - `get_rule_type_for_field(field_name)` - Return EXT_VALUE or VALIDATION
   - `get_edv_table_for_field(field_name)` - Return EDV table name
   - `is_parent_field(field_name)` - Check if field is a parent in chain
   - `get_children_fields(field_name)` - Get child fields for parent
   - `get_parent_field(field_name)` - Get parent field for child
   - `resolve_table_reference(ref_id)` - Convert "1.1" to "COLUMN_NAME"

4. **LLMFallback** - Optional LLM-based matching
   - `__init__(enabled=False, use_llm_only=False)` - Initialize with mode
   - `match_source_type(logic, action_type, candidates)` - Fallback for L2
   - `extract_rules_from_logic(logic, field_type)` - LLM-only mode
   - Model: GPT-4o-mini, temperature=0.0
   - Track usage in stats

5. **RuleTypePlacer** - Main processing class
   - `__init__(matcher, schema_lookup, edv_handler, llm_fallback)` - Initialize with all dependencies
   - `process_schema(schema)` - Process entire schema (**MUST clear all existing formFillRules first**)
   - `_process_single_field(field, panel_name)` - Process single field, add rules to formFillRules
   - `_process_edv_field(field, edv_config)` - Handle EDV-mapped fields
   - `_has_reference_table_pattern(logic)` - Detect reference table mentions (table X.X patterns)
   - `_is_dropdown_field(field_type)` - Check if field type is dropdown variant
   - `_detect_supplementary_rules(logic, field_type, existing_actions)` - Find additional rules missed by patterns
   - `_create_skeleton_rule(action_type, source_type, field)` - Create rule with schema enrichment
   - `_enrich_skeleton_rule(rule, schema_lookup)` - Add schema metadata to skeleton
   - `print_stats()` - Print final statistics

   **CRITICAL**: `process_schema()` MUST clear all `formFillRules` arrays before processing:
   ```python
   for field in fields:
       field['formFillRules'] = []  # Clear existing rules
   ```

   **CRITICAL**: `_process_single_field()` MUST skip fields with no logic:
   ```python
   logic = field.get('preFillData', {}).get('value', '').strip()
   if not logic:
       logger.debug(f"Skipping field {field_name} (no logic from BUD)")
       self.stats.skipped += 1
       return
   ```

   **Supplementary Patterns** to detect:
   - Conditional visibility: "if X then visible" → MAKE_VISIBLE + MAKE_INVISIBLE
   - Derive from validation: "data from PAN validation" → VALIDATION + PAN_NUMBER
   - Conditional mandatory: "if X then mandatory" → MAKE_MANDATORY + MAKE_NON_MANDATORY
   - Non-editable derived: "non-editable, data from" → MAKE_DISABLED + VALIDATION

### Statistics to Track
- `total_fields`: Total fields processed
- `skipped`: Fields skipped due to skip patterns
- `destination_only`: Fields marked as destination
- `rules_placed`: Total skeleton rules created
- `deterministic_matches`: L2 matches via patterns
- `llm_matches`: L2 matches via LLM fallback
- `no_match`: Fields with no actionType match
- `schema_lookups_found`: Rules found in Rule-Schemas.json
- `schema_lookups_missing`: Rules not found in Rule-Schemas.json (used fallback)
- `edv_rules_placed`: EDV rules from EDV mapping files
- `edv_ext_value`: EXT_VALUE + EXTERNAL_DATA_VALUE rules
- `edv_validation`: VALIDATION + EXTERNAL_DATA_VALUE rules

### Logging Requirements

```python
import logging
logger = logging.getLogger(__name__)

# Log at appropriate levels:
logger.debug("Pattern match details")
logger.info("Processing panel: {panel_name}")
logger.warning("No sourceType found for {actionType}")
logger.error("Failed to load file: {path}")
```

---

## Eval Check

- Script runs without errors
- Produces valid JSON with `formFillRules` arrays
- ActionTypes match reference within threshold
- Statistics show deterministic-first behavior
- Logging demonstrates processing flow
- Skeleton rules contain enriched metadata from Rule-Schemas.json
- processingType values come from schema lookup (not hardcoded)
- **EDV rules use correct actionType/sourceType:**
  - Dropdowns with reference tables → `EXT_VALUE` + `EXTERNAL_DATA_VALUE`
  - Fields deriving values from tables → `VALIDATION` + `EXTERNAL_DATA_VALUE`
  - NO `EXT_DROP_DOWN` + `FORM_FILL_DROP_DOWN` for reference table dropdowns
- Parent-child relationships captured in rule metadata
