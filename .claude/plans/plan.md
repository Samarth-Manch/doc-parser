# Rule Extraction Coding Agent Implementation Plan

## Executive Summary

Create a **rule extraction agent** (`rule_extraction_agent.py`) that automatically extracts rules from BUD logic/rules sections and populates `formFillRules` arrays in the JSON schema. The system uses a **hybrid approach**: deterministic pattern-based extraction for common cases with LLM fallback for complex logic statements.

**Target**: 100% accuracy on Vendor Creation Sample BUD (330+ logic statements)

## Architecture Overview

```
BUD Document → Parse with doc_parser → Extract Logic → Rule Selection → Field Matching → Rule Generation → Output
      ↓                  ↓                   ↓                ↓               ↓                ↓              ↓
   .docx           DocumentParser      field.logic     Decision Tree    Fuzzy Match     Build JSON    Populated
                   field.rules         field.rules     + LLM Fallback   Field IDs       Rules         Schema
```

## Output JSON Structure (MUST MATCH REFERENCE)

The generated output MUST match the exact structure of `documents/json_output/vendor_creation_sample_bud.json`.

**CRITICAL: All IDs must be sequential integers starting from 1, NOT random numbers!**

```json
{
  "template": {
    "id": 1,                              // Sequential: always 1 for template
    "templateName": "Vendor Creation",
    "key": "TMPTS00001",
    "companyCode": "pidilite",
    "templateType": "DUAL",
    "documentTypes": [
      {
        "id": 1,                          // Sequential: starts at 1
        "createUser": "FIRST_PARTY",
        "updateUser": "FIRST_PARTY",
        "documentType": "Vendor Creation",
        "displayName": "Vendor Creation",
        "partyType": "SECOND_PARTY",
        "formFillMetadatas": [
          {
            "id": 1,                      // Sequential: 1, 2, 3, ...
            "formTag": {
              "id": 1,                    // Sequential: 1, 2, 3, ...
              "name": "RuleCheck",
              "type": "TEXT"
            },
            "variableName": "_ruleChe74_",
            "formFillRules": [
              {
                "id": 1,                  // Sequential: 1 (first rule)
                "createUser": "FIRST_PARTY",
                "updateUser": "FIRST_PARTY",
                "actionType": "MAKE_DISABLED",
                "processingType": "CLIENT",
                "sourceIds": [1],         // References field ID 1
                "destinationIds": [2, 3, 4],  // References field IDs
                "conditionalValues": ["Disable"],
                "condition": "NOT_IN",
                "conditionValueType": "TEXT",
                "postTriggerRuleIds": [],
                "button": "",
                "searchable": false,
                "executeOnFill": true,
                "executeOnRead": false,
                "executeOnEsign": false,
                "executePostEsign": false,
                "runPostConditionFail": false
              },
              {
                "id": 2,                  // Sequential: 2 (second rule)
                "actionType": "MAKE_VISIBLE",
                // ... other fields
              }
            ]
          },
          {
            "id": 2,                      // Sequential: next field
            "formTag": { "id": 2, "name": "FieldName", "type": "TEXT" },
            "formFillRules": [
              { "id": 3, /* ... */ },     // Sequential: continues
              { "id": 4, /* ... */ }
            ]
          }
        ]
      }
    ]
  }
}
```

### CRITICAL: Sequential ID Generation (Starting from 1)

**All IDs in the generated JSON MUST be sequential integers starting from 1, NOT random numbers.**

This applies to ALL objects with IDs:
- Rule IDs (`formFillRules[].id`) → 1, 2, 3, 4, ...
- Field/Metadata IDs (`formFillMetadatas[].id`) → 1, 2, 3, 4, ...
- Template IDs (`template.id`) → 1
- DocumentType IDs (`documentTypes[].id`) → 1, 2, ...
- FormTag IDs (`formTag.id`) → 1, 2, 3, ...
- Any other object with an `id` field

**ID Generator Implementation:**
```python
class IdGenerator:
    """Generate sequential IDs starting from 1 for each object type."""

    def __init__(self):
        self.counters = {}

    def next_id(self, id_type: str = 'rule') -> int:
        """Get next sequential ID for given type."""
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

    def reset(self, id_type: str = None):
        """Reset counter(s) to 0."""
        if id_type:
            self.counters[id_type] = 0
        else:
            self.counters = {}

# Global ID generator instance
id_generator = IdGenerator()

# Usage in rule creation:
def create_rule(action_type: str, source_ids: list, ...) -> dict:
    return {
        "id": id_generator.next_id('rule'),  # Sequential: 1, 2, 3, ...
        "actionType": action_type,
        "sourceIds": source_ids,
        ...
    }
```

**Important for Rule Chaining:**
When rules need to reference other rules via `postTriggerRuleIds`:
1. First create all rules and assign sequential IDs
2. Then build the chain references using the assigned IDs

```python
# Step 1: Create rules with sequential IDs
rules = []
verify_rule = {"id": id_generator.next_id('rule'), "actionType": "VERIFY", ...}  # id: 1
ocr_rule = {"id": id_generator.next_id('rule'), "actionType": "OCR", ...}        # id: 2
rules.extend([verify_rule, ocr_rule])

# Step 2: Link OCR to VERIFY using assigned IDs
ocr_rule["postTriggerRuleIds"] = [verify_rule["id"]]  # [1]
```

### formFillRule Required Fields

Every generated rule MUST have these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | int | Yes | Sequential rule ID starting from 1 |
| `createUser` | string | Yes | "FIRST_PARTY" |
| `updateUser` | string | Yes | "FIRST_PARTY" |
| `actionType` | string | Yes | e.g., "MAKE_VISIBLE", "VERIFY", "OCR" |
| `processingType` | string | Yes | "CLIENT" or "SERVER" |
| `sourceIds` | int[] | Yes | Source field ID(s) |
| `destinationIds` | int[] | Yes | Destination field ID(s), use -1 for unused ordinals |
| `conditionalValues` | string[] | Conditional | Values to match |
| `condition` | string | Conditional | "IN" or "NOT_IN" |
| `conditionValueType` | string | Conditional | "TEXT" |
| `postTriggerRuleIds` | int[] | Yes | Rule IDs to trigger after this rule |
| `button` | string | Yes | Button text or "" |
| `searchable` | bool | Yes | Default false |
| `executeOnFill` | bool | Yes | Default true |
| `executeOnRead` | bool | Yes | Default false |
| `executeOnEsign` | bool | Yes | Default false |
| `executePostEsign` | bool | Yes | Default false |
| `runPostConditionFail` | bool | Yes | Default false |

### Additional Fields for Specific Rule Types

**VERIFY/OCR Rules:**
- `sourceType`: string (e.g., "PAN_NUMBER", "PAN_IMAGE")

**EXT_DROP_DOWN/EXT_VALUE Rules:**
- `sourceType`: "FORM_FILL_DROP_DOWN" or "EXTERNAL_DATA_VALUE"
- `params`: string (e.g., "COMPANY_CODE")

**Cross-validation Rules (GSTIN_WITH_PAN):**
- `params`: JSON string with error message
- `onStatusFail`: "CONTINUE"

## CRITICAL: Parse BUD Document First

**Before any rule extraction, the BUD document MUST be parsed using doc_parser:**

```python
from doc_parser import DocumentParser

parser = DocumentParser()
parsed = parser.parse("documents/Vendor Creation Sample BUD.docx")

# Access fields with their natural language logic
for field in parsed.all_fields:
    print(f"Field: {field.name}")
    print(f"Type: {field.field_type}")
    print(f"Logic: {field.logic}")  # <-- THIS IS THE NATURAL LANGUAGE LOGIC
    print(f"Rules: {field.rules}")  # <-- ADDITIONAL RULES TEXT
```

## Natural Language Logic to Rule Mapping Examples

These examples show the ACTUAL logic from the BUD and the corresponding rules that should be generated.

### Example 1: OCR Rule (Upload PAN → PAN)

**BUD Field**: Upload PAN (FILE type)
**Logic from BUD**: "File size should be up to 15Mb, Get PAN from OCR rule"

**Generated Rule** (placed on Upload PAN field):
```json
{
  "actionType": "OCR",
  "sourceType": "PAN_IMAGE",
  "processingType": "SERVER",
  "sourceIds": [275533],           // Upload PAN field ID
  "destinationIds": [275534],      // PAN text field ID
  "postTriggerRuleIds": [119970],  // Links to VERIFY rule on PAN field
  "executeOnFill": true
}
```

**Key Pattern**: "Get X from OCR rule" or "OCR rule" → Generate OCR rule

---

### Example 2: VERIFY Rule (PAN Validation)

**BUD Field**: PAN (TEXT type)
**Logic from BUD**: "Perform PAN Validation, It should be upper case field."

**Generated Rules** (placed on PAN field):
```json
[
  {
    "actionType": "CONVERT_TO",
    "sourceType": "UPPER_CASE",
    "sourceIds": [275534],
    "destinationIds": []
  },
  {
    "actionType": "VERIFY",
    "sourceType": "PAN_NUMBER",
    "processingType": "SERVER",
    "sourceIds": [275534],                    // PAN field ID
    "destinationIds": [-1, -1, -1, 275535, -1, 275537, -1, 275536, 275538, -1],
    // ordinal 4 (Fullname) → Pan Holder Name (275535)
    // ordinal 6 (Pan retrieval status) → PAN Status (275537)
    // ordinal 8 (Pan type) → PAN Type (275536)
    // ordinal 9 (Aadhaar seeding status) → Aadhaar PAN List Status (275538)
    "postTriggerRuleIds": [120188, 120233, 120232],
    "button": "VERIFY",
    "executeOnFill": true
  }
]
```

**Key Pattern**: "Perform X Validation" or "Validate X" → Generate VERIFY rule with ordinal-mapped destinationIds

---

### Example 3: VERIFY Destination Fields (Non-Editable)

**BUD Field**: Pan Holder Name (TEXT type)
**Logic from BUD**: "Data will come from PAN validation. Non-Editable"

**Generated Rule**: NONE on this field!
- This field is a DESTINATION of the PAN VERIFY rule
- The VERIFY rule is placed on the SOURCE field (PAN), not here
- Only generate MAKE_DISABLED if explicitly stated

**Key Insight**: "Data will come from X validation" means this field is a VERIFY DESTINATION, NOT a source

---

### Example 4: Visibility Rules (Multiple Destinations)

**BUD Field**: Please select GST option (DROPDOWN type)
**Logic**: Controls visibility of multiple fields

**BUD Fields Controlled** (each has logic like):
- GSTIN IMAGE: "if the field 'Please select GST option' values is yes then visible..."
- GSTIN: "if the field 'Please select GST option' values is yes then visible..."
- Trade Name: "if the field 'Please select GST option' values is yes then visible..."

