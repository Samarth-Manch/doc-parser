#!/usr/bin/env python3
"""
Compare Form Builders Dispatcher

This script:
1. Parses a BUD document using DocumentParser to extract expected fields
2. Calls the Claude compare_form_builders skill with the extracted fields
3. Generates a comparison report with BUD field validation

Primary Focus: Generated (QA) form vs BUD specification
Secondary Reference: Human-Made (UAT) form
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


def extract_bud_fields(document_path: str) -> dict:
    """
    Parse BUD document and extract all fields organized by panel.

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
    all_field_names = []

    for panel_name, fields in panels.items():
        panel_fields = []
        for f in fields:
            field_data = {
                "field_name": f.name,
                "variable_name": f.variable_name or f"__{f.name.lower().replace(' ', '_')}__",
                "field_type": f.field_type.value if hasattr(f.field_type, 'value') else str(f.field_type),
                "is_mandatory": f.is_mandatory,
                "panel": panel_name
            }
            panel_fields.append(field_data)
            all_field_names.append(f.name)

        fields_by_panel[panel_name] = panel_fields

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
        "fields_by_panel": fields_by_panel,
        "all_field_names": all_field_names
    }


def call_claude_command(
    generated_url: str,
    human_made_url: str,
    bud_fields_json_path: str,
    output_dir: str,
    report_file: str,
    generated_login_url: str = None,
    generated_username: str = None,
    generated_password: str = None,
    human_made_login_url: str = None,
    human_made_username: str = None,
    human_made_password: str = None
) -> str:
    """
    Call the Claude compare_form_builders skill with BUD field validation.

    Args:
        generated_url: Generated (QA) form builder URL
        human_made_url: Human-Made (UAT/reference) form builder URL
        bud_fields_json_path: Path to the JSON file containing BUD fields
        output_dir: Directory for output files
        report_file: Name of the report file
        generated_login_url: Optional login URL for Generated environment
        generated_username: Optional username for Generated environment
        generated_password: Optional password for Generated environment
        human_made_login_url: Optional login URL for Human-Made environment
        human_made_username: Optional username for Human-Made environment
        human_made_password: Optional password for Human-Made environment

    Returns:
        Command output or None on failure
    """
    # Build the prompt with all parameters
    prompt_parts = [
        f"Compare Generated (QA) form builder against BUD specification with Human-Made (UAT) as reference.",
        f"",
        f"## URLs",
        f"GENERATED_URL = {generated_url}",
        f"HUMAN_MADE_URL = {human_made_url}",
        f"",
        f"## BUD Fields Reference",
        f"BUD_FIELDS_JSON = {bud_fields_json_path}",
        f"",
        f"## Output",
        f"OUTPUT_DIR = {output_dir}",
        f"REPORT_FILE = {report_file}",
    ]

    # Add login credentials if provided
    if generated_login_url or generated_username:
        prompt_parts.extend([
            f"",
            f"## Authentication - Generated Environment",
        ])
        if generated_login_url:
            prompt_parts.append(f"GENERATED_LOGIN_URL = {generated_login_url}")
        if generated_username:
            prompt_parts.append(f"GENERATED_USERNAME = {generated_username}")
        if generated_password:
            prompt_parts.append(f"GENERATED_PASSWORD = {generated_password}")

    if human_made_login_url or human_made_username:
        prompt_parts.extend([
            f"",
            f"## Authentication - Human-Made Environment",
        ])
        if human_made_login_url:
            prompt_parts.append(f"HUMAN_MADE_LOGIN_URL = {human_made_login_url}")
        if human_made_username:
            prompt_parts.append(f"HUMAN_MADE_USERNAME = {human_made_username}")
        if human_made_password:
            prompt_parts.append(f"HUMAN_MADE_PASSWORD = {human_made_password}")

    prompt_parts.extend([
        f"",
        f"Use the /compare_form_builders skill to perform the comparison with BUD field validation.",
        f"",
        f"IMPORTANT: Prioritize Generated (QA) vs BUD comparison. Human-Made (UAT) is secondary reference.",
        f"",
        f"Mark fields as CRITICAL (red) if:",
        f"1. Field exists in BUD but is MISSING from Generated form (implementation gap - HIGH PRIORITY)",
        f"2. Field exists in Generated form but is NOT in BUD (undocumented field - needs review)",
        f"",
        f"DO NOT select templates yourself - the human will navigate to the correct page.",
    ])

    prompt = "\n".join(prompt_parts)

    # Call claude with the command
    try:
        result = subprocess.run(
            [
                "claude",
                "-p", prompt,
                "--allowedTools", "mcp__chrome-devtools__*,Read,Write,Bash"
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
        description="Compare Generated (QA) form builder against BUD specification with Human-Made (UAT) reference"
    )
    parser.add_argument(
        "document_path",
        help="Path to the BUD document (.docx) for field reference"
    )
    parser.add_argument(
        "--generated-url",
        required=True,
        help="Generated (QA) form builder URL"
    )
    parser.add_argument(
        "--human-made-url",
        required=True,
        help="Human-Made (UAT/reference) form builder URL"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: reports/)"
    )
    parser.add_argument(
        "--report-file",
        default=None,
        help="Report filename (default: form_builder_comparison_<timestamp>.md)"
    )

    # Authentication for Generated environment
    parser.add_argument(
        "--generated-login-url",
        default=None,
        help="Login URL for Generated environment"
    )
    parser.add_argument(
        "--generated-username",
        default=None,
        help="Username for Generated environment"
    )
    parser.add_argument(
        "--generated-password",
        default=None,
        help="Password for Generated environment"
    )

    # Authentication for Human-Made environment
    parser.add_argument(
        "--human-made-login-url",
        default=None,
        help="Login URL for Human-Made environment"
    )
    parser.add_argument(
        "--human-made-username",
        default=None,
        help="Username for Human-Made environment"
    )
    parser.add_argument(
        "--human-made-password",
        default=None,
        help="Password for Human-Made environment"
    )

    # Debug options
    parser.add_argument(
        "--fields-only",
        action="store_true",
        help="Only extract and output BUD fields data (skip comparison)"
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Path to save extracted BUD fields JSON (for debugging)"
    )

    args = parser.parse_args()

    # Validate document path
    if not os.path.exists(args.document_path):
        print(f"Error: Document not found: {args.document_path}", file=sys.stderr)
        sys.exit(1)

    # Set up output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = args.output_dir or "reports"
    report_file = args.report_file or f"form_builder_comparison_{timestamp}.md"

    os.makedirs(output_dir, exist_ok=True)

    # Extract BUD fields
    print(f"Parsing BUD document: {args.document_path}")
    try:
        bud_fields_data = extract_bud_fields(args.document_path)
    except Exception as e:
        print(f"Error parsing document: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Extracted {bud_fields_data['document_info']['total_fields']} fields from {bud_fields_data['document_info']['total_panels']} panels")

    # Save BUD fields JSON
    bud_fields_json_path = args.json_output or os.path.join(output_dir, f"bud_fields_{timestamp}.json")
    with open(bud_fields_json_path, 'w') as f:
        json.dump(bud_fields_data, f, indent=2)
    print(f"BUD fields saved to: {bud_fields_json_path}")

    # If fields-only mode, just output and exit
    if args.fields_only:
        print("\n--- Extracted BUD Fields ---")
        print(json.dumps(bud_fields_data, indent=2))
        sys.exit(0)

    # Call Claude command for comparison
    print(f"\nStarting form builder comparison...")
    print(f"Generated (QA): {args.generated_url}")
    print(f"Human-Made (UAT): {args.human_made_url}")
    print(f"Output: {os.path.join(output_dir, report_file)}")

    result = call_claude_command(
        generated_url=args.generated_url,
        human_made_url=args.human_made_url,
        bud_fields_json_path=bud_fields_json_path,
        output_dir=output_dir,
        report_file=report_file,
        generated_login_url=args.generated_login_url,
        generated_username=args.generated_username,
        generated_password=args.generated_password,
        human_made_login_url=args.human_made_login_url,
        human_made_username=args.human_made_username,
        human_made_password=args.human_made_password
    )

    if result:
        print("\nComparison complete.")
        print(f"Report saved to: {os.path.join(output_dir, report_file)}")
        print(f"BUD fields reference: {bud_fields_json_path}")
    else:
        print("\nComparison failed. BUD fields data is available at:", bud_fields_json_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
