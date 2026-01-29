# Form Builder Comparison Report

**Generated:** 2026-01-28 18:50:00

---

## 1. Document Information

| Property | URL 1 (QA) | URL 2 (UAT) |
|----------|------------|-------------|
| **URL** | https://qa.manchtech.com/dash/template/3869/document/9146/form-builder | https://uat.manchtech.com/dash/template/3802/document/9029/form-builder |
| **Template Name** | Vendor Creation Sample BUD | Vendor Creation |
| **Template ID** | 3869 | 3802 |
| **Document ID** | 9146 | 9029 |
| **Environment** | QA | UAT |
| **Organization** | NETAMBIT | PIDILITE |

---

## 2. Executive Summary

| Metric | URL 1 (QA) | URL 2 (UAT) | Difference |
|--------|------------|-------------|------------|
| **Total Panels** | 11 | 18 | +7 in UAT |
| **Total Fields** | ~131 | ~244 | +113 in UAT |
| **Panels Match** | No | - | - |
| **Field Count Match** | No | - | - |

### Key Findings
- **7 additional panels** exist in UAT that are not in QA
- **Significant field additions** in existing panels (Basic Details, Bank Details, etc.)
- UAT form has more comprehensive workflow support (Approver Mapping, Adhoc Approvers)
- UAT form has better support for Import vendors with dedicated fields

---

## 3. Panel Structure Comparison

| # | Panel Name | QA (URL 1) | UAT (URL 2) | Status |
|---|------------|------------|-------------|--------|
| 1 | Basic Details | 31 fields | 53 fields | **Modified** (+22 fields) |
| 2 | PAN and GST Details | 26 fields | 26 fields | Match |
| 3 | Vendor Basic Details | 7 fields | 13 fields | **Modified** (+6 fields) |
| 4 | Address Details | 12 fields | 17 fields | **Modified** (+5 fields) |
| 5 | Bank Details | 11 fields | 21 fields | **Modified** (+10 fields) |
| 6 | CIN and TDS Details | 5 fields | 6 fields | **Modified** (+1 field) |
| 7 | MSME Details | 27 fields | 27 fields | Match |
| 8 | Vendor Duplicity Details | 12 fields | 12 fields | Match |
| 9 | Purchase Organization Details | 9 fields | 25 fields | **Modified** (+16 fields) |
| 10 | Payment Details | 11 fields | 17 fields | **Modified** (+6 fields) |
| 11 | Vertical Head Details | - | 1 field | **New in UAT** |
| 12 | Functional Head Details | - | 1 field | **New in UAT** |
| 13 | Withholding Tax Details | 3 fields | 10 fields | **Modified** (+7 fields) |
| 14 | Auditor Details | - | 1 field | **New in UAT** |
| 15 | MDC Details | - | 2 fields | **New in UAT** |
| 16 | Approver Mapping | - | 21 fields | **New in UAT** |
| 17 | Common Fields Panel | - | 14 fields | **New in UAT** |
| 18 | Addition of Approver | - | 32 fields | **New in UAT** |

---

## 4. Detailed Panel Analysis

### 4.1 Basic Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Search term / Reference Number(Transaction ID) | Yes | - |
| RuleCheck | - | Yes |
| Transaction ID | - | Yes |
| Created on / Created On | Yes | Yes |
| Created By / Created By Name | Yes | Yes |
| Created By Email | - | Yes |
| Created By Mobile | - | Yes |
| Name/ First Name of the Organization * | Yes | Yes |
| Select the process type * | Yes | Yes (no asterisk) |
| Choose the Group of Company * | - | Yes |
| Company and Ownership | - | Yes |
| Company Code | - | Yes |
| Company Ownership | - | Yes |
| Company Country | - | Yes |
| Process Type | Yes | Yes |
| Account Group/Vendor Type * | Yes | Yes |
| Account Group Code | - | Yes |
| Account Group description | - | Yes |
| Group key/Corporate Group * | Yes | Yes |
| Vendor Domestic or Import * | Yes | Yes (no asterisk) |
| Process Flow Condition | - | Yes |
| Country * | Yes | Yes (no asterisk) |
| Country Name | Yes | - |
| Country Code | Yes | Yes |
| Country Code (Domestic) | - | Yes |
| Country Description (Domestic) | - | Yes |
| Vendor Country | - | Yes |
| Country Description | - | Yes |
| E4, E5, E6 | - | Yes |
| Company Code * | Yes | - |
| Mobile Number * | Yes | Yes (2 fields) |
| Do you wish to add additional mobile numbers (India)? | Yes | Yes |
| Do you wish to add additional mobile numbers (Non-India)? | Yes | Yes |
| Mobile Number 2-5 (Domestic) | Yes | Yes |
| Mobile Number 2-5 (Import) | Yes | Yes |
| Vendor Contact Email * | Yes | Yes |
| Vendor Contact Name * | Yes | Yes |
| Do you wish to add additional email addresses? | Yes | Yes |
| Email 2 | Yes | Yes |
| Concerned email addresses? | Yes | Yes |
| Add the concerned Email Id | Yes | Yes |
| Email ID | Yes | Yes |
| Central Enrolment number (CEN) | - | Yes |
| Central Enrollment Attachment | - | Yes |
| Type of Industry | - | Yes |
| Vendor Mobile Number | - | Yes |
| Vendor Mobile Number OTP | - | Yes |