**Generated Rules** (placed on "Please select GST option" field, NOT on each destination):
```json
[
  {
    "actionType": "MAKE_VISIBLE",
    "processingType": "CLIENT",
    "sourceIds": [275511],                    // GST option field ID
    "destinationIds": [275512, 275513, 275514, 275515, 275516],  // Multiple fields
    // GSTIN IMAGE, GSTIN, Trade Name, Legal Name, Reg Date
    "conditionalValues": ["GST Registered"],
    "condition": "IN",
    "executeOnFill": true
  },
  {
    "actionType": "MAKE_VISIBLE",
    "processingType": "CLIENT",
    "sourceIds": [275511],
    "destinationIds": [275512, 275513, 275514, 275515, 275516],
    "conditionalValues": ["SEZ"],
    "condition": "IN"
  },
  // Similar for "Compounding"
  {
    "actionType": "MAKE_INVISIBLE",
    "processingType": "CLIENT",
    "sourceIds": [275511],
    "destinationIds": [275512, 275513, 275514, 275515, 275516],
    "conditionalValues": ["GST Non-Registered"],
    "condition": "IN"
  }
]
```

**CRITICAL INSIGHT**: Visibility rules are placed on the CONTROLLING/SOURCE field, with multiple destinations in destinationIds array. They are NOT placed on each destination field individually!

---

### Example 5: OCR → VERIFY Chain (GSTIN)

**BUD Fields**:
1. GSTIN IMAGE (FILE): "Get GSTIN from OCR rule"
2. GSTIN (TEXT): "Perform GSTIN validation and store the data in next fields"
3. Trade Name, Legal Name, etc. (TEXT): "Data will come from GSTIN verification"

**Generated Rules Chain**:

On GSTIN IMAGE field:
```json
{
  "actionType": "OCR",
  "sourceType": "GSTIN_IMAGE",
  "sourceIds": [275512],           // GSTIN IMAGE field
  "destinationIds": [275513],      // GSTIN text field
  "postTriggerRuleIds": [119608]   // Links to GSTIN VERIFY rule
}
```

On GSTIN field:
```json
{
  "actionType": "VERIFY",
  "sourceType": "GSTIN",
  "sourceIds": [275513],           // GSTIN field
  "destinationIds": [275514, 275515, 275516, 275517, 275518, 275519, -1, 275520, 275521, 275522, 275523],
  // ordinal 1 → Trade Name (275514)
  // ordinal 2 → Legal Name (275515)
  // ordinal 3 → Reg Date (275516)
  // ordinal 7 → -1 (Flat number not mapped)
  // etc.
  "postTriggerRuleIds": [120188, 120171, 120176, 120177, 120178, 120179]
}
```

---

### Example 6: MAKE_DISABLED Rule

**BUD Field**: Transaction ID (TEXT type)
**Logic from BUD**: "System-generated transaction ID (Non-Editable)"

**Generated Rule**:
```json
{
  "actionType": "MAKE_DISABLED",
  "processingType": "CLIENT",
  "sourceIds": [275633],           // RuleCheck control field
  "destinationIds": [275491],      // Transaction ID field
  "conditionalValues": ["Disable"],
  "condition": "NOT_IN",           // Always triggers
  "executeOnFill": true
}
```

## Processing Algorithm

The rule extraction follows this specific order:

### Step 1: Parse BUD Document
```python
from doc_parser import DocumentParser
parser = DocumentParser()
parsed = parser.parse(bud_path)
```

### Step 2: Build Field Index
```python
# Map field names to field objects and IDs
field_by_name = {f.name: f for f in parsed.all_fields}
field_by_id = {f.id: f for f in schema['formFillMetadatas']}
```

### Step 3: First Pass - Identify Controlling Fields
```python
# Find fields that control others (visibility sources)
for field in parsed.all_fields:
    logic = field.logic or ''

    # Pattern: "if the field 'X' values is Y then visible"
    match = re.search(r"if.*field.*['\"](.+?)['\"].*values?\s+is\s+(\w+)\s+then\s+(visible|mandatory)", logic)
    if match:
        controlling_field = match.group(1)  # e.g., "Please select GST option"
        value = match.group(2)              # e.g., "yes"
        action = match.group(3)             # e.g., "visible"

        # Group this field as a destination of the controlling field
        visibility_groups[controlling_field].append({
            'destination_field': field.name,
            'conditional_value': value,
            'action': action
        })
```

### Step 4: Second Pass - Generate Rules
```python
for field in parsed.all_fields:
    logic = field.logic or ''
    rules = []

    # 1. Check for OCR pattern
    if re.search(r"(from|using)\s+OCR|OCR\s+rule|Get\s+\w+\s+from\s+OCR", logic, re.I):
        rules.append(build_ocr_rule(field))

    # 2. Check for VERIFY pattern (but NOT "Data will come from X validation")
    if re.search(r"Perform\s+\w+\s+[Vv]alidation|[Vv]alidate\s+\w+", logic, re.I):
        if not re.search(r"Data\s+will\s+come\s+from", logic, re.I):
            rules.append(build_verify_rule(field))

    # 3. Check for visibility SOURCES (fields that control others)
    if field.name in visibility_groups:
        rules.extend(build_visibility_rules(field, visibility_groups[field.name]))

    # 4. Check for MAKE_DISABLED
    if re.search(r"Non-Editable|non-editable|read-only|disable", logic, re.I):
        rules.append(build_disabled_rule(field))

    # 5. Skip expression/execute rules
    if should_skip_logic(logic):
        continue

    # Add rules to field
    field_schema['formFillRules'].extend(rules)
```

### Step 5: Third Pass - Link Rule Chains (CRITICAL - 0% in eval!)
```python
# Link OCR rules to VERIFY rules via postTriggerRuleIds
# This is CRITICAL - eval showed 0% rule chaining correctness!
for ocr_rule in all_ocr_rules:
    destination_field_id = ocr_rule['destinationIds'][0]

    # Find VERIFY rule that uses this field as source
    for verify_rule in all_verify_rules:
        if destination_field_id in verify_rule.get('sourceIds', []):
            ocr_rule['postTriggerRuleIds'].append(verify_rule['id'])
            break
```

### Step 5: Third Pass - Link Rule Chains (CRITICAL - 0% in eval!)

**This is the most critical fix - eval showed 0% rule chaining correctness!**

```python
# OCR → VERIFY Rule Chaining
# When an OCR rule extracts data to a field, and that field has a VERIFY rule,
# the OCR rule must trigger the VERIFY rule via postTriggerRuleIds

def link_ocr_to_verify_rules(all_rules: List[Dict]) -> None:
    """Link OCR rules to corresponding VERIFY rules."""

    # Build index of VERIFY rules by source field
    verify_by_source = {}
    for rule in all_rules:
        if rule['actionType'] == 'VERIFY':
            for source_id in rule.get('sourceIds', []):
                verify_by_source[source_id] = rule

    # Link OCR rules to VERIFY rules
    for rule in all_rules:
        if rule['actionType'] == 'OCR':
            # OCR destinationIds[0] is the field being populated
            dest_field_id = rule['destinationIds'][0] if rule.get('destinationIds') else None

            if dest_field_id and dest_field_id in verify_by_source:
                verify_rule = verify_by_source[dest_field_id]
                if 'postTriggerRuleIds' not in rule:
                    rule['postTriggerRuleIds'] = []
                if verify_rule.get('id') not in rule['postTriggerRuleIds']:
                    rule['postTriggerRuleIds'].append(verify_rule['id'])

# OCR → VERIFY Chain Mappings (from eval report)
OCR_VERIFY_CHAINS = {
    # OCR sourceType → VERIFY sourceType
    "PAN_IMAGE": "PAN_NUMBER",           # PAN OCR → PAN VERIFY
    "GSTIN_IMAGE": "GSTIN",              # GSTIN OCR → GSTIN VERIFY
    "CHEQUEE": "BANK_ACCOUNT_NUMBER",    # Cheque OCR → Bank VERIFY
    "MSME": "MSME_UDYAM_REG_NUMBER",     # MSME OCR → MSME VERIFY
    "CIN": "CIN_ID",                     # CIN OCR → CIN VERIFY
    "AADHAR_IMAGE": None,                # Aadhaar Front - no VERIFY
    "AADHAR_BACK_IMAGE": None,           # Aadhaar Back - no VERIFY
}
```

---

## CRITICAL: Multi-Source VERIFY Rules

Some VERIFY rule schemas require **multiple source fields** (not just one). If you only provide partial sourceIds, the API will reject with an error like:
`"Id is not present for the mandatory field Bank Account Number"`

### Multi-Source VERIFY Rule Types

| Source Type | Required Source Fields | numberOfItems |
|-------------|----------------------|---------------|
| `BANK_ACCOUNT_NUMBER` | IFSC Code, Bank Account Number | 2 |
| `GSTIN_WITH_PAN` | PAN, GSTIN | 2 |
| `DRIVING_LICENCE_NUMBER` | DLNumber, DOB | 2 |
| `DRUG_LICENCE` | State Code, Drug Licence Number | 2 |
| `PAN_NUMBER_V2` | Name, DOB | 2 |
| `SHOP_OR_ESTABLISMENT` | State Code, ID Number | 2 |
| `EXTERNAL_DATA_VALUE` | Form Field 1, Form Field 2 | 2 |

### Example: BANK_ACCOUNT_NUMBER VERIFY Rule

**Schema (from Rule-Schemas.json ID 361)**:
```json
{
  "source": "BANK_ACCOUNT_NUMBER",
  "action": "VERIFY",
  "sourceFields": {
    "numberOfItems": 2,
    "fields": [
      {"name": "IFSC Code", "ordinal": 1, "mandatory": true},
      {"name": "Bank Account Number", "ordinal": 2, "mandatory": true}
    ]
  },
  "destinationFields": {
    "numberOfItems": 4,
    "fields": [
      {"name": "Bank Beneficiary Name", "ordinal": 1},
      {"name": "Bank Reference", "ordinal": 2},
      {"name": "Verification Status", "ordinal": 3},
      {"name": "Message", "ordinal": 4}
    ]
  }
}
```

**WRONG Implementation** (causes API error):
```python
# WRONG: Only one sourceId
verify_rule = {
    "actionType": "VERIFY",
    "sourceType": "BANK_ACCOUNT_NUMBER",
    "sourceIds": [88],  # Missing IFSC Code!
    "destinationIds": [89, 90, 91, 92]
}
```

**CORRECT Implementation**:
```python
# CORRECT: Both required source fields
verify_rule = {
    "actionType": "VERIFY",
    "sourceType": "BANK_ACCOUNT_NUMBER",
    "sourceIds": [87, 88],  # [IFSC_Code_ID, Bank_Account_Number_ID]
    "destinationIds": [89, 90, 91, 92]
}
```

### Building Multi-Source VERIFY Rules

```python
def build_multi_source_verify_rule(source_type: str, all_fields: list) -> dict:
    """
    Build VERIFY rule with ALL required source fields.

    CRITICAL: Check schema.sourceFields and include ALL mandatory fields.
    """
    schema = get_rule_schema("VERIFY", source_type)
    if not schema:
        raise ValueError(f"No schema found for {source_type}")

    source_fields_schema = schema.get('sourceFields', {})
    num_required = source_fields_schema.get('numberOfItems', 1)

    # Build sourceIds array with ALL required fields in ordinal order
    source_ids = []
    for field_spec in source_fields_schema.get('fields', []):
        field_name = field_spec['name']
        ordinal = field_spec['ordinal']
        is_mandatory = field_spec.get('mandatory', False)

        # Find matching BUD field
        matched_field = fuzzy_match_field_by_name(field_name, all_fields)

        if matched_field:
            # Ensure array is long enough for this ordinal
            while len(source_ids) < ordinal:
                source_ids.append(-1)
            source_ids[ordinal - 1] = matched_field['id']
        elif is_mandatory:
            raise ValueError(f"Mandatory field '{field_name}' not found for {source_type}")

    return {
        "actionType": "VERIFY",
        "sourceType": source_type,
        "sourceIds": source_ids,
        # ... other fields
    }
```

