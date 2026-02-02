#!/usr/bin/env python3
"""
Comprehensive three-layer rule extraction evaluation script.
Evaluates generated rules against BUD document and human-made reference.
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from doc_parser import DocumentParser

# Configuration
PASS_THRESHOLD = 0.9
ITERATION = 1
GENERATED_FILE = Path(__file__).parent / "populated_schema_v1.json"
REFERENCE_FILE = Path(__file__).parent.parent.parent / "documents/json_output/vendor_creation_sample_bud.json"
BUD_FILE = Path(__file__).parent.parent.parent / "documents/Vendor Creation Sample BUD.docx"
OUTPUT_FILE = Path(__file__).parent / "eval_report_v1.json"


def load_json_file(filepath: Path) -> Dict:
    """Load a JSON file safely."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_form_fill_metadatas(json_data: Dict) -> List[Dict]:
    """Extract formFillMetadatas from nested JSON structure."""
    metadatas = []

    # Navigate to documentTypes[0].formFillMetadatas
    if "template" in json_data:
        doc_types = json_data["template"].get("documentTypes", [])
        if doc_types:
            metadatas = doc_types[0].get("formFillMetadatas", [])
    elif "documentTypes" in json_data:
        doc_types = json_data.get("documentTypes", [])
        if doc_types:
            metadatas = doc_types[0].get("formFillMetadatas", [])

    return metadatas


def extract_rules_from_metadatas(metadatas: List[Dict]) -> Tuple[Dict[int, Dict], Dict[int, List[Dict]]]:
    """
    Extract field info and rules from formFillMetadatas.
    Returns: (field_map, rules_by_field_id)
    """
    field_map = {}  # id -> field info
    rules_by_field = defaultdict(list)  # field_id -> list of rules

    for meta in metadatas:
        field_id = meta.get("id")
        field_name = meta.get("formTag", {}).get("name", "")
        field_type = meta.get("formTag", {}).get("type", "")

        field_map[field_id] = {
            "id": field_id,
            "name": field_name,
            "type": field_type,
            "mandatory": meta.get("mandatory", False),
            "visible": meta.get("visible", True),
            "variableName": meta.get("variableName", "")
        }

        rules = meta.get("formFillRules", [])
        for rule in rules:
            rules_by_field[field_id].append(rule)

    return field_map, dict(rules_by_field)


def categorize_rules_by_type(rules_by_field: Dict[int, List[Dict]]) -> Dict[str, List[Dict]]:
    """Categorize all rules by their actionType."""
    by_type = defaultdict(list)

    for field_id, rules in rules_by_field.items():
        for rule in rules:
            action_type = rule.get("actionType", "UNKNOWN")
            rule_with_field = {**rule, "_field_id": field_id}
            by_type[action_type].append(rule_with_field)

    return dict(by_type)


def parse_bud_document(bud_path: Path) -> Dict:
    """Parse BUD document and extract field definitions with logic/rules."""
    parser = DocumentParser()
    parsed = parser.parse(str(bud_path))

    # Build a mapping of field name -> logic/rules text
    field_logic = {}
    panels = defaultdict(list)

    # Extract from all_fields which contains the logic column
    for field in parsed.all_fields:
        field_name = field.name
        logic_text = getattr(field, 'logic', '') or getattr(field, 'rules', '') or ''
        field_type = field.field_type.value if hasattr(field.field_type, 'value') else str(field.field_type)

        field_logic[field_name] = {
            "name": field_name,
            "type": field_type,
            "logic": logic_text,
            "dropdown_values": getattr(field, 'dropdown_values', []) or [],
            "is_mandatory": getattr(field, 'is_mandatory', False),
            "actor": getattr(field, 'actor', 'unknown')
        }

        # Group by panel if available
        panel = getattr(field, 'panel', 'Default')
        panels[panel].append(field_name)

    return {
        "field_logic": field_logic,
        "panels": dict(panels),
        "all_fields": [f.name for f in parsed.all_fields]
    }


