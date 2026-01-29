---
name: Compare Form Builder Pages
allowed-tools: mcp__chrome-devtools__*, Read, Write, Bash
description: Compares Generated (QA) form builder against BUD specification, with Human-Made (UAT) as secondary reference.
---

# Compare Form Builder Pages - QA vs BUD Validation

## Objective

Perform a **visual comparison** of a Generated (QA) form builder against the BUD specification using Chrome DevTools MCP server. The Human-Made (UAT) form serves as a secondary reference.

**Primary Focus:** Validate that the Generated form implements all BUD-specified fields.

Extract and compare:
* Panel names and order
* Field names within each panel
* Field types (when clicked)
* Field placement and structure
* Identify BUD fields missing from Generated form (CRITICAL)
* Identify undocumented fields in Generated form

This comparison is **implementation-critical** for ensuring BUD compliance.

---

## Hard Constraints (Mandatory)

* Use **only** Chrome DevTools MCP tools for browser interaction
* Do **not** use WebFetch (authenticated pages require browser session)
* Must set viewport to **desktop dimensions** (1920x1080) to avoid mobile view
* **DO NOT select or navigate to templates yourself** - the human will open the correct form builder page in the browser
* Navigate to each URL and extract data sequentially
* **Prioritize Generated (QA) vs BUD comparison** - UAT is secondary reference only
* Treat similar field names as equivalent (e.g., "PAN" = "Permanent Account Number")
* Generate a comprehensive markdown report focused on QA/BUD compliance
* Abort if login is required and user is not authenticated

Any deviation = incorrect behavior.

---

## Variables

```text
GENERATED_URL      = $ARGUMENTS.generated_url   (QA/Generated form builder URL)
HUMAN_MADE_URL     = $ARGUMENTS.human_made_url  (UAT/Reference form builder URL)
OUTPUT_DIR         = reports/
REPORT_FILE        = form_builder_comparison_<timestamp>.md
BUD_FIELDS_JSON    = $ARGUMENTS.bud_fields_json (optional - path to JSON with BUD fields)
```

`<timestamp>` format: `YYYY-MM-DD_HH-MM-SS`

**Note**: If login credentials are needed, the user must be already logged in via the browser, or credentials should be provided as:
```text
GENERATED_LOGIN_URL      = (optional) URL to login page for Generated environment
GENERATED_USERNAME       = (optional) Login username for Generated environment
GENERATED_PASSWORD       = (optional) Login password for Generated environment

HUMAN_MADE_LOGIN_URL     = (optional) URL to login page for Human-Made environment
HUMAN_MADE_USERNAME      = (optional) Login username for Human-Made environment
HUMAN_MADE_PASSWORD      = (optional) Login password for Human-Made environment
```

### BUD Fields Validation (Required for Full Comparison)

If `BUD_FIELDS_JSON` is provided, the comparison will include BUD field validation:
- Each field in the comparison will have an "In BUD" column
- **CRITICAL** issues are marked in **RED** with detailed notes:
  1. Field exists in BUD but MISSING from Generated form → **Implementation gap (HIGH PRIORITY)**
  2. Field exists in Generated form but NOT in BUD → Undocumented field (Review needed)

---

## IMPORTANT: Human Template Selection

**DO NOT attempt to select or navigate to form builder templates yourself.**

The human user will:
1. Open Chrome browser
2. Navigate to the correct form builder page
3. Ensure they are logged in
4. Tell you when the page is ready

Your role is to:
1. Wait for confirmation that the page is ready
2. Take a snapshot to verify the form builder is loaded
3. Extract field data from the currently displayed page

If the page shows a template selection screen or dashboard instead of the form builder, **ASK the human to navigate to the correct page**.

---

## Prerequisites (Abort if Any Fail)

