# Expression Rules Reference — Agent Documentation

This is the definitive reference for writing **Expression (Client)** rules on the Manch platform.
Expression rules store a JavaScript-like expression string in the `conditionalValues[0]` field of a rule.
The expression engine is based on [expr-eval](https://github.com/silentmatt/expr-eval) with Manch-specific custom functions.

Use this document to understand every available function, its syntax, and how to compose them into complete rules.

---

## Table of Contents

1. [Field References & Variable Names](#1-field-references--variable-names)
2. [Expression Syntax Basics](#2-expression-syntax-basics)
3. [Complete Function Reference](#3-complete-function-reference)
4. [Operators & Logic](#4-operators--logic)
5. [Common Composition Patterns](#5-common-composition-patterns)
6. [Real-World Examples (English → Expression)](#6-real-world-examples-english--expression)
7. [Expression Rule JSON Structure](#7-expression-rule-json-structure)
8. [Critical Rules & Gotchas](#8-critical-rules--gotchas)

---

## 1. Field References & Variable Names

Every field on a form has a `variableName` (e.g. `__companyName__` in JSON).

**In expression strings**, variable names use **single underscores** and are **quoted**:
- JSON `variableName`: `__companyName__`
- Expression string: `"_companyName_"`

| Usage | Syntax | Example |
|-------|--------|---------|
| Get a field's **value** | `vo("_variableName_")` | `vo("_companyName_")` |
| Get a field's **element** (advanced) | `elbyid(numericId)` | `elbyid(123)` |
| Cast value to **number** | `+vo("_field_")` | `+vo("_age_") >= 18` |

> **Critical**: Always quote variable names in `vo()`. Always use single underscores `"_varName_"` inside expressions.
> In `source_fields` and `destination_fields` arrays in the JSON, use double underscores: `__varName__`.

---

## 2. Expression Syntax Basics

### Single Expression
```
mvi(vo("_field1_") == "Yes", "_field2_")
```

### Chaining Multiple Expressions
Separate with `;` — all are executed left-to-right:
```
mvi(vo("_f_") == "Yes", "_dep_");mm(vo("_f_") == "Yes", "_dep_")
```

### Event-Triggered Expressions
Wrap with `on("change")` or `on("load")` for event-based execution:
```
on("change") and (cf(true, "_child_");asdff(true, "_child_");rffdd(true, "_child_"))
```

### Load-Time with Party/Status Conditions
```
on("load") and (po() == 1) and (mvi(true, "_field1_");dis(true, "_field1_"))
on("load") and (tso() == "SENT_TO_SECOND_PARTY" and (mvi(true, "_vendorPanel_")))
```

---

## 3. Complete Function Reference

### 3.1 Value & Display Functions

#### `valOf(id)` — alias: `vo`
Gets the value of a field by its variable name or form-fill-metadata-id.
```
vo("_fieldName_")     // by variable name (most common)
vo(123)               // by numeric metadata id (rare)
```

#### `getElementById(id)` — alias: `elbyid`
Gets the DOM element by form-fill-metadata-id. Used for advanced access.
```
elbyid(123)
```

#### `concat(values...)`
Concatenates all values (including literal strings).
```
concat(vo("_first_"), ', ', vo("_last_"), ' is correct')
=> "John, Doe is correct"
```

#### `concatWithDelimiter(delimiter, values...)` — alias: `cwd`
Concatenates values with a delimiter. **Ignores empty or null strings**.
```
cwd(', ', vo("_city_"), vo("_state_"))
=> "Mumbai, Maharashtra"    // if both have values
=> "Mumbai"                 // if state is empty (no trailing comma)
```

---

### 3.2 Visibility Functions

#### `makeVisible(condition, ...destVars)` — alias: `mvi`
Makes destination fields **visible** if condition is `true`.
```
mvi(vo("_gstPresent_") == "Yes", "_gstNumber_", "_gstImage_")
```

#### `makeInvisible(condition, ...destVars)` — alias: `minvi`
Makes destination fields **invisible** if condition is `true`.
```
minvi(vo("_gstPresent_") == "No", "_gstNumber_", "_gstImage_")
```

> **Rule**: Always pair `mvi` and `minvi` for complete coverage — one for the positive case, one for the negative.

---

### 3.3 Enable / Disable Functions

#### `enable(condition, ...destVars)` — alias: `en`
Enables (makes editable) destination fields if condition is `true`.
```
en(vo("_status_") == "Active", "_editField_")
```

#### `disable(condition, ...destVars)` — alias: `dis`
Disables (makes read-only) destination fields if condition is `true`.
```
dis(vo("_status_") == "Submitted", "_editField_", "_anotherField_")
```

---

### 3.4 Mandatory / Non-Mandatory Functions

#### `makeMandatory(condition, ...destVars)` — alias: `mm`
Makes destination fields **mandatory** (required) if condition is `true`.
```
mm(vo("_gstPresent_") == "Yes", "_gstNumber_")
```

#### `makeNonMandatory(condition, ...destVars)` — alias: `mnm`
Makes destination fields **non-mandatory** (optional) if condition is `true`.
```
mnm(vo("_gstPresent_") != "Yes", "_gstNumber_")
```

> **Rule**: Always pair `mm` and `mnm` for complete coverage.

---

### 3.5 Copy / Derive Value Functions

#### `copyToFillData(condition, srcValue, ...destVars)` — alias: `ctfd`
Copies `srcValue` to all destination fields if condition is `true`.
`srcValue` can be a literal string, a `vo()` call, a `concat()`, `elbyid()`, or any expression returning a value.

```
// Copy a literal string
ctfd(vo("_panType_") == "Company", "CO", "_typeCode_")

// Copy value from another field
ctfd(true, vo("_sourceField_"), "_destField_")

// Copy an element reference
ctfd(vo("_trigger_") == "a", elbyid(120), "_dest1_", "_dest2_")

// Copy concatenated value
ctfd(true, concat(vo("_f1_"), vo("_f2_")), "_combined_")

// Copy substring (chars 0-34)
ctfd(vo("_firmName_") != "", replaceRange(vo("_firmName_"), 0, 34), "_firmName1_")
```

> **Critical**: Always follow `ctfd` with `asdff` to persist the derived value to the server:
> ```
> ctfd(true, vo("_src_"), "_dest_");asdff(true, "_dest_")
> ```

---

### 3.6 Clear / Auto-Save / Refresh Functions

These three are almost always used **together** when a parent field changes and dependent child fields need to reset.

#### `clearField(condition, ...destVars)` — alias: `cf`
Clears the value of destination fields.
```
cf(true, "_childDropdown_", "_otherField_")
```

#### `asdff(condition, ...destVars)` — auto-save form fill data
Persists the current value (possibly cleared or derived) back to the server.
```
asdff(true, "_childDropdown_")
```

#### `rffdd(condition, ...destVars)` — refresh form fill dropdown data
Reloads dropdown options for destination fields (used for cascading EDV dropdowns).
```
rffdd(true, "_childDropdown_")
```

#### `rffd(condition, ...destVars)` — refresh form fill data
Reloads field data for non-dropdown fields.
```
rffd(true, "_someField_")
```

> **Standard cascade-clear pattern (parent changes → child resets):**
> ```
> on("change") and (cf(true, "_child_");asdff(true, "_child_");rffdd(true, "_child_"))
> ```
> Use `rffdd` for dropdown children, `rffd` for non-dropdown children.

---

### 3.7 Error Handling Functions

#### `addError(condition, message, ...destVars)` — alias: `adderr`
Shows an error message on destination fields if condition is `true`.
```
adderr(vo("_owner_") == "Yes" and vo("_licensee_") == "No",
       "The group owner must be a licensee!",
       "_licensee_")
```

#### `removeError(condition, ...destVars)` — alias: `remerr`
Removes error messages from destination fields if condition is `true`.
```
remerr(vo("_owner_") != "Yes" or vo("_licensee_") != "No",
       "_owner_", "_licensee_")
```

> **Rule**: Always pair `adderr` with `remerr` using the **negated** condition so the error clears when conditions change.

---

### 3.8 Session & Party Functions

#### `partyType()` — alias: `pt()`
Returns the current party type.
- `"FP"` — First Party (Initiator)
- `"SP"` — Second Party (Vendor/Recipient)
- `undefined` — if not set
```
mvi(pt() == "SP", "_vendorOnlyField_")
```

#### `memberType()` — alias: `mt()`
Returns the current transaction member type.
- `"CREATED_BY"` — the user who created the transaction
- `"CREATED_FOR"` — the vendor/recipient
- `"APPROVER"` — an approver
- `"GENERIC_PARTY"`
```
mvi(mt() == "APPROVER", "_approverNotes_")
```

#### `sessionBasedMakeVisible(condition, param, ...destVars)` — alias: `sbmvi`
Makes fields visible for a specific session/party type.
```
sbmvi(true, "SECOND_PARTY", "_vendorField_")
sbmvi(vo("_trigger_") == "a", "GENERIC_STATIC", "_field1_", "_field2_")
```
**Param values**: `"FIRST_PARTY"`, `"SECOND_PARTY"`, `"GENERIC_STATIC"`

#### `sessionBasedMakeInvisible(condition, param, ...destVars)` — alias: `sbminvi`
Makes fields invisible for a specific session/party type.
```
sbminvi(vo("_trigger_") == "a", "SECOND_PARTY", "_field1_", "_field2_")
```

#### `tso()` — transaction status
Returns the transaction status string. Common value: `"SENT_TO_SECOND_PARTY"`.
```
on("load") and (tso() == "SENT_TO_SECOND_PARTY" and (mvi(true, "_vendorSection_")))
```

#### `po()` — party order
Returns the party order (numeric). `po() == 1` typically means approver/reviewer view.
```
on("load") and (po() == 1) and (mvi(true, "_field1_");dis(true, "_field1_"))
```

---

### 3.9 String & Utility Functions

#### `toLowerCase()` — alias: `tolc`
Transforms value to lowercase.
```
tolc(vo("_email_"))
```

#### `toUpperCase()` — alias: `touc`
Transforms value to uppercase.
```
touc(vo("_code_"))
```

#### `contains(sequenceToSearch, value)` — alias: `cntns`
Returns `true` if the sequence contains the value.
```
cntns('+', 'start')   // false
cntns(vo("_phone_"), '+')  // true if phone contains '+'
```

#### `replaceRange(string, start, end, substitute, replaceEachChar?)` — alias: `rplrng`
Replaces characters from index `start` to `end` with `substitute`.
- `replaceEachChar = true` (default): each character in range is replaced by `substitute`
- `replaceEachChar = false`: entire range replaced by `substitute` once

```
rplrng("1234567890ab", 0, 8, "X")         => "XXXXXXXX90ab"
rplrng("1234567890ab", 0, 8, "X", false)  => "X90ab"
rplrng("1234567890ab", 0, 8, "", false)   => "90ab"
```

Use cases: Extract substring, mask characters, split long strings into parts.

#### `regexTest(value, regex)` — alias: `rgxtst`
Returns `true` if the value matches the regex.
```
rgxtst(vo("_pan_"), '/^[A-Z]{5}[0-9]{4}[A-Z]$/')
rgxtst(vo("_phone_"), '/^\\d{10}$/')
rgxtst(vo("_field1_"), vo("_regexField_"))  // regex from another field
```

#### `validationStatusOf(id)` — alias: `vso`
Returns the validation status of a field.
Possible values: `"INIT"`, `"SUCCESS"`, `"FAIL"`, `"PENDING"`, `"ABORTED"`, `"TIMEOUT"`, `"WARN"`
```
vso(12345)   // => "SUCCESS"
```

#### `setAgeFromDate(srcVar, destVar)`
Calculates age in years from a date field and writes to destination.
```
setAgeFromDate("_dateOfBirth_", "_age_");asdff(vo("_age_") != "", "_age_")
```

#### `executeRuleById(condition, ...formFillMetadataIds)` — alias: `erbyid`
Executes all rules defined on another form-fill-data (to avoid duplicating rules).
```
erbyid(true, 121)
```

#### `formTag()` — alias: `ft`
Returns the name/label of a form field.
```
ft(340)
```

---

## 4. Operators & Logic

| Operator | Meaning | Example |
|----------|---------|---------|
| `==` | Equals | `vo("_type_") == "Yes"` |
| `!=` | Not equals | `vo("_type_") != "No"` |
| `<` | Less than | `+vo("_age_") < 18` |
| `>` | Greater than | `+vo("_score_") > 100` |
| `<=` | Less than or equal | `+vo("_qty_") <= 0` |
| `>=` | Greater than or equal | `+vo("_age_") >= 18` |
| `and` | Logical AND | `vo("_a_") == "X" and vo("_b_") == "Y"` |
| `or` | Logical OR | `vo("_a_") == "X" or vo("_a_") == "Z"` |
| `not` | Logical NOT | `not (vo("_a_") == "X")` |
| `true` | Always true (unconditional) | `cf(true, "_field_")` |
| `""` | Empty string check | `vo("_field_") == ""` |

### Number Casting
**Always prefix `vo()` with `+` when comparing numeric values:**
```
+vo("_age_") < 18        // CORRECT — numeric comparison
vo("_age_") < 18          // WRONG — string comparison, may produce wrong results
+vo("_val1_") < +vo("_val2_")   // CORRECT — comparing two numeric fields
```

### Parentheses
Use parentheses to group conditions:
```
(vo("_a_") == "X" and vo("_b_") == "Y") or vo("_c_") == "Z"
```

### String Comparison
String values are always quoted with double quotes inside the expression:
```
vo("_field_") == "SomeValue"
vo("_field_") == ""          // check for empty
vo("_field_") != ""          // check for non-empty
```

---

## 5. Common Composition Patterns

### Pattern 1: Simple Conditional Visibility (Toggle)
**When**: Field B should be visible if Field A = "Yes", invisible otherwise.
```
mvi(vo("_fieldA_") == "Yes", "_fieldB_");
minvi(vo("_fieldA_") != "Yes", "_fieldB_")
```

### Pattern 2: Conditional Visibility + Mandatory
**When**: Field B should be visible AND mandatory when Field A = "Yes", invisible and non-mandatory otherwise.
```
mvi(vo("_fieldA_") == "Yes", "_fieldB_");
mm(vo("_fieldA_") == "Yes", "_fieldB_");
minvi(vo("_fieldA_") != "Yes", "_fieldB_");
mnm(vo("_fieldA_") != "Yes", "_fieldB_")
```

### Pattern 3: Multi-Value OR Condition
**When**: Fields become mandatory if a trigger has any of several specific values.
```
mm(vo("_accGrp_") == "INDS" or vo("_accGrp_") == "FIVN" or vo("_accGrp_") == "CAVN",
   "_clerk_", "_clerkTel_", "_clerkEmail_");
mnm(vo("_accGrp_") != "INDS" and vo("_accGrp_") != "FIVN" and vo("_accGrp_") != "CAVN",
    "_clerk_", "_clerkTel_", "_clerkEmail_")
```
> **Note**: The negation of `(A or B or C)` is `(not A and not B and not C)` — use `!=` with `and` for the opposite branch.

### Pattern 4: Three-Way Condition (Yes / No / Blank)
**When**: Different behavior for "Yes", "No", and empty (unselected).
```
// Yes: make visible + mandatory
mvi(vo("_createKey_") == "Yes", "_bankField_");
mm(vo("_createKey_") == "Yes", "_bankField_");
// No: invisible + non-mandatory
minvi(vo("_createKey_") == "No", "_bankField_");
mnm(vo("_createKey_") == "No", "_bankField_");
// Blank: invisible + non-mandatory
minvi(vo("_createKey_") == "", "_bankField_");
mnm(vo("_createKey_") == "", "_bankField_")
```

### Pattern 5: Cascade Clear (Parent Dropdown Changes → Child Resets)
**When**: Changing a parent dropdown should clear, save, and refresh child dropdown(s).
**Placed on the parent field.**
```
on("change") and (cf(true, "_child_");asdff(true, "_child_");rffdd(true, "_child_"))
```
For multiple children:
```
on("change") and (
  cf(true, "_child1_", "_child2_", "_child3_");
  asdff(true, "_child1_", "_child2_", "_child3_");
  rffdd(true, "_child1_", "_child2_", "_child3_")
)
```
For non-dropdown children, use `rffd` instead of `rffdd`:
```
on("change") and (cf(true, "_child_");asdff(true, "_child_");rffd(true, "_child_"))
```

### Pattern 6: Derive/Copy Value on Condition
**When**: Copy a value to a destination field based on a condition.
```
ctfd(vo("_panType_") == "Company", "CO", "_typeCode_");
ctfd(vo("_panType_") != "Company", "CT", "_typeCode_");
asdff(true, "_typeCode_")
```

### Pattern 7: Derive Value Unconditionally
**When**: Always copy/derive a value.
```
ctfd(true, concat(vo("_first_"), ' ', vo("_last_")), "_fullName_");
asdff(true, "_fullName_")
```

### Pattern 8: Split Long Text into Multiple Fields
**When**: A long string needs to be split across fields (e.g., character limits).
```
ctfd(vo("_firmName_") != "", replaceRange(vo("_firmName_"), 0, 34), "_firmName1_");
ctfd(vo("_firmName_") != "", replaceRange(vo("_firmName_"), 35, 60), "_firmName2_");
asdff(vo("_firmName_") != "", "_firmName1_", "_firmName2_")
```

### Pattern 9: Validation Error + Removal
**When**: Show an error when a condition is met, remove it when not.
```
adderr(vo("_owner_") == "Yes" and vo("_licensee_") == "No",
       "The group owner must be a licensee!",
       "_licensee_");
remerr(vo("_owner_") != "Yes" or vo("_licensee_") != "No",
       "_owner_", "_licensee_")
```

### Pattern 10: Age from Date + Validation
**When**: Calculate age from DOB, validate minimum age, show/hide warning.
```
setAgeFromDate("_dob_", "_age_");
asdff(vo("_age_") != "", "_age_");
adderr(vo("_age_") != "" and +vo("_age_") < 18, "Age must be 18 or above", "_age_", "_dob_");
remerr(vo("_age_") != "" and +vo("_age_") >= 18, "_age_", "_dob_");
mvi(vo("_age_") != "" and +vo("_age_") < 18, "_ageWarningLabel_");
minvi(vo("_age_") != "" and +vo("_age_") >= 18, "_ageWarningLabel_");
minvi(vo("_age_") == "", "_ageWarningLabel_")
```

### Pattern 11: Load-Time Approver-Only View
**When**: On load, make certain fields visible/disabled for approver view only.
```
on("load") and (po() == 1) and (
  mvi(true, "_approverField1_", "_approverField2_");
  minvi(true, "_initiatorField_");
  dis(true, "_approverField1_")
)
```

### Pattern 12: Numeric Comparison Between Fields
**When**: Show different labels based on comparing two numeric fields.
```
minvi(true, "_label1_", "_label2_");
mvi(+vo("_textf1_") < +vo("_textf2_"), "_label1_");
mvi(+vo("_textf1_") > +vo("_textf2_"), "_label2_");
minvi(+vo("_textf1_") == +vo("_textf2_"), "_label1_", "_label2_")
```

### Pattern 13: Session-Based Visibility
**When**: Fields should be visible/invisible based on party type (FIRST_PARTY vs SECOND_PARTY).
```
sbmvi(true, "SECOND_PARTY", "_vendorField_", "_vendorSection_");
sbminvi(true, "FIRST_PARTY", "_vendorField_", "_vendorSection_")
```

### Pattern 14: Regex Validation
**When**: Validate a field's format and show error for invalid input.
```
adderr(vo("_pan_") != "" and not rgxtst(vo("_pan_"), '/^[A-Z]{5}[0-9]{4}[A-Z]$/'),
       "Invalid PAN format", "_pan_");
remerr(vo("_pan_") == "" or rgxtst(vo("_pan_"), '/^[A-Z]{5}[0-9]{4}[A-Z]$/'),
       "_pan_")
```

### Pattern 15: Second Party Load with Transaction Status
**When**: On load, check transaction status and conditionally show/hide for second party.
```
on("load") and (tso() == "SENT_TO_SECOND_PARTY" and (
  mvi(vo("_field1_") == "PAN" and vo("_field2_") == "Test", "_panPanel_", "_panDetails_", "_panNumber_");
  mm(vo("_field1_") == "PAN" and vo("_field2_") == "Test", "_panNumber_");
  mnm(vo("_field1_") != "PAN" or vo("_field2_") != "Test", "_panNumber_");
  minvi(vo("_field1_") != "PAN" or vo("_field2_") != "Test", "_panPanel_", "_panDetails_", "_panNumber_")
))
```

### Pattern 16: Compound Condition Visibility + Mandatory + Invisibility
**When**: Multiple conditions control visibility of multiple field groups (e.g., GST Present Yes/No/Blank).
```
// Blank: everything invisible and non-mandatory
minvi(vo("_isgstpresent_") == "", "_gstImage_", "_gstnumber_", "_declaration_");
mnm(vo("_isgstpresent_") == "", "_gstImage_", "_gstnumber_", "_declaration_");
// Yes: GST fields visible+mandatory, declaration invisible+non-mandatory
mvi(vo("_isgstpresent_") == "Yes", "_gstImage_", "_gstnumber_");
mm(vo("_isgstpresent_") == "Yes", "_gstImage_", "_gstnumber_");
minvi(vo("_isgstpresent_") == "Yes", "_declaration_");
mnm(vo("_isgstpresent_") == "Yes", "_declaration_");
// No: declaration visible+mandatory, GST fields invisible+non-mandatory
mvi(vo("_isgstpresent_") == "No", "_declaration_");
mm(vo("_isgstpresent_") == "No", "_declaration_");
minvi(vo("_isgstpresent_") == "No", "_gstImage_", "_gstnumber_");
mnm(vo("_isgstpresent_") == "No", "_gstImage_", "_gstnumber_")
```

---

## 6. Real-World Examples (English → Expression)

These examples show how to translate natural-language business rules into expression syntax. Study these to learn the mapping from English wording to expression code.

---

### Example A: Clear child fields on parent change
**English**: Upon changing the cheque image, clear the IFSC and Account Number, save the cleared values, and refresh the fields.

**Expression** (placed on the cheque image field):
```
on("change") and (cf(true,"_IFSCNumber_","_AccountNumber_");asdff(true,"_IFSCNumber_","_AccountNumber_");rffd(true,"_IFSCNumber_","_AccountNumber_"))
```

**Key points**: `on("change")` triggers on field change. `cf` clears, `asdff` saves, `rffd` refreshes (non-dropdown fields use `rffd`, dropdown fields use `rffdd`).

---

### Example B: Cross-field error validation
**English**: An error should be displayed if "Are you the group owner?" is "Yes" and "Are you one of the licensees?" is "No". Error message: "The group owner must mandatorily be a licensee within the group!" Remove the error if these conditions are not met.

**Expression**:
```
adderr(vo("_areyouaGroupowner_") == "Yes" and vo("_areyouoneofLicensees_") == "No",
       "The group owner must mandatorily be a licensee within the group!",
       "_areyouoneofLicensees_");
remerr(vo("_areyouaGroupowner_") != "Yes" or vo("_areyouoneofLicensees_") != "No",
       "_areyouaGroupowner_", "_areyouoneofLicensees_")
```

**Key points**: `adderr` condition is the error condition. `remerr` condition is the **negation** of the error condition. Note DeMorgan's law: `not (A and B)` = `(not A or not B)`.

---

### Example C: Three-way visibility (Yes/No/Blank) with mandatory
**English**:
- If "GST Present" = "Yes": Make GST image and GST number visible and mandatory. Make declaration invisible and non-mandatory.
- If "GST Present" = "No": Make declaration visible and mandatory. Make GST image and GST number invisible and non-mandatory.
- If "GST Present" = blank: Everything invisible and non-mandatory.

**Expression** (placed on the "GST Present" field):
```
on("change") and (minvi(vo("_isgstpresent_") == "", "_gstImage_","_gstnumber_","_declaration_");mnm(vo("_isgstpresent_") == "", "_gstImage_","_gstnumber_","_declaration_");mvi(vo("_isgstpresent_") == "Yes", "_gstImage_","_gstnumber_");mm(vo("_isgstpresent_") == "Yes", "_gstImage_","_gstnumber_");minvi(vo("_isgstpresent_") == "Yes", "_declaration_");mnm(vo("_isgstpresent_") == "Yes", "_declaration_");mvi(vo("_isgstpresent_") == "No", "_declaration_");mm(vo("_isgstpresent_") == "No", "_declaration_");minvi(vo("_isgstpresent_") == "No", "_gstImage_","_gstnumber_");mnm(vo("_isgstpresent_") == "No", "_gstImage_","_gstnumber_"))
```

**Key points**: Each value of the dropdown ("Yes", "No", "") gets its own set of `mvi`/`minvi`/`mm`/`mnm` calls for the affected fields.

---

### Example D: Numeric comparison between fields
**English**: Label 1 and Label 2 should always be invisible. If textf1 < textf2, show Label 1. If textf1 > textf2, show Label 2. If they are equal, both invisible.

**Expression**:
```
minvi(true,"_lable1_","_lable2_");
mvi(+vo("_textf1_") < +vo("_textf2_"),"_lable1_");
mvi(+vo("_textf1_") > +vo("_textf2_"),"_lable2_");
minvi(+vo("_textf1_") == +vo("_textf2_"),"_lable1_","_lable2_")
```

**Key points**: Start with `minvi(true,...)` to set default invisible. Use `+vo()` for numeric comparison. Each condition gets its own `mvi`/`minvi`.

---

### Example E: Multi-value OR → mandatory/non-mandatory
**English**: If Account Group is 'INDS' or 'FIVN' or 'CAVN' or 'IMPS' then Clerk at Vendor, Clerks tel no and Clerks internet add are mandatory. Otherwise, non-mandatory.

**Expression**:
```
mm(vo("_HeaderDataAccountGroup_") == "INDS" or vo("_HeaderDataAccountGroup_") == "FIVN" or vo("_HeaderDataAccountGroup_") == "CAVN" or vo("_HeaderDataAccountGroup_") == "IMPS",
   "_CorrespondenceClerkatvendor_","_CorrespondenceAcctclerkstelno_","_CorrespondenceClerksinternetadd_");
mnm(vo("_HeaderDataAccountGroup_") != "INDS" and vo("_HeaderDataAccountGroup_") != "FIVN" and vo("_HeaderDataAccountGroup_") != "CAVN" and vo("_HeaderDataAccountGroup_") != "IMPS",
    "_CorrespondenceClerkatvendor_","_CorrespondenceAcctclerkstelno_","_CorrespondenceClerksinternetadd_")
```

**Key points**: The `mm` condition uses `or` for any matching value. The `mnm` negation uses `!=` with `and` (DeMorgan's law).

---

### Example F: Cascading dropdown clear on parent change
**English**: If the value of field 'Country' changes, then clear, autosave and refresh the dropdown values of the field 'Region'.

**Expression** (placed on Country field):
```
on("change") and (cf(true,"_AddressDetailsRegion_");asdff(true,"_AddressDetailsRegion_");rffdd(true,"_AddressDetailsRegion_"))
```

**Key points**: Standard cascade-clear pattern. `rffdd` (not `rffd`) because Region is a dropdown.

---

### Example G: Multi-condition visibility across two fields
**English**: If PAN Card Category = "Yes" and PAN Aadhaar Link Status != "Y", show "20% TDS deducted" field. If PAN Card Category = "Yes" and PAN Aadhaar Link Status = "Y", hide it.

**Expression**:
```
mvi(vo("_PanDetailsPANCardCategory_") == "Yes" and vo("_pANAadhaarLinkStatus15_") != "Y",
    "_20TdsWillBeDeductedForInoperativePanUs206AA90_");
minvi(vo("_PanDetailsPANCardCategory_") == "Yes" and vo("_pANAadhaarLinkStatus15_") == "Y",
      "_20TdsWillBeDeductedForInoperativePanUs206AA90_")
```

---

### Example H: Complex multi-condition visibility (Yes/No/Blank with many fields)
**English**: If "Do you want to create new Bank Key?" = "Yes": make 11 bank fields visible, make Bank Country Key and Bank Keys mandatory. If blank: make all 11 fields invisible and non-mandatory. If "No": make all invisible and non-mandatory.

**Expression**:
```
minvi(vo("_BankMasterDoyouwanttocreatenewbankkey_") == "",
      "_BankMasterBankCountryKey_","_BankMasterBankKeys_","_BankMasterBankName_","_BankMasterBranchName_","_BankMasterStreetHouse_","_BankMasterCity_","_BankMasterRegion_","_BankMasterSWIFTBIC_","_BankMasterBankGroup_","_BankMasterPostbankAcct_","_BankMasterBankNumber_");
mnm(vo("_BankMasterDoyouwanttocreatenewbankkey_") == "",
    "_BankMasterBankCountryKey_","_BankMasterBankKeys_","_BankMasterBankName_","_BankMasterBranchName_","_BankMasterStreetHouse_","_BankMasterCity_","_BankMasterRegion_","_BankMasterSWIFTBIC_","_BankMasterBankGroup_","_BankMasterPostbankAcct_","_BankMasterBankNumber_");
mvi(vo("_BankMasterDoyouwanttocreatenewbankkey_") == "Yes",
    "_BankMasterBankCountryKey_","_BankMasterBankKeys_","_BankMasterBankName_","_BankMasterBranchName_","_BankMasterStreetHouse_","_BankMasterCity_","_BankMasterRegion_","_BankMasterSWIFTBIC_","_BankMasterBankGroup_","_BankMasterPostbankAcct_","_BankMasterBankNumber_");
mm(vo("_BankMasterDoyouwanttocreatenewbankkey_") == "Yes",
   "_BankMasterBankCountryKey_","_BankMasterBankKeys_");
mnm(vo("_BankMasterDoyouwanttocreatenewbankkey_") == "No",
    "_BankMasterBankCountryKey_","_BankMasterBankKeys_");
minvi(vo("_BankMasterDoyouwanttocreatenewbankkey_") == "No",
      "_BankMasterBankCountryKey_","_BankMasterBankKeys_","_BankMasterBankName_","_BankMasterBranchName_","_BankMasterStreetHouse_","_BankMasterCity_","_BankMasterRegion_","_BankMasterSWIFTBIC_","_BankMasterBankGroup_","_BankMasterPostbankAcct_","_BankMasterBankNumber_")
```

**Key points**: Different subsets of fields get different rules (e.g., only 2 of 11 fields become mandatory). Each dropdown value gets separate statements.

---

### Example I: Conditional copy value
**English**: If the PAN type is "Company" then copy "CO" to Field1, otherwise copy "CT" to Field1.

**Expression**:
```
ctfd(vo("_pANType_") == "Company", "CO", "_Field1_");
ctfd(vo("_pANType_") != "Company", "CT", "_Field1_");
asdff(true, "_Field1_")
```

---

### Example J: Approver view (load-time)
**English**: Make fields visible, make some invisible, and disable for Approver View.

**Expression**:
```
on("load") and (po() == 1) and (mvi(true, "_Field1_","_Field2_");minvi(true,"_Field3_","_Field4_");dis(true,"_Field1_"))
```

---

### Example K: Age calculation with validation and label
**English**: Capture age to Field 2 from Field 1. If age < 18 show error. If age >= 18 remove error.

**Expression**:
```
setAgeFromDate("_Field1_","_Field2_");
asdff(vo("_Field2_") != "","_Field2_");
remerr(vo("_Field2_") != "" and +vo("_Field2_") >= 18,"_Field2_","_Field1_");
adderr(vo("_Field2_") != "" and +vo("_Field2_") < 18, "age should be above 18","_Field2_","_Field1_");
mvi(vo("_Field2_") != "" and +vo("_Field2_") < 18,"_label_");
minvi(vo("_Field2_") != "" and +vo("_Field2_") >= 18,"_label_");
minvi(vo("_Field2_") == "","_label_")
```

---

### Example L: Simple dropdown clear on change
**English**: Changing any value in dropdown of field1 should clear field 2.

**Expression** (placed on field1):
```
on("change") and (cf(true,"_Field1_");asdff(true,"_Field1_"))
```

---

### Example M: EDV Attribute Copy (conditionList format)
**English**: From the TestEDV Attribute 1 copy the value to Attribute 3.

**Expression** (this uses `params.conditionList` JSON, not conditionalValues):
```json
{
  "conditionList": [
    {
      "ddType": ["TestEDV"],
      "criterias": [{"a2": 123456}],
      "da": ["a1"],
      "criteriaSearchAttr": [],
      "additionalOptions": null,
      "emptyAddOptionCheck": null,
      "ddProperties": null
    }
  ]
}
```

> **Note**: EDV rules use `params.conditionList` instead of `conditionalValues`. These are handled by the EDV agent, not expression rules.

---

## 7. Expression Rule JSON Structure

In the pipeline JSON, an Expression (Client) rule looks like:

```json
{
  "rule_name": "Expression (Client)",
  "source_fields": ["__triggerField__"],
  "destination_fields": ["__dependentField1__", "__dependentField2__"],
  "params": null,
  "conditionalValues": [
    "mvi(vo(\"_triggerField_\") == \"Yes\", \"_dependentField1_\", \"_dependentField2_\");minvi(vo(\"_triggerField_\") != \"Yes\", \"_dependentField1_\", \"_dependentField2_\")"
  ],
  "condition": null,
  "conditionValueType": null,
  "_expressionRuleType": "visibility"
}
```

### `_expressionRuleType` Values

This internal tag identifies the purpose of the expression:

| Value | Functions Used | Purpose |
|-------|---------------|---------|
| `"visibility"` | `mvi`, `minvi` | Make Visible / Invisible rules |
| `"mandatory"` | `mm`, `mnm` | Make Mandatory / Non-Mandatory rules |
| `"enable_disable"` | `en`, `dis` | Enable / Disable rules |
| `"derivation"` | `ctfd` + `asdff` | Value copying/derivation |
| `"clear_field"` | `cf` + `asdff` + `rffdd`/`rffd` | Cascading clears |
| `"error"` | `adderr` + `remerr` | Validation error messages |
| `"session"` | `sbmvi` / `sbminvi` | Session-based visibility |
| `"event"` | `on("change")` or `on("load")` | Event-triggered rules |

### Field Mapping

- **`source_fields`**: The field(s) whose values are read in the expression (the triggers). Use `__doubleUnderscore__` format.
- **`destination_fields`**: The field(s) affected by the expression (targets of `mvi`, `cf`, `ctfd`, etc.). Use `__doubleUnderscore__` format.
- **`conditionalValues[0]`**: The expression string itself. Variable names inside use `"_singleUnderscore_"` format.

---

## 8. Critical Rules & Gotchas

1. **Variable name format**: In expression strings use `"_varName_"` (single underscores, quoted). In JSON arrays (`source_fields`, `destination_fields`) use `__varName__` (double underscores).

2. **Always pair opposites**: If you write `mvi(condition, ...)`, also write `minvi(negated_condition, ...)`. Same for `mm`/`mnm`, `en`/`dis`, `adderr`/`remerr`.

3. **Number casting**: Always use `+vo("_field_")` when comparing numbers. Without `+`, values are compared as strings (`"9" > "10"` is true as a string comparison).

4. **After `ctfd` always add `asdff`**: Derived values must be persisted with `asdff`.

5. **After `cf` always add `asdff` + `rffdd`/`rffd`**: Cleared values must be saved and the field refreshed. Use `rffdd` for dropdowns, `rffd` for non-dropdown fields.

6. **`adderr`/`remerr` pairing**: The `remerr` condition must be the **logical negation** of the `adderr` condition. Use DeMorgan's law: `not (A and B)` = `(not A or not B)`.

7. **`on("change")` wrapping**: Use for actions triggered by field value changes (clearing children, cascading). The entire set of chained actions goes inside `and (...)`.

8. **`on("load")` wrapping**: Use for actions that should execute when the form loads (approver views, initial state setup).

9. **Semicolons**: Chain multiple function calls with `;`. All are executed left-to-right.

10. **`true` as condition**: Use when the action should always execute (unconditional). Example: `cf(true, "_field_")` always clears.

11. **Empty string check**: `vo("_field_") == ""` checks if a field is empty/blank. This is the standard way to test for "no value selected".

12. **Multiple destination fields**: Most functions accept variadic destination fields. Pass them as comma-separated arguments: `mvi(condition, "_f1_", "_f2_", "_f3_")`.

13. **Session-based rules**: `sbmvi`/`sbminvi` take an extra `param` argument between condition and destVars. Valid params: `"FIRST_PARTY"`, `"SECOND_PARTY"`, `"GENERIC_STATIC"`.

14. **Expression string escaping in JSON**: When the expression is stored in a JSON string, double quotes inside must be escaped: `\"`. For example: `"mvi(vo(\"_field_\") == \"Yes\", \"_dep_\")"`.

---

## Quick Function Alias Cheat Sheet

| Full Name | Alias | Signature |
|-----------|-------|-----------|
| `valOf` | `vo` | `vo(variableName)` |
| `getElementById` | `elbyid` | `elbyid(id)` |
| `concat` | — | `concat(val1, val2, ...)` |
| `concatWithDelimiter` | `cwd` | `cwd(delimiter, val1, val2, ...)` |
| `makeVisible` | `mvi` | `mvi(condition, ...destVars)` |
| `makeInvisible` | `minvi` | `minvi(condition, ...destVars)` |
| `enable` | `en` | `en(condition, ...destVars)` |
| `disable` | `dis` | `dis(condition, ...destVars)` |
| `makeMandatory` | `mm` | `mm(condition, ...destVars)` |
| `makeNonMandatory` | `mnm` | `mnm(condition, ...destVars)` |
| `copyToFillData` | `ctfd` | `ctfd(condition, srcValue, ...destVars)` |
| `clearField` | `cf` | `cf(condition, ...destVars)` |
| `autoSaveFormFillData` | `asdff` | `asdff(condition, ...destVars)` |
| `refreshFormFillDropdownData` | `rffdd` | `rffdd(condition, ...destVars)` |
| `refreshFormFillData` | `rffd` | `rffd(condition, ...destVars)` |
| `addError` | `adderr` | `adderr(condition, message, ...destVars)` |
| `removeError` | `remerr` | `remerr(condition, ...destVars)` |
| `partyType` | `pt` | `pt()` |
| `memberType` | `mt` | `mt()` |
| `sessionBasedMakeVisible` | `sbmvi` | `sbmvi(condition, param, ...destVars)` |
| `sessionBasedMakeInvisible` | `sbminvi` | `sbminvi(condition, param, ...destVars)` |
| `toLowerCase` | `tolc` | `tolc(value)` |
| `toUpperCase` | `touc` | `touc(value)` |
| `contains` | `cntns` | `cntns(sequence, value)` |
| `replaceRange` | `rplrng` | `rplrng(str, start, end, subst, replaceEachChar?)` |
| `regexTest` | `rgxtst` | `rgxtst(value, regex)` |
| `validationStatusOf` | `vso` | `vso(id)` |
| `setAgeFromDate` | — | `setAgeFromDate(srcVar, destVar)` |
| `executeRuleById` | `erbyid` | `erbyid(condition, ...metadataIds)` |
| `formTag` | `ft` | `ft(id)` |
| `transactionStatusOf` | `tso` | `tso()` |
| `partyOrder` | `po` | `po()` |
