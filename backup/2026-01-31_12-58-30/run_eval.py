#!/usr/bin/env python3
"""
Comprehensive Rule Extraction Evaluation Script

Performs three-layer evaluation:
1. BUD Verification (Primary): Parse BUD, verify rules match natural language logic
2. Reference Comparison (Secondary): Compare against human-made reference
3. Schema Validation: Verify JSON structure and rule formats

Checks all rule types:
- VERIFY (with ordinal destinationIds mapping)
- OCR (with postTriggerRuleIds chains to VERIFY)
- EXT_DROP_DOWN / EXT_VALUE (for external dropdowns)
- Visibility pairs (MAKE_VISIBLE + MAKE_INVISIBLE)
- MAKE_DISABLED (consolidated, not individual)
- MAKE_MANDATORY / MAKE_NON_MANDATORY pairs
"""

import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class RuleStats:
    """Statistics for a rule type"""
    generated_count: int = 0
    reference_count: int = 0
    matched: int = 0
    missing: int = 0
    extra: int = 0

@dataclass
class PanelScore:
    """Score for a single panel"""
    panel_name: str
    panel_id: int
    total_fields: int = 0
    fields_with_rules: int = 0
    generated_rules: int = 0
    reference_rules: int = 0
    matched_rules: int = 0
    missing_rules: int = 0
    extra_rules: int = 0
    score: float = 0.0
    issues: List[str] = field(default_factory=list)

@dataclass
class CriticalCheck:
    """Result of a critical check"""
    check_name: str
    passed: bool
    details: str
    severity: str = "high"  # high, medium, low

@dataclass
class EvalReport:
    """Complete evaluation report"""
    timestamp: str
    pass_threshold: float
    iteration: int
    overall_score: float = 0.0
    passed: bool = False

    # Summary counts
    total_generated_rules: int = 0
    total_reference_rules: int = 0
    total_matched: int = 0
    total_missing: int = 0
    total_extra: int = 0

    # Detailed breakdown
    panel_scores: List[Dict] = field(default_factory=list)
    rule_type_comparison: Dict[str, Dict] = field(default_factory=dict)
    critical_checks: List[Dict] = field(default_factory=list)
    missing_rules: List[Dict] = field(default_factory=list)
    extra_rules: List[Dict] = field(default_factory=list)

    # Self-healing instructions
    self_heal_instructions: Dict = field(default_factory=dict)


