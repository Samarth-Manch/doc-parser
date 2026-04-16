"""
Validates Section 4.7: Record List View.

Checks that the list of fields displayed on dashboards contains more
than just the default sample fields.  Raises a WARNING when the list
contains *only* sample fields (suggesting the author review whether
additional fields are needed) or when sample fields are missing.
"""

from docx import Document
from models import RecordListViewResult
from .doc_utils import (
    find_section_heading_index,
    find_heading_by_number,
    next_heading_position,
    body_index,
)


SAMPLE_FIELDS = [
    "Transaction ID",
    "Company Name – Title",
    "Process Name",
    "Create By",
    "Created Date",
    "Status",
]

SECTION_HEADING = "4.7 Record List View"

# Dash-like characters used as separators in BUD documents
_DASHES = {"–", "—", "-", "\u2013", "\u2014"}


def _match_sample(field_text: str) -> str | None:
    """
    Return the matching sample field name if *field_text* matches, else None.

    Matches exactly or when the field text starts with a sample field name
    followed by whitespace/dash (to handle appended descriptions).
    """
    for sample in SAMPLE_FIELDS:
        if field_text == sample:
            return sample
        # Check if text starts with sample name followed by separator/space
        if field_text.startswith(sample):
            rest = field_text[len(sample):].lstrip()
            if not rest or rest[0] in _DASHES or rest[0] == "(":
                return sample
    return None


def _find_47_heading(doc: Document) -> int | None:
    """Locate the Section 4.7 heading paragraph index."""
    idx = find_section_heading_index(doc, SECTION_HEADING)
    if idx is not None:
        return idx
    # Fallback: look for any paragraph starting with "4.7"
    return find_heading_by_number(doc, "4.7")


def _is_description(text: str) -> bool:
    """Return True if the paragraph looks like a description, not a field name."""
    lower = text.lower()
    # Multi-line text or very long text is likely a description
    if "\n" in text or len(text) > 120:
        return True
    # Common description keywords
    desc_keywords = ["list ", "below", "columns", "displayed", "dashboards", "following"]
    return any(kw in lower for kw in desc_keywords)


def _extract_bullet_fields(doc: Document, heading_idx: int) -> list[str]:
    """
    Extract field names from bullet-point paragraphs between the 4.7
    heading and the next heading.
    """
    heading_elem = doc.paragraphs[heading_idx]._element
    start_pos = body_index(doc, heading_elem)
    end_pos = next_heading_position(doc, heading_idx)

    fields: list[str] = []
    for para in doc.paragraphs[heading_idx + 1:]:
        pos = body_index(doc, para._element)
        if pos >= end_pos:
            break

        text = para.text.strip()
        if not text:
            continue

        # Skip sub-headings
        if para.style.name.startswith("Heading"):
            break

        # Skip descriptive paragraphs
        if _is_description(text):
            continue

        # Strip common bullet prefixes
        for prefix in ("•", "-", "–", "—", "*"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        # Strip trailing punctuation / numbering artefacts
        text = text.rstrip(".;,")
        if text:
            fields.append(text)

    return fields


def validate_record_list_view(doc: Document) -> list[RecordListViewResult]:
    """Validate Section 4.7 Record List View fields against the sample list."""
    results: list[RecordListViewResult] = []

    heading_idx = _find_47_heading(doc)
    if heading_idx is None:
        results.append(RecordListViewResult(
            message="Section 4.7 Record List View not found in the document.",
            status="WARNING",
            suggestion="Please add section 4.7 Record List View to the document.",
        ))
        return results

    fields = _extract_bullet_fields(doc, heading_idx)
    if not fields:
        results.append(RecordListViewResult(
            message="No fields found under Section 4.7.",
            status="WARNING",
            suggestion="Please add the record list view fields under section 4.7.",
        ))
        return results

    # A field literally named "Type" is not allowed in Section 4.7.
    if any(f.strip().lower() == "type" for f in fields):
        results.append(RecordListViewResult(
            message='A field named "Type" is not allowed in Section 4.7 Record List View.',
            status="FAIL",
            suggestion='Please remove or rename the field named "Type" in Section 4.7.',
        ))

    # Match each field against the sample list
    matched_samples: set[str] = set()
    extra_fields: list[str] = []

    for f in fields:
        sample_match = _match_sample(f)
        if sample_match:
            matched_samples.add(sample_match)
        else:
            extra_fields.append(f)

    missing_sample = sorted(set(SAMPLE_FIELDS) - matched_samples)

    # Produce a single summary result per scenario
    if not extra_fields and not missing_sample:
        # All fields are exactly the sample list, nothing more
        results.append(RecordListViewResult(
            message=(
                "The Record List View contains only the default sample fields. "
                "Please review and add any additional fields specific to your process."
            ),
            status="WARNING",
            suggestion="Please add fields specific to your process along with the sample fields.",
        ))
    elif not extra_fields and missing_sample:
        # Only sample fields present but some are missing
        results.append(RecordListViewResult(
            message=(
                "The Record List View contains only sample fields and is missing: "
                + ", ".join(missing_sample) + ". "
                "Please review and add any additional fields specific to your process."
            ),
            status="WARNING",
            suggestion="Please add the missing sample fields and any fields specific to your process.",
        ))
    elif extra_fields and missing_sample:
        # Has custom fields but some sample fields are missing
        results.append(RecordListViewResult(
            message=(
                "The Record List View has additional fields but is missing these "
                "sample fields: " + ", ".join(missing_sample) + ". "
                "Please verify whether these are intentionally excluded."
            ),
            status="WARNING",
            suggestion="Please add the missing sample fields, or confirm they are intentionally excluded.",
        ))
    else:
        # Has extra fields and all sample fields present
        results.append(RecordListViewResult(
            message="The Record List View contains all sample fields and additional custom fields.",
            status="PASS",
            suggestion="No changes needed.",
        ))

    return results


# ── Registry integration ────────────────────────────────────────────────────

from openpyxl import Workbook
from .registry import BaseValidator, ValidatorRegistry, ValidationContext
from excel_writer import write_header, apply_severity_fill, auto_width, write_pass_row


@ValidatorRegistry.register
class RecordListViewValidator(BaseValidator):
    name = "Validate Record List View"
    sheet_name = "Record List View"
    description = "Checks that Section 4.7 Record List View contains more than just sample fields."

    def validate(self, ctx: ValidationContext) -> list[RecordListViewResult]:
        return validate_record_list_view(ctx.doc)

    def write_sheet(self, wb: Workbook, results: list[RecordListViewResult]) -> None:
        ws = wb.create_sheet(self.sheet_name)
        headers = ["Message", "Status", "Suggestion"]
        write_header(ws, headers)

        for i, r in enumerate(results, start=2):
            ws.cell(row=i, column=1, value=r.message)
            ws.cell(row=i, column=2, value=r.status)
            apply_severity_fill(ws.cell(row=i, column=2), r.status)
            ws.cell(row=i, column=3, value=r.suggestion)

        if not results:
            write_pass_row(ws, 2, len(headers), "PASS - Record List View fields look good.")

        auto_width(ws)
