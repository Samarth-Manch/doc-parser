# Form Builder Comparison Report

## Document Information

| Attribute | Document 9146 | Document 9145 |
|-----------|---------------|---------------|
| **Document ID** | 9146 | 9145 |
| **Template ID** | 3869 | 3868 |
| **Template Name** | Vendor Creation Sample BUD | Vendor Creation Sample BUD 2 |
| **URL** | https://qa.manchtech.com/dash/template/3869/document/9146/form-builder | https://qa.manchtech.com/dash/template/3868/document/9145/form-builder |
| **Comparison Date** | 2026-01-28 | 2026-01-28 |
| **Environment** | QA (qa.manchtech.com) | QA (qa.manchtech.com) |

---

## Executive Summary

| Metric | Document 9146 | Document 9145 | Status |
|--------|---------------|---------------|--------|
| **Total Panels** | 11 | 11 | MATCH |
| **Total Fields** | 154 | 155 | DIFFERENCE |
| **Panels with Differences** | 1 | 1 | - |

### Key Finding
Document 9145 contains **1 additional field** ("Rule Check") in the "Withholding Tax Details" panel that is **missing from document 9146**.

---

## Panel Structure Comparison

Both documents share an identical panel structure with 11 panels in the same order:

| # | Panel Name | 9146 Fields | 9145 Fields | Status |
|---|------------|-------------|-------------|--------|
| 1 | Basic Details | 31 | 31 | MATCH |
| 2 | PAN and GST Details | 26 | 26 | MATCH |
| 3 | Vendor Basic Details | 7 | 7 | MATCH |
| 4 | Address Details | 12 | 12 | MATCH |
| 5 | Bank Details | 11 | 11 | MATCH |
| 6 | CIN and TDS Details | 5 | 5 | MATCH |
| 7 | MSME Details | 27 | 27 | MATCH |
| 8 | Vendor Duplicity Details | 12 | 12 | MATCH |
| 9 | Purchase Organization Details | 9 | 9 | MATCH |
| 10 | Payment Details | 11 | 11 | MATCH |
| 11 | **Withholding Tax Details** | **3** | **4** | **DIFFERENCE** |

---

## Detailed Panel Analysis

### 1. Basic Details Panel (31 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Search term / Reference Number(Transaction ID) | Present | Present |
| 2 | Created on | Present | Present |
| 3 | Created By | Present | Present |
| 4 | Name/ First Name of the Organization * | Present | Present |
| 5 | Select the process type * | Present | Present |
| 6 | Process Type | Present | Present |
| 7 | Account Group/Vendor Type * | Present | Present |
| 8 | Group key/Corporate Group * | Present | Present |
| 9 | Vendor Domestic or Import * | Present | Present |
| 10 | Country * | Present | Present |
| 11 | Country Name | Present | Present |
| 12 | Country Code | Present | Present |
| 13 | Company Code * | Present | Present |
| 14 | Mobile Number * | Present | Present |
| 15 | Do you wish to add additional mobile numbers (India)? | Present | Present |
| 16 | Do you wish to add additional mobile numbers (Non-India)? | Present | Present |
| 17 | Mobile Number 2 (Domestic) | Present | Present |
| 18 | Mobile Number 3 (Domestic) | Present | Present |
| 19 | Mobile Number 4 (Domestic) | Present | Present |
| 20 | Mobile Number 5 (Domestic) | Present | Present |
| 21 | Mobile Number 2 (Import) | Present | Present |
| 22 | Mobile Number 3 (Import) | Present | Present |
| 23 | Mobile Number 4 (Import) | Present | Present |
| 24 | Mobile Number 5 (Import) | Present | Present |
| 25 | Vendor Contact Email * | Present | Present |
| 26 | Vendor Contact Name * | Present | Present |
| 27 | Do you wish to add additional email addresses? | Present | Present |
| 28 | Email 2 | Present | Present |
| 29 | Concerned email addresses? | Present | Present |
| 30 | Add the concerned Email Id | Present | Present |
| 31 | Email ID | Present | Present |

**Status: IDENTICAL**

---

