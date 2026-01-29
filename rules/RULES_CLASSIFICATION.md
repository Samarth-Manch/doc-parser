# Manch Platform Rules Classification

This document classifies all 182 rules supported by the Manch platform into functional buckets to help narrow down search space when selecting appropriate rules.

## Rule Types Overview

There are **two main types of rules**:

1. **Standard/Pre-defined Rules** - Server-side or client-side rules with specific functionality (182 rules)
2. **Expression Rules** - Custom JavaScript-like expressions using expr-eval library for complex conditional logic

---

## Bucket Classification

### 1. Aadhaar Rules (OCR + Validation)
**Purpose:** Extract and verify Aadhaar card data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 359 | Aadhaar Front OCR | OCR | SERVER | Extract name, gender, dob, aadhaar number, age from front |
| 348 | Aadhaar Back OCR | OCR | SERVER | Extract address, pin, city, state, father name from back |
| 303 | Offline Aadhaar EKYC | VALIDATION | SERVER | Verify Aadhaar via offline XML |
| 187 | Copy Aadhaar Signer Details | COPY | SERVER | Copy Aadhaar signer info to fields |

**Use Case:** When working with Aadhaar cards - extract data from uploaded images and verify against UIDAI.

---

### 2. PAN Rules (OCR + Validation)
**Purpose:** Extract and verify PAN card data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 344 | PAN OCR | OCR | SERVER | Extract PAN number, name, father name, dob |
| 360 | Validate PAN | VALIDATION | SERVER | Verify PAN with name, type, Aadhaar seeding status |
| 213 | Validate PAN (Client) | VALIDATION | CLIENT | Client-side PAN validation |
| 236 | Validate PAN V2 | VALIDATION | SERVER | Enhanced PAN validation |
| 289 | PAN to CIN Validation | VALIDATION | SERVER | Map company PAN to CIN |

**Use Case:** When working with PAN cards - extract data and verify against Income Tax database.

---

### 3. GSTIN Rules (OCR + Validation)
**Purpose:** Extract and verify GST registration data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 347 | GSTIN OCR | OCR | SERVER | Extract GSTIN, legal name, trade name, address |
| 253 | GSTIN OCR (Client) | OCR | CLIENT | Client-side GSTIN extraction |
| 355 | Validate GSTIN | VALIDATION | SERVER | Verify GST registration, jurisdiction |
| 296 | Validate GSTIN With PAN | VALIDATION | SERVER | Cross-validate GSTIN with PAN |
| 274 | Validate GSTN Filing | VALIDATION | SERVER | Check GST return filing status |

**Use Case:** When working with GST certificates - extract and verify registration status.

---

### 4. Driving License Rules (OCR + Validation)
**Purpose:** Extract and verify driving license data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 250 | Driving License (India) OCR | OCR | SERVER | Extract DL number, name, dob, validity, address |
| 261 | Validate Driving Licence | VALIDATION | SERVER | Verify DL validity, vehicle classes, address |

**Use Case:** When working with driving licenses - extract and verify against RTO database.

---

### 5. Passport Rules (OCR)
**Purpose:** Extract passport data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 204 | Passport Front (India) OCR | OCR | SERVER | Extract passport no, name, nationality, dob, expiry |
| 318 | Passport Back (India) OCR | OCR | SERVER | Extract father name, mother name, address |

**Use Case:** When working with passports - extract data from uploaded images.

---

### 6. Voter ID Rules (OCR + Validation)
**Purpose:** Extract and verify voter ID data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 312 | Voter Id OCR | OCR | SERVER | Extract voter ID, name, father name, dob, gender |
| 182 | Validate Voter Id | VALIDATION | SERVER | Verify against electoral roll with district, state |

**Use Case:** When working with voter ID cards - extract and verify against electoral database.

---

### 7. Vehicle Registration Rules (OCR + Validation)
**Purpose:** Extract and verify vehicle registration data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 269 | Cheque OCR | OCR | SERVER | Extract bank name, IFSC, account number (from cancelled cheque) |
| 279 | Validate RC | VALIDATION | SERVER | Verify vehicle registration, owner, insurance, fitness |

**Use Case:** When working with vehicle documents - verify RC against RTO database.

---

