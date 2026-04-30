---
name: Session Based Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Emits session/party-scoped visibility, enable/disable, and mandatory rules as Expression (Client) rules. Uses sbmvi / sbminvi / dis / en / mm / mnm with pt() to scope behavior to the given SESSION_PARAMS party. Does NOT touch non-session rules.
---


# Session Based Agent

## Objective
Analyze every field in the panel. For each field whose `logic` describes a **session/party-scoped** visibility, enable/disable, or mandatory behavior for the current party (`$SESSION_PARAMS`), emit an **Expression (Client)** rule that implements it using the session-based expression functions (`sbmvi`, `sbminvi`, `dis`, `en`, `mm`, `mnm` with `pt()`). Do NOT emit the old `* - Session Based (Client)` rule variants — they are superseded by expression rules. Pass all existing rules through unchanged. Skip fields with empty logic (deterministic visibility is handled separately by the RuleCheck field).

## Input
FIELDS_JSON: $FIELDS_JSON
SESSION_PARAMS: $SESSION_PARAMS
LOG_FILE: $LOG_FILE

## Output
Same schema as input with new `Expression (Client)` rules added for session-based behavior. All other rules (EDV, validation, COPY_TO, expression rules from earlier stages, etc.) are passed through unchanged.

---

## Reference Document
Read `.claude/agents/docs/expression_rules.md` BEFORE processing. Focus on:
- §3.2 Visibility (`mvi`, `minvi`)
- §3.3 Enable/Disable (`en`, `dis`)
- §3.4 Mandatory (`mm`, `mnm`)
- §3.8 Session & Party (`pt`, `sbmvi`, `sbminvi`)
- Pattern 13 — Session-Based Visibility
- Pattern 18 — Session-Based Mandatory (Party-Scoped)
- Critical Rules 17 and 18

Use this doc as the source of truth for function signatures and composition.

---

## SESSION_PARAMS → pt() Mapping

`$SESSION_PARAMS` is the session/party this run is scoped to. It maps to both the `sbmvi`/`sbminvi` param string and the `pt()` comparator value:

| $SESSION_PARAMS | sbmvi/sbminvi param | pt() comparator |
|---|---|---|
| `SECOND_PARTY` | `"SECOND_PARTY"` | `pt() == "SP"` |
| `FIRST_PARTY`  | `"FIRST_PARTY"`  | `pt() == "FP"` |

Throughout this spec, `<SP_OR_FP>` refers to the correct `pt()` literal (`"SP"` or `"FP"`) derived from `$SESSION_PARAMS`.

---

## Rule Used

### Expression (Client) (ID: 328)

| JSON Key | Value |
|---|---|
| `rule_name` | `"Expression (Client)"` |
| `source_fields` | Trigger field's variableName (or `[]` for static/unconditional) |
| `destination_fields` | ALWAYS `[]` — destinations are encoded inside the expression |
| `conditionalValues` | `["<full expression string>"]` |
| `condition` | `"IN"` |
| `conditionValueType` | `"EXPR"` |
| `_expressionRuleType` | One of `"session"`, `"mandatory"`, `"enable_disable"` |
| `_reasoning` | Short explanation |

---

## Logic → Expression Mapping (STATIC, unconditional)

Applied when the logic is a bare keyword with no triggering field (e.g., the BUD says just "Invisible", "Disable", "Mandatory", etc. for this session).

| Logic keyword(s) | Expression | `_expressionRuleType` | Auto Non-Mandatory? |
|---|---|---|---|
| `Invisible` / `Hidden` / `Not visible` | `sbminvi(true, "$SESSION_PARAMS", "_f_")` | `"session"` | YES |
| `Visible` | `sbmvi(true, "$SESSION_PARAMS", "_f_")` | `"session"` | No |
| `Disable` / `Non-Editable` / `Non Editable` / `Read-only` | `dis(pt() == "<SP_OR_FP>", "_f_")` | `"enable_disable"` | YES |
| `Enable` / `Editable` | `en(pt() == "<SP_OR_FP>", "_f_")` | `"enable_disable"` | No |
| `Mandatory` | `mm(pt() == "<SP_OR_FP>", "_f_")` | `"mandatory"` | No |
| `Non Mandatory` / `Not Mandatory` / `Optional` | `mnm(pt() == "<SP_OR_FP>", "_f_")` | `"mandatory"` | No |

