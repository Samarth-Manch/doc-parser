"""
Verify that sections 4.4, 4.5.1, and 4.5.2 each contain a
properly structured field-level table.
"""

from docx import Document
from models import TableCheckResult
from .doc_utils import (
    REQUIRED_SECTIONS,
    find_section_heading_index,
    find_heading_by_number,
    paragraph_position,
    next_heading_position,
    tables_in_section,
    is_field_table,
)


def check_table_existence(doc: Document) -> list[TableCheckResult]:
    """Verify sections 4.4, 4.5.1, and 4.5.2 each contain a proper field-level table."""
    results = []

    for section_num, section_heading in REQUIRED_SECTIONS:
        heading_idx = find_section_heading_index(doc, section_heading)

        if heading_idx is None:
            heading_idx = find_heading_by_number(doc, section_num)

        # Section 4.4 missing is an error; 4.5.1/4.5.2 missing is a warning
        missing_status = "FAIL" if section_num == "4.4" else "WARNING"

        if heading_idx is None:
            results.append(TableCheckResult(
                status=missing_status,
                section=section_num,
                message=f"Section '{section_num}' not found in document.",
                details="Expected a heading containing this section number.",
                suggestion=f"Please add section {section_num} to the document.",
            ))
            continue

        tables      = tables_in_section(doc, doc.paragraphs[heading_idx].text)
        field_tables = [t for t in tables if is_field_table(t)]

        if not tables:
            # Check whether the section is explicitly marked Not Applicable
            start_pos    = paragraph_position(doc, heading_idx)
            end_pos      = next_heading_position(doc, heading_idx)
            section_text = ""
            body         = list(doc.element.body)

            for para in doc.paragraphs[heading_idx + 1:]:
                if body.index(para._element) >= end_pos:
                    break
                section_text += para.text.strip() + " "

            if "not applicable" in section_text.lower():
                results.append(TableCheckResult(
                    status="INFO",
                    section=section_num,
                    message=f"Section '{section_num}' is marked 'Not Applicable' — no table expected.",
                    details=f"Heading: '{doc.paragraphs[heading_idx].text.strip()}'",
                    suggestion="No changes needed.",
                ))
            else:
                results.append(TableCheckResult(
                    status=missing_status,
                    section=section_num,
                    message=f"Section '{section_num}' exists but contains no tables.",
                    details=f"Heading: '{doc.paragraphs[heading_idx].text.strip()}'",
                    suggestion='Please add a table to this section, or mark it as "Not Applicable" if it does not apply.',
                ))

        elif not field_tables:
            results.append(TableCheckResult(
                status="WARNING",
                section=section_num,
                message=(
                    f"Section '{section_num}' has {len(tables)} table(s) "
                    f"but none match the expected field-table structure."
                ),
                details="Expected columns: 'Field Name', 'Field Type', 'Mandatory', 'Logic'",
                suggestion="Please rewrite the table using the standard column layout: Field Name, Field Type, Mandatory, Logic.",
            ))

        else:
            for ft in field_tables:
                row_count = len(ft.rows) - 1
                if row_count < 1:
                    results.append(TableCheckResult(
                        status="WARNING",
                        section=section_num,
                        message=f"Section '{section_num}' has an empty field table (header row only).",
                        details="Table has no data rows.",
                        suggestion='Please add fields to the table, or mark the section as "Not Applicable" if it does not apply.',
                    ))
                else:
                    results.append(TableCheckResult(
                        status="PASS",
                        section=section_num,
                        message=f"Field table found with {row_count} row(s).",
                        details="",
                        suggestion="No changes needed.",
                    ))

    return results


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class TableFormattingValidator(BaseValidator):
    name = "Validate Table Consistency"
    sheet_name = "Table Formatting"
    description = "Verifies that sections 4.4, 4.5.1, and 4.5.2 each contain a properly structured field-level table."

    def validate(self, ctx: ValidationContext) -> list[TableCheckResult]:
        return check_table_existence(ctx.doc)

    def write_sheet(self, wb: Workbook, results: list[TableCheckResult]) -> None:
        ws = wb.active
        ws.title = self.sheet_name
        headers = ["Section", "Message", "Details", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.section)
            ws.cell(row=i, column=2, value=r.message)
            ws.cell(row=i, column=3, value=r.details)
            ws.cell(row=i, column=4, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=4), r.status)
            ws.cell(row=i, column=5, value=r.suggestion)

        if not results:
            write_pass_row(ws, 2, len(headers), "PASS - All sections have valid tables.")

        auto_width(ws)
