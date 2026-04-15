"""
Checks that fields marked as non-editable in the Logic column of sections
4.4, 4.5.1, and 4.5.2 have their Field Type set to "TEXT".
"""

from docx import Document
from models import NonEditableCheckResult
from .doc_utils import (
    get_column_index,
    iter_field_tables,
)


NON_EDITABLE_PHRASES = [
    "always non editable",
    "always non-editable",
    "non-editable",
    "non editable",
]

ALLOWED_NON_EDITABLE_TYPES = {"TEXT", "DATE"}


def _check_tables_for_section(
    section: str, field_tables: list,
) -> list[NonEditableCheckResult]:
    """Check non-editable fields in the given tables for one section."""
    results: list[NonEditableCheckResult] = []

    for table in field_tables:
        headers = [cell.text.strip().lower() for cell in table.rows[0].cells]

        logic_col = get_column_index(headers, "logic")
        type_col = get_column_index(headers, "type", "field type")
        name_col = get_column_index(headers, "field name", "filed name")

        if logic_col is None or type_col is None:
            continue

        for r_idx, row in enumerate(table.rows[1:], start=2):
            logic_text = row.cells[logic_col].text.strip()
            logic_lower = logic_text.lower()
            field_type = row.cells[type_col].text.strip()
            field_name = row.cells[name_col].text.strip() if name_col is not None else "Unknown"

            if not logic_text or not field_type:
                continue

            matched_phrase = None
            for phrase in NON_EDITABLE_PHRASES:
                if phrase in logic_lower:
                    matched_phrase = phrase
                    break

            if matched_phrase and field_type.upper() not in ALLOWED_NON_EDITABLE_TYPES:
                results.append(NonEditableCheckResult(
                    section=section,
                    field_name=field_name[:50],
                    field_type=field_type,
                    status="FAIL",
                    suggestion=f"{field_type} cannot be non-editable, make sure that field should not be non-editable.",
                ))

    return results


def validate_non_editable_fields(doc: Document) -> list[NonEditableCheckResult]:
    """Check that non-editable fields in sections 4.4, 4.5.1, 4.5.2 have Field Type = TEXT."""
    results: list[NonEditableCheckResult] = []

    for section_key, field_tables in iter_field_tables(doc):
        results.extend(_check_tables_for_section(section_key, field_tables))

    return results


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class NonEditableValidator(BaseValidator):
    name = "Validate Non-Editable Field Types"
    sheet_name = "Non-Editable Check"
    description = "Verifies that fields marked as non-editable have their Field Type set to TEXT."

    def validate(self, ctx: ValidationContext) -> list[NonEditableCheckResult]:
        return validate_non_editable_fields(ctx.doc)

    def write_sheet(self, wb: Workbook, results: list[NonEditableCheckResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Section", "Field Name", "Field Type", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.section)
            ws.cell(row=i, column=2, value=r.field_name)
            ws.cell(row=i, column=3, value=r.field_type)
            ws.cell(row=i, column=4, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=4), r.status)
            ws.cell(row=i, column=5, value=r.suggestion)

        if not results:
            write_pass_row(ws, 2, len(headers), "PASS - All non-editable fields have type TEXT.")

        auto_width(ws)
