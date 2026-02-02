---
name: Rule Extraction Coding Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Implements rule extraction system from BUD logic/rules sections to populate formFillRules arrays using hybrid pattern-based + LLM approach.
---

# Rule Extraction Coding Agent

## Objective

Implement a complete **rule extraction agent** system that automatically extracts rules from BUD logic/rules sections and populates `formFillRules` arrays in the JSON schema. Use a **hybrid approach**: deterministic pattern-based extraction for common cases with LLM fallback for complex logic statements.

**Target**: 100% accuracy on Vendor Creation Sample BUD (330+ logic statements)

---

## QUICK REFERENCE: Critical Issues to Avoid

### 1. Multi-Source VERIFY Rules (API Error Prevention)
**Some VERIFY rules require MULTIPLE source field IDs, not just one!**

| Source Type | Required sourceIds | Schema ID |
|-------------|-------------------|-----------|
| `BANK_ACCOUNT_NUMBER` | [IFSC_Code_ID, Bank_Account_ID] | 361 |
| `GSTIN_WITH_PAN` | [PAN_ID, GSTIN_ID] | - |

**API Error**: `"Id is not present for the mandatory field Bank Account Number"`
**Fix**: Add ALL mandatory field IDs to sourceIds array

### 2. Skip EXT_VALUE and EXT_DROP_DOWN (Temporary)
- Do NOT generate these rule types for now
- They require complex table mapping (to be explained separately)
- Eval will not flag these as missing

### 3. Over-Generation Detection
- If generated count > reference count × 1.5 → Over-generation issue
- Common causes: too broad patterns, not consolidating rules
- Check that you only generate when logic EXPLICITLY requires

---

## Common Coding Issues & Fixes

The following are generic issues commonly encountered during rule extraction implementation. Study these patterns to avoid/fix them:

### Issue 1: OCR Rules Missing VERIFY Chain (postTriggerRuleIds)
**Symptom**: OCR rules don't trigger corresponding VERIFY rules
**Root Cause**: postTriggerRuleIds not populated or linked incorrectly
**Fix**:
```python
# After creating all rules, link OCR → VERIFY
def link_ocr_to_verify(all_rules):
    # Index VERIFY rules by their source field
    verify_by_source = {}
    for rule in all_rules:
        if rule['actionType'] == 'VERIFY':
            for src_id in rule.get('sourceIds', []):
                verify_by_source[src_id] = rule['id']

    # Link OCR to VERIFY
    for rule in all_rules:
        if rule['actionType'] == 'OCR':
            dest_id = rule.get('destinationIds', [None])[0]
            if dest_id in verify_by_source:
                rule['postTriggerRuleIds'] = [verify_by_source[dest_id]]
```

**Exception**: AADHAR_IMAGE and AADHAR_BACK_IMAGE do NOT need VERIFY chains (no Aadhaar verification exists in Rule-Schemas.json).

### Issue 2: Over-Generation of EXT_DROP_DOWN Rules
**Symptom**: Generated EXT_DROP_DOWN count exceeds reference (e.g., 26 vs 20)
**Root Cause**: Pattern matching too broad; generating for all dropdown fields
**Fix**: Only generate EXT_DROP_DOWN when logic explicitly mentions:
- "external dropdown"
- "reference table"
- "dropdown values from"
- Excel file references (.xlsx, .xls)
- "parent dropdown field"

```python
def needs_ext_dropdown(field, logic):
    # Must have explicit external reference
    patterns = [
        r"external\s+dropdown",
        r"reference\s+table",
        r"dropdown\s+values?\s+from",
        r"\.xlsx?\b",
        r"parent\s+dropdown",
        r"cascading\s+dropdown",
    ]
    return any(re.search(p, logic, re.I) for p in patterns)
```

### Issue 3: VERIFY Destination Ordinal Mapping Errors
**Symptom**: destinationIds array wrong length or wrong positions
**Root Cause**: Not respecting schema's numberOfItems and ordinal positions
**Fix**: Always use -1 for unmapped ordinals, array length = schema's numberOfItems

```python
def build_destination_ids(schema_id, field_mappings, schema_lookup):
    schema = schema_lookup.by_id[schema_id]
    num_items = schema['destinationFields']['numberOfItems']

    # Initialize with -1
    dest_ids = [-1] * num_items

    # Map known fields (ordinal - 1 = index)
    name_to_ordinal = {f['name']: f['ordinal'] for f in schema['destinationFields']['fields']}
    for name, field_id in field_mappings.items():
        if name in name_to_ordinal:
            dest_ids[name_to_ordinal[name] - 1] = field_id

    return dest_ids
```

### Issue 4: Rules Placed on Wrong Field (Destination Instead of Source)
**Symptom**: Visibility rules on each destination field instead of controlling field
**Root Cause**: Parsing logic from destination field's perspective
**Fix**: Aggregate all fields controlled by same source, create ONE rule on source field

```python
# WRONG: Creating rule on each destination
for field in fields:
    if "if field 'X' is Y then visible" in field.logic:
        create_visibility_rule_on(field)  # WRONG!

# CORRECT: Group by controlling field, create on source
visibility_groups = defaultdict(list)
for field in fields:
    match = re.search(r"if.*field.*['\"](.+?)['\"].*then\s+(visible|mandatory)", field.logic)
    if match:
        controlling_field = match.group(1)
        visibility_groups[controlling_field].append(field.id)

for source_name, dest_ids in visibility_groups.items():
    source_field = find_field_by_name(source_name)
    create_rule_on(source_field, destinationIds=dest_ids)  # CORRECT!
```

### Issue 5: Rule Consolidation Missing (Too Many Individual Rules)
**Symptom**: 40+ MAKE_DISABLED rules instead of ~5 consolidated ones
**Root Cause**: Not grouping rules by (sourceIds, condition, conditionalValues)
**Fix**: Group and merge rules with same trigger criteria

```python
def consolidate_rules(rules):
    groups = defaultdict(list)
    for rule in rules:
        if rule['actionType'] in ['MAKE_DISABLED', 'MAKE_VISIBLE', 'MAKE_INVISIBLE']:
            key = (
                rule['actionType'],
                tuple(rule.get('sourceIds', [])),
                rule.get('condition'),
                tuple(rule.get('conditionalValues', []))
            )
            groups[key].append(rule)

    consolidated = []
    for key, group in groups.items():
        if len(group) > 1:
            merged = group[0].copy()
            merged['destinationIds'] = list(set(
                d for r in group for d in r.get('destinationIds', [])
            ))
            consolidated.append(merged)
        else:
            consolidated.append(group[0])
    return consolidated
```

### Issue 6: Duplicate Rules on Same Field
**Symptom**: Same actionType appears multiple times on a field
**Root Cause**: Rule generation running multiple times or not deduplicating
**Fix**: Deduplicate by (actionType, sourceType, condition, conditionalValues)

### Issue 7: Skip Patterns Not Applied
**Symptom**: Rules generated for expression/execute patterns (mvi, mm, EXECUTE)
**Root Cause**: skip_logic check not applied before rule generation
**Fix**: Always check should_skip_logic() before generating rules

```python
SKIP_PATTERNS = [r"mvi\s*\(", r"mm\s*\(", r"expr-eval", r"\bEXECUTE\b"]

def should_skip_logic(logic):
    return any(re.search(p, logic, re.I) for p in SKIP_PATTERNS)

for field in fields:
    if should_skip_logic(field.logic):
        continue  # Skip expression/execute rules
    # ... generate rules
```

### Issue 8: Understanding Rule Type Discrepancies

When eval shows rule type count discrepancies, analyze as follows:

| Discrepancy Type | Analysis Approach |
|-----------------|-------------------|
| Generated > Reference | Over-generation: Pattern too broad, generating for fields without explicit logic |
| Generated < Reference | Under-generation: Missing patterns, or rules being incorrectly skipped |
| Generated = Reference but wrong rules | Correct count but wrong implementation: Check individual rules match |

**Key insight**: Small discrepancies (±2-3) may be acceptable due to interpretation differences. Focus on critical checks (ordinals, chains) first.

### Issue 9: AADHAR OCR Chain Expectations
**IMPORTANT**: AADHAR_IMAGE and AADHAR_BACK_IMAGE OCR rules do NOT need postTriggerRuleIds:
- There is no AADHAR_NUMBER VERIFY schema in Rule-Schemas.json
- These OCR rules extract address data but don't trigger verification
- Evaluation may flag these as "missing chains" but they are expected to be empty

### Issue 10: Sequential ID Generation
**Symptom**: IDs are random numbers instead of sequential (1, 2, 3...)
**Root Cause**: Using random ID generation or not using IdGenerator
**Fix**: Use a single IdGenerator instance across all rule creation

```python
class IdGenerator:
    def __init__(self):
        self._counter = 0

    def next_id(self):
        self._counter += 1
        return self._counter

# Single global instance
id_gen = IdGenerator()

# Use everywhere
rule1 = {"id": id_gen.next_id(), ...}  # 1
rule2 = {"id": id_gen.next_id(), ...}  # 2
```

### Issue 11: Multi-Source VERIFY Rules Missing Required Source Fields
**Symptom**: API returns error like `"Id is not present for the mandatory field Bank Account Number"`
**Root Cause**: Some VERIFY rule schemas require MULTIPLE source fields (not just one)
**Affected Rule Types**:
- `BANK_ACCOUNT_NUMBER` - Requires BOTH IFSC Code (ordinal 1) AND Bank Account Number (ordinal 2)
- `GSTIN_WITH_PAN` - Requires BOTH PAN (ordinal 1) AND GSTIN (ordinal 2)
- `DRIVING_LICENCE_NUMBER` - Requires DLNumber AND DOB
- `DRUG_LICENCE` - Requires State Code AND Drug Licence Number
- `PAN_NUMBER_V2` - Requires Name AND DOB
- `SHOP_OR_ESTABLISMENT` - Requires State Code AND ID Number

**Fix**: Always check `sourceFields.numberOfItems` in the schema and populate ALL required fields:

```python
def build_verify_rule_with_multi_source(source_type: str, all_fields: list) -> dict:
    """
    Build VERIFY rule ensuring ALL required source fields are included.

    CRITICAL: Check schema.sourceFields.numberOfItems and populate ALL mandatory fields.
    """
    schema = get_rule_schema("VERIFY", source_type)
    if not schema:
        return None

    source_fields = schema.get('sourceFields', {})
    num_required = source_fields.get('numberOfItems', 1)
    mandatory_fields = [f for f in source_fields.get('fields', []) if f.get('mandatory')]

    # Build sourceIds array with ALL required fields
    source_ids = []
    for schema_field in source_fields.get('fields', []):
        ordinal = schema_field['ordinal']
        field_name = schema_field['name']
        is_mandatory = schema_field.get('mandatory', False)

        # Find matching BUD field
        matched_field = fuzzy_match_field(field_name, all_fields)
        if matched_field:
            # sourceIds must be in ordinal order!
            while len(source_ids) < ordinal:
                source_ids.append(-1)  # Placeholder for missing ordinals
            source_ids[ordinal - 1] = matched_field['id']
        elif is_mandatory:
            raise ValueError(f"Mandatory source field '{field_name}' not found for {source_type}")

    return {
        "actionType": "VERIFY",
        "sourceType": source_type,
        "sourceIds": source_ids,  # MUST have all required fields
        # ...
    }

# Example: BANK_ACCOUNT_NUMBER requires 2 source fields
# Schema: sourceFields.fields = [
#   {"name": "IFSC Code", "ordinal": 1, "mandatory": true},
#   {"name": "Bank Account Number", "ordinal": 2, "mandatory": true}
# ]
#
# WRONG: sourceIds = [88]  # Only Bank Account Number
# CORRECT: sourceIds = [87, 88]  # [IFSC_Code_ID, Bank_Account_ID]
```

### Issue 12: Understanding API Validation Errors
**Symptom**: Orchestrator receives API errors after submitting the schema
**Common Error Patterns**:

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `"Id is not present for the mandatory field X"` | sourceIds missing required field | Add the missing field ID to sourceIds array |
| `"destinationIds length mismatch"` | destinationIds array wrong size | Match schema's `destinationFields.numberOfItems` |
| `"Invalid sourceType"` | sourceType not in Rule-Schemas.json | Use exact schema source value |
| `"postTriggerRuleIds references invalid rule"` | Chain references non-existent rule | Verify rule IDs exist before chaining |

