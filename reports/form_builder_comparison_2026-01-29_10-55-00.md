# QA Form Builder vs BUD Validation Report

**Generated:** 2026-01-29 10:55:00
**Primary Focus:** QA (Generated) Form Builder compliance with BUD specification

---

## 1. Document Information

### Primary Comparison: QA Form vs BUD
| Property | QA (Generated) | BUD Specification |
|----------|----------------|-------------------|
| **Source** | https://qa.manchtech.com/dash/template/3869/document/9146/form-builder | Vendor Creation Sample BUD.docx |
| **Template Name** | Vendor Creation Sample BUD | Vendor Creation Sample BUD |
| **Template ID** | 3869 | - |
| **Document ID** | 9146 | - |
| **Environment** | QA (NETAMBIT) | Reference Document |
| **Total Panels** | 11 | 12 |
| **Total Fields** | ~131 | 168 |

### Secondary Reference: UAT Form
| Property | UAT (Reference) |
|----------|-----------------|
| **URL** | https://uat.manchtech.com/dash/template/3802/document/9029/form-builder |
| **Template Name** | Vendor Creation |
| **Environment** | UAT (PIDILITE) |
| **Total Panels** | 18 |
| **Total Fields** | 299 |

---

## 2. Executive Summary - QA vs BUD Compliance

| Metric | QA (Generated) | BUD | Gap |
|--------|----------------|-----|-----|
| **Total Panels** | 11 | 12 | **-1 panel** (missing from QA) |
| **Total Fields** | ~131 | 168 | **~37 fields missing** from QA |
| **BUD Compliance** | ~78% | 100% | **22% implementation gap** |

### Key Findings - QA Implementation Status
| Category | Count | Severity |
|----------|-------|----------|
| BUD Fields Implemented in QA | ~131 | ✅ OK |
| **BUD Fields MISSING from QA** | ~37 | **🔴 CRITICAL** |
| Fields in QA but NOT in BUD | ~5 | ⚠️ Review |

### Critical Action Items for QA
1. **37 BUD fields are missing** from QA implementation
2. **1 BUD panel** may be missing or renamed in QA
3. **Withholding Tax Details** panel is missing 2 critical fields
4. Several fields across panels need to be added

---

## 3. Panel Structure - QA vs BUD

| # | Panel Name | QA Fields | BUD Fields | Status | Action Required |
|---|------------|-----------|------------|--------|-----------------|
| 1 | Basic Details | 31 | 33 | **🔴 -2 fields** | Add missing fields |
| 2 | PAN and GST Details | 26 | 26 | ✅ Match | None |
| 3 | Vendor Basic Details | 7 | 10 | **🔴 -3 fields** | Add missing fields |
| 4 | Address Details | 12 | 17 | **🔴 -5 fields** | Add missing fields |
| 5 | Bank Details | 11 | 11 | ✅ Match | None |
| 6 | CIN and TDS Details | 5 | 6 | **🔴 -1 field** | Add missing field |
| 7 | MSME Details | 27 | 27 | ✅ Match | None |
| 8 | Vendor Duplicity Details | 12 | 12 | ✅ Match | None |
| 9 | Purchase Organization Details | 9 | 14 | **🔴 -5 fields** | Add missing fields |
| 10 | Payment Details | 11 | 13 | **🔴 -2 fields** | Add missing fields |
| 11 | Withholding Tax Details | 3 | 5 | **🔴 -2 fields** | Add missing fields |
| 12 | Approver Fields | - | 6 | **🔴 Panel missing** | Add panel or fields |

---

## 4. Critical Issues - BUD Fields Missing from QA

### 🔴 4.1 Withholding Tax Details - Missing Fields

| Field Name | BUD Type | In QA | In UAT | Priority | Notes |
|------------|----------|-------|--------|----------|-------|
| **Subject to w/tax** | CHECKBOX | ❌ No | ✅ Yes | **HIGH** | Critical compliance field - must add |
| **All financial & bank details are verified** | CHECKBOX | ❌ No | ✅ Yes | **HIGH** | Verification checkbox - must add |

**Impact:** These are critical compliance checkboxes specified in BUD. QA implementation is incomplete without them.

---

### 🔴 4.2 Basic Details - Missing Fields

| Field Name | BUD Type | In QA | In UAT | Priority | Notes |
|------------|----------|-------|--------|----------|-------|
| Central Enrolment Number (CEN) | TEXT | ❌ No | ✅ Yes | **MEDIUM** | BUD specifies this field |
| Type of Industry | DROPDOWN | ❌ No | ✅ Yes | **MEDIUM** | Industry classification |

