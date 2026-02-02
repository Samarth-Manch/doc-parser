#!/usr/bin/env python3
"""
Comprehensive Rule Extraction Evaluation Script
Evaluates generated rule extraction output against BUD document and reference JSON.
"""

import json
import sys
import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from doc_parser import DocumentParser

def load_json(filepath):
    """Load JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def extract_rules_from_json(data):
    """Extract all formFillRules from the JSON structure."""
    rules = []
    field_rules = {}  # Maps field ID to list of rules
    field_names = {}  # Maps field ID to field name

    template = data.get('template', data)
    doc_types = template.get('documentTypes', [])

    for doc_type in doc_types:
        metadatas = doc_type.get('formFillMetadatas', [])
        for meta in metadatas:
            field_id = meta.get('id')
            field_name = meta.get('formTag', {}).get('name', 'Unknown')
            field_names[field_id] = field_name

            field_rules_list = meta.get('formFillRules', [])
            if field_rules_list:
                field_rules[field_id] = field_rules_list
                rules.extend(field_rules_list)

    return rules, field_rules, field_names

def count_rules_by_type(rules):
    """Count rules by actionType."""
    counts = defaultdict(int)
    for rule in rules:
        action_type = rule.get('actionType', 'UNKNOWN')
        counts[action_type] += 1
    return dict(counts)

def extract_panels_from_schema(data):
    """Extract panels (PANEL type fields) from schema."""
    panels = {}
    current_panel = "Default"

    template = data.get('template', data)
    doc_types = template.get('documentTypes', [])

    for doc_type in doc_types:
        metadatas = doc_type.get('formFillMetadatas', [])
        for meta in metadatas:
            form_tag = meta.get('formTag', {})
            field_type = form_tag.get('type', '')
            field_name = form_tag.get('name', 'Unknown')
            field_id = meta.get('id')

            if field_type == 'PANEL':
                current_panel = field_name
                if current_panel not in panels:
                    panels[current_panel] = []
            else:
                if current_panel not in panels:
                    panels[current_panel] = []
                panels[current_panel].append({
                    'id': field_id,
                    'name': field_name,
                    'type': field_type,
                    'rules': meta.get('formFillRules', [])
                })

    return panels

def check_ocr_verify_chains(rules, field_names):
    """Check OCR rules for proper VERIFY chain linking."""
    ocr_rules = [r for r in rules if r.get('actionType') == 'OCR']
    verify_rules = [r for r in rules if r.get('actionType') == 'VERIFY']

    # Build map of verify rules by their sourceIds
    verify_by_source = {}
    for vr in verify_rules:
        for src_id in vr.get('sourceIds', []):
            verify_by_source[src_id] = vr

    chain_results = []
    correctly_chained = 0

    for ocr in ocr_rules:
        ocr_id = ocr.get('id')
        source_type = ocr.get('sourceType', '')
        dest_ids = ocr.get('destinationIds', [])
        post_trigger = ocr.get('postTriggerRuleIds', [])

        # Skip AADHAR types - they don't need VERIFY chains
        if 'AADHAR' in source_type.upper():
            chain_results.append({
                'ocr_rule_id': ocr_id,
                'source_type': source_type,
                'status': 'SKIP',
                'reason': 'AADHAR types do not require VERIFY chains'
            })
            continue

        # Find if any destination field has a VERIFY rule
        verify_found = False
        chained = False

        for dest_id in dest_ids:
            if dest_id in verify_by_source:
                verify_found = True
                verify_rule = verify_by_source[dest_id]
                if verify_rule.get('id') in post_trigger:
                    chained = True
                    correctly_chained += 1
                    chain_results.append({
                        'ocr_rule_id': ocr_id,
                        'source_type': source_type,
                        'verify_rule_id': verify_rule.get('id'),
                        'status': 'PASS',
                        'chained': True
                    })
                    break

        if not chained:
            chain_results.append({
                'ocr_rule_id': ocr_id,
                'source_type': source_type,
                'status': 'FAIL',
                'reason': 'Missing postTriggerRuleIds to VERIFY' if verify_found else 'No VERIFY rule for destination',
                'chained': False
            })

    total_requiring_chain = len([r for r in chain_results if r.get('status') != 'SKIP'])

    return {
        'total_ocr_rules': len(ocr_rules),
        'requiring_chain': total_requiring_chain,
        'correctly_chained': correctly_chained,
        'chain_rate': correctly_chained / total_requiring_chain if total_requiring_chain > 0 else 1.0,
        'details': chain_results
    }

def check_verify_ordinals(rules):
    """Check VERIFY rules for correct ordinal mapping."""
    # Expected ordinal counts by sourceType
    ORDINAL_COUNTS = {
        'PAN_NUMBER': 10,
        'GSTIN': 21,
        'BANK_ACCOUNT_NUMBER': 4,
        'MSME_UDYAM_REG_NUMBER': 21,
        'CIN_ID': 14
    }

    verify_rules = [r for r in rules if r.get('actionType') == 'VERIFY']
    results = []
    correct_count = 0

    for vr in verify_rules:
        source_type = vr.get('sourceType', '')
        dest_ids = vr.get('destinationIds', [])
        expected = ORDINAL_COUNTS.get(source_type)

        if expected:
            actual = len(dest_ids)
            is_correct = actual == expected
            if is_correct:
                correct_count += 1

            results.append({
                'rule_id': vr.get('id'),
                'source_type': source_type,
                'expected_ordinals': expected,
                'actual_ordinals': actual,
                'status': 'PASS' if is_correct else 'FAIL'
            })
        else:
            results.append({
                'rule_id': vr.get('id'),
                'source_type': source_type,
                'status': 'UNKNOWN_TYPE',
                'actual_ordinals': len(dest_ids)
            })

    total_checkable = len([r for r in results if r.get('status') != 'UNKNOWN_TYPE'])

    return {
        'total_verify_rules': len(verify_rules),
        'checkable_rules': total_checkable,
        'correct_ordinals': correct_count,
        'ordinal_rate': correct_count / total_checkable if total_checkable > 0 else 1.0,
        'details': results
    }

def check_rule_consolidation(rules):
    """Check if MAKE_DISABLED rules are properly consolidated."""
    disabled_rules = [r for r in rules if r.get('actionType') == 'MAKE_DISABLED']

    # Count unique source+condition combinations
    consolidation_keys = set()
    for dr in disabled_rules:
        key = (
            tuple(sorted(dr.get('sourceIds', []))),
            dr.get('condition', ''),
            tuple(sorted(dr.get('conditionalValues', [])))
        )
        consolidation_keys.add(key)

    # If count of rules >> count of unique keys, consolidation is poor
    is_consolidated = len(disabled_rules) <= len(consolidation_keys) * 2

    return {
        'total_disabled_rules': len(disabled_rules),
        'unique_patterns': len(consolidation_keys),
        'is_consolidated': is_consolidated,
        'expected_max': len(consolidation_keys),
        'status': 'PASS' if is_consolidated else 'FAIL'
    }

def validate_json_structure(data):
    """Validate JSON structure matches expected format."""
    errors = []

    # Check root structure
    template = data.get('template', data)

    if 'documentTypes' not in template:
        errors.append("Missing 'documentTypes' in template")
        return {'valid': False, 'errors': errors}

    doc_types = template.get('documentTypes', [])
    if not doc_types:
        errors.append("Empty documentTypes array")
        return {'valid': False, 'errors': errors}

    # Check first document type
    doc_type = doc_types[0]
    if 'formFillMetadatas' not in doc_type:
        errors.append("Missing 'formFillMetadatas' in documentType")
        return {'valid': False, 'errors': errors}

    # Validate rule structure
    metadatas = doc_type.get('formFillMetadatas', [])
    rule_count = 0

    for meta in metadatas:
        for rule in meta.get('formFillRules', []):
            rule_count += 1
            # Check required fields
            required = ['id', 'actionType', 'sourceIds', 'executeOnFill']
            for field in required:
                if field not in rule:
                    errors.append(f"Rule {rule.get('id', 'unknown')} missing required field: {field}")

            # Check types
            if 'sourceIds' in rule and not isinstance(rule['sourceIds'], list):
                errors.append(f"Rule {rule.get('id')}: sourceIds must be array")

            if 'destinationIds' in rule and not isinstance(rule['destinationIds'], list):
                errors.append(f"Rule {rule.get('id')}: destinationIds must be array")

    return {
        'valid': len(errors) == 0,
        'errors': errors[:20],  # Limit error output
        'total_errors': len(errors),
        'rules_checked': rule_count
    }

def compare_rule_counts(gen_counts, ref_counts):
    """Compare rule counts between generated and reference."""
    discrepancies = []
    all_types = set(gen_counts.keys()) | set(ref_counts.keys())

    for action_type in sorted(all_types):
        gen = gen_counts.get(action_type, 0)
        ref = ref_counts.get(action_type, 0)

        if gen != ref:
            diff = gen - ref
            severity = "HIGH" if abs(diff) > 5 else "MEDIUM"

            # Special handling for MAKE_DISABLED
            if action_type == "MAKE_DISABLED" and gen > ref * 5:
                issue = "Rules not consolidated - should have fewer rules with multiple destinationIds"
                severity = "HIGH"
            elif gen > ref:
                issue = f"Over-generated by {diff}"
            else:
                issue = f"Under-generated by {abs(diff)}"

            discrepancies.append({
                'action_type': action_type,
                'generated': gen,
                'reference': ref,
                'difference': diff,
                'issue': issue,
                'severity': severity
            })

    return discrepancies

def evaluate_panel(panel_name, fields, ref_field_rules, ref_field_names):
    """Evaluate a single panel's rules."""
    issues = []
    fields_with_issues = 0

    for field in fields:
        field_id = field['id']
        field_name = field['name']
        gen_rules = field.get('rules', [])

        # Find corresponding reference field by name
        ref_id = None
        for rid, rname in ref_field_names.items():
            if rname.lower() == field_name.lower():
                ref_id = rid
                break

        if ref_id and ref_id in ref_field_rules:
            ref_rules = ref_field_rules[ref_id]

            # Compare rule types
            gen_types = set(r.get('actionType') for r in gen_rules)
            ref_types = set(r.get('actionType') for r in ref_rules)

            missing = ref_types - gen_types
            extra = gen_types - ref_types

            if missing or extra:
                fields_with_issues += 1
                if missing:
                    issues.append({
                        'field': field_name,
                        'field_id': field_id,
                        'issue': f"Missing rule types: {', '.join(missing)}",
                        'severity': 'HIGH' if any(t in ['VERIFY', 'OCR'] for t in missing) else 'MEDIUM'
                    })
                if extra:
                    issues.append({
                        'field': field_name,
                        'field_id': field_id,
                        'issue': f"Extra rule types: {', '.join(extra)}",
                        'severity': 'LOW'
                    })

    total_fields = len(fields)
    score = 1.0 - (fields_with_issues / total_fields) if total_fields > 0 else 1.0

    return {
        'panel_name': panel_name,
        'total_fields': total_fields,
        'fields_with_issues': fields_with_issues,
        'panel_score': round(score, 2),
        'issues': issues
    }

