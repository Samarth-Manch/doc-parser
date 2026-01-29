#!/usr/bin/env python3
"""
Display All Sections - Comprehensive Section Iterator Output
This script uses SectionIterator to display all content from a document in a well-formatted way.
"""

from get_section_by_index import SectionIterator
from datetime import datetime
import json
import sys


def format_content(content):
    """Convert content (string or list) to formatted string."""
    if isinstance(content, list):
        return '\n'.join(str(item) for item in content if item)
    elif isinstance(content, str):
        return content
    else:
        return str(content)


def display_table(table, table_num):
    """Display table data in a formatted way."""
    print(f"\n  📊 Table {table_num}")
    print("  " + "-" * 76)

    if isinstance(table, dict):
        rows = table.get('rows', [])
        print(f"  Structure: Dictionary with {len(rows)} rows")

        if rows:
            # Display first row as header if it looks like headers
            first_row = rows[0]

            if isinstance(first_row, dict):
                # Dictionary rows
                headers = list(first_row.keys())
                print(f"  Columns: {', '.join(headers)}")
                print()

                # Display data
                for idx, row in enumerate(rows[:10], 1):  # Show first 10 rows
                    print(f"  Row {idx}:")
                    for key, value in row.items():
                        if value:  # Only show non-empty values
                            print(f"    • {key}: {str(value)[:80]}")
                    if idx < len(rows):
                        print()

                if len(rows) > 10:
                    print(f"  ... and {len(rows) - 10} more rows")

            elif isinstance(first_row, list):
                # List rows
                print(f"  Columns: {len(first_row)}")
                print()

                for idx, row in enumerate(rows[:10], 1):  # Show first 10 rows
                    print(f"  Row {idx}: {' | '.join(str(cell)[:30] for cell in row)}")

                if len(rows) > 10:
                    print(f"  ... and {len(rows) - 10} more rows")

    elif isinstance(table, list):
        print(f"  Structure: List with {len(table)} rows")
        print()

        for idx, row in enumerate(table[:10], 1):  # Show first 10 rows
            if isinstance(row, dict):
                print(f"  Row {idx}:")
                for key, value in row.items():
                    if value:
                        print(f"    • {key}: {str(value)[:80]}")
            elif isinstance(row, list):
                print(f"  Row {idx}: {' | '.join(str(cell)[:30] for cell in row)}")
            else:
                print(f"  Row {idx}: {str(row)[:80]}")

            if idx < min(len(table), 10):
                print()

        if len(table) > 10:
            print(f"  ... and {len(table) - 10} more rows")

    print("  " + "-" * 76)


def display_section(section, section_num, total_sections):
    """Display a single section with all its content."""

    # Section header
    print("\n" + "=" * 80)
    print(f"SECTION {section_num}/{total_sections}")
    print("=" * 80)

    # Metadata
    print(f"📍 Index: {section.get('index', 'N/A')}")
    print(f"📝 Heading: {section.get('heading', 'NO HEADING')}")
    print(f"🔢 Level: {section.get('level', 'N/A')}")

    parent_path = section.get('parent_path', '')
    if parent_path:
        print(f"📂 Parent Path: {parent_path}")
    else:
        print(f"📂 Parent Path: (root)")

    print("-" * 80)

    # Content
    content = section.get('content', '')
    content_str = format_content(content)

    print(f"📄 Content:")
    print()

    if content_str.strip():
        # Display content with proper indentation
        content_lines = content_str.split('\n')
        for line in content_lines:
            if line.strip():
                print(f"  {line}")
            else:
                print()
    else:
        print("  [NO CONTENT]")

    # Tables
    tables = section.get('tables', [])

    if tables:
        print()
        print("-" * 80)
        print(f"📊 Tables in this section: {len(tables)}")

        for table_idx, table in enumerate(tables, 1):
            display_table(table, table_idx)
    else:
        print()
        print("-" * 80)
        print("📊 Tables: None")

    print()


def main():
    """Main function to display all sections from a document."""

    # Check if document path is provided
    if len(sys.argv) > 1:
        document_path = sys.argv[1]
    else:
        # Default document
        document_path = "extraction/Outlet_KYC _UB_3334.docx"

    print("=" * 80)
    print("COMPLETE SECTION DISPLAY")
    print("=" * 80)
    print(f"📁 Document: {document_path}")
    print(f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Initialize SectionIterator
    print("\n🔄 Initializing SectionIterator...")
    try:
        iterator = SectionIterator(document_path)
        iterator.parse()
        print("✓ Document parsed successfully")
    except Exception as e:
        print(f"✗ Error parsing document: {e}")
        return 1

    # Get total sections
    total_sections = iterator.get_section_count()
    print(f"✓ Found {total_sections} sections")

    # Display each section
    for section_index in range(total_sections):
        section = iterator.get_section_by_index(section_index)
        display_section(section, section_index + 1, total_sections)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Count sections by level
    level_counts = {}
    sections_with_content = 0
    sections_with_tables = 0
    total_content_length = 0

    for idx in range(total_sections):
        section = iterator.get_section_by_index(idx)

        # Level count
        level = section.get('level', 'Unknown')
        level_counts[level] = level_counts.get(level, 0) + 1

        # Content analysis
        content = section.get('content', '')
        content_str = format_content(content)

        if content_str.strip():
            sections_with_content += 1
            total_content_length += len(content_str)

        # Table analysis
        if section.get('tables'):
            sections_with_tables += 1

    print(f"📊 Total Sections: {total_sections}")
    print()

    print("Sections by Level:")
    for level in sorted(level_counts.keys()):
        print(f"  • Level {level}: {level_counts[level]} section(s)")
    print()

    print(f"📝 Sections with content: {sections_with_content}/{total_sections}")
    print(f"📊 Sections with tables: {sections_with_tables}/{total_sections}")
    print(f"📏 Total content length: {total_content_length:,} characters")
    print()

    print("=" * 80)
    print("✓ Display completed successfully")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
