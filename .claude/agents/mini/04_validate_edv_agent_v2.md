---
name: Validate EDV Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Populates params, source_fields, and destination_fields for Validate EDV rules. Validate EDV is a server-side validation rule that queries an EDV (External Data Value) table by a source field value and auto-populates multiple destination fields based on table columns. The destination fields map positionally to table columns, with -1 for skipped columns. This is distinct from the EDV dropdown agent which handles EXT_DROP_DOWN / EXT_VALUE rules with conditionList params. This agent handles both simple lookups (params is just a table name string) and filtered lookups (params is JSON with conditionList specifying filter conditions across multiple source fields).
---


# Validate EDV Agent

## Objectivecr

Populate `params`, `source_fields`, and `destination_fields` for all Validate EDV rules ("Validate EDV (Server)" and "Validate External Data Value (Client)"). Agent 02 (Source/Destination) intentionally leaves these fields empty for Validate EDV rules because they require reference table analysis to determine the correct column-to-field mapping. This agent fills in the gaps by:

1. Determining the correct EDV table name from the field's logic section and reference tables
2. Building the `params` — either a simple table name string or a JSON object with `conditionList` for filtered lookups
3. Populating `source_fields` — the field(s) whose values are sent to the EDV table for lookup
4. Populating `destination_fields` — mapping form fields positionally to EDV table columns, using `-1` for columns that don't map to any form field

## Input
FIELDS_JSON: $FIELDS_JSON
REFERENCE_TABLES: $REFERENCE_TABLES
LOG_FILE: $LOG_FILE

## Output
The same schema as input, but with Validate EDV rules having correctly populated `params`, `source_fields`, and `destination_fields`. Non-Validate-EDV rules are passed through unchanged.

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)
1) **ONLY** modify rules named "Validate EDV (Server)" or "Validate External Data Value (Client)". All other rules must be passed through **UNCHANGED**.
2) The `source_fields` for a Validate EDV rule is the field whose value is being looked up in the EDV table. This is usually the field the rule is placed on, but for filtered lookups there can be additional source fields.
3) The `destination_fields` array must be ordered **positionally** matching the EDV table columns. If a table column does not map to any form field, use `"-1"` in that position. If a column maps to a field, use that field's `variableName`.
4) **ALL** destination fields must exist in the field list provided in `$FIELDS_JSON`. Do **NOT** invent fields.
5) Table names in `params` should be **UPPERCASE** with underscores (e.g., `"COMPANY_CODE"`, `"PIN-CODE"`, `"IFSC"`). Derive the table name from the logic text and reference tables.
6) For **simple lookups** (single source field, no filtering conditions), `params` is just the table name string, e.g. `"COMPANY_CODE"`.
7) For **filtered lookups** (multiple source fields, conditional filtering), `params` is a JSON object with `param` (table name) and `conditionList` array.

---

## How Validate EDV Works

Validate EDV is a **server-side validation** rule that:
1. Takes one or more source field values from the form
2. Queries an External Data Value (EDV) table on the server
3. Returns matching row data
4. Auto-populates destination fields with values from the matched row's columns

### Key Differences from EDV Dropdown (Agent 03)
| Aspect | EDV Dropdown (Agent 03) | Validate EDV (This Agent) |
|--------|------------------------|---------------------------|
| Rule Names | "EDV Dropdown (Client)" | "Validate EDV (Server)", "Validate External Data Value (Client)" |
| Action Type | `EXT_DROP_DOWN` / `EXT_VALUE` | `VALIDATION` / `VERIFY` |
| Processing | Client-side | Server-side (usually) |
| Purpose | Populate dropdown options | Validate a value and auto-fill related fields |
| Params Format | `conditionList` with `ddType`, `criterias`, `da` | Simple string OR `{param, conditionList}` with condition filters |
| Destination | Usually empty (dropdown itself) | Multiple fields mapped positionally to table columns |
| Button | None | "Verify" (sometimes empty) |

### Rule Schema Details
- **"Validate EDV (Server)"** (Rule ID: 346): `action=VALIDATION`, `source=EXTERNAL_DATA_VALUE`, `processingType=SERVER`, 1 mandatory source field, unlimited destination fields
- **"Validate External Data Value (Client)"** (Rule ID: 196): `action=VERIFY`, `source=EXTERNAL_DATA_VALUE`, `processingType=CLIENT`, 2 source fields (1 optional + 1 mandatory), unlimited destination fields

---

## Params Structure

### Pattern 1: Simple String (Single Source, No Filter)
When a single field value is looked up directly in an EDV table with no additional filtering:

```
"params": "TABLE_NAME"
```

