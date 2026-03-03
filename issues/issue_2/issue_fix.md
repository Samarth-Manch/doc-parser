# Issue 2 Fix: BUD Ambiguity — Not a Pipeline Bug

## Root Cause

This is a **BUD authoring issue**, not a pipeline bug.

The Vendor Behaviour table (Section 4.5.2) uses an ambiguous field reference:

> "Visible if Process type is India"

There are two fields with similar names in the Basic Details panel:

| Field Name | variableName | Type | Values |
|---|---|---|---|
| Select the process type | `_selecttheprocesstypebasicdetails_` | EXTERNAL_DROP_DOWN_VALUE | `India`, `International` |
| Process Type | `_processtypebasicdetails_` | TEXT (hidden, derived) | `DOM IN`, `INT` |

The BUD says **"Process type"** — which doesn't exactly match either field name. The session-based agent resolved it to the wrong one (`Process Type` instead of `Select the process type`).

## Why the BUD Is at Fault

The BUD already uses exact quoted field names elsewhere. For example:

> `Make visible and Mandatory if "Do you wish to add additional mobile numbers (India)?" is Yes`

That's unambiguous. But for the affected fields, it uses an imprecise, unquoted reference that could match either field.

## Recommended Fix

**Correct the BUD** to use exact quoted field names in the logic column:

### Before (ambiguous)
- Row 16: `Dropdown values are Yes / No. Visible if Process type is India`
- Row 17: `Dropdown values are Yes / No. Visible if process type is international`

### After (explicit)
- Row 16: `Dropdown values are Yes / No. Visible if "Select the process type" is India`
- Row 17: `Dropdown values are Yes / No. Visible if "Select the process type" is International`

## Affected Fields

- `_doyouwishtoaddadditionalmobilenumbersindiabasicdetails_` (Row 16, Vendor Behaviour)
- `_doyouwishtoaddadditionalmobilenumbersnonindiabasicdetails_` (Row 17, Vendor Behaviour)

## Fix Applied

A corrected BUD was created at `documents/Vendor Creation Sample BUD 3.docx` (duplicate of BUD 2 with fixes).

### What Was Changed

Two cells in the **Vendor Behaviour table (Section 4.5.2)**, Basic Details panel:

| Row | Field | Before | After |
|-----|-------|--------|-------|
| 16 | Do you wish to add additional mobile numbers (India)? | `Dropdown values are Yes / No. Visible if Process type is India` | `Dropdown values are Yes / No. Visible if "Select the process type" is India` |
| 17 | Do you wish to add additional mobile numbers (Non-India)? | `Dropdown values are Yes / No. Visible if process type is international` | `Dropdown values are Yes / No. Visible if "Select the process type" is International` |

### How It Was Fixed

1. Copied `Vendor Creation Sample BUD 2.docx` → `Vendor Creation Sample BUD 3.docx`
2. Unpacked the docx (ZIP archive of XML files)
3. Located the two ambiguous logic strings in `word/document.xml` (lines 39857 and 40010)
4. Replaced the unquoted, inexact "Process type" with the exact quoted field name `"Select the process type"` — matching the convention already used elsewhere in the BUD
5. Also capitalized "International" in row 17 to match the actual dropdown value
6. Repacked the docx

### Why This Fixes the Issue

The session-based agent matches field references in logic text to actual field names. With the exact quoted name `"Select the process type"`, it will resolve to `_selecttheprocesstypebasicdetails_` (the dropdown with values `India` / `International`) instead of `_processtypebasicdetails_` (the hidden derived field with values `DOM IN` / `INT`).

## Status

**Resolved.** Fixed BUD available at `documents/Vendor Creation Sample BUD 3.docx`. No pipeline code change needed.
