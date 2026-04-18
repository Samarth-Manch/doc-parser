---
name: Validate EDV Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Places Validate EDV rules on dropdown fields and populates their params, source_fields, and destination_fields. Analyzes field logic and reference tables to determine if a dropdown needs a Validate EDV rule, then builds the complete rule with positional column-to-field mapping.
---


# Validate EDV Agent

## Objective

Determine which dropdown fields need a Validate EDV rule, place the rule, and populate its `params`, `source_fields`, and `destination_fields`. The Validate EDV rules will NOT be present in the input — this agent is responsible for both placing and fully populating them.

## Input
FIELDS_JSON: $FIELDS_JSON
REFERENCE_TABLES: $REFERENCE_TABLES
LOG_FILE: $LOG_FILE
ALL_PANELS_INDEX: $ALL_PANELS_INDEX (optional — provided only in cross-panel mode)

## Output
The same schema as input, but with Validate EDV rules **added** to dropdown fields that need them, fully populated with `params`, `source_fields`, and `destination_fields`. Pre-existing rules are passed through unchanged.

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)
1) Do **NOT** modify any pre-existing rules. All existing rules must be passed through **UNCHANGED**. This agent only **adds** new Validate EDV rules.
2) The Validate EDV (Server) rule is **almost always placed on the source field** — the field whose value triggers the EDV lookup. Identify which field is the source (the field that "affects" or "drives" the lookup) and place the rule **on that field**. The source field can be any type (DROPDOWN, TEXT, etc.), not just dropdowns.
3) **Multiple fields can be derived from a single Validate EDV rule**, but the derivation logic is often **spread across the destination fields' logic sections**, not on the source field itself. You must scan ALL fields' logic to find derivation mentions (e.g., "derived from X field through validation", "auto-populated based on X from EDV table") and **consolidate** them into a single Validate EDV rule placed on the source field.
4) The `source_fields` contains ALL fields involved in the EDV lookup trigger. Usually the field the rule is placed on, but filtered lookups and parent-child relationships can have additional source fields. If a parent-child dropdown relationship exists, the rule is placed on the **child dropdown**, and `source_fields` must include BOTH the parent field (lookup key / a1) AND the child field itself (the field the rule is placed on). In cross-panel mode, if the parent is from another panel, include its variableName from ALL_PANELS_INDEX.
5) The first column (a1) of the EDV table is **always the lookup key** and must be **skipped** in `destination_fields` — do NOT include a mapping for it. The `destination_fields` array starts from the **2nd column (a2)** onward. So if the EDV table has N columns, `destination_fields` must have exactly **N-1** entries. Use `"-1"` for unmapped columns, `variableName` for mapped columns.
6) **ALL** source and destination fields must exist in $FIELDS_JSON — unless ALL_PANELS_INDEX is provided (cross-panel mode), in which case source fields may also come from ALL_PANELS_INDEX. If the true source field (lookup key / a1) does NOT exist in $FIELDS_JSON, check ALL_PANELS_INDEX to resolve it. If ALL_PANELS_INDEX is also NOT provided, SKIP that Validate EDV rule entirely. **IMPORTANT**: Do NOT skip a Validate EDV rule merely because the cascading dropdown's parent (a1) is cross-panel. The Validate EDV fires when the CHILD dropdown value is selected — if the child field is in this panel and has intra-panel destination fields to derive, the rule MUST still be placed. Use the cross-panel parent's variableName from ALL_PANELS_INDEX in source_fields alongside the child field. Do **NOT** invent fields.
7) Table names in `params` should be **UPPERCASE** with underscores (e.g., `"COMPANY_CODE"`, `"PIN-CODE"`).
8) For **simple lookups** (single source, no filter), `params` = table name string.
9) For **filtered lookups** (multiple sources, conditional), `params` = JSON object with `param` and `conditionList`.

---

## Rule Construct (from Rule-Schemas.json)

When placing a Validate EDV rule, you MUST always use the following construct from Rule-Schemas.json. This is the canonical schema — do NOT deviate from it.

