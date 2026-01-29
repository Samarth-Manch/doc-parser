#!/usr/bin/env python3
"""
Intra-Panel Rule Field References Dispatcher

This script:
1. Parses a BUD document using DocumentParser
2. Extracts all fields and organizes them by panel
3. Calls Claude command for each panel separately
4. Consolidates all panel results into a single JSON output
5. Outputs one consolidated JSON with all intra-panel references
"""

import argparse
import json
import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from doc_parser import DocumentParser


def sanitize_panel_name(panel_name: str) -> str:
    """
    Sanitize panel name for use in filenames.

    Args:
        panel_name: Original panel name

    Returns:
        Sanitized string safe for filenames
    """
    # Replace spaces with underscores
    sanitized = panel_name.replace(" ", "_")
    # Remove special characters except underscores
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', sanitized)
    return sanitized


def extract_panel_data(document_path: str) -> dict:
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

    # Convert fields to serializable format for each panel
    panels_data = {}
    for panel_name, fields in panels.items():
        panels_data[panel_name] = [
            {
                "field_name": f.name,
                "variable_name": f.variable_name or f"__{f.name.lower().replace(' ', '_')}__",
                "field_type": f.field_type.value if hasattr(f.field_type, 'value') else str(f.field_type),
                "logic": f.logic or "",
                "rules": f.rules or "",
                "visibility_condition": getattr(f, 'visibility_condition', "") or "",
                "validation": getattr(f, 'validation', "") or "",
                "mandatory": getattr(f, 'mandatory', False)
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
        "panels_data": panels_data
    }


def create_panel_input_json(document_info: dict, panel_name: str, fields: list, output_path: str) -> None:
    """
    Create input JSON file for a single panel.

    Args:
        document_info: Document metadata
        panel_name: Name of the panel
        fields: List of fields in this panel
        output_path: Path to save the JSON file
    """
    panel_data = {
        "document_info": {
            "file_name": document_info["file_name"],
            "file_path": document_info["file_path"],
            "extraction_timestamp": document_info["extraction_timestamp"],
            "total_fields": len(fields)
        },
        "panel_name": panel_name,
        "fields": fields
    }

    with open(output_path, 'w') as f:
        json.dump(panel_data, f, indent=2)


def call_claude_command(panel_json_path: str, output_dir: str, panel_name: str, doc_name: str) -> dict:
    """
    Call the Claude intra_panel_rule_field_references command with panel fields.

    Args:
        panel_json_path: Path to the JSON file containing panel fields data
        output_dir: Directory for output files
        panel_name: Name of the panel being analyzed
        doc_name: Document name for output file naming

    Returns:
        Dictionary with panel analysis results or None if failed
    """
    # Determine output file path
    sanitized_name = sanitize_panel_name(panel_name)
    output_file = os.path.join(output_dir, f"{doc_name}_{sanitized_name}_intra_panel_references.json")

    # Prepare the prompt referencing the file path
    prompt = f"""Analyze the pre-extracted BUD fields data for intra-panel field references.

## Panel Being Analyzed
{panel_name}

## Input File
Read the extracted fields data from: {panel_json_path}

## Output File
Save the intra-panel references JSON to: {output_file}

Use the /intra_panel_rule_field_references skill to analyze these fields and detect within-panel dependencies.
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
            print(f"    ✗ Claude command failed: {result.stderr}", file=sys.stderr)
            return None

        # Read the generated output file
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    panel_result = json.load(f)
                return panel_result
            except Exception as e:
                print(f"    ✗ Failed to read output file: {e}", file=sys.stderr)
                return None
        else:
            print(f"    ✗ Output file not created: {output_file}", file=sys.stderr)
            return None

    except FileNotFoundError:
        print("Error: 'claude' command not found. Ensure Claude CLI is installed.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"    ✗ Error calling Claude: {e}", file=sys.stderr)
        return None


def consolidate_panel_results(panel_results: list, document_info: dict) -> dict:
    """
    Consolidate all panel-specific results into a single summary structure.

    Args:
        panel_results: List of dictionaries containing panel analysis results
        document_info: Document metadata

    Returns:
        Consolidated summary dictionary
    """
    consolidated = {
        "document_info": document_info,
        "panels_analyzed": len(panel_results),
        "panel_results": [],
        "total_relationship_summary": {
            "visibility_control": 0,
            "mandatory_control": 0,
            "value_derivation": 0,
            "data_dependency": 0,
            "validation": 0,
            "enable_disable": 0,
            "conditional": 0,
            "clear_operation": 0,
            "other": 0
        },
        "all_controlling_fields": []
    }

    for panel_result in panel_results:
        # Add complete panel result
        panel_data = {
            "panel_name": panel_result.get("panel_info", {}).get("panel_name", "Unknown"),
            "panel_info": panel_result.get("panel_info", {}),
            "intra_panel_references": panel_result.get("intra_panel_references", []),
            "relationship_summary": panel_result.get("relationship_summary", {}),
            "controlling_fields": panel_result.get("controlling_fields", [])
        }
        consolidated["panel_results"].append(panel_data)

        # Aggregate relationship counts
        if "relationship_summary" in panel_result:
            for rel_type, count in panel_result["relationship_summary"].items():
                if rel_type in consolidated["total_relationship_summary"]:
                    consolidated["total_relationship_summary"][rel_type] += count

        # Aggregate controlling fields
        if "controlling_fields" in panel_result:
            panel_name = panel_result.get("panel_info", {}).get("panel_name", "Unknown")
            for cf in panel_result["controlling_fields"]:
                cf_copy = cf.copy()
                cf_copy["panel"] = panel_name
                consolidated["all_controlling_fields"].append(cf_copy)

    return consolidated


def main():
    parser = argparse.ArgumentParser(
        description="Extract intra-panel field references from a BUD document"
    )
    parser.add_argument(
        "document_path",
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: extraction/intra_panel_output/<timestamp>/)"
    )
    parser.add_argument(
        "--panels",
        nargs="*",
        default=None,
        help="Specific panels to analyze (default: all panels)"
    )
    parser.add_argument(
        "--fields-only",
        action="store_true",
        help="Only extract and output fields data (skip Claude analysis)"
    )
    parser.add_argument(
        "--keep-individual",
        action="store_true",
        help="Keep individual panel JSON files (they are created temporarily and deleted by default)"
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
        output_dir = f"extraction/intra_panel_output/{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    # Extract fields data
    print(f"Parsing document: {args.document_path}")
    try:
        data = extract_panel_data(args.document_path)
    except Exception as e:
        print(f"Error parsing document: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracted {data['document_info']['total_fields']} fields from {data['document_info']['total_panels']} panels")

    # Determine which panels to process
    panels_to_process = args.panels if args.panels else data["panels"]

    # Filter out panels that don't exist
    valid_panels = [p for p in panels_to_process if p in data["panels_data"]]
    if len(valid_panels) < len(panels_to_process):
        invalid = set(panels_to_process) - set(valid_panels)
        print(f"Warning: Ignoring unknown panels: {invalid}", file=sys.stderr)

    # Filter panels with at least 2 fields (intra-panel refs need at least 2 fields)
    analyzable_panels = [p for p in valid_panels if len(data["panels_data"][p]) >= 2]
    skipped_panels = [p for p in valid_panels if len(data["panels_data"][p]) < 2]

    if skipped_panels:
        print(f"Skipping {len(skipped_panels)} panels with < 2 fields: {skipped_panels}")

    # Save full fields JSON if requested
    if args.json_output:
        with open(args.json_output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Full fields data saved to: {args.json_output}")

    # If fields-only mode, just output and exit
    if args.fields_only:
        print("\nPanels found:")
        for panel_name, fields in data["panels_data"].items():
            print(f"  - {panel_name}: {len(fields)} fields")
        sys.exit(0)

    doc_name = Path(args.document_path).stem

    # Process each panel separately and collect results
    print(f"\nProcessing {len(analyzable_panels)} panels...")
    panel_results = []
    individual_files = []

    for i, panel_name in enumerate(analyzable_panels, 1):
        fields = data["panels_data"][panel_name]
        print(f"[{i}/{len(analyzable_panels)}] Analyzing: {panel_name} ({len(fields)} fields)")

        # Create panel input JSON
        sanitized_name = sanitize_panel_name(panel_name)
        panel_json_path = os.path.join(output_dir, f"input_{sanitized_name}.json")
        create_panel_input_json(data["document_info"], panel_name, fields, panel_json_path)

        # Call Claude command for this panel
        result = call_claude_command(panel_json_path, output_dir, panel_name, doc_name)

        if result:
            panel_results.append(result)
            print(f"    ✓ Analysis complete")
            # Track individual file for potential cleanup
            individual_files.append(os.path.join(output_dir, f"{doc_name}_{sanitized_name}_intra_panel_references.json"))
        else:
            print(f"    ✗ Analysis failed")

        # Clean up input file
        if os.path.exists(panel_json_path):
            os.remove(panel_json_path)

    # Consolidate results into single JSON
    if len(panel_results) > 0:
        print(f"\nConsolidating results from {len(panel_results)} panels...")
        consolidated = consolidate_panel_results(panel_results, data["document_info"])

        consolidated_path = os.path.join(output_dir, f"{doc_name}_intra_panel_references.json")

        with open(consolidated_path, 'w') as f:
            json.dump(consolidated, f, indent=2)

        print(f"Consolidated results saved to: {consolidated_path}")

        # Clean up individual panel files unless requested to keep them
        if not args.keep_individual:
            for file_path in individual_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
            print(f"Cleaned up {len(individual_files)} temporary panel files")

    panels_processed = len(panel_results)

    # Final summary
    print("\n" + "="*60)
    print("INTRA-PANEL ANALYSIS COMPLETE")
    print("="*60)
    print(f"Document: {data['document_info']['file_name']}")
    print(f"Panels analyzed: {panels_processed}/{len(valid_panels)}")
    print(f"Output directory: {output_dir}")
    if panels_processed > 0:
        print(f"Consolidated output: {doc_name}_intra_panel_references.json")
    print("="*60)


if __name__ == "__main__":
    main()
