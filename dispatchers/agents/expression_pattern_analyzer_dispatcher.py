#!/usr/bin/env python3
"""
Expression Pattern Analyzer Dispatcher

Reads the EXECUTE rule dump CSV, filters rules containing cf/ctfd/asdff/rffdd,
batches them into groups of 10, and iteratively calls a Claude agent to analyze
patterns and update a documentation file.

Usage:
    python3 dispatchers/agents/expression_pattern_analyzer_dispatcher.py \
        --csv rules/expression_rules_example/Form_FillRule_EXECUTE_DUMP.csv \
        --output documentations/expression_function_patterns.md \
        --batch-size 10 \
        --max-batches 50

    # Resume from a specific batch (e.g., after interruption)
    python3 dispatchers/agents/expression_pattern_analyzer_dispatcher.py \
        --csv rules/expression_rules_example/Form_FillRule_EXECUTE_DUMP.csv \
        --start-batch 25
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stream_utils import stream_and_print

PROJECT_ROOT = str(Path(__file__).parent.parent.parent)

# Patterns to filter rules that use the target functions
TARGET_FUNCTIONS = re.compile(r'\b(cf|ctfd|asdff|rffdd)\s*\(', re.IGNORECASE)


def parse_csv(csv_path: str) -> list:
    """Parse the CSV dump and return rows as dicts."""
    rows = []
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def filter_relevant_rules(rows: list) -> list:
    """Filter rules that contain cf, ctfd, asdff, or rffdd in conditional_values."""
    relevant = []
    for row in rows:
        cv = row.get('conditional_values', '')
        if TARGET_FUNCTIONS.search(cv):
            relevant.append({
                'id': row.get('id', ''),
                'conditional_values': cv,
                'condition': row.get('condition', ''),
                'condition_value_type': row.get('condition_value_type', ''),
                'source_ids': row.get('source_ids', ''),
                'form_fill_metadata_id': row.get('form_fill_metadata_id', ''),
                'execute_on_fill': row.get('execute_on_fill', ''),
                'execute_on_read': row.get('execute_on_read', ''),
                'run_post_condition_fail': row.get('run_post_condition_fail', ''),
            })
    return relevant


def deduplicate_rules(rules: list) -> list:
    """Remove exact duplicates based on conditional_values content."""
    seen = set()
    unique = []
    for rule in rules:
        cv = rule['conditional_values'].strip()
        if cv not in seen:
            seen.add(cv)
            unique.append(rule)
    return unique


def call_agent(batch: list, batch_num: int, total_batches: int,
               patterns_file: str, temp_dir: Path, model: str,
               verbose: bool = True) -> bool:
    """Call the Claude agent for a single batch."""
    batch_file = temp_dir / f"batch_{batch_num:04d}.json"
    log_file = temp_dir / f"batch_{batch_num:04d}_log.txt"

    with open(batch_file, 'w') as f:
        json.dump(batch, f, indent=2)

    prompt = f"""Analyze batch {batch_num} of {total_batches} expression rules.

## Input
- BATCH_JSON: {batch_file}
- PATTERNS_FILE: {patterns_file}
- BATCH_NUMBER: {batch_num}
- TOTAL_BATCHES: {total_batches}
- LOG_FILE: {log_file}

