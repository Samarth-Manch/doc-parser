"""
OOXML Document Parser for extracting fields, rules, workflows, and metadata.
"""

from .parser import DocumentParser
from .models import (
    ParsedDocument,
    FieldDefinition,
    TableData,
    Section,
    WorkflowStep,
    ApprovalRule,
)

__version__ = "1.0.0"
__all__ = [
    "DocumentParser",
    "ParsedDocument",
    "FieldDefinition",
    "TableData",
    "Section",
    "WorkflowStep",
    "ApprovalRule",
]
