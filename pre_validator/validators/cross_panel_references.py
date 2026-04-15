"""
Check that when a field's logic references another field (in double quotes)
that doesn't exist in the same panel, the logic also mentions the panel name
where the referenced field lives.

Fields in logic are identified by double-quoted strings.
ALL-UPPERCASE quoted strings are treated as EDV reference table names and skipped.
"""

import re
from models import CrossPanelReferenceResult
from .doc_utils import group_fields_by_panel


def _extract_quoted_field_names(logic: str) -> list[str]:
    """Extract double-quoted strings from logic, excluding ALL-UPPERCASE identifiers
    (EDV refs) but keeping strings that contain spaces even if uppercase."""
    matches = re.findall(r'"([^"]+)"', logic)
    result = []
    for m in matches:
        m = m.strip()
        if not m:
            continue
        # Exclude ALL_CAPS_UNDERSCORE_DIGIT identifiers (no spaces) — these are EDV refs
        # But keep strings with spaces even if uppercase
        if re.match(r'^[A-Z0-9_]+$', m) and ' ' not in m:
            continue
        result.append(m)
    return result


def _build_field_to_panel_map(fields: list) -> dict[str, str]:
    """Build a map of normalized field name -> panel name."""
    result: dict[str, str] = {}
    for f in fields:
        if hasattr(f, "field_type_raw") and f.field_type_raw and f.field_type_raw.strip().upper() == "PANEL":
            continue
        panel = (f.section or "").strip() or "(no panel)"
        result[(f.name or "").strip().lower()] = panel
    return result


def validate_cross_panel_references(
    raw_fields: dict[str, list],
) -> list[CrossPanelReferenceResult]:
    """
    For each field, check that cross-panel field references in its logic
    include the corresponding panel name.
    """
    section_map = {
        "4.4": raw_fields.get("all", []),
        "4.5.1": raw_fields.get("initiator", []),
        "4.5.2": raw_fields.get("spoc", []),
    }

    results: list[CrossPanelReferenceResult] = []

    for section_label, fields in section_map.items():
        if not fields:
            continue

        panels = group_fields_by_panel(fields)
        field_to_panel = _build_field_to_panel_map(fields)
        all_field_names = set(field_to_panel.keys())

        for panel_name, panel_fields in panels.items():
            panel_field_names = {
                (f.name or "").strip().lower() for f in panel_fields
            }

            for f in panel_fields:
                logic = f.logic or ""
                if not logic.strip():
                    continue

                referenced_names = _extract_quoted_field_names(logic)

                for ref_name in referenced_names:
                    ref_key = ref_name.strip().lower()

                    if ref_key not in all_field_names:
                        continue

                    if ref_key in panel_field_names:
                        continue

                    ref_panel = field_to_panel[ref_key]

                    if ref_panel.lower() in logic.lower():
                        continue

                    results.append(CrossPanelReferenceResult(
                        section=section_label,
                        field_name=(f.name or "").strip(),
                        panel=panel_name,
                        referenced_field=ref_name,
                        referenced_field_panel=ref_panel,
                        status="FAIL",
                        message=(
                            f'Logic references "{ref_name}" which belongs to '
                            f'panel "{ref_panel}", but the panel name is not '
                            f"mentioned in the logic."
                        ),
                        suggestion=f'Please add "{ref_panel}" panel as reference in the logic.',
                    ))

    return results


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class CrossPanelReferenceValidator(BaseValidator):
    name = "Validate Cross Panel References"
    sheet_name = "Cross-Panel References"
    description = "Checks that logic referencing fields in other panels includes the target panel name."

    def validate(self, ctx: ValidationContext) -> list[CrossPanelReferenceResult]:
        return validate_cross_panel_references(ctx.raw_fields)

    def write_sheet(self, wb: Workbook, results: list[CrossPanelReferenceResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Section", "Field Name", "Panel", "Referenced Field", "Referenced Field Panel", "Message", "Status"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.section)
            ws.cell(row=i, column=2, value=r.field_name)
            ws.cell(row=i, column=3, value=r.panel)
            ws.cell(row=i, column=4, value=r.referenced_field)
            ws.cell(row=i, column=5, value=r.referenced_field_panel)
            ws.cell(row=i, column=6, value=r.message)
            ws.cell(row=i, column=7, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=7), r.status)

        if not results:
            write_pass_row(ws, 2, len(headers), "PASS - All cross-panel field references include the panel name.")

        auto_width(ws)
