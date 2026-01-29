---
name: Unstructured Rules Extraction from BUD
allowed-tools: Bash, Read
description: Extracts implementation-critical natural language rules not present in structured parser output.
---


# Unstructured Rules Extraction from BUD (Claude Code Prompt)

## Objective

Extract **only unstructured, natural-language rule information** from a single Business Understanding Document (BUD) that is:

* **Not present in structured parser output**
* **Critical for implementation**
* Written as **meta-rules, behavioral notes, or engineering guidance**
* Related to **fields and rules only** (not workflows)

This command exists to ensure **important implementation logic written outside tables** is not missed.

---

## Hard Constraints (Mandatory)

* Do **not** create new scripts
* Do **not** reimplement document parsing
* Do **not** scan directories or auto-discover files
* Do **not** re-extract structured fields, tables, or workflows
* Do **not** process multiple documents
* Use **only** the variables defined below
* Use **only** `SectionIterator`
* Process the document **section by section**
* Abort immediately if any prerequisite fails
* Process **only** the document specified in `DOCUMENT_PATH`

Any deviation = incorrect behavior.

---

## Variables (Use As-Is)

```text
DOCUMENT_PATH = extraction/Outlet_KYC _UB_3334.docx
RULES_PATH    = RULES_REFERENCE.md
OUTPUT_DIR    = extraction/rule_info_output/<date_time>/
LOG_FILE      = extraction/rule_info_output/<date_time>/execution_log.txt
```

`<date_time>` format: `YYYY-MM-DD_HH-MM-SS`

Only this document may generate output.

---

## Prerequisites (Abort if Any Fail)

1. Import must succeed:

   ```python
   from get_section_by_index import SectionIterator
   ```
2. `DOCUMENT_PATH` exists
3. `RULES_PATH` exists (read-only reference)

If the import fails → **abort immediately**

---

## Logging (Required)

Initialize logging **before any processing** using the provided boilerplate.

Log:

* Prerequisite checks
* Section iterator initialization
* Per-section metadata
* Rule acceptance / rejection decisions
* Skip reasons
* Self-check warnings
* Final summary

Logs must be written to **console and `execution_log.txt`**.

---

## Step 1: Initialize Section Iterator (Once Only)

```python
iterator = SectionIterator(DOCUMENT_PATH)
iterator.parse()

total_sections = iterator.get_section_count()
```

* Parsing must happen **once**
* Do **not** re-parse per section

---

## Step 2: Section-by-Section Processing (Mandatory)

Iterate strictly by section index:

```python
for section_index in range(total_sections):
    section = iterator.get_section_by_index(section_index)
```

For each section, log:

* Heading
* Level
* Parent path
* Content length
* Table count

---

## Scope Filtering (Critical)

Skip sections when:

* Content is empty
* Section is clearly workflow-related (approver flow, escalation, routing)
* Content is primarily tables or structured field definitions

Each skip **must be logged with reason**.

---

## Rule Extraction Criteria

### Extract ONLY from `section['content']` (paragraph text)

Accept **only**:

* Meta rules affecting multiple fields
* Behavioral dependencies written in plain English
* Validation or consistency rules outside tables
* Engineering or implementation notes
* Generic information about rules instructions which need to be followed by the engineers.

### Examples (Valid)

* “If a parent dropdown changes, all dependent dropdown values must be cleared.”
* “Copied values must be cleared if the source field is reset.”

---

### Explicitly Exclude

* Field definitions
* Field descriptions
* Table content
* Workflow logic
* Anything already available in structured parser output

Rejected content **must be logged** with a reason.

---

## Rule Classification

Each accepted rule must be classified into one of:

* `implementation_note`
* `behavioral_rule`
* `dependency_rule`
* `validation_rule`
* `data_consistency_rule`
* `other`

Classification decision must be logged.

---

## Step 3: Output JSON

### File Name (Mandatory)

```
<bud_file_name>_meta_rules.json
```

### JSON Structure

```json
{
  "document_name": "Outlet_KYC _UB_3334",
  "total_sections": 35,
  "rules_extracted": 9,
  "unstructured_rules": [
    {
      "section_name": "4.4 Field-Level Information",
      "section_level": 2,
      "parent_path": "4. Vendor Creation Functional Requirements",
      "section_index": 13,
      "rule_type": "implementation_note",
      "text": "If a parent dropdown value changes, all dependent dropdowns must be cleared."
    }
  ]
}
```

Each rule **must include**:

* `section_name`
* `section_level`
* `parent_path`
* `section_index`
* `rule_type`
* `text` (verbatim or lightly normalized)

No additional files may be generated.

---

## Step 4: Mandatory Console Summary

Print:

```
Document: <document_name>
Sections processed: <N>
Unstructured rules extracted: <M>
Output saved at: extraction/rule_info_output/<date_time>/<document_name>_meta_rules.json
Execution log: extraction/rule_info_output/<date_time>/execution_log.txt
```

Always instruct the user to **review the log file** for extraction decisions and warnings.

---

## Enforcement

* Exactly one document
* Exactly one output JSON
* Exactly one execution log
* No workflow deviations

This is a **deterministic unstructured-rule extraction command**, not an interpretive task.
