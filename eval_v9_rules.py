#!/usr/bin/env python3
"""
Rule Extraction Evaluation Script - Compare v9 output against reference.
"""

import json
from collections import defaultdict
from pathlib import Path


def load_json(path: str) -> dict:
    """Load JSON file."""
    with open(path, 'r') as f:
        return json.load(f)


def extract_rules_by_type(schema: dict) -> dict:
    """Extract all rules from schema grouped by action type."""
    rules_by_type = defaultdict(list)

    # Handle different schema formats
    if "template" in schema:
        metadatas = schema["template"]["documentTypes"][0]["formFillMetadatas"]
    else:
        metadatas = schema.get("documentTypes", [{}])[0].get("formFillMetadatas", [])

    for metadata in metadatas:
        field_name = metadata.get("formTag", {}).get("name", "Unknown")
        field_id = metadata.get("id")

        for rule in metadata.get("formFillRules", []):
            action_type = rule.get("actionType", "UNKNOWN")
            rules_by_type[action_type].append({
                "field_name": field_name,
                "field_id": field_id,
                "rule": rule
            })

    return rules_by_type


def count_rules(schema: dict) -> dict:
    """Count rules by action type."""
    rules_by_type = extract_rules_by_type(schema)
    return {k: len(v) for k, v in rules_by_type.items()}


def find_ocr_verify_chains(schema: dict) -> list:
    """Find OCR rules and check if they have postTriggerRuleIds to VERIFY rules."""
    chains = []

    if "template" in schema:
        metadatas = schema["template"]["documentTypes"][0]["formFillMetadatas"]
    else:
        metadatas = schema.get("documentTypes", [{}])[0].get("formFillMetadatas", [])

    # Build rule ID to action type mapping
    rule_id_to_action = {}
    for metadata in metadatas:
        for rule in metadata.get("formFillRules", []):
            rule_id_to_action[rule.get("id")] = rule.get("actionType")

    # Find OCR rules
    for metadata in metadatas:
        field_name = metadata.get("formTag", {}).get("name", "Unknown")

        for rule in metadata.get("formFillRules", []):
            if rule.get("actionType") == "OCR":
                source_type = rule.get("sourceType", "")
                post_triggers = rule.get("postTriggerRuleIds", [])

                # Check if any post trigger is a VERIFY rule
                verify_triggers = [
                    pid for pid in post_triggers
                    if rule_id_to_action.get(pid) == "VERIFY"
                ]

                chains.append({
                    "field": field_name,
                    "ocr_source": source_type,
                    "ocr_rule_id": rule.get("id"),
                    "post_triggers": post_triggers,
                    "verify_triggers": verify_triggers,
                    "chained": len(verify_triggers) > 0
                })

    return chains


def count_unique_destinations(schema: dict, action_type: str) -> int:
    """Count unique destination field IDs for a given action type."""
    rules_by_type = extract_rules_by_type(schema)
    all_dests = set()

    for item in rules_by_type.get(action_type, []):
        dests = item["rule"].get("destinationIds", [])
        all_dests.update([d for d in dests if d != -1])

    return len(all_dests)


