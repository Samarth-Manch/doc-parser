#!/usr/bin/env python3
"""
Validate EDV Mini Agent Dispatcher

This script:
1. Reads BUD document using doc_parser to extract reference tables
2. Reads output from EDV Rule agent (panel-by-panel)
3. For each panel, filters reference tables mentioned in fields' logic
4. Calls Validate EDV mini agent to analyze dropdown fields and place Validate EDV rules
5. ALL panels are processed, regardless of whether they have dropdown fields
6. Outputs single JSON file containing all panels with Validate EDV rules placed and populated
"""

import argparse
import json
import subprocess
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
from stream_utils import stream_and_print

# Import doc_parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from doc_parser import DocumentParser
from context_optimization import (
    strip_rules_except, restore_all_rules, is_edv_related_rule, log_strip_savings,
)

PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


def query_context_usage(panel_name: str, agent_name: str) -> Optional[str]:
    """
    Query the last claude agent session for context/token usage.
    Uses --continue to resume the last conversation and ask for usage stats.

    Returns:
        Usage report string, or None if failed
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


def extract_reference_tables_from_parser(parsed_doc) -> List[Dict]:
    """
    Extract reference tables from parsed document and convert to EDV format.

    Args:
        parsed_doc: ParsedDocument from DocumentParser

    Returns:
        List of reference tables in agent format
    """
    reference_tables = []

    if hasattr(parsed_doc, 'reference_tables'):
        for i, table in enumerate(parsed_doc.reference_tables):
            # Build attributes/columns mapping
            attributes = {}
            if hasattr(table, 'headers') and table.headers:
                for idx, header in enumerate(table.headers, start=1):
                    attributes[f"a{idx}"] = header

            # Get sample data (limit to first 4 rows)
            sample_data = []
            if hasattr(table, 'rows') and table.rows:
                sample_data = table.rows[:4]

            # Determine source file and sheet name
            source_file = "unknown"
            sheet_name = "Sheet1"

            if hasattr(table, 'source_file') and table.source_file:
                source_file = table.source_file
            elif hasattr(table, 'title') and table.title:
                source_file = f"{table.title}.xlsx"

            if hasattr(table, 'sheet_name') and table.sheet_name:
                sheet_name = table.sheet_name

            # Build table data
            table_data = {
                "attributes/columns": attributes,
                "sample_data": sample_data,
                "source_file": source_file,
                "sheet_name": sheet_name,
                "table_type": "reference",
                "source": "excel"
            }

            # Add table ID if available
            if hasattr(table, 'title') and table.title:
                table_data["title"] = table.title
                match = re.search(r'(?:reference\s+)?table\s+(\d+\.?\d*)', table.title, re.I)
                if match:
                    table_data["reference_id"] = match.group(1)
                else:
                    table_data["reference_id"] = f"1.{i + 1}"
            else:
                table_data["reference_id"] = f"1.{i + 1}"

            reference_tables.append(table_data)

    return reference_tables


def detect_table_references_in_logic(logic: str) -> List[str]:
    """
    Detect reference table mentions in field logic.

    Args:
        logic: Field logic text

    Returns:
        List of table reference IDs found (e.g., ["1.3", "2.1"])
    """
    if not logic:
        return []

    references = []

    patterns = [
        r'reference\s+table\s+(\d+\.?\d*)',
        r'table\s+(\d+\.?\d*)',
        r'ref\.?\s*table\s+(\d+\.?\d*)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, logic, re.I)
        references.extend(matches)

    return list(set(references))


def get_referenced_tables_for_panel(panel_fields: List[Dict], all_reference_tables: List[Dict]) -> List[Dict]:
    """
    Filter reference tables to only those mentioned in the panel's fields' logic.

    Args:
        panel_fields: List of fields in the panel
        all_reference_tables: All available reference tables

    Returns:
        Filtered list of reference tables mentioned in this panel
    """
    referenced_ids = set()

    for field in panel_fields:
        logic = field.get('logic', '')
        if logic:
            table_refs = detect_table_references_in_logic(logic)
            referenced_ids.update(table_refs)

    if not referenced_ids:
        return []

    filtered_tables = []
    for table in all_reference_tables:
        table_id = table.get('reference_id', '')
        if table_id in referenced_ids:
            filtered_tables.append(table)

    return filtered_tables


DROPDOWN_TYPES = {
    "DROPDOWN", "EXTERNAL_DROP_DOWN_VALUE", "MULTI_DROPDOWN",
    "dropdown", "external_dropdown", "multi_dropdown",
}


def panel_has_dropdown_fields(panel_fields: List[Dict]) -> bool:
    """
    Check if any field in the panel is a dropdown type.
    Validate EDV rules are always placed on dropdown fields.

    Args:
        panel_fields: List of fields in the panel

    Returns:
        True if at least one field is a dropdown
    """
    for field in panel_fields:
        field_type = field.get('type', '')
        if field_type.upper() in {t.upper() for t in DROPDOWN_TYPES}:
            return True
    return False


def count_dropdown_fields(panel_fields: List[Dict]) -> int:
    """Count total dropdown fields in a panel."""
    count = 0
    for field in panel_fields:
        field_type = field.get('type', '')
        if field_type.upper() in {t.upper() for t in DROPDOWN_TYPES}:
            count += 1
    return count


def call_validate_edv_mini_agent(panel_fields: List[Dict], reference_tables: List[Dict],
                                  panel_name: str, temp_dir: Path,
                                  context_usage: bool = False,
                                  verbose: bool = True,
                                  model: str = "opus",
                                  all_panels_index_file: Optional[Path] = None) -> Optional[List[Dict]]:
    """
    Call the Validate EDV mini agent via claude -p

    Args:
        panel_fields: Fields from EDV agent output
        reference_tables: Filtered reference tables for this panel
        panel_name: Name of the panel
        temp_dir: Directory for temp files
        all_panels_index_file: Optional path to JSON file with all panels' field index
                               (for cross-panel source field resolution)

    Returns:
        List of fields with Validate EDV params/source/dest populated, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    tables_input_file = temp_dir / f"{safe_panel_name}_tables_input.json"
    output_file = temp_dir / f"{safe_panel_name}_validate_edv_output.json"
    log_file = temp_dir / f"{safe_panel_name}_validate_edv_log.txt"

    # Strip non-EDV rules to reduce context window usage
    stripped_fields, stored_rules = strip_rules_except(panel_fields, is_edv_related_rule)
    if verbose:
        log_strip_savings(panel_fields, stripped_fields, panel_name)

    # Write stripped fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(stripped_fields, f, indent=2)

    # Write reference tables to temp file
    with open(tables_input_file, 'w') as f:
        json.dump(reference_tables, f, indent=2)

    # Build prompt with optional cross-panel context
    cross_panel_section = ""
    if all_panels_index_file:
        cross_panel_section = f"""- ALL_PANELS_INDEX: {all_panels_index_file}

**CROSS-PANEL MODE**: This panel has fields whose logic references fields from OTHER panels.
When a field's logic says a value depends on a field from another panel (e.g., "dependent on Vendor Number from Vendor Details panel"),
use ALL_PANELS_INDEX to resolve that field's variableName and use it as the source_field in the Validate EDV rule.
Source fields from other panels ARE allowed in cross-panel mode — they do NOT need to exist in FIELDS_JSON.
"""

    prompt = f"""Process fields for panel "{panel_name}".

## Input
- FIELDS_JSON: {fields_input_file}
- REFERENCE_TABLES: {tables_input_file}
- LOG_FILE: {log_file}
{cross_panel_section}
## Output
Write JSON array to: {output_file}

Follow the agent prompt instructions to place and populate Validate EDV rules on dropdown fields.
"""

    try:
        if verbose:
            print(f"\n{'='*70}")
            print(f"PROCESSING PANEL: {panel_name}")
            print(f"  Fields: {len(panel_fields)}")
            print(f"  Dropdown Fields: {count_dropdown_fields(panel_fields)}")
            print(f"  Reference Tables: {len(reference_tables)}")
            print('='*70)

        # Call claude -p with the Validate EDV mini agent
        safe_name = re.sub(r'[^\w\-]', '_', panel_name)
        stream_log = temp_dir / f"{safe_name}_stream.log"
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--agent", "mini/04_validate_edv_agent_v2",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        # Stream and print real-time output
        output_lines = stream_and_print(process, verbose=verbose, log_file_path=stream_log)

        process.wait()

        if process.returncode != 0:
            print(f"  Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Query context usage from the agent session (opt-in)
        if context_usage:
            print(f"\n--- Context Usage ({panel_name}) ---")
            usage = query_context_usage(panel_name, "Validate EDV")
            if usage:
                print(usage)
            else:
                print("(Could not retrieve context usage)")
            print("---")

        # Read output file
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
                result = restore_all_rules(result, stored_rules)
                if verbose:
                    print(f"  Panel '{panel_name}' completed - {len(result)} fields processed")
                return result
            except json.JSONDecodeError as e:
                print(f"  Failed to parse output JSON: {e}", file=sys.stderr)
                return None
        else:
            print(f"  Output file not found: {output_file}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("  Error: 'claude' command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Error calling Validate EDV mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Validate EDV Dispatcher - Panel-by-panel Validate EDV params population"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to BUD document (.docx)"
    )
    parser.add_argument(
        "--edv-output",
        required=True,
        help="Path to EDV Rule agent output JSON (panels with EDV dropdown params)"
    )
    parser.add_argument(
        "--output",
        default="output/validate_edv/all_panels_validate_edv.json",
        help="Output file for all panels (default: output/validate_edv/all_panels_validate_edv.json)"
    )
    parser.add_argument(
        "--context-usage",
        action="store_true",
        default=False,
        help="Query and display context window usage after each panel (adds ~30s per panel)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel panels to process (default: 4, use 1 for sequential)"
    )
    parser.add_argument(
        "--model",
        default="opus",
        help="Claude model to use (default: opus)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.bud).exists():
        print(f"Error: BUD file not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.edv_output).exists():
        print(f"Error: EDV agent output file not found: {args.edv_output}", file=sys.stderr)
        sys.exit(1)

    # Create output directory and temp directory
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    temp_dir = output_file.parent / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse BUD document to extract reference tables
    print(f"Parsing BUD document: {args.bud}")
    parser_obj = DocumentParser()
    parsed_doc = parser_obj.parse(args.bud)

    # Step 2: Extract and convert reference tables
    print("Extracting reference tables...")
    all_reference_tables = extract_reference_tables_from_parser(parsed_doc)
    print(f"Found {len(all_reference_tables)} reference tables")

    if all_reference_tables:
        print("\nAvailable reference tables:")
        for table in all_reference_tables:
            ref_id = table.get('reference_id', 'unknown')
            title = table.get('title', 'No title')
            cols = len(table.get('attributes/columns', {}))
            print(f"  - {ref_id}: {title} ({cols} columns)")

    # Step 3: Load EDV agent output
    print(f"\nLoading EDV agent output: {args.edv_output}")
    with open(args.edv_output, 'r') as f:
        edv_data = json.load(f)

    print(f"Found {len(edv_data)} panels in input")

    # Build ALL_PANELS_INDEX so agent can resolve cross-panel source fields
    all_panels_index = {}
    for pname, pfields in edv_data.items():
        for field in pfields:
            if not isinstance(field, dict):
                continue
            var = field.get('variableName', '')
            fname = field.get('field_name', '')
            ftype = field.get('type', '')
            if var:
                all_panels_index[var] = {
                    "field_name": fname,
                    "panel": pname,
                    "type": ftype
                }

    all_panels_index_file = temp_dir / "all_panels_index.json"
    with open(all_panels_index_file, 'w') as f:
        json.dump(all_panels_index, f, indent=2)
    print(f"Built ALL_PANELS_INDEX: {len(all_panels_index)} fields across {len(edv_data)} panels")

    # Step 4: Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS WITH VALIDATE EDV AGENT")
    print("="*70)

    max_workers = args.max_workers

    # Prepare jobs
    jobs = []
    skipped_panels = 0
    for panel_name, panel_fields in edv_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue

        referenced_tables = get_referenced_tables_for_panel(panel_fields, all_reference_tables)
        dropdown_count = count_dropdown_fields(panel_fields)
        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {dropdown_count} dropdowns, {len(referenced_tables)} referenced tables")

        if referenced_tables:
            print("  Referenced tables:")
            for table in referenced_tables:
                ref_id = table.get('reference_id', 'unknown')
                cols = list(table.get('attributes/columns', {}).values())
                print(f"    - {ref_id}: columns={cols}")

        jobs.append((panel_name, panel_fields, referenced_tables))

    successful_panels = 0
    failed_panels = 0
    total_fields_processed = 0
    all_results = {}

    if max_workers <= 1:
        # Sequential processing
        for panel_name, panel_fields, referenced_tables in jobs:
            result = call_validate_edv_mini_agent(
                panel_fields, referenced_tables, panel_name, temp_dir,
                context_usage=args.context_usage, verbose=True, model=args.model,
                all_panels_index_file=all_panels_index_file
            )
            if result:
                successful_panels += 1
                total_fields_processed += len(result)
                all_results[panel_name] = result
            else:
                failed_panels += 1
                all_results[panel_name] = panel_fields
                total_fields_processed += len(panel_fields)
                print(f"  Panel '{panel_name}' failed - using original data", file=sys.stderr)
    else:
        # Parallel processing
        print(f"\nProcessing {len(jobs)} panels in parallel (max_workers={max_workers})")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_panel = {}
            for panel_name, panel_fields, referenced_tables in jobs:
                future = executor.submit(
                    call_validate_edv_mini_agent,
                    panel_fields, referenced_tables, panel_name, temp_dir,
                    context_usage=args.context_usage, verbose=False, model=args.model,
                    all_panels_index_file=all_panels_index_file
                )
                future_to_panel[future] = (panel_name, panel_fields)

            for future in as_completed(future_to_panel):
                panel_name, original_fields = future_to_panel[future]
                try:
                    result = future.result()
                    if result:
                        successful_panels += 1
                        total_fields_processed += len(result)
                        all_results[panel_name] = result
                        print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
                    else:
                        failed_panels += 1
                        all_results[panel_name] = original_fields
                        total_fields_processed += len(original_fields)
                        print(f"✗ Panel '{panel_name}' failed - using original data", file=sys.stderr)
                except Exception as e:
                    failed_panels += 1
                    all_results[panel_name] = original_fields
                    total_fields_processed += len(original_fields)
                    print(f"✗ Panel '{panel_name}' error: {e}", file=sys.stderr)

    # Reorder results to match original panel sequence
    ordered_results = {}
    for panel_name in edv_data:
        if panel_name in all_results:
            ordered_results[panel_name] = all_results[panel_name]
    all_results = ordered_results

    # Step 5: Write all results to single output file
    if all_results:
        print(f"\nWriting all results to: {output_file}")
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"Successfully wrote {len(all_results)} panels to output file")

    # Print final summary
    print("\n" + "="*70)
    print("VALIDATE EDV DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(edv_data)}")
    print(f"Successfully Processed: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Skipped (empty): {skipped_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Total Reference Tables: {len(all_reference_tables)}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
