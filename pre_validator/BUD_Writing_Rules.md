# Rules for Writing a Valid BUD (Business Understanding Document)

This document lists every rule enforced by the BUD Pre-Validator.
Follow these rules when authoring a BUD to ensure it passes all validation checks.

---

## 1. Document Structure

**1.1** The BUD must be a `.docx` (Word) file.

**1.2** The document **MUST** contain these three sections:
- **Section 4.4** — Field-Level Information (master field definitions)
- **Section 4.5.1** — Initiator Behaviour (fields visible to the Initiator)
- **Section 4.5.2** — SPOC/Vendor Behaviour (fields visible to the SPOC)

**1.3** Optionally, the document may contain:
- **Section 4.6** — Reference Tables (lookup/EDV table definitions)
- **Section 4.7** — Record List View (fields displayed in list view)

**1.4** If Section 4.5.1 or 4.5.2 is intentionally omitted, it must be explicitly marked as "Not Applicable" in the document.

---

## 2. Table Formatting

**2.1** Each of Sections 4.4, 4.5.1, and 4.5.2 must contain at least one properly structured field table.

**2.2** Field tables must have these column headers:
- Field Name
- Field Type
- Mandatory
- Logic

**2.3** Each field table must contain at least one data row (not just headers).

---

## 3. Valid Field Types

**3.1** Every value in the "Field Type" column must be one of the recognized types:

| | |
|---|---|
| `TEXT` | `TEXTAREA` |
| `NUMBER` | `DATE` |
| `TIME` | `DROPDOWN` |
| `EXTERNAL_DROP_DOWN_VALUE` | `EXTERNAL_DROP_DOWN_DISPLAY` |
| `CHECK_BOX` | `RADIAL_BUTTON` |
| `FILE` | `IMAGE` |
| `PANEL` | `ARRAY_HDR` (or `ARRAY_HEADER`) |
| `ARRAY_END` | `LABEL` |
| `BUTTON_SUBMIT` | `BUTTON_APPROVE` |
| `BUTTON_REJECT` | `BUTTON_RETURN` |
| `BUTTON_CUSTOM` | `VIDEO` |
| `VIDEO_URL` | `AUDIO` |
| `AUDIO_URL` | `HYPERLINK` |
| `SIGNATURE` | `BARCODE` |
| `QR_CODE` | `GEOLOCATION` |
| `SLIDER` | `RATING` |
| `TOGGLE` | `RICH_TEXT` |
| `COLOR_PICKER` | `CURRENCY` |

**3.2** Each cell in the Field Type column must contain exactly **ONE** type.
Do NOT combine multiple types (e.g., `TEXT/NUMBER` or `DROPDOWN, CHECKBOX`).

**3.3** Field type values are case-sensitive and must match exactly.

---

## 4. Field Consistency

**4.1** Every field listed in Section 4.5.1 **MUST** also exist in Section 4.4.

**4.2** Every field listed in Section 4.5.2 **MUST** also exist in Section 4.4.

**4.3** Sub-tables (4.5.1 and 4.5.2) cannot introduce fields that are absent from the master table (4.4).

---

## 5. Visibility Consistency

**5.1** If a field's logic in Section 4.4 indicates the field is "visible", that field **MUST** appear in at least one of Section 4.5.1 or 4.5.2.

**5.2** Visibility keywords recognized: `visible`, `invisible`, `not visible`.

---

## 6. Mandatory + Invisible Conflict

**6.1** A field **MUST NOT** be marked both mandatory AND invisible unless its logic includes a value derivation clause.

**6.2** Acceptable derivation phrases that resolve this conflict:
- `set to`
- `default`
- `derive` / `derived` / `derives` / `deriving`
- `populate` / `populated` / `populates` / `populating`
- `auto-fill`
- `assign` / `assigned` / `assigns`
- `reference`
- `display from`
- `look-up`
- `from EDV`
- `:=` or `=`

If a field is both mandatory and invisible, its logic **MUST** contain one of the above phrases to indicate the value is automatically derived.

---

## 7. Field Uniqueness

**7.1** Within each panel, field names must be unique. No two fields in the same panel can share the same name.

**7.2** Panel names (fields with type `PANEL`) must be unique within each section. No two panels in the same section can share the same name.

**7.3** These rules apply independently to Sections 4.4, 4.5.1, and 4.5.2.

---

## 8. Panel Structure

**8.1** Fields with type `PANEL` define panel groupings. All subsequent fields belong to that panel until the next PANEL row.

**8.2** Every field **MUST** belong to a panel. No field may appear outside (before) any PANEL row. If a field has no panel assignment, it is flagged as an **ERROR**.

**8.3** This rule applies independently to Sections 4.4, 4.5.1, and 4.5.2.

---

## 9. EDV / Dropdown Logic

**9.1** Fields with types `EXTERNAL_DROP_DOWN_VALUE`, `DROPDOWN`, or `TEXT` must have logic that references:
- **(a)** A reference table (using words like "Reference", "Table", or "EDV")
- **(b)** An attribute or column (using words like "attribute" or "column")

**9.2** Both a table reference AND a column/attribute reference are expected. Missing either one produces a **WARNING**.

**9.3** This rule applies across all sections (4.4, 4.5.1, 4.5.2).

---

## 10. Cross-Panel References