**Differences:** UAT has 22 additional fields including company ownership, CEN enrollment, industry type, and OTP verification.

---

### 4.2 PAN and GST Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| PAN DETAILS | Yes | Yes |
| Upload PAN | Yes | Yes |
| PAN | Yes | Yes |
| Pan Holder Name | Yes | Yes |
| PAN Type | Yes | Yes |
| PAN Status | Yes | Yes |
| Aadhaar PAN List Status | Yes | Yes |
| GST Details | Yes | Yes |
| Please select GST option | Yes | Yes |
| GSTIN IMAGE | Yes | Yes |
| GSTIN | Yes | Yes |
| Trade Name | Yes | Yes |
| Legal Name | Yes | Yes |
| Reg Date | Yes | Yes |
| Type | Yes | Yes |
| Building Number | Yes | Yes |
| Street | Yes | Yes |
| City | Yes | Yes |
| District | Yes | Yes |
| State | Yes | Yes |
| Pin Code | Yes | Yes |
| Upload Declaration | Yes | Yes |
| GST Vendor Classification | Yes | Yes |
| ID Type | Yes | Yes |
| Service Tax Registration Number | Yes | Yes |
| Language Key | Yes | Yes |

**Differences:** No differences - panels match exactly.

---

### 4.3 Vendor Basic Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Name/ First Name of the Organization | Yes | Yes |
| Name/ Middle Name of the Organization | Yes | Yes |
| Name/ Last Name of the Organization | Yes | Yes |
| Name 4/Alternate Name | Yes | Yes |
| Title | Yes | - |
| Title (Domestic) | - | Yes |
| Title | - | Yes |
| Business Registration Number Available? | Yes | Yes |
| Business Registration Number | Yes | Yes |
| Additional Registration Number Applicable? | - | Yes |
| Additional Registration Number | - | Yes |
| Tax Number Category (GST) | - | Yes |
| Tax Number Category (SSI) | - | Yes |
| Tax Number Category (International) | - | Yes |

**Differences:** UAT has 6 additional tax number category fields and registration fields.

---

### 4.4 Address Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Please Choose Address Proof | Yes | Yes |
| Electricity bill copy | Yes | Yes |
| Aadhaar Front copy | Yes | Yes |
| Aadhaar Back Image / Aaadhar Back Image | Yes | Yes (typo) |
| Street | Yes | Yes |
| Street 1 | Yes | Yes |
| Street 2 | Yes | Yes |
| Street 3 | Yes | Yes |
| Postal Code | Yes | Yes |
| City | Yes | Yes |
| District | Yes | Yes |
| State | Yes | Yes |
| Region (Import) | - | Yes |
| City (Import) | - | Yes |
| District (Import) | - | Yes |
| Postal Code (Import) | - | Yes |
| Country | - | Yes |

**Differences:** UAT has 5 additional import vendor address fields.

---

### 4.5 Bank Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Please choose the option | Yes | Yes |
| Cancelled Cheque Image | Yes | Yes |
| Passbook/Bank Letter | Yes | Yes |
| Please enter IFSC and Account ... | Yes | Yes (full text) |
| IFSC Code | Yes | Yes |
| Bank Account Number | Yes | Yes |
| Name of Account Holder | Yes | Yes |
| Bank Name | Yes | Yes |
| Bank Branch | Yes | Yes |
| Bank Address | Yes | Yes |
| Bank Country | Yes | Yes |
| Bank Statement/Confirmation/Passbook Image | - | Yes |
| SWIFT Image | - | Yes |
| Cheque (Import) | - | Yes |
| IFSC Code / SWIFT Code / Bank Key | - | Yes |
| Bank Account Number (Import) | - | Yes |
| Name of Account Holder (Import) | - | Yes |
| Bank Name (Import) | - | Yes |
| Bank Branch (Import) | - | Yes |
| Bank Address (Import) | - | Yes |
| Bank Country (Import) | - | Yes |