### 2. PAN and GST Details Panel (26 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | PAN DETAILS | Present | Present |
| 2 | Upload PAN | Present | Present |
| 3 | PAN | Present | Present |
| 4 | Pan Holder Name | Present | Present |
| 5 | PAN Type | Present | Present |
| 6 | PAN Status | Present | Present |
| 7 | Aadhaar PAN List Status | Present | Present |
| 8 | GST Details | Present | Present |
| 9 | Please select GST option | Present | Present |
| 10 | GSTIN IMAGE | Present | Present |
| 11 | GSTIN | Present | Present |
| 12 | Trade Name | Present | Present |
| 13 | Legal Name | Present | Present |
| 14 | Reg Date | Present | Present |
| 15 | Type | Present | Present |
| 16 | Building Number | Present | Present |
| 17 | Street | Present | Present |
| 18 | City | Present | Present |
| 19 | District | Present | Present |
| 20 | State | Present | Present |
| 21 | Pin Code | Present | Present |
| 22 | Upload Declaration | Present | Present |
| 23 | GST Vendor Classification | Present | Present |
| 24 | ID Type | Present | Present |
| 25 | Service Tax Registration Number | Present | Present |
| 26 | Language Key | Present | Present |

**Status: IDENTICAL**

---

### 3. Vendor Basic Details Panel (7 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Name/ First Name of the Organization | Present | Present |
| 2 | Name/ Middle Name of the Organization | Present | Present |
| 3 | Name/ Last Name of the Organization | Present | Present |
| 4 | Name 4/Alternate Name | Present | Present |
| 5 | Title | Present | Present |
| 6 | Business Registration Number Available? | Present | Present |
| 7 | Business Registration Number | Present | Present |

**Status: IDENTICAL**

---

### 4. Address Details Panel (12 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Please Choose Address Proof | Present | Present |
| 2 | Electricity bill copy | Present | Present |
| 3 | Aadhaar Front copy | Present | Present |
| 4 | Aadhaar Back Image | Present | Present |
| 5 | Street | Present | Present |
| 6 | Street 1 | Present | Present |
| 7 | Street 2 | Present | Present |
| 8 | Street 3 | Present | Present |
| 9 | Postal Code | Present | Present |
| 10 | City | Present | Present |
| 11 | District | Present | Present |
| 12 | State | Present | Present |

**Status: IDENTICAL**

---

### 5. Bank Details Panel (11 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Please choose the option | Present | Present |
| 2 | Cancelled Cheque Image | Present | Present |
| 3 | Passbook/Bank Letter | Present | Present |
| 4 | Please enter IFSC and Account ... | Present | Present |
| 5 | IFSC Code | Present | Present |
| 6 | Bank Account Number | Present | Present |
| 7 | Name of Account Holder | Present | Present |
| 8 | Bank Name | Present | Present |
| 9 | Bank Branch | Present | Present |
| 10 | Bank Address | Present | Present |
| 11 | Bank Country | Present | Present |

**Status: IDENTICAL**

---

### 6. CIN and TDS Details Panel (5 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | CIN Certificate | Present | Present |
| 2 | CIN | Present | Present |
| 3 | FDA Registration Number | Present | Present |
| 4 | TDS Applicable? | Present | Present |
| 5 | TDS Certificate | Present | Present |

**Status: IDENTICAL**

---

### 7. MSME Details Panel (27 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Is SSI / MSME Applicable? | Present | Present |
| 2 | MSME Image | Present | Present |
| 3 | MSME Registration Number | Present | Present |
| 4 | Name | Present | Present |
| 5 | Type | Present | Present |
| 6 | Address | Present | Present |
| 7 | Category | Present | Present |
| 8 | Date | Present | Present |
| 9 | Enterprise | Present | Present |
| 10 | Major Activity | Present | Present |
| 11 | Date of Commencement | Present | Present |
| 12 | Dice Name | Present | Present |
| 13 | State | Present | Present |
| 14 | Applied State | Present | Present |
| 15 | Modified Date | Present | Present |
| 16 | Expiry Date | Present | Present |
| 17 | Address Line1 | Present | Present |
| 18 | Building | Present | Present |
| 19 | Street | Present | Present |
| 20 | Area | Present | Present |
| 21 | City | Present | Present |
| 22 | Pin | Present | Present |
| 23 | State | Present | Present |
| 24 | District | Present | Present |
| 25 | Classification Year | Present | Present |
| 26 | Classification Date | Present | Present |
| 27 | MSME Declaration | Present | Present |

