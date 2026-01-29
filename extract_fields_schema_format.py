#!/usr/bin/env python3
"""
Field extractor that outputs in the same format as documents/json_output.
Matches the exact schema structure with template.documentTypes.formFillMetadatas.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from doc_parser import DocumentParser


def generate_template_id(doc_name: str) -> int:
    """Generate a template ID from document name (extract existing ID if present)."""
    # Try to extract existing template ID from filename (e.g., "3625" from "KYC Master - UB 3625")
    match = re.search(r'\b(\d{4})\b', doc_name)
    if match:
        return int(match.group(1))
    # Otherwise generate a hash-based ID
    return abs(hash(doc_name)) % 10000


def extract_template_name(doc_name: str) -> str:
    """Extract template name from document filename."""
    # Remove file extension
    name = Path(doc_name).stem
    # Remove ID patterns like "UB 3625, 3626, 3630" or "- 3625"
    name = re.sub(r'\s*-?\s*UB\s*[\d,\s]+', '', name)
    name = re.sub(r'\s*-?\s*[\d,\s]+$', '', name)
    # Clean up extra spaces, commas, and dashes
    name = re.sub(r'\s*-\s*$', '', name)
    name = re.sub(r',+', ',', name)  # Multiple commas to single
    name = re.sub(r',\s*$', '', name)  # Trailing commas
    name = re.sub(r'\s+', ' ', name).strip()
    return name if name else Path(doc_name).stem


def extract_fields_schema_format(docx_path: str) -> Dict[str, Any]:
    """
    Extract fields in the exact format of documents/json_output/*.json files.

    Args:
        docx_path: Path to the DOCX file

    Returns:
        Dictionary matching the template.documentTypes.formFillMetadatas schema
    """
    parser = DocumentParser()
    parsed = parser.parse(docx_path)

    doc_name = Path(docx_path).name
    template_id = generate_template_id(doc_name)
    template_name = extract_template_name(doc_name)

    # Build formFillMetadatas array
    form_fill_metadatas = []
    for idx, field in enumerate(parsed.all_fields, start=1):
        # Generate IDs
        metadata_id = (template_id * 10000) + idx
        form_tag_id = (template_id * 100) + idx

        form_fill_metadatas.append({
            "id": metadata_id,
            "mandatory": field.is_mandatory,
            "formTag": {
                "id": form_tag_id,
                "name": field.name,
                "type": field.field_type.value
            }
        })

    # Build the complete schema structure
    schema = {
        "template": {
            "id": template_id,
            "templateName": template_name,
            "key": f"TMPTS{template_id:05d}",
            "companyCode": "ubgroup",
            "documentTypes": [
                {
                    "id": template_id * 10,
                    "documentType": f"{template_name} Process",
                    "formFillMetadatas": form_fill_metadatas
                }
            ]
        }
    }

    return schema


def process_document(docx_path: str, output_dir: str = "output/schema_format") -> str:
    """
    Process a single document and save the output in schema format.

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

    # Extract fields in schema format
    schema = extract_fields_schema_format(str(docx_path_obj))

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate output filename matching the pattern: <id>-schema.json
    template_id = schema['template']['id']
    output_file = output_path / f"{template_id}-schema.json"

    # Save output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    num_fields = len(schema['template']['documentTypes'][0]['formFillMetadatas'])
    print(f"  ✓ Extracted {num_fields} fields")
    print(f"  ✓ Template ID: {template_id}")
    print(f"  ✓ Saved to: {output_file}")

    return str(output_file)


def process_all_documents(
    input_dir: str = "documents",
    output_dir: str = "output/schema_format",
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
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "output/schema_format"
        process_document(docx_path, output_dir)
    else:
        # Process all documents in the documents directory
        output_files = process_all_documents()

        if output_files:
            print("=" * 60)
            print(f"Successfully processed {len(output_files)} document(s)")
            print(f"Output saved to: output/schema_format/")


if __name__ == "__main__":
    main()