### 8. Company/CIN Rules (OCR + Validation)
**Purpose:** Extract and verify company registration data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 357 | CIN OCR | OCR | SERVER | Extract CIN number, company name, PAN, address |
| 349 | Validate CIN | VALIDATION | SERVER | Verify company registration, directors, MCA status |

**Use Case:** When working with company documents - extract and verify against MCA database.

---

### 9. MSME/Udyam Rules (OCR + Validation)
**Purpose:** Extract and verify MSME registration data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 214 | MSME OCR | OCR | SERVER | Extract Udyam number, name, category, address |
| 337 | Validate MSME | VALIDATION | SERVER | Verify MSME/Udyam registration, enterprise type |

**Use Case:** When working with MSME certificates - extract and verify Udyam registration.

---

### 10. FSSAI Rules (OCR + Validation)
**Purpose:** Extract and verify food license data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 327 | FSSAI OCR | OCR | SERVER | Extract registration no, name, validity, business type |
| 356 | Validate FSSAI | VALIDATION | SERVER | Verify food license validity, category |
| 271 | Validate FSSAI Application Number | VALIDATION | SERVER | Verify FSSAI application status |

**Use Case:** When working with food business licenses - extract and verify FSSAI registration.

---

### 11. TAN Rules (OCR + Validation)
**Purpose:** Extract and verify TAN data

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 305 | TDS OCR | OCR | SERVER | Extract deductor name, TAN, certificate no, year |
| 322 | Validate TAN | VALIDATION | SERVER | Verify Tax deduction account number |
| 311 | Validate TAN (Client) | VALIDATION | CLIENT | Client-side TAN validation |

**Use Case:** When working with TDS certificates - extract and verify TAN.

---

### 12. Other Document OCR Rules
**Purpose:** Extract data from other document types

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 216 | Business Card OCR | OCR | SERVER | Extract name, company, emails, phones, address |
| 306 | Cowin OCR | OCR | SERVER | Extract vaccination details |
| 194 | IncomeTax Return OCR | OCR | SERVER | Extract ITR details, income, tax |
| 208 | IncomeTax Return Summary OCR | OCR | SERVER | Extract income tax summary |
| 189 | Oversea Document OCR | OCR | SERVER | Generic OCR for overseas documents |

**Use Case:** Extract data from business cards, vaccination certificates, ITR documents.

---

### 13. Other Validation Rules
**Purpose:** Verify other business registrations and compliance

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 290 | Validate Drug Licence | VALIDATION | SERVER | Verify drug license |
| 335 | Validate Shops and Est | VALIDATION | SERVER | Verify shop & establishment registration |
| 319 | Section206ABVerification | VALIDATION | SERVER | Section 206AB compliance for TDS |
| 244 | Validate eInvoice Status | VALIDATION | SERVER | E-invoice generation status |

**Use Case:** Verify drug licenses, shop registrations, tax compliance.

---

### 14. Bank Account Validation Rules
**Purpose:** Verify bank account details

| Rule ID | Rule Name | Type | Processing | Description |
|---------|-----------|------|------------|-------------|
| 361 | Validate Bank Account | VALIDATION | SERVER | Verify bank account with beneficiary name |
| 269 | Cheque OCR | OCR | SERVER | Extract bank details from cancelled cheque |

**Use Case:** When verifying bank account ownership - penny drop verification.

---

### 15. EDV (External Data Value) Rules
**Purpose:** Work with external lookup tables for dropdown population, data retrieval, and validation

| Rule ID | Rule Name | Action | Purpose |
|---------|-----------|--------|---------|
| 295 | EDV Dropdown (Client) | EXT_VALUE | Populate dropdown from EDV table |
| 196 | Validate External Data Value (Client) | VERIFY | Client-side EDV validation |
| 346 | Validate EDV (Server) | VALIDATION | Server-side EDV validation |
| 285 | Get Data From EDV | VERIFY | Retrieve data from EDV (e.g., IFSC to bank name) |
| 266 | Count EDV Records | COUNT | Count matching EDV records |
| 281 | Create Master Record | INSERT_INTO_TABLE | Insert new record into EDV table |
| 320 | Generate Table From EDV | GENERATE_ARRAY_FORM_GROUPS | Create dynamic table from EDV data |
| 353 | Fetch Related Txns External Data Value (Client) | FETCH_RELATED_TRANSACTIONS | Fetch related transactions via EDV |
| 207 | Set Date EDV (Client) | SET_DATE | Set date from EDV lookup |

