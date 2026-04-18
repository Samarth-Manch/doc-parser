#!/usr/bin/env python3
"""
Expression Rule Dispatcher

Two modes:
  1. No --panels arg  → each panel is processed separately, one agent call per panel
                        (runs in parallel by default)
  2. --panels 0,2,4   → panels at those indices are sent together in ONE agent call
                        (all in a single shared context, output for all returned at once)
"""

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from stream_utils import stream_and_print

from context_optimization import strip_all_rules, merge_expression_rules, log_strip_savings, normalize_variable_names

PROJECT_ROOT = str(Path(__file__).parent.parent.parent)

_CONTEXT_USAGE_PROMPT = (
    "Give a rough estimate of the context window usage for this conversation. "
    "Estimate: total tokens used and what percentage of the 200K window that is. "
    "One line only."
)


def _query_context_usage(label: str) -> None:
    """Ask the last claude session to self-report its context usage via --continue."""
    print(f"\n{'─'*56}")
    print(f"  CONTEXT REPORT  [{label}]")
    print(f"  Prompt sent to Claude:")
    print(f"  > {_CONTEXT_USAGE_PROMPT}")
    print(f"{'─'*56}")
    try:
        process = subprocess.run(
            ["claude", "--continue", "-p", _CONTEXT_USAGE_PROMPT],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        if process.returncode == 0 and process.stdout.strip():
            for line in process.stdout.strip().splitlines():
                print(f"  {line}")
        else:
            print("  (no response)")
    except Exception as e:
        print(f"  (error querying usage: {e})")
    print(f"{'─'*56}\n")


# ── Single-panel agent call ────────────────────────────────────────────────

def call_agent_single(
    panel_fields: List[Dict],
    panel_name: str,
    temp_dir: Path,
    verbose: bool = True,
    model: str = "opus",
) -> Optional[List[Dict]]:
    safe = re.sub(r'[^\w\-]', '_', panel_name)
    input_file  = temp_dir / f"{safe}_expr_input.json"
    output_file = temp_dir / f"{safe}_expr_output.json"
    log_file    = temp_dir / f"{safe}_expr_log.txt"

    # Strip rules for context savings — agent only needs field logic
    fields_to_send, _ = strip_all_rules(panel_fields)
    if verbose:
        log_strip_savings(panel_fields, fields_to_send, panel_name)

    with open(input_file, 'w') as f:
        json.dump(fields_to_send, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input
- FIELDS_JSON: {input_file}   (JSON array of fields)
- LOG_FILE: {log_file}

## Output
Write the resulting JSON array to: {output_file}

Follow the agent prompt instructions (expression_rule_agent).
"""

    agent_output = _run_agent(prompt, output_file, panel_name, verbose, model, multi=False)
    if agent_output is not None:
        # Defensive: collapse any '__name__' drift back to '_name_' canonical form
        agent_output = normalize_variable_names(agent_output)
        # Merge: start from original fields (all existing rules intact),
        # replace only expression/visibility/session rules with agent's output
        result = merge_expression_rules(panel_fields, agent_output)
    else:
        result = None
    if verbose:
        _query_context_usage(panel_name)
    return result


# ── Multi-panel agent call (all panels together in one context) ────────────

def call_agent_multi(
    panels: Dict[str, List[Dict]],
    temp_dir: Path,
    verbose: bool = True,
    model: str = "opus",
) -> Optional[Dict[str, List[Dict]]]:
    label = "_".join(re.sub(r'[^\w\-]', '_', n)[:12] for n in panels)[:60]
    input_file  = temp_dir / f"multi_{label}_input.json"
    output_file = temp_dir / f"multi_{label}_output.json"
    log_file    = temp_dir / f"multi_{label}_log.txt"

    # Strip rules for context savings — agent only needs field logic
    panels_to_send = {}
    for pname, pfields in panels.items():
        stripped, _ = strip_all_rules(pfields)
        panels_to_send[pname] = stripped
        if verbose:
            log_strip_savings(pfields, stripped, pname)

    with open(input_file, 'w') as f:
        json.dump(panels_to_send, f, indent=2)

    names = ", ".join(f'"{n}"' for n in panels)

    prompt = f"""Process the following panels together: {names}.

## Input
- PANELS_JSON: {input_file}
  This is a JSON object where each key is a panel name and each value is the
  array of fields for that panel.
- LOG_FILE: {log_file}

## Output
Write a JSON object with the same keys (panel names) to: {output_file}
Each value must be the processed fields array for that panel.

Apply expression_rule_agent logic to EVERY panel in the input.
Panels share this context — use that awareness when building expressions.
"""

    agent_output = _run_agent(prompt, output_file, f"[{names}]", verbose, model, multi=True)
    if agent_output is not None:
        # Merge: start from original fields, replace only expression rules
        result = {}
        for pname, agent_fields in agent_output.items():
            # Defensive: collapse any '__name__' drift back to '_name_'
            agent_fields = normalize_variable_names(agent_fields)
            if pname in panels:
                result[pname] = merge_expression_rules(panels[pname], agent_fields)
            else:
                result[pname] = agent_fields
    else:
        result = None
    if verbose:
        _query_context_usage(", ".join(panels))
    return result


# ── Shared subprocess runner ───────────────────────────────────────────────

def _run_agent(prompt, output_file, label, verbose, model, multi):
    try:
        if verbose:
            print(f"\n{'='*70}")
            print(f"PROCESSING: {label}")
            print('='*70)

        stream_log = output_file.parent / f"{output_file.stem}_stream.log"
        process = subprocess.Popen(
            ["claude", "--model", model, "--effort", "max", "-p", prompt,
             "--output-format", "stream-json", "--verbose",
             "--agent", "mini/expression_rule_agent",
             "--allowedTools", "Read,Write"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT,
        )

        stream_and_print(process, verbose=verbose, log_file_path=stream_log)

        process.wait()

        if process.returncode != 0:
            print(f"  Agent failed (exit {process.returncode})", file=sys.stderr)
            return None

        if not output_file.exists():
            print(f"  Output file missing: {output_file}", file=sys.stderr)
            return None

        try:
            with open(output_file, 'r') as f:
                result = json.load(f)
            if verbose:
                if multi:
                    print(f"  Done — {len(result)} panels")
                else:
                    print(f"  Done — {len(result)} fields")
            return result
        except json.JSONDecodeError as e:
            print(f"  Bad JSON in output: {e}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("  Error: 'claude' command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Unexpected error: {e}", file=sys.stderr)
        return None


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Expression Rule Dispatcher.\n"
            "  No --panels  → each panel processed separately (parallel by default).\n"
            "  --panels 0,2 → panels at those indices go together in ONE agent call."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", required=True,
                        help="Input JSON file (panel name → fields array)")
    parser.add_argument("--output",
                        default="output/expression_rules/all_panels_expression.json",
                        help="Output file path")
    parser.add_argument("--panels",
                        default=None,
                        help="Comma-separated panel indices to process together in one call "
                             "(e.g. --panels 0,2,4). Omit to process all panels one by one.")
    parser.add_argument("--max-workers", type=int, default=4,
                        help="Parallel workers for one-by-one mode (default: 4)")
    parser.add_argument("--model", default="opus",
                        help="Claude model (default: opus)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with open(input_path, 'r') as f:
        input_data: Dict[str, List] = json.load(f)

    panel_names = list(input_data.keys())

    print(f"Loaded {len(panel_names)} panels from {input_path}")
    for i, name in enumerate(panel_names):
        print(f"  [{i}] {name}  ({len(input_data[name])} fields)")

    # ── Mode 1: specific panels → one combined agent call ─────────────────
    if args.panels is not None:
        try:
            indices = [int(x.strip()) for x in args.panels.split(',')]
        except ValueError:
            print("Error: --panels must be comma-separated integers (e.g. 0,2,4)", file=sys.stderr)
            sys.exit(1)

        for idx in indices:
            if idx < 0 or idx >= len(panel_names):
                print(f"Error: index {idx} out of range (0–{len(panel_names)-1})", file=sys.stderr)
                sys.exit(1)

        selected = {panel_names[i]: input_data[panel_names[i]] for i in indices}
        print(f"\nSending {len(selected)} panels together in one agent call: "
              f"{', '.join(selected)}")

        result = call_agent_multi(selected, temp_dir, verbose=True, model=args.model)

        if result is None:
            print("Combined agent call failed.", file=sys.stderr)
            sys.exit(1)

        # Merge into full output (unprocessed panels pass through unchanged)
        all_results = dict(input_data)          # start with all original panels
        for name, fields in result.items():
            all_results[name] = fields          # overwrite processed panels

        # Preserve original panel order
        ordered = {p: all_results[p] for p in panel_names}

        with open(output_file, 'w') as f:
            json.dump(ordered, f, indent=2)

        print(f"\nOutput written to: {output_file}")
        print(f"Panels processed:  {list(result.keys())}")
        sys.exit(0)

    # ── Mode 2: no selection → one-by-one (parallel) ──────────────────────
    jobs = [(name, input_data[name]) for name in panel_names if input_data[name]]
    skipped = len(panel_names) - len(jobs)

    all_results: Dict[str, List] = {}
    succeeded = failed = 0

    if args.max_workers <= 1:
        for panel_name, panel_fields in jobs:
            result = call_agent_single(panel_fields, panel_name, temp_dir,
                                       verbose=True, model=args.model)
            if result:
                succeeded += 1
                all_results[panel_name] = result
            else:
                failed += 1
                all_results[panel_name] = panel_fields
                print(f"  '{panel_name}' failed — using original", file=sys.stderr)
    else:
        print(f"\nProcessing {len(jobs)} panels in parallel (max_workers={args.max_workers})")
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_map = {
                executor.submit(call_agent_single, pf, pn, temp_dir, False, args.model): (pn, pf)
                for pn, pf in jobs
            }
            for future in as_completed(future_map):
                panel_name, original = future_map[future]
                try:
                    result = future.result()
                    if result:
                        succeeded += 1
                        all_results[panel_name] = result
                        print(f"✓ '{panel_name}' — {len(result)} fields")
                    else:
                        failed += 1
                        all_results[panel_name] = original
                        print(f"✗ '{panel_name}' failed", file=sys.stderr)
                    _query_context_usage(panel_name)
                except Exception as e:
                    failed += 1
                    all_results[panel_name] = original
                    print(f"✗ '{panel_name}' error: {e}", file=sys.stderr)

    # Add skipped empty panels back
    for name in panel_names:
        if name not in all_results:
            all_results[name] = input_data[name]

    ordered = {p: all_results[p] for p in panel_names}
    with open(output_file, 'w') as f:
        json.dump(ordered, f, indent=2)

    print("\n" + "="*70)
    print("EXPRESSION RULE DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total panels:  {len(panel_names)}")
    print(f"Succeeded:     {succeeded}")
    print(f"Failed:        {failed}")
    print(f"Skipped:       {skipped}")
    print(f"Output:        {output_file}")
    print("="*70)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