**10.1** When a field's logic references another field (identified by double-quoted names like `"Company Type"`), and the referenced field is in a **DIFFERENT** panel, the logic **MUST** include the target panel's name.

**10.2** ALL-UPPERCASE quoted strings (e.g., `"VENDOR_MASTER"`) are treated as EDV table references, not field references, and are excluded from this check.

---

## 11. Non-Editable Fields

**11.1** If a field's logic contains any of the following non-editable phrases, the field's type **MUST** be `TEXT`:
- `always non editable`
- `always non-editable`
- `always disabled`
- `non-editable`
- `non editable`

**11.2** This rule applies to all sections (4.4, 4.5.1, 4.5.2).

---

## 12. Array Brackets

**12.1** Every `ARRAY_HDR` (or `ARRAY_HEADER`) must have a corresponding `ARRAY_END`.

**12.2** Every `ARRAY_END` must have a preceding `ARRAY_HDR`.

**12.3** Arrays **CANNOT** be nested. A new `ARRAY_HDR` must not appear before the previous array is closed with `ARRAY_END`. Maximum nesting depth is 1.

**12.4** All arrays must be closed by the end of the table. No unclosed `ARRAY_HDR` is allowed.

---

## 13. Conditional Logic / Clear Field Rules

**13.1** If a field's logic contains a conditional reference to another field (detected by phrases like `when FIELD is`, `if FIELD is`, `based on FIELD`, `depending on FIELD`), it **MUST** include a clear or inverse clause.

**13.2** Acceptable clear/inverse phrases:
- `otherwise ... clear` / `otherwise ... cleared`
- `else ... clear` / `else ... cleared`
- `then ... clear` / `then ... cleared`
- `otherwise ... invisible` / `otherwise ... hidden` / `otherwise ... non-mandatory`
- `else ... invisible` / `else ... hidden` / `else ... non-mandatory`
- `clear panel`

**13.3** Pure derivation statements (`derived from`, `fetched from`, `lookup from`) are excluded from this rule.

---

## 14. Rule Uniqueness (No Duplicate Logic)

**14.1** The same field's logic **MUST NOT** be duplicated across sections. Specifically, logic in 4.4 is compared against 4.5.1 and 4.5.2.

**14.2** Duplicate detection tiers (from strictest to loosest):
| Tier | Method | Severity |
|---|---|---|
| (a) | EXACT match (after whitespace normalization) | **ERROR** |
| (b) | Fuzzy similarity >= 95% | **WARNING** |
| (c) | LLM-flagged duplicate (same business logic despite different wording) | **WARNING** |

**14.3** Rules shorter than 30 characters are excluded from this check.

---

## 15. Reference Tables

**15.1** Every reference table cited in any field's logic **MUST** exist in Section 4.6.

**15.2** Reference table formats recognized:
- **Numbered:** `Table 1.1`, `Reference Table 1.3`
- **Named:** `Reference Table - VC_BASIC_DETAILS`
- **Named:** `Reference Table VEN_EXT_APPROVAL_MATRIX`
- **Named:** `NOUN_MODIFIER reference table`

**15.3** If field logic references tables but Section 4.6 is missing or empty, a **WARNING** is raised.

**15.4** Table name matching is case-insensitive and normalizes separators (hyphens, underscores, and spaces are treated as equivalent).

---

## 16. Record List View

**16.1** If Section 4.7 is present, it defines the fields shown in the record list view. Fields are listed as bullet points.

**16.2** The Record List View **SHOULD** include the following sample/default fields:
- Transaction ID
- Company Name – Title
- Process Name
- Created By
- Created Date
- Status

**16.3** The Record List View should contain additional fields beyond the defaults. A list with only the sample fields produces a **WARNING** to review and add more fields relevant to the process.

**16.4** If any of the sample fields listed in 16.2 are missing, a **WARNING** is raised listing the missing fields.

---

## Severity Levels

When validation fails, issues are categorized as:

| Level | Meaning |
|---|---|
| **ERROR** | Must be fixed. Prevents the BUD from being valid. |
| **WARNING** | Should be reviewed and corrected. |
| **INFO** | Informational note, non-critical. |
| **PASS** | Validation passed successfully. |
| **N/A** | Not applicable (section not present in document). |

---

## Summary Checklist

Before submitting a BUD document, verify:

- [ ] Document contains Sections 4.4, 4.5.1, and 4.5.2 with proper tables
- [ ] All field types are valid single values from the approved list
- [ ] All fields in 4.5.1 and 4.5.2 exist in 4.4
- [ ] Visible fields appear in at least one behaviour table
- [ ] No field is both mandatory and invisible without value derivation
- [ ] Every field is inside a panel (no fields before the first PANEL row)
- [ ] Field names are unique within each panel
- [ ] Panel names are unique within each section
- [ ] EDV/Dropdown fields reference both a table and an attribute/column
- [ ] Cross-panel field references include the target panel name
- [ ] Non-editable fields have type TEXT
- [ ] ARRAY_HDR and ARRAY_END are properly paired (no nesting)
- [ ] Conditional logic includes clear/inverse clauses
- [ ] No duplicate logic across sections for the same field
- [ ] All referenced tables exist in Section 4.6
- [ ] Record List View (4.7) includes sample fields and additional custom fields