1. Chrome DevTools MCP server must be connected
2. Browser must be accessible via `mcp__chrome-devtools__list_pages`
3. User must be logged in to the application (or provide credentials)
4. **Human must have the form builder page open** (do not navigate to templates)
5. Both URLs must be accessible form builder pages

If Chrome DevTools is not available → **abort immediately with instructions**

---

## Step 1: Setup Browser Environment

### 1.1 Check Browser Connection

```
mcp__chrome-devtools__list_pages
```

If no pages available, inform user to open Chrome with DevTools.

### 1.2 Set Desktop Viewport

Before extracting data, set viewport to desktop dimensions:

```
mcp__chrome-devtools__emulate({
  viewport: {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false
  }
})
```

This prevents "mobile only" warnings on form builder pages.

---

## Step 2: Handle Authentication (If Required)

### 2.1 Navigate to Generated URL

```
mcp__chrome-devtools__navigate_page({
  type: "url",
  url: GENERATED_URL
})
```

### 2.2 Check for Login Page

Take a snapshot and check if redirected to login:

```
mcp__chrome-devtools__take_snapshot
```

If login page detected:
- If credentials provided: Fill login form and submit
- If no credentials: **Ask user to log in manually** and wait

### 2.3 Verify Form Builder Loaded

After login, verify the form builder is displayed (NOT a dashboard or template selection).

**If you see a template list or dashboard:** Ask the human to navigate to the correct form builder page.

---

## Step 2.5: Load BUD Fields Reference (Required)

Read and parse the BUD fields data:

```
Read BUD_FIELDS_JSON file
```

The JSON structure contains:
```json
{
  "document_info": {
    "file_name": "document.docx",
    "total_fields": 150,
    "total_panels": 10
  },
  "panels": ["Basic Details", "Bank Details", ...],
  "fields_by_panel": {
    "Basic Details": [
      {"field_name": "Name", "field_type": "TEXT", "is_mandatory": true, "panel": "Basic Details"},
      ...
    ]
  },
  "all_field_names": ["Name", "Email", "Phone", ...]
}
```

Store this data for validation during comparison.

---

## Step 3: Extract Data from Generated Form (GENERATED_URL)

### 3.1 Capture Form Metadata

From the page snapshot, extract:
- Template name (heading element)
- Document ID (from URL)
- Template ID (from URL)

### 3.2 Extract Panel List

Identify all panel buttons (expandable buttons with panel names).

### 3.3 Extract Fields from Each Panel

For each panel:

1. Click the panel button to expand:
   ```
   mcp__chrome-devtools__click({ uid: <panel_button_uid>, includeSnapshot: true })
   ```

2. From the snapshot, extract all field names (StaticText elements within the panel region)

3. Record:
   - Panel name
   - Field names in order
   - Field count

### 3.4 Store Data Structure

```json
{
  "url": "GENERATED_URL",
  "environment": "Generated (QA)",
  "template_name": "Template Name",
  "document_id": "9146",
  "template_id": "3869",
  "panels": [
    {
      "name": "Basic Details",
      "fields": ["Field 1", "Field 2", ...],
      "field_count": 31
    }
  ],
  "total_fields": 154
}
```

---

## Step 4: Extract Data from Human-Made Form (HUMAN_MADE_URL)

### 4.1 Navigate to Human-Made URL

```
mcp__chrome-devtools__navigate_page({
  type: "url",
  url: HUMAN_MADE_URL
})
```

### 4.2 Repeat Extraction Process

Follow the same extraction process as Step 3 for HUMAN_MADE_URL.

---

## Step 5: Perform Comparison (QA vs BUD Priority)

### 5.1 Primary: Generated vs BUD Validation

For EACH field in the BUD specification:

1. **Check if field exists in Generated form** (case-insensitive match with normalization)
2. **Mark CRITICAL if missing from Generated:**
   - Note: "BUD field '{field_name}' (Panel: {panel}) is NOT implemented in Generated form"
   - Priority: HIGH - must be fixed