**Examples:**
- `"COMPANY_CODE"` — look up company code, return company details
- `"PIN-CODE"` — look up pin code, return city/district/state/country
- `"IFSC"` — look up IFSC code, return bank branch details
- `"COUNTRY"` — look up country code, return country info
- `"CURRENCY_COUNTRY"` — look up currency, return currency details

### Pattern 2: JSON with conditionList (Multiple Sources, Filtered Lookup)
When the lookup requires additional filtering conditions beyond the primary source field:

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

**Fields in conditionList:**
| Field | Purpose | Example |
|-------|---------|---------|
| `conditionNumber` | Which attribute/column number to filter on (1-based, but usually starts at 2 since attribute 1 is the primary lookup) | `2` |
| `conditionType` | Type of comparison | `"IN"` |
| `conditionValueType` | Data type of the condition value | `"TEXT"` |
| `conditionAttributes` | Which EDV attributes hold the filter values; format is `"attributeNvalue"` where N is the column number | `["attribute2value", "attribute3value"]` |
| `continueOnFailure` | Whether to continue if validation fails | `true` |
| `errorMessage` | Error message shown on validation failure | `"No data found!!"` |

**When to use filtered lookup:**
- Logic mentions filtering by multiple criteria (e.g., "based on Company Code AND Vendor Type")
- Multiple source fields need to be sent to the EDV table
- The logic mentions cross-referencing between fields from different parts of the form

---

## Destination Field Mapping with -1 Skipping

The `destination_fields` array maps **positionally** to the columns of the EDV table. Each position corresponds to a table column (a1, a2, a3, ...).

- If a column's data should populate a form field, put that field's `variableName` at that position
- If a column should be skipped (no form field needs it), put `"-1"` at that position

### Examples

**Simple 1:1 mapping (PIN-CODE table with 4 columns):**
```
EDV Table Columns: [Pin Code, City, District, State, Country]
                       a1       a2      a3       a4      a5
destination_fields: ["__city__", "__district__", "__state__", "__country__"]
```
Source field is the pin code field itself (a1 is the lookup key, not a destination). Destinations start from a2.

**Mapping with skips (VC_VENDOR_TYPES table with 5 columns):**
```
EDV Table Columns: [Code, Vendor Name, Type, Category, SubCategory]
                     a1      a2         a3      a4         a5
destination_fields: ["-1", "__vendor_name__", "-1", "__category__", "__subcategory__"]
```
Columns 1 and 3 don't map to any field, so `-1` is used.

**Sparse mapping (COMPANY_CODE_PURCHASE_ORGANIZATION, only need column 9):**
```
destination_fields: ["-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1", "__purchase_org__"]
```
Only the 9th column maps to a form field; all others are skipped.

### How to Determine the Mapping
1. Read the field's logic section to understand which fields get auto-populated after validation
2. Look at the reference table to understand column structure (a1, a2, a3, ...)
3. Match each column to a form field based on column name and logic description
4. If a column matches a form field, use that field's `variableName`; otherwise use `"-1"`

---

## Approach

<field_loop>

### 1. Read the logic section of the particular field
Understand the logic of the current field from $FIELDS_JSON.
Log: Append "Step 1: Read logic for field <field_name>" to $LOG_FILE

### 2. Identify all fields in the panel
Understand what all fields are given to you as input from $FIELDS_JSON, as destination fields must come from this list.

<rule_loop>

### 3. Check if current rule is a Validate EDV rule
Check whether the current rule is "Validate EDV (Server)" or "Validate External Data Value (Client)". If NOT, skip to the next rule — do not modify it.
Log: Append "Step 3: Rule <rule_name> on field <field_name> — is Validate EDV: yes/no" to $LOG_FILE

### 4. Determine the EDV table name
From the field's logic section and $REFERENCE_TABLES:
- Look for table references in logic (e.g., "table 1.3", "reference table", "EDV table", or explicit table names like "COMPANY_CODE")
- Match to a reference table from $REFERENCE_TABLES
- Determine the EDV table name (UPPERCASE with underscores or hyphens as appropriate)
Log: Append "Step 4: EDV table for <field_name>: <table_name>" to $LOG_FILE

### 5. Determine source fields
- The primary source field is the field the rule is placed on (the field being validated/verified)
- If the logic mentions filtering by other fields, add those as additional source fields
- All source fields must exist in the field list
Log: Append "Step 5: Source fields for <field_name>: <source_field_list>" to $LOG_FILE

