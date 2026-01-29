---
name: Intra-Panel Field References Detection
allowed-tools: Read, Write
description: Detects and documents within-panel field dependencies in a single Business Understanding Document.
---


# Intra-Panel Field References Detection (Claude Code Prompt)

## Objective

Detect **intra-panel field dependencies** from pre-extracted BUD field data by analyzing the **logic** section of each field.
An intra-panel dependency exists when a field's **logic** references another field located in the **SAME panel**.

This output is **implementation-critical** for understanding local panel UI behavior and field interactions within a single panel.

This is a **deterministic analysis task** on pre-parsed data.

---

## Input

You will be provided with:
1. **Input File Path**: Path to a JSON file containing pre-extracted fields data for a SINGLE panel
2. **Output Directory**: Directory to save the analysis results

**First action**: Read the input JSON file using the Read tool.

## Input JSON Format

The input file contains pre-extracted fields data for a single panel in the following format:

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "file_path": "extraction/Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-01-24T14:30:00Z",
    "total_fields": 25
  },
  "panel_name": "PAN and GST Details",
  "fields": [
    {
      "field_name": "Please select GST option",
      "variable_name": "__please_select_gst_option__",
      "field_type": "EXTERNAL_DROPDOWN",
      "logic": "Dropdown values are Yes/No",
      "rules": "",
      "visibility_condition": "",
      "validation": "",
      "mandatory": true
    },
    {
      "field_name": "GSTIN",
      "variable_name": "__gstin__",
      "field_type": "TEXT",
      "logic": "if the field \"Please select GST option\" values is yes then visible and mandatory otherwise invisible and non-mandatory. Perform GSTIN validation.",
      "rules": "",
      "visibility_condition": "",
      "validation": "",
      "mandatory": false
    }
  ]
}
```

---

## Hard Constraints (Mandatory)

* Do **not** parse any documents - data is pre-extracted
* Do **not** create scripts or code files
* Do **not** scan directories or auto-discover files
* Use **only** the provided fields data from input
* Output **only** the JSON result file
* Abort immediately if input data is malformed
* **CRITICAL: Only analyze the `logic` field for intra-panel references**
* **CRITICAL: Only include references where BOTH source and target fields are in the SAME panel**

Any deviation = incorrect behavior.

---

## Variables

```text
OUTPUT_DIR    = extraction/intra_panel_output/<date_time>/
```

`<date_time>` format: `YYYY-MM-DD_HH-MM-SS`

Use the output directory provided in the prompt, or create one with current timestamp.

---

## Step 1: Build Lookup Index

From the provided `fields` array, create:

1. **Field name index** (case-insensitive) → maps to field object
2. **Variable name index** → maps to field object
3. **Partial name variations** → handle variations like "GST option", "Please select GST option"

---

## Step 2: Intra-Panel Reference Detection (CRITICAL - Read Carefully)

For each field in `fields`, analyze **ONLY** the `field.logic` text.

### Reference Detection Approach

Look for patterns in the logic text that reference other fields:
- Explicit field names in quotes: `"Please select GST option"`
- Field name mentions: `if GST option is selected`, `based on PAN field`
- Variable references: `__please_select_gst_option__`

### Understanding Operation Direction

When analyzing a field's logic, you must understand **what role the current field plays**:

1. **CONTROLLED_BY (current field is TARGET)** - The current field's behavior is CONTROLLED by another field:
   - Logic contains: "if X is selected", "based on X", "derived from X", "copy from X"
   - Example: Field "GSTIN" has logic "if 'Please select GST option' is yes then visible"
     - **Source**: "Please select GST option" (controls visibility)
     - **Target**: "GSTIN" (is controlled)
     - **operation_type**: "controlled_by"

2. **CONTROLS (current field is SOURCE)** - The current field CONTROLS another field (rare in logic text):
   - Logic contains: "controls X visibility", "sets X mandatory"
   - **operation_type**: "controls"

### Real Examples - CORRECT Interpretation:

| Field Being Analyzed | Logic Text | Source Field | Target Field | relationship_type | operation_type |
|---------------------|------------|--------------|--------------|-------------------|----------------|
| GSTIN | "if the field 'Please select GST option' values is yes then visible" | Please select GST option | GSTIN | visibility_control | controlled_by |
| Trade Name | "if the field 'Please select GST option' values is yes then visible" | Please select GST option | Trade Name | visibility_control | controlled_by |
| Pan Holder Name | "Data will come from PAN validation" | PAN | Pan Holder Name | data_dependency | controlled_by |
| Process Type | "IF India is selected in previous field then value is DOM IN" | Select the process type | Process Type | value_derivation | controlled_by |
| Vendor Domestic or Import | "If account group/vendor type is selected as ZDES then derived as Domestic" | Account Group/Vendor Type | Vendor Domestic or Import | value_derivation | controlled_by |
| Country | "If Select the process type field value is India then country is India" | Select the process type | Country | value_derivation | controlled_by |

---

## Intra-Panel Rule (CRITICAL)

**ONLY include references where BOTH source and target fields are in the SAME panel.**

Since all fields in the input belong to the same panel, verify that:
1. The source field name found in the logic EXISTS in the `fields` array
2. If the source field doesn't exist in this panel's fields array, EXCLUDE this reference (it's a cross-panel reference)

---

## Relationship Type Classification

| Type               | Keywords in Logic                              |
| ------------------ | ---------------------------------------------- |
| visibility_control | visible, hide, show, hidden, invisible, applicable, visible and mandatory |
| mandatory_control  | mandatory, required, non-mandatory             |
| value_derivation   | derive, derived, value is, default value, auto-derived, get from |
| data_dependency    | Data will come from, based on, copy from, fetched from |
| validation         | validate, verify, check, validation, perform validation |
| enable_disable     | enable, disable, editable, non-editable        |
| conditional        | if, when, based on (general conditional behavior) |
| clear_operation    | clear, reset                                   |
| other              | fallback                                       |

---

## Step 3: Output JSON

Filename:

```
<document_name>_<panel_name>_intra_panel_references.json
```

(Sanitize panel name: replace spaces with underscores, remove special characters)

**MANDATORY SCHEMA - Use this structure exactly, no deviations:**

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-01-24T14:30:00Z"
  },
  "panel_info": {
    "panel_name": "PAN and GST Details",
    "total_fields": 25,
    "fields_with_intra_panel_refs": 12,
    "fields_controlling_others": 3
  },
  "controlling_fields": [
    {
      "field_name": "Please select GST option",
      "variable_name": "__please_select_gst_option__",
      "field_type": "EXTERNAL_DROPDOWN",
      "controls_count": 10,
      "controlled_fields": ["GSTIN", "Trade Name", "Legal Name", "Reg Date", "Type", "Building Number", "Street", "City", "District", "State"]
    }
  ],
  "intra_panel_references": [
    {
      "source_field": {
        "field_name": "Please select GST option",
        "variable_name": "__please_select_gst_option__",
        "field_type": "EXTERNAL_DROPDOWN"
      },
      "target_field": {
        "field_name": "GSTIN",
        "variable_name": "__gstin__",
        "field_type": "TEXT"
      },
      "reference_details": {
        "matched_text": "Please select GST option",
        "location_found": "logic",
        "relationship_type": "visibility_control",
        "operation_type": "controlled_by",
        "raw_expression": "if the field \"Please select GST option\" values is yes then visible and mandatory otherwise invisible and non-mandatory"
      }
    },
    {
      "source_field": {
        "field_name": "PAN",
        "variable_name": "__pan__",
        "field_type": "TEXT"
      },
      "target_field": {
        "field_name": "Pan Holder Name",
        "variable_name": "__pan_holder_name__",
        "field_type": "TEXT"
      },
      "reference_details": {
        "matched_text": "PAN validation",
        "location_found": "logic",
        "relationship_type": "data_dependency",
        "operation_type": "controlled_by",
        "raw_expression": "Data will come from PAN validation. Non-Editable"
      }
    }
  ],
  "relationship_summary": {
    "visibility_control": 8,
    "mandatory_control": 5,
    "value_derivation": 3,
    "data_dependency": 4,
    "validation": 2,
    "enable_disable": 1,
    "conditional": 2,
    "clear_operation": 0,
    "other": 0
  },
  "dependency_chains": [
    {
      "root_field": "Please select GST option",
      "chain_length": 1,
      "affected_fields": ["GSTIN", "Trade Name", "Legal Name", "Reg Date", "Type", "Building Number", "Street", "City", "District", "State", "Pin Code"]
    }
  ]
}
```

