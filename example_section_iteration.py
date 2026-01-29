#!/usr/bin/env python3
"""
Example script demonstrating section-by-section processing of BUD documents.

This shows how Claude Code skills can use get_section_by_index.py to
process large documents incrementally, reducing context load.
"""

import json
import sys
from pathlib import Path

# Import the SectionIterator class directly for efficiency
from get_section_by_index import SectionIterator


def extract_notes_from_section(section: dict) -> list:
    """
    Extract implementation notes from a section.

    This is a simplified example - in real usage, you would:
    - Use Claude API to analyze the content
    - Apply more sophisticated rule extraction logic
    - Handle different types of rules and notes
    """
    notes = []

    # Look for paragraphs containing "Note" or other keywords
    keywords = ["Note", "note", "Important", "IMPORTANT", "Rule", "rule"]

    for paragraph in section["content"]:
        if any(keyword in paragraph for keyword in keywords):
            notes.append({
                "section_name": section["heading"],
                "section_level": section["level"],
                "parent_path": section["parent_path"],
                "rule_type": "implementation_note",
                "text": paragraph,
                "index": section["index"]
            })

    return notes


def process_document_by_sections(document_path: str, output_file: str = None):
    """
    Process a BUD document section by section and extract notes.

    Args:
        document_path: Path to the .docx document
        output_file: Optional path to save results (JSON)
    """
    print(f"Processing document: {document_path}")
    print("-" * 70)

    # Step 1: Initialize iterator and parse document once
    print("\nStep 1: Parsing document...")
    iterator = SectionIterator(document_path)
    iterator.parse()
    total_sections = iterator.get_section_count()
    print(f"Found {total_sections} sections (including subsections)")

    # Step 2: Get section overview
    print("\nStep 2: Getting section overview...")
    sections = iterator.list_sections()

    # Print section summary
    print(f"\nDocument structure:")
    for section in sections[:10]:  # Show first 10
        indent = "  " * (section["level"] - 1)
        print(f"  {section['index']:2d}. {indent}{section['heading']}")
    if len(sections) > 10:
        print(f"  ... and {len(sections) - 10} more sections")

    # Step 3: Process each section
    print(f"\nStep 3: Processing sections...")
    all_notes = []

    for i in range(total_sections):
        # Progress indicator
        print(f"  [{i+1}/{total_sections}] ", end="", flush=True)

        # Get section data (no re-parsing needed!)
        section = iterator.get_section_by_index(i)

        # Extract notes from this section
        notes = extract_notes_from_section(section)

        if notes:
            print(f"✓ {section['heading']}: Found {len(notes)} note(s)")
            all_notes.extend(notes)
        else:
            print(f"○ {section['heading']}: No notes")

    # Step 4: Display results
    print(f"\n{'-' * 70}")
    print(f"\nExtraction complete!")
    print(f"Total sections processed: {total_sections}")
    print(f"Total notes extracted: {len(all_notes)}")

    if all_notes:
        print(f"\nExtracted notes by section:")
        current_section = None
        for note in all_notes:
            if note["section_name"] != current_section:
                current_section = note["section_name"]
                print(f"\n{note['section_name']}:")
            print(f"  • {note['text'][:100]}{'...' if len(note['text']) > 100 else ''}")

    # Step 5: Save to file if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            "document": document_path,
            "total_sections": total_sections,
            "notes_extracted": len(all_notes),
            "notes": all_notes
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\nResults saved to: {output_file}")

    return all_notes


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 example_section_iteration.py <document_path> [output_file.json]")
        print("\nExample:")
        print('  python3 example_section_iteration.py "documents/Vendor Creation Sample BUD(1).docx"')
        print('  python3 example_section_iteration.py "documents/Vendor Creation Sample BUD(1).docx" output/notes.json')
        sys.exit(1)

    document_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    # Validate document exists
    if not Path(document_path).exists():
        print(f"Error: Document not found: {document_path}", file=sys.stderr)
        sys.exit(1)

    # Process document
    process_document_by_sections(document_path, output_file)


if __name__ == "__main__":
    main()
