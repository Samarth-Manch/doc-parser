#!/usr/bin/env python3
"""
Comprehensive Evaluation Script for Rule Extraction v9
Performs three-layer evaluation: BUD Verification, Reference Comparison, Schema Validation
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from doc_parser import DocumentParser

# Configuration
GENERATED_PATH = "adws/2026-02-01_14-44-47/populated_schema_v9.json"
REFERENCE_PATH = "documents/json_output/vendor_creation_sample_bud.json"
BUD_PATH = "documents/Vendor Creation Sample BUD.docx"
OUTPUT_PATH = "adws/2026-02-01_14-44-47/eval_report_v9.json"
PASS_THRESHOLD = 0.9
ITERATION = 9


def load_json(path):
    """Load JSON file"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_rules_by_field(json_data):
    """Extract all formFillRules grouped by field id and actionType"""
    rules_by_field = defaultdict(list)
    rules_by_type = defaultdict(list)
    all_rules = []

    doc_types = json_data.get("template", {}).get("documentTypes", [])
    for doc_type in doc_types:
        for metadata in doc_type.get("formFillMetadatas", []):
            field_id = metadata.get("id")
            field_name = metadata.get("formTag", {}).get("name", "")
            field_type = metadata.get("formTag", {}).get("type", "")

            for rule in metadata.get("formFillRules", []):
                rule_info = {
                    "field_id": field_id,
                    "field_name": field_name,
                    "field_type": field_type,
                    "rule": rule
                }
                rules_by_field[field_id].append(rule_info)
                rules_by_type[rule.get("actionType", "UNKNOWN")].append(rule_info)
                all_rules.append(rule_info)

    return rules_by_field, rules_by_type, all_rules


def extract_fields_map(json_data):
    """Extract field id to name mapping"""
    fields = {}
    doc_types = json_data.get("template", {}).get("documentTypes", [])
    for doc_type in doc_types:
        for metadata in doc_type.get("formFillMetadatas", []):
            field_id = metadata.get("id")
            field_name = metadata.get("formTag", {}).get("name", "")
            field_type = metadata.get("formTag", {}).get("type", "")
            fields[field_id] = {
                "name": field_name,
                "type": field_type,
                "mandatory": metadata.get("mandatory", False),
                "visible": metadata.get("visible", True),
                "editable": metadata.get("editable", True)
            }
    return fields


def extract_panels(json_data):
    """Extract panel structure"""
    panels = []
    doc_types = json_data.get("template", {}).get("documentTypes", [])
    for doc_type in doc_types:
        current_panel = None
        panel_fields = []
        for metadata in doc_type.get("formFillMetadatas", []):
            field_type = metadata.get("formTag", {}).get("type", "")
            field_name = metadata.get("formTag", {}).get("name", "")
            field_id = metadata.get("id")

            if field_type == "PANEL":
                if current_panel:
                    panels.append({
                        "name": current_panel,
                        "fields": panel_fields
                    })
                current_panel = field_name
                panel_fields = []
            else:
                panel_fields.append({
                    "id": field_id,
                    "name": field_name,
                    "type": field_type
                })

        if current_panel:
            panels.append({
                "name": current_panel,
                "fields": panel_fields
            })

    return panels


def analyze_rule_types(rules_by_type):
    """Analyze rule type distribution"""
    analysis = {}
    for rule_type, rules in rules_by_type.items():
        analysis[rule_type] = {
            "count": len(rules),
            "fields": list(set(r["field_name"] for r in rules))
        }
    return analysis


def check_ocr_chains(rules_by_type):
    """Check OCR rules and their postTriggerRuleIds chains"""
    ocr_rules = rules_by_type.get("OCR", [])
    issues = []
    valid_chains = []

    for rule_info in ocr_rules:
        rule = rule_info["rule"]
        post_trigger = rule.get("postTriggerRuleIds", [])

        if not post_trigger:
            issues.append({
                "field": rule_info["field_name"],
                "rule_id": rule.get("id"),
                "issue": "OCR rule missing postTriggerRuleIds chain"
            })
        else:
            valid_chains.append({
                "field": rule_info["field_name"],
                "rule_id": rule.get("id"),
                "post_trigger_ids": post_trigger
            })

    return {
        "total_ocr_rules": len(ocr_rules),
        "valid_chains": len(valid_chains),
        "issues": issues,
        "chains": valid_chains
    }


