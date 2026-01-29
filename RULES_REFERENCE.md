# Rules Extraction Reference Guide

This document contains detailed information about fields, rules, source fields, and destination fields for the Document Parser rules extraction system.

---

## Table of Contents

1. [Field Structure](#field-structure)
2. [Field Types](#field-types)
3. [Expression Rules](#expression-rules)
4. [Predefined/Standard Rules](#predefinedstandard-rules)
5. [Source Field Identification](#source-field-identification)
6. [Destination Field Identification](#destination-field-identification)
7. [Logic Patterns from Documents](#logic-patterns-from-documents)
8. [Rule Schema Structure](#rule-schema-structure)

---

## Field Structure

### FieldDefinition Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Display name of the field (e.g., "Company Name", "GSTIN") |
| `field_type` | FieldType | Enum value for field type |
| `field_type_raw` | string | Original type value from document |
| `is_mandatory` | bool | Whether field is required |
| `logic` | string | Natural language logic/rules text |
| `rules` | string | Additional rules text |
| `default_value` | string | Default value if any |
| `visibility_condition` | string | Visibility condition text |
| `validation` | string | Validation rules text |
| `section` | string | Section/panel this field belongs to |
| `dropdown_values` | list[str] | Options for dropdown fields |
| `variable_name` | string | Auto-generated ID (e.g., `__pan__`, `__gstin__`) |

### Variable Name Format

Variable names follow the pattern: `__field_name__`
- Lowercase
- Spaces replaced with underscores
- Special characters removed
- Examples:
  - "Company Name" → `__company_name__`
  - "GSTIN" → `__gstin__`
  - "Do you wish to add additional mobile numbers (India)?" → `__add_mobile_india__`

---

## Field Types

### FieldType Enum Values

| Type | Description | Typical Use |
|------|-------------|-------------|
| `TEXT` | Single-line text input | Names, IDs, addresses |
| `DROPDOWN` | Single-select dropdown | Country, Status, Type |
| `MULTI_DROPDOWN` | Multi-select dropdown | Multiple categories |
| `DATE` | Date picker | DOB, Registration date |
| `FILE` | File upload | Documents, images |
| `CHECKBOX` | Checkbox (editable) | Yes/No toggles |
| `STATIC_CHECKBOX` | Checkbox (read-only) | Display-only flags |
| `MOBILE` | Mobile number input | Phone numbers with validation |
| `EMAIL` | Email input | Email with validation |
| `NUMBER` | Numeric input | Amounts, counts |
| `PANEL` | Container/section | Group of fields |
| `LABEL` | Display-only text | Instructions, headings |
| `EXTERNAL_DROPDOWN` | External data dropdown | API-driven options |
| `UNKNOWN` | Unrecognized type | Fallback |

### Type Variations in Documents

| Document Value | Maps To |
|----------------|---------|
| "Multi Dropdown", "MULTI_DROPDOWN", "MultiDropdown" | `MULTI_DROPDOWN` |
| "Static Check Box", "STATIC_CHECKBOX" | `STATIC_CHECKBOX` |
| "External Drop Down Value", "EXTERNAL_DROPDOWN" | `EXTERNAL_DROPDOWN` |
| "Mobile", "MOBILE" | `MOBILE` |
| "Text", "TEXT" | `TEXT` |

---

## Expression Rules

Expression rules use the **expr-eval** JavaScript library syntax. These control dynamic field behavior based on conditions.

### Expression Rule Functions

#### Visibility Functions

| Function | Alias | Description | Syntax |
|----------|-------|-------------|--------|
| `makeVisible` | `mvi` | Show fields when condition is true | `mvi(condition, destId1, destId2, ...)` |
| `makeInvisible` | `minvi` | Hide fields when condition is true | `minvi(condition, destId1, destId2, ...)` |
| `sessionBasedMakeVisible` | `sbmvi` | Show based on session param | `sbmvi(condition, param, destIds)` |
| `sessionBasedMakeInvisible` | `sbminvi` | Hide based on session param | `sbminvi(condition, param, destIds)` |

#### Mandatory Functions

| Function | Alias | Description | Syntax |
|----------|-------|-------------|--------|
| `makeMandatory` | `mm` | Make fields required | `mm(condition, destId1, destId2, ...)` |
| `makeNonMandatory` | `mnm` | Make fields optional | `mnm(condition, destId1, destId2, ...)` |
| `sessionBasedMakeMandatory` | `sbmm` | Mandatory based on session | `sbmm(condition, param, destIds)` |
| `sessionBasedMakeNonMandatory` | `sbmnm` | Optional based on session | `sbmnm(condition, param, destIds)` |

#### Enable/Disable Functions

| Function | Alias | Description | Syntax |
|----------|-------|-------------|--------|
| `enable` | `en` | Enable (editable) fields | `en(condition, destId1, destId2, ...)` |
| `disable` | `dis` | Disable (read-only) fields | `dis(condition, destId1, destId2, ...)` |
| `sessionBasedMakeEnabled` | `sben` | Enable based on session | `sben(condition, param, destIds)` |
| `sessionBasedMakeDisabled` | `sbdis` | Disable based on session | `sbdis(condition, param, destIds)` |

#### Data Manipulation Functions

| Function | Alias | Description | Syntax |
|----------|-------|-------------|--------|
| `copyToFillData` | `ctfd` | Copy value to fields | `ctfd(condition, srcValue, destId1, destId2, ...)` |
| `clearField` | `cf` | Clear field values | `cf(condition, destId1, destId2, ...)` |
| `executeRuleById` | `erbyid` | Execute rules of another field | `erbyid(condition, formFillMetadataIds)` |

#### Error Functions

| Function | Alias | Description | Syntax |
|----------|-------|-------------|--------|
| `addError` | `adderr` | Add error message | `adderr(condition, message, destId1, ...)` |
| `removeError` | `remerr` | Remove error message | `remerr(condition, destId1, ...)` |

#### Helper Functions

| Function | Alias | Description | Returns |
|----------|-------|-------------|---------|
| `valOf` | `vo` | Get field value by ID | Field value |
| `getElementById` | `elbyid` | Get element by ID | Element reference |
| `partyType` | `pt` | Current party type | "FP", "SP", or undefined |
| `memberType` | `mt` | Transaction member type | "CREATED_BY", "CREATED_FOR", "APPROVER", "GENERIC_PARTY" |
| `validationStatusOf` | `vso` | Get validation status | "INIT", "SUCCESS", "FAIL", "PENDING", "ABORTED", "TIMEOUT", "WARN" |
| `formTag` | `ft` | Get form field name | Field name string |

#### String Functions

| Function | Alias | Description |
|----------|-------|-------------|
| `concat` | - | Concatenate values |
| `concatWithDelimiter` | `cwd` | Concatenate with delimiter |
| `toLowerCase` | `tolc` | Convert to lowercase |
| `toUpperCase` | `touc` | Convert to uppercase |
| `contains` | `cntns` | Check if string contains value |
| `replaceRange` | `rplrng` | Replace range of characters |
| `regexTest` | `rgxtst` | Test regex pattern |

### Expression Syntax

```javascript
// Basic condition
vo("__field_var__") == 'value'

// Multiple conditions with AND
vo("__field1__") == 'Yes' and vo("__field2__") == 'Active'

// Multiple conditions with OR
vo("__field1__") == 'Yes' or vo("__field2__") == 'Yes'

// Not equal
vo("__field__") != 'No'

// Comparison operators
vo("__amount__") > 1000
vo("__age__") >= 18

// Combined expression example
mvi(vo("__gst_option__") == 'Yes', "__gstin__", "__gst_address__");
mm(vo("__gst_option__") == 'Yes', "__gstin__");
minvi(vo("__gst_option__") != 'Yes', "__gstin__", "__gst_address__");
mnm(vo("__gst_option__") != 'Yes', "__gstin__");
```

---

## Predefined/Standard Rules

These are pre-configured rules defined in `Rule-Schemas.json`. Total: **182 rules** across **14 clusters**.

### Rule Clusters Overview

| Cluster | Action Count | Rule Count | Description |
|---------|--------------|------------|-------------|
| **VERIFY** | 1 | 23 | External API verification (PAN, GST, Bank, etc.) |
| **COPY_TO** | 1 | 20 | Copy data between fields/party entities |
| **OCR** | 1 | 19 | Text extraction from document images |
| **COPY_TO_ATTRIBUTES** | 16 | 16 | Copy to transaction/generic party attributes |
| **VALIDATION** | 1 | 11 | Data validation and comparison rules |
| **FIELD_STATE** | 12 | 12 | Visibility, mandatory, enable/disable controls |
| **DATE_TIME** | 9 | 10 | Date/time operations and calculations |
| **DOCUMENT_MGMT** | 8 | 9 | Document upload, delete, classify operations |
| **COMPARISON** | 8 | 8 | Field comparison and duplicate checking |
| **GEOLOCATION** | 5 | 7 | GPS, distance, and location services |
| **DATA_TRANSFORM** | 6 | 6 | Data transformation and calculations |
| **EXTERNAL_DATA** | 5 | 6 | External data lookup and fetch operations |
| **OTP_AUTH** | 5 | 5 | OTP sending and authentication verification |
| **IDENTITY_BIOMETRIC** | 4 | 4 | Face comparison, video KYC, name matching |
| **FORM_GENERATION** | 1 | 4 | Dynamic form/table generation |
| **TRANSACTION_MGMT** | 5 | 5 | Transaction workflow and user management |
| **SPECIALIZED** | 12 | 12 | Domain-specific and miscellaneous operations |

---

### Cluster 1: VERIFY (23 rules)

External API verification services for identity and business documents.

| Rule Name | Source Type | Description |
|-----------|-------------|-------------|
| Validate PAN | PAN_NUMBER | Validate PAN against Income Tax database |
| Validate PAN (Client) | PAN_NUMBER | Client-side PAN validation |
| Validate PAN V2 | PAN_NUMBER_V2 | Enhanced PAN validation |
| PAN to CIN Validation | PAN_TO_CIN | Derive company CIN from PAN |
| Section206ABVerification | SECTION_206AB | Check 206AB compliance status |
| Validate GSTIN | GSTIN | Verify GST registration number |
| Validate GSTIN With PAN | GSTIN_WITH_PAN | Cross-validate GST with PAN |
| Validate GSTN Filing | GSTIN_RETURN_STATUS | Check GST return filing status |
| Validate Bank Account | BANK_ACCOUNT_NUMBER | Verify bank account details |
| Validate CIN | CIN_ID | Validate Company Identification Number |
| Validate TAN | TAN_NUMBER | Verify Tax Deduction Account Number |
| Validate TAN (Client) | TAN_NUMBER | Client-side TAN validation |
| Validate Driving Licence | DRIVING_LICENCE_NUMBER | Verify driving license |
| Validate FSSAI | FSSAI | Verify FSSAI license |
| Validate FSSAI Application Number | FSSAI_APPLICATION_NUMBER | Verify FSSAI application |
| Validate MSME | MSME_UDYAM_REG_NUMBER | Verify MSME Udyam registration |
| Validate RC | VEHICLE_REG_NUMBER | Verify vehicle registration |
| Validate Shops and Est | SHOP_OR_ESTABLISMENT | Verify shop license |
| Validate Drug Licence | DRUG_LICENCE | Verify drug license |
| Validate Voter Id | VOTER_ID | Verify voter ID |
| Validate eInvoice Status | EINVOICE_STATUS | Check e-invoice status |
| Get Data From EDV | EXTERNAL_DATA_VALUE | Fetch external data value |
| Validate External Data Value (Client) | EXTERNAL_DATA_VALUE | Client-side EDV validation |

---

### Cluster 2: COPY_TO (20 rules)

Copy data between form fields and party/transaction entities.

| Rule Name | Source Type | Description |
|-----------|-------------|-------------|
| Copy Aadhaar Signer Details | AADHAAR_SIGNER_DETAILS | Copy Aadhaar signer info |
| Copy CreatedBy Details | CREATED_BY | Copy transaction creator info |
| Copy CreatedFor Details | CREATED_FOR | Copy target party info |
| Copy FirstParty Name | FIRST_PARTY_NAME | Copy first party name |
| Copy FirstParty Email | FIRST_PARTY_EMAIL | Copy first party email |
| Copy FirstParty Mobile Number | FIRST_PARTY_MOBILE_NUMBER | Copy first party mobile |
| Copy FirstParty Company Name | FIRST_PARTY_COMPANY_NAME | Copy first party company |
| Copy To SecondParty Name | SECOND_PARTY_NAME | Copy to second party name |
| Copy To SecondParty Email | SECOND_PARTY_EMAIL | Copy to second party email |
| Copy To SecondParty Mobile Number | SECOND_PARTY_MOBILE_NUMBER | Copy to second party mobile |
| Copy To SecondParty Company Name | SECOND_PARTY_COMPANY_NAME | Copy to second party company |
| Copy Value | FORM_FILL_METADATA | Copy form field value |
| Copy To FormField Client | FORM_FILL_METADATA | Client-side field copy |
| Copy To Option Name | FORM_FILL_METADATA_OPTION_NAME | Copy dropdown option name |
| Copy to Title | WORK_FLOW_DATA_TITLE | Copy to workflow title |
| Copy To Transaction Message | TRANSACTION_MESSAGE | Copy to transaction message |
| Copy To Transaction Title | TRANSACTION_TITLE | Copy to transaction title |
| Copy To WorkFlowData Message | WORK_FLOW_DATA_MESSAGE | Copy to workflow message |
| Reminder Service | REMINDER_SERVICE | Configure reminder service |
| Reset PreFill Value | PRE_FILL_DATA | Reset pre-filled data |

---

### Cluster 3: OCR (19 rules)

Text extraction from document images using AI/ML.

| Rule Name | Source Type | Destination Fields |
|-----------|-------------|-------------------|
| PAN OCR | PAN_IMAGE | panNo, name, fatherName, dob |
| Aadhaar Front OCR | AADHAR_IMAGE | aadharNumberMasked, name, gender, dob, address |
| Aadhaar Back OCR | AADHAR_BACK_IMAGE | aadharAddress1-2, pin, city, dist, state, fatherName |
| GSTIN OCR | GSTIN_IMAGE | regNumber, legalName, tradeName, address, state |
| GSTIN OCR (Client) | GSTIN_IMAGE | Client-side GST extraction |
| Passport Front (India) OCR | PASSPORT | passportNumber, name, nationality, dob, placeOfBirth |
| Passport Back (India) OCR | PASSPORT_BACK_IMAGE | address, fatherName, motherName, spouseName |
| Driving License (India) OCR | DRIVING_LICENCE_IMAGE | dlNumber, name, dob, address, validUntil |
| Cheque OCR | CHEQUEE | accountNumber, ifscCode, bankName, branchName |
| Business Card OCR | BUSINESS_CARD | contactName, companyNames, email, phone |
| CIN OCR | CIN | cinNumber, companyName, registrationDate |
| FSSAI OCR | FSSAI | fssaiNumber, validUntil, businessName |
| MSME OCR | MSME | msmeNumber, enterpriseName, category |
| IncomeTax Return OCR | INCOME_TAX_RETURN | panNumber, assessmentYear, totalIncome |
| IncomeTax Return Summary OCR | INCOME_TAX_RETURN_SUMMARY | Summary extraction from ITR |
| TDS OCR | TDS | TDS certificate extraction |
| Voter Id OCR | VOTER_ID_IMAGE | voterId, name, address |
| Cowin OCR | COWIN | vaccinationStatus, doses, certificateId |
| Oversea Document OCR | OVERSEAS_DOCUMENT | Generic overseas document extraction |

---

### Cluster 4: COPY_TO_ATTRIBUTES (16 rules)

Copy field values to transaction attributes and generic party fields.

**Transaction Attributes (8 rules):**
| Rule Name | Action | Description |
|-----------|--------|-------------|
| Copy To Attr1 | COPY_TO_TRANSACTION_ATTR1 | Copy to Transaction Attribute 1 |
| Copy To Attr2 | COPY_TO_TRANSACTION_ATTR2 | Copy to Transaction Attribute 2 |
| Copy To Attr3 | COPY_TO_TRANSACTION_ATTR3 | Copy to Transaction Attribute 3 |
| Copy To Attr4 | COPY_TO_TRANSACTION_ATTR4 | Copy to Transaction Attribute 4 |
| Copy To Attr5 | COPY_TO_TRANSACTION_ATTR5 | Copy to Transaction Attribute 5 |
| Copy To Attr6 | COPY_TO_TRANSACTION_ATTR6 | Copy to Transaction Attribute 6 |
| Copy To Attr7 | COPY_TO_TRANSACTION_ATTR7 | Copy to Transaction Attribute 7 |
| Copy To Attr8 | COPY_TO_TRANSACTION_ATTR8 | Copy to Transaction Attribute 8 |

**Internal Attributes (4 rules):**
| Rule Name | Action | Description |
|-----------|--------|-------------|
| Copy To Internal Attr1 | COPY_TO_TRANSACTION_INTERNAL_ATTR1 | Copy to Internal Attribute 1 |
| Copy To Internal Attr2 | COPY_TO_TRANSACTION_INTERNAL_ATTR2 | Copy to Internal Attribute 2 |
| Copy To Internal Attr3 | COPY_TO_TRANSACTION_INTERNAL_ATTR3 | Copy to Internal Attribute 3 |
| Copy To Internal Attr4 | COPY_TO_TRANSACTION_INTERNAL_ATTR4 | Copy to Internal Attribute 4 |

**Generic Party Fields (4 rules):**
| Rule Name | Action | Description |
|-----------|--------|-------------|
| Copy To GenericParty Name | COPY_TO_GENERIC_PARTY_NAME | Copy to generic party name |
| Copy To GenericParty Email | COPY_TO_GENERIC_PARTY_EMAIL | Copy to generic party email |
| Copy To GenericParty Mobile Number | COPY_TO_GENERIC_PARTY_MOBILE_NUMBER | Copy to generic party mobile |
| Copy To GenericParty Company Name | COPY_TO_GENERIC_PARTY_COMPANY_NAME | Copy to generic party company |

---

### Cluster 5: VALIDATION (11 rules)

Data validation, comparison, and de-duplication rules.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Compare If Same | VALIDATION | Check if values are same |
| Compare If Not Same | VALIDATION | Check if values differ |
| Validation Same As FormField | VALIDATION | Validate same as another field |
| SameAsFormFllMetadataValidationV2 | VALIDATION | Enhanced same-field validation |
| Validate Same FromFillMetadata | VALIDATION | Validate with additional checks |
| De-duplication check | VALIDATION | Check for duplicate entries |
| Get value from FFDD | VALIDATION | Get value from form dropdown |
| Validate BulkBatch | VALIDATION | Validate bulk batch data |
| Validate EDV (Server) | VALIDATION | Server-side EDV validation |
| Calculate BulkBatch Liability | VALIDATION | Calculate liability for batches |
| Offline Aadhaar EKYC | VALIDATION | Offline Aadhaar verification |

---

### Cluster 6: FIELD_STATE (12 rules)

Control field visibility, mandatory status, and editability.

**Direct Field State Actions (6 rules):**
| Rule Name | Action | Description |
|-----------|--------|-------------|
| Make Visible (Client) | MAKE_VISIBLE | Show field conditionally |
| Make Invisible (Client) | MAKE_INVISIBLE | Hide field conditionally |
| Make Mandatory (Client) | MAKE_MANDATORY | Make field required |
| Make Non Mandatory (Client) | MAKE_NON_MANDATORY | Make field optional |
| Enable Field (Client) | MAKE_ENABLED | Enable field editing |
| Disable Field (Client) | MAKE_DISABLED | Disable field editing |

**Session-Based State Actions (6 rules):**
| Rule Name | Action | Description |
|-----------|--------|-------------|
| Make Visible - Session Based | SESSION_BASED_MAKE_VISIBLE | Show based on session |
| Make Invisible - Session Based | SESSION_BASED_MAKE_INVISIBLE | Hide based on session |
| Make Mandatory - Session Based | SESSION_BASED_MAKE_MANDATORY | Required based on session |
| Make NonMandatory - Session Based | SESSION_BASED_MAKE_NON_MANDATORY | Optional based on session |
| Enable Field - Session Based | SESSION_BASED_MAKE_ENABLED | Enable based on session |
| Make Disable - Session Based | SESSION_BASED_MAKE_DISABLED | Disable based on session |

---

### Cluster 7: DATE_TIME (10 rules)

Date/time operations, calculations, and validations.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Set Date EDV | SET_DATE | Set date from external data |
| Set Date Firstparty Mobile No | SET_DATE | Set date from first party mobile |
| Set Age From Date | SET_AGE_FROM_DATE | Calculate age from date |
| Set Age From Date (Client) | SET_AGE_FROM_DATE | Client-side age calculation |
| Set Date From Month Or Year | SET_DATE_FROM_MONTH_OR_YEAR | Construct date from parts |
| Split Date | SET_DATE_FROM_MONTH_OR_YEAR | Split date into components |
| Set Date From Previous Date | SET_DATE_FROM_PREV_DATE_OR_CMP_TWO_DATE | Calculate relative date |
| Check Data Range | SET_START_END_DATE_VALIDATION | Validate date range |
| SetNextOrPreviousWeekdayFromDate | SET_START_OR_END_DATE_IN_WEEK | Calculate weekday dates |
| Get FY | DERIVE_FINANCIAL_YEAR | Derive financial year |
| Derive QTR | QUARTER | Derive quarter from date |

---

### Cluster 8: DOCUMENT_MGMT (9 rules)

Document upload, delete, and management operations.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Hide Document | DELETE_DOCUMENT | Hide/soft-delete document |
| Delete Document | DELETE_FILE | Delete uploaded file |
| Unhide Document | UNDELETE_DOCUMENT | Restore hidden document |
| Unhide Document (Client) | UNDELETE_DOCUMENT | Client-side restore |
| DigiLocker E-Kyc | PULL_CLOUD_DOCUMENT | Fetch document from DigiLocker |
| Upload File Size Limit | UPLOAD_FILE_SIZE_LIMIT | Enforce upload size limit |
| ClassifyImage | CLASSIFY_DOCUMENT | Auto-classify document type |
| Make Upload Mandatory | MAKE_DOCUMENT_UPLOAD_MANDATORY | Require document upload |
| Make Document Sign Mandatory | MAKE_DOCUMENT_SIGN_MANDATORY | Require document signature |

---

### Cluster 9: COMPARISON (8 rules)

Field comparison, time comparison, and duplicate checking.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Compare Name | COMPARE | Compare names fuzzy match |
| Compare Date With Offset | COMPARE_DATE_WITH_OFFSET | Compare dates with offset |
| Compare time with start time | COMPARE_SOURCE_TIME | Compare against source time |
| Compare Time | COMPARE_DESTINATION_TIME | Compare against destination time |
| Check Duplicate | CHECK_DUPLICATE | Check for duplicate values |
| Invalidate FFDD Record | DUPLICATE_VALUE_CHECK | Mark duplicate records |
| Compare Text | CONTAINS_TEXT | Check if text contains value |
| Does Not Contain | DOES_NOT_CONTAIN_TEXT | Check if text doesn't contain value |

---

### Cluster 10: GEOLOCATION (7 rules)

GPS coordinates, distance calculation, and location services.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Calculate Distance | GET_GEOLOCATION | Calculate distance between points |
| Check Location Serviceability | GET_GEOLOCATION | Check if location is serviceable |
| Get Lat/Long From Address | GET_GEOLOCATION | Geocode address to coordinates |
| Get Location Generic Map | GET_LOCATION | Get location from map selection |
| Get Distance Generic Map | GET_DISTANCE | Calculate distance on map |
| Get Lat/Long From Image | EXTRACT_GPS_COORDINATES | Extract GPS from image metadata |
| Out Of Polygon Check | OUT_OF_POLYGON_CHECK | Check if point is within polygon |

---

### Cluster 11: DATA_TRANSFORM (6 rules)

Data transformation, calculation, and field clearing.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Convert To Lower Case | CONVERT_TO | Convert text to lowercase |
| Convert to UPPER | CONVERT_TO | Convert text to uppercase |
| Convert To Words | CONVERT_TO_WORDS | Convert number to words |
| Concatenate | CONCAT | Concatenate multiple values |
| Clear FormField | CLEAR_FIELD | Clear field value |
| Calculate TDS | CALCULATE_TDS | Calculate TDS amount |

---

### Cluster 12: EXTERNAL_DATA (6 rules)

External data lookup, dropdown population, and data fetch.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Fetch user details | LOOKUP | Lookup app user details |
| Lookup Staging Data | LOOKUP | Fetch from staging table |
| EDV Dropdown | EXT_VALUE | Populate dropdown from EDV |
| FFD Dropdown | EXT_DROP_DOWN | Populate dropdown from FFD |
| Export Import FormField | EXPORT_IMPORT_FORMFILLDATA | Export/import form data |
| Fetch Related Txns External Data Value | FETCH_RELATED_TRANSACTIONS | Fetch related transactions |

---

### Cluster 13: OTP_AUTH (5 rules)

OTP sending, validation, and authentication verification.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Send Mobile OTP | SEND_OTP | Send OTP to mobile number |
| Send Email OTP | SEND_OTP | Send OTP to email address |
| Validate Otp | VALIDATE_OTP | Validate submitted OTP |
| Validate Liveliness Otp | VERIFY_LIVELINESS_OTP | Verify OTP with liveness check |
| Validate Email | SEND_EMAIL_FOR_VERIFICATION | Send verification email |

---

### Cluster 14: IDENTITY_BIOMETRIC (4 rules)

Face comparison, video KYC, and identity matching.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Compare Face | FACE_COMPARE | Compare faces in two images |
| Video Kyc | VIDEO_KYC | Video-based KYC verification |
| GigIndiaNameMatch | GIG_INDIA_NAME_MATCH | Match names with GigIndia API |
| Set eSign Auth Mode | SET_ESIGN_AUTH_MODE | Configure eSign authentication |

---

### Cluster 15: FORM_GENERATION (4 rules)

Dynamic form and table generation.

| Rule Name | Action | Source | Description |
|-----------|--------|--------|-------------|
| Generate Table Form DropDown | GENERATE_ARRAY_FORM_GROUPS | FORM_FILL_DROP_DOWN | Generate table from dropdown |
| Generate Table Form Staging | GENERATE_ARRAY_FORM_GROUPS | STAGING_DATA | Generate table from staging |
| Generate Table From EDV | GENERATE_ARRAY_FORM_GROUPS | EXTERNAL_DATA_VALUE | Generate table from EDV |
| Generate Table From Transaction | GENERATE_ARRAY_FORM_GROUPS | TRANSACTION | Generate table from transaction |

---

### Cluster 16: TRANSACTION_MGMT (5 rules)

Transaction workflow and user management operations.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Create FFDD Record | INSERT_INTO_TABLE | Create form dropdown record |
| Create Master Record | INSERT_INTO_TABLE | Create master data record |
| Reassign Create For | REASSIGN_CREATED_FOR | Reassign transaction target |
| Copy User As CreatedFor | APP_USER_TO_TRANSACTION_CREATED_FOR_RULE | Assign user as created for |
| AppUser List FormFillDropDown | APP_USER_LIST | Populate user list dropdown |
| Make Action Based On FormFill Txn Info | MAKE_ACTION_BASED_ON_FORMFILL_TXN_INFO | Action based on transaction info |

---

### Cluster 17: SPECIALIZED (12 rules)

Domain-specific and miscellaneous operations.

| Rule Name | Action | Description |
|-----------|--------|-------------|
| Expression (Client) | EXECUTE | Execute custom expression |
| Count EDV Records | COUNT | Count external data records |
| Get Count | COUNT_NUMBER_OF_VALUES_AVAILABLE | Count available values |
| Copy Offer Transaction Details | COPY_TO_TRANSACTION_CHAIN_TXN_ID | Copy offer transaction chain |
| Conditional Copy | CONDITIONAL_COPY | Copy based on condition |
| Copy to Supporting Document | COPY_TO_DOCUMENT_STORAGE_ID | Copy to document storage |
| Customer Feedback Sentiment | CUSTOMER_FEEDBACK_SENTIMENT | Analyze feedback sentiment |
| Speech To Text | SPEECH_TO_TEXT | Convert audio to text |
| Detect Document Type | DETECT_MENU | Auto-detect document menu |
| Generate eStamp | GENERATE_ESTAMP | Generate e-stamp certificate |
| Generate Unique Code | EMPLOYEE_CODE_GENERATION | Generate employee code |
| Check Payment Status | PAYMENT_STATUS_CHECK | Check payment status |
| Qc Reload Amount | QC_RELOAD_AMOUNT_RULE | QC reload amount rule |
| Qc Qwik POS Create Code | QWIK_POS_CREATE_CODE | Create POS code |
| Qc Bosch Quick POS | VERIFY_QC_REGISTRATION_CODE | Verify QC registration |

### OCR Rules (19 total)

#### Document Types for OCR

| Source Type | Rule Name | Destination Fields |
|-------------|-----------|-------------------|
| `PAN_IMAGE` | PAN OCR | panNo, name, fatherName, dob |
| `AADHAR_IMAGE` | Aadhaar Front OCR | aadharNumberMasked, name, gender, dob, address |
| `AADHAR_BACK_IMAGE` | Aadhaar Back OCR | aadharAddress1, aadharAddress2, aadharPin, aadharCity, aadharDist, aadharState |
| `GSTIN_IMAGE` | GSTIN OCR | regNumber, legalName, tradeName, business, doi, address1, address2, pin, state, type, city |
| `PASSPORT_IMAGE` | Passport Front OCR | passportNumber, name, nationality, dob, placeOfBirth, dateOfIssue, dateOfExpiry |
| `PASSPORT_BACK_IMAGE` | Passport Back OCR | address, fatherName, motherName, spouseName |
| `DRIVING_LICENCE_IMAGE` | Driving License OCR | dlNumber, name, dob, address, validUntil |
| `CHEQUEE` | Cheque OCR | accountNumber, ifscCode, bankName, branchName |
| `BUSINESS_CARD` | Business Card OCR | contactName, firstName, lastName, companyNames, email, phone |
| `CIN` | CIN Document OCR | cinNumber, companyName, registrationDate |
| `FSSAI` | FSSAI License OCR | fssaiNumber, validUntil, businessName |
| `MSME` | MSME Certificate OCR | msmeNumber, enterpriseName, category |
| `INCOME_TAX_RETURN` | ITR OCR | panNumber, assessmentYear, totalIncome |
| `COWIN` | COVID Certificate OCR | vaccinationStatus, doses, certificateId |

### VERIFY Rules (23 total)

#### Verification Types

| Source Type | Rule Name | Input Fields | Output Fields |
|-------------|-----------|--------------|---------------|
| `PAN_TO_CIN` | PAN to CIN Validation | PAN | Company CIN, Company Name, DateOfInc, ROC City, Reg Number, Category |
| `SECTION_206AB` | Section 206AB Verification | PAN | Pan Name, Allotment Date, Financial Year, Aadhaar Link Status |
| `GSTIN_VERIFICATION` | GSTIN Verification | GSTIN | Legal Name, Trade Name, Status, Address, Registration Date |
| `BANK_ACCOUNT` | Bank Account Verification | Account Number, IFSC | Account Holder Name, Bank Name, Branch |
| `EXTERNAL_DATA_VALUE` | Get Data From EDV | Variable Key | External Data Value |

### COPY_TO Rules (20 total)

| Rule Name | Source | Destination |
|-----------|--------|-------------|
| Copy Aadhaar Signer Details | AADHAAR_SIGNER_DETAILS | commonName, title, yob, gender |
| Copy CreatedBy Details | CREATED_BY | Creator information fields |
| Copy CreatedFor Details | CREATED_FOR | Target party information fields |
| Copy to Transaction Attr1-8 | Form field | Transaction attribute 1-8 |
| Copy to Document Storage ID | Document | Storage ID field |
| Copy to Generic Party Name | Form field | Generic party name |
| Copy to Generic Party Email | Form field | Generic party email |
| Copy to Generic Party Mobile | Form field | Generic party mobile |

### Rule Schema Structure

```json
{
  "id": 347,
  "name": "GSTIN OCR",
  "source": "GSTIN_IMAGE",
  "action": "OCR",
  "processingType": "SERVER",
  "applicableTypes": ["GSTIN_IMAGE"],
  "sourceFields": {
    "numberOfItems": 1,
    "fields": [
      {"name": "GSTIN Image", "ordinal": 1, "mandatory": true}
    ]
  },
  "destinationFields": {
    "numberOfItems": 11,
    "fields": [
      {"name": "regNumber", "ordinal": 1, "mandatory": false},
      {"name": "legalName", "ordinal": 2, "mandatory": false},
      {"name": "tradeName", "ordinal": 3, "mandatory": false}
      // ... more fields
    ]
  },
  "params": {
    "paramType": "json",
    "jsonSchema": { /* parameter schema */ }
  },
  "deleted": false,
  "validatable": true,
  "skipValidations": false,
  "conditionsRequired": true
}
```

---

## Source Field Identification

### What is a Source Field?

The **source field** is the field whose value:
- Is checked in a condition (for expression rules)
- Provides input data (for OCR/validation rules)
- Is copied FROM (for copy rules)

### Source Field Patterns in Logic Text

#### Pattern 1: "if {field} is {value}"
```
Logic: "Make visible if GST Option is Yes"
Source: "GST Option"
```

#### Pattern 2: "based on {field}"
```
Logic: "Dropdown values will come based on Account Group selection"
Source: "Account Group"
```

#### Pattern 3: "when {field} is selected"
```
Logic: "Visible when Country is selected as India"
Source: "Country"
```

#### Pattern 4: "field {field} value is"
```
Logic: "If the field Do you wish to add additional mobile numbers value is Yes"
Source: "Do you wish to add additional mobile numbers"
```

#### Pattern 5: "data from {source}" / "copy from {source}"
```
Logic: "Data will come from GSTIN verification"
Source: GSTIN field (for verification rule)

Logic: "Copy from Basic Details panel"
Source: Fields in Basic Details panel
```

#### Pattern 6: "Get {data} from {rule}"
```
Logic: "Get GSTIN from OCR rule"
Source: GSTIN Image upload field
```

#### Pattern 7: "Apply {rule} on {field}"
```
Logic: "Apply PAN OCR on uploaded PAN card"
Source: PAN card upload field
```

### Source Field for Standard Rules

| Rule Type | Source Field Is |
|-----------|-----------------|
| OCR | File upload field for the document type |
| VALIDATION | Text/number field containing data to validate |
| VERIFY | Field containing ID/number to verify externally |
| COPY_TO | Field containing value to copy |

### Document Type to Upload Field Mapping

| Document Type Keyword | Expected Upload Field Keywords |
|----------------------|-------------------------------|
| PAN | "pan card", "pan image", "pan upload", "upload pan" |
| Aadhaar | "aadhaar", "aadhar", "aadhaar front", "aadhaar image" |
| Aadhaar Back | "aadhaar back", "aadhar back" |
| GST / GSTIN | "gst certificate", "gstin", "gst image", "gst upload" |
| Passport | "passport", "passport front", "passport image" |
| Cheque | "cheque", "cancelled cheque", "bank cheque" |
| Driving License | "driving", "licence", "dl", "driving license" |

---

## Destination Field Identification

### What is a Destination Field?

The **destination field** is the field that:
- Is affected by the rule (shown/hidden/enabled/disabled)
- Receives data (from OCR/validation/copy)
- Has its mandatory status changed

### Destination Field Patterns in Logic Text

#### Pattern 1: Current Field as Default
```
Field: "GSTIN"
Logic: "Make visible if GST Option is Yes"
Destination: GSTIN (the current field itself)
```

#### Pattern 2: Explicit "make {field} visible/mandatory"
```
Logic: "Make Additional Mobile Number 1 visible"
Destination: "Additional Mobile Number 1"
```

#### Pattern 3: "then {field} should be"
```
Logic: "If Yes, then GST Certificate should be mandatory"
Destination: "GST Certificate"
```

#### Pattern 4: "copy to {field}" / "store in {field}"
```
Logic: "Copy to Address Details panel"
Destination: Fields in Address Details panel

Logic: "Store the data in next fields"
Destination: Following fields in document order
```

#### Pattern 5: Multiple destinations with "and"
```
Logic: "Make visible GSTIN and GST Address"
Destinations: ["GSTIN", "GST Address"]
```

### Destination Fields from Rule Schema

For Standard Rules, destinations come from `destinationFields` in Rule-Schemas.json:

| Rule | Schema Destinations | Map To Document Fields |
|------|--------------------|-----------------------|
| PAN OCR | panNo, name, fatherName, dob | "PAN Number", "Name as per PAN", "Father's Name", "Date of Birth" |
| GSTIN OCR | regNumber, legalName, tradeName, address1, pin, state, city | "GSTIN", "Legal Name", "Trade Name", "Address Line 1", "PIN Code", "State", "City" |
| Aadhaar OCR | aadharNumberMasked, name, gender, dob | "Aadhaar Number", "Name", "Gender", "Date of Birth" |

### Schema Field to Document Field Mapping Examples

| Schema Field | Possible Document Field Names |
|--------------|------------------------------|
| `panNo` | "PAN Number", "PAN", "PAN No" |
| `name` | "Name", "Full Name", "Name as per PAN", "Name as per Aadhaar" |
| `fatherName` | "Father's Name", "Father Name" |
| `dob` | "Date of Birth", "DOB", "Birth Date" |
| `regNumber` | "GSTIN", "GST Number", "Registration Number" |
| `legalName` | "Legal Name", "Legal Name as per GST" |
| `tradeName` | "Trade Name", "Business Name" |
| `address1` | "Address Line 1", "Address 1", "Street" |
| `pin` | "PIN Code", "Pincode", "PIN" |
| `state` | "State", "State Name" |
| `city` | "City", "City Name" |

---

## Logic Patterns from Documents

### Actual Logic Examples from Vendor Creation BUD

#### Visibility + Mandatory Combined
```
Field: "Mobile Number 2 (Domestic)"
Logic: "Make visible and Mandatory if "Do you wish to add additional mobile numbers (India)?" is Yes otherwise it should be invisible and non-mandatory."

Source: "Do you wish to add additional mobile numbers (India)?"
Destination: "Mobile Number 2 (Domestic)"
Actions: mvi, mm (if Yes), minvi, mnm (if not Yes)
```

#### OCR with Visibility Condition
```
Field: "GSTIN IMAGE"
Logic: "if the field "Please select GST option" values is yes then visible and mandatory otherwise invisible and non-mandatory. System should allow upload size up to 15 Mb. Get GSTIN from OCR rule"

Source (visibility): "Please select GST option"
Source (OCR): This field itself (GSTIN IMAGE)
Destination (OCR): GSTIN and related fields
Actions: mvi, mm (if Yes), minvi, mnm (if No), OCR
```

#### Validation with Data Flow
```
Field: "GSTIN"
Logic: "if the field "Please select GST option" values is yes then visible and mandatory otherwise invisible and non-mandatory. Data will come from GSTIN OCR rule. Perform GSTIN validation and store the data in next fields. Apply PAN with GST rule also."

Source (visibility): "Please select GST option"
Source (data): GSTIN IMAGE (OCR)
Destination: This field + next fields
Actions: mvi, mm, GSTIN OCR, GSTIN Validation
```

#### Conditional Copy
```
Field: "Street 1"
Logic: "If GST uploaded then copy the data from GST field and Non-Mandatory, Non-Editable. If GST is not uploaded then it is mandatory. If Aadhaar is uploaded then get the data from Aadhaar OCR and non-editable. If Electricity bill is uploaded then user will enter the data"

Sources: GST fields, Aadhaar fields
Conditions: GST uploaded, Aadhaar uploaded, Electricity bill uploaded
Actions: ctfd, mm/mnm, en/dis based on conditions
```

#### Disable Only
```
Field: "Transaction ID"
Logic: "System-generated transaction ID from Manch (Non-Editable) • Disable"

Source: None (system generated)
Destination: This field
Actions: dis(true, "__transaction_id__")
```

#### Derived/Calculated Field
```
Field: "Vendor Domestic or Import"
Logic: "Default behaviour is Invisible, If account group/vendor type is selected as ZDES, ZDOM, ZRPV, ZONE (any one) then derived it as Domestic. If Account group/vendor type is selected as ZIMP, ZSTV, ZDAS (any one) then derived it as import • Disable"

Source: "Account group/vendor type"
Destination: This field
Actions: minvi (default), ctfd with derived values based on selection
```

### Logic Pattern Statistics (Vendor Creation BUD)

| Pattern Type | Count | Percentage |
|--------------|-------|------------|
| Disable rules | 58 | 41% |
| Visibility rules | 48 | 34% |
| Mandatory rules | 48 | 34% |
| Validation rules | 38 | 27% |
| Dropdown logic | 25 | 18% |
| Copy rules | 19 | 13% |
| OCR rules | 12 | 8% |

Note: Many fields have multiple rule types (e.g., visibility + mandatory).

---

## Rule Schema Structure

### Complete Rule Object Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | number | Unique rule identifier |
| `name` | string | Rule display name |
| `source` | string | Source type (e.g., "PAN_IMAGE", "GSTIN_IMAGE") |
| `action` | string | Action type (e.g., "OCR", "VERIFY", "VALIDATION") |
| `processingType` | string | "SERVER" or "CLIENT" |
| `applicableTypes` | array | List of applicable document/field types |
| `sourceFields` | object | Input fields specification |
| `destinationFields` | object | Output fields specification |
| `params` | object | Additional parameters and schema |
| `deleted` | boolean | Soft delete flag |
| `validatable` | boolean | Whether rule can be validated |
| `skipValidations` | boolean | Skip validation flag |
| `conditionsRequired` | boolean | Whether conditions are required |
| `button` | string | Button text (e.g., "Verify", "Extract") |
| `updateUser` | string | "FIRST_PARTY" or "SECOND_PARTY" |

### Field Specification Structure

```json
{
  "numberOfItems": 4,
  "fields": [
    {
      "name": "fieldName",
      "ordinal": 1,
      "mandatory": false,
      "unlimited": false
    }
  ]
}
```

### All Action Types (97 unique)

```
APP_USER_LIST, APP_USER_TO_TRANSACTION_CREATED_FOR_RULE, CALCULATE_TDS,
CHECK_DUPLICATE, CLASSIFY_DOCUMENT, CLEAR_FIELD, COMPARE,
COMPARE_DATE_WITH_OFFSET, COMPARE_DESTINATION_TIME, COMPARE_SOURCE_TIME,
CONCAT, CONDITIONAL_COPY, CONTAINS_TEXT, CONVERT_TO, CONVERT_TO_WORDS,
COPY_TO, COPY_TO_DOCUMENT_STORAGE_ID, COPY_TO_GENERIC_PARTY_*,
COPY_TO_TRANSACTION_ATTR1-8, COPY_TO_TRANSACTION_CHAIN_TXN_ID,
COPY_TO_TRANSACTION_INTERNAL_ATTR1-4, COUNT, COUNT_NUMBER_OF_VALUES_AVAILABLE,
CUSTOMER_FEEDBACK_SENTIMENT, DELETE_DOCUMENT, DELETE_FILE,
DERIVE_FINANCIAL_YEAR, DETECT_MENU, DOES_NOT_CONTAIN_TEXT,
DUPLICATE_VALUE_CHECK, EMPLOYEE_CODE_GENERATION, EXECUTE,
EXPORT_IMPORT_FORMFILLDATA, EXTRACT_GPS_COORDINATES, EXT_DROP_DOWN,
EXT_VALUE, FACE_COMPARE, FETCH_RELATED_TRANSACTIONS,
GENERATE_ARRAY_FORM_GROUPS, GENERATE_ESTAMP, GET_DISTANCE,
GET_GEOLOCATION, GET_LOCATION, GIG_INDIA_NAME_MATCH, INSERT_INTO_TABLE,
LOOKUP, MAKE_ACTION_BASED_ON_FORMFILL_TXN_INFO, MAKE_DISABLED,
MAKE_DOCUMENT_SIGN_MANDATORY, MAKE_DOCUMENT_UPLOAD_MANDATORY,
MAKE_ENABLED, MAKE_INVISIBLE, MAKE_MANDATORY, MAKE_NON_MANDATORY,
MAKE_VISIBLE, OCR, OUT_OF_POLYGON_CHECK, PAYMENT_STATUS_CHECK,
PULL_CLOUD_DOCUMENT, QC_RELOAD_AMOUNT_RULE, QUARTER, QWIK_POS_CREATE_CODE,
REASSIGN_CREATED_FOR, SEND_EMAIL_FOR_VERIFICATION, SEND_OTP,
SESSION_BASED_MAKE_*, SET_AGE_FROM_DATE, SET_DATE,
SET_DATE_FROM_MONTH_OR_YEAR, SET_DATE_FROM_PREV_DATE_OR_CMP_TWO_DATE,
SET_ESIGN_AUTH_MODE, SET_START_END_DATE_VALIDATION,
SET_START_OR_END_DATE_IN_WEEK, SPEECH_TO_TEXT, UNDELETE_DOCUMENT,
UPLOAD_FILE_SIZE_LIMIT, VALIDATE_OTP, VALIDATION, VERIFY,
VERIFY_LIVELINESS_OTP, VERIFY_QC_REGISTRATION_CODE, VIDEO_KYC
```

---

## Quick Reference

### Expression Rule Template

```javascript
// Visibility: show if condition, hide otherwise
mvi(vo("__source_field__") == 'Yes', "__dest_field__");
minvi(vo("__source_field__") != 'Yes', "__dest_field__");

// Mandatory: required if condition, optional otherwise
mm(vo("__source_field__") == 'Yes', "__dest_field__");
mnm(vo("__source_field__") != 'Yes', "__dest_field__");

// Disable field (always read-only)
dis(true, "__field__");

// Copy value conditionally
ctfd(vo("__condition_field__") == 'Yes', vo("__source__"), "__dest__");

// Clear field conditionally
cf(vo("__condition_field__") == 'No', "__field_to_clear__");
```

### Com
mon Logic to Expression Mapping

| Logic Pattern | Expression |
|---------------|------------|
| "visible if X is Yes" | `mvi(vo("__x__")=='Yes', "__current__")` |
| "mandatory if X is Yes" | `mm(vo("__x__")=='Yes', "__current__")` |
| "invisible and non-mandatory otherwise" | `minvi(vo("__x__")!='Yes', "__current__"); mnm(vo("__x__")!='Yes', "__current__")` |
| "disable" / "non-editable" | `dis(true, "__current__")` |
| "copy from X" | `ctfd(true, vo("__x__"), "__current__")` |
| "based on X selection" | Condition uses `vo("__x__")` |