**Common EDV Use Cases:**
- IFSC code lookup to get bank name and branch
- State/City cascading dropdowns
- Product catalog lookups
- Custom validation against master data tables

**Use Case:** When you need to populate dropdowns from external tables or validate against master data.

---

### 16. FFD (Form Fill Dropdown) Rules
**Purpose:** Work with form-specific dropdown tables

| Rule ID | Rule Name | Action | Purpose |
|---------|-----------|--------|---------|
| 192 | FFD Dropdown (Client) | EXT_DROP_DOWN | Populate dropdown from FFD table |
| 226 | Create FFDD Record | INSERT_INTO_TABLE | Insert new dropdown record |
| 219 | Invalidate FFDD Record | DUPLICATE_VALUE_CHECK | Mark FFD record as invalid |
| 330 | Get value from FFDD | VALIDATION | Retrieve value from FFD |
| 222 | Generate Table Form DropDown | GENERATE_ARRAY_FORM_GROUPS | Create table from FFD |
| 331 | AppUser List FormFillDropDown (Client) | APP_USER_LIST | Populate dropdown with app users |

**Use Case:** When you need template-specific dropdown options or cascading dropdowns.

---

### 17. AI/ML Rules
**Purpose:** Intelligent document processing, face recognition, and natural language features

| Rule ID | Rule Name | Action | Purpose |
|---------|-----------|--------|---------|
| 186 | ClassifyImage | CLASSIFY_DOCUMENT | Classify document type using AI |
| 278 | Detect Document Type | DETECT_MENU | Detect if document is a menu/form |
| 273 | Compare Face | FACE_COMPARE | Compare faces in two images for verification |
| 362 | Speech To Text | SPEECH_TO_TEXT | Convert audio to text transcription |
| 365 | Customer Feedback Sentiment | CUSTOMER_FEEDBACK_SENTIMENT | Analyze customer feedback sentiment |
| 333 | GigIndiaNameMatch | GIG_INDIA_NAME_MATCH | AI-based name matching for identity verification |

**Use Case:** When you need intelligent document processing, biometric verification, speech-to-text, or sentiment analysis.

---

### 18. Form Control Rules (UI Visibility/State)
**Purpose:** Control field visibility, mandatory status, and enabled state

#### Visibility Rules
| Rule ID | Rule Name | Action | Processing |
|---------|-----------|--------|------------|
| 343 | Make Visible (Client) | MAKE_VISIBLE | CLIENT |
| 336 | Make Invisible (Client) | MAKE_INVISIBLE | CLIENT |
| 191 | Make Visible - Session Based (Client) | SESSION_BASED_MAKE_VISIBLE | CLIENT |
| 217 | Make Invisible - Session Based (Client) | SESSION_BASED_MAKE_INVISIBLE | CLIENT |

#### Mandatory Rules
| Rule ID | Rule Name | Action | Processing |
|---------|-----------|--------|------------|
| 325 | Make Mandatory (Client) | MAKE_MANDATORY | CLIENT |
| 288 | Make Non Mandatory (Client) | MAKE_NON_MANDATORY | CLIENT |
| 252 | Make Mandatory - Session Based (Client) | SESSION_BASED_MAKE_MANDATORY | CLIENT |
| 197 | Make NonMandatory - Session Based (Client) | SESSION_BASED_MAKE_NON_MANDATORY | CLIENT |

#### Enable/Disable Rules
| Rule ID | Rule Name | Action | Processing |
|---------|-----------|--------|------------|
| 185 | Enable Field (Client) | MAKE_ENABLED | CLIENT |
| 314 | Disable Field (Client) | MAKE_DISABLED | CLIENT |
| 272 | Enable Field - Session Based (Client) | SESSION_BASED_MAKE_ENABLED | CLIENT |
| 193 | Make Disable - Session Based (Client) | SESSION_BASED_MAKE_DISABLED | CLIENT |

#### Document Visibility
| Rule ID | Rule Name | Action | Purpose |
|---------|-----------|--------|---------|
| 229 | Hide Document | DELETE_DOCUMENT | Hide a document type |
| 238 | Unhide Document | UNDELETE_DOCUMENT | Show hidden document |
| 262 | Unhide Document (Client) | UNDELETE_DOCUMENT | Client-side unhide |
| 283 | Delete Document | DELETE_FILE | Permanently delete document |
| 200 | Make Document Sign Mandatory | MAKE_DOCUMENT_SIGN_MANDATORY | Require document signature |
| 230 | Make Upload Mandatory | MAKE_DOCUMENT_UPLOAD_MANDATORY | Require document upload |

