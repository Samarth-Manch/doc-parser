"""
Every field name must be unique within each panel of each table.
A panel is defined by a row whose type column is PANEL.
"""

from collections import Counter, defaultdict
from models import FieldUniquenessResult, FieldDuplicateRow, PanelUniquenessRow
from .doc_utils import group_fields_by_panel


# Field types that denote ARRAY boundary markers. Duplicates across these
# pairs are expected (e.g. one ARRAY_HDR + one ARRAY_END with the same name)
# and should not be flagged.
_ARRAY_BOUNDARY_TYPES = {"ARRAY_HDR", "ARRAY_END", "ARRAY HEADER", "ARRAY END"}


def _is_array_type(field) -> bool:
    """Return True if the field's raw type is an ARRAY boundary marker."""
    raw = getattr(field, "field_type_raw", None)
    if not raw:
        return False
    return raw.strip().upper() in _ARRAY_BOUNDARY_TYPES


def _find_duplicates(fields: list) -> list[str]:
    """Return field names that appear more than once.

    Duplicates where every occurrence is an ARRAY boundary marker
    (ARRAY_HDR / ARRAY_END / ARRAY HEADER / ARRAY END) are excluded,
    since those are expected pairs. If even one occurrence is a
    non-array type, the duplicate is still flagged.
    """
    grouped: dict[str, list] = defaultdict(list)
    for f in fields:
        name = (f.name or "").strip().lower()
        if not name:
            continue
        grouped[name].append(f)

    duplicates = []
    for name, occurrences in grouped.items():
        if len(occurrences) <= 1:
            continue
        if all(_is_array_type(f) for f in occurrences):
            continue
        duplicates.append(name)
    return sorted(duplicates)


def _find_duplicate_panels(fields: list) -> set[str]:
    """Return panel names that appear more than once in a section."""
    panel_names = [
        (f.name or "").strip().lower()
        for f in fields
        if hasattr(f, "field_type_raw") and f.field_type_raw and f.field_type_raw.strip().upper() == "PANEL"
        and (f.name or "").strip()
    ]
    return {name for name, count in Counter(panel_names).items() if count > 1}


def validate_field_uniqueness(
    all_fields: list,
    initiator_fields: list,
    spoc_fields: list,
) -> FieldUniquenessResult:
    """Check that every field name is unique within each panel independently."""
    field_duplicates: list[FieldDuplicateRow] = []
    panel_uniqueness: list[PanelUniquenessRow] = []

    for table_section, fields in [("4.4", all_fields), ("4.5.1", initiator_fields), ("4.5.2", spoc_fields)]:
        if not fields:
            field_duplicates.append(FieldDuplicateRow(
                section=table_section, panel="N/A", field_name="", status="N/A",
                suggestion="Section has no fields, no changes needed.",
            ))
            panel_uniqueness.append(PanelUniquenessRow(
                section=table_section, duplicate_panels="", status="N/A",
                suggestion="Section has no fields, no changes needed.",
            ))
            continue

        # --- Field name uniqueness (Table 1) ---
        panels = group_fields_by_panel(fields)
        for panel_name, panel_fields in panels.items():
            dupes = _find_duplicates(panel_fields)
            if dupes:
                for dup in dupes:
                    field_duplicates.append(FieldDuplicateRow(
                        section=table_section, panel=panel_name,
                        field_name=dup, status="FAIL",
                        suggestion="Please delete the duplicate field or change the field name.",
                    ))
            else:
                field_duplicates.append(FieldDuplicateRow(
                    section=table_section, panel=panel_name,
                    field_name="", status="PASS",
                    suggestion="No changes needed.",
                ))

        # --- Panel name uniqueness (Table 2) ---
        dup_panels = _find_duplicate_panels(fields)
        if dup_panels:
            panel_uniqueness.append(PanelUniquenessRow(
                section=table_section,
                duplicate_panels=", ".join(sorted(dup_panels)),
                status="FAIL",
                suggestion="Please delete the duplicate panel or change the panel name.",
            ))
        else:
            panel_uniqueness.append(PanelUniquenessRow(
                section=table_section, duplicate_panels="", status="PASS",
                suggestion="No changes needed.",
            ))

    return FieldUniquenessResult(
        field_duplicates=field_duplicates,
        panel_uniqueness=panel_uniqueness,
    )


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class FieldUniquenessValidator(BaseValidator):
    name = "Validate Field Uniqueness"
    sheet_name = "Field Uniqueness"
    description = "Ensures field names are unique within each panel and that panel names are not duplicated."

    def validate(self, ctx: ValidationContext) -> list[FieldUniquenessResult]:
        return [validate_field_uniqueness(
            ctx.raw_fields["all"], ctx.raw_fields["initiator"], ctx.raw_fields["spoc"],
        )]

    def write_sheet(self, wb: Workbook, results: list[FieldUniquenessResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        result = results[0]

        # ── Table 1: Field Name Uniqueness ──
        row = 1
        headers1 = ["Section", "Panel", "Duplicate Field", "Status", "Suggestion"]
        write_header(ws, headers1)
        row = 2

        for r in result.field_duplicates:
            ws.cell(row=row, column=1, value=r.section)
            ws.cell(row=row, column=2, value=r.panel)
            ws.cell(row=row, column=3, value=r.field_name if r.field_name else ("—" if r.status == "PASS" else ""))
            ws.cell(row=row, column=4, value=r.status)
            apply_severity_fill(ws.cell(row=row, column=4), r.status)
            ws.cell(row=row, column=5, value=r.suggestion)

            row += 1

        # ── Blank separator row ──
        row += 1

        # ── Table 2: Panel Name Uniqueness ──
        has_panel_duplicates = any(r.status == "FAIL" for r in result.panel_uniqueness)

        if has_panel_duplicates:
            headers2 = ["Section", "Duplicate Panel Names", "Status", "Suggestion"]
            # Write second header row manually at the current row offset
            from excel_writer import HEADER_FONT, HEADER_FILL
            from openpyxl.styles import Alignment
            for col, header in enumerate(headers2, start=1):
                cell = ws.cell(row=row, column=col, value=header)
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
                cell.alignment = Alignment(horizontal="center")
            row += 1

            for r in result.panel_uniqueness:
                if r.status == "FAIL":
                    ws.cell(row=row, column=1, value=r.section)
                    ws.cell(row=row, column=2, value=r.duplicate_panels)
                    ws.cell(row=row, column=3, value=r.status)
                    apply_severity_fill(ws.cell(row=row, column=3), r.status)
                    ws.cell(row=row, column=4, value=r.suggestion)
                    row += 1
        else:
            write_pass_row(ws, row, 4, "PASS - No duplicate panels.")

        auto_width(ws)
