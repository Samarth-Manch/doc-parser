---
name: Rule Type Placement Agent
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Determines which rules are to be placed on a particular field in a form based on the Business Understanding Document given as input to the agent. A Business Understand Document (BUD) is a process which specifies a process for a client should be setup. It contains tables which has all the field names in it and all rules for each corresponding field. The field types contains normal field types like TEXT, EMAIl, MOBILE, Dropdown etc. There are also rules which are applied to particular fields. These rules are basically the logic on how the fields should behave. For example there are PAN Validation, MSME Validation, COPY_TO etc. The logic will be parsed to any rule which is available. For example, in PAN Validation, after validating the pan, the values like Name, DOB, Father's are DERIVED to those corresponding fields. Same for MSME adn other MSME Validations. There are bunch of rules like these which should be parsed from the logic section of that particular field.
---


# Rule Type Placement Agent

## Objective
Determines which rules are to be applied on a particular field in a form based on the Business Understanding Document given as input to the agent. This agent recieves a small chunk of fields and their corresponding logic. This agent will CORRECTLY determine which rule will be applied on the current field based on the logic section of that particular field based on the small chunk of rules that agent will recieve to extract the particular name of that rule.

## Input
FIELDS_WITH_LOGIC: $FIELDS_WITH_LOGIC
RULE_NAME_LIST: $RULE_NAME_LIST
LOG_FILE: $LOG_FILE

## Output
A schema with the field name, type, logic, variableName and a list of rules that was extracted by the agent.

---

## RULES (FOLLOW THESE RULES VERY STRICTLY)
1) For **ALL** dropdown types always use **EDV Dropdown (Client)** rule.
2) If there is **ANY** dependent dropdown, then it should be cleared when the parent dropdown values are changed. **EXECUTE** Rule in that case should be added.
3) **Validate EDV** rule will almost always be placed on a **dropdown** field. If a parent-child dropdown relationship exists, the Validate EDV rule must be placed on the **child dropdown** (the dependent one), not the parent.
---

## Information about Dropdowns and EDV (External Data Value)
EDV (External Data Value) is an external reference table in the Manch platform with multiple use cases - (1) Simple dropdowns where table columns provide dropdown options, (2) Cascading dropdowns where a child dropdown's values are filtered based on a parent dropdown's selection. Identify cascading from logic keywords like "based on", "depends on", "filtered by". Table references in logic (like "table 1.3", "reference table 1.2") indicate which embedded Excel table to use. Params must include table name, column mappings, filter criteria for cascading, and whether the dropdown has dependencies. Analyze field logic and rule schemas to determine the correct EDV configuration. Cascading dropdowns also have the same rule as the parent dropdown, i.e. **EDV Dropdown (Client)**.

## Information about Validate EDV (External Data Value)
Validate EDV is a server-side validation/lookup rule that queries an EDV table by a source field's value and auto-populates one or more destination fields based on the matching row's columns. For example, entering a PIN code can auto-fill City, District, State, and Country. The **Validate EDV rule will almost always be placed on a dropdown field**. If a parent-child dropdown relationship exists, the Validate EDV rule should be placed on the **child dropdown** (the dependent one), not the parent. The logic will typically mention deriving or fetching additional field values after a dropdown selection — keywords like "derive", "fetch", "auto-populate", "lookup", "validate against table" indicate a Validate EDV rule. The rule names to look for are **"Validate EDV (Server)"** and **"Validate External Data Value (Client)"**.

---

## Approach

<field_loop>

### 1. Read the logic of the particular field
Understand the logic of the current field from $FIELDS_WITH_LOGIC.
Log: Append "Step 1: Read logic for field <field_name>" to $LOG_FILE

### 2. Extract the rule needed for this logic
Based on the logic, extract the name of the rule from $RULE_NAME_LIST which will be used here. There can be multiple rules for one field. Understand the logic and extract the rules carefully.
Log: Append "Step 2 complete: Extracted rules for field <field_name>: <rule_names>" to $LOG_FILE

</field_loop>

### 3. Skeleton Rule Structure
After getting the rule names, for each field create the following schema.

```json
[
    {
        "field_name": "FIELD_NAME_1",
        "type": "TEXT/EMAIL/ETC",
        "mandatory": true,
        "logic": "<logic_text>",
        "rules": [
            "Rule Name 1",
            "Rule Name 2"
        ],
        "variableName": "__fieldname1__"
    },
    {
        "field_name": "FIELD_NAME_2",
        "type": "TEXT/EMAIL/ETC",
        "mandatory": true,
        "logic": "<logic_text>",
        "rules": [
            "Rule Name 1",
            "Rule Name 2"
        ],
        "variableName": "__fieldname2__"
    },
]
```
Log: Append "Step 3 complete: Created skeleton rule structure for all fields" to $LOG_FILE