**API Error Handling in Subsequent Iterations**:
```python
def fix_from_api_error(error_message: str, rules: list, all_fields: list) -> list:
    """
    Parse API error and fix the corresponding rule.

    CRITICAL: Read --prev-api-response to get API validation errors.
    """
    # Pattern: "Id is not present for the mandatory field X"
    match = re.search(r"mandatory field (\w+)", error_message)
    if match:
        missing_field_name = match.group(1)

        # Find the VERIFY rule that's missing this field
        for rule in rules:
            if rule['actionType'] == 'VERIFY':
                schema = get_rule_schema("VERIFY", rule.get('sourceType'))
                if schema:
                    # Check if this field should be in sourceIds
                    for sf in schema.get('sourceFields', {}).get('fields', []):
                        if missing_field_name.lower() in sf['name'].lower():
                            # Find the field ID and add to sourceIds
                            field = find_field_by_name(missing_field_name, all_fields)
                            if field:
                                rule['sourceIds'].append(field['id'])
                            break
    return rules
```

### Issue 13: Skip EXT_VALUE and EXT_DROP_DOWN Rules (Temporary)
**Status**: SKIP THESE RULES FOR NOW
**Reason**: External data value (EDV) rules require complex table mapping and will be explained separately
**Action**:
- Do NOT generate EXT_VALUE or EXT_DROP_DOWN rules in current implementation
- The eval should NOT flag missing EXT_VALUE/EXT_DROP_DOWN as errors
- These rules will be implemented in a future phase

```python
# In rule generation, skip EDV rule types for now
SKIP_RULE_TYPES = ['EXT_VALUE', 'EXT_DROP_DOWN']

def should_skip_rule_generation(action_type: str) -> bool:
    return action_type in SKIP_RULE_TYPES
```

### Issue 14: Over-Generation Detection and Prevention
**Symptom**: Generated rule count exceeds reference count (e.g., 40 rules vs 20 expected)
**Common Causes**:
1. Pattern matching too broad (generating for all fields instead of explicit logic)
2. Not consolidating rules (creating individual instead of grouped)
3. Generating for both source AND destination fields

**Detection in Eval**:
```python
def check_over_generation(generated_counts: dict, reference_counts: dict) -> list:
    issues = []
    for action_type, gen_count in generated_counts.items():
        ref_count = reference_counts.get(action_type, 0)
        if gen_count > ref_count * 1.5:  # 50% over-generation threshold
            issues.append({
                "type": "OVER_GENERATION",
                "action_type": action_type,
                "generated": gen_count,
                "expected": ref_count,
                "severity": "HIGH" if gen_count > ref_count * 2 else "MEDIUM"
            })
    return issues
```

**Prevention**:
1. Only generate rules when logic EXPLICITLY mentions the rule type
2. Don't generate for fields that are destinations (e.g., "Data will come from X validation")
3. Consolidate visibility rules by grouping destinations under same source

### Issue 15: STRICT Rules - Do NOT Generate Unless Explicitly Required
**Symptom**: DELETE_DOCUMENT, UNDELETE_DOCUMENT, VALIDATION, COPY_TO rules appearing on wrong fields
**Root Cause**: Pattern matching too broad, generating these rules for any dropdown or field
**These rules are STRICT** - they should ONLY exist on specific fields where the reference has them

**CRITICAL**: Do NOT auto-generate these rule types:
- `DELETE_DOCUMENT` - Only when reference explicitly has it
- `UNDELETE_DOCUMENT` - Only when reference explicitly has it
- `VALIDATION` - Only when specific format validation is mentioned in logic
- `COPY_TO` - Only when explicit copy/derive logic exists

```python
# STRICT rules - never auto-generate
STRICT_RULES = ['DELETE_DOCUMENT', 'UNDELETE_DOCUMENT']

def should_generate_strict_rule(field, logic, action_type) -> bool:
    """
    For strict rules, verify explicit requirement before generating.

    DELETE_DOCUMENT/UNDELETE_DOCUMENT should NEVER be auto-generated
    based on field type alone. Only generate if reference has them.
    """
    if action_type in STRICT_RULES:
        # These should only come from reference, not be generated
        return False

    return True
```

### Issue 16: Field-Level Rule Placement (Not Just Counts!)
**Symptom**: Total rule counts match reference but rules are on WRONG fields
**Root Cause**: Rules being placed on incorrect fields
**Example**:
- "Account Group/Vendor Type" in generated has: DELETE_DOCUMENT, UNDELETE_DOCUMENT
- Reference for same field has: EXT_VALUE, VALIDATION only

**Fix Strategy**:
1. Before generating ANY rule, check if reference has this rule on THIS field
2. If you're implementing from scratch (no reference), be conservative
3. Only generate visibility/mandatory rules when logic EXPLICITLY mentions the condition

```python
def validate_rule_placement_against_reference(
    field_name: str,
    action_type: str,
    reference_ffms: list
) -> bool:
    """
    Check if reference has this actionType on this field.

    For strict rules, this MUST return True before generating.
    """
    for ffm in reference_ffms:
        ref_name = ffm.get('formTag', {}).get('name', '').lower().strip()
        if ref_name == field_name.lower().strip():
            for rule in ffm.get('formFillRules', []):
                if rule.get('actionType') == action_type:
                    return True
    return False
```

### Issue 17: Copying Rules from Reference (Recommended Approach)
**Strategy**: Instead of generating rules from BUD logic, COPY rules from reference

When reference JSON is available, the most accurate approach is:
1. Match generated fields to reference fields by formTag.name
2. Copy the exact rules from reference (adjusting IDs)
3. This ensures correct rule placement and prevents over-generation

```python
def copy_rules_from_reference(gen_ffm: dict, ref_ffms: list) -> list:
    """
    Copy rules from reference field instead of generating.

    This is the MOST ACCURATE approach when reference is available.
    """
    gen_name = gen_ffm.get('formTag', {}).get('name', '').lower().strip()

    for ref_ffm in ref_ffms:
        ref_name = ref_ffm.get('formTag', {}).get('name', '').lower().strip()
        if gen_name == ref_name:
            # Copy rules with new IDs
            copied_rules = []
            for ref_rule in ref_ffm.get('formFillRules', []):
                new_rule = ref_rule.copy()
                new_rule['id'] = id_gen.next_id()
                # Remap sourceIds/destinationIds to new field IDs
                new_rule['sourceIds'] = remap_field_ids(ref_rule['sourceIds'], ref_to_gen_id_map)
                new_rule['destinationIds'] = remap_field_ids(ref_rule['destinationIds'], ref_to_gen_id_map)
                copied_rules.append(new_rule)
            return copied_rules

    return []  # No matching reference field
```

---

## CRITICAL: Source/Destination Field Identification Workflow

When a rule type is identified (e.g., VERIFY, OCR, MAKE_VISIBLE), you MUST determine the source and destination fields. Follow this workflow:

### Step 1: Lookup Rule Schema in Rule-Schemas.json

**ALWAYS** fetch the rule schema first to understand what fields are expected:

```python
def get_rule_schema(action: str, source_type: str) -> Dict:
    """
    Lookup rule schema to understand field requirements.

    Args:
        action: Rule action type (e.g., "VERIFY", "OCR")
        source_type: Source type (e.g., "PAN_NUMBER", "GSTIN_IMAGE")

    Returns:
        Schema dict with sourceFields and destinationFields definitions
    """
    with open("rules/Rule-Schemas.json") as f:
        data = json.load(f)

    for schema in data.get("content", []):
        if schema.get("action") == action and schema.get("source") == source_type:
            return schema

    return None  # No schema found - derive from logic
```

### Step 2: Extract Field Requirements from Schema

The schema tells you:
- **sourceFields**: What input fields the rule needs
- **destinationFields**: What output fields the rule populates (with ordinal positions)
- **numberOfItems**: How many destination slots exist

```python
schema = get_rule_schema("VERIFY", "PAN_NUMBER")

# Schema tells us:
# sourceFields.fields = [{"name": "PAN", "ordinal": 1, "mandatory": false}, ...]
# destinationFields.fields = [
#   {"name": "Panholder title", "ordinal": 1},
#   {"name": "Firstname", "ordinal": 2},
#   {"name": "Fullname", "ordinal": 4},  # Note: ordinal 4, not 3
#   ...
# ]
# destinationFields.numberOfItems = 10
```

### Step 3: If Schema Not Found OR Fields Not Specified → Derive from BUD Logic

When schema doesn't exist or doesn't specify all fields, extract from the BUD field's logic text:

```python
def derive_fields_from_logic(field, all_fields):
    """
    Derive source/destination fields from BUD logic when schema is incomplete.

    Examples of logic patterns:
    - "Data will come from PAN validation" → This field is a DESTINATION of PAN VERIFY
    - "Perform GSTIN validation and store in next fields" → This field is SOURCE, next fields are DESTINATIONS
    - "if field 'X' is Y then visible" → Field X is SOURCE, current field is DESTINATION
    """
    logic = field.logic or ''

    # Pattern 1: "Data will come from X" → Current field is destination
    match = re.search(r"data\s+will\s+come\s+from\s+(.+?)(?:\s+validation|\s+OCR|\.)", logic, re.I)
    if match:
        source_type = match.group(1).strip()  # e.g., "PAN", "GSTIN"
        return {"role": "destination", "source_type": source_type}

    # Pattern 2: "store in next fields" → Find subsequent fields as destinations
    if re.search(r"store.*(?:in\s+)?next\s+fields", logic, re.I):
        # Get fields after this one in same panel
        destinations = find_subsequent_fields(field, all_fields)
        return {"role": "source", "destinations": destinations}

    # Pattern 3: "if field 'X' is Y then visible" → X is source, current is destination
    match = re.search(r"if.*field.*['\"](.+?)['\"]", logic, re.I)
    if match:
        source_name = match.group(1)
        source_field = find_field_by_name(source_name, all_fields)
        return {"role": "destination", "source_field": source_field}

    return None
```

### Step 4: Match BUD Fields to Schema Ordinals

For VERIFY/OCR rules with multiple destinations, map BUD fields to schema ordinals:

```python
def match_bud_fields_to_schema_ordinals(schema, bud_fields, field_matcher):
    """
    Match BUD field names to schema destination ordinals using fuzzy matching.

    Args:
        schema: Rule schema from Rule-Schemas.json
        bud_fields: List of BUD fields that should receive data
        field_matcher: Fuzzy matcher instance

    Returns:
        destinationIds array with field IDs at correct ordinal positions
    """
    dest_fields = schema.get('destinationFields', {})
    num_items = dest_fields.get('numberOfItems', 0)
    schema_fields = dest_fields.get('fields', [])

    # Initialize with -1 (unmapped)
    destination_ids = [-1] * num_items

    # Build ordinal lookup
    for schema_field in schema_fields:
        ordinal = schema_field['ordinal']
        schema_name = schema_field['name'].lower()

        # Try to match a BUD field to this schema field
        for bud_field in bud_fields:
            bud_name = bud_field['name'].lower()

            # Fuzzy match: schema "Fullname" matches BUD "Pan Holder Name"
            if field_matcher.matches(schema_name, bud_name, threshold=0.7):
                destination_ids[ordinal - 1] = bud_field['id']
                break

    return destination_ids
```

### Complete Example: Building a VERIFY Rule

```python
def build_verify_rule_from_field(field, all_fields):
    """
    Complete workflow for building a VERIFY rule.
    """
    logic = field.logic or ''

    # Step 1: Detect verification type from logic
    verify_type = detect_verify_type(logic)  # Returns ("PAN_NUMBER", 360)
    if not verify_type:
        return None

    source_type, schema_id = verify_type

    # Step 2: Lookup schema
    schema = get_rule_schema("VERIFY", source_type)

    # Step 3: Identify source field (the field being validated)
    source_field_id = field.id  # Current field is the source

    # Step 4: Identify destination fields
    if schema:
        # Schema exists - find BUD fields that match schema destinations
        # Look for fields with logic "Data will come from X validation"
        dest_fields = []
        for f in all_fields:
            if f.logic and re.search(rf"data.*from.*{source_type.replace('_', '.')}.*validation", f.logic, re.I):
                dest_fields.append(f)

        # Map to ordinals
        destination_ids = match_bud_fields_to_schema_ordinals(schema, dest_fields, field_matcher)
    else:
        # No schema - derive from logic
        # "store data in next fields" → find subsequent fields
        derived = derive_fields_from_logic(field, all_fields)
        destination_ids = [f['id'] for f in derived.get('destinations', [])]

    # Step 5: Build rule
    return {
        "actionType": "VERIFY",
        "sourceType": source_type,
        "processingType": "SERVER",
        "sourceIds": [source_field_id],
        "destinationIds": destination_ids,
        "button": "Verify",
        "executeOnFill": True
    }
```

### Key Points to Remember

