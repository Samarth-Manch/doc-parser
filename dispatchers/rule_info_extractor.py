#!/usr/bin/env python3
"""
Rule Info Extractor Dispatcher

This script:
1. Uses SectionIterator to parse a BUD document section-by-section
2. Identifies sections that contain field-level information (not workflows)
3. Extracts content from relevant sections
4. Calls the Claude command with the extracted section data
5. Outputs the meta-rules JSON

Usage:
    python rule_info_extractor.py <document_path> [options]
    python rule_info_extractor.py <document_path> --sections 13,14,15
    python rule_info_extractor.py <document_path> --auto-detect
"""

import argparse
import json
import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from get_section_by_index import SectionIterator


# Keywords that indicate field-level information sections
FIELD_SECTION_KEYWORDS = [
    'field-level',
    'field level',
    'fields',
    'field information',
    'field details',
    'field definition',
    'field logic',
    'field rules',
    'reference table',
    'dropdown',
    'validation',
]

# Keywords that indicate workflow/process sections (should be excluded)
WORKFLOW_SECTION_KEYWORDS = [
    'behaviour',
    'behavior',
    'process detail',
    'approver',
    'initiator',
    'spoc',
    'workflow',
    'flow chart',
    'flowchart',
    'approval flow',
    'escalation',
    'routing',
    'notification',
    'communication',
    'email template',
    'sms template',
    'access management',
    'reporting',
    'integration',
]

# Content patterns that indicate meta-rules (valuable for extraction)
META_RULE_PATTERNS = [
    r'if\s+.*?(dropdown|field|value).*?(change|clear|reset)',
    r'dependent\s+dropdown',
    r'parent\s+dropdown',
    r'should\s+be\s+clear',
    r'(visible|invisible|mandatory|non-mandatory)\s+.*?(when|if|based)',
    r'copy.*?values?\s+.*?(clear|reset)',
    r'note\s*[-–:]',
    r'important\s*[-–:]',
    r'rule\s*[-–:]',
]


def is_field_related_section(section: Dict[str, Any]) -> tuple[bool, str]:
    """
    Determine if a section contains field-level information.

    Args:
        section: Section dictionary from SectionIterator

    Returns:
        Tuple of (is_field_related, reason)
    """
    heading = section.get('heading', '').lower()
    content = ' '.join(section.get('content', [])).lower()
    parent_path = section.get('parent_path', '').lower()

    # Check for explicit workflow indicators in heading - skip these
    for keyword in WORKFLOW_SECTION_KEYWORDS:
        if keyword in heading:
            return False, f"Workflow keyword '{keyword}' in heading"

    # Check for field-related indicators in heading
    for keyword in FIELD_SECTION_KEYWORDS:
        if keyword in heading:
            return True, f"Field keyword '{keyword}' in heading"

    # Check content for meta-rule patterns
    has_meta_rules = False
    meta_rule_found = None
    for pattern in META_RULE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            has_meta_rules = True
            meta_rule_found = pattern
            break

    # If content has meta-rule patterns and is not in a workflow section, include it
    if has_meta_rules:
        # Double-check parent path doesn't indicate workflow
        for keyword in WORKFLOW_SECTION_KEYWORDS:
            if keyword in parent_path:
                return False, f"Workflow keyword '{keyword}' in parent path"
        return True, f"Meta-rule pattern found: {meta_rule_found}"

    # Check if section has tables with field definitions
    if section.get('fields') and len(section['fields']) > 0:
        return True, f"Contains {len(section['fields'])} field definitions"

    # Skip empty sections
    if not content.strip():
        return False, "Empty content"

    # Skip sections that are primarily about process/workflow based on content
    workflow_content_keywords = ['login', 'submit', 'approve', 'reject', 'assign', 'notification']
    workflow_count = sum(1 for kw in workflow_content_keywords if kw in content)
    if workflow_count >= 3:
        return False, f"Content appears workflow-related ({workflow_count} workflow keywords)"

    return False, "No field-related indicators found"


