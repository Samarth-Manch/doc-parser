---
name: Assembly Coding Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Stage 5 - Generates Python code for final assembly, consolidation, and validation.
---

# Assembly Coding Agent (Stage 5)

## Objective

Generate a Python script that:
1. Consolidates similar rules (reduces count)
2. Assigns sequential IDs
3. Validates final structure
4. Produces API-ready output

## Input Files

- `--schema`: Schema with all rules (from Stage 4)
- `--reference`: Reference schema for structure validation
- `--output`: Output path for final schema

## Output

Python script that produces the final consolidated, validated schema.

---

## Approach

### 1. Rule Consolidation

**Consolidation Key:**
Rules with same (actionType, sourceType, sourceIds, condition, conditionalValues) can be merged.

**Consolidatable Action Types:**
- MAKE_VISIBLE
- MAKE_INVISIBLE
- MAKE_MANDATORY
- MAKE_OPTIONAL
- MAKE_DISABLED
- MAKE_ENABLED
- SET_VALUE
- CLEAR_VALUE

**Merge Algorithm:**
```
1. Group rules by consolidation key
2. For consolidatable types with same key:
   - Merge destinationIds arrays
   - Remove duplicates from destinationIds
   - Keep first rule as base
3. Non-consolidatable rules pass through unchanged
4. Track merge statistics
```

**Example:** 40 MAKE_DISABLED rules with same sourceId → 5 consolidated rules

### 2. Sequential ID Assignment

Assign sequential IDs starting from 1:
- **Rules**: 1, 2, 3, ...
- **Fields**: 1, 2, 3, ...
- **FormTags**: 1, 2, 3, ...

Build `rule_id_map` (old_id → new_id) for reference updates.

### 3. Reference Updates

Update `postTriggerRuleIds` to use new sequential IDs:
```
For each rule:
  For each id in postTriggerRuleIds:
    new_id = rule_id_map.get(old_id, old_id)
    Update reference
```

### 4. Default Fields

Ensure all rules have required fields:
```json
{
  "id": 1,
  "createUser": "FIRST_PARTY",
  "updateUser": "FIRST_PARTY",
  "actionType": "...",
  "processingType": "CLIENT|SERVER",
  "sourceIds": [...],
  "destinationIds": [...],
  "postTriggerRuleIds": [],
  "button": "",
  "searchable": false,
  "executeOnFill": true,
  "executeOnRead": false,
  "executeOnEsign": false,
  "executePostEsign": false,
  "runPostConditionFail": false
}
```

### 5. Validation

**Required field checks:**
- id, actionType, processingType, sourceIds, destinationIds

**Reference validation:**
- All sourceIds reference existing field IDs
- All postTriggerRuleIds reference existing rule IDs

**Duplicate detection:**
- No duplicate rule IDs
- No duplicate field IDs

### 6. Cleanup

Remove temporary fields added during processing:
- `_field_id`

---

## Code Requirements

### CLI Interface
```
python stage_5_assembly.py \
    --schema input.json \
    --reference reference.json \
    --output output.json \
    --verbose
```

### Required Classes/Functions

1. **RuleConsolidator** - Consolidates similar rules
   - `get_consolidation_key(rule)` - Generate grouping key
   - `should_consolidate(action_type)` - Check if type is consolidatable
   - `merge_rules(rules)` - Merge rules with same key
   - `consolidate(schema)` - Consolidate all rules

2. **IDAssigner** - Assigns sequential IDs
   - `assign_ids(schema)` - Assign all IDs
   - `update_references(schema)` - Update postTriggerRuleIds

3. **StructureValidator** - Validates final structure
   - `validate_rule(rule, field_ids, rule_ids)` - Validate single rule
   - `validate(schema)` - Validate entire schema
   - `stats_rule_count(schema)` - Count total rules

4. **RuleDefaults** - Applies default fields
   - `apply_defaults(schema)` - Apply defaults to all rules

5. **Assembler** - Main orchestrator
   - `assemble(schema)` - Run all steps
   - `_clean_temp_fields(schema)` - Remove _field_id etc.
   - `print_stats()` - Print statistics

### Statistics to Track
- `original_count`: Rules before consolidation
- `consolidated_count`: Rules after consolidation
- `rules_merged`: Number of rules merged
- `rules_assigned`: IDs assigned
- `fields_assigned`: Field IDs assigned
- `form_tags_assigned`: FormTag IDs assigned
- Validation errors and warnings

### Logging Requirements

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Consolidating rules...")
logger.info(f"Consolidated {original} -> {consolidated} rules")
logger.debug(f"Merged {count} rules into 1 ({action_type})")
logger.info("Assigning sequential IDs...")
logger.info(f"Assigned IDs: {stats}")
logger.info("Validating schema structure...")
logger.warning(f"Rule {id}: sourceId {src_id} not found")
```

---

## Eval Check

- Valid JSON structure
- Sequential IDs (no gaps)
- Rules properly consolidated
- No orphan references (all IDs exist)
- All required fields present
