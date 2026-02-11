#!/usr/bin/env python3
"""
Validate EDV Mini Agent Dispatcher

This script:
1. Reads BUD document using doc_parser to extract reference tables
2. Reads output from EDV Rule agent (panel-by-panel)
3. For each panel, checks if any fields have Validate EDV rules
4. Filters reference tables mentioned in fields' logic
5. Calls Validate EDV mini agent with panel fields and filtered reference tables
6. Panels with no Validate EDV rules are passed through unchanged
7. Outputs single JSON file containing all panels with Validate EDV params populated
"""

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

# Import doc_parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from doc_parser import DocumentParser


VALIDATE_EDV_RULE_NAMES = {
    "Validate EDV (Server)",
    "Validate External Data Value (Client)",
}


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


def panel_has_validate_edv_rules(panel_fields: List[Dict]) -> bool:
    """
    Check if any field in the panel has a Validate EDV rule.

    Args:
        panel_fields: List of fields in the panel

    Returns:
        True if at least one field has a Validate EDV rule
    """
    for field in panel_fields:
        rules = field.get('rules', [])
        for rule in rules:
            rule_name = rule.get('rule_name', '') if isinstance(rule, dict) else str(rule)
            if rule_name in VALIDATE_EDV_RULE_NAMES:
                return True
    return False


def count_validate_edv_rules(panel_fields: List[Dict]) -> int:
    """Count total Validate EDV rules across all fields in a panel."""
    count = 0
    for field in panel_fields:
        rules = field.get('rules', [])
        for rule in rules:
            rule_name = rule.get('rule_name', '') if isinstance(rule, dict) else str(rule)
            if rule_name in VALIDATE_EDV_RULE_NAMES:
                count += 1
    return count


def call_validate_edv_mini_agent(panel_fields: List[Dict], reference_tables: List[Dict],
                                  panel_name: str, temp_dir: Path) -> Optional[List[Dict]]:
    """
    Call the Validate EDV mini agent via claude -p

    Args:
        panel_fields: Fields from EDV agent output
        reference_tables: Filtered reference tables for this panel
        panel_name: Name of the panel
        temp_dir: Directory for temp files

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

    # Write fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(panel_fields, f, indent=2)

    # Write reference tables to temp file
    with open(tables_input_file, 'w') as f:
        json.dump(reference_tables, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}" and populate Validate EDV rule parameters, source fields, and destination fields.

## Input Data
1. Fields with rules: {fields_input_file}
2. Reference tables: {tables_input_file}
3. Log file: {log_file}

## Task
For each field in the input:
1. Read the field's logic text and examine its rules
2. For Validate EDV rules ("Validate EDV (Server)" or "Validate External Data Value (Client)"):
   a. Determine the EDV table name from logic and reference tables
   b. Populate source_fields (the field being validated + any filter fields)
   c. Populate destination_fields positionally matching table columns:
      - Use field variableNames for columns that map to form fields
      - Use "-1" for columns that should be skipped
   d. Build params:
      - Simple string (table name) for single-source lookups
      - JSON object with "param" and "conditionList" for filtered lookups
3. For non-Validate-EDV rules, leave them completely unchanged

## Key Rules
- destination_fields array is POSITIONAL — each index corresponds to a table column (a1, a2, a3, ...)
- Use "-1" for any column position that doesn't map to a form field
- All destination fields must exist in the input field list
- Simple params: just the table name string, e.g. "COMPANY_CODE"
- Filtered params: {{"param": "TABLE_NAME", "conditionList": [...]}}
- DO NOT modify any non-Validate-EDV rules

## Output
Write a JSON array to: {output_file}

The output should have the same structure as input, but with Validate EDV rules having populated params, source_fields, and destination_fields:

```json
[
  {{
    "field_name": "Field Name",
    "type": "TEXT",
    "mandatory": true,
    "logic": "...",
    "rules": [
      {{
        "id": 1,
        "rule_name": "Validate EDV (Server)",
        "source_fields": ["__pin_code__"],
        "destination_fields": ["__city__", "__district__", "__state__", "__country__"],
        "params": "PIN-CODE",
        "_reasoning": "Explanation of table mapping and column-to-field correspondence"
      }},
      {{
        "id": 2,
        "rule_name": "Some Other Rule",
        "source_fields": ["__field1__"],
        "destination_fields": ["__field2__"],
        "_reasoning": "Unchanged from input"
      }}
    ],
    "variableName": "__pin_code__"
  }}
]
```

IMPORTANT:
- Only modify Validate EDV rules — all other rules must be passed through unchanged
- Keep all existing fields and attributes from input
- Log each step to the log file
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name}")
        print(f"  Fields: {len(panel_fields)}")
        print(f"  Reference Tables: {len(reference_tables)}")
        print(f"  Validate EDV Rules: {count_validate_edv_rules(panel_fields)}")
        print('='*70)

        # Call claude -p with the Validate EDV mini agent
        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--agent", "mini/04_validate_edv_agent_v2",
                "--allowedTools", "Read,Write"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        # Collect output
        output_lines = []
        for line in process.stdout:
            print(line, end='', flush=True)
            output_lines.append(line)

        process.wait()

        if process.returncode != 0:
            print(f"  Mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Read output file
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
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

    # Step 4: Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS WITH VALIDATE EDV AGENT")
    print("="*70)

    successful_panels = 0
    failed_panels = 0
    skipped_panels = 0
    passthrough_panels = 0
    total_fields_processed = 0
    all_results = {}

    for panel_name, panel_fields in edv_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue

        # Check if this panel has any Validate EDV rules
        if not panel_has_validate_edv_rules(panel_fields):
            print(f"\nPanel '{panel_name}': no Validate EDV rules - passing through unchanged")
            all_results[panel_name] = panel_fields
            passthrough_panels += 1
            total_fields_processed += len(panel_fields)
            continue

        # Filter reference tables for this panel
        referenced_tables = get_referenced_tables_for_panel(panel_fields, all_reference_tables)

        validate_edv_count = count_validate_edv_rules(panel_fields)
        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {validate_edv_count} Validate EDV rules, {len(referenced_tables)} referenced tables")

        if referenced_tables:
            print("  Referenced tables:")
            for table in referenced_tables:
                ref_id = table.get('reference_id', 'unknown')
                cols = list(table.get('attributes/columns', {}).values())
                print(f"    - {ref_id}: columns={cols}")

        # Call Validate EDV mini agent
        result = call_validate_edv_mini_agent(
            panel_fields,
            referenced_tables,
            panel_name,
            temp_dir
        )

        if result:
            successful_panels += 1
            total_fields_processed += len(result)
            all_results[panel_name] = result
        else:
            failed_panels += 1
            # On failure, pass through original data
            all_results[panel_name] = panel_fields
            total_fields_processed += len(panel_fields)
            print(f"  Panel '{panel_name}' failed - using original data", file=sys.stderr)

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
    print(f"Processed (with Validate EDV): {successful_panels}")
    print(f"Passed Through (no Validate EDV): {passthrough_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Skipped (empty): {skipped_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Total Reference Tables: {len(all_reference_tables)}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
