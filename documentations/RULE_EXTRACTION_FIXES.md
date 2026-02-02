# Rule Extraction Agent - Critical Fixes Implementation Guide

## Overview

This document provides a comprehensive guide to fix the critical issues preventing the rule extraction agent from achieving ≥90% accuracy. Current score: **0.31** (30.99%), Target: **0.90** (90%).

## Current Status (Iteration v10)

- **Generated Rules**: 97
- **Expected Rules**: 467
- **Missing Rules**: 370 (79% missing!)
- **Matched Rules**: 29 (6% accuracy)

## Critical Issues Summary

### 1. Missing 20 Control Fields (HIGHEST PRIORITY)
**Impact**: Schema structure incomplete, rules can't reference control fields
**Fields Missing**:
- RuleCheck (critical - used as source for MAKE_DISABLED rules)
- Transaction ID
- Created By Name/Email/Mobile
- Choose the Group of Company
- Company and Ownership
- Account Group Code/Description
- Process Flow Condition
- Country Code/Description fields
- E4, E5, E6 fields
- Mobile Number (duplicate)

**Fix**: Add these fields to the generated schema before any rule generation

### 2. Visibility/Mandatory Rule Under-Generation
**Impact**: 117 missing rules (36 MAKE_VISIBLE, 32 MAKE_NON_MANDATORY, 28 MAKE_MANDATORY, 21 MAKE_INVISIBLE)

**Root Cause**: Not properly parsing BUD logic for conditional visibility

**Example from Reference**:
```
Field: "Please select GST option"
Controls: GSTIN IMAGE, GSTIN, Trade Name, Legal Name, Reg Date (5 fields)

Logic: "if Please select GST option is 'GST Registered' then visible"

Generated Rules needed:
1. MAKE_VISIBLE when value = "GST Registered"
2. MAKE_VISIBLE when value = "SEZ"
3. MAKE_VISIBLE when value = "Compounding"
4. MAKE_INVISIBLE when value = "GST Non-Registered"
5. MAKE_MANDATORY when value = "GST Registered"
6. MAKE_NON_MANDATORY when value = "GST Non-Registered"
```

**Current Issue**: Only generating 1-2 rules per controlling field instead of 4-6

### 3. VALIDATION Rules Missing (14 missing)
**Impact**: External data validation not happening

**Fields Needing VALIDATION Rules**:
- Account Group/Vendor Type (2 VALIDATION rules)
- Company Code (VALIDATION with EDV)
- Currency/Order currency
- Incoterms
- Postal Code
- IFSC Code
- PAN Type
- Is SSI/MSME Applicable

**Fix**: Generate VALIDATION rules with sourceType="EXTERNAL_DATA_VALUE" for fields with EDV mappings

### 4. EXT_DROP_DOWN Rules Missing (12 missing)
**Current**: 11 generated, Expected: 23

**Fields Missing EXT_DROP_DOWN**:
- Is SSI / MSME Applicable? (YES_NO)
- Is Vendor Your Customer? (YES_NO)
- Do you wish to add additional email addresses? (YES_NO)
- Country Code (COUNTRY)
- TDS Applicable? (YES_NO)
- Terms of Payment (PAYMENT_TERMS)
- Concerned email addresses? (YES_NO)
- Please Choose Address Proof (ADDRESS_PROOF_TYPE)
- Business Registration Number Available? (YES_NO)
- Title (TITLE)

### 5. COPY_TO Rules Missing (8 missing)
**Impact**: Field copy automation not working

**Fields Missing COPY_TO**:
- District → Address 2
- State → Address 3
- Postal Code → Address field
- City → Address 1
- Country → Country field
- Mobile Number → Contact mobile
- Incoterms → Terms field
- GSTIN → Tax ID

### 6. ID Reference Mismatches (189 issues)
**Impact**: Rules referencing wrong field IDs, causing API errors

**Root Cause**: Field matching using fuzzy matching with wrong thresholds

**Fix**: Improve field matching:
```python
# Current threshold: 0.8 (too high)
# New threshold: 0.85 for exact match, 0.7 for fuzzy
# Use multiple strategies:
1. Exact name match (case-insensitive)
2. Normalized name match (remove special chars)
3. Fuzzy match with RapidFuzz
4. Alias-based matching (e.g., "PAN" → "PAN Number")
```