def classify_section_type(section: Dict[str, Any]) -> str:
    """
    Classify a section into a type category.

    Args:
        section: Section dictionary

    Returns:
        Section type string
    """
    heading = section.get('heading', '').lower()

    if 'field' in heading:
        return 'field_information'
    elif 'reference' in heading or 'table' in heading:
        return 'reference_data'
    elif any(kw in heading for kw in ['behaviour', 'behavior', 'process']):
        return 'workflow'
    elif 'integration' in heading:
        return 'integration'
    elif 'communication' in heading:
        return 'communication'
    elif any(kw in heading for kw in ['scope', 'objective', 'summary', 'background']):
        return 'overview'
    else:
        return 'other'


def extract_sections_data(document_path: str, section_indices: Optional[List[int]] = None,
                          auto_detect: bool = False) -> dict:
    """
    Extract section data from document using SectionIterator.

    Args:
        document_path: Path to the BUD document (.docx)
        section_indices: Specific section indices to process (optional)
        auto_detect: If True, automatically detect field-related sections

    Returns:
        Dictionary containing document info and extracted sections
    """
    iterator = SectionIterator(document_path)
    iterator.parse()

    total_sections = iterator.get_section_count()

    # Determine which sections to process
    sections_to_process = []
    section_classification = []

    if section_indices:
        # Use provided indices
        for idx in section_indices:
            if 0 <= idx < total_sections:
                section = iterator.get_section_by_index(idx)
                is_field, reason = is_field_related_section(section)
                sections_to_process.append({
                    'index': idx,
                    'section': section,
                    'is_field_related': is_field,
                    'classification_reason': reason,
                    'section_type': classify_section_type(section)
                })
    elif auto_detect:
        # Auto-detect field-related sections
        for idx in range(total_sections):
            section = iterator.get_section_by_index(idx)
            is_field, reason = is_field_related_section(section)
            section_type = classify_section_type(section)

            section_classification.append({
                'index': idx,
                'heading': section.get('heading', ''),
                'is_field_related': is_field,
                'reason': reason,
                'section_type': section_type
            })

            if is_field:
                sections_to_process.append({
                    'index': idx,
                    'section': section,
                    'is_field_related': is_field,
                    'classification_reason': reason,
                    'section_type': section_type
                })
    else:
        # Process all sections, let Claude filter
        for idx in range(total_sections):
            section = iterator.get_section_by_index(idx)
            is_field, reason = is_field_related_section(section)
            sections_to_process.append({
                'index': idx,
                'section': section,
                'is_field_related': is_field,
                'classification_reason': reason,
                'section_type': classify_section_type(section)
            })

    # Build document info
    return {
        "document_info": {
            "file_name": Path(document_path).name,
            "file_path": document_path,
            "extraction_timestamp": datetime.now().isoformat(),
            "total_sections": total_sections,
            "sections_to_analyze": len([s for s in sections_to_process if s['is_field_related']])
        },
        "section_classification": section_classification if auto_detect else [],
        "sections": [
            {
                "index": s['index'],
                "heading": s['section'].get('heading', ''),
                "level": s['section'].get('level', 0),
                "parent_path": s['section'].get('parent_path', ''),
                "content": s['section'].get('content', []),
                "is_field_related": s['is_field_related'],
                "classification_reason": s['classification_reason'],
                "section_type": s['section_type'],
                "has_tables": len(s['section'].get('tables', [])) > 0,
                "table_count": len(s['section'].get('tables', []))
            }
            for s in sections_to_process
        ]
    }


