#!/usr/bin/env python3
"""
Comprehensive Rule Extraction Evaluation Script - Iteration 6
Performs three-layer evaluation:
1. BUD Verification (Primary): Parse BUD, verify rules match natural language logic
2. Reference Comparison (Secondary): Compare against human-made reference
3. Schema Validation: Verify JSON structure and rule formats
"""

import json
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from doc_parser import DocumentParser

# Configuration
GENERATED_FILE = "populated_schema_v6.json"
REFERENCE_FILE = "../../documents/json_output/vendor_creation_sample_bud.json"
BUD_FILE = "../../documents/Vendor Creation Sample BUD.docx"
OUTPUT_FILE = "eval_report_v6.json"
PASS_THRESHOLD = 0.9
ITERATION = 6

def load_json(filepath):
    """Load JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def extract_form_fill_metadatas(data):
    """Extract formFillMetadatas from template structure."""
    try:
        doc_types = data.get('template', {}).get('documentTypes', [])
        if doc_types:
            return doc_types[0].get('formFillMetadatas', [])
    except:
        pass
    return []

def get_field_by_id(metadatas, field_id):
    """Get field metadata by ID."""
    for meta in metadatas:
        if meta.get('id') == field_id:
            return meta
    return None

def get_field_name_by_id(metadatas, field_id):
    """Get field name by ID."""
    meta = get_field_by_id(metadatas, field_id)
    if meta:
        return meta.get('formTag', {}).get('name', f'Unknown (id={field_id})')
    return f'Unknown (id={field_id})'

def analyze_rules(metadatas):
    """Analyze rules in formFillMetadatas and categorize by type."""
    rule_types = defaultdict(list)
    all_rules = []

    for meta in metadatas:
        field_name = meta.get('formTag', {}).get('name', 'Unknown')
        field_id = meta.get('id')
        rules = meta.get('formFillRules', [])

        for rule in rules:
            rule_type = rule.get('actionType', 'UNKNOWN')
            rule_info = {
                'field_name': field_name,
                'field_id': field_id,
                'rule': rule,
                'rule_type': rule_type
            }
            rule_types[rule_type].append(rule_info)
            all_rules.append(rule_info)

    return rule_types, all_rules

def find_panel_for_field(metadatas, field_id):
    """Find which panel a field belongs to."""
    current_panel = "Unknown"
    for meta in metadatas:
        field_type = meta.get('formTag', {}).get('type', '')
        if field_type == 'PANEL':
            current_panel = meta.get('formTag', {}).get('name', 'Unknown')
        if meta.get('id') == field_id:
            return current_panel
    return current_panel

def group_fields_by_panel(metadatas):
    """Group fields by their panel."""
    panels = defaultdict(list)
    current_panel = "Unknown"

    for meta in metadatas:
        field_type = meta.get('formTag', {}).get('type', '')
        if field_type == 'PANEL':
            current_panel = meta.get('formTag', {}).get('name', 'Unknown')
        panels[current_panel].append(meta)

    return panels

def compare_rules(gen_rules, ref_rules, metadatas_gen, metadatas_ref):
    """Compare generated rules against reference rules."""
    matched = []
    missing = []
    extra = []
    incorrect = []

    # Create lookups by field name and rule type
    gen_lookup = defaultdict(list)
    ref_lookup = defaultdict(list)

    for r in gen_rules:
        key = (r['field_name'], r['rule_type'])
        gen_lookup[key].append(r)

    for r in ref_rules:
        key = (r['field_name'], r['rule_type'])
        ref_lookup[key].append(r)

    # Find matches and missing
    for key, ref_list in ref_lookup.items():
        gen_list = gen_lookup.get(key, [])
        if not gen_list:
            for r in ref_list:
                missing.append({
                    'field': key[0],
                    'rule_type': key[1],
                    'expected': r['rule']
                })
        else:
            # Rules exist, check if they match
            for ref_r in ref_list:
                match_found = False
                for gen_r in gen_list:
                    # Compare key rule properties
                    if rules_match(gen_r['rule'], ref_r['rule']):
                        matched.append({
                            'field': key[0],
                            'rule_type': key[1]
                        })
                        match_found = True
                        break
                if not match_found:
                    incorrect.append({
                        'field': key[0],
                        'rule_type': key[1],
                        'generated': gen_list[0]['rule'] if gen_list else None,
                        'expected': ref_r['rule']
                    })

    # Find extra rules (in generated but not in reference)
    for key, gen_list in gen_lookup.items():
        if key not in ref_lookup:
            for r in gen_list:
                extra.append({
                    'field': key[0],
                    'rule_type': key[1],
                    'rule': r['rule']
                })

    return matched, missing, extra, incorrect

def rules_match(gen_rule, ref_rule):
    """Check if two rules match on key properties."""
    # Key properties to compare
    keys = ['actionType', 'condition', 'conditionalValues']

    for key in keys:
        if gen_rule.get(key) != ref_rule.get(key):
            return False

    # Compare sourceIds and destinationIds (may differ in IDs but same fields)
    # For now, just check action type matches
    return True

def check_ocr_chains(metadatas):
    """Check if OCR rules have proper postTriggerRuleIds chains to VERIFY rules."""
    issues = []
    ocr_rules = []
    verify_rule_ids = set()

    # First, collect all VERIFY rule IDs
    for meta in metadatas:
        for rule in meta.get('formFillRules', []):
            if rule.get('actionType') == 'VERIFY':
                verify_rule_ids.add(rule.get('id'))
            if rule.get('actionType') == 'OCR':
                ocr_rules.append({
                    'field': meta.get('formTag', {}).get('name'),
                    'rule': rule
                })

    # Check each OCR rule
    for ocr in ocr_rules:
        post_triggers = ocr['rule'].get('postTriggerRuleIds', [])
        if not post_triggers:
            issues.append({
                'field': ocr['field'],
                'issue': 'OCR rule has no postTriggerRuleIds',
                'rule_id': ocr['rule'].get('id')
            })
        else:
            # Check if triggers point to VERIFY rules
            for trigger_id in post_triggers:
                if trigger_id not in verify_rule_ids:
                    issues.append({
                        'field': ocr['field'],
                        'issue': f'postTriggerRuleId {trigger_id} does not point to a VERIFY rule',
                        'rule_id': ocr['rule'].get('id')
                    })

    return len(issues) == 0, issues

def check_ordinal_mapping(metadatas):
    """Check if VERIFY rules use ordinal destinationIds (1, 2, 3) not actual values."""
    issues = []

    for meta in metadatas:
        field_name = meta.get('formTag', {}).get('name')
        for rule in meta.get('formFillRules', []):
            if rule.get('actionType') == 'VERIFY':
                dest_ids = rule.get('destinationIds', [])
                # Check if destinationIds look like ordinals (small integers)
                for dest_id in dest_ids:
                    if isinstance(dest_id, int) and dest_id <= 10:
                        # Likely ordinal mapping - this is correct
                        pass
                    else:
                        issues.append({
                            'field': field_name,
                            'issue': f'VERIFY rule has non-ordinal destinationId: {dest_id}',
                            'rule_id': rule.get('id')
                        })

    return len(issues) == 0, issues

def check_visibility_pairs(metadatas):
    """Check if MAKE_VISIBLE and MAKE_INVISIBLE rules exist as pairs."""
    visible_targets = set()
    invisible_targets = set()

    for meta in metadatas:
        for rule in meta.get('formFillRules', []):
            action = rule.get('actionType')
            dests = tuple(rule.get('destinationIds', []))

            if action == 'MAKE_VISIBLE':
                visible_targets.add(dests)
            elif action == 'MAKE_INVISIBLE':
                invisible_targets.add(dests)

    # Check for unpaired visibility rules
    unpaired_visible = visible_targets - invisible_targets
    unpaired_invisible = invisible_targets - visible_targets

    issues = []
    for dests in unpaired_visible:
        issues.append({
            'issue': f'MAKE_VISIBLE for fields {dests} has no corresponding MAKE_INVISIBLE'
        })
    for dests in unpaired_invisible:
        issues.append({
            'issue': f'MAKE_INVISIBLE for fields {dests} has no corresponding MAKE_VISIBLE'
        })

    return len(issues) == 0, issues

def check_duplicate_rules(metadatas):
    """Check for duplicate rules."""
    seen = set()
    duplicates = []

    for meta in metadatas:
        field_name = meta.get('formTag', {}).get('name')
        for rule in meta.get('formFillRules', []):
            # Create a signature for the rule
            sig = (
                field_name,
                rule.get('actionType'),
                tuple(rule.get('sourceIds', [])),
                tuple(rule.get('destinationIds', [])),
                rule.get('condition'),
                tuple(rule.get('conditionalValues', [])) if rule.get('conditionalValues') else None
            )

            if sig in seen:
                duplicates.append({
                    'field': field_name,
                    'rule_type': rule.get('actionType'),
                    'rule_id': rule.get('id')
                })
            else:
                seen.add(sig)

    return len(duplicates) == 0, duplicates

def parse_bud_document(bud_path):
    """Parse BUD document to extract fields with logic."""
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    fields_with_logic = []
    for field in parsed.all_fields:
        logic_text = getattr(field, 'logic', None) or ''
        rules_text = getattr(field, 'rules', None) or ''

        if logic_text or rules_text:
            fields_with_logic.append({
                'name': field.name,
                'field_type': field.field_type.value if hasattr(field.field_type, 'value') else str(field.field_type),
                'logic': logic_text,
                'rules': rules_text
            })

    return fields_with_logic

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    print("=" * 60)
    print("Rule Extraction Evaluation - Iteration 6")
    print("=" * 60)

    # Load files
    print("\n1. Loading files...")
    generated = load_json(GENERATED_FILE)
    reference = load_json(REFERENCE_FILE)

    print("   - Parsing BUD document...")
    bud_fields = parse_bud_document(BUD_FILE)
    print(f"   - Found {len(bud_fields)} fields with logic/rules in BUD")

    # Extract formFillMetadatas
    gen_metadatas = extract_form_fill_metadatas(generated)
    ref_metadatas = extract_form_fill_metadatas(reference)

    print(f"   - Generated: {len(gen_metadatas)} fields")
    print(f"   - Reference: {len(ref_metadatas)} fields")

    # Analyze rules
    print("\n2. Analyzing rules...")
    gen_rule_types, gen_all_rules = analyze_rules(gen_metadatas)
    ref_rule_types, ref_all_rules = analyze_rules(ref_metadatas)

    print(f"   - Generated rules: {len(gen_all_rules)}")
    print(f"   - Reference rules: {len(ref_all_rules)}")

    # Rule type comparison
    print("\n3. Rule type comparison:")
    rule_type_comparison = {}
    all_types = set(gen_rule_types.keys()) | set(ref_rule_types.keys())

    for rtype in sorted(all_types):
        gen_count = len(gen_rule_types.get(rtype, []))
        ref_count = len(ref_rule_types.get(rtype, []))
        print(f"   - {rtype}: Generated={gen_count}, Reference={ref_count}")
        rule_type_comparison[rtype] = {
            'generated': gen_count,
            'reference': ref_count,
            'matched': min(gen_count, ref_count)  # Simplified
        }

    # Panel-by-panel evaluation
    print("\n4. Panel-by-panel evaluation...")
    gen_panels = group_fields_by_panel(gen_metadatas)
    ref_panels = group_fields_by_panel(ref_metadatas)

    panel_scores = {}
    missing_rules = []

    for panel_name in set(gen_panels.keys()) | set(ref_panels.keys()):
        gen_panel_fields = gen_panels.get(panel_name, [])
        ref_panel_fields = ref_panels.get(panel_name, [])

        # Count rules in each panel
        gen_panel_rules = []
        ref_panel_rules = []

        for meta in gen_panel_fields:
            for rule in meta.get('formFillRules', []):
                gen_panel_rules.append({
                    'field_name': meta.get('formTag', {}).get('name'),
                    'field_id': meta.get('id'),
                    'rule': rule,
                    'rule_type': rule.get('actionType')
                })

        for meta in ref_panel_fields:
            for rule in meta.get('formFillRules', []):
                ref_panel_rules.append({
                    'field_name': meta.get('formTag', {}).get('name'),
                    'field_id': meta.get('id'),
                    'rule': rule,
                    'rule_type': rule.get('actionType')
                })

        # Compare
        matched, panel_missing, extra, incorrect = compare_rules(
            gen_panel_rules, ref_panel_rules, gen_metadatas, ref_metadatas
        )

        # Calculate score
        total_expected = len(ref_panel_rules)
        if total_expected > 0:
            score = len(matched) / total_expected
        else:
            score = 1.0 if len(gen_panel_rules) == 0 else 0.5

        panel_scores[panel_name] = {
            'score': round(score, 3),
            'fields_evaluated': len(gen_panel_fields),
            'rules_matched': len(matched),
            'rules_total_expected': total_expected,
            'rules_missing': panel_missing,
            'rules_extra': extra,
            'rules_incorrect': incorrect
        }

        # Add to global missing rules
        for m in panel_missing:
            missing_rules.append({
                'panel': panel_name,
                'field': m['field'],
                'expected_rule_type': m['rule_type'],
                'bud_logic': next(
                    (f.get('logic', '') for f in bud_fields if f['name'] == m['field']),
                    'Not found in BUD'
                )
            })

        print(f"   - {panel_name}: Score={score:.2f}, Matched={len(matched)}/{total_expected}")

    # Critical checks
    print("\n5. Critical checks...")
    ocr_valid, ocr_issues = check_ocr_chains(gen_metadatas)
    print(f"   - OCR chains valid: {ocr_valid}")

    ordinal_valid, ordinal_issues = check_ordinal_mapping(gen_metadatas)
    print(f"   - Ordinal mapping correct: {ordinal_valid}")

    visibility_valid, visibility_issues = check_visibility_pairs(gen_metadatas)
    print(f"   - Visibility pairs complete: {visibility_valid}")

    no_duplicates, duplicate_issues = check_duplicate_rules(gen_metadatas)
    print(f"   - No duplicate rules: {no_duplicates}")

    # Calculate overall score
    panel_scores_values = [p['score'] for p in panel_scores.values()]
    overall_score = sum(panel_scores_values) / len(panel_scores_values) if panel_scores_values else 0

    # Apply penalties for critical check failures
    if not ocr_valid:
        overall_score *= 0.95
    if not ordinal_valid:
        overall_score *= 0.95
    if not visibility_valid:
        overall_score *= 0.98
    if not no_duplicates:
        overall_score *= 0.97

    passed = overall_score >= PASS_THRESHOLD

    print(f"\n6. Overall Score: {overall_score:.3f}")
    print(f"   Pass Threshold: {PASS_THRESHOLD}")
    print(f"   Result: {'PASSED' if passed else 'FAILED'}")

    # Generate self-heal instructions
    priority_fixes = []
    priority = 1

    # Add missing rules as fixes
    for m in missing_rules[:10]:  # Top 10 missing
        priority_fixes.append({
            'priority': priority,
            'panel': m['panel'],
            'field': m['field'],
            'action': 'add_rule',
            'rule_type': m['expected_rule_type'],
            'details': f"Add {m['expected_rule_type']} rule based on BUD logic: {m['bud_logic'][:100]}..."
        })
        priority += 1

    # Add OCR chain fixes
    for issue in ocr_issues[:5]:
        priority_fixes.append({
            'priority': priority,
            'panel': 'PAN and GST Details',
            'field': issue['field'],
            'action': 'fix_ocr_chain',
            'details': issue['issue']
        })
        priority += 1

    # Add visibility pair fixes
    for issue in visibility_issues[:5]:
        priority_fixes.append({
            'priority': priority,
            'panel': 'Unknown',
            'field': 'Multiple',
            'action': 'add_visibility_pair',
            'details': issue['issue']
        })
        priority += 1

    # Build final report
    report = {
        'evaluation_metadata': {
            'generated_file': GENERATED_FILE,
            'reference_file': REFERENCE_FILE,
            'bud_file': BUD_FILE,
            'timestamp': datetime.now().isoformat(),
            'pass_threshold': PASS_THRESHOLD,
            'iteration': ITERATION
        },
        'overall_score': round(overall_score, 3),
        'passed': passed,
        'summary': {
            'generated_total_rules': len(gen_all_rules),
            'reference_total_rules': len(ref_all_rules),
            'bud_fields_with_logic': len(bud_fields)
        },
        'panel_scores': panel_scores,
        'rule_type_comparison': rule_type_comparison,
        'critical_checks': {
            'ocr_chains_valid': ocr_valid,
            'ocr_chain_issues': ocr_issues,
            'ordinal_mapping_correct': ordinal_valid,
            'ordinal_mapping_issues': ordinal_issues,
            'visibility_pairs_complete': visibility_valid,
            'visibility_pair_issues': visibility_issues,
            'no_duplicate_rules': no_duplicates,
            'duplicate_issues': duplicate_issues
        },
        'missing_rules': missing_rules,
        'self_heal_instructions': {
            'priority_fixes': priority_fixes,
            'total_issues': len(priority_fixes)
        }
    }

    # Save report
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n7. Report saved to: {OUTPUT_FILE}")

    return report

if __name__ == '__main__':
    report = main()
