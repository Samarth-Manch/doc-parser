# Manch Expression Language — Rule Generation Guide

You are writing `.expr` rules for the Manch platform. Follow this EXACT step-by-step process to generate correct, production-ready expression rules.

---

## STEP 1: ANALYZE THE REQUIREMENT

Before writing ANY code, answer these questions:

1. **Trigger field**: Which field's value drives the rule?
2. **Trigger type**: Is it a single-select dropdown, multi-select dropdown, text field, or checkbox?
3. **Possible values**: List EVERY value the trigger can have (including blank/empty).
4. **Target fields/panels**: For EACH trigger value, which fields/panels are affected?
5. **Actions needed**: For each target — show/hide? mandatory/optional? enable/disable? copy? clear? error?
6. **Event wrapper**: Does this fire on `"change"`, `"load"`, `"blur"`, or always (no wrapper)? ONLY add `on("change")` or `on("load")` if the user EXPLICITLY mentions it. Do NOT add event wrappers by default.
7. **Cascade clear**: When the trigger changes, should child fields be cleared + saved + refreshed?
8. **Default condition**: If the user does NOT specify a condition (e.g., "disable this field", "hide this panel"), use `true` as the condition. A trigger field is NOT required — unconditional rules are valid.

---

## STEP 2: CHOOSE THE CONDITION TYPE

| Trigger type | Condition syntax | Negated syntax |
|---|---|---|
| Single value | `vo("_f_") == "Yes"` | `vo("_f_") != "Yes"` |
| Multi-value OR | `vo("_f_") == "A" or vo("_f_") == "B"` | `vo("_f_") != "A" and vo("_f_") != "B"` |
| Multi-select contains | `cntns("Option", vo("_f_"))` | `not(cntns("Option", vo("_f_")))` |
| Empty check | `vo("_f_") == ""` | `vo("_f_") != ""` |
| Numeric comparison | `+vo("_f_") >= 18` | `+vo("_f_") < 18` |
| Compound AND | `vo("_a_") == "X" and vo("_b_") == "Y"` | `vo("_a_") != "X" or vo("_b_") != "Y"` |
| Always/unconditional | `true` | *(no pair needed)* |

---

## STEP 3: SELECT THE PATTERN

### Pattern A — Unconditional (condition is `true`) — DEFAULT when no condition specified
No pairing needed. State is permanent. This is the DEFAULT pattern when the user does not specify a condition (e.g., "disable this field" → `dis(true, "_field_")`).
```
minvi(true, "_field_")
dis(true, "_field_")
mnm(true, "_field_")
mm(true, "_field_")
en(true, "_field_")
```

### Pattern B — Simple Visibility Toggle
```
mvi(CONDITION, "_dest_");minvi(NEGATED_CONDITION, "_dest_")
```
Production example:
```
mvi(vo("_Discussion1_") == "Other", "_Other1_");minvi(vo("_Discussion1_") != "Other", "_Other1_")
```

### Pattern C — Visibility + Mandatory
```
mvi(CONDITION, "_dest_");mm(CONDITION, "_dest_");minvi(NEGATED_CONDITION, "_dest_");mnm(NEGATED_CONDITION, "_dest_")
```
Production example:
```
mvi(vo("_isGstinPresentList_") == "Yes", "_gstinNumber_", "_gstinName_", "_gstinState_");mm(vo("_isGstinPresentList_") == "Yes", "_gstinNumber_", "_gstinName_", "_gstinState_");minvi(vo("_isGstinPresentList_") != "Yes", "_gstinNumber_", "_gstinName_", "_gstinState_");mnm(vo("_isGstinPresentList_") != "Yes", "_gstinNumber_", "_gstinName_", "_gstinState_")
```

### Pattern D — Visibility + Mandatory + Clear + Error Reset
When hiding fields, also clear values, remove errors, make non-mandatory.
```
mvi(CONDITION, ...dests);mm(CONDITION, ...dests);minvi(NEGATED_CONDITION, ...dests);mnm(NEGATED_CONDITION, ...dests);remerr(NEGATED_CONDITION, ...dests);cf(NEGATED_CONDITION, ...dests)
```
Production example:
```
mvi(vo("_isPANPresent_") == "Yes", "_panNumber_", "_panImage_");mm(vo("_isPANPresent_") == "Yes", "_panNumber_", "_panImage_");minvi(vo("_isPANPresent_") != "Yes", "_panNumber_", "_panImage_");mnm(vo("_isPANPresent_") != "Yes", "_panNumber_", "_panImage_");remerr(vo("_isPANPresent_") != "Yes", "_panNumber_", "_panImage_");cf(vo("_isPANPresent_") != "Yes", "_panNumber_", "_panImage_")
```