**Use Case:** When you need to show/hide fields based on conditions or control form behavior.

---

### 19. Data Copy & Transform Rules
**Purpose:** Copy values between fields and transform data

#### Field-to-Field Copy
| Rule ID | Rule Name | Action | Purpose |
|---------|-----------|--------|---------|
| 270 | Copy Value | COPY_TO | Copy value between form fields |
| 210 | Copy To FormField Client (Client) | COPY_TO | Client-side copy |
| 228 | Conditional Copy (Client) | CONDITIONAL_COPY | Copy based on condition |
| 221 | Clear FormField (Client) | CLEAR_FIELD | Clear field value |

#### Transaction Attribute Copy
| Rule ID | Rule Name | Destination |
|---------|-----------|-------------|
| 260 | Copy To Attr1 | Transaction Attr1 |
| 190 | Copy To Attr2 | Transaction Attr2 |
| 324 | Copy To Attr3 | Transaction Attr3 |
| 184 | Copy To Attr4 | Transaction Attr4 |
| 188 | Copy To Attr5 | Transaction Attr5 |
| 225 | Copy To Attr6 | Transaction Attr6 |
| 341 | Copy To Attr7 | Transaction Attr7 |
| 280 | Copy To Attr8 | Transaction Attr8 |
| 302 | Copy To Internal Attr1 | Internal Attr1 |
| 263 | Copy To Internal Attr2 | Internal Attr2 |
| 317 | Copy To Internal Attr3 | Internal Attr3 |
| 334 | Copy To Internal Attr4 | Internal Attr4 |

#### Party Details Copy
| Rule ID | Rule Name | Copies |
|---------|-----------|--------|
| 277 | Copy FirstParty Name | First party name |
| 227 | Copy FirstParty Email | First party email |
| 233 | Copy FirstParty Mobile Number | First party mobile |
| 310 | Copy FirstParty Company Name | Company name |
| 241 | Copy To SecondParty Name | Second party name |
| 256 | Copy To SecondParty Email | Second party email |
| 212 | Copy To SecondParty Mobile Number | Second party mobile |
| 203 | Copy To SecondParty Company Name | Company name |
| 240 | Copy To GenericParty Name | Generic party name |
| 249 | Copy To GenericParty Email | Generic party email |
| 358 | Copy To GenericParty Mobile Number | Generic party mobile |
| 215 | Copy To GenericParty Company Name | Company name |
| 258 | Copy CreatedBy Details | Creator details |
| 287 | Copy CreatedFor Details | Created-for details |

#### Data Transformation
| Rule ID | Rule Name | Transform |
|---------|-----------|-----------|
| 294 | Concatenate | Join multiple field values |
| 298 | Convert To Lower Case (Client) | To lowercase |
| 345 | Convert to UPPER (Client) | To uppercase |
| 183 | Convert To Words (Client) | Number to words |

#### Other Copy Operations
| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 264 | Copy To Transaction Title | Set transaction title |
| 300 | Copy To Transaction Message | Set transaction message |
| 342 | Copy to Title | Set workflow data title |
| 257 | Copy To WorkFlowData Message | Set workflow message |
| 246 | Copy to Supporting Document | Link supporting document |
| 254 | Copy Offer Transaction Details | Chain transaction copy |
| 297 | Copy To Option Name | Copy dropdown option name |
| 284 | Reset PreFill Value | Reset prefilled data |

**Use Case:** When you need to copy or transform data between fields.

---

### 20. Comparison & Validation Rules
**Purpose:** Compare values and validate field content

| Rule ID | Rule Name | Action | Purpose |
|---------|-----------|--------|---------|
| 232 | Compare Text | CONTAINS_TEXT | Check if text contains substring |
| 326 | Does Not Contain | DOES_NOT_CONTAIN_TEXT | Check text doesn't contain |
| 243 | Compare If Same | VALIDATION | Validate two fields match |
| 352 | Compare If Not Same | VALIDATION | Validate two fields differ |
| 354 | Compare Name | COMPARE | Name comparison with fuzzy matching |
| 237 | Validation Same As FormField (Client) | VALIDATION | Client-side same value check |
| 267 | SameAsFormFllMetadataValidationV2 | VALIDATION | Enhanced same value validation |
| 350 | Validate Same FromFillMetadata | VALIDATION | Validate and compare form data |
| 242 | De-duplication check | VALIDATION | Check for duplicate records |
| 195 | Check Duplicate | CHECK_DUPLICATE | Find duplicate transactions |