```json
{
    "name": "Validate EDV (Server)",
    "source": "EXTERNAL_DATA_VALUE",
    "action": "VALIDATION",
    "processingType": "SERVER",
    "applicableTypes": [],
    "sourceFields": {
        "numberOfItems": 1,
        "fields": [
            {
                "name": "Form Field",
                "ordinal": 1,
                "mandatory": true,
                "unlimited": false
            }
        ]
    },
    "destinationFields": {
        "numberOfItems": 1,
        "fields": [
            {
                "name": "Form Field",
                "ordinal": 1,
                "mandatory": false,
                "unlimited": true
            }
        ]
    },
    "params": {
        "paramType": "string",
        "jsonSchema": {
            "type": "object",
            "uiSchema": {},
            "properties": {
                "value": {
                    "title": "ExternalData metdatada",
                    "remoteEnum": "v2/company/{{companyId}}/external-data-metadata?page=0&size=1000&sort=id%2Cdesc&fetchAll=true&genericData=true&searchParam=",
                    "transformer": "*.name"
                }
            }
        }
    },
    "deleted": false,
    "validatable": false,
    "skipValidations": false,
    "conditionsRequired": false,
    "button": "Verify"
}
```

Key points from this construct:
- **rule_name** must always be `"Validate EDV (Server)"` (not "Validate External Data Value (Client)" or any other variant)
- **sourceFields**: At least 1 source field (the field(s) whose values trigger the lookup). For parent-child relationships, include both parent and child fields.
- **destinationFields**: 1 base destination field with `unlimited: true`, meaning multiple destination fields are allowed.
- **params**: Takes a string value (the EDV table name) or a JSON object with `param` and `conditionList` for filtered lookups.
- **button**: `"Verify"` — this rule creates a verification/validation button on the form.

---

## Params Structure

### Simple String (Single Source, No Filter)
```
"params": "TABLE_NAME"
```

### JSON with conditionList (Multiple Sources, Filtered Lookup)
```json
{
    "param": "TABLE_NAME",
    "conditionList": [
        {
            "conditionNumber": 2,
            "conditionType": "IN",
            "conditionValueType": "TEXT",
            "conditionAttributes": ["attribute4value", "attribute9value"],
            "continueOnFailure": true,
            "errorMessage": "No data found!!"
        }
    ]
}
```

| Field | Purpose |
|-------|---------|
| `conditionNumber` | Which column number to filter on (1-based, usually starts at 2) |
| `conditionType` | Type of comparison (e.g., `"IN"`) |
| `conditionValueType` | Data type of the condition value |
| `conditionAttributes` | EDV attributes holding filter values; format: `"attributeNvalue"` where **N is the actual column position in the EDV table** (e.g., if the filter field is in column 2 of the table, use `"attribute2value"`; if column 9, use `"attribute9value"`). N is NOT a sequential index — it must match the real column position in the reference table. |
| `continueOnFailure` | Whether to continue if validation fails |
| `errorMessage` | Error message on failure |

---

## Approach

### Pre-scan: Identify all fields and scan for EDV derivation relationships

Before processing individual fields, scan **ALL** fields in $FIELDS_JSON to build a complete picture of source-destination relationships:

1. **List all fields**: Note each field's `variableName`, `type`, `field_name`, and `logic`.
2. **Scan every field's logic for derivation mentions**: Look for keywords in each field's logic: "derive", "fetch", "auto fetch", "auto-populate", "lookup", "validate against table", "on validation", "will be populated", "through Validation from", "derived automatically through Validation", "through Validation", "based on", "depends on", "filtered by", "from Reference Table", "from EDV table".
3. **Identify source fields**: For each field that mentions being derived/auto-populated, determine **which field is the source** — the field whose value triggers the EDV lookup. The source is the field that "affects" this field, the field being validated against the EDV table. **IMPORTANT**: A field can be a source field for Validate EDV even if it already has an EDV Dropdown rule. The EDV Dropdown rule populates dropdown options; the Validate EDV rule performs a lookup and auto-fills related fields on selection. These are separate purposes — do NOT skip a source field just because it already has an EDV Dropdown rule with destination_fields. **CROSS-PANEL**: If the logic says the source field is from another panel (e.g., "dependent on Vendor Number from Vendor Details panel"), the true source is that cross-panel field. Read ALL_PANELS_INDEX to resolve its variableName. The lookup key (a1) of the reference table corresponds to this cross-panel field, NOT a field in the current panel.
4. **Group by source field**: Multiple destination fields may each mention being derived from the **same source field** via the **same EDV table**. Consolidate these into a single Validate EDV rule to be placed on that source field.
5. **Check derivability**: For each identified source field, verify that the derivation can actually be done via an EDV rule. If $REFERENCE_TABLES has a matching table, use it to confirm column mappings. If $REFERENCE_TABLES is empty or has no matching table, but the logic explicitly names an EDV table (e.g., "Reference Table- TABLE_NAME attribute N"), still proceed — use the table name and attribute numbers from the logic text to build the rule.

