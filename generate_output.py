import json

# Read the input file
with open('output/validate_edv/temp/Basic_Details_fields_input.json', 'r') as f:
    fields = json.load(f)

# Find the Country field and add Validate EDV rule
for field in fields:
    if field['variableName'] == '__country__':
        # Add the Validate EDV rule after the existing rules
        validate_edv_rule = {
            'id': 296,
            'rule_name': 'Validate EDV (Server)',
            'source_fields': ['__country__'],
            'destination_fields': ['-1', '__country_code__', '-1', '-1', '__country_name__', '-1'],
            'params': 'TABLE_1_1',
            '_reasoning': 'Placed by Validate EDV agent. TABLE_1_1 columns map positionally: a1 (Language Key) -> skip, a2 (Country/Region Key) -> __country_code__, a3 (Country/Region Name short) -> skip, a4 (Nationality) -> skip, a5 (Country/Region Name) -> __country_name__, a6 (Nationality Long) -> skip. When user selects a country from the dropdown, the system validates against TABLE_1_1 and auto-populates Country Code and Country Name fields.'
        }
        field['rules'].append(validate_edv_rule)
        break

# Write the output file
with open('output/validate_edv/temp/Basic_Details_validate_edv_output.json', 'w') as f:
    json.dump(fields, f, indent=2)

print('Output file created successfully')
