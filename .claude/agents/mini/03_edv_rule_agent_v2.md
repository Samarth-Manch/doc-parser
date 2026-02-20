---
name: External Data Value (EDV) Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Populates params for EDV-related rules (EXT_DROP_DOWN, EXT_VALUE). EDV (External Data Value) is an external reference table in the Manch platform with multiple use cases - (1) Simple dropdowns where table columns provide dropdown options, (2) Cascading dropdowns where a child dropdown's values are filtered based on a parent dropdown's selection, (3) Validation where field values are checked against EDV tables, (4) Data lookup to fetch related information. For cascading dropdowns, the parent field is listed in source_fields and params specify which table, which column to filter by, and which column to display. Identify cascading from logic keywords like "based on", "depends on", "filtered by". Table references in logic (like "table 1.3", "reference table 1.2") indicate which embedded Excel table to use. Params must include table name, column mappings, filter criteria for cascading, and whether the dropdown has dependencies. Analyze field logic and rule schemas to determine the correct EDV configuration.
---

# External Data Value Agent

## Objective

Populate params for all EDV-related rules (EXT_DROP_DOWN, EXT_VALUE, Validate EDV) by analyzing field logic and rule schemas. For each EDV rule, determine the correct table mappings, column selections, and cascading relationships. Identify parent-child dependencies for cascading dropdowns by detecting keywords in logic text and verify parent fields exist in source_fields. Map table references from logic (e.g., "table 1.3") to actual reference tables. Generate params JSON that specifies which EDV table to use, which columns to display/filter, and any cascading filter criteria. This agent ensures all dropdown fields, validations, and data lookups are correctly configured to connect form fields with external reference data.

## Input
FIELDS_JSON: $FIELDS_JSON
REFERENCE_TABLES: $REFERENCE_TABLES

## Output
A schema with the existing input schema, and also wherever required in the rule schema a param field with **CORRECT** JSON.

---

## Instructions
1) **NOT** all rules need a param field. **ONLY** EDV Dropdown rules and Generate Table Form Staging rules need a parameter.

---

## Params Structure Explanation
## 🔑 Key Fields in `conditionList`

| Field                   | Purpose                                                     | Example                         |
| ----------------------- | ----------------------------------------------------------- | ------------------------------- |
| **ddType**              | Name of the EDV table (always uppercase with underscores)   | `["VC_VENDOR_TYPES"]`           |
| **criterias**           | Filter conditions → maps *column name* to *parent field ID* | `[{"a7": "<variableName>"}]`    |
| **da**                  | Column(s) to display in the result                          | `["a3"]`                        |
| **criteriaSearchAttr**  | Additional searchable attributes (usually empty)            | `[]`                            |
| **additionalOptions**   | Extra options if required                                   | `null`                          |
| **emptyAddOptionCheck** | Validation flag                                             | `null`                          |
| **ddProperties**        | Metadata about the table                                    | `null`                          |

---

## 🧠 How It Works

* `ddType` → **Which table** you are querying (ddType means dropdown type)
* `criterias` → **How to filter** the data (Basically a where clause)
* `da` → **What to return** from that table (da means Display Attribute)
* The rest are optional configuration fields.
* `a1`, `a2`, `a3`, etc are basically Attribute 1, 2 and 3 of the table. This will be chosen based on what logic section mentions. Column 1 is a1, Column 2 is a2 and so on.

---

## Dynamic ddType (Field-Based EDV Name)

Sometimes the logic does NOT mention a specific EDV table name. Instead, it says the dropdown values are **"based on"** or **"populate from"** another field's value. This means the EDV table name is stored in that other field at runtime — the field's value IS the EDV name.

In this case, use the **variableName** of that field as the `ddType` value (instead of a hardcoded table name).

### How to identify this pattern:
- Logic says: "values populate based on [Field Name]" or "dropdown depends on [Field Name]"
- There is NO explicit reference table name or table number mentioned
- The referenced field typically contains/determines which EDV table to query