Log: Append "Pre-scan complete: Identified <N> potential Validate EDV rules. Source fields: <list>. Grouped destinations: <map>" to $LOG_FILE

---

<field_loop>

### 1. Check if this field was identified as a source field in the pre-scan
Using the pre-scan results, check if this field was identified as a **source field** for a Validate EDV rule. If this field is NOT a source field (i.e., it is only a destination or has no EDV relationship), skip to the next field.
Log: Append "Step 1: Field <field_name> is source field: yes/no" to $LOG_FILE

### 2. Read the logic of this source field and all its destination fields
Read the logic of the current source field AND the logic of all destination fields identified in the pre-scan. The derivation information is often written in the **destination fields' logic**, not the source field itself. Combine all relevant logic to get the full picture.
Log: Append "Step 2: Source field <field_name> has <N> destination fields: <list>" to $LOG_FILE

### 3. Check if this is a parent or child dropdown (if applicable)
If the source field is a dropdown, determine the relationship:
- **Independent**: No dependency on other dropdowns.
- **Parent**: Other dropdowns depend on this one.
- **Child**: Depends on a parent dropdown ("based on", "depends on", "filtered by"). Validate EDV rule must be on the **child**, not the parent.
If it is a parent-only field (no lookup/derivation on its own), the rule should be on the child instead — skip this field.
Log: Append "Step 3: Field <field_name> dropdown classification: Independent/Parent/Child" to $LOG_FILE

### 4. Confirm this field needs a Validate EDV rule
Based on Steps 1-3 and the pre-scan, confirm whether a Validate EDV rule should be **placed** on this source field. A Validate EDV rule is needed when:
- The field's value is used to look up / validate against an EDV/reference table AND auto-populate other fields from the result
- Destination fields' logic mentions "auto fetch", "derived from", "fetched from", "through validation", or references a specific table attribute (e.g., "attribute N") for auto-population
- A Validate EDV rule is needed **even if the field already has an EDV Dropdown rule**. The two rules serve different purposes — EDV Dropdown populates the dropdown options, while Validate EDV performs the lookup and auto-fills related fields on selection. Do NOT skip a field just because EDV Dropdown already has destination_fields.

**Cross-panel source handling**: If the lookup key (a1) is a field from another panel, use ALL_PANELS_INDEX to resolve its variableName and include it in source_fields. The rule is still placed on the child dropdown field in THIS panel. Only SKIP if ALL_PANELS_INDEX is NOT provided AND the lookup key cannot be resolved. Do NOT skip when the child field itself is in this panel and has intra-panel destinations to derive — the cascading dropdown source being cross-panel does NOT make the Validate EDV rule cross-panel.

If NOT needed, skip to the next field — leave existing rules unchanged.
Log: Append "Step 4: Field <field_name> needs Validate EDV: yes/no. Reason: <reason>" to $LOG_FILE

### 5. Determine the EDV table name
From logic and $REFERENCE_TABLES:
- Look for table references in logic (e.g., "table 1.3", "COMPANY_CODE", "PIN-CODE", "Reference Table- TABLE_NAME")
- If $REFERENCE_TABLES has a matching table, use it to confirm column mappings
- If $REFERENCE_TABLES is empty or has no matching table, extract the table name directly from the logic text (e.g., "Reference Table- VC_BASIC_DETAILS" → table name is `VC_BASIC_DETAILS`)
- Derive the table name in UPPERCASE
Log: Append "Step 5: EDV table for <field_name>: <table_name>" to $LOG_FILE

