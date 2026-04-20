#!/usr/bin/env python3
"""Build a global field index from a BUD .docx for cross-panel annotation."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from doc_parser import DocumentParser


def main():
    bud_path = sys.argv[1]
    out_path = sys.argv[2]
    parser = DocumentParser()
    parsed = parser.parse(bud_path)

    panels = {}
    for f in parsed.all_fields:
        panel = f.section or ""
        if not panel:
            continue
        panels.setdefault(panel, []).append({
            "name": f.name,
            "variable_name": f.variable_name,
            "field_type": str(f.field_type),
            "logic": f.logic or "",
        })

    index = {
        "bud": bud_path,
        "panels": [
            {"name": pn, "fields": fs} for pn, fs in panels.items()
        ],
    }

    with open(out_path, "w") as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path} ({sum(len(p['fields']) for p in index['panels'])} fields, {len(index['panels'])} panels)")


if __name__ == "__main__":
    main()