def generate_self_heal_instructions(discrepancies, ocr_chain_check, verify_ordinal_check, consolidation_check):
    """Generate prioritized fix instructions."""
    priority_fixes = []
    priority = 1

    # Priority 1: OCR → VERIFY chains
    if ocr_chain_check['chain_rate'] < 1.0:
        failed_chains = [d for d in ocr_chain_check['details'] if d.get('status') == 'FAIL']
        priority_fixes.append({
            'priority': priority,
            'fix_type': 'ocr_verify_chains',
            'description': 'Add postTriggerRuleIds to link OCR → VERIFY rules',
            'affected_rules': [d['ocr_rule_id'] for d in failed_chains],
            'severity': 'CRITICAL',
            'implementation': "ocr_rule['postTriggerRuleIds'] = [verify_rule_id]"
        })
        priority += 1

    # Priority 2: VERIFY ordinal mapping
    if verify_ordinal_check['ordinal_rate'] < 1.0:
        failed_ordinals = [d for d in verify_ordinal_check['details'] if d.get('status') == 'FAIL']
        priority_fixes.append({
            'priority': priority,
            'fix_type': 'verify_ordinal_mapping',
            'description': 'Fix destinationIds array length for VERIFY rules',
            'affected_rules': [d['rule_id'] for d in failed_ordinals],
            'severity': 'CRITICAL',
            'details': failed_ordinals
        })
        priority += 1

    # Priority 3-5: Missing rules by type
    missing_types = []
    for d in discrepancies:
        if d['difference'] < 0:  # Under-generated
            missing_types.append(d)

    # Sort by severity and difference magnitude
    for d in sorted(missing_types, key=lambda x: (-abs(x['difference']), x['action_type'])):
        if d['action_type'] in ['VERIFY', 'OCR']:
            severity = 'HIGH'
        elif d['action_type'] in ['EXT_DROP_DOWN', 'EXT_VALUE']:
            severity = 'HIGH'
        else:
            severity = 'MEDIUM'

        priority_fixes.append({
            'priority': priority,
            'fix_type': f"missing_{d['action_type'].lower()}_rules",
            'description': f"Add {abs(d['difference'])} missing {d['action_type']} rules",
            'generated': d['generated'],
            'expected': d['reference'],
            'severity': severity
        })
        priority += 1

    # Consolidation fix
    if not consolidation_check['is_consolidated']:
        priority_fixes.append({
            'priority': priority,
            'fix_type': 'consolidate_disabled_rules',
            'description': f"Merge {consolidation_check['total_disabled_rules']} MAKE_DISABLED into ~{consolidation_check['expected_max']} consolidated rules",
            'severity': 'HIGH',
            'implementation': "Group by sourceIds + condition + conditionalValues, merge destinationIds"
        })
        priority += 1

    return {'priority_fixes': priority_fixes}

