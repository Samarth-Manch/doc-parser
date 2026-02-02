---
name: Eval Rule Extraction Output
allowed-tools: Read, Write, Bash, Glob, Grep
description: Comprehensive evaluation of generated rule extraction output against BUD document and human-made reference. Panel-by-panel checking with intelligent discrepancy detection.
---

# Eval Rule Extraction Output (Claude Code Prompt)

## Objective

Perform **comprehensive intelligent evaluation** of the generated rule extraction output by:
1. **PRIMARY**: Comparing against BUD document (source of truth for logic)
2. **SECONDARY**: Comparing against human-made reference JSON in `documents/json_output/`
3. **Panel-by-panel** verification of all fields and rules
4. **Intelligent detection** of missing rules, incorrect mappings, and structural issues

This is an **intelligent evaluation task** that understands rule semantics, field relationships, and BUD logic.

---

## Common Issues & Root Causes

Based on observed evaluation patterns, the following issues commonly occur and should be checked:

### 1. OCR → VERIFY Chain Issues
**Symptom**: Missing postTriggerRuleIds on OCR rules
**Root Cause**: OCR rules not linked to corresponding VERIFY rules
**Check**: Every OCR rule for PAN_IMAGE, GSTIN_IMAGE, CHEQUEE, MSME, CIN should have postTriggerRuleIds
**Exception**: AADHAR_IMAGE and AADHAR_BACK_IMAGE do NOT need VERIFY chains (no Aadhaar verification schema exists)

### 2. Over-Generation of Rules
**Symptom**: Generated count exceeds reference count (e.g., EXT_DROP_DOWN: 26 vs 20)
**Root Cause**: Pattern matching too aggressive; generating rules for fields that don't need them
**Check**: Verify that rules are only generated when logic explicitly requires them
**Fix Guidance**: Tighten pattern matching to require explicit keywords, not just field type

### 3. Under-Generation of Rules
**Symptom**: Generated count less than reference count
**Root Cause**: Pattern matching not detecting all valid logic patterns
**Check**: Review BUD logic text for fields missing rules
**Fix Guidance**: Add additional pattern variants to detection logic

### 4. Incorrect Rule Placement
**Symptom**: Rules placed on destination field instead of source/controlling field
**Root Cause**: Misunderstanding of visibility/mandatory rule placement
**Check**: MAKE_VISIBLE/MAKE_INVISIBLE rules should be on the controlling field (the one with the dropdown/checkbox), with destinationIds pointing to controlled fields

### 5. VERIFY Ordinal Mapping Errors
**Symptom**: destinationIds array has wrong length or wrong field IDs at positions
**Root Cause**: Schema ordinal mapping not correctly implemented
**Check**: Each VERIFY sourceType has a specific number of destination ordinals:
  - PAN_NUMBER: 10 ordinals
  - GSTIN: 21 ordinals
  - BANK_ACCOUNT_NUMBER: 4 ordinals
  - MSME_UDYAM_REG_NUMBER: 21 ordinals
  - CIN_ID: 14 ordinals

### 6. Rule Consolidation Issues
**Symptom**: Multiple separate MAKE_DISABLED rules instead of single rule with multiple destinationIds
**Root Cause**: Not consolidating rules with same sourceIds + condition + conditionalValues
**Check**: MAKE_DISABLED count should be ~5 (consolidated), not 40-50+ (individual)

### 7. Duplicate Rules
**Symptom**: Same rule type appears multiple times on same field
**Root Cause**: Rule deduplication not working correctly
**Check**: Each field should have at most one rule of each actionType (with some exceptions for different conditionalValues)

### 8. Multi-Source VERIFY Rules Missing Required Fields (CRITICAL)
**Symptom**: API returns `"Id is not present for the mandatory field X"`
**Root Cause**: VERIFY rules with multiple required source fields only have partial sourceIds
**Affected Rule Types**:
- `BANK_ACCOUNT_NUMBER` - Requires 2 sourceIds (IFSC Code, Bank Account Number)
- `GSTIN_WITH_PAN` - Requires 2 sourceIds (PAN, GSTIN)
- `DRIVING_LICENCE_NUMBER` - Requires 2 sourceIds
- `DRUG_LICENCE` - Requires 2 sourceIds

**Check**: Verify sourceIds.length matches schema's sourceFields.numberOfItems for mandatory rules
```python
def check_multi_source_verify_rules(verify_rules: list, schemas: dict) -> list:
    """
    CRITICAL: Check that VERIFY rules have ALL required source fields.

    Some VERIFY schemas require multiple source fields (not just one).
    If sourceIds is incomplete, API will reject with 'mandatory field' error.
    """
    issues = []
    for rule in verify_rules:
        source_type = rule.get('sourceType')
        schema = schemas.get(source_type)
        if not schema:
            continue

        required_count = schema.get('sourceFields', {}).get('numberOfItems', 1)
        mandatory_fields = [f for f in schema.get('sourceFields', {}).get('fields', [])
                          if f.get('mandatory')]

        actual_count = len([s for s in rule.get('sourceIds', []) if s != -1])

        if actual_count < len(mandatory_fields):
            issues.append({
                "type": "MISSING_SOURCE_FIELDS",
                "severity": "CRITICAL",
                "rule_id": rule.get('id'),
                "source_type": source_type,
                "expected_mandatory": len(mandatory_fields),
                "actual_count": actual_count,
                "mandatory_field_names": [f['name'] for f in mandatory_fields],
                "fix_hint": f"Add missing field IDs to sourceIds. Schema requires: {[f['name'] for f in mandatory_fields]}"
            })
    return issues
```

### 9. Over-Generation of Rules
**Symptom**: Generated count significantly exceeds reference count
**Root Cause**: Pattern matching too broad, not consolidating, or generating for both source and destination
**Check**: Flag when generated count > reference count * 1.5 (50% threshold)
```python
def check_over_generation(gen_counts: dict, ref_counts: dict) -> list:
    issues = []
    for action_type, gen_count in gen_counts.items():
        ref_count = ref_counts.get(action_type, 0)
        if ref_count > 0 and gen_count > ref_count * 1.5:
            issues.append({
                "type": "OVER_GENERATION",
                "severity": "HIGH",
                "action_type": action_type,
                "generated": gen_count,
                "expected": ref_count,
                "ratio": round(gen_count / ref_count, 2),
                "fix_hint": "Tighten pattern matching; only generate when logic explicitly requires"
            })
    return issues
```

