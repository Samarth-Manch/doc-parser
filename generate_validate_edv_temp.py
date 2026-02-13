import json

# Read the input
with open('output/validate_edv/temp/Basic_Details_fields_input.json', 'r') as f:
    fields = json.load(f)

# Find the Country field and add Validate EDV rule
for field in fields:
    if field['field_name'] == 'Country':
        # Add the Validate EDV rule as the second rule (id=2)
        validate_edv_rule = {
            'id': 2,
            'rule_name': 'Validate EDV (Server)',
            'source_fields': ['__country__'],
            'destination_fields': ['-1', '__country_code__', '-1', '-1', '__country_name__'],
            'params': '1.1',
            '_reasoning': 'Placed by Validate EDV agent. When a country is selected, table 1.1 is queried to populate Country Code (a2) and Country Name (a5). Positional mapping: a1=skip (selected country key), a2=country_code (Country/Region Name), a3=skip (Nationality), a4=skip (Country/Region Name duplicate), a5=country_name (Nationality Long).'
        }
        field['rules'].append(validate_edv_rule)
        break

# Write the output
with open('output/validate_edv/temp/Basic_Details_validate_edv_output.json', 'w') as f:
    json.dump(fields, f, indent=2)

print('Output written successfully')
