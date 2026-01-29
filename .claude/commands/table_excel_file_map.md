---
name: Map Excel Tables to Fields
allowed-tools: Bash, Read
description: Maps BUD fields to referenced Excel tables, sheets, and columns used for dropdowns or lookups.
---


# Map Excel Tables to Fields (Claude Code Prompt)

## Objective

Create a **mapping** between fields extracted from a single Business Understanding Document (BUD) and **Excel-backed reference tables** embedded in the document.

The output must clearly state:

* Which **field** depends on which **Excel file**
* Which **sheet**
* Which **table reference**
* Which **columns** (explicit, inferred, or fallback)

This mapping is **implementation-critical**.

---

## Hard Constraints (Mandatory)

* Do **not** create permanent scripts
* Do **not** reimplement document parsing
* Do **not** scan directories or auto-discover files
* Do **not** process multiple documents
* Use **only** the variables defined below
* Use **only** `DocumentParser` from `doc_parser`
* Parse the document **exactly once**
* Abort immediately if any prerequisite fails
* Process **only** the document specified in `DOCUMENT_PATH`

Any deviation = incorrect behavior.

---

## Variables (Use As-Is)

```text
DOCUMENT_PATH = extraction/Vendor Creation Sample BUD.docx
RULES_PATH    = RULES_REFERENCE.md
OUTPUT_DIR    = extraction/excel_field_map_output/<date_time>/
LOG_FILE      = extraction/excel_field_map_output/<date_time>/execution_log.txt
```

`<date_time>` format: `YYYY-MM-DD_HH-MM-SS`

Only this document may generate output.

---

## Prerequisites (Abort if Any Fail)

1. Import must succeed:

   ```python
   from doc_parser import DocumentParser
   ```
2. `DOCUMENT_PATH` exists
3. `RULES_PATH` exists (read-only reference)

If the import fails → **abort immediately**

---

## Logging (Required)

Initialize logging **before any processing** using the provided boilerplate.

Log:

* Prerequisite checks
* Parsing counts
* Excel table discovery
* Per-field mapping decisions
* Skipped mappings with reasons
* Strategy usage statistics
* Final summary

Logs must be written to **console and `execution_log.txt`**.

---

## Step 1: Parse Document (Once Only)

```python
parser = DocumentParser()
parsed = parser.parse(DOCUMENT_PATH)
```

Immediately extract and retain **only**:

```python
all_fields = parsed.all_fields
reference_tables = parsed.reference_tables
```

Do **not** re-parse.
Do **not** retain the full `parsed` object afterward.

---

## Step 2: Extract Excel Tables

From `reference_tables`, extract only Excel-backed tables:

```python
excel_tables = [t for t in reference_tables if t.source == "excel"]
```

For each table, log:

* Table index
* Excel file name
* Sheet name
* Column headers

---

## Step 3: Field-to-Excel Mapping

### Scope Rule (Critical)

Iterate **only** over `all_fields`.

A field is eligible **only if** its `logic` contains an **explicit table reference**.

---

### Table Reference Detection

Recognize:

* `table X.Y`
* `reference table X.Y`
* `table X`

**Index Resolution Rules**

* `X.Y` → use `Y` as 1-based index
* `X` → use `X` as 1-based index

Out-of-range indices → log warning and skip.

---

### Column Selection Strategy (Strict Priority)

#### 1. Explicit Column References (Highest Priority)

Detect:

* `column N`
* `Nth column`
* `first / second / third column`
* Combined phrases (`first and second columns`)

Include **only** those columns.

Match type: `explicit_column_reference`

---

#### 2. Inferred Columns (Medium Priority)

If no explicit columns:

* Compare field name vs column names
* Similarity threshold ≥ **0.7**

Include matching columns only.

Match type: `inferred_column`

---

#### 3. All Columns (Fallback)

If no explicit or inferred matches:

* Include **all non-empty columns**

Match type: `all_columns_fallback`

---

### Exclusions (Mandatory)

Exclude:

* Fields without table references
* Tables that cannot be resolved
* Columns out of bounds
* Empty or unnamed columns

Each exclusion **must be logged with a reason**.

---

## Step 4: Output JSON

### File Name (Mandatory)

```
<bud_file_name>_excel_field_map.json
```

### Required JSON Content

Top-level:

* `document_name`
* `total_fields`
* `fields_with_table_references`
* `mapped_fields_count`
* `excel_tables`
* `field_excel_mappings`

Each **field_excel_mapping** must include:

* Full field object
* Excel file name
* Sheet name
* Table reference
* Matched columns (with indices and match types)

No additional files may be generated.

---

## Step 5: Mandatory Console Summary

Print:

```
Document: <document_name>
Total fields: <N>
Fields with explicit table references: <R>
Fields mapped to Excel: <M>
Excel tables found: <E>

Match Strategy Distribution:
  - Explicit columns: <X>
  - Inferred columns: <Y>
  - All columns (fallback): <Z>

Output saved at: extraction/excel_field_map_output/<date_time>/<document_name>_excel_field_map.json
Execution log: extraction/excel_field_map_output/<date_time>/execution_log.txt
```

Always instruct the user to **review the log file** for warnings and skipped mappings.

---

## Enforcement

* Exactly one document
* Exactly one output JSON
* Exactly one execution log
* No workflow deviations

This is a **deterministic extraction and mapping command**, not an interpretive task.