### Pattern E — Contains / Multi-Select Visibility
For EACH option, write BOTH `mvi` AND `minvi(not(cntns(...)))`. NEVER skip the negative.
```
mvi(cntns("OptionA", vo("_trigger_")), "_panelA_");minvi(not(cntns("OptionA", vo("_trigger_"))), "_panelA_");mvi(cntns("OptionB", vo("_trigger_")), "_panelB_");minvi(not(cntns("OptionB", vo("_trigger_"))), "_panelB_")
```
Production example (7 options, each properly paired):
```
mvi(cntns("Healthcare,Pharma,Medical Devices or Surgical or Hospital Equipment", vo("_ifyeswhatsector_")), "_healthcarepleasespecify4_");minvi(not(cntns("Healthcare,Pharma,Medical Devices or Surgical or Hospital Equipment", vo("_ifyeswhatsector_"))), "_healthcarepleasespecify4_");mvi(cntns("Others", vo("_ifyeswhatsector_")), "_industryotherspleasespecify4_");minvi(not(cntns("Others", vo("_ifyeswhatsector_"))), "_industryotherspleasespecify4_");mvi(cntns("ITES", vo("_ifyeswhatsector_")), "_itespleasespecify4_");minvi(not(cntns("ITES", vo("_ifyeswhatsector_"))), "_itespleasespecify4_")
```

### Pattern F — Contains + Visibility + Mandatory + Clear
Full pattern for multi-select with all actions:
```
mvi(cntns("X", vo("_trigger_")), "_dest_");minvi(not(cntns("X", vo("_trigger_"))), "_dest_");mm(cntns("X", vo("_trigger_")), "_dest_");mnm(not(cntns("X", vo("_trigger_"))), "_dest_");cf(not(cntns("X", vo("_trigger_"))), "_dest_")
```
Production example:
```
mvi(cntns("Yes", vo("_internetconnectivity_")), "_typeofconnectivity_");minvi(not(cntns("Yes", vo("_internetconnectivity_"))), "_typeofconnectivity_");mm(cntns("Yes", vo("_internetconnectivity_")), "_typeofconnectivity_");mnm(not(cntns("Yes", vo("_internetconnectivity_"))), "_typeofconnectivity_");cf(cntns("Yes", vo("_internetconnectivity_")), "_typeofconnectivity_");cf(not(cntns("Yes", vo("_internetconnectivity_"))), "_typeofconnectivity_")
```

### Pattern G — Three-Way Condition (Blank / Yes / No)
Each value gets its own block.
```
// Blank: hide all, make non-mandatory
minvi(vo("_gst_") == "", ...allFields);mnm(vo("_gst_") == "", ...allFields);
// Yes: show gst fields, hide declaration
mvi(vo("_gst_") == "Yes", "_gstImage_", "_gstNum_");mm(vo("_gst_") == "Yes", "_gstImage_", "_gstNum_");minvi(vo("_gst_") == "Yes", "_declaration_");mnm(vo("_gst_") == "Yes", "_declaration_");
// No: show declaration, hide gst fields
mvi(vo("_gst_") == "No", "_declaration_");mm(vo("_gst_") == "No", "_declaration_");minvi(vo("_gst_") == "No", "_gstImage_", "_gstNum_");mnm(vo("_gst_") == "No", "_gstImage_", "_gstNum_")
```

### Pattern H — Multi-Value OR with Mandatory
```
mm(vo("_accGrp_") == "INDS" or vo("_accGrp_") == "FIVN" or vo("_accGrp_") == "CAVN", "_clerk_", "_clerkTel_");mnm(vo("_accGrp_") != "INDS" and vo("_accGrp_") != "FIVN" and vo("_accGrp_") != "CAVN", "_clerk_", "_clerkTel_")
```
**Note**: `or` in the positive becomes `and` with `!=` in the negative.

### Pattern I — Cascade Clear (on change) — ONLY when explicitly requested
When parent changes, clear + save + refresh child fields. **Only use this when the user explicitly asks for on change / cascade clear behavior.**
```
on("change") and (cf(true, "_child1_", "_child2_");asdff(true, "_child1_", "_child2_");rffdd(true, "_dropdownChild_");rffd(true, "_nonDropdownChild_"))
```
Use `rffdd` for dropdown children, `rffd` for non-dropdown children.

Production example:
```
on("change") and (cf(true, "_selectOption62_");asdff(true, "_selectOption62_");rffdd(true, "_selectOption62_"))
```

