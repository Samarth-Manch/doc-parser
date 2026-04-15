"""
bud_validator.py
Parses the document and runs all registered validators,
then writes results to Excel and HTML reports.
"""

import os
import sys

from document_reader import parse_document
from validators import ValidatorRegistry, ValidationContext
from excel_writer import write_validation_report
from html_writer import write_html_report

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_output")
EXCEL_DIR = os.path.join(OUTPUT_DIR, "excel_output")
HTML_DIR = os.path.join(OUTPUT_DIR, "html_output")
DEFAULT_FILE = "Vendor Creation Sample BUD 3.docx"


def validate_bud(file_path: str) -> None:
    master_fields, sub_tables, raw_fields, doc = parse_document(file_path)
    print("Document Parsed Successfully.")

    ctx = ValidationContext(
        master_fields=master_fields,
        sub_tables=sub_tables,
        raw_fields=raw_fields,
        doc=doc,
    )

    # Run all registered validators
    results = ValidatorRegistry.run_all(ctx)

    # Ensure output directories exist
    os.makedirs(EXCEL_DIR, exist_ok=True)
    os.makedirs(HTML_DIR, exist_ok=True)

    base = os.path.splitext(os.path.basename(file_path))[0]

    # Write Excel report
    excel_path = os.path.join(EXCEL_DIR, f"{base}_validation.xlsx")
    write_validation_report(excel_path, results)
    print(f"Excel report written to: {excel_path}")

    # Write HTML report
    html_path = os.path.join(HTML_DIR, f"{base}_validation.html")
    write_html_report(html_path, results, doc_name=base)
    print(f"HTML report written to: {html_path}")


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    validate_bud(file_path)