### 6. Determine source fields
- Primary source field = the field whose value is the lookup key (a1) for the EDV table
- In standard (intra-panel) mode: this is usually the field the rule is placed on
- **In cross-panel mode**: if the lookup key (a1) is a field from another panel (identified in pre-scan step 3), use that cross-panel field's variableName from ALL_PANELS_INDEX as the source field. The rule is still placed on the field in THIS panel that triggers or benefits from the lookup, but source_fields references the actual lookup key field.
- **IMPORTANT — child dropdown source fields**: When the rule is placed on a child dropdown field and the parent/lookup key is a different field (whether cross-panel or intra-panel), `source_fields` MUST include BOTH: (1) the parent/lookup key field (a1), AND (2) the child field itself (the field the rule is placed on). The child field is needed because its selection triggers the validation lookup. Example: if Vendor Number (a1) is the parent and Company Code (a2) is the child, source_fields = [vendor_number_var, company_code_var].
- If logic mentions filtering by additional fields, add those as additional source fields
- Source fields must exist in $FIELDS_JSON or ALL_PANELS_INDEX (cross-panel)
Log: Append "Step 6: Source fields for <field_name>: <source_field_list>" to $LOG_FILE

### 7. Determine destination fields with positional column mapping
Using the reference table from Step 5, the pre-scan results, and the combined logic from Step 2:

**If $REFERENCE_TABLES has the matching table:**
1. Read table column structure (`a1`, `a2`, `a3`, ...)
2. **Skip the first column (a1)** — it is always the lookup key and is never included in destination fields
3. Starting from `a2`, for each remaining column: mapped column = field's `variableName`, unmapped column = `"-1"`
4. The resulting array has exactly **N-1** entries (where N = total EDV columns). For example, a 5-column EDV table produces exactly 4 destination fields (mapping a2→a5).

**If $REFERENCE_TABLES is empty or has no matching table:**
1. Determine the total number of columns from the highest attribute number mentioned in the logic across all destination fields (e.g., if logic mentions "attribute 14", the table has at least 14 columns)
2. **Skip position 1 (a1)** — it is the lookup key
3. Build the destination array from position 2 to N: place each destination field's `variableName` at the position matching its attribute number, fill all other positions with `"-1"`

**Common rules:**
5. All variableNames must exist in the field list
6. Include ALL destination fields gathered from the pre-scan — remember that derivation logic is spread across multiple fields' logic sections
Log: Append "Step 7: Destination fields for <field_name>: <destination_array> (skipped a1 lookup key, N-1 entries)" to $LOG_FILE

### 8. Build the params
- **Simple lookup** (1 source field, no conditions): `params` = table name string
- **Filtered lookup** (multiple source fields, conditional): `params` = JSON with `param` and `conditionList`
- **CRITICAL for conditionAttributes**: The `"attributeNvalue"` format uses N = the **actual column position in the EDV table**, NOT a sequential index. For example, if the filter field corresponds to column 2 (a2) in the reference table, use `"attribute2value"`. If column 5, use `"attribute5value"`. Always derive N from the field's actual attribute/column number in the reference table.
Log: Append "Step 8: Params for <field_name>: <params_value>" to $LOG_FILE

### 9. Place the Validate EDV rule on the source field and fill in the details
Add a new Validate EDV rule object to the **source field's** `rules` array using the **Rule Construct** defined above. The rule must have:
- `rule_name`: Always `"Validate EDV (Server)"` (this is the canonical name from Rule-Schemas.json — do NOT use any other variant)
- `source_fields` from Step 6
- `destination_fields` from Step 7
- `params` from Step 8
- `_reasoning` with explanation referencing table columns, source field, and all destination field mappings

All existing rules on the field are kept **unchanged**. The Validate EDV rule is **added** alongside them.
Log: Append "Step 9: Placed Validate EDV rule on source field <field_name> with <N> source fields, <M> destination fields" to $LOG_FILE

</field_loop>

### 10. Create the output JSON
Assemble final output JSON. Verify all placed Validate EDV rules have non-empty `source_fields`, `destination_fields`, and `params`. All pre-existing rules are unchanged.
Log: Append "Step 10 complete: Created output JSON" to $LOG_FILE

---

## Input JSON Structure