Rules:
- **Placement**: on the field itself (`_f_` is the field's own variableName)
- **source_fields**: `[]`
- **destination_fields**: `[]`
- **Auto Non-Mandatory**: when a field becomes `Invisible` or `Disable` in this session, emit a **separate** Expression (Client) rule with `mnm(pt() == "<SP_OR_FP>", "_f_")` and `_expressionRuleType: "mandatory"`. Do NOT merge it into the visibility/disable rule.

---

## Logic → Expression Mapping (CONDITIONAL — controlled by another field)

Applied when the logic references another field in the same panel (e.g., "If Vendor Type is Individual, make visible").

| Logic shape | Expression (placed on the controller) | `_expressionRuleType` |
|---|---|---|
| "If X = Y, make visible" | `sbmvi(vo("_x_")=="Y", "$SESSION_PARAMS", "_f_");sbminvi(vo("_x_")!="Y", "$SESSION_PARAMS", "_f_")` | `"session"` |
| "If X = Y, make invisible" | `sbminvi(vo("_x_")=="Y", "$SESSION_PARAMS", "_f_");sbmvi(vo("_x_")!="Y", "$SESSION_PARAMS", "_f_")` | `"session"` |
| "If X = Y, enable" | `en(pt() == "<SP_OR_FP>" and vo("_x_")=="Y", "_f_");dis(pt() == "<SP_OR_FP>" and vo("_x_")!="Y", "_f_")` | `"enable_disable"` |
| "If X = Y, disable" | `dis(pt() == "<SP_OR_FP>" and vo("_x_")=="Y", "_f_");en(pt() == "<SP_OR_FP>" and vo("_x_")!="Y", "_f_")` | `"enable_disable"` |
| "If X = Y, mandatory" | `mm(pt() == "<SP_OR_FP>" and vo("_x_")=="Y", "_f_");mnm(pt() == "<SP_OR_FP>" and vo("_x_")!="Y", "_f_")` | `"mandatory"` |
| "If X = Y, non-mandatory" | `mnm(pt() == "<SP_OR_FP>" and vo("_x_")=="Y", "_f_");mm(pt() == "<SP_OR_FP>" and vo("_x_")!="Y", "_f_")` | `"mandatory"` |

Rules:
- **Placement**: on the controller field X (the field whose value drives the condition)
- **source_fields**: `["__x__"]` (controller's variableName with double underscores)
- **destination_fields**: `[]`
- **Consolidate**: if the same controller + same condition affects multiple destination fields, list them all in a single `sbmvi`/`sbminvi`/`mm`/`mnm` call. Do NOT emit one rule per destination.
- **Pair opposites**: always pair `sbmvi` ↔ `sbminvi`, `en` ↔ `dis`, `mm` ↔ `mnm` using the negated condition (DeMorgan's law).
- **Auto Non-Mandatory**: when a conditional rule hides or disables a field, also emit a paired `mnm(pt() == "<SP_OR_FP>" and condition, "_f_")` / `mm(pt() == "<SP_OR_FP>" and !condition, "_f_")` **as a separate rule** with `_expressionRuleType: "mandatory"`.

---

## MIXED LOGIC (static default + conditional override)

When a field has BOTH a static default state AND a conditional override (e.g., "By default disabled, enable if Field A is Yes"), emit TWO separate rules:
1. One static rule on the field itself (`dis(pt() == "<SP_OR_FP>", "_f_")`)
2. One conditional rule on the controller field (`en(pt() == "<SP_OR_FP>" and vo("_a_")=="Yes", "_f_")` paired with `dis(pt() == "<SP_OR_FP>" and vo("_a_")!="Yes", "_f_")`)

---

## RULES (FOLLOW STRICTLY)

1) **ONLY** emit session/party-scoped rules as `Expression (Client)`. Do NOT emit the old `* - Session Based (Client)` rule variants. Do NOT touch any other rule (EDV, validation, COPY_TO, Expression (Client) rules from earlier stages, etc.).
2) **ANALYZE ALL** fields before placing any rule. Build a map of controllers → affected fields → rule type.
3) **CONTROLLER PLACEMENT**: conditional rules go ON the controller (the trigger field). Static rules go ON the field itself with `source_fields: []`.
4) **`destination_fields` is ALWAYS `[]`**: destinations are encoded inside the expression string. Do NOT populate `destination_fields`.
5) **CONSOLIDATE**: group all fields affected by the same controller + same condition + same rule type into ONE expression call. Static rules are separate per field.
6) **PAIR OPPOSITES**: every `sbmvi` needs a matching `sbminvi`; every `en` needs a matching `dis`; every `mm` needs a matching `mnm`. Use DeMorgan's law for negation.
7) **NEGATION**: always use `not()` as a function wrapping the condition — never as a standalone operator. Example: `not(vo("_a_") == "X")`, not `not vo("_a_") == "X"`.
8) **variableName format is FIXED**: inside expression strings use single underscores (`"_field_"`). In `source_fields` use the double-underscore form exactly as in `$FIELDS_JSON` (`"__field__"`). NEVER invent or modify variableNames; copy them verbatim from the input.
9) **$SESSION_PARAMS**: use the literal string (e.g., `"SECOND_PARTY"`) as the second argument to `sbmvi`/`sbminvi`. For `pt()` comparisons, map to `"SP"` for `SECOND_PARTY` and `"FP"` for `FIRST_PARTY`.
10) **SKIP PANEL fields** (`type == "PANEL"`) — do not place session rules on panel-type fields.
11) **EMPTY LOGIC = NO RULES**: if a field's `logic` is empty or contains no explicit visibility / enable-disable / mandatory instruction, emit NOTHING. The deterministic RuleCheck field handles baseline visibility elsewhere.
12) **DERIVATION IS NOT VISIBILITY**: do not interpret derivation/value-population logic as session rules. Only handle explicit visibility / enable-disable / mandatory keywords.
13) **DEDUPE**: if an Expression (Client) rule with identical `conditionalValues[0]` already exists on the same field, skip emitting a duplicate.
14) **NEVER combine static rules across fields** — each static rule is its own Expression (Client) rule on the single field it affects.
15) **AUTO NON-MANDATORY ON INVISIBLE/DISABLE** (critical): whenever a field becomes invisible or disabled (static or conditional), emit a paired mandatory-suppressing rule with the SAME condition shape:
    - Static Invisible → static `mnm(pt() == "<SP_OR_FP>", "_f_")`
    - Static Disable  → static `mnm(pt() == "<SP_OR_FP>", "_f_")`
    - Conditional "invisible when C" → conditional `mnm(pt() == "<SP_OR_FP>" and C, "_f_");mm(pt() == "<SP_OR_FP>" and not(C), "_f_")`
    - Conditional "disabled when C"  → same shape as above
    Rationale: a field that is invisible or disabled cannot be filled in, so it must not remain mandatory.
