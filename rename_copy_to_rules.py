#!/usr/bin/env python3
"""Rename 'Copy To (Client)' rules to 'Copy To FormField Client (Client)' to match Rule-Schemas.json."""

import json
import sys


def rename_copy_to_rules(input_path, output_path=None):
    if output_path is None:
        output_path = input_path

    with open(input_path, "r") as f:
        data = json.load(f)

    OLD_NAME = "Copy To (Client)"
    NEW_NAME = "Copy To FormField Client (Client)"

    total_renamed = 0
    for panel_name, fields in data.items():
        if not isinstance(fields, list):
            continue
        for field in fields:
            if not isinstance(field, dict):
                continue
            for rule in field.get("rules", []):
                if rule.get("rule_name") == OLD_NAME:
                    rule["rule_name"] = NEW_NAME
                    total_renamed += 1
                    fname = field.get("variableName", field.get("field_name", field.get("name", "?")))
                    print(f"  [{panel_name}] {fname}: renamed rule")

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nTotal rules renamed: {total_renamed}")
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.json> [output.json]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    rename_copy_to_rules(input_path, output_path)