### Pattern J — Copy/Derive + Auto-Save
```
ctfd(CONDITION, srcValue, "_dest_");asdff(CONDITION, "_dest_")
```
Production examples:
```
// Copy literal
ctfd(vo("_panType_") == "Company", "CO", "_typeCode_");ctfd(vo("_panType_") != "Company", "CT", "_typeCode_");asdff(true, "_typeCode_")

// Copy field value
ctfd(true, vo("_sourceField_"), "_destField_");asdff(true, "_destField_")

// Concatenate
ctfd(true, concat(vo("_firstName_"), " ", vo("_lastName_")), "_fullName_");asdff(true, "_fullName_")

// Arithmetic
ctfd(vo("_quantity_") != "" and vo("_rate_") != "", +vo("_quantity_") * +vo("_rate_"), "_total_");asdff(true, "_total_")

// Sum fields
ctfd(vo("_map4B1_"), +vo("_map4B1_") + +vo("_map4B2_") + +vo("_map4B3_") + +vo("_map4B4_"), "_grossSalary_");erbyid(true, "_grossSalary_")
```

### Pattern K — Error + Remove Error
```
adderr(CONDITION, "message", "_dest_");remerr(NEGATED_CONDITION, "_dest_")
```
Production examples:
```
// Numeric validation
adderr(vo("_age_") != "" and +vo("_age_") < 18, "Age must be 18 or above", "_age_");remerr(vo("_age_") != "" and +vo("_age_") >= 18, "_age_")

// AND condition (De Morgan: and→or in remerr)
adderr(vo("_groupOwner_") == "Yes" and vo("_licensee_") == "No", "The group owner must be a licensee!", "_licensee_");remerr(vo("_groupOwner_") != "Yes" or vo("_licensee_") != "No", "_groupOwner_", "_licensee_")

// Range validation
adderr(vo("_field_") != "" and (+vo("_field_") < 0 or +vo("_field_") > 2.5), "Value should be between 0 and 2.5%", "_field_");remerr(+vo("_field_") >= 0 and +vo("_field_") <= 2.5, "_field_")

// Regex validation
adderr(vo("_pan_") != "" and not(rgxtst(vo("_pan_"), '/^[A-Z]{5}[0-9]{4}[A-Z]$/')), "Invalid PAN format", "_pan_");remerr(vo("_pan_") == "" or rgxtst(vo("_pan_"), '/^[A-Z]{5}[0-9]{4}[A-Z]$/'), "_pan_")

// Case-insensitive name comparison
adderr(vo("_panHolderName_") != "" and touc(vo("_vendorName_")) != touc(vo("_panHolderName_")), "PAN Name does not match Customer Name", "_panHolderName_");remerr(true, "_panHolderName_")
```

### Pattern L — Enable/Disable Based on Dependency
```
dis(vo("_startDate_") == "", "_endDate_");en(vo("_startDate_") != "", "_endDate_");cf(vo("_startDate_") == "", "_endDate_");asdff(vo("_startDate_") == "", "_endDate_")
```

### Pattern M — SSM String Split
```
ssm(vo("_street_") != "", "RANDOM_INDEX", "_street1_", 4, 0, 34);ssm(vo("_street_") != "", "RANDOM_INDEX", "_street2_", 4, 35, 69);ssm(vo("_street_") != "", "RANDOM_INDEX", "_street3_", 4, 70, 104);asdff(vo("_street_") != "", "_street1_", "_street2_", "_street3_")
```
Index modes: `"RANDOM_INDEX"` (general), `"FIRST_INDEX"` (from start), `"LAST_INDEX"` (from end), `"SUBSTRING"` (substring).

Production examples:
```
// Extract 4th character of PAN
ssm(vo("_pannumber_") != "", "FIRST_INDEX", "_pAN4thCharacter39_", 10, 3, 4)

// Extract last 4 digits of Aadhaar
ssm(vo("_V24_") != "", "LAST_INDEX", "_aadharCompare152_", 0, 0, 4)

// Extract substring for comparison
ssm(vo("_vendortanno_") != "", "SUBSTRING", "_tANFirstFourValues54_", 10, 0, 4);asdff(true, "_tANFirstFourValues54_")
```

### Pattern N — svfd Split Value by Delimiter
`svfd(condition, delimiter, maxParts, ...destVars)` splits a field value by delimiter and distributes parts to destination fields. Use `-1` as a dest to skip/discard a part.
```
// Split "Code - Description" by " -" into description field only (-1 skips the code part)
svfd(vo("_restID9_") != "", " -", 1, "_restID9Desc_", -1)

// Split address by space into two address lines
svfd(vo("_address_") != "", " ", 8, "_addressLine1_", "_addressLine2_")

// Split reference by delimiter
svfd(vo("_reltxn_") != "", "~*~", 1, "_referenceno_", -1)
```

