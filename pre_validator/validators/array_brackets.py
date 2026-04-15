"""
Checks that ARRAY_HEADER (or ARRAY_HDR) and ARRAY_END in the Field Type
column of sections 4.4, 4.5.1, and 4.5.2 are properly paired.
"""

from docx import Document
from models import ArrayBracketCheckResult
from .doc_utils import (
    get_column_index,
    iter_field_tables,
)


OPEN_TOKENS = {"ARRAY_HEADER", "ARRAY_HDR"}
CLOSE_TOKEN = "ARRAY_END"


def _check_brackets_in_tables(
    section: str, field_tables: list,
) -> list[ArrayBracketCheckResult]:
    """Validate ARRAY_HEADER/ARRAY_END pairing in the given tables."""
    results: list[ArrayBracketCheckResult] = []

    for table in field_tables:
        headers = [c.text.strip().lower() for c in table.rows[0].cells]

        type_col = get_column_index(headers, "field type", "type")
        name_col = get_column_index(headers, "field name", "filed name")

        if type_col is None:
            continue

        depth = 0
        open_row = None
        open_field = None

        for r_idx, row in enumerate(table.rows[1:], start=2):
            field_type = row.cells[type_col].text.strip().upper()
            field_name = (
                row.cells[name_col].text.strip() if name_col is not None else f"Row {r_idx}"
            )

            if field_type in OPEN_TOKENS:
                if depth >= 1:
                    results.append(ArrayBracketCheckResult(
                        section=section,
                        status="FAIL",
                        field_name=field_name,
                        row=r_idx,
                        message=f"Nested {field_type} before closing previous array",
                        details=(
                            f"ARRAY_HEADER opened at row {open_row} "
                            f"(Field: '{open_field}') but no ARRAY_END before "
                            f"this {field_type}. Nesting depth must not exceed 1."
                        ),
                        suggestion="Please close the previous array with ARRAY_END before opening a new one.",
                    ))
                depth += 1
                open_row = r_idx
                open_field = field_name

            elif field_type == CLOSE_TOKEN:
                if depth == 0:
                    results.append(ArrayBracketCheckResult(
                        section=section,
                        status="FAIL",
                        field_name=field_name,
                        row=r_idx,
                        message="ARRAY_END without a preceding ARRAY_HEADER",
                        details=(
                            f"Found ARRAY_END but no ARRAY_HEADER / ARRAY_HDR "
                            f"was opened before it."
                        ),
                        suggestion="Please add the matching ARRAY_HDR before this ARRAY_END, or remove this ARRAY_END.",
                    ))
                else:
                    # Check name mismatch between ARRAY_HEADER and ARRAY_END
                    if open_field and field_name and open_field.strip().lower() != field_name.strip().lower():
                        results.append(ArrayBracketCheckResult(
                            section=section,
                            status="FAIL",
                            field_name=field_name,
                            row=r_idx,
                            message="ARRAY_END field name does not match opening ARRAY_HEADER",
                            details=(
                                f"Opening ARRAY_HEADER at row {open_row} has field name "
                                f"'{open_field}' but this ARRAY_END has field name '{field_name}'."
                            ),
                            suggestion="Please make sure ARRAY_END has the same field name as its matching ARRAY_HDR.",
                        ))
                    depth -= 1
                    open_row = None
                    open_field = None

        if depth > 0:
            results.append(ArrayBracketCheckResult(
                section=section,
                status="FAIL",
                field_name=open_field or "",
                row=open_row or 0,
                message="Unclosed ARRAY_HEADER — missing ARRAY_END",
                details=(
                    f"ARRAY_HEADER opened at row {open_row} "
                    f"(Field: '{open_field}') was never closed with ARRAY_END."
                ),
                suggestion="Please add the matching ARRAY_END to close this ARRAY_HDR.",
            ))

    return results


def validate_array_brackets(doc: Document) -> list[ArrayBracketCheckResult]:
    """Check ARRAY_HEADER/ARRAY_END pairing in sections 4.4, 4.5.1, 4.5.2."""
    results: list[ArrayBracketCheckResult] = []

    for section_key, field_tables in iter_field_tables(doc):
        results.extend(_check_brackets_in_tables(section_key, field_tables))

    return results


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class ArrayBracketValidator(BaseValidator):
    name = "Validate Array Bracket Pairing"
    sheet_name = "Array Bracket Check"
    description = "Checks that ARRAY_HEADER and ARRAY_END markers in the Field Type column are properly paired."

    def validate(self, ctx: ValidationContext) -> list[ArrayBracketCheckResult]:
        return validate_array_brackets(ctx.doc)

    def write_sheet(self, wb: Workbook, results: list[ArrayBracketCheckResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Section", "Field Name", "Row", "Message", "Details", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.section)
            ws.cell(row=i, column=2, value=r.field_name)
            ws.cell(row=i, column=3, value=r.row)
            ws.cell(row=i, column=4, value=r.message)
            ws.cell(row=i, column=5, value=r.details)
            ws.cell(row=i, column=6, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=6), r.status)
            ws.cell(row=i, column=7, value=r.suggestion)

        if not results:
            write_pass_row(ws, 2, len(headers), "PASS - All ARRAY_HEADER/ARRAY_END pairs are properly matched.")

        auto_width(ws)
