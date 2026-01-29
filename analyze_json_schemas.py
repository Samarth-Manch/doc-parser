"""Analyze JSON schema files to understand rule implementations"""
import json
import os
from collections import defaultdict

json_dir = "documents/json_output"

def analyze_json_file(filepath):
    """Analyze a single JSON schema file"""
    with open(filepath) as f:
        data = json.load(f)

    analysis = {
        "filename": os.path.basename(filepath),
        "top_keys": list(data.keys()),
        "rules": [],
        "rule_types": defaultdict(int),
        "expressions": [],
        "ocr_rules": [],
        "validation_rules": [],
        "visibility_rules": [],
        "copy_rules": [],
        "fields_count": 0
    }

    # Navigate through the structure to find rules
    def find_rules(obj, path=""):
        if isinstance(obj, dict):
            # Check for rule-related keys
            if "rules" in obj:
                rules = obj["rules"]
                if isinstance(rules, list):
                    for rule in rules:
                        if isinstance(rule, dict):
                            analysis["rules"].append(rule)
                            rule_name = rule.get("ruleName", rule.get("name", "unknown"))
                            rule_action = rule.get("action", "")
                            analysis["rule_types"][rule_name] += 1

                            # Categorize rules
                            if "OCR" in rule_name.upper():
                                analysis["ocr_rules"].append(rule)
                            if "EXECUTE" in rule_name.upper() or "EXPRESSION" in rule_name.upper():
                                analysis["expressions"].append(rule)
                            if "VALIDATION" in rule_name.upper() or "VERIFY" in rule_name.upper():
                                analysis["validation_rules"].append(rule)
                            if "VISIBLE" in rule_name.upper() or "INVISIBLE" in rule_name.upper():
                                analysis["visibility_rules"].append(rule)
                            if "COPY" in rule_name.upper():
                                analysis["copy_rules"].append(rule)

            # Check for expression in params
            if "params" in obj and isinstance(obj["params"], dict):
                if "value" in obj["params"]:
                    val = obj["params"]["value"]
                    if val and any(fn in str(val) for fn in ["vo(", "mvi(", "minvi(", "mm(", "mnm(", "ctfd("]):
                        analysis["expressions"].append({
                            "path": path,
                            "expression": val,
                            "context": obj
                        })

            # Count fields
            if "formFillMetadataList" in obj:
                analysis["fields_count"] += len(obj["formFillMetadataList"])

            for key, value in obj.items():
                find_rules(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_rules(item, f"{path}[{i}]")

    find_rules(data)
    return analysis

# Analyze all JSON files
print("="*100)
print("ANALYSIS OF JSON SCHEMA FILES")
print("="*100)

all_analyses = []
for filename in sorted(os.listdir(json_dir)):
    if filename.endswith('.json'):
        filepath = os.path.join(json_dir, filename)
        print(f"\n{'='*80}")
        print(f"FILE: {filename}")
        print(f"{'='*80}")

        analysis = analyze_json_file(filepath)
        all_analyses.append(analysis)

        print(f"Top-level keys: {analysis['top_keys']}")
        print(f"Total rules found: {len(analysis['rules'])}")
        print(f"Fields count: {analysis['fields_count']}")
        print(f"\nRule types breakdown:")
        for rule_type, count in sorted(analysis["rule_types"].items(), key=lambda x: -x[1])[:15]:
            print(f"  {rule_type}: {count}")

        print(f"\nOCR Rules: {len(analysis['ocr_rules'])}")
        print(f"Expression Rules: {len(analysis['expressions'])}")
        print(f"Validation Rules: {len(analysis['validation_rules'])}")
        print(f"Visibility Rules: {len(analysis['visibility_rules'])}")
        print(f"Copy Rules: {len(analysis['copy_rules'])}")

# Show sample rules
print("\n" + "="*100)
print("SAMPLE RULES FROM ALL FILES")
print("="*100)

# Collect all unique rule types
all_rule_types = defaultdict(list)
for analysis in all_analyses:
    for rule in analysis["rules"]:
        rule_name = rule.get("ruleName", rule.get("name", "unknown"))
        all_rule_types[rule_name].append(rule)

print(f"\nTotal unique rule types: {len(all_rule_types)}")
print("\nAll rule types found:")
for rule_type in sorted(all_rule_types.keys()):
    print(f"  - {rule_type} ({len(all_rule_types[rule_type])} occurrences)")