---

## TEMPORARY: Skip EXT_VALUE and EXT_DROP_DOWN Rules

**Status**: SKIP THESE RULE TYPES FOR NOW

External data value (EDV) rules require complex table mapping configuration that will be explained separately.

**Action for Coding Agent**:
- Do NOT generate EXT_VALUE or EXT_DROP_DOWN rules
- Focus on VERIFY, OCR, visibility, mandatory, and disabled rules first

**Action for Eval**:
- Do NOT flag missing EXT_VALUE or EXT_DROP_DOWN as errors
- Exclude these rule types from comparison counts
- Mark as "SKIPPED" in evaluation report

---

## EDV (External Data Value) Rules - Comprehensive Guide

### What is EDV?

EDV (External Data Value) is an external table system used for:
1. **Dropdown values**: Populating dropdown options from master tables
2. **Cascading/Parent-child dropdowns**: Filtering child dropdown based on parent selection
3. **Validations**: IFSC validation, PAN lookup, etc.
4. **Auto-population**: Filling fields based on external table lookups

### Reference Table to EDV Table Mapping

BUD documents reference tables like "Reference Table 1.3". These map to EDV table names:

| BUD Reference | EDV Table Name | Purpose |
|---------------|----------------|---------|
| Table 1.3 | `VC_VENDOR_TYPES` | Vendor type and group codes |
| Table 1.2 | `COMPANY_CODE_PURCHASE_ORGANIZATION` | Company codes and purchase orgs |
| Table 2.1 | `COUNTRY` | Country list |
| Table 3.1 | `BANK_OPTIONS` | Bank selection options |
| Table 4.1 | `CURRENCY_COUNTRY` | Currency codes |
| Table 5.1 | `TITLE` | Title (Mr/Mrs/Ms) |
| - | `PIDILITE_YES_NO` | Simple Yes/No dropdown |
| - | `YES_NO`, `CB_YES_NO` | Yes/No dropdowns |
| - | `INDIVIDUAL_GROUP` | Individual/Group selection |
| - | `WITHHOLDING_TAX_DATA` | Tax codes |

### EXT_DROP_DOWN vs EXT_VALUE

| Type | When to Use | params Format | sourceType |
|------|-------------|---------------|------------|
| `EXT_DROP_DOWN` | Simple dropdown from EDV table | String: `"TABLE_NAME"` | `EXTERNAL_DATA_VALUE` or `FORM_FILL_DROP_DOWN` |
| `EXT_VALUE` | Cascading dropdown OR auto-populate | JSON: `"[{conditionList...}]"` | `EXTERNAL_DATA_VALUE` |

---

### EXT_DROP_DOWN params Structure (Simple String)

EXT_DROP_DOWN uses simple string params for dropdown tables:

```json
{
  "actionType": "EXT_DROP_DOWN",
  "sourceType": "EXTERNAL_DATA_VALUE",
  "processingType": "CLIENT",
  "sourceIds": [238480],
  "destinationIds": [-1],
  "params": "YES_NO",
  "searchable": false,
  "executeOnFill": true
}
```

**params** is just the EDV table name as a string.

**Common EXT_DROP_DOWN params values from production**:
- `YES_NO`, `CB_YES_NO`, `PIDILITE_YES_NO` - Yes/No dropdowns
- `INDIVIDUAL_GROUP`, `CB_IND_GROUP` - Individual/Group selection
- `LINK`, `LINK_EST_PRO` - Link type dropdowns
- `IND_ESTA` - Individual/Establishment
- `INACTIVE` - Active/Inactive status
- `COMPANY_CODE` - Company codes

---

### EXT_VALUE params Structure (JSON conditionList)

EXT_VALUE uses JSON params with `conditionList` structure for cascading dropdowns and filtered lookups.

**Key fields in conditionList**:
| Field | Description | Example |
|-------|-------------|---------|
| `ddType` | EDV table name (array) | `["VC_VENDOR_TYPES"]` |
| `criterias` | Filter criteria: column → parent field ID | `[{"a1": 275496}]` |
| `da` | Display attribute/column to show | `["a2"]` |
| `ddProperties` | Group property (optional) | `"OUTLET_LICENSE_GROUP"` |
| `criteriaSearchAttr` | Search attributes (usually empty) | `[]` |

**Column Notation**: EDV uses `a1`, `a2`, `a3`... for columns:
- `a1` = Column 1, `a2` = Column 2, etc.
- "first column" → `a1`, "second column" → `a2`

---

### EXT_VALUE Params Patterns (From Production)

#### Pattern 1: Simple lookup (no filtering)
```json
[{
  "conditionList": [
    {"ddType": ["COMPLIANT_KYC"]},
    {"da": ["a1"]}
  ]
}]
```

#### Pattern 2: With ddProperties (group property)
```json
[{
  "conditionList": [
    {"ddType": ["OUTLET_LICENSEE_DETAILS"]},
    {"ddProperties": "OUTLET_LICENSE_GROUP"},
    {"da": ["a1"]}
  ]
}]
```

#### Pattern 3: Single parent filtering (cascading dropdown)
```json
[{
  "conditionList": [
    {"ddType": ["OUTLET_LICENSEE_DETAILS"]},
    {"criterias": [{"a1": 232150}]},
    {"da": ["a2"]}
  ]
}]
```
**Explanation**: Filter rows where column `a1` matches value from field `232150`, display column `a2`.

#### Pattern 4: Multi-parent filtering (multiple criteria)
```json
[{
  "conditionList": [
    {"ddType": ["OUTLET_LICENSEE_DETAILS"]},
    {"criterias": [{"a1": 238459, "a2": 238460}]},
    {"da": ["a3"]}
  ]
}]
```
**Explanation**: Filter by BOTH `a1` (from field 238459) AND `a2` (from field 238460), display `a3`.

#### Pattern 5: Complex multi-level filtering (4+ criteria)
```json
[{
  "conditionList": [
    {"ddType": ["OUTLET_LICENSEE_DETAILS"]},
    {"criterias": [{"a1": 238459, "a2": 238460, "a3": 238462, "a4": 238463}]},
    {"da": ["a5"]}
  ]
}]
```

---

### Parent-Child Dropdown Examples

#### Example: Vendor Type → Group Key

**BUD Logic**:
- **Account Group/Vendor Type** (ID: 275496): "Dropdown values are first and second columns of reference table 1.3"
- **Group key/Corporate Group** (ID: 275498): "Dropdown values will come based on the account group/vendor type selection field as 2nd column of reference table 1.3"

**Generated Rules**:

**Parent field (simple dropdown)**:
```json
{
  "actionType": "EXT_DROP_DOWN",
  "sourceType": "FORM_FILL_DROP_DOWN",
  "sourceIds": [275496],
  "params": "VC_VENDOR_TYPES"
}
```

**Child field (cascading lookup)**:
```json
{
  "actionType": "EXT_VALUE",
  "sourceType": "EXTERNAL_DATA_VALUE",
  "sourceIds": [275498],
  "params": "[{\"conditionList\":[{\"ddType\":[\"VC_VENDOR_TYPES\"]},{\"criterias\":[{\"a1\":275496}]},{\"da\":[\"a2\"]}]}]"
}
```

---

### Building EXT_VALUE params Programmatically

```python
import json

def build_ext_value_params(
    edv_table: str,
    filter_column: str = None,
    parent_field_id: int = None,
    display_column: str = "a1",
    dd_properties: str = None
) -> str:
    """Build EXT_VALUE params JSON."""

    condition_list = [{"ddType": [edv_table]}]

    # Add ddProperties if specified
    if dd_properties:
        condition_list.append({"ddProperties": dd_properties})

    # Add filter criteria if parent-child relationship
    if filter_column and parent_field_id:
        condition_list.append({"criterias": [{filter_column: parent_field_id}]})

    # Add display attribute
    condition_list.append({"da": [display_column]})

    params_obj = [{"conditionList": condition_list}]
    return json.dumps(params_obj)

# Example: Simple lookup
params = build_ext_value_params("COMPLIANT_KYC", display_column="a1")
# Result: '[{"conditionList":[{"ddType":["COMPLIANT_KYC"]},{"da":["a1"]}]}]'

# Example: Cascading dropdown
params = build_ext_value_params(
    edv_table="VC_VENDOR_TYPES",
    filter_column="a1",
    parent_field_id=275496,
    display_column="a2"
)
# Result: '[{"conditionList":[{"ddType":["VC_VENDOR_TYPES"]},{"criterias":[{"a1":275496}]},{"da":["a2"]}]}]'
```

---

### VERIFY Rules - External Validation (NO params!)

**IMPORTANT**: VERIFY rules do NOT have `params`. They use `sourceType` for validation type:

```json
{
  "actionType": "VERIFY",
  "sourceType": "PAN_NUMBER",
  "sourceIds": [238473],
  "destinationIds": [-1, -1, -1, -1, -1, 238475, 238474, -1, -1, -1]
}
```

```json
{
  "actionType": "VERIFY",
  "sourceType": "BANK_ACCOUNT_NUMBER",
  "sourceIds": [238481, 238482],  // [IFSC_ID, Account_Number_ID]
  "destinationIds": [238483, -1, -1, 238486]
}
```

**VERIFY sourceType values**: `PAN_NUMBER`, `BANK_ACCOUNT_NUMBER`, `GSTIN`, `IFSC`, `AADHAR`, `MSME_UDYAM_REG_NUMBER`, `CIN_ID`

---

### EDV Detection Patterns in BUD Logic

```python
EDV_PATTERNS = [
    r"reference\s+table\s+(\d+\.?\d*)",     # "reference table 1.3"
    r"dropdown\s+values?\s+(?:from|are)",   # "Dropdown values from..."
    r"based\s+on\s+(?:the\s+)?(.+?)\s+selection",  # "based on X selection"
    r"parent\s+dropdown\s+field",           # "Parent dropdown field"
    r"cascading\s+dropdown",                # "Cascading dropdown"
    r"external\s+(?:data\s+)?value",        # "External data value"
    r"edv\s+rule",                          # "EDV rule"
    r"column\s+(\d+)\s+of\s+(?:reference\s+)?table",  # "column 2 of table"
    r"first\s+(?:and\s+second\s+)?columns?\s+of",     # "first column of"
]
```

---

### EDV Input Files (from Orchestrator)

When available, use these files passed via command-line:
- `--edv-tables`: `*_edv_tables.json` - Table name mappings
- `--field-edv-mapping`: `*_field_edv_mapping.json` - Pre-built params templates

These contain:
1. `table_name_mapping`: Reference table → EDV table name mapping
2. `field_edv_mappings`: Pre-built params templates for each field
3. `parent_child_chains`: Parent-child dropdown relationships

---

## CRITICAL: Field-Level Rule Comparison (Not Just Counts!)

