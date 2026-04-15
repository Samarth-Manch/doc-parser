"""
Verify every field in each sub-table exists in the master table,
check visibility consistency, and mandatory+invisible logic.
"""

import re

from models import FieldConsistencyResult, VisibilityConsistencyResult, MandatoryInvisibleResult


_NAME_CANDIDATES = ("field name", "filed name", "name")
_TYPE_CANDIDATES = ("field type", "fieldtype", "type", "data type")
_MANDATORY_CANDIDATES = ("mandatory", "required", "is mandatory")
_LOGIC_CANDIDATES = ("logic", "logic and rules", "logic and rules other than common logic",
                     "rules", "rule", "validation", "description")


def _is_complete_field_table(table) -> bool:
    """Return True if the table has all four required columns:
    field name, field type, mandatory, and logic.
    """
    if len(table.rows) < 2:
        return False
    headers = [c.text.strip().lower() for c in table.rows[0].cells]
    has_name = any(h in headers for h in _NAME_CANDIDATES)
    has_type = any(h in headers for h in _TYPE_CANDIDATES)
    has_mandatory = any(h in headers for h in _MANDATORY_CANDIDATES)
    has_logic = any(h in headers for h in _LOGIC_CANDIDATES)
    return has_name and has_type and has_mandatory and has_logic


def _get_raw_field_names_for_section(doc, section_key: str) -> set[str] | None:
    """Extract all field names from a section's tables in the raw doc,
    regardless of whether the field type is valid/present.

    Returns None if the section has no heading or no complete field tables
    (indicating the section should be skipped entirely).
    Returns a set of lowercase field names if valid tables are found.
    """
    from .doc_utils import find_section_heading, tables_under_section, get_column_index

    if doc is None:
        return None

    heading_idx = find_section_heading(doc, section_key)
    if heading_idx is None:
        return None

    names = set()
    found_valid_table = False
    for table in tables_under_section(doc, heading_idx):
        if not _is_complete_field_table(table):
            continue
        found_valid_table = True
        headers = [c.text.strip().lower() for c in table.rows[0].cells]
        name_idx = get_column_index(headers, *_NAME_CANDIDATES)
        if name_idx is None:
            continue
        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if name_idx < len(cells) and cells[name_idx]:
                names.add(cells[name_idx].strip().lower())

    return names if found_valid_table else None


def validate_field_consistency(master_fields: dict, sub_tables: dict, doc=None) -> list[FieldConsistencyResult]:
    """Verify every field in each sub-table exists in the master table.

    Skips a section entirely if its raw doc tables lack the four required columns
    (field name, field type, mandatory, logic).
    Fields present in 4.4 raw tables but dropped due to missing type are excluded
    (the field_types validator already flags those).
    """
    # Get field names from raw 4.4 tables (includes fields with missing types)
    raw_master_names = _get_raw_field_names_for_section(doc, "4.4") or set()

    results = []
    for section, fields in sub_tables.items():
        if not fields:
            # Section not available in the document — skip validation
            continue

        # Check if this section's raw tables have the required columns
        raw_section_names = _get_raw_field_names_for_section(doc, section)
        if raw_section_names is None:
            # Section tables lack required columns — skip validation
            continue

        missing = fields.keys() - set(master_fields.keys()) - raw_master_names
        if not missing:
            results.append(FieldConsistencyResult(
                section=section, status="PASS", missing_fields="",
                suggestion="No changes needed.",
            ))
        else:
            results.append(FieldConsistencyResult(
                section=section, status="FAIL", missing_fields=", ".join(sorted(missing)),
                suggestion="Please add the missing fields to the sub-tables, or remove them from the master table.",
            ))

    return results


def _logic_indicates_visible(logic: str) -> bool | None:
    """Check if the logic text indicates a visibility rule.
    Returns True if visible, False if invisible, None if not a visibility rule.
    """
    logic_lower = logic.strip().lower()
    if not logic_lower:
        return None
    if re.search(r'\binvisible\b', logic_lower) or re.search(r'\bnot\s+visible\b', logic_lower):
        return False
    if re.search(r'\bvisible\b', logic_lower):
        return True
    return None


