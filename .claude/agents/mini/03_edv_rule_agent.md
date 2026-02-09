---
name: EDV Rule Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Stage 3 - Generates EXT_DROP_DOWN, EXT_VALUE, and EDV VALIDATION rules with correct params.
---

# EDV Rule Agent (Stage 3)

## Objective
Generate `params` for EDV-related rules: EXT_DROP_DOWN, EXT_VALUE, and VALIDATION with EXTERNAL_DATA_VALUE sourceType.

## Input
- Schema with rules (from Stage 2)
- BUD document
- Keyword tree: `rule_extractor/static/keyword_tree.json` (edv_table_mapping section)
- EDV tables JSON (from edv_table_mapping dispatcher)
- Field-EDV mapping JSON (from edv_table_mapping dispatcher)
- Rule info meta-rules JSON (from dispatcher)

## Output
Schema with params populated for all EDV rules.

---

## Approach

### 1. EXT_DROP_DOWN Rules
Simple dropdown - params is a string (table name).

**Detect from BUD:**
- "Dropdown values are Yes / No" → params: "PIDILITE_YES_NO"
- "Dropdown values refer table 1.6" → lookup in edv_table_mapping

**Output:**
```json
{
  "actionType": "EXT_DROP_DOWN",
  "sourceType": "FORM_FILL_DROP_DOWN",
  "params": "TABLE_NAME",
  "searchable": true
}
```

### 2. EXT_VALUE Rules
Cascading/dependent dropdown - params is JSON string.

**Detect from BUD:**
- "based on X selection"
- "first and second columns of reference table"

**Build params structure:**
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

### 3. VALIDATION with EXTERNAL_DATA_VALUE
EDV validation that validates against a table AND populates destination fields with column values.

**Detect from BUD:**
- "validate from EDV table"
- "fetch data from table and populate fields"
- "validation will populate [field names]"

#### 3a. Simple EDV Validation
params is string (table name).

**Output:**
```json
{
  "actionType": "VALIDATION",
  "sourceType": "EXTERNAL_DATA_VALUE",
  "processingType": "SERVER",
  "sourceIds": [source_field_id],
  "destinationIds": [field1_id, field2_id, field3_id],
  "params": "COMPANY_CODE",
  "postTriggerRuleIds": [next_rule_id]
}
```

#### 3b. Complex EDV Validation with Conditions
params is JSON with conditionList for multi-field validation.

**Detect from BUD:**
- Multiple source fields required
- Condition checking mentioned
- "attribute validation"

**Build params structure:**
```json
{
  "param": "APPROVERMATRIXSETUP",
  "conditionList": [{
    "conditionNumber": 2,
    "conditionType": "IN",
    "conditionValueType": "TEXT",
    "conditionAttributes": ["attribute2value", "attribute3value"],
    "continueOnFailure": true,
    "errorMessage": "No data found!!"
  }]
}
```

**Output:**
```json
{
  "actionType": "VALIDATION",
  "sourceType": "EXTERNAL_DATA_VALUE",
  "processingType": "SERVER",
  "sourceIds": [field1_id, field2_id, field3_id],
  "destinationIds": [-1, -1, dest1_id, dest2_id, ...],
  "params": "{\"param\":\"TABLE_NAME\",\"conditionList\":[...]}",
  "postTriggerRuleIds": []
}
```

### 4. Table Name Extraction
Table names are NOT hardcoded - extract from BUD document and reference JSON:

**From BUD:**
- "dropdown values refer table 1.3" → look up table 1.3 in BUD appendix
- "yes/no dropdown" → find YES_NO variant in reference
- "validate against [table name]" → extract table name

**From Reference JSON:**
- Look at existing rules with same actionType/sourceType
- Extract `params` values to understand table naming conventions

**Patterns:**
- Reference table mentions: `reference table (\d+\.\d+)`
- Table number: `table (\d+\.\d+)`
- Common: `yes/no` → search reference for YES_NO variant

### 5. Column Notation
- "first column" → a1
- "second column" → a2
- "column N" → aN

### 6. destinationIds for EDV VALIDATION
- Array length matches schema's numberOfItems
- Use ordinal mapping: ordinal N → index N-1
- Use -1 for unmapped ordinals (fields not in BUD)

---

## Logging Requirements

All generated code MUST include proper logging:

```python
import logging

logger = logging.getLogger(__name__)

# Log levels:
logger.debug("Detailed debug info")      # For tracing execution
logger.info("Processing EDV rule X")     # For key operations
logger.warning("Table not found: X")     # For recoverable issues
logger.error("Failed to process: X")     # For errors
```

**Required logging points:**
- Log when processing starts with input file paths
- Log EDV table mappings loaded
- Log each rule type being processed (EXT_DROP_DOWN, EXT_VALUE, VALIDATION)
- Log params generation with table names
- Log summary statistics and output path

---

## Eval Check
- EXT_DROP_DOWN has string params
- EXT_VALUE has valid JSON params
- VALIDATION/EXTERNAL_DATA_VALUE has correct params format
- destinationIds correctly mapped for validation rules
- Table names are correct