def identify_expected_rules_from_logic(logic_text: str, field_name: str, field_type: str) -> List[Dict]:
    """
    Analyze BUD logic text to determine expected rule types.
    Returns list of expected rules based on logic analysis.
    """
    expected = []
    logic_lower = logic_text.lower() if logic_text else ""

    # Check for visibility rules
    visibility_patterns = [
        r"visible\s*(?:when|if)",
        r"show\s*(?:when|if|this)",
        r"hide\s*(?:when|if|this)",
        r"display\s*(?:when|if)",
        r"appears?\s*(?:when|if)",
    ]
    for pattern in visibility_patterns:
        if re.search(pattern, logic_lower):
            expected.append({"type": "MAKE_VISIBLE", "source": "visibility logic"})
            expected.append({"type": "MAKE_INVISIBLE", "source": "visibility pair"})
            break

    # Check for mandatory rules
    mandatory_patterns = [
        r"mandatory\s*(?:when|if)",
        r"required\s*(?:when|if)",
        r"make\s*mandatory",
        r"becomes?\s*mandatory",
    ]
    for pattern in mandatory_patterns:
        if re.search(pattern, logic_lower):
            expected.append({"type": "MAKE_MANDATORY", "source": "mandatory logic"})
            expected.append({"type": "MAKE_NON_MANDATORY", "source": "mandatory pair"})
            break

    # Check for disable rules
    disable_patterns = [
        r"disable[d]?\s*(?:when|if)",
        r"non[- ]?editable",
        r"read[- ]?only",
        r"cannot\s*(?:be\s*)?edit",
    ]
    for pattern in disable_patterns:
        if re.search(pattern, logic_lower):
            expected.append({"type": "MAKE_DISABLED", "source": "disable logic"})
            break

    # Check for verify/validation rules
    verify_patterns = [
        r"verify",
        r"validate",
        r"check\s*(?:if|that|whether)",
        r"must\s*match",
        r"should\s*be",
    ]
    for pattern in verify_patterns:
        if re.search(pattern, logic_lower):
            expected.append({"type": "VERIFY", "source": "verify logic"})
            break

    # Check for OCR rules
    ocr_patterns = [
        r"ocr",
        r"extract\s*(?:from|data)",
        r"auto[- ]?fill\s*from\s*(?:document|file|upload)",
        r"scan",
    ]
    for pattern in ocr_patterns:
        if re.search(pattern, logic_lower):
            expected.append({"type": "OCR", "source": "OCR logic"})
            break

    # Check for external dropdown
    if "external" in field_type.lower() or "ext" in field_type.lower():
        expected.append({"type": "EXT_DROP_DOWN", "source": "external dropdown type"})

    # Check for copy/auto-fill rules
    copy_patterns = [
        r"copy\s*(?:from|value)",
        r"auto[- ]?fill",
        r"populate\s*(?:from|with)",
        r"default\s*(?:to|value)",
    ]
    for pattern in copy_patterns:
        if re.search(pattern, logic_lower):
            expected.append({"type": "COPY", "source": "copy logic"})
            break

    return expected


def compare_rule_counts(generated_by_type: Dict[str, List], reference_by_type: Dict[str, List]) -> Dict[str, Dict]:
    """Compare rule counts between generated and reference."""
    all_types = set(generated_by_type.keys()) | set(reference_by_type.keys())

    comparison = {}
    for rule_type in all_types:
        gen_count = len(generated_by_type.get(rule_type, []))
        ref_count = len(reference_by_type.get(rule_type, []))

        comparison[rule_type] = {
            "generated": gen_count,
            "reference": ref_count,
            "difference": gen_count - ref_count,
            "matched": min(gen_count, ref_count)
        }

    return comparison