Production example (clear + split + save on change):
```
on("change") and (cf(vo("_restID9_") == "", "_restID9Desc_");svfd(vo("_restID9_") != "", " -", 1, "_restID9Desc_", -1);asdff(true, "_restID9Desc_"))
```

### Pattern O — rvm Regex Replace (Title Trimming)
`rvm(sourceValue, regexPattern, replacement, global, destVar)` — regex replace and store result.
```
// Trim Mr/Ms/Mrs from PAN name
rvm(vo("_panHolderName_"), "^(Mr|Ms|Mrs|Miss|Dr|Master|MR|MS|MRS|MISS|DR|MASTER)(\\.|\\ )?", "", true, "_panNameTrimmed_");asdff(vo("_panHolderName_") != "", "_panNameTrimmed_")

// Trim title from entity name on blur
on("blur") and rvm(vo("_EntityName_"), "(Mr|Ms|Mrs|Miss|Dr).?", "", true)
```

### Pattern P — pgtm Page Template Manager
`pgtm(condition, type, ...destVars)` — maps field values using page templates (e.g., PAN type lookup, GSTIN state code).
```
// PAN type mapping
pgtm(vo("_pan_") != "", "PAN", "_panTypeMap_");erbyid(vo("_panTypeMap_") != "", "_panTypeMap_")

// GSTIN state code extraction
pgtm(vo("_gstin_") != "", "GSTIN", "_gstinTypeMap_");erbyid(vo("_gstinTypeMap_") != "", "_gstinTypeMap_")

// FSSAI state code lookup
pgtm(vo("_fssaiNumber_") != "", "FSSAI", "_fssaiStateCode_", 1, 3);cf(vo("_fssaiNumber_") == "", "_fssaiStateCodeSap_", "_fssaiState_", "_fssaiStateCode_");erbyid(vo("_fssaiStateCode_") != "", "_fssaiStateCode_")
```

### Pattern Q — mgem / mngem Generic Editable Mandatory
`mgem(condition, ...destVars)` makes fields mandatory in generic-editable mode. `mngem` is its negative pair.
```
mgem(vo("_companyCode_") == "MELC", "_productionPlant54_");mngem(vo("_companyCode_") != "MELC", "_productionPlant54_")
```

### Pattern R — Approver/Load View
```
on("load") and (po() == 1) and (mvi(true, "_f1_", "_f2_");dis(true, "_f1_", "_f2_");minvi(true, "_f3_", "_f4_"))
```

### Pattern S — Session-Based Visibility
```
sbmvi(vo("_referenceID_") != "", "SECOND_PARTY", "_settlementPanel_", "_chequeDetails_")
```

### Pattern T — Guard Condition
Outer condition gates inner rules — inner rules only execute when guard is true.
```
vo("_gstin_") != "" and (ssm(vo("_gstin_") != "", "FIRST_INDEX", "_gstinPanMatch_", 15, 2, 12);adderr(vo("_panNumber_") != "" and vo("_gstinPanMatch_") != "" and tolc(vo("_gstinPanMatch_")) != tolc(vo("_panNumber_")), "PAN in GSTIN does not match PAN number", "_gstin_");remerr(tolc(vo("_gstinPanMatch_")) == tolc(vo("_panNumber_")), "_gstin_"))
```

### Pattern U — Execute Another Field's Rules
```
erbyid(true, "_grossSalary_")
on("change") and erbyid(true, "_accName_")
erbyid(vo("_kyctype_") != "", "_mobileDuplicateCheckStatus87_")
```

### Pattern V — Advanced Dropdown Rule (ADR)
`adr(condition, delimiter, numberOfWords, ...splitIds, ...refreshIds)` / `advanceDropdownRule` — splits a dropdown value by delimiter and distributes parts to destination fields, then refreshes dependent dropdowns (cascading EDV). Use `-1` in a split array to skip/discard a part.
```
on("change") and adr(vo("_mainGro75_")!="", "-", 1, ["_mainGro10_", -1], ["_subGroup12_"])
```
This splits the value of `_mainGro75_` by `"-"`, takes the first word and puts it in `_mainGro10_` (discards the rest with `-1`), then refreshes dropdown `_subGroup12_`.

### Pattern W — Age Calculation
```
setAgeFromDate("_dateOfBirth_", "_age_");asdff(vo("_age_") != "", "_age_");adderr(vo("_age_") != "" and +vo("_age_") < 18, "Age must be 18 or above", "_age_");remerr(vo("_age_") != "" and +vo("_age_") >= 18, "_age_")
```

