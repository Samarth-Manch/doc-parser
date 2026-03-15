# Expression Function Patterns: cf, ctfd, asdff, rffdd

> **Auto-generated document** — patterns discovered by analyzing real production EXECUTE rules from the Manch platform database dump. This document is iteratively updated by the Expression Pattern Analyzer agent.

---

## Table of Contents

1. [Overview](#overview)
2. [Individual Function Patterns](#individual-function-patterns)
3. [Two-Function Combinations](#two-function-combinations)
4. [Three-Function Combinations](#three-function-combinations)
5. [Four-Function Combination](#four-function-combination)
6. [Composite Patterns (with other functions)](#composite-patterns)
7. [Conditional Logic Patterns](#conditional-logic-patterns)
8. [Structural Patterns](#structural-patterns)
9. [Anti-Patterns & Gotchas](#anti-patterns--gotchas)

---

## Overview

The four core data-manipulation functions in Manch Expression (Client) rules are:

| Function | Alias | Purpose |
|----------|-------|---------|
| `copyToFillData` | `ctfd` | Derive/copy a value into destination fields |
| `clearField` | `cf` | Clear destination field values |
| `autoSaveFormFillData` | `asdff` | Persist the current field value to the server |
| `refreshFormFillDropdownData` | `rffdd` | Reload dropdown options (for cascading EDV dropdowns) |
| `fillDropdownData` | `fdd` | Populate destination fields from a dropdown's backing data columns |
| `concatenateWithDelimiter` | `cwd` | Join multiple values with a delimiter string |
| `concat` | `concat` | Concatenate multiple values into a single string (no delimiter) |
| `roundTo` | `roundTo` | Round a numeric value to N decimal places |
| `addSelectOptions` | `addSelectOptions` | Dynamically populate a dropdown's options from a list of field variable names |
| `selectedOptionMetaDataId` | `selectedOptionMetaDataId` | Get the metadata ID (variable name) of the currently selected dropdown option |
| `copyMultiple` | `copyMultiple` | Copy arrays of source fields to corresponding destination fields in parallel |
| `valOfSaved` | `vso` | Gets the field's **server-side/saved** value (as opposed to `vo` which reads the current client-side value) |

These functions are frequently used **together** in specific patterns. This document catalogs every observed pattern from production data.

---

## Individual Function Patterns

### I-1. ctfd — Computed Value Derivation

**Description:** `ctfd` is used alone to derive a computed value (e.g., arithmetic on field values) and write it to a destination field. No save or clear is needed because the result is purely display-side.

**When Used:** Calculated fields (e.g., multiplication of two columns in a repeatable row) where the result does not need to be persisted immediately and no prior value needs clearing.

**Generic Template:**
```
ctfd(<non-empty-condition>, <arithmetic-expression>, "<dest_var>")
```

**Real Example (Rule 72647):**
```
{ctfd(vo("_oldDisDetails21_"), *vo("_oldDisDetails21_") * *vo("_oldDisDetails22_"), "_oldDisDetails23_");}
```
Multiplies two detail fields and writes the product to a third field. The condition `vo("_oldDisDetails21_")` ensures derivation only happens when the source is non-empty.

**Variant — Chained Computation DAG (Rule 81982):** Multiple `ctfd` calls can form a **computation pipeline/DAG** where the output of one `ctfd` feeds as input into the next. This creates a spreadsheet-like chain of dependent calculations:
```
{ctfd(vo("_oldDisDetails3_")!="",(+vo("_oldDisDetails3_") / +vo("_30num_")) * +vo("_normInDaysEDV_"),"_dis1partyD17_");
 ctfd(vo("_dis1partyD17_")!="",(+vo("_dis1partyD17_") / +vo("_perCaserateEDV_")),"_avgStock3500_");
 ctfd(vo("_avgStock3500_")!="",((+vo("_avgStock3500_") / +vo("_100num_"))* +vo("_70num_")) * +vo("_FactorEDV_"),"_Godown1_");
 ctfd(vo("_oldDisDetails3_")!="",((+vo("_oldDisDetails3_") / +vo("_100000num_")) / +vo("_40num_")) * +vo("_OfcEDV_"),"_LandD1_");
 ctfd(vo("_dis1partyD11_")!="",+vo("_dis1partyD11_") + +vo("_dis1partyD8_") + +vo("_dis1partyD12_"),"_countOfSupStaff1_");
 ctfd(vo("_countOfSupStaff1_")!="",+vo("_countOfSupStaff1_") * +vo("_10num_"),"_Staff1_");
 ctfd(vo("_Godown1_")!="",+vo("_Godown1_") + +vo("_LandD1_") + +vo("_OfcEDV_") + +vo("_Staff1_") + +vo("_POSMedv_") + +vo("_MeetingEDV_"),"_dis1partyD14_");
 ctfd(vo("_dis1partyD14_")!="",+vo("_dis1partyD14_") * +vo("_RentalSqFtEDV_"),"_RentalSqFt1_");
 ctfd(vo("_dis1partyD14_")!="",+vo("_dis1partyD14_") * +vo("_RentalTownEDV_"),"_RentalTown1_");
 ctfd(vo("_RentalSqFt1_")!="",vo("_RentalSqFt1_"),"_TotalCost1_");}
```
10 chained `ctfd` calls computing a cost model: daily distribution → average stock → godown cost → land cost → staff count → staff cost → total overhead → rental costs → total cost. Key traits:
- **No `asdff`** — all results are display-only (computed on load, `execute_on_fill: true`)
- Uses **numeric constant fields** (e.g., `_30num_`, `_100num_`, `_70num_`) as EDV-sourced constants
- Extensive use of `+vo()` for numeric coercion (see [CL-8](#cl-8-numeric-coercion-with-vo))
- Some steps branch from the same source (`_oldDisDetails3_` feeds both step 1 and step 4)
- The DAG structure means field evaluation order matters — each `ctfd` depends on prior results being available

**Variant — Sum-of-Many-Fields with erbyid Chaining (Rules 17765, 52604, 52618):** `ctfd` sums many column values and writes the total to a destination field, then `erbyid` triggers the destination field's own rules for further processing:
```
{[0:0]={"ctfd(vo(\"_map4B1_\"), +vo(\"_map4B1_\") + +vo(\"_map4B2_\") + +vo(\"_map4B3_\") + +vo(\"_map4B4_\") + +vo(\"_map4B5_\") + +vo(\"_map4B6_\") + +vo(\"_map4B7_\") + +vo(\"_map4B8_\") + +vo(\"_map4B9_\"), \"_grossSalary_\");erbyid(true, \"_grossSalary_\")"}}
```
Non-array context variant (Rule 52604):
```
{ctfd(vo("_map4B1_"), +vo("_map4B1_") + +vo("_map4B2_") + +vo("_map4B3_") + +vo("_map4B4_") + +vo("_map4B5_") + +vo("_map4B6_") + +vo("_map4B7_") + +vo("_map4B8_") + +vo("_map4B9_"), "_grossSalary_");erbyid(true, "_grossSalary_")}
```
MAP5 variant (Rule 52618):
```
{ctfd(vo("_map5B1_"), +vo("_map5B1_") + +vo("_map5B2_") + ... + +vo("_map5B9_"), "_map5B10_");erbyid(true, "_map5B10_")}
```
Key traits:
- Sums **9 fields** using `+vo()` numeric coercion into a total field
- The condition `vo("_map4B1_")` / `vo("_map5B1_")` ensures the first column is non-empty before computing
- `erbyid(true, ...)` delegates to the total field's own rules (e.g., for further derivations or validations that depend on the total) -- see [C-14](#c-14-ctfd--erbyid--derive-then-delegate)
- Works in **both** array context `[0:0]` (Rule 17765, `run_post_condition_fail: true`) and **non-array context** (Rules 52604, 52618, `run_post_condition_fail: false`)
- MAP4 variant sums into `_grossSalary_`, MAP5 variant sums into `_map5B10_` — parallel salary structure across divisions

**Variant — Massive Lookup Table / Code Mapping (Rule 32997):** `ctfd` can implement an entire **code-to-value mapping table** using dozens of calls with the same source field, each checking a different value and writing a different result. This is effectively a switch-case or VLOOKUP implemented as sequential `ctfd` calls:
```
{ctfd(vo("_fssaiStateCode_") == "00","Ok","_fssaiStateCodeSap_");
 ctfd(vo("_fssaiStateCode_") == "01","01","_fssaiStateCodeSap_");
 ctfd(vo("_fssaiStateCode_") == "02","02","_fssaiStateCodeSap_");
 ... (37 state codes → SAP codes)
 ctfd(vo("_fssaiStateCode_") == "00","CENTRAL","_fssaiState_");
 ctfd(vo("_fssaiStateCode_") == "01","ANDHRA PRADESH","_fssaiState_");
 ctfd(vo("_fssaiStateCode_") == "02","ARUNACHAL PRADESH","_fssaiState_");
 ... (37 state codes → state names)
 erbyid(vo("_fssaiState_")!="","_fssaiState_");}
```
Key traits:
- **74 `ctfd` calls** in a single rule — the largest observed use of ctfd
- Maps the same source field (`_fssaiStateCode_`) to **two different destination fields** (`_fssaiStateCodeSap_` and `_fssaiState_`) — the first set maps codes to SAP numeric codes, the second maps codes to state names
- Only one condition matches at a time (mutually exclusive equality checks), so the last-writer-wins concern is irrelevant
- `erbyid` at the end delegates to the state name field's own rules
- No `asdff` — display-only derivation
- This is an extreme version of [CL-2](#cl-2-multi-branch-on-dropdown-value) scaled to 37+ values across 2 destinations

**Variant — Simple 2-Value Code Mapping (Rule 50823):** The minimal form of the lookup table pattern — just two `ctfd` calls mapping short codes to human-readable labels:
```
{ctfd(vo("_panCopy62_") == "S","Yes","_pancopyyesno42_");ctfd(vo("_panCopy62_") == "N","No","_pancopyyesno42_");}
```
Maps "S" → "Yes" and "N" → "No" for a PAN copy flag. `execute_on_fill: true` — runs on form load to translate the stored code into a display value. No `asdff` — display-only. This is the simplest end of the spectrum from 2-value (Rule 50823) to 74-value (Rule 32997) code mappings.

**Variant — Load-Time Display Label via concat() (Rule 51859):** `ctfd` wrapped in `on("load")` uses `concat()` to build a formatted composite display string from multiple source fields. This creates a human-readable label on form load:
```
{on("load") and (ctfd(vo("_cityID90_")!="",concat(vo("_cityID90_")," - ",vo("_city_")),"_cityId_"))}
```
On form load, when cityID90 is non-empty, concatenate the city ID, literal `" - "`, and city name into a composite display value for the `_cityId_` field. Key traits:
- **`on("load")`** — fires only on form load, not on field changes (see [S-9](#s-9-onload-wrapper))
- **`concat()` as value parameter** — the delimiter `" - "` is embedded as a regular argument between field values, unlike `cwd()` where the delimiter is the first parameter. This is simpler for 2-field joins with a fixed separator
- **Display formatting** — creates a "ID - Name" composite label from separate ID and name fields
- No `asdff` — display-only derivation
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Variant — Load-Time Zone Label via concat() (Rule 51860):** Identical pattern to Rule 51859 but for zone fields instead of city fields:
```
{on("load") and (ctfd(vo("_zoneID83_")!="",concat(vo("_zoneID83_")," - ",vo("_zone_")),"_zoneId_"))}
```
On form load, concatenate zone ID, `" - "`, and zone name into the `_zoneId_` display field. Confirms this pattern is reused across different entity types (city, zone) in the same form.

**Variant — Progressive Enhancement with Fallback (Rule 51921):** Two `ctfd` calls with overlapping conditions, where the second **overwrites** the first when additional data is available. Creates a fallback-to-full display label:
```
{on("load") and (ctfd(vo("_cityID90_")!="",vo("_cityID90_"),"_cityId_");ctfd(vo("_cityID90_")!="" and vo("_city_")!="",concat(vo("_cityID90_")," - ",vo("_city_")),"_cityId_"))}
```
Two-phase derivation: (1) When only cityID90 exists, write just the ID. (2) When BOTH cityID90 and city name exist, overwrite with the full "ID - Name" format. The second `ctfd` has a **stricter compound `and` condition** — it only fires when both fields are non-empty. When only the ID is available, the user sees just the ID. When both are available, the full formatted label appears. Key traits:
- **Overwrite semantics** — the second `ctfd` targets the same destination as the first, relying on sequential evaluation order
- **Compound `and` condition** — `vo("_cityID90_")!="" and vo("_city_")!=""` ensures both source fields are populated
- This is a **graceful degradation** pattern for composite display labels
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Variant — Progressive Enhancement for Zone (Rule 51926):** The same two-phase fallback pattern applied to zone fields instead of city fields, confirming it generalizes across entity types:
```
{on("load") and (ctfd(vo("_zoneID83_")!="",vo("_zoneID83_"),"_zoneId_");ctfd(vo("_zoneID83_")!="" and vo("_zone_")!="",concat(vo("_zoneID83_")," - ",vo("_zone_")),"_zoneId_"))}
```
Phase 1: When zone ID is non-empty, write just the ID. Phase 2: When BOTH zone ID and zone name exist, overwrite with "ID - Name" format. Identical structure to Rule 51921 (city variant). `execute_on_fill: true`, `run_post_condition_fail: false`.

**Variant — Implicit-Value 2-Parameter Shorthand (Rule 52127):** `ctfd` with only **2 parameters** — the condition value implicitly doubles as the source value. No explicit source value parameter:
```
{ctfd(vo("_validtill_"),"_endDate70_");}
```
When `_validtill_` is non-empty, copy its value to `_endDate70_`. The `vo("_validtill_")` serves as both the condition (truthy check) and the implicitly derived value. This is a shorthand for `ctfd(vo("_validtill_"), vo("_validtill_"), "_endDate70_")`. Key traits:
- **Only 2 parameters** instead of the standard 3+ — `ctfd(condition, destination)` with no explicit `srcValue`
- The condition's evaluated result IS the copied value — the field value that makes the condition truthy is the same value written to the destination
- `source_ids` is empty `{}` — the rule has no explicitly declared source, consistent with the implicit source
- `execute_on_fill: true`, `execute_on_read: false`
- See also [S-11](#s-11-ctfd-2-parameter-shorthand) for structural documentation

**Variant — Mass Multi-Destination Propagation with Dual-Condition Guards (Rule 52717):** 20 `ctfd` calls propagate a single source value (`_addressLine1Permanent_`) to 10 dependent address fields using a two-phase guard strategy. Phase 1 fills empty fields; Phase 2 re-synchronizes fields that still hold the old source value:
```
{ctfd(vo("_dependaddress_")=="", vo("_addressLine1Permanent_"), "_dependaddress_");
 ctfd(vo("_dependaddress1_")=="", vo("_addressLine1Permanent_"), "_dependaddress1_");
 ctfd(vo("_dependaddress2_")=="", vo("_addressLine1Permanent_"), "_dependaddress2_");
 ... (10 calls, one per dependent field, condition: dest is empty)
 ctfd(vo("_dependaddress_")==vo("_addressLine1Permanent_"), vo("_addressLine1Permanent_"), "_dependaddress_");
 ctfd(vo("_dependaddress1_")==vo("_addressLine1Permanent_"), vo("_addressLine1Permanent_"), "_dependaddress1_");
 ctfd(vo("_dependaddress2_")==vo("_addressLine1Permanent_"), vo("_addressLine1Permanent_"), "_dependaddress2_");
 ... (10 calls, one per dependent field, condition: dest equals source)}
```
Two-phase logic:
1. **Phase 1 — Fill empty:** `ctfd(vo("_dependaddressN_")=="", vo("_addressLine1Permanent_"), "_dependaddressN_")` — if the dependent field is empty, copy the permanent address into it. This initializes unfilled fields.
2. **Phase 2 — Re-sync stale:** `ctfd(vo("_dependaddressN_")==vo("_addressLine1Permanent_"), vo("_addressLine1Permanent_"), "_dependaddressN_")` — if the dependent field still holds the same value as the source (i.e., hasn't been manually changed by the user), re-copy. This is effectively a no-op on the current evaluation but ensures the field stays synchronized if the source changes later.

Key traits:
- **20 `ctfd` calls** — 10 dependent fields x 2 condition phases each
- **Each `ctfd` checks its own destination** as the condition — the condition references the field being written to, not a separate source
- **Propagate-if-empty-or-unchanged semantics** — respects user overrides: if a user has manually changed a dependent address to something different from the source, neither phase will overwrite it
- **Single source value** `vo("_addressLine1Permanent_")` across all 20 calls — fan-out from one source to many destinations
- No `asdff` — display-only propagation
- `execute_on_fill: false`, `run_post_condition_fail: false`

**Variant — Multi-Source Weighted Sum (Rule 36676):** `ctfd` computes a weighted sum across multiple source fields with different multipliers, implementing a purity-adjusted gold valuation formula:
```
{ctfd(vo("_goldWeightIn18CaratInGrams97_"),
  (+vo("_goldWeightIn18CaratInGrams97_") * 18 * +vo("_currentRateOfGoldInPerGram_") / 24) +
  (+vo("_goldWeightIn22CaratInGrams75_") * 22 * +vo("_currentRateOfGoldInPerGram_") / 24) +
  (+vo("_goldWeightIn24CaratInGrams69_") * 24 * +vo("_currentRateOfGoldInPerGram_") / 24),
  "_totalPledgedValue_");}
```
Computes total pledged gold value by normalizing weights across 18, 22, and 24 carat purities: each weight is multiplied by its carat value and the current gold rate, then divided by 24 to get the equivalent fine gold value. The three terms are summed into a single `_totalPledgedValue_` destination.

Key traits:
- **Weighted sum formula** — `(w₁ × p₁ × rate / 24) + (w₂ × p₂ × rate / 24) + (w₃ × p₃ × rate / 24)` where p₁=18, p₂=22, p₃=24
- **Three distinct source fields** combined in a single arithmetic expression — each `+vo()` reads a different weight field
- **Shared multiplier field** `_currentRateOfGoldInPerGram_` is referenced 3 times in the formula
- **Condition** `vo("_goldWeightIn18CaratInGrams97_")` — only the first weight field is checked for non-empty; if 22 or 24 carat weights are empty, `+vo("")` → 0, which is correct (zero contribution)
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Variant — Scoring Rubric: Multi-Branch Map → Weight → Total (Rules 82038, 82040, 82042, 82044):** A 3-stage scoring pattern where `ctfd` first maps a dropdown value to a numeric score via multi-branch conditions, then multiplies by a weight factor, then sums all weighted scores into a total. Four identical rules implement this for different review categories (sales, financial review, delivery management, competency):
```
{on("change") and (ctfd(vo("_dis1invD7_")=="Proprietor" or vo("_dis1invD7_")=="Manager","4","_compSpeakScore1_");
 ctfd(vo("_dis1invD7_")=="Other","1","_compSpeakScore1_");
 ctfd(vo("_dis1invD7_")=="","0","_compSpeakScore1_"));
 ctfd(vo("_compSpeakScore1_")!="",+vo("_compSpeakScore1_") * +vo("_25perNum_"),"_compSpeakScore125_");
 ctfd(vo("_compSpeakScore1_")!="",+vo("_salesreview125_") + +vo("_finReviewScore125_")+ +vo("_delManScore125_")+ +vo("_compSpeakScore125_"),"_invTotalScore1_");}
```
Three-stage pipeline:
1. **Multi-branch map** (inside `on("change")` parentheses): Proprietor/Manager → 4, Other → 1, empty → 0 into a raw score field
2. **Weight multiplication**: raw score × 25% factor → weighted score field
3. **Total aggregation**: sum of all 4 weighted category scores → total score field

Key traits:
- **`or` condition for multi-value match** — `=="Proprietor" or =="Manager"` maps two values to the same score
- **Parenthesis scoping** — the 3 branch `ctfd` calls are wrapped in `on("change") and (...)`, while the 2 computation `ctfd` calls are OUTSIDE the parentheses (always evaluate, not only on change)
- **Shared total field** — all 4 category rules write to the SAME `_invTotalScore1_` destination, each recomputing the total. The last one evaluated wins (all produce the same sum)
- **Numeric constant field** `_25perNum_` holds the 0.25 weight factor (loaded from EDV)
- **No `asdff`** — display-only scoring, `execute_on_fill: true`
- Reused across 4 review categories in the same form, confirming it's a reusable scoring rubric pattern

**Frequency:** Uncommon as a standalone pattern (usually paired with `asdff`).

### I-2. asdff — Standalone Auto-Save

**Description:** `asdff` is used alone to persist field value(s) to the server without any derivation or clearing. The field's current value is saved as-is.

**When Used:** Two main scenarios:
1. A field saves **itself** after being populated (e.g., by an external rule or user input in a repeatable row).
2. A condition change triggers saving multiple related fields that were previously modified by other rules.

**Generic Template (self-save):**
```
asdff(vo("<field>") != "", "<field>")
```

**Generic Template (conditional multi-field save):**
```
on("change") and asdff(<condition>, "<dest1>", "<dest2>", "<dest3>", "<dest4>")
```

**Real Example — Self-Save in Array Context (Rule 30679):**
```
{[0:0]={"asdff(vo(\"_manchReferenceID50_\") != \"\", \"_manchReferenceID50_\");"}}
```
When the reference ID is non-empty, save it. The field saves itself — no derivation or clearing. Array context (`[0:0]`), `run_post_condition_fail: true`.

**Real Example — Conditional Multi-Field Save on Change (Rule 19229):**
```
{on("change") and asdff(vo("_areYouDirectly_")=="No","_V34_","_V38_","_V42_","_V46_");}
```
When "are you directly" is "No", save four fields at once. Triggered on change. These fields were likely populated/cleared by other rules; this rule ensures they are persisted.

**Variant — Unconditional Mass Save (Rule 17533):** `asdff` with `true` condition saving **13 fields** at once — the largest observed single `asdff` call. Used to persist all product-related fields in a shopping cart / order form:
```
{[0:0]={"asdff(true, \"_productNameShirt_\", \"_productNameShirtprice_\", \"_tshirtqty_\", \"_tshirtamount_\", \"_productNameBag_\", \"_productNamebagprice_\", \"_bagqty_\", \"_bagamount_\", \"_productNameRainCoat_\", \"_productNameRainCoatPrice_\", \"_raincoatqty_\", \"_raincoatamount_\",\"_totalamount_\");"}}
```
Saves all product names, prices, quantities, amounts, and total in one call. The `true` condition means every evaluation triggers the save. Array context `[0:0]`, `run_post_condition_fail: true`. Related to Rule 17539 ([C-20](#c-20-mvi--fdd--ctfd--erbyid--click-triggered-product-selection)) which populates these fields.

**Key Observations:**
- `asdff` can target the **same field** it reads (self-save) or **different fields**
- Can save **multiple fields** in a single call — up to **13 fields** observed (Rule 17533)
- Often has `run_post_condition_fail: true`, meaning it runs after other rules complete
- `on("change")` wrapper is optional — depends on when the save should trigger

**Frequency:** Uncommon but observed in both array and non-array contexts.

### I-3. cf — Multi-Branch Standalone Clear

**Description:** Multiple `cf` calls with different conditions, each clearing different field groups. No save (`asdff`), no refresh (`rffdd`), no error removal (`remerr`). Pure client-side clearing.

**When Used:** When a categorization field changes and different groups of dependent fields need to be cleared based on the selected value, but persistence is handled elsewhere (e.g., by a separate save rule or on form submission).

**Generic Template:**
```
cf(vo("<src>") == "<val_A>", "<field_group_A>");
cf(vo("<src>") == "<val_B>", "<field_group_B>");
cf(vo("<src>") == "<val_C>", "<field_group_C>");
```

**Real Example (Rule 19212):**
```
{cf(vo(72709)=="GSTIN",72710,72711);cf(vo(72709)=="PAN",72710,72720);cf(vo(72709)=="CIN",72711,72720);}
```
When the document type is "GSTIN", clear PAN and CIN fields. When "PAN", clear GSTIN and CIN. When "CIN", clear GSTIN and PAN. Each branch clears the fields belonging to the *other* categories.

**Key Observations:**
- Uses **numeric field IDs** instead of variable names (see [S-7](#s-7-numeric-field-ids))
- Some fields appear in multiple cf calls (e.g., 72710 is cleared for both GSTIN and PAN conditions) — this is because a field should be cleared whenever it's not the active category
- No `asdff` — the clear is client-side only. Persistence may happen via form submission or a separate rule
- `run_post_condition_fail: true`

**Variant — Single-Condition Single-Field Clear (Rule 20197):** The simplest `cf` usage — a single condition clearing a single field:
```
{cf(vo("_paymenttype_")=="Cash","_typeOfCredit_");}
```
When payment type is "Cash", clear the type of credit field. `run_post_condition_fail: true`. No branches, no error removal, no save — pure minimal clear.

**Variant — Compound Equality-Guard Clear (Rule 1877):** `cf` with a complex AND condition that checks both a flag field AND cross-field equality before clearing. Uses numeric field IDs:
```
{cf((vo(24399)=="No" and vo(24393)==vo(24400) and vo(24394)==vo(24401) and vo(24395)==vo(24402)
    and vo(24396)==vo(24403) and vo(24397)==vo(24404) and vo(24398)==vo(24405)),
   24400,24401,24402,24403,24404,24405);}
```
Clears 6 destination fields only when: (1) field 24399 is "No" AND (2) six source-destination pairs are equal (the destination fields still contain copies from the source). This is a "revert copies" pattern — when the user answers "No" (e.g., "are addresses the same?"), the copied fields are cleared only if they haven't been manually changed. `run_post_condition_fail: true`.

**Variant — Large Empty-Guard Clear on Load (Rule 36385):** Single `cf` call with an empty-check condition clearing **11 dependent fields** at once. Runs on form load (`execute_on_fill: true`) to reset detail fields when a parent presence flag is empty:
```
{cf(vo("_isgstpresent17_")=="","_tradeName18_","_longName19_","_regDate20_","_cityCity21_","_typeType22_","_buildingNo23_","_flatNo24_","_districtCode25_","_stateCode26_","_streetStreet27_","_pinCode28_")}
```
When the GST presence field is empty, clear all 11 GST detail fields (trade name, long name, registration date, city, type, building no, flat no, district code, state code, street, pin code). Key traits:
- **11 fields** in a single `cf` call — among the largest observed standalone clears
- **Empty-check condition** `vo(...)==""` — clears when the parent is absent, not when it changes to a specific value
- **`execute_on_fill: true`** — fires on form load to ensure stale detail fields are cleaned up when GST is not present
- No `asdff` — client-side only; no `on("change")` wrapper since it runs on load
- `run_post_condition_fail: false`

**Variant — Blur-Triggered Empty-Guard Clear of Multiple Dependents (Rule 36949):** A standalone `cf` wrapped in `on("blur")` clears multiple dependent fields when the source field is empty. No `asdff`, no `rffdd`, no `remerr`:
```
{on("blur") and (cf(vo("_manPin_")=="","_manDistrict_","_manState_"))}
```
When the pin code field loses focus and is empty, clear the district and state fields. The `on("blur")` wrapper ensures the clear only fires when the user tabs/clicks away, not during typing. This is the I-3 standalone clear combined with [S-6 on("blur")](#s-6-onblur-wrapper). `execute_on_fill: true`, `run_post_condition_fail: false`.

**Variant — NOT-EQUAL Multi-Branch Clear for Document Type Switching (Rule 36931):** Instead of `==` (clear OTHER groups), uses `!=` (clear THIS group when NOT selected). Each `cf` clears its own document type's fields when a different type is chosen. This produces the same net effect as I-3's base pattern but with inverted logic:
```
{on("change") and (cf(vo("_kyctype_") != "Driving License E-Verify" ,"_1DLdob_","_1DLnumber_","_1DLname_","_1DLvalidtill_","_1DLaddress_");
 cf(vo("_kyctype_") != "Aadhaar E-Verify" ,"_aadNo_","_aadName_","_aadGen_","_aadDOB_","_addPerAad_",106730,"_pinAad_","_cityAad_","_distAad_","_stateAad_");
 cf(vo("_kyctype_") != "Aadhaar Upload" ,"_V24_","_V25_","_V26_","_V27_","_V30_","_V31_","_V32_","_city54_","_district24_","_state38_","_aadhfront_","_aadhback_");
 cf(vo("_kyctype_") != "Driving License Upload" ,"_dl_","_DLnumber_","_DLdob_","_DLvalidtill_","_DLname_","_DLaddress_","_dl_");
 cf(vo("_kyctype_") != "Passport Upload" ,"_passportFrontImage62_","_uploadPassport50_","_surnameSurname51_",...<18 fields total>));}
```
Five KYC document types, each with its own `cf` call. When the user selects "Aadhaar E-Verify", the 4 other `cf` calls fire (their `!=` conditions are true) and clear DL E-Verify, Aadhaar Upload, DL Upload, and Passport fields. The Aadhaar E-Verify `cf` does NOT fire (condition is false).

Key traits:
- **Inverted logic from base I-3** — base uses `==` to target OTHER groups; this uses `!=` to target OWN group. Both achieve "clear non-selected groups"
- **Up to 18 fields per `cf` call** — Passport Upload has the most fields to clear
- **Mixed field references** — uses both variable names (`"_aadNo_"`) and a numeric field ID (`106730`) in the same `cf` call
- **5 branches for 5 document types** — scales naturally with each new document type adding one more `cf` call
- **No `asdff`** — client-side only clear, `on("change")` event
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Uncommon as a standalone pattern (usually paired with `asdff` or `remerr`).

### I-4. rffdd — Standalone Conditional Dropdown Refresh

**Description:** `rffdd` is used alone to refresh a dropdown's options based on a condition, without clearing the field first. This assumes the dropdown's current value is acceptable or irrelevant — only the available options need updating.

**When Used:** When a parent field changes and a child dropdown needs its options reloaded, but the child's current value should be preserved (or was already cleared by another rule). Often wrapped in `on("change")`.

**Generic Template:**
```
on("change") and (rffdd(<condition>, "<dropdown_var>"))
```

**Real Example (Rule 48829):**
```
{on("change") and (rffdd(vo("_LocQue8_")=="Restaurant Location", "_restID9_"))}
```
When the location type equals "Restaurant Location", refresh the restaurant ID dropdown options. No clear is needed because the restaurant dropdown is only relevant when this specific location type is selected.

**Variant — Unconditional Multi-Field Refresh (Rules 33655, 33832):** `rffdd` can use a literal `true` condition and target **multiple dropdown fields** in a single call. This fires unconditionally on every change, refreshing all listed dropdowns regardless of the parent's new value:
```
{on("change") and (rffdd(true, "_degreeordiploma_","_specialization69_"))}
```
When ANY change occurs on the source field, both degree/diploma and specialization dropdowns are refreshed. The `true` condition means no value check is needed — any change should reload options. This is used when the parent-child relationship is unconditional and the child dropdowns always depend on the parent. `execute_on_fill: true`, `run_post_condition_fail: true`.

**Variant — Unconditional Single-Field Refresh (Rules 33654, 33836):** The simplest `rffdd` usage — unconditional refresh of a single dropdown on change:
```
{on("change") and (rffdd(true, "_specialization69_"))}
```
Refreshes the specialization dropdown on every change to the parent field. Often used alongside the multi-field variant when different parent fields each refresh different subsets of the cascade chain. `execute_on_fill: true`, `run_post_condition_fail: true`.

**Variant — Unconditional in Array Context (Rule 34712):** The unconditional single-field refresh appears in array context `[0:0]`, confirming it works identically inside repeatable rows:
```
{[0:0]={"on(\"change\") and (rffdd(true, \"_district_\"))"}}
```
Refreshes the district dropdown on every change to the parent field within a repeatable row. `execute_on_fill: true`, `run_post_condition_fail: true`.

**Frequency:** Observed in targeted dropdown refresh scenarios where clearing is handled elsewhere. Unconditional `true`-condition variants are common for simple cascading hierarchies (e.g., degree → specialization, state → district).

---

## Two-Function Combinations

### II-1. ctfd + asdff — Derive Literal Value and Save

**Description:** Sets a destination field to a literal (hardcoded) string value, then auto-saves that field to the server. The same condition governs both functions.

**When Used:** When a source field having a value should trigger a fixed/literal value to be written and persisted in another field (e.g., setting a trigger flag, deriving a status).

**Generic Template:**
```
ctfd(<condition>, "<literal_value>", "<dest_var>");
asdff(<condition>, "<dest_var>");
```

**Real Example (Rule 48579):**
```
{ctfd(vo("_manchReferenceID50_")!="", "TRIGGERINVOICE", "_invoiceGen_");
 asdff(vo("_manchReferenceID50_")!="", "_invoiceGen_");}
```
When the reference ID is non-empty, sets `_invoiceGen_` to the literal "TRIGGERINVOICE" and saves it.

**Frequency:** Common.

**Variant — Field Value Source (Rule 48839):** `ctfd` can also copy a **field value** (via `vo()`) instead of a literal string:
```
ctfd(vo("_IsMeetingQue7_")=="Away", vo("_Text1_"), "_compareL1Manager87_");
asdff(true, "_compareL1Manager87InPerson_");
```
Here `vo("_Text1_")` is the source value, dynamically reading from another field rather than using a hardcoded string. This variant is common in routing/assignment rules.

**Variant — Blur-Triggered Arithmetic Derivation with Auto-Save (Rules 76491, 76488, 76494, 76493, 76486, 76502, 76505):** `ctfd` computes an **arithmetic product** of two fields and writes the result to a third field, with `asdff(true, ...)` to persist the result. Wrapped in `on("blur")` to avoid recalculating on every keystroke. The condition checks both operands are non-empty before computing:
```
{on("blur") and (ctfd(vo("_A_")!="" and vo("_B_")!="", +vo("_A_") * +vo("_B_"), "_C_"); asdff(true, "_C_"))}
```
Real Example (Rule 76491):
```
{on("blur") and (ctfd(vo("_dis1partyD9_")!="" and vo("_v5_")!="", +vo("_dis1partyD9_") * +vo("_v5_"), "_v6_"); asdff(true, "_v6_"))}
```
When both `_dis1partyD9_` and `_v5_` are non-empty, multiply them and write the product to `_v6_`, then save. Key traits:
- **`on("blur")`** — fires when either operand field loses focus, not on every keystroke. This is appropriate for numeric input fields where the user may be typing multiple digits
- **Compound `and` non-empty guard** — `vo("_A_")!="" and vo("_B_")!=""` ensures both operands have values before attempting arithmetic, preventing `NaN` or incorrect results
- **`+vo()` numeric coercion** on both operands (see [CL-8](#cl-8-numeric-coercion-with-vo)) — converts string field values to numbers for multiplication
- **`asdff(true, dest)`** — unconditional save of the computed result, ensuring the product is persisted
- **7 identical instances** in the same form — each computing `quantity × rate = amount` for different line items in a discount/distribution table (field naming patterns: `_dis1partyD7_`×`_v1_`→`_v2_`, `_dis1partyD8_`×`_v3_`→`_v4_`, etc.)
- All share: `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`
- Differs from I-1 (ctfd-only arithmetic) by adding `asdff` — the computed result must be persisted, not just displayed
- Differs from the base II-1 pattern by using **arithmetic expressions** instead of literal values

### II-2. cf + asdff — Clear and Save (Empty-Guard)

**Description:** Clears a dependent field and auto-saves it when the source field is empty. Typically used as one half of a guard pattern (paired with enable/disable).

**When Used:** When a source (e.g., a date picker) is emptied, the dependent field must also be cleared and persisted as empty.

**Generic Template:**
```
cf(vo("<source_var>") == "", "<dest_var>");
asdff(vo("<source_var>") == "", "<dest_var>");
```

**Real Example (Rule 28311):**
```
{[0:0]={"cf(vo(\"_eduationstartdate_\")==\"\",\"_eduationenddate_\");
         asdff(vo(\"_eduationstartdate_\") == \"\", \"_eduationenddate_\");"}}
```
When the education start date is cleared, the end date is also cleared and saved.

**Frequency:** Common (especially in repeatable rows with date pairs).

**Variant — Differing Conditions (Rule 48838):** The `cf` and `asdff` may use **different conditions**. The `cf` can have a broader condition than `asdff`:
```
{on("change") and (
  cf((vo("_IsMeetingQue7_")=="Away" or vo("_IsMeetingQue7_")=="AM Introduction"),
     "_LocQue8_","_restID9_","_pleOtheLoca10_");
  asdff(vo("_IsMeetingQue7_")=="Away", "_LocQue8_","_restID9_","_pleOtheLoca10_")
)}
```
Here `cf` fires for both "Away" and "AM Introduction", but `asdff` only fires for "Away". This means for "AM Introduction" the fields are cleared client-side but not saved — likely because another rule handles the save for that case.

**Variant — Specific-Value Conditional Clear and Save (Rule 34711):** Instead of an empty-guard (`==""`) condition, `cf` and `asdff` fire when the source field has a **specific value**. This is used when selecting one option invalidates data in dependent fields:
```
{on("change") and (cf(vo("_isYourMobileL_")=="Yes","_uploadAadhaarFront51_","_uploadAadhaarBackImage26_");asdff(vo("_isYourMobileL_")=="Yes","_uploadAadhaarFront51_","_uploadAadhaarBackImage26_"));}
```
When "Is Your Mobile Linked" is "Yes" (meaning Aadhaar is linked to mobile → use DigiLocker), clear and save the physical upload fields (front/back images). Both `cf` and `asdff` share the same condition. `execute_on_fill: true`, `run_post_condition_fail: true`. This extends II-2 from "clear when empty" to "clear when a specific selection invalidates dependent data."

**Variant — Self-Clear-and-Save Reset Button (Rule 33168):** `cf` and `asdff` target the **same field** that triggers the rule, creating a "reset button" pattern. The field clears and saves itself on change:
```
{on("change") and (cf(vo("_allTheAboveDetailAreCorrect54_")!="", "_allTheAboveDetailAreCorrect54_");asdff(true, "_allTheAboveDetailAreCorrect54_"))}
```
When the field has a value, clear it, then always save. This creates a one-time trigger: the field is set by the user (or another rule), fires its change event, immediately clears itself, and saves the cleared state. The momentary non-empty value can be caught by other rules before the clear fires. `execute_on_fill: true`, `run_post_condition_fail: true`.

**Variant — Unconditional Reset on Change (Rule 52736):** The simplest possible "reset on change" pattern — `cf(true, ...)` and `asdff(true, ...)` both with unconditional `true` conditions inside `on("change")`. Any change to the parent field always clears and saves the child:
```
{on("change") and (cf(true,"_eduationenddate_");asdff(true, "_eduationenddate_"))}
```
When the parent field (education start date) changes, unconditionally clear and save the education end date. No condition checking — the end date always resets when the start date changes. This is the minimal form of II-2: one target field, `true` conditions, `on("change")` wrapper. `execute_on_fill: false`, `run_post_condition_fail: false`.

**Variant — Massive Unconditional Clear+Save (Rule 75193):** `cf` and `asdff` both with `true` condition targeting **40 fields** under `on("change")`. The largest observed cf+asdff combination:
```
{on("change") and (cf(true,"_assetType23_","_pIVISIAssetCodeEnterNAIfNotApplicable28_","_vblvisicoolertype_","_vblvisicoolerimage_","_assetType56_","_pIVISIAssetCode74_","_vISITypeAndSizeForPI46_","_vBLVISICoolerImageUpload63_",...<40 fields total>);asdff(true,"_assetType23_","_pIVISIAssetCodeEnterNAIfNotApplicable28_","_vblvisicoolertype_","_vblvisicoolerimage_","_assetType56_","_pIVISIAssetCode74_","_vISITypeAndSizeForPI46_","_vBLVISICoolerImageUpload63_",...<same 40 fields>))}
```
Any change to the parent field unconditionally clears and saves ALL 40 child fields. The fields are grouped in repeating sets of 4 related fields (asset type, asset code, type/size, image upload) across 10 row positions — this is a cross-row mass reset. Key traits:
- **40 fields** — the largest observed `cf`+`asdff` target count (vs 13 in Rule 17533's `asdff` alone)
- Both `cf` and `asdff` use identical `true` conditions and identical field lists
- Wrapped in `on("change")` to prevent firing on load
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`
- No `rffdd` — none of the 40 fields are dropdowns needing refresh

**Variant — Parent-Inclusive Save (Rule 36988):** The `asdff` saves not only the cleared child fields but also the **parent/source field** that triggered the rule. The `cf` targets only children, while `asdff` includes the parent in its field list:
```
{on("change") and (cf(vo("_isGstinPresent_")=="No","_gstinImageCrop_","_gstin_","_tradename_","_gstinmatch_");
 asdff(vo("_isGstinPresent_")=="No","_isGstinPresent_","_gstinImageCrop_","_gstin_"))}
```
When "Is GSTIN Present" is "No": (1) `cf` clears 4 child fields (image crop, GSTIN number, trade name, match status), (2) `asdff` saves the parent field (`_isGstinPresent_`) PLUS 2 of the cleared children. Key traits:
- **`asdff` field list is a superset** — includes the source field `_isGstinPresent_` which `cf` does not target
- **`asdff` field list is a subset of `cf`** for children — only saves 2 of the 4 cleared fields (possibly because `_tradename_` and `_gstinmatch_` don't need server persistence)
- The parent field's value ("No") is persisted alongside the clear operation
- `execute_on_fill: true`, `run_post_condition_fail: false`

### II-3. cf + remerr — Clear and Remove Error

**Description:** Clears a field and removes any validation error on it, both under the same condition. No auto-save is performed.

**When Used:** When a parent selection changes such that a dependent field is no longer relevant -- clear its value and remove any error that was previously flagged.

**Generic Template:**
```
remerr(<condition>, "<dest_var1>", "<dest_var2>", ...);
cf(<condition>, "<dest_var1>", "<dest_var2>", ...);
```

**Real Example (Rule 28904):**
```
{[0:0]={"remerr(vo(\"_operationalQuest1_\")==\"No\",\"_operationalQuest2_\");
         cf(vo(\"_operationalQuest1_\")==\"No\",\"_operationalQuest2_\");"}}
```
When operational question 1 is answered "No", question 2 is cleared and its error removed.

**Note:** `remerr` typically appears **before** `cf` in the expression.

**Frequency:** Common.

### II-4. cf + rffdd — Clear and Refresh Dropdown

**Description:** Clears a child dropdown field and then refreshes its options. This is the basic cascading dropdown reset pattern.

**When Used:** When a parent dropdown changes, the child dropdown must be cleared of its old value and its options reloaded to reflect the new parent selection.

**Generic Template:**
```
cf(<condition>, "<child_dropdown_var>");
rffdd(<condition>, "<child_dropdown_var>");
```

**Real Example (from Rule 48619, partial):**
```
cf(vo("_employeeiddrob_")!="", "_salesgroupdrob_");
rffdd(vo("_salesofficedrob_")!="", "_salesgroupdrob_");
```
Clears the sales group dropdown and refreshes it. Note: in this example, the conditions differ between `cf` and `rffdd` -- the clear is triggered by a different field than the refresh.

**Variant — Reversed Order: rffdd Before cf (Rule 80701):** The `rffdd` call can appear **before** the `cf` call, reversing the standard clear-then-refresh order. Both use `true` as the condition and target the same multi-field set:
```
{on ("change") and (rffdd (true,"_referencecode_","_rEFERENCECode72_","_depotcode_"); cf(true,"_referencecode_","_rEFERENCECode72_","_depotcode_"))}
```
On change: first refresh the dropdown options for all three fields, then clear all three. This sequence refreshes options before clearing, which may be intentional to ensure the dropdown receives updated options before the stale selection is removed. In the standard order (cf then rffdd), the dropdown is empty when the refresh fires.

Key differences from base II-4:
- **rffdd first, cf second** — reversed from the standard `cf` then `rffdd` order
- **Both use `true` condition** — unconditional, no value checking
- **Multi-field targeting** — 3 fields in both calls (reference code, reference code variant, depot code)
- **`on ("change")` with space** — syntactic variant confirming whitespace between function name and parenthesis is tolerated
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Common (fundamental cascading dropdown pattern).

### II-5. ctfd + rffdd — Multi-Branch Derivation with Dropdown Refresh

**Description:** Multiple `ctfd` calls derive literal values into destination fields based on a dropdown's value (multi-branch), followed by `rffdd` to refresh dropdown data for the destination fields. No `cf` (prior values are overwritten by `ctfd`) and no `asdff` (display-only or persistence handled elsewhere).

**When Used:** When a parent dropdown determines fixed values for multiple child fields (code, display name, description), and those child fields also need their dropdown options refreshed. Common in master-data mapping (e.g., plant type → storage location code + name + description).

**Generic Template:**
```
on("change") and (
  ctfd(vo("<src>") == "<val_A>", "<literal_A1>", "<dest1>");
  ctfd(vo("<src>") == "<val_A>", "<literal_A2>", "<dest2>");
  ctfd(vo("<src>") == "<val_A>", "<literal_A3>", "<dest3>");
  ctfd(vo("<src>") == "<val_B>", "<literal_B1>", "<dest1>");
  ctfd(vo("<src>") == "<val_B>", "<literal_B2>", "<dest2>");
  ctfd(vo("<src>") == "<val_B>", "<literal_B3>", "<dest3>");
  rffdd(true, "<dest1>", "<dest2>", "<dest3>")
)
```

**Real Example (Rule 83675):**
```
{on ("change")and (ctfd(vo("_natureofplant_") == "Sub Contracting Location","ST01 - Subcontract SL","_storagelocation_");
 ctfd(vo("_natureofplant_") == "Sub Contracting Location","ST01","_sTORAGELOCATIONCODE28_");
 ctfd(vo("_natureofplant_") == "Sub Contracting Location","Subcontract SL","_storagelocationdesc_");
 ctfd(vo("_natureofplant_") == "Own Manufacturing Plant","FG01 - FG stores","_storagelocation_");
 ctfd(vo("_natureofplant_") == "Own Manufacturing Plant","FG01","_sTORAGELOCATIONCODE28_");
 ctfd(vo("_natureofplant_") == "Own Manufacturing Plant","FG stores","_storagelocationdesc_");
 ctfd(vo("_natureofplant_") == "DEPOT CODE/RDC","MA01 - Main store-Depot","_storagelocation_");
 ctfd(vo("_natureofplant_") == "DEPOT CODE/RDC","MA01","_sTORAGELOCATIONCODE28_");
 ctfd(vo("_natureofplant_") == "DEPOT CODE/RDC","Main store-Depot","_storagelocationdesc_");
 rffdd(true,"_storagelocation_","_sTORAGELOCATIONCODE28_","_storagelocationdesc_"))}
```
3 plant types × 3 destination fields = 9 `ctfd` calls. Each plant type maps to a composite display value (`_storagelocation_`), a code (`_sTORAGELOCATIONCODE28_`), and a description (`_storagelocationdesc_`). The single `rffdd(true, ...)` refreshes all three fields unconditionally after derivation.

**Key Observations:**
- **Multi-destination per branch** — each source value maps to 3 fields (display, code, description), unlike CL-2 which maps one source value to one destination
- **No `cf`** — `ctfd` overwrites prior values directly; no explicit clearing needed since every branch writes to every destination
- **No `asdff`** — display-only derivation; persistence may be handled elsewhere
- **`rffdd(true, ...)` at the end** — unconditional refresh of all destination fields, not just dropdowns. The `true` condition ensures refresh fires regardless of which branch matched
- **`on("change")` wrapper** — fires only on user interaction
- This is a **ctfd-matrix + rffdd** pattern, combining [CL-7](#cl-7-multi-branch-multi-destination-ctfd-matrix) with dropdown refresh
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Observed in plant/location/master-data mapping scenarios.

---

## Three-Function Combinations

### III-1. cf + asdff + rffdd — Cascade-Clear Trio

**Description:** Clears child dropdown(s), saves the cleared state, and refreshes the dropdown options. This is the standard parent-dropdown-changed pattern for cascading EDV dropdowns.

**When Used:** A parent dropdown changes, so child dropdowns must be: (1) cleared of stale values, (2) saved as empty, and (3) refreshed with new options based on the new parent value.

**Generic Template:**
```
cf(<condition>, "<child1>", "<child2>", ...);
asdff(true, "<child1>", "<child2>", ...);
rffdd(true, "<child1>", "<child2>", ...);
```

**Real Example (from Rule 48618, partial):**
```
on("change") and (
  cf(vo("_customertypedrob_")=="P016-Retailer", "_doyouhavegstregistereddrob_");
  cf(vo("_customertypedrob_")=="P011-Non-Trade Customer", "_doyouhavegstregistereddrob_");
  asdff(true, "_doyouhavegstregistereddrob_");
  rffdd(true, "_doyouhavegstregistereddrob_")
)
```
When the customer type is Retailer or Non-Trade, the GST registration dropdown is cleared. Regardless of the branch, the field is saved and refreshed.

**Variant — All-True Unconditional Cascade (Rule 115707):** All three functions use `true` as the condition, meaning the cascade fires unconditionally on every change:
```
{on("change") and (cf(true,"_dMSNumber69_","_typeOfBusiness52_");asdff(true,"_dMSNumber69_","_typeOfBusiness52_");rffdd(true,"_dMSNumber69_","_typeOfBusiness52_"))}
```
ANY change to the parent field always clears, saves, and refreshes both child dropdowns. No condition checking — the parent-child relationship is unconditional. This simplified variant is used when the children should **always** reset regardless of what the parent's new value is.

**Variant — Asymmetric Field Targeting (Rule 50391):** `cf` can target **more fields** than `rffdd` when only some of the cleared fields are dropdowns. Non-dropdown fields are cleared and saved but do not need a dropdown refresh:
```
{on("change") and (cf(vo("_taxCategory_")!="194R GIFT","_tdsPaidFlag_","_tDSGiftAmountWipro_","_customerRefNoonlyForNEFT57_");asdff(vo("_taxCategory_")!="194R GIFT","_tdsPaidFlag_","_tDSGiftAmountWipro_","_customerRefNoonlyForNEFT57_");rffdd(vo("_taxCategory_")!="194R GIFT","_tdsPaidFlag_"))}
```
`cf` and `asdff` target 3 fields (the dropdown plus 2 non-dropdown fields), while `rffdd` targets only the 1 dropdown field (`_tdsPaidFlag_`). The non-dropdown fields (`_tDSGiftAmountWipro_`, `_customerRefNoonlyForNEFT57_`) are cleared and saved but not refreshed. Also notable: all three functions share the **same condition** rather than using `true` for `asdff`/`rffdd`.

**Variant — Cascade-Clear Trio + dis/en Inside on("change") (Rule 83677):** The standard cascade-clear trio can be combined with `dis`/`en` (enable/disable gating) **all inside** a single `on("change")` block. Unlike [C-4](#c-4-full-four-function--disen--branching-derivation-with-dropdown-cascade-and-enabledisable) where `dis`/`en` are placed outside the event wrapper (always evaluated), here they are event-scoped:
```
{on("change") and (cf(true,"_subchannel3_");rffdd(true,"_subchannel3_");asdff(true,"_subchannel3_");dis(vo("_channel3_")== "","_subchannel3_");en(vo("_channel3_")!= "","_subchannel3_"))}
```
On change of the parent channel field: unconditionally clear, refresh, and save the subchannel dropdown, then disable it when the channel is empty and enable it when the channel has a value. All five function calls are inside the `on("change")` block.

Key differences from C-4:
- **`dis`/`en` inside `on("change")`** — in C-4, `dis`/`en` are outside the event wrapper so they evaluate on every render. Here they only fire on change events, which means the enable/disable state is NOT enforced on form load. This relies on the initial disabled state being set by other means (e.g., form config or execute_on_fill)
- **No `ctfd`** — unlike C-4 which derives a value for some branches, this rule only clears/refreshes (no fixed value derivation). The cf+rffdd+asdff trio handles the child completely via clearing and refresh
- **Single target field** — all functions target the same `_subchannel3_` field
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`

**Frequency:** Very common.

### III-2. cf + remerr + asdff — Clear, Remove Error, and Save

**Description:** Clears dependent fields, removes their validation errors, and auto-saves them. Combines the cleanup of II-3 (cf + remerr) with persistence of II-2 (cf + asdff). Multiple branches can target different field groups based on the source value.

**When Used:** When a categorization field (e.g., address proof type) changes and previously relevant fields must be: (1) cleared of stale values, (2) freed of validation errors, and (3) persisted as empty. Each branch clears the fields that are NOT relevant to the current selection.

**Generic Template:**
```
on("change") and (
  cf(<condition_not_A>, "<fields_for_A>");
  remerr(<condition_not_A>, "<fields_for_A>");
  asdff(<condition_not_A>, "<fields_for_A>");
  cf(<condition_not_B>, "<fields_for_B>");
  remerr(<condition_not_B>, "<fields_for_B>");
  asdff(<condition_not_B>, "<fields_for_B>")
)
```

**Real Example (Rule 33143):**
```
{on("change")and(
  cf(vo("_2OperAddressproof_")!="Aadhaar","_2OperAadhaarImg_","_4Adhaarlinktomobile_");
  remerr(vo("_2OperAddressproof_")!="Aadhaar","_2OperAadhaarImg_");
  cf(vo("_2OperAddressproof_")!="Driving Licence","_2OperDLimg_");
  remerr(vo("_2OperAddressproof_")!="Driving Licence","_2OperDLimg_");
  asdff(vo("_2OperAddressproof_")!="Aadhaar", "_2OperAadhaarImg_","_4Adhaarlinktomobile_");
  asdff(vo("_2OperAddressproof_")!="Driving Licence", "_2OperDLimg_")
)}
```
When address proof is not Aadhaar: clear Aadhaar image + mobile link, remove error on Aadhaar image, save both. When not Driving Licence: clear DL image, remove error, save. Each proof type has its own cf+remerr+asdff group. `execute_on_fill: true`, `run_post_condition_fail: true`.

**Key Observations:**
- Groups of (cf, remerr, asdff) per condition branch, each targeting different field sets
- `remerr` may target **fewer fields** than `cf`/`asdff` (e.g., only the image field, not the mobile link)
- The `!=` conditions mean every non-matching proof type gets cleared — this is the "clear irrelevant" pattern
- Wrapped in `on("change")` to avoid firing on load
- No empty `source_ids` — the rule's source field is implicit from `form_fill_metadata_id`

**Variant — Self-Save-First with Multi-Branch Clearing (Rules 36968, 34699):** The rule begins with an **unconditional `asdff(true, source_field)`** to persist the source field's own value before branching into conditional clear+save+remerr groups for different child field sets. This "self-save-first" pattern ensures the source selection is persisted independently of the branch logic:
```
{on("change") and (asdff(true,"_doYouHaveCheque97_");
 cf(vo("_doYouHaveCheque97_")!="Yes","_chequeUpload72_","_IFSCNumber_","_ANumber_");
 asdff(vo("_doYouHaveCheque97_")!="Yes","_chequeUpload72_","_IFSCNumber_","_ANumber_");
 remerr(vo("_doYouHaveCheque97_")!="Yes","_chequeUpload72_","_IFSCNumber_","_ANumber_");
 cf(vo("_doYouHaveCheque97_")!="No","_iFSC77_","_accountNumber67_");
 asdff(vo("_doYouHaveCheque97_")!="No","_iFSC77_","_accountNumber67_");
 remerr(vo("_doYouHaveCheque97_")!="No","_iFSC77_","_accountNumber67_"));}
```
Self-save first, then two branches: when NOT "Yes" (i.e., "No"), clear+save+remerr cheque/IFSC/account fields. When NOT "No" (i.e., "Yes"), clear+save+remerr manual IFSC/account fields. Each branch clears the alternative path's fields.

Rule 34699 scales this to **three branches** (PAN, Aadhaar, GST Certificate), each with cf+asdff+remerr targeting different document-specific field groups. Notable for its asymmetric `remerr` targeting — `remerr` may target **fewer fields** than `cf`/`asdff` within the same branch:
```
{on("change") and (asdff(true,"_PanOrAadhaar_");
 cf(vo("_PanOrAadhaar_")=="PAN","_uploadAadhaarFront51_","_uploadAadhaarBackImage26_","_gstCertificate_");
 cf(vo("_PanOrAadhaar_")=="Aadhaar","_panUpload_","_GSTNumber_","_GSTtradeName_",...<16 GST+PAN fields>);
 cf(vo("_PanOrAadhaar_")=="GST Certificate","_uploadAadhaarFront51_","_uploadAadhaarBackImage26_","_panUpload_");
 asdff(vo("_PanOrAadhaar_")=="PAN","_uploadAadhaarFront51_","_uploadAadhaarBackImage26_","_gstCertificate_");
 asdff(vo("_PanOrAadhaar_")=="Aadhaar","_panUpload_","_GSTNumber_","_gstCertificate_");
 asdff(vo("_PanOrAadhaar_")=="GST Certificate","_uploadAadhaarFront51_","_uploadAadhaarBackImage26_","_panUpload_");
 remerr(vo("_PanOrAadhaar_")!="PAN","_panUpload_");
 remerr(vo("_PanOrAadhaar_")!="GST Certificate","_gstCertificate_");
 remerr(vo("_PanOrAadhaar_")!="Aadhaar","_uploadAadhaarFront51_","_uploadAadhaarBackImage26_"));}
```
Key traits of the self-save-first variant:
- **`asdff(true, source)` first** — persists the source field before any branch logic fires. This guarantees the selection is saved even if branch processing fails or is interrupted
- **`==` conditions for cf/asdff** — uses equality checks (clear when IS this type), unlike the base pattern's `!=` conditions (clear when NOT this type). Rule 34699 uses `==` for cf/asdff but `!=` for remerr — a mixed approach
- **Three-branch scaling** — each document type has its own cf+asdff+remerr group, with the "Aadhaar" branch clearing the most fields (16 GST-related fields)
- **`run_post_condition_fail: true`** on Rule 34699 — ensures the rule completes fully even if some conditions fail
- `execute_on_fill: true` (Rule 34699), `execute_on_fill: false` (Rule 36968)

**Frequency:** Observed in document/proof type selection forms.

### III-3. ctfd + cf + asdff — Derive Some, Clear Others, Save All

**Description:** Based on branching conditions, some destination fields get a derived/literal value while others get cleared. All affected fields are then saved.

**When Used:** When a source field's value determines which of several dependent fields should have a value vs be empty.

**Generic Template:**
```
ctfd(<condition_A>, "<value>", "<dest_var>");
cf(<condition_B>, "<dest_var>");
asdff(true, "<dest_var>");
```

**Real Example (from Rule 48618, partial):**
```
ctfd(vo("_customertypedrob_")=="P001-Dealer", "Yes", "_doyouhavegstregistereddrob_");
cf(vo("_customertypedrob_")=="P016-Retailer", "_doyouhavegstregistereddrob_");
cf(vo("_customertypedrob_")=="P011-Non-Trade Customer", "_doyouhavegstregistereddrob_");
asdff(true, "_doyouhavegstregistereddrob_");
```
For Dealer, set GST registered to "Yes". For Retailer and Non-Trade, clear it. Always save.

**Variant — Email Routing with Compound AND Conditions (Rules 51577, 51578, 51579, 51573, 51572, 51571):** `ctfd` copies a **field value** (via `vo()`) from a source email field to a destination "copy" email field under one condition, while `cf` clears that same destination under the opposite condition. Always saved with `asdff(true, ...)`. Conditions can be compound AND checks involving multiple source fields (e.g., equipment type AND agreement type):
```
{on("change") and (cf(vo("_equipmenttype_")=="Visi","_clusterBDMEmailCopy40_");cf(vo("_equipmenttype_")=="PMX" and vo("_pleaseselectpmxagreement_")=="Regular AFH","_clusterBDMEmailCopy40_");ctfd(vo("_equipmenttype_")=="PMX" and vo("_pleaseselectpmxagreement_")=="Central Agreement",vo("_clusterBDMEmail76_"),"_clusterBDMEmailCopy40_");asdff(true,"_clusterBDMEmailCopy40_"))}
```
Three branches: Visi → clear copy field. PMX + Regular AFH → clear copy field. PMX + Central Agreement → copy from source email field. Always save.

Simpler binary variant (Rules 51573, 51572):
```
{on("change") and (ctfd(vo("_ischequewaiver_")=="No",vo("_financeEmail16_"),"_financeEmailCopy55_");cf(vo("_ischequewaiver_")=="Yes","_financeEmailCopy55_");asdff(true,"_financeEmailCopy55_"))}
```
When cheque waiver is "No": copy finance email → copy field. When "Yes": clear copy field. Always save.

Key traits:
- `ctfd` uses `vo("<source_email>")` as the source value — **field-value copy**, not a literal
- Multiple rules in the same form each handle a **different email routing** (cluster BDM, HOS, BDM, finance, unit MEC, head MEM) with the same condition structure
- The **cf/ctfd mapping can be inverted** between rules: what copies in one rule clears in another (e.g., Rule 51571 copies on "Yes" and clears on "No", opposite to 51573/51572)
- Compound `and` conditions check **two different source fields** (equipment type + agreement type)
- `execute_on_fill: true`, `execute_on_read: false`

**Variant — Compound OR+AND Multi-Field Branching (Rule 80725):** `cf(true, ...)` unconditionally clears the destination first, then multiple `ctfd` calls with **compound OR+AND conditions across two different source fields** derive different literal values. The conditions combine an **OR-group** on the first source field with **equality/OR checks** on the second source field, implementing a two-dimensional decision matrix:
```
{on("change") and (cf(true,"_a120_");
 ctfd((vo("_companycode_") == "MIL" or vo("_companycode_") == "MIF" or vo("_companycode_") == "MPKF")
   and (vo("_natureofplant_") == "Own Manufacturing Plant" or vo("_natureofplant_") == "Sub Contracting Location"),
   "Yes", "_a120_");
 ctfd((vo("_companycode_") == "MIL" or vo("_companycode_") == "MIF" or vo("_companycode_") == "MPKF")
   and vo("_natureofplant_") == "DEPOT CODE/RDC",
   "No", "_a120_");
 asdff(true,"_a120_"))}
```
Two-dimensional branching: company code must be in {MIL, MIF, MPKF} AND nature of plant determines the output. If plant is Manufacturing/Sub-Contracting → "Yes". If plant is DEPOT CODE/RDC → "No". For any other company code or plant combination, the field remains cleared (from the initial `cf(true, ...)`). Key traits:
- **`cf(true, dest)` as pre-clear** — unconditionally clears the destination before conditional derivation, ensuring a clean slate. If no `ctfd` condition matches, the field stays empty
- **Two-dimensional condition** — `(field1 == A or field1 == B or field1 == C) and (field2 == D or field2 == E)` creates a matrix where both dimensions must match
- **Shared OR-group prefix** — both `ctfd` calls share the same OR-group for company code; they differ only on the nature-of-plant check. This is a common pattern when the first dimension acts as a gate and the second dimension determines the output value
- **Implicit "else" via pre-clear** — company codes NOT in the OR-group leave the field cleared, acting as a default/fallback without an explicit `cf` or `ctfd` for the else case
- Extends [CL-2](#cl-2-multi-branch-on-dropdown-value) from single-field conditions to multi-field compound conditions
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`

**Frequency:** Common.

---

## Four-Function Combination

### IV-1. ctfd + cf + asdff + rffdd — Full Branching Derivation with Dropdown Cascade

**Description:** The complete pattern: for some branch conditions, derive a value; for other branch conditions, clear the field; always save the field; always refresh dropdown options. This handles all possible states of a dependent dropdown that may be auto-populated, cleared, or refreshed depending on the parent's value.

**When Used:** Complex branching on a parent dropdown where:
- Some parent values cause the child to be set to a fixed value (and disabled)
- Other parent values cause the child to be cleared and refreshed (user must select)

**Generic Template:**
```
on("change") and (
  ctfd(<condition_A>, "<literal>", "<dest_var>");
  ctfd(<condition_B>, "<literal>", "<dest_var>");
  cf(<condition_C>, "<dest_var>");
  rffdd(<condition_C>, "<dest_var>");
  asdff(true, "<dest_var>");
  rffdd(true, "<dest_var>")
);
dis(<condition_A>, "<dest_var>");
dis(<condition_B>, "<dest_var>");
en(<condition_C>, "<dest_var>")
```

**Real Example (Rule 48617):**
```
{on("change") and (
  rffdd(vo("_customertypedrob_")=="P011-Non-Trade Customer", "_distributionchanneldrob_");
  ctfd(vo("_customertypedrob_")=="P001-Dealer", "TR - Trade", "_distributionchanneldrob_");
  ctfd(vo("_customertypedrob_")=="P016-Retailer", "TR - Trade", "_distributionchanneldrob_");
  cf(vo("_customertypedrob_")=="P011-Non-Trade Customer", "_distributionchanneldrob_");
  asdff(true, "_distributionchanneldrob_");
  rffdd(true, "_distributionchanneldrob_")
);
dis(vo("_customertypedrob_")=="P001-Dealer", "_distributionchanneldrob_");
dis(vo("_customertypedrob_")=="P016-Retailer", "_distributionchanneldrob_");
en(vo("_customertypedrob_")=="P011-Non-Trade Customer", "_distributionchanneldrob_")}
```
For Dealer/Retailer: derive "TR - Trade" and disable the field. For Non-Trade Customer: clear, refresh options, and enable the field. Always save and refresh.

**Variant — Multi-Destination Split Targeting (Rule 51476):** The four functions can target **different destination fields** rather than all converging on the same one. `ctfd`+`asdff` manage one field while `cf`+`rffdd` reset a separate dropdown. This occurs when a single parent field's value determines both a derived value for one child and a cascade reset for a different child:
```
{on("change") and (ctfd(vo("_equipmenttype_")=="Visi","Regular","_regCentralTypeMap12_");ctfd(vo("_equipmenttype_")=="PMX","","_regCentralTypeMap12_");asdff(true,"_regCentralTypeMap12_");cf(vo("_equipmenttype_")=="PMX","_pleaseselectpmxagreement_");rffdd(vo("_equipmenttype_")=="PMX","_pleaseselectpmxagreement_"))}
```
When equipment type is "Visi": derive "Regular" into `_regCentralTypeMap12_`. When "PMX": derive "" (empty) into `_regCentralTypeMap12_` AND clear+refresh `_pleaseselectpmxagreement_`. Always save `_regCentralTypeMap12_`. Key differences from base IV-1:
- `ctfd`+`asdff` target `_regCentralTypeMap12_` while `cf`+`rffdd` target `_pleaseselectpmxagreement_` — the four functions split across two destinations
- Uses `ctfd("", ...)` to clear one field (see [AP-3](#ap-3-ctfd-with-empty-string-as-clear)) while using `cf` to clear the other — showing both clearing approaches coexisting in the same rule
- `cf`+`rffdd` are condition-gated (`=="PMX"`) rather than unconditional (`true`) — the cascade only fires for one branch
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Observed in complex dropdown branching scenarios.

---

## Composite Patterns

### C-1. cf + asdff + dis/en — Empty-Guard with Enable/Disable

**Description:** When the source field is empty, the dependent field is cleared, saved, and disabled. When the source has a value, the dependent is enabled. This is a "guard" pattern ensuring users cannot interact with a field until its prerequisite is filled.

**When Used:** Date pairs (start/end), sequential field dependencies where the second field only makes sense after the first is filled.

**Generic Template:**
```
dis(vo("<source>") == "", "<dest>");
en(vo("<source>") != "", "<dest>");
cf(vo("<source>") == "", "<dest>");
asdff(vo("<source>") == "", "<dest>");
```

**Real Example (Rule 28311):**
```
{[0:0]={"dis(vo(\"_eduationstartdate_\")==\"\",\"_eduationenddate_\");
         en(vo(\"_eduationstartdate_\")!=\"\",\"_eduationenddate_\");
         cf(vo(\"_eduationstartdate_\")==\"\",\"_eduationenddate_\");
         asdff(vo(\"_eduationstartdate_\") == \"\", \"_eduationenddate_\");"}}
```
Education end date is disabled+cleared when start date is empty; enabled when start date has a value. This pattern appeared twice in this batch (Rules 28311, 28310) with date fields.

**Variant — Non-Array Context (Rules 52747, 52771, 52783, 52788, 52791):** The same gate pattern appears outside array context (no `[0:0]` wrapper), confirming it applies to both repeatable-row and standalone field pairs:
```
{dis(vo("_employeeJoingDate_")=="","_employeeLeavingDate_");en(vo("_employeeJoingDate_")!="","_employeeLeavingDate_");cf(vo("_employeeJoingDate_")=="","_employeeLeavingDate_");asdff(vo("_employeeJoingDate_") == "", "_employeeLeavingDate_");}
```
Employee leaving date is disabled+cleared when joining date is empty; enabled when joining date has a value. This generalizes C-1 beyond education date pairs to any sequential date dependency (joining/leaving, start/end). All 5 rules use `execute_on_fill: false`, `run_post_condition_fail: false`. These gate rules are always deployed as **matched pairs** with an [on("change") unconditional reset rule (II-2)](#ii-2-cf--asdff--clear-and-save-empty-guard) on the same source field — see [S-13](#s-13-paired-gate--reset-rules).

**Frequency:** Very common (date pairs in both repeatable rows and standalone contexts).

### C-2. cf + mvi/minvi — Branching Visibility with Clear

**Description:** Based on a dropdown/radio value, different groups of fields are shown or hidden. Fields being hidden are also cleared to prevent stale data.

**When Used:** Conditional form sections where selecting one option reveals one set of fields and hides another. The hidden fields must be cleared.

**Generic Template:**
```
minvi(<empty_condition>, <all_fields>)
or (mvi(<condition_A>, <group_A_fields>) and cf(true, <group_B_fields>) and minvi(true, <group_B_fields>))
or (mvi(<condition_B>, <group_B_fields>) and minvi(true, <group_A_fields>))
```

**Real Example (Rule 29074):**
```
{[0:0]={"minvi(vo(\"_aadhques_\")==\"\",\"_aadhfront_\",\"_aadhback_\",\"_digilockerAadharAuthorize12_\")
 or (mvi(vo(\"_aadhques_\")==\"Yes\",\"_digilockerAadharAuthorize12_\")
     and cf(true,\"_aadhfront_\",\"_aadhback_\")
     and minvi(true,\"_aadhfront_\",\"_aadhback_\"))
 or (mvi(vo(\"_aadhques_\")==\"No\",\"_aadhfront_\",\"_aadhback_\")
     and minvi(true,\"_digilockerAadharAuthorize12_\"))"}}
```
When empty: hide all. When "Yes": show digilocker, clear+hide physical upload fields. When "No": show physical uploads, hide digilocker.

**Note:** `cf(true, ...)` is used with a literal `true` condition inside an `or` branch -- the branching is handled by the outer `or` structure, so the `cf` always fires within its branch.

**Variant — Non-Array Context (Rule 32180):** The same Aadhaar visibility pattern appears outside array context (no `[0:0]` wrapper), using the identical `or`-chained branch structure:
```
{minvi(vo("_aadhques_")=="","_aadhfront_","_aadhback_","_digilockerAadharAuthorize12_")
 or (mvi(vo("_aadhques_")=="Yes","_digilockerAadharAuthorize12_")
     and cf(true,"_aadhfront_","_aadhback_")
     and minvi(true,"_aadhfront_","_aadhback_"))
 or (mvi(vo("_aadhques_")=="No","_aadhfront_","_aadhback_")
     and minvi(true,"_digilockerAadharAuthorize12_"))}
```
This confirms that C-2 is not specific to array context -- it appears identically in non-array rules.

**Variant — Mega Multi-Proof-Type Branching with Nested Sub-Conditions (Rules 51081, 51092):** C-2 scales to handle 5–7+ proof/document types in a single rule, each with its own `mvi`/`minvi` pair and `cf` cleanup. Additionally, some proof types have **nested sub-conditions** that further refine visibility within the type (e.g., Aadhaar Card → "Is linked to mobile?" → Yes/No sub-branches):
```
mvi(vo("_identityproof_")=="Pan Card","_IDpanupload_","_IDpan_","_IDpanholdername_");
minvi(vo("_identityproof_")!="Pan Card","_IDpanupload_","_IDpan_","_IDpanholdername_");
mvi(vo("_identityproof_")=="Driving License","_IDdl_","_IDdlnumber_","_IDname_","_IDdob_","_IDvalidtill_");
minvi(vo("_identityproof_")!="Driving License","_IDdl_","_IDdlnumber_","_IDname_","_IDdob_","_IDvalidtill_");
... (Passport, Ration Card, Aadhaar Card branches)
mvi(vo("_identityproof_")=="Aadhaar Card" and vo("_IDisAdhaarLinkedToMobile228_")=="Yes",
    "_IDdigilockerAadharAuthorize10_");
minvi(vo("_identityproof_")=="Aadhaar Card" and vo("_IDisAdhaarLinkedToMobile228_")!="Yes",
    "_IDdigilockerAadharAuthorize10_");
mvi(vo("_identityproof_")=="Aadhaar Card" and vo("_IDisAdhaarLinkedToMobile228_")=="No",
    "_IDaadhaarFrontImage21_","_IDaadhaarBackImage17_");
minvi(vo("_identityproof_")=="Aadhaar Card" and vo("_IDisAdhaarLinkedToMobile228_")!="No",
    "_IDaadhaarFrontImage21_","_IDaadhaarBackImage17_");
cf(vo("_identityproof_")!="Aadhaar Card","_IDisAdhaarLinkedToMobile228_");
cf(vo("_identityproof_")!="Pan Card","_IDpanupload_","_IDpan_","_IDpanholdername_");
cf(vo("_identityproof_")!="Driving License","_IDdl_","_IDdlnumber_","_IDname_","_IDdob_","_IDvalidtill_");
... (cf for each proof type clearing its fields)
```
Key traits:
- **5–7 proof type branches** in a single rule, each with its own mvi/minvi pair and cf cleanup
- **Nested sub-conditions** for Aadhaar: compound `and` conditions check both proof type AND a sub-field (`_IDisAdhaarLinkedToMobile228_`) to control sub-section visibility (digilocker vs physical upload)
- **One cf per proof type** clears ALL that type's fields when not selected — separate cf calls per type rather than one large cf
- Can include a `ctfd` at the end for cross-section derivation (Rule 51081 derives a default value from identity proof context into an address proof field)
- Very large field counts: 15+ fields for Aadhaar, 5+ for Driving License, etc.
- Flat semicolon-separated structure (no `or` branching)
- No `mm`/`mnm` — visibility-only management in these rules
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Observed in KYC/identity verification forms with multiple document type options.

**Frequency:** Observed in conditional section visibility (both array and non-array contexts).

### C-3. cf + remerr — Multi-Branch Clear with Error Removal

**Description:** Multiple branches based on a dropdown value, each clearing different sets of fields and removing their errors. Different conditions clear different field groups.

**When Used:** When a categorization field changes and previously-filled dependent fields for other categories need to be cleared along with their validation errors.

**Generic Template:**
```
remerr(<condition_A>, <fields_for_A>);
cf(<condition_A>, <fields_for_A>);
remerr(<condition_B>, <fields_for_B>);
cf(<condition_B>, <fields_for_B>);
```

**Real Example (Rule 28840):**
```
{[0:0]={"remerr(vo(\"_isFssaiPresent_\")==\"Applied\",\"_fssai_\",\"_comp_\",\"_lcatname_\");
         cf(vo(\"_isFssaiPresent_\")==\"Applied\",\"_fssai_\",\"_comp_\",\"_lcatname_\");
         remerr(vo(\"_isFssaiPresent_\")==\"Certificate\",\"_lcatid_\");
         cf(vo(\"Certificate\")==\"Applied\",\"_lcatid_\");"}}
```
When FSSAI status is "Applied", clear the certificate-related fields. When "Certificate", clear the application-related field. Each branch pairs `remerr` before `cf`.

**Note:** This rule contains a likely bug -- `cf(vo("Certificate")=="Applied",...)` should probably be `cf(vo("_isFssaiPresent_")=="Certificate",...)`.

**Frequency:** Observed in multi-option categorization fields.

### C-4. Full Four-Function + dis/en — Branching Derivation with Dropdown Cascade and Enable/Disable

**Description:** The most complete composite pattern. Combines all four core functions with `dis`/`en`. Under `on("change")`, some branches derive a literal value and disable the field; other branches clear, refresh, and enable the field. Save always runs.

**When Used:** Parent dropdown determines whether a child dropdown is auto-populated (fixed value, disabled) or user-selectable (cleared, refreshed, enabled).

**Generic Template:**
```
on("change") and (
  ctfd(<condition_fixed_value>, "<literal>", "<dest>");
  cf(<condition_user_selects>, "<dest>");
  asdff(true, "<dest>");
  rffdd(true, "<dest>")
);
dis(<condition_fixed_value>, "<dest>");
en(<condition_user_selects>, "<dest>")
```

**Real Examples:** Rules 48617 and 48618 both follow this pattern. See [IV-1](#iv-1-ctfd--cf--asdff--rffdd--full-branching-derivation-with-dropdown-cascade) for full examples.

**Variant — Multi-Way Conditional Editability Matrix (Rule 51493):** Extends C-4 from binary branching (fixed vs user-selectable) to **N-way branching** where each source value maps to a different pre-filled value AND editability state. Uses multiple `ctfd` calls (lookup-table style) paired with matched `dis`/`en` calls per value, plus unconditional `asdff`:
```
{on("change") and (ctfd(vo("_equipmentsize_")=="100","4","_emptyincases_");
 ctfd(vo("_equipmentsize_")=="270","10","_emptyincases_");
 ctfd(vo("_equipmentsize_")=="350","","_emptyincases_");
 ctfd(vo("_equipmentsize_")=="450","","_emptyincases_");
 ctfd(vo("_equipmentsize_")=="600","","_emptyincases_");
 ctfd(vo("_equipmentsize_")=="1000","","_emptyincases_");
 dis(vo("_equipmentsize_")=="100","_emptyincases_");
 dis(vo("_equipmentsize_")=="270","_emptyincases_");
 en(vo("_equipmentsize_")=="350","_emptyincases_");
 en(vo("_equipmentsize_")=="450","_emptyincases_");
 en(vo("_equipmentsize_")=="600","_emptyincases_");
 en(vo("_equipmentsize_")=="1000","_emptyincases_");
 asdff(true,"_emptyincases_"))}
```
6 equipment sizes map to: sizes 100/270 → pre-fill with "4"/"10" and disable (known values), sizes 350/450/600/1000 → clear via `ctfd("")` and enable (user must enter). All wrapped in `on("change")` with unconditional `asdff`.

Key differences from base C-4:
- **N-way branching** (6 values) instead of binary — each source value gets its own `ctfd` + `dis`/`en`
- Uses **`ctfd("", ...)`** for clearing instead of `cf` (see [AP-3](#ap-3-ctfd-with-empty-string-as-clear)) — maintaining consistency within the `ctfd` matrix
- No `rffdd` — the destination is a text field, not a dropdown
- **All within `on("change")`** — unlike base C-4 where `dis`/`en` are outside the event wrapper
- `execute_on_fill: true`, `execute_on_read: false`

**Frequency:** Common in complex dropdown cascading scenarios.

### C-5. cf + rffdd + en — Clear, Refresh, and Enable

**Description:** Clears child dropdown(s), refreshes their options, and enables them. Wrapped in `on("change")`. Different conditions may govern different targets.

**When Used:** When a parent field changes and multiple child dropdowns need to be reset, but with different refresh conditions per child (e.g., one child depends on the parent, another depends on a sibling).

**Generic Template:**
```
on("change") and (
  cf(<condition>, "<child1>", "<child2>");
  rffdd(<condition_for_child1>, "<child1>");
  rffdd(true, "<child2>");
  en(true, "<child2>")
)
```

**Real Example (Rule 48619):**
```
{on("change") and (
  cf(vo("_employeeiddrob_")!="", "_salesgroupdrob_", "_deliveryplantdrob_");
  rffdd(vo("_salesofficedrob_")!="", "_salesgroupdrob_");
  rffdd(true, "_deliveryplantdrob_");
  en(true, "_deliveryplantdrob_")
)}
```
Clears both sales group and delivery plant. Refreshes sales group only when sales office has a value. Always refreshes and enables delivery plant.

**Note:** The `cf` condition references a different field (`_employeeiddrob_`) than the `rffdd` condition (`_salesofficedrob_`), showing that clear and refresh can be governed by different source fields.

**Frequency:** Observed in multi-level dropdown cascades.

### C-6. ctfd + adderr/remerr — Validation with Status Derivation

**Description:** `ctfd` is used to set a validation status field ("Valid"/"Invalid") while `adderr`/`remerr` manage error messages on the validated field. The validation comparison (e.g., new > old) determines which branch fires. This pattern frequently uses `ctfd` nested inside `adderr` as its condition parameter (see [CL-5](#cl-5-ctfd-nested-as-adderr-condition)).

**When Used:** Business validation rules where a numeric or categorical comparison determines validity, and the result must be both (1) written as a status to a field and (2) surfaced as a user-visible error.

**Generic Template:**
```
(adderr(ctfd(<comparison>, "Invalid", "<status_dest>"), "<error_msg>", "<validated_field>", "<status_dest>")
 or (ctfd(true, "Valid", "<status_dest>") and remerr(true, "<validated_field>", "<status_dest>")))
```

**Real Example (Rule 27652, partial — Dineout Restaurant, downsell=No, Percentage base):**
```
(vo("_basecommold_")=="Percentage" and vo("_basecommnew_")=="Percentage" and vo("_billtaxold_")==vo("_billtaxnew_"))
and (
  (remerr(+vo("_oldpercomm_") < +vo("_newpercomm_"), "_newpercomm_")
   and ctfd(true, "Valid", "_commissionstatus_"))
  or
  (adderr(true, "New Commission should be greater than old Commission", "_newpercomm_")
   and ctfd(true, "Invalid", "_commissionstatus_"))
)
```
When old commission types match: if old < new, remove errors and set "Valid"; otherwise add error and set "Invalid".

**Note:** In Rule 27652, both `remerr` and `ctfd` use the numeric comparison as the condition for `remerr`, and `true` for `ctfd`/`adderr` within each `or` branch — the branching is handled by `or` short-circuit semantics. In Rules 27658/27659, the ctfd is nested directly inside adderr.

**Variant — With cntns() Pre-Validation Guards (Rules 6067, 6065, 6021):** The validation pattern can be preceded by guard conditions that use `cntns()` to check for invalid data markers (e.g., a "+" prefix in numeric fields). The guard short-circuits the entire validation when the data is not in a validatable state:
```
(vo("_ayrors_")!="Restaurant") and (
  (vo(39447)=="No" and vo(23936)=="No"
   and not cntns("+",vo(22126)) and not cntns("+",vo(22124))
   and (vo(22123) == vo(22125)
        or (ctfd(true,"Valid",40501) and remerr(true,22126,40501) and false)))
  and (adderr(ctfd(+vo(22126) < +vo(22124),"Invalid",40501),
              "New Commission should be greater than old Commission ",22126,40501)
       or (ctfd(true,"Valid",40501) and remerr(true,22126,40501)))
)
```
Key additions beyond the base pattern:
- `not cntns("+",vo(...))` guards reject fields containing "+" (partial/invalid data)
- An equality guard `vo(22123) == vo(22125)` short-circuits when values match, setting "Valid" and removing errors via the `ctfd+remerr+false` idiom (see [CL-6](#cl-6-and-false-short-circuit-terminator))
- Uses **numeric field IDs** throughout
- Multiple rules (6067, 6065, 6021, 6034) implement the same pattern with different guard conditions (e.g., `vo(39447)=="Yes"` vs `"No"`, comparison direction `<` vs `>=`)
- Array context `[0:0]`
- Rule 6034 confirms the `>=` comparison direction variant (downsell validation: new commission should be **less** than old): `adderr(ctfd(+vo(23255) >= +vo(23253),"Invalid",40904),"New Commission should be less than old Commission",23255,40904)`

**Variant — Cross-Field Name Validation with Override Bypass (Rule 33653):** `ctfd` copies a field value to a comparison field, while `adderr`/`remerr` validate cross-field name matching using `touc()` for case-insensitive comparison. An override flag field can bypass the validation entirely:
```
{ctfd(vo("_candidateName_")!="",vo("_candidateName_"),"_nameOfCandidateCompareCheck_");
 remerr(vo("_oballow_")=="Yes","_nameOfaccountholder_");
 adderr(vo("_oballow_")!="Yes" and vo("_nameOfaccountholder_")!="" and vo("_candidateName_")!=""
   and touc(vo("_candidateName_")) != touc(vo("_nameOfaccountholder_")),
   "Name as per Bank and Aadhaar not matching","_nameOfaccountholder_");
 remerr(touc(vo("_candidateName_")) == touc(vo("_nameOfaccountholder_")),"_nameOfaccountholder_");}
```
Four-part logic: (1) `ctfd` copies candidate name to a comparison helper field. (2) `remerr` unconditionally removes error when override is allowed (`_oballow_` == "Yes"). (3) `adderr` adds mismatch error only when: override NOT allowed, both fields non-empty, and names differ (case-insensitive). (4) `remerr` removes error when names match (case-insensitive). `execute_on_fill: true`, `run_post_condition_fail: true`.

Key differences from base C-6:
- The `ctfd` copies a **field value** to a comparison field (not a status like "Valid"/"Invalid")
- `touc()` (to uppercase) enables **case-insensitive** name matching (see [CL-12](#cl-12-touc-case-insensitive-comparison))
- An **override bypass** field (`_oballow_`) can suppress validation entirely
- The `adderr` and `remerr` target a **different field** than the `ctfd` destination — the error appears on the bank account holder field, not the comparison field

**Frequency:** Common in commission/financial validation rules. Cross-field name validation variant observed in KYC/onboarding forms.

### C-7. cf + remerr + mvi/minvi + mm/mnm — Full Branch Visibility with Mandatory

**Description:** Extends C-2 (branching visibility with clear) by also managing mandatory/non-mandatory states. When a section is shown, its required fields become mandatory. When hidden, fields are cleared, errors removed, and mandatory status removed.

**When Used:** Complex form sections where a categorization dropdown determines which entire section is visible, mandatory, and active. The hidden section must be fully reset.

**Generic Template:**
```
(minvi(vo("<src>")=="", <all_fields>))
or (mvi(vo("<src>")=="<val_A>", <group_A_fields>)
    and mm(true, <required_A_fields>)
    and mnm(true, <group_B_fields>)
    and cf(true, <group_B_fields>)
    and remerr(true, <group_B_fields>)
    and minvi(true, <group_B_fields>))
or (mvi(vo("<src>")!="<val_A>", <group_B_fields>)
    and mm(true, <required_B_fields>)
    and mnm(true, <group_A_fields>)
    and cf(true, <group_A_fields>)
    and remerr(true, <group_A_fields>)
    and minvi(true, <group_A_fields>))
```

**Real Example (Rule 27646, abbreviated — from 100+ field references):**
```
{[0:0]={"(minvi(vo(\"_ayrors_\")==\"\", <all_commission_fields>))
 or (mvi(vo(\"_ayrors_\")==\"Dineout Restaurant\", <dineout_fields>)
     and mm(true, <dineout_required_fields>)
     and mnm(true, <non_dineout_fields>)
     and cf(true, <non_dineout_fields>)
     and remerr(true, <non_dineout_fields>)
     and minvi(true, <non_dineout_fields>))
 or (mvi(vo(\"_ayrors_\")!=\"Dineout Restaurant\", <non_dineout_fields>)
     and mm(true, <non_dineout_required_fields>)
     and mnm(true, <dineout_specific_fields>)
     and cf(true, <dineout_specific_fields>)
     and remerr(true, <dineout_specific_fields>)
     and minvi(true, <dineout_specific_fields>))"}}
```
When restaurant type is empty: hide everything. When "Dineout Restaurant": show dineout-specific fields, make them mandatory, clear+hide+remove-errors+make-non-mandatory for the other set. When any other type: reverse.

**Key observation:** This rule references **100+ fields** — an extreme case of batch field management. The `and`-chained operations ensure all five actions (show, mandate, clear, remove-error, hide) execute within each branch.

**Variant — 5+ Branches, Non-Array Context (Rules 16545, 16546, 16548, 16549):** The same pattern appears outside array context (no `[0:0]`) with **5 or more branches**. When the categorization field has many possible values (e.g., "Percentage", "Fixed", "Percentage + Fixed", "Order value based - Percentage"), each branch shows its relevant fields, mandates them, and performs the full clear+remerr+mnm+minvi cleanup on all other branches' fields:
```
(minvi(vo("_basecommold_")=="", <all_fields>))
or (mvi(vo("_basecommold_")=="Percentage", "_billtaxold_","_oldpercomm_")
    and mm(true, "_billtaxold_","_oldpercomm_")
    and mnm(true, <fixed_and_slab_fields>)
    and cf(true, <fixed_and_slab_fields>)
    and remerr(true, <fixed_and_slab_fields>)
    and minvi(true, <fixed_and_slab_fields>))
or (mvi(vo("_basecommold_")=="Fixed", "_billtaxold_","_oldfixcomm_")
    and mm(true, "_billtaxold_","_oldfixcomm_")
    and mnm(true, <percentage_and_slab_fields>)
    and cf(true, <percentage_and_slab_fields>)
    and remerr(true, <percentage_and_slab_fields>)
    and minvi(true, <percentage_and_slab_fields>))
or (mvi(vo("_basecommold_")=="Percentage + Fixed", "_billtaxold_","_oldpercomm_","_oldfixcomm_")
    ...)
or (mvi(vo("_basecommold_")=="Order value based - Percentage", "_onBucketsSelectionOld_")
    and mm(true, "_onBucketsSelectionOld_")
    and mnm(true, "_oldpercomm_","_oldfixcomm_")
    and cf(true, "_oldpercomm_","_oldfixcomm_")
    and remerr(true, "_oldpercomm_","_oldfixcomm_")
    and minvi(true, "_oldpercomm_","_oldfixcomm_"))
```
Key differences from the base pattern: (1) No array context -- used at the panel level rather than inside repeatable rows. (2) 5+ `or` branches for each possible category value. (3) Each branch's `mvi` and `mm` lists vary in which fields are shown/mandated, while `mnm`/`cf`/`remerr`/`minvi` target the complement set. (4) Multiple rules (16545 for old fields, 16546 for new fields, etc.) implement the same structure for parallel field sets.

**Variant — Array Context with Large-Scale Branching (Rule 16551):** Rule 16551 extends C-7 in array context with three mega-branches (empty, "Restaurant", non-Restaurant), each targeting 100+ fields for show/hide/mandate/clear/error-remove across old commission fields, new commission fields, and addon fields simultaneously. This confirms C-7 scales to very large field counts.

**Variant — With erbyid Delegation (Rule 50586):** C-7 can be followed by multiple `erbyid(true, ...)` calls that delegate rule execution to child fields. After the visibility/mandatory branching completes, the erbyid calls trigger each child field's own rules:
```
{((minvi(vo("_V34_")=="","_gstst1_"))
  or (mvi(vo("_V34_")=="Yes","_gstst1_") and mm(true,"_V38_"))
  or (mnm(vo("_V34_")=="No","_V38_","_gst2_",...,"_gst8_")
      and cf(true,"_V38_","_V39_",...many fields...)
      and remerr(true,"_V38_","_gst2_",...,"_gst8_")
      and minvi(true,"_gstst1_","_gstst2_",...,"_gstst8_")));
 erbyid(true,"_gst2_");erbyid(true,"_gst3_");...erbyid(true,"_gst8_");}
```
Three branches: (1) Empty → hide status field. (2) "Yes" → show status, mandate GST number. (3) "No" → make non-mandatory, clear all GST fields (numbers, trade names, registration dates, districts, states, cities across 8 GST entries), remove errors, hide all status fields. After branching, 7 `erbyid` calls delegate to GST entry fields 2–8 to trigger their own rules (likely clearing/resetting child fields).

Key additions beyond base C-7:
- **`erbyid` delegation chain** — semicolon-separated after the `or`-chained branches, firing unconditionally with `true`
- The "No" branch `cf` targets **48+ fields** across 8 GST entry groups (numbers, trade names, long names, registration dates, districts, states, cities)
- `erbyid` targets only the GST number fields, which presumably have their own rules for cascading clears/refreshes

**Frequency:** Observed in large categorization forms. Both array and non-array contexts.

**Variant — Progressive Additive Visibility with Kill Switch (Rule 35735):** A C-7 variant where increasing source values progressively show **more** sections (additive) rather than switching between mutually exclusive sections. Additionally, a separate "kill switch" field can hide everything regardless of the count. Uses array context with 3 phases:
```
{[0:0]={"mnm(true,<all 40 fields>);
  minvi(true,<all 40 fields + 5 end markers>);
  mvi(vo(\"_numberOfKPI_\")==\"1\",\"_end1_\",<KPI 1 fields>);
  mm(vo(\"_numberOfKPI_\")==\"1\",<KPI 1 fields>);
  mvi(vo(\"_numberOfKPI_\")==\"2\",\"_end1_\",\"_end2_\",<KPI 1+2 fields>);
  mm(vo(\"_numberOfKPI_\")==\"2\",<KPI 1+2 fields>);
  mvi(vo(\"_numberOfKPI_\")==\"3\",\"_end1_\",\"_end2_\",\"_end3_\",<KPI 1+2+3 fields>);
  mm(vo(\"_numberOfKPI_\")==\"3\",<KPI 1+2+3 fields>);
  mvi(vo(\"_numberOfKPI_\")==\"4\",...<KPI 1+2+3+4 fields>);
  mm(vo(\"_numberOfKPI_\")==\"4\",...);
  mvi(vo(\"_numberOfKPI_\")==\"5\",...<all KPI fields>);
  mm(vo(\"_numberOfKPI_\")==\"5\",...);
  mnm(vo(\"_kpiquestion_\")==\"No\",<all fields>);
  minvi(vo(\"_kpiquestion_\")==\"No\",<all fields + end markers>);
  cf(vo(\"_numberOfKPI_\")==\"1\",<KPI 2-5 fields>);
  cf(vo(\"_numberOfKPI_\")==\"2\",<KPI 3-5 fields>);
  cf(vo(\"_numberOfKPI_\")==\"3\",<KPI 4-5 fields>);
  cf(vo(\"_numberOfKPI_\")==\"4\",<KPI 5 fields>);
  cf(vo(\"_kpiquestion_\")==\"No\",<all fields + end markers>);"}}
```

Three-phase logic:
1. **Reset all** — `mnm(true, ...)` + `minvi(true, ...)` unconditionally reset all 40+ fields to non-mandatory and hidden
2. **Progressive show** — each KPI count value (1–5) shows its fields PLUS all lower-numbered KPI fields. KPI=1 shows set 1, KPI=2 shows sets 1+2, KPI=3 shows sets 1+2+3, etc. The `mvi` and `mm` field lists grow with each count value
3. **Progressive clear + kill switch** — `cf` for each count clears the unused higher-numbered KPI sections. A separate `cf(vo("_kpiquestion_")=="No", ...)` clears EVERYTHING regardless of count

Key differences from base C-7:
- **Additive visibility** — each branch is a superset of the previous (1⊂2⊂3⊂4⊂5), NOT mutually exclusive sections
- **Two independent control fields** — `_numberOfKPI_` controls count, `_kpiquestion_` is a kill switch
- **End marker fields** (`_end1_` through `_end5_`) — ARRAY_END markers are shown/hidden alongside content fields
- **No `or`-chaining** — flat semicoloned statements with the reset-all/show-subset/clear-complement structure instead
- **Progressive `cf`** — each count value clears only the fields ABOVE that count (complement set decreases as count increases)
- Each KPI set has 8 fields (name, PAN image, PAN number, PAN name, father's name, Aadhaar front, Aadhaar back, cheque/passbook) for a total of 40 data fields across 5 KPIs
- `execute_on_fill: true`, `run_post_condition_fail: true`

**Variant — Two-Dimensional Matrix Visibility with ctfd Default Injection (Rule 52547):** A C-7 variant where visibility is controlled by **two independent dimensions** (e.g., division × employee type), creating a matrix of show/hide/mandatory combinations. Additionally, `ctfd` injects a default value ("0") for specific dimension combinations, and `remerr` clears validation errors as part of the reset phase:
```
{minvi(vo("_divisionComp_")==""  or vo("_employeeType_")=="", <all_fields>);
 mnm(vo("_divisionComp_")==""  or vo("_employeeType_")=="", <all_fields>);
 remerr(vo("_divisionComp_")==""  or vo("_employeeType_")=="", <all_fields>);
 mvi(touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="Permanent", <MAP4_fields>);
 mvi(touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="FTC", <MAP4_fields>);
 mvi(touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="Part Timer", <MAP4_fields>);
 mvi(touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="Apprentice", <MAP4_apprentice_fields>);
 mm(...same conditions..., ...same field sets...);
 minvi(touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="Apprentice", <MAP4_non_apprentice_fields>);
 mnm(...complement field sets...);
 mvi(touc(vo("_divisionComp_"))=="MAP5" and vo("_employeeType_")=="Permanent", <MAP5_fields>);
 ... (symmetric MAP5 branches)
 minvi(touc(vo("_divisionComp_"))=="MAP5" ..., <MAP4_fields>);
 ... (cross-dimension hide: when MAP5, hide MAP4 fields and vice versa)
 ctfd(vo("_employeeType_")=="Apprentice", "0", <all_salary_fields>);}
```
Four-phase logic:
1. **Reset when either dimension empty** — `minvi`/`mnm`/`remerr` all use `or` condition (`divisionComp=="" or employeeType==""`) to hide, un-mandate, and clear errors on ALL fields when either dimension is unset
2. **Matrix show/mandate** — `mvi`/`mm` calls use compound `and` conditions combining both dimensions. Each dimension×value combination has its own field set. MAP4 Permanent/FTC/Part Timer show one set, MAP4 Apprentice shows a different (smaller) set, MAP5 variants show MAP5-specific fields
3. **Cross-dimension hide** — `minvi`/`mnm` calls explicitly hide the OTHER dimension's fields (when MAP4 selected, hide MAP5 fields and vice versa)
4. **Default value injection** — `ctfd("0", ...many fields)` sets all salary fields to "0" when employee type is Apprentice (instead of clearing them, gives them a defined default value)

Key differences from base C-7:
- **Two-dimensional branching** — `and` compound conditions on two independent source fields, creating a matrix (not a linear branch per value)
- **Cross-dimension hiding** — must explicitly hide fields belonging to the OTHER dimension's sets, in addition to the standard branch cleanup
- **`ctfd` for default value injection** — instead of `cf` to clear unused fields, `ctfd` writes a meaningful default ("0") to prevent empty salary fields for Apprentice employees
- **`touc()` for case-insensitive comparison** on one dimension (see [CL-12](#cl-12-touc-case-insensitive-comparison))
- **`remerr` in the reset phase** — errors are cleaned up alongside visibility/mandatory resets when either dimension is empty
- **`or` condition for reset** — the reset condition uses `or` (either field empty), while show/mandate conditions use `and` (both fields must have specific values)
- `execute_on_fill: false`, `run_post_condition_fail: false`

### C-7b. cf + remerr + mvi/minvi + mm/mnm — Flat Opposite-Condition Variant

**Description:** A simplified form of C-7 that uses **flat semicolon-separated statements** with opposite conditions instead of `or`-chained branches. Each function explicitly uses the condition or its negation, making the branching implicit rather than structural.

**When Used:** When the source field has only two relevant states (e.g., "Yes" vs everything else) and the number of target fields is small (2–3), making the `or`-chained structure unnecessarily complex.

**Generic Template:**
```
mnm(vo("<src>") != "<active_val>", "<dest1>", "<dest2>");
minvi(vo("<src>") != "<active_val>", "<dest1>", "<dest2>");
remerr(vo("<src>") != "<active_val>", "<dest1>", "<dest2>");
cf(vo("<src>") != "<active_val>", "<dest1>", "<dest2>");
mvi(vo("<src>") == "<active_val>", "<dest1>", "<dest2>");
mm(vo("<src>") == "<active_val>", "<dest1>", "<dest2>");
```

**Real Example (Rule 32989):**
```
{mnm(vo("_isGSTPresent?74_")!="Yes","_V39_","_V40_");
 minvi(vo("_isGSTPresent?74_")!="Yes","_V39_","_V40_");
 remerr(vo("_isGSTPresent?74_")!="Yes","_V39_","_V40_");
 cf(vo("_isGSTPresent?74_")!="Yes","_V39_","_V40_");
 mvi(vo("_isGSTPresent?74_")=="Yes","_V39_","_V40_");
 mm(vo("_isGSTPresent?74_")=="Yes","_V39_","_V40_");}
```
When GST is NOT "Yes": make non-mandatory, hide, remove errors, clear. When GST IS "Yes": show and make mandatory. Six flat statements with explicit opposite conditions instead of `or`-chained branches.

**Key Observations:**
- **No `or` branching** — relies on conditions being mutually exclusive (`!="Yes"` vs `=="Yes"`)
- All 6 functions target the **same 2 fields** — clean and symmetric
- Order is: cleanup functions first (mnm, minvi, remerr, cf), then activation functions (mvi, mm)
- The variable name `_isGSTPresent?74_` contains a `?` character — confirming that special characters are allowed in variable names (see also [S-7](#s-7-numeric-field-ids) for `.` and `-` in variable names)
- No `asdff` — client-side only

**Variant — With Separate-Target rffdd Cascade (Rule 80623):** C-7b extended with `rffdd(true, ...)` targeting a **different field** from the visibility/mandatory target. The source dropdown controls both visibility of a "specify" field AND cascade refresh of a child dropdown:
```
{on ("change") and mvi(vo("_category16_")=="Not Found","_newCategory23_"); mm(vo("_category16_")=="Not Found","_newCategory23_"); minvi(vo("_category16_")!="Not Found","_newCategory23_");mnm(vo("_category16_")!="Not Found","_newCategory23_");rffdd(true,"_sub-Category35_");cf(vo("_category16_")=="", "_newCategory23_");}
```
Five-function logic: (1) When category is "Not Found": show and mandate the "New Category" text field. (2) When NOT "Not Found": hide and un-mandate it. (3) Always refresh the sub-category dropdown (`rffdd`). (4) When category is empty: clear the "New Category" field.

Key differences from base C-7b:
- **`rffdd` targets a different field** (`_sub-Category35_`) than the visibility/mandatory target (`_newCategory23_`) — one rule manages two independent concerns
- **`cf` with empty-guard** — `cf(vo(...)=="", ...)` clears the text field when the source is emptied, separate from the visibility logic
- **`on("change") and mvi(...)`** — the event wrapper applies only to the first `mvi` call (no parentheses around the full expression); remaining functions are always-evaluated ([S-5](#s-5-mixed-event-scoped-and-always-evaluated))
- **Space in `on ("change")`** — syntactic variant confirming whitespace between `on` and `(` is tolerated
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Variant — Deactivation-Only: remerr + minvi + cf without Activation Side (Rule 52627):** A partial C-7b that handles only the "hide/clear/remove-error" side, without any `mvi`/`mm` activation. Multiple conditions (specific value AND empty) each trigger the same trio of deactivation functions on the same field group. The "show" side is presumably handled by a separate rule:
```
{remerr(vo("_vaccinationInfoStatus_")=="Not Vaccinated","_vaccinationInfoName_","_vaccinationInfoDose1_","_vaccinationInfoDose2_","_vaccinationInfoCertficate_");
 remerr(vo("_vaccinationInfoStatus_")=="","_vaccinationInfoName_","_vaccinationInfoDose1_","_vaccinationInfoDose2_","_vaccinationInfoCertficate_");
 minvi(vo("_vaccinationInfoStatus_")=="Not Vaccinated","_vaccinationInfoName_","_vaccinationInfoDose1_","_vaccinationInfoDose2_","_vaccinationInfoCertficate_");
 minvi(vo("_vaccinationInfoStatus_")=="","_vaccinationInfoName_","_vaccinationInfoDose1_","_vaccinationInfoDose2_","_vaccinationInfoCertficate_");
 cf(vo("_vaccinationInfoStatus_")=="Not Vaccinated","_vaccinationInfoName_","_vaccinationInfoDose1_","_vaccinationInfoDose2_","_vaccinationInfoCertficate_");
 cf(vo("_vaccinationInfoStatus_")=="","_vaccinationInfoName_","_vaccinationInfoDose1_","_vaccinationInfoDose2_","_vaccinationInfoCertficate_");}
```
Six calls total: 3 function types x 2 conditions. When vaccination status is "Not Vaccinated" OR empty, all 4 child fields are: (1) errors removed, (2) hidden, (3) cleared. The ordering is `remerr` first, then `minvi`, then `cf` — cleanup before structural changes before data changes. Key differences from base C-7b:
- **No activation functions** (`mvi`, `mm`, `mnm`) — only deactivation. The rule only handles the "hide" scenario
- **Two conditions trigger the same action** — both "Not Vaccinated" and empty `""` produce identical behavior, but they are separate calls rather than using an `or` condition
- **Could be simplified** to use `or` conditions: `remerr(vo(...)=="Not Vaccinated" or vo(...)=="", ...)` — the duplicate calls suggest either a stylistic choice or incremental rule construction
- All 4 target fields are the same across all 6 calls — clean and symmetric
- `execute_on_fill: false`, `run_post_condition_fail: false`

**Frequency:** Observed in simple binary visibility toggles.

**Variant — Compound OR Conditions (Rule 34409):** C-7b extends to handle fields with many possible "active" values by using compound `or` conditions. When the source field has 9+ possible values that should all trigger the same behavior, a chain of `or` comparisons replaces a single `==` check:
```
{mvi(vo("_educationprofile1_")=="Pursuing Diploma" or vo("_educationprofile1_")=="Diploma Holder"
     or vo("_educationprofile1_")=="Pursuing Graduation" or vo("_educationprofile1_")=="Graduate"
     or vo("_educationprofile1_")=="Pursuing Post Graduation" or vo("_educationprofile1_")=="Postgraduate"
     or vo("_educationprofile1_")=="Pursuing PhD" or vo("_educationprofile1_")=="PhD"
     or vo("_educationprofile1_")=="Others","_degreeordiploma_");
 minvi(<same 9-way negation with AND>,"_degreeordiploma_");
 mm(<same 9-way OR condition>,"_degreeordiploma_");
 mnm(<same 9-way AND negation>,"_degreeordiploma_");
 cf(<same 9-way AND negation>,"_degreeordiploma_");
 mvi(vo("_educationprofile1_")=="Others education profile","_educationprofilespe_");
 minvi(vo("_educationprofile1_")!="Others education profile","_educationprofilespe_");
 mm(vo("_educationprofile1_")=="Others education profile","_educationprofilespe_");
 mnm(vo("_educationprofile1_")!="Others education profile","_educationprofilespe_");
 cf(vo("_educationprofile1_")!="Others education profile","_educationprofilespe_");
 minvi(vo("_educationprofile1_")=="Below Metric","_educationstream_");
 mvi(vo("_educationprofile1_")!="Below Metric","_educationstream_");
 mnm(vo("_educationprofile1_")=="Below Metric","_educationstream_");
 mm(vo("_educationprofile1_")!="Below Metric","_educationstream_");
 cf(vo("_educationprofile1_")=="Below Metric","_educationstream_");}
```
Key traits:
- **Three independent field groups** from the same source: `_degreeordiploma_` (9-value OR), `_educationprofilespe_` ("Others" only), `_educationstream_` (inverse: hidden for "Below Metric", shown for everything else)
- The negation of 9-value OR uses `and` with all `!=` — logically correct (De Morgan's law)
- The `_educationstream_` group uses **inverse logic**: `minvi` on the positive value, `mvi` on the negation — hiding the field specifically for one value rather than showing it for one value
- Each group independently has the full mvi+minvi+mm+mnm+cf quintuple
- `execute_on_fill: true`, `run_post_condition_fail: true`

**Variant — Mandatory-Only without Visibility (Rule 34507):** A simplified C-7b that manages only **mandatory/non-mandatory state and clearing** — no visibility changes (`mvi`/`minvi`). Fields remain visible regardless, but their mandatory status and values change based on the source:
```
{[0:0]={"mm(vo(101930)==\"Individual\",102663);
         mnm(vo(101930)!=\"Individual\",102663);
         mm(vo(101930)==\"Partner\",101947);
         mnm(vo(101930)!=\"Partner\",101947);
         cf(vo(101930)!=\"Partner\",101946,101947,101948,101949,...,101958);"}}
```
Two field groups: (1) field 102663 is mandatory when "Individual". (2) field 101947 is mandatory when "Partner", and 13 partner-related fields are cleared when NOT "Partner". Uses numeric field IDs in array context. `execute_on_fill: true`, `run_post_condition_fail: true`.

Key differences from base C-7b: no `mvi`/`minvi` (fields always visible), no `remerr`, and the `cf` targets a much larger set of fields (13) than the `mm`/`mnm` targets (1 each).

**Sub-Variant — cf Superset of mm/mnm Targets (Rules 51692, 51695, 51691, 51693):** The `cf` call targets a **superset** of the fields managed by `mm`/`mnm`. The mandatory fields are a subset of the clearable fields — when the parent is empty, both mandatory and additional dependent fields are cleared:
```
mm(vo("_equipmentType77_")!="","_make83_","_assetNo34_","_serialNo22_","_dateOfInstallation65_");
mnm(vo("_equipmentType77_")=="","_make83_","_assetNo34_","_serialNo22_","_dateOfInstallation65_");
cf(vo("_equipmentType77_")=="","_make83_","_assetNo34_","_serialNo22_","_towerType34_","_towerMake36_","_cabinet83_","_stabilizer18_","_dateOfInstallation65_");
```
`mm`/`mnm` manage 4 fields (make, asset, serial, date). `cf` manages **9 fields** — the same 4 plus tower type, tower make, cabinet, stabilizer, and date. The extra fields are related but optional (not mandatory), so they only need clearing, not mandatory management. 7 confirmed instances with identical structure across different equipment type rows (Rules 51692, 51695, 51691, 51693, 51694, 51696, 51697). `execute_on_fill: true`, `run_post_condition_fail: false`.

**Variant — Exhaustive cf with cntns()+not() (Rule 34566):** C-7b combined with `cntns()` for multi-select fields, where `cf` fires on **both** the positive and negative conditions, resulting in unconditional clearing. Uses `not()` for negation:
```
{mvi(cntns("Yes", vo("_analternatesource_")),"_alternateSource31_");
 minvi(not(cntns("Yes", vo("_analternatesource_"))),"_alternateSource31_");
 mm(cntns("Yes", vo("_analternatesource_")),"_alternateSource31_");
 mnm(not(cntns("Yes", vo("_analternatesource_"))),"_alternateSource31_");
 cf(cntns("Yes", vo("_analternatesource_")),"_alternateSource31_");
 cf(not(cntns("Yes", vo("_analternatesource_"))),"_alternateSource31_");}
```
Key traits:
- **`not(cntns(...))`** as negation pattern — `not()` wraps the entire contains check (see [CL-13](#cl-13-not-function-for-condition-negation))
- **Exhaustive cf** — both `cf(cntns(...))` and `cf(not(cntns(...)))` cover all cases, so the field is **always cleared** on any change. This is intentional: the child field resets to force re-entry regardless of the parent's new value
- Single target field for all 6 function calls
- `execute_on_fill: true`; `run_post_condition_fail` varies — `false` in Rule 34566, but **`true`** in Rules 34631, 34634, 34626, 34627, 34647, 34649 (6 additional confirmed instances)
- Confirmed with multiple check values: "Yes" (Rules 34631, 34634, 34647), "Others" (Rules 34626, 34627, 34649) — not limited to a single keyword

**Sub-Variant — Multi-Group with Different Match Values (Rule 34653):** The exhaustive-cf pattern can appear **multiple times** in the same rule, each group checking a **different value** from the same source field and targeting **different destination fields**:
```
{mvi(cntns("Connected", vo("_connectivitystatus_")),"_bharathnetetc_","_majorproviders_","_privateconnectioninvillage_","_publiconnections_");
 minvi(not(cntns("Connected", vo("_connectivitystatus_"))),"_bharathnetetc_","_majorproviders_","_privateconnectioninvillage_","_publiconnections_");
 mm(cntns("Connected", vo("_connectivitystatus_")),"_bharathnetetc_","_majorproviders_","_privateconnectioninvillage_","_publiconnections_");
 mnm(not(cntns("Connected", vo("_connectivitystatus_"))),"_bharathnetetc_","_majorproviders_","_privateconnectioninvillage_","_publiconnections_");
 cf(cntns("Connected", vo("_connectivitystatus_")),"_bharathnetetc_","_majorproviders_","_privateconnectioninvillage_","_publiconnections_");
 cf(not(cntns("Connected", vo("_connectivitystatus_"))),"_bharathnetetc_","_majorproviders_","_privateconnectioninvillage_","_publiconnections_");
 mvi(cntns("Not connected", vo("_connectivitystatus_")),"_reasonnotconnectivity_","_bringinternet_");
 minvi(not(cntns("Not connected", vo("_connectivitystatus_"))),"_reasonnotconnectivity_","_bringinternet_");
 mm(cntns("Not connected", vo("_connectivitystatus_")),"_reasonnotconnectivity_","_bringinternet_");
 mnm(not(cntns("Not connected", vo("_connectivitystatus_"))),"_reasonnotconnectivity_","_bringinternet_");
 cf(cntns("Not connected", vo("_connectivitystatus_")),"_reasonnotconnectivity_","_bringinternet_");
 cf(not(cntns("Not connected", vo("_connectivitystatus_"))),"_reasonnotconnectivity_","_bringinternet_");}
```
Two independent groups from `_connectivitystatus_`: (1) "Connected" → 4 provider fields, (2) "Not connected" → 2 reason/alternative fields. Each group has the full 6-function exhaustive-cf sextuple. The groups are NOT mutually exclusive in a multi-select context, but for a single-select they represent independent cleanup groups per branch. `execute_on_fill: true`, `run_post_condition_fail: true`.

**Sub-Variant — Large-Scale Multi-Group (4+ branches, Rules 34638, 35185):** The multi-group pattern scales to 4–6+ branches from the same source field, each with the full 6-function sextuple and targeting large field sets (9–11 fields per group). Rule 34638 checks `_pleaseSelectTheBelowScenarios57_` for 4 scenario values ("Part -1", "Part -2", "Part -3", "Part -4"), each revealing its own section of 9–11 fields (e.g., Part-1 → `_Part1_`, `_villageconnectivity_`, `_govtinstitution_`, ... 9 fields; Part-2 → `_Part2_`, `_dedicatedteacher_`, `_betterlearning_`, ... 11 fields). Rule 35185 checks `_district_` for **6** district values ("Telangana Others", "Odisha Others", "Maharastra Others", "Himachal Pradesh Others", "Bihar Others", "Assam Others"), each toggling a single destination field. Key traits:
- Each branch is independently toggled in multi-select contexts — selecting multiple scenarios shows multiple sections simultaneously
- Total function calls can reach **72** (6 branches × 6 functions × 2 conditions) in a single rule, making these among the longest observed expressions
- All groups share the same structural template: `mvi(cntns(val,src), fields); minvi(not(cntns(val,src)), fields); mm(...); mnm(...); cf(...); cf(not(...))`
- `execute_on_fill: true`, `run_post_condition_fail: true`

**Sub-Variant — Basic C-7b Sextuple with cntns+remerr (Rules 51933, 35547):** The simplest form of C-7b with `cntns()`-based conditions: a single target field with the full function sextuple (mvi+minvi+mm+mnm+cf+remerr). This is the non-exhaustive version — `cf` fires only on the negative condition, and `remerr` removes errors alongside the clear:
```
{mvi(cntns("Negative", vo("_driverSentimentcv_")),"_driverSentimentnegativecv_");
 minvi(not(cntns("Negative", vo("_driverSentimentcv_"))),"_driverSentimentnegativecv_");
 mm(cntns("Negative", vo("_driverSentimentcv_")),"_driverSentimentnegativecv_");
 mnm(not(cntns("Negative", vo("_driverSentimentcv_"))),"_driverSentimentnegativecv_");
 cf(not(cntns("Negative", vo("_driverSentimentcv_"))),"_driverSentimentnegativecv_");
 remerr(not(cntns("Negative", vo("_driverSentimentcv_"))),"_driverSentimentnegativecv_");}
```
When the sentiment field contains "Negative": show, make mandatory. When it does NOT contain "Negative": hide, make non-mandatory, clear, remove errors. All 6 functions target the same single field. Key differences from the exhaustive-cf variant (Rule 34566):
- **Single `cf`** on negative condition only — NOT the double `cf(positive)+cf(negative)` exhaustive pattern
- **`remerr` included** — adds error removal alongside the clear (the exhaustive variant had no `remerr`)
- Function order: positive functions (mvi, mm) first, then negative functions (minvi, mnm, cf, remerr) — different from base C-7b's cleanup-first order

Rule 35547 shows the same pattern without `remerr` — a 5-function quintuple:
```
{mvi(cntns("Others", vo("_nonconnectivity_")),"_pleasespecify2_");
 minvi(not(cntns("Others", vo("_nonconnectivity_"))),"_pleasespecify2_");
 mm(cntns("Others", vo("_nonconnectivity_")),"_pleasespecify2_");
 mnm(not(cntns("Others", vo("_nonconnectivity_"))),"_pleasespecify2_");
 cf(not(cntns("Others", vo("_nonconnectivity_"))),"_pleasespecify2_");}
```
`execute_on_fill: true`, `run_post_condition_fail: false`.

**Sub-Variant — 5-Branch Numeric ID Multi-Document-Type (Rule 35843):** C-7b scales to **5 document type branches** using numeric field IDs. Each branch has the full mvi/minvi/mm/mnm/cf quintuple. The source field `vo(102403)` controls which document section is visible:
```
{mvi(vo(102403)=="Voter ID",102391,102392);
 minvi(vo(102403)!="Voter ID",102391,102392);
 mm(vo(102403)=="Voter ID",102391,102392);
 mnm(vo(102403)!="Voter ID",102391,102392);
 cf(vo(102403)!="Voter ID",102391,102392);
 mvi(vo(102403)=="Driving License",102393,102394,102395,102396,102397);
 minvi(vo(102403)!="Driving License",102393,102394,102395);
 mm(vo(102403)=="Driving License",102393,102394);
 mnm(vo(102403)!="Driving License",102393,102394);
 cf(vo(102403)!="Driving License",102393,102394);
 mvi(vo(102403)=="Passport",102481,102769,102770,102771,102772);
 ... (Bank Statement, Bank Declaration branches)}
```
Key traits:
- **5 document types**: Voter ID, Driving License, Passport, Bank Statement, Bank Declaration
- **Asymmetric field counts**: Voter ID has 2 fields, Driving License has 5 (mvi) but mm/mnm/cf target only 2 of those 5 — not all visible fields are mandatory
- **Numeric field IDs** throughout (see [S-7](#s-7-numeric-field-ids))
- `execute_on_fill: true`, `run_post_condition_fail: false`

### C-8. pgtm + cf + erbyid — Parse Substring, Clear on Empty, Delegate

**Description:** `pgtm` (parseGetTextMatch) extracts a substring from a field value based on position, writing it to a destination field. `cf` clears related fields when the source is empty. `erbyid` delegates to the extracted field's own rules for further processing (e.g., a lookup table mapping).

**When Used:** When a field value (e.g., FSSAI license number) contains embedded information (e.g., state code in positions 1–3) that must be extracted and used for downstream lookups.

**Generic Template:**
```
pgtm(vo("<src>") != "", "<label>", "<dest>", <start_pos>, <length>);
cf(vo("<src>") == "", "<related_field_1>", "<related_field_2>", "<dest>");
erbyid(vo("<dest>") != "", "<dest>");
```

**Real Example (Rule 32995):**
```
{pgtm(vo("_V55_")!="","FSSAI","_fssaiStateCode_",1,3);
 cf(vo("_V55_") == "","_fssaiStateCodeSap_","_fssaiState_","_fssaiStateCode_");
 erbyid(vo("_fssaiStateCode_")!="","_fssaiStateCode_");}
```
When the FSSAI number (`_V55_`) is non-empty, extract characters at positions 1–3 (the state code portion) into `_fssaiStateCode_`. When empty, clear the SAP code, state name, and state code fields. When the state code is non-empty, delegate to its own rules (which implements a 74-entry ctfd lookup table mapping state codes to names and SAP codes — see Rule 32997).

**Key Observations:**
- `pgtm` signature: `pgtm(condition, "<label>", "<dest>", startPos, length)` — the label ("FSSAI") appears to be a tag/description, not functional
- `cf` acts as the "empty guard" — clears all dependent fields when the source is cleared
- `erbyid` creates a two-rule chain: Rule 32995 extracts the code, Rule 32997 maps it to values
- The `cf` targets 3 fields while `pgtm` only targets 1 — the other 2 are populated by the delegated rule

**Frequency:** Rare. Observed for parsing embedded codes from license/registration numbers.

### C-9. cf + svfd + asdff — Clear, Extract Substring, and Save

**Description:** Clears a description field, extracts a substring from a dropdown's display value using `svfd` (splitValueFromDropdown), and saves the result. The `svfd` function parses composite dropdown values (e.g., "ID - Description") to extract a specific part.

**When Used:** When a dropdown displays "code - description" format and a separate field needs just the description (or just the code) portion.

**Generic Template:**
```
cf(<empty_condition>, "<desc_field>");
cf(<reset_condition>, "<desc_field>");
svfd(<has_value_condition>, "<delimiter>", <part_index>, "<desc_field>", <direction>);
asdff(<condition>, "<desc_field>");
```

**Real Example (Rule 48864):**
```
{on("change") and (
  cf(vo("_restID9_")=="", "_restID9Desc_");
  cf(vo("_LocQue8_")=="Restaurant Location", "_restID9Desc_");
  asdff(vo("_restID9Desc_")=="", "_restID9Desc_");
  svfd(vo("_restID9_")!="", " -", 1, "_restID9Desc_", -1);
  asdff(vo("_restID9_")!="", "_restID9Desc_")
)}
```
When restaurant ID is empty or location type is "Restaurant Location", clear the description. When restaurant ID has a value, split it using " -" delimiter, take part at index 1, write to description, and save. Two `asdff` calls: one saves the cleared state, another saves the extracted value.

**Note:** `svfd` is a new function not previously documented. Signature appears to be: `svfd(condition, delimiter, partIndex, destVar, direction)`. The `-1` direction likely means "everything after the delimiter."

**Variant — Simple Binary Empty/Non-Empty (Rules 51764, 51765):** A simplified C-9 with only two branches: empty (clear+save) and non-empty (extract+save). No extra condition-specific `cf` call:
```
{on("change") and (cf(vo("_cityId_")=="", "_cityID90_");asdff(vo("_cityId_")=="", "_cityID90_");svfd(vo("_cityId_")!="", " -", 1, "_cityID90_", -1);asdff(vo("_cityId_")!="", "_cityID90_"))}
```
When city ID is empty: clear and save the description field. When non-empty: extract the text after " -" and save. Same pattern for zone ID (Rule 51765 with `_zoneId_` → `_zoneID83_`). Key differences from the base C-9: only one `cf` (empty guard, no extra condition), and both `asdff` calls use the same field condition rather than one being unconditional. `execute_on_fill: true`, `run_post_condition_fail: false`.

**Variant — With Downstream Cascade rffdd (Rule 51918):** C-9 extended with `rffdd(true, ...)` targeting a **different field** to refresh a downstream dropdown that depends on the extracted value. The svfd extraction feeds a cascade chain:
```
{on("change") and (cf(vo("_cityId_")=="", "_cityID90_");asdff(vo("_cityId_")=="", "_cityID90_");svfd(vo("_cityId_")!="", " -", 1, "_cityID90_", -1);asdff(vo("_cityId_")!="", "_cityID90_");rffdd(true,"_zoneId_"))}
```
Same binary empty/non-empty pattern as Rules 51764/51765 (clear+save when empty, extract+save when non-empty), but adds `rffdd(true,"_zoneId_")` to unconditionally refresh the zone dropdown after the city ID is extracted. The zone dropdown options depend on the city — when the city changes, the zone options must reload. `execute_on_fill: true`, `run_post_condition_fail: false`.

Key additions beyond base C-9:
- **`rffdd` on a different target field** (`_zoneId_` vs `_cityID90_`) — the extraction and cascade target different fields
- `rffdd(true, ...)` is unconditional — the zone always refreshes when the city changes, regardless of whether the city was cleared or populated
- Creates a **svfd → rffdd cascade chain**: city dropdown → extract city ID → refresh zone dropdown

**Frequency:** Rare. Observed for composite dropdown value extraction (4 instances: Rules 48864, 51764, 51765, 51918).

### C-10. cf + rffdd + dis in on("blur") — Blur-Triggered Cascade Reset

**Description:** On blur of a parent field, clears multiple child dropdowns, refreshes each independently, and disables one. Similar to the standard cascade-clear pattern but triggered on blur instead of change.

**When Used:** When the parent field is one where the user types/selects and the cascade should only fire after they leave the field (e.g., an employee ID lookup field).

**Generic Template:**
```
on("blur") and (
  cf(<condition>, "<child1>", "<child2>", "<child3>");
  rffdd(<condition>, "<child1>");
  rffdd(<condition>, "<child2>");
  rffdd(<condition>, "<child3>");
  dis(true, "<child_to_disable>")
)
```

**Real Example (Rule 48622):**
```
{on("blur") and (
  cf(vo("_employeeiddrob_")!="","_salesofficedrob_","_deliveryplantdrob_","_salesgroupdrob_");
  rffdd(vo("_employeeiddrob_")!="","_salesofficedrob_");
  rffdd(vo("_employeeiddrob_")!="","_deliveryplantdrob_");
  rffdd(vo("_employeeiddrob_")!="","_salesgroupdrob_");
  dis(true,"_deliveryplantdrob_")
)}
```
On blur: when employee ID is non-empty, clear all three child dropdowns, refresh each separately, and disable delivery plant. Note `rffdd` is called per-child rather than once with multiple args.

**Frequency:** Less common. Observed for employee/user lookup cascades.

### C-11. ctfd("NA") + minvi + mvi + mm + mnm — Hide with Default Value Instead of Clear

**Description:** Instead of using `cf` to clear hidden fields, `ctfd` writes a default value (typically "NA") into them. Combined with visibility and mandatory management. This is a variant of [C-7](#c-7-cf--remerr--mvminvi--mmmnm--full-branch-visibility-with-mandatory) where the "inactive" branch derives a sentinel value rather than clearing.

**When Used:** When hidden/inactive fields must have a non-empty value (e.g., "NA") to satisfy downstream validation or reporting requirements, rather than being truly empty.

**Generic Template:**
```
minvi(vo("<src>") == "", "<dest1>", "<dest2>");
mvi(vo("<src>") == "<active_val>", "<dest1>", "<dest2>") and mm(true, "<dest1>", "<dest2>");
mnm(vo("<src>") == "<inactive_val>", "<dest1>", "<dest2>")
  and ctfd(true, "NA", "<dest1>", "<dest2>")
  and minvi(true, "<dest1>", "<dest2>")
```

**Real Example (Rule 48942):**
```
{minvi(vo(53828)=="",53264,53265);
 mvi(vo(53828)=="Yes",53264,53265) and mm(true,53264,53265);
 mnm(vo(53828)=="No",53264,53265) and ctfd(true,"NA",53264,53265) and minvi(true,53264,53265)}
```
Three branches: (1) Empty → hide both fields. (2) "Yes" → show and make mandatory. (3) "No" → make non-mandatory, derive "NA" into both fields, and hide them.

**Key Observations:**
- Uses **numeric field IDs** instead of variable names (see [S-7](#s-7-numeric-field-ids))
- `ctfd(true, "NA", ...)` writes to **multiple destination fields** in a single call
- The "No" branch chains `mnm`, `ctfd`, and `minvi` with `and` — all three must succeed
- No `asdff` — the "NA" value is not persisted immediately (display-side only or saved on form submit)
- No `cf` — fields are filled with "NA" instead of cleared, which is semantically different

**Variant — Single-Branch with remerr (Rule 32969):** A simplified form of C-11 that handles only the "inactive" branch (the "active" branch is presumably handled by a separate rule). Adds `remerr` to clear validation errors from the hidden fields:
```
{ctfd(vo("_V32_")=="Indirect","NA","_fssaiStatus_");minvi(vo("_V32_")=="Indirect","_V55_","_V59_","_fssaiStatusApplication_");remerr(vo("_V32_")=="Indirect","_V55_","_V59_","_fssaiStatusApplication_");mnm(vo("_V32_")=="Indirect","_V55_","_V59_","_fssaiStatusApplication_");}
```
When the field equals "Indirect": (1) derive "NA" into the FSSAI status field, (2) hide 3 dependent fields, (3) remove errors from them, (4) make them non-mandatory. All four functions share the **same condition**. Key differences from base C-11: uses `remerr` for error cleanup, no `mvi`/`mm` branches (single-direction rule), and the `ctfd` targets a different field (`_fssaiStatus_`) than the `minvi`/`remerr`/`mnm` fields.

**Frequency:** Rare. Observed when downstream systems require non-empty values for inactive fields.

### C-12. cf + mvi/minvi + mm/mnm + cntns — Multi-Select Contains-Based Visibility

**Description:** Uses `contains()` (or `cntns()`) to check whether a **multi-select/multi-value field** includes a specific option, then shows/hides, mandates/un-mandates, and clears the corresponding sub-section. Unlike C-7, which uses `==` equality for mutually exclusive branches, this pattern uses `contains()` for **independently toggleable sub-sections** -- each sub-section is visible or hidden based on whether the multi-select includes its keyword.

**When Used:** When a field allows selecting multiple options (e.g., addon features like "Collection Fees", "Minimum Commission", "Access Commission") and each selected option reveals its own sub-section of fields.

**Generic Template:**
```
(minvi(vo("<multi_select>")=="", <all_subsection_fields>))
or (
  (mvi(contains("<option_A>", vo("<multi_select>")), <section_A_fields>)
   and mm(true, <section_A_fields>))
  or (cf(true, <section_A_fields>) and mnm(true, <section_A_fields>) and minvi(true, <section_A_fields>));
  (mvi(contains("<option_B>", vo("<multi_select>")), <section_B_fields>)
   and mm(true, <section_B_fields>))
  or (cf(true, <section_B_fields>) and mnm(true, <section_B_fields>) and minvi(true, <section_B_fields>))
)
```

**Real Example (Rule 16547):**
```
{(minvi(vo("_addon_")=="","_mincommperiod_","_mincomm_","_collfees_","_acccomm_"))
 or (
   (mvi(contains("Collection Fees",vo("_addon_")),"_collfees_") and mm(true,"_collfees_"))
   or (cf(true,"_collfees_") and mnm(true,"_collfees_") and minvi(true,"_collfees_"));
   (mvi(contains("Minimum Commission",vo("_addon_")),"_mincommperiod_","_mincomm_")
    and mm(true,"_mincommperiod_","_mincomm_"))
   or (cf(true,"_mincommperiod_","_mincomm_") and mnm(true,"_mincommperiod_","_mincomm_")
       and minvi(true,"_mincommperiod_","_mincomm_"));
   (mvi(contains("Access Commission",vo("_addon_")),"_acccomm_") and mm(true,"_acccomm_"))
   or (cf(true,"_acccomm_") and mnm(true,"_acccomm_") and minvi(true,"_acccomm_"))
 )}
```
When the addon field is empty, hide all sub-section fields. Otherwise, for each possible addon option: if `contains()` matches, show and mandate the corresponding fields; if not, clear, un-mandate, and hide them.

**Key Observations:**
- Each sub-section is **independent** -- multiple options can be selected simultaneously, and each controls its own fields
- Sub-sections are separated by **semicolons** within the outer `or` block, making them independent evaluation units
- The `or` within each sub-section works as an if/else: `(show and mandate) or (clear and un-mandate and hide)`
- `contains("<option>", vo(...))` checks if the multi-select value includes the option string
- No `asdff` -- persistence handled externally
- No `remerr` -- unlike C-7, this variant does not remove errors (possibly because the sub-sections are simpler with fewer validation constraints)

**Frequency:** Observed in multi-select addon/feature configuration forms.

### C-16. ctfd + cf + dis + en + mm + mnm — Tri-State Percentage Split with Complement Calculation

**Description:** A three-branch `or`-chained pattern where a parent tri-state field ("NA"/"No"/"Yes") controls two linked numeric fields (e.g., percentage split). Each branch configures different field values, enable/disable states, and mandatory states. The "Yes" branch includes a **complement calculation** (`100 - +vo(field)`) to auto-derive the second field as the remainder.

**When Used:** Percentage split scenarios where a parent field determines whether the split is applicable: "NA" → both fields get "NA" and are disabled; "No" → one field gets 100% and both are disabled; "Yes" → one field is editable+mandatory, the other auto-calculates as 100 minus the entered value.

**Generic Template:**
```
(ctfd(vo(<parent>)=="NA","NA",<field1>,<field2>) and dis(true,<field1>,<field2>) and mnm(true,<field1>))
or (ctfd(vo(<parent>)=="No",100,<field2>) and dis(true,<field1>,<field2>) and mnm(true,<field1>) and cf(vo(<field1>),<field1>))
or (cf(vo(<field1>)=="No" or vo(<field1>)=="NA",<field1>,<field2>);
    ctfd((vo(<parent>)=="Yes" and vo(<field1>)),100 - +vo(<field1>),<field2>);
    dis(vo(<parent>)=="Yes",<field2>) and en(true,<field1>) and mm(true,<field1>))
```

**Real Example (Rule 12378):**
```
{(ctfd(vo(61259)=="NA","NA",61204,61205) and dis(true,61204,61205) and mnm(true,61204)) or (ctfd(vo(61259)=="No",100,61205) and dis(true,61204,61205) and mnm(true,61204) and cf(vo(61204),61204)) or (cf(vo(61204)=="No" or vo(61204)=="NA",61204,61205); ctfd((vo(61259)=="Yes" and vo(61204)),100 - +vo(61204),61205); dis(vo(61259)=="Yes",61205) and en(true,61204) and mm(true,61204))}
```

Three branches:
1. **"NA" branch:** `ctfd` writes "NA" to both fields, `dis` disables both, `mnm` makes field1 non-mandatory
2. **"No" branch:** `ctfd` writes 100 to field2, `dis` disables both, `mnm` makes field1 non-mandatory, `cf(vo(field1), field1)` self-clears field1 (see below)
3. **"Yes" branch:** `cf` clears stale values ("No"/"NA") from both fields, `ctfd` computes `100 - +vo(field1)` into field2 (complement calculation), `dis` disables field2 (auto-calculated), `en` enables field1 (user-editable), `mm` makes field1 mandatory

**Key Observations:**
- **Complement arithmetic** `100 - +vo(field)` — derives the remainder of a percentage split. Uses `+vo()` for numeric coercion (see [CL-8](#cl-8-numeric-coercion-with-vo))
- **`cf(vo(field), field)` self-clear** — uses the field's own value as the condition AND targets itself. Effectively clears the field whenever it has a truthy value (a "reset on truthy" idiom)
- **`ctfd` writes to multiple destinations** in branch 1 (`ctfd("NA", field1, field2)`) — writes the same value to 2 fields
- Uses **numeric field IDs** throughout (see [S-7](#s-7-numeric-field-ids))
- `execute_on_fill: false`, `execute_on_read: false`, `run_post_condition_fail: true`
- Confirmed with 4 identical instances (Rules 12378, 12372, 12382, 12380) — each handling a different parent→child pair in the same percentage split form
- The "Yes" branch has a **compound condition** `vo(parent)=="Yes" and vo(field1)` — ensures ctfd only fires when the user has entered a value in field1, preventing `100 - 0 = 100` from appearing prematurely

**Frequency:** Observed in percentage allocation/split forms. 9 instances confirmed with identical structure (Rules 12378, 12372, 12382, 12380, 12376, 12374, 12370, 12368, 12366).

**Variant — With erbyid Delegation (Rules 12593, 12595):** The tri-state percentage split pattern can be followed by `erbyid` calls that delegate rule execution to aggregate status fields after the split is computed. This chains the percentage split into an aggregate status derivation pipeline:
```
{(ctfd(vo(61798)=="NA","NA",61799,61800) and dis(true,61799,61800) and mnm(true,61799))
 or (ctfd(vo(61798)=="No",100,61800) and dis(true,61799,61800) and mnm(true,61799) and cf(vo(61799),61799))
 or (cf(vo(61799)=="No" or vo(61799)=="NA",61799,61800);
     ctfd((vo(61798)=="Yes" and vo(61799)),100 - +vo(61799),61800);
     dis(vo(61798)=="Yes",61800) and en(true,61799) and mm(true,61799));
 erbyid(true,61794);erbyid(true,61795)}
```
The three-branch logic is identical to the base C-16 pattern. After the branching, two `erbyid(true, ...)` calls delegate to fields 61794 and 61795 — these are likely aggregate status fields (e.g., [C-18](#c-18-ctfd--concat--cntns--aggregate-multi-field-status-derivation)) that re-compute their roll-up status when any child percentage split changes.

Key additions beyond base C-16:
- **`erbyid` delegation** — semicolon-separated after the `or`-chained branches, firing unconditionally with `true`
- Rule 12593 has **two** erbyid targets, Rule 12595 has **one** — the number of delegates varies by how many aggregate fields depend on this split
- The `erbyid` calls reference fields from the same panel (61794, 61795) that aggregate across multiple percentage splits
- Confirms C-16 can feed into [C-14](#c-14-ctfd--erbyid--derive-then-delegate) delegation chains

**Variant — Complement with roundTo() (Rule 12451):** The complement calculation can be wrapped in `roundTo()` to control decimal precision. Instead of `100 - +vo(field)`, the expression uses `roundTo(100 - +vo(field), 2)` to round the result to 2 decimal places:
```
{ctfd(vo(61048),roundTo(100 - +vo(61048),2),61274)}
```
When field 61048 has a value (truthy condition), compute `100 - value` rounded to 2 decimal places and write to field 61274. This is a simplified single-branch version of C-16 — only the "Yes" complement calculation branch, without the "NA" and "No" branches. Uses numeric field IDs. `run_post_condition_fail: true`.

Key additions beyond base C-16:
- **`roundTo(expr, decimals)`** — new rounding function wrapping the arithmetic expression. Signature: `roundTo(value, decimalPlaces)`
- Standalone complement without the full tri-state branching — just the calculation
- The condition is `vo(61048)` (truthy check) rather than a parent field comparison

**Variant — Flat Opposite-Condition Style with not(cntns()) (Rule 51320):** C-12 can use the flat C-7b-style statement structure instead of `or`-chained branches. Each product/option gets a flat quintuple of mvi+minvi+mm+mnm+cf with `cntns()` for the positive and `not(cntns())` for the negative:
```
{mvi(cntns("RCU-Small", vo("_pmxsize_")), "_pleaseEnterRCUSmallQuantitiy63_");
 minvi(not(cntns("RCU-Small", vo("_pmxsize_"))), "_pleaseEnterRCUSmallQuantitiy63_");
 mm(cntns("RCU-Small", vo("_pmxsize_")), "_pleaseEnterRCUSmallQuantitiy63_");
 mnm(not(cntns("RCU-Small", vo("_pmxsize_"))), "_pleaseEnterRCUSmallQuantitiy63_");
 cf(not(cntns("RCU-Small", vo("_pmxsize_"))), "_pleaseEnterRCUSmallQuantitiy63_");
 mvi(cntns("RCU-Big", vo("_pmxsize_")), "_pleaseEnterQuantity47_");
 minvi(not(cntns("RCU-Big", vo("_pmxsize_"))), "_pleaseEnterQuantity47_");
 mm(cntns("RCU-Big", vo("_pmxsize_")), "_pleaseEnterQuantity47_");
 mnm(not(cntns("RCU-Big", vo("_pmxsize_"))), "_pleaseEnterQuantity47_");
 cf(not(cntns("RCU-Big", vo("_pmxsize_"))), "_pleaseEnterQuantity47_");
 ... (6 more product sizes: PMX 4V, PMX 6V, Tower-6v, Tower-8v, Bargun)}
```
Key differences from base C-12:
- **Flat structure** (semicoloned statements) instead of `or`-chained branches — matches C-7b style
- Uses `not(cntns(...))` for negation instead of relying on `or` branch short-circuiting (see [CL-13](#cl-13-not-function-for-condition-negation))
- `cf` only fires on the **negative** condition (unlike the exhaustive variant in C-7b Rule 34566 where both fire)
- **8 independent sub-sections** for 8 product sizes, each with exactly 5 functions: mvi, minvi, mm, mnm, cf
- Each sub-section controls a **single field** (quantity or type field for that product)
- `execute_on_fill: true`, `run_post_condition_fail: false`

### C-13. ctfd + mvi/minvi — Derive Composite Category Then Route Visibility

**Description:** A two-phase pattern where multiple `ctfd` calls first derive a **composite category string** from a combination of source field values, writing the result to an intermediate field. Then `mvi`/`minvi` calls use the **derived intermediate value** (not the original source fields) to control which panels or field groups are visible. This decouples the categorization logic from the visibility logic.

**When Used:** When visibility depends on a combination of 2+ source fields (e.g., outlet type x beneficiary type x PAN type) and the resulting category space is large (e.g., 8+ categories). The intermediate category field simplifies downstream logic by collapsing multi-dimensional conditions into a single categorical value.

**Generic Template:**
```
ctfd(<compound_cond_1>, "<category_label_1>", "<category_dest>");
ctfd(<compound_cond_2>, "<category_label_2>", "<category_dest>");
...
ctfd(<compound_cond_N>, "<category_label_N>", "<category_dest>");
minvi(true, <all_panels>);
mvi(vo("<category_dest>")=="<category_label_1>", <panel_for_1>);
mvi(vo("<category_dest>")=="<category_label_2>", <panel_for_2>);
...
```

**Real Example (Rule 32044):**
```
{[0:0]={"
  ctfd(vo(\"_outlettype_\")==\"Group\" and vo(\"_beneficiarytype_\")==\"Licensee\"
       and vo(\"_beneficiarypantype_\")==\"Individual\",
       \"Licensee Group Individual\",\"_beneficiarypancategory_\");
  ctfd(vo(\"_outlettype_\")!=\"Group\" and vo(\"_beneficiarytype_\")==\"Licensee\"
       and vo(\"_beneficiarypantype_\")==\"Individual\",
       \"Licensee Individual\",\"_beneficiarypancategory_\");
  ctfd(vo(\"_outlettype_\")==\"Group\" and vo(\"_beneficiarytype_\")==\"Licensee\"
       and vo(\"_beneficiarypantype_\")==\"Firm/Limited Liability Partnership\",
       \"Licensee Group Firm\",\"_beneficiarypancategory_\");
  ctfd(vo(\"_outlettype_\")!=\"Group\" and vo(\"_beneficiarytype_\")==\"Licensee\"
       and vo(\"_beneficiarypantype_\")==\"Firm/Limited Liability Partnership\",
       \"Licensee Firm\",\"_beneficiarypancategory_\");
  ctfd(vo(\"_outlettype_\")==\"Group\" and vo(\"_beneficiarytype_\")==\"Operator\"
       and vo(\"_beneficiarypantype_\")==\"Individual\",
       \"Operator Group Individual\",\"_beneficiarypancategory_\");
  ... (8 total ctfd calls covering all combinations)
  minvi(true,\"_1licenseepanel_\",\"_2licenseepanel_\",\"_1OperatorPanel_\",\"_2OperatorPanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Licensee Individual\",\"_1licenseepanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Licensee Group Individual\",\"_1licenseepanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Licensee Group Firm\",\"_2licenseepanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Licensee Firm\",\"_2licenseepanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Operator Individual\",
       \"_1licenseepanel_\",\"_1OperatorPanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Operator Firm\",
       \"_1licenseepanel_\",\"_2OperatorPanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Operator Group Individual\",
       \"_2licenseepanel_\",\"_1OperatorPanel_\");
  mvi(vo(\"_beneficiarypancategory_\")==\"Operator Group Firm\",
       \"_2licenseepanel_\",\"_2OperatorPanel_\");
"}}
```
Phase 1 (derivation): 8 `ctfd` calls map every combination of outlet type (Group/not-Group) x beneficiary type (Licensee/Operator) x PAN type (Individual/Firm) to a human-readable category label. Phase 2 (visibility): `minvi(true, ...)` hides all panels first, then 8 `mvi` calls show the appropriate panel(s) based on the derived category.

**Key Observations:**
- The intermediate field (`_beneficiarypancategory_`) acts as a **computed dimension reduction** -- 3 source fields x 2+ values each are collapsed to 1 field with 8 category values
- `minvi(true, ...)` acts as a **reset-all** before individual `mvi` calls selectively show panels
- Some `mvi` calls show **multiple panels** (e.g., "Operator Individual" shows both `_1licenseepanel_` and `_1OperatorPanel_`), making the visibility logic richer than simple 1-to-1 mapping
- **No `asdff`** -- the derived category is display-only
- **No `cf`** -- visibility is controlled, but no field clearing (panels contain their own fields managed separately)
- Array context `[0:0]`
- Semicolon-separated statements ensure derivation completes before visibility is evaluated

**Variant — Extended with asdff + erbyid + mm/mnm (Rules 32917, 32918):** The base C-13 pattern can be extended with additional functions to create a comprehensive "derive category, persist, manage visibility + mandatory, and delegate" mega-rule. Rule 32917 adds `asdff`, `erbyid`, `mm`/`mnm` to the derivation+visibility core:
```
ctfd(<compound_cond_1>, "<category_1>", "_beneficiarypancategory_");
ctfd(<compound_cond_2>, "<category_2>", "_beneficiarypancategory_");
... (16 total ctfd calls covering all combinations)
minvi(true, "_gSTDetails60_");
mvi(vo("_beneficiarypancategory_")=="<category_1>");
mvi(vo("_beneficiarypancategory_")=="<category_2>", "_gSTDetails60_");
... (8 mvi calls for visibility routing)
minvi(<negated_condition>, "_tpsp_", "_2OperBankStateimg_");
mvi(<positive_condition>, "_tpsp_", "_2OperBankStateimg_");
mnm(<negated_condition>, "_tpsp_", "_2OperBankStateimg_");
mm(<positive_condition>, "_tpsp_", "_2OperBankStateimg_");
erbyid(vo("_beneficiarytype_") != "", "_esignMethod_");
asdff(vo("_beneficiarypancategory_") != "", "_beneficiarypancategory_");
erbyid(vo("_beneficiarytype_") != "", "_beneficiarypancategory_");
```
Key additions beyond base C-13:
- **`asdff`** persists the derived category to the server (base C-13 was display-only)
- **`erbyid`** delegates rule execution to `_esignMethod_` and `_beneficiarypancategory_` fields, cascading the derivation into further rule chains (see [C-14](#c-14-ctfd--erbyid--derive-then-delegate))
- **`mm`/`mnm`** manages mandatory state of related fields based on the derived category
- **`minvi`/`mvi`** for additional field groups beyond the main panels (e.g., GST details, TPSP)
- 16 `ctfd` calls (vs 8 in Rule 32044) because it also handles "Group Licensee" and "Group Operator" beneficiary types
- Non-array context (vs array context in Rule 32044)

Rule 32918 further extends this pattern by adding a **validation guard** at the top: `cf` + `adderr`/`remerr` clear the category and show errors when the PAN type is not in the allowed set, before proceeding with the same derivation logic.

**Frequency:** Observed in complex multi-dimensional categorization scenarios.

### C-14. ctfd + erbyid — Derive Then Delegate

**Description:** After deriving a value with `ctfd`, `erbyid` (executeRuleById) is used to trigger the **destination field's own rules**. This creates a rule chain where the derived value causes downstream rules on that field to re-evaluate, enabling cascading derivations across fields.

**When Used:** When setting a field's value should trigger further processing: additional derivations, visibility changes, or dropdown refreshes that are defined as rules on the destination field itself. Rather than duplicating all downstream logic in the current rule, `erbyid` delegates to the destination's own rule definitions.

**Generic Template:**
```
ctfd(<condition>, <value_or_expression>, "<dest_var>");
erbyid(<condition>, "<dest_var>");
```

**Real Example — Sum with Delegation (Rule 17765):**
```
{[0:0]={"ctfd(vo(\"_map4B1_\"), +vo(\"_map4B1_\") + +vo(\"_map4B2_\") + ... + +vo(\"_map4B9_\"), \"_grossSalary_\");erbyid(true, \"_grossSalary_\")"}}
```
Sums 9 salary components into `_grossSalary_`, then triggers `_grossSalary_`'s own rules (which may compute taxes, deductions, or net pay based on the new gross salary value).

**Real Example — Category Derivation with Delegation (Rule 32917, partial):**
```
erbyid(vo("_beneficiarytype_") != "", "_esignMethod_");
asdff(vo("_beneficiarypancategory_") != "", "_beneficiarypancategory_");
erbyid(vo("_beneficiarytype_") != "", "_beneficiarypancategory_");
```
After deriving the beneficiary PAN category (via 16 `ctfd` calls earlier in the rule), `erbyid` delegates to both `_esignMethod_` and `_beneficiarypancategory_` fields to trigger their own rules. The `asdff` saves the category before `erbyid` triggers downstream processing.

**Key Observations:**
- `erbyid` typically uses `true` or a broad non-empty condition, since the delegation should fire whenever the derivation fires
- Can delegate to **multiple fields** — either via separate `erbyid` calls (e.g., Rule 32917) or via a **single `erbyid` call with multiple target parameters**: `erbyid(condition, "field1", "field2")` (e.g., Rule 36714: `erbyid(vo("_panHolderName_") != "", "_BankBeneficiary_","_bankValidationStatus33_")`)
- Order matters: `ctfd` must fire before `erbyid` so the destination has the new value when its rules execute
- When combined with `asdff`, the save should occur before `erbyid` to ensure the persisted value is available to downstream rules

**Variant — Sum + Delegate + Validation Matrix (Rule 18078):** Extends the base derive-then-delegate pattern with `remerr` + multiple `adderr` calls that form a **validation matrix** across two dimensions (division type × employee type). Uses `touc()` for case-insensitive division comparison:
```
{ctfd(vo("_map5B1_"), +vo("_map5B1_") + +vo("_map5B2_") + ... + +vo("_map5B9_"), "_map5B10_");
 erbyid(true, "_map5B10_");
 remerr(true,"_map4B1_","_map5B1_");
 adderr((touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="Permanent"
   and +vo("_map4B1_") == 0), "Basic salary should be greater than 0","_map4B1_");
 adderr((touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="FTC"
   and +vo("_map4B1_") == 0), "Basic salary should be greater than 0","_map4B1_");
 adderr((touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="Part Timer"
   and +vo("_map4B1_") == 0), "Basic salary should be greater than 0","_map4B1_");
 adderr((touc(vo("_divisionComp_"))=="MAP5" and vo("_employeeType_")=="Permanent"
   and +vo("_map5B1_") == 0), "Basic salary should be greater than 0","_map5B1_");
 adderr((touc(vo("_divisionComp_"))=="MAP5" and vo("_employeeType_")=="FTC"
   and +vo("_map5B1_") == 0), "Basic salary should be greater than 0","_map5B1_");
 adderr((touc(vo("_divisionComp_"))=="MAP5" and vo("_employeeType_")=="Part Timer"
   and +vo("_map5B1_") == 0), "Basic salary should be greater than 0","_map5B1_");}
```
Five-phase logic: (1) `ctfd` sums 9 MAP5 salary fields into a total. (2) `erbyid` delegates to the total field's rules. (3) `remerr(true, ...)` unconditionally clears errors on both MAP4 and MAP5 basic salary fields. (4–9) Six `adderr` calls form a 2×3 matrix: division (MAP4, MAP5) × employee type (Permanent, FTC, Part Timer), each checking `+vo(...) == 0` for zero salary. `run_post_condition_fail: true`.

Key additions beyond base C-14:
- **`remerr(true, ...)` reset** — unconditionally clears errors before re-evaluating the matrix
- **`adderr` validation matrix** — 6 calls covering all dimension combinations, each with compound AND conditions
- **`touc()`** for case-insensitive division code matching (see [CL-12](#cl-12-touc-case-insensitive-comparison))
- **`+vo(...) == 0`** numeric zero-check — a variant of [CL-8](#cl-8-numeric-coercion-with-vo) for equality rather than comparison
- Targets **different fields** for MAP4 vs MAP5 divisions (`_map4B1_` vs `_map5B1_`)

**Frequency:** Observed in salary/payroll computations and complex categorization rules. Confirmed with symmetric MAP4 (Rule 52603) and MAP5 (Rule 18078) instances using identical structure.

### C-15. cf + fdd + asdff — Clear, Fill from Dropdown Data, and Save

**Description:** `fdd` (fillDropdownData) populates multiple destination fields from the linked data of a dropdown/lookup field. When the source dropdown is empty, `cf` clears the destinations. When it has a value, `fdd` fills the destinations from the dropdown's associated data columns. `asdff` saves all destinations unconditionally.

**When Used:** When selecting a value in a dropdown (e.g., an approval or lookup field) should auto-populate related fields (email, phone) from the dropdown's backing data table, and clearing the dropdown should clear those fields.

**Generic Template:**
```
on("change") and (
  cf(vo("<source_dropdown>") == "", "<dest1>", "<dest2>");
  fdd(vo("<source_dropdown>") != "", "<source_dropdown>", "<dest1>", "<dest2>");
  asdff(true, "<dest1>", "<dest2>")
)
```

**Real Example (Rule 51426):**
```
{on("change") and (cf(vo("_mEEApproval37_")=="","_mEEEmailID36_","_mEEMobileNumber64_");fdd(vo("_mEEApproval37_")!="","_mEEApproval37_","_mEEEmailID36_","_mEEMobileNumber64_");asdff(true,"_mEEEmailID36_","_mEEMobileNumber64_"))}
```
When the MEE Approval dropdown is empty, clear email and mobile fields. When it has a value, `fdd` fills email and mobile from the dropdown's associated data. Always save both fields. `execute_on_fill: true`, `run_post_condition_fail: false`.

**Key Observations:**
- **`fdd` is a new function** not previously documented — signature: `fdd(condition, source_dropdown_var, ...dest_vars)`. The source dropdown appears as the second parameter, and destinations follow. `fdd` presumably reads columnar data associated with the dropdown option and maps it to destination fields by position
- `cf` and `fdd` use **opposite conditions** (empty vs non-empty) — standard empty-guard pattern (see [CL-1](#cl-1-opposite-conditions-empty-vs-non-empty-guard))
- `asdff(true, ...)` is unconditional since exactly one of `cf` or `fdd` always fires
- Wrapped in `on("change")` to fire only when the dropdown selection changes
- Similar to `ctfd` for value derivation, but `fdd` derives from the dropdown's **backing data table** rather than from a specified literal or field expression

**Frequency:** Rare. Observed for dropdown-linked data population (approval → contact details).

### C-17. ctfd + cwd — Concatenate Multiple Fields with Delimiter

**Description:** `ctfd` derives a value by using `cwd` (concatenateWithDelimiter) to join multiple field values with a delimiter string (e.g., `", "`). The concatenated result is written to a destination field. `cwd` is a helper function that produces a single string from N field values, skipping empty values.

**When Used:** Summary/display fields that need to show a comma-separated (or otherwise delimited) list of values collected across multiple source fields (e.g., consolidating category selections, names, or codes from separate fields into one readable string).

**Generic Template:**
```
ctfd(true, cwd("<delimiter>", vo(<field1>), vo(<field2>), ..., vo(<fieldN>)), <dest>)
```

**Real Example (Rule 12432):**
```
{ctfd(true,cwd(", ",vo(61138),vo(61144),vo(61150),vo(61156),vo(61162)),61271)}
```
Concatenates the values of 5 fields (61138, 61144, 61150, 61156, 61162) using `", "` as the delimiter and writes the result to field 61271. The condition is `true` — always fires. Uses numeric field IDs. `run_post_condition_fail: true`.

**Key Observations:**
- **`cwd` (concatenateWithDelimiter)** — new function. Signature: `cwd(delimiter, value1, value2, ..., valueN)`. The first argument is the delimiter string, followed by N values to join
- `cwd` is nested **inside** `ctfd` as the source value parameter — `ctfd` handles the condition and destination, `cwd` handles the value construction
- Uses `vo()` calls for each source field — reads live field values
- No `asdff` — display-only derivation
- The `true` condition means this fires unconditionally on every evaluation

**Frequency:** Uncommon but recurring. 5 confirmed instances (Rules 12432, 12566, 12561, 12571, 12576) — all concatenating 5 numeric-ID fields with `", "` delimiter and unconditional `true` condition.

### C-18. ctfd + concat + cntns — Aggregate Multi-Field Status Derivation

**Description:** Multiple field values are aggregated using `concat()` into a single string, then `cntns()` (contains) checks are applied to determine the aggregate status. Based on whether the concatenated string contains "Yes", "No", or "NA", a status value is derived via `ctfd`. This implements a "majority/presence logic" — if ANY source contains "Yes" AND any contains "No" or "NA", the aggregate is "Yes" (mixed → affirming); if NONE contain "Yes", the aggregate is "No" or "NA".

**When Used:** Roll-up/summary fields that derive an aggregate status from multiple independent Yes/No/NA sub-fields (e.g., "Overall Compliance Status" derived from 7 individual compliance checks). The aggregate logic detects the presence of specific values in the combined string rather than checking each field individually.

**Generic Template (with local variable):**
```
concatenatedVal=concat(vo(<field1>), vo(<field2>), ..., vo(<fieldN>));
(((cntns("Yes", concatenatedVal) and cntns("No", concatenatedVal))
  or (cntns("Yes", concatenatedVal) and cntns("NA", concatenatedVal)))
 and ctfd(true, "Yes", <dest>))
or (((not cntns("Yes", concatenatedVal) and not cntns("No", concatenatedVal)))
 and ctfd(true, "NA", <dest>))
or (((not cntns("Yes", concatenatedVal) and cntns("No", concatenatedVal)))
 and ctfd(true, "No", <dest>))
or (((not cntns("Yes", concatenatedVal) and not cntns("NA", concatenatedVal)))
 and ctfd(true, "No", <dest>))
```

**Real Example — With Local Variable (Rule 12441):**
```
{concatenatedVal=concat(vo(61187),vo(61252),vo(61195),vo(61210));(((cntns("Yes",concatenatedVal) and cntns("No",concatenatedVal)) or (cntns("Yes",concatenatedVal) and cntns("NA",concatenatedVal))) and ctfd (true,"Yes",61268)) or (((not cntns("Yes",concatenatedVal) and not cntns("No",concatenatedVal))) and ctfd(true,"NA",61268)) or (((not cntns("Yes",concatenatedVal) and cntns("No",concatenatedVal))) and ctfd(true,"No",61268)) or (((not cntns("Yes",concatenatedVal) and not cntns("NA",concatenatedVal))) and ctfd(true,"No",61268))}
```
Concatenates 4 sub-status fields into a variable `concatenatedVal`, then applies 4-branch logic:
1. If contains "Yes" AND (contains "No" OR "NA") → derive "Yes" (mixed = affirming)
2. If contains neither "Yes" nor "No" → derive "NA" (all NA)
3. If no "Yes" but has "No" → derive "No"
4. If no "Yes" and no "NA" → derive "No" (fallback)

**Real Example — With Inline concat (Rule 12352):**
```
{(((cntns("Yes",concat(vo(61255),vo(61256),vo(61257),vo(61258),vo(61259),vo(61260),vo(61265))) and cntns("No",concat(vo(61255),vo(61256),vo(61257),vo(61258),vo(61259),vo(61260),vo(61265)))) or (cntns("Yes",concat(...)) and cntns("NA",concat(...)))) and ctfd (true,"Yes",61195)) or (((not cntns("Yes",concat(...)) and not cntns("No",concat(...)))) and ctfd(true,"NA",61195)) or (((not cntns("Yes",concat(...)) and cntns("No",concat(...)))) and ctfd(true,"No",61195)) or (((not cntns("Yes",concat(...)) and not cntns("NA",concat(...)))) and ctfd(true,"No",61195));erbyid(true,61187)}
```
Same 4-branch logic but with 7 source fields concatenated inline (no local variable). Ends with `erbyid(true, 61187)` to delegate to another field's rules after deriving the aggregate status.

**Key Observations:**
- **`concat()` function** — concatenates field values into a single string for substring checking. Signature: `concat(value1, value2, ..., valueN)`. Unlike `cwd`, no delimiter is specified (values are joined directly)
- **Local variable assignment** — `concatenatedVal=concat(...)` assigns the concatenated result to a reusable variable, avoiding repeated `concat()` calls. This is a significant structural pattern (see [CL-14](#cl-14-local-variable-assignment))
- **`cntns()` for presence detection** — checks if any source field contributed a specific value by searching the concatenated string
- **`not cntns()` for absence** — uses `not` function for negation (see [CL-13](#cl-13-not-function-for-condition-negation))
- The logic prioritizes "Yes" — if ANY source has "Yes" and there's at least one dissenter ("No" or "NA"), the aggregate is still "Yes" (affirming bias)
- Two implementation styles: **local variable** (Rule 12441, 4 fields) vs **inline concat** (Rule 12352, 7 fields). The inline style repeats the `concat()` call in every `cntns()` check, which is verbose but avoids variable overhead
- `erbyid` delegation at the end (Rule 12352) chains this aggregate status into further rule processing
- Uses numeric field IDs throughout
- `run_post_condition_fail: true`

**Frequency:** Observed in multi-field aggregate status derivation. At least 2 instances confirmed.

### C-19. ctfd with "NA" Default for Multiple Fields

**Description:** A simplified single-branch pattern where `ctfd` writes the literal "NA" to multiple destination fields when a condition is met. This is the minimal form of the "NA" default derivation seen in [C-11](#c-11-ctfdna--minvi--mvi--mm--mnm--hide-with-default-value-instead-of-clear), without any visibility or mandatory management.

**When Used:** When a parent field's value (e.g., "No") means several child fields are not applicable, and they should be set to "NA" rather than cleared. No visibility changes — the fields remain visible but show "NA".

**Generic Template:**
```
ctfd(vo(<parent>)=="<inactive_val>","NA",<field1>,<field2>,<field3>)
```

**Real Example (Rule 12452):**
```
{ctfd(vo(61249)=="No","NA",61177,61178,61179)}
```
When field 61249 is "No", write "NA" to three destination fields (61177, 61178, 61179) in a single `ctfd` call. Uses numeric field IDs. No `asdff`, no visibility changes, no enable/disable. `run_post_condition_fail: true`.

**Key Observations:**
- **Multi-destination ctfd** — writes the same value ("NA") to 3 fields in one call
- Simplest possible "NA" derivation — no branching, no visibility, no mandatory management
- Distinct from `cf` (clearing) — "NA" is a sentinel value, not empty
- No `asdff` — display-only (or saved on form submit)
- Often paired with other rules on the same parent field that handle the "Yes" branch

**Frequency:** Observed in forms with NA/Not-Applicable sentinel value requirements.

---

## Conditional Logic Patterns

### CL-1. Opposite Conditions (Empty vs Non-Empty Guard)

**Description:** The same source field is tested for empty and non-empty. The empty branch triggers `cf`+`asdff`+`dis`; the non-empty branch triggers `en`. This ensures mutual exclusivity.

**When Used:** Date pair dependencies, sequential field requirements.

**Generic Template:**
```
dis(vo("<src>") == "", "<dest>");
en(vo("<src>") != "", "<dest>");
cf(vo("<src>") == "", "<dest>");
asdff(vo("<src>") == "", "<dest>");
```

**Real Examples:** Rules 28311, 28310.

**Frequency:** Common.

### CL-2. Multi-Branch on Dropdown Value

**Description:** Multiple `ctfd` and/or `cf` calls, each with a different `vo("<src>") == "<value>"` condition, targeting the same destination field. Each branch sets a different literal or clears the field. Typically followed by an unconditional `asdff(true, ...)` and `rffdd(true, ...)`.

**When Used:** When the parent dropdown has 3+ options and the behavior for the child field differs per option.

**Generic Template:**
```
ctfd(vo("<src>") == "<val_A>", "<literal_A>", "<dest>");
ctfd(vo("<src>") == "<val_B>", "<literal_B>", "<dest>");
cf(vo("<src>") == "<val_C>", "<dest>");
asdff(true, "<dest>");
rffdd(true, "<dest>");
```

**Real Example (Rule 48617):**
```
ctfd(vo("_customertypedrob_")=="P001-Dealer", "TR - Trade", "_distributionchanneldrob_");
ctfd(vo("_customertypedrob_")=="P016-Retailer", "TR - Trade", "_distributionchanneldrob_");
cf(vo("_customertypedrob_")=="P011-Non-Trade Customer", "_distributionchanneldrob_");
asdff(true, "_distributionchanneldrob_");
rffdd(true, "_distributionchanneldrob_");
```

**Variant — Value Grouping via OR Conditions (Rule 83739):** Multiple source values are OR'd together in a single `ctfd` condition to map to the same output value. This is a "many-to-one" mapping — collapsing sub-categories into parent categories:
```
{on ("load") and ctfd(vo("_selectGrade82_")=="A1" or vo("_selectGrade82_")=="A2" or vo("_selectGrade82_")=="A3","A1","_temp92_");
 ctfd(vo("_selectGrade82_")=="B1" or vo("_selectGrade82_")=="B2" or vo("_selectGrade82_")=="B3","B1","_temp92_");}
```
Sub-grades A1/A2/A3 are grouped into parent grade "A1", and B1/B2/B3 into "B1". Key traits:
- **OR conditions** — multiple values per branch, unlike typical CL-2 where each branch checks one value
- **Many-to-one mapping** — 6 values collapse into 2 output groups (vs the typical 1:1 code mapping)
- **`on("load")`** — fires on form load to compute the grouped grade for display/routing
- No `asdff` — display-only derivation
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Variant — Dropdown with "Other" Free-Text Option (Rules 36921, 36922, 36923):** When a dropdown includes an "Other" option alongside predefined values, the rule uses multiple `ctfd` calls to echo predefined values into a display field, combined with **dual `cf` calls** that handle the bidirectional clearing: one `cf` clears the display field when "Other" is selected (to enable free-text entry in a separate field), and the opposite `cf` clears the free-text "Other" field when a predefined option is selected. No `asdff` — display-only derivation:
```
{ctfd(vo("_franchisefees_")=="Rs.50,000","Rs.50,000","_o1a_");
 ctfd(vo("_franchisefees_")=="Rs.1,00,000","Rs.1,00,000","_o1a_");
 ctfd(vo("_franchisefees_")=="Rs.1,50,000","Rs.1,50,000","_o1a_");
 ctfd(vo("_franchisefees_")=="Rs.2,00,000","Rs.2,00,000","_o1a_");
 ctfd(vo("_franchisefees_")=="Rs.75,000","Rs.75,000","_o1a_");
 cf(vo("_franchisefees_")=="Other","_o1a_");
 cf(vo("_franchisefees_")!="Other","_o1_");}
```
Five `ctfd` calls echo the predefined fee values into the `_o1a_` display field. Two `cf` calls handle the "Other" toggle: (1) When source is "Other", clear the display field `_o1a_` (since the user will type a custom value in the free-text field `_o1_`). (2) When source is NOT "Other", clear the free-text field `_o1_` (since a predefined value is selected and displayed in `_o1a_`).

Key traits:
- **Self-echo ctfd** — the source value and the derived value are identical strings (e.g., `ctfd(vo(...)=="Rs.50,000","Rs.50,000","_o1a_")`). The ctfd effectively copies the dropdown value to the display field verbatim
- **Bidirectional cf** — two `cf` calls with **opposite conditions** clear **different target fields**: `cf(=="Other", display_field)` and `cf(!="Other", freetext_field)`. This ensures only one field has a value at a time
- **No `asdff`** — display-only derivation (`execute_on_fill: true`, `run_post_condition_fail: false`)
- **Three confirmed instances** in the same form with identical structure: franchise fees (Rule 36921 → `_o1a_`/`_o1_`), brand cost (Rule 36922 → `_o2a_`/`_o2_`), security deposit (Rule 36923 → `_o3a_`/`_o3_`). Each has 5–9 predefined values plus the "Other" toggle
- Rule 36923 has 9 predefined values (Rs.50,000 through Rs.10,00,000) — the largest observed instance
- The naming convention `_oNa_` (auto-display) and `_oN_` (free-text Other) suggests a consistent form pattern for fee/cost fields

**Frequency:** Observed in fee/cost configuration forms with "Other" free-text option. 3 confirmed instances.

**Frequency:** Common.

### CL-3. cf(true, ...) Inside or-Branch

**Description:** `cf` is called with a literal `true` condition inside an `or`-chained branch. The branch itself provides the condition gating (the `or` only evaluates the branch when the preceding conditions are false). This is a structural idiom for "always clear within this branch."

**When Used:** Branching visibility patterns where one branch shows a field group and must always clear the other group.

**Real Example (Rule 29074):**
```
mvi(vo("_aadhques_")=="Yes", "_digilockerAadharAuthorize12_")
  and cf(true, "_aadhfront_", "_aadhback_")
  and minvi(true, "_aadhfront_", "_aadhback_")
```

**Frequency:** Observed in `or`-chained visibility patterns.

### CL-4. asdff(true, ...) and rffdd(true, ...) — Unconditional Save/Refresh

**Description:** `asdff` and/or `rffdd` are called with `true` as the condition, meaning they always fire regardless of which branch was taken. This is used after conditional `ctfd`/`cf` calls to ensure the destination field is always saved and/or refreshed.

**When Used:** After branching `ctfd`/`cf` logic, to guarantee persistence and dropdown refresh.

**Generic Template:**
```
ctfd(<cond_A>, ...);
cf(<cond_B>, ...);
asdff(true, "<dest>");
rffdd(true, "<dest>");
```

**Real Examples:** Rules 48617, 48618.

**Frequency:** Very common.

### CL-5. ctfd Nested as adderr Condition

**Description:** `ctfd` is used as the **condition parameter** of `adderr`. The `ctfd` call evaluates its own condition, sets a value in a destination field, and returns a truthy/falsy result that `adderr` then uses to decide whether to add the error. This is an advanced pattern combining derivation and validation in a single nested expression.

**When Used:** Validation rules where the same comparison determines both the derived status ("Valid"/"Invalid") and whether an error message should be shown. The nesting avoids duplicating the comparison logic.

**Generic Template:**
```
adderr(ctfd(<numeric_comparison>, "<Invalid_literal>", "<status_dest>"),
       "<error_message>", "<error_field>", "<status_dest>")
or (ctfd(true, "Valid", "<status_dest>") and remerr(true, "<error_field>", "<status_dest>"))
```

**Real Example (Rule 27659):**
```
adderr(ctfd(+vo("_NewCommissionPercent_") >= +vo("_OldCommissionPercent_"),"Invalid","_commissionstatus_"),
       "New Commission should be less than old Commission","_NewCommissionPercent_","_commissionstatus_")
or (ctfd(true,"Valid","_commissionstatus_") and remerr(true,"_NewCommissionPercent_","_commissionstatus_"))
```
When new commission >= old commission: ctfd sets status to "Invalid" AND returns truthy, so adderr adds the error. Otherwise: ctfd falls through (returns falsy), the `or` branch fires, setting status to "Valid" and removing errors.

**Note:** The `ctfd` inside `adderr` does double duty: it both derives the status value AND acts as the conditional gate for the error. This is possible because `ctfd` returns a value (the condition result) that can be consumed by the outer function.

**Frequency:** Observed in commission validation rules (Rules 27658, 27659, 27652).

### CL-6. `and false` Short-Circuit Terminator

**Description:** A branch ends with `and false` to force the entire branch to evaluate as falsy, causing execution to fall through to the next `or` branch. The preceding functions in the `and` chain still execute (side effects fire), but the branch as a whole fails.

**When Used:** When a branch needs to perform side effects (like `ctfd` to set a value and `remerr` to remove errors) but should NOT prevent the next `or` branch from being evaluated. Essentially a "do this, then continue" pattern.

**Generic Template:**
```
(<guard_condition> and (
  <desired_outcome>
  or (ctfd(true, "<value>", "<dest>") and remerr(true, "<field>") and false)
))
```

**Real Example (Rule 27659, partial):**
```
(vo("_NewCommissionExpression_") == vo("_OldCommissionExpression_")
  or (ctfd(true,"Valid","_commissionstatus_") and remerr(true,"_NewCommissionPercent_","_commissionstatus_") and false))
```
If the expressions are equal, the branch succeeds (short-circuit). If not equal, ctfd sets "Valid" and remerr clears errors (side effects), but `and false` forces the branch to fail, allowing the outer validation logic to proceed.

**Frequency:** Observed in complex validation rules with multiple fallthrough paths.

### CL-7. Multi-Branch Multi-Destination ctfd Matrix

**Description:** Multiple `ctfd` calls form a matrix of conditions × destinations, where each combination of condition values maps to specific values being written to specific destination fields. Each ctfd targets a potentially different destination with a potentially different source value.

**When Used:** Routing/assignment rules where a categorization field (e.g., meeting type) determines which manager/assignee fields get which values. Each branch of the categorization leads to a different assignment pattern across multiple destinations.

**Generic Template:**
```
on("change") and (
  ctfd(<condition_A>, <value_1>, "<dest_1>", "<dest_2>", "<dest_3>");
  ctfd(<condition_B>, vo("<source_field>"), "<dest_2>");
  ctfd(<condition_B>, <value_1>, "<dest_1>");
  ctfd(<condition_B>, <value_1>, "<dest_3>");
  ctfd(<condition_C>, vo("<source_field>"), "<dest_3>");
  ctfd(<condition_C>, <value_1>, "<dest_1>");
  ctfd(<condition_C>, <value_1>, "<dest_2>");
  asdff(true, "<dest_1>")
)
```

**Real Example (Rule 48839):**
```
{on("change") and (
  ctfd(vo("_IsMeetingQue7_")=="In-Person" and vo("_LocQue8_")=="Restaurant Location",
       "sprt@manchtech.com","_compareL1Manager87InPerson_","_compareL1Manager87_","_compareL1Manager87AmIntroduction_");
  ctfd(vo("_IsMeetingQue7_")=="Away",vo("_Text1_"),"_compareL1Manager87_");
  ctfd(vo("_IsMeetingQue7_")=="Away","sprt@manchtech.com","_compareL1Manager87InPerson_");
  ctfd(vo("_IsMeetingQue7_")=="Away","sprt@manchtech.com","_compareL1Manager87AmIntroduction_");
  ctfd(vo("_IsMeetingQue7_")=="AM Introduction",vo("_Text1_"),"_compareL1Manager87AmIntroduction_");
  ctfd(vo("_IsMeetingQue7_")=="AM Introduction","sprt@manchtech.com","_compareL1Manager87InPerson_");
  ctfd(vo("_IsMeetingQue7_")=="AM Introduction","sprt@manchtech.com","_compareL1Manager87_");
  asdff(true,"_compareL1Manager87InPerson_")
)}
```
Three destination fields, three meeting types: each combination gets either a literal email or a field value. The first ctfd targets all three destinations with the same literal, while subsequent ctfds set individual destinations per condition.

**Key observations:**
- `ctfd` can accept **multiple destination fields** in a single call (first ctfd writes to 3 fields at once)
- `ctfd` can copy a **field value** via `vo()` as the source, not just literals
- Compound conditions using `and` (e.g., `vo("_IsMeetingQue7_")=="In-Person" and vo("_LocQue8_")=="Restaurant Location"`)

**Variant — Two-Dimensional Pricing Matrix with asdff (Rule 36303):** The multi-branch multi-destination pattern scales to a **two-dimensional condition grid** where each cell is defined by compound `and` conditions from **two** source fields. Each cell writes different literal values to **four** destination fields. This implements a full pricing/tariff lookup table:
```
{vo("_selType_") !="" and (
 ctfd(vo("_selType_") == "Zero Commission" and vo("_selDuration_") == "3 months",
      "One- Time Setup Fee: Rs. 1000/- + Rs. 3900 + 2.5% Transaction Charges + GST", "_subTotal_");
 ctfd(vo("_selType_") == "Zero Commission" and vo("_selDuration_") == "3 months",
      "Rs. 4900/-", "_subTotalCopy_");
 ctfd(vo("_selType_") == "Zero Commission" and vo("_selDuration_") == "3 months",
      "Rs. 5782/-", "_amountPayableCopy_");
 ctfd(vo("_selType_") == "Zero Commission" and vo("_selDuration_") == "3 months",
      "1", "_amtPayGST_");
 ctfd(vo("_selType_") == "Zero Commission" and vo("_selDuration_") == "6 months",
      "One- Time Setup Fee: Rs. 1000/- + Rs. 7200 + 2.5% Transaction Charges + GST", "_subTotal_");
 ... (6 months and 12 months variants for Zero Commission)
 ctfd(vo("_selType_") == "Subscription + Commission" and vo("_selDuration_") == "3 months",
      "One- Time Fee: Rs. 1000/- + Rs. 1500 + 7.5% Commission on Orders = Rs. 2500/- + GST", "_subTotal_");
 ... (3/6/12 months variants for Subscription + Commission)
 ctfd(vo("_selType_") == "Only Commission",
      "One Time Setup Fee: Rs. 1000/- + 12.5% Commissions on Orders (No Monthly Fees) = Rs. 1000/- + GST", "_subTotal_");
 ctfd(vo("_selType_") == "Only Commission","Rs. 1180/-", "_amountPayableCopy_");
 ctfd(vo("_selType_") == "Only Commission","Rs. 1000/-", "_subTotalCopy_");
 ctfd(vo("_selType_") == "Only Commission","1180", "_amtPayGST_");
 asdff(vo("_brand_") !="" and vo("_selType_") != "", "_amtPay_","_amtPayGST_")
)}
```
A 3×3+1 pricing grid: 3 subscription types × 3 durations = 9 cells (plus "Only Commission" which is duration-independent = 1 extra cell). Each cell writes 4 destination fields: subtotal description, subtotal amount, amount payable, and GST amount — all hardcoded literal values.

Key differences from base CL-7:
- **Two-dimensional compound condition** — `vo("_selType_") == X and vo("_selDuration_") == Y` creates a grid, vs single-dimension in base CL-7
- **Outer guard** — `vo("_selType_") != ""` wraps the entire expression, preventing evaluation when selection type is empty
- **Four destination fields per cell** — `_subTotal_`, `_subTotalCopy_`, `_amountPayableCopy_`, `_amtPayGST_`
- **asdff with compound condition** — `asdff(vo("_brand_") !="" and vo("_selType_") != "", ...)` saves two fields only when both brand and type are selected (introduces a third source field)
- **"Only Commission" row** — one type is duration-independent (4 ctfd calls without duration condition), breaking the perfect grid
- **~28 ctfd calls** in total — larger than the base CL-7 example but smaller than the 74-call code mapping in I-1
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Observed in assignment/routing rules and pricing/tariff configuration forms.

### CL-8. Numeric Coercion with +vo()

**Description:** The `+` prefix operator is used before `vo()` to coerce the field value from string to number for numeric comparison. Without this, the comparison would be lexicographic (string comparison).

**When Used:** When comparing commission percentages, amounts, or other numeric field values that are stored as strings but need numeric ordering.

**Generic Template:**
```
+vo("<field_A>") < +vo("<field_B>")
+vo("<field_A>") >= +vo("<field_B>")
```

**Real Example (Rule 27652, partial):**
```
remerr(+vo("_oldpercomm_") < +vo("_newpercomm_"), "_newpercomm_")
```
Compares old and new commission percentages numerically. The `+` prefix ensures `"10" < "9"` evaluates correctly as `10 < 9` → false, rather than the string comparison `"10" < "9"` → true.

**Real Examples:** Rules 27652, 27658, 27659.

**Variant — Complement Arithmetic (Rules 12378, 12372, 12382, 12380):** `+vo()` coercion is used inside arithmetic expressions, not just comparisons. The `100 - +vo(field)` pattern computes a percentage complement:
```
ctfd((vo(61259)=="Yes" and vo(61204)),100 - +vo(61204),61205)
```
Derives `100 - field1_value` into field2 — the remainder of a percentage split. The `+` prefix on `vo(61204)` ensures the subtraction is numeric, not string concatenation. See also [C-16](#c-16-ctfd--cf--dis--en--mm--mnm--tri-state-percentage-split-with-complement-calculation).

**Frequency:** Common in validation rules involving numeric fields.

### CL-9. Opposite-Condition ctfd — Default Value with Override

**Description:** Two `ctfd` calls with **opposite conditions** (empty vs non-empty) target the **same destination field**, followed by unconditional `asdff`. When the source is empty, a default/fallback value is written; when the source has a value, its actual value is copied. This is a "default value with override" pattern.

**When Used:** When a field should always have a value — either the user-provided value (if present) or a system default (if empty). Common for email CC fields, fallback assignees, etc.

**Generic Template:**
```
ctfd(vo("<source>") == "", "<default_value>", "<dest>");
ctfd(vo("<source>") != "", vo("<source>"), "<dest>");
asdff(true, "<dest>")
```

**Real Example (Rule 48878):**
```
{ctfd(vo("_alternateOwnerEmailId20_")=="","sprt@manchtech.com","_alternateOwnerEmailIdCC_");
 ctfd(vo("_alternateOwnerEmailId20_")!="",vo("_alternateOwnerEmailId20_"),"_alternateOwnerEmailIdCC_");
 asdff(true, "_alternateOwnerEmailIdCC_")}
```
If alternate owner email is empty, set CC to the default "sprt@manchtech.com". If it has a value, copy that value to CC. Always save. The `asdff(true, ...)` ensures the destination is persisted regardless of which branch fired.

**Key Observations:**
- The two `ctfd` conditions are **mutually exclusive** (== "" vs != ""), ensuring exactly one fires
- The second `ctfd` uses `vo()` as the source value (field copy), while the first uses a literal string (default)
- `asdff` uses `true` since exactly one of the two ctfd calls will always fire
- `execute_on_fill: true` — runs on form load to set the default immediately

**Variant — Multi-Field Parallel Self-Default (Rule 32327):** Multiple `ctfd` calls each check their **own** destination field for emptiness and write the same default value. A single unconditional `asdff` saves all fields at once. This is a "parallel initialization" pattern where several fields independently get a default if empty:
```
{on("change") and (
  ctfd(vo("_compareL1Manager87_")=="","sprt@manchtech.com","_compareL1Manager87_");
  ctfd(vo("_compareL1Manager87InPerson_")=="","sprt@manchtech.com","_compareL1Manager87InPerson_");
  ctfd(vo("_compareL1Manager87AmIntroduction_")=="","sprt@manchtech.com","_compareL1Manager87AmIntroduction_");
  asdff(true,"_compareL1Manager87_","_compareL1Manager87InPerson_","_compareL1Manager87AmIntroduction_")
)}
```
Three manager email fields each self-default to `"sprt@manchtech.com"` if empty. Unlike the base CL-9 pattern, there is **no override branch** (no `ctfd(vo(...)!="", ...)`) — only the default path. The `asdff(true, ...)` saves all three unconditionally since at least one default will always fire. `run_post_condition_fail: true`.

**Variant — Value Echo with Opposite Clear (Rules 32900, 32899):** A specific use of opposite conditions where one branch echoes the source value as a literal into the destination, and the opposite branch clears it (writes `""`). Wrapped in `on("change")` with unconditional `asdff`:
```
{on("change") and (ctfd(vo("_yesNoNone2_") == "None", "None", "_none2_");ctfd(vo("_yesNoNone2_") != "None", "", "_none2_");asdff(true, "_none2_"))}
```
When the selection is "None", write "None" to a helper field. When the selection is anything else, clear the helper field. Always save. This captures the "None" choice as a separate stored value, effectively isolating a specific selection for downstream logic. `execute_on_fill: true`, `run_post_condition_fail: true`.

**Frequency:** Observed in email/assignee routing rules and yes/no/none selection fields.

### CL-12. touc() — Case-Insensitive Comparison via To-Uppercase

**Description:** The `touc()` (to uppercase) function wraps `vo()` to convert a field value to uppercase before comparison. This enables **case-insensitive** string matching in conditions, since both sides are uppercased before comparison.

**When Used:** Two main scenarios:
1. **Name matching validation** — comparing user-entered names across different sources (e.g., bank account holder vs Aadhaar name) where case may differ
2. **Code/category matching** — comparing division codes or category values where the stored case may vary

**Generic Template — Equality Check:**
```
touc(vo("<field_A>")) == touc(vo("<field_B>"))
```

**Generic Template — Constant Comparison:**
```
touc(vo("<field>")) == "<UPPERCASE_CONSTANT>"
```

**Real Example — Name Matching (Rule 33653):**
```
adderr(... and touc(vo("_candidateName_")) != touc(vo("_nameOfaccountholder_")),
       "Name as per Bank and Aadhaar not matching","_nameOfaccountholder_");
remerr(touc(vo("_candidateName_")) == touc(vo("_nameOfaccountholder_")),"_nameOfaccountholder_");
```
Compares candidate name and account holder name case-insensitively. Error added when mismatch, removed when match.

**Real Example — Division Code Matching (Rule 18078):**
```
adderr((touc(vo("_divisionComp_"))=="MAP4" and vo("_employeeType_")=="Permanent"
  and +vo("_map4B1_") == 0), "Basic salary should be greater than 0","_map4B1_");
```
Compares the division code against "MAP4" case-insensitively, in case the stored value uses different casing.

**Key Observations:**
- `touc()` wraps `vo()`, not the other way around — `touc(vo("_field_"))` reads the value then uppercases it
- When comparing two fields, **both** sides must use `touc()` for true case-insensitive comparison
- When comparing to a constant, the constant should be uppercase (e.g., `"MAP4"`, `"MAP5"`)
- Often used inside `adderr`/`remerr` conditions for validation rules

**Variant — touc() as ctfd Value for In-Place Self-Uppercase (Rule 36714):** `touc()` is used not in a condition but as the **value parameter** of `ctfd`, writing the uppercased field value back to the **same field**. This is an in-place self-transformation:
```
{minvi(vo("_panHolderName_")=="","_panHolderName_");
 mvi(vo("_panHolderName_")!="","_panHolderName_");
 ctfd(vo("_panHolderName_")!="",touc(vo("_panHolderName_")),"_panHolderName_");
 erbyid(vo("_panHolderName_") != "", "_BankBeneficiary_","_bankValidationStatus33_")}
```
When PAN holder name is non-empty: (1) make visible, (2) uppercase the value in-place via `ctfd(condition, touc(vo("field")), "field")`, (3) delegate to bank beneficiary and validation status fields via `erbyid`. Key traits:
- **`touc()` in value position** — `ctfd(cond, touc(vo("_field_")), "_field_")` — distinct from CL-12's usage in conditions. The field's own value is read, uppercased, and written back
- **Self-referencing ctfd** — source and destination are the **same field** (`_panHolderName_`)
- **`erbyid` with 2 target fields** — `erbyid(cond, "field1", "field2")` delegates to multiple fields in a single call (see [C-14](#c-14-ctfd--erbyid--derive-then-delegate))
- Combined with `minvi`/`mvi` visibility toggle on the same field
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Observed in KYC name matching and payroll division code validation rules.

### CL-13. not() Function for Condition Negation

**Description:** The `not()` function wraps a boolean expression to negate its result. This is used when the negation cannot be expressed with a simple `!=` operator — most commonly when negating `cntns()` (contains) checks. `not(cntns(...))` is the complement of `cntns(...)`, returning true when the value does NOT contain the search string.

**When Used:** Two main scenarios:
1. **Multi-select field negation** — `cntns()` checks whether a multi-value field includes a keyword; `not(cntns(...))` is needed for the opposite condition since `!=` doesn't apply to substring matching
2. **Complex boolean negation** — when the positive condition involves a function call that can't be directly inverted with `!=`

**Generic Template:**
```
mvi(cntns("<option>", vo("<field>")), "<dest>");
minvi(not(cntns("<option>", vo("<field>"))), "<dest>");
```

**Real Example (Rule 34566):**
```
{mvi(cntns("Yes", vo("_analternatesource_")),"_alternateSource31_");
 minvi(not(cntns("Yes", vo("_analternatesource_"))),"_alternateSource31_");}
```
When the field contains "Yes": show the field. When it does NOT contain "Yes": hide it. The `not()` wraps the entire `cntns()` call.

**Real Example — Multi-Product (Rule 51320):**
```
cf(not(cntns("RCU-Small", vo("_pmxsize_"))), "_pleaseEnterRCUSmallQuantitiy63_");
mnm(not(cntns("PMX 4V", vo("_pmxsize_"))), "_pmxtype_");
```
When the multi-select does NOT contain "RCU-Small", clear the RCU-Small quantity field. When it does NOT contain "PMX 4V", make the PMX type field non-mandatory.

**Key Observations:**
- `not()` wraps the entire function call: `not(cntns(...))`, NOT `cntns(not(...))`
- Used as the direct complement of `cntns()` — where `cntns()` is the positive condition, `not(cntns())` is the negative
- Functionally equivalent to `!= true` on the result, but syntactically cleaner
- Always paired with the positive `cntns()` form on the same field — the two conditions form a complete partition (contains OR not-contains)
- Distinct from `!=` comparisons: `!=` tests value inequality, while `not(cntns(...))` tests substring non-membership

**Frequency:** Observed in multi-select/multi-value field visibility rules. Common wherever `cntns()` is used for conditions.

### CL-14. Local Variable Assignment in Expressions

**Description:** A local variable is assigned at the start of the expression using `varName=<expression>` syntax (no `var` keyword, no quotes around the variable name). The variable can then be referenced by name throughout the rest of the expression, avoiding repeated evaluation of the same sub-expression.

**When Used:** When the same computed value (typically `concat()` of multiple fields) is referenced multiple times in subsequent `cntns()` checks. The variable avoids recalculating the concatenation for each check.

**Generic Template:**
```
<varName>=<expression>;
<rest of expression using varName>
```

**Real Example (Rule 12441):**
```
{concatenatedVal=concat(vo(61187),vo(61252),vo(61195),vo(61210));
 (((cntns("Yes",concatenatedVal) and cntns("No",concatenatedVal)) ...) and ctfd(true,"Yes",61268))
 or ...}
```
`concatenatedVal` is assigned the result of `concat()` on 4 fields. It is then used in 8 subsequent `cntns()` calls within the branching logic. Without the variable, each `cntns()` would need to repeat the full `concat(vo(...),vo(...),vo(...),vo(...))` call.

**Key Observations:**
- **No declaration keyword** — just `name=expr`, not `var name = expr`
- The variable name is **unquoted** and follows standard identifier rules
- **Scope** — the variable is available for the rest of the expression after assignment
- Commonly used with `concat()` to cache a concatenated string for multiple `cntns()` checks
- Contrast with Rule 12352 which uses **inline concat** (repeating the concat call 8+ times) instead of a variable — both approaches work, but the variable is more maintainable
- The semicolon after the assignment separates it from the subsequent logic

**Variant — Literal String Variables for Text Distribution (Rule 12386):** Local variables can hold **literal text strings** (not computed values) that are then derived into multiple fields via `ctfd`. This is used to split a long paragraph across several fields:
```
{v1="In the event of any breach of this clause or any terms of this Term Sheet, ";
 v2="except in case of a force majeure event, the Asset Partner(s) shall be liable ";
 v3="to pay to the Service Provider a break-away fee of Rs 50000 ";
 v4="(Rupees Fifty Thousand Only).";
 (ctfd(vo(61250)=="Yes",v1,61261) and ctfd(true,v2,61262) and ctfd(true,v3,61263)
  and ctfd(true,v4,61264) and mm(true,61184,61251,61261,61262,61263,61264)
  and mvi(true,61184))
 or (cf(vo(61250)=="No",61251,61261,61262,61263,61264)
  and mnm(true,61184,61251,61261,61262,61263,61264) and minvi(true,61184))}
```
Four variables (v1–v4) each hold a sentence fragment. The "Yes" branch derives each fragment into a separate destination field, then makes all fields visible and mandatory. The "No" branch clears all fields, makes them non-mandatory, and hides them. Key traits:
- **Literal string assignment** — `v1="text"` (not `v1=concat(...)` or `v1=vo(...)`) — the value is a hardcoded string
- **`and`-chained ctfd with `true`** — only the first `ctfd` has the real condition (`vo(61250)=="Yes"`); subsequent `ctfd(true,...)` calls use `true` because the `and` chain short-circuits if the first fails (see note below)
- Combines **text derivation + visibility + mandatory** in a single `or`-branched expression
- Uses **numeric field IDs** (61250, 61261, etc.)
- `execute_on_fill: false`, `run_post_condition_fail: true`

**Note on `and`-chained `true` conditions:** When multiple `ctfd(true, ...)` calls are chained with `and` after a guarded first call (`ctfd(condition, ...)`), the `true` conditions are safe because the `and` operator short-circuits — if the first call's condition fails, the entire `and` chain is skipped. This is an alternative to repeating the same condition in every `ctfd` call and is commonly used when the derived values are unrelated (different variables, different destinations) but share the same activation condition.

**Frequency:** Rare. Observed when the same sub-expression would be repeated many times, or when literal text strings need to be distributed across multiple fields.

### CL-15. remerr(+condition) — Plus-Prefix Error Removal Modifier

**Description:** The `remerr` function's condition parameter is prefixed with `+` (e.g., `remerr(+vo(...)!="val", ...)`). Unlike `+vo()` for numeric coercion ([CL-8](#cl-8-numeric-coercion-with-vo)), the `+` here is applied to the **entire condition expression** (including string comparisons like `!="Certificate of Incorporation"`), suggesting it is a `remerr`-specific modifier rather than numeric coercion.

**When Used:** Observed in multi-branch visibility rules (C-7b style) where each branch has paired `cf` and `remerr` calls. The `cf` uses a normal condition while the `remerr` for the same logic uses the `+` prefix. This may indicate a "sticky" or "force" error removal that prevents subsequent `adderr` from re-adding errors within the same evaluation cycle.

**Generic Template:**
```
cf(vo(<src>)!="<val>", <fields>);
remerr(+vo(<src>)!="<val>", <fields>);
```

**Real Example (Rule 34654, partial — one of 4 branches):**
```
{mvi(vo(102403)=="Certificate of Incorporation",102788,102803,103787);
 minvi(vo(102403)!="Certificate of Incorporation",102788,102803,103787);
 mm(vo(102403)=="Certificate of Incorporation",102788,102803);
 mnm(vo(102403)!="Certificate of Incorporation",102788,102803,103787);
 cf(vo(102403)!="Certificate of Incorporation",102788,102803,103787);
 remerr(+vo(102403)!="Certificate of Incorporation",102788,102803,103787);
 ... (3 more branches: GST Certificate, Shop and Establishment Certificate, Utility Bill)}
```
Four document-type branches, each with the full 6-function sextuple (mvi/minvi/mm/mnm/cf/remerr). The `remerr` calls all use `+` prefix on their conditions, while `cf`, `mvi`, `minvi`, `mm`, `mnm` use normal conditions.

**Key Observations:**
- The `+` appears **only on `remerr`** conditions — not on `cf`, `mvi`, or other functions in the same rule
- Applied to **string comparisons** (`!="Certificate of Incorporation"`), confirming this is NOT numeric coercion
- Appears consistently across all 4 branches in Rule 34654 — systematic usage, not a typo
- The `mm` targets a **subset** (2 fields) of the `mvi`/cf/remerr targets (3 fields) — not all visible fields are mandatory
- Uses numeric field IDs throughout
- `execute_on_fill: true`, `run_post_condition_fail: true`

**Frequency:** Observed in multi-branch document type selection rules. Distinct from numeric `+vo()` coercion.

### CL-10. ctfd("") as Conditional Clear Inside on("change")

**Description:** `ctfd` with an empty string `""` as the value is used inside `on("change")` to conditionally clear a field, paired with `asdff`. This is functionally equivalent to `cf` but uses `ctfd` instead (see also [AP-3](#ap-3-ctfd-with-empty-string-as-clear)).

**When Used:** When the clear operation is part of a change-triggered flow, often with compound conditions involving multiple source fields.

**Real Example — Compound AND+OR Condition (Rule 48885):**
```
{on("change") and (
  ctfd((vo("_IsMeetingQue7_")=="Away" or vo("_IsMeetingQue7_")=="AM Introduction")
    and vo("_moMCapturedCorrectly17_")=="Yes","","_compareL1Manager87_");
  asdff(true, "_compareL1Manager87_"))}
```
When meeting type is "Away" or "AM Introduction" AND MoM is captured correctly, clear the compare L1 manager field. The `asdff(true, ...)` always saves.

**Real Example — Simple Condition (Rule 48898):**
```
{on("change") and (ctfd(vo("_Discussion1_")!="Other","","_Other1_");asdff(vo("_Discussion1_")!="Other","_Other1_"))}
```
When discussion topic is NOT "Other", clear the "Other" text field and save. Note: here `asdff` has the **same condition** as `ctfd` (not `true`), meaning the save only fires when the field is being cleared.

**Key Observation:** The choice between `ctfd("", ...)` and `cf(...)` appears to be stylistic. Both achieve the same result (empty the field). The `ctfd` approach may be preferred when the same expression also contains `ctfd` calls that derive actual values (see [AP-3](#ap-3-ctfd-with-empty-string-as-clear)).

**Frequency:** Common in change-triggered clearing rules.

### CL-11. Multi-Source ctfd Convergence to Same Destination

**Description:** Multiple `ctfd` calls from **different source fields** all write the **same value** to the **same destination field**. Each ctfd has a condition based on a different source field, but the derived output is identical. This is effectively an OR-gate spread across independent source evaluations — if any source matches, the destination gets the value.

**When Used:** Aggregation/status fields that should show a result (e.g., "Not Matched") whenever **any** of several independent checks fail. Each check is its own ctfd rather than combining them into a single compound condition, which may be for readability or because the checks were added incrementally.

**Generic Template:**
```
ctfd(vo("<source_field_A>") == "<trigger_val>", "<derived_value>", "<dest>");
ctfd(vo("<source_field_B>") == "<trigger_val>", "<derived_value>", "<dest>");
```

**Real Example (Rule 69503):**
```
{ctfd(vo("_PANmatchStatus_") == "Mismatch", "Not Matched", "_nameMatch14_");
 ctfd(vo("_bankNameMatchStatus_") == "Mismatch", "Not Matched", "_nameMatch14_");}
```
If PAN match status is "Mismatch", set name match to "Not Matched". If bank name match status is "Mismatch", also set it to "Not Matched". Both converge on the same destination with the same value. `execute_on_fill: true` — runs on form load to compute the aggregate status.

**Key Observations:**
- Different from [CL-7](#cl-7-multi-branch-multi-destination-ctfd-matrix) (which maps conditions to **different** destinations) — here all conditions converge on the **same** destination
- Different from [CL-2](#cl-2-multi-branch-on-dropdown-value) (which branches on the same source field) — here each ctfd checks a **different** source field
- No `asdff` — display-only derivation (`execute_on_fill: true`, `execute_on_read: false`)
- If both conditions are true, the second `ctfd` overwrites the first — but since both write the same value, the result is deterministic
- Could be refactored to a single `ctfd` with an `or` condition, but the separate-call approach is clearer when sources are semantically independent

**Frequency:** Observed in match/validation status aggregation rules.

### CL-16. Boolean Aggregation Gate (AND/OR Across Multiple Fields)

**Description:** Multiple `ctfd` calls use compound `or`/`and` conditions across **different source fields** to derive a single boolean output ("True"/"False") into a destination field. The first `ctfd` fires when ANY source indicates failure (OR-gate for "False"), the second fires when ALL sources indicate success (AND-gate for "True"). Followed by unconditional `asdff` to persist the result.

**When Used:** Approval/gating fields where multiple independent validation results must ALL pass for an overall approval status. The boolean output drives downstream approval workflows.

**Generic Template:**
```
ctfd(vo("<result1>") == "false" or vo("<result2>") == "false" or vo("<result3>") == "false", "False", "<gate_dest>");
ctfd(vo("<result1>") == "true" and vo("<result2>") == "true" and vo("<result3>") == "true", "True", "<gate_dest>");
asdff(true, "<gate_dest>");
```

**Real Example (Rule 120483):**
```
{ctfd(vo("_result199_")=="false" or vo("_result248_")=="false" or vo("_result311_")=="false","False","_approver_");
 ctfd(vo("_result199_")=="true" and vo("_result248_")=="true" and vo("_result311_")=="true","True","_approver_");
 asdff(true,"_approver_");}
```
Three independent result fields (`_result199_`, `_result248_`, `_result311_`) are aggregated: if ANY is "false", the approver field is set to "False"; if ALL are "true", set to "True". The `asdff(true, ...)` persists the aggregated result.

**Key Observations:**
- **Different from [CL-11](#cl-11-multi-source-ctfd-convergence-to-same-destination)** — CL-11 uses separate `ctfd` calls per source field with independent conditions, while CL-16 combines all sources into compound `or`/`and` conditions within single `ctfd` calls
- **Complementary conditions** — the `or`-based "False" branch and the `and`-based "True" branch are logical complements, ensuring exactly one fires
- **Boolean string values** — uses `"true"`/`"false"` and `"True"`/`"False"` string comparisons (case-sensitive), not native boolean types
- **`asdff(true, ...)`** — unconditional save ensures the gate result is always persisted regardless of which branch matched
- The pattern implements `dest = (result1 AND result2 AND result3)` using two complementary `ctfd` calls
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`

**Variant — Boolean Aggregation Gate with Downstream Routing (Rule 80740):** Extends the base CL-16 pattern by adding **conditional routing logic** after the gate. The gate result feeds additional `ctfd`+`asdff` pairs that copy or clear values based on the boolean outcome:
```
{ctfd(vo("_pANResult53_")=="S" or vo("_mobileNumberResult71_")=="S" or vo("_emailResult76_")=="S" or vo("_gSTResult74_")=="S","True","_finalResult47_");
 ctfd(vo("_pANResult53_")!="S" and vo("_gSTResult74_")!="S" and vo("_mobileNumberResult71_")!="S" and vo("_emailResult76_")!="S","False","_finalResult47_");
 asdff(vo("_finalResult47_")!="","_finalResult47_");
 ctfd(vo("_finalResult47_")=="True" and vo("_salesHeadEmail_")!="",vo("_salesHeadEmail_"),"_extra277_");
 ctfd(vo("_finalResult47_")=="False" and vo("_salesHeadEmail_")!="","","_extra277_");
 asdff(vo("_finalResult47_")!="","_extra277_");}
```
Six-step pipeline:
1. **OR-gate** — if ANY result field equals "S" (suspicious/screening hit), set gate to "True"
2. **AND-gate** — if ALL result fields are NOT "S", set gate to "False"
3. **Save gate** — `asdff` persists the gate result (conditional on non-empty, not unconditional `true`)
4. **Route on True** — if gate is "True" AND salesHeadEmail exists, copy email to notification field
5. **Route on False** — if gate is "False" AND salesHeadEmail exists, clear the notification field (set to "")
6. **Save routed value** — `asdff` persists the notification field

Key differences from base CL-16:
- **Sentinel value `"S"`** instead of `"true"`/`"false"` — the source fields contain screening results, not boolean strings
- **`asdff` is conditional** `vo("_finalResult47_")!=""` — not unconditional `true` as in base pattern
- **Downstream routing** — the gate result drives additional `ctfd` calls that copy/clear an email notification field
- **`ctfd` with empty string `""`** — `ctfd(cond,"","_extra277_")` writes an empty string, functionally equivalent to a conditional clear but using `ctfd` instead of `cf`
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`

**Frequency:** Observed in multi-factor approval/validation gate rules.

### CL-17. vso() — Server-Side/Saved Value Comparison

**Description:** The `vso()` (value of saved/original) function reads the **server-side saved value** of a field, as opposed to `vo()` which reads the current client-side value. This enables comparisons between the current in-flight value and the last-persisted state.

**When Used:** When the rule needs to check what value was previously saved on the server (e.g., checking if a bank validation has previously returned "FAIL") rather than the current client-side value. This is important when the field may have been modified client-side by other rules but the server still holds the original validation result.

**Generic Template:**
```
vso("<field_var>") == "<server_value>"
```

**Real Example — Bank Validation Status Check (Rule 36990):**
```
{(cf(vso("_BankaccNo_")=="FAIL" and touc(vo("_BankBeneficiary_"))!="VERIFIED","_BankBeneficiary_")
  and asdff(vso("_BankaccNo_")=="FAIL" and touc(vo("_BankBeneficiary_"))!="VERIFIED","_BankBeneficiary_"));}
```
When the server-side bank account number validation result is "FAIL" AND the beneficiary name is not "VERIFIED" (case-insensitive via `touc()`): clear and save the beneficiary name field. Key traits:
- **`vso()` reads server state** — `vso("_BankaccNo_")` checks the persisted validation status, not the current client-side value. The client may have changed the field, but the server still reports "FAIL"
- **Mixed `vso()` and `vo()`** — the condition combines `vso()` for one field (server state) with `vo()` via `touc()` for another (current value)
- **Self-clearing** — `cf` and `asdff` both target `_BankBeneficiary_`, the same field checked in the `touc()` condition
- **`and`-chained `cf` + `asdff`** — uses `and` instead of `;` to chain the two functions (see [S-3](#s-3-semicolon-separated-statements))
- No event wrapper — fires on evaluation (triggered by `execute_on_fill: true`)
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`

**Key Observations:**
- `vso()` is distinct from `vo()` — `vo()` reads the DOM/client value, `vso()` reads the last-saved server value
- Typically used for **validation status fields** where the server holds the authoritative result of an external API call (bank verification, PAN validation, etc.)
- Can appear in compound conditions alongside `vo()`, enabling rules that compare current state vs. saved state

**Frequency:** Rare. Observed in bank/KYC validation rules where server-side status must be checked.

---

## Structural Patterns

### S-1. Array Context [0:0]={...}

**Description:** The expression is wrapped in `[0:0]={...}`, indicating it applies within a repeatable row (array/grid) context. The `[0:0]` notation means "row 0, column 0" -- the rule applies to each row independently.

**When Used:** Fields inside ARRAY_HDR / ARRAY_END blocks (repeatable sections like education history, employment history, operational questionnaires).

**Generic Template:**
```
{[0:0]={"<expression>"}}
```

**Real Examples:** Rules 28311, 28310, 28904, 29074, 28840.

**Note:** Array-context rules use escaped quotes (`\"`) since the expression is a string value within a JSON-like structure.

**Frequency:** Very common. Approximately half the rules in this batch used array context.

### S-2. on("change") Wrapper

**Description:** The expression begins with `on("change") and (...)`, wrapping the core logic in an event trigger. The parenthesized block only fires on the "change" event of the source field.

**When Used:** For dropdown-change-triggered cascading logic. The `on("change")` ensures the expensive refresh/save operations only happen when the user actively changes the value, not on form load.

**Generic Template:**
```
{on("change") and (<core_expression>); <additional_expressions_outside_event>}
```

**Real Examples:** Rules 48617, 48618, 48619.

**Note:** Expressions outside the `on("change") and (...)` block (e.g., `dis(...)`, `en(...)`) fire on every evaluation, not just on change. This is intentional -- enable/disable state should always reflect the current value.

**Frequency:** Common for dropdown cascading rules.

### S-3. Semicolon-Separated Statements

**Description:** Multiple function calls are separated by semicolons within the expression. Each call is an independent statement that evaluates in order.

**When Used:** Standard statement separation for all expressions with multiple function calls.

**Generic Template:**
```
func1(...); func2(...); func3(...);
```

**Frequency:** Universal.

### S-4. or-Chained Branches

**Description:** Multiple branches connected with `or`, each handling a different condition. Within each branch, `and` chains multiple function calls that must all succeed.

**When Used:** Mutually exclusive visibility/behavior branches (e.g., show group A or group B or hide all).

**Generic Template:**
```
<branch_empty> or (<branch_A> and <action_A>) or (<branch_B> and <action_B>)
```

**Real Example (Rule 29074):**
```
minvi(vo("_aadhques_")=="", ...)
or (mvi(vo("_aadhques_")=="Yes", ...) and cf(true, ...) and minvi(true, ...))
or (mvi(vo("_aadhques_")=="No", ...) and minvi(true, ...))
```

**Frequency:** Observed in complex visibility rules.

### S-5. Mixed Event-Scoped and Always-Evaluated

**Description:** Part of the expression is inside `on("change") and (...)` and part is outside it. The inner part only fires on change events; the outer part fires on every evaluation (load, change, etc.).

**When Used:** Cascading dropdown logic where save/refresh should only happen on change, but enable/disable state should always be set.

**Real Example (Rule 48617):**
```
{on("change") and (rffdd(...); ctfd(...); cf(...); asdff(...); rffdd(...));
 dis(...);
 dis(...);
 en(...);
 ctfd(...);
 ctfd(...)}
```

**Note:** In Rule 48617, `ctfd` calls appear both inside and outside the `on("change")` block. The outside `ctfd` calls ensure the derived value is set even on form load/read, while the inside ones handle the change event flow.

**Frequency:** Common.

### S-6. on("blur") Wrapper

**Description:** Similar to `on("change")` but fires on the "blur" event — when the source field loses focus. The expression is wrapped in `on("blur") and (...)`.

**When Used:** When the cascading/clearing logic should fire after the user leaves the field rather than immediately on value change. This is typically used when the field value might be typed (not selected from a dropdown) and intermediate keystrokes should not trigger expensive refresh operations.

**Generic Template:**
```
{on("blur") and (<core_expression>)}
```

**Real Example (Rule 48622):**
```
{on("blur") and (
  cf(vo("_employeeiddrob_")!="","_salesofficedrob_","_deliveryplantdrob_","_salesgroupdrob_");
  rffdd(vo("_employeeiddrob_")!="","_salesofficedrob_");
  rffdd(vo("_employeeiddrob_")!="","_deliveryplantdrob_");
  rffdd(vo("_employeeiddrob_")!="","_salesgroupdrob_");
  dis(true,"_deliveryplantdrob_")
)}
```
On blur of the employee ID dropdown: clear three child dropdowns, refresh each individually, and disable delivery plant.

**Note:** `rffdd` is called separately for each child field (rather than in a single call with multiple args), possibly to allow per-child conditional refresh in related rules.

**Frequency:** Less common than `on("change")`. Observed for fields where immediate change-triggered logic would be premature.

### S-7. Numeric Field IDs Instead of Variable Names

**Description:** Some expressions use raw **numeric field IDs** (e.g., `53828`, `72709`) instead of quoted variable names (e.g., `"_fieldName_"`). The `vo()` function and destination parameters accept either format. Numeric IDs reference the `form_fill_metadata_id` directly.

**When Used:** Older rules or rules generated by systems that use metadata IDs rather than human-readable variable names. Functionally identical to variable-name references.

**Real Example (Rule 48942):**
```
{minvi(vo(53828)=="",53264,53265);
 mvi(vo(53828)=="Yes",53264,53265) and mm(true,53264,53265);
 mnm(vo(53828)=="No",53264,53265) and ctfd(true,"NA",53264,53265) and minvi(true,53264,53265)}
```
`vo(53828)` reads the value of the field with metadata ID 53828. Destinations `53264`, `53265` are metadata IDs (no quotes needed for numeric IDs).

**Real Example (Rule 19212):**
```
{cf(vo(72709)=="GSTIN",72710,72711);cf(vo(72709)=="PAN",72710,72720);cf(vo(72709)=="CIN",72711,72720);}
```
All field references use numeric IDs.

**Key Observations:**
- Numeric IDs are **not quoted** — `vo(53828)` not `vo("53828")`
- Destination IDs are also unquoted — `53264` not `"53264"`
- **Mixed usage** (numeric IDs + variable names) within the same rule is confirmed. Rule 34512 uses numeric IDs for visibility/clear logic (`vo(102672)`, `101960`, `102673`) but variable names for `remerr` (`vo("_isYourMobileL_")`, `"_uploadAadhaarFront51_"`) — likely because different parts of the rule were authored at different times or by different systems
- The choice between numeric IDs and variable names has no functional difference
- Numeric IDs can appear in complex compound conditions, e.g., `cf((vo(24399)=="No" and vo(24393)==vo(24400) and ...), 24400,24401,...)` with cross-field equality checks (Rule 1877)
- **Special characters in variable names:** Variable names can contain `?` (e.g., `_isGSTPresent?74_` in Rule 32989), `.` (period), and `-` (hyphen). Rule 35193 uses `_pleaseSelectBelowResponseForSemi-structuredQuestionnaire.36_` — containing both a hyphen and a period. These are quoted string variable names, so any characters valid in strings are allowed

**Frequency:** Observed occasionally, primarily in older or auto-generated rules.

### S-9. on("load") Wrapper

**Description:** The expression uses `on("load") and (...)` to fire only when the form is first loaded/rendered. Unlike `on("change")` (fires on user interaction) and `on("blur")` (fires on focus loss), `on("load")` fires once during form initialization.

**When Used:** For display-time derivations that should compute a value when the form loads but NOT re-fire when the user changes fields. Typically used to format composite display strings from pre-existing field values (e.g., building an "ID - Name" label from separate ID and name fields).

**Generic Template:**
```
{on("load") and (<derivation_expression>)}
```

**Real Example (Rule 51859):**
```
{on("load") and (ctfd(vo("_cityID90_")!="",concat(vo("_cityID90_")," - ",vo("_city_")),"_cityId_"))}
```
On form load, when the city ID is non-empty, concatenate it with the city name using " - " separator and write the formatted label to `_cityId_`. This creates a display-friendly composite value from two separate fields.

**Key Observations:**
- `on("load")` is the third event type after `on("change")` ([S-2](#s-2-onchange-wrapper)) and `on("blur")` ([S-6](#s-6-onblur-wrapper))
- Typically paired with `execute_on_fill: true` — the load event fires when the form is filled/rendered
- No `asdff` typically needed — load-time derivations are display-only
- The inner expression can use any derivation function (`ctfd`, `concat`, etc.)
- Useful for one-time initialization that should not trigger on subsequent changes

**Frequency:** Rare. Observed for display-formatting derivations at form load time.

### S-10. on("click") Wrapper

**Description:** The expression uses `on("click") and (...)` to fire only when the source field (typically a button or action element) is clicked. Unlike `on("change")` (fires on value change) and `on("blur")` (fires on focus loss), `on("click")` fires on a discrete user action — clicking a button, link, or action trigger.

**When Used:** For action-triggered logic where a user explicitly clicks a button to add an item, submit an action, or trigger a complex operation. The click event is distinct from value changes and is typically used on button-type fields or action triggers, not on data entry fields.

**Generic Template:**
```
{[0:0]={"on(\"click\") and (<guard_condition> and (<branch_logic>))"}}
```

**Real Example (Rule 17539):**
```
{[0:0]={"on(\"click\") and (vo(\"_itemProduct_\")!=\"\" and (mvi(vo(\"_itemProduct_\")==\"T-Shirt\", \"_productNameShirt_\", ...) and fdd(true, 71400, 71405, 71406) and ctfd(true, +vo(\"_productNameShirtprice_\") * +vo(\"_tshirtqty_\"), \"_tshirtamount_\") and ctfd(true, vo(\"_itemProduct_\"), \"_productNameShirt_\")) or (mvi(vo(\"_itemProduct_\")==\"Bag\", ...) and fdd(...) and ctfd(...) and ctfd(...)) or (mvi(vo(\"_itemProduct_\")==\"Raincoat\", ...) and fdd(...) and ctfd(...) and ctfd(...));erbyid(true, \"_totalamount_\");erbyid(true, \"_zoneName_\"))\"}}
```
On click: check that a product is selected, then branch by product type to show fields, fill dropdown data, compute amounts, and delegate to total/zone rules. See [C-20](#c-20-mvi--fdd--ctfd--erbyid--click-triggered-product-selection) for full analysis.

**Key Observations:**
- `on("click")` is the **fourth event type** after `on("change")` ([S-2](#s-2-onchange-wrapper)), `on("blur")` ([S-6](#s-6-onblur-wrapper)), and `on("load")` ([S-9](#s-9-onload-wrapper))
- Typically used in **array context** (`[0:0]`) for repeatable row actions (e.g., "Add Item" buttons)
- The click handler usually includes a **guard condition** (e.g., `vo("_itemProduct_")!=""`) to ensure required data is present before processing
- Often triggers complex multi-function logic (visibility + dropdown fill + derivation + delegation) in a single click action
- `execute_on_fill: false`, `execute_on_read: false` — click events don't fire on form load

**Frequency:** Rare. Observed for button-triggered item selection/addition in order forms.

### S-8. Square Bracket Wrapper `{[...]}`

**Description:** The expression is wrapped in `{[...]}` with square brackets inside the outer curly braces, instead of the standard `{...}`. This appears to be a valid alternative syntax that functions identically to the standard wrapper.

**When Used:** Appears interchangeably with the standard `{...}` syntax. No functional difference observed — the wrapped expression evaluates the same way.

**Generic Template:**
```
{[<expression>]}
```

**Real Example (Rule 34393):**
```
{[on("change") and (rffdd(true, "_specialization69_"))]}
```
Compare with the identical logic without square brackets (Rule 33654):
```
{on("change") and (rffdd(true, "_specialization69_"))}
```
Both refresh the specialization dropdown unconditionally on change. The only difference is the `[...]` wrapper.

**Key Observations:**
- The square brackets appear to be optional and syntactically equivalent to their absence
- Both `{[...]}` and `{...}` produce the same runtime behavior
- May be an artifact of different rule authoring tools or migration between system versions
- `execute_on_fill: true`, `run_post_condition_fail: true` — same metadata as the non-bracketed version

**Frequency:** Rare. Observed sporadically alongside standard `{...}` syntax.

### S-11. ctfd 2-Parameter Shorthand

**Description:** `ctfd` is called with only **2 parameters** — condition and destination — omitting the explicit source value. In this form, the evaluated condition value implicitly doubles as the source value that gets copied to the destination. This is a shorthand for `ctfd(vo("field"), vo("field"), "dest")`.

**When Used:** Simple field-to-field copy operations where the source field's non-empty value should be directly copied to a destination field. The condition "is the source non-empty?" and the value "what to copy" are the same `vo()` call.

**Generic Template:**
```
ctfd(vo("<source_field>"), "<dest_field>")
```

Equivalent to:
```
ctfd(vo("<source_field>"), vo("<source_field>"), "<dest_field>")
```

**Real Example (Rule 52127):**
```
{ctfd(vo("_validtill_"),"_endDate70_");}
```
When `_validtill_` is non-empty (truthy), its value is copied to `_endDate70_`. Only 2 parameters: the `vo()` call serves as both the condition and the implicit source value.

**Key Observations:**
- **Minimal parameter count** — 2 instead of the standard 3+ for `ctfd`
- `source_ids` is empty `{}` — the rule declares no explicit source, consistent with the condition being the implicit source
- `execute_on_fill: true`, `execute_on_read: false` — fires on form fill (load) to copy pre-existing values
- No `asdff` — display-only copy
- Distinct from the standard 3-parameter `ctfd(condition, value, dest)` where condition and value can differ
- This form is only viable when the condition IS the value to copy — it cannot be used when the condition differs from the source value (e.g., `ctfd(vo("X")=="Yes", vo("Y"), "dest")`)

**Variant — Cross-Field Copy with Populated source_ids (Rule 52167):** The 2-parameter shorthand can be placed on a **different field** than the source, with `source_ids` pointing to the actual source field. This extends the pattern from self-referencing to cross-field copying:
```
{ctfd(vo("_validtill_"),"_enddate_");}
```
Copies `_validtill_` value to `_enddate_`. Unlike Rule 52127 where `source_ids` is empty `{}`, here `source_ids: {132941}` points to the `_validtill_` field, while `form_fill_metadata_id: 132902` is a different field. Also notable: `condition: ""` and `condition_value_type: ""` are empty strings (not "IN"/"EXPR" as in most rules). `execute_on_fill: true`, `run_post_condition_fail: false`.

Key differences from base S-11:
- **`source_ids` populated** with the actual source field's metadata ID — the rule is placed on a different field (132902) but listens to changes from the source field (132941)
- **Empty `condition`/`condition_value_type`** — no explicit condition metadata, relying entirely on the expression's internal `vo()` check
- Confirms the 2-parameter shorthand works in cross-field contexts, not just self-referencing

**Frequency:** Rare. Observed for simple field-to-field value propagation.

### S-12. on("change") and Without Parentheses

**Description:** The `on("change")` event wrapper is followed by `and` and a function call **without** wrapping the function call in parentheses. In the standard pattern ([S-2](#s-2-onchange-wrapper)), the inner expression is always parenthesized: `on("change") and (<expression>)`. In this variant, the parentheses are omitted: `on("change") and ctfd(...)`.

**When Used:** Simple single-function-call rules where only one function needs to be event-gated. The parentheses are syntactically unnecessary when there is only one function call (no semicolons or `or`-chaining needed).

**Generic Template:**
```
on("change") and ctfd(<condition>, <value>, "<dest>")
```

**Real Example (Rule 52722):**
```
{on("change") and ctfd(true, vo("_addressLine1Permanent_"), "_dependaddress_")}
```
On change, unconditionally copy the permanent address value to the dependent address field. No parentheses around the `ctfd(...)` call — the `and` operator directly joins `on("change")` and `ctfd(...)`.

**Key Observations:**
- **No parentheses** around the inner expression — contrast with `{on("change") and (ctfd(...))}` which is the standard form
- Functionally equivalent to the parenthesized version — the `and` operator binds `on("change")` to the single `ctfd` call
- Only viable for **single function calls** — if multiple functions were needed (semicoloned or `or`-chained), parentheses would be required for correct grouping
- `execute_on_fill: false`, `run_post_condition_fail: false`
- Confirms that the expression parser treats parentheses as optional for single-statement event wrappers

**Frequency:** Rare. Observed for simple single-function event-gated rules.

### S-14. on("focus") Wrapper

**Description:** The expression uses `on("focus") and (...)` to fire only when the source field receives focus. Unlike `on("change")` (fires on value change), `on("blur")` (fires on focus loss), and `on("load")` (fires on form load), `on("focus")` fires the moment a field gains focus — typically used to dynamically populate dropdown options before the user interacts.

**When Used:** For dynamically populating a dropdown's options from other field values at interaction time. The `on("focus")` event ensures options are built fresh each time the user goes to select a value, reflecting the latest state of the source fields.

**Generic Template:**
```
{on("focus") and <setup_expression>;
 on("change") and (<change_expression>)}
```

**Real Example (Rule 52987, partial):**
```
{on("focus") and addSelectOptions("_gratuityNomName_",
  ["_dependentsName_","_dependentsName1_",...,"_dependentsName9_"]);
 on("change") and (...)}
```
On focus, the `addSelectOptions` function populates the gratuity nominee name dropdown with options sourced from 10 dependent name fields. This ensures the dropdown always reflects the current dependents list when the user clicks on it.

**Key Observations:**
- `on("focus")` is the **fifth event type** after `on("change")` ([S-2](#s-2-onchange-wrapper)), `on("blur")` ([S-6](#s-6-onblur-wrapper)), `on("load")` ([S-9](#s-9-onload-wrapper)), and `on("click")` ([S-10](#s-10-onclick-wrapper))
- Typically paired with `on("change")` in the same rule — focus sets up options, change handles the selection
- Used with `addSelectOptions` to build dynamic dropdowns from field values (not static EDV data)
- `execute_on_fill: true`, `execute_on_read: false`

**Frequency:** Rare. Observed for dynamic dropdown population from sibling field values.

### S-13. Paired Gate + Reset Rules

**Description:** A single source field gets **two separate rules** that work as a complementary pair: (1) a **gate rule** ([C-1](#c-1-cf--asdff--disen--empty-guard-with-enabledisable)) that handles read-time/load-time state (disable+clear when empty, enable when filled), and (2) a **reset rule** ([II-2 unconditional variant](#ii-2-cf--asdff--clear-and-save-empty-guard)) that handles change-time behavior (always clear+save the child on parent change). Together they fully manage a dependent field's lifecycle.

**When Used:** Date pairs (start/end, joining/leaving) and any parent-child dependency where the child must be both guarded on load and reset on change.

**Generic Template (2 rules on the same source field):**
```
// Rule A — Gate (evaluates on every render):
{dis(vo("<source>") == "", "<dest>"); en(vo("<source>") != "", "<dest>"); cf(vo("<source>") == "", "<dest>"); asdff(vo("<source>") == "", "<dest>");}

// Rule B — Reset (only fires on change):
{on("change") and (cf(true, "<dest>"); asdff(true, "<dest>"))}
```

**Real Example (Rules 52788 + 52789 on `_employeeJoingDate_`):**
```
// Rule 52788 — Gate:
{dis(vo("_employeeJoingDate_")=="","_employeeLeavingDate_");en(vo("_employeeJoingDate_")!="","_employeeLeavingDate_");cf(vo("_employeeJoingDate_")=="","_employeeLeavingDate_");asdff(vo("_employeeJoingDate_") == "", "_employeeLeavingDate_");}

// Rule 52789 — Reset on change:
{on("change") and (cf(true,"_employeeLeavingDate_");asdff(true, "_employeeLeavingDate_"))}
```

**Why Two Rules?** The gate rule (A) uses conditional logic (`vo("")==""`) that evaluates on every render — it correctly disables/enables the child based on the current state. But it does NOT clear the child when the parent changes from one non-empty value to another (since the condition `==""` doesn't fire). The reset rule (B) fills this gap: `on("change")` with `cf(true,...)` unconditionally clears the child whenever the parent changes, regardless of what the new value is. Together: gate handles state, reset handles transitions.

**Confirmed Pairs from Batches 22–25 (8+ pairs):**
| Gate Rule | Reset Rule | Source → Destination |
|-----------|------------|---------------------|
| 52735 | (other batch) | `_eduationstartdate_` → `_eduationenddate_` |
| 52747 | 52748 | `_eduationstartdate2_` → `_eduationenddate2_` |
| 52759 | 52760 | `_eduationstartdate3_` → `_eduationenddate3_` |
| 52771 | 52772 | `_eduationstartdate4_` → `_eduationenddate4_` |
| 52783 | 52784 | `_eduationstartdate5_` → `_eduationenddate5_` |
| 52788 | 52789 | `_employeeJoingDate_` → `_employeeLeavingDate_` |
| 52791 | 52792 | `_employeeJoingDate1_` → `_employeeLeavingDate1_` |
| 52794 | 52795 | `_employeeJoingDate2_` → `_employeeLeavingDate2_` |
| 52797 | 52798 | `_employeeJoingDate3_` → `_employeeLeavingDate3_` |
| 52800 | 52801 | `_employeeJoingDate4_` → `_employeeLeavingDate4_` |

**Key Observations:**
- Both rules share the **same `source_ids` and `form_fill_metadata_id`** — they are placed on the same source field
- Both use `execute_on_fill: false`, `execute_on_read: false` — they rely on condition evaluation timing rather than explicit fill/read flags
- The gate rule uses **opposite conditions** (`==""` for dis/cf/asdff, `!=""` for en) — classic [CL-1 Opposite Conditions](#cl-1-opposite-conditions-empty-vs-non-empty-guard)
- The reset rule uses **`true` conditions** inside `on("change")` — unconditional within the event scope
- This pair pattern scales across numbered field instances (education dates 2–5, employee dates 0–4)

**Frequency:** Very common. Every date-pair or parent-child field dependency in this batch uses this paired approach.

### C-20. mvi + fdd + ctfd + erbyid — Click-Triggered Product Selection

**Description:** A complex multi-branch pattern triggered by `on("click")` that implements an "add item to cart" workflow. Each branch corresponds to a product type: (1) `mvi` shows the product's fields, (2) `fdd` fills price/details from the dropdown's backing data, (3) `ctfd` computes the line amount (price × quantity), (4) `ctfd` copies the product name. After all branches, `erbyid` delegates to aggregate fields (total amount, zone).

**When Used:** Order/item selection forms where clicking an "Add" button should populate a product row with its details, compute the line total, and trigger aggregate recalculation.

**Generic Template:**
```
on("click") and (vo("<selection>")!="" and (
  (mvi(vo("<selection>")=="<product_A>", <product_A_fields>)
   and fdd(true, <dropdown_id>, <price_dest>, <detail_dest>)
   and ctfd(true, +vo("<price>") * +vo("<qty>"), "<amount>")
   and ctfd(true, vo("<selection>"), "<name_dest>"))
  or (mvi(vo("<selection>")=="<product_B>", <product_B_fields>)
   and fdd(true, ...) and ctfd(true, ...) and ctfd(true, ...))
  or (...more products...);
  erbyid(true, "<total_field>");
  erbyid(true, "<other_aggregate>"))
)
```

**Real Example (Rule 17539):**
```
{[0:0]={"on(\"click\") and (vo(\"_itemProduct_\")!=\"\" and (mvi(vo(\"_itemProduct_\")==\"T-Shirt\", \"_productNameShirt_\", \"_productNameShirtprice_\", \"_tshirtqty_\", \"_tshirtamount_\", \"_removetshirt_\", \"_itemLable1_\") and fdd(true, 71400, 71405, 71406) and ctfd(true, +vo(\"_productNameShirtprice_\") * +vo(\"_tshirtqty_\"), \"_tshirtamount_\") and ctfd(true, vo(\"_itemProduct_\"), \"_productNameShirt_\")) or (mvi(vo(\"_itemProduct_\")==\"Bag\", \"_productNameBag_\", \"_productNamebagprice_\", \"_bagqty_\", \"_bagamount_\", \"_removebag_\", \"_itemLable1_\") and fdd(true, 71400, 71410, 71411) and ctfd(true, +vo(\"_productNamebagprice_\") * +vo(\"_bagqty_\"), \"_bagamount_\") and ctfd(true, vo(\"_itemProduct_\"), \"_productNameBag_\")) or (mvi(vo(\"_itemProduct_\")==\"Raincoat\", \"_productNameRainCoat_\", \"_productNameRainCoatPrice_\", \"_raincoatqty_\", \"_raincoatamount_\", \"_removeraincoat_\", \"_itemLable1_\") and fdd(true, 71400, 71415, 71416) and ctfd(true, +vo(\"_productNameRainCoatPrice_\") * +vo(\"_raincoatqty_\"), \"_raincoatamount_\") and ctfd(true, vo(\"_itemProduct_\"), \"_productNameRainCoat_\"));erbyid(true, \"_totalamount_\");erbyid(true, \"_zoneName_\"))\"}}
```

Three product branches (T-Shirt, Bag, Raincoat), each with identical 4-function structure:
1. **`mvi`** — shows 6 product-specific fields (name, price, quantity, amount, remove button, label)
2. **`fdd(true, 71400, <price_dest>, <detail_dest>)`** — fills price and detail fields from dropdown 71400's backing data. `fdd` uses **numeric field IDs** for source and destinations
3. **`ctfd(true, +vo("<price>") * +vo("<qty>"), "<amount>")`** — computes line amount as price × quantity using `+vo()` numeric coercion ([CL-8](#cl-8-numeric-coercion-with-vo))
4. **`ctfd(true, vo("<selection>"), "<name>")`** — copies the selected product name to the product name display field

After the `or`-branched product logic:
- **`erbyid(true, "_totalamount_")`** — delegates to the total amount field's rules (which likely sums all line amounts)
- **`erbyid(true, "_zoneName_")`** — delegates to the zone name field's rules

**Key Observations:**
- **`on("click")` event** — this is the only observed use of click-triggered logic (see [S-10](#s-10-onclick-wrapper))
- **`fdd` with numeric IDs** — `fdd(true, 71400, 71405, 71406)` uses the source dropdown's metadata ID (71400) and destination metadata IDs. The first arg after condition is the **source dropdown**, followed by **destination fields** (positional column mapping)
- All `ctfd`/`fdd` calls within branches use **`true` conditions** because the branch is gated by the outer `mvi` condition — if `mvi`'s condition fails, the `and` chain short-circuits ([CL-14](#cl-14-local-variable-assignment-in-expressions) note on `and`-chained `true`)
- **`erbyid` outside branches** — semicolon-separated after the `or` chain, so it fires unconditionally after any branch succeeds
- Related to Rule 17533 ([I-2 mass save](#i-2-asdff--standalone-auto-save)) which persists all the fields populated by this click handler
- Array context `[0:0]`, `execute_on_fill: false`, `run_post_condition_fail: true`

**Frequency:** Rare. Observed in product/item selection order forms.

---

## Anti-Patterns & Gotchas

### C-21. ctfd + dis — Derive Fixed Value and Lock Field

**Description:** `ctfd` writes a hardcoded literal value to a destination field and `dis` disables it, preventing user modification. Both use `true` as the condition — unconditional derivation and lock. This is a "set and forget" pattern for fields that should always show a system-determined value.

**When Used:** Setting default/sentinel values that users should not modify, such as far-future end dates (e.g., "31-12-2055" meaning "no expiry"), fixed status codes, or system-generated constants.

**Generic Template:**
```
ctfd(true, "<literal_value>", "<dest_var>");
dis(true, "<dest_var>");
```

**Real Example (Rule 52166):**
```
{ctfd(true,"31-12-2055","_endDate70_");dis(true,"_endDate70_");}
```
Unconditionally sets the end date to a far-future date (December 31, 2055) and disables the field. The date acts as a "no end date" sentinel. `execute_on_fill: true` — fires on form load. `run_post_condition_fail: false`.

**Real Example (Rule 52169):**
```
{ctfd(true,"31-12-2055","_enddate_");dis(true,"_enddate_");}
```
Identical pattern with a different destination field name. Confirms this is a reusable pattern for far-future date defaults. `condition: ""`, `condition_value_type: ""` — no explicit condition metadata.

**Key Observations:**
- Both `ctfd` and `dis` use `true` — unconditional, no branching
- No `asdff` — the value is derived on load and saved on form submission
- No `cf` — the field is set, not cleared (the literal value replaces any previous value)
- Distinct from C-4/C-16 (which have branching with dis/en) — this is a single-branch, fixed-value pattern
- The far-future date "31-12-2055" is a common sentinel for "no expiry" or "indefinite validity"
- `execute_on_fill: true` ensures the default is set on form load

**Frequency:** Observed in date/validity fields. At least 2 confirmed instances.

### C-22. cf + en + mnm + minvi + ctfd + mvi + mm + dis — Dynamic Slab/Bucket Configuration with Derivation Chaining

**Description:** An 8-function mega-rule that manages a variable-count set of slab/bucket sections. A selection field (e.g., "Number of Buckets") determines how many slab groups (each with start, end, and commission fields) are shown, mandated, and configured. The rule chains slab end values to next slab start values, sets a sentinel value for the last slab's end, and disables the auto-calculated last slab end field.

**When Used:** Commission structures, pricing tiers, or any configuration where the number of active sections is dynamic. Each slab has a start range, end range, and value field. The slabs must be contiguous (end of slab N = start of slab N+1) and the last slab's end is always a fixed maximum (e.g., "999999" meaning infinity).

**Generic Template (5 phases):**
```
on("change") and (
  // Phase 1: Reset ALL — clear, enable, un-mandate, hide everything
  cf(true, <all_slab_fields>);
  en(true, <all_end_fields>);
  mnm(true, <all_slab_fields>);
  minvi(true, <all_slab_fields>);

  // Phase 2: Derivation — sentinel for last slab + chaining
  ctfd(vo(<bucketCount>)=="1", "999999", <slab1_end>);
  ctfd(vo(<bucketCount>)=="2", "999999", <slab2_end>);
  ... (one per possible count value)
  ctfd(vo(<slab1_end>)!="", vo(<slab1_end>), <slab2_start>);
  ctfd(vo(<slab2_end>)!="", vo(<slab2_end>), <slab3_start>);
  ... (chain: end of slab N → start of slab N+1)

  // Phase 3: Progressive additive visibility
  mvi(vo(<bucketCount>)=="1", <slab1_fields>);
  mvi(vo(<bucketCount>)=="2", <slab1_fields>, <slab2_fields>);
  mvi(vo(<bucketCount>)=="3", <slab1_fields>, <slab2_fields>, <slab3_fields>);
  ... (each count shows slabs 1..N — additive)

  // Phase 4: Progressive additive mandatory
  mm(vo(<bucketCount>)=="1", <slab1_fields>);
  mm(vo(<bucketCount>)=="2", <slab1_fields>, <slab2_fields>);
  ... (mirrors visibility)

  // Phase 5: Selective disable — lock last slab's end field
  dis(vo(<bucketCount>)=="1", <slab1_end>);
  dis(vo(<bucketCount>)=="2", <slab2_end>);
  ... (disable the auto-calculated sentinel end field)
)
```

**Real Example (Rule 52521 — New Slabs, abridged):**
```
{on("change") and (
  cf(true,"_slab1ennew_","_slab1comnew_","_slab2stnew_","_slab2ennew_",...,"_slab10comnew_");
  en(true,"_slab1ennew_","_slab2ennew_",...,"_slab10ennew_");
  mnm(true,"_slab1stnew_","_slab1ennew_","_slab1comnew_",...,"_slab10comnew_");
  minvi(true,"_slab1stnew_","_slab1ennew_","_slab1comnew_",...,"_slab10comnew_");

  ctfd(vo("_onBucketsSelection_")=="1","999999","_slab1ennew_");
  ctfd(vo("_onBucketsSelection_")=="2","999999","_slab2ennew_");
  ... (up to 10)
  ctfd(vo("_slab1ennew_")!="",vo("_slab1ennew_"),"_slab2stnew_");
  ctfd(vo("_slab2ennew_")!="",vo("_slab2ennew_"),"_slab3stnew_");
  ... (chain through 9 transitions)

  mvi(vo("_onBucketsSelection_")=="1","_slab1stnew_","_slab1ennew_","_slab1comnew_");
  mvi(vo("_onBucketsSelection_")=="2","_slab1stnew_","_slab1ennew_","_slab1comnew_",
      "_slab2stnew_","_slab2ennew_","_slab2comnew_");
  ... (up to 10, each a superset of the previous)

  mm(vo("_onBucketsSelection_")=="1","_slab1stnew_","_slab1ennew_","_slab1comnew_");
  mm(vo("_onBucketsSelection_")=="2","_slab1stnew_","_slab1ennew_","_slab1comnew_",
      "_slab2stnew_","_slab2ennew_","_slab2comnew_");
  ... (mirrors mvi structure)

  dis(vo("_onBucketsSelection_")=="1","_slab1ennew_");
  dis(vo("_onBucketsSelection_")=="2","_slab2ennew_");
  ... (up to 10)
)}
```

**Key Observations:**
- **8 distinct functions** in a single rule — the most function-diverse pattern observed: `cf`, `en`, `mnm`, `minvi`, `ctfd`, `mvi`, `mm`, `dis`
- **5 clear phases**: (1) Reset all to clean state, (2) Derive sentinel + chain values, (3) Progressive show, (4) Progressive mandate, (5) Selective lock
- **Derivation chaining** (`ctfd`) — slab end → next slab start creates contiguous ranges. If the user enters "100" as slab 1 end, slab 2 start auto-populates as "100"
- **Sentinel value "999999"** — the last active slab always ends at "999999" (effectively infinity). `ctfd` writes this based on which bucket count is selected
- **`en` + `dis` interplay** — Phase 1 `en(true, ...)` enables ALL end fields, then Phase 5 `dis(condition, ...)` selectively disables the LAST end field (since it's auto-set to "999999" and shouldn't be edited)
- **Progressive additive field lists** — `mvi`/`mm` for count=N lists ALL fields from slab 1 through slab N (superset pattern, same as [C-7 Progressive Additive Visibility](#c-7-cf--remerr--mvminvi--mmmnm--full-branch-visibility-with-mandatory))
- **Symmetric old/new instances** — Rule 52521 handles "new" slab fields, Rule 52520 handles "old" slab fields with identical structure but `_*Old_` variable names and `_onBucketsSelectionOld_` as the source
- **Each slab has 3 fields** — start (`_slabNst*_`), end (`_slabNen*_`), commission (`_slabNcom*_`) — 30 fields across 10 slabs
- `on("change")` wrapper, `run_post_condition_fail: true`
- Builds on C-7's progressive additive pattern but adds the derivation chaining and enable/disable phases that C-7 lacks

**Frequency:** Observed in commission/slab configuration forms. 2 confirmed instances (Rules 52521, 52520) for old and new slab sets.

---

## Anti-Patterns & Gotchas

### AP-1. Mismatched vo() Reference

**Description:** A `cf` or other function call references the wrong field in its `vo()` condition. Instead of using the source variable name, a literal value string is passed to `vo()`.

**Real Example (Rule 28840):**
```
cf(vo("Certificate")=="Applied", "_lcatid_")
```
This should almost certainly be:
```
cf(vo("_isFssaiPresent_")=="Certificate", "_lcatid_")
```
The `vo("Certificate")` call tries to get the value of a field named "Certificate", which is likely not a valid variable name -- it was probably meant to check if the FSSAI field equals "Certificate".

**Frequency:** Rare (likely a data entry error).

### AP-2. Duplicate ctfd Calls Inside and Outside on("change")

**Description:** The same `ctfd` call appears both inside `on("change") and (...)` and outside it. This means the derivation happens twice on change events (once in the event block, once in the always-evaluated block).

**Real Example (Rule 48617):**
```
on("change") and (...ctfd(vo("_customertypedrob_")=="P001-Dealer","TR - Trade","_distributionchanneldrob_")...);
...
ctfd(vo("_customertypedrob_")=="P001-Dealer","TR - Trade","_distributionchanneldrob_");
```
The outside copy is needed for load-time evaluation, but this means the `ctfd` fires twice on change.

**Frequency:** Observed in complex dropdown rules.

### AP-3. ctfd with Empty String as Clear

**Description:** `ctfd` is used with an empty string `""` as the value, effectively clearing a field via `ctfd` instead of using `cf`. This is semantically a clear operation but implemented as "derive empty string."

**When Used:** When the field needs to be first reset (via ctfd to "") inside an event block, then conditionally re-populated with an actual value outside the event block. The two-phase approach (clear on change, then re-derive on every evaluation) prevents stale values.

**Real Example (Rule 48869):**
```
{on("change") and (
  ctfd(vo("_account3_")!= "","","_triggerRule96_");
  asdff(vo("_account3_")!= "", "_triggerRule96_"));
ctfd((vo("_IsMeetingQue7_") != "In-Person" or vo("_LocQue8_") != "Restaurant Location")
  and vo("_account3_")!= "" and vo("_restaurantName24_")== "",
  vo("_account3_"),"_triggerRule96_");
asdff(vo("_account3_")!= "", "_triggerRule96_");}
```
Inside `on("change")`: ctfd sets `_triggerRule96_` to `""` (clearing it). Outside: ctfd conditionally re-populates with the actual account value.

**Note:** This is distinct from `cf` because `ctfd` with `""` still writes a value (empty string), while `cf` truly empties the field. In practice the effect is the same, but this pattern is typically used when the same destination is both cleared and set within the same rule.

**Frequency:** Observed in trigger-field rules.

### AP-4. Redundant Overlapping Condition Guards

**Description:** Multiple `ctfd` calls compute the **same value** to the **same destination** but with **overlapping conditions** of increasing strictness. The less restrictive conditions may produce incorrect results (e.g., multiplying when one operand is empty → `0` or `NaN`), while the most restrictive condition is the correct guard. The final matching `ctfd` overwrites the others, so the result is correct, but the redundant calls are wasteful.

**When Used:** Defensive programming or incremental rule construction where each source field gets its own guard condition, plus a compound condition for the full computation. May be intentional (ensuring the computation fires regardless of evaluation order) or accidental (copy-paste without consolidation).

**Real Example (Rule 52363):**
```
{ctfd(vo("_rclimitcount_")!="",+vo("_rclimitcount_") * +vo("_rcageing_"),"_parameter1_");
 ctfd(vo("_rcageing_")!="",+vo("_rclimitcount_") * +vo("_rcageing_"),"_parameter1_");
 ctfd(vo("_rclimitcount_")!="" and vo("_rcageing_")!="",+vo("_rclimitcount_") * +vo("_rcageing_"),"_parameter1_");
 ctfd(vo("_parameter1_")!="",(+vo("_parameter1_") * 1000),"_rcamt_");}
```
Three `ctfd` calls compute `rclimitcount × rcageing` → `_parameter1_` with:
1. Guard: only `_rclimitcount_` non-empty (if `_rcageing_` is empty, `+vo("")` → 0, result is 0)
2. Guard: only `_rcageing_` non-empty (if `_rclimitcount_` is empty, result is 0)
3. Guard: BOTH non-empty (correct guard — ensures both operands exist)

The third `ctfd` with the compound `and` condition is the only correct one. The first two may write `0` prematurely when only one field is populated. Since all three target the same destination, the last match wins — if both fields are populated, the third `ctfd` fires last and writes the correct value. But if only one field is populated, the rule writes `0` instead of nothing.

A fourth `ctfd` chains the intermediate result: `parameter1 × 1000 → _rcamt_`, forming a 2-step computation pipeline (see [I-1 Chained Computation DAG](#i-1-ctfd--computed-value-derivation)).

**Key Observations:**
- The correct guard is `vo("A")!="" and vo("B")!=""` — the compound condition
- The single-field guards are **subsets** of the compound condition
- Last-writer-wins semantics makes the final result correct only when all fields are populated
- When partially populated, the intermediate value is `0` (from `+vo("") × valid_value`)
- `execute_on_fill: true`, `run_post_condition_fail: false`

**Frequency:** Rare. Likely a defensive or auto-generated pattern.

### AP-5. Duplicate Identical ctfd Calls

**Description:** The exact same `ctfd` call (identical condition, value, and destination) appears twice consecutively within a single rule expression. This is redundant — the second call overwrites the first with the same value.

**Real Example (Rule 36714, partial):**
```
ctfd(vo("_panHolderName_")!="",touc(vo("_panHolderName_")),"_panHolderName_");
ctfd(vo("_panHolderName_")!="",touc(vo("_panHolderName_")),"_panHolderName_");
```
Both calls have identical condition (`vo("_panHolderName_")!=""`), identical value (`touc(vo("_panHolderName_"))`), and identical destination (`"_panHolderName_"`). The second call is completely redundant.

**Key Observations:**
- Distinct from [AP-2](#ap-2-duplicate-ctfd-calls-inside-and-outside-onchange) — here both calls are in the same scope (no `on("change")` wrapper difference)
- Distinct from [AP-4](#ap-4-redundant-overlapping-condition-guards) — here the conditions are literally identical, not just overlapping
- Likely a copy-paste error during rule construction
- Has no functional impact — the second call simply repeats the first

**Frequency:** Rare. Likely a data entry error.

### C-23. erbyid + cf + asdff — Delegate-Up Then Clear-Down on Change

**Description:** On change, the rule does two things simultaneously: (1) **delegates upward** via `erbyid` to trigger re-evaluation of a parent/aggregate field's rules (e.g., marital status), and (2) **clears downward** via `cf`+`asdff` to wipe and save multiple dependent child fields when the source is empty. This creates a bidirectional effect from a single field change.

**When Used:** Dependent relation fields (e.g., a dependent's relationship dropdown) that both affect an upstream aggregate (marital status determines how many dependents are valid) and control downstream detail fields (name, gender, DOB, age) that should be cleared when the relation is emptied.

**Generic Template:**
```
{on("change") and (erbyid(true, "<upstream_field>"); cf(vo("<source>")==""", "<child_1>", "<child_2>", ..., "<child_N>"); asdff(vo("<source>")=="", "<child_1>", "<child_2>", ..., "<child_N>"))}
```

**Real Example (Rule 52814):**
```
{on("change") and (erbyid(true, "_maritalStatus_");cf(vo("_dependentsRelation_")=="","_dependentsName_","_dependentsGender_","_dependentsDob_","_dependentsDobAge_");asdff(vo("_dependentsRelation_")=="","_dependentsName_","_dependentsGender_","_dependentsDob_","_dependentsDobAge_"))}
```
When the dependent's relation dropdown changes: (1) always trigger marital status field's rules via `erbyid(true, ...)`, (2) if the relation is now empty, clear and save the 5 detail fields (name, gender, DOB, age). `execute_on_fill: true`, `run_post_condition_fail: false`.

**Key Observations:**
- `erbyid` uses **unconditional `true`** — the upstream re-evaluation always happens on any change, regardless of the new value
- `cf` and `asdff` use **conditional `vo(...)==""`** — clearing only happens when the relation is emptied, not when it's changed to another value
- The **same condition and field list** is shared between `cf` and `asdff` (standard clear-and-persist pair)
- This is distinct from [C-14](#c-14-ctfd--erbyid--derive-then-delegate) (derive then delegate) — here there is no derivation, only clearing + delegation
- All 3 rules target **5 child fields** per relation row: name, gender, DOB, DOB age

**Numbered Instances (Rules 52814, 52825, 52845):**
| Rule | Source Field | Upstream Delegate | Child Fields (5 per row) | execute_on_fill |
|------|-------------|-------------------|--------------------------|-----------------|
| 52814 | `_dependentsRelation_` | `_maritalStatus_` | `_dependentsName_`, `_dependentsGender_`, `_dependentsDob_`, `_dependentsDobAge_` | true |
| 52825 | `_dependentsRelation1_` | `_maritalStatus_` | `_dependentsName1_`, `_dependentsGender1_`, `_dependentsDob1_`, `_dependentsDobAge1_` | false |
| 52845 | `_dependentsRelation2_` | `_maritalStatus_` | `_dependentsName2_`, `_dependentsGender2_`, `_dependentsDob2_`, `_dependentsDobAge2_` | false |
| 52860 | `_dependentsRelation3_` | `_maritalStatus_` | `_dependentsName3_`, `_dependentsGender3_`, `_dependentsDob3_`, `_dependentsDobAge3_` | false |
| 52879 | `_dependentsRelation4_` | `_maritalStatus_` | `_dependentsName4_`, `_dependentsGender4_`, `_dependentsDob4_`, `_dependentsDobAge4_` | false |
| 52893 | `_dependentsRelation5_` | `_maritalStatus_` | `_dependentsName5_`, `_dependentsGender5_`, `_dependentsDob5_`, `_dependentsDobAge5_` | false |
| 52910 | `_dependentsRelation6_` | `_maritalStatus_` | `_dependentsName6_`, `_dependentsGender6_`, `_dependentsDob6_`, `_dependentsDobAge6_` | false |
| 52930 | `_dependentsRelation7_` | `_maritalStatus_` | `_dependentsName7_`, `_dependentsGender7_`, `_dependentsDob7_`, `_dependentsDobAge7_` | false |
| 52944 | `_dependentsRelation8_` | `_maritalStatus_` | `_dependentsName8_`, `_dependentsGender8_`, `_dependentsDob8_`, `_dependentsDobAge8_` | false |
| 52964 | `_dependentsRelation9_` | `_maritalStatus_` | `_dependentsName9_`, `_dependentsGender9_`, `_dependentsDob9_`, `_dependentsDobAge9_` | true |

All 10 instances delegate to the **same upstream field** (`_maritalStatus_`), confirming a fan-in pattern where multiple dependent rows all trigger the same parent re-evaluation. `execute_on_fill` is `true` only for the first (unsuffixed, Rule 52814) and last (suffix 9, Rule 52964) instances; all others are `false`.

**Frequency:** Common in forms with repeatable dependent/family member rows. 10 numbered instances observed (suffixes 0–9).

### C-24. mnm + mm + mvi/minvi + ctfd — Age-Gated Guardian Visibility/Mandatory with Address Derivation

**Description:** Manages guardian fields based on the nominee's age. When the nominee is a minor (age < 18), guardian fields are made visible and mandatory, and the permanent address is derived into the guardian address. When the nominee is an adult (age >= 18), guardian fields are hidden, made non-mandatory, and the guardian address is reset. This combines visibility (`mvi`/`minvi`), mandatory state (`mm`/`mnm`), and value derivation (`ctfd`) in a single rule without any `cf` clearing or `remerr` error removal.

**When Used:** EPF/PF nomination forms where a guardian is required only for minor nominees. The age check examines two age fields (primary and secondary nominee ages) with OR logic — if either nominee is under 18, guardian details are required.

**Generic Template (Full — with visibility):**
```
{mnm(<age_over_18_condition>, "<guardian_field_1>", "<guardian_field_2>", "<guardian_field_3>");
 minvi(<age_over_18_condition>, "<guardian_field_1>", "<guardian_field_2>", "<guardian_field_3>", "<guardian_section>");
 mvi(<age_under_18_condition>, "<guardian_field_1>", "<guardian_field_2>", "<guardian_field_3>", "<guardian_section>");
 mm(<age_under_18_condition>, "<guardian_field_1>", "<guardian_field_2>", "<guardian_field_3>");
 ctfd(<age_over_18_condition>, vo("<permanent_address>"), "<guardian_address>")}
```

**Generic Template (Reduced — mandatory + derivation only):**
```
{mnm(<age_over_18_condition>, "<guardian_field_1>", "<guardian_field_2>", "<guardian_field_3>");
 mm(<age_under_18_condition>, "<guardian_field_1>", "<guardian_field_2>", "<guardian_field_3>");
 ctfd(<age_under_18_condition>, vo("<permanent_address>"), "<guardian_address>")}
```

**Real Example — Full Variant (Rule 52979):**
```
{mnm((vo("_epfAge_")==""  or +vo("_epfAge_") >= 18) or (vo("_epfAge2_")==""  or +vo("_epfAge2_") >= 18), "_guardianName_", "_guardiandob_", "_guardianAddress_");
 minvi((vo("_epfAge_")==""  or +vo("_epfAge_") >= 18) or (vo("_epfAge2_")==""  or +vo("_epfAge2_") >= 18), "_guardianName_", "_guardiandob_", "_guardianAddress_", "_guardian_");
 mvi((vo("_epfAge_")!="" and +vo("_epfAge_") < 18) or (vo("_epfAge2_")!="" and +vo("_epfAge2_") < 18), "_guardianName_", "_guardiandob_", "_guardianAddress_", "_guardian_");
 mm((vo("_epfAge_")!="" and +vo("_epfAge_") < 18) or (vo("_epfAge2_")!="" and +vo("_epfAge2_") < 18), "_guardianName_", "_guardiandob_", "_guardianAddress_");
 ctfd((vo("_epfAge_")==""  or +vo("_epfAge_") >= 18) or (vo("_epfAge2_")==""  or +vo("_epfAge2_") >= 18), vo("_addressLine1Permanent_"), "_guardianAddress_")}
```
Five-function composite: When BOTH ages are empty or >= 18: make guardian fields non-mandatory (`mnm`), hide them (`minvi`), and derive permanent address into guardian address (`ctfd`). When EITHER age is < 18 (and non-empty): make guardian fields visible (`mvi`) and mandatory (`mm`). The `ctfd` on the over-18 branch effectively resets guardian address to the permanent address when guardianship is no longer required.

**Real Example — Reduced Variant (Rule 52984):**
```
{mnm((vo("_epfAge_")==""  or +vo("_epfAge_") >= 18) or (vo("_epfAge2_")==""  or +vo("_epfAge2_") >= 18), "_guardianName_", "_guardiandob_", "_guardianAddress_");
 mm((vo("_epfAge_")!="" and +vo("_epfAge_") < 18) or (vo("_epfAge2_")!="" and +vo("_epfAge2_") < 18), "_guardianName_", "_guardiandob_", "_guardianAddress_");
 ctfd((vo("_epfAge_")!="" and +vo("_epfAge_") < 18) or (vo("_epfAge2_")!="" and +vo("_epfAge2_") < 18), vo("_addressLine1Permanent_"), "_guardianAddress_")}
```
Three-function variant: Same mandatory toggling (`mnm`/`mm`) but **no visibility management** (no `mvi`/`minvi`). The `ctfd` here fires on the **under-18 condition** — deriving the permanent address into guardian address when a minor is detected. Different source metadata ID (134173 vs 134165), suggesting placement on a different trigger field.

**Key Observations:**
- **Complementary conditions** — the over-18 and under-18 conditions are logical inverses, ensuring exactly one branch fires:
  - Over-18: `(vo("_epfAge_")==""  or +vo("_epfAge_") >= 18) or (vo("_epfAge2_")==""  or +vo("_epfAge2_") >= 18)` — treats empty as adult (safe default)
  - Under-18: `(vo("_epfAge_")!="" and +vo("_epfAge_") < 18) or (vo("_epfAge2_")!="" and +vo("_epfAge2_") < 18)` — requires non-empty AND below threshold
- **Two age fields** checked with `OR` — `_epfAge_` and `_epfAge2_` (primary and secondary nominee). Either being a minor triggers guardian requirements
- **`+vo()` numeric coercion** used for age comparison (see [CL-8](#cl-8-numeric-coercion-with-vo))
- **Empty-as-adult default** — when age is empty, the over-18 condition evaluates to true, hiding/disabling guardian fields. This prevents guardian fields from appearing before age is entered
- **`ctfd` serves different purposes** in the two variants: in Rule 52979 it resets on the over-18 branch (cleanup), while in Rule 52984 it derives on the under-18 branch (initialization)
- **No `cf` or `remerr`** — unlike [C-7](#c-7-cf--remerr--mviminvi--mmmnm--full-branch-visibility-with-mandatory), guardian fields are hidden/non-mandatory but not cleared or error-stripped. The assumption is that hiding + non-mandatory is sufficient reset
- **`mvi`/`minvi` target one extra field** (`_guardian_`) compared to `mm`/`mnm` — the guardian section header is shown/hidden but not made mandatory
- `execute_on_fill: false`, `execute_on_read: false`, `run_post_condition_fail: false` for both rules

**Frequency:** Rare. Observed in EPF/PF nomination forms with minor nominee handling.

### C-25. addSelectOptions + selectedOptionMetaDataId + copyMultiple + asdff — Focus-Populated Dynamic Dropdown with Conditional Multi-Field Copy

**Description:** A two-phase rule combining `on("focus")` and `on("change")` events. Phase 1 (`on("focus")`): dynamically builds a dropdown's option list from sibling field values using `addSelectOptions`. Phase 2 (`on("change")`): when the user selects an option, `selectedOptionMetaDataId` identifies which source field was selected, and `copyMultiple` copies a parallel set of related fields (e.g., relation, age, address) from the selected source into the destination fields. An unconditional `asdff` at the end persists all destination fields.

**When Used:** Gratuity/nomination forms where a nominee must be selected from a list of previously entered dependents. The dropdown is dynamically populated with dependent names, and selecting one auto-fills the nominee's relation, age, and address from the corresponding dependent's data.

**Generic Template:**
```
{on("focus") and addSelectOptions("<dropdown_field>",
  ["<source_name_1>", "<source_name_2>", ..., "<source_name_N>"]);
 on("change") and (
  (selectedOptionMetaDataId("<dropdown_field>")=="<source_name_1>"
   and copyMultiple(["<src_rel_1>","<src_age_1>","<src_addr_1>"],
                    ["<dest_rel>","<dest_age>","<dest_addr>"]))
  or (selectedOptionMetaDataId("<dropdown_field>")=="<source_name_2>"
   and copyMultiple(["<src_rel_2>","<src_age_2>","<src_addr_2>"],
                    ["<dest_rel>","<dest_age>","<dest_addr>"]))
  or ... (one branch per source)
  or asdff(true, "<dest_addr>", "<dest_age>", "<dest_rel>", "<other_dest>")
 )}
```

**Real Example (Rule 52987):**
```
{on("focus") and addSelectOptions("_gratuityNomName_",
  ["_dependentsName_","_dependentsName1_","_dependentsName2_","_dependentsName3_",
   "_dependentsName4_","_dependentsName5_","_dependentsName6_","_dependentsName7_",
   "_dependentsName8_","_dependentsName9_"]);
 on("change") and (
  (selectedOptionMetaDataId("_gratuityNomName_")=="_dependentsName_"
   and copyMultiple(["_dependentsRelation_","_dependentsDobAge_","_dependaddress_"],
                    ["_newRelationForm11_","_newRelForm1Age_","_gratuityNomAddress_"]))
  or (selectedOptionMetaDataId("_gratuityNomName_")=="_dependentsName1_"
   and copyMultiple(["_dependentsRelation1_","_dependentsDobAge1_","_dependaddress1_"],
                    ["_newRelationForm11_","_newRelForm1Age_","_gratuityNomAddress_"]))
  or ... (8 more branches for dependents 2–9)
  or asdff(true,"_gratuityNomAddress_","_newRelForm1Age_","_newRelationForm11_","_gratuityNomProportion_")
 )}
```

**Key Observations:**
- **Three new helper functions** not previously documented:
  - `addSelectOptions(dropdown, [field_list])` — builds dropdown options from field variable names at runtime
  - `selectedOptionMetaDataId(dropdown)` — returns the **variable name** (not value) of the selected option, enabling lookup by source identity
  - `copyMultiple([sources], [destinations])` — parallel array copy; `sources[0]` → `destinations[0]`, `sources[1]` → `destinations[1]`, etc.
- **Two-event pattern** — `on("focus")` for setup + `on("change")` for action (see [S-14](#s-14-onfocus-wrapper))
- **10 branches** — one per numbered dependent (suffix 0–9), each mapping to the same 3 destination fields from different source fields
- **`asdff` as final `or` branch** — the `asdff(true,...)` at the end of the `or` chain fires after any `copyMultiple` succeeds (or if no branch matches). It persists 4 destination fields unconditionally
- **`selectedOptionMetaDataId` returns variable names** — the comparison uses `=="_dependentsNameN_"` (the variable name string), not the displayed value. This is critical: the dropdown options ARE field references, and selection identifies WHICH field was chosen
- `source_ids` and `form_fill_metadata_id` are the **same** (134182) — the rule is placed on the dropdown field itself
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`

**Frequency:** Rare. Observed in gratuity nomination forms linking nominees to dependents.

### C-26. adderr/remerr + mvi/minvi + ctfd + asdff — Confirm Field Validation with Visibility and Status

**Description:** A confirm-field validation pattern that checks whether two fields (original and re-entered) match. On mismatch: adds an error, hides a dependent field, sets a status flag to "No", and saves. On match: removes the error, shows the dependent field, sets status to "Yes", and saves. The `adderr`/`remerr` return values drive `or`-branch selection.

**When Used:** QR ID confirmation, password re-entry, or any "enter twice to verify" pattern where a downstream action (e.g., uploading an ID card) should only be enabled when the two entries match.

**Generic Template:**
```
{(vo("<original>") and vo("<confirm>") and (
  asdff(true, "<confirm>");
  (adderr(vo("<confirm>")!=vo("<original>"), "<error_msg>", "<confirm>")
   and minvi(true, "<dependent_field>")
   and ctfd(true, "No", "<status_flag>") and asdff(true, "<status_flag>"))
  or (remerr(true, "<confirm>")
   and mvi(true, "<dependent_field>")
   and ctfd(true, "Yes", "<status_flag>") and asdff(true, "<status_flag>"))
))}
```

**Real Example (Rule 24601):**
```
{(vo("_qRID20_") and vo("_reenterQRID31_") and (
  asdff(true, "_reenterQRID31_");
  (adderr(vo("_reenterQRID31_")!=vo("_qRID20_"),
         "The QR ID and its confirm are not the same","_reenterQRID31_")
   and minvi(true, "_uploadIDCard71_")
   and ctfd(true,"No","_isactive34_") and asdff(true, "_isactive34_"))
  or (remerr(true,"_reenterQRID31_")
   and mvi(true, "_uploadIDCard71_")
   and ctfd(true,"Yes","_isactive34_") and asdff(true, "_isactive34_"))
))}
```

**Key Observations:**
- **Outer guard** — `vo("_qRID20_") and vo("_reenterQRID31_")` ensures both fields are non-empty before validating
- **Unconditional save first** — `asdff(true, "_reenterQRID31_")` persists the re-entered value before validation
- **`adderr` drives `or` branching** — `adderr` returns truthy when the error is added (mismatch), causing the `and`-chain to continue with `minvi` + `ctfd("No")`. When values match, `adderr`'s condition is false → it returns falsy → the `or` falls through to the `remerr` branch
- **`remerr(true,...)` in the match branch** — unconditional error removal because the `or` only reaches this branch when values match
- **Bidirectional effects from validation result:**
  - Mismatch → hide upload field (`minvi`) + set inactive (`ctfd("No")`)
  - Match → show upload field (`mvi`) + set active (`ctfd("Yes")`)
- **`asdff` on status field** — the active/inactive status is persisted immediately in both branches
- Extends [C-6](#c-6-ctfd--adderremerr--validation-with-status-derivation) by adding **visibility management** (`mvi`/`minvi`) alongside the validation status derivation
- `condition: ""` (empty), `execute_on_fill: true`, `run_post_condition_fail: true`

**Frequency:** Rare. Observed in QR ID confirmation fields with dependent upload gating.

### C-27. erbyid + rffdd — Delegate Then Refresh Self

**Description:** `erbyid` triggers re-evaluation of the field's own rules, followed by `rffdd` to refresh its dropdown options. Both are unconditional (`true`). This is a self-referencing "re-initialize on load" pattern placed on the field itself.

**When Used:** Dropdown fields that need their own rules re-evaluated and options refreshed when the form loads. The `erbyid` ensures any dependent logic fires, then `rffdd` refreshes the dropdown data.

**Generic Template:**
```
{erbyid(true, "<field>") and (rffdd(true, "<field>"))}
```

**Real Example (Rule 36693):**
```
{erbyid(true,"_numberOfPieces71_") and (rffdd(true, "_numberOfPieces71_"))}
```
Unconditionally re-evaluate the `_numberOfPieces71_` field's rules and refresh its dropdown options. `source_ids` and `form_fill_metadata_id` are both `106398` — self-referencing. `execute_on_fill: true`.

**Key Observations:**
- Both functions target the **same field** — self-referencing
- **`and` chaining** — `rffdd` only fires if `erbyid` succeeds
- **No condition logic** — both use `true`, pure initialization
- Distinct from [C-14](#c-14-ctfd--erbyid--derive-then-delegate) (derive then delegate to another field) — here there is no derivation, and the target is self
- `execute_on_fill: true`, `execute_on_read: false`, `run_post_condition_fail: false`

**Additional Examples (Rules 36738, 36745, 36748, 36810, 36807):** Five instances from a gold loan form follow the identical pattern for different calculated fields:
```
{erbyid(true,"_goldWeightIn18CaratInGrams97_") and (rffdd(true, "_goldWeightIn18CaratInGrams97_"))}
{erbyid(true,"_goldWeightIn22CaratInGrams75_") and (rffdd(true, "_goldWeightIn22CaratInGrams75_"))}
{erbyid(true,"_goldWeightIn24CaratInGrams69_") and (rffdd(true, "_goldWeightIn24CaratInGrams69_"))}
{erbyid(true,"_totalPledgedValue_") and (rffdd(true, "_totalPledgedValue_"))}
{erbyid(true,"_eligibleValueForLoan_") and (rffdd(true, "_eligibleValueForLoan_"))}
```
All `execute_on_fill: true`, `run_post_condition_fail: false`. These gold weight/value fields form a computation chain where each field's rules must re-evaluate and refresh when the form loads.

**Frequency:** Common in forms with calculated/derived fields. Observed across gold loan valuation, piece counting, and other computed field forms. At least 6 confirmed instances.

