#!/usr/bin/env python3
"""
Form Validation Mini Agent Dispatcher

For each panel in the inter-panel output, call the Form Validation mini agent
to detect simple length/format validations from each field's `logic` text and
emit a `formValidations` array on every field.

Input:  output of inter-panel dispatcher (panel_name -> [field, ...])
Output: same shape, with `formValidations` added to every field.
"""

import argparse
import json
import subprocess
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from stream_utils import stream_and_print

PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


def call_form_validation_mini_agent(panel_fields: List[Dict],
                                     panel_name: str,
                                     temp_dir: Path,
                                     verbose: bool = True,
                                     model: str = "opus") -> Optional[List[Dict]]:
    """Call the Form Validation mini agent for a single panel."""
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    output_file = temp_dir / f"{safe_panel_name}_form_validation_output.json"
    log_file = temp_dir / f"{safe_panel_name}_form_validation_log.txt"

    with open(fields_input_file, 'w') as f:
        json.dump(panel_fields, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}".

## Input
- FIELDS_JSON: {fields_input_file}
- LOG_FILE: {log_file}

## Output
Write JSON array to: {output_file}

Follow the agent prompt (09_form_validation_agent) to add a `formValidations`
array to every field. Do NOT modify any other keys; existing `rules` must be
preserved verbatim.
"""

    try:
        if verbose:
            print(f"\n{'='*70}")
            print(f"PROCESSING PANEL: {panel_name}")
            print(f"  Fields: {len(panel_fields)}")
            print('='*70)

        stream_log = temp_dir / f"{safe_panel_name}_stream.log"
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--agent", "mini/09_form_validation_agent",
                "--allowedTools", "Read,Write",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=PROJECT_ROOT,
        )

        stream_and_print(process, verbose=verbose, log_file_path=stream_log)
        process.wait()

        if process.returncode != 0:
            print(f"✗ Form Validation mini agent failed (exit {process.returncode})", file=sys.stderr)
            return None

        if not output_file.exists():
            print(f"✗ Output file not found: {output_file}", file=sys.stderr)
            return None

        with open(output_file, 'r') as f:
            result = json.load(f)

        if verbose:
            print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
        return result

    except FileNotFoundError:
        print("✗ Error: 'claude' command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"✗ Error calling Form Validation mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Form Validation Dispatcher - add formValidations to each field"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to inter-panel dispatcher output JSON (panels with rules)",
    )
    parser.add_argument(
        "--output",
        default="output/form_validation/all_panels_form_validation.json",
        help="Output file (default: output/form_validation/all_panels_form_validation.json)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel panels (default: 4)",
    )
    parser.add_argument(
        "--model",
        default="opus",
        help="Claude model to use (default: opus)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"✗ Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with open(input_path, 'r') as f:
        input_data = json.load(f)

    print(f"Found {len(input_data)} panels in input")

    jobs = []
    skipped_panels = 0
    for panel_name, panel_fields in input_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue
        jobs.append((panel_name, panel_fields))

    successful_panels = 0
    failed_panels = 0
    all_results: Dict[str, List[Dict]] = {}

    if args.max_workers <= 1:
        for panel_name, panel_fields in jobs:
            result = call_form_validation_mini_agent(
                panel_fields, panel_name, temp_dir, verbose=True, model=args.model
            )
            if result:
                successful_panels += 1
                all_results[panel_name] = result
            else:
                failed_panels += 1
                all_results[panel_name] = panel_fields
                print(f"✗ Panel '{panel_name}' failed - using original", file=sys.stderr)
    else:
        print(f"\nProcessing {len(jobs)} panels in parallel (max_workers={args.max_workers})")
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_panel = {
                executor.submit(
                    call_form_validation_mini_agent,
                    panel_fields, panel_name, temp_dir, False, args.model,
                ): panel_name
                for panel_name, panel_fields in jobs
            }
            for future in as_completed(future_to_panel):
                panel_name = future_to_panel[future]
                try:
                    result = future.result()
                    if result:
                        successful_panels += 1
                        all_results[panel_name] = result
                        print(f"✓ Panel '{panel_name}' completed - {len(result)} fields")
                    else:
                        failed_panels += 1
                        # Fall back to original fields (with empty formValidations)
                        fallback = input_data[panel_name]
                        for field in fallback:
                            field.setdefault('formValidations', [])
                        all_results[panel_name] = fallback
                        print(f"✗ Panel '{panel_name}' failed - using original", file=sys.stderr)
                except Exception as e:
                    failed_panels += 1
                    fallback = input_data[panel_name]
                    for field in fallback:
                        field.setdefault('formValidations', [])
                    all_results[panel_name] = fallback
                    print(f"✗ Panel '{panel_name}' error: {e}", file=sys.stderr)

    # Preserve original panel order
    ordered = {p: all_results[p] for p in input_data if p in all_results}
    # Include any skipped (empty) panels too, to keep structure identical
    for p in input_data:
        if p not in ordered:
            ordered[p] = input_data[p]

    with open(output_file, 'w') as f:
        json.dump(ordered, f, indent=2)

    print("\n" + "="*70)
    print("FORM VALIDATION DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(input_data)}")
    print(f"Successful:   {successful_panels}")
    print(f"Failed:       {failed_panels}")
    print(f"Skipped:      {skipped_panels}")
    print(f"Output File:  {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