def check_verify_rules(rules_by_type):
    """Check VERIFY rules for ordinal destinationIds mapping"""
    verify_rules = rules_by_type.get("VERIFY", [])
    issues = []
    valid_rules = []

    for rule_info in verify_rules:
        rule = rule_info["rule"]
        dest_ids = rule.get("destinationIds", [])

        if not dest_ids:
            issues.append({
                "field": rule_info["field_name"],
                "rule_id": rule.get("id"),
                "issue": "VERIFY rule missing destinationIds"
            })
        else:
            valid_rules.append({
                "field": rule_info["field_name"],
                "rule_id": rule.get("id"),
                "destination_count": len(dest_ids)
            })

    return {
        "total_verify_rules": len(verify_rules),
        "valid_rules": len(valid_rules),
        "issues": issues
    }


def check_visibility_pairs(rules_by_type):
    """Check MAKE_VISIBLE and MAKE_INVISIBLE pairs"""
    visible_rules = rules_by_type.get("MAKE_VISIBLE", [])
    invisible_rules = rules_by_type.get("MAKE_INVISIBLE", [])

    visible_targets = defaultdict(list)
    invisible_targets = defaultdict(list)

    for rule_info in visible_rules:
        rule = rule_info["rule"]
        source_ids = tuple(rule.get("sourceIds", []))
        for dest_id in rule.get("destinationIds", []):
            visible_targets[(source_ids, dest_id)].append(rule_info)

    for rule_info in invisible_rules:
        rule = rule_info["rule"]
        source_ids = tuple(rule.get("sourceIds", []))
        for dest_id in rule.get("destinationIds", []):
            invisible_targets[(source_ids, dest_id)].append(rule_info)

    # Find unpaired visibility rules
    missing_invisible = []
    missing_visible = []
    proper_pairs = []

    for key in visible_targets:
        if key not in invisible_targets:
            missing_invisible.append({
                "source_ids": list(key[0]),
                "destination_id": key[1],
                "field": visible_targets[key][0]["field_name"]
            })
        else:
            proper_pairs.append({
                "source_ids": list(key[0]),
                "destination_id": key[1]
            })

    for key in invisible_targets:
        if key not in visible_targets:
            missing_visible.append({
                "source_ids": list(key[0]),
                "destination_id": key[1],
                "field": invisible_targets[key][0]["field_name"]
            })

    return {
        "total_visible_rules": len(visible_rules),
        "total_invisible_rules": len(invisible_rules),
        "proper_pairs": len(proper_pairs),
        "missing_invisible_counterparts": missing_invisible,
        "missing_visible_counterparts": missing_visible
    }


def check_mandatory_pairs(rules_by_type):
    """Check MAKE_MANDATORY and MAKE_NON_MANDATORY pairs"""
    mandatory_rules = rules_by_type.get("MAKE_MANDATORY", [])
    non_mandatory_rules = rules_by_type.get("MAKE_NON_MANDATORY", [])

    mandatory_targets = defaultdict(list)
    non_mandatory_targets = defaultdict(list)

    for rule_info in mandatory_rules:
        rule = rule_info["rule"]
        source_ids = tuple(rule.get("sourceIds", []))
        for dest_id in rule.get("destinationIds", []):
            mandatory_targets[(source_ids, dest_id)].append(rule_info)

    for rule_info in non_mandatory_rules:
        rule = rule_info["rule"]
        source_ids = tuple(rule.get("sourceIds", []))
        for dest_id in rule.get("destinationIds", []):
            non_mandatory_targets[(source_ids, dest_id)].append(rule_info)

    # Find unpaired mandatory rules
    missing_non_mandatory = []
    proper_pairs = []

    for key in mandatory_targets:
        if key not in non_mandatory_targets:
            missing_non_mandatory.append({
                "source_ids": list(key[0]),
                "destination_id": key[1],
                "field": mandatory_targets[key][0]["field_name"]
            })
        else:
            proper_pairs.append({
                "source_ids": list(key[0]),
                "destination_id": key[1]
            })

    return {
        "total_mandatory_rules": len(mandatory_rules),
        "total_non_mandatory_rules": len(non_mandatory_rules),
        "proper_pairs": len(proper_pairs),
        "missing_non_mandatory_counterparts": missing_non_mandatory
    }