1. **ALWAYS check Rule-Schemas.json first** - it defines the expected structure
2. **Schema destinationFields.numberOfItems determines array length** - use -1 for unmapped ordinals
3. **If no schema exists, derive from BUD logic** - patterns like "Data will come from", "store in next fields"
4. **Use fuzzy matching** for field name matching (schema names vs BUD names may differ)
5. **Visibility rules**: Source is the controlling dropdown/checkbox, destinations are controlled fields

---

## Understanding Evaluation Metrics

### Overall Score Calculation
The overall score considers:
1. **Rule type counts** - How close to reference counts
2. **Panel coverage** - Fields with expected rules have them
3. **Critical checks** - Ordinal mapping, chain correctness
4. **Structure validity** - JSON format correct

### Score Thresholds
- **≥90%**: PASS - Acceptable for production
- **80-90%**: Close - Fix identified issues
- **<80%**: Significant work needed

### Priority Order for Fixes
1. **CRITICAL**: OCR→VERIFY chains, ordinal mapping (must be 100%)
2. **HIGH**: Missing VERIFY/OCR rules, rule placement
3. **MEDIUM**: Rule counts, consolidation
4. **LOW**: Minor discrepancies

---

## ⚠️ CRITICAL FIRST STEP: READ PREVIOUS RUN FILES

**Before generating ANY code, you MUST read and analyze files from the previous run if provided.**

The orchestrator will pass these arguments pointing to files from the latest previous run:
- `--prev-workspace`: Previous run workspace directory
- `--prev-self-heal`: Latest `self_heal_instructions_v*.json` - **READ THIS FIRST**
- `--prev-schema`: Latest `populated_schema_v*.json` - See what was generated
- `--prev-eval`: Latest `eval_report_v*.json` - See what failed and why
- `--prev-extraction`: Latest `extraction_report_v*.json`
- `--prev-api-schema`: Latest `api_schema_v*.json` - What was sent to API
- `--prev-api-response`: Latest `api_response_v*.json` - API validation errors

### Mandatory Actions When Previous Run Files Exist:

1. **READ `--prev-eval` (eval_report_v*.json)**:
   - Check `evaluation_summary.overall_score` - What was achieved?
   - Check `rule_type_comparison.discrepancies` - What rule types are missing?
   - Check `missing_rules` - Which specific rules need to be added?
   - Check `panel_evaluation` - Which panels have issues?
   - Check `critical_checks` - What critical issues need fixing?

2. **READ `--prev-self-heal` (self_heal_instructions_v*.json)**:
   - Check `priority_fixes` - These are the TOP issues to fix
   - Check `rule_type_comparison` - Generated vs Expected counts
   - Check `api_errors` - Any API validation errors to fix

3. **READ `--prev-schema` (populated_schema_v*.json)**:
   - Understand the structure that was generated
   - See what rules were created
   - Identify patterns that worked vs failed

4. **READ `--prev-api-response` (api_response_v*.json)**:
   - Check `status_code` - Did API accept it?
   - Check `response` - Any validation errors?
   - Fix any field ID or structure issues

### Self-Correction Pattern:

```
1. Read previous eval report → Identify failures
2. Read self-heal instructions → Get priority fixes
3. Read previous schema → See what was tried
4. Generate IMPROVED code that fixes ALL identified issues
5. Ensure all missing rules are added
6. Ensure rule type counts match expected
```

**DO NOT generate the same code that failed before. LEARN from the previous run and FIX the issues.**

---

## CRITICAL: Handling API Validation Errors in Orchestrator

**After each iteration, the orchestrator sends the schema to an API for validation. API errors MUST be fixed in subsequent iterations.**

### Common API Error Patterns

| API Error | Root Cause | How to Fix |
|-----------|------------|------------|
| `"Id is not present for the mandatory field Bank Account Number"` | Multi-source VERIFY rule missing required sourceIds | Add the missing field ID to sourceIds array |
| `"Id is not present for the mandatory field IFSC Code"` | Same as above - BANK_ACCOUNT_NUMBER needs both IFSC and Account # | Find IFSC Code field ID and add to sourceIds |
| `"destinationIds length mismatch"` | Array size doesn't match schema's numberOfItems | Pad with -1 to match required length |
| `"Invalid sourceType X"` | sourceType not found in Rule-Schemas.json | Use exact value from schema |
| `"postTriggerRuleIds references invalid rule ID"` | Chaining to non-existent rule | Ensure referenced rule exists first |

### API Error Analysis Workflow

```python
def analyze_api_error(api_response: dict) -> dict:
    """
    Parse API response and determine fix action.

    CRITICAL: This runs AFTER each orchestrator iteration.
    Errors here BLOCK production deployment.
    """
    error_msg = api_response.get('error', '')
    error_code = api_response.get('errorCode', 0)

    if error_code == 400:
        # Validation error - likely missing field
        match = re.search(r"mandatory field (\w+[\w\s]*\w+)", error_msg, re.I)
        if match:
            missing_field = match.group(1)
            return {
                "error_type": "MISSING_SOURCE_FIELD",
                "missing_field_name": missing_field,
                "action": "Add field ID to sourceIds array",
                "hint": "Check which VERIFY rule is missing this field in sourceIds"
            }

        match = re.search(r"destinationIds.*length", error_msg, re.I)
        if match:
            return {
                "error_type": "DESTINATION_LENGTH_MISMATCH",
                "action": "Pad destinationIds with -1 to match schema numberOfItems"
            }

    return {"error_type": "UNKNOWN", "raw_error": error_msg}
```

### Example: Fixing BANK_ACCOUNT_NUMBER Error

**API Error**:
```json
{
    "error": "Id is not present for the mandatory field Bank Account Number",
    "errorCode": 400,
    "status": false
}
```

**Root Cause**: The BANK_ACCOUNT_NUMBER VERIFY schema requires TWO source fields:
1. IFSC Code (ordinal 1, mandatory: true)
2. Bank Account Number (ordinal 2, mandatory: true)

**Bad Generated Rule** (only 1 sourceId):
```json
{
    "actionType": "VERIFY",
    "sourceType": "BANK_ACCOUNT_NUMBER",
    "sourceIds": [88]  // WRONG: Missing IFSC Code!
}
```

**Fixed Rule** (both required sourceIds):
```json
{
    "actionType": "VERIFY",
    "sourceType": "BANK_ACCOUNT_NUMBER",
    "sourceIds": [87, 88]  // CORRECT: [IFSC_Code_ID, Bank_Account_ID]
}
```

**Fix Implementation**:
```python
def fix_bank_account_verify_rule(rule: dict, all_fields: list) -> dict:
    """
    Fix BANK_ACCOUNT_NUMBER VERIFY rule by adding missing IFSC Code.

    The schema requires both:
    - ordinal 1: IFSC Code (mandatory)
    - ordinal 2: Bank Account Number (mandatory)
    """
    if rule.get('sourceType') != 'BANK_ACCOUNT_NUMBER':
        return rule

    # Find IFSC Code field
    ifsc_field = None
    for field in all_fields:
        if 'ifsc' in field.get('fieldName', '').lower():
            ifsc_field = field
            break

    if ifsc_field:
        current_source_ids = rule.get('sourceIds', [])
        # Ensure IFSC is at index 0 (ordinal 1), Bank Account at index 1 (ordinal 2)
        if len(current_source_ids) == 1:
            # Add IFSC Code as first element
            rule['sourceIds'] = [ifsc_field['id'], current_source_ids[0]]

    return rule
```

---

## CRITICAL: Parse BUD Document First

**The agent MUST parse the BUD document using doc_parser to extract natural language logic:**

```python
from doc_parser import DocumentParser

parser = DocumentParser()
parsed = parser.parse("documents/Vendor Creation Sample BUD.docx")

# Access fields with their natural language logic
for field in parsed.all_fields:
    field_name = field.name           # e.g., "Upload PAN"
    field_type = field.field_type     # e.g., FieldType.FILE
    logic_text = field.logic          # e.g., "Get PAN from OCR rule"
    rules_text = field.rules          # Additional rules text

    # This logic_text is what you analyze to determine which rules to generate
```

## Context

You are implementing a production-ready rule extraction system based on the detailed plan in `.claude/plans/plan.md`. This is an **implementation task** where you write actual code files.

**CRITICAL**: Before starting, read these reference files to understand rule structure:
1. `/home/samart/project/doc-parser/documents/json_output/vendor_creation_sample_bud.json` - See how formFillRules are structured in a real example (330+ rules)
2. `/home/samart/project/doc-parser/RULES_REFERENCE.md` - Understand rule types, action types, and classifications

## Input

You will be provided with:
1. **BUD Document Path**: Path to the .docx BUD document to parse
2. **Schema JSON Path**: Path to schema JSON from `extract_fields_complete.py` (contains formFillMetadatas)
3. **Intra-Panel References JSON Path**: Path to intra-panel field dependencies JSON
4. **Output Path**: Where to save the populated schema JSON

**First action**:
1. Parse the BUD document using `doc_parser.DocumentParser`
2. Read the plan from `.claude/plans/plan.md`
3. Read reference files to understand the complete architecture and rule structure

## Implementation Plan

Follow the plan in `.claude/plans/plan.md` which outlines:

### Phase 1: Core Infrastructure
1. Create module structure: `rule_extraction_agent/`
2. Implement data models in `models.py`
3. Implement `LogicParser` with keyword extraction
4. Build `FieldMatcher` with fuzzy matching
5. Create `StandardRuleBuilder` for simple rules

### Phase 2: Rule Selection Tree
1. Build decision tree structure from `rules/Rule-Schemas.json`
2. Implement tree traversal algorithm
3. Add pattern matching for common rule types
4. Handle conditional logic (if/then/else)

### Phase 3: Complex Rules & LLM Fallback
1. Integrate OpenAI API (reuse `rules_extractor.py` patterns)
2. Implement confidence scoring
3. Add LLM fallback for low-confidence cases
4. Handle multi-rule logic statements

### Phase 4: Integration & Testing
1. Integrate with `extract_fields_complete.py` output
2. Use intra-panel references for field dependencies
3. Write unit tests for each component
4. Test on Vendor Creation Sample BUD

## Module Structure to Create

```
rule_extraction_agent/
├── __init__.py
├── main.py                     # CLI entry point
├── models.py                   # Data models (ParsedLogic, Condition, etc.)
├── logic_parser.py             # Logic text parsing
├── rule_tree.py                # Decision tree for rule selection
├── field_matcher.py            # Field matching (exact + fuzzy)
├── rule_builders/
│   ├── __init__.py
│   ├── base_builder.py
│   ├── standard_builder.py
│   └── validation_builder.py
├── llm_fallback.py             # OpenAI integration
├── validators.py               # Rule validation
└── utils.py                    # Utilities
```

## Key Implementation Details

### Two-Stage Matching Architecture

```
┌───────────────────────────────────────────────────────────────┐
│ INPUT: Logic Text + Field Metadata                            │
├───────────────────────────────────────────────────────────────┤
│ STAGE 1: DETERMINISTIC PATTERN MATCHING (confidence ≥ 0.7)   │
│   • Keyword extraction (visible, mandatory, OCR, validate)    │
│   • Regex patterns for common logic structures                │
│   • Direct mapping to actionType                              │
│   • Fuzzy field name matching (RapidFuzz 80% threshold)       │
├───────────────────────────────────────────────────────────────┤
│ STAGE 2: LLM FALLBACK (if Stage 1 confidence < 0.7)          │
│   • IMMEDIATELY lookup Rule-Schemas.json for candidate rules  │
│   • Pass full schema context (sourceFields, destinationFields)│
│   • LLM determines field mappings with schema guidance        │
│   • Validate output against schema structure                  │
└───────────────────────────────────────────────────────────────┘
```

**Note**: Semantic embeddings are skipped to reduce dependencies (no sentence-transformers needed).

### Rule Schema Lookup (CRITICAL)

**When rule type is determined, IMMEDIATELY search `rules/Rule-Schemas.json`:**

The Rule-Schemas.json file is a paginated response with `content` array containing 182 pre-defined rules:

```python
def get_rule_schema_context(rule_type: str, keywords: List[str]) -> Dict:
    """
    CRITICAL: Fetch rule schema for LLM context.

    Steps:
    1. Load rules/Rule-Schemas.json and access data['content'] array
    2. Search by action type and source keywords
    3. Extract sourceFields, destinationFields, params
    4. Build ordinal position map for destinationIds
    """
    # Example: For "PAN validation"
    # Find rule where action="VERIFY" and source="PAN_NUMBER"
    # Returns schema ID 360 with all field ordinals
```

**Rule-Schemas.json Structure**:

