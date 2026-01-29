---
name: Unstructured Rules Extraction from BUD
allowed-tools: Read, Write
description: Extracts implementation-critical natural language rules not present in structured parser output.
---


# Unstructured Rules Extraction from BUD (Claude Code Prompt)

## Objective

Extract **only unstructured, natural-language rule information** from pre-extracted BUD section data that is:

* **Not present in structured parser output** (not field definitions in tables)
* **Critical for implementation** (generic rules that apply across fields)
* Written as **meta-rules, behavioral notes, or engineering guidance**
* Related to **fields and rules only** (not workflows)

This command exists to ensure **important implementation logic written as prose/notes** is not missed.

---

## Input

You will be provided with:
1. **Input File Path**: Path to a JSON file containing pre-extracted sections data
2. **Output Directory**: Directory to save the analysis results

**First action**: Read the input JSON file using the Read tool.

## Input JSON Format

The input file contains pre-extracted sections data in the following format:

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "file_path": "extraction/Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-01-24T14:30:00Z",
    "total_sections": 35,
    "sections_to_analyze": 3
  },
  "sections": [
    {
      "index": 13,
      "heading": "4.4 Field-Level Information",
      "level": 2,
      "parent_path": "4. Vendor Creation Functional Requirements",
      "content": [
        "Below are the details of each field used in this process.",
        "Note – If there is any dependent dropdown, then it should be clear when the parent dropdown values are changed.",
        "Note – If based on dropdown values, fields are visible, invisible, mandatory, or non-mandatory, then respective fields should be clear when dropdown values are changed."
      ],
      "is_field_related": true,
      "classification_reason": "Field keyword 'field-level' in heading",
      "section_type": "field_information"
    }
  ]
}
```

---

## Hard Constraints (Mandatory)

* Do **not** parse any documents - data is pre-extracted
* Do **not** create scripts or code files
* Do **not** scan directories or auto-discover files
* Use **only** the provided sections data from input
* Output **only** the JSON result file
* Abort immediately if input data is malformed
* **CRITICAL: Only process sections where `is_field_related` is true**
* **CRITICAL: Only extract from `content` array (paragraph text), NOT from tables**

Any deviation = incorrect behavior.

---

## Variables

```text
OUTPUT_DIR    = extraction/rule_info_output/<date_time>/
```

`<date_time>` format: `YYYY-MM-DD_HH-MM-SS`

Use the output directory provided in the prompt, or create one with current timestamp.

---

## Step 1: Filter Sections

From the provided `sections` data:

1. **Only process sections** where `is_field_related` is `true`
2. **Skip sections** where `section_type` is `workflow` or similar
3. **Log** each section's classification decision

---

## Step 2: Extract Meta-Rules from Content

For each field-related section, analyze the `content` array (list of paragraph strings).

### What to Extract (INCLUDE):

1. **Dependency Clearing Rules**:
   - "If a parent dropdown changes, dependent dropdowns must be cleared"
   - "If the original field is cleared, copy values should also be cleared"

2. **Behavioral Meta-Rules**:
   - "If based on dropdown values, fields become visible/invisible/mandatory"
   - "Respective fields should be clear when dropdown values are changed"

3. **Implementation Notes**:
   - Lines starting with "Note –", "Important:", "Rule:"
   - Generic guidance that applies to multiple fields

4. **Data Consistency Rules**:
   - Copy/clear relationships between fields
   - Cascade behaviors

5. **Engineering Guidance**:
   - Instructions for developers/implementers
   - "Should be", "Must be", "Always" statements

### What to EXCLUDE (DO NOT Extract):

1. **Field Definitions** - Individual field names, types, descriptions
2. **Table Content** - Anything from tables (these are in structured output)
3. **Workflow Steps** - Login, submit, approve, reject steps
4. **UI Navigation** - "Click on", "Navigate to"
5. **Boilerplate Text** - Section titles, generic introductions

---

## Rule Classification

Each extracted rule must be classified into ONE of:

| Type | Description | Example Keywords |
|------|-------------|------------------|
| `dependency_rule` | Rules about field dependencies | dependent, parent, child, cascade |
| `clearing_rule` | Rules about when to clear/reset values | clear, reset, empty, blank |
| `visibility_rule` | Rules about field visibility | visible, invisible, hidden, show, hide |
| `mandatory_rule` | Rules about mandatory/optional status | mandatory, required, optional, non-mandatory |
| `copy_rule` | Rules about copying/deriving values | copy, derive, replicate, same as |
| `validation_rule` | Rules about data validation | validate, check, verify, ensure |
| `behavioral_rule` | General behavioral rules | when, if, should, must |
| `implementation_note` | Engineering/implementation guidance | note, important, developer |
| `other` | Anything that doesn't fit above | fallback |

---

## Step 3: Output JSON

Filename:

```
<document_name>_meta_rules.json
```

**MANDATORY SCHEMA - Use this structure exactly, no deviations:**

```json
{
  "document_info": {
    "file_name": "Vendor Creation Sample BUD.docx",
    "extraction_timestamp": "2026-01-24T14:30:00Z",
    "total_sections_analyzed": 3,
    "total_rules_extracted": 5
  },
  "extraction_summary": {
    "sections_processed": [
      {
        "index": 13,
        "heading": "4.4 Field-Level Information",
        "rules_found": 3
      }
    ],
    "sections_skipped": [
      {
        "index": 15,
        "heading": "4.5.1 Initiator Behaviour",
        "skip_reason": "Workflow section"
      }
    ]
  },
  "meta_rules": [
    {
      "rule_id": "MR001",
      "section": {
        "index": 13,
        "heading": "4.4 Field-Level Information",
        "level": 2,
        "parent_path": "4. Vendor Creation Functional Requirements"
      },
      "rule_type": "dependency_rule",
      "rule_text": "If there is any dependent dropdown, then it should be clear when the parent dropdown values are changed.",
      "applies_to": "all_dependent_dropdowns",
      "implementation_impact": "Implement cascade clear on parent dropdown change event"
    },
    {
      "rule_id": "MR002",
      "section": {
        "index": 13,
        "heading": "4.4 Field-Level Information",
        "level": 2,
        "parent_path": "4. Vendor Creation Functional Requirements"
      },
      "rule_type": "clearing_rule",
      "rule_text": "If based on dropdown values, fields are visible, invisible, mandatory, or non-mandatory, then respective fields should be clear when dropdown values are changed.",
      "applies_to": "all_conditional_fields",
      "implementation_impact": "Clear field values when visibility/mandatory state changes due to dropdown"
    },
    {
      "rule_id": "MR003",
      "section": {
        "index": 13,
        "heading": "4.4 Field-Level Information",
        "level": 2,
        "parent_path": "4. Vendor Creation Functional Requirements"
      },
      "rule_type": "copy_rule",
      "rule_text": "If the user is copying any values to another FFD and the original field is getting cleared, then copy values should also be cleared.",
      "applies_to": "all_copy_operations",
      "implementation_impact": "Track copy source-target relationships; clear target when source is cleared"
    }
  ],
  "rule_type_summary": {
    "dependency_rule": 1,
    "clearing_rule": 1,
    "copy_rule": 1,
    "visibility_rule": 0,
    "mandatory_rule": 0,
    "validation_rule": 0,
    "behavioral_rule": 0,
    "implementation_note": 0,
    "other": 0
  },
  "implementation_checklist": [
    "Implement cascade clear for all dependent dropdowns when parent value changes",
    "Clear field values when visibility/mandatory state changes",
    "Track copy relationships and implement cascade clear for copied values"
  ]
}
```

**CRITICAL SCHEMA RULES:**
1. Each rule must have a unique `rule_id` (MR001, MR002, etc.)
2. `rule_text` must be the verbatim or lightly normalized text from the document
3. `applies_to` should describe what fields/scenarios this rule affects
4. `implementation_impact` should describe what the developer needs to do
5. `meta_rules` array contains the actual extracted rules
6. `implementation_checklist` summarizes actionable items for developers

No additional files may be generated.

---

## Step 4: Final Console Summary

Print:

* Document name
* Sections analyzed
* Sections skipped (with reasons)
* Total meta-rules extracted
* Rule type distribution
* Output file location

---

## Real Examples from Vendor Creation BUD

### Section 4.4 "Field-Level Information" Content:

```text
Note – If there is any dependent dropdown, then it should be clear when the parent dropdown values are changed.
Note – If based on dropdown values, fields are visible, invisible, mandatory, or non-mandatory, then respective fields should be clear when dropdown values are changed.
Note – If the user is copying any values to another FFD and the original field is getting cleared, then copy values should also be cleared. E.g. In this process, when GST is uploaded, the GST address is copied into the address detail panel. If the GST address is getting clear, then the address details should also get clear.
```

### Expected Extraction:

| Rule ID | Type | Text | Applies To |
|---------|------|------|------------|
| MR001 | dependency_rule | If there is any dependent dropdown... | all_dependent_dropdowns |
| MR002 | clearing_rule | If based on dropdown values, fields are visible... | all_conditional_fields |
| MR003 | copy_rule | If the user is copying any values... | all_copy_operations |

---

## Enforcement

* No document parsing (data is pre-extracted)
* Exactly one output JSON file
* No code generation or script creation
* No deviations from workflow
* **CRITICAL: Only extract from sections where `is_field_related` is true**
* **CRITICAL: Only extract meta-rules from prose/notes, not field definitions**
* **CRITICAL: Use the exact JSON schema structure provided above**
* **CRITICAL: Generate `implementation_checklist` with actionable items**

This is a **strict analysis command** on pre-provided data.

If you are extracting individual field names, types, or table content, you are violating the core requirement. Focus only on meta-rules written as prose/notes.
