"""Comprehensive analysis of real rules from JSON schema files"""
import json
import os
from collections import defaultdict
import re

json_dir = "documents/json_output"

def extract_all_rules(data, path=''):
    """Recursively extract all rules from the JSON structure"""
    rules = []
    form_fields = []

    if isinstance(data, dict):
        # Check for formFillRules
        if 'formFillRules' in data and data['formFillRules']:
            for rule in data['formFillRules']:
                rule['_source_path'] = path
                rules.append(rule)

        # Check for formFillMetadatas (form fields)
        if 'formFillMetadatas' in data:
            for ffm in data['formFillMetadatas']:
                field_info = {
                    'id': ffm.get('id'),
                    'tagName': ffm.get('tagName'),
                    'fieldName': ffm.get('fieldName'),
                    'fieldType': ffm.get('fieldType'),
                    'label': ffm.get('label'),
                    'mandatory': ffm.get('mandatory'),
                    'rules_count': len(ffm.get('formFillRules', []))
                }
                form_fields.append(field_info)

        # Recurse
        for key, value in data.items():
            sub_rules, sub_fields = extract_all_rules(value, f'{path}.{key}')
            rules.extend(sub_rules)
            form_fields.extend(sub_fields)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            sub_rules, sub_fields = extract_all_rules(item, f'{path}[{i}]')
            rules.extend(sub_rules)
            form_fields.extend(sub_fields)

    return rules, form_fields

# Analyze all files
all_rules = []
all_fields = []
file_summaries = []

for filename in sorted(os.listdir(json_dir)):
    if filename.endswith('.json'):
        filepath = os.path.join(json_dir, filename)
        with open(filepath) as f:
            data = json.load(f)

        rules, fields = extract_all_rules(data)
        all_rules.extend(rules)
        all_fields.extend(fields)

        file_summaries.append({
            'filename': filename,
            'rules_count': len(rules),
            'fields_count': len(fields)
        })

print("="*100)
print("COMPREHENSIVE ANALYSIS OF REAL MANCH PLATFORM RULES")
print("="*100)

# File summaries
print("\n📁 FILE SUMMARIES")
print("-"*100)
for fs in file_summaries:
    print(f"  {fs['filename']}: {fs['rules_count']} rules, {fs['fields_count']} fields")

print(f"\n  TOTAL: {len(all_rules)} rules, {len(all_fields)} fields")

# Action type distribution
print("\n\n📊 RULE ACTION TYPE DISTRIBUTION")
print("-"*100)
action_types = defaultdict(list)
for rule in all_rules:
    action = rule.get('actionType', 'UNKNOWN')
    action_types[action].append(rule)

for action, rules in sorted(action_types.items(), key=lambda x: -len(x[1])):
    print(f"  {action}: {len(rules)} rules")

# Processing type distribution
print("\n\n⚙️ PROCESSING TYPE DISTRIBUTION")
print("-"*100)
processing_types = defaultdict(int)
for rule in all_rules:
    pt = rule.get('processingType', 'UNKNOWN')
    processing_types[pt] += 1

for pt, count in sorted(processing_types.items(), key=lambda x: -x[1]):
    print(f"  {pt}: {count} rules")

# Source type distribution
print("\n\n📤 SOURCE TYPE DISTRIBUTION")
print("-"*100)
source_types = defaultdict(int)
for rule in all_rules:
    st = rule.get('sourceType', 'N/A')
    source_types[st] += 1

for st, count in sorted(source_types.items(), key=lambda x: -x[1]):
    print(f"  {st}: {count} rules")

# EXECUTE rules analysis (Expression-based)
print("\n\n🔧 EXECUTE (EXPRESSION) RULES ANALYSIS")
print("-"*100)
execute_rules = action_types.get('EXECUTE', [])
print(f"Total EXECUTE rules: {len(execute_rules)}")

# Extract expression patterns
expression_functions = defaultdict(int)
expression_samples = []

for rule in execute_rules:
    cond_vals = rule.get('conditionalValues', [])
    for val in cond_vals:
        if val:
            # Find function calls
            funcs = re.findall(r'(\w+)\s*\(', str(val))
            for func in funcs:
                expression_functions[func] += 1

            if len(expression_samples) < 20:
                expression_samples.append({
                    'id': rule.get('id'),
                    'expression': val[:300],
                    'sourceIds': rule.get('sourceIds', []),
                    'destinationIds': rule.get('destinationIds', [])
                })

print("\nFunction usage in EXECUTE expressions:")
for func, count in sorted(expression_functions.items(), key=lambda x: -x[1]):
    print(f"  {func}(): {count} occurrences")