### Pattern X — Copy Multiple Fields in Parallel
`copyMultiple([sourceFields], [destFields])` — copies multiple source fields to multiple destination fields in parallel. Used with an external condition.
```
// Copy dependents' relation, DOB, address to EPF fields
condition and copyMultiple(["_dependentsRelation_","_dependentsDob_","_dependaddress_"], ["_epfRelation_","_epfDob_","_epfAddress_"])
```

### Pattern Y — Convert Number to Words
`ctw(sourceField, destField)` — converts a numeric field value to words (for salary, CTC display).
```
ctw("_grosssalary_", "_grossinwords_")
ctw("_tctc1_", "_CTCinWords_")
```

### Pattern Z — Set Conditional Date Range
`setcondstartenddate(destField, startDateField, endDateField)` — sets a date range on the destination field from start/end date fields.
```
setcondstartenddate("_beneficiaryValidity13_", "_licencevalidfrom_", "_licencevalidto_")
on("change") and setcondstartenddate("_validity_", "_startDate_", "_endDate_")
```

### Pattern AA — Conditional Clear on Selection Change
When a selector changes, clear the fields that no longer apply.
```
on("change") and (cf(vo("_addressProof_") != "Aadhaar", "_aadhaarImg_");remerr(vo("_addressProof_") != "Aadhaar", "_aadhaarImg_");cf(vo("_addressProof_") != "Driving Licence", "_dlImg_");remerr(vo("_addressProof_") != "Driving Licence", "_dlImg_");asdff(vo("_addressProof_") != "Aadhaar", "_aadhaarImg_");asdff(vo("_addressProof_") != "Driving Licence", "_dlImg_"))
```

---

## STEP 4: NEGATE THE CONDITION (De Morgan's Law)

This is the MOST CRITICAL step. For every positive action, write the negative pair with the CORRECTLY negated condition.

| Positive condition | Negated condition |
|---|---|
| `A == "X"` | `A != "X"` |
| `A != "X"` | `A == "X"` |
| `A == "X" or A == "Y"` | `A != "X" and A != "Y"` |
| `A == "X" and B == "Y"` | `A != "X" or B != "Y"` |
| `cntns("val", vo("_f_"))` | `not(cntns("val", vo("_f_")))` |
| `not(cntns("val", vo("_f_")))` | `cntns("val", vo("_f_"))` |
| `+vo("_f_") < 18` | `+vo("_f_") >= 18` |
| `+vo("_f_") > 18` | `+vo("_f_") <= 18` |

**Rules**:
- Flip `==` ↔ `!=`
- Flip `or` ↔ `and`
- Wrap/unwrap `not()` for `cntns()`
- Flip `<` ↔ `>=`, `>` ↔ `<=`

**WRONG** (always true!): `mnm(vo("_f_") != "A" or vo("_f_") != "B", "_dest_")`
**CORRECT**: `mnm(vo("_f_") != "A" and vo("_f_") != "B", "_dest_")`

---

## STEP 5: BUILD THE RULE IN ORDER

Write statements in this order (include only what applies):

1. **Visibility pairs**: `mvi(COND, ...);minvi(NEG_COND, ...)`
2. **Mandatory pairs**: `mm(COND, ...);mnm(NEG_COND, ...)`
3. **Enable/Disable pairs**: `en(COND, ...);dis(NEG_COND, ...)`
4. **Copy/Derive + Save**: `ctfd(COND, src, ...);asdff(COND, ...)`
5. **Error pairs**: `adderr(COND, msg, ...);remerr(NEG_COND, ...)`
6. **Clear on hide**: `cf(NEG_COND, ...);remerr(NEG_COND, ...)`
7. **Cascade clear** (SEPARATE rule): `on("change") and (cf(true, ...ALL);asdff(true, ...ALL);rffdd(true, ...DROPDOWNS);rffd(true, ...NON_DROPDOWNS))`

Join statements with `;`. Wrap in event if needed: `on("change") and (...)`.

---

## STEP 6: VERIFY COMPLETENESS

Before finalizing, check EVERY item:

- [ ] Every `mvi` has a matching `minvi` with NEGATED condition (unless condition is `true`)
- [ ] Every `mm` has a matching `mnm` with NEGATED condition
- [ ] Every `adderr` has a matching `remerr` with NEGATED condition
- [ ] Every `ctfd` / `cf` / `ssm` is followed by `asdff`
- [ ] `cntns()` is negated with `not(cntns())` — NEVER with `!=`
- [ ] `or` conditions are negated as `and` with flipped operators
- [ ] Numeric comparisons use `+` prefix: `+vo("_age_") >= 18`
- [ ] ALL panels/fields from the requirement are included — count them
- [ ] Cascade-clear includes ALL child fields from ALL panels
- [ ] No trailing commas before `)`
- [ ] All variable names use `"_variableName_"` format

