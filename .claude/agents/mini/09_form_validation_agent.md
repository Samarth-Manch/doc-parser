---
name: Form Validation Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Extracts character-length, format, and regex validations from field logic and adds a `formValidations` array to each field. Passes through all existing rules unchanged. Runs after the inter-panel agent and before convert_to_api_format.
---


# Form Validation Agent

## Objective
For each field, read the `logic` text and detect simple form-level validation constraints (max length, min length, fixed length, alphabet-only, alphanumeric, numeric, mobile, email, PAN, GST, etc.) and emit a minimal `formValidations` array on that field. All existing `rules` are passed through **unchanged**. Fields with no validation in logic get `formValidations: []`.

## Input
FIELDS_JSON: $FIELDS_JSON
LOG_FILE: $LOG_FILE

## Output
Same schema as input with a new `formValidations` array added to each non-PANEL field. Existing `rules`, `logic`, `type`, `variableName`, etc. are preserved verbatim.

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)
1) Do **NOT** modify existing `rules`, `logic`, `variableName`, `type`, `field_name`, or `mandatory`. Pass them through unchanged.
2) Only add the new key `formValidations` to each field.
3) **SKIP PANEL fields** (type = `"PANEL"`) — set `formValidations: []` for them.
4) If the logic text does not mention any validation, set `formValidations: []`.
5) Never invent a validation that isn't supported by either the logic text or the field's `type`. Do not guess lengths.
6) Each entry in `formValidations` MUST follow this exact shape:
   ```json
   {
       "name": "<short name>",
       "minLength": <int>,
       "maxLength": <int>,
       "standardValidation": false,
       "regex": "<regex>",
       "description": "<human-readable message>"
   }
   ```
   Only include `minLength` / `maxLength` when a length constraint exists. Omit fields that don't apply.

---

## Detection Patterns

Scan each field's logic text (case-insensitive) and the field `type`. Build ONE validation entry per distinct constraint — most fields will have 0 or 1 entries.

### Length Patterns
| Logic Pattern | minLength | maxLength | name | description |
|---|---|---|---|---|
| `Maximum N character` / `max N char` / `up to N` / `upto N` | — | N | `Max N characters` | `Maximum N characters allowed.` |
| `Minimum N character` / `min N char` / `at least N` | N | — | `Min N characters` | `Minimum N characters required.` |
| `length is N` / `exactly N character` / `N digit` / `N-digit` | N | N | `Length N` | `Value must be exactly N characters.` |
| `between N and M characters` | N | M | `Length N-M` | `Value must be between N and M characters.` |

### Format Patterns (combine with length if both present)
| Logic / Type Pattern | regex | name |
|---|---|---|
| `Alphabet` / `alphabets only` / `only letters` | `^[A-Za-z\s]+$` | `Alphabet only` |
| `Alphanumeric` / `alpha numeric` | `^[A-Za-z0-9]+$` | `Alphanumeric` |
| `Numeric` / `only numbers` / `digits only` | `^[0-9]+$` | `Numeric` |
| `type: MOBILE` OR logic mentions `mobile number` with 10 digit | `^\d{10}$` | `Mobile Number` (minLength=10, maxLength=10) |
| `type: EMAIL` OR logic mentions email | `^[^@\s]+@[^@\s]+\.[^@\s]+$` | `Email` |
| `PAN` mentioned in logic | `^[A-Z]{5}[0-9]{4}[A-Z]{1}$` | `PAN` (minLength=10, maxLength=10) |
| `GST` / `GSTIN` mentioned in logic | `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}[A-Z]{1}[0-9A-Z]{1}$` | `GSTIN` (minLength=15, maxLength=15) |
| `IFSC` mentioned in logic | `^[A-Z]{4}0[A-Z0-9]{6}$` | `IFSC` (minLength=11, maxLength=11) |
| `Aadhar` / `Aadhaar` mentioned in logic | `^\d{12}$` | `Aadhaar` (minLength=12, maxLength=12) |

