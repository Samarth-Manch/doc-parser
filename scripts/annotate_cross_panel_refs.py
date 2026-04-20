#!/usr/bin/env python3
"""Annotate cross-panel references in BUD field logic using claude -p opus.

For each field with non-empty logic, send its logic + the field's current panel +
a compact global field index to the LLM and ask it to return the logic with
`(from <Panel> panel)` annotations inserted after any referenced field whose
host panel differs from the current field's panel. Ambiguous or unresolved
references are annotated as `(from ??? panel)`.

Output: JSON map of {field_id: {old, new, panel, field_name}} that the docx
patcher uses.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


PROMPT_TEMPLATE = """You are annotating a BUD (Business Understanding Document) field's logic text with cross-panel references.

CURRENT FIELD:
- Panel: {current_panel}
- Field name: {field_name}
- Logic: {logic_json}

GLOBAL FIELD INDEX (panel -> field names):
{index_block}

TASK:
Read the logic text. Find every reference to another field (by name or close paraphrase). For each referenced field:
1. If the referenced field exists in the CURRENT panel ({current_panel}), DO NOT annotate it.
2. If the referenced field exists in a DIFFERENT panel, insert ` (from <Panel Name> panel)` immediately after the referenced field name / quoted phrase.
3. If the referenced field cannot be found in any panel, OR matches fields in multiple panels ambiguously, insert ` (from ??? panel)` after it.
4. Do NOT annotate staging/table/column names (e.g., "VC_BASIC_DETAILS", "11th column") — only actual field-name references.
5. Preserve the original logic text verbatim. Only INSERT the annotation; never rewrite, reorder, or delete original words, punctuation, or whitespace.
6. If the logic does not reference any other field, return it unchanged.

STYLE EXAMPLES (from a reference BUD):
- Original: Value is derived based on field "Vendor Name and code" value as 11th column of VC_BASIC_DETAILS staging.
- Annotated: Value is derived based on field "Vendor Name and code" (from Basic Details panel) value as 11th column of VC_BASIC_DETAILS staging.

OUTPUT:
Return ONLY a JSON object with this exact shape, no markdown fence, no prose:
{{"annotated_logic": "<the full logic, with annotations inserted where required>", "changed": <true|false>}}
"""


def compact_index(index: dict, current_panel: str) -> str:
    """Return a compact 'Panel: f1 | f2 | f3' block listing all fields across panels."""
    lines = []
    for panel in index["panels"]:
        names = [f["name"] for f in panel["fields"] if f["name"]]
        marker = "  (CURRENT)" if panel["name"] == current_panel else ""
        lines.append(f"- {panel['name']}{marker}: " + " | ".join(names))
    return "\n".join(lines)


def call_claude(prompt: str, model: str, timeout: int) -> str:
    """Invoke claude -p and return stdout."""
    result = subprocess.run(
        ["claude", "--model", model, "-p", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude exit {result.returncode}: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def parse_response(raw: str) -> dict:
    """Extract the JSON object from the LLM response."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    # try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # find first { ... last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start:end + 1])
    raise ValueError(f"Could not parse JSON from response: {raw[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="field_index.json path")
    ap.add_argument("--output", required=True, help="output annotations json path")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--resume", action="store_true", help="Skip field_ids already in output file")
    args = ap.parse_args()

    with open(args.index) as fh:
        index = json.load(fh)

    annotations = {}
    if args.resume and Path(args.output).exists():
        with open(args.output) as fh:
            annotations = json.load(fh)
        print(f"Resumed: {len(annotations)} annotations already present")

    index_block_cache = {}
    total = sum(1 for p in index["panels"] for f in p["fields"] if f.get("logic", "").strip())
    done = 0

    for panel in index["panels"]:
        panel_name = panel["name"]
        for field in panel["fields"]:
            logic = (field.get("logic") or "").strip()
            if not logic:
                continue
            fid = f"{panel_name}::{field['name']}"
            done += 1
            if fid in annotations:
                print(f"[{done}/{total}] SKIP (cached) {fid}")
                continue

            if panel_name not in index_block_cache:
                index_block_cache[panel_name] = compact_index(index, panel_name)

            prompt = PROMPT_TEMPLATE.format(
                current_panel=panel_name,
                field_name=field["name"],
                logic_json=json.dumps(logic, ensure_ascii=False),
                index_block=index_block_cache[panel_name],
            )

            t0 = time.time()
            try:
                raw = call_claude(prompt, args.model, args.timeout)
                parsed = parse_response(raw)
                new_logic = parsed.get("annotated_logic", logic)
                changed = bool(parsed.get("changed", new_logic != logic))
            except Exception as exc:
                print(f"[{done}/{total}] ERROR {fid}: {exc}", file=sys.stderr)
                annotations[fid] = {
                    "panel": panel_name,
                    "field_name": field["name"],
                    "old": logic,
                    "new": logic,
                    "changed": False,
                    "error": str(exc)[:400],
                }
                with open(args.output, "w") as fh:
                    json.dump(annotations, fh, indent=2, ensure_ascii=False)
                continue

            annotations[fid] = {
                "panel": panel_name,
                "field_name": field["name"],
                "old": logic,
                "new": new_logic,
                "changed": changed,
            }
            dur = time.time() - t0
            marker = "CHANGED" if changed else "no-change"
            print(f"[{done}/{total}] {marker} {fid} ({dur:.1f}s)")

            # Persist after every field so we can resume safely
            with open(args.output, "w") as fh:
                json.dump(annotations, fh, indent=2, ensure_ascii=False)

    print(f"\nDone. {sum(1 for a in annotations.values() if a.get('changed'))}/{len(annotations)} fields annotated.")


if __name__ == "__main__":
    main()