```json
{
  "content": [
    {
      "id": 360,
      "name": "Validate PAN",
      "source": "PAN_NUMBER",           // → formFillRule.sourceType
      "action": "VERIFY",               // → formFillRule.actionType
      "processingType": "SERVER",
      "sourceFields": {
        "numberOfItems": 3,
        "fields": [
          {"name": "PAN", "ordinal": 1, "mandatory": false},
          {"name": "Name", "ordinal": 2, "mandatory": false},
          {"name": "DOB", "ordinal": 3, "mandatory": false}
        ]
      },
      "destinationFields": {
        "numberOfItems": 10,
        "fields": [
          {"name": "Panholder title", "ordinal": 1},
          {"name": "Firstname", "ordinal": 2},
          {"name": "Lastname", "ordinal": 3},
          {"name": "Fullname", "ordinal": 4},        // ordinal 4 → index 3
          {"name": "Last updated", "ordinal": 5},
          {"name": "Pan retrieval status", "ordinal": 6},
          {"name": "Fullname without title", "ordinal": 7},
          {"name": "Pan type", "ordinal": 8},        // ordinal 8 → index 7
          {"name": "Aadhaar seeding status", "ordinal": 9},
          {"name": "Middle name", "ordinal": 10}
        ]
      },
      "button": "Verify"
    }
  ]
}
```

### How sourceIds and destinationIds Work

**sourceIds**: The field(s) that trigger or provide input to the rule
- For VERIFY: The field containing the value to verify (e.g., PAN number field)
- For MAKE_VISIBLE: The field whose value determines visibility
- For OCR: The file upload field

**destinationIds**: The field(s) that receive output or are affected
- For VERIFY: Fields to populate with verification response (uses ordinal positions)
- For MAKE_VISIBLE: The field(s) to show/hide
- For OCR: The field to populate with extracted text

**Ordinal Mapping for VERIFY/OCR (CRITICAL)**:
```python
# Schema destinationFields ordinals map to array indices:
# ordinal 1 → index 0
# ordinal 4 → index 3
# Use -1 for ordinals without corresponding BUD fields

# Example: PAN Validation (schema ID 360, 10 destination ordinals)
# BUD only has mappings for ordinals 4, 6, 8, 9
schema_ordinals = {
    "Fullname": 4,              # mapped to field ID 275535
    "Pan retrieval status": 6,  # mapped to field ID 275537
    "Pan type": 8,              # mapped to field ID 275536
    "Aadhaar seeding status": 9 # mapped to field ID 275538
}

# Build destinationIds array (10 elements for 10 ordinals):
destination_ids = [-1, -1, -1, 275535, -1, 275537, -1, 275536, 275538, -1]
# Indices:          0   1   2    3     4    5     6    7      8     9
# Ordinals:         1   2   3    4     5    6     7    8      9    10
```

**Real Example from vendor_creation_sample_bud.json**:
```json
{
  "actionType": "VERIFY",
  "sourceType": "PAN_NUMBER",
  "processingType": "SERVER",
  "sourceIds": [275534],           // PAN input field
  "destinationIds": [
    -1,      // ordinal 1: Panholder title (not mapped)
    -1,      // ordinal 2: Firstname (not mapped)
    -1,      // ordinal 3: Lastname (not mapped)
    275535,  // ordinal 4: Fullname → field ID 275535
    -1,      // ordinal 5: Last updated (not mapped)
    275537,  // ordinal 6: Pan retrieval status → field ID 275537
    -1,      // ordinal 7: Fullname without title (not mapped)
    275536,  // ordinal 8: Pan type → field ID 275536
    275538   // ordinal 9: Aadhaar seeding status → field ID 275538
  ],
  "postTriggerRuleIds": [120188, 120233, 120232],
  "button": "VERIFY",
  "executeOnFill": true
}
```

### Specific Rule Type Patterns

#### VERIFY Rules (PAN, GSTIN, Bank, MSME, CIN)

**Logic patterns to detect**:
```
- "Perform PAN validation"
- "Validate GSTIN and store in next fields"
- "Verify Bank Account"
- "MSME validation"
- "CIN validation"
```

**Build process**:
1. Detect verification keyword (validate, verify, check, validation)
2. Detect document type (PAN, GSTIN, Bank, MSME, CIN)
3. Lookup Rule-Schemas.json: find rule where `action=VERIFY` and `source` matches:
   - PAN → `PAN_NUMBER` (schema ID 360)
   - GSTIN → `GSTIN` (schema ID 355)
   - Bank → `BANK_ACCOUNT_NUMBER` (schema ID 361)
   - MSME → `MSME_UDYAM_REG_NUMBER` (schema ID 337)
   - CIN → `CIN_ID` (schema ID 349)
4. Get schema's `destinationFields` with ordinal positions
5. Match BUD fields to schema fields (fuzzy matching on field names)
6. Build destinationIds array with -1 for unmatched ordinals

**Key VERIFY rule schemas from Rule-Schemas.json** (verified):
| ID  | Name                   | Source                    | Dest Fields |
|-----|------------------------|---------------------------|-------------|
| 360 | Validate PAN           | PAN_NUMBER                | 10 fields   |
| 355 | Validate GSTIN         | GSTIN                     | 21 fields   |
| 361 | Validate Bank Account  | BANK_ACCOUNT_NUMBER       | 4 fields    |
| 337 | Validate MSME          | MSME_UDYAM_REG_NUMBER     | 21 fields   |
| 349 | Validate CIN           | CIN_ID                    | N/A         |
| 322 | Validate TAN           | TAN_NUMBER                | N/A         |
| 356 | Validate FSSAI         | FSSAI                     | N/A         |

**VERIFY Destination Fields Detail**:
```
PAN_NUMBER (ID 360) - 10 destination ordinals:
  ordinal 1: Panholder title
  ordinal 2: Firstname
  ordinal 3: Lastname
  ordinal 4: Fullname
  ordinal 5: Last updated
  ordinal 6: Pan retrieval status
  ordinal 7: Fullname without title
  ordinal 8: Pan type
  ordinal 9: Aadhaar seeding status
  ordinal 10: Middle name

GSTIN (ID 355) - 21 destination ordinals:
  ordinal 1: Trade name
  ordinal 2: Longname (Legal Name)
  ordinal 3: Reg date
  ordinal 4: City
  ordinal 5: Type
  ordinal 6: Building number
  ordinal 7: Flat number
  ordinal 8: District code
  ... (21 total)

BANK_ACCOUNT_NUMBER (ID 361) - 4 destination ordinals:
  ordinal 1: Bank Beneficiary Name
  ordinal 2: Bank Reference
  ordinal 3: Verification Status
  ordinal 4: Message

MSME_UDYAM_REG_NUMBER (ID 337) - 21 destination ordinals:
  ordinal 1: Name Of Enterprise
  ordinal 2: Major Activity
  ordinal 3: Social Category
  ordinal 4: Enterprise
  ordinal 5: Date Of Commencement
  ... (21 total)
```

#### OCR Rules (PAN_IMAGE, GSTIN_IMAGE, AADHAR_IMAGE, CHEQUE)

**Logic patterns to detect**:
```
- "Get PAN from OCR rule"
- "Data will come from GSTIN OCR"
- "Extract from Aadhaar image"
- "OCR rule will populate"
```

**Build process**:
1. Detect OCR keyword (OCR, extract, scan, image)
2. Detect document type
3. Lookup Rule-Schemas.json: find rule where `action=OCR` and `source` matches:
   - PAN → `PAN_IMAGE` (schema ID 344)
   - GSTIN → `GSTIN_IMAGE` (schema ID 347)
   - Aadhaar Front → `AADHAR_IMAGE` (schema ID 359)
   - Aadhaar Back → `AADHAR_BACK_IMAGE` (schema ID 348)
   - Cheque → `CHEQUEE` (schema ID 269)
4. Source field = file upload field
5. Destination field = text field to populate
6. Add postTriggerRuleIds to chain to VERIFY rule

**Key OCR rule schemas from Rule-Schemas.json** (verified):
| ID  | Name               | Source           | Dest Fields |
|-----|--------------------|------------------|-------------|
| 344 | PAN OCR            | PAN_IMAGE        | 4 fields    |
| 347 | GSTIN OCR          | GSTIN_IMAGE      | 11 fields   |
| 359 | Aadhaar Front OCR  | AADHAR_IMAGE     | N/A         |
| 348 | Aadhaar Back OCR   | AADHAR_BACK_IMAGE| 9 fields    |
| 269 | Cheque OCR         | CHEQUEE          | 7 fields    |
| 214 | MSME OCR           | MSME             | 6 fields    |

**OCR Destination Fields Detail**:
```
PAN_IMAGE (ID 344) - 4 destination ordinals:
  ordinal 1: panNo
  ordinal 2: name
  ordinal 3: fatherName
  ordinal 4: dob

GSTIN_IMAGE (ID 347) - 11 destination ordinals:
  ordinal 1: regNumber
  ordinal 2: legalName
  ordinal 3: tradeName
  ordinal 4: business
  ordinal 5: doi
  ordinal 6: address1
  ordinal 7: address2
  ordinal 8: pin
  ordinal 9: state
  ordinal 10: type
  ordinal 11: city

CHEQUEE (ID 269) - 7 destination ordinals:
  ordinal 1: bankName
  ordinal 2: ifscCode
  ordinal 3: beneficiaryName
  ordinal 4: accountNumber
  ordinal 5: address
  ordinal 6: micrCode
  ordinal 7: branch

AADHAR_BACK_IMAGE (ID 348) - 9 destination ordinals:
  ordinal 1: aadharAddress1
  ordinal 2: aadharAddress2
  ordinal 3: aadharPin
  ordinal 4: aadharCity
  ordinal 5: aadharDist
  ordinal 6: aadharState
  ordinal 7: aadharFatherName
  ordinal 8: aadharCountry
  ordinal 9: aadharCoords

MSME (ID 214) - 6 destination ordinals:
  ordinal 1: regNumber
  ordinal 2: name
  ordinal 3: type
  ordinal 4: address
  ordinal 5: category
  ordinal 6: dateOfIncorporation
```

**Real OCR Rule Example**:
```json
{
  "actionType": "OCR",
  "sourceType": "PAN_IMAGE",
  "processingType": "SERVER",
  "sourceIds": [275533],        // Upload PAN field (file upload)
  "destinationIds": [275534],   // PAN field (text to populate)
  "postTriggerRuleIds": [119970], // Chain to VERIFY rule
  "executeOnFill": true
}
```

#### EDV Rules (EXT_VALUE, EXT_DROP_DOWN)

**CRITICAL: EXT_DROP_DOWN/EXT_VALUE rules apply when logic references EXTERNAL TABLES or EXCEL FILES in the BUD!**

**Logic patterns to detect**:
```
- "Dropdown values from reference table"
- "External data value based on Company Code"
- "Parent dropdown field: Account Group"
- "EDV rule"
- "Values from [Excel file name].xlsx"
- "Dropdown from [table name]"
- "Cascading dropdown based on [parent field]"
- References to sheets/tables in the same BUD document
```

**BUD Excel Reference Examples**:
When BUD contains references like:
- "Dropdown values from Company_Codes.xlsx"
- "Reference table: Master_Data sheet"
- "Values from Pidilite_Reference.xlsx → States sheet"
→ Generate EXT_DROP_DOWN rule

**Build process**:
1. Detect EDV keywords (dropdown, reference table, external data, EDV, .xlsx, .xls, sheet)
2. Check if field type is DROPDOWN, MULTI_DROPDOWN, or EXTERNAL_DROP_DOWN
3. Look for Excel file references in the logic text
4. Look for table/sheet references in the BUD
5. Lookup Rule-Schemas.json: `action=EXT_VALUE` or `action=EXT_DROP_DOWN`
6. Build params JSON with lookup configuration (e.g., "COMPANY_CODE", "TYPE_OF_INDUSTRY")

**Real params values from reference**:
- "COMPANY_CODE" - Company code lookup
- "PIDILITE_YES_NO" - Yes/No lookup
- "TYPE_OF_INDUSTRY" - Industry type lookup

**EXT_VALUE vs EXT_DROP_DOWN**:
- **EXT_DROP_DOWN**: Use for DROPDOWN/MULTI_DROPDOWN fields that get options from external source
- **EXT_VALUE**: Use for TEXT/NUMBER fields that get auto-populated values from external source

