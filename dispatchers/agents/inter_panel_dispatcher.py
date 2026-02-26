#!/usr/bin/env python3
"""
Inter-Panel Cross-Panel Rules Dispatcher (v2 — Two-Pass Architecture)

This script:
1. Quick scan: checks if any cross-panel references exist (early exit if none)
2. Pass 1: Global analysis — sends ALL panels in compact format to a single LLM call
   that creates direct rules (Copy To, visibility) and flags complex references
3. Pass 2: Complex rules — if complex refs exist, sends involved panels to a second
   LLM call that creates Expression (Client) rules (derivation, clearing, EDV)
4. Pass 3: Merge + validate — deterministic Python merges both passes into output,
   validates variableNames, deduplicates, tags _inter_panel_source
"""

import argparse
import json
import subprocess
import sys
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from context_optimization import strip_all_rules_multi_panel
from inter_panel_utils import (
    build_compact_panels_text,
    build_variablename_index,
    quick_cross_panel_scan,
    validate_inter_panel_rules,
    merge_all_rules_into_output,
    read_inter_panel_output,
    read_complex_refs,
    get_involved_panels,
)


PROJECT_ROOT = str(Path(__file__).parent.parent.parent)

# Master log file — set in main(), used by log() globally
_master_log: Optional[Path] = None


def log(msg: str, also_print: bool = True):
    """Log a timestamped message to master log file and optionally to stdout."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    if also_print:
        print(line, flush=True)
    if _master_log:
        with open(_master_log, 'a') as f:
            f.write(line + '\n')


def elapsed_str(start: float) -> str:
    """Return human-readable elapsed time string."""
    secs = time.time() - start
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs // 60)
    remaining = secs % 60
    return f"{mins}m {remaining:.1f}s"


def query_context_usage(pass_name: str) -> Optional[str]:
    """
    Query the last claude agent session for context/token usage.
    """
    usage_prompt = (
        "Report the context window usage for this conversation. "
        "Include: (1) number of input tokens used, "
        "(2) number of output tokens used, "
        "(3) total tokens used, and "
        "(4) percentage of the context window (200K tokens) that is filled. "
        "Format as a brief one-line summary."
    )

    try:
        process = subprocess.run(
            ["claude", "--continue", "-p", usage_prompt],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )

        if process.returncode == 0 and process.stdout.strip():
            return process.stdout.strip()
        return None
    except Exception:
        return None


def call_pass1_analysis_agent(compact_file: Path,
                               direct_rules_file: Path,
                               complex_refs_file: Path,
                               log_file: Path,
                               model: str = "opus") -> bool:
    """
    Call the Pass 1 global analysis agent via claude -p.

    Args:
        compact_file: Path to compact panels text file
        direct_rules_file: Path where agent writes direct rules JSON
        complex_refs_file: Path where agent writes complex refs JSON
        log_file: Path for agent log file
        model: Claude model to use

    Returns:
        True on success, False on failure
    """
    prompt = f"""Analyze all panels for cross-panel references.

## Input
- COMPACT_PANELS_FILE: {compact_file}
- DIRECT_RULES_FILE: {direct_rules_file}
- COMPLEX_REFS_FILE: {complex_refs_file}
- LOG_FILE: {log_file}

Follow the agent prompt instructions (09_inter_panel_analysis_agent).
If no direct rules, write empty dict {{}} to {direct_rules_file}.
If no complex refs, write empty list [] to {complex_refs_file}.
"""

    try:
        log("PASS 1: GLOBAL ANALYSIS — Starting")
        log(f"  Compact panels file: {compact_file}")
        log(f"  Direct rules output: {direct_rules_file}")
        log(f"  Complex refs output: {complex_refs_file}")
        log(f"  Agent log (tail -f): {log_file}")

        t0 = time.time()

        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--agent", "mini/09_inter_panel_analysis_agent",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        for line in process.stdout:
            print(line, end='', flush=True)

        process.wait()

        if process.returncode != 0:
            log(f"Pass 1 FAILED (exit code {process.returncode}) after {elapsed_str(t0)}")
            return False

        log(f"Pass 1 COMPLETE — took {elapsed_str(t0)}")
        return True

    except FileNotFoundError:
        print("  Error: 'claude' command not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Error calling Pass 1 agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def call_pass2_complex_agent(complex_refs_file: Path,
                              involved_panels_file: Path,
                              complex_rules_file: Path,
                              log_file: Path,
                              model: str = "opus") -> bool:
    """
    Call the Pass 2 complex rules agent via claude -p.

    Args:
        complex_refs_file: Path to complex refs JSON from Pass 1
        involved_panels_file: Path to involved panels full JSON
        complex_rules_file: Path where agent writes complex rules JSON
        log_file: Path for agent log file
        model: Claude model to use

    Returns:
        True on success, False on failure
    """
    prompt = f"""Process complex cross-panel references flagged by Pass 1.