**Problem**: The current eval passes when total rule counts match, but rules may be on WRONG FIELDS.

**Example from actual comparison**:
```
Field: Account Group/Vendor Type
  GENERATED has: DELETE_DOCUMENT, UNDELETE_DOCUMENT, MAKE_VISIBLE, MAKE_INVISIBLE, COPY_TO
  REFERENCE has: EXT_VALUE, VALIDATION only
  → 5 EXTRA rules that shouldn't exist!

Field: GSTIN
  GENERATED has: VALIDATION, COPY_TO
  REFERENCE has: VERIFY
  → Missing VERIFY, has wrong rules!
```

**Eval MUST check**:
1. Rules on each field match reference (not just total counts)
2. sourceIds and destinationIds have correct structure
3. Strict rules (DELETE_DOCUMENT, UNDELETE_DOCUMENT) only where expected

---

## STRICT Rules - Do NOT Auto-Generate

These rule types should NEVER be auto-generated based on field type alone:

| Rule Type | When to Generate |
|-----------|------------------|
| `DELETE_DOCUMENT` | Only copy from reference - NEVER auto-generate |
| `UNDELETE_DOCUMENT` | Only copy from reference - NEVER auto-generate |
| `VALIDATION` | Only when explicit format validation in BUD logic |
| `COPY_TO` | Only when explicit copy/derive logic in BUD |

**Wrong approach**: "This is a dropdown, add DELETE_DOCUMENT"
**Correct approach**: "Reference has DELETE_DOCUMENT on this field, copy it"

---

### Step 6: Fourth Pass - EXT_DROP_DOWN/EXT_VALUE Rules (17 missing!)

**CRITICAL**: EXT_DROP_DOWN rules are applied when logic references:
1. **External tables** in the BUD document
2. **Excel files** (.xlsx, .xls) referenced in the BUD
3. **Reference tables** mentioned in field logic
4. **Cascading dropdowns** dependent on parent fields

```python
# EXT_DROP_DOWN Detection Patterns
EXT_DROPDOWN_PATTERNS = [
    r"external\s+dropdown",                    # "External dropdown"
    r"dropdown\s+values?\s+from\s+(?:table|excel|reference)",  # "Dropdown values from table"
    r"reference\s+table\s*:",                  # "Reference table: xyz"
    r"parent\s+dropdown\s+field",              # "Parent dropdown field: xyz"
    r"values?\s+from\s+(?:sheet|excel)",       # "Values from sheet xyz"
    r"cascading\s+dropdown",                   # "Cascading dropdown"
    r"dependent\s+on\s+(?:field|dropdown)",    # "Dependent on field xyz"
    r"filter(?:ed)?\s+by\s+parent",            # "Filtered by parent"
    r"\.xlsx?\b",                              # Excel file reference (.xlsx, .xls)
    r"master\s+(?:data|table|list)",           # "Master data", "Master table"
    r"lookup\s+(?:table|from)",                # "Lookup table", "Lookup from"
]

# EXT_VALUE Detection Patterns (for non-dropdown external data)
EXT_VALUE_PATTERNS = [
    r"external\s+(?:data\s+)?value",           # "External value", "External data value"
    r"value\s+from\s+(?:table|excel|external)", # "Value from table"
    r"edv\s+rule",                             # "EDV rule"
    r"lookup\s+value",                         # "Lookup value"
    r"data\s+from\s+(?:reference|master)",     # "Data from reference table"
    r"auto-?populate\s+from",                  # "Auto-populate from"
    r"fetch\s+(?:from|value)",                 # "Fetch from", "Fetch value"
]

# When checking BUD for external references:
def has_external_reference(logic: str, bud_tables: List[str]) -> Tuple[bool, str]:
    """
    Check if logic references external tables or Excel files.

    Returns: (is_external, rule_type)
      - rule_type: "EXT_DROP_DOWN" for dropdowns, "EXT_VALUE" for text/values
    """
    # Check for Excel file references
    if re.search(r"\.(xlsx?|xls)\b", logic, re.I):
        return (True, "EXT_DROP_DOWN" if "dropdown" in logic.lower() else "EXT_VALUE")

    # Check for table references in BUD
    for table_name in bud_tables:
        if table_name.lower() in logic.lower():
            return (True, "EXT_DROP_DOWN")

    # Check for EXT_VALUE patterns first
    for pattern in EXT_VALUE_PATTERNS:
        if re.search(pattern, logic, re.I):
            return (True, "EXT_VALUE")

    # Check for dropdown patterns
    for pattern in EXT_DROPDOWN_PATTERNS:
        if re.search(pattern, logic, re.I):
            return (True, "EXT_DROP_DOWN")

    return (False, None)

# Build EXT_VALUE rule
def build_ext_value_rule(field_id: int, params: str = "") -> Dict:
    """Build EXT_VALUE rule for external data values."""
    return {
        "actionType": "EXT_VALUE",
        "sourceType": "EXTERNAL_DATA_VALUE",
        "processingType": "SERVER",
        "sourceIds": [field_id],
        "destinationIds": [],
        "params": params,
        "executeOnFill": True
    }

# Detect EXT_DROP_DOWN from logic
def detect_ext_dropdown(logic: str, field_type: str) -> bool:
    """Detect if field needs EXT_DROP_DOWN rule."""
    if not logic:
        return False

    # Field must be dropdown type
    if field_type not in ['DROPDOWN', 'MULTI_DROPDOWN', 'EXTERNAL_DROPDOWN']:
        return False

    for pattern in EXT_DROPDOWN_PATTERNS:
        if re.search(pattern, logic, re.IGNORECASE):
            return True

    # Also check for Excel file references in BUD
    if re.search(r"\.(xlsx?|xls)\b", logic, re.IGNORECASE):
        return True

    return False

# Build EXT_DROP_DOWN rule
def build_ext_dropdown_rule(field: Dict, parent_field: Dict = None) -> Dict:
    """Build EXT_DROP_DOWN rule for external/cascading dropdowns."""
    rule = {
        "actionType": "EXT_DROP_DOWN",
        "processingType": "SERVER",
        "sourceIds": [field['id']],
        "destinationIds": [],
        "executeOnFill": True
    }

    # If cascading (has parent), set parent as source
    if parent_field:
        rule['sourceIds'] = [parent_field['id']]
        rule['destinationIds'] = [field['id']]

    return rule

# Common cascading dropdown patterns from vendor creation
CASCADING_DROPDOWNS = [
    ("Country", "State"),           # Country → State cascade
    ("State", "District"),          # State → District cascade
    ("State", "City"),              # State → City cascade
    ("Bank Name", "Branch"),        # Bank → Branch cascade
    ("Account Group", "Account Type"),
]

def detect_cascading_dropdowns(all_fields: List[Dict]) -> List[Tuple]:
    """Identify cascading dropdown pairs from field logic."""
    cascades = []

    for field in all_fields:
        logic = field.get('logic', '') or ''

        # Pattern: "Parent dropdown field: X"
        match = re.search(r"parent\s+dropdown\s+field\s*:\s*['\"]?([^'\"]+)['\"]?", logic, re.I)
        if match:
            parent_name = match.group(1).strip()
            cascades.append((parent_name, field['name']))

        # Pattern: "Dependent on field X"
        match = re.search(r"dependent\s+on\s+(?:field|dropdown)\s*[:\s]+['\"]?([^'\"]+)['\"]?", logic, re.I)
        if match:
            parent_name = match.group(1).strip()
            cascades.append((parent_name, field['name']))

    return cascades
```

### Step 7: Fifth Pass - Missing VERIFY Rules Detection

**Eval showed missing: BANK_ACCOUNT_NUMBER, MSME_UDYAM_REG_NUMBER, GSTIN_WITH_PAN**

```python
# Additional VERIFY patterns to detect
VERIFY_PATTERNS = {
    # Document type keyword → (source type, schema ID)
    "pan": ("PAN_NUMBER", 360),
    "gstin": ("GSTIN", 355),
    "gst": ("GSTIN", 355),
    "bank": ("BANK_ACCOUNT_NUMBER", 361),
    "ifsc": ("BANK_ACCOUNT_NUMBER", 361),
    "msme": ("MSME_UDYAM_REG_NUMBER", 337),
    "udyam": ("MSME_UDYAM_REG_NUMBER", 337),
    "cin": ("CIN_ID", 349),
    "tan": ("TAN_NUMBER", 322),
    "fssai": ("FSSAI", 356),
}

def detect_verify_type(logic: str) -> Optional[Tuple[str, int]]:
    """Detect VERIFY type from logic text."""
    logic_lower = logic.lower()

    # Check for verification keywords
    if not re.search(r"(perform|validate|verify|validation|verification)", logic_lower):
        return None

    # Skip destination fields ("Data will come from X validation")
    if re.search(r"data\s+will\s+come\s+from", logic_lower):
        return None

    for keyword, (source_type, schema_id) in VERIFY_PATTERNS.items():
        if keyword in logic_lower:
            return (source_type, schema_id)

    return None

# Cross-validation rule: GSTIN_WITH_PAN
def build_gstin_with_pan_rule(pan_field_id: int, gstin_field_id: int) -> Dict:
    """Build cross-validation rule to verify PAN matches GSTIN."""
    return {
        "actionType": "VERIFY",
        "sourceType": "GSTIN_WITH_PAN",
        "processingType": "SERVER",
        "sourceIds": [pan_field_id, gstin_field_id],
        "destinationIds": [],
        "params": "{ \"paramMap\": {\"errorMessage\": \"GSTIN and PAN doesn't match.\"}}",
        "executeOnFill": True
    }
```

### Step 8: Sixth Pass - Missing OCR Rules Detection

**Eval showed missing: CHEQUEE, AADHAR_BACK_IMAGE, CIN, MSME**

```python
# OCR patterns for different document types
OCR_PATTERNS = {
    # Field name patterns → (source type, schema ID)
    r"upload\s*pan|pan\s*(?:image|upload|file)": ("PAN_IMAGE", 344),
    r"upload\s*gstin|gstin\s*(?:image|upload|file)": ("GSTIN_IMAGE", 347),
    r"aadhaar?\s*front|front\s*aadhaar?": ("AADHAR_IMAGE", 359),
    r"aadhaar?\s*back|back\s*aadhaar?": ("AADHAR_BACK_IMAGE", 348),
    r"cheque|cancelled\s*cheque": ("CHEQUEE", 269),
    r"cin\s*(?:image|upload|file)|upload\s*cin": ("CIN", None),  # CIN OCR
    r"msme\s*(?:image|upload|file)|upload\s*msme|udyam": ("MSME", None),  # MSME OCR
}

def detect_ocr_type(field_name: str, logic: str) -> Optional[Tuple[str, int]]:
    """Detect OCR type from field name or logic."""
    combined = f"{field_name} {logic}".lower()

    # Must have OCR keywords in logic
    if not re.search(r"ocr|extract|scan", combined):
        # Also check if it's a file upload field that matches patterns
        if not re.search(r"upload|file|image", combined):
            return None

    for pattern, (source_type, schema_id) in OCR_PATTERNS.items():
        if re.search(pattern, combined, re.IGNORECASE):
            return (source_type, schema_id)

    return None

# Find destination field for OCR (the field being populated)
def find_ocr_destination(field: Dict, all_fields: List[Dict]) -> Optional[int]:
    """Find the field that OCR will populate."""
    field_name = field['name'].lower()

    # Pattern: "Upload X" → "X" field
    # e.g., "Upload PAN" → "PAN"
    match = re.match(r"upload\s+(.+)", field_name, re.I)
    if match:
        target_name = match.group(1).strip()

        # Find matching field
        for f in all_fields:
            if f['name'].lower() == target_name.lower():
                return f['id']
            # Also try with variations
            if target_name.lower() in f['name'].lower() and f.get('field_type') in ['TEXT', 'DROPDOWN']:
                return f['id']

    return None
```