def main():
    # Input paths
    generated_path = "adws/2026-02-01_01-13-42/populated_schema_v1.json"
    reference_path = "documents/json_output/vendor_creation_sample_bud.json"
    bud_path = "documents/Vendor Creation Sample BUD.docx"
    output_path = "adws/2026-02-01_01-13-42/eval_report_v1.json"

    pass_threshold = 0.9
    iteration = 1

    print("=" * 64)
    print("RULE EXTRACTION EVALUATION REPORT")
    print("=" * 64)
    print(f"Generated: {generated_path}")
    print(f"Reference: {reference_path}")
    print(f"BUD Source: {bud_path}")
    print(f"Iteration: {iteration}")
    print("-" * 64)

    # Load files
    print("\nLoading files...")
    generated_data = load_json(generated_path)
    reference_data = load_json(reference_path)

    # Parse BUD document
    print("Parsing BUD document...")
    try:
        parser = DocumentParser()
        parsed_bud = parser.parse(bud_path)
        bud_fields_count = len(parsed_bud.all_fields)
        print(f"  BUD fields extracted: {bud_fields_count}")
    except Exception as e:
        print(f"  Warning: Could not parse BUD: {e}")
        bud_fields_count = 0

    # Extract rules
    print("\nExtracting rules...")
    gen_rules, gen_field_rules, gen_field_names = extract_rules_from_json(generated_data)
    ref_rules, ref_field_rules, ref_field_names = extract_rules_from_json(reference_data)

    print(f"  Generated rules: {len(gen_rules)}")
    print(f"  Reference rules: {len(ref_rules)}")

    # Count by type
    gen_counts = count_rules_by_type(gen_rules)
    ref_counts = count_rules_by_type(ref_rules)

    # Layer 3: JSON Structure Validation
    print("\nValidating JSON structure...")
    structure_check = validate_json_structure(generated_data)
    print(f"  Structure valid: {structure_check['valid']}")
    if structure_check['total_errors'] > 0:
        print(f"  Errors found: {structure_check['total_errors']}")

    # Critical checks
    print("\nPerforming critical checks...")

    # OCR → VERIFY chains
    ocr_chain_check = check_ocr_verify_chains(gen_rules, gen_field_names)
    print(f"  OCR → VERIFY chains: {ocr_chain_check['correctly_chained']}/{ocr_chain_check['requiring_chain']} ({ocr_chain_check['chain_rate']*100:.0f}%)")

    # VERIFY ordinal mapping
    verify_ordinal_check = check_verify_ordinals(gen_rules)
    print(f"  VERIFY ordinals: {verify_ordinal_check['correct_ordinals']}/{verify_ordinal_check['checkable_rules']} ({verify_ordinal_check['ordinal_rate']*100:.0f}%)")

    # Rule consolidation
    consolidation_check = check_rule_consolidation(gen_rules)
    print(f"  MAKE_DISABLED consolidation: {consolidation_check['status']} ({consolidation_check['total_disabled_rules']} rules, {consolidation_check['unique_patterns']} patterns)")

    # Layer 2: Reference comparison
    print("\nComparing rule counts...")
    discrepancies = compare_rule_counts(gen_counts, ref_counts)

    # Panel evaluation
    print("\nEvaluating panels...")
    gen_panels = extract_panels_from_schema(generated_data)
    panel_evaluations = []

    for panel_name, fields in gen_panels.items():
        panel_eval = evaluate_panel(panel_name, fields, ref_field_rules, ref_field_names)
        panel_evaluations.append(panel_eval)
        status = "⚠️" if panel_eval['panel_score'] < 0.7 else "✓"
        print(f"  {panel_name}: {panel_eval['panel_score']*100:.0f}% ({panel_eval['fields_with_issues']} issues) {status}")

    # Calculate overall score
    # Score components:
    # - OCR chain rate (25%)
    # - VERIFY ordinal rate (25%)
    # - Rule count accuracy (25%)
    # - Panel coverage (25%)

    total_discrepancy_weight = sum(abs(d['difference']) for d in discrepancies)
    max_expected = sum(ref_counts.values())
    rule_count_score = 1.0 - (total_discrepancy_weight / max_expected) if max_expected > 0 else 1.0
    rule_count_score = max(0, rule_count_score)

    avg_panel_score = sum(p['panel_score'] for p in panel_evaluations) / len(panel_evaluations) if panel_evaluations else 1.0

    overall_score = (
        ocr_chain_check['chain_rate'] * 0.25 +
        verify_ordinal_check['ordinal_rate'] * 0.25 +
        rule_count_score * 0.25 +
        avg_panel_score * 0.25
    )

    evaluation_passed = overall_score >= pass_threshold

    print("\n" + "=" * 64)
    print(f"OVERALL SCORE: {overall_score*100:.0f}% (Threshold: {pass_threshold*100:.0f}%)")
    print(f"RESULT: {'PASSED' if evaluation_passed else 'FAILED'}")
    print("=" * 64)

    # Rule type comparison table
    print("\nRULE TYPE COMPARISON:")
    print("-" * 64)
    print(f"{'Type':<25} {'Generated':>10} {'Reference':>10} {'Status':<15}")
    print("-" * 64)

    all_types = sorted(set(gen_counts.keys()) | set(ref_counts.keys()))
    for action_type in all_types:
        gen = gen_counts.get(action_type, 0)
        ref = ref_counts.get(action_type, 0)
        if gen == ref:
            status = "✓"
        elif gen > ref:
            status = f"+{gen - ref}"
        else:
            status = f"-{ref - gen}"
        print(f"{action_type:<25} {gen:>10} {ref:>10} {status:<15}")

    # Generate self-heal instructions
    self_heal = generate_self_heal_instructions(
        discrepancies,
        ocr_chain_check,
        verify_ordinal_check,
        consolidation_check
    )

    if self_heal['priority_fixes']:
        print("\nTOP PRIORITY FIXES:")
        print("-" * 64)
        for fix in self_heal['priority_fixes'][:5]:
            print(f"{fix['priority']}. [{fix['severity']}] {fix['description']}")

    # Build evaluation report
    report = {
        'evaluation_summary': {
            'generated_output': generated_path,
            'reference_output': reference_path,
            'bud_document': bud_path,
            'evaluation_timestamp': datetime.now().isoformat(),
            'iteration': iteration,
            'overall_score': round(overall_score, 4),
            'pass_threshold': pass_threshold,
            'evaluation_passed': evaluation_passed,
            'component_scores': {
                'ocr_chain_rate': ocr_chain_check['chain_rate'],
                'verify_ordinal_rate': verify_ordinal_check['ordinal_rate'],
                'rule_count_accuracy': round(rule_count_score, 4),
                'panel_coverage': round(avg_panel_score, 4)
            }
        },
        'panel_evaluation': panel_evaluations,
        'bud_logic_verification': {
            'total_bud_fields': bud_fields_count,
            'note': 'BUD verification requires parsing field logic text'
        },
        'rule_type_comparison': {
            'reference': ref_counts,
            'generated': gen_counts,
            'discrepancies': discrepancies
        },
        'critical_checks': {
            'json_structure_valid': structure_check['valid'],
            'json_structure_errors': structure_check['errors'],
            'verify_ordinal_mapping': verify_ordinal_check,
            'ocr_verify_chains': ocr_chain_check,
            'make_disabled_consolidation': consolidation_check
        },
        'missing_rules': [d for d in discrepancies if d['difference'] < 0],
        'over_generated_rules': [d for d in discrepancies if d['difference'] > 0],
        'self_heal_instructions': self_heal
    }

    # Save report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 64)
    print(f"Detailed report saved to: {output_path}")
    print("=" * 64)

    return report

if __name__ == '__main__':
    main()
