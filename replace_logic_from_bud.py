#!/usr/bin/env python3
"""
Replace logic fields in a pipeline JSON from the original BUD document.

Usage:
    python3 replace_logic_from_bud.py \
        --json output/vendor/runs/3/expression_rules/all_panels_expression_rules.json \
        --bud "documents/Vendor Creation Sample BUD 2.docx"
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parent)
sys.path.insert(0, PROJECT_ROOT)

from doc_parser import DocumentParser


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for fuzzy matching."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def build_bud_logic_index(bud_path: str) -> dict:
    """
    Parse BUD and return {(normalized_panel, normalized_field_name): logic}.
    """
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    index = {}
    for field in parsed.all_fields:
        panel = field.section.strip()
        name = field.name.strip()
        logic = (field.logic or '').strip()
        if panel and name:
            key = (normalize(panel), normalize(name))
            index[key] = logic

    return index


def replace_logic(json_path: str, bud_path: str) -> None:
    with open(json_path) as f:
        data = json.load(f)

    print(f"Parsing BUD: {bud_path}")
    bud_index = build_bud_logic_index(bud_path)
    print(f"  Built index with {len(bud_index)} fields")

    replaced = 0
    not_found = []

    for panel_name, fields in data.items():
        norm_panel = normalize(panel_name)
        for field in fields:
            field_name = field.get('field_name', '').strip()
            if not field_name or field.get('type', '').upper() == 'PANEL':
                continue

            key = (norm_panel, normalize(field_name))
            if key in bud_index:
                new_logic = bud_index[key]
                if field.get('logic') != new_logic:
                    field['logic'] = new_logic
                    replaced += 1
            else:
                not_found.append(f"{panel_name} / {field_name}")

    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nReplaced logic in {replaced} fields.")
    if not_found:
        print(f"No BUD match found for {len(not_found)} fields:")
        for entry in not_found:
            print(f"  - {entry}")


def main():
    parser = argparse.ArgumentParser(description="Replace field logic from BUD document.")
    parser.add_argument('--json', required=True, help='Pipeline JSON file to update')
    parser.add_argument('--bud', required=True, help='BUD .docx file')
    args = parser.parse_args()

    if not Path(args.json).exists():
        print(f"Error: JSON file not found: {args.json}", file=sys.stderr)
        sys.exit(1)
    if not Path(args.bud).exists():
        print(f"Error: BUD file not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    replace_logic(args.json, args.bud)


if __name__ == '__main__':
    main()
