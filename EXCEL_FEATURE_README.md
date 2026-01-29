# Excel Reference Table Extraction Feature

## Overview
The document parser now automatically extracts and displays reference tables from embedded Excel files (.xlsx) within Word documents.

## Features

### 1. Automatic Detection
- Searches for Excel files in `word/embeddings/` directory of DOCX files
- Supports `.xlsx` and `.xls` formats
- No user action required - extraction happens automatically during parsing

### 2. Multi-Sheet Support
- Extracts data from ALL sheets in each Excel file
- Each sheet becomes a separate reference table
- Sheet names are preserved and displayed

### 3. Full Data Extraction
- All rows and columns are extracted
- Headers automatically detected (first row)
- Empty rows are filtered out
- Cell values converted to strings for consistent display

### 4. GUI Display
The Tables tab in the GUI now shows:
- **Source identification**: Excel tables marked with 📊 icon, Word tables with 📄
- **Complete metadata**:
  - Excel filename
  - Sheet name
  - Row and column counts
- **Formatted table view**:
  - Professional box-drawing borders
  - Auto-calculated column widths (capped at 30 chars)
  - Up to 100 rows displayed for Excel tables
  - Clear indication of additional rows if table is larger

### 5. Statistics
The Overview tab displays:
- Total reference tables count
- Breakdown by source (Word document vs Excel files)
- Detailed extraction statistics

## Example Output

```
📊 TABLE 2: REFERENCE
   Source: EXCEL FILE - Microsoft_Excel_Worksheet1.xlsx
   Sheet: Sheet1
   Size: 246 rows × 6 columns

   ┌────────────────────────────────────────────────────────────────┐
   │ Language Key   │ Country/Region Key   │ Country/Region Name   │
   ├────────────────┼──────────────────────┼───────────────────────┤
   │ EN             │ AD                   │ Andorran              │
   │ EN             │ AE                   │ Utd.Arab Emir.        │
   │ EN             │ AF                   │ Afghanistan           │
   └────────────────────────────────────────────────────────────────┘
   Total: 246 rows displayed
```

## Test Results

### Vendor Creation Sample BUD(1).docx
- ✅ 9 embedded Excel files detected
- ✅ 9 reference tables extracted
- ✅ Tables include: Country codes (246 rows), Vendor types (27 rows), IncoTerms (99 rows), Tax codes (66 rows), Industries (154 rows), and more

### Outlet_KYC _UB_3334.docx
- ✅ 2 embedded Excel files detected
- ✅ 4 reference tables extracted (2 sheets each)
- ✅ Tables include: Audit Log (57 rows) and State Head Group approval form (6 rows)

## Technical Implementation

### Files Modified
1. **requirements.txt**: Added `openpyxl>=3.1.0`
2. **models.py**: Enhanced `TableData` with `source`, `source_file`, `sheet_name` fields
3. **parser.py**: Added `_extract_excel_reference_tables()` and `_parse_excel_sheet()` methods
4. **document_parser_gui.py**: Updated `display_tables()` and `display_overview()` for Excel table display

### Code Architecture
- **Parser**: Automatically calls Excel extraction during `_extract_reference_tables()`
- **Temporary files**: Excel files are extracted to temp files, parsed, then cleaned up
- **Error handling**: Gracefully handles missing openpyxl, corrupt files, empty sheets
- **Performance**: Efficient extraction using openpyxl's `data_only=True` mode

## Usage

### Running the GUI
```bash
python3 document_parser_gui.py
```

### Programmatic Access
```python
from doc_parser.parser import DocumentParser

parser = DocumentParser()
result = parser.parse("document.docx")

# Access Excel tables
excel_tables = [t for t in result.reference_tables if t.source == "excel"]

for table in excel_tables:
    print(f"File: {table.source_file}")
    print(f"Sheet: {table.sheet_name}")
    print(f"Size: {table.row_count} x {table.column_count}")
    print(f"Data: {table.rows}")
```

## Dependencies

Install required package:
```bash
pip install openpyxl
# or
python3 -m pip install --break-system-packages openpyxl
```

## Known Limitations
1. Only supports `.xlsx` and `.xls` files (not `.xlsm` macros)
2. Formulas are evaluated to values (not preserved as formulas)
3. Formatting (colors, fonts) is not extracted, only data
4. Very wide tables (>10 columns) may wrap in the GUI display
5. Column width is capped at 30 characters for readability

## Future Enhancements
- Export Excel tables to separate Excel files
- Filter/search within Excel table data
- Support for linked (not embedded) Excel files
- Preserve cell formatting and styles
