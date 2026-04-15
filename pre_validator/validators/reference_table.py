"""
Validates that reference tables cited in field logic exist in section 4.6.

Scans all field logic strings for table references and checks that the
referenced table name appears as a listed entry (text label or embedded
Excel file name) in section 4.6 Reference Tables.

Section 4.6 entries come in three flavours across BUD documents:
  1. Numbered:  "Table 1.1", "Table 1.2"
  2. Named:     "VC_BASIC_DETAILS", "Noun-Modifier", "Table YES_NO"
  3. OLE links: embedded Excel files whose paths appear in field codes
"""

import os
import re
from lxml import etree
from models import ReferenceTableResult


# ── Patterns for extracting table references FROM field logic ────────────────

# Pattern 1 — numbered, optionally followed by parenthesized name:
# e.g. "table 1.1", "reference table 1.3 (COUNTRY)"
_PAT_NUMBERED = re.compile(
    r"(?:refer(?:ence)?\s+)?table\s+(\d+\.\d+)(?:\s*\(([A-Za-z_][A-Za-z0-9_]*)\))?",
    re.IGNORECASE,
)

# Pattern 2 — named after separator dash/colon
_PAT_NAMED_AFTER_SEP = re.compile(
    r"(?:reference\s+)?table\s*(?:name)?\s*[-:]\s*([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)

# Pattern 3 — named after "Reference Table " with space, requires underscore
_PAT_NAMED_AFTER_SPACE = re.compile(
    r"reference\s+table\s+([A-Za-z_][A-Za-z0-9_]*(?:_[A-Za-z0-9_]+)+)",
    re.IGNORECASE,
)

# Pattern 4 — name BEFORE "reference table"
_PAT_NAME_BEFORE = re.compile(
    r"(\b[A-Za-z_][A-Za-z0-9_]*)\s+reference\s+table",
    re.IGNORECASE,
)

# Pattern 5+6 — EDV followed by ALL-CAPS name, handles straight/curly/missing quotes
_PAT_EDV = re.compile(
    r'\bEDV\s+["\u201c\u201d\u201e]?([A-Z][A-Z0-9_]+)["\u201c\u201d\u201f]?',
)

# Pattern 7 — "column N of (the) (Table)? TABLE_NAME"
_PAT_COLUMN_OF = re.compile(
    r'column\s+\d+\s+of\s+(?:the\s+)?(?:(?:refer(?:ence)?\s+)?table\s+)?'
    r'["\u201c\u201e]?([A-Z][A-Z0-9_]*(?:_[A-Z0-9_]+)*)["\u201d\u201f]?',
    re.IGNORECASE,
)

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ── Normalisation ─────────────────────────────────────────────────────────

_NON_TABLE_KEYWORDS = frozenset({"edv", "staging", "data", "table"})


def _normalise(name: str) -> str:
    """Lower-case, strip leading 'table' prefix, unify separators."""
    n = name.strip().lower()
    n = re.sub(r"^table\s+", "", n)
    n = re.sub(r"[-_\s]+", "_", n)
    return n


def _is_table_identifier(name: str, raw_text: str) -> bool:
    """Return True if name looks like a genuine table identifier."""
    if name.lower() in _NON_TABLE_KEYWORDS:
        return False
    if "_" in name:
        return True
    if raw_text.isupper() and len(raw_text) >= 2:
        return True
    return False


# ── Section 4.6 extraction ──────────────────────────────────────────────────

def _extract_table_identifiers(text: str) -> list[str]:
    """Parse a single text entry from section 4.6 and extract table identifiers."""
    ids = []
    t = text.strip()
    if not t:
        return ids

    # Extract table number (e.g. "1.9" from "Table 1.9 - PAYMENT_MODE")
    num_match = re.search(r"(?:(?:refer(?:ence)?\s+)?table\s+)?(\d+\.\d+)", t, re.IGNORECASE)
    if num_match:
        ids.append(num_match.group(1))

    # Extract UPPER_CASE identifiers with underscores
    name_matches = re.findall(r"\b[A-Za-z_][A-Za-z0-9]*(?:_[A-Za-z0-9_]+)+\b", t)
    for name in name_matches:
        if name.lower() not in _NON_TABLE_KEYWORDS:
            ids.append(name)

    # Extract parenthesized names
    paren_matches = re.findall(r"\(([A-Za-z_][A-Za-z0-9_]*)\)", t)
    for name in paren_matches:
        if name.lower() not in _NON_TABLE_KEYWORDS:
            ids.append(name)

    # If nothing was extracted but text looks like a single ALL-CAPS identifier, take it
    if not ids and re.match(r"^[A-Z][A-Z0-9]+$", t) and t.lower() not in _NON_TABLE_KEYWORDS:
        ids.append(t)

    return ids


def _extract_section_46_tables(doc) -> set[str]:
    """
    Parse section 4.6 and return a set of normalised reference-table identifiers.
    """
    names: set[str] = set()

    # Locate section 4.6 heading
    heading_idx = None
    for i, para in enumerate(doc.paragraphs):
        if "4.6" in para.text and para.style.name.startswith("Heading"):
            heading_idx = i
            break

    if heading_idx is None:
        return names

    body = list(doc.element.body)
    start = body.index(doc.paragraphs[heading_idx]._element)

    # Find next heading body position
    end = len(body)
    for para in doc.paragraphs[heading_idx + 1:]:
        if para.style.name.startswith("Heading"):
            end = body.index(para._element)
            break

    # Walk body elements between headings
    for idx, elem in enumerate(body):
        if idx <= start or idx >= end:
            continue

        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag == "p":
            # Collect visible text
            visible_parts = []
            for t_elem in elem.iter(f"{{{_W_NS}}}t"):
                if t_elem.text:
                    visible_parts.append(t_elem.text)
            visible = "".join(visible_parts).strip()

            if visible:
                for ident in _extract_table_identifiers(visible):
                    names.add(_normalise(ident))

            # Extract file names from OLE LINK field codes
            xml_str = etree.tostring(elem, encoding="unicode")
            for m in re.finditer(r'"([^"]+\.xlsx?)"', xml_str, re.IGNORECASE):
                fname = os.path.basename(m.group(1))
                name_no_ext = os.path.splitext(fname)[0]
                names.add(_normalise(name_no_ext))

        elif tag == "tbl":
            # Also scan table cells in section 4.6
            for t_elem in elem.iter(f"{{{_W_NS}}}t"):
                if t_elem.text:
                    for ident in _extract_table_identifiers(t_elem.text.strip()):
                        names.add(_normalise(ident))

    return names


# ── Logic reference extraction ───────────────────────────────────────────────

def _extract_logic_refs(logic: str) -> dict[str, str]:
    """Return a dict of {normalised_name: original_name} for table refs in a logic string."""
    refs: dict[str, str] = {}

    def add_ref(raw: str) -> None:
        key = _normalise(raw)
        if key not in refs:
            refs[key] = raw.strip()

    # Pattern 1: numbered tables — add both number and parenthesized name
    for m in _PAT_NUMBERED.finditer(logic):
        add_ref(m.group(1))  # always add the table number
        if m.group(2):
            add_ref(m.group(2))  # also add parenthesized name if present

    # Pattern 2: named after separator
    for m in _PAT_NAMED_AFTER_SEP.finditer(logic):
        raw = m.group(1)
        if raw.lower() not in _NON_TABLE_KEYWORDS:
            add_ref(raw)

    # Pattern 3: named after "Reference Table" with space
    for m in _PAT_NAMED_AFTER_SPACE.finditer(logic):
        add_ref(m.group(1))

    # Pattern 4: name before "reference table"
    for m in _PAT_NAME_BEFORE.finditer(logic):
        raw = m.group(1)
        if _is_table_identifier(raw, raw):
            add_ref(raw)

    # Pattern 5+6: EDV with ALL-CAPS name
    for m in _PAT_EDV.finditer(logic):
        add_ref(m.group(1))

    # Pattern 7: column N of TABLE_NAME
    for m in _PAT_COLUMN_OF.finditer(logic):
        raw = m.group(1)
        if raw.lower() not in _NON_TABLE_KEYWORDS:
            add_ref(raw)

    return refs


# ── Field checker ────────────────────────────────────────────────────────────

def _check_fields(
    fields: dict,
    section_label: str,
    available_normalised: set[str],
) -> list[ReferenceTableResult]:
    results: list[ReferenceTableResult] = []
    already_reported: set[tuple[str, str]] = set()

    for field_name, data in fields.items():
        logic = data.get("logic") or ""
        for norm_ref, orig_ref in _extract_logic_refs(logic).items():
            if norm_ref in available_normalised:
                continue
            key = (field_name, norm_ref)
            if key in already_reported:
                continue
            already_reported.add(key)

            # Use "Table X.Y" display for numbered refs, otherwise original case
            display = f"Table {orig_ref}" if re.match(r"\d+\.\d+$", norm_ref) else orig_ref
            results.append(ReferenceTableResult(
                section=section_label,
                field_name=field_name,
                referenced_table=display,
                status="WARNING",
                message=f"'{display}' referenced in logic but not found in section 4.6 Reference Tables",
                suggestion=f'Please make sure you have referenced the correct EDV table, or add "{display}" in section 4.6.',
            ))

    return results


# ── Public API ───────────────────────────────────────────────────────────────

def validate_reference_tables(
    master_fields: dict,
    sub_tables: dict,
    doc,
) -> list[ReferenceTableResult]:
    """Check that every reference table cited in field logic is listed in section 4.6."""
    available = _extract_section_46_tables(doc)

    if not available:
        return [ReferenceTableResult(
            section="4.6",
            field_name="N/A",
            referenced_table="N/A",
            status="WARNING",
            message="Section 4.6 Reference Tables not found or contains no table entries",
            suggestion="Please add section 4.6 with the reference tables used in the document.",
        )]

    results = _check_fields(master_fields, "4.4", available)
    for section, fields in sub_tables.items():
        results.extend(_check_fields(fields, section, available))

    return results


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class ReferenceTableValidator(BaseValidator):
    name = "Validate Reference Tables"
    sheet_name = "Reference Tables"
    description = "Validates that reference tables cited in field logic exist as entries in section 4.6."

    def validate(self, ctx: ValidationContext) -> list[ReferenceTableResult]:
        return validate_reference_tables(ctx.master_fields, ctx.sub_tables, ctx.doc)

    def write_sheet(self, wb: Workbook, results: list[ReferenceTableResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Section", "Field Name", "Referenced Table", "Message", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.section)
            ws.cell(row=i, column=2, value=r.field_name)
            ws.cell(row=i, column=3, value=r.referenced_table)
            ws.cell(row=i, column=4, value=r.message)
            ws.cell(row=i, column=5, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=5), r.status)
            ws.cell(row=i, column=6, value=r.suggestion)

        if not results:
            write_pass_row(ws, 2, len(headers),
                            "PASS - All referenced tables exist in section 4.6.")

        auto_width(ws)