**Status: IDENTICAL**

---

### 8. Vendor Duplicity Details Panel (12 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Exception Duplicate Vendor creation (Checkbox) | Present | Present |
| 2 | Exception Duplicate Vendor creation (Label) | Present | Present |
| 3 | Duplicate Vendor Number | Present | Present |
| 4 | Duplicate Vendor Description | Present | Present |
| 5 | Block status | Present | Present |
| 6 | Duplicate GST Result | Present | Present |
| 7 | Duplicate PAN Result | Present | Present |
| 8 | Duplicate Email Result | Present | Present |
| 9 | Duplicate Mobile Result | Present | Present |
| 10 | Duplicate Bank Account Number Result | Present | Present |
| 11 | Justification for Duplicate Vendor Creation | Present | Present |
| 12 | Comments | Present | Present |

**Status: IDENTICAL**

---

### 9. Purchase Organization Details Panel (9 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Company Code | Present | Present |
| 2 | Order currency | Present | Present |
| 3 | Purchase Organization * | Present | Present |
| 4 | Terms of Payment * | Present | Present |
| 5 | Incoterms | Present | Present |
| 6 | Incoterms (Part 2) | Present | Present |
| 7 | GR-Based Inv. Verif. | Present | Present |
| 8 | Schema Grp, Supplier | Present | Present |
| 9 | Automatic PO | Present | Present |

**Status: IDENTICAL**

---

### 10. Payment Details Panel (11 fields each)

| # | Field Name | 9146 | 9145 |
|---|------------|------|------|
| 1 | Payment Methods * | Present | Present |
| 2 | House Bank | Present | Present |
| 3 | Minority Indicator | Present | Present |
| 4 | VENDOR INVOICE | Present | Present |
| 5 | Reconciliation acct * | Present | Present |
| 6 | Currency * | Present | Present |
| 7 | Is Vendor Your Customer? * | Present | Present |
| 8 | Customer Code | Present | Present |
| 9 | Service Tax File | Present | Present |
| 10 | Share with | Present | Present |
| 11 | Additional File | Present | Present |

**Status: IDENTICAL**

---

### 11. Withholding Tax Details Panel (DIFFERENCE FOUND)

| # | Field Name | 9146 | 9145 | Status |
|---|------------|------|------|--------|
| 1 | Withholding Tax Type * | Present | Present | MATCH |
| 2 | Recipient Type | Present | Present | MATCH |
| 3 | Withholding Tax Code * | Present | Present | MATCH |
| 4 | **Rule Check** | **MISSING** | **Present** | **DIFFERENCE** |

**Status: DIFFERENT - Document 9145 has 1 additional field**

---

## Differences Summary

### Fields Missing in Document 9146

| Panel | Field Name | Present in 9145 | Missing in 9146 |
|-------|------------|-----------------|-----------------|
| Withholding Tax Details | Rule Check | YES | YES |

### Fields Missing in Document 9145

*None - Document 9145 contains all fields from 9146 plus additional fields.*

---

## Recommendations

1. **Investigate "Rule Check" Field**: Determine if the "Rule Check" field in document 9145 should be added to document 9146 for consistency.

2. **Field Type Verification**: Consider verifying field types for all fields if type-level differences need to be identified.

3. **Version Control**: Document which version (9145 or 9146) should be considered the source of truth.

---

## Appendix: Comparison Methodology

### Tools Used
- Chrome DevTools MCP Server for browser automation
- Visual inspection of form builder interface
- Panel-by-panel field extraction

### Process
1. Navigated to each form builder URL
2. Set viewport to desktop dimensions (1920x1080)
3. Expanded each panel sequentially
4. Captured all field names from each panel
5. Performed side-by-side comparison

### Limitations
- Field types were not individually verified (requires clicking each field)
- Field properties (mandatory, visibility rules, etc.) were not compared
- Only field names and panel structure were compared

---

*Report generated on: 2026-01-28*
*Comparison performed by: Claude Code with Chrome DevTools MCP*
