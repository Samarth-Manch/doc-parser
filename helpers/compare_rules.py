#!/usr/bin/env python3
"""
Compare generated rule names against reference JSON
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

def load_reference_rules(ref_path):
    """Load reference rules from vendor_creation.json"""
    with open(ref_path, 'r') as f:
        data = json.load(f)

    fields_with_rules = {}

    for field in data['template']['documentTypes'][0]['formFillMetadatas']:
        field_name = field['formTag']['name']
        rules = field.get('formFillRules', [])

        # Extract rule names from reference
        rule_names = []
        for rule in rules:
            # Get the rule name from Rule-Schemas.json by looking up action/source
            action = rule.get('actionType', '')
            source = rule.get('sourceType', '')

            # Store both actionType and sourceType for matching
            rule_names.append({
                'action': action,
                'source': source,
                'full': f"{action}_{source}" if source else action
            })

        if rule_names:
            fields_with_rules[field_name] = rule_names

    return fields_with_rules

def load_generated_rules(output_dir):
    """Load generated rules from panel JSON files"""
    generated = {}
    errors = []

    output_path = Path(output_dir)
    for panel_file in output_path.glob("*_rules.json"):
        try:
            with open(panel_file, 'r') as f:
                fields = json.load(f)

            for field in fields:
                field_name = field['field_name']
                rules = field.get('rules', [])
                generated[field_name] = rules
        except json.JSONDecodeError as e:
            errors.append(f"{panel_file.name}: {e}")

    if errors:
        print(f"\n⚠ Warning: {len(errors)} files had JSON errors:")
        for err in errors:
            print(f"  - {err}")

    return generated

def load_rule_schemas(schema_path):
    """Load Rule-Schemas.json to map names to action/source"""
    with open(schema_path, 'r') as f:
        data = json.load(f)

    name_to_rule = {}

    for rule in data.get('content', []):
        name = rule.get('name', '')
        action = rule.get('action', '')
        source = rule.get('source', '')

        if name:
            name_to_rule[name] = {
                'action': action,
                'source': source,
                'full': f"{action}_{source}" if source else action
            }

    return name_to_rule

def compare_rules(reference, generated, name_to_rule):
    """Compare reference and generated rules"""

    results = {
        'exact_match': [],
        'partial_match': [],
        'missing_rules': [],
        'extra_rules': [],
        'field_not_found': []
    }

    for field_name, ref_rules in reference.items():
        if field_name not in generated:
            results['field_not_found'].append({
                'field': field_name,
                'expected_rules': [r['full'] for r in ref_rules]
            })
            continue

        gen_rule_names = generated[field_name]

        # Convert generated rule names to action/source format
        gen_rules = []
        for rule_name in gen_rule_names:
            if rule_name in name_to_rule:
                gen_rules.append(name_to_rule[rule_name])
            else:
                gen_rules.append({'action': rule_name, 'source': '', 'full': rule_name})

        # Check for matches
        ref_fulls = {r['full'] for r in ref_rules}
        gen_fulls = {g['full'] for g in gen_rules}

        if ref_fulls == gen_fulls:
            results['exact_match'].append(field_name)
        else:
            missing = ref_fulls - gen_fulls
            extra = gen_fulls - ref_fulls

            if missing or extra:
                results['partial_match'].append({
                    'field': field_name,
                    'expected': sorted(list(ref_fulls)),
                    'generated': sorted(list(gen_fulls)),
                    'missing': sorted(list(missing)),
                    'extra': sorted(list(extra))
                })

    return results

def print_report(results):
    """Print comparison report"""

    total = len(results['exact_match']) + len(results['partial_match']) + len(results['field_not_found'])

    print("="*80)
    print("RULE COMPARISON REPORT")
    print("="*80)
    print(f"\nTotal Fields with Rules: {total}")
    print(f"✓ Exact Matches: {len(results['exact_match'])}")
    print(f"~ Partial Matches: {len(results['partial_match'])}")
    print(f"✗ Fields Not Found: {len(results['field_not_found'])}")

    if results['exact_match']:
        accuracy = len(results['exact_match']) / total * 100
        print(f"\nAccuracy: {accuracy:.1f}%")

    if results['partial_match']:
        print("\n" + "="*80)
        print("PARTIAL MATCHES (Rules Differ)")
        print("="*80)

        for item in results['partial_match'][:20]:  # Show first 20
            print(f"\nField: {item['field']}")
            print(f"  Expected: {item['expected']}")
            print(f"  Generated: {item['generated']}")
            if item['missing']:
                print(f"  Missing: {item['missing']}")
            if item['extra']:
                print(f"  Extra: {item['extra']}")

        if len(results['partial_match']) > 20:
            print(f"\n... and {len(results['partial_match']) - 20} more")

    if results['field_not_found']:
        print("\n" + "="*80)
        print("FIELDS NOT FOUND IN GENERATED OUTPUT")
        print("="*80)

        for item in results['field_not_found'][:10]:
            print(f"\nField: {item['field']}")
            print(f"  Expected Rules: {item['expected_rules']}")

        if len(results['field_not_found']) > 10:
            print(f"\n... and {len(results['field_not_found']) - 10} more")

def main():
    ref_path = "documents/json_output/vendor_creation.json"
    gen_dir = "output/rule_placement_v2/panels"
    schema_path = "rules/Rule-Schemas.json"

    print("Loading reference rules...")
    reference = load_reference_rules(ref_path)
    print(f"Found {len(reference)} fields with rules in reference")

    print("\nLoading generated rules...")
    generated = load_generated_rules(gen_dir)
    print(f"Found {len(generated)} fields in generated output")

    print("\nLoading Rule-Schemas.json...")
    name_to_rule = load_rule_schemas(schema_path)
    print(f"Found {len(name_to_rule)} rule definitions")

    print("\nComparing...")
    results = compare_rules(reference, generated, name_to_rule)

    print_report(results)

    # Save detailed results
    output_file = "rule_comparison_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()
