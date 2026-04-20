#!/usr/bin/env python3
"""Batch-per-panel annotator for cross-panel field references.

One claude -p call per panel. Input lists all the fields in that panel (with
logic) plus the global index; output is a JSON map of field_name ->
{annotated_logic, changed}. Panels are processed in parallel with a worker
pool.

Supports --resume: if annotations.json exists, fields already populated are
skipped. If every field in a panel is already cached, that panel is skipped
entirely.
"""
import argparse
import concurrent.futures
import json
import subprocess
import sys
import threading
import time
from pathlib import Path


PROMPT_TEMPLATE = """You are annotating a BUD (Business Understanding Document) panel's field logic texts with cross-panel references.

CURRENT PANEL: {panel_name}

FIELDS IN THIS PANEL (with logic):
{fields_block}

GLOBAL FIELD INDEX (panel -> field names):
{index_block}

TASK:
For EACH field above, read its logic text. Find every reference to another field (by name or close paraphrase). For each referenced field:
1. If the referenced field exists in the CURRENT panel ({panel_name}), DO NOT annotate it.
2. If the referenced field exists in a DIFFERENT panel, insert ` (from <Panel Name> panel)` immediately after the referenced field name / quoted phrase.
3. If the referenced field cannot be found in any panel, OR matches multiple panels ambiguously, insert ` (from ??? panel)` after it.
4. Do NOT annotate staging/table/column names (e.g., "VC_BASIC_DETAILS", "11th column") — only actual field-name references.
5. Preserve each logic text VERBATIM. Only INSERT annotations; never rewrite, reorder, or delete original words, punctuation, or whitespace.
6. If a field's logic does not reference any other field, return it unchanged with changed=false.

STYLE EXAMPLE (from a reference BUD):
- Original: Value is derived based on field "Vendor Name and code" value as 11th column of VC_BASIC_DETAILS staging.
- Annotated: Value is derived based on field "Vendor Name and code" (from Basic Details panel) value as 11th column of VC_BASIC_DETAILS staging.

OUTPUT:
Return ONLY a JSON object (no markdown fence, no prose) of this shape:
{{
  "fields": [
    {{"field_name": "<exact name>", "annotated_logic": "<full logic with annotations>", "changed": <true|false>}},
    ...
  ]
}}
Include one entry for every field provided above, in the same order.
"""


def compact_index(panels, current_panel):
    lines = []
    for p in panels:
        names = [f["name"] for f in p["fields"] if f["name"]]
        marker = "  (CURRENT)" if p["name"] == current_panel else ""
        lines.append(f"- {p['name']}{marker}: " + " | ".join(names))
    return "\n".join(lines)


def build_fields_block(fields):
    lines = []
    for i, f in enumerate(fields, 1):
        lines.append(f'[{i}] field_name: "{f["name"]}"')
        lines.append(f'    logic: {json.dumps(f["logic"], ensure_ascii=False)}')
    return "\n".join(lines)


def parse_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start:end + 1])
    raise ValueError(f"Could not parse JSON from response: {raw[:400]}")


def process_panel(panel, all_panels, model, timeout):
    """Call claude -p for one panel. Return dict of field_name -> result."""
    fields = [f for f in panel["fields"] if (f.get("logic") or "").strip()]
    if not fields:
        return panel["name"], {}

    prompt = PROMPT_TEMPLATE.format(
        panel_name=panel["name"],
        fields_block=build_fields_block(fields),
        index_block=compact_index(all_panels, panel["name"]),
    )

    t0 = time.time()
    proc = subprocess.run(
        ["claude", "--model", model, "-p", prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    dur = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}: {proc.stderr.strip()[:300]}")
    parsed = parse_response(proc.stdout)

    out = {}
    for item in parsed.get("fields", []):
        name = item.get("field_name")
        if name:
            out[name] = {
                "annotated_logic": item.get("annotated_logic", ""),
                "changed": bool(item.get("changed", False)),
            }
    return panel["name"], out, dur, len(fields)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    with open(args.index) as fh:
        index = json.load(fh)
    panels = index["panels"]

    annotations = {}
    if args.resume and Path(args.output).exists():
        with open(args.output) as fh:
            annotations = json.load(fh)
        print(f"Resumed: {len(annotations)} entries already present")

    # Decide which panels still need work
    todo = []
    for p in panels:
        needs = [f for f in p["fields"] if (f.get("logic") or "").strip() and f"{p['name']}::{f['name']}" not in annotations]
        if needs:
            todo.append(p)
    print(f"Panels needing work: {len(todo)} / {len(panels)}")

    lock = threading.Lock()

    def persist():
        with open(args.output, "w") as fh:
            json.dump(annotations, fh, indent=2, ensure_ascii=False)

    def submit_panel(panel):
        t0 = time.time()
        panel_name = panel["name"]
        # Build a reduced-panel payload with only the fields that still need work.
        reduced = {"name": panel_name, "fields": [f for f in panel["fields"] if (f.get("logic") or "").strip() and f"{panel_name}::{f['name']}" not in annotations]}
        try:
            name, results, dur, nf = process_panel(reduced, panels, args.model, args.timeout)
        except Exception as exc:
            return panel_name, None, str(exc), time.time() - t0
        return panel_name, results, None, dur

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {pool.submit(submit_panel, p): p for p in todo}
        for fut in concurrent.futures.as_completed(futures):
            panel = futures[fut]
            panel_name, results, err, dur = fut.result()
            if err:
                print(f"[ERROR] {panel_name}: {err[:300]} ({dur:.1f}s)", file=sys.stderr)
                # stamp errors on each needs-work field so we can retry later
                with lock:
                    for f in panel["fields"]:
                        if (f.get("logic") or "").strip():
                            fid = f"{panel_name}::{f['name']}"
                            if fid not in annotations:
                                annotations[fid] = {
                                    "panel": panel_name,
                                    "field_name": f["name"],
                                    "old": f["logic"],
                                    "new": f["logic"],
                                    "changed": False,
                                    "error": err[:400],
                                }
                    persist()
                continue
            with lock:
                filled = 0
                missing_logic = 0
                for f in panel["fields"]:
                    logic = (f.get("logic") or "").strip()
                    if not logic:
                        continue
                    fid = f"{panel_name}::{f['name']}"
                    if fid in annotations:
                        continue
                    r = results.get(f["name"])
                    if r is None:
                        # LLM skipped this field — mark as unchanged, flag missing
                        annotations[fid] = {
                            "panel": panel_name,
                            "field_name": f["name"],
                            "old": f["logic"],
                            "new": f["logic"],
                            "changed": False,
                            "error": "missing in LLM batch output",
                        }
                        missing_logic += 1
                        continue
                    annotations[fid] = {
                        "panel": panel_name,
                        "field_name": f["name"],
                        "old": f["logic"],
                        "new": r["annotated_logic"] or f["logic"],
                        "changed": bool(r["changed"]),
                    }
                    filled += 1
                persist()
            total_changed = sum(1 for fid, a in annotations.items() if a.get("panel") == panel_name and a.get("changed"))
            print(f"[OK] {panel_name}: +{filled} fields ({missing_logic} missing, {total_changed} changed in panel) in {dur:.1f}s")

    changed = sum(1 for v in annotations.values() if v.get("changed"))
    errored = sum(1 for v in annotations.values() if v.get("error"))
    print(f"\nDone. {len(annotations)} total entries, {changed} with cross-panel refs, {errored} errors.")


if __name__ == "__main__":
    main()