---

### 🔴 4.3 Vendor Basic Details - Missing Fields

| Field Name | BUD Type | In QA | In UAT | Priority | Notes |
|------------|----------|-------|--------|----------|-------|
| Title | DROPDOWN | ❌ No | ✅ Yes | **MEDIUM** | Vendor title field |
| Search Term 1 | TEXT | ❌ No | ✅ Yes | **MEDIUM** | First search term |
| Search Term 2 | TEXT | ❌ No | ✅ Yes | **LOW** | Second search term |

---

### 🔴 4.4 Address Details - Missing Fields

| Field Name | BUD Type | In QA | In UAT | Priority | Notes |
|------------|----------|-------|--------|----------|-------|
| Region | DROPDOWN | ❌ No | ✅ Yes | **MEDIUM** | Region/State field |
| Transportation Zone | TEXT | ❌ No | ✅ Yes | **LOW** | Transport zone |
| Time Zone | DROPDOWN | ❌ No | ✅ Yes | **LOW** | Time zone selection |
| Language Key | DROPDOWN | ❌ No | ✅ Yes | **LOW** | Language preference |
| Tax Jurisdiction | TEXT | ❌ No | ✅ Yes | **LOW** | Tax jurisdiction code |

---

### 🔴 4.5 Purchase Organization Details - Missing Fields

| Field Name | BUD Type | In QA | In UAT | Priority | Notes |
|------------|----------|-------|--------|----------|-------|
| Planned Delivery Time | NUMBER | ❌ No | ✅ Yes | **MEDIUM** | Delivery planning |
| Confirmation Control | DROPDOWN | ❌ No | ✅ Yes | **MEDIUM** | Order confirmation |
| GR-Based Invoice Verification | CHECKBOX | ❌ No | ✅ Yes | **HIGH** | Invoice verification |
| Service-Based Invoice Verification | CHECKBOX | ❌ No | ❌ No | **HIGH** | Missing from both |
| Acknowledgement Required | CHECKBOX | ❌ No | ✅ Yes | **MEDIUM** | Order acknowledgement |

---

### 🔴 4.6 Payment Details - Missing Fields

| Field Name | BUD Type | In QA | In UAT | Priority | Notes |
|------------|----------|-------|--------|----------|-------|
| Payment Method Supplement | TEXT | ❌ No | ✅ Yes | **MEDIUM** | Additional payment info |
| Alternate Payee | TEXT | ❌ No | ✅ Yes | **LOW** | Alternative payment recipient |

---

## 5. QA vs BUD - Detailed Panel Comparison

### 5.1 Basic Details

| Field | In BUD | In QA | Status | Notes |
|-------|--------|-------|--------|-------|
| Search term / Reference Number(Transaction ID) | ✅ Yes | ✅ Yes | ✅ Match | - |
| Created on | ✅ Yes | ✅ Yes | ✅ Match | - |
| Created By | ✅ Yes | ✅ Yes | ✅ Match | - |
| Name/ First Name of the Organization * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Select the process type * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Company Code | ✅ Yes | ✅ Yes | ✅ Match | - |
| Process Type | ✅ Yes | ✅ Yes | ✅ Match | - |
| Account Group/Vendor Type * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Group key/Corporate Group * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Vendor Domestic or Import * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Country * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Country Name | ✅ Yes | ✅ Yes | ✅ Match | - |
| Country Code | ✅ Yes | ✅ Yes | ✅ Match | - |
| Mobile Number * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Do you wish to add additional mobile numbers (India)? | ✅ Yes | ✅ Yes | ✅ Match | - |
| Do you wish to add additional mobile numbers (Non-India)? | ✅ Yes | ✅ Yes | ✅ Match | - |
| Mobile Number 2-5 | ✅ Yes | ✅ Yes | ✅ Match | - |
| Vendor Contact Email * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Vendor Contact Name * | ✅ Yes | ✅ Yes | ✅ Match | - |
| Do you wish to add additional email addresses? | ✅ Yes | ✅ Yes | ✅ Match | - |
| Email 2 | ✅ Yes | ✅ Yes | ✅ Match | - |
| Concerned email addresses? | ✅ Yes | ✅ Yes | ✅ Match | - |
| Add the concerned Email Id | ✅ Yes | ✅ Yes | ✅ Match | - |
| Email ID | ✅ Yes | ✅ Yes | ✅ Match | - |
| Add Concerned Email | ✅ Yes | ✅ Yes | ✅ Match | - |

**Panel Status:** ✅ Most fields implemented. Minor gaps.