_CONDITIONAL_PATTERNS = [re.compile(p) for p in [
    r'\bif\b', r'\bwhen\b', r'\bbased\s+on\b',
    r'\bdepending\b', r'\bonly\s+for\b', r'\bcondition\b',
]]


def _is_conditional_visibility(logic: str) -> bool:
    """Check if the visibility rule is conditional (e.g. 'visible only if ...')."""
    logic_lower = logic.strip().lower()
    return any(p.search(logic_lower) for p in _CONDITIONAL_PATTERNS)


# Derivation patterns — matches JS logicDerivesValue exactly
_DERIVATION_PATTERNS = [re.compile(p) for p in [
    r'\bset\s+to\b', r'\bdefault\b', r'\bderiv(e|ed|es|ing)\b',
    r'\bpopulat(e|ed|es|ing)\b', r'\bauto[-\s]?(fill|populat|generat|assign)\b',
    r'\bassign(ed|s)?\b', r'\breference\b',
    r':=', r'(?<!=)=(?!=)',
]]


def _logic_derives_value(logic: str) -> bool:
    """Check if the logic text indicates that a value is being derived/set."""
    logic_lower = logic.strip().lower()
    return any(p.search(logic_lower) for p in _DERIVATION_PATTERNS)


# Non-mandatory patterns — matches JS logicRemovesMandatoryWhenInvisible exactly
_REMOVES_MANDATORY_PATTERNS = [re.compile(p) for p in [
    r'\bnon[\s-]?mandatory\b',
    r'\bnot[\s-]?mandatory\b',
    r'\bmandatory\s*[:\s]\s*no\b',
    r'\bremove\s+(the\s+)?mandatory\b',
    r'\bmade\s+invisible\s+and\s+non[\s-]?mandatory\b',
    r'\binvisible\s+and\s+non[\s-]?mandatory\b',
    r'\bnon[\s-]?mandatory\s+and\s+(non[\s-]?)?invisible\b',
]]


def _logic_removes_mandatory_when_invisible(logic: str) -> bool:
    """Check if the logic removes mandatory status when the field is invisible."""
    logic_lower = logic.strip().lower()
    return any(p.search(logic_lower) for p in _REMOVES_MANDATORY_PATTERNS)


def validate_visibility_consistency(
    master_fields: dict, sub_tables: dict,
) -> list[VisibilityConsistencyResult]:
    """If a field in 4.4 has logic indicating 'visible', it should exist in 4.5.1 and 4.5.2.
    Sections with no fields (i.e. section not present in document) are excluded from the check.
    """
    # Only consider sections that are actually present in the document
    available_sub_tables = {s: f for s, f in sub_tables.items() if f}

    if not available_sub_tables:
        # No sub-tables available — skip visibility validation entirely
        return []

    results = []
    for field_name, info in master_fields.items():
        logic = info.get("logic", "")
        visibility = _logic_indicates_visible(logic)
        if visibility is not True:
            continue

        present_in_any = any(field_name in fields for fields in available_sub_tables.values())
        missing_sections = [
            section for section, fields in available_sub_tables.items()
            if field_name not in fields
        ]

        if not present_in_any:
            # Unconditional visible/mandatory → ERROR; conditional → WARNING
            severity = "WARNING" if _is_conditional_visibility(logic) else "FAIL"
            results.append(VisibilityConsistencyResult(
                field_name=field_name,
                logic=logic,
                status=severity,
                missing_in=", ".join(missing_sections),
                suggestion="Please add the missing field to any of the sub-tables, or remove it from the master table, or mark it as invisible.",
            ))

    return results