### 10. Skip EXT_VALUE and EXT_DROP_DOWN in Evaluation (TEMPORARY)
**Status**: IGNORE THESE RULE TYPES FOR NOW
**Reason**: External data value rules require complex table mapping (to be implemented later)
**Action**:
- Do NOT flag missing EXT_VALUE or EXT_DROP_DOWN rules as errors
- Do NOT count these in rule type comparison
- Mark as "SKIPPED" in evaluation report

```python
# Rule types to skip in evaluation
SKIP_RULE_TYPES_IN_EVAL = ['EXT_VALUE', 'EXT_DROP_DOWN']

def filter_rules_for_eval(rules: list) -> list:
    """Filter out rule types that should be skipped in evaluation."""
    return [r for r in rules if r.get('actionType') not in SKIP_RULE_TYPES_IN_EVAL]
```

### 11. CRITICAL: Field-Level Rule Comparison (Not Just Total Counts!)
**Symptom**: Total rule counts match but rules are on WRONG FIELDS
**Root Cause**: Eval only compares aggregate counts, not field-by-field rules
**This is a MAJOR gap** - the current eval passes when rules exist but are misplaced

**MANDATORY CHECK**: Compare rules BY FIELD, not just by total count

```python
def compare_rules_by_field(gen_ffms: list, ref_ffms: list) -> dict:
    """
    CRITICAL: Compare rules field-by-field, not just total counts.

    This catches:
    - Rules on wrong fields
    - Extra rules that shouldn't exist on a field
    - Missing rules that should be on a field
    - Wrong actionType on a field
    """
    issues = []

    # Build reference lookup by formTag.name (normalized)
    def normalize(name):
        if not name:
            return ''
        return name.lower().strip().replace('/', ' ').replace('-', ' ')

    ref_by_name = {}
    for ffm in ref_ffms:
        name = normalize(ffm.get('formTag', {}).get('name', ''))
        if name:
            ref_by_name[name] = ffm

    # Check each generated field
    for gen_ffm in gen_ffms:
        gen_name = normalize(gen_ffm.get('formTag', {}).get('name', ''))
        gen_rules = gen_ffm.get('formFillRules', [])
        field_display = gen_ffm.get('formTag', {}).get('name', 'Unknown')

        ref_ffm = ref_by_name.get(gen_name)
        if not ref_ffm:
            if gen_rules:
                issues.append({
                    "type": "EXTRA_FIELD_WITH_RULES",
                    "field": field_display,
                    "severity": "HIGH",
                    "rules": [r.get('actionType') for r in gen_rules],
                    "fix_hint": "This field doesn't exist in reference or has different name"
                })
            continue

        ref_rules = ref_ffm.get('formFillRules', [])

        # Compare action types with counts
        from collections import Counter
        gen_actions = Counter([r.get('actionType') for r in gen_rules])
        ref_actions = Counter([r.get('actionType') for r in ref_rules])

        extra_in_gen = gen_actions - ref_actions
        missing_in_gen = ref_actions - gen_actions

        if extra_in_gen:
            issues.append({
                "type": "EXTRA_RULES_ON_FIELD",
                "field": field_display,
                "severity": "HIGH",
                "extra_rules": dict(extra_in_gen),
                "fix_hint": "Remove these rules - they don't exist in reference for this field"
            })

        if missing_in_gen:
            issues.append({
                "type": "MISSING_RULES_ON_FIELD",
                "field": field_display,
                "severity": "HIGH",
                "missing_rules": dict(missing_in_gen),
                "fix_hint": "Add these rules - they exist in reference for this field"
            })

    return {
        "total_field_issues": len(issues),
        "issues": issues
    }
```

### 12. sourceIds and destinationIds Validation
**Symptom**: Rules exist but with wrong source/destination field IDs
**Root Cause**: Field matching incorrect or ordinal mapping wrong
**This affects**: All rule types but especially VERIFY, OCR, visibility rules

**MANDATORY CHECK**: For matching rules, verify sourceIds and destinationIds match reference pattern

```python
def validate_source_destination_ids(gen_rule: dict, ref_rule: dict, gen_ffms: list, ref_ffms: list) -> list:
    """
    Validate that sourceIds and destinationIds have correct structure.

    Checks:
    1. sourceIds length matches reference
    2. For VERIFY: sourceIds has ALL required fields per schema
    3. destinationIds length matches schema numberOfItems
    4. No invalid IDs (-1 where there should be valid ID)
    """
    issues = []

    gen_source_ids = gen_rule.get('sourceIds', [])
    ref_source_ids = ref_rule.get('sourceIds', [])
    gen_dest_ids = gen_rule.get('destinationIds', [])
    ref_dest_ids = ref_rule.get('destinationIds', [])

    # Check sourceIds length
    if len(gen_source_ids) != len(ref_source_ids):
        issues.append({
            "type": "SOURCE_IDS_LENGTH_MISMATCH",
            "severity": "CRITICAL",
            "action_type": gen_rule.get('actionType'),
            "source_type": gen_rule.get('sourceType'),
            "expected_length": len(ref_source_ids),
            "actual_length": len(gen_source_ids),
            "fix_hint": f"sourceIds should have {len(ref_source_ids)} elements, not {len(gen_source_ids)}"
        })

    # Check destinationIds length (for VERIFY/OCR)
    if gen_rule.get('actionType') in ['VERIFY', 'OCR']:
        if len(gen_dest_ids) != len(ref_dest_ids):
            issues.append({
                "type": "DESTINATION_IDS_LENGTH_MISMATCH",
                "severity": "CRITICAL",
                "action_type": gen_rule.get('actionType'),
                "source_type": gen_rule.get('sourceType'),
                "expected_length": len(ref_dest_ids),
                "actual_length": len(gen_dest_ids),
                "fix_hint": f"destinationIds should have {len(ref_dest_ids)} elements"
            })

    return issues
```

