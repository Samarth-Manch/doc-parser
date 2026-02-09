#!/usr/bin/env python3
"""
EDV Rule Mini Agent Dispatcher

This script:
1. Reads BUD document using doc_parser to extract reference tables
2. Reads output from source_destination_agent (panel-by-panel)
3. For each panel, filters only reference tables mentioned in fields' logic
4. Converts reference tables to EDV agent's expected format
5. Calls mini agent with panel fields and filtered reference tables
6. Outputs single JSON file containing all panels with EDV params populated
"""

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict

# Import doc_parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from doc_parser import DocumentParser


def extract_reference_tables_from_parser(parsed_doc) -> List[Dict]:
    """
    Extract reference tables from parsed document and convert to EDV format.

    Args:
        parsed_doc: ParsedDocument from DocumentParser

    Returns:
        List of reference tables in EDV agent format
    """
    reference_tables = []

    if hasattr(parsed_doc, 'reference_tables'):
        for i, table in enumerate(parsed_doc.reference_tables):
            # Build attributes/columns mapping
            attributes = {}
            if hasattr(table, 'headers') and table.headers:
                for idx, header in enumerate(table.headers, start=1):
                    attributes[f"a{idx}"] = header

            # Get sample data (limit to first 3-4 rows)
            sample_data = []
            if hasattr(table, 'rows') and table.rows:
                sample_data = table.rows[:4]  # Take first 4 rows

            # Determine source file and sheet name
            source_file = "unknown"
            sheet_name = "Sheet1"

            if hasattr(table, 'source_file') and table.source_file:
                source_file = table.source_file
            elif hasattr(table, 'title') and table.title:
                # Try to extract filename from title
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
                # Try to extract reference ID from title
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

    # Pattern: "reference table X.Y" or "table X.Y"
    patterns = [
        r'reference\s+table\s+(\d+\.?\d*)',
        r'table\s+(\d+\.?\d*)',
        r'ref\.?\s*table\s+(\d+\.?\d*)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, logic, re.I)
        references.extend(matches)

    # Remove duplicates and return
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
    # Collect all table references from all fields in this panel
    referenced_ids = set()

    for field in panel_fields:
        logic = field.get('logic', '')
        if logic:
            table_refs = detect_table_references_in_logic(logic)
            referenced_ids.update(table_refs)

    if not referenced_ids:
        return []

    # Filter tables based on referenced IDs
    filtered_tables = []
    for table in all_reference_tables:
        table_id = table.get('reference_id', '')
        if table_id in referenced_ids:
            filtered_tables.append(table)

    return filtered_tables


def call_edv_mini_agent(panel_fields: List[Dict], reference_tables: List[Dict],
                        panel_name: str, temp_dir: Path) -> Optional[List[Dict]]:
    """
    Call the EDV Rule mini agent via claude -p

    Args:
        panel_fields: Fields from source_destination_agent output
        reference_tables: Filtered reference tables for this panel
        panel_name: Name of the panel
        temp_dir: Directory for temp files

    Returns:
        List of fields with EDV params populated, or None if failed
    """

    # Sanitize panel name for filename
    safe_panel_name = re.sub(r'[^\w\-]', '_', panel_name)

    # Temp files for input/output
    fields_input_file = temp_dir / f"{safe_panel_name}_fields_input.json"
    tables_input_file = temp_dir / f"{safe_panel_name}_tables_input.json"
    output_file = temp_dir / f"{safe_panel_name}_edv_output.json"

    # Write fields to temp file
    with open(fields_input_file, 'w') as f:
        json.dump(panel_fields, f, indent=2)

    # Write reference tables to temp file
    with open(tables_input_file, 'w') as f:
        json.dump(reference_tables, f, indent=2)

    prompt = f"""Process fields for panel "{panel_name}" and populate EDV rule parameters.

## Input Data
1. Fields with rules: {fields_input_file}
2. Reference tables: {tables_input_file}

## Task
For each field in the input:
1. Read the field's logic text and examine its rules
2. For EDV-related rules (EXT_DROP_DOWN, EXT_VALUE), populate the params field
3. Analyze table references in logic to determine:
   - Which table to use (ddType)
   - Which columns to display (da)
   - Filter criteria for cascading dropdowns (criterias)
4. For non-EDV rules, leave params empty or don't add it

## Rules for EDV params:
- Independent/Parent dropdowns: Empty criterias array
- Dependent/Child dropdowns: Specify criterias mapping parent fields to table columns
- Use field variableNames from source_fields for parent references
- Map columns as a1, a2, a3, etc. based on table structure
- Only include tables mentioned in the field's logic section

## Output
Write a JSON array to: {output_file}

The output should have the same structure as input, but with params added to EDV rules:

```json
[
  {{
    "field_name": "Field Name",
    "type": "DROPDOWN",
    "mandatory": true,
    "logic": "...",
    "rules": [
      {{
        "id": 1,
        "rule_name": "EXT_DROP_DOWN",
        "source_fields": ["__parent_field__"],
        "destination_fields": ["__current_field__"],
        "params": {{
          "conditionList": [
            {{
              "ddType": ["TABLE_NAME"],
              "criterias": [{{"a1": "__parent_field__"}}],
              "da": ["a2", "a3"],
              "criteriaSearchAttr": [],
              "additionalOptions": null,
              "emptyAddOptionCheck": null,
              "ddProperties": null
            }}
          ],
          "__reasoning": "Explanation of why this structure was chosen"
        }},
        "_reasoning": "..."
      }}
    ],
    "variableName": "__current_field__"
  }}
]
```

IMPORTANT:
- Only add params to EDV-related rules
- Keep all existing fields, rules, and attributes from input
- Add params alongside existing rule attributes
"""

    try:
        print(f"\n{'='*70}")
        print(f"PROCESSING PANEL: {panel_name}")
        print(f"  Fields: {len(panel_fields)}")
        print(f"  Reference Tables: {len(reference_tables)}")
        print('='*70)

        # Call claude -p with the EDV mini agent
        process = subprocess.Popen(
            [
                "claude",
                "-p", prompt,
                "--agent", "mini/03_edv_rule_agent_v2",
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
            print(f"✗ EDV mini agent failed with exit code: {process.returncode}", file=sys.stderr)
            return None

        # Read output file
        if output_file.exists():
            try:
                with open(output_file, 'r') as f:
                    result = json.load(f)
                print(f"✓ Panel '{panel_name}' completed - {len(result)} fields processed")
                return result
            except json.JSONDecodeError as e:
                print(f"✗ Failed to parse output JSON: {e}", file=sys.stderr)
                return None
        else:
            print(f"✗ Output file not found: {output_file}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("✗ Error: 'claude' command not found", file=sys.stderr)
        return None
    except Exception as e:
        print(f"✗ Error calling EDV mini agent: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser(
        description="EDV Rule Dispatcher - Panel-by-panel EDV params population"
    )
    parser.add_argument(
        "--bud",
        required=True,
        help="Path to BUD document (.docx)"
    )
    parser.add_argument(
        "--source-dest-output",
        required=True,
        help="Path to source_destination_agent output JSON (panels with rules)"
    )
    parser.add_argument(
        "--output",
        default="output/edv_rules/all_panels_edv.json",
        help="Output file for all panels (default: output/edv_rules/all_panels_edv.json)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.bud).exists():
        print(f"✗ Error: BUD file not found: {args.bud}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.source_dest_output).exists():
        print(f"✗ Error: Source-destination output file not found: {args.source_dest_output}", file=sys.stderr)
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
            print(f"  - {ref_id}: {title}")

    # Step 3: Load source-destination agent output
    print(f"\nLoading source-destination output: {args.source_dest_output}")
    with open(args.source_dest_output, 'r') as f:
        source_dest_data = json.load(f)

    print(f"Found {len(source_dest_data)} panels in input")

    # Step 4: Process each panel
    print("\n" + "="*70)
    print("PROCESSING PANELS WITH EDV AGENT")
    print("="*70)

    successful_panels = 0
    failed_panels = 0
    skipped_panels = 0
    total_fields_processed = 0
    all_results = {}

    for panel_name, panel_fields in source_dest_data.items():
        if not panel_fields:
            print(f"\nSkipping panel '{panel_name}' - no fields")
            skipped_panels += 1
            continue

        # Filter reference tables for this panel
        referenced_tables = get_referenced_tables_for_panel(panel_fields, all_reference_tables)

        print(f"\nPanel '{panel_name}': {len(panel_fields)} fields, {len(referenced_tables)} referenced tables")

        if referenced_tables:
            print("  Referenced tables:")
            for table in referenced_tables:
                ref_id = table.get('reference_id', 'unknown')
                print(f"    - {ref_id}")

        # Call EDV mini agent
        result = call_edv_mini_agent(
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
            print(f"✗ Panel '{panel_name}' failed", file=sys.stderr)

    # Step 5: Write all results to single output file
    if all_results:
        print(f"\nWriting all results to: {output_file}")
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"✓ Successfully wrote {len(all_results)} panels to output file")

    # Print final summary
    print("\n" + "="*70)
    print("EDV DISPATCHER COMPLETE")
    print("="*70)
    print(f"Total Panels: {len(source_dest_data)}")
    print(f"Successful: {successful_panels}")
    print(f"Failed: {failed_panels}")
    print(f"Skipped: {skipped_panels}")
    print(f"Total Fields Processed: {total_fields_processed}")
    print(f"Total Reference Tables: {len(all_reference_tables)}")
    print(f"Output File: {output_file}")
    print("="*70)

    sys.exit(0 if failed_panels == 0 else 1)


if __name__ == "__main__":
    main()