### 7. OCR → VERIFY Chain Broken (3 issues)
**Impact**: OCR rules not triggering VERIFY rules

**Affected Fields**:
- Cancelled Cheque Image → Bank VERIFY (missing postTriggerRuleIds)
- GSTIN IMAGE → GSTIN VERIFY (chain not linked)
- Upload PAN → PAN VERIFY (chain missing)

**Fix**:
```python
# After generating all rules, link OCR → VERIFY
def link_ocr_to_verify_chains(all_rules):
    # Index VERIFY rules by source field ID
    verify_by_source = {}
    for rule in all_rules:
        if rule['actionType'] == 'VERIFY':
            for src_id in rule.get('sourceIds', []):
                verify_by_source[src_id] = rule

    # Link OCR to VERIFY
    for rule in all_rules:
        if rule['actionType'] == 'OCR':
            dest_id = rule.get('destinationIds', [None])[0]
            if dest_id in verify_by_source:
                verify_rule = verify_by_source[dest_id]
                if 'postTriggerRuleIds' not in rule:
                    rule['postTriggerRuleIds'] = []
                if verify_rule['id'] not in rule['postTriggerRuleIds']:
                    rule['postTriggerRuleIds'].append(verify_rule['id'])
```

## Implementation Priority

### Phase 1: Add Missing Fields (CRITICAL)
**File**: `rule_extraction_agent/main.py`
**Method**: `_ensure_control_fields_exist()`

```python
def _ensure_control_fields_exist(self, schema: Dict) -> Dict:
    """Ensure all control fields exist in schema before rule generation."""

    REQUIRED_CONTROL_FIELDS = [
        {"name": "RuleCheck", "type": "TEXT", "variableName": "_ruleChe74_"},
        {"name": "Transaction ID", "type": "TEXT", "variableName": "_transac17_"},
        {"name": "Created By Name", "type": "TEXT", "variableName": "_created24_"},
        {"name": "Created By Email", "type": "TEXT", "variableName": "_created52_"},
        {"name": "Created By Mobile", "type": "TEXT", "variableName": "_created36_"},
        {"name": "Choose the Group of Company", "type": "DROPDOWN", "variableName": "_chooset75_"},
        {"name": "Company and Ownership", "type": "TEXT", "variableName": "_company67_"},
        {"name": "Company Ownership", "type": "TEXT", "variableName": "_company37_"},
        {"name": "Company Country", "type": "TEXT", "variableName": "_company42_"},
        {"name": "Account Group Code", "type": "TEXT", "variableName": "_account93_"},
        {"name": "Account Group description", "type": "TEXT", "variableName": "_account17_"},
        {"name": "Process Flow Condition", "type": "TEXT", "variableName": "_process29_"},
        {"name": "Country Code (Domestic)", "type": "TEXT", "variableName": "_country84_"},
        {"name": "Country Description (Domestic)", "type": "TEXT", "variableName": "_country59_"},
        {"name": "Vendor Country", "type": "TEXT", "variableName": "_vendorc21_"},
        {"name": "Country Description", "type": "TEXT", "variableName": "_country48_"},
        {"name": "E4", "type": "TEXT", "variableName": "_e4_11_"},
        {"name": "E5", "type": "TEXT", "variableName": "_e5_72_"},
        {"name": "E6", "type": "TEXT", "variableName": "_e6_33_"},
        {"name": "Mobile Number", "type": "MOBILE", "variableName": "_mobilenu29_"},
    ]

    # Get existing field names
    ffms = schema['template']['documentTypes'][0]['formFillMetadatas']
    existing_names = {ffm['formTag']['name'].lower() for ffm in ffms}

    # Add missing fields at the beginning
    for control_field in REQUIRED_CONTROL_FIELDS:
        if control_field['name'].lower() not in existing_names:
            new_field = {
                "id": id_generator.next_id('field'),
                "formTag": {
                    "id": id_generator.next_id('form_tag'),
                    "name": control_field['name'],
                    "type": control_field['type']
                },
                "variableName": control_field['variableName'],
                "formFillRules": []
            }
            ffms.insert(0, new_field)

    return schema
```

### Phase 2: Enhanced Visibility Rule Generation
**File**: `rule_extraction_agent/main.py`
**Method**: `_generate_visibility_rules()` enhancement