### 13. DELETE_DOCUMENT/UNDELETE_DOCUMENT Over-Generation
**Symptom**: DELETE_DOCUMENT and UNDELETE_DOCUMENT rules appearing on fields that shouldn't have them
**Root Cause**: These rules are being incorrectly generated for dropdown fields
**Check**: These rules should ONLY appear on specific fields, not on every dropdown

```python
# Common over-generated rules that need strict checking
STRICT_CHECK_RULES = ['DELETE_DOCUMENT', 'UNDELETE_DOCUMENT', 'VALIDATION', 'COPY_TO']

def check_strict_rule_placement(gen_ffms: list, ref_ffms: list) -> list:
    """
    Check that strict rules are ONLY on fields where they appear in reference.

    These rules should NOT be generated liberally - only when explicitly in reference.
    """
    issues = []

    # Build set of (field_name, actionType) from reference
    ref_field_rules = set()
    for ffm in ref_ffms:
        name = ffm.get('formTag', {}).get('name', '').lower().strip()
        for rule in ffm.get('formFillRules', []):
            if rule.get('actionType') in STRICT_CHECK_RULES:
                ref_field_rules.add((name, rule.get('actionType')))

    # Check generated
    for ffm in gen_ffms:
        name = ffm.get('formTag', {}).get('name', '').lower().strip()
        field_display = ffm.get('formTag', {}).get('name', 'Unknown')

        for rule in ffm.get('formFillRules', []):
            action_type = rule.get('actionType')
            if action_type in STRICT_CHECK_RULES:
                if (name, action_type) not in ref_field_rules:
                    issues.append({
                        "type": "INCORRECTLY_PLACED_STRICT_RULE",
                        "field": field_display,
                        "action_type": action_type,
                        "severity": "HIGH",
                        "fix_hint": f"Remove {action_type} from this field - not in reference"
                    })

    return issues
```

---

## Input

You will be provided with:
1. **Generated Output Path**: Path to the populated schema JSON generated by the rule extraction agent
2. **Reference Output Path**: Path to the human-made reference JSON in `documents/json_output/`
3. **BUD Document Path**: Path to the original BUD .docx document
4. **Eval Report Output Path**: Where to save the evaluation report

**First action**:
1. Parse BUD document using doc_parser to extract field logic
2. Read generated JSON
3. Read reference JSON

---

## Three-Layer Evaluation Strategy

### Layer 1: BUD Document Verification (PRIMARY - Most Important)

Parse the BUD document and verify that rules match the natural language logic:

```python
from doc_parser import DocumentParser

parser = DocumentParser()
parsed = parser.parse(bud_path)

# For each field in BUD
for field in parsed.all_fields:
    logic = field.logic or ''

    # Check what rules SHOULD be generated based on logic
    expected_rules = analyze_logic_for_expected_rules(logic)

    # Compare with generated rules
    generated_rules = get_generated_rules_for_field(field.name)

    # Verify match
    verify_rules_match_logic(expected_rules, generated_rules, logic)
```

### Layer 2: Reference JSON Comparison (SECONDARY)

Compare generated output against human-made reference for structural correctness:

```python
# Load both JSONs
generated = load_json(generated_path)
reference = load_json(reference_path)

# Compare field-by-field, rule-by-rule
for field in reference_fields:
    compare_rules(reference_rules, generated_rules)
```

### Layer 3: Schema Validation

Validate generated JSON structure matches expected format:
- Correct hierarchy: template → documentTypes → formFillMetadatas → formFillRules
- All required fields present in each rule
- Correct data types

---

## Panel-by-Panel Evaluation

### Step 1: Extract Panels from BUD

```python
# Group fields by their panel/section
panels = {}
for field in parsed.all_fields:
    panel_name = field.section or "Default"
    if panel_name not in panels:
        panels[panel_name] = []
    panels[panel_name].append(field)
```

### Step 2: Evaluate Each Panel

For each panel, evaluate:

1. **Field Coverage**: Are all BUD fields present in generated output?
2. **Rule Coverage**: Does each field have appropriate rules based on its logic?
3. **Rule Correctness**: Are the rules correctly structured?
4. **Cross-Field Dependencies**: Are visibility/mandatory rules correctly linking fields?

### Step 3: Panel Report

Generate per-panel evaluation:

```json
{
  "panel_name": "GST Details",
  "total_fields": 15,
  "fields_with_rules_expected": 12,
  "fields_with_rules_generated": 10,
  "coverage": 0.83,
  "issues": [
    {"field": "GSTIN", "issue": "Missing VERIFY rule"},
    {"field": "Trade Name", "issue": "Missing visibility pair"}
  ]
}
```

---

## Comprehensive Rule Type Checking

### 1. VERIFY Rules Evaluation

| Check | Criteria | Severity |
|-------|----------|----------|
| Presence | All fields with "Perform X validation" logic have VERIFY rule | HIGH |
| sourceType | Matches Rule-Schemas.json (PAN_NUMBER, GSTIN, etc.) | HIGH |
| sourceIds | Contains the validation input field ID | HIGH |
| destinationIds | Correct ordinal mapping with -1 for unmapped | CRITICAL |
| destinationIds length | Matches schema's destinationFields.numberOfItems | CRITICAL |
| postTriggerRuleIds | Links to downstream rules (visibility, etc.) | MEDIUM |
| button | Has appropriate button text ("Verify", "VERIFY") | LOW |

**VERIFY Rules to Check**:
- PAN_NUMBER (schema 360) - 10 destination ordinals
- GSTIN (schema 355) - 21 destination ordinals
- BANK_ACCOUNT_NUMBER (schema 361) - 4 destination ordinals
- MSME_UDYAM_REG_NUMBER (schema 337) - 21 destination ordinals
- GSTIN_WITH_PAN (cross-validation) - params with error message
- CIN_ID (schema 349)