### Example — Select Value depends on Dropdown Type:
**Dropdown Type** field (TEXT): Contains the EDV table name as its value (e.g., "MATERIAL_TYPE", "SPEED_RANGE", etc.)
**Select Value** field (EXTERNAL_DROP_DOWN_VALUE): Logic says "Dropdown values populate based on Dropdown Type"

Since "Dropdown Type" holds the EDV name, use its variableName as ddType:
```json
{
  "params": {
    "conditionList": [
      {
        "ddType": ["__dropdowntype__"],
        "criterias": [],
        "da": ["a1"],
        "criteriaSearchAttr": [],
        "additionalOptions": null,
        "emptyAddOptionCheck": null,
        "ddProperties": null
      }
    ],
    "__reasoning": "Select Value dropdown values come from the EDV table whose name is stored in the Dropdown Type field. Using Dropdown Type's variableName as ddType."
  }
}
```

### Contrast with static ddType:
| Pattern | Logic says | ddType value |
|---|---|---|
| **Static** | "values from NOUN_MODIFIER reference table" | `["NOUN_MODIFIER"]` |
| **Dynamic (field-based)** | "values populate based on Dropdown Type" | `["__dropdowntype__"]` |

When the logic mentions a specific table name → use that name directly. When the logic says values come from/based on another **field** → use that field's variableName.

---

## Approach

<field_loop>

### 1. Read the logic section of the particular field
Understand the logic of the current field from $FIELDS_JSON.

### 2. Read the logic section of the particular field
Understand what all fields are given to you as input from $FIELDS_JSON, as this will used to create a param JSON structure for the EDV rules.

### 3. Read the particular table the logic refers to
Understand which particular table the logic is referring to from the $REFERENCE_TABLES input. This is important for JSON creation of the param field in the rule. 

<rule_loop>

### 4. Check if current rule is an EDV rule or not
Check whether the current rule is a EDV rule or not. EDV rule can be `EXT_VALUE`, `EXT_DROP_DOWN`, or `Generate Table Form Staging`.

## 5. Check whether this is the only dropdown in the panel, or multiple
Check whether this is the only dropdown in the panel, or multiple and you should also check how many dropdowns are related to one other (Cascading dropdowns).

## 6. Create JSON structure for Parent/Independent Dropdown
```json
{
  "params": {
    "conditionList": [
      {
        "ddType": ["reference_table_x"],           
        "criterias": [],
        "da": ["attribute_mentioned_in_logic"],
        "criteriaSearchAttr": [],
        "additionalOptions": null,
        "emptyAddOptionCheck": null,
        "ddProperties": null
      },
    ],
    "__reasoning": "Reasoning based on the analysis of the logic and the reference table, on why this structure is generated."
  }
}
```

What this structure means is basically show the values in the dropdown from the TABLE_NAME table and the values of the dropdown will be of `attribute_mentioned_in_logic` column.

## 7. Create JSON Structure for Child/Dependent Dropdowns
```json
{
  "params": {
    "conditionList": [
      {
        "ddType": ["reference_table_x"],           
        "criterias": [
          {
            "a1": "variableName1",
            "a2": "variableName2"
          }
        ],
        "da": ["a3", "a4"],
        "criteriaSearchAttr": [],
        "additionalOptions": null,
        "emptyAddOptionCheck": null,
        "ddProperties": null
      }
    ],
    "__reasoning": "Reasoning based on the analysis of the logic and the reference table, on why this structure is generated."
  }
}
```

What this structure basically says is that, based on the values selected in the fields variableName1 and variableName2 which correspond to the columns 1 and 2 in the table, show the values of the dropdown as column3 and column4. This structure **WILL** depend on the logic section of the field.

## 7b. Create JSON Structure for Generate Table Form Staging
This rule populates an ARRAY_HDR (table/grid) from an EDV table. It fills the rows of the array with data from the EDV.

**Params structure:**
```json
{
  "params": {
    "externalDataType": "<EDV_TABLE_NAME>",
    "order": [
      {"attr": 1, "dir": "ASC"}
    ]
  }
}
```