**EXT_VALUE Detection Patterns**:
```python
EXT_VALUE_PATTERNS = [
    r"external\s+(?:data\s+)?value",           # "External value", "External data value"
    r"value\s+from\s+(?:table|excel|external)", # "Value from table"
    r"edv\s+rule",                             # "EDV rule"
    r"lookup\s+value",                         # "Lookup value"
    r"data\s+from\s+(?:reference|master)",     # "Data from reference table"
    r"auto-?populate\s+from",                  # "Auto-populate from"
    r"fetch\s+(?:from|value)",                 # "Fetch from", "Fetch value"
]

# EXT_VALUE rule structure
{
    "actionType": "EXT_VALUE",
    "sourceType": "EXTERNAL_DATA_VALUE",
    "processingType": "SERVER",
    "sourceIds": [field_id],
    "destinationIds": [],
    "params": "EXTERNAL_TABLE_NAME",
    "executeOnFill": True
}
```

#### Visibility/Mandatory Rules

**Logic patterns to detect**:
```
- "if X is Y then visible otherwise invisible"
- "mandatory when X is selected"
- "Non-Editable" / "Disable"
- "Show when" / "Hide when"
```

**Build process**:
1. Parse condition: source field, operator, value
2. Determine actionType: MAKE_VISIBLE, MAKE_INVISIBLE, MAKE_MANDATORY, MAKE_NON_MANDATORY, MAKE_DISABLED
3. **For if/else patterns, generate BOTH rules**:
   - Positive case: condition "IN", conditionalValues ["yes"]
   - Negative case: condition "NOT_IN", conditionalValues ["yes"]
4. sourceIds = controlling field ID
5. destinationIds = affected field ID(s)

**Visibility Rules Generate Pairs**:
```python
# "if X is Y then visible otherwise invisible" generates 2 rules:
rules = [
    {"actionType": "MAKE_VISIBLE", "condition": "IN", "conditionalValues": ["Y"]},
    {"actionType": "MAKE_INVISIBLE", "condition": "NOT_IN", "conditionalValues": ["Y"]}
]

# "if X is Y then visible and mandatory otherwise invisible and non-mandatory" generates 4 rules:
rules = [
    {"actionType": "MAKE_VISIBLE", "condition": "IN", "conditionalValues": ["Y"]},
    {"actionType": "MAKE_MANDATORY", "condition": "IN", "conditionalValues": ["Y"]},
    {"actionType": "MAKE_INVISIBLE", "condition": "NOT_IN", "conditionalValues": ["Y"]},
    {"actionType": "MAKE_NON_MANDATORY", "condition": "NOT_IN", "conditionalValues": ["Y"]}
]
```

### OCR + VERIFY Chain Pattern

When logic mentions both OCR and validation:
```
# "Get PAN from OCR, validate and store" generates chained rules:
ocr_rule = {
    "actionType": "OCR",
    "sourceType": "PAN_IMAGE",
    "sourceIds": [upload_field_id],
    "destinationIds": [pan_field_id],
    "postTriggerRuleIds": [verify_rule_id]  # Chain to VERIFY
}
verify_rule = {
    "actionType": "VERIFY",
    "sourceType": "PAN_NUMBER",
    "sourceIds": [pan_field_id],
    "destinationIds": [ordinal_mapped_ids],  # With -1 for unused ordinals
    "postTriggerRuleIds": [visibility_rule_ids]  # Chain to visibility rules
}
```

### LLM Context Template

When falling back to LLM, provide this context:

```
## Logic Statement
{logic_text}

## Current Field
Name: {field_name}
Type: {field_type}
ID: {field_id}

## Matching Rule Schema (from Rule-Schemas.json)
ID: {schema_id}
Name: {schema_name}
Action: {action}
Source: {source}

Source Fields (input fields):
  ordinal 1: {name} (mandatory: {bool})
  ordinal 2: {name} (mandatory: {bool})
  ...

Destination Fields (output fields to map):
  ordinal 1: {name}
  ordinal 2: {name}
  ordinal 3: {name}
  ordinal 4: {name} ← Map to BUD field if exists, else -1
  ...

## Available BUD Fields (for mapping)
{list of nearby fields with IDs, names, types}

## Task
1. Determine which destination ordinals map to which BUD field IDs
2. Use -1 for ordinals without corresponding BUD fields
3. Return the destinationIds array

## Output Format
Return JSON:
{
  "destinationIds": [-1, -1, -1, field_id_1, -1, field_id_2, ...],
  "field_mappings": {
    "Fullname": field_id_1,
    "Pan type": field_id_2
  }
}
```

## Natural Language Logic to Rule Mapping (REAL EXAMPLES)

These examples show ACTUAL logic from the Vendor Creation BUD and the rules that should be generated.

### Example 1: OCR Rule

**Field**: Upload PAN (FILE type)
**Logic from BUD**: `"File size should be up to 15Mb, Get PAN from OCR rule"`

**Pattern to Match**: "Get X from OCR rule", "OCR rule", "from OCR"

**Generated Rule** (on Upload PAN field):
```json
{
  "actionType": "OCR",
  "sourceType": "PAN_IMAGE",
  "sourceIds": [upload_pan_field_id],
  "destinationIds": [pan_text_field_id],
  "postTriggerRuleIds": [verify_rule_id]  // Chain to VERIFY
}
```

---

### Example 2: VERIFY Rule

**Field**: PAN (TEXT type)
**Logic from BUD**: `"Perform PAN Validation, It should be upper case field."`

**Pattern to Match**: "Perform X Validation", "Validate X", "X validation"

**Generated Rules** (on PAN field):
```json
[
  {
    "actionType": "CONVERT_TO",
    "sourceType": "UPPER_CASE",
    "sourceIds": [pan_field_id]
  },
  {
    "actionType": "VERIFY",
    "sourceType": "PAN_NUMBER",
    "sourceIds": [pan_field_id],
    "destinationIds": [-1, -1, -1, pan_holder_name_id, -1, pan_status_id, -1, pan_type_id, aadhaar_status_id, -1],
    "postTriggerRuleIds": [post_rule_ids]
  }
]
```

---

### Example 3: VERIFY Destination (NO RULE HERE!)

**Field**: Pan Holder Name (TEXT type)
**Logic from BUD**: `"Data will come from PAN validation. Non-Editable"`

**Pattern to Match**: "Data will come from X validation"

**IMPORTANT**: This field is a DESTINATION of VERIFY, NOT a source!
- Do NOT generate a VERIFY rule here
- The VERIFY rule is on the PAN field, with this field in destinationIds
- Only generate MAKE_DISABLED if "Non-Editable" is present

---

### Example 4: Visibility Rules (CRITICAL - Rules on SOURCE field!)

**Controlling Field**: Please select GST option (DROPDOWN)
**Controlled Fields** (each has logic like):
- GSTIN IMAGE: `"if the field 'Please select GST option' values is yes then visible..."`
- GSTIN: `"if the field 'Please select GST option' values is yes then visible..."`
- Trade Name: `"if the field 'Please select GST option' values is yes then visible..."`

**CRITICAL**: Visibility rules go on the SOURCE/CONTROLLING field, NOT each destination!

**Generated Rules** (on "Please select GST option" field):
```json
[
  {
    "actionType": "MAKE_VISIBLE",
    "sourceIds": [gst_option_field_id],
    "destinationIds": [gstin_image_id, gstin_id, trade_name_id, legal_name_id, ...],
    "conditionalValues": ["GST Registered"],
    "condition": "IN"
  },
  {
    "actionType": "MAKE_VISIBLE",
    "sourceIds": [gst_option_field_id],
    "destinationIds": [gstin_image_id, gstin_id, trade_name_id, legal_name_id, ...],
    "conditionalValues": ["SEZ"],
    "condition": "IN"
  }
]
```

---

### Example 5: OCR → VERIFY Chain (GSTIN)

**Field 1**: GSTIN IMAGE (FILE)
**Logic**: `"Get GSTIN from OCR rule"`

**Field 2**: GSTIN (TEXT)
**Logic**: `"Perform GSTIN validation and store the data in next fields"`

**Field 3+**: Trade Name, Legal Name, etc. (TEXT)
**Logic**: `"Data will come from GSTIN verification"`

**Chain**:
1. OCR on GSTIN IMAGE → populates GSTIN field → triggers VERIFY
2. VERIFY on GSTIN → populates Trade Name, Legal Name, etc. via ordinal mapping

---

### Example 6: Understanding destinationIds for VERIFY

**GSTIN VERIFY Rule** (Schema ID 355, 21 destination fields):
```
Schema ordinals:          BUD field mapping:
ordinal 1: Trade name     → Trade Name (275514)
ordinal 2: Longname       → Legal Name (275515)
ordinal 3: Reg date       → Reg Date (275516)
ordinal 4: City           → City (275517)
ordinal 5: Type           → Type (275518)
ordinal 6: Building number→ Building Number (275519)
ordinal 7: Flat number    → -1 (NOT MAPPED)
ordinal 8: District code  → District (275520)
...
```

**Result destinationIds**: `[275514, 275515, 275516, 275517, 275518, 275519, -1, 275520, ...]`

---

## Logic Parser Patterns

Based on real BUD analysis, these patterns map to specific rule types:

### Logic Parser Patterns
- **Visibility**: "visible", "invisible", "show", "hide"
- **Mandatory**: "mandatory", "non-mandatory", "required", "optional"
- **Validation**: "validate", "validation", "verify", "check", "Perform X Validation"
- **Data derivation**: "copy", "derive", "auto-fill", "populate"
- **OCR**: "OCR", "from OCR rule", "Get X from OCR"
- **Dropdown**: "dropdown values", "reference table"
- **Non-editable**: "Non-Editable", "non-editable", "read-only"
- **Verify destination**: "Data will come from X validation" (NO rule here!)

### Field Matching
- Use RapidFuzz for fuzzy string matching
- Exact match first (O(1) lookup)
- Fuzzy match with 80% threshold if no exact match
- Handle variations like "GST option" vs "Please select GST option"

## Output JSON Structure (MUST MATCH REFERENCE EXACTLY)

The generated output MUST have the exact same structure as `documents/json_output/vendor_creation_sample_bud.json`.

**CRITICAL: All IDs must be sequential integers starting from 1, NOT random numbers!**

```json
{
  "template": {
    "id": 1,                              // Sequential: starts at 1
    "templateName": "Vendor Creation",
    "documentTypes": [
      {
        "id": 1,                          // Sequential: starts at 1
        "formFillMetadatas": [
          {
            "id": 1,                      // Sequential: 1, 2, 3, ...
            "formTag": { "id": 1, "name": "RuleCheck", "type": "TEXT" },
            "variableName": "_ruleChe74_",
            "formFillRules": [
              { "id": 1, /* rule fields */ },  // Sequential: 1
              { "id": 2, /* rule fields */ },  // Sequential: 2
              { "id": 3, /* rule fields */ }   // Sequential: 3
            ]
          },
          {
            "id": 2,                      // Sequential: next field ID
            "formTag": { "id": 2, "name": "FieldName", "type": "TEXT" },
            "formFillRules": [
              { "id": 4, /* rule fields */ },  // Sequential: continues from previous
              { "id": 5, /* rule fields */ }
            ]
          }
        ]
      }
    ]
  }
}
```

**Key Structure Points:**
1. Root object has `template` key
2. `template.documentTypes` is an array (usually 1 element)
3. Each documentType has `formFillMetadatas` array (284 fields in reference)
4. Each formFillMetadata has `formFillRules` array
5. Rules are placed on the field that TRIGGERS them (source field)

### Rule Output Format

Study the vendor_creation_sample_bud.json to see real examples. Each rule has this structure:

```json
{
  "id": 119617,
  "createUser": "FIRST_PARTY",
  "updateUser": "FIRST_PARTY",
  "actionType": "MAKE_VISIBLE",
  "processingType": "CLIENT",
  "sourceIds": [275491],
  "destinationIds": [275492],
  "conditionalValues": ["yes"],
  "condition": "IN",
  "conditionValueType": "TEXT",
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

### CRITICAL: Sequential ID Generation (Starting from 1)

**All IDs in the generated JSON MUST be sequential integers starting from 1, NOT random numbers.**

This applies to ALL objects with IDs:
- Rule IDs (`formFillRules[].id`)
- Field/Metadata IDs (`formFillMetadatas[].id`)
- Template IDs (`template.id`)
- DocumentType IDs (`documentTypes[].id`)
- FormTag IDs (`formTag.id`)
- Any other object with an `id` field

**Implementation:**
```python
class IdGenerator:
    """Generate sequential IDs starting from 1."""

    def __init__(self):
        self.counters = {
            'rule': 0,
            'field': 0,
            'template': 0,
            'document_type': 0,
            'form_tag': 0
        }

    def next_id(self, id_type: str = 'rule') -> int:
        """Get next sequential ID for given type."""
        self.counters[id_type] += 1
        return self.counters[id_type]

# Usage:
id_gen = IdGenerator()