For EACH field in the Generated form:
1. **Check if field exists in BUD**
2. **Mark for review if not in BUD:**
   - Note: "Field '{field_name}' exists in Generated form but not documented in BUD - verify if intentional"

### 5.2 Secondary: Human-Made as Reference

Use Human-Made form to see if missing BUD fields are implemented elsewhere:
- If a BUD field is missing from Generated but present in Human-Made → indicates implementation needed
- If a field is in Generated but not in Human-Made or BUD → may be outdated/deprecated

### 5.3 In BUD Column Values

- ✅ Yes - Field exists in BUD
- ❌ No - Field NOT in BUD (Review)
- ⚠️ Similar - Field has similar name in BUD (fuzzy match)

### 5.4 Field Name Normalization Rules

Treat these as equivalent:
- "PAN" = "Permanent Account Number" = "PAN Number"
- "GST" = "GSTIN" = "GST Number"
- Ignore trailing asterisks (*) for mandatory indicators
- Ignore case differences
- Ignore minor whitespace/punctuation differences

---

## Step 6: Generate Report (QA vs BUD Focus)

### 6.1 Report Structure

Create a markdown report with:

1. **Document Information** - URLs, template names, IDs, comparison date, BUD reference
2. **Executive Summary - QA vs BUD Compliance** - Compliance percentage, gap count
3. **Critical Issues - BUD Fields Missing from QA** - Priority action items
4. **Panel Structure - QA vs BUD** - Table showing panels and field counts
5. **Detailed Panel Analysis** - Each panel's fields with BUD validation
6. **Summary - QA Implementation Status** - Compliant vs non-compliant panels
7. **Recommendations - Priority Actions for QA** - HIGH/MEDIUM/LOW priority fixes
8. **UAT Reference (Secondary)** - Additional UAT-only functionality

### 6.2 Field Table Format (QA vs BUD Priority)

```markdown
| Field | In BUD | In QA (Generated) | In UAT (Human-Made) | Status | Notes |
|-------|--------|-------------------|---------------------|--------|-------|
| Transaction ID | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Match | - |
| Subject to w/tax | ✅ Yes | ❌ No | ✅ Yes | **🔴 MISSING** | BUD field not in QA - must add |
| RuleCheck | ❌ No | ❌ No | ✅ Yes | ⚠️ Review | UAT-only field, not in BUD |
```

### 6.3 Critical Issues Section

```markdown
## Critical Issues - BUD Fields Missing from QA

### 🔴 HIGH Priority (Must Fix)

| Field Name | BUD Panel | BUD Type | In UAT | Notes |
|------------|-----------|----------|--------|-------|
| Subject to w/tax | Withholding Tax Details | CHECKBOX | ✅ Yes | Critical compliance field - must add |

**Impact:** These BUD-specified fields are missing from the QA implementation.

### 🟡 MEDIUM Priority

| Field Name | BUD Panel | BUD Type | In UAT | Notes |
|------------|-----------|----------|--------|-------|
| Region | Address Details | DROPDOWN | ✅ Yes | Address field needed |
```

### 6.4 Save Report

```
Write report to: reports/form_builder_comparison_<timestamp>.md
```

---

## Step 7: Console Summary

Print to console:

```
=== QA vs BUD Validation Complete ===

Generated Form (QA): <generated_url>
  Template: <template_name>
  Panels: <panel_count>
  Fields: <field_count>

BUD Reference: <bud_document_name>
  Total Panels: <bud_panel_count>
  Total Fields: <bud_field_count>

QA vs BUD Compliance:
  BUD Fields Implemented: <count> / <total> (<percentage>%)
  🔴 BUD Fields MISSING from QA: <count>
  ⚠️ QA Fields not in BUD: <count>

Priority Actions:
  HIGH: <count> fields
  MEDIUM: <count> fields
  LOW: <count> fields

Human-Made Form (UAT) - Reference:
  Panels: <panel_count>
  Fields: <field_count>

Report saved: reports/form_builder_comparison_<timestamp>.md
```