### 2. OCR Rules Evaluation

| Check | Criteria | Severity |
|-------|----------|----------|
| Presence | All file upload fields with OCR logic have OCR rule | HIGH |
| sourceType | Matches schema (PAN_IMAGE, GSTIN_IMAGE, CHEQUEE, etc.) | HIGH |
| sourceIds | Contains the file upload field ID | HIGH |
| destinationIds | Points to correct text field(s) | HIGH |
| postTriggerRuleIds | **CRITICAL**: Links to VERIFY rule | CRITICAL |
| Ordinal mapping | For multi-destination OCR (CHEQUEE), correct ordinals | HIGH |

**OCR Rules to Check**:
- PAN_IMAGE (schema 344) → chains to PAN_NUMBER VERIFY
- GSTIN_IMAGE (schema 347) → chains to GSTIN VERIFY
- CHEQUEE (schema 269) → chains to BANK_ACCOUNT_NUMBER VERIFY
- AADHAR_BACK_IMAGE (schema 348)
- MSME (schema 214) → chains to MSME_UDYAM_REG_NUMBER VERIFY

**OCR → VERIFY Chain Verification**:
```python
def verify_ocr_chains(rules):
    for ocr_rule in rules:
        if ocr_rule['actionType'] == 'OCR':
            # OCR destination field should be VERIFY source field
            dest_field = ocr_rule['destinationIds'][0]

            # Find corresponding VERIFY rule
            verify_rule = find_verify_with_source(dest_field)

            # Check chain exists
            if verify_rule:
                if verify_rule['id'] not in ocr_rule.get('postTriggerRuleIds', []):
                    report_error("OCR missing postTriggerRuleIds", "CRITICAL")
            else:
                report_error("No VERIFY rule for OCR destination", "HIGH")
```

### 3. EXT_DROP_DOWN / EXT_VALUE Rules Evaluation

**When to expect these rules**:
- Field type is DROPDOWN, MULTI_DROPDOWN, EXTERNAL_DROP_DOWN
- Logic mentions "external dropdown", "reference table", "values from"
- Logic references Excel files (.xlsx, .xls)
- Cascading dropdown pattern (parent dropdown field)

| Check | Criteria | Severity |
|-------|----------|----------|
| Presence | External dropdown fields have EXT_DROP_DOWN rule | HIGH |
| sourceType | "FORM_FILL_DROP_DOWN" or "EXTERNAL_DATA_VALUE" | MEDIUM |
| params | Contains table/reference name | MEDIUM |
| Cascading | Parent-child dropdowns properly linked | HIGH |

**Expected count from reference**: 20 EXT_DROP_DOWN rules

### 4. Visibility Rules Evaluation

**Pattern Detection**:
```
"if X is Y then visible otherwise invisible"
```

**Expected Output**:
- MAKE_VISIBLE with condition="IN", conditionalValues=["Y"]
- MAKE_INVISIBLE with condition="NOT_IN", conditionalValues=["Y"]

| Check | Criteria | Severity |
|-------|----------|----------|
| Pair completeness | Both IN and NOT_IN rules present | MEDIUM |
| Placement | Rules on SOURCE field, not destinations | HIGH |
| Consolidation | Multiple destinations in single rule | MEDIUM |
| sourceIds | Points to controlling field | HIGH |
| destinationIds | Points to controlled field(s) | HIGH |

### 5. Mandatory Rules Evaluation

**Pattern Detection**:
```
"mandatory when X is selected"
"if X is Y then mandatory otherwise non-mandatory"
```

| Check | Criteria | Severity |
|-------|----------|----------|
| Pair completeness | Both MAKE_MANDATORY and MAKE_NON_MANDATORY | MEDIUM |
| Linked with visibility | When visibility logic includes mandatory | MEDIUM |

### 6. MAKE_DISABLED Rules Evaluation

**Pattern Detection**:
```
"Non-Editable", "non-editable", "read-only", "disable"
```

| Check | Criteria | Severity |
|-------|----------|----------|
| Consolidation | Single rule with multiple destinationIds | HIGH |
| Count check | Reference has 5, not 53 individual rules | HIGH |
| RuleCheck pattern | Uses control field for bulk disable | MEDIUM |

### 7. CONVERT_TO Rules Evaluation

**Pattern Detection**:
```
"upper case", "uppercase", "UPPER_CASE"
```

| Check | Criteria | Severity |
|-------|----------|----------|
| Presence | PAN fields have UPPER_CASE conversion | LOW |

### 8. Skip Pattern Verification

**Must NOT generate rules for**:
- Expression patterns: `mvi(`, `mm(`, `expr-eval`
- Execute patterns: `EXECUTE`, `execute rule`
- Calculation patterns: `mvi('fieldA') + mvi('fieldB')`

---

## Logic-to-Rule Verification

For each field in BUD, verify the generated rules match the logic:

### Logic Pattern → Expected Rules