def check_disabled_consolidation(rules_by_type):
    """Check if MAKE_DISABLED rules are consolidated"""
    disabled_rules = rules_by_type.get("MAKE_DISABLED", [])

    # Group by source field
    by_source = defaultdict(list)
    for rule_info in disabled_rules:
        rule = rule_info["rule"]
        source_ids = tuple(rule.get("sourceIds", []))
        by_source[source_ids].append(rule_info)

    # Check for consolidation
    consolidated = []
    fragmented = []

    for source_ids, rules in by_source.items():
        if len(rules) == 1:
            consolidated.append({
                "source_ids": list(source_ids),
                "destination_count": len(rules[0]["rule"].get("destinationIds", []))
            })
        else:
            fragmented.append({
                "source_ids": list(source_ids),
                "rule_count": len(rules),
                "issue": "Multiple MAKE_DISABLED rules from same source - should be consolidated"
            })

    return {
        "total_disabled_rules": len(disabled_rules),
        "consolidated_sources": len(consolidated),
        "fragmented_sources": len(fragmented),
        "fragmentation_issues": fragmented
    }


def compare_rule_counts(gen_by_type, ref_by_type):
    """Compare rule counts between generated and reference"""
    all_types = set(gen_by_type.keys()) | set(ref_by_type.keys())

    comparison = {}
    for rule_type in sorted(all_types):
        gen_count = len(gen_by_type.get(rule_type, []))
        ref_count = len(ref_by_type.get(rule_type, []))
        diff = gen_count - ref_count

        comparison[rule_type] = {
            "generated": gen_count,
            "reference": ref_count,
            "difference": diff,
            "status": "MATCH" if diff == 0 else ("OVER" if diff > 0 else "UNDER")
        }

    return comparison


def calculate_panel_scores(gen_panels, ref_panels, gen_rules_by_field, ref_rules_by_field):
    """Calculate scores per panel"""
    panel_scores = []

    for gen_panel in gen_panels:
        panel_name = gen_panel["name"]

        # Find matching reference panel
        ref_panel = None
        for rp in ref_panels:
            if rp["name"].lower() == panel_name.lower():
                ref_panel = rp
                break

        gen_field_ids = [f["id"] for f in gen_panel["fields"]]

        # Count rules for this panel's fields
        gen_rule_count = sum(len(gen_rules_by_field.get(fid, [])) for fid in gen_field_ids)

        if ref_panel:
            ref_field_ids = [f["id"] for f in ref_panel["fields"]]
            ref_rule_count = sum(len(ref_rules_by_field.get(fid, [])) for fid in ref_field_ids)

            # Calculate match score
            if ref_rule_count > 0:
                score = min(gen_rule_count / ref_rule_count, 1.0)
            else:
                score = 1.0 if gen_rule_count == 0 else 0.5
        else:
            ref_rule_count = 0
            score = 0.5  # Panel exists in generated but not reference

        panel_scores.append({
            "panel": panel_name,
            "generated_field_count": len(gen_panel["fields"]),
            "generated_rule_count": gen_rule_count,
            "reference_rule_count": ref_rule_count,
            "score": round(score, 3)
        })

    return panel_scores


def identify_missing_rules(gen_rules_by_type, ref_rules_by_type):
    """Identify potentially missing rule patterns from reference"""
    missing = []

    for rule_type, ref_rules in ref_rules_by_type.items():
        gen_rules = gen_rules_by_type.get(rule_type, [])

        if len(gen_rules) < len(ref_rules):
            missing.append({
                "rule_type": rule_type,
                "expected": len(ref_rules),
                "found": len(gen_rules),
                "gap": len(ref_rules) - len(gen_rules)
            })

    return missing