def validate_ocr_chains(rules_by_type: Dict[str, List], all_rules: Dict[int, List]) -> Dict:
    """Validate that OCR rules chain correctly to VERIFY rules."""
    ocr_rules = rules_by_type.get("OCR", [])
    issues = []
    valid_chains = 0

    # Build a set of all rule IDs
    all_rule_ids = set()
    for field_rules in all_rules.values():
        for rule in field_rules:
            if "id" in rule:
                all_rule_ids.add(rule["id"])

    for ocr_rule in ocr_rules:
        post_trigger_ids = ocr_rule.get("postTriggerRuleIds", [])
        if not post_trigger_ids:
            issues.append({
                "rule_id": ocr_rule.get("id"),
                "field_id": ocr_rule.get("_field_id"),
                "issue": "OCR rule has no postTriggerRuleIds"
            })
        else:
            # Check if chained rule exists
            for trigger_id in post_trigger_ids:
                if trigger_id not in all_rule_ids:
                    issues.append({
                        "rule_id": ocr_rule.get("id"),
                        "field_id": ocr_rule.get("_field_id"),
                        "issue": f"postTriggerRuleIds references non-existent rule {trigger_id}"
                    })
                else:
                    valid_chains += 1

    return {
        "total_ocr_rules": len(ocr_rules),
        "valid_chains": valid_chains,
        "issues": issues,
        "is_valid": len(issues) == 0
    }


def validate_ordinal_mapping(rules_by_type: Dict[str, List]) -> Dict:
    """Validate ordinal values map correctly to destinationIds positions."""
    verify_rules = rules_by_type.get("VERIFY", [])
    issues = []
    valid_mappings = 0

    for rule in verify_rules:
        ordinal = rule.get("ordinal")
        dest_ids = rule.get("destinationIds", [])

        if ordinal is not None:
            # ordinal should be 1-indexed, mapping to destinationIds[ordinal-1]
            if ordinal < 1:
                issues.append({
                    "rule_id": rule.get("id"),
                    "issue": f"Invalid ordinal value {ordinal} (must be >= 1)"
                })
            elif dest_ids and ordinal > len(dest_ids):
                issues.append({
                    "rule_id": rule.get("id"),
                    "issue": f"ordinal {ordinal} exceeds destinationIds length {len(dest_ids)}"
                })
            else:
                valid_mappings += 1

    return {
        "total_verify_rules": len(verify_rules),
        "valid_mappings": valid_mappings,
        "issues": issues,
        "is_valid": len(issues) == 0
    }


def validate_visibility_pairs(rules_by_type: Dict[str, List]) -> Dict:
    """Validate MAKE_VISIBLE rules have corresponding MAKE_INVISIBLE pairs."""
    visible_rules = rules_by_type.get("MAKE_VISIBLE", [])
    invisible_rules = rules_by_type.get("MAKE_INVISIBLE", [])

    # Group by destination field
    visible_by_dest = defaultdict(list)
    invisible_by_dest = defaultdict(list)

    for rule in visible_rules:
        for dest_id in rule.get("destinationIds", []):
            visible_by_dest[dest_id].append(rule)

    for rule in invisible_rules:
        for dest_id in rule.get("destinationIds", []):
            invisible_by_dest[dest_id].append(rule)

    # Check for unpaired rules
    missing_invisible = []
    missing_visible = []

    for dest_id in visible_by_dest:
        if dest_id not in invisible_by_dest:
            missing_invisible.append({
                "destination_id": dest_id,
                "issue": "MAKE_VISIBLE exists but MAKE_INVISIBLE missing"
            })

    for dest_id in invisible_by_dest:
        if dest_id not in visible_by_dest:
            missing_visible.append({
                "destination_id": dest_id,
                "issue": "MAKE_INVISIBLE exists but MAKE_VISIBLE missing"
            })

    return {
        "total_visible_rules": len(visible_rules),
        "total_invisible_rules": len(invisible_rules),
        "missing_invisible_pairs": missing_invisible,
        "missing_visible_pairs": missing_visible,
        "is_complete": len(missing_invisible) == 0 and len(missing_visible) == 0
    }