**CRITICAL SCHEMA RULES:**
1. `intra_panel_references` must use nested objects: `source_field`, `target_field`, `reference_details`
2. `reference_details.operation_type` must be either "controlled_by" or "controls"
3. `source_field` is the field that CONTROLS behavior
4. `target_field` is the field that IS CONTROLLED
5. `controlling_fields` lists fields that control other fields (act as sources)
6. `dependency_chains` shows chains of field dependencies within the panel
7. **ZERO cross-panel references in output** - if a referenced field is not in this panel, exclude it

No additional files may be generated.

---

## Step 4: Final Console Summary

Print:

* Panel name analyzed
* Total fields in panel
* Fields with intra-panel refs (count)
* Total intra-panel relationships found
* Key controlling fields (fields that control multiple others)
* Relationship type distribution
* Output file location

---

## Enforcement

* No document parsing (data is pre-extracted)
* Exactly one output JSON file per panel
* No code generation or script creation
* No deviations from workflow
* **CRITICAL: Only intra-panel references (source and target in SAME panel)**
* **CRITICAL: Only analyze the `logic` field**
* **CRITICAL: Correctly identify source (controls) vs target (is controlled)**
* **CRITICAL: Include operation_type ("controlled_by" or "controls")**
* **CRITICAL: Use the exact JSON schema structure provided above**
* **Zero cross-panel references in output**

This is a **strict analysis command** on pre-provided data.

If the source field doesn't exist in the panel's field list, you are including a cross-panel reference. Stop and filter those out.
