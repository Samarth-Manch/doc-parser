"""
Quick test to verify Excel file extraction from DOCX
"""

from doc_parser.parser import DocumentParser
from pathlib import Path

def test_excel_extraction():
    """Test Excel extraction on available documents"""
    parser = DocumentParser()

    # Test documents
    test_docs = [
        "documents/Vendor Creation Sample BUD(1).docx",
        "documents/Outlet_KYC _UB_3334.docx",
    ]

    for doc_path in test_docs:
        if not Path(doc_path).exists():
            print(f"Skipping {doc_path} - file not found")
            continue

        print(f"\n{'='*80}")
        print(f"Testing: {Path(doc_path).name}")
        print(f"{'='*80}")

        try:
            # Parse the document
            result = parser.parse(doc_path)

            # Count tables by source
            word_tables = [t for t in result.reference_tables if t.source == "document"]
            excel_tables = [t for t in result.reference_tables if t.source == "excel"]

            print(f"\nReference Tables Summary:")
            print(f"  Total reference tables: {len(result.reference_tables)}")
            print(f"  From Word document: {len(word_tables)}")
            print(f"  From Excel files: {len(excel_tables)}")

            # Show Excel table details
            if excel_tables:
                print(f"\nExcel Tables Found:")
                for i, table in enumerate(excel_tables, 1):
                    print(f"\n  Table {i}:")
                    print(f"    Source File: {table.source_file}")
                    print(f"    Sheet: {table.sheet_name}")
                    print(f"    Size: {table.row_count} rows × {table.column_count} columns")
                    print(f"    Headers: {table.headers[:5]}...")  # Show first 5 headers
            else:
                print(f"\n  ℹ No embedded Excel files found in this document")

            print(f"\n✓ Test completed successfully for {Path(doc_path).name}")

        except Exception as e:
            print(f"\n✗ Error testing {Path(doc_path).name}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_excel_extraction()