def validate_mandatory_invisible(
    master_fields: dict,
) -> list[MandatoryInvisibleResult]:
    """If a field in 4.4 is invisible AND mandatory, the logic should derive a value."""
    results = []
    for field_name, info in master_fields.items():
        logic = info.get("logic", "")
        is_mandatory = info.get("is_mandatory", False)
        visibility = _logic_indicates_visible(logic)

        if visibility is not False:
            continue
        if not is_mandatory:
            continue

        # Check if logic removes mandatory when invisible — emit PASS (not skip)
        if _logic_removes_mandatory_when_invisible(logic):
            results.append(MandatoryInvisibleResult(
                field_name=field_name,
                logic=logic,
                is_mandatory=is_mandatory,
                status="PASS",
                reason="Logic removes mandatory status when field is invisible",
                suggestion="No changes needed.",
            ))
        elif _logic_derives_value(logic):
            results.append(MandatoryInvisibleResult(
                field_name=field_name,
                logic=logic,
                is_mandatory=is_mandatory,
                status="PASS",
                reason="Logic derives a value for the invisible mandatory field",
                suggestion="No changes needed.",
            ))
        else:
            results.append(MandatoryInvisibleResult(
                field_name=field_name,
                logic=logic,
                is_mandatory=is_mandatory,
                status="FAIL",
                reason="Field is invisible and mandatory but logic does not derive a value",
                suggestion="Please make the field non-mandatory, or add logic that derives a value for it.",
            ))

    return results


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class FieldConsistencyValidator(BaseValidator):
    name = "Validate Field Consistency"
    sheet_name = "Field Consistency"
    description = "Checks that every field in sub-tables (4.5.1/4.5.2) exists in the master table (4.4)."

    def validate(self, ctx: ValidationContext) -> list[FieldConsistencyResult]:
        return validate_field_consistency(ctx.master_fields, ctx.sub_tables, ctx.doc)

    def write_sheet(self, wb: Workbook, results: list[FieldConsistencyResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Section", "Missing Fields", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.section)
            ws.cell(row=i, column=2, value=r.missing_fields)
            ws.cell(row=i, column=3, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=3), r.status)
            ws.cell(row=i, column=4, value=r.suggestion)

        auto_width(ws)


@ValidatorRegistry.register
class VisibilityConsistencyValidator(BaseValidator):
    name = "Validate Visibility Consistency"
    sheet_name = "Visibility Consistency"
    description = "Ensures field visibility settings are consistent between master and sub-tables."

    def validate(self, ctx: ValidationContext) -> list[VisibilityConsistencyResult]:
        return validate_visibility_consistency(ctx.master_fields, ctx.sub_tables)

    def write_sheet(self, wb: Workbook, results: list[VisibilityConsistencyResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Field Name", "Logic", "Missing In Sections", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.field_name)
            ws.cell(row=i, column=2, value=r.logic)
            ws.cell(row=i, column=3, value=r.missing_in)
            ws.cell(row=i, column=4, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=4), r.status)
            ws.cell(row=i, column=5, value=r.suggestion)

        if not results:
            write_pass_row(ws, 2, len(headers), "PASS - No visible fields with missing sub-table entries.")

        auto_width(ws)


@ValidatorRegistry.register
class MandatoryInvisibleValidator(BaseValidator):
    name = "Validate Invisible Mandatory Consistency"
    sheet_name = "Mandatory Invisible"
    description = "Flags fields that are both mandatory and invisible, which is a logical conflict."

    def validate(self, ctx: ValidationContext) -> list[MandatoryInvisibleResult]:
        return validate_mandatory_invisible(ctx.master_fields)

    def write_sheet(self, wb: Workbook, results: list[MandatoryInvisibleResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Field Name", "Logic", "Mandatory", "Reason", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.field_name)
            ws.cell(row=i, column=2, value=r.logic)
            ws.cell(row=i, column=3, value="TRUE" if r.is_mandatory else "FALSE")
            ws.cell(row=i, column=4, value=r.reason)
            ws.cell(row=i, column=5, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=5), r.status)
            ws.cell(row=i, column=6, value=r.suggestion)

        if not results:
            write_pass_row(ws, 2, len(headers), "PASS - No mandatory invisible fields without value derivation.")

        auto_width(ws)