---

## Error Handling

### Mobile View Warning

If page shows "Form Builder is only supported on desktop devices":
1. Set viewport to desktop dimensions
2. Reload page
3. Retry

### Login Required

If redirected to login page:
1. Check if credentials provided
2. If yes: Attempt automated login
3. If no: Ask user to log in manually and confirm

### Template Selection Screen

If page shows template list instead of form builder:
1. **DO NOT attempt to select a template**
2. Ask the human user to navigate to the correct form builder page
3. Wait for confirmation before proceeding

### Page Load Timeout

If page doesn't load within 30 seconds:
1. Take screenshot for debugging
2. Report error with screenshot path
3. Abort comparison

---

## Usage Examples

### Basic Comparison

```
/compare_form_builders generated_url=https://qa.manchtech.com/dash/template/3869/document/9146/form-builder human_made_url=https://uat.manchtech.com/dash/template/3802/document/9029/form-builder
```

### With BUD Fields Validation

```
/compare_form_builders generated_url=<GENERATED_URL> human_made_url=<HUMAN_MADE_URL> bud_fields_json=reports/bud_fields_2026-01-28.json
```

### With Authentication

```
/compare_form_builders generated_url=<GENERATED_URL> human_made_url=<HUMAN_MADE_URL> bud_fields_json=<BUD_JSON> generated_username=user@example.com generated_password=password123 human_made_username=user@example.com human_made_password=password456
```

### Using the Dispatcher (Recommended for BUD Validation)

The dispatcher script handles BUD document parsing automatically:

```bash
# Basic usage - extracts BUD fields and runs comparison
python3 dispatchers/compare_form_builders.py documents/vendor_creation_bud.docx \
    --generated-url "https://qa.manchtech.com/dash/template/3869/document/9146/form-builder" \
    --human-made-url "https://uat.manchtech.com/dash/template/3802/document/9029/form-builder"

# With authentication
python3 dispatchers/compare_form_builders.py documents/vendor_creation_bud.docx \
    --generated-url "https://qa.manchtech.com/dash/template/3869/document/9146/form-builder" \
    --human-made-url "https://uat.manchtech.com/dash/template/3802/document/9029/form-builder" \
    --generated-username "user@example.com" \
    --generated-password "password123" \
    --human-made-username "user@example.com" \
    --human-made-password "password456"

# Extract BUD fields only (for debugging)
python3 dispatchers/compare_form_builders.py documents/vendor_creation_bud.docx --fields-only
```

---

## Enforcement

* Two URLs must be provided (Generated and Human-Made)
* Desktop viewport must be set before navigation
* **DO NOT select templates** - human will navigate to correct page
* All panels must be expanded and captured
* **Report must prioritize QA vs BUD comparison**
* Report must include all BUD fields missing from QA as CRITICAL
* No assumptions about field equivalence beyond stated normalization rules
* Screenshot evidence for any errors encountered
* **BUD Validation:**
  - MUST check every BUD field against Generated form
  - MUST mark BUD fields missing from QA as CRITICAL/HIGH priority
  - MUST include detailed notes explaining implementation gaps
  - MUST include priority recommendations section

This is a **deterministic comparison command** using browser automation.

---

## Output Files

1. **Comparison Report**: `reports/form_builder_comparison_<timestamp>.md`
2. **Screenshots** (on error): `reports/screenshots/error_<timestamp>.png`
3. **BUD Fields JSON** (when using dispatcher): `reports/bud_fields_<timestamp>.json`

---

## Notes for Implementation

- Chrome DevTools MCP tools use `uid` identifiers that change on each snapshot
- Always take a fresh snapshot before interacting with elements
- Panel expansion may take time - wait for content to load
- Some form builders use lazy loading - scroll may be needed for large panels
- **Never select templates yourself** - wait for human to set up the page
