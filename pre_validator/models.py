"""
models.py
Result dataclasses for each validation step.
"""

from dataclasses import dataclass, field


@dataclass
class TableCheckResult:
    section: str        # 4.4, 4.5.1, 4.5.2
    message: str
    details: str
    status: str         # FAIL | WARNING | INFO | PASS
    suggestion: str = ""


@dataclass
class FieldConsistencyResult:
    section: str        # 4.5.1, 4.5.2
    missing_fields: str # comma-separated names, empty if PASS
    status: str         # PASS | FAIL | N/A
    suggestion: str = ""


@dataclass
class VisibilityConsistencyResult:
    field_name: str         # field from 4.4
    logic: str              # the logic text
    missing_in: str         # comma-separated sections where field is missing
    status: str             # PASS | FAIL | WARNING
    suggestion: str = ""


@dataclass
class MandatoryInvisibleResult:
    field_name: str         # field from 4.4
    logic: str              # the logic text
    is_mandatory: bool
    reason: str             # explanation of the issue
    status: str             # PASS | FAIL
    suggestion: str = ""


@dataclass
class EDVLogicResult:
    section: str
    field_name: str
    field_type: str
    message: str
    status: str = "WARNING"
    suggestion: str = ""


@dataclass
class FieldDuplicateRow:
    """One row per panel (PASS) or per duplicate field (FAIL) in a section."""
    section: str            # 4.4, 4.5.1, 4.5.2
    panel: str              # panel name
    field_name: str         # duplicate field name, empty for PASS rows
    status: str             # PASS | FAIL | N/A
    suggestion: str = ""


@dataclass
class PanelUniquenessRow:
    """One row per section showing whether panel names are unique."""
    section: str            # 4.4, 4.5.1, 4.5.2
    duplicate_panels: str   # comma-separated duplicate panel names, empty if PASS
    status: str             # PASS | FAIL | N/A
    suggestion: str = ""


@dataclass
class FieldUniquenessResult:
    """Wrapper holding both sub-tables for the Field Uniqueness sheet."""
    field_duplicates: list  # list[FieldDuplicateRow]
    panel_uniqueness: list  # list[PanelUniquenessRow]


@dataclass
class FieldTypeResult:
    section: str        # 4.4, 4.5.1, 4.5.2
    field_name: str
    invalid_type: str
    status: str         # FAIL | WARNING
    suggestion: str = ""


@dataclass
class RuleDuplicateResult:
    location: str           # "Section 4.4 vs Section 4.5.1"
    detection_tier: str     # EXACT | FUZZY | LLM
    field_a: str
    section_a: str
    rule_a: str
    field_b: str
    section_b: str
    rule_b: str
    reason: str             # explanation text
    status: str             # FAIL | WARNING
    suggestion: str = ""


@dataclass
class NonEditableCheckResult:
    section: str            # 4.4
    field_name: str
    field_type: str         # actual type found
    status: str             # FAIL | INFO
    suggestion: str = ""


@dataclass
class ArrayBracketCheckResult:
    section: str            # 4.4, 4.5.1, 4.5.2
    field_name: str
    row: int
    message: str
    details: str
    status: str             # FAIL | INFO
    suggestion: str = ""


@dataclass
class ClearFieldLogicResult:
    section: str            # 4.4, 4.5.1, 4.5.2
    field_name: str         # the field whose logic was checked
    referenced_field: str   # the field referenced in the condition
    condition_text: str     # the conditional phrase found
    logic: str              # the full logic text of the field
    status: str             # FAIL | PASS
    suggestion: str = ""


@dataclass
class ReferenceTableResult:
    section: str            # 4.4, 4.5.1, 4.5.2
    field_name: str         # the field whose logic references a table
    referenced_table: str   # the table reference found in logic (e.g. "Table 1.3")
    message: str            # explanation
    status: str             # WARNING | PASS
    suggestion: str = ""


@dataclass
class CrossPanelReferenceResult:
    section: str                # 4.4, 4.5.1, 4.5.2
    field_name: str             # the field whose logic references another field
    panel: str                  # panel the field belongs to
    referenced_field: str       # the field name found in the logic
    referenced_field_panel: str # the panel where the referenced field actually lives
    message: str                # explanation
    status: str                 # PASS | FAIL
    suggestion: str = ""


@dataclass
class FieldOutsidePanelResult:
    section: str        # 4.4, 4.5.1, 4.5.2
    field_name: str     # the field that is outside any panel
    message: str        # explanation
    status: str         # FAIL | PASS | N/A
    suggestion: str = ""


@dataclass
class RecordListViewResult:
    message: str        # human-readable summary
    status: str         # WARNING | PASS
    suggestion: str = ""