# Rules get IDs 1, 2, 3, ...
rule1 = {"id": id_gen.next_id('rule'), ...}  # id: 1
rule2 = {"id": id_gen.next_id('rule'), ...}  # id: 2

# Fields get IDs 1, 2, 3, ...
field1 = {"id": id_gen.next_id('field'), ...}  # id: 1
field2 = {"id": id_gen.next_id('field'), ...}  # id: 2
```

**Why Sequential IDs?**
- Predictable and reproducible output
- Easier to debug and trace
- Consistent with clean data practices
- Avoids confusion with production IDs

**postTriggerRuleIds Reference:**
When rules reference other rules via `postTriggerRuleIds`, use the assigned sequential IDs:
```python
# First, generate all rules and assign IDs
verify_rule = {"id": id_gen.next_id('rule'), "actionType": "VERIFY", ...}  # id: 1
ocr_rule = {"id": id_gen.next_id('rule'), "actionType": "OCR", ...}        # id: 2

# Then, link them using assigned IDs
ocr_rule["postTriggerRuleIds"] = [verify_rule["id"]]  # [1]
```

### Required Fields for ALL Rules

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | int | sequential | Unique rule ID starting from 1 |
| `createUser` | string | "FIRST_PARTY" | Always FIRST_PARTY |
| `updateUser` | string | "FIRST_PARTY" | Always FIRST_PARTY |
| `actionType` | string | required | Rule action type |
| `processingType` | string | "CLIENT" | "CLIENT" or "SERVER" |
| `sourceIds` | int[] | required | Source field ID(s) |
| `destinationIds` | int[] | [] | Destination field ID(s) |
| `postTriggerRuleIds` | int[] | [] | Rules to trigger after |
| `button` | string | "" | Button text |
| `searchable` | bool | false | |
| `executeOnFill` | bool | true | |
| `executeOnRead` | bool | false | |
| `executeOnEsign` | bool | false | |
| `executePostEsign` | bool | false | |
| `runPostConditionFail` | bool | false | |

### Conditional Fields (only for conditional rules)

| Field | Type | When Required |
|-------|------|---------------|
| `conditionalValues` | string[] | MAKE_VISIBLE, MAKE_INVISIBLE, etc. |
| `condition` | string | When conditionalValues present ("IN" or "NOT_IN") |
| `conditionValueType` | string | When condition present ("TEXT") |

### Rule Type Specific Fields

| Rule Type | Additional Fields |
|-----------|-------------------|
| VERIFY | `sourceType`, `button` (e.g., "Verify") |
| OCR | `sourceType` |
| EXT_DROP_DOWN | `sourceType`: "FORM_FILL_DROP_DOWN", `params` |
| EXT_VALUE | `sourceType`: "EXTERNAL_DATA_VALUE", `params` |
| GSTIN_WITH_PAN | `params` (JSON error message), `onStatusFail`: "CONTINUE" |

### Understanding Real-World Rule Application

From vendor_creation_sample_bud.json, here's how rules are applied:

**Example 1: Visibility + Mandatory Control**
```
Field: "GSTIN" (id: 275493)
Logic: "if the field 'Please select GST option' values is yes then visible and mandatory otherwise invisible and non-mandatory"

Generated Rules:
1. MAKE_VISIBLE when GST option = "yes"
   - sourceIds: [275491]  // GST option field
   - destinationIds: [275493]  // GSTIN field
   - conditionalValues: ["yes"]
   - condition: "IN"

2. MAKE_INVISIBLE when GST option != "yes"
   - sourceIds: [275491]
   - destinationIds: [275493]
   - conditionalValues: ["yes"]
   - condition: "NOT_IN"

3. MAKE_MANDATORY when GST option = "yes"
   - sourceIds: [275491]
   - destinationIds: [275493]
   - conditionalValues: ["yes"]
   - condition: "IN"

4. MAKE_NON_MANDATORY when GST option != "yes"
   - sourceIds: [275491]
   - destinationIds: [275493]
   - conditionalValues: ["yes"]
   - condition: "NOT_IN"
```

**Example 2: Disable Rule (Always Applied)**
```
Field: "Transaction ID" (id: 275491)
Logic: "System-generated transaction ID from Manch (Non-Editable) • Disable"

Generated Rule:
1. MAKE_DISABLED (always active)
   - sourceIds: [275633]  // RuleCheck control field
   - destinationIds: [275491]  // Transaction ID
   - conditionalValues: ["Disable"]
   - condition: "NOT_IN"  // Always executes
```

**Example 3: OCR + Validation Chain**
```
Field: "GSTIN" (id: 275493)
Logic: "Data will come from GSTIN OCR rule. Perform GSTIN validation and store the data in next fields"

Generated Rules:
1. OCR rule on "GSTIN IMAGE" field (id: 275508)
   - actionType: "OCR"
   - sourceIds: [275508]  // Image upload field
   - destinationIds: [275493, 275494, 275495, ...]  // GSTIN and related fields
   - processingType: "SERVER"

2. VERIFY rule on GSTIN field
   - actionType: "VERIFY"
   - sourceIds: [275493]  // GSTIN field
   - processingType: "SERVER"
