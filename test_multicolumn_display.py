"""
Test multi-column Excel table display
"""

from doc_parser.parser import DocumentParser
from pathlib import Path

def test_multicolumn_display():
    """Test display of multi-column Excel table"""
    parser = DocumentParser()

    doc_path = "documents/Vendor Creation Sample BUD(1).docx"

    print(f"Parsing: {Path(doc_path).name}\n")

    result = parser.parse(doc_path)

    # Find a multi-column Excel table
    excel_tables = [t for t in result.reference_tables if t.source == "excel"]

    # Show the country table (table with 6 columns)
    for table in excel_tables:
        if table.column_count >= 5:
            print(f"📊 TABLE: {table.table_type.upper()}")
            print(f"   Source: EXCEL FILE - {table.source_file}")
            print(f"   Sheet: {table.sheet_name}")
            print(f"   Size: {table.row_count} rows × {table.column_count} columns")
            print()

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

                # Print first 15 rows
                for row in table.rows[:15]:
                    row_line = "   │ "
                    for col_idx, cell in enumerate(row):
                        if col_idx < len(table.headers):
                            cell_text = str(cell)[:col_widths[col_idx]-2]
                            row_line += f"{cell_text:<{col_widths[col_idx]}} │ "
                    print(row_line)

                print("   └─" + "─" * (len(header_line) - 6) + "─┘")

                if table.row_count > 15:
                    print(f"   ... and {table.row_count - 15} more rows (total: {table.row_count} rows)")

            print("\n" + "=" * 120)
            break  # Show just one example

if __name__ == "__main__":
    test_multicolumn_display()