def main():
    # File paths
    generated_path = "/home/samart/project/doc-parser/adws/2026-01-31_18-47-29/populated_schema_v3.json"
    reference_path = "/home/samart/project/doc-parser/documents/json_output/vendor_creation_sample_bud.json"

    print("=" * 70)
    print("RULE EXTRACTION EVALUATION - V9 vs Reference")
    print("=" * 70)

    # Load files
    print("\nLoading files...")
    generated = load_json(generated_path)
    reference = load_json(reference_path)

    # Count rules
    gen_counts = count_rules(generated)
    ref_counts = count_rules(reference)

    print("\n" + "-" * 70)
    print("RULE TYPE COMPARISON")
    print("-" * 70)
    print(f"{'Rule Type':<30} {'Generated':>12} {'Reference':>12} {'Diff':>10}")
    print("-" * 70)

    all_types = sorted(set(list(gen_counts.keys()) + list(ref_counts.keys())))
    total_gen = 0
    total_ref = 0

    for rule_type in all_types:
        gen = gen_counts.get(rule_type, 0)
        ref = ref_counts.get(rule_type, 0)
        diff = gen - ref
        diff_str = f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "="
        print(f"{rule_type:<30} {gen:>12} {ref:>12} {diff_str:>10}")
        total_gen += gen
        total_ref += ref

    print("-" * 70)
    print(f"{'TOTAL':<30} {total_gen:>12} {total_ref:>12} {total_gen - total_ref:>+10}")

    # OCR -> VERIFY chains
    print("\n" + "-" * 70)
    print("OCR -> VERIFY CHAIN ANALYSIS")
    print("-" * 70)

    gen_chains = find_ocr_verify_chains(generated)
    ref_chains = find_ocr_verify_chains(reference)

    print(f"\nGenerated OCR Rules: {len(gen_chains)}")
    for chain in gen_chains:
        status = "[CHAINED]" if chain["chained"] else "[NOT CHAINED]"
        print(f"  - {chain['ocr_source']}: {status} (triggers: {chain['post_triggers']})")

    print(f"\nReference OCR Rules: {len(ref_chains)}")
    for chain in ref_chains:
        status = "[CHAINED]" if chain["chained"] else "[NOT CHAINED]"
        print(f"  - {chain['ocr_source']}: {status} (triggers: {chain['post_triggers']})")

    gen_chained = sum(1 for c in gen_chains if c["chained"])
    ref_chained = sum(1 for c in ref_chains if c["chained"])

    print(f"\nChained OCR rules: Generated={gen_chained}/{len(gen_chains)}, Reference={ref_chained}/{len(ref_chains)}")

    # MAKE_DISABLED consolidation check
    print("\n" + "-" * 70)
    print("MAKE_DISABLED CONSOLIDATION CHECK")
    print("-" * 70)

    gen_disabled_dests = count_unique_destinations(generated, "MAKE_DISABLED")
    ref_disabled_dests = count_unique_destinations(reference, "MAKE_DISABLED")

    print(f"Generated: {gen_counts.get('MAKE_DISABLED', 0)} rules, {gen_disabled_dests} unique destinations")
    print(f"Reference: {ref_counts.get('MAKE_DISABLED', 0)} rules, {ref_disabled_dests} unique destinations")

    # VERIFY rule destination counts
    print("\n" + "-" * 70)
    print("VERIFY RULE ANALYSIS")
    print("-" * 70)

    gen_verify = extract_rules_by_type(generated).get("VERIFY", [])
    ref_verify = extract_rules_by_type(reference).get("VERIFY", [])

    print(f"\nGenerated VERIFY Rules: {len(gen_verify)}")
    for item in gen_verify:
        rule = item["rule"]
        dests = rule.get("destinationIds", [])
        non_empty = len([d for d in dests if d != -1])
        print(f"  - {rule.get('sourceType', 'N/A')}: {non_empty} destinations (of {len(dests)} ordinals)")

    print(f"\nReference VERIFY Rules: {len(ref_verify)}")
    for item in ref_verify:
        rule = item["rule"]
        dests = rule.get("destinationIds", [])
        non_empty = len([d for d in dests if d != -1])
        print(f"  - {rule.get('sourceType', 'N/A')}: {non_empty} destinations (of {len(dests)} ordinals)")

    # Calculate overall score
    print("\n" + "=" * 70)
    print("OVERALL SCORE")
    print("=" * 70)

    # Check key metrics
    metrics = {
        "OCR chains": (gen_chained >= ref_chained, f"{gen_chained}/{len(gen_chains)} vs {ref_chained}/{len(ref_chains)}"),
        "VERIFY rules": (gen_counts.get('VERIFY', 0) >= ref_counts.get('VERIFY', 0), f"{gen_counts.get('VERIFY', 0)} vs {ref_counts.get('VERIFY', 0)}"),
        "MAKE_VISIBLE rules": (gen_counts.get('MAKE_VISIBLE', 0) >= ref_counts.get('MAKE_VISIBLE', 0), f"{gen_counts.get('MAKE_VISIBLE', 0)} vs {ref_counts.get('MAKE_VISIBLE', 0)}"),
        "MAKE_DISABLED consolidated": (gen_counts.get('MAKE_DISABLED', 0) <= 5, f"{gen_counts.get('MAKE_DISABLED', 0)} (should be <=5)"),
        "EXT_DROP_DOWN rules": (gen_counts.get('EXT_DROP_DOWN', 0) >= 10, f"{gen_counts.get('EXT_DROP_DOWN', 0)} (should be >=10)"),
    }

    passed = 0
    for metric, (success, details) in metrics.items():
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {metric}: {details}")
        if success:
            passed += 1

    score = passed / len(metrics) * 100
    print(f"\nScore: {passed}/{len(metrics)} metrics passed ({score:.0f}%)")

    # Key issues remaining
    print("\n" + "-" * 70)
    print("REMAINING ISSUES TO FIX")
    print("-" * 70)

    issues = []

    # Check for missing rule types
    missing_types = set(ref_counts.keys()) - set(gen_counts.keys())
    if missing_types:
        issues.append(f"Missing rule types: {', '.join(missing_types)}")

    # Check specific rule counts
    if gen_counts.get('COPY_TO', 0) < ref_counts.get('COPY_TO', 0):
        issues.append(f"Missing COPY_TO rules: {gen_counts.get('COPY_TO', 0)} vs {ref_counts.get('COPY_TO', 0)} in reference")

    # Check unchained OCR rules
    unchained = [c for c in gen_chains if not c["chained"]]
    if unchained:
        types = [c["ocr_source"] for c in unchained]
        issues.append(f"OCR rules without VERIFY chain: {', '.join(types)}")

    if not issues:
        print("  No critical issues found!")
    else:
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")

    print("\n" + "=" * 70)
    print("Evaluation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
