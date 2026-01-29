---
name: Inter-Panel Field References Detection
allowed-tools: Read, Write
description: Detects and documents cross-panel field dependencies in a single Business Understanding Document.
---


# Inter-Panel Field References Detection (Claude Code Prompt)

## Objective

Detect **cross-panel field dependencies** from pre-extracted BUD field data by analyzing the **logic** section of each field.
A cross-panel dependency exists when a field's **logic** references a field located in a **different panel**.

This output is **implementation-critical** for understanding global UI behavior.

This is a **deterministic analysis task** on pre-parsed data.

---

## Input

You will be provided with:
1. **Input File Path**: Path to a JSON file containing pre-extracted fields data
2. **Output Directory**: Directory to save the analysis results

**First action**: Read the input JSON file using the Read tool.

## Input JSON Format

The input file contains pre-extracted fields data in the following format:

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "file_path": "extraction/Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-01-24T14:30:00Z",
    "total_fields": 85,
    "total_panels": 6
  },
  "panels": ["Initiator Panel", "SPOC Panel", "Approver Panel"],
  "fields_by_panel": {
    "Initiator Panel": [
      {
        "field_name": "Vendor Type",
        "variable_name": "__vendor_type__",
        "field_type": "DROPDOWN",
        "logic": "mvi(__approval_level__) if value = 'External'",
        "rules": "",
        "visibility_condition": "",
        "validation": "",
        "mandatory": true,
        "panel": "Initiator Panel"
      }
    ]
  }
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
* **CRITICAL: Only analyze the `logic` field for cross-panel references**

Any deviation = incorrect behavior.

---

## Variables

```text
OUTPUT_DIR    = extraction/inter_panel_output/<date_time>/
```

`<date_time>` format: `YYYY-MM-DD_HH-MM-SS`

Use the output directory provided in the prompt, or create one with current timestamp.

---

## Step 1: Build Lookup Indexes

From the provided `fields_by_panel` data, create:

1. **Field name index** (case-insensitive) → maps to field object with panel info
2. **Variable name index** → maps to field object with panel info
3. **Panel name variations** → map variations like "basic detail panel", "Basic Details", "basic details" to the canonical panel name

---

## Step 2: Cross-Panel Reference Detection (CRITICAL - Read Carefully)

For each field in `fields_by_panel`, analyze **ONLY** the `field.logic` text.

**IMPORTANT: Determine SOURCE and TARGET correctly based on the logic semantics:**

### Understanding Operation Direction

When analyzing a field's logic, you must understand **what role the current field plays**:

1. **INCOMING reference (current field is TARGET)** - The current field RECEIVES data or is CONTROLLED BY another field:
   - Logic contains: "Copy from X", "derived from X", "get from X", "based on X panel", "if X is selected"
   - Example: Field "Street" in "Address Details" has logic "Copy from GST field"
     - **Source**: GST field in "PAN and GST Details" panel (provides data)
     - **Target**: Street field in "Address Details" panel (receives data)
     - **operation_type**: "incoming" (from the perspective of the field being analyzed)

2. **OUTGOING reference (current field is SOURCE)** - The current field CONTROLS or PROVIDES data to another field:
   - Logic contains: "controls X", "sets X visibility", "makes X mandatory"
   - Example: Field "Process Type" in "Basic Details" has logic "If selected, show Bank Details panel"
     - **Source**: Process Type in "Basic Details" (controls visibility)
     - **Target**: Fields in "Bank Details" panel (are controlled)
     - **operation_type**: "outgoing"

### Real Examples - CORRECT Interpretation:

| Field Being Analyzed | Panel | Logic Text | Source Field | Source Panel | Target Field | Target Panel | operation_type |
|---------------------|-------|------------|--------------|--------------|--------------|--------------|----------------|
| Name/ First Name | Vendor Basic Details | "Copy from Name/ First Name of the Organization field of basic detail panel" | Name/ First Name of the Organization | Basic Details | Name/ First Name | Vendor Basic Details | incoming |
| Street | Address Details | "If GST uploaded then copy the data from GST field" | Street | PAN and GST Details | Street | Address Details | incoming |
| Company Code | Withholding Tax Details | "Copy from 'Basic Details' panel" | Company Code | Basic Details | Company Code | Withholding Tax Details | incoming |
| Title | Vendor Basic Details | "Title derived from PAN Card" | PAN | PAN and GST Details | Title | Vendor Basic Details | incoming |

---

## Panel Name Matching

Logic text often contains informal panel references. Map these to actual panel names:

| Text Pattern | Actual Panel |
|--------------|--------------|
| "basic detail panel", "Basic Details" | Basic Details |
| "GST field", "GST panel", "PAN and GST" | PAN and GST Details |
| "vendor basic", "vendor details" | Vendor Basic Details |
| "address panel", "address details" | Address Details |
| "bank panel", "bank details" | Bank Details |
| "CIN panel", "TDS panel" | CIN and TDS Details |
| "MSME panel" | MSME Details |
| "payment panel" | Payment Details |
| "withholding panel" | Withholding Tax Details |