def call_claude_command(sections_json_path: str, output_dir: str) -> str:
    """
    Call the Claude rule_info_extractor command with extracted sections.

    Args:
        sections_json_path: Path to the JSON file containing extracted sections data
        output_dir: Directory for output files

    Returns:
        Claude command output
    """
    prompt = f"""Analyze the pre-extracted BUD sections data for unstructured meta-rules.

## Input File
Read the extracted sections data from: {sections_json_path}

## Output Directory
Save the meta-rules JSON to: {output_dir}

Use the /rule_info_extrator skill to analyze these sections and extract implementation-critical natural language rules.
"""

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
        description="Extract unstructured meta-rules from BUD document sections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect field-related sections
  python rule_info_extractor.py document.docx --auto-detect

  # Process specific sections
  python rule_info_extractor.py document.docx --sections 13,14,15

  # List all sections with classification
  python rule_info_extractor.py document.docx --list

  # Extract sections data only (skip Claude analysis)
  python rule_info_extractor.py document.docx --sections-only
        """
    )
    parser.add_argument(
        "document_path",
        help="Path to the BUD document (.docx)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: extraction/rule_info_output/<timestamp>/)"
    )
    parser.add_argument(
        "--sections",
        type=str,
        default=None,
        help="Comma-separated list of section indices to process (e.g., '13,14,15')"
    )
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        help="Automatically detect field-related sections (recommended)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all sections with their classification and exit"
    )
    parser.add_argument(
        "--sections-only",
        action="store_true",
        help="Only extract sections data (skip Claude analysis)"
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Path to save extracted sections JSON (for debugging)"
    )

    args = parser.parse_args()

    # Validate document path
    if not os.path.exists(args.document_path):
        print(f"Error: Document not found: {args.document_path}", file=sys.stderr)
        sys.exit(1)

    # Parse section indices if provided
    section_indices = None
    if args.sections:
        try:
            section_indices = [int(x.strip()) for x in args.sections.split(',')]
        except ValueError:
            print(f"Error: Invalid section indices: {args.sections}", file=sys.stderr)
            sys.exit(1)

    # If --list flag, just show section classification
    if args.list:
        iterator = SectionIterator(args.document_path)
        iterator.parse()

        print(f"\nDocument: {args.document_path}")
        print(f"Total sections: {iterator.get_section_count()}")
        print("\nSection Classification:")
        print("-" * 100)
        print(f"{'Idx':<4} {'Type':<20} {'Field?':<8} {'Heading':<40} {'Reason'}")
        print("-" * 100)

        field_sections = []
        for idx in range(iterator.get_section_count()):
            section = iterator.get_section_by_index(idx)
            is_field, reason = is_field_related_section(section)
            section_type = classify_section_type(section)
            heading = section.get('heading', '')[:38]

            marker = "YES" if is_field else "no"
            print(f"{idx:<4} {section_type:<20} {marker:<8} {heading:<40} {reason[:30]}")

            if is_field:
                field_sections.append(idx)

        print("-" * 100)
        print(f"\nField-related sections detected: {field_sections}")
        print(f"Use: python rule_info_extractor.py {args.document_path} --sections {','.join(map(str, field_sections))}")
        sys.exit(0)

    # Set up output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = f"extraction/rule_info_output/{timestamp}"

    os.makedirs(output_dir, exist_ok=True)

    # Extract sections data
    print(f"Parsing document: {args.document_path}")
    try:
        sections_data = extract_sections_data(
            args.document_path,
            section_indices=section_indices,
            auto_detect=args.auto_detect or (section_indices is None)
        )
    except Exception as e:
        print(f"Error parsing document: {e}", file=sys.stderr)
        sys.exit(1)

    field_related_count = len([s for s in sections_data['sections'] if s['is_field_related']])
    print(f"Total sections: {sections_data['document_info']['total_sections']}")
    print(f"Field-related sections to analyze: {field_related_count}")

    # Save sections JSON
    if args.json_output:
        with open(args.json_output, 'w') as f:
            json.dump(sections_data, f, indent=2)
        print(f"Sections data saved to: {args.json_output}")

    # If sections-only mode, output and exit
    if args.sections_only:
        print("\nField-related sections:")
        for s in sections_data['sections']:
            if s['is_field_related']:
                print(f"  [{s['index']}] {s['heading']}")
                for line in s['content'][:3]:
                    if line.strip():
                        print(f"      > {line[:80]}...")
        sys.exit(0)

    # Save sections data for Claude command
    sections_json_path = os.path.join(output_dir, "extracted_sections.json")
    with open(sections_json_path, 'w') as f:
        json.dump(sections_data, f, indent=2)
    print(f"Sections data saved to: {sections_json_path}")

    # Call Claude command
    print("Calling Claude for meta-rule extraction...")
    result = call_claude_command(sections_json_path, output_dir)

    if result:
        print("\nClaude analysis complete.")
        print(f"Output directory: {output_dir}")
    else:
        print("\nClaude analysis failed. Sections data is available at:", sections_json_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
