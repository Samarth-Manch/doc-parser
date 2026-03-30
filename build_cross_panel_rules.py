import json

with open('output/ph/runs/3/inter_panel/temp/complex_corporate_marketing___corporatemarketingotherdetails___panels.json') as f:
    panels = json.load(f)

with open('output/ph/runs/3/inter_panel/temp/complex_corporate_marketing___corporatemarketingotherdetails___refs.json') as f:
    refs = json.load(f)

dest_var = '_corporatemarketingotherdetails_'

rules_to_place = {
    '_companytypebasicdetails_': {
        'rule_name': 'Expression (Client)',
        'source_fields': ['_companytypebasicdetails_'],
        'destination_fields': [],
        'conditionalValues': ['on("change") and (cf(true, "' + dest_var + '");asdff(true, "' + dest_var + '");rffdd(true, "' + dest_var + '"))'],
        'condition': 'IN',
        'conditionValueType': 'EXPR',
        '_expressionRuleType': 'clear_field',
        '_reasoning': 'Cross-panel clearing: Clear Corporate Marketing in Other Details when Company Type in Basic Details changes.'
    },
    '_selectthephleveltobecreatedbasicdetails_': {
        'rule_name': 'Expression (Client)',
        'source_fields': ['_selectthephleveltobecreatedbasicdetails_'],
        'destination_fields': [],
        'conditionalValues': ['on("change") and (cf(true, "' + dest_var + '");asdff(true, "' + dest_var + '");rffdd(true, "' + dest_var + '"))'],
        'condition': 'IN',
        'conditionValueType': 'EXPR',
        '_expressionRuleType': 'clear_field',
        '_reasoning': 'Cross-panel clearing: Clear Corporate Marketing in Other Details when Select the PH level to be created in Basic Details changes.'
    }
}

output = {}
for panel_name, fields in panels.items():
    new_fields = []
    for field in fields:
        field_copy = dict(field)
        var = field_copy.get('variableName', '')
        if var in rules_to_place:
            existing_rules = field_copy.get('rules', [])
            has_clearing = any(
                r.get('rule_name') == 'Expression (Client)' and
                any('cf(' in cv for cv in r.get('conditionalValues', [])) and
                any(dest_var in cv for cv in r.get('conditionalValues', []))
                for r in existing_rules
            )
            if not has_clearing:
                field_copy['rules'] = list(existing_rules) + [rules_to_place[var]]
        new_fields.append(field_copy)
    output[panel_name] = new_fields

out_path = 'output/ph/runs/3/inter_panel/temp/complex_corporate_marketing___corporatemarketingotherdetails___rules.json'
with open(out_path, 'w') as f:
    json.dump(output, f, indent=2)

log_path = 'output/ph/runs/3/inter_panel/temp/complex_corporate_marketing___corporatemarketingotherdetails___log.txt'
with open(log_path, 'a') as f:
    f.write('Step 1: Read complex refs - 2 clearing references found\n')
    f.write('Step 2: Read involved panels - Other Details, Basic Details\n')
    f.write('Step 3: Both refs are cross-panel clearing: Company Type and Select PH level -> Corporate Marketing\n')
    f.write('Step 4: Placed 2 Expression (Client) clear_field rules on Basic Details trigger fields\n')
    f.write('  - _companytypebasicdetails_: clear _corporatemarketingotherdetails_ on change\n')
    f.write('  - _selectthephleveltobecreatedbasicdetails_: clear _corporatemarketingotherdetails_ on change\n')
    f.write('Step 5: Output written to rules JSON\n')

with open(out_path) as f:
    result = json.load(f)

total_rules = 0
for pname, fields in result.items():
    for field in fields:
        for r in field.get('rules', []):
            if r.get('_expressionRuleType') == 'clear_field':
                total_rules += 1
                print(f'  Rule on {field["variableName"]} in {pname}: {r["conditionalValues"][0][:80]}...')

print(f'\nTotal clearing rules placed: {total_rules}')
print(f'Output panels: {list(result.keys())}')