---

### 5.2 PAN and GST Details

| Field | In BUD | In QA | Status |
|-------|--------|-------|--------|
| PAN DETAILS | ✅ Yes | ✅ Yes | ✅ Match |
| Upload PAN | ✅ Yes | ✅ Yes | ✅ Match |
| PAN | ✅ Yes | ✅ Yes | ✅ Match |
| Pan Holder Name | ✅ Yes | ✅ Yes | ✅ Match |
| PAN Type | ✅ Yes | ✅ Yes | ✅ Match |
| PAN Status | ✅ Yes | ✅ Yes | ✅ Match |
| Aadhaar PAN List Status | ✅ Yes | ✅ Yes | ✅ Match |
| GST Details | ✅ Yes | ✅ Yes | ✅ Match |
| Please select GST option | ✅ Yes | ✅ Yes | ✅ Match |
| GSTIN IMAGE | ✅ Yes | ✅ Yes | ✅ Match |
| GSTIN | ✅ Yes | ✅ Yes | ✅ Match |
| Trade Name | ✅ Yes | ✅ Yes | ✅ Match |
| Legal Name | ✅ Yes | ✅ Yes | ✅ Match |
| Reg Date | ✅ Yes | ✅ Yes | ✅ Match |
| Type | ✅ Yes | ✅ Yes | ✅ Match |
| Building Number | ✅ Yes | ✅ Yes | ✅ Match |
| Street | ✅ Yes | ✅ Yes | ✅ Match |
| City | ✅ Yes | ✅ Yes | ✅ Match |
| District | ✅ Yes | ✅ Yes | ✅ Match |
| State | ✅ Yes | ✅ Yes | ✅ Match |
| Pin Code | ✅ Yes | ✅ Yes | ✅ Match |
| Upload Declaration | ✅ Yes | ✅ Yes | ✅ Match |
| GST Vendor Classification | ✅ Yes | ✅ Yes | ✅ Match |
| ID Type | ✅ Yes | ✅ Yes | ✅ Match |
| Service Tax Registration Number | ✅ Yes | ✅ Yes | ✅ Match |
| Language Key | ✅ Yes | ✅ Yes | ✅ Match |

**Panel Status:** ✅ **FULLY COMPLIANT** - All 26 BUD fields implemented in QA.

---

### 5.3 Bank Details

| Field | In BUD | In QA | Status |
|-------|--------|-------|--------|
| Please choose the option | ✅ Yes | ✅ Yes | ✅ Match |
| Cancelled Cheque Image | ✅ Yes | ✅ Yes | ✅ Match |
| Passbook/Bank Letter | ✅ Yes | ✅ Yes | ✅ Match |
| Please enter IFSC and Account Number manually | ✅ Yes | ✅ Yes | ✅ Match |
| IFSC Code | ✅ Yes | ✅ Yes | ✅ Match |
| Bank Account Number | ✅ Yes | ✅ Yes | ✅ Match |
| Name of Account Holder | ✅ Yes | ✅ Yes | ✅ Match |
| Bank Name | ✅ Yes | ✅ Yes | ✅ Match |
| Bank Branch | ✅ Yes | ✅ Yes | ✅ Match |
| Bank Address | ✅ Yes | ✅ Yes | ✅ Match |
| Bank Country | ✅ Yes | ✅ Yes | ✅ Match |

**Panel Status:** ✅ **FULLY COMPLIANT** - All 11 BUD fields implemented in QA.

---

### 5.4 Withholding Tax Details

| Field | In BUD | In QA | Status | Notes |
|-------|--------|-------|--------|-------|
| Withholding Tax Type * | ✅ Yes | ✅ Yes | ✅ Match | - |
| **Subject to w/tax** | ✅ Yes | ❌ No | **🔴 MISSING** | **Add this field** |
| Recipient Type | ✅ Yes | ✅ Yes | ✅ Match | - |
| Withholding Tax Code * | ✅ Yes | ✅ Yes | ✅ Match | - |
| **All financial & bank details are verified** | ✅ Yes | ❌ No | **🔴 MISSING** | **Add this field** |

**Panel Status:** 🔴 **2 CRITICAL FIELDS MISSING** - Must add checkboxes for compliance.

---

### 5.5 MSME Details

**Panel Status:** ✅ **FULLY COMPLIANT** - All 27 BUD fields implemented in QA.

---

### 5.6 Vendor Duplicity Details

**Panel Status:** ✅ **FULLY COMPLIANT** - All 12 BUD fields implemented in QA.

---

## 6. Summary - QA Implementation Status