| Logic Pattern | Expected Rule(s) |
|---------------|------------------|
| "Get X from OCR rule" | OCR with postTriggerRuleIds |
| "Perform X validation" | VERIFY with ordinal destinationIds |
| "Data will come from X validation" | NO RULE (it's a VERIFY destination) |
| "if X is Y then visible otherwise invisible" | MAKE_VISIBLE (IN) + MAKE_INVISIBLE (NOT_IN) |
| "if X is Y then mandatory" | MAKE_MANDATORY (IN) + MAKE_NON_MANDATORY (NOT_IN) |
| "Non-Editable" | MAKE_DISABLED |
| "External dropdown" / "reference table" | EXT_DROP_DOWN |
| "upper case field" | CONVERT_TO UPPER_CASE |
| "mvi('field')" | NO RULE (skip expression) |

### Verification Algorithm

```python
def verify_logic_to_rules(field, generated_rules):
    logic = field.logic or ''
    issues = []

    # 1. OCR Check
    if re.search(r"(from|using)\s+OCR|OCR\s+rule|Get\s+\w+\s+from\s+OCR", logic, re.I):
        ocr_rules = [r for r in generated_rules if r['actionType'] == 'OCR']
        if not ocr_rules:
            issues.append({"type": "missing_rule", "expected": "OCR", "severity": "HIGH"})
        else:
            # Check postTriggerRuleIds
            for ocr in ocr_rules:
                if not ocr.get('postTriggerRuleIds'):
                    issues.append({"type": "missing_chain", "rule": "OCR", "severity": "CRITICAL"})

    # 2. VERIFY Check (but NOT for "Data will come from")
    if re.search(r"Perform\s+\w+\s+[Vv]alidation|[Vv]alidate\s+\w+", logic, re.I):
        if not re.search(r"Data\s+will\s+come\s+from", logic, re.I):
            verify_rules = [r for r in generated_rules if r['actionType'] == 'VERIFY']
            if not verify_rules:
                issues.append({"type": "missing_rule", "expected": "VERIFY", "severity": "HIGH"})
            else:
                # Check destinationIds ordinal mapping
                for v in verify_rules:
                    dest_ids = v.get('destinationIds', [])
                    source_type = v.get('sourceType', '')
                    expected_len = get_schema_dest_count(source_type)
                    if len(dest_ids) != expected_len:
                        issues.append({
                            "type": "incorrect_ordinals",
                            "expected_len": expected_len,
                            "actual_len": len(dest_ids),
                            "severity": "CRITICAL"
                        })

    # 3. Visibility Check
    if re.search(r"(visible|invisible).*otherwise.*(visible|invisible)", logic, re.I):
        visible_rules = [r for r in generated_rules if r['actionType'] == 'MAKE_VISIBLE']
        invisible_rules = [r for r in generated_rules if r['actionType'] == 'MAKE_INVISIBLE']
        if not visible_rules or not invisible_rules:
            issues.append({"type": "missing_visibility_pair", "severity": "MEDIUM"})

    # 4. Skip Pattern Check
    if should_skip_logic(logic):
        if generated_rules:
            issues.append({"type": "should_be_skipped", "severity": "MEDIUM"})

    # 5. EXT_DROP_DOWN Check
    if has_external_reference(logic, field.field_type):
        ext_rules = [r for r in generated_rules if r['actionType'] in ['EXT_DROP_DOWN', 'EXT_VALUE']]
        if not ext_rules:
            issues.append({"type": "missing_rule", "expected": "EXT_DROP_DOWN/EXT_VALUE", "severity": "HIGH"})

    return issues
```

---

## JSON Structure Validation

Verify the generated JSON matches the exact structure of the reference:

```python
def validate_json_structure(generated):
    errors = []

    # 1. Root structure
    if 'template' not in generated:
        errors.append("Missing 'template' root key")
        return errors

    template = generated['template']

    # 2. Template required fields
    required_template_fields = ['id', 'templateName', 'documentTypes']
    for field in required_template_fields:
        if field not in template:
            errors.append(f"Missing template.{field}")

    # 3. DocumentTypes structure
    if 'documentTypes' not in template or not template['documentTypes']:
        errors.append("Missing or empty documentTypes array")
        return errors

    doc_type = template['documentTypes'][0]

    # 4. FormFillMetadatas
    if 'formFillMetadatas' not in doc_type:
        errors.append("Missing formFillMetadatas in documentType")
        return errors

    # 5. Validate each rule structure
    for meta in doc_type['formFillMetadatas']:
        for rule in meta.get('formFillRules', []):
            rule_errors = validate_rule_structure(rule)
            errors.extend(rule_errors)

    return errors

def validate_rule_structure(rule):
    errors = []
    required_fields = [
        'id', 'createUser', 'updateUser', 'actionType', 'processingType',
        'sourceIds', 'executeOnFill', 'executeOnRead',
        'executeOnEsign', 'executePostEsign', 'runPostConditionFail'
    ]

    for field in required_fields:
        if field not in rule:
            errors.append(f"Rule {rule.get('id', 'unknown')} missing required field: {field}")

    # Type validation
    if 'sourceIds' in rule and not isinstance(rule['sourceIds'], list):
        errors.append(f"Rule {rule.get('id')}: sourceIds must be array")

    if 'destinationIds' in rule and not isinstance(rule['destinationIds'], list):
        errors.append(f"Rule {rule.get('id')}: destinationIds must be array")

    return errors
```

---

## Rule Count Comparison

Compare rule type distribution between generated and reference:

```python
EXPECTED_RULE_COUNTS = {
    "MAKE_VISIBLE": 18,
    "MAKE_INVISIBLE": 19,
    "MAKE_DISABLED": 5,          # Should be consolidated!
    "MAKE_MANDATORY": 12,
    "MAKE_NON_MANDATORY": 12,
    "EXT_DROP_DOWN": 20,
    "VERIFY": 5,                 # PAN, GSTIN, GSTIN_WITH_PAN, Bank, MSME
    "OCR": 6,                    # PAN, GSTIN, Aadhaar Back, Cheque, MSME, CIN
    "CONVERT_TO": 10,
    "COPY_TO": 15,
}

def compare_rule_counts(generated_rules, reference_rules):
    gen_counts = count_by_action_type(generated_rules)
    ref_counts = count_by_action_type(reference_rules)

    discrepancies = []
    for action_type, expected in EXPECTED_RULE_COUNTS.items():
        gen_count = gen_counts.get(action_type, 0)
        ref_count = ref_counts.get(action_type, expected)

        if gen_count != ref_count:
            severity = "HIGH" if abs(gen_count - ref_count) > 5 else "MEDIUM"

            # Special case: MAKE_DISABLED should be 5, not 53
            if action_type == "MAKE_DISABLED" and gen_count > 10:
                discrepancies.append({
                    "action_type": action_type,
                    "generated": gen_count,
                    "expected": ref_count,
                    "issue": "Rules not consolidated - should have single rule with multiple destinationIds",
                    "severity": "HIGH"
                })
            else:
                discrepancies.append({
                    "action_type": action_type,
                    "generated": gen_count,
                    "expected": ref_count,
                    "severity": severity
                })

    return discrepancies
```

---

## Evaluation Metrics

### Coverage Metrics
- **Field Coverage**: % of BUD fields with generated rules
- **Rule Coverage**: % of expected rules that exist
- **Panel Coverage**: % of panels fully covered

### Accuracy Metrics
- **Exact Match Rate**: Rules match reference exactly
- **Semantic Match Rate**: Rules achieve same behavior
- **False Positive Rate**: Incorrect or unnecessary rules
- **Skip Pattern Compliance**: Expression/execute patterns correctly skipped

### Critical Metrics (Must be 100%)
- **Ordinal Mapping Correctness**: VERIFY destinationIds structure
- **Rule Chaining Correctness**: OCR → VERIFY postTriggerRuleIds
- **JSON Structure Validity**: All required fields present
- **Field-Level Rule Match**: Rules on correct fields (not just correct counts!)
- **sourceIds Length Match**: All VERIFY rules have required source fields
- **No Strict Rule Misplacement**: DELETE_DOCUMENT, UNDELETE_DOCUMENT only where expected

### Quality Metrics
- **Visibility Pair Completeness**: IN + NOT_IN pairs
- **Rule Consolidation**: MAKE_DISABLED merged correctly
- **EXT_DROP_DOWN Coverage**: External dropdowns detected

---

## Output Format

### Eval Report JSON

```json
{
  "evaluation_summary": {
    "generated_output": "path/to/generated.json",
    "reference_output": "path/to/reference.json",
    "bud_document": "path/to/bud.docx",
    "evaluation_timestamp": "2026-01-30T14:35:00Z",
    "overall_score": 0.85,
    "pass_threshold": 0.90,
    "evaluation_passed": false
  },

  "panel_evaluation": [
    {
      "panel_name": "Basic Details",
      "total_fields": 10,
      "fields_evaluated": 10,
      "fields_with_issues": 2,
      "panel_score": 0.80,
      "issues": [
        {"field": "Transaction ID", "issue": "Missing MAKE_DISABLED", "severity": "MEDIUM"}
      ]
    },
    {
      "panel_name": "GST Details",
      "total_fields": 15,
      "fields_evaluated": 15,
      "fields_with_issues": 5,
      "panel_score": 0.67,
      "issues": [
        {"field": "GSTIN", "issue": "VERIFY missing postTriggerRuleIds", "severity": "HIGH"},
        {"field": "GSTIN IMAGE", "issue": "OCR missing chain to VERIFY", "severity": "CRITICAL"}
      ]
    }
  ],

  "bud_logic_verification": {
    "total_fields_with_logic": 150,
    "fields_correctly_processed": 120,
    "fields_with_issues": 30,
    "logic_compliance_rate": 0.80,
    "unprocessed_patterns": [
      {"pattern": "Perform Bank validation", "count": 1, "fields": ["Bank Account Number"]},
      {"pattern": "MSME validation", "count": 1, "fields": ["MSME Number"]}
    ]
  },

  "rule_type_comparison": {
    "reference": {
      "MAKE_VISIBLE": 18,
      "MAKE_INVISIBLE": 19,
      "MAKE_DISABLED": 5,
      "VERIFY": 5,
      "OCR": 6,
      "EXT_DROP_DOWN": 20
    },
    "generated": {
      "MAKE_VISIBLE": 8,
      "MAKE_INVISIBLE": 8,
      "MAKE_DISABLED": 53,
      "VERIFY": 2,
      "OCR": 2,
      "EXT_DROP_DOWN": 3
    },
    "discrepancies": [
      {"type": "MAKE_DISABLED", "issue": "53 vs 5 - not consolidated", "severity": "HIGH"},
      {"type": "VERIFY", "issue": "Missing 3 VERIFY rules", "severity": "HIGH"},
      {"type": "OCR", "issue": "Missing 4 OCR rules", "severity": "HIGH"},
      {"type": "EXT_DROP_DOWN", "issue": "Missing 17 rules", "severity": "HIGH"}
    ]
  },

  "critical_checks": {
    "json_structure_valid": true,
    "verify_ordinal_mapping": {
      "total_verify_rules": 2,
      "correct_ordinals": 1,
      "incorrect_ordinals": 1,
      "details": [
        {"field": "PAN", "status": "PASS", "dest_count": 9},
        {"field": "GSTIN", "status": "FAIL", "expected": 11, "actual": 5}
      ]
    },
    "ocr_verify_chains": {
      "total_ocr_rules": 2,
      "correctly_chained": 0,
      "missing_chains": 2,
      "details": [
        {"ocr_field": "Upload PAN", "verify_field": "PAN", "chained": false},
        {"ocr_field": "GSTIN IMAGE", "verify_field": "GSTIN", "chained": false}
      ]
    },
    "multi_source_verify_check": {
      "note": "Check VERIFY rules have ALL required sourceIds per schema",
      "rules_checked": [
        {
          "source_type": "BANK_ACCOUNT_NUMBER",
          "required_sources": 2,
          "actual_sources": 1,
          "status": "FAIL",
          "missing_field": "IFSC Code",
          "api_error_predicted": "Id is not present for the mandatory field Bank Account Number"
        }
      ],
      "pass_rate": 0.0
    },
    "over_generation_check": {
      "note": "Detect when generated count significantly exceeds reference",
      "threshold": 1.5,
      "issues": [
        {"action_type": "MAKE_DISABLED", "generated": 53, "expected": 5, "ratio": 10.6, "severity": "HIGH"}
      ]
    },
    "skipped_rule_types": {
      "note": "These rule types are excluded from evaluation (TEMPORARY)",
      "types": ["EXT_VALUE", "EXT_DROP_DOWN"],
      "reason": "External data value rules require complex table mapping - to be implemented later"
    },
    "field_level_rule_comparison": {
      "note": "CRITICAL: Compare rules FIELD BY FIELD, not just total counts",
      "total_fields_compared": 168,
      "fields_with_correct_rules": 112,
      "fields_with_extra_rules": 35,
      "fields_with_missing_rules": 21,
      "pass_rate": 0.67,
      "extra_rule_issues": [
        {
          "field": "Account Group/Vendor Type",
          "extra_rules": ["DELETE_DOCUMENT", "UNDELETE_DOCUMENT", "MAKE_VISIBLE", "MAKE_INVISIBLE", "COPY_TO"],
          "severity": "HIGH",
          "fix": "Remove these rules - reference only has EXT_VALUE, VALIDATION"
        },
        {
          "field": "Select the process type",
          "extra_rules": ["DELETE_DOCUMENT", "UNDELETE_DOCUMENT"],
          "severity": "HIGH",
          "fix": "Remove these rules - not in reference for this field"
        }
      ],
      "missing_rule_issues": [
        {
          "field": "GSTIN",
          "missing_rules": ["VERIFY"],
          "severity": "CRITICAL",
          "fix": "Add VERIFY rule with correct sourceIds"
        }
      ]
    },
    "strict_rule_misplacement": {
      "note": "DELETE_DOCUMENT, UNDELETE_DOCUMENT should only appear where reference has them",
      "total_misplaced": 15,
      "details": [
        {"field": "Account Group/Vendor Type", "misplaced_rules": ["DELETE_DOCUMENT", "UNDELETE_DOCUMENT"]},
        {"field": "Country", "misplaced_rules": ["DELETE_DOCUMENT", "UNDELETE_DOCUMENT"]}
      ]
    },
    "source_destination_id_validation": {
      "note": "Check sourceIds and destinationIds match reference structure",
      "issues": [
        {
          "rule_type": "VERIFY",
          "source_type": "BANK_ACCOUNT_NUMBER",
          "issue": "sourceIds has 1 element, should have 2 (IFSC + Account)",
          "severity": "CRITICAL"
        }
      ]
    }
  },

  "missing_rules": [
    {
      "category": "VERIFY",
      "missing_count": 3,
      "fields": [
        {"name": "Bank Account Number", "expected_type": "BANK_ACCOUNT_NUMBER", "schema_id": 361},
        {"name": "MSME Number", "expected_type": "MSME_UDYAM_REG_NUMBER", "schema_id": 337},
        {"name": "GSTIN", "expected_type": "GSTIN_WITH_PAN", "note": "Cross-validation"}
      ]
    },
    {
      "category": "OCR",
      "missing_count": 4,
      "fields": [
        {"name": "Cheque Upload", "expected_type": "CHEQUEE", "schema_id": 269},
        {"name": "Aadhaar Back Upload", "expected_type": "AADHAR_BACK_IMAGE", "schema_id": 348},
        {"name": "CIN Upload", "expected_type": "CIN"},
        {"name": "MSME Upload", "expected_type": "MSME", "schema_id": 214}
      ]
    },
    {
      "category": "EXT_DROP_DOWN",
      "missing_count": 17,
      "pattern": "Fields with external/cascading dropdown logic"
    }
  ],

  "false_positives": [
    {
      "field": "Type",
      "issue": "Duplicate MAKE_DISABLED rules (2 instead of 1)",
      "recommendation": "Deduplicate rules"
    }
  ],

  "self_heal_instructions": {
    "priority_fixes": [
      {
        "priority": 1,
        "fix_type": "ocr_verify_chains",
        "description": "Add postTriggerRuleIds to link OCR → VERIFY",
        "affected_fields": ["Upload PAN", "GSTIN IMAGE"],
        "implementation": "ocr_rule['postTriggerRuleIds'] = [verify_rule_id]"
      },
      {
        "priority": 2,
        "fix_type": "missing_verify_rules",
        "description": "Add VERIFY rules for BANK, MSME, GSTIN_WITH_PAN",
        "affected_fields": ["Bank Account Number", "MSME Number", "GSTIN"],
        "schema_ids": {"BANK_ACCOUNT_NUMBER": 361, "MSME_UDYAM_REG_NUMBER": 337}
      },
      {
        "priority": 3,
        "fix_type": "missing_ocr_rules",
        "description": "Add OCR rules for CHEQUEE, AADHAR_BACK, CIN, MSME",
        "affected_fields": ["Cheque Upload", "Aadhaar Back", "CIN Upload", "MSME Upload"],
        "schema_ids": {"CHEQUEE": 269, "AADHAR_BACK_IMAGE": 348, "MSME": 214}
      },
      {
        "priority": 4,
        "fix_type": "ext_dropdown_rules",
        "description": "Add EXT_DROP_DOWN for external/cascading dropdowns",
        "pattern": "Look for external table references, Excel files, parent dropdown"
      },
      {
        "priority": 5,
        "fix_type": "consolidate_disabled_rules",
        "description": "Merge 53 MAKE_DISABLED into 5 consolidated rules",
        "implementation": "Group by sourceIds + condition, merge destinationIds"
      }
    ]
  }
}
```

---

## Console Output

```
================================================================
RULE EXTRACTION EVALUATION REPORT
================================================================
Generated: adws/2026-01-30_14-30-45/populated_schema.json
Reference: documents/json_output/vendor_creation_sample_bud.json
BUD Source: documents/Vendor Creation Sample BUD.docx

Overall Score: 42% (Threshold: 90%) - FAILED
----------------------------------------------------------------

PANEL-BY-PANEL EVALUATION:
----------------------------------------------------------------
Panel: Basic Details           Score: 85%  (2 issues)
Panel: GST Details             Score: 45%  (8 issues) ⚠️
Panel: Address Details         Score: 70%  (5 issues)
Panel: Bank Details            Score: 30%  (6 issues) ⚠️
Panel: MSME Details            Score: 20%  (4 issues) ⚠️
...

BUD LOGIC VERIFICATION:
----------------------------------------------------------------
Fields with logic analyzed: 150
Correctly processed: 120 (80%)
Issues detected: 30

Missing patterns:
  - "Perform Bank validation" → No VERIFY rule (1 field)
  - "MSME validation" → No VERIFY rule (1 field)
  - "External dropdown" → No EXT_DROP_DOWN (17 fields)

CRITICAL CHECKS:
----------------------------------------------------------------
❌ OCR → VERIFY Chaining: 0% (0/6 rules chained)
⚠️ VERIFY Ordinal Mapping: 50% (1/2 correct)
✅ JSON Structure: Valid

RULE TYPE COMPARISON:
----------------------------------------------------------------
Type            Generated  Reference  Status
MAKE_VISIBLE         8         18     MISSING 10
MAKE_INVISIBLE       8         19     MISSING 11
MAKE_DISABLED       53          5     ⚠️ NOT CONSOLIDATED
VERIFY               2          5     MISSING 3
OCR                  2          6     MISSING 4
EXT_DROP_DOWN        3         20     MISSING 17

TOP PRIORITY FIXES:
----------------------------------------------------------------
1. [CRITICAL] Add postTriggerRuleIds to OCR rules for VERIFY chaining
2. [HIGH] Add missing VERIFY: BANK_ACCOUNT_NUMBER, MSME, GSTIN_WITH_PAN
3. [HIGH] Add missing OCR: CHEQUEE, AADHAR_BACK, CIN, MSME
4. [HIGH] Add EXT_DROP_DOWN for 17 external dropdown fields
5. [HIGH] Consolidate 53 MAKE_DISABLED rules into 5

================================================================
Detailed report saved to: adws/2026-01-30_14-30-45/eval_report.json
================================================================
```

---

## Pass/Fail Criteria

### Must Pass (Critical)
- [ ] JSON structure valid
- [ ] OCR → VERIFY chain correctness ≥ 90%
- [ ] VERIFY ordinal mapping correctness ≥ 90%
- [ ] No critical severity issues

### Should Pass (High)
- [ ] Rule type counts within 20% of reference
- [ ] Field coverage ≥ 85%
- [ ] Overall score ≥ 90%

### Evaluation Passes If:
1. All critical checks pass
2. Overall score ≥ 0.90
3. High severity issues ≤ 5

---

## Interpreting Discrepancies

### When Generated > Reference (Over-generation)
This indicates the extraction is generating rules that don't exist in the reference. Check:
1. **Is the logic pattern too broad?** Tighten regex patterns
2. **Are duplicate rules being created?** Improve deduplication
3. **Is the field type check correct?** Only generate EXT_DROP_DOWN for DROPDOWN types

### When Generated < Reference (Under-generation)
This indicates missing rules. Check:
1. **Is the BUD logic being parsed correctly?** Verify doc_parser extracts all logic text
2. **Are all pattern variants covered?** Add missing keyword patterns
3. **Are rules being incorrectly skipped?** Check skip patterns aren't too aggressive

### When Chain Rate < 100%
Missing OCR → VERIFY chains. Check:
1. **Does the OCR type have a corresponding VERIFY type?** (AADHAR types do NOT)
2. **Is the VERIFY rule being generated?** OCR can only chain to existing VERIFY
3. **Is the destination field ID correctly identified?** OCR dest = VERIFY source

### Acceptable Discrepancies
Some discrepancies are acceptable:
- **±2-3 rules** of certain types due to interpretation differences
- **AADHAR OCR without chains** - These don't have VERIFY rules
- **Minor consolidation differences** - As long as behavior is equivalent

---

## Rule Type Reference

| Action Type | Processing | When to Generate | Expected Count |
|-------------|------------|------------------|----------------|
| MAKE_VISIBLE | CLIENT | "visible when/if" logic | ~18 |
| MAKE_INVISIBLE | CLIENT | "invisible when/if" logic | ~19 |
| MAKE_DISABLED | CLIENT | "Non-Editable", consolidated | ~5 |
| MAKE_MANDATORY | CLIENT | "mandatory when/if" | ~12 |
| MAKE_NON_MANDATORY | CLIENT | "non-mandatory", "optional" | ~10-12 |
| VERIFY | SERVER | "Perform X validation" | ~5-6 |
| OCR | SERVER | "from OCR", "Get X from OCR" | ~6-7 |
| EXT_DROP_DOWN | CLIENT/SERVER | External table reference | ~20 |
| EXT_VALUE | SERVER | External data value | ~13 |
| CONVERT_TO | CLIENT | "upper case", case conversion | ~21 |
| VALIDATION | CLIENT | Format validation patterns | ~18 |
| COPY_TO | SERVER | "copy to", "derive from" | ~12 |

---

## Self-Heal Instruction Generation

When generating self_heal_instructions, prioritize fixes as follows:

1. **CRITICAL (Priority 1)**: OCR → VERIFY chain linking
2. **HIGH (Priority 2-3)**: Missing rules (VERIFY, OCR, visibility)
3. **MEDIUM (Priority 4-5)**: Rule consolidation, count mismatches
4. **LOW (Priority 6+)**: Minor discrepancies, formatting

Each instruction should include:
- **fix_type**: Category of fix (e.g., "ocr_verify_chains", "missing_verify_rules")
- **description**: Clear description of what to fix
- **affected_fields/sourceTypes**: Specific items affected
- **implementation**: Code hint or approach (optional)

---

## Hard Constraints

* **BUD is the source of truth** - logic in BUD determines expected rules
* **Panel-by-panel evaluation** - identify issues per panel
* **Intelligent comparison** - understand rule semantics, not just structure
* **Comprehensive checking** - verify all rule types (VERIFY, OCR, visibility, mandatory, disabled, EXT_DROP_DOWN)
* **Critical checks must pass** - OCR chains, ordinal mapping, JSON structure
* **Actionable feedback** - provide specific fixes in self_heal_instructions
* **Reference as validation** - use reference JSON to confirm expected behavior

---

## Usage in Orchestrator

1. Orchestrator runs rule extraction agent
2. Orchestrator calls this eval skill with:
   - Generated output path
   - Reference output path
   - BUD document path
   - Eval report output path
3. Eval skill performs comprehensive evaluation
4. If evaluation fails:
   - Feed `self_heal_instructions` to code agent
   - Code agent fixes issues
   - Re-run eval (max 3 iterations)
5. Evaluation passes → proceed to next step

This is a **critical quality gate** that ensures reliable and robust rule extraction.
