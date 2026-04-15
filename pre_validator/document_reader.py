"""
document_reader.py
Responsible for all document I/O and structured field extraction.

Uses the docs_parser package (DocumentParser) for parsing, then converts
its ParsedDocument output into the dict format expected by downstream
validators.

parse_document() is the single point of entry for loading a BUD .docx.
It opens the file via docs_parser and returns:
    - master_fields : fields extracted from section 4.4
    - sub_tables    : fields extracted from sections 4.5.1 and 4.5.2
    - doc           : the open Document object, so callers can pass it to
                      other validators without a second file open.
"""

from docx import Document
from docx.document import Document as DocxDocument
from docs_parser import DocumentParser


def _fields_to_dict(field_definitions: list) -> dict:
    """
    Convert a list of FieldDefinition objects into the dict format
    expected by validators: {field_name: {"type": ..., "logic": ...}}
    """
    result = {}
    for f in field_definitions:
        key = f.name.strip().lower()
        if key:
            result[key] = {"type": f.field_type_raw, "logic": f.logic, "is_mandatory": f.is_mandatory}
    return result


def parse_document(file_path: str) -> tuple[dict, dict, dict, DocxDocument]:
    """
    Open the .docx file, parse it via docs_parser, and extract all
    structured field data in the format expected by downstream validators.

    Args:
        file_path: Path to the .docx file.

    Returns:
        (master_fields, sub_tables, raw_fields, doc)

        master_fields : {field_name: {"type": ..., "logic": ...}}  — from 4.4
        sub_tables    : {"4.5.1": {...}, "4.5.2": {...}}           — from 4.5.x
        raw_fields    : {"all": [...], "initiator": [...], "spoc": [...]} — raw FieldDefinition lists
        doc           : open Document object for downstream validators
    """
    # Use docs_parser to get the rich ParsedDocument
    parser = DocumentParser()
    parsed_doc = parser.parse(file_path)

    # Convert all_fields (master / section 4.4) to dict format
    master_fields = _fields_to_dict(parsed_doc.all_fields)

    # Convert actor-specific fields to sub_tables dict format
    # initiator_fields → 4.5.1, spoc_fields → 4.5.2
    sub_tables = {
        "4.5.1": _fields_to_dict(parsed_doc.initiator_fields),
        "4.5.2": _fields_to_dict(parsed_doc.spoc_fields),
    }

    # Keep raw field lists for validators that need them (e.g. uniqueness)
    raw_fields = {
        "all": parsed_doc.all_fields,
        "initiator": parsed_doc.initiator_fields,
        "spoc": parsed_doc.spoc_fields,
    }

    # Re-open the document for validators that need the raw doc object
    # (validate_tables, validate_types, validate_rules all operate on
    #  the raw python-docx Document directly)
    doc = Document(file_path)

    return master_fields, sub_tables, raw_fields, doc
