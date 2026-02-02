#!/usr/bin/env python3
"""
Deterministic field extractor - extracts only field name, type, and mandatory status.
No rules, no AI processing - pure deterministic parsing from DOCX tables.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from doc_parser import DocumentParser


def extract_fields_simple(docx_path: str) -> List[Dict[str, Any]]:
    """
    Extract only field name, field type, and mandatory status from a document.

    Args:
        docx_path: Path to the DOCX file

    Returns:
        List of dictionaries with fieldName, fieldType, and mandatory keys
    """
    parser = DocumentParser()
    parsed = parser.parse(docx_path)

    # Extract simple field information
    fields_output = []
    for field in parsed.all_fields:
        fields_output.append({
            'fieldName': field.name,
            'fieldType': field.field_type.value,
            'mandatory': field.is_mandatory
        })

    return fields_output


def process_document(docx_path: str, output_dir: str = "output/simple_fields") -> str:
    """
    Process a single document and save the output.

    Args:
        docx_path: Path to the DOCX file
        output_dir: Directory to save output JSON

    Returns:
        Path to the output JSON file
    """
    docx_path_obj = Path(docx_path)

    if not docx_path_obj.exists():
        raise FileNotFoundError(f"Document not found: {docx_path}")

    print(f"Processing: {docx_path_obj.name}")

    # Extract fields
    fields = extract_fields_simple(str(docx_path_obj))

    # Prepare output
    output_data = {
        'source_document': docx_path_obj.name,
        'extraction_date': datetime.now().isoformat(),
        'total_fields': len(fields),
        'fields': fields
    }

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate output filename
    doc_name = docx_path_obj.stem
    output_file = output_path / f"{doc_name}_fields.json"

    # Save output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Extracted {len(fields)} fields")
    print(f"  ✓ Saved to: {output_file}")

    return str(output_file)


def process_all_documents(
    input_dir: str = "documents",
    output_dir: str = "output/simple_fields",
    pattern: str = "*.docx"
) -> List[str]:
    """
    Process all DOCX documents in a directory.

    Args:
        input_dir: Directory containing DOCX files
        output_dir: Directory to save output JSON files
        pattern: File pattern to match (default: *.docx)

    Returns:
        List of output file paths
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Find all DOCX files
    docx_files = list(input_path.glob(pattern))

    if not docx_files:
        print(f"No DOCX files found in {input_dir}")
        return []

    print(f"Found {len(docx_files)} document(s) to process\n")

    output_files = []
    for docx_file in sorted(docx_files):
        try:
            output_file = process_document(str(docx_file), output_dir)
            output_files.append(output_file)
            print()
        except Exception as e:
            print(f"  ✗ Error processing {docx_file.name}: {e}")
            print()

    return output_files


def main():
    """Main entry point for the script."""
    if len(sys.argv) > 1:
        # Process specific file
        docx_path = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "output/simple_fields"
        process_document(docx_path, output_dir)
    else:
        # Process all documents in the documents directory
        output_files = process_all_documents()

        if output_files:
            print("=" * 60)
            print(f"Successfully processed {len(output_files)} document(s)")
            print(f"Output saved to: output/simple_fields/")


if __name__ == "__main__":
    main()
