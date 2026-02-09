---
name: Post Trigger Chain Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Links rules via postTriggerRuleIds (OCR→VERIFY chains, etc.)
---

# Post Trigger Chain Agent (Stage 4)

## Objective
Populate `postTriggerRuleIds` arrays to link rules in chains (e.g., OCR → VERIFY).

## Input
- Schema with rules (from Stage 3)
- Keyword tree (ocr_verify_chains section)

## Output
Schema with postTriggerRuleIds populated.

---

## Approach

### 1. Build Rule Index
Create lookups:
- Rules by actionType + sourceType
- Rules by sourceIds (which field triggers them)
- Rule ID to rule object

### 2. Link OCR → VERIFY Chains
Use `ocr_verify_chains` from keyword tree:
```
PAN_IMAGE → PAN_NUMBER
GSTIN_IMAGE → GSTIN
CHEQUEE → BANK_ACCOUNT_NUMBER
MSME → MSME_UDYAM_REG_NUMBER
CIN → CIN_ID
```

**Logic:**
1. Find OCR rule by sourceType
2. Get the field it populates (destinationIds[0] or first valid destination)
3. Find VERIFY rule where sourceIds contains that field
4. Set OCR rule's postTriggerRuleIds = [VERIFY_rule_id]

### 3. VERIFY → Cross-Validation Chains
- PAN VERIFY → GSTIN_WITH_PAN VERIFY (if both exist)
- GSTIN VERIFY → GSTIN_WITH_PAN VERIFY

### 4. VERIFY → Visibility Chains (if applicable)
Some VERIFY rules trigger visibility changes after validation.

### 5. Handle Aadhaar OCR
- AADHAR_IMAGE and AADHAR_BACK_IMAGE have NO verify chains
- postTriggerRuleIds should be empty or link to other rules

---

## Key Chains from Reference
```
PAN OCR (119969) → PAN VERIFY (119970)
GSTIN OCR (119606) → GSTIN VERIFY (119608)
CHEQUE OCR (120064) → BANK VERIFY (120067)
MSME OCR (119610) → MSME VERIFY (119612)
```

---

## Logging Requirements

All generated code MUST include proper logging:

**Required logging points:**
- Log when processing starts with input file paths
- Log rule index building (rules by type, by sourceIds)
- Log each chain being created (OCR → VERIFY, etc.)
- Log summary of chains created
- Log output path when writing

---

## Eval Check
- OCR rules have postTriggerRuleIds to VERIFY (where applicable)
- Referenced rule IDs exist
- Chain correctness matches reference patterns