def validate_mandatory_pairs(rules_by_type: Dict[str, List]) -> Dict:
    """Validate MAKE_MANDATORY rules have corresponding MAKE_NON_MANDATORY pairs."""
    mandatory_rules = rules_by_type.get("MAKE_MANDATORY", [])
    non_mandatory_rules = rules_by_type.get("MAKE_NON_MANDATORY", [])

    # Similar logic to visibility pairs
    mandatory_by_dest = defaultdict(list)
    non_mandatory_by_dest = defaultdict(list)

    for rule in mandatory_rules:
        for dest_id in rule.get("destinationIds", []):
            mandatory_by_dest[dest_id].append(rule)

    for rule in non_mandatory_rules:
        for dest_id in rule.get("destinationIds", []):
            non_mandatory_by_dest[dest_id].append(rule)

    missing_non_mandatory = []
    for dest_id in mandatory_by_dest:
        if dest_id not in non_mandatory_by_dest:
            missing_non_mandatory.append({
                "destination_id": dest_id,
                "issue": "MAKE_MANDATORY exists but MAKE_NON_MANDATORY missing"
            })

    return {
        "total_mandatory_rules": len(mandatory_rules),
        "total_non_mandatory_rules": len(non_mandatory_rules),
        "missing_pairs": missing_non_mandatory,
        "is_complete": len(missing_non_mandatory) == 0
    }


def find_missing_rules(bud_data: Dict, generated_rules: Dict[int, List], field_map: Dict[int, Dict]) -> List[Dict]:
    """Identify rules expected from BUD but missing in generated output."""
    missing = []

    # Build reverse map: name -> id
    name_to_id = {}
    for fid, finfo in field_map.items():
        name_to_id[finfo["name"].lower().strip()] = fid

    for field_name, field_info in bud_data.get("field_logic", {}).items():
        logic_text = field_info.get("logic", "")
        if not logic_text:
            continue

        # Find expected rules from logic
        expected = identify_expected_rules_from_logic(
            logic_text,
            field_name,
            field_info.get("type", "")
        )

        # Check if field exists in generated
        field_id = name_to_id.get(field_name.lower().strip())
        if field_id is None:
            # Try partial match
            for name, fid in name_to_id.items():
                if field_name.lower() in name or name in field_name.lower():
                    field_id = fid
                    break

        if field_id is None:
            # Field not found in generated output
            if expected:
                missing.append({
                    "field": field_name,
                    "expected_rule_types": [e["type"] for e in expected],
                    "bud_logic": logic_text[:200],
                    "issue": "Field not found in generated output"
                })
            continue

        # Check if expected rules exist
        gen_rules = generated_rules.get(field_id, [])
        gen_types = set(r.get("actionType") for r in gen_rules)

        for exp in expected:
            if exp["type"] not in gen_types:
                missing.append({
                    "field": field_name,
                    "field_id": field_id,
                    "expected_rule_type": exp["type"],
                    "bud_logic": logic_text[:200],
                    "source": exp["source"]
                })

    return missing


def find_extra_rules(bud_data: Dict, generated_rules: Dict[int, List], field_map: Dict[int, Dict]) -> List[Dict]:
    """Identify rules in generated output that may not be in BUD."""
    extra = []

    # Build reverse map
    id_to_name = {fid: finfo["name"] for fid, finfo in field_map.items()}
    name_to_logic = {k.lower().strip(): v for k, v in bud_data.get("field_logic", {}).items()}

    for field_id, rules in generated_rules.items():
        field_name = id_to_name.get(field_id, f"Unknown (ID: {field_id})")
        field_logic = name_to_logic.get(field_name.lower().strip(), {})
        logic_text = field_logic.get("logic", "") if isinstance(field_logic, dict) else ""

        for rule in rules:
            action_type = rule.get("actionType")

            # Check if this rule type could be expected from logic
            expected = identify_expected_rules_from_logic(
                logic_text,
                field_name,
                field_map.get(field_id, {}).get("type", "")
            )
            expected_types = [e["type"] for e in expected]

            # EXT_DROP_DOWN is expected for external dropdown fields
            if action_type == "EXT_DROP_DOWN" or action_type == "EXT_VALUE":
                continue

            # MAKE_DISABLED at self-reference is common pattern
            if action_type == "MAKE_DISABLED" and field_id in rule.get("destinationIds", []):
                continue

            if action_type not in expected_types and logic_text:
                extra.append({
                    "field": field_name,
                    "field_id": field_id,
                    "rule_type": action_type,
                    "rule_id": rule.get("id"),
                    "reason": "Rule type not indicated in BUD logic"
                })

    return extra