---

## SYNTAX REFERENCE

- Semicolons `;` separate statements. Commas `,` separate function arguments.
- Field references: `"_variableName_"` (single underscores, inside double quotes)
- Variable names can contain inner underscores: `"_is_gstn_available_"`
- `//` line comments (in .expr files only)
- Keywords: `and`, `or`, `true`, `false`, `not()`
- `+` prefix for numeric casting: `+vo("_age_") >= 18`
- Operators: `==`, `!=`, `<`, `>`, `<=`, `>=`, `+`, `-`, `*`, `/`, `%`
- String literals: `"value"`. Regex: `'/^[A-Z]{5}[0-9]{4}[A-Z]$/'`

---

## FUNCTION REFERENCE

### Value Access
| Function | Description |
|---|---|
| `vo("_varName_")` | Get field value by variable name |
| `vo(123)` | Get field value by numeric metadata ID |
| `+vo("_f_")` | Cast field value to number |
| `elbyid(123)` | Get DOM element by metadata ID |

### Visibility (always pair mvi ↔ minvi)
| Function | Description |
|---|---|
| `mvi(condition, ...destVars)` | Show fields if condition true |
| `minvi(condition, ...destVars)` | Hide fields if condition true |

### Enable/Disable (always pair en ↔ dis)
| Function | Description |
|---|---|
| `en(condition, ...destVars)` | Enable fields |
| `dis(condition, ...destVars)` | Disable fields |

### Mandatory (always pair mm ↔ mnm)
| Function | Description |
|---|---|
| `mm(condition, ...destVars)` | Make fields mandatory |
| `mnm(condition, ...destVars)` | Make fields optional |

### Copy/Derive (always follow with asdff)
| Function | Description |
|---|---|
| `ctfd(condition, srcValue, ...destVars)` | Copy value to fields |
| `asdff(condition, ...destVars)` | Persist values to server |

### Clear/Save/Refresh
| Function | Description |
|---|---|
| `cf(condition, ...destVars)` | Clear field values |
| `rffdd(condition, ...destVars)` | Refresh dropdown options |
| `rffd(condition, ...destVars)` | Refresh non-dropdown data |

### Error (always pair adderr ↔ remerr)
| Function | Description |
|---|---|
| `adderr(condition, message, ...destVars)` | Show error |
| `remerr(condition, ...destVars)` | Remove error |

### String/Utility
| Function | Description |
|---|---|
| `concat(val1, val2, ...)` | Concatenate values |
| `cwd(delimiter, val1, val2, ...)` | Concat with delimiter (ignores empty) |
| `tolc(value)` | Lowercase |
| `touc(value)` | Uppercase |
| `cntns(valueToFind, sequence)` | Check if sequence contains value |
| `rplrng(string, start, end, sub, replaceEach?)` | Replace char range |
| `rgxtst(value, regex)` | Test value against regex |
| `roundTo(value, decimals)` | Round number |
| `size(value)` | Get length/size |
| `not(condition)` | Logical NOT |

### SSM / String Split
| Function | Description |
|---|---|
| `ssm(condition, indexMode, destVar, len, start, end)` | Extract substring |
| `svfd(condition, delimiter, maxParts, ...destVars)` | Split by delimiter |
| `adr(condition, delimiter, numberOfWords, ...splitIds, ...refreshIds)` | Advanced dropdown rule — split & cascade |
| `rvm(value, regex, replacement, global, destVar)` | Regex replace |

### Page Template / Type Mapping
| Function | Description |
|---|---|
| `pgtm(condition, type, ...destVars)` | Page template manager |
| `mgem(condition, ...destVars)` | Make generic editable mandatory |
| `mngem(condition, ...destVars)` | Make generic editable non-mandatory |

### Session/Party
| Function | Description |
|---|---|
| `pt()` | Party type: "FP", "SP" |
| `mt()` | Member type: "CREATED_BY", "CREATED_FOR", "APPROVER", "GENERIC_PARTY" |
| `tso()` | Transaction status: "SENT_TO_SECOND_PARTY" |
| `po()` | Party order (1 = approver) |
| `on(event)` | Event trigger: "change", "load", "input", "blur", "keyup" |
| `sbmvi(condition, param, ...destVars)` | Session-based show |
| `sbminvi(condition, param, ...destVars)` | Session-based hide |

