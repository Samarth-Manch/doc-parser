"""
document_reader.py
Thin wrapper around section_parser.parse_bud().

parse_document() is the single entry point for loading a BUD .docx.
"""

from section_parser import BUDDocument, parse_bud


def parse_document(file_path: str) -> BUDDocument:
    """Parse a BUD .docx file and return a BUDDocument."""
    return parse_bud(file_path)