## Input
- COMPLEX_REFS_FILE: {complex_refs_file}
- FIELDS_JSON: {involved_panels_file}
  This is a JSON object where each key is a panel name and each value is the
  array of fields for that panel. These are the involved panels with full field data.
- COMPLEX_RULES_FILE: {complex_rules_file}
- LOG_FILE: {log_file}

Use the expression_rule_agent instructions to build Expression (Client) rules
for cross-panel derivation, clearing, and EDV references.
The complex refs describe what needs to be done; the involved panels provide
the field context. Write the output rules to COMPLEX_RULES_FILE.
If no rules could be created, write empty dict {{}} to {complex_rules_file}.
"""

    try:
        log("PASS 2: COMPLEX RULES — Starting (using expression_rule_agent)")
        log(f"  Complex refs input: {complex_refs_file}")
        log(f"  Involved panels: {involved_panels_file}")
        log(f"  Complex rules output: {complex_rules_file}")
        log(f"  Agent log (tail -f): {log_file}")

        t0 = time.time()

        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--agent", "mini/expression_rule_agent",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT
        )

        for line in process.stdout:
            print(line, end='', flush=True)

        process.wait()

        if process.returncode != 0:
            log(f"Pass 2 FAILED (exit code {process.returncode}) after {elapsed_str(t0)}")
            return False

        log(f"Pass 2 COMPLETE — took {elapsed_str(t0)}")
        return True

    except FileNotFoundError:
        print("  Error: 'claude' command not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Error calling Pass 2 agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Inter-Panel Cross-Panel Rules Dispatcher (v2) — Two-Pass Architecture"
    )
    parser.add_argument(
        "--clear-child-output",
        required=True,
        help="Path to input JSON from previous stage (e.g., expression rules output)"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "--output",
        default="output/inter_panel/all_panels_inter_panel.json",
        help="Output file (default: output/inter_panel/all_panels_inter_panel.json)"
    )
    parser.add_argument(
        "--context-usage",
        action="store_true",
        default=False,
        help="Query and display context window usage after each pass (adds ~30s per pass)"
    )
    parser.add_argument(
        "--model",
        default="opus",
        help="Claude model to use (default: opus)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.clear_child_output).exists():
        print(f"Error: Clear Child Fields output not found: {args.clear_child_output}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.bud).exists():
        print(f"Error: BUD document not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Set up master log file
    global _master_log
    _master_log = temp_dir / "inter_panel_master.log"
    # Clear previous log
    with open(_master_log, 'w') as f:
        f.write(f"=== Inter-Panel Dispatcher v2 — {datetime.now().isoformat()} ===\n")

    pipeline_start = time.time()
    log("=" * 60, also_print=False)
    log("INTER-PANEL DISPATCHER v2 STARTED")
    log(f"Master log: {_master_log}")
    print(f"  Monitor progress:  tail -f {_master_log}")

    # Load input data
    log(f"Loading input: {args.clear_child_output}")
    with open(args.clear_child_output, 'r') as f:
        input_data = json.load(f)

    all_panel_names = list(input_data.keys())
    input_field_count = sum(len(fields) for fields in input_data.values())
    log(f"Found {len(input_data)} panels: {', '.join(all_panel_names)}")
    log(f"Total fields: {input_field_count}")

    # ══════════════════════════════════════════════════════════════════════
    # QUICK SCAN: Check if any cross-panel references exist
    # ══════════════════════════════════════════════════════════════════════
    log("Quick cross-panel scan...")
    t0 = time.time()
    has_cross_panel = quick_cross_panel_scan(input_data)
    log(f"Quick scan done in {elapsed_str(t0)} — result: {'refs found' if has_cross_panel else 'no refs'}")

    if not has_cross_panel:
        log("No cross-panel references detected — copying input to output (early exit)")
        with open(output_file, 'w') as f:
            json.dump(input_data, f, indent=2)
        log(f"Output: {output_file} ({input_field_count} fields, unchanged)")
        sys.exit(0)

    log("Cross-panel references detected — proceeding with two-pass analysis")

    # Build variableName index for validation
    var_index = build_variablename_index(input_data)
    log(f"Built variableName index: {len(var_index)} fields across {len(input_data)} panels")

    # ══════════════════════════════════════════════════════════════════════
    # PASS 1: Global Analysis (1 LLM call)
    # ══════════════════════════════════════════════════════════════════════
    compact_text = build_compact_panels_text(input_data)
    compact_file = temp_dir / "compact_panels.txt"
    with open(compact_file, 'w') as f:
        f.write(compact_text)
    log(f"Compact panels text written: {compact_file} ({len(compact_text)} chars)")

    direct_rules_file = temp_dir / "direct_rules.json"
    complex_refs_file = temp_dir / "complex_refs.json"
    pass1_log_file = temp_dir / "pass1_log.txt"
    # Initialize agent log file
    with open(pass1_log_file, 'w') as f:
        f.write(f"=== Pass 1 Agent Log — {datetime.now().isoformat()} ===\n")
    log(f"Pass 1 agent log (tail -f): {pass1_log_file}")

    pass1_success = call_pass1_analysis_agent(
        compact_file, direct_rules_file, complex_refs_file, pass1_log_file,
        model=args.model
    )

    if args.context_usage:
        print(f"\n--- Context Usage (Pass 1) ---")
        usage = query_context_usage("Pass 1")
        if usage:
            print(usage)
        else:
            print("(Could not retrieve context usage)")
        print("---")

    # Read Pass 1 outputs
    pass1_direct_rules = None
    pass1_complex_refs = None
    pass1_direct_count = 0
    pass1_complex_count = 0

    if pass1_success:
        pass1_direct_rules = read_inter_panel_output(direct_rules_file)
        pass1_complex_refs = read_complex_refs(complex_refs_file)

        if pass1_direct_rules:
            pass1_direct_count = sum(
                sum(len(e.get('rules_to_add', [])) for e in entries)
                for entries in pass1_direct_rules.values()
            )
            log(f"Pass 1 direct rules: {pass1_direct_count} rules for "
                f"{len(pass1_direct_rules)} panels")
        else:
            pass1_direct_rules = {}
            log("Pass 1: No direct rules produced")

        if pass1_complex_refs:
            pass1_complex_count = len(pass1_complex_refs)
            log(f"Pass 1 complex refs: {pass1_complex_count} references flagged for Pass 2")
            for i, ref in enumerate(pass1_complex_refs, 1):
                log(f"  Complex ref {i}: type={ref.get('type','?')} "
                    f"{ref.get('source_panel','?')}.{ref.get('source_field','?')} -> "
                    f"{ref.get('target_panel','?')}.{ref.get('target_field','?')}")
        else:
            pass1_complex_refs = []
            log("Pass 1: No complex references flagged")
    else:
        log("Pass 1 FAILED — will output unchanged input")
        pass1_direct_rules = {}
        pass1_complex_refs = []

    # ══════════════════════════════════════════════════════════════════════
    # PASS 2: Complex Rules (0 or 1 LLM call)
    # ══════════════════════════════════════════════════════════════════════
    pass2_rules = {}
    pass2_count = 0

    if pass1_complex_refs:
        # Extract involved panels (full field data)
        involved = get_involved_panels(pass1_complex_refs, input_data)
        involved_panels_file = temp_dir / "involved_panels.json"
        # Strip all rules from involved panels to reduce context window usage
        involved_stripped = strip_all_rules_multi_panel(involved)
        with open(involved_panels_file, 'w') as f:
            json.dump(involved_stripped, f, indent=2)
        log(f"Involved panels for Pass 2: {', '.join(involved.keys())} "
            f"({sum(len(fs) for fs in involved.values())} fields)")

        complex_rules_file = temp_dir / "complex_rules.json"
        pass2_log_file = temp_dir / "pass2_log.txt"
        # Initialize agent log file
        with open(pass2_log_file, 'w') as f:
            f.write(f"=== Pass 2 Agent Log — {datetime.now().isoformat()} ===\n")
        log(f"Pass 2 agent log (tail -f): {pass2_log_file}")

        pass2_success = call_pass2_complex_agent(
            complex_refs_file, involved_panels_file, complex_rules_file, pass2_log_file,
            model=args.model
        )

        if args.context_usage:
            print(f"\n--- Context Usage (Pass 2) ---")
            usage = query_context_usage("Pass 2")
            if usage:
                print(usage)
            else:
                print("(Could not retrieve context usage)")
            print("---")

        if pass2_success:
            pass2_rules = read_inter_panel_output(complex_rules_file)
            if pass2_rules:
                pass2_count = sum(
                    sum(len(e.get('rules_to_add', [])) for e in entries)
                    for entries in pass2_rules.values()
                )
                log(f"Pass 2 complex rules: {pass2_count} rules for "
                    f"{len(pass2_rules)} panels")
            else:
                pass2_rules = {}
                log("Pass 2: No complex rules produced")
        else:
            log("Pass 2 FAILED — complex rules will be skipped")
            pass2_rules = {}
    else:
        log("Pass 2 skipped — no complex references to process")

    # ══════════════════════════════════════════════════════════════════════
    # PASS 3: Merge + Validate (deterministic Python)
    # ══════════════════════════════════════════════════════════════════════
    log("PASS 3: MERGE + VALIDATE — Starting")
    t0 = time.time()

    # Validate rules before merging
    if pass1_direct_rules:
        pass1_direct_rules, stripped1 = validate_inter_panel_rules(pass1_direct_rules, var_index)
        if stripped1 > 0:
            log(f"  Pass 1 validation: stripped {stripped1} invalid rules/entries")
        else:
            log(f"  Pass 1 validation: all rules valid")

    if pass2_rules:
        pass2_rules, stripped2 = validate_inter_panel_rules(pass2_rules, var_index)
        if stripped2 > 0:
            log(f"  Pass 2 validation: stripped {stripped2} invalid rules/entries")
        else:
            log(f"  Pass 2 validation: all rules valid")

    # Merge all rules into output
    log("Merging rules into output...")
    all_results = merge_all_rules_into_output(input_data, pass1_direct_rules, pass2_rules)

    # Verify field counts
    output_field_count = sum(len(fields) for fields in all_results.values())

    # Count new cross-panel rules
    cross_panel_rule_count = 0
    for panel_fields in all_results.values():
        for field in panel_fields:
            for rule in field.get('rules', []):
                if isinstance(rule, dict) and rule.get('_inter_panel_source') == 'cross-panel':
                    cross_panel_rule_count += 1

    log(f"Pass 3 COMPLETE — took {elapsed_str(t0)}")

    # ══════════════════════════════════════════════════════════════════════
    # Write output
    # ══════════════════════════════════════════════════════════════════════
    log(f"Writing output to: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    total_time = elapsed_str(pipeline_start)

    # Summary
    summary = f"""
{'='*60}
INTER-PANEL DISPATCHER (v2) COMPLETE — Total: {total_time}
{'='*60}
Total Panels: {len(input_data)}
Pass 1 — Global Analysis:
  Direct rules created: {pass1_direct_count}
  Complex refs flagged: {pass1_complex_count}
{'Pass 2 — Complex Rules:' if pass1_complex_count > 0 else 'Pass 2 — Skipped (no complex refs)'}"""
    if pass1_complex_count > 0:
        summary += f"\n  Complex rules created: {pass2_count}"
    summary += f"""
Pass 3 — Merge + Validate:
  Cross-panel rules added: {cross_panel_rule_count}
Field Counts:
  Input: {input_field_count}
  Output: {output_field_count}
  {'WARNING: Field count mismatch!' if input_field_count != output_field_count else 'OK: Field counts match'}
Output File: {output_file}
Master Log: {_master_log}
{'='*60}"""

    log(summary)

    sys.exit(0)


if __name__ == "__main__":
    main()