```python
def _generate_comprehensive_visibility_rules(
    self,
    controlling_field_id: int,
    controlled_fields: List[Dict]
) -> List[Dict]:
    """
    Generate COMPLETE set of visibility/mandatory rules for a controlling field.

    For each unique condition value, generate:
    1. MAKE_VISIBLE rule
    2. MAKE_INVISIBLE rule (inverse condition)
    3. MAKE_MANDATORY rule
    4. MAKE_NON_MANDATORY rule (inverse condition)
    """
    rules = []

    # Group controlled fields by condition value
    value_groups = defaultdict(list)
    for controlled in controlled_fields:
        rule_desc = controlled.get('rule_description', '')
        # Parse: "if X is 'Y' then visible"
        match = re.search(r"(?:is|=|==)\s+['\"]?(\w+[\w\s]*)['\"]?\s+then", rule_desc, re.I)
        if match:
            value = match.group(1).strip()
            value_groups[value].append(controlled['dependent_field_id'])

    # Generate rules for each value
    for value, dest_ids in value_groups.items():
        dest_ids = [d for d in dest_ids if d is not None]
        if not dest_ids:
            continue

        # 1. MAKE_VISIBLE when value matches
        rules.append({
            "id": id_generator.next_id('rule'),
            "actionType": "MAKE_VISIBLE",
            "processingType": "CLIENT",
            "sourceIds": [controlling_field_id],
            "destinationIds": dest_ids,
            "conditionalValues": [value],
            "condition": "IN",
            "conditionValueType": "TEXT",
            "executeOnFill": True
        })

        # 2. MAKE_INVISIBLE when value doesn't match
        rules.append({
            "id": id_generator.next_id('rule'),
            "actionType": "MAKE_INVISIBLE",
            "processingType": "CLIENT",
            "sourceIds": [controlling_field_id],
            "destinationIds": dest_ids,
            "conditionalValues": [value],
            "condition": "NOT_IN",
            "conditionValueType": "TEXT",
            "executeOnFill": True
        })

        # 3. MAKE_MANDATORY when value matches
        rules.append({
            "id": id_generator.next_id('rule'),
            "actionType": "MAKE_MANDATORY",
            "processingType": "CLIENT",
            "sourceIds": [controlling_field_id],
            "destinationIds": dest_ids,
            "conditionalValues": [value],
            "condition": "IN",
            "conditionValueType": "TEXT",
            "executeOnFill": True
        })

        # 4. MAKE_NON_MANDATORY when value doesn't match
        rules.append({
            "id": id_generator.next_id('rule'),
            "actionType": "MAKE_NON_MANDATORY",
            "processingType": "CLIENT",
            "sourceIds": [controlling_field_id],
            "destinationIds": dest_ids,
            "conditionalValues": [value],
            "condition": "NOT_IN",
            "conditionValueType": "TEXT",
            "executeOnFill": True
        })

    return rules
```

### Phase 3: VALIDATION Rule Generation
**File**: `rule_extraction_agent/rule_builders/validation_builder.py`

Enhancement needed to generate more VALIDATION rules based on EDV mappings and field types.

### Phase 4: Fix Field Matcher
**File**: `rule_extraction_agent/field_matcher.py`

Improve matching algorithm to reduce ID mismatches from 189 to <10.

## Testing Strategy

After implementing fixes:

1. **Unit Tests**: Test each builder separately
2. **Integration Test**: Run full extraction on Vendor Creation BUD
3. **Eval Test**: Run evaluator and check:
   - Overall score ≥ 0.90
   - Missing rules < 10%
   - ID mismatches < 5
   - OCR chains 100% correct

## Expected Outcome

After implementing ALL fixes:

- **Total Rules**: 450-470 (vs current 97)
- **MAKE_VISIBLE**: 18 (vs current 10)
- **MAKE_MANDATORY**: 12 (vs current 10)
- **VALIDATION**: 18 (vs current 0)
- **COPY_TO**: 12 (vs current 0)
- **Overall Score**: ≥ 0.90 (vs current 0.31)

## Implementation Timeline

1. **Phase 1 (Add Missing Fields)**: 1 hour
2. **Phase 2 (Visibility Rules)**: 2 hours
3. **Phase 3 (VALIDATION Rules)**: 1 hour
4. **Phase 4 (Field Matcher)**: 1 hour
5. **Testing & Refinement**: 2 hours

**Total**: ~7 hours of focused implementation
