# Issue 2: Session-Based Agent Picks Wrong Source Field for Conditional Visibility

## Summary

The session-based mini agent selects `_processtypebasicdetails_` (a derived hidden TEXT field) as the source for conditional visibility rules, but checks for value `"India"`. This field never contains `"India"` — it contains `"DOM IN"` or `"INT"`. The condition never matches, so affected fields are permanently hidden in second party.

## Affected Fields

- `_doyouwishtoaddadditionalmobilenumbersindiabasicdetails_` ("Do you wish to add additional mobile numbers (India)?")
- `_doyouwishtoaddadditionalmobilenumbersnonindiabasicdetails_` ("Do you wish to add additional mobile numbers (Non-India)?")
- Potentially any field whose session-based visibility depends on "Process Type"

## Root Cause

There are two similarly named fields in Basic Details:

| Field Name | variableName | Type | Values |
|---|---|---|---|
| Select the process type | `_selecttheprocesstypebasicdetails_` | EXTERNAL_DROP_DOWN_VALUE | `India`, `International` |
| Process Type | `_processtypebasicdetails_` | TEXT (hidden, derived) | `DOM IN`, `INT` |

The session-based mini agent picked `_processtypebasicdetails_` as the source field. The BUD 4.5.2 logic says "Visible if Process type is India" — the agent matched "Process type" to the wrong field.

## What Happens at Runtime

The generated rules (on `_processtypebasicdetails_` in `all_panels_session_based.json`):

```json
{
    "rule_name": "Make Visible - Session Based (Client)",
    "source_fields": ["_processtypebasicdetails_"],
    "destination_fields": ["_doyouwishtoaddadditionalmobilenumbersindiabasicdetails_"],
    "params": "SECOND_PARTY",
    "conditionalValues": ["India"],
    "condition": "IN"
}
```

```json
{
    "rule_name": "Make Invisible - Session Based (Client)",
    "source_fields": ["_processtypebasicdetails_"],
    "destination_fields": ["_doyouwishtoaddadditionalmobilenumbersindiabasicdetails_"],
    "params": "SECOND_PARTY",
    "conditionalValues": ["India"],
    "condition": "NOT_IN"
}
```

At runtime, `_processtypebasicdetails_` = `"DOM IN"` (when India is selected):

1. `IN ["India"]` on `"DOM IN"` -> **false** -> Make Visible never fires
2. `NOT_IN ["India"]` on `"DOM IN"` -> **true** -> Make Invisible always fires

Result: field is permanently hidden in second party regardless of selection.

## Correct Fix

The source field should be `_selecttheprocesstypebasicdetails_` (the dropdown with actual `"India"` / `"International"` values):

```json
{
    "rule_name": "Make Visible - Session Based (Client)",
    "source_fields": ["_selecttheprocesstypebasicdetails_"],
    "destination_fields": ["_doyouwishtoaddadditionalmobilenumbersindiabasicdetails_"],
    "params": "SECOND_PARTY",
    "conditionalValues": ["India"],
    "condition": "IN"
}
```

## Where to Fix

The session-based mini agent prompt needs guidance to distinguish between a user-facing dropdown and its derived hidden counterpart. When the BUD logic says "if Process type is India", the agent should resolve to the dropdown field that has `"India"` as a selectable value, not the derived field that stores a mapped code.

## Run Details

- Output: `output/vendor/runs/6/session_based/all_panels_session_based.json`
- Wrong rules at lines: 870-915 (conditional visibility on Process Type for SECOND_PARTY)
- Stage: Session Based (Stage 7)