## Instructions
1. Read the current patterns file at {patterns_file}
2. Read the batch of rules at {batch_file}
3. Analyze how cf, ctfd, asdff, rffdd are used in each rule
4. Update {patterns_file} with any new patterns or enriched existing patterns
5. Follow the agent prompt instructions (helpers/expression_pattern_analyzer)
"""

    if verbose:
        print(f"\n{'='*70}")
        print(f"BATCH {batch_num}/{total_batches}  ({len(batch)} rules)")
        print(f"{'='*70}")

    try:
        stream_log = temp_dir / f"batch_{batch_num:04d}_stream.log"
        process = subprocess.Popen(
            ["claude", "--model", model, "-p", prompt,
             "--output-format", "stream-json", "--verbose",
             "--agent", "helpers/expression_pattern_analyzer",
             "--allowedTools", "Read,Write,Edit"],
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
            return False

        if verbose:
            print(f"  Batch {batch_num} complete")

        return True

    except FileNotFoundError:
        print("  Error: 'claude' command not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Unexpected error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Expression Pattern Analyzer — discovers patterns in EXECUTE rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--csv",
        default="rules/expression_rules_example/Form_FillRule_EXECUTE_DUMP.csv",
        help="Path to the CSV dump of EXECUTE rules",
    )
    parser.add_argument(
        "--output",
        default="documentations/expression_function_patterns.md",
        help="Path to the patterns documentation file (read and updated iteratively)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=10,
        help="Number of rules per batch (default: 10)",
    )
    parser.add_argument(
        "--max-batches", type=int, default=0,
        help="Max batches to process (0 = all, default: 0)",
    )
    parser.add_argument(
        "--start-batch", type=int, default=1,
        help="Start from this batch number (for resuming, default: 1)",
    )
    parser.add_argument(
        "--model", default="sonnet",
        help="Claude model to use (default: sonnet)",
    )
    parser.add_argument(
        "--no-dedup", action="store_true",
        help="Skip deduplication of rules (process all including duplicates)",
    )
    args = parser.parse_args()

    csv_path = Path(PROJECT_ROOT) / args.csv if not Path(args.csv).is_absolute() else Path(args.csv)
    patterns_file = Path(PROJECT_ROOT) / args.output if not Path(args.output).is_absolute() else Path(args.output)

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Ensure patterns file exists
    patterns_file.parent.mkdir(parents=True, exist_ok=True)
    if not patterns_file.exists():
        print(f"Error: Patterns file not found: {patterns_file}", file=sys.stderr)
        print("Run the script from the project root or create the seed file first.")
        sys.exit(1)

    temp_dir = patterns_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # ── Parse & filter ──
    print(f"Parsing CSV: {csv_path}")
    all_rows = parse_csv(str(csv_path))
    print(f"  Total rows in CSV: {len(all_rows)}")

    relevant = filter_relevant_rules(all_rows)
    print(f"  Rules with cf/ctfd/asdff/rffdd: {len(relevant)}")

    if not args.no_dedup:
        relevant = deduplicate_rules(relevant)
        print(f"  After deduplication: {len(relevant)}")

    if not relevant:
        print("No relevant rules found. Exiting.")
        sys.exit(0)

    # ── Batch ──
    batch_size = args.batch_size
    batches = [relevant[i:i+batch_size] for i in range(0, len(relevant), batch_size)]
    total_batches = len(batches)

    if args.max_batches > 0:
        batches = batches[:args.max_batches]
        print(f"  Limiting to {args.max_batches} batches (of {total_batches} total)")
        total_batches = min(total_batches, args.max_batches)

    start_idx = args.start_batch - 1
    if start_idx > 0:
        batches = batches[start_idx:]
        print(f"  Resuming from batch {args.start_batch}")

    print(f"\nProcessing {len(batches)} batches of ~{batch_size} rules each")
    print(f"Patterns file: {patterns_file}")
    print(f"Model: {args.model}")
    print()

    # ── Process batches sequentially ──
    succeeded = 0
    failed = 0

    for i, batch in enumerate(batches):
        batch_num = start_idx + i + 1

        ok = call_agent(
            batch=batch,
            batch_num=batch_num,
            total_batches=total_batches,
            patterns_file=str(patterns_file),
            temp_dir=temp_dir,
            model=args.model,
            verbose=True,
        )

        if ok:
            succeeded += 1
        else:
            failed += 1
            print(f"  Batch {batch_num} failed — continuing with next batch")

    # ── Summary ──
    print(f"\n{'='*70}")
    print("EXPRESSION PATTERN ANALYZER COMPLETE")
    print(f"{'='*70}")
    print(f"Total batches:  {len(batches)}")
    print(f"Succeeded:      {succeeded}")
    print(f"Failed:         {failed}")
    print(f"Patterns file:  {patterns_file}")
    print(f"{'='*70}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
