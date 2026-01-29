#!/usr/bin/env python3
"""
Inter-Panel Rule Field References Dispatcher

This script:
1. Parses a BUD document using DocumentParser
2. Extracts all fields and organizes them by panel
3. Calls the Claude command with the extracted data
4. Outputs the cross-panel references JSON
"""

import argparse
import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from doc_parser import DocumentParser


def extract_fields_data(document_path: str) -> dict:
    """
    Parse document and extract all fields organized by panel.

    Args:
        document_path: Path to the BUD document (.docx)

    Returns:
        Dictionary containing document info and fields by panel
    """
    parser = DocumentParser()
    parsed = parser.parse(document_path)

    # Build panel map
    panels = {}
    for field in parsed.all_fields:
        panel_name = field.section or "Unknown Panel"
        if panel_name not in panels:
            panels[panel_name] = []
        panels[panel_name].append(field)

    # Convert fields to serializable format
    fields_by_panel = {}
    for panel_name, fields in panels.items():
        fields_by_panel[panel_name] = [
            {
                "field_name": f.name,
                "variable_name": f.variable_name or f"__{f.name.lower().replace(' ', '_')}__",
                "field_type": f.field_type.value if hasattr(f.field_type, 'value') else str(f.field_type),
                "logic": f.logic or "",
                "rules": f.rules or "",
                "visibility_condition": getattr(f, 'visibility_condition', "") or "",
                "validation": getattr(f, 'validation', "") or "",
                "mandatory": getattr(f, 'mandatory', False),
                "panel": panel_name
            }
            for f in fields
        ]

    # Build document info
    doc_name = Path(document_path).name

    return {
        "document_info": {
            "file_name": doc_name,
            "file_path": document_path,
            "extraction_timestamp": datetime.now().isoformat(),
            "total_fields": len(parsed.all_fields),
            "total_panels": len(panels)
        },
        "panels": list(panels.keys()),
        "fields_by_panel": fields_by_panel
    }


def call_claude_command(fields_json_path: str, output_dir: str) -> str:
    """
    Call the Claude inter_panel_rule_field_references command with extracted fields.

    Args:
        fields_json_path: Path to the JSON file containing extracted fields data
        output_dir: Directory for output files

    Returns:
        Path to the output JSON file
    """
    # Prepare the prompt referencing the file path
    prompt = f"""Analyze the pre-extracted BUD fields data for cross-panel field references.

## Input File
Read the extracted fields data from: {fields_json_path}

## Output Directory
Save the inter-panel references JSON to: {output_dir}

Use the /inter_panel_rule_field_references skill to analyze these fields and detect cross-panel dependencies.
"""

    # Call claude with the command
    try:
        result = subprocess.run(
            [
                "claude",
                "-p", prompt,
                "--allowedTools", "Read,Write"
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        if result.returncode != 0:
            print(f"Claude command failed: {result.stderr}", file=sys.stderr)
            return None

        return result.stdout

    except FileNotFoundError:
        print("Error: 'claude' command not found. Ensure Claude CLI is installed.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error calling Claude: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Extract inter-panel field references from a BUD document"
    )
    parser.add_argument(
        "document_path",
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: extraction/inter_panel_output/<timestamp>/)"
    )
    parser.add_argument(
        "--fields-only",
        action="store_true",
        help="Only extract and output fields data (skip Claude analysis)"
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Path to save extracted fields JSON (for debugging or manual analysis)"
    )

    args = parser.parse_args()

    # Validate document path
    if not os.path.exists(args.document_path):
        print(f"Error: Document not found: {args.document_path}", file=sys.stderr)
        sys.exit(1)

    # Set up output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"extraction/inter_panel_output/{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    # Extract fields data
    print(f"Parsing document: {args.document_path}")
    try:
        fields_data = extract_fields_data(args.document_path)
    except Exception as e:
        print(f"Error parsing document: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracted {fields_data['document_info']['total_fields']} fields from {fields_data['document_info']['total_panels']} panels")

    # Save fields JSON if requested
    if args.json_output:
        with open(args.json_output, 'w') as f:
            json.dump(fields_data, f, indent=2)
        print(f"Fields data saved to: {args.json_output}")

    # If fields-only mode, just output and exit
    if args.fields_only:
        print(json.dumps(fields_data, indent=2))
        sys.exit(0)

    # Save fields data for Claude command
    fields_json_path = os.path.join(output_dir, "extracted_fields.json")
    with open(fields_json_path, 'w') as f:
        json.dump(fields_data, f, indent=2)
    print(f"Fields data saved to: {fields_json_path}")

    # Call Claude command
    print("Calling Claude for cross-panel reference analysis...")
    result = call_claude_command(fields_json_path, output_dir)

    if result:
        print("\nClaude analysis complete.")
        print(f"Output directory: {output_dir}")
    else:
        print("\nClaude analysis failed. Fields data is available at:", fields_json_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
