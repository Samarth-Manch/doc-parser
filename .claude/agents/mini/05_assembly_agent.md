---
name: Assembly Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Stage 5 - Assembles all rule outputs into final schema with consolidation and validation.
---

# Assembly Agent (Stage 5)

## Objective
Combine outputs from all previous stages into final schema. Consolidate rules, assign sequential IDs, and validate structure.

## Input
- Schema with all rules populated (from Stage 4)
- Reference schema structure

## Output
Final schema ready for API submission.

---

## Approach

### 1. Rule Consolidation
Merge rules with same (sourceIds, actionType, condition, conditionalValues):

**Example:** 40 individual MAKE_DISABLED rules → ~5 consolidated rules with multiple destinationIds

```python
# Group rules
key = (actionType, tuple(sourceIds), condition, tuple(conditionalValues))
groups[key].append(rule)

# Merge destinationIds
merged_rule['destinationIds'] = list(set(
    d for r in group for d in r.get('destinationIds', [])
))
```

### 2. Sequential ID Assignment
All IDs must be sequential integers starting from 1:
- Rule IDs: 1, 2, 3, ...
- Field IDs: 1, 2, 3, ... (if regenerating)
- FormTag IDs: 1, 2, 3, ...

After ID assignment, update all postTriggerRuleIds references.

### 3. Required Fields for All Rules
Ensure each rule has:
```json
{
  "id": sequential_int,
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

### 4. Conditional Fields
For visibility/mandatory rules, add:
- `conditionalValues`: ["value1", "value2"]
- `condition`: "IN" or "NOT_IN"
- `conditionValueType`: "TEXT"

### 5. Final Validation
- All referenced field IDs exist
- All postTriggerRuleIds reference existing rules
- No duplicate rules on same field
- Structure matches reference format

### 6. Output Structure
```json
{
  "template": {
    "id": 1,
    "templateName": "...",
    "documentTypes": [{
      "id": 1,
      "formFillMetadatas": [...]
    }]
  }
}
```

---

## Logging Requirements

All generated code MUST include proper logging:

```python
import logging

logger = logging.getLogger(__name__)

# Log levels:
logger.debug("Detailed debug info")      # For tracing execution
logger.info("Consolidating rules...")    # For key operations
logger.warning("Orphan reference: X")    # For recoverable issues
logger.error("Validation failed: X")     # For errors
```

**Required logging points:**
- Log when processing starts with input file paths
- Log rule counts before and after consolidation
- Log ID assignment ranges (e.g., "Assigned rule IDs 1-45")
- Log validation results (passed/failed checks)
- Log final statistics (total rules, fields, panels)
- Log output path when writing

---

## Eval Check
- Structure valid JSON
- All IDs sequential
- Rules consolidated properly
- No orphan references
