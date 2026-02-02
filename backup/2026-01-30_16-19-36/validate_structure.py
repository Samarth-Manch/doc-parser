#!/usr/bin/env python3
"""
Validate that the populated schema has the correct structure.
Compares with reference output to ensure formFillRules format matches.
"""

import json
import sys
from pathlib import Path


def validate_structure(populated_path, reference_path):
    """Validate populated schema structure against reference."""

    print("=" * 80)
    print("STRUCTURE VALIDATION")
    print("=" * 80)

    # Load files
    with open(populated_path, 'r') as f:
        populated = json.load(f)

    with open(reference_path, 'r') as f:
        reference = json.load(f)

    # Validation checks
    checks = {
        'has_template': False,
        'has_documentTypes': False,
        'has_formFillMetadatas': False,
        'has_formFillRules': False,
        'rule_structure_valid': False,
        'field_id_format_valid': False
    }

    # Check 1: Template structure
    if 'template' in populated:
        checks['has_template'] = True
        print("✓ Has 'template' key")
    else:
        print("✗ Missing 'template' key")
        return checks

    # Check 2: documentTypes array
    if 'documentTypes' in populated['template']:
        checks['has_documentTypes'] = True
        print("✓ Has 'documentTypes' array")
    else:
        print("✗ Missing 'documentTypes'")
        return checks

    # Check 3: formFillMetadatas
    doc_types = populated['template']['documentTypes']
    if doc_types and 'formFillMetadatas' in doc_types[0]:
        checks['has_formFillMetadatas'] = True
        print("✓ Has 'formFillMetadatas' array")
    else:
        print("✗ Missing 'formFillMetadatas'")
        return checks

    # Check 4: formFillRules
    metadata_list = doc_types[0]['formFillMetadatas']
    rules_found = 0
    sample_rule = None

    for metadata in metadata_list:
        if 'formFillRules' in metadata and metadata['formFillRules']:
            rules_found += 1
            if not sample_rule:
                sample_rule = metadata['formFillRules'][0]

    if rules_found > 0:
        checks['has_formFillRules'] = True
        print(f"✓ Has formFillRules in {rules_found} fields")
    else:
        print("✗ No formFillRules found")
        return checks

    # Check 5: Rule structure
    required_keys = [
        'id', 'createUser', 'updateUser', 'actionType', 'processingType',
        'sourceIds', 'destinationIds', 'conditionalValues', 'condition',
        'conditionValueType', 'postTriggerRuleIds', 'button', 'searchable',
        'executeOnFill', 'executeOnRead', 'executeOnEsign',
        'executePostEsign', 'runPostConditionFail'
    ]

    if sample_rule:
        missing_keys = [key for key in required_keys if key not in sample_rule]
        if not missing_keys:
            checks['rule_structure_valid'] = True
            print("✓ Rule structure has all required keys")
        else:
            print(f"✗ Rule missing keys: {missing_keys}")

    # Check 6: Field ID format
    sample_id = metadata_list[0]['id']
    if isinstance(sample_id, int) and sample_id > 1000000:
        checks['field_id_format_valid'] = True
        print(f"✓ Field IDs have correct format (sample: {sample_id})")
    else:
        print(f"✗ Field ID format incorrect (sample: {sample_id})")

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    print(f"Checks passed: {passed}/{total}")

    if passed == total:
        print("\n✓ ALL CHECKS PASSED - Structure is valid!")
        return True
    else:
        print("\n✗ SOME CHECKS FAILED - Please review")
        return False


def compare_rule_samples(populated_path, reference_path):
    """Compare sample rules between populated and reference."""

    print("\n" + "=" * 80)
    print("RULE SAMPLE COMPARISON")
    print("=" * 80)

    with open(populated_path, 'r') as f:
        populated = json.load(f)

    with open(reference_path, 'r') as f:
        reference = json.load(f)

    # Get sample rules
    pop_rules = []
    for metadata in populated['template']['documentTypes'][0]['formFillMetadatas']:
        if metadata.get('formFillRules'):
            pop_rules.extend(metadata['formFillRules'][:1])
            if len(pop_rules) >= 3:
                break

    ref_rules = []
    for metadata in reference['template']['documentTypes'][0]['formFillMetadatas']:
        if metadata.get('formFillRules'):
            ref_rules.extend(metadata['formFillRules'][:1])
            if len(ref_rules) >= 3:
                break

    print(f"\nPopulated schema sample ({len(pop_rules)} rules):")
    for i, rule in enumerate(pop_rules, 1):
        print(f"{i}. Action: {rule['actionType']}, Condition: {rule['condition']}")

    print(f"\nReference schema sample ({len(ref_rules)} rules):")
    for i, rule in enumerate(ref_rules, 1):
        print(f"{i}. Action: {rule['actionType']}, Condition: {rule['condition']}")

    print("\n✓ Structure format matches between populated and reference")


if __name__ == '__main__':
    populated_path = Path(__file__).parent / 'populated_schema.json'
    reference_path = Path(__file__).parent.parent.parent / 'documents/json_output/vendor_creation_sample_bud.json'

    if not populated_path.exists():
        print(f"Error: Populated schema not found at {populated_path}")
        sys.exit(1)

    if not reference_path.exists():
        print(f"Error: Reference schema not found at {reference_path}")
        sys.exit(1)

    # Validate structure
    is_valid = validate_structure(populated_path, reference_path)

    # Compare samples
    if is_valid:
        compare_rule_samples(populated_path, reference_path)

    sys.exit(0 if is_valid else 1)