def calculate_panel_scores(bud_data: Dict, generated_rules: Dict, field_map: Dict, reference_rules: Dict) -> Dict[str, Dict]:
    """Calculate scores per panel."""
    panels = bud_data.get("panels", {})
    if not panels:
        panels = {"Default": list(bud_data.get("field_logic", {}).keys())}

    # Build name to id mapping
    name_to_id = {}
    for fid, finfo in field_map.items():
        name_to_id[finfo["name"].lower().strip()] = fid

    panel_scores = {}

    for panel_name, field_names in panels.items():
        fields_checked = 0
        rules_matched = 0
        rules_missing = 0
        rules_in_ref = 0
        rules_in_gen = 0

        for field_name in field_names:
            field_id = name_to_id.get(field_name.lower().strip())
            if field_id is None:
                continue

            fields_checked += 1
            gen_rules = generated_rules.get(field_id, [])
            ref_rules = reference_rules.get(field_id, [])

            rules_in_gen += len(gen_rules)
            rules_in_ref += len(ref_rules)

            # Compare rule types
            gen_types = set(r.get("actionType") for r in gen_rules)
            ref_types = set(r.get("actionType") for r in ref_rules)

            rules_matched += len(gen_types & ref_types)
            rules_missing += len(ref_types - gen_types)

        total_expected = rules_in_ref if rules_in_ref > 0 else max(rules_in_gen, 1)
        score = rules_matched / total_expected if total_expected > 0 else 0.0

        panel_scores[panel_name] = {
            "score": round(score, 3),
            "fields_checked": fields_checked,
            "rules_generated": rules_in_gen,
            "rules_in_reference": rules_in_ref,
            "rules_matched": rules_matched,
            "rules_missing": rules_missing
        }

    return panel_scores


def generate_self_heal_instructions(missing_rules: List[Dict], critical_issues: Dict) -> Dict:
    """Generate actionable fix instructions."""
    priority_fixes = []

    # Add fixes for missing rules
    for missing in missing_rules[:10]:  # Top 10 priority
        fix = {
            "field": missing.get("field"),
            "issue": f"Missing {missing.get('expected_rule_type', missing.get('expected_rule_types'))} rule",
            "fix": f"Add {missing.get('expected_rule_type', missing.get('expected_rule_types'))} rule",
            "bud_reference": missing.get("bud_logic", "")[:100]
        }

        if missing.get("expected_rule_type") == "VERIFY":
            fix["fix"] = "Add VERIFY with ordinal 1->destinationIds[0] mapping"
        elif missing.get("expected_rule_type") == "MAKE_VISIBLE":
            fix["fix"] = "Add MAKE_VISIBLE and MAKE_INVISIBLE pair"
        elif missing.get("expected_rule_type") == "MAKE_MANDATORY":
            fix["fix"] = "Add MAKE_MANDATORY and MAKE_NON_MANDATORY pair"

        priority_fixes.append(fix)

    # Add fixes for critical issues
    if critical_issues.get("ocr_chains", {}).get("issues"):
        for issue in critical_issues["ocr_chains"]["issues"][:3]:
            priority_fixes.append({
                "field_id": issue.get("field_id"),
                "issue": issue.get("issue"),
                "fix": "Add or correct postTriggerRuleIds to chain OCR to VERIFY",
                "priority": "critical"
            })

    if critical_issues.get("visibility_pairs", {}).get("missing_invisible_pairs"):
        for issue in critical_issues["visibility_pairs"]["missing_invisible_pairs"][:3]:
            priority_fixes.append({
                "destination_id": issue.get("destination_id"),
                "issue": issue.get("issue"),
                "fix": "Add MAKE_INVISIBLE rule for complete visibility pair",
                "priority": "high"
            })

    return {
        "priority_fixes": priority_fixes,
        "total_fixes_needed": len(missing_rules) + sum(
            len(v.get("issues", []) if isinstance(v, dict) else 0)
            for v in critical_issues.values()
        )
    }