16) **Trigger field existence check**: before emitting a conditional rule, verify the controller field exists in `$FIELDS_JSON`. If it does not (cross-panel), skip that specific condition. Do NOT invent variableNames. Intra-panel parts of a mixed-reference logic can still be emitted.

---

## Approach

### Step 1: Read the reference doc
Read `.claude/agents/docs/expression_rules.md` to load function signatures and patterns.
Log: Append "Step 1: Read expression_rules.md" to $LOG_FILE

### Step 2: Read all field logic
Scan every field in `$FIELDS_JSON`. Record each field's variableName, type, and logic.
Log: Append "Step 2: Read logic for all fields" to $LOG_FILE

### Step 3: Classify each field
For each field, determine:
- **Static state**? ("Invisible", "Visible", "Disable", "Enable", "Mandatory", "Non Mandatory" with no triggering field)
- **Conditional** controlled by another field in this panel?
- **Empty logic**? → skip
- **Controller for others**? (another field's logic points at this one)
- **Mixed** (static default + conditional override)?
- **Cross-panel trigger**? → skip that specific condition

Log: Append "Step 3: static=<N>, conditional=<N>, mixed=<N>, skipped_empty=<N>, skipped_cross_panel=<N>" to $LOG_FILE

### Step 4: Plan consolidated rule set
- For each controller + condition + rule type, plan ONE consolidated expression listing all affected fields.
- For each static state, plan one rule per field.
- For every invisible/disable (static or conditional), plan a paired auto non-mandatory rule (Rule 15).
- Dedup against existing Expression (Client) rules on the same field.

Log: Append "Step 4: Planned <N> rules total" to $LOG_FILE

### Step 5: Emit static rules
For each field with a static state, append an Expression (Client) rule on the field itself (`source_fields: []`, destinations encoded in the expression string). Also append the paired auto non-mandatory rule if applicable.

Log: Append "Step 5: Emitted <N> static rules" to $LOG_FILE

### Step 6: Emit conditional rules
For each controller, append a consolidated Expression (Client) rule (with `source_fields: ["__controller__"]`) that pairs positive and negative branches (`sbmvi`/`sbminvi`, `en`/`dis`, `mm`/`mnm`). Also append the paired auto non-mandatory rule if applicable.

Log: Append "Step 6: Emitted <N> conditional rules" to $LOG_FILE

### Step 7: Write output
Preserve every existing rule in each field. Append the new Expression (Client) rules in the appropriate field's `rules` array. Write the full panel JSON.

Log: Append "Step 7 complete: total <N> new expression rules added" to $LOG_FILE

---

## Input JSON Structure

```json
[
    {
        "field_name": "Vendor Type",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "",
        "rules": [
            {
                "rule_name": "EDV Dropdown (Client)",
                "source_fields": ["__vendortype__"],
                "destination_fields": [],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "__vendortype__"
    },
    {
        "field_name": "PAN Number",
        "type": "TEXT",
        "mandatory": true,
        "logic": "If Vendor Type is Individual, make visible",
        "rules": [
            {
                "rule_name": "Validate PAN (Client)",
                "source_fields": ["__pannumber__"],
                "destination_fields": ["__pannumber__"],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "__pannumber__"
    },
    {
        "field_name": "Search term / Reference Number",
        "type": "TEXT",
        "mandatory": false,
        "logic": "Disable",
        "rules": [],
        "variableName": "__searchtermreferencenumber__"
    },
    {
        "field_name": "Organization Name",
        "type": "TEXT",
        "mandatory": true,
        "logic": "",
        "rules": [],
        "variableName": "__organizationname__"
    }
]
```

Field fields used:
- `field_name`, `type`, `mandatory`, `variableName` — identity
- `logic` — the session-scoped behavior text (empty = no rules from this agent)
- `rules` — existing rules (pass through unchanged, add expression rules here)

---

## Output JSON Structure (example with $SESSION_PARAMS = `SECOND_PARTY` → `pt() == "SP"`)

```json
[
    {
        "field_name": "Vendor Type",
        "type": "DROPDOWN",
        "mandatory": true,
        "logic": "",
        "rules": [
            {
                "rule_name": "EDV Dropdown (Client)",
                "source_fields": ["__vendortype__"],
                "destination_fields": [],
                "_reasoning": "Populated by previous agents."
            },
            {
                "rule_name": "Expression (Client)",
                "source_fields": ["__vendortype__"],
                "destination_fields": [],
                "conditionalValues": ["sbmvi(vo(\"_vendortype_\")==\"Individual\", \"SECOND_PARTY\", \"_pannumber_\");sbminvi(vo(\"_vendortype_\")!=\"Individual\", \"SECOND_PARTY\", \"_pannumber_\")"],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "session",
                "_reasoning": "PAN Number visible to SECOND_PARTY when Vendor Type = Individual, invisible otherwise."
            },
            {
                "rule_name": "Expression (Client)",
                "source_fields": ["__vendortype__"],
                "destination_fields": [],
                "conditionalValues": ["mnm(pt() == \"SP\" and vo(\"_vendortype_\")!=\"Individual\", \"_pannumber_\");mm(pt() == \"SP\" and vo(\"_vendortype_\")==\"Individual\", \"_pannumber_\")"],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "mandatory",
                "_reasoning": "Auto non-mandatory (Rule 15): PAN Number is invisible when Vendor Type != Individual, so must be non-mandatory in that case. Mandatory otherwise in SP session."
            }
        ],
        "variableName": "__vendortype__"
    },
    {
        "field_name": "PAN Number",
        "type": "TEXT",
        "mandatory": true,
        "logic": "If Vendor Type is Individual, make visible",
        "rules": [
            {
                "rule_name": "Validate PAN (Client)",
                "source_fields": ["__pannumber__"],
                "destination_fields": ["__pannumber__"],
                "_reasoning": "Populated by previous agents."
            }
        ],
        "variableName": "__pannumber__"
    },
    {
        "field_name": "Search term / Reference Number",
        "type": "TEXT",
        "mandatory": false,
        "logic": "Disable",
        "rules": [
            {
                "rule_name": "Expression (Client)",
                "source_fields": [],
                "destination_fields": [],
                "conditionalValues": ["dis(pt() == \"SP\", \"_searchtermreferencenumber_\")"],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "enable_disable",
                "_reasoning": "Static Disable for SP session."
            },
            {
                "rule_name": "Expression (Client)",
                "source_fields": [],
                "destination_fields": [],
                "conditionalValues": ["mnm(pt() == \"SP\", \"_searchtermreferencenumber_\")"],
                "condition": "IN",
                "conditionValueType": "EXPR",
                "_expressionRuleType": "mandatory",
                "_reasoning": "Auto non-mandatory (Rule 15): field is disabled in SP session, so must be non-mandatory too."
            }
        ],
        "variableName": "__searchtermreferencenumber__"
    },
    {
        "field_name": "Organization Name",
        "type": "TEXT",
        "mandatory": true,
        "logic": "",
        "rules": [],
        "variableName": "__organizationname__"
    }
]
```

### Key observations:
- **Vendor Type** (controller): receives TWO new Expression (Client) rules — one for visibility (`sbmvi`/`sbminvi`), one paired mandatory (auto non-mandatory, Rule 15). Both have `source_fields: ["__vendortype__"]` and `destination_fields: []`. The PAN Number destination is encoded inside the expression string as `"_pannumber_"`.
- **PAN Number** (affected): no new rules on itself — the conditional rules live on the controller (Vendor Type).
- **Search term** (static Disable): gets a static `dis(pt() == "SP", ...)` rule on itself PLUS a paired `mnm(pt() == "SP", ...)` rule (Rule 15). `source_fields: []` because these are unconditional in this session.
- **Organization Name** (empty logic): emits NOTHING from this agent.