### Step 9: Seventh Pass - Deduplication and Consolidation

**CRITICAL: Eval showed 53 MAKE_DISABLED rules vs 5 in reference!**

```python
# CRITICAL: Reference uses single rule with multiple destinationIds

def consolidate_rules(all_rules: List[Dict]) -> List[Dict]:
    """Consolidate and deduplicate rules."""

    # 1. Group rules by (actionType, sourceIds, condition, conditionalValues)
    rule_groups = defaultdict(list)
    non_groupable = []

    GROUPABLE_ACTIONS = ['MAKE_DISABLED', 'MAKE_VISIBLE', 'MAKE_INVISIBLE',
                         'MAKE_MANDATORY', 'MAKE_NON_MANDATORY']

    for rule in all_rules:
        action = rule.get('actionType')
        if action in GROUPABLE_ACTIONS:
            key = (
                action,
                tuple(sorted(rule.get('sourceIds', []))),
                rule.get('condition'),
                tuple(sorted(rule.get('conditionalValues', [])))
            )
            rule_groups[key].append(rule)
        else:
            non_groupable.append(rule)

    # 2. Merge grouped rules - combine destinationIds
    consolidated = []
    for key, rules in rule_groups.items():
        if len(rules) == 1:
            consolidated.append(rules[0])
        else:
            # Merge: combine all destinationIds, keep other fields from first rule
            merged = rules[0].copy()
            all_dest_ids = set()
            for r in rules:
                all_dest_ids.update(r.get('destinationIds', []))
            merged['destinationIds'] = sorted(list(all_dest_ids))
            consolidated.append(merged)

    # 3. Add non-groupable rules
    consolidated.extend(non_groupable)

    # 4. Remove exact duplicates
    seen = set()
    deduplicated = []
    for rule in consolidated:
        # Create unique key
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

# Remove duplicate rules per field
def remove_field_duplicates(field_rules: List[Dict]) -> List[Dict]:
    """Remove duplicate rules for a single field."""
    seen = set()
    unique = []

    for rule in field_rules:
        key = (
            rule.get('actionType'),
            rule.get('sourceType'),
            rule.get('condition'),
            tuple(rule.get('conditionalValues', []))
        )
        if key not in seen:
            seen.add(key)
            unique.append(rule)

    return unique
```

### Rule Generation Templates

**IMPORTANT: All rules use sequential IDs from the global IdGenerator, starting from 1.**

```python
# Global ID generator - ensures all IDs are sequential starting from 1
class IdGenerator:
    def __init__(self):
        self.counters = {}

    def next_id(self, id_type: str = 'rule') -> int:
        if id_type not in self.counters:
            self.counters[id_type] = 0
        self.counters[id_type] += 1
        return self.counters[id_type]

# Single global instance used throughout
id_generator = IdGenerator()

# Base rule template - ALL rules must have these fields
def create_base_rule(
    action_type: str,
    source_ids: List[int],
    destination_ids: List[int] = None,
    processing_type: str = "CLIENT"
) -> Dict:
    """Create base rule with all required fields and sequential ID."""
    return {
        "id": id_generator.next_id('rule'),  # Sequential: 1, 2, 3, ...
        "createUser": "FIRST_PARTY",
        "updateUser": "FIRST_PARTY",
        "actionType": action_type,
        "processingType": processing_type,
        "sourceIds": source_ids,
        "destinationIds": destination_ids or [],
        "postTriggerRuleIds": [],
        "button": "",
        "searchable": False,
        "executeOnFill": True,
        "executeOnRead": False,
        "executeOnEsign": False,
        "executePostEsign": False,
        "runPostConditionFail": False
    }

# Conditional rule (MAKE_VISIBLE, MAKE_INVISIBLE, etc.)
def create_conditional_rule(
    action_type: str,
    source_ids: List[int],
    destination_ids: List[int],
    conditional_values: List[str],
    condition: str = "IN"
) -> Dict:
    """Create conditional visibility/mandatory rule with auto-generated sequential ID."""
    rule = create_base_rule(action_type, source_ids, destination_ids)
    rule.update({
        "conditionalValues": conditional_values,
        "condition": condition,
        "conditionValueType": "TEXT"
    })
    return rule

# VERIFY rule
def create_verify_rule(
    source_type: str,
    source_ids: List[int],
    destination_ids: List[int],
    post_trigger_ids: List[int] = None,
    button: str = "Verify"
) -> Dict:
    """Create VERIFY rule for validation with auto-generated sequential ID."""
    rule = create_base_rule("VERIFY", source_ids, destination_ids, "SERVER")
    rule.update({
        "sourceType": source_type,
        "button": button,
        "postTriggerRuleIds": post_trigger_ids or []
    })
    return rule

# OCR rule
def create_ocr_rule(
    source_type: str,
    source_ids: List[int],
    destination_ids: List[int],
    post_trigger_ids: List[int] = None
) -> Dict:
    """Create OCR rule for document extraction with auto-generated sequential ID."""
    rule = create_base_rule("OCR", source_ids, destination_ids, "SERVER")
    rule.update({
        "sourceType": source_type,
        "postTriggerRuleIds": post_trigger_ids or []
    })
    return rule

# EXT_DROP_DOWN rule
def create_ext_dropdown_rule(
    source_ids: List[int],
    params: str
) -> Dict:
    """Create external dropdown rule with auto-generated sequential ID."""
    rule = create_base_rule("EXT_DROP_DOWN", source_ids, [])
    rule.update({
        "sourceType": "FORM_FILL_DROP_DOWN",
        "params": params,
        "searchable": True
    })
    return rule

# GSTIN_WITH_PAN cross-validation
def create_gstin_pan_rule(
    pan_field_id: int,
    gstin_field_id: int
) -> Dict:
    """Create GSTIN with PAN cross-validation rule with auto-generated sequential ID."""
    rule = create_base_rule("VERIFY", [pan_field_id, gstin_field_id], [], "SERVER")
    rule.update({
        "sourceType": "GSTIN_WITH_PAN",
        "params": '{ "paramMap": {"errorMessage": "GSTIN and PAN doesn\'t match."}}',
        "onStatusFail": "CONTINUE"
    })
    return rule
```

### Summary: Complete Processing Pipeline

```python
def process_bud_to_rules(bud_path: str, schema_path: str) -> Dict:
    """Complete rule extraction pipeline with all fixes from eval."""

    # Step 1: Parse BUD
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    # Step 2: Build field index
    field_by_name = {f.name: f for f in parsed.all_fields}
    field_by_id = {}  # Populate from schema

    # Step 3: First pass - Identify visibility controlling fields
    visibility_groups = identify_visibility_sources(parsed.all_fields)

    # Step 4: Second pass - Generate rules for each field
    all_rules = []
    for field in parsed.all_fields:
        if should_skip_logic(field.logic):
            continue

        rules = generate_field_rules(field, visibility_groups, field_by_name)
        all_rules.extend(rules)

    # Step 5: Link OCR → VERIFY chains (CRITICAL!)
    link_ocr_to_verify_rules(all_rules)

    # Step 6: Add EXT_DROP_DOWN rules for external dropdowns
    cascades = detect_cascading_dropdowns(parsed.all_fields)
    for parent_name, child_name in cascades:
        parent = field_by_name.get(parent_name)
        child = field_by_name.get(child_name)
        if parent and child:
            all_rules.append(build_ext_dropdown_rule(child, parent))

    # Step 7: Add missing VERIFY rules
    add_missing_verify_rules(parsed.all_fields, all_rules)

    # Step 8: Add missing OCR rules
    add_missing_ocr_rules(parsed.all_fields, all_rules, field_by_name)

    # Step 9: Consolidate and deduplicate
    final_rules = consolidate_rules(all_rules)

    return {"formFillRules": final_rules}
```

---

## Verified Schema IDs from Rule-Schemas.json

**VERIFY Rules (182 total schemas, key ones below):**
| ID  | Name                   | Source                    | Dest Fields |
|-----|------------------------|---------------------------|-------------|
| 360 | Validate PAN           | PAN_NUMBER                | 10 fields   |
| 355 | Validate GSTIN         | GSTIN                     | 21 fields   |
| 361 | Validate Bank Account  | BANK_ACCOUNT_NUMBER       | 4 fields    |
| 337 | Validate MSME          | MSME_UDYAM_REG_NUMBER     | 21 fields   |
| 349 | Validate CIN           | CIN_ID                    | N/A         |
| 322 | Validate TAN           | TAN_NUMBER                | N/A         |
| 356 | Validate FSSAI         | FSSAI                     | 11 fields   |

**OCR Rules:**
| ID  | Name               | Source           | Dest Fields |
|-----|--------------------|------------------|-------------|
| 344 | PAN OCR            | PAN_IMAGE        | 4 fields    |
| 347 | GSTIN OCR          | GSTIN_IMAGE      | 11 fields   |
| 348 | Aadhaar Back OCR   | AADHAR_BACK_IMAGE| 9 fields    |
| 269 | Cheque OCR         | CHEQUEE          | 7 fields    |
| 214 | MSME OCR           | MSME             | 6 fields    |

**Destination Ordinal Mappings:**

```
PAN_NUMBER (ID 360) Destination Ordinals:
  1: Panholder title    | 6: Pan retrieval status
  2: Firstname          | 7: Fullname without title
  3: Lastname           | 8: Pan type
  4: Fullname           | 9: Aadhaar seeding status
  5: Last updated       | 10: Middle name

CHEQUEE (ID 269) Destination Ordinals:
  1: bankName           | 5: address
  2: ifscCode           | 6: micrCode
  3: beneficiaryName    | 7: branch
  4: accountNumber

AADHAR_BACK_IMAGE (ID 348) Destination Ordinals:
  1: aadharAddress1     | 6: aadharState
  2: aadharAddress2     | 7: aadharFatherName
  3: aadharPin          | 8: aadharCountry
  4: aadharCity         | 9: aadharCoords
  5: aadharDist
```

---

## Core Components

### 1. Logic Parser (`logic_parser.py`)
**Purpose**: Parse natural language logic statements into structured data

**Key Classes**:
- `LogicParser`: Main parser coordinating all extraction
- `KeywordExtractor`: Extract action keywords (visible, mandatory, validate, etc.)
- `EntityExtractor`: Extract field references and document types
- `ConditionExtractor`: Extract conditional logic (if/then/else)

**Pattern Categories** (from BUD analysis):
- Conditional visibility (78 occurrences): "visible", "invisible", "show", "hide"
- Conditional mandatory (28): "mandatory", "non-mandatory", "required", "optional"
- Validation rules (64): "validate", "validation", "verify", "check"
- Data derivation (19): "copy", "derive", "auto-fill", "populate"
- OCR extraction (19): "OCR", "extract from"
- Dropdown control (37): "dropdown values", "reference table"