## FIELDS_JSON
```json
[
    {
        "field_name": "FIELD_NAME_1",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "<logic_text>",
        "rules": [
            {
                "id": 1,
                "rule_name": "EDV Dropdown (Client)",
                "source_fields": ["_fieldname1_"],
                "destination_fields": [],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "_fieldname1_"
    },
    {
        "field_name": "FIELD_NAME_2",
        "type": "TEXT",
        "mandatory": true,
        "logic": "<logic_text>",
        "rules": [
            {
                "id": 1,
                "rule_name": "Some Other Rule",
                "source_fields": ["_fieldname2_"],
                "destination_fields": ["_fieldname3_"],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "_fieldname2_"
    }
]
```

## REFERENCE_TABLES
```json
[
    {
        "attributes/columns": {
            "a1": "Pin Code",
            "a2": "City",
            "a3": "District",
            "a4": "State",
            "a5": "Country"
        },
        "sample_data": [
            ["110001", "New Delhi", "Central Delhi", "Delhi", "India"],
            ["400001", "Mumbai", "Mumbai City", "Maharashtra", "India"]
        ],
        "source_file": "oleObject5.xlsx",
        "sheet_name": "Sheet1",
        "table_type": "reference",
        "source": "excel"
    }
]
```

---

## Output JSON Structure
```json
[
    {
        "field_name": "Pin Code",
        "type": "TEXT",
        "mandatory": true,
        "logic": "Enter pin code. On validation, city, district, state, and country will be auto-populated from the PIN-CODE EDV table.",
        "rules": [
            {
                "id": 1,
                "rule_name": "Validate EDV (Server)",
                "source_fields": [
                    "_pincode_"
                ],
                "destination_fields": [
                    "_city_",
                    "_district_",
                    "_state_",
                    "_country_"
                ],
                "params": "PIN-CODE",
                "_reasoning": "PIN-CODE EDV table has 5 columns. Source is pin code field. Destinations map to a2-a5. Column a1 is the lookup key, not a destination."
            }
        ],
        "variableName": "_pincode_"
    },
    {
        "field_name": "Vendor Type",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "Select vendor type. On validation, vendor name, category, and sub-category are auto-populated from VC_VENDOR_TYPES table.",
        "rules": [
            {
                "id": 1,
                "rule_name": "Validate EDV (Server)",
                "source_fields": [
                    "_vendortype_"
                ],
                "destination_fields": [
                    "_vendorname_",
                    "-1",
                    "_category_",
                    "_subcategory_"
                ],
                "params": "VC_VENDOR_TYPES",
                "_reasoning": "VC_VENDOR_TYPES has 5 columns. Column a1 is the lookup key (skipped). Destinations start from a2: a2→vendor_name, a3→not needed (-1), a4→category, a5→subcategory. Total 4 destination fields."
            },
            {
                "id": 2,
                "rule_name": "EDV Dropdown (Client)",
                "source_fields": ["_vendortype_"],
                "destination_fields": [],
                "params": {},
                "_reasoning": "Dropdown rule passed through unchanged by this agent."
            }
        ],
        "variableName": "_vendortype_"
    },
    {
        "field_name": "Purchase Organization",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "Based on Company Code and Vendor Type, look up purchase organization from COMPANY_CODE_PURCHASE_ORGANIZATION table.",
        "rules": [
            {
                "id": 1,
                "rule_name": "Validate EDV (Server)",
                "source_fields": [
                    "_companycode_",
                    "_vendortype_",
                    "_purchaseorganization_"
                ],
                "destination_fields": [
                    "-1", "-1", "-1", "-1", "-1", "-1", "-1",
                    "_purchaseorgdesc_"
                ],
                "params": {
                    "param": "COMPANY_CODE_PURCHASE_ORGANIZATION",
                    "conditionList": [
                        {
                            "conditionNumber": 2,
                            "conditionType": "IN",
                            "conditionValueType": "TEXT",
                            "conditionAttributes": ["attribute4value", "attribute9value"],
                            "continueOnFailure": true,
                            "errorMessage": "No data found!!"
                        }
                    ]
                },
                "_reasoning": "Filtered lookup with 3 source fields. Table has 9 columns. Column a1 is lookup key (skipped). Destinations start from a2: columns a2-a8 not needed (-1), a9→purchase_org_desc. Total 8 destination fields."
            }
        ],
        "variableName": "_purchaseorganization_"
    }
]
```
