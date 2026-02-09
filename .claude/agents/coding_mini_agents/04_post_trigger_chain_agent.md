---
name: Post Trigger Chain Coding Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Stage 4 - Generates Python code for linking rules via postTriggerRuleIds.
---

# Post Trigger Chain Coding Agent (Stage 4)

## Objective

Generate a Python script that populates `postTriggerRuleIds` arrays to link rules in chains (e.g., OCR → VERIFY).

## Input Files

- `--schema`: Schema with rules (from Stage 3)
- `--keyword-tree`: Keyword tree JSON (contains ocr_verify_chains)
- `--output`: Output path

## Output

Python script that links rules with deterministic chain detection.

---

## Approach

### 1. Build Rule Index

Create lookup indexes for fast rule access:
- `rules_by_id`: rule ID → rule object
- `rules_by_type`: actionType → list of rules
- `rules_by_source_type`: sourceType → list of rules
- `rules_by_source_ids`: tuple(sourceIds) → list of rules
- `field_rules`: field_id → list of rules on that field

Assign temporary IDs to rules if not present.

### 2. OCR → VERIFY Chain Detection

**Method 1: Keyword tree mapping**
```json
"ocr_verify_chains": {
  "PAN_IMAGE": "PAN_NUMBER",
  "GSTIN_IMAGE": "GSTIN",
  "CHEQUEE": "BANK_ACCOUNT_NUMBER",
  "MSME": "MSME_UDYAM_REG_NUMBER",
  "CIN": "CIN_ID"
}
```

For each OCR rule:
1. Get OCR sourceType (e.g., PAN_IMAGE)
2. Look up corresponding VERIFY sourceType (e.g., PAN_NUMBER)
3. Find VERIFY rule with that sourceType
4. Add VERIFY rule ID to OCR's postTriggerRuleIds

**Method 2: Destination-based detection**
1. Get OCR rule's destinationIds
2. Find VERIFY rule where sourceIds contains destination field
3. Link OCR → VERIFY

### 3. VERIFY Cross-Validation Chains

**PAN → GSTIN_WITH_PAN:**
- Find PAN VERIFY rule (sourceType: PAN_NUMBER)
- Find GSTIN_WITH_PAN VERIFY rule
- Link PAN → GSTIN_WITH_PAN

**GSTIN → GSTIN_WITH_PAN:**
- Find GSTIN VERIFY rule (sourceType: GSTIN)
- Link GSTIN → GSTIN_WITH_PAN

### 4. Chain Building Algorithm

```
For each OCR rule:
  1. Get ocr_source_type
  2. Check keyword_tree.ocr_verify_chains mapping
  3. If mapping found:
     - Find VERIFY rule with mapped sourceType
     - Add to postTriggerRuleIds
  4. Else:
     - Get OCR destination field
     - Find VERIFY rule with that field as source
     - Add to postTriggerRuleIds
  5. Track stats (deterministic/no_chain)

For VERIFY cross-validation:
  1. Find GSTIN_WITH_PAN rules
  2. Link PAN VERIFY → GSTIN_WITH_PAN
  3. Link GSTIN VERIFY → GSTIN_WITH_PAN
```

### 5. Ensure Empty Arrays

All rules must have `postTriggerRuleIds` field:
- If no chains, set to empty array `[]`
- Never leave undefined

### 6. Special Cases

**AADHAR_IMAGE:**
- No VERIFY chain (just OCR extraction)
- postTriggerRuleIds = []

**VALIDATION rules:**
- May trigger other rules
- Check logic for chaining patterns

---

## Code Requirements

### CLI Interface
```
python stage_4_post_trigger.py \
    --schema input.json \
    --keyword-tree keyword_tree.json \
    --output output.json \
    --verbose
```

### Required Classes/Functions

1. **RuleIndex** - Index for fast rule lookups
   - `_build_index(schema)` - Build all indexes
   - `find_verify_for_ocr(ocr_rule)` - Find VERIFY by destination

2. **ChainBuilder** - Loads chain mappings from keyword tree
   - `_load_chains(path)` - Load ocr_verify_chains
   - `get_verify_source_type(ocr_source_type)` - Get mapped VERIFY type

3. **PostTriggerLinker** - Main processing class
   - `link_ocr_to_verify()` - Link all OCR → VERIFY
   - `link_verify_cross_validation()` - Link PAN/GSTIN → GSTIN_WITH_PAN
   - `ensure_empty_arrays()` - Ensure all rules have postTriggerRuleIds
   - `process_schema()` - Process entire schema
   - `print_stats()` - Print statistics

### Statistics to Track
- `ocr_verify_chains`: OCR → VERIFY links created
- `verify_cross_chains`: VERIFY cross-validation links
- `other_chains`: Other chain types
- `deterministic`: Chains from keyword tree mapping
- `no_chain`: Rules without chains

### Logging Requirements

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Indexed {count} rules")
logger.info(f"Action types: {list(rules_by_type.keys())}")
logger.debug(f"Linked OCR {src_type} -> VERIFY {dest_type}")
logger.debug(f"Found VERIFY rule {id} for OCR destination {field_id}")
logger.info("Linking VERIFY cross-validation chains...")
```

---

## Eval Check

- OCR rules have postTriggerRuleIds to VERIFY
- Referenced rule IDs exist
- Chain patterns match keyword tree mappings
- All rules have postTriggerRuleIds (even if empty)