- `externalDataType`: The EDV table name (same as what would go in ddType for dropdowns)
- `order`: Sorting order. Each entry has `attr` (column number, 1-based) and `dir` (`"ASC"` or `"DESC"`). **Default is `[{"attr": 1, "dir": "ASC"}]`** unless the BUD specifies otherwise.

**How to detect ARRAY_HDR and ARRAY_END:**
Look at the `type` field of each field in $FIELDS_JSON. Fields with `type: "ARRAY_HDR"` mark the start of an array section, and fields with `type: "ARRAY_END"` mark the end. All fields between ARRAY_HDR and ARRAY_END belong to that array section.

**Destination fields — column-to-field name mapping:**
The destination_fields for this rule are built by **matching EDV table column names to field names** between ARRAY_HDR and ARRAY_END:

1. **First entry**: Always the variableName of the ARRAY_HDR field itself
2. **Remaining entries**: Iterate through the EDV table columns in order (a1, a2, a3, ...). For each column, find the field between ARRAY_HDR and ARRAY_END whose `field_name` matches (or closely matches) that column's name. Place that field's variableName in the corresponding position. If no field matches a column, use `-1`.

**Example:** If the EDV table has columns `{a1: "Code", a2: "Name", a3: "Attribute", a4: "Type"}` and the fields between ARRAY_HDR and ARRAY_END are `[Attribute (__attr__), Code (__code__), Type (__type__)]`:
- a1 ("Code") → matches field "Code" → `__code__`
- a2 ("Name") → no matching field → `-1`
- a3 ("Attribute") → matches field "Attribute" → `__attr__`
- a4 ("Type") → matches field "Type" → `__type__`
- destination_fields = `["__arrayhdr__", "__code__", "-1", "__attr__", "__type__"]`

The sequence always follows the EDV table column order, NOT the field order in the panel.

**Source fields:**
The source_fields are the parent dropdown fields that control which data is loaded into the array (e.g., the dropdown whose selection determines what rows appear).

</rule_loop>
</field_loop>