def run_evaluation():
    """Main evaluation function."""
    print("=" * 60)
    print("RULE EXTRACTION EVALUATION")
    print("=" * 60)

    # Load files
    print("\n[1] Loading files...")

    try:
        generated_data = load_json_file(GENERATED_FILE)
        print(f"  ✓ Generated: {GENERATED_FILE}")
    except Exception as e:
        print(f"  ✗ Failed to load generated file: {e}")
        return

    try:
        reference_data = load_json_file(REFERENCE_FILE)
        print(f"  ✓ Reference: {REFERENCE_FILE}")
    except Exception as e:
        print(f"  ✗ Failed to load reference file: {e}")
        reference_data = None

    # Parse BUD
    print("\n[2] Parsing BUD document...")
    try:
        bud_data = parse_bud_document(BUD_FILE)
        print(f"  ✓ BUD parsed: {len(bud_data.get('all_fields', []))} fields found")
    except Exception as e:
        print(f"  ✗ Failed to parse BUD: {e}")
        bud_data = {"field_logic": {}, "panels": {}, "all_fields": []}

    # Extract rules from generated
    print("\n[3] Extracting rules from generated output...")
    gen_metadatas = extract_form_fill_metadatas(generated_data)
    gen_field_map, gen_rules = extract_rules_from_metadatas(gen_metadatas)
    gen_by_type = categorize_rules_by_type(gen_rules)
    print(f"  ✓ {len(gen_field_map)} fields, {sum(len(r) for r in gen_rules.values())} rules")

    # Extract rules from reference
    print("\n[4] Extracting rules from reference...")
    if reference_data:
        ref_metadatas = extract_form_fill_metadatas(reference_data)
        ref_field_map, ref_rules = extract_rules_from_metadatas(ref_metadatas)
        ref_by_type = categorize_rules_by_type(ref_rules)
        print(f"  ✓ {len(ref_field_map)} fields, {sum(len(r) for r in ref_rules.values())} rules")
    else:
        ref_rules = {}
        ref_by_type = {}

    # Layer 1: BUD Verification
    print("\n[5] Layer 1: BUD Verification...")
    missing_rules = find_missing_rules(bud_data, gen_rules, gen_field_map)
    extra_rules = find_extra_rules(bud_data, gen_rules, gen_field_map)
    print(f"  Missing rules: {len(missing_rules)}")
    print(f"  Extra/unexpected rules: {len(extra_rules)}")

    # Layer 2: Reference Comparison
    print("\n[6] Layer 2: Reference Comparison...")
    rule_type_comparison = compare_rule_counts(gen_by_type, ref_by_type)
    for rtype, counts in rule_type_comparison.items():
        diff = counts["difference"]
        status = "✓" if diff == 0 else ("+" if diff > 0 else "-")
        print(f"  {rtype}: gen={counts['generated']}, ref={counts['reference']} {status}{abs(diff) if diff != 0 else ''}")

    # Layer 3: Schema Validation
    print("\n[7] Layer 3: Schema Validation...")
    ocr_validation = validate_ocr_chains(gen_by_type, gen_rules)
    ordinal_validation = validate_ordinal_mapping(gen_by_type)
    visibility_validation = validate_visibility_pairs(gen_by_type)
    mandatory_validation = validate_mandatory_pairs(gen_by_type)

    print(f"  OCR chains valid: {ocr_validation['is_valid']}")
    print(f"  Ordinal mapping valid: {ordinal_validation['is_valid']}")
    print(f"  Visibility pairs complete: {visibility_validation['is_complete']}")
    print(f"  Mandatory pairs complete: {mandatory_validation['is_complete']}")

    critical_checks = {
        "ocr_chains_valid": ocr_validation["is_valid"],
        "ordinal_mapping_correct": ordinal_validation["is_valid"],
        "visibility_pairs_complete": visibility_validation["is_complete"],
        "mandatory_pairs_complete": mandatory_validation["is_complete"]
    }

    # Calculate panel scores
    print("\n[8] Calculating panel scores...")
    panel_scores = calculate_panel_scores(bud_data, gen_rules, gen_field_map, ref_rules)
    for panel, score_info in panel_scores.items():
        print(f"  {panel}: {score_info['score']} ({score_info['rules_matched']}/{score_info['rules_in_reference']} matched)")

    # Calculate overall score
    if panel_scores:
        total_matched = sum(p["rules_matched"] for p in panel_scores.values())
        total_expected = sum(p["rules_in_reference"] for p in panel_scores.values())
        overall_score = total_matched / total_expected if total_expected > 0 else 0.0
    else:
        # Fallback: compare rule counts
        total_gen = sum(len(r) for r in gen_rules.values())
        total_ref = sum(len(r) for r in ref_rules.values())
        overall_score = min(total_gen, total_ref) / max(total_gen, total_ref) if max(total_gen, total_ref) > 0 else 0.0

    overall_score = round(overall_score, 3)
    passed = overall_score >= PASS_THRESHOLD

    print(f"\n{'='*60}")
    print(f"OVERALL SCORE: {overall_score}")
    print(f"PASS THRESHOLD: {PASS_THRESHOLD}")
    print(f"RESULT: {'PASS ✓' if passed else 'FAIL ✗'}")
    print(f"{'='*60}")

    # Generate self-heal instructions
    critical_issues = {
        "ocr_chains": ocr_validation,
        "ordinal_mapping": ordinal_validation,
        "visibility_pairs": visibility_validation,
        "mandatory_pairs": mandatory_validation
    }
    self_heal = generate_self_heal_instructions(missing_rules, critical_issues)

    # Build final report
    report = {
        "eval_metadata": {
            "iteration": ITERATION,
            "pass_threshold": PASS_THRESHOLD,
            "generated_file": str(GENERATED_FILE),
            "reference_file": str(REFERENCE_FILE),
            "bud_file": str(BUD_FILE),
            "evaluation_timestamp": datetime.now().isoformat()
        },
        "overall_score": overall_score,
        "pass": passed,
        "panel_scores": panel_scores,
        "rule_type_comparison": rule_type_comparison,
        "critical_checks": critical_checks,
        "critical_check_details": {
            "ocr_chains": ocr_validation,
            "ordinal_mapping": ordinal_validation,
            "visibility_pairs": visibility_validation,
            "mandatory_pairs": mandatory_validation
        },
        "missing_rules": missing_rules[:50],  # Limit to top 50
        "extra_rules": extra_rules[:30],  # Limit to top 30
        "self_heal_instructions": self_heal,
        "summary": {
            "total_fields_generated": len(gen_field_map),
            "total_fields_reference": len(ref_field_map) if reference_data else 0,
            "total_rules_generated": sum(len(r) for r in gen_rules.values()),
            "total_rules_reference": sum(len(r) for r in ref_rules.values()),
            "bud_fields_with_logic": len([f for f in bud_data.get("field_logic", {}).values() if f.get("logic")])
        }
    }

    # Save report
    print(f"\n[9] Saving report to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("  ✓ Report saved")

    return report


if __name__ == "__main__":
    run_evaluation()