**Example**:
```python
logic = "if field 'GST option' is yes then visible and mandatory"
parsed = LogicParser().parse(logic)
# Returns:
# - keywords: ['if', 'visible', 'mandatory']
# - condition: Condition(field='GST option', op='==', value='yes')
# - actions: ['make_visible', 'make_mandatory']
# - field_refs: ['GST option']
```

### 2. Rule Selection Tree (`rule_tree.py`)
**Purpose**: Deterministically select rules based on keywords and patterns

**Tree Structure**:
```
ROOT
├─ VISIBILITY_CONTROL
│  ├─ MAKE_VISIBLE → actionType: "MAKE_VISIBLE"
│  └─ MAKE_INVISIBLE → actionType: "MAKE_INVISIBLE"
├─ MANDATORY_CONTROL
│  ├─ MAKE_MANDATORY → actionType: "MAKE_MANDATORY"
│  └─ MAKE_NON_MANDATORY → actionType: "MAKE_NON_MANDATORY"
├─ EDITABILITY_CONTROL
│  ├─ DISABLE → actionType: "MAKE_DISABLED"
│  └─ ENABLE → actionType: "MAKE_ENABLED"
├─ VALIDATION
│  ├─ PAN_VALIDATION → STANDARD Rule #360
│  ├─ GSTIN_VALIDATION → STANDARD Rule #355
│  ├─ BANK_VALIDATION → STANDARD Rule #361
│  └─ [Other validations...]
├─ OCR_EXTRACTION
│  ├─ PAN_OCR → STANDARD Rule #344
│  ├─ AADHAAR_FRONT_OCR → STANDARD Rule #359
│  ├─ GSTIN_OCR → STANDARD Rule #347
│  └─ [Other OCR rules...]
└─ DATA_OPERATIONS
   ├─ COPY_TO → actionType: "COPY_TO"
   └─ CLEAR_FIELD → actionType: "CLEAR_FIELD"
```

**Traversal Algorithm**:
1. Extract keywords from logic text
2. Match keywords to tree nodes
3. Navigate to appropriate category
4. If deterministic match found → return rule
5. If ambiguous → use LLM fallback

### 3. Field Matcher (`field_matcher.py`)
**Purpose**: Match field references from logic text to actual field IDs in schema

**Approach**: RapidFuzz library for fuzzy string matching
- Exact match first (O(1) lookup)
- Fuzzy match if no exact match (token_sort_ratio scorer)
- Threshold: 80% similarity

**Example**:
```python
matcher = FieldMatcher(schema)
# Logic: "if field 'Please select GST option' is yes"
field_info = matcher.match_field("Please select GST option")
# Returns: FieldInfo(id=275491, variable_name="_pleaseSelect48_")
```

### 4. Rule Builders (`rule_builders/`)
**Purpose**: Generate formFillRules JSON structures

**Types**:
- `StandardRuleBuilder`: Rules with actionType (MAKE_VISIBLE, MAKE_MANDATORY, etc.)
- `ComplexRuleBuilder`: Rules requiring sourceIds + destinationIds + conditions
- `ValidationRuleBuilder`: OCR/validation rules from Rule-Schemas.json