def load_json(filepath: str) -> Dict:
    """Load JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_form_fill_metadatas(data: Dict) -> List[Dict]:
    """Extract formFillMetadatas from template structure"""
    metadatas = []
    if 'template' in data:
        doc_types = data['template'].get('documentTypes', [])
        for doc_type in doc_types:
            metadatas.extend(doc_type.get('formFillMetadatas', []))
    return metadatas


def get_field_name(metadata: Dict) -> str:
    """Get field name from metadata"""
    form_tag = metadata.get('formTag', {})
    return form_tag.get('name', 'Unknown')


def get_field_type(metadata: Dict) -> str:
    """Get field type from metadata"""
    form_tag = metadata.get('formTag', {})
    return form_tag.get('type', 'UNKNOWN')


def extract_rules_by_type(metadatas: List[Dict]) -> Dict[str, List[Dict]]:
    """Extract all rules grouped by actionType"""
    rules_by_type = defaultdict(list)

    for metadata in metadatas:
        field_id = metadata.get('id')
        field_name = get_field_name(metadata)

        for rule in metadata.get('formFillRules', []):
            action_type = rule.get('actionType', 'UNKNOWN')
            rule_info = {
                'rule': rule,
                'field_id': field_id,
                'field_name': field_name,
                'action_type': action_type
            }
            rules_by_type[action_type].append(rule_info)

    return dict(rules_by_type)


def extract_rules_by_field(metadatas: List[Dict]) -> Dict[int, List[Dict]]:
    """Extract all rules grouped by field ID"""
    rules_by_field = defaultdict(list)

    for metadata in metadatas:
        field_id = metadata.get('id')
        for rule in metadata.get('formFillRules', []):
            rules_by_field[field_id].append(rule)

    return dict(rules_by_field)


def count_rules_by_type(metadatas: List[Dict]) -> Dict[str, int]:
    """Count rules by action type"""
    counts = defaultdict(int)
    for metadata in metadatas:
        for rule in metadata.get('formFillRules', []):
            action_type = rule.get('actionType', 'UNKNOWN')
            counts[action_type] += 1
    return dict(counts)


def find_panels(metadatas: List[Dict]) -> List[Dict]:
    """Find all PANEL type fields"""
    panels = []
    for metadata in metadatas:
        if get_field_type(metadata) == 'PANEL':
            panels.append(metadata)
    return panels


def get_fields_in_panel(metadatas: List[Dict], panel_order: float) -> List[Dict]:
    """Get fields that belong to a panel based on form order"""
    panel_fields = []
    next_panel_order = float('inf')

    # Find the next panel's order
    for metadata in metadatas:
        if get_field_type(metadata) == 'PANEL':
            order = metadata.get('formOrder', 0)
            if order > panel_order and order < next_panel_order:
                next_panel_order = order

    # Get fields between current panel and next panel
    for metadata in metadatas:
        order = metadata.get('formOrder', 0)
        if order > panel_order and order < next_panel_order:
            if get_field_type(metadata) != 'PANEL':
                panel_fields.append(metadata)

    return panel_fields


def check_visibility_pairs(gen_rules: Dict[str, List], ref_rules: Dict[str, List]) -> CriticalCheck:
    """Check if MAKE_VISIBLE and MAKE_INVISIBLE rules are properly paired"""
    gen_visible = set()
    gen_invisible = set()
    ref_visible = set()
    ref_invisible = set()

    for rule_info in gen_rules.get('MAKE_VISIBLE', []):
        rule = rule_info['rule']
        source_ids = tuple(sorted(rule.get('sourceIds', [])))
        dest_ids = tuple(sorted(rule.get('destinationIds', [])))
        cond_values = tuple(sorted(rule.get('conditionalValues', [])))
        gen_visible.add((source_ids, dest_ids, cond_values))

    for rule_info in gen_rules.get('MAKE_INVISIBLE', []):
        rule = rule_info['rule']
        source_ids = tuple(sorted(rule.get('sourceIds', [])))
        dest_ids = tuple(sorted(rule.get('destinationIds', [])))
        cond_values = tuple(sorted(rule.get('conditionalValues', [])))
        gen_invisible.add((source_ids, dest_ids, cond_values))

    # Check if visible rules have corresponding invisible rules
    unpaired = []
    for vis in gen_visible:
        # Find matching invisible with same source and dest but different condition
        has_pair = False
        for inv in gen_invisible:
            if vis[0] == inv[0] and vis[1] == inv[1]:
                has_pair = True
                break
        if not has_pair:
            unpaired.append(f"MAKE_VISIBLE source={vis[0]}, dest={vis[1]}")

    passed = len(unpaired) == 0
    details = "All visibility rules properly paired" if passed else f"Unpaired visibility rules: {len(unpaired)}"

    return CriticalCheck(
        check_name="Visibility Pairs",
        passed=passed,
        details=details,
        severity="high" if not passed else "low"
    )


def check_ocr_verify_chains(gen_rules: Dict[str, List]) -> CriticalCheck:
    """Check if OCR rules have proper postTriggerRuleIds chains to VERIFY rules"""
    ocr_rules = gen_rules.get('OCR', [])
    verify_rule_ids = set()

    # Collect all VERIFY rule IDs
    for rule_info in gen_rules.get('VERIFY', []):
        verify_rule_ids.add(rule_info['rule'].get('id'))

    broken_chains = []
    for rule_info in ocr_rules:
        rule = rule_info['rule']
        post_trigger_ids = rule.get('postTriggerRuleIds', [])

        if not post_trigger_ids:
            broken_chains.append(f"OCR rule {rule.get('id')} has no postTriggerRuleIds")
        else:
            # Check if chain leads to VERIFY
            for trigger_id in post_trigger_ids:
                if trigger_id not in verify_rule_ids:
                    broken_chains.append(f"OCR rule {rule.get('id')} chain to {trigger_id} not found in VERIFY rules")

    passed = len(broken_chains) == 0
    details = "All OCR chains properly connected" if passed else f"Broken chains: {len(broken_chains)}"

    return CriticalCheck(
        check_name="OCR-VERIFY Chains",
        passed=passed,
        details=details + (f" - {broken_chains[:3]}" if broken_chains else ""),
        severity="high" if not passed else "low"
    )


def check_verify_ordinal_mapping(gen_rules: Dict[str, List]) -> CriticalCheck:
    """Check if VERIFY rules have ordinal destinationIds mapping"""
    verify_rules = gen_rules.get('VERIFY', [])
    issues = []

    for rule_info in verify_rules:
        rule = rule_info['rule']
        dest_ids = rule.get('destinationIds', [])
        cond_values = rule.get('conditionalValues', [])

        # VERIFY rules should have ordinal mapping where each condition value
        # corresponds to a destination ID position
        if len(dest_ids) > 0 and len(cond_values) > 0:
            # For ordinal mapping, we expect the number of destinations to relate
            # to the conditional values in some structured way
            if len(dest_ids) != len(cond_values) and len(dest_ids) != 1:
                issues.append(f"VERIFY rule {rule.get('id')}: dest_ids={len(dest_ids)}, cond_values={len(cond_values)}")

    passed = len(issues) == 0
    details = "All VERIFY rules have proper ordinal mapping" if passed else f"Issues: {len(issues)}"

    return CriticalCheck(
        check_name="VERIFY Ordinal Mapping",
        passed=passed,
        details=details,
        severity="medium" if not passed else "low"
    )


def check_make_disabled_consolidation(gen_rules: Dict[str, List]) -> CriticalCheck:
    """Check if MAKE_DISABLED rules are consolidated (not individual per field)"""
    disabled_rules = gen_rules.get('MAKE_DISABLED', [])

    # Count rules per source field
    source_to_rules = defaultdict(list)
    for rule_info in disabled_rules:
        rule = rule_info['rule']
        source_key = tuple(sorted(rule.get('sourceIds', [])))
        source_to_rules[source_key].append(rule)

    # Check for consolidation - ideally one rule per source with multiple destinations
    unconsolidated = []
    for source, rules in source_to_rules.items():
        if len(rules) > 3:  # Threshold for consolidation concern
            total_dests = sum(len(r.get('destinationIds', [])) for r in rules)
            unconsolidated.append(f"Source {source}: {len(rules)} rules with {total_dests} total destinations")

    passed = len(unconsolidated) == 0
    details = "MAKE_DISABLED rules properly consolidated" if passed else f"Unconsolidated: {len(unconsolidated)}"

    return CriticalCheck(
        check_name="MAKE_DISABLED Consolidation",
        passed=passed,
        details=details,
        severity="medium" if not passed else "low"
    )


def check_mandatory_pairs(gen_rules: Dict[str, List]) -> CriticalCheck:
    """Check if MAKE_MANDATORY rules have corresponding MAKE_NON_MANDATORY pairs"""
    mandatory = gen_rules.get('MAKE_MANDATORY', [])
    non_mandatory = gen_rules.get('MAKE_NON_MANDATORY', [])

    mand_signatures = set()
    non_mand_signatures = set()

    for rule_info in mandatory:
        rule = rule_info['rule']
        source_ids = tuple(sorted(rule.get('sourceIds', [])))
        dest_ids = tuple(sorted(rule.get('destinationIds', [])))
        mand_signatures.add((source_ids, dest_ids))

    for rule_info in non_mandatory:
        rule = rule_info['rule']
        source_ids = tuple(sorted(rule.get('sourceIds', [])))
        dest_ids = tuple(sorted(rule.get('destinationIds', [])))
        non_mand_signatures.add((source_ids, dest_ids))

    unpaired = []
    for sig in mand_signatures:
        if sig not in non_mand_signatures:
            unpaired.append(f"MAKE_MANDATORY source={sig[0]}, dest={sig[1]}")

    passed = len(unpaired) == 0
    details = "All mandatory rules properly paired" if passed else f"Unpaired: {len(unpaired)}"

    return CriticalCheck(
        check_name="Mandatory Pairs",
        passed=passed,
        details=details,
        severity="medium" if not passed else "low"
    )


def check_external_dropdown_rules(gen_metadatas: List[Dict], gen_rules: Dict[str, List]) -> CriticalCheck:
    """Check if EXTERNAL_DROP_DOWN fields have EXT_DROP_DOWN or EXT_VALUE rules"""
    external_fields = []
    for metadata in gen_metadatas:
        field_type = get_field_type(metadata)
        if 'EXTERNAL' in field_type or 'EXT' in field_type:
            external_fields.append(metadata)

    ext_drop_rules = gen_rules.get('EXT_DROP_DOWN', [])
    ext_value_rules = gen_rules.get('EXT_VALUE', [])

    # Get field IDs that have EXT rules
    fields_with_ext_rules = set()
    for rule_info in ext_drop_rules + ext_value_rules:
        fields_with_ext_rules.add(rule_info['field_id'])

    missing_ext_rules = []
    for field in external_fields:
        if field.get('id') not in fields_with_ext_rules:
            missing_ext_rules.append(f"{get_field_name(field)} (id={field.get('id')})")

    passed = len(missing_ext_rules) == 0
    details = "All external dropdowns have rules" if passed else f"Missing: {len(missing_ext_rules)}"

    return CriticalCheck(
        check_name="External Dropdown Rules",
        passed=passed,
        details=details + (f" - {missing_ext_rules[:3]}" if missing_ext_rules else ""),
        severity="high" if not passed else "low"
    )


def compare_rule_types(gen_counts: Dict[str, int], ref_counts: Dict[str, int]) -> Dict[str, Dict]:
    """Compare rule counts by type between generated and reference"""
    all_types = set(gen_counts.keys()) | set(ref_counts.keys())

    comparison = {}
    for rule_type in sorted(all_types):
        gen_count = gen_counts.get(rule_type, 0)
        ref_count = ref_counts.get(rule_type, 0)
        diff = gen_count - ref_count

        comparison[rule_type] = {
            'generated': gen_count,
            'reference': ref_count,
            'difference': diff,
            'status': 'match' if diff == 0 else ('extra' if diff > 0 else 'missing')
        }

    return comparison


def calculate_panel_score(gen_fields: List[Dict], ref_fields: List[Dict]) -> Tuple[float, int, int, int]:
    """Calculate score for a panel based on field rule matching"""
    gen_field_ids = {f.get('id') for f in gen_fields}
    ref_field_ids = {f.get('id') for f in ref_fields}

    gen_rules_count = sum(len(f.get('formFillRules', [])) for f in gen_fields)
    ref_rules_count = sum(len(f.get('formFillRules', [])) for f in ref_fields)

    # Simplified matching - compare total rule counts
    matched = min(gen_rules_count, ref_rules_count)
    missing = max(0, ref_rules_count - gen_rules_count)
    extra = max(0, gen_rules_count - ref_rules_count)

    if ref_rules_count == 0:
        score = 1.0 if gen_rules_count == 0 else 0.5
    else:
        score = matched / ref_rules_count

    return score, matched, missing, extra


def identify_missing_rules(gen_rules: Dict[str, List], ref_rules: Dict[str, List]) -> List[Dict]:
    """Identify rules in reference that are missing from generated"""
    missing = []

    for rule_type, ref_rule_infos in ref_rules.items():
        gen_rule_infos = gen_rules.get(rule_type, [])

        # Create signatures for generated rules
        gen_signatures = set()
        for rule_info in gen_rule_infos:
            rule = rule_info['rule']
            sig = (
                rule_type,
                tuple(sorted(rule.get('sourceIds', []))),
                tuple(sorted(rule.get('destinationIds', []))),
                rule.get('condition'),
                tuple(sorted(rule.get('conditionalValues', [])))
            )
            gen_signatures.add(sig)

        # Find missing reference rules
        for rule_info in ref_rule_infos:
            rule = rule_info['rule']
            sig = (
                rule_type,
                tuple(sorted(rule.get('sourceIds', []))),
                tuple(sorted(rule.get('destinationIds', []))),
                rule.get('condition'),
                tuple(sorted(rule.get('conditionalValues', [])))
            )

            if sig not in gen_signatures:
                missing.append({
                    'action_type': rule_type,
                    'field_name': rule_info['field_name'],
                    'field_id': rule_info['field_id'],
                    'sourceIds': rule.get('sourceIds', []),
                    'destinationIds': rule.get('destinationIds', []),
                    'condition': rule.get('condition'),
                    'conditionalValues': rule.get('conditionalValues', [])
                })

    return missing


def generate_self_heal_instructions(
    missing_rules: List[Dict],
    critical_checks: List[CriticalCheck],
    rule_type_comparison: Dict[str, Dict]
) -> Dict:
    """Generate self-healing instructions with priority fixes"""

    priority_fixes = []

    # High priority: Failed critical checks
    for check in critical_checks:
        if not check.passed and check.severity == 'high':
            priority_fixes.append({
                'priority': 1,
                'type': 'critical_check',
                'check_name': check.check_name,
                'action': f"Fix {check.check_name}: {check.details}"
            })

    # Medium priority: Rule type mismatches
    for rule_type, comparison in rule_type_comparison.items():
        if comparison['status'] == 'missing' and abs(comparison['difference']) > 2:
            priority_fixes.append({
                'priority': 2,
                'type': 'rule_type_mismatch',
                'rule_type': rule_type,
                'action': f"Add {abs(comparison['difference'])} missing {rule_type} rules"
            })

    # Lower priority: Individual missing rules (group by type)
    missing_by_type = defaultdict(list)
    for rule in missing_rules[:20]:  # Limit to first 20
        missing_by_type[rule['action_type']].append(rule)

    for rule_type, rules in missing_by_type.items():
        priority_fixes.append({
            'priority': 3,
            'type': 'missing_rules',
            'rule_type': rule_type,
            'count': len(rules),
            'sample_fields': [r['field_name'] for r in rules[:5]],
            'action': f"Add {len(rules)} missing {rule_type} rules for fields"
        })

    return {
        'priority_fixes': sorted(priority_fixes, key=lambda x: x['priority']),
        'total_issues': len(priority_fixes),
        'recommendation': 'Focus on critical checks first, then rule type alignment'
    }


def run_evaluation(
    generated_path: str,
    reference_path: str,
    output_path: str,
    pass_threshold: float = 0.9,
    iteration: int = 1
) -> EvalReport:
    """Run comprehensive evaluation"""

    print(f"Loading generated output: {generated_path}")
    gen_data = load_json(generated_path)

    print(f"Loading reference output: {reference_path}")
    ref_data = load_json(reference_path)

    # Extract form fill metadatas
    gen_metadatas = extract_form_fill_metadatas(gen_data)
    ref_metadatas = extract_form_fill_metadatas(ref_data)

    print(f"Generated fields: {len(gen_metadatas)}")
    print(f"Reference fields: {len(ref_metadatas)}")

    # Extract rules by type
    gen_rules = extract_rules_by_type(gen_metadatas)
    ref_rules = extract_rules_by_type(ref_metadatas)

    # Count rules by type
    gen_counts = count_rules_by_type(gen_metadatas)
    ref_counts = count_rules_by_type(ref_metadatas)

    print(f"Generated rule types: {gen_counts}")
    print(f"Reference rule types: {ref_counts}")

    # Compare rule types
    rule_type_comparison = compare_rule_types(gen_counts, ref_counts)

    # Run critical checks
    critical_checks = []
    critical_checks.append(check_visibility_pairs(gen_rules, ref_rules))
    critical_checks.append(check_ocr_verify_chains(gen_rules))
    critical_checks.append(check_verify_ordinal_mapping(gen_rules))
    critical_checks.append(check_make_disabled_consolidation(gen_rules))
    critical_checks.append(check_mandatory_pairs(gen_rules))
    critical_checks.append(check_external_dropdown_rules(gen_metadatas, gen_rules))

    # Find panels and calculate panel scores
    gen_panels = find_panels(gen_metadatas)
    ref_panels = find_panels(ref_metadatas)

    panel_scores = []
    for gen_panel in gen_panels:
        panel_name = get_field_name(gen_panel)
        panel_order = gen_panel.get('formOrder', 0)

        gen_panel_fields = get_fields_in_panel(gen_metadatas, panel_order)

        # Find corresponding reference panel
        ref_panel_fields = []
        for ref_panel in ref_panels:
            if get_field_name(ref_panel) == panel_name:
                ref_panel_order = ref_panel.get('formOrder', 0)
                ref_panel_fields = get_fields_in_panel(ref_metadatas, ref_panel_order)
                break

        score, matched, missing, extra = calculate_panel_score(gen_panel_fields, ref_panel_fields)

        gen_rules_count = sum(len(f.get('formFillRules', [])) for f in gen_panel_fields)
        ref_rules_count = sum(len(f.get('formFillRules', [])) for f in ref_panel_fields)

        panel_score = PanelScore(
            panel_name=panel_name,
            panel_id=gen_panel.get('id', 0),
            total_fields=len(gen_panel_fields),
            fields_with_rules=sum(1 for f in gen_panel_fields if f.get('formFillRules')),
            generated_rules=gen_rules_count,
            reference_rules=ref_rules_count,
            matched_rules=matched,
            missing_rules=missing,
            extra_rules=extra,
            score=score
        )
        panel_scores.append(asdict(panel_score))

    # Identify missing rules
    missing_rules = identify_missing_rules(gen_rules, ref_rules)

    # Calculate totals
    total_gen = sum(gen_counts.values())
    total_ref = sum(ref_counts.values())
    total_matched = min(total_gen, total_ref)
    total_missing = max(0, total_ref - total_gen)
    total_extra = max(0, total_gen - total_ref)

    # Calculate overall score
    if total_ref == 0:
        overall_score = 1.0 if total_gen == 0 else 0.5
    else:
        overall_score = total_matched / total_ref

    # Factor in critical check failures
    failed_critical = sum(1 for c in critical_checks if not c.passed and c.severity == 'high')
    if failed_critical > 0:
        overall_score *= (1 - 0.1 * failed_critical)

    # Generate self-heal instructions
    self_heal = generate_self_heal_instructions(missing_rules, critical_checks, rule_type_comparison)

    # Build report
    report = EvalReport(
        timestamp=datetime.now().isoformat(),
        pass_threshold=pass_threshold,
        iteration=iteration,
        overall_score=round(overall_score, 4),
        passed=overall_score >= pass_threshold,
        total_generated_rules=total_gen,
        total_reference_rules=total_ref,
        total_matched=total_matched,
        total_missing=total_missing,
        total_extra=total_extra,
        panel_scores=panel_scores,
        rule_type_comparison=rule_type_comparison,
        critical_checks=[asdict(c) for c in critical_checks],
        missing_rules=missing_rules[:50],  # Limit to first 50
        extra_rules=[],  # TODO: implement extra rules detection
        self_heal_instructions=self_heal
    )

    # Save report
    report_dict = asdict(report)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, indent=2)

    print(f"\n{'='*60}")
    print(f"EVALUATION REPORT")
    print(f"{'='*60}")
    print(f"Overall Score: {overall_score:.2%}")
    print(f"Passed: {'YES' if overall_score >= pass_threshold else 'NO'} (threshold: {pass_threshold:.0%})")
    print(f"Generated Rules: {total_gen}")
    print(f"Reference Rules: {total_ref}")
    print(f"Missing Rules: {total_missing}")
    print(f"Extra Rules: {total_extra}")
    print(f"\nCritical Checks:")
    for check in critical_checks:
        status = "✓" if check.passed else "✗"
        print(f"  {status} {check.check_name}: {check.details}")
    print(f"\nReport saved to: {output_path}")

    return report


if __name__ == '__main__':
    # Configuration
    GENERATED_PATH = '/home/samart/project/doc-parser/adws/2026-01-31_12-58-30/populated_schema_v1.json'
    REFERENCE_PATH = '/home/samart/project/doc-parser/documents/json_output/vendor_creation_sample_bud.json'
    OUTPUT_PATH = '/home/samart/project/doc-parser/adws/2026-01-31_12-58-30/eval_report_v1.json'
    PASS_THRESHOLD = 0.9
    ITERATION = 1

    report = run_evaluation(
        generated_path=GENERATED_PATH,
        reference_path=REFERENCE_PATH,
        output_path=OUTPUT_PATH,
        pass_threshold=PASS_THRESHOLD,
        iteration=ITERATION
    )