### Copy/Utility
| Function | Description |
|---|---|
| `copyMultiple([sources], [dests])` | Copy multiple source fields to dest fields in parallel |
| `ctw(sourceField, destField)` | Convert numeric value to words |
| `lnv(value)` | Returns length of value (used in conditions: `lnv(vo("_f_")) == 10`) |
| `indexbygrpid(fieldVar, startIndex)` | Returns sequential index within a group |

### Other
| Function | Description |
|---|---|
| `vso(id)` | Validation status: "INIT", "SUCCESS", "FAIL", "PENDING" |
| `setAgeFromDate(srcVar, destVar)` | Calculate age from date |
| `erbyid(condition, ...ids)` | Execute another field's rules |
| `ft(id)` | Get field label |
| `setcondstartenddate(destVar, startVar, endVar)` | Set conditional date range |

---

## COMMON MISTAKES TO AVOID

1. **Forgetting the negative pair**: Every `mvi` needs `minvi`, every `mm` needs `mnm`, every `adderr` needs `remerr`.
2. **Wrong negation of `or`**: `or` becomes `and` with `!=`. Using `or` with `!=` is ALWAYS true.
3. **Missing `not()` for `cntns`**: Negate `cntns("X", vo("_f_"))` as `not(cntns("X", vo("_f_")))` — NEVER as `vo("_f_") != "X"`.
4. **Missing `+` for numbers**: `+vo("_age_") > 18` not `vo("_age_") > 18`.
5. **Forgetting `asdff`**: After `ctfd`, `cf`, `ssm`, `rvm` — values won't persist without `asdff`.
6. **Missing `on("change")`**: Cascade clear MUST be wrapped in `on("change") and (...)`.
7. **Trailing commas**: `mvi(true, "_f_",)` is WRONG.
8. **Missing fields in cascade clear**: The `on("change")` block must include ALL child fields from ALL panels.
9. **`adr` uses array syntax**: `adr` arguments use `[...]` brackets for split/refresh groups: `adr(cond, "-", 1, ["_dest_", -1], ["_refresh_"])`.
10. **`svfd` uses -1 to skip**: `svfd(cond, " -", 1, "_dest_", -1)` — use `-1` as dest to discard a split part.

---

## ENGLISH-TO-EXPRESSION EXAMPLES

These examples show how to translate natural-language requirements into expression rules. Use these as reference when generating rules from plain English descriptions.

### Example 1: Cascade clear on change
**Requirement**: Upon changing the cheque image, clear the IFSC and Account Number, save the cleared value, and refresh the fields.
```
on("change") and (cf(true,"_IFSCNumber_","_AccountNumber_");asdff(true,"_IFSCNumber_","_AccountNumber_");rffd(true,"_IFSCNumber_","_AccountNumber_"))
```

### Example 2: Error validation pair
**Requirement**: An error should be displayed if "Are you the group owner?" is "Yes" and "Are you one of the licensees?" is "No". The error message should read: "The group owner must be a licensee within the group!" Remove the error when conditions are not met.
```
adderr(vo("_areyouaGroupowner_")=="Yes" and vo("_areyouoneofLicensees_")=="No","The group owner must mandatorily be a licensee within the group!","_areyouoneofLicensees_");remerr(vo("_areyouaGroupowner_")!="Yes" or vo("_areyouoneofLicensees_")!="No","_areyouaGroupowner_","_areyouoneofLicensees_")
```

### Example 3: Three-way visibility (Yes/No/Blank)
**Requirement**: If "GST Present" is "Yes": show GST image and GST number, make mandatory. If "No": show declaration, make mandatory, hide GST fields. If blank: hide all, make non-mandatory.
```
on("change") and (minvi(vo("_isgstpresent_") == "", "_gstImage_","_gstnumber_","_declaration_");mnm(vo("_isgstpresent_") == "", "_gstImage_","_gstnumber_","_declaration_");mvi(vo("_isgstpresent_") == "Yes", "_gstImage_","_gstnumber_");mm(vo("_isgstpresent_") == "Yes", "_gstImage_","_gstnumber_");minvi(vo("_isgstpresent_") == "Yes", "_declaration_");mnm(vo("_isgstpresent_") == "Yes", "_declaration_");mvi(vo("_isgstpresent_") == "No", "_declaration_");mm(vo("_isgstpresent_") == "No", "_declaration_");minvi(vo("_isgstpresent_") == "No", "_gstImage_","_gstnumber_");mnm(vo("_isgstpresent_") == "No", "_gstImage_","_gstnumber_"))
```