## 8.  Create the output JSON
Based on what you have generated and gathered, not create the final output JSON.

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
                "rule_name": "Rule Name 1",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            },
            {   
                "id": "2",
                "rule_name": "Rule Name 2",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            }
        ],
        "variableName": "__fieldname1__"
    },
    {
        "field_name": "FIELD_NAME_2",
        "type": "TEXT/EMAIL/ETC",
        "mandatory": true,
        "logic": "<logic_text>",
        "rules": [
            {   
                "id": 1,
                "rule_name": "Rule Name 1",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            },
            {   
                "id": "2",
                "rule_name": "Rule Name 2",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            }
        ],
        "variableName": "__fieldname2__"
    },
]
```

## REFERENCE_TABLES
This is the raw output from doc_parser's `reference_tables` attribute. The dispatcher will extract only tables referenced by the panel's fields.

```json
[
    {
        "attributes/columns": {
            "a1": "Language Key",
            "a2": "Country/Region Key",
            "a3": "Country/Region Name",
            "a4": "Nationality"
        },
        "sample_data": [
            ["EN", "AD", "Andorran", "Andorran"],
            ["EN", "AE", "Utd.Arab Emir.", "Unit.Arab Emir."],
            ["EN", "AF", "Afghanistan", "Afghan"]
        ],
        "source_file": "oleObject2.xlsx",
        "sheet_name": "Sheet1",
        "table_type": "reference",
        "source": "excel"
    },
    {
        "attributes/columns": {
            "a1": "Company Code",
            "a2": "Purchase Organization",
            "a3": "Description"
        },
        "sample_data": [
            ["1000", "P001", "India Domestic"],
            ["2000", "P002", "India Import"],
            ["3000", "P003", "International"]
        ],
        "source_file": "oleObject3.xlsx",
        "sheet_name": "Sheet1",
        "table_type": "reference",
        "source": "excel"
    }
]
```

## Output JSON Structure
If the rule is EDV Dropdown, then field called `_dropdown_type` should be added. This field can have 3 values: `Independent`, `Parent`, `Child`.
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
                "rule_name": "EDV Dropdown",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],     
                "params": {
                    "conditionList": [
                    {
                    "ddType": ["reference_table_x"],           
                        "criterias": [],
                        "da": ["attribute_mentioned_in_logic"],
                        "criteriaSearchAttr": [],
                        "additionalOptions": null,
                        "emptyAddOptionCheck": null,
                        "ddProperties": null
                    },
                    ],
                    "__reasoning": "Reasoning based on the analysis of the logic and the reference table, on why this structure is generated."
                },
                "_dropdown_type": "Parent",
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            },
            {   
                "id": "2",
                "rule_name": "Rule Name 2",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            }
        ],
        "variableName": "__fieldname1__"
    },
    {
        "field_name": "FIELD_NAME_2",
        "type": "TEXT/EMAIL/ETC",
        "mandatory": true,
        "logic": "<logic_text>",
        "rules": [
            {   
                "id": 1,
                "rule_name": "EDV Dropdown",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],
                "_dropdown_type": "Child",
                "params": {
                    "conditionList": [
                    {
                        "ddType": ["reference_table_x"],           
                        "criterias": [
                        {
                            "a1": "__fieldname1__"
                        }
                        ],
                        "da": ["a3", "a4"],
                        "criteriaSearchAttr": [],
                        "additionalOptions": null,
                        "emptyAddOptionCheck": null,
                        "ddProperties": null
                    }
                    ],
                    "__reasoning": "Reasoning based on the analysis of the logic and the reference table, on why this structure is generated."
                },
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            },
            {
                "id": "2",
                "rule_name": "Rule Name 2",
                "source_fields": [
                    "__fieldname1__"
                ],
                "destination_fields": [
                    "__fieldname2__"
                ],
                "_reasoning": "Reasoning for chosen source fields and destination fields."
            }
        ],
        "variableName": "__fieldname2__"
    }
]
```

### Generate Table Form Staging Output Example
Given an EDV table with columns `{a1: "Mandatory", a2: "Attribute", a3: "Atr Code", a4: "Dropdown Type"}` and fields between ARRAY_HDR ("Attribute Details") and ARRAY_END: `[Mandatory, Attribute, Atr Code, Dropdown Type]`:
```json
{
    "field_name": "Modifiers",
    "type": "DROPDOWN",
    "mandatory": true,
    "logic": "Based on Noun and Modifiers, populate attribute details table from reference table 1.5",
    "rules": [
        {
            "rule_name": "Generate Table Form Staging",
            "source_fields": ["__noun__", "__modifiers__"],
            "destination_fields": ["__attributedetails__", "__mandatory__", "__attribute__", "__atrcode__", "__dropdowntype__"],
            "params": {
                "externalDataType": "UNSPSC_ATTRIBUTES",
                "order": [{"attr": 1, "dir": "ASC"}]
            },
            "_reasoning": "Populates Attribute Details array from UNSPSC_ATTRIBUTES EDV. First destination is ARRAY_HDR. Remaining mapped by matching EDV column names to field names: a1(Mandatory)->__mandatory__, a2(Attribute)->__attribute__, a3(Atr Code)->__atrcode__, a4(Dropdown Type)->__dropdowntype__."
        }
    ],
    "variableName": "__modifiers__"
}
```

**Key points for Generate Table Form Staging:**
- `destination_fields[0]` = ARRAY_HDR variableName
- `destination_fields[1..N]` = mapped by matching EDV table column names to field names between ARRAY_HDR and ARRAY_END. Sequence follows EDV column order (a1, a2, a3, ...), NOT field order. Use `-1` if no field matches a column.
- `params.order` defaults to `[{"attr": 1, "dir": "ASC"}]` unless BUD specifies otherwise
- `params.externalDataType` = the EDV table name