print("\nSample EXECUTE expressions:")
for i, sample in enumerate(expression_samples[:10], 1):
    print(f"\n  [{i}] ID: {sample['id']}")
    print(f"      Expression: {sample['expression'][:150]}...")
    print(f"      Sources: {sample['sourceIds'][:3]}")
    print(f"      Destinations: {sample['destinationIds'][:3]}")

# OCR rules analysis
print("\n\n🔍 OCR RULES ANALYSIS")
print("-"*100)
ocr_rules = [r for r in all_rules if 'OCR' in r.get('actionType', '')]
print(f"Total OCR rules: {len(ocr_rules)}")

ocr_types = defaultdict(int)
for rule in ocr_rules:
    ocr_types[rule.get('actionType')] += 1

for ot, count in sorted(ocr_types.items(), key=lambda x: -x[1]):
    print(f"  {ot}: {count} rules")

# Sample OCR rule
if ocr_rules:
    sample_ocr = ocr_rules[0]
    print(f"\nSample OCR rule:")
    print(f"  ActionType: {sample_ocr.get('actionType')}")
    print(f"  SourceType: {sample_ocr.get('sourceType')}")
    print(f"  SourceIds: {sample_ocr.get('sourceIds')}")
    print(f"  DestinationIds: {sample_ocr.get('destinationIds')[:5]}...")

# Validation rules
print("\n\n✅ VALIDATION RULES ANALYSIS")
print("-"*100)
validation_rules = [r for r in all_rules if any(x in r.get('actionType', '').upper() for x in ['VALIDATION', 'VERIFY', 'COMPARE'])]
print(f"Total validation-related rules: {len(validation_rules)}")

validation_types = defaultdict(int)
for rule in validation_rules:
    validation_types[rule.get('actionType')] += 1

for vt, count in sorted(validation_types.items(), key=lambda x: -x[1]):
    print(f"  {vt}: {count} rules")

# Visibility rules
print("\n\n👁️ VISIBILITY RULES ANALYSIS")
print("-"*100)
visibility_rules = [r for r in all_rules if any(x in r.get('actionType', '').upper() for x in ['VISIBLE', 'INVISIBLE'])]
print(f"Total visibility rules: {len(visibility_rules)}")

visibility_types = defaultdict(int)
for rule in visibility_rules:
    visibility_types[rule.get('actionType')] += 1

for vt, count in sorted(visibility_types.items(), key=lambda x: -x[1]):
    print(f"  {vt}: {count} rules")

# Sample visibility rule with conditions
vis_with_conditions = [r for r in visibility_rules if r.get('conditionalValues')]
if vis_with_conditions:
    print(f"\nSample visibility rule with conditions:")
    sample = vis_with_conditions[0]
    print(f"  ActionType: {sample.get('actionType')}")
    print(f"  Condition: {sample.get('condition')}")
    print(f"  ConditionalValues: {sample.get('conditionalValues')}")
    print(f"  SourceIds: {sample.get('sourceIds')}")
    print(f"  DestinationIds: {sample.get('destinationIds')[:5]}...")

# Copy rules
print("\n\n📋 COPY RULES ANALYSIS")
print("-"*100)
copy_rules = [r for r in all_rules if 'COPY' in r.get('actionType', '').upper()]
print(f"Total copy rules: {len(copy_rules)}")

copy_types = defaultdict(int)
for rule in copy_rules:
    copy_types[rule.get('actionType')] += 1

for ct, count in sorted(copy_types.items(), key=lambda x: -x[1]):
    print(f"  {ct}: {count} rules")

# Mandatory rules
print("\n\n❗ MANDATORY RULES ANALYSIS")
print("-"*100)
mandatory_rules = [r for r in all_rules if 'MANDATORY' in r.get('actionType', '').upper()]
print(f"Total mandatory rules: {len(mandatory_rules)}")

mandatory_types = defaultdict(int)
for rule in mandatory_rules:
    mandatory_types[rule.get('actionType')] += 1

for mt, count in sorted(mandatory_types.items(), key=lambda x: -x[1]):
    print(f"  {mt}: {count} rules")

# Full rule structure example
print("\n\n📄 COMPLETE RULE STRUCTURE EXAMPLES")
print("-"*100)

# Show one complete example of each major type
examples_to_show = ['EXECUTE', 'MAKE_INVISIBLE', 'OCR', 'COPY_TO', 'MAKE_MANDATORY']
for action_type in examples_to_show:
    rules_of_type = action_types.get(action_type, [])
    if rules_of_type:
        print(f"\n--- {action_type} Rule Example ---")
        rule = rules_of_type[0]
        # Remove internal path key
        rule_clean = {k: v for k, v in rule.items() if not k.startswith('_')}
        print(json.dumps(rule_clean, indent=2)[:800])
        if len(json.dumps(rule_clean)) > 800:
            print("  ...")