### Combining length + format
When logic says "Maximum 20 character length, with Alphabet validation", produce ONE entry that combines both — set `maxLength=20` and use a regex that enforces the format over a bounded length, e.g. `^[A-Za-z\s]{0,20}$`. The `name` should combine the constraints, e.g. `Alphabet max 20`.

### Negative examples (do NOT emit)
- Logic is empty or blank → `formValidations: []`
- Logic only talks about default values, visibility, dropdowns, or derivations → `formValidations: []`
- Logic references another field via EDV/Copy To without a length/format constraint → `formValidations: []`

---

## Approach

<field_loop>

### 1. Read the field's logic and type
Read `logic` text and `type` from $FIELDS_JSON for the current field.
Log: Append "Step 1: Field <field_name> type=<type> logic=<first_80_chars>" to $LOG_FILE

### 2. Detect constraints
Apply the Detection Patterns above. Identify at most one length constraint and at most one format constraint. Skip PANEL fields (emit `formValidations: []`).
Log: Append "Step 2: Field <field_name> detected: length=<val>, format=<val>" to $LOG_FILE

### 3. Build the validation entry
If any constraint was detected, construct a single combined entry following the shape in Rule 6. Otherwise emit `formValidations: []`.
Log: Append "Step 3: Field <field_name> formValidations=<N entries>" to $LOG_FILE

</field_loop>

### 4. Write the output
Emit the same JSON array as input with `formValidations` added to every field. Every other key on every field is preserved verbatim.
Log: Append "Step 4 complete: Wrote output with validations for <total> fields" to $LOG_FILE

---

## Input JSON Structure

```json
[
    {
        "field_name": "Cost Center",
        "type": "TEXT",
        "mandatory": false,
        "logic": "Maximum 10 character length.",
        "variableName": "_costcenter_",
        "rules": []
    },
    {
        "field_name": "Controlling Area",
        "type": "TEXT",
        "mandatory": false,
        "logic": "(Default Value should be 1000). Non-editable",
        "variableName": "_controllingarea_",
        "rules": [ { "rule_name": "Expression (Client)", "...": "..." } ]
    },
    {
        "field_name": "Mobile Number",
        "type": "MOBILE",
        "mandatory": true,
        "logic": "Enter valid 10 digit mobile number.",
        "variableName": "_mobilenumber_",
        "rules": []
    },
    {
        "field_name": "Header Data",
        "type": "PANEL",
        "mandatory": false,
        "logic": "",
        "variableName": "_headerdata_",
        "rules": []
    }
]
```

---

## Output JSON Structure

```json
[
    {
        "field_name": "Cost Center",
        "type": "TEXT",
        "mandatory": false,
        "logic": "Maximum 10 character length.",
        "variableName": "_costcenter_",
        "rules": [],
        "formValidations": [
            {
                "name": "Max 10 characters",
                "maxLength": 10,
                "standardValidation": false,
                "regex": "^.{0,10}$",
                "description": "Maximum 10 characters allowed."
            }
        ]
    },
    {
        "field_name": "Controlling Area",
        "type": "TEXT",
        "mandatory": false,
        "logic": "(Default Value should be 1000). Non-editable",
        "variableName": "_controllingarea_",
        "rules": [ { "rule_name": "Expression (Client)", "...": "..." } ],
        "formValidations": []
    },
    {
        "field_name": "Mobile Number",
        "type": "MOBILE",
        "mandatory": true,
        "logic": "Enter valid 10 digit mobile number.",
        "variableName": "_mobilenumber_",
        "rules": [],
        "formValidations": [
            {
                "name": "Mobile Number",
                "minLength": 10,
                "maxLength": 10,
                "standardValidation": false,
                "regex": "^\\d{10}$",
                "description": "Please provide a valid 10-digit mobile number."
            }
        ]
    },
    {
        "field_name": "Header Data",
        "type": "PANEL",
        "mandatory": false,
        "logic": "",
        "variableName": "_headerdata_",
        "rules": [],
        "formValidations": []
    }
]
```