def generate_self_heal_instructions(
    visibility_check,
    mandatory_check,
    disabled_check,
    ocr_check,
    verify_check,
    missing_rules
):
    """Generate self-healing instructions with priority fixes"""
    priority_fixes = []

    # Priority 1: Critical structural issues
    if ocr_check["issues"]:
        priority_fixes.append({
            "priority": 1,
            "type": "OCR_CHAIN_MISSING",
            "description": "OCR rules missing postTriggerRuleIds chains to VERIFY rules",
            "count": len(ocr_check["issues"]),
            "action": "Add postTriggerRuleIds pointing to corresponding VERIFY rule IDs",
            "affected_fields": [i["field"] for i in ocr_check["issues"]]
        })

    if verify_check["issues"]:
        priority_fixes.append({
            "priority": 1,
            "type": "VERIFY_DESTINATION_MISSING",
            "description": "VERIFY rules missing ordinal destinationIds",
            "count": len(verify_check["issues"]),
            "action": "Add destinationIds with proper ordinal field mappings",
            "affected_fields": [i["field"] for i in verify_check["issues"]]
        })

    # Priority 2: Pairing issues
    if visibility_check["missing_invisible_counterparts"]:
        priority_fixes.append({
            "priority": 2,
            "type": "VISIBILITY_PAIR_INCOMPLETE",
            "description": "MAKE_VISIBLE rules without corresponding MAKE_INVISIBLE",
            "count": len(visibility_check["missing_invisible_counterparts"]),
            "action": "Add MAKE_INVISIBLE counterpart rules with NOT_IN condition",
            "affected": visibility_check["missing_invisible_counterparts"][:5]
        })

    if mandatory_check["missing_non_mandatory_counterparts"]:
        priority_fixes.append({
            "priority": 2,
            "type": "MANDATORY_PAIR_INCOMPLETE",
            "description": "MAKE_MANDATORY rules without corresponding MAKE_NON_MANDATORY",
            "count": len(mandatory_check["missing_non_mandatory_counterparts"]),
            "action": "Add MAKE_NON_MANDATORY counterpart rules with NOT_IN condition",
            "affected": mandatory_check["missing_non_mandatory_counterparts"][:5]
        })

    # Priority 3: Consolidation issues
    if disabled_check["fragmentation_issues"]:
        priority_fixes.append({
            "priority": 3,
            "type": "DISABLED_FRAGMENTATION",
            "description": "Multiple MAKE_DISABLED rules from same source should be consolidated",
            "count": len(disabled_check["fragmentation_issues"]),
            "action": "Merge destination IDs into single MAKE_DISABLED rule per source",
            "affected": disabled_check["fragmentation_issues"][:5]
        })

    # Priority 4: Missing rule types
    for missing in missing_rules:
        priority_fixes.append({
            "priority": 4,
            "type": "RULE_COUNT_MISMATCH",
            "description": f"Fewer {missing['rule_type']} rules than reference",
            "expected": missing["expected"],
            "found": missing["found"],
            "gap": missing["gap"],
            "action": f"Review BUD for additional {missing['rule_type']} rule triggers"
        })

    return priority_fixes