**Use Case:** When you need to validate that values match or check for duplicates.

---

### 21. Date & Time Rules
**Purpose:** Date manipulation, comparison, and calculations

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 259 | Set Age From Date | Calculate age from DOB (server) |
| 276 | Set Age From Date (Client) | Calculate age from DOB (client) |
| 202 | Check Data Range | Validate date within range |
| 286 | Compare Date With Offset | Compare date with offset |
| 301 | Compare Time | Compare time values |
| 315 | Compare time with start time | Compare with start time |
| 234 | Split Date | Split date into day/month/year |
| 206 | Set Date From Month Or Year (Client) | Construct date from parts |
| 209 | Set Date From Previous Date Or Compare Two Date (Client) | Date operations |
| 239 | SetNextOrPreviousWeekdayFromDate | Get weekday from date |
| 201 | Set Date Firstparty Mobile No (Client) | Set date from party info |
| 309 | Get FY | Get financial year from date |
| 332 | Derive QTR | Get quarter from date |

**Use Case:** When you need to work with dates - age calculation, date validation, period derivation.

---

### 22. Geolocation Rules
**Purpose:** Location-based validation and calculations

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 265 | Calculate Distance | Calculate distance between coordinates |
| 329 | Check Location Serviceability | Check if location is serviceable |
| 211 | Get Lat/Long From Address | Geocode address to coordinates |
| 351 | Get Lat/Long From Image | Extract GPS from image EXIF |
| 220 | Get Location Generic Map (Client) | Get location from map |
| 308 | Get Distance Generic Map (Client) | Calculate distance on map |
| 199 | Out Of Polygon Check (Client) | Check if point is within polygon |

**Use Case:** When you need location validation, distance calculation, or geo-fencing.

---

### 23. Calculation & Financial Rules
**Purpose:** Financial calculations and TDS processing

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 307 | Calculate TDS | Calculate TDS amount based on rules |
| 205 | Calculate BulkBatch Liability | Calculate bulk batch liability |
| 282 | Validate BulkBatch | Validate bulk batch data |
| 291 | Get Count | Count values in fields |

**Use Case:** When you need to calculate TDS or process financial batches.

---

### 24. Table Generation Rules
**Purpose:** Create dynamic tables from data sources

| Rule ID | Rule Name | Source |
|---------|-----------|--------|
| 320 | Generate Table From EDV | External Data Value |
| 222 | Generate Table Form DropDown | Form Fill Dropdown |
| 321 | Generate Table Form Staging | Staging Data |
| 323 | Generate Table From Transaction | Transaction |

**Use Case:** When you need to create dynamic repeating sections or tables.

---

### 25. OTP & Verification Rules
**Purpose:** Send and validate one-time passwords

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 339 | Send Email OTP (Client) | Send OTP via email |
| 338 | Send Mobile OTP (Client) | Send OTP via SMS |
| 340 | Validate Otp (Client) | Validate entered OTP |
| 255 | Validate Email | Email verification link |
| 275 | Validate Liveliness Otp (Client) | Liveliness check OTP |

**Use Case:** When you need OTP-based verification.

---

### 26. KYC & eSign Rules
**Purpose:** Digital signature and KYC verification

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 223 | DigiLocker E-Kyc (Client) | Fetch documents from DigiLocker |
| 299 | Video Kyc (Client) | Video-based KYC |
| 292 | Set eSign Auth Mode | Configure eSign authentication |
| 313 | Generate eStamp | Generate eStamp certificate |

**Use Case:** When you need digital KYC or eSignature.

---

### 27. Expression Rules (Custom Logic)
**Purpose:** Execute custom JavaScript-like expressions for complex conditional logic

| Rule ID | Rule Name | Processing |
|---------|-----------|------------|
| 328 | Expression (Client) | CLIENT |

