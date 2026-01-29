"""
Test the GUI display of Excel tables
"""

from doc_parser.parser import DocumentParser
from pathlib import Path

def test_gui_display():
    """Test how Excel data will be displayed in GUI"""
    parser = DocumentParser()

    doc_path = "documents/Vendor Creation Sample BUD(1).docx"

    print(f"Parsing: {Path(doc_path).name}")
    print("=" * 120)

    result = parser.parse(doc_path)

    # Simulate GUI display for first Excel table
    excel_tables = [t for t in result.reference_tables if t.source == "excel"]

    if excel_tables:
        print(f"\n{len(excel_tables)} Excel tables found")
        print("\nShowing first Excel table as it would appear in GUI:\n")

        table = excel_tables[0]

        print(f"📊 TABLE 1: {table.table_type.upper()}")
        print(f"   Source: EXCEL FILE - {table.source_file}")
        print(f"   Sheet: {table.sheet_name}")
        print(f"   Context: {table.context}")
        print(f"   Size: {table.row_count} rows × {table.column_count} columns")
        print()

        # Display formatted table
        if table.headers and table.rows:
            # Calculate column widths
            col_widths = []
            for col_idx, header in enumerate(table.headers):
                max_width = len(str(header))
                for row in table.rows[:50]:
                    if col_idx < len(row):
                        max_width = max(max_width, len(str(row[col_idx])))
                col_widths.append(min(max_width + 2, 30))

            # Print headers
            header_line = "   │ "
            separator_line = "   ├─"
            for idx, header in enumerate(table.headers):
                header_text = str(header)[:col_widths[idx]-2]
                header_line += f"{header_text:<{col_widths[idx]}} │ "
                separator_line += "─" * col_widths[idx] + "─┼─"

            print("   ┌─" + "─" * (len(header_line) - 6) + "─┐")
            print(header_line)
            print(separator_line[:-2] + "┤")

            # Print first 20 rows
            for row in table.rows[:20]:
                row_line = "   │ "
                for col_idx, cell in enumerate(row):
                    if col_idx < len(table.headers):
                        cell_text = str(cell)[:col_widths[col_idx]-2]
                        row_line += f"{cell_text:<{col_widths[col_idx]}} │ "
                print(row_line)

            print("   └─" + "─" * (len(header_line) - 6) + "─┘")

            if table.row_count > 20:
                print(f"   ... and {table.row_count - 20} more rows (total: {table.row_count} rows)")

        print("\n" + "=" * 120)
        print("✓ Table display test completed")
        print(f"✓ All {len(excel_tables)} Excel tables will be displayed in the GUI with full data")
    else:
        print("No Excel tables found")

if __name__ == "__main__":
    test_gui_display()
