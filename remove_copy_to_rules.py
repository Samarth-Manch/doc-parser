#!/usr/bin/env python3
"""Remove all Copy To rules from a pipeline JSON output file."""

import json
import sys


def remove_copy_to_rules(input_path, output_path=None):
    if output_path is None:
        output_path = input_path

    with open(input_path, "r") as f:
        data = json.load(f)

    total_removed = 0
    for panel_name, fields in data.items():
        for field in fields:
            original_count = len(field.get("rules", []))
            field["rules"] = [
                r for r in field.get("rules", [])
                if "Copy To" not in r.get("rule_name", "")
            ]
            removed = original_count - len(field["rules"])
            if removed:
                total_removed += removed
                print(f"  [{panel_name}] {field['field_name']}: removed {removed} Copy To rule(s)")

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nTotal Copy To rules removed: {total_removed}")
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.json> [output.json]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    remove_copy_to_rules(input_path, output_path)