**Differences:** UAT has 10 additional import vendor bank fields and SWIFT support.

---

### 4.6 CIN and TDS Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| CIN Certificate | Yes | Yes |
| CIN | Yes | Yes |
| FDA Registered? | - | Yes |
| FDA Registration Number | Yes | Yes |
| TDS Applicable? | Yes | Yes |
| TDS Certificate | Yes | Yes |

**Differences:** UAT has "FDA Registered?" question field.

---

### 4.7 MSME Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Is SSI / MSME Applicable? | Yes | Yes |
| MSME Image | Yes | Yes |
| MSME Registration Number | Yes | Yes |
| Name | Yes | Yes |
| Type | Yes | Yes |
| Address | Yes | Yes |
| Category | Yes | Yes |
| Date | Yes | Yes |
| Enterprise | Yes | Yes |
| Major Activity | Yes | Yes |
| Date of Commencement | Yes | Yes |
| Dice Name / Dic Name | Yes | Yes (typo diff) |
| State | Yes | Yes |
| Applied State | Yes | Yes |
| Modified Date | Yes | Yes |
| Expiry Date | Yes | Yes |
| Address Line1 | Yes | Yes |
| Building / Buliding | Yes | Yes (typo diff) |
| Street | Yes | Yes |
| Area | Yes | Yes |
| City | Yes | Yes |
| Pin | Yes | Yes |
| State | Yes | Yes |
| District | Yes | Yes |
| Classification Year | Yes | Yes |
| Classification Date | Yes | Yes |
| MSME Declaration | Yes | Yes |

**Differences:** Minor typo differences ("Dice Name" vs "Dic Name", "Building" vs "Buliding").

---

### 4.8 Vendor Duplicity Details

**No differences** - Both forms have identical fields.

---

### 4.9 Purchase Organization Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Company Code | Yes | Yes |
| Order currency | Yes | Yes |
| Order Currency Code | - | Yes |
| Order Currency Description | - | Yes |
| Purchase Organization * | Yes | Yes (no asterisk) |
| Purchase Organization Code | - | Yes |
| Purchase Organization Description | - | Yes |
| Terms of Payment * | Yes | Yes (no asterisk) |
| Payment Terms Code | - | Yes |
| Payment Terms Description | - | Yes |
| Incoterms | Yes | Yes |
| Incoterms Code | - | Yes |
| Incoterms Description | - | Yes |
| Incoterms (Part 2) | Yes | Yes |
| Incoterms (Part 2) Code | - | Yes |
| Incoterms (Part 2) Description | - | Yes |
| GR-Based Inv. Verif. | Yes | Yes |
| Schema Grp, Supplier | Yes | Yes |
| Automatic PO | Yes | Yes |
| Service-Based Invoice Verification | - | Yes |
| Details | - | Yes |
| Is Vendor Your Customer? | - | Yes |
| Customer Code | - | Yes |
| Service Tax File | - | Yes |

**Differences:** UAT has 16 additional fields with code/description pairs and service verification.

---

### 4.10 Payment Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Company Code | - | Yes |
| Payment Methods * | Yes | Yes (no asterisk) |
| House Bank | Yes | Yes |
| SSI Indicator | - | Yes |
| Minority Indicator | Yes | Yes |
| VENDOR INVOICE / Vendor Invoice | Yes | Yes |
| Reconciliation acct * / Reconciliation Account | Yes | Yes |
| Reconciliation Account Code | - | Yes |
| Reconciliation Account Description | - | Yes |
| Currency * / Currency | Yes | Yes |
| Currency Code | - | Yes |
| Currency Description | - | Yes |
| Is Vendor Your Customer? * | Yes | - |
| Customer Code | Yes | - |
| Service Tax File | Yes | - |
| Share with | Yes | Yes |
| Additional File | Yes | Yes |
| Clerk Abbreviation | - | Yes |
| Check Double Invoice | - | Yes |
| Requestor Comments | - | Yes |

**Differences:** Fields reorganized between panels. UAT has additional accounting fields.

---

### 4.11 Withholding Tax Details