### 6. Determine destination fields with positional mapping
- Read the reference table columns from $REFERENCE_TABLES
- For each column in the table, determine if a form field should be populated from it
- Build the destination array positionally: `variableName` for mapped columns, `"-1"` for skipped columns
- The first column is often the lookup key itself and usually maps to `-1` (since it's the source, not a destination)
Log: Append "Step 6: Destination fields for <field_name>: <destination_field_list>" to $LOG_FILE

### 7. Build params
- **Simple lookup** (1 source field, no conditions): `params` = table name string
- **Filtered lookup** (multiple source fields or conditional logic): `params` = JSON object with `param` (table name) and `conditionList`
Log: Append "Step 7: Params for <field_name>: <params_value>" to $LOG_FILE

</rule_loop>

</field_loop>

### 8. Create the output JSON
Assemble the final output JSON with all Validate EDV rules populated and all other rules passed through unchanged.
Log: Append "Step 8 complete: Created output JSON for all fields" to $LOG_FILE

---

## Input JSON Structure

## FIELDS_JSON
```json
[
    {
        "field_name": "FIELD_NAME_1",
        "type": "TEXT/EMAIL/ETC",
        "mandatory": true,
        "logic": "<logic_text>",
        "rules": [
            {
                "id": 1,
                "rule_name": "Validate EDV (Server)",
                "source_fields": [],
                "destination_fields": [],
                "_reasoning": "Left empty by source/destination agent for Validate EDV."
            },
            {
                "id": 2,
                "rule_name": "Some Other Rule",
                "source_fields": ["__fieldname1__"],
                "destination_fields": ["__fieldname2__"],
                "_reasoning": "Already populated by source/destination agent."
            }
        ],
        "variableName": "__fieldname1__"
    }
]
```

## REFERENCE_TABLES
This is the raw output from doc_parser's `reference_tables` attribute. The dispatcher will extract only tables referenced by the panel's fields.

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
                    "__pin_code__"
                ],
                "destination_fields": [
                    "__city__",
                    "__district__",
                    "__state__",
                    "__country__"
                ],
                "params": "PIN-CODE",
                "_reasoning": "PIN-CODE EDV table has 5 columns (Pin Code, City, District, State, Country). Source is the pin code field itself. Destinations map to columns a2-a5 (City, District, State, Country). Column a1 (Pin Code) is the lookup key, not a destination."
            }
        ],
        "variableName": "__pin_code__"
    },
    {
        "field_name": "Vendor Type",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "Select vendor type. On validation, vendor name, category, and sub-category are auto-populated from VC_VENDOR_TYPES table. Column 1 (Code) and Column 3 (Type) are not needed.",
        "rules": [
            {
                "id": 1,
                "rule_name": "Validate EDV (Server)",
                "source_fields": [
                    "__vendor_type__"
                ],
                "destination_fields": [
                    "-1",
                    "__vendor_name__",
                    "-1",
                    "__category__",
                    "__subcategory__"
                ],
                "params": "VC_VENDOR_TYPES",
                "_reasoning": "VC_VENDOR_TYPES table has 5 columns. Column 1 (Code) is the lookup key (-1). Column 2 (Vendor Name) maps to __vendor_name__. Column 3 (Type) not needed (-1). Column 4 (Category) and Column 5 (SubCategory) map to form fields."
            },
            {
                "id": 2,
                "rule_name": "EDV Dropdown (Client)",
                "source_fields": ["__vendor_type__"],
                "destination_fields": [],
                "params": {
                    "conditionList": [
                        {
                            "ddType": ["VC_VENDOR_TYPES"],
                            "criterias": [],
                            "da": ["a1"],
                            "criteriaSearchAttr": [],
                            "additionalOptions": null,
                            "emptyAddOptionCheck": null,
                            "ddProperties": null
                        }
                    ],
                    "__reasoning": "This is the dropdown rule, NOT a Validate EDV rule — passed through unchanged."
                },
                "_reasoning": "Dropdown rule passed through unchanged by this agent."
            }
        ],
        "variableName": "__vendor_type__"
    },
    {
        "field_name": "Purchase Organization",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "Based on Company Code and Vendor Type, look up purchase organization from COMPANY_CODE_PURCHASE_ORGANIZATION table. Only column 9 (Purchase Org) is needed.",
        "rules": [
            {
                "id": 1,
                "rule_name": "Validate EDV (Server)",
                "source_fields": [
                    "__company_code__",
                    "__vendor_type__",
                    "__purchase_organization__"
                ],
                "destination_fields": [
                    "-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1",
                    "__purchase_org_desc__"
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
                "_reasoning": "Filtered lookup: source fields are Company Code, Vendor Type, and Purchase Organization. The conditionList filters on attributes 4 and 9 of the COMPANY_CODE_PURCHASE_ORGANIZATION table. Only column 9 maps to a form field; columns 1-8 are skipped with -1."
            }
        ],
        "variableName": "__purchase_organization__"
    }
]
```