---

## Cross-Panel Rule (CRITICAL)

**ONLY include references where source and target fields are in DIFFERENT panels.**

```
source_field.panel != target_field.panel
```

**EXCLUDE all intra-panel (same-panel) references.**

---

## Relationship Type Classification

| Type               | Keywords in Logic                              |
| ------------------ | ---------------------------------------------- |
| copy_operation     | copy, derive, derived, get from, based on      |
| visibility_control | visible, hide, show, hidden, applicable        |
| mandatory_control  | mandatory, required, non-mandatory             |
| validation         | validate, verify, check, if...then             |
| enable_disable     | enable, disable, editable, non-editable        |
| default_value      | default, by default, auto-derived              |
| clear_operation    | clear, reset                                   |
| conditional        | if, when, based on (conditional behavior)      |
| other              | fallback                                       |

---

## Step 3: Output JSON

Filename:

```
<document_name>_inter_panel_references.json
```

**MANDATORY SCHEMA - Use this structure exactly, no deviations:**

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-01-24T14:30:00Z",
    "total_fields": 85,
    "total_panels": 6
  },
  "panel_summary": [
    {
      "panel_name": "Initiator Panel",
      "field_count": 25,
      "fields_with_cross_panel_refs": 3
    }
  ],
  "cross_panel_references": [
    {
      "source_field": {
        "field_name": "Name/ First Name of the Organization",
        "variable_name": "__name/_first_name_of_the_organization__",
        "panel": "Basic Details",
        "field_type": "TEXT"
      },
      "target_field": {
        "field_name": "Name/ First Name of the Organization",
        "variable_name": "__name/_first_name_of_the_organization__",
        "panel": "Vendor Basic Details",
        "field_type": "TEXT"
      },
      "reference_details": {
        "matched_text": "Name/ First Name of the Organization field of basic detail panel",
        "location_found": "logic",
        "relationship_type": "copy_operation",
        "operation_type": "incoming",
        "raw_expression": "Copy from Name/ First Name of the Organization field of basic detail panel"
      }
    },
    {
      "source_field": {
        "field_name": "PAN",
        "variable_name": "__pan__",
        "panel": "PAN and GST Details",
        "field_type": "TEXT"
      },
      "target_field": {
        "field_name": "Title",
        "variable_name": "__title__",
        "panel": "Vendor Basic Details",
        "field_type": "DROPDOWN"
      },
      "reference_details": {
        "matched_text": "PAN Card",
        "location_found": "logic",
        "relationship_type": "copy_operation",
        "operation_type": "incoming",
        "raw_expression": "Title derived from PAN Card as follow: If the 4th character is 'C'..."
      }
    }
  ],
  "relationship_summary": {
    "copy_operation": 12,
    "visibility_control": 8,
    "mandatory_control": 5,
    "validation": 3,
    "enable_disable": 2,
    "default_value": 4,
    "conditional": 6,
    "clear_operation": 1,
    "other": 0
  },
  "dependency_graph": {
    "source_panels": {
      "Basic Details": {
        "affects_panels": ["Vendor Basic Details", "Address Details"],
        "reference_count": 15
      },
      "PAN and GST Details": {
        "affects_panels": ["Vendor Basic Details", "Address Details"],
        "reference_count": 10
      }
    },
    "target_panels": {
      "Vendor Basic Details": {
        "affected_by_panels": ["Basic Details", "PAN and GST Details"],
        "reference_count": 18
      },
      "Address Details": {
        "affected_by_panels": ["PAN and GST Details"],
        "reference_count": 8
      }
    }
  }
}
```

**CRITICAL SCHEMA RULES:**
1. `cross_panel_references` must use nested objects: `source_field`, `target_field`, `reference_details`
2. `reference_details.operation_type` must be either "incoming" or "outgoing"
3. `source_field` is the field that PROVIDES data or CONTROLS behavior
4. `target_field` is the field that RECEIVES data or IS CONTROLLED
5. `panel_summary` must be an array of objects, NOT an object with panel names as keys

No additional files may be generated.

---

## Step 4: Final Console Summary

Print:

* Total fields analyzed
* Total panels
* Fields with cross-panel refs
* Total relationships found
* Top source panels (panels that provide data to others)
* Top target panels (panels that receive data from others)
* Relationship type distribution
* Output file location

---

## Enforcement

* No document parsing (data is pre-extracted)
* Exactly one output JSON file
* No code generation or script creation
* No deviations from workflow
* **CRITICAL: Only cross-panel references (source panel ≠ target panel)**
* **CRITICAL: Only analyze the `logic` field**
* **CRITICAL: Correctly identify source (provides) vs target (receives)**
* **CRITICAL: Include operation_type ("incoming" or "outgoing")**
* **CRITICAL: Use the exact JSON schema structure provided above**
* **Zero intra-panel references in output**

This is a **strict analysis command** on pre-provided data.

If the source and target panels are identical, you are violating the core requirement. Stop and filter those out.