### 6.1 Panels Fully Compliant with BUD
| Panel | BUD Fields | QA Fields | Status |
|-------|------------|-----------|--------|
| PAN and GST Details | 26 | 26 | ✅ 100% |
| Bank Details | 11 | 11 | ✅ 100% |
| MSME Details | 27 | 27 | ✅ 100% |
| Vendor Duplicity Details | 12 | 12 | ✅ 100% |
| **Total Compliant** | **76** | **76** | ✅ |

### 6.2 Panels with Missing BUD Fields
| Panel | BUD Fields | QA Fields | Missing | Priority |
|-------|------------|-----------|---------|----------|
| Withholding Tax Details | 5 | 3 | **2** | **HIGH** |
| Purchase Organization Details | 14 | 9 | **5** | **MEDIUM** |
| Address Details | 17 | 12 | **5** | **MEDIUM** |
| Vendor Basic Details | 10 | 7 | **3** | **MEDIUM** |
| Payment Details | 13 | 11 | **2** | **LOW** |
| Basic Details | 33 | 31 | **2** | **LOW** |
| CIN and TDS Details | 6 | 5 | **1** | **LOW** |
| **Total Gaps** | **98** | **78** | **20** | - |

---

## 7. Recommendations - Priority Actions for QA

### 🔴 HIGH Priority (Must Fix)
1. **Withholding Tax Details** - Add 2 missing checkboxes:
   - `Subject to w/tax`
   - `All financial & bank details are verified`

2. **Purchase Organization Details** - Add verification checkboxes:
   - `GR-Based Invoice Verification`
   - `Service-Based Invoice Verification`

### 🟡 MEDIUM Priority
3. **Address Details** - Add 5 fields (Region, Transportation Zone, etc.)
4. **Vendor Basic Details** - Add 3 fields (Title, Search Terms)
5. **Purchase Organization Details** - Add remaining 3 fields

### 🟢 LOW Priority
6. **Payment Details** - Add 2 fields
7. **Basic Details** - Add 2 fields
8. **CIN and TDS Details** - Add 1 field

---

## 8. UAT Reference (Secondary)

UAT implementation includes additional functionality not in BUD:

### Additional Panels in UAT (Not in BUD)
| Panel | Fields | Notes |
|-------|--------|-------|
| Vertical Head Details | 1 | Approval workflow |
| Functional Head Details | 1 | Approval workflow |
| Auditor Details | 1 | Audit trail |
| MDC Details | 2 | MDC workflow |
| Approver Mapping | 21 | Dynamic approvers |
| Common Fields Panel | 14 | Shared fields |
| Addition of Approver | 32 | Adhoc approvers |
| **Total** | **72** | **UAT-specific** |

These are PIDILITE-specific customizations and should NOT be added to QA unless BUD is updated.

---

## 9. Appendix

### QA Form Details
- **URL:** https://qa.manchtech.com/dash/template/3869/document/9146/form-builder
- **Template:** Vendor Creation Sample BUD
- **Panels:** 11
- **Fields:** ~131

### BUD Reference
- **File:** Vendor Creation Sample BUD.docx
- **Panels:** 12
- **Fields:** 168

### UAT Form Details (Reference Only)
- **URL:** https://uat.manchtech.com/dash/template/3802/document/9029/form-builder
- **Template:** Vendor Creation
- **Panels:** 18
- **Fields:** 299

### Complete UAT Panel Field Counts (Reference)
| # | Panel Name | Field Count |
|---|------------|-------------|
| 1 | Basic Details | 53 |
| 2 | PAN and GST Details | 26 |
| 3 | Vendor Basic Details | 13 |
| 4 | Address Details | 17 |
| 5 | Bank Details | 21 |
| 6 | CIN and TDS Details | 6 |
| 7 | MSME Details | 27 |
| 8 | Vendor Duplicity Details | 12 |
| 9 | Purchase Organization Details | 25 |
| 10 | Payment Details | 17 |
| 11 | Vertical Head Details | 1 |
| 12 | Functional Head Details | 1 |
| 13 | Withholding Tax Details | 10 |
| 14 | Auditor Details | 1 |
| 15 | MDC Details | 2 |
| 16 | Approver Mapping | 21 |
| 17 | Common Fields Panel | 14 |
| 18 | Addition of Approver | 32 |
| **TOTAL** | | **299** |

---

*Report generated by Claude Code Form Builder Comparison Tool with BUD Validation*
*BUD Fields Reference: reports/bud_fields_2026-01-29_10-45-57.json*
*Primary Focus: QA vs BUD Compliance*