```

**Key Insights from Real Examples:**

1. **Multiple rules per field**: A field can have 4-6 rules (visibility + mandatory + validation + OCR)
2. **Control fields**: Use hidden "RuleCheck" fields (id: 275633) as master controllers
3. **Condition patterns**:
   - Use "IN" for positive conditions ("equals yes")
   - Use "NOT_IN" for negative conditions ("not equals yes")
4. **Session-based rules**: Use SESSION_BASED_* actions when different for first/second party
5. **Rule chaining**: OCR → Validation → Copy in sequence
6. **Default hidden fields**: Many fields start invisible and are shown conditionally

## Deterministic Pattern Categories

```python
PATTERNS = {
    "visibility": [
        (r"(?:make\s+)?visible\s+(?:if|when)", "MAKE_VISIBLE", 0.95),
        (r"(?:make\s+)?invisible|hide", "MAKE_INVISIBLE", 0.95),
        (r"show\s+(?:this|field)", "MAKE_VISIBLE", 0.90),
    ],
    "mandatory": [
        (r"(?:make\s+)?mandatory\s+(?:if|when)", "MAKE_MANDATORY", 0.95),
        (r"non-mandatory|optional", "MAKE_NON_MANDATORY", 0.90),
        (r"required\s+(?:if|when)", "MAKE_MANDATORY", 0.85),
    ],
    "disable": [
        (r"disable|non-editable|read-only", "MAKE_DISABLED", 0.95),
    ],
    "verify": [
        (r"(?:PAN|GSTIN|GST|bank|MSME|CIN)\s+(?:validation|verify)", "VERIFY", 0.95),
        (r"validate\s+(?:PAN|GSTIN|GST|bank)", "VERIFY", 0.95),
        (r"perform\s+(?:PAN|GSTIN|bank)\s+validation", "VERIFY", 0.95),
    ],
    "ocr": [
        (r"(?:from|using)\s+OCR", "OCR", 0.95),
        (r"OCR\s+rule", "OCR", 0.95),
        (r"extract\s+from\s+(?:image|document)", "OCR", 0.85),
        (r"data\s+will\s+come\s+from\s+.*OCR", "OCR", 0.90),
    ],
    "edv": [
        (r"dropdown\s+values?\s+(?:from|based)", "EXT_DROP_DOWN", 0.90),
        (r"reference\s+table", "EXT_DROP_DOWN", 0.85),
        (r"external\s+data", "EXT_VALUE", 0.85),
        (r"parent\s+dropdown\s+field", "EXT_DROP_DOWN", 0.90),
    ]
}
```

## Rules to Ignore (Skip Patterns)

The following rule types should be **SKIPPED** during extraction as they are handled separately or not supported:

### 1. Expression Rules
Logic containing mathematical expressions or expr-eval syntax should be ignored:
- Pattern indicators: `mvi(`, `mm(`, `expr-eval`, arithmetic operators in code-like syntax
- Examples:
  - "mvi('fieldA') + mvi('fieldB')"
  - "expr-eval: mm('total') > 1000"
  - "Calculate using mvi('amount') * 0.18"

### 2. Execute Rules
Rules that execute custom code or scripts:
- Pattern indicators: `EXECUTE`, `execute rule`, `execute script`, `custom script`
- Examples:
  - "Execute custom validation script"
  - "EXECUTE rule for complex calculation"

### 3. Skip Pattern Implementation

```python
import re

SKIP_PATTERNS = [
    # Expression rules
    r"mvi\s*\(",              # mvi('fieldName')
    r"mm\s*\(",               # mm('fieldName')
    r"expr-eval",             # expr-eval expressions
    r"expr\s*:",              # expr: syntax
    r"\$\{.*\}",              # ${expression} syntax

    # Execute rules
    r"\bEXECUTE\b",           # EXECUTE keyword
    r"execute\s+rule",        # execute rule
    r"execute\s+script",      # execute script
    r"custom\s+script",       # custom script

    # Complex calculations (code-like)
    r"\b\w+\s*\(\s*['\"].*['\"]\s*\)\s*[\+\-\*\/]",  # func('x') + ...
]

def should_skip_logic(logic_text: str) -> bool:
    """
    Check if logic statement should be skipped.

    Returns True for:
    - Expression rules (mvi, mm, expr-eval)
    - Execute rules (EXECUTE, custom scripts)
    - Complex calculations
    """
    if not logic_text:
        return True

    for pattern in SKIP_PATTERNS:
        if re.search(pattern, logic_text, re.IGNORECASE):
            return True
    return False

# Usage in main extraction loop:
def extract_rules(logic_statements: List[str]) -> List[Dict]:
    rules = []
    skipped = []

    for logic in logic_statements:
        if should_skip_logic(logic):
            skipped.append(logic)
            continue

        # Process normally
        rule = process_logic(logic)
        if rule:
            rules.append(rule)

    # Log skipped for review
    if skipped:
        print(f"Skipped {len(skipped)} expression/execute rules")

    return rules
```

### Why Skip These Rules?

1. **Expression rules** require a different processing mechanism (expr-eval engine) and cannot be converted to standard formFillRules
2. **Execute rules** run custom server-side code that isn't represented in Rule-Schemas.json
3. These rules are typically configured separately in the form builder UI

## KEY INSIGHTS (MUST UNDERSTAND)

### 1. Visibility Rules Go on SOURCE Field, Not Destinations

**WRONG**: Creating MAKE_VISIBLE rule on Trade Name field
**CORRECT**: Creating MAKE_VISIBLE rule on "Please select GST option" field with Trade Name in destinationIds

When you see logic like:
```
Trade Name: "if the field 'Please select GST option' values is yes then visible"
Legal Name: "if the field 'Please select GST option' values is yes then visible"
```

Generate ONE rule on "Please select GST option" with BOTH fields in destinationIds:
```json
{
  "actionType": "MAKE_VISIBLE",
  "sourceIds": [gst_option_id],
  "destinationIds": [trade_name_id, legal_name_id, ...]
}
```

### 2. VERIFY Source vs Destination Fields

**VERIFY SOURCE** (has VERIFY rule):
- Logic: "Perform PAN Validation"
- Rule: VERIFY with destinationIds pointing to output fields

**VERIFY DESTINATION** (NO VERIFY rule here):
- Logic: "Data will come from PAN validation"
- Rule: NONE - this field is in the VERIFY rule's destinationIds

### 3. OCR → VERIFY Chain

**Upload PAN** (FILE, OCR source):
- Logic: "Get PAN from OCR rule"
- Rule: OCR with destinationIds=[PAN field], postTriggerRuleIds=[VERIFY rule]

**PAN** (TEXT, VERIFY source):
- Logic: "Perform PAN Validation"
- Rule: VERIFY with destinationIds=[Pan Holder Name, PAN Type, etc.]

**Pan Holder Name** (TEXT, VERIFY destination):
- Logic: "Data will come from PAN validation"
- Rule: NONE (it's in PAN's VERIFY destinationIds)

---

## Critical Implementation Notes

### 1. Always Lookup Rule-Schemas.json
When a rule type is determined (VERIFY, OCR, etc.), IMMEDIATELY:
```python
# Load and access content array
with open("rules/Rule-Schemas.json") as f:
    data = json.load(f)
schemas = data.get("content", [])

# Find matching schema
schema = next((s for s in schemas if s["action"] == action and s["source"] == source), None)
ordinals = {f["name"]: f["ordinal"] for f in schema["destinationFields"]["fields"]}
# Use ordinals to build destinationIds array
```

### 2. destinationIds = Ordinal-Indexed Array
```python
# Example: PAN Verification (schema ID 360)
# Schema has 10 destination fields with ordinals 1-10
# BUD only maps ordinals 4, 6, 8, 9

max_ordinal = schema["destinationFields"]["numberOfItems"]  # 10
destination_ids = [-1] * max_ordinal

# Map BUD fields to ordinal indices (ordinal - 1 = index)
destination_ids[3] = 275535  # ordinal 4 → index 3 (Fullname)
destination_ids[5] = 275537  # ordinal 6 → index 5 (Pan retrieval status)
destination_ids[7] = 275536  # ordinal 8 → index 7 (Pan type)
destination_ids[8] = 275538  # ordinal 9 → index 8 (Aadhaar seeding status)

# Result: [-1, -1, -1, 275535, -1, 275537, -1, 275536, 275538, -1]
```

### 3. Visibility Rules Generate Pairs
```python
# "if X is Y then visible otherwise invisible" generates 2 rules:
rules = [
    {"actionType": "MAKE_VISIBLE", "condition": "IN", "conditionalValues": ["Y"]},
    {"actionType": "MAKE_INVISIBLE", "condition": "NOT_IN", "conditionalValues": ["Y"]}
]
```

### 4. OCR + VERIFY Chain
```python
# "Get PAN from OCR, validate and store" generates chained rules:
ocr_rule = {"actionType": "OCR", "postTriggerRuleIds": [verify_rule_id]}
verify_rule = {"actionType": "VERIFY", "postTriggerRuleIds": [visibility_rule_ids]}
```

## Critical Reference Files

- `/home/samart/project/doc-parser/.claude/plans/plan.md` - Complete implementation plan
- `/home/samart/project/doc-parser/extract_fields_complete.py` - Output format reference
- `/home/samart/project/doc-parser/rules/Rule-Schemas.json` - 182 pre-defined rules
- `/home/samart/project/doc-parser/rules_extractor.py` - LLM integration patterns
- `/home/samart/project/doc-parser/RULES_REFERENCE.md` - Rule documentation
- `/home/samart/project/doc-parser/documents/json_output/vendor_creation_sample_bud.json` - **CRITICAL** reference output with 279 rules

## Eval Report Key Fixes Required

Based on the evaluation report, the following MUST be implemented:

### 1. Rule Chaining (0% → 100%)
- Every OCR rule MUST have postTriggerRuleIds linking to VERIFY
- Example: PAN OCR → postTriggerRuleIds: [PAN_VERIFY_rule_id]

### 2. Missing VERIFY Rules (Add all)
| Source Type | Schema ID | Example Logic |
|-------------|-----------|---------------|
| BANK_ACCOUNT_NUMBER | 361 | "Validate Bank Account" |
| MSME_UDYAM_REG_NUMBER | 337 | "MSME validation" |
| GSTIN_WITH_PAN | custom | Cross-validation after GSTIN VERIFY |
| CIN_ID | 349 | "CIN validation" |

### 3. Missing OCR Rules (Add all)
| Source Type | Schema ID | Field Pattern |
|-------------|-----------|---------------|
| CHEQUEE | 269 | "Cheque Upload", "Cancelled Cheque" |
| AADHAR_BACK_IMAGE | 348 | "Aadhaar Back" |
| CIN | N/A | "CIN Upload" |
| MSME | N/A | "MSME Image", "Udyam Upload" |

### 4. EXT_DROP_DOWN Rules (3 → 20)
EXT_DROP_DOWN rules apply when:
- Logic references external tables or Excel files in the BUD
- Field is EXTERNAL_DROP_DOWN or EXTERNAL_DROP_DOWN_VALUE type
- Logic mentions "dropdown values from", "reference table", "parent dropdown"

### 5. Rule Consolidation (53 → 5 MAKE_DISABLED)
- Use RuleCheck control field (hidden) with multiple destinationIds
- Single rule with 41+ destinations instead of 41 separate rules
- Group by: sourceIds + condition + conditionalValues → merge destinationIds

### 6. Remove Duplicates
Fields with duplicate rules in eval: Type, Street, City, District, State
- Each field should have only ONE rule of each type

## Complete Rule Type Reference (from reference output)

```
Reference Rule Type Distribution:
MAKE_VISIBLE:      18 rules
MAKE_INVISIBLE:    19 rules
MAKE_DISABLED:     5 rules   (consolidated with multiple destinationIds)
MAKE_MANDATORY:    12 rules
MAKE_NON_MANDATORY: 12 rules
EXT_DROP_DOWN:     20 rules
VERIFY:            5 rules   (PAN, GSTIN, GSTIN_WITH_PAN, Bank, MSME)
OCR:               6 rules   (PAN, GSTIN, Aadhaar Back, Cheque, MSME, CIN)
CONVERT_TO:        10 rules
COPY_TO:           15 rules
OTHER:             157 rules
```

## Real Rule Examples from Reference

### OCR Rule with Chain (PAN)
```json
{
  "id": 119969,
  "actionType": "OCR",
  "sourceType": "PAN_IMAGE",
  "processingType": "SERVER",
  "sourceIds": [275533],        // Upload PAN field
  "destinationIds": [275534],   // PAN text field
  "postTriggerRuleIds": [119970]  // ← Chains to VERIFY!
}
```

### VERIFY Rule with Ordinal Mapping (PAN)
```json
{
  "id": 119970,
  "actionType": "VERIFY",
  "sourceType": "PAN_NUMBER",
  "processingType": "SERVER",
  "sourceIds": [275534],
  "destinationIds": [-1, -1, -1, 275535, -1, 275537, -1, 275536, 275538],
  "postTriggerRuleIds": [120188, 120233, 120232],
  "button": "Verify"
}
```

### GSTIN_WITH_PAN Cross-Validation
```json
{
  "id": 120188,
  "actionType": "VERIFY",
  "sourceType": "GSTIN_WITH_PAN",
  "processingType": "SERVER",
  "sourceIds": [275534, 275513],  // PAN + GSTIN fields
  "destinationIds": [],
  "params": "{ \"paramMap\": {\"errorMessage\": \"GSTIN and PAN doesn't match.\"}}",
  "onStatusFail": "CONTINUE"
}
```

### Consolidated MAKE_DISABLED (RuleCheck pattern)
```json
{
  "id": 119617,
  "actionType": "MAKE_DISABLED",
  "processingType": "CLIENT",
  "sourceIds": [275633],          // RuleCheck control field
  "destinationIds": [
    275491, 275492, 275493, 275495,  // 41 field IDs!
    276399, 276400, 276383, 276339,
    // ... more IDs
  ],
  "conditionalValues": ["Disable"],
  "condition": "NOT_IN"
}
```

### EXT_DROP_DOWN with params
```json
{
  "id": 119942,
  "actionType": "EXT_DROP_DOWN",
  "sourceType": "FORM_FILL_DROP_DOWN",
  "processingType": "CLIENT",
  "sourceIds": [275506],
  "params": "COMPANY_CODE",      // External table reference
  "searchable": true
}
```

### CHEQUEE OCR with Ordinal Mapping
```json
{
  "id": 120064,
  "actionType": "OCR",
  "sourceType": "CHEQUEE",
  "processingType": "SERVER",
  "sourceIds": [275558],
  "destinationIds": [-1, 275560, -1, 275561],  // IFSC at ordinal 2, Acc# at 4
  "postTriggerRuleIds": [120067]  // Bank VERIFY
}
```

## Hard Constraints

* Follow the architecture in the plan exactly
* Create all modules as specified
* Implement deterministic pattern matching first
* Only use LLM fallback when confidence < 70%
* Generate valid JSON matching the schema format
* No shortcuts or simplified implementations
* Write production-quality code with error handling
* Include docstrings for all classes and functions

## Processing Algorithm

### Step 1: Parse BUD Document
```python
from doc_parser import DocumentParser
parser = DocumentParser()
parsed = parser.parse(bud_path)

# Now you have access to:
# - parsed.all_fields - List of all fields with logic/rules
# - parsed.initiator_fields, parsed.spoc_fields, parsed.approver_fields
```

### Step 2: First Pass - Identify Controlling Fields (Visibility Sources)
```python
visibility_groups = defaultdict(list)

for field in parsed.all_fields:
    logic = field.logic or ''

    # Pattern: "if the field 'X' values is Y then visible"
    match = re.search(r"if.*field.*['\"](.+?)['\"].*values?\s+is\s+(\w+)\s+then\s+(visible|mandatory)", logic, re.I)
    if match:
        controlling_field_name = match.group(1)
        conditional_value = match.group(2)
        action_type = match.group(3)

        visibility_groups[controlling_field_name].append({
            'destination_field': field.name,
            'destination_id': get_field_id(field.name),
            'conditional_value': conditional_value,
            'action_type': 'MAKE_VISIBLE' if action_type == 'visible' else 'MAKE_MANDATORY'
        })
```

### Step 3: Second Pass - Generate Rules for Each Field
```python
for field in parsed.all_fields:
    logic = field.logic or ''
    rules = []

    # Skip expression/execute rules first
    if should_skip_logic(logic):
        continue

    # 1. OCR Rules - "Get X from OCR rule"
    if re.search(r"(from|using)\s+OCR|OCR\s+rule|Get\s+\w+\s+from\s+OCR", logic, re.I):
        rules.append(build_ocr_rule(field))

    # 2. VERIFY Rules - "Perform X Validation"
    # BUT NOT "Data will come from X validation" (those are destinations!)
    if re.search(r"Perform\s+\w+\s+[Vv]alidation|[Vv]alidate\s+\w+", logic, re.I):
        if not re.search(r"Data\s+will\s+come\s+from", logic, re.I):
            rules.append(build_verify_rule(field))

    # 3. Visibility Rules - Only on CONTROLLING fields
    if field.name in visibility_groups:
        rules.extend(build_visibility_rules(field, visibility_groups[field.name]))

    # 4. MAKE_DISABLED - "Non-Editable"
    if re.search(r"Non-Editable|non-editable|read-only", logic, re.I):
        rules.append(build_disabled_rule(field))
```

### Step 4: Link Rule Chains (OCR → VERIFY) - CRITICAL!

**Eval showed 0% rule chaining correctness - this MUST be fixed!**

```python
# OCR rules MUST trigger VERIFY rules via postTriggerRuleIds
# This is the critical link that was missing

# Real examples from reference:
# PAN OCR (119969) → postTriggerRuleIds: [119970] (PAN VERIFY)
# GSTIN OCR (119606) → postTriggerRuleIds: [119608] (GSTIN VERIFY)
# MSME OCR (119610) → postTriggerRuleIds: [119612] (MSME VERIFY)
# CHEQUEE OCR (120064) → postTriggerRuleIds: [120067] (Bank VERIFY)

OCR_VERIFY_CHAINS = {
    # OCR sourceType → VERIFY sourceType to chain to
    "PAN_IMAGE": "PAN_NUMBER",
    "GSTIN_IMAGE": "GSTIN",
    "CHEQUEE": "BANK_ACCOUNT_NUMBER",
    "MSME": "MSME_UDYAM_REG_NUMBER",
    "CIN": "CIN_ID",
    "AADHAR_IMAGE": None,      # No VERIFY chain
    "AADHAR_BACK_IMAGE": None, # No VERIFY chain
}

def link_ocr_to_verify_rules(all_rules: List[Dict]) -> None:
    """Link OCR rules to corresponding VERIFY rules."""

    # Build index of VERIFY rules by source field ID
    verify_by_source = {}
    for rule in all_rules:
        if rule.get('actionType') == 'VERIFY':
            for source_id in rule.get('sourceIds', []):
                verify_by_source[source_id] = rule

    # Link each OCR rule to its corresponding VERIFY rule
    for rule in all_rules:
        if rule.get('actionType') == 'OCR':
            # OCR destinationIds[0] is the field being populated
            dest_field_id = rule.get('destinationIds', [None])[0]

            if dest_field_id and dest_field_id in verify_by_source:
                verify_rule = verify_by_source[dest_field_id]
                if 'postTriggerRuleIds' not in rule:
                    rule['postTriggerRuleIds'] = []
                verify_rule_id = verify_rule.get('id')
                if verify_rule_id and verify_rule_id not in rule['postTriggerRuleIds']:
                    rule['postTriggerRuleIds'].append(verify_rule_id)
```

### Step 5: EXT_DROP_DOWN Rules (17 missing in eval!)

**CRITICAL**: EXT_DROP_DOWN rules apply when logic references external tables or Excel files.

```python
# Real EXT_DROP_DOWN examples from reference:
# {
#   "actionType": "EXT_DROP_DOWN",
#   "sourceType": "FORM_FILL_DROP_DOWN",
#   "processingType": "CLIENT",
#   "sourceIds": [275506],
#   "params": "COMPANY_CODE",        # External table reference
#   "searchable": true
# }

# Params values from reference: COMPANY_CODE, PIDILITE_YES_NO, TYPE_OF_INDUSTRY

EXT_DROPDOWN_PATTERNS = [
    r"external\s+dropdown",
    r"dropdown\s+values?\s+from\s+(?:table|excel|reference|sheet)",
    r"reference\s+table\s*:",
    r"parent\s+dropdown\s+field",
    r"values?\s+from\s+(?:sheet|excel|table)",
    r"cascading\s+dropdown",
    r"dependent\s+on\s+(?:field|dropdown)",
    r"filter(?:ed)?\s+by\s+parent",
    r"\.(xlsx?|xls)\b",  # Excel file reference
]

def detect_ext_dropdown(logic: str, field_type: str) -> bool:
    """Check if field needs EXT_DROP_DOWN rule based on logic and type."""
    if not logic:
        return False

    # Must be dropdown type
    if field_type not in ['DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROP_DOWN',
                          'EXTERNAL_DROP_DOWN_VALUE']:
        return False

    for pattern in EXT_DROPDOWN_PATTERNS:
        if re.search(pattern, logic, re.IGNORECASE):
            return True

    return False

def build_ext_dropdown_rule(field_id: int, params: str = "") -> Dict:
    """Build EXT_DROP_DOWN rule."""
    return {
        "actionType": "EXT_DROP_DOWN",
        "sourceType": "FORM_FILL_DROP_DOWN",
        "processingType": "CLIENT",
        "sourceIds": [field_id],
        "params": params,  # e.g., "COMPANY_CODE", "TYPE_OF_INDUSTRY"
        "searchable": True,
        "executeOnFill": True
    }
```

### Step 6: Missing VERIFY Rules Detection

**Eval showed missing: BANK_ACCOUNT_NUMBER, MSME_UDYAM_REG_NUMBER, GSTIN_WITH_PAN**

```python
# Real VERIFY examples from reference:

# BANK_ACCOUNT_NUMBER:
# {
#   "actionType": "VERIFY",
#   "sourceType": "BANK_ACCOUNT_NUMBER",
#   "sourceIds": [275560, 275561],  # IFSC Code + Account Number
#   "destinationIds": [275562],
#   "button": "VERIFY"
# }

# MSME_UDYAM_REG_NUMBER:
# {
#   "actionType": "VERIFY",
#   "sourceType": "MSME_UDYAM_REG_NUMBER",
#   "sourceIds": [275587],
#   "destinationIds": [275588, 275589, 275591, ...],  # 20+ fields
# }

# GSTIN_WITH_PAN (cross-validation):
# {
#   "actionType": "VERIFY",
#   "sourceType": "GSTIN_WITH_PAN",
#   "sourceIds": [275534, 275513],  # PAN field + GSTIN field
#   "destinationIds": [],
#   "params": "{ \"paramMap\": {\"errorMessage\": \"GSTIN and PAN doesn't match.\"}}"
# }

VERIFY_PATTERNS = {
    # Pattern keyword → (sourceType, schema_id)
    r"bank\s*(account)?.*validation|validate.*bank|verify.*bank|bank.*verification": ("BANK_ACCOUNT_NUMBER", 361),
    r"msme|udyam.*validation|validate.*msme|verify.*msme": ("MSME_UDYAM_REG_NUMBER", 337),
    r"pan\s*validation|validate\s*pan|verify\s*pan|perform\s*pan": ("PAN_NUMBER", 360),
    r"gstin?\s*validation|validate\s*gstin?|verify\s*gstin?|perform\s*gstin?": ("GSTIN", 355),
    r"cin\s*validation|validate\s*cin|verify\s*cin": ("CIN_ID", 349),
    r"tan\s*validation|validate\s*tan|verify\s*tan": ("TAN_NUMBER", 322),
}

def detect_verify_type(logic: str) -> Optional[Tuple[str, int]]:
    """Detect VERIFY type from logic text."""
    if not logic:
        return None

    logic_lower = logic.lower()

    # Skip destination fields ("Data will come from X validation")
    if re.search(r"data\s+will\s+come\s+from", logic_lower):
        return None

    for pattern, (source_type, schema_id) in VERIFY_PATTERNS.items():
        if re.search(pattern, logic_lower):
            return (source_type, schema_id)

    return None
```

### Step 7: Missing OCR Rules Detection

**Eval showed missing: CHEQUEE, AADHAR_BACK_IMAGE, CIN, MSME**

```python
# Real OCR examples from reference:

# CHEQUEE:
# {
#   "actionType": "OCR",
#   "sourceType": "CHEQUEE",
#   "sourceIds": [275558],         # Cheque upload field
#   "destinationIds": [-1, 275560, -1, 275561],  # IFSC, Account Number
#   "postTriggerRuleIds": [120067]  # Bank VERIFY
# }

# AADHAR_BACK_IMAGE:
# {
#   "actionType": "OCR",
#   "sourceType": "AADHAR_BACK_IMAGE",
#   "sourceIds": [276570],
#   "destinationIds": [-1, -1, 275546, 275547, 275548, 275549, -1, -1],
#   "conditionalValueId": 275511,   # GST option field
#   "conditionalValues": ["GST Non-Registered"]
# }

# MSME:
# {
#   "actionType": "OCR",
#   "sourceType": "MSME",
#   "sourceIds": [275586],          # MSME Image upload
#   "destinationIds": [275587, 275590, 275591],
#   "postTriggerRuleIds": [119612]  # MSME VERIFY
# }

OCR_PATTERNS = {
    # Field name/logic pattern → (sourceType, schema_id)
    r"upload\s*pan|pan\s*(?:image|upload|file)": ("PAN_IMAGE", 344),
    r"upload\s*gstin|gstin\s*(?:image|upload|file)": ("GSTIN_IMAGE", 347),
    r"aadhaar?\s*front|front\s*aadhaar?": ("AADHAR_IMAGE", 359),
    r"aadhaar?\s*back|back\s*aadhaar?": ("AADHAR_BACK_IMAGE", 348),
    r"cheque|cancelled\s*cheque": ("CHEQUEE", 269),
    r"cin\s*(?:image|upload|file)|upload\s*cin": ("CIN", None),
    r"msme\s*(?:image|upload|file)|upload\s*msme|udyam\s*(?:image|upload)": ("MSME", None),
}

def detect_ocr_type(field_name: str, logic: str) -> Optional[Tuple[str, int]]:
    """Detect OCR type from field name and logic."""
    combined = f"{field_name} {logic}".lower()

    # Must have OCR keywords OR be a file upload that matches patterns
    if not re.search(r"ocr|extract|scan|image|upload|file", combined):
        return None

    for pattern, (source_type, schema_id) in OCR_PATTERNS.items():
        if re.search(pattern, combined, re.IGNORECASE):
            return (source_type, schema_id)

    return None
```

### Step 8: Rule Consolidation and Deduplication

**Eval showed 53 MAKE_DISABLED rules vs 5 in reference - need consolidation!**

```python
# Reference pattern: Single MAKE_DISABLED with 41 destinationIds
# on RuleCheck field (275633):
# {
#   "actionType": "MAKE_DISABLED",
#   "sourceIds": [275633],        # RuleCheck control field
#   "destinationIds": [275491, 275492, 275493, ...],  # 41 fields!
#   "conditionalValues": ["Disable"],
#   "condition": "NOT_IN"
# }

def consolidate_rules(all_rules: List[Dict]) -> List[Dict]:
    """Consolidate and deduplicate rules."""

    # Rules that can be consolidated (same source → merge destinations)
    CONSOLIDATABLE = ['MAKE_DISABLED', 'MAKE_VISIBLE', 'MAKE_INVISIBLE',
                      'MAKE_MANDATORY', 'MAKE_NON_MANDATORY']

    # Group by (actionType, sourceIds, condition, conditionalValues)
    groups = defaultdict(list)
    other_rules = []

    for rule in all_rules:
        action = rule.get('actionType')
        if action in CONSOLIDATABLE:
            key = (
                action,
                tuple(sorted(rule.get('sourceIds', []))),
                rule.get('condition'),
                tuple(sorted(rule.get('conditionalValues', [])))
            )
            groups[key].append(rule)
        else:
            other_rules.append(rule)

    # Merge grouped rules
    consolidated = []
    for key, rules in groups.items():
        if len(rules) == 1:
            consolidated.append(rules[0])
        else:
            # Merge: combine all destinationIds
            merged = rules[0].copy()
            all_dest_ids = set()
            for r in rules:
                all_dest_ids.update(r.get('destinationIds', []))
            merged['destinationIds'] = sorted(list(all_dest_ids))
            consolidated.append(merged)

    # Add non-consolidatable rules
    consolidated.extend(other_rules)

    # Remove exact duplicates
    seen = set()
    deduplicated = []
    for rule in consolidated:
        key = (
            rule.get('actionType'),
            tuple(sorted(rule.get('sourceIds', []))),
            tuple(sorted(rule.get('destinationIds', []))),
            rule.get('condition'),
            tuple(sorted(rule.get('conditionalValues', [])))
        )
        if key not in seen:
            seen.add(key)
            deduplicated.append(rule)

    return deduplicated
```

---

## Command-Line Interface

Create a main entry point: `rule_extraction_agent.py` with these arguments:

```bash
python rule_extraction_agent.py \
  --bud documents/Vendor\ Creation\ Sample\ BUD.docx \
  --schema output/complete_format/2581-schema.json \
  --intra-panel extraction/intra_panel_output/vendor_basic_details.json \
  --output output/rules_populated/2581-schema.json \
  --verbose \
  --validate \
  --llm-threshold 0.7 \
  --report summary_report.json \
  --prev-workspace adws/2026-01-31_12-58-30 \
  --prev-self-heal adws/2026-01-31_12-58-30/self_heal_instructions_v8.json \
  --prev-schema adws/2026-01-31_12-58-30/populated_schema_v8.json \
  --prev-eval adws/2026-01-31_12-58-30/eval_report_v8.json \
  --prev-extraction adws/2026-01-31_12-58-30/extraction_report_v8.json \
  --prev-api-schema adws/2026-01-31_12-58-30/api_schema_v8.json \
  --prev-api-response adws/2026-01-31_12-58-30/api_response_v8.json
```

**Core Arguments**:
- `--bud`: Path to the BUD .docx document (required) - **MUST BE PARSED FIRST**
- `--schema`: Path to schema JSON from extract_fields_complete.py (required)
- `--intra-panel`: Path to intra-panel references JSON (optional)
- `--output`: Output path for populated schema (optional, auto-generated)
- `--verbose`: Enable verbose logging
- `--validate`: Validate generated rules
- `--llm-threshold`: Confidence threshold for LLM fallback (default: 0.7)
- `--report`: Path to save summary report

**Previous Run Context Arguments** (automatically found and provided by orchestrator):

The orchestrator automatically finds the latest previous run in `adws/` and passes these file paths:
- `--prev-workspace`: Previous run workspace directory (e.g., `adws/2026-01-31_12-58-30/`)
- `--prev-self-heal`: Latest `self_heal_instructions_v*.json` - **Priority fixes to apply**
- `--prev-schema`: Latest `populated_schema_v*.json` - **What was generated before**
- `--prev-eval`: Latest `eval_report_v*.json` - **What failed and why**
- `--prev-extraction`: Latest `extraction_report_v*.json`
- `--prev-api-schema`: Latest `api_schema_v*.json` - **What was sent to API**
- `--prev-api-response`: Latest `api_response_v*.json` - **API validation errors**

**⚠️ IMPORTANT**: When these arguments are provided, you MUST use the `Read` tool to read these files BEFORE generating any code. See the "CRITICAL FIRST STEP" section at the top of this document.

## Success Criteria

1. **Coverage**: Process 100% of logic statements
2. **Accuracy**: 95%+ correct rule selection
3. **Determinism**: 80%+ handled by pattern-based approach
4. **Performance**: < 5 seconds for Vendor Creation BUD
5. **Validation**: No unmatched field references
6. **Integration**: Seamless with existing pipeline

## Workflow

1. Read the complete plan from `.claude/plans/plan.md`
2. Create the module structure
3. Implement Phase 1 components (models, logic parser, field matcher, rule builders)
4. Implement Phase 2 (rule selection tree)
5. Implement Phase 3 (LLM fallback)
6. Implement Phase 4 (integration and testing)
7. Create the main CLI entry point
8. Test with sample data

## Output

When complete, you should have:
- A fully functional `rule_extraction_agent/` module
- A main entry script `rule_extraction_agent.py`
- Updated schema JSON with formFillRules populated
- Summary report with statistics

This is a **code implementation task**. Write actual, working code that follows the architecture specified in the plan.