def main():
    print("=" * 60)
    print("COMPREHENSIVE RULE EXTRACTION EVALUATION - v9")
    print("=" * 60)

    # Load files
    print("\n[1/7] Loading files...")
    gen_data = load_json(GENERATED_PATH)
    ref_data = load_json(REFERENCE_PATH)

    # Parse BUD document
    print("[2/7] Parsing BUD document...")
    try:
        parser = DocumentParser()
        bud_parsed = parser.parse(BUD_PATH)
        bud_fields = len(bud_parsed.all_fields)
        bud_panels = [f.name for f in bud_parsed.all_fields if f.field_type.name == "PANEL"]
        print(f"    BUD contains {bud_fields} fields in {len(bud_panels)} panels")
    except Exception as e:
        print(f"    Warning: Could not parse BUD document: {e}")
        bud_fields = 0
        bud_panels = []

    # Extract rules
    print("[3/7] Extracting rules from generated output...")
    gen_by_field, gen_by_type, gen_all_rules = extract_rules_by_field(gen_data)
    gen_fields = extract_fields_map(gen_data)
    gen_panels = extract_panels(gen_data)
    print(f"    Generated: {len(gen_all_rules)} rules across {len(gen_fields)} fields")

    print("[4/7] Extracting rules from reference output...")
    ref_by_field, ref_by_type, ref_all_rules = extract_rules_by_field(ref_data)
    ref_fields = extract_fields_map(ref_data)
    ref_panels = extract_panels(ref_data)
    print(f"    Reference: {len(ref_all_rules)} rules across {len(ref_fields)} fields")

    # Analyze rule types
    print("[5/7] Analyzing rule types...")
    gen_analysis = analyze_rule_types(gen_by_type)
    ref_analysis = analyze_rule_types(ref_by_type)

    # Compare rule counts
    rule_comparison = compare_rule_counts(gen_by_type, ref_by_type)

    print("\n    Rule Type Comparison:")
    print("    " + "-" * 50)
    for rule_type, comp in sorted(rule_comparison.items()):
        status_icon = "✓" if comp["status"] == "MATCH" else ("↑" if comp["status"] == "OVER" else "↓")
        print(f"    {status_icon} {rule_type}: {comp['generated']} vs {comp['reference']} (ref) [{comp['status']}]")

    # Critical checks
    print("\n[6/7] Running critical checks...")

    ocr_check = check_ocr_chains(gen_by_type)
    print(f"    OCR Chains: {ocr_check['valid_chains']}/{ocr_check['total_ocr_rules']} valid")

    verify_check = check_verify_rules(gen_by_type)
    print(f"    VERIFY Rules: {verify_check['valid_rules']}/{verify_check['total_verify_rules']} valid")

    visibility_check = check_visibility_pairs(gen_by_type)
    print(f"    Visibility Pairs: {visibility_check['proper_pairs']} proper pairs")
    print(f"      Missing INVISIBLE: {len(visibility_check['missing_invisible_counterparts'])}")
    print(f"      Missing VISIBLE: {len(visibility_check['missing_visible_counterparts'])}")

    mandatory_check = check_mandatory_pairs(gen_by_type)
    print(f"    Mandatory Pairs: {mandatory_check['proper_pairs']} proper pairs")
    print(f"      Missing NON_MANDATORY: {len(mandatory_check['missing_non_mandatory_counterparts'])}")

    disabled_check = check_disabled_consolidation(gen_by_type)
    print(f"    MAKE_DISABLED: {disabled_check['consolidated_sources']} consolidated, {disabled_check['fragmented_sources']} fragmented")

    # Panel-by-panel scores
    print("\n[7/7] Calculating panel scores...")
    panel_scores = calculate_panel_scores(gen_panels, ref_panels, gen_by_field, ref_by_field)

    print("\n    Panel Scores:")
    print("    " + "-" * 50)
    for ps in panel_scores:
        score_bar = "█" * int(ps["score"] * 10) + "░" * (10 - int(ps["score"] * 10))
        print(f"    {score_bar} {ps['score']:.2f} - {ps['panel'][:40]}")

    # Calculate overall score
    avg_panel_score = sum(ps["score"] for ps in panel_scores) / len(panel_scores) if panel_scores else 0

    # Identify missing rules
    missing_rules = identify_missing_rules(gen_by_type, ref_by_type)

    # Generate self-heal instructions
    priority_fixes = generate_self_heal_instructions(
        visibility_check,
        mandatory_check,
        disabled_check,
        ocr_check,
        verify_check,
        missing_rules
    )

    # Compile report
    report = {
        "metadata": {
            "evaluation_timestamp": datetime.now().isoformat(),
            "iteration": ITERATION,
            "pass_threshold": PASS_THRESHOLD,
            "generated_file": GENERATED_PATH,
            "reference_file": REFERENCE_PATH,
            "bud_file": BUD_PATH
        },
        "summary": {
            "overall_score": round(avg_panel_score, 3),
            "pass": avg_panel_score >= PASS_THRESHOLD,
            "generated_total_rules": len(gen_all_rules),
            "reference_total_rules": len(ref_all_rules),
            "generated_total_fields": len(gen_fields),
            "reference_total_fields": len(ref_fields),
            "bud_total_fields": bud_fields
        },
        "rule_type_comparison": rule_comparison,
        "panel_scores": panel_scores,
        "critical_checks": {
            "ocr_chains": ocr_check,
            "verify_rules": verify_check,
            "visibility_pairs": visibility_check,
            "mandatory_pairs": mandatory_check,
            "disabled_consolidation": disabled_check
        },
        "missing_rules": missing_rules,
        "self_heal_instructions": {
            "priority_fixes": priority_fixes,
            "fix_count": len(priority_fixes),
            "critical_count": len([f for f in priority_fixes if f["priority"] == 1])
        }
    }

    # Save report
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"\n  Overall Score: {avg_panel_score:.3f}")
    print(f"  Pass Threshold: {PASS_THRESHOLD}")
    print(f"  Status: {'✓ PASS' if avg_panel_score >= PASS_THRESHOLD else '✗ FAIL'}")
    print(f"\n  Priority Fixes: {len(priority_fixes)}")
    print(f"  Critical Fixes: {len([f for f in priority_fixes if f['priority'] == 1])}")
    print(f"\n  Report saved to: {OUTPUT_PATH}")

    return report


if __name__ == "__main__":
    main()