**Output Format** (matches documents/json_output/*.json):
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
  "executeOnFill": true,
  "executeOnRead": false
}
```

### 5. LLM Fallback Handler (`llm_fallback.py`)
**Purpose**: Handle complex/ambiguous logic using OpenAI (like existing `rules_extractor.py`)

**When to use**:
- Pattern-based extraction confidence < 70%
- No clear keyword match in decision tree
- Complex multi-step logic
- Nested conditions

**Integration**:
```python
# Try deterministic first
rules = rule_tree.select_rules(parsed_logic)
if rules.confidence < 0.7:
    # Fall back to LLM
    rules = llm_fallback.extract_rules(logic_text, rule_schemas)
```

## Module Structure

```
rule_extraction_agent/
├── __init__.py
├── main.py                     # CLI entry point
├── models.py                   # Data models
│   ├── ParsedLogic
│   ├── Condition
│   ├── RuleSelection
│   ├── GeneratedRule
│   └── FieldInfo
├── logic_parser.py             # Logic text parsing
├── rule_tree.py                # Decision tree
├── field_matcher.py            # Field matching
├── schema_lookup.py            # NEW: Rule-Schemas.json query interface
├── id_mapper.py                # NEW: Ordinal-to-index mapping for destinationIds
├── matchers/                   # NEW: Multi-stage matching
│   ├── __init__.py
│   ├── pipeline.py             # Multi-stage matching coordinator
│   ├── deterministic.py        # Pattern-based matcher
│   └── llm_fallback.py         # LLM fallback with schema context
├── rule_builders/
│   ├── __init__.py
│   ├── base_builder.py
│   ├── standard_builder.py
│   ├── validation_builder.py
│   ├── verify_builder.py       # NEW: VERIFY rule builder
│   └── ocr_builder.py          # NEW: OCR rule builder
├── llm_fallback.py             # OpenAI integration
├── validators.py               # Rule validation
└── utils.py                    # Utilities
```

## Integration Points

### Input Files
1. **Schema JSON** (from `extract_fields_complete.py`):
   - Path: `output/complete_format/NNNN-schema.json`
   - Contains: formFillMetadatas with field IDs, names, types
   - Needs: formFillRules arrays to be populated

2. **Intra-Panel References** (from `intra_panel_rule_field_references.py`):
   - Path: Provided as command-line argument
   - Contains: Field dependency information
   - Usage: Helps identify source/destination relationships

3. **Rule Schemas** (`rules/Rule-Schemas.json`):
   - 182 pre-defined rules for OCR, validation, etc.
   - Used for STANDARD rules (not actionType rules)

### Output
- Updated schema JSON with formFillRules populated
- Summary report: rules generated, confidence scores, unmatched fields

## New Core Components

### Schema Lookup Module (`schema_lookup.py`)

```python
class RuleSchemaLookup:
    """Query interface for Rule-Schemas.json (182 pre-defined rules)."""

    def __init__(self, path: str = "rules/Rule-Schemas.json"):
        with open(path, 'r') as f:
            data = json.load(f)
        self.schemas = data.get('content', [])
        self._build_indexes()

    def _build_indexes(self):
        """Build fast lookup indexes."""
        self.by_id = {s['id']: s for s in self.schemas}
        self.by_action = {}
        for s in self.schemas:
            action = s.get('action')
            if action not in self.by_action:
                self.by_action[action] = []
            self.by_action[action].append(s)

    def find_by_action_and_source(self, action: str, source: str) -> Optional[Dict]:
        """Find rule schema by action type and source type."""
        for schema in self.by_action.get(action, []):
            if schema.get('source') == source:
                return schema
        return None

    def get_destination_ordinals(self, schema_id: int) -> Dict[str, int]:
        """Get mapping of destination field names to ordinal positions."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return {}
        dest_fields = schema.get('destinationFields', {}).get('fields', [])
        return {f['name']: f['ordinal'] for f in dest_fields}

    def get_source_field_requirements(self, schema_id: int) -> List[Dict]:
        """Get source field requirements (mandatory, etc.)."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return []
        return schema.get('sourceFields', {}).get('fields', [])

    def build_llm_context(self, schema_id: int) -> str:
        """Build context string for LLM fallback."""
        schema = self.by_id.get(schema_id)
        if not schema:
            return ""

        lines = [
            f"Rule Schema ID: {schema['id']}",
            f"Name: {schema['name']}",
            f"Action: {schema['action']}",
            f"Source: {schema['source']}",
            "",
            "Source Fields:"
        ]

        for f in schema.get('sourceFields', {}).get('fields', []):
            lines.append(f"  ordinal {f['ordinal']}: {f['name']} (mandatory: {f.get('mandatory', False)})")

        lines.append("")
        lines.append("Destination Fields:")
        for f in schema.get('destinationFields', {}).get('fields', []):
            lines.append(f"  ordinal {f['ordinal']}: {f['name']}")

        return "\n".join(lines)
```

### Destination ID Mapper Module (`id_mapper.py`)

```python
class DestinationIdMapper:
    """Maps BUD field IDs to ordinal-indexed destinationIds arrays."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        self.schema_lookup = schema_lookup

    def map_to_ordinals(
        self,
        schema_id: int,
        field_mappings: Dict[str, int]  # schema_field_name → field_id
    ) -> List[int]:
        """
        Build destinationIds array with -1 for unused ordinals.

        Args:
            schema_id: Rule schema ID from Rule-Schemas.json
            field_mappings: Dict mapping schema field names to BUD field IDs

        Returns:
            List of field IDs indexed by ordinal position (ordinal 1 → index 0)

        Example:
            schema_id = 360  # Validate PAN (10 destination fields)
            field_mappings = {"Fullname": 275535, "Pan type": 275536}
            Returns: [-1, -1, -1, 275535, -1, -1, -1, 275536, -1, -1]
        """
        schema = self.schema_lookup.by_id.get(schema_id)
        if not schema:
            return []

        num_items = schema.get('destinationFields', {}).get('numberOfItems', 0)
        dest_fields = schema.get('destinationFields', {}).get('fields', [])

        # Initialize with -1 for all ordinal positions
        destination_ids = [-1] * num_items

        # Map field names to their ordinal positions
        name_to_ordinal = {f['name']: f['ordinal'] for f in dest_fields}

        # Fill in mapped field IDs at correct ordinal positions
        for field_name, field_id in field_mappings.items():
            ordinal = name_to_ordinal.get(field_name)
            if ordinal and 1 <= ordinal <= num_items:
                destination_ids[ordinal - 1] = field_id  # ordinal 1 → index 0

        return destination_ids
```

### Multi-Stage Matching Pipeline (`matchers/pipeline.py`)

```python
class MatchingPipeline:
    """Two-stage matching: deterministic patterns → LLM fallback."""

    def __init__(self, schema_path: str = "rules/Rule-Schemas.json"):
        self.deterministic = DeterministicMatcher()
        self.llm_fallback = LLMFallback()
        self.schema_lookup = RuleSchemaLookup(schema_path)
        self.field_matcher = FieldMatcher()

    def match(
        self,
        logic_text: str,
        field_info: Dict,
        all_fields: List[Dict]
    ) -> MatchResult:
        """
        Match logic text to rule(s) using two-stage approach.

        Stage 1: Deterministic pattern matching
        Stage 2: LLM fallback with Rule-Schemas.json context
        """
        # Stage 1: Deterministic pattern matching
        result = self.deterministic.match(logic_text)

        if result.confidence >= 0.7:
            # High confidence - proceed with deterministic result
            # Still need to resolve field IDs
            result.source_field_id = self.field_matcher.find_source_field(
                result.source_field_name, all_fields
            )
            return result

        # Stage 2: LLM with Rule-Schemas.json context
        # CRITICAL: Lookup candidate rules and pass schema to LLM
        candidate_schemas = self.schema_lookup.find_candidates(
            logic_text,
            result.possible_action_types
        )
        schema_context = self.schema_lookup.build_llm_context(candidate_schemas)

        return self.llm_fallback.match(
            logic_text,
            field_info,
            schema_context,
            all_fields
        )
```

### Rule-Specific Builders

#### VERIFY Rule Builder (`rule_builders/verify_builder.py`)

```python
class VerifyRuleBuilder:
    """Builds VERIFY rules (PAN, GSTIN, Bank, MSME, CIN validation)."""

    def __init__(self, schema_lookup: RuleSchemaLookup, id_mapper: DestinationIdMapper):
        self.schema_lookup = schema_lookup
        self.id_mapper = id_mapper

    def build(
        self,
        schema_id: int,
        source_field_id: int,
        field_mappings: Dict[str, int],  # schema_field → bud_field_id
        post_trigger_ids: List[int] = None
    ) -> Dict:
        """
        Build VERIFY rule with proper destinationIds ordinal mapping.

        Example for PAN Validation (schema_id=360):
            source_field_id = 275534  # PAN input field
            field_mappings = {
                "Fullname": 275535,
                "Pan retrieval status": 275537,
                "Pan type": 275536,
                "Aadhaar seeding status": 275538
            }
        """
        schema = self.schema_lookup.by_id.get(schema_id)
        if not schema:
            raise ValueError(f"Schema {schema_id} not found")

        destination_ids = self.id_mapper.map_to_ordinals(schema_id, field_mappings)

        return {
            "actionType": schema["action"],
            "sourceType": schema["source"],
            "processingType": schema.get("processingType", "SERVER"),
            "sourceIds": [source_field_id],
            "destinationIds": destination_ids,
            "postTriggerRuleIds": post_trigger_ids or [],
            "button": schema.get("button", "Verify"),
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }
```

#### OCR Rule Builder (`rule_builders/ocr_builder.py`)

```python
class OcrRuleBuilder:
    """Builds OCR rules (PAN_IMAGE, GSTIN_IMAGE, etc.)."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        self.schema_lookup = schema_lookup

    def build(
        self,
        schema_id: int,
        upload_field_id: int,
        output_field_id: int,
        post_trigger_ids: List[int] = None
    ) -> Dict:
        """
        Build OCR rule.

        Args:
            schema_id: OCR schema ID (e.g., 344 for PAN OCR)
            upload_field_id: File upload field ID (source)
            output_field_id: Text field ID to populate (destination)
            post_trigger_ids: Rule IDs to trigger after OCR (e.g., VERIFY rule)
        """
        schema = self.schema_lookup.by_id.get(schema_id)
        if not schema:
            raise ValueError(f"Schema {schema_id} not found")

        return {
            "actionType": "OCR",
            "sourceType": schema["source"],
            "processingType": "SERVER",
            "sourceIds": [upload_field_id],
            "destinationIds": [output_field_id],
            "postTriggerRuleIds": post_trigger_ids or [],
            "button": "",
            "executeOnFill": True,
            "executeOnRead": False,
            "executeOnEsign": False,
            "executePostEsign": False,
            "runPostConditionFail": False
        }
```

### Deterministic Pattern Categories

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

### Rules to Ignore

The following rule types should be **skipped** during extraction as they are handled differently:

1. **Expression Rules**: Logic containing mathematical expressions or expr-eval syntax
   - Pattern: Contains `mvi(`, `mm(`, `expr-eval`, arithmetic operators in code-like syntax
   - Example: "mvi('fieldA') + mvi('fieldB')"

2. **Execute Rules**: Rules that execute custom code or scripts
   - Pattern: Contains `EXECUTE`, `execute rule`, `script`
   - Example: "Execute custom validation script"

```python
SKIP_PATTERNS = [
    r"mvi\s*\(", r"mm\s*\(", r"expr-eval",
    r"\bEXECUTE\b", r"execute\s+rule", r"execute\s+script"
]

def should_skip_logic(logic_text: str) -> bool:
    """Check if logic should be skipped (expression/execute rules)."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, logic_text, re.IGNORECASE):
            return True
    return False
```

---

## Implementation Steps

### Phase 1: Core Infrastructure (Days 1-2)
1. Create module structure and data models
2. Implement LogicParser with keyword extraction
3. Build FieldMatcher with fuzzy matching
4. Create StandardRuleBuilder for simple rules
5. **NEW**: Implement RuleSchemaLookup for Rule-Schemas.json queries
6. **NEW**: Implement DestinationIdMapper for ordinal-indexed arrays

**Deliverable**: Can parse logic and match fields

### Phase 2: Rule Selection Tree (Days 3-4)
1. Build decision tree structure from Rule-Schemas.json
2. Implement tree traversal algorithm
3. Add pattern matching for common rule types
4. Handle conditional logic (if/then/else)

**Deliverable**: Deterministic rule selection for 80% of cases

### Phase 3: Complex Rules & LLM Fallback (Day 5)
1. Integrate OpenAI API (reuse `rules_extractor.py` patterns)
2. Implement confidence scoring
3. Add LLM fallback for low-confidence cases
4. Handle multi-rule logic statements

**Deliverable**: Full coverage including complex cases

### Phase 4: Integration & Testing (Days 6-7)
1. Integrate with `extract_fields_complete.py` output
2. Use intra-panel references for field dependencies
3. Write unit tests for each component
4. Test on Vendor Creation Sample BUD
5. Manual review and accuracy validation

**Deliverable**: Working end-to-end system

## Critical Files to Modify/Create

### New Files (Create)
- `rule_extraction_agent/` (entire module)
- `rule_extraction_agent.py` (main entry script)

### Reference Files (Read-Only)
- `/home/samart/project/doc-parser/extract_fields_complete.py` - Output format reference
- `/home/samart/project/doc-parser/rules/Rule-Schemas.json` - Rule definitions
- `/home/samart/project/doc-parser/rules_extractor.py` - LLM integration patterns
- `/home/samart/project/doc-parser/RULES_REFERENCE.md` - Rule documentation
- `/home/samart/project/doc-parser/documents/Vendor Creation Sample BUD.docx` - Test data
- `/home/samart/project/doc-parser/documents/json_output/vendor_creation_sample_bud.json` - Expected output

### Integration Points
- Input: JSON from `extract_fields_complete.py`
- Input: JSON from intra-panel template
- Output: Updated JSON with formFillRules

## Command-Line Interface

```bash
# Basic usage
python rule_extraction_agent.py \
  --schema output/complete_format/2581-schema.json \
  --intra-panel extraction/intra_panel_output/vendor_basic_details.json \
  --output output/rules_populated/2581-schema.json

# With options
python rule_extraction_agent.py \
  --schema output/complete_format/2581-schema.json \
  --intra-panel extraction/intra_panel_output/vendor_basic_details.json \
  --output output/rules_populated/2581-schema.json \
  --verbose \
  --validate \
  --llm-threshold 0.7 \
  --report summary_report.json
```

**Arguments**:
- `--schema`: Path to schema JSON from extract_fields_complete.py (required)
- `--intra-panel`: Path to intra-panel references JSON (required)
- `--output`: Output path for populated schema (optional, auto-generated)
- `--verbose`: Enable verbose logging
- `--validate`: Validate generated rules
- `--llm-threshold`: Confidence threshold for LLM fallback (default: 0.7)
- `--report`: Path to save summary report

## Example Logic Processing

### Example 1: Simple Conditional Visibility

**Input Logic**:
```
"if the field 'Please select GST option' value is yes then visible and mandatory
otherwise invisible and non-mandatory"
```

**Processing**:
1. **Parse**: Extract condition (field='GST option', op='==', value='yes')
2. **Actions**: ['make_visible', 'make_mandatory', 'make_invisible', 'make_non_mandatory']
3. **Match**: 'GST option' → Field ID 275491
4. **Select Rules**: 4 rules (visibility + mandatory for both conditions)
5. **Generate**:

```json
[
  {
    "actionType": "MAKE_VISIBLE",
    "processingType": "CLIENT",
    "sourceIds": [275491],
    "destinationIds": [275492],
    "conditionalValues": ["yes"],
    "condition": "IN"
  },
  {
    "actionType": "MAKE_MANDATORY",
    "processingType": "CLIENT",
    "sourceIds": [275491],
    "destinationIds": [275492],
    "conditionalValues": ["yes"],
    "condition": "IN"
  },
  {
    "actionType": "MAKE_INVISIBLE",
    "processingType": "CLIENT",
    "sourceIds": [275491],
    "destinationIds": [275492],
    "conditionalValues": ["yes"],
    "condition": "NOT_IN"
  },
  {
    "actionType": "MAKE_NON_MANDATORY",
    "processingType": "CLIENT",
    "sourceIds": [275491],
    "destinationIds": [275492],
    "conditionalValues": ["yes"],
    "condition": "NOT_IN"
  }
]
```

### Example 2: Validation + Editability

**Input Logic**:
```
"Data will come from PAN validation. Non-Editable"
```

**Processing**:
1. **Parse**: Keywords ['validation', 'non-editable'], doc_type='PAN'
2. **Select Rules**:
   - STANDARD Rule #360 (Validate PAN)
   - actionType: MAKE_DISABLED
3. **Generate**:

```json
[
  {
    "actionType": "VERIFY_PAN",
    "processingType": "SERVER",
    "sourceIds": [275510],
    "destinationIds": [275511],
    // ... validation rule from Rule-Schemas.json
  },
  {
    "actionType": "MAKE_DISABLED",
    "processingType": "CLIENT",
    "sourceIds": [275511],
    "destinationIds": [275511]
  }
]
```

## Validation Strategy

### Unit Tests
- `test_logic_parser.py`: Test keyword/entity/condition extraction
- `test_field_matcher.py`: Test exact/fuzzy matching
- `test_rule_tree.py`: Test rule selection accuracy
- `test_rule_builders.py`: Test JSON generation

### Integration Tests
- `test_vendor_creation_bud.py`: Full pipeline test on Vendor Creation BUD
- Compare against `documents/json_output/vendor_creation_sample_bud.json`
- Validate all 330+ logic statements processed
- Check rule type distribution

### Manual Review
- Review generated rules for each panel
- Verify source/destination field mappings
- Check conditional logic correctness
- Validate actionType selections

## Success Criteria

1. **Coverage**: Process 100% of logic statements in Vendor Creation Sample BUD
2. **Accuracy**: 95%+ correct rule selection (measured against manual review)
3. **Determinism**: 80%+ handled by pattern-based approach (not LLM)
4. **Performance**: < 5 seconds processing time for Vendor Creation BUD
5. **Validation**: No unmatched field references
6. **Integration**: Seamless integration with extract_fields_complete.py output

## Edge Cases to Handle

1. **Multiple rules in one logic statement**: "visible and mandatory" → 2 rules
2. **If/else clauses**: Generate rules for both branches
3. **Reference tables**: Extract table IDs and column references
4. **Nested conditions**: Use LLM fallback
5. **Unmatched field names**: Fuzzy matching with manual review fallback
6. **Empty logic**: Skip field, no rules generated
7. **Complex workflows**: Break into atomic rules

## Verification Steps

### 1. Test Pattern Matching
```bash
python3 -c "
from rule_extraction_agent.matchers.deterministic import DeterministicMatcher
m = DeterministicMatcher()
print(m.match('Make visible if GST option is Yes'))
print(m.match('Perform PAN validation'))
print(m.match('Get data from OCR rule'))
print(m.match('mvi(fieldA) + mvi(fieldB)'))  # Should be skipped
"
```

### 2. Test Schema Lookup
```bash
python3 -c "
from rule_extraction_agent.schema_lookup import RuleSchemaLookup
s = RuleSchemaLookup()
print('PAN Validation:', s.find_by_action_and_source('VERIFY', 'PAN_NUMBER'))
print('Ordinals:', s.get_destination_ordinals(360))
print('GSTIN OCR:', s.find_by_action_and_source('OCR', 'GSTIN_IMAGE'))
"
```

### 3. Test destinationIds Mapping
```bash
python3 -c "
from rule_extraction_agent.schema_lookup import RuleSchemaLookup
from rule_extraction_agent.id_mapper import DestinationIdMapper

schema_lookup = RuleSchemaLookup()
mapper = DestinationIdMapper(schema_lookup)

# PAN Validation example (schema ID 360, 10 destination fields)
result = mapper.map_to_ordinals(360, {
    'Fullname': 275535,
    'Pan retrieval status': 275537,
    'Pan type': 275536,
    'Aadhaar seeding status': 275538
})
print('destinationIds:', result)
# Expected: [-1, -1, -1, 275535, -1, 275537, -1, 275536, 275538, -1]
"
```

### 4. Test Rule Builders
```bash
python3 -c "
from rule_extraction_agent.schema_lookup import RuleSchemaLookup
from rule_extraction_agent.id_mapper import DestinationIdMapper
from rule_extraction_agent.rule_builders.verify_builder import VerifyRuleBuilder
from rule_extraction_agent.rule_builders.ocr_builder import OcrRuleBuilder
import json

schema_lookup = RuleSchemaLookup()
id_mapper = DestinationIdMapper(schema_lookup)
verify_builder = VerifyRuleBuilder(schema_lookup, id_mapper)
ocr_builder = OcrRuleBuilder(schema_lookup)

# Build PAN VERIFY rule
verify_rule = verify_builder.build(
    schema_id=360,
    source_field_id=275534,
    field_mappings={'Fullname': 275535, 'Pan type': 275536},
    post_trigger_ids=[120188]
)
print('VERIFY Rule:', json.dumps(verify_rule, indent=2))

# Build PAN OCR rule
ocr_rule = ocr_builder.build(
    schema_id=344,
    upload_field_id=275533,
    output_field_id=275534,
    post_trigger_ids=[verify_rule.get('id')]
)
print('OCR Rule:', json.dumps(ocr_rule, indent=2))
"
```

### 5. End-to-End Test
```bash
python3 rule_extraction_agent.py \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --schema-rules "rules/Rule-Schemas.json" \
    --output "output/test_rules.json" \
    --verbose
```

### 6. Compare with Reference
- Compare generated rules with `documents/json_output/vendor_creation_sample_bud.json`
- Verify destinationIds ordinal positions are correct
- Check that -1 is used for unmapped ordinals
- Verify rule chaining (postTriggerRuleIds) is correct

```bash
python3 -c "
import json

# Load generated and reference
with open('output/test_rules.json') as f:
    generated = json.load(f)
with open('documents/json_output/vendor_creation_sample_bud.json') as f:
    reference = json.load(f)

# Compare VERIFY rules
gen_verify = [r for r in generated.get('rules', []) if r.get('actionType') == 'VERIFY']
ref_verify = []
for doc in reference.get('template', {}).get('documentTypes', []):
    for meta in doc.get('formFillMetadatas', []):
        for rule in meta.get('formFillRules', []):
            if rule.get('actionType') == 'VERIFY':
                ref_verify.append(rule)

print(f'Generated VERIFY rules: {len(gen_verify)}')
print(f'Reference VERIFY rules: {len(ref_verify)}')

# Check destinationIds array lengths
for rule in gen_verify:
    dest_ids = rule.get('destinationIds', [])
    print(f'Rule source={rule.get(\"sourceType\")}: destinationIds length={len(dest_ids)}')
"
```

---

## Summary of Changes

| File | Changes |
|------|---------|
| `.claude/agents/rule_extraction_coding_agent.md` | Add multi-stage matching architecture, schema lookup details, sourceIds/destinationIds explanation, rule-specific patterns, rules to ignore |
| `.claude/plans/plan.md` | Add schema_lookup.py module, id_mapper.py module, enhanced pipeline architecture, rule builders, verification steps, skip patterns |
| `rule_extraction_agent/schema_lookup.py` | NEW: Rule-Schemas.json query interface |
| `rule_extraction_agent/id_mapper.py` | NEW: Ordinal-to-index mapping for destinationIds |
| `rule_extraction_agent/matchers/pipeline.py` | NEW: Multi-stage matching coordinator |
| `rule_extraction_agent/matchers/llm_fallback.py` | ENHANCED: Include schema context in prompts |
| `rule_extraction_agent/rule_builders/verify_builder.py` | NEW: VERIFY rule builder with ordinal mapping |
| `rule_extraction_agent/rule_builders/ocr_builder.py` | NEW: OCR rule builder |

---

## Source/Destination Field Identification

When building rules, source and destination fields MUST be correctly identified. Follow this priority order:

### Priority 1: Lookup Rule-Schemas.json
```python
# Always check schema first
schema = find_schema(action="VERIFY", source="PAN_NUMBER")  # Schema ID 360
# Schema defines:
# - sourceFields: what inputs are needed
# - destinationFields: what outputs with ordinal positions
# - numberOfItems: array length for destinationIds
```

### Priority 2: Derive from BUD Field Logic
When schema doesn't exist or doesn't specify all mappings:

| Logic Pattern | Interpretation |
|---------------|----------------|
| "Perform X validation" | Current field is SOURCE |
| "Data will come from X validation" | Current field is DESTINATION |
| "store data in next fields" | Subsequent fields are DESTINATIONS |
| "if field 'X' is Y then visible" | X is SOURCE, current field is DESTINATION |
| "Get X from OCR rule" | Current file field is SOURCE, X text field is DESTINATION |

### Priority 3: Infer from Field Relationships
- FILE upload field + TEXT field with same name → OCR: FILE→TEXT
- DROPDOWN field + multiple fields with same visibility condition → DROPDOWN is SOURCE
- Fields with "Non-Editable" after validation mention → DESTINATIONS of VERIFY rule

### Building destinationIds Array
```python
# For VERIFY rules, destinationIds must match schema ordinal count
num_items = schema['destinationFields']['numberOfItems']  # e.g., 10 for PAN
dest_ids = [-1] * num_items  # Initialize with -1

# Map BUD fields to ordinal positions (ordinal - 1 = index)
for bud_field in matched_fields:
    ordinal = schema_field_ordinals[bud_field.name]
    dest_ids[ordinal - 1] = bud_field.id
```

---

## Troubleshooting Guide

### Issue: OCR → VERIFY Chains Missing
**Check**:
1. Are VERIFY rules being created for the OCR destination fields?
2. Is `link_ocr_to_verify_rules()` being called AFTER all rules are generated?
3. Is the OCR destinationIds[0] matching the VERIFY sourceIds?

**Solution**: Ensure rule linking happens as a final pass after all rules exist.

**Exception**: AADHAR_IMAGE and AADHAR_BACK_IMAGE don't need VERIFY chains - no Aadhaar verification schema exists.

### Issue: Rule Count Discrepancies

| Discrepancy | Likely Cause | Fix |
|-------------|--------------|-----|
| EXT_DROP_DOWN too high | Pattern too broad | Require explicit "external"/"reference table" keywords |
| EXT_DROP_DOWN too low | Missing Excel file detection | Add `.xlsx?` pattern matching |
| VALIDATION too high | Over-detecting format validation | Check field actually has validation requirement |
| MAKE_DISABLED too high | Not consolidating | Group by (sourceIds, condition, conditionalValues) |
| VERIFY missing | Pattern not matching BUD text | Check for "Perform X validation", "Validate X" variants |
| OCR missing | File upload fields not detected | Check field type is FILE and has OCR keywords |

### Issue: Incorrect destinationIds Structure
**For VERIFY rules**:
- destinationIds array MUST have exact length matching schema's numberOfItems
- Use -1 for ordinals that don't map to BUD fields
- Example: PAN_NUMBER has 10 ordinals, so array length = 10

**For OCR rules**:
- destinationIds contains the field(s) being populated
- For simple OCR (PAN_IMAGE): single destination
- For multi-field OCR (CHEQUEE): use ordinal mapping like VERIFY

### Issue: Rules on Wrong Field
**Visibility/Mandatory rules** go on the CONTROLLING field (the dropdown/checkbox that determines visibility), NOT on the controlled fields.

**Pattern**:
```
Field A (DROPDOWN): "Choose option"
Field B (TEXT): "if field 'Choose option' is yes then visible"

Rule placement: Field A (source), with destinationIds=[Field B ID]
NOT: Field B with sourceIds=[Field A ID]
```

### Issue: Missing Rules for Fields
Check these potential causes:
1. **Logic text not parsed**: Verify doc_parser extracts field.logic correctly
2. **Pattern not matching**: Add regex pattern variants
3. **Incorrectly skipped**: Check if field matches skip patterns (mvi, EXECUTE)
4. **Wrong panel assignment**: Verify panel grouping is correct

### Issue: API Validation Errors
When API returns 400 status:
1. Check JSON structure matches expected format exactly
2. Verify all required fields present on rules
3. Ensure sourceIds and destinationIds reference valid field IDs
4. Check conditionalValues format (must be string array)

---

## Rule Type Quick Reference

| Source Type | Schema ID | Dest Ordinals | Chain To |
|-------------|-----------|---------------|----------|
| PAN_IMAGE (OCR) | 344 | 4 | PAN_NUMBER VERIFY |
| PAN_NUMBER (VERIFY) | 360 | 10 | Visibility rules |
| GSTIN_IMAGE (OCR) | 347 | 11 | GSTIN VERIFY |
| GSTIN (VERIFY) | 355 | 21 | GSTIN_WITH_PAN |
| GSTIN_WITH_PAN (VERIFY) | - | 0 | - |
| CHEQUEE (OCR) | 269 | 7 | BANK_ACCOUNT_NUMBER |
| BANK_ACCOUNT_NUMBER (VERIFY) | 361 | 4 | - |
| MSME (OCR) | 214 | 6 | MSME_UDYAM_REG_NUMBER |
| MSME_UDYAM_REG_NUMBER (VERIFY) | 337 | 21 | - |
| CIN (OCR) | - | 1 | CIN_ID |
| CIN_ID (VERIFY) | 349 | 14 | - |
| AADHAR_IMAGE (OCR) | 359 | - | None |
| AADHAR_BACK_IMAGE (OCR) | 348 | 9 | None |

---

## Future Enhancements

1. **Inter-panel dependencies**: Handle cross-panel field references
2. **Expression syntax**: Support expr-eval expressions (mvi, mm, etc.)
3. **Rule optimization**: Merge redundant rules
4. **Confidence reporting**: Detailed confidence scores per rule
5. **Interactive mode**: Allow manual field matching confirmation
6. **Multi-BUD training**: Learn patterns from multiple BUDs

