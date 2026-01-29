#!/usr/bin/env python3
"""
Section-by-section document iterator for BUD documents.

This script allows Claude Code skills to iterate through document sections
one at a time to reduce context load when processing large documents.

Usage:
    python get_section_by_index.py <document_path> <section_index>
    python get_section_by_index.py <document_path> --count
    python get_section_by_index.py <document_path> --list
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from doc_parser.parser import DocumentParser
from doc_parser.models import Section


class SectionIterator:
    """Iterator for document sections that handles nested subsections."""

    def __init__(self, document_path: str):
        """
        Initialize the iterator with a document.

        Args:
            document_path: Path to the .docx document
        """
        self.document_path = document_path
        self.parser = DocumentParser()
        self.parsed_doc = None
        self.flattened_sections = []

    def parse(self):
        """Parse the document and flatten the section hierarchy."""
        print(f"Parsing document: {self.document_path}", file=sys.stderr)

        # Redirect stdout to stderr during parsing to avoid polluting JSON output
        import io
        import contextlib

        # Save original stdout
        original_stdout = sys.stdout

        try:
            # Redirect stdout to stderr during parsing
            sys.stdout = sys.stderr
            self.parsed_doc = self.parser.parse(self.document_path)
        finally:
            # Restore original stdout
            sys.stdout = original_stdout

        self.flattened_sections = self._flatten_sections(self.parsed_doc.sections)
        print(f"Found {len(self.flattened_sections)} sections (including subsections)", file=sys.stderr)

    def _flatten_sections(self, sections: List[Section], parent_path: str = "") -> List[Dict[str, Any]]:
        """
        Recursively flatten section hierarchy into a list.

        Args:
            sections: List of Section objects
            parent_path: Parent section path (e.g., "1.1")

        Returns:
            List of dictionaries containing flattened section data
        """
        flattened = []

        for section in sections:
            # Create section entry
            section_data = {
                "heading": section.heading,
                "level": section.level,
                "content": section.content,
                "tables": [table.to_dict() for table in section.tables],
                "fields": [field.to_dict() for field in section.fields],
                "workflow_steps": [step.to_dict() for step in section.workflow_steps],
                "parent_path": parent_path,
                "has_subsections": len(section.subsections) > 0,
                "subsection_count": len(section.subsections)
            }

            flattened.append(section_data)

            # Recursively flatten subsections
            if section.subsections:
                subsection_path = section.heading if not parent_path else f"{parent_path} > {section.heading}"
                flattened.extend(self._flatten_sections(section.subsections, subsection_path))

        return flattened

    def get_section_count(self) -> int:
        """Get total number of sections (including subsections)."""
        if not self.flattened_sections:
            self.parse()
        return len(self.flattened_sections)

    def get_section_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get a section by its index.

        Args:
            index: Zero-based index of the section

        Returns:
            Dictionary containing section data or None if index is out of range
        """
        if not self.flattened_sections:
            self.parse()

        if 0 <= index < len(self.flattened_sections):
            section = self.flattened_sections[index].copy()
            section["index"] = index
            section["total_sections"] = len(self.flattened_sections)
            return section
        else:
            return None

    def list_sections(self) -> List[Dict[str, str]]:
        """
        Get a list of all sections with their indices and headings.

        Returns:
            List of dictionaries with index, heading, and level
        """
        if not self.flattened_sections:
            self.parse()

        return [
            {
                "index": i,
                "heading": section["heading"],
                "level": section["level"],
                "parent_path": section["parent_path"],
                "content_length": len(" ".join(section["content"])),
                "table_count": len(section["tables"]),
                "field_count": len(section["fields"])
            }
            for i, section in enumerate(self.flattened_sections)
        ]


def main():
    """Main entry point for CLI usage."""
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  python get_section_by_index.py <document_path> <section_index>", file=sys.stderr)
        print("  python get_section_by_index.py <document_path> --count", file=sys.stderr)
        print("  python get_section_by_index.py <document_path> --list", file=sys.stderr)
        sys.exit(1)

    document_path = sys.argv[1]

    # Validate document exists
    if not Path(document_path).exists():
        print(f"Error: Document not found: {document_path}", file=sys.stderr)
        sys.exit(1)

    # Create iterator
    iterator = SectionIterator(document_path)

    # Handle different commands
    if len(sys.argv) == 2:
        print("Error: Missing argument. Use --count, --list, or provide section index", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[2]

    if command == "--count":
        # Return total section count
        count = iterator.get_section_count()
        result = {
            "document": document_path,
            "total_sections": count
        }
        print(json.dumps(result, indent=2))

    elif command == "--list":
        # Return list of all sections
        sections = iterator.list_sections()
        result = {
            "document": document_path,
            "total_sections": len(sections),
            "sections": sections
        }
        print(json.dumps(result, indent=2))

    else:
        # Get specific section by index
        try:
            index = int(command)
        except ValueError:
            print(f"Error: Invalid section index: {command}", file=sys.stderr)
            sys.exit(1)

        section = iterator.get_section_by_index(index)

        if section is None:
            print(f"Error: Section index {index} out of range (0-{iterator.get_section_count()-1})", file=sys.stderr)
            sys.exit(1)

        # Output section data as JSON
        result = {
            "document": document_path,
            "section": section
        }
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