### Example 4: Multi-value mandatory
**Requirement**: If Account Group is "INDS", "FIVN", "CAVN", or "IMPS" then Clerk, Clerk tel, and Clerk email are mandatory. Otherwise non-mandatory.
```
mm(vo("_HeaderDataAccountGroup_")=="INDS" or vo("_HeaderDataAccountGroup_")=="FIVN" or vo("_HeaderDataAccountGroup_")=="CAVN" or vo("_HeaderDataAccountGroup_")=="IMPS","_CorrespondenceClerkatvendor_","_CorrespondenceAcctclerkstelno_","_CorrespondenceClerksinternetadd_");mnm(vo("_HeaderDataAccountGroup_")!="INDS" and vo("_HeaderDataAccountGroup_")!="FIVN" and vo("_HeaderDataAccountGroup_")!="CAVN" and vo("_HeaderDataAccountGroup_")!="IMPS","_CorrespondenceClerkatvendor_","_CorrespondenceAcctclerkstelno_","_CorrespondenceClerksinternetadd_")
```

### Example 5: Copy/derive with condition
**Requirement**: If PAN type is "Company" copy "CO" to Field1, otherwise copy "CT". Save the result.
```
ctfd(vo("_pANType_")=="Company","CO","_Field1_");ctfd(vo("_pANType_")!="Company","CT","_Field1_");asdff(true,"_Field1_")
```

### Example 6: Approver view on load
**Requirement**: Show and disable fields for approver (party order 1). Hide other fields.
```
on("load") and (po() == 1) and (mvi(true, "_Field1_","_Field2_");minvi(true,"_Field3_","_Field4_");dis(true,"_Field1_"))
```

### Example 7: Second party (vendor) view
**Requirement**: On load, for second party, show PAN panel if field1 type is PAN and field2 is Test, make mandatory; otherwise hide.
```
on("load") and (tso()=="SENT_TO_SECOND_PARTY" and (mvi(vo("_Field1_") == "PAN" and vo("_Field2_") == "Test","_pANPanel_","_pANDetails_","_pAN14_");mm(vo("_Field1_") == "PAN" and vo("_Field2_") == "Test","_pAN14_");mnm(vo("_Field1_") != "PAN" or vo("_Field2_") != "Test","_pAN14_");minvi(vo("_Field1_") != "PAN" or vo("_Field2_") != "Test","_pANPanel_","_pANDetails_","_pAN14_")))
```

### Example 8: Age calculation with error
**Requirement**: Calculate age from date of birth. Show error if under 18.
```
setAgeFromDate("_dateOfBirth_","_age_");asdff(vo("_age_")!="","_age_");adderr(vo("_age_") != "" and +vo("_age_") < 18, "Age must be 18 or above","_age_");remerr(vo("_age_") != "" and +vo("_age_") >= 18,"_age_")
```

### Example 9: Country change cascades to Region dropdown
**Requirement**: When Country field changes, clear Region, save, and refresh its dropdown options.
```
on("change") and (cf(true,"_Region_");asdff(true,"_Region_");rffdd(true,"_Region_"))
```

### Example 10: Advanced Dropdown Rule (ADR)
**Requirement**: On change, split the main group dropdown value by "-" delimiter, put the first part into the sub-field (discard rest), and refresh the dependent sub-group dropdown.
```
on("change") and adr(vo("_mainGro75_")!="", "-", 1, ["_mainGro10_", -1], ["_subGroup12_"])
```

### Example 11: Split field value by delimiter
**Requirement**: Split the restaurant ID by " -" delimiter, put the description part into the description field (skip the code), and save.
```
on("change") and (cf(vo("_restID9_") == "", "_restID9Desc_");svfd(vo("_restID9_") != "", " -", 1, "_restID9Desc_", -1);asdff(true, "_restID9Desc_"))
```

### Example 12: Compound visibility with PAN Aadhaar check
**Requirement**: If PAN Card Category is "Yes" AND PAN Aadhaar Link Status is NOT "Y", show the TDS warning label. If link status IS "Y", hide it.
```
mvi(vo("_PanDetailsPANCardCategory_") == "Yes" and vo("_pANAadhaarLinkStatus15_") != "Y","_20TdsLabel_");minvi(vo("_PanDetailsPANCardCategory_") == "Yes" and vo("_pANAadhaarLinkStatus15_") == "Y","_20TdsLabel_")
```

### Example 13: Enable/Disable based on dependency
**Requirement**: Disable end date when start date is empty. Enable and clear when start date has a value.
```
dis(vo("_startDate_") == "", "_endDate_");en(vo("_startDate_") != "", "_endDate_");cf(vo("_startDate_") == "", "_endDate_");asdff(vo("_startDate_") == "", "_endDate_")
```