**Expression Functions Available:**
- `vo(id)` / `valOf(id)` - Get field value by ID
- `mvi(condition, destIds)` - Make visible if condition true
- `minvi(condition, destIds)` - Make invisible if condition true
- `mm(condition, destIds)` - Make mandatory if condition true
- `mnm(condition, destIds)` - Make non-mandatory if condition true
- `en(condition, destIds)` - Enable if condition true
- `dis(condition, destIds)` - Disable if condition true
- `ctfd(condition, srcValue, destIds)` - Copy to fill data if condition true
- `cf(condition, destIds)` - Clear field if condition true
- `adderr(condition, message, destIds)` - Add error message
- `remerr(condition, destIds)` - Remove error message
- `concat(values)` - Concatenate values
- `cwd(delimiter, values)` - Concatenate with delimiter
- `tolc(value)` / `touc(value)` - Case conversion
- `cntns(seq, value)` - Check if string contains
- `vso(id)` - Get validation status
- `pt()` - Get party type (FP/SP)
- `mt()` - Get member type (CREATED_BY, APPROVER, etc.)
- `rplrng(str, start, end, subst)` - Replace range in string
- `rgxtst(value, regex)` - Test regex pattern
- `setAgeFromDate(srcId, destId)` - Calculate age from date

**Use Case:** When pre-defined rules don't cover your logic needs.

---

### 28. User & Assignment Rules
**Purpose:** User lookup and assignment operations

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 251 | Fetch user details | Get user details by ID/email/mobile |
| 231 | Copy User As CreatedFor | Assign user as created-for |
| 248 | Reassign Create For | Reassign transaction to different user |

**Use Case:** When you need to look up or assign users dynamically.

---

### 29. Payment & POS Rules
**Purpose:** Payment processing and POS integration

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 218 | Check Payment Status (Client) | Check payment status |
| 198 | Qc Bosch Quick POS | Bosch POS verification |
| 304 | Qc Qwik POS Create Code | Create POS code |
| 316 | Qc Reload Amount | Reload amount to card |

**Use Case:** When integrating with payment systems or POS terminals.

---

### 30. Utility Rules
**Purpose:** Various utility functions

| Rule ID | Rule Name | Purpose |
|---------|-----------|---------|
| 245 | Generate Unique Code | Generate unique identifiers |
| 268 | Reminder Service | Configure reminders |
| 224 | Export Import FormField (Client) | Export/import form data |
| 293 | Make Action Based On FormFill Txn Info (Client) | Action based on transaction |
| 247 | Upload File Size Limit First Party Email (Client) | Limit file upload size |
| 364 | Lookup Staging Data | Query staging data |

---

## Bucket Selection Guide

| Need | Bucket |
|------|--------|
| Extract/verify Aadhaar | Aadhaar Rules |
| Extract/verify PAN | PAN Rules |
| Extract/verify GSTIN | GSTIN Rules |
| Extract/verify Driving License | Driving License Rules |
| Extract/verify Voter ID | Voter ID Rules |
| Extract/verify Company/CIN | Company/CIN Rules |
| Extract/verify MSME | MSME/Udyam Rules |
| Extract/verify FSSAI | FSSAI Rules |
| Verify bank account | Bank Account Validation Rules |
| Populate dropdown from external table | EDV Rules |
| Validate against master data (IFSC, etc.) | EDV Rules |
| Template-specific dropdowns | FFD Rules |
| AI document classification | AI/ML Rules |
| Face matching | AI/ML Rules |
| Speech to text | AI/ML Rules |
| Show/hide fields conditionally | Form Control Rules or Expression |
| Make fields mandatory conditionally | Form Control Rules or Expression |
| Copy data between fields | Data Copy Rules or Expression |
| Compare field values | Comparison Rules or Expression |
| Calculate age from date | Date & Time Rules |
| Location-based validation | Geolocation Rules |
| Calculate TDS | Calculation Rules |
| Create dynamic tables | Table Generation Rules |
| OTP verification | OTP Rules |
| Digital KYC/eSign | KYC & eSign Rules |
| Complex conditional logic | Expression Rules |
| Payment integration | Payment & POS Rules |

---

## Processing Types

- **SERVER**: Rules executed on server (OCR, Validation, most VERIFY)
- **CLIENT**: Rules executed on client device (UI control, Expression)

Client rules provide faster response but have limited access to server data.
Server rules have full validation capability but require network round-trip.