| Field | QA (URL 1) | UAT (URL 2) |
|-------|------------|-------------|
| Company Code | - | Yes |
| Is Withholding Tax applicable? | - | Yes |
| Withholding Tax Data | - | Yes |
| Withholding Tax Type * | Yes | Yes (no asterisk) |
| Subject to Withholding Tax | - | Yes |
| Recipient Type | Yes | Yes |
| Withholding Tax Code * | Yes | Yes (no asterisk) |
| All financial & bank details are verified | - | Yes |

**Differences:** UAT has 7 additional fields including verification checkbox.

---

## 5. Panels Only in UAT (URL 2)

### 5.1 Vertical Head Details (NEW)
- Vertical Head Comments

### 5.2 Functional Head Details (NEW)
- Functional Head Comments

### 5.3 Auditor Details (NEW)
- Auditor Comments

### 5.4 MDC Details (NEW)
- Vendor Number
- MDC Comments

### 5.5 Approver Mapping (NEW)
- Approver 1 / Requestor Name, Email, Mobile
- Approver 2 Vertical Head Name, Email, Mobile
- Approver 3 Functional Head Name, Email, Mobile
- Approver 4 Accounts Team Name, Email, Mobile
- Country Head Name, Email, Phone Number
- Approver 5 Auditor Team Name, Email, Mobile
- Approver 6 MDC Team Name, Email, Mobile

### 5.6 Common Fields Panel (NEW)
- Common Mobile Number, Country, Company Code, Title
- Common Bank Account Number, Bank IFSC/Key
- Common Postal code, City, District, Region
- Common Bank Country, Bank Holder Name
- Account Group Code, Account Group/Vendor Type Description

### 5.7 Addition of Approver (NEW)
- Do you want to send the request to Adhoc Approver?
- Please choose number of Approver
- Adhoc Approver1-5 Details (Name, Email, Mobile for each)
- MDC Approver fields
- Trigger Rule One

---

## 6. Differences Summary

### 6.1 Structural Differences
| Type | Count | Details |
|------|-------|---------|
| New Panels in UAT | 7 | Vertical Head, Functional Head, Auditor, MDC, Approver Mapping, Common Fields, Addition of Approver |
| Modified Panels | 9 | Basic Details, Vendor Basic Details, Address Details, Bank Details, CIN and TDS, Purchase Organization, Payment Details, Withholding Tax Details |
| Matching Panels | 3 | PAN and GST Details, MSME Details, Vendor Duplicity Details |

### 6.2 Field-Level Differences
| Panel | Fields Added in UAT |
|-------|---------------------|
| Basic Details | +22 (Company fields, CEN, OTP verification) |
| Vendor Basic Details | +6 (Tax categories, additional registration) |
| Address Details | +5 (Import vendor address fields) |
| Bank Details | +10 (Import vendor bank fields, SWIFT) |
| CIN and TDS Details | +1 (FDA question) |
| Purchase Organization Details | +16 (Code/Description pairs, service verification) |
| Payment Details | +6 (Accounting fields, comments) |
| Withholding Tax Details | +7 (Applicability, verification) |

### 6.3 Minor Differences (Typos)
- "Aadhaar Back Image" (QA) vs "Aaadhar Back Image" (UAT)
- "Dice Name" (QA) vs "Dic Name" (UAT)
- "Building" (QA) vs "Buliding" (UAT)

---

## 7. Recommendations

### 7.1 For QA to UAT Migration
1. **Add 7 new panels** to QA environment:
   - Vertical Head Details
   - Functional Head Details
   - Auditor Details
   - MDC Details
   - Approver Mapping
   - Common Fields Panel
   - Addition of Approver

2. **Update existing panels** with additional fields:
   - Add 22 fields to Basic Details
   - Add import vendor support to Bank Details and Address Details
   - Add code/description pairs to Purchase Organization Details

3. **Fix typos** in UAT:
   - "Aaadhar Back Image" → "Aadhaar Back Image"
   - "Dic Name" → "Dice Name"
   - "Buliding" → "Building"

### 7.2 For UAT to Production
1. Verify all new approval workflow panels are properly configured
2. Test import vendor fields thoroughly
3. Ensure Common Fields Panel values propagate correctly
4. Test Adhoc Approver workflow with all 5 approver slots

---

## 8. Appendix

### Forms Compared
- **QA Form:** Vendor Creation Sample BUD (Template 3869, Document 9146)
- **UAT Form:** Vendor Creation (Template 3802, Document 9029)

### Comparison Methodology
- Visual inspection using Chrome DevTools MCP
- Panel-by-panel field extraction
- Case-insensitive field name matching
- Normalized similar field names (e.g., "PAN" = "Permanent Account Number")

---

*Report generated by Claude Code Form Builder Comparison Tool*
