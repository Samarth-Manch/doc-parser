# Table 4.4 Differences: Vendor Extension BUD 1.0 vs Pidilite Extension BUD 2.0

Comparison of the **Field-Level Information** table (Section 4.4) between:
- **BUD 1.0**: `Vendor Extension BUD- 11th Mar.docx`
- **BUD 2.0**: `Pidilite Extension BUD- 2.0.docx`

---

## 1. Structural Differences

| Metric | BUD 1.0 | BUD 2.0 |
|---|---|---|
| Total field rows | 109 | 103 |
| Unique fields (excl. headers) | 102 | 95 |
| Header column 1 name | `Field Name+A1:D5` | `Field Name` |
| Mandatory convention | TRUE / FALSE | YES / NO |

---

## 2. Fields Only in BUD 2.0 (11 fields)

| Field Name | Field Type | Mandatory |
|---|---|---|
| Choose the Group of Company | Text | NO |
| Existing Company Code | Text | NO |
| Existing Company Code and Purchase Org | Array End | NO |
| Existing Purchase Organization | Text | NO |
| Extending Company Code | Dropdown | Yes |
| Extending Company Code and Purchase Org | Array End | — |
| Extending Purchase Organization | Dropdown | YES |
| Requestor Email | Text | NO |
| Requestor Mobile | Text | NO |
| Requestor Name | Text | NO |
| Withholding Tax Details Table | Array End | NO |

---

## 3. Fields Only in BUD 1.0 (18 fields)

| Field Name | Field Type | Mandatory |
|---|---|---|
| Address Number | Text | FALSE |
| Approver 1 / Requestor Email | Text | FALSE |
| Approver 1 / Requestor Mobile | Text | FALSE |
| Approver 1 / Requestor Name | Text | FALSE |
| Approver 2 Vertical Head Email | Text | FALSE |
| Approver 2 Vertical Head Mobile | Text | FALSE |
| Approver 2 Vertical Head Name | Text | FALSE |
| Choose the group of Company Extension to: | Text | TRUE |
| Company Code | Text | FALSE |
| Company Code and Purchase Org | ARRAY_END | — |
| Ext CC and PO | ARRAY_END | — |
| Extended Company Code | Dropdown | TRUE |
| Extended Purchase Organization | Dropdown | TRUE |
| ID Type | Text | FALSE |
| Purchase Organization | Text | FALSE |
| Share with | Text | FALSE |
| Title | Text | FALSE |
| Vendor Number | Text | FALSE |

---

## 4. Renamed / Equivalent Fields (likely same field, different naming)

| BUD 2.0 | BUD 1.0 |
|---|---|
| Requestor Name / Email / Mobile | Approver 1 / Requestor Name / Email / Mobile |
| Choose the Group of Company | Choose the group of Company Extension to: |
| Extending Company Code | Extended Company Code |
| Extending Purchase Organization | Extended Purchase Organization |
| Extending Company Code and Purchase Org | Ext CC and PO |
| Existing Company Code | Company Code |
| Existing Purchase Organization | Purchase Organization |

---

## 5. Significant Logic Differences (shared fields)

| Field | BUD 2.0 | BUD 1.0 |
|---|---|---|
| **Adhoc Approver Email/Name/Mobile (1-5)** | Fetched from ADHOC_APPROVER EDV (cols 2-4) | Fetched from VENDORFLOWAPPROVERLOGICUPDATE EDV (cols 1, 6, 7) |
| **Adhoc Approver (1-5)** | Visibility logic only | Value = concatenation of 1st + 6th column of VENDORFLOWAPPROVERLOGICUPDATE |
| **Vendor Name and Code** | Concatenation of 1st+3rd cols from VC_BASIC_DETAILS staging | Same + adds "Or 1st and 3rd column from Table 1.1" alternative |
| **Terms of Payment** | Dropdown from EDV: TERMS_OF_PAYMENT | Dropdown from formfill dropdown: TERMS_OF_PAYMENT |
| **Do you want to send to Adhoc Approver?** | Mandatory=NO, visible for MDC approver | Mandatory=TRUE, on change clears approver fields |
| **Bank Key** | Derived from 2nd col of VC_BANK_DETAILS | "Awaiting staging data update" |
| **Language Key** | "Pidilite to provide the information" | "Awaiting staging data update" |
| **Payment Methods** | Derived from 13th col of VC_COMPANY_DETAILS | "Awaiting staging data update" |
| **Reconciliation Account** | Derived from 10th col of VC_COMPANY_DETAILS | "Awaiting staging data update" |
| **Name of Representative** | Derived from 1st col of VC_CIN_DETAILS | "Awaiting staging data update" |
| **Search term / Reference Number** | Derived from 56th col of VC_ADDRESS_DETAILS | "Awaiting staging data update" |
| **Service Tax Registration Number** | "Pidilite to provide" | Derived from 7th col of VC_BASIC_DETAILS |
| **Street 1 / 2 / 3** | Derived from cols 43/44/45 of VC_ADDRESS_DETAILS | Derived from cols 46/47/48 of VC_ADDRESS_DETAILS (offset +3) |
| **Most derivation fields** | Source key: "Vendor Name and code" | Source key: "Vendor Code" or "Address Number" (more specific lookup keys) |

---

## 6. Key Takeaways

- **BUD 1.0 has more fields** (102 vs 95), mainly adding Approver 2 Vertical Head fields, Address Number, Vendor Number, ID Type, Title, and Share with.
- **BUD 2.0 consolidates naming** (e.g., "Extending" instead of "Extended", "Requestor" instead of "Approver 1 / Requestor").
- **EDV source tables changed**: Adhoc approver fields switched from `VENDORFLOWAPPROVERLOGICUPDATE` (BUD 1.0) to `ADHOC_APPROVER` (BUD 2.0).
- **Several fields in BUD 1.0 have placeholder logic** ("awaiting staging data update") that BUD 2.0 fills in with actual derivation rules.
- **Street column offsets differ**: BUD 2.0 uses cols 43-45, BUD 1.0 uses cols 46-48 for the same VC_ADDRESS_DETAILS staging.
- **Mandatory convention**: BUD 1.0 uses TRUE/FALSE, BUD 2.0 uses YES/NO.
