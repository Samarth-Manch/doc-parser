"""
Data models for representing parsed document structures.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class FieldType(Enum):
    """Official field types from the system."""
    # Basic Input Types
    TEXT = "TEXT"
    TEXTAREA = "TEXTAREA"
    NUMBER = "NUMBER"
    DATE = "DATE"
    TIME = "TIME"
    PASSWORD = "PASSWORD"
    MASKED_FIELD = "MASKED_FIELD"
    FOUR_DIGITS = "FOUR_DIGITS"

    # Dropdown Types
    DROPDOWN = "DROPDOWN"
    OPTION = "OPTION"
    EXTERNAL_DROP_DOWN_VALUE = "EXTERNAL_DROP_DOWN_VALUE"
    EXTERNAL_DROP_DOWN_MULTISELECT = "EXTERNAL_DROP_DOWN_MULTISELECT"
    MULTISELECT_EXTERNAL_DROPDOWN = "MULTISELECT_EXTERNAL_DROPDOWN"
    EXTERNAL_DROP_DOWN_RADIOBUTTON = "EXTERNAL_DROP_DOWN_RADIOBUTTON"

    # Selection Types
    CHECK_BOX = "CHECK_BOX"
    STATIC_CHECK_BOX = "STATIC_CHECK_BOX"
    RADIAL_BUTTON = "RADIAL_BUTTON"

    # File Types
    FILE = "FILE"
    MULTIPLE_FILE = "MULTIPLE_FILE"
    IMAGE = "IMAGE"
    IMAGE_DISPLAY = "IMAGE_DISPLAY"
    IMAGE_VIEW = "IMAGE_VIEW"
    PDF = "PDF"
    VIDEO = "VIDEO"
    VIDEO_NATIVE = "VIDEO_NATIVE"

    # Layout/Grouping Types
    PANEL = "PANEL"
    GRP_HDR = "GRP_HDR"
    GRP_END = "GRP_END"
    ROW_HDR = "ROW_HDR"
    ROW_END = "ROW_END"
    ARRAY_HDR = "ARRAY_HDR"
    ARRAY_END = "ARRAY_END"
    CARD_HDR = "CARD_HDR"
    CARD_END = "CARD_END"

    # Button Types
    BUTTON_HDR = "BUTTON_HDR"
    BUTTON_END = "BUTTON_END"
    BUTTON_ICON = "BUTTON_ICON"
    DYNAMIC_BUTTON = "DYNAMIC_BUTTON"
    EXECUTE_BUTTON = "EXECUTE_BUTTON"

    # Display Types
    LABEL = "LABEL"
    COMMENT = "COMMENT"
    PREVIEW = "PREVIEW"
    HTML_PREVIEW = "HTML_PREVIEW"
    TABLE_VIEW = "TABLE_VIEW"
    BASE_DOC_VIEW = "BASE_DOC_VIEW"
    IFRAME = "IFRAME"

    # Verification Types
    PAN = "PAN"
    PAN_NUMBER = "PAN_NUMBER"
    VOTER_ID = "VOTER_ID"
    OTP = "OTP"
    OTP_BOX = "OTP_BOX"

    # Video KYC Types
    VIDEO_KYC = "VIDEO_KYC"
    VIDEO_KYC_RECORD = "VIDEO_KYC_RECORD"
    VIDEO_AGENT_KYC = "VIDEO_AGENT_KYC"

    # Audio Types
    AUDIO = "AUDIO"
    AUDIO_OTP = "AUDIO_OTP"
    AUDIO_FORM_FILL = "AUDIO_FORM_FILL"
    AUDIO_RECORD = "AUDIO_RECORD"

    # Location Types
    STATIC_LOCATION = "STATIC_LOCATION"
    DYNAMIC_LOCATION = "DYNAMIC_LOCATION"
    COMPASS_DIRECTION = "COMPASS_DIRECTION"
    ADVANCE_MAP = "ADVANCE_MAP"

    # Special Types
    FORMULA = "FORMULA"
    VARIABLE = "VARIABLE"
    ACTION = "ACTION"
    QR_SCANNER = "QR_SCANNER"
    CONTENT_VALUE_INFO = "CONTENT_VALUE_INFO"

    # Payment Types
    MAKE_PAYMENT = "MAKE_PAYMENT"
    CHECK_PAYMENT = "CHECK_PAYMENT"
    MAKE_ESTAMP = "MAKE_ESTAMP"

    # Notes Types
    NOTES = "NOTES"
    NOTE_HISTORY = "NOTE_HISTORY"

    # Legacy/Compatibility
    MOBILE = "MOBILE"
    EMAIL = "EMAIL"

    # Unknown/Fallback
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, value: str) -> "FieldType":
        """Parse field type from string value with comprehensive mappings."""
        if not value:
            return cls.UNKNOWN

        normalized = value.upper().strip().replace(" ", "_").replace("-", "_")

        # Comprehensive mappings for common variations
        mappings = {
            # Dropdown variations
            "DROPDOWN": cls.DROPDOWN,
            "DROP_DOWN": cls.DROPDOWN,
            "MULTI_DROPDOWN": cls.MULTISELECT_EXTERNAL_DROPDOWN,
            "MULTIDROPDOWN": cls.MULTISELECT_EXTERNAL_DROPDOWN,
            "MULTI_SELECT_DROPDOWN": cls.MULTISELECT_EXTERNAL_DROPDOWN,
            "EXTERNAL_DROPDOWN": cls.EXTERNAL_DROP_DOWN_VALUE,
            "EXTERNAL_DROP_DOWN": cls.EXTERNAL_DROP_DOWN_VALUE,

            # Checkbox variations
            "CHECKBOX": cls.CHECK_BOX,
            "STATIC_CHECKBOX": cls.STATIC_CHECK_BOX,
            "STATIC_CHECK_BOX": cls.STATIC_CHECK_BOX,

            # Radio button variations
            "RADIO": cls.RADIAL_BUTTON,
            "RADIO_BUTTON": cls.RADIAL_BUTTON,
            "RADIOBUTTON": cls.RADIAL_BUTTON,

            # File variations
            "FILE_UPLOAD": cls.FILE,
            "UPLOAD": cls.FILE,

            # Text variations
            "TEXTBOX": cls.TEXT,
            "TEXT_BOX": cls.TEXT,
            "INPUT": cls.TEXT,
            "TEXTFIELD": cls.TEXT,
            "TEXT_FIELD": cls.TEXT,

            # Number variations
            "NUMERIC": cls.NUMBER,
            "INTEGER": cls.NUMBER,

            # Date variations
            "DATE_PICKER": cls.DATE,
            "DATEPICKER": cls.DATE,

            # Mobile/Email (legacy)
            "PHONE": cls.MOBILE,
            "MOBILE_NUMBER": cls.MOBILE,
            "EMAIL_ADDRESS": cls.EMAIL,

            # Bank account variations
            "BANK_ACCOUNT": cls.MASKED_FIELD,
            "BANK_ACCOUNT_NUMBER": cls.MASKED_FIELD,
            "ACCOUNT_NUMBER": cls.MASKED_FIELD,
        }

        if normalized in mappings:
            return mappings[normalized]

        # Try direct match with enum
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class FieldDefinition:
    """Represents a field with its type, rules, and constraints."""
    name: str
    field_type: FieldType
    field_type_raw: str  # Original value from document
    is_mandatory: bool
    logic: str = ""
    rules: str = ""
    default_value: str = ""
    visibility_condition: str = ""
    validation: str = ""
    section: str = ""  # Which section/panel this field belongs to
    dropdown_values: list[str] = field(default_factory=list)
    variable_name: str = ""  # Auto-generated alphanumeric ID like __pan__, __gst__, etc.

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "field_type_raw": self.field_type_raw,
            "is_mandatory": self.is_mandatory,
            "logic": self.logic,
            "rules": self.rules,
            "default_value": self.default_value,
            "visibility_condition": self.visibility_condition,
            "validation": self.validation,
            "section": self.section,
            "dropdown_values": self.dropdown_values,
            "variable_name": self.variable_name,
        }


@dataclass
class TableData:
    """Represents a table with headers and rows."""
    headers: list[str]
    rows: list[list[str]]
    table_type: str = ""  # e.g., "field_definitions", "reference", "workflow", "matrix"
    context: str = ""  # Heading/section where this table appears
    cell_formats: list[list["CellFormatting"]] = field(default_factory=list)  # Cell formatting for each cell
    table_format: Optional["TableFormatting"] = None  # Table-level formatting
    source: str = "document"  # "document" or "excel" - indicates where table came from
    source_file: str = ""  # For Excel tables, the filename of the source Excel file
    sheet_name: str = ""  # For Excel tables, the sheet name

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.headers) if self.headers else 0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "headers": self.headers,
            "rows": self.rows,
            "table_type": self.table_type,
            "context": self.context,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "cell_formats": [[c.to_dict() for c in row_formats] for row_formats in self.cell_formats] if self.cell_formats else [],
            "table_format": self.table_format.to_dict() if self.table_format else None,
            "source": self.source,
            "source_file": self.source_file,
            "sheet_name": self.sheet_name,
        }


@dataclass
class WorkflowStep:
    """Represents a step in a workflow or process."""
    step_number: int
    description: str
    actor: str  # Who performs this step (Initiator, SPOC, Approver, etc.)
    action_type: str = ""  # e.g., "login", "upload", "validate", "approve"
    conditions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "actor": self.actor,
            "action_type": self.action_type,
            "conditions": self.conditions,
            "notes": self.notes,
        }


@dataclass
class ApprovalRule:
    """Represents an approval routing rule."""
    condition: str
    approver: str
    approval_type: str = ""  # e.g., "individual", "group", "sequential"
    routing_logic: str = ""

    def to_dict(self) -> dict:
        return {
            "condition": self.condition,
            "approver": self.approver,
            "approval_type": self.approval_type,
            "routing_logic": self.routing_logic,
        }


@dataclass
class Section:
    """Represents a document section with its content."""
    heading: str
    level: int  # Heading level (1, 2, 3, etc.)
    content: list[str]  # Paragraphs in this section
    subsections: list["Section"] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    fields: list[FieldDefinition] = field(default_factory=list)
    workflow_steps: list[WorkflowStep] = field(default_factory=list)
    runs: list[list["RunFormatting"]] = field(default_factory=list)  # Formatted text runs per paragraph
    paragraph_formats: list["ParagraphFormatting"] = field(default_factory=list)  # Paragraph formatting

    def to_dict(self) -> dict:
        return {
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
            "subsections": [s.to_dict() for s in self.subsections],
            "tables": [t.to_dict() for t in self.tables],
            "fields": [f.to_dict() for f in self.fields],
            "workflow_steps": [w.to_dict() for w in self.workflow_steps],
            "runs": [[r.to_dict() for r in para_runs] for para_runs in self.runs],
            "paragraph_formats": [p.to_dict() for p in self.paragraph_formats],
        }


@dataclass
class VersionEntry:
    """Represents a version history entry."""
    version: str
    approved_by: str
    revision_date: str
    description: str
    author: str

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "approved_by": self.approved_by,
            "revision_date": self.revision_date,
            "description": self.description,
            "author": self.author,
        }


@dataclass
class DocumentMetadata:
    """Document-level metadata."""
    title: str = ""
    author: str = ""
    subject: str = ""
    created: Optional[str] = None
    modified: Optional[str] = None
    last_modified_by: str = ""
    company: str = ""
    process_name: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "created": self.created,
            "modified": self.modified,
            "last_modified_by": self.last_modified_by,
            "company": self.company,
            "process_name": self.process_name,
        }


@dataclass
class IntegrationField:
    """Represents a field mapping for integration."""
    internal_field_name: str
    external_system: str
    external_field_name: str
    data_type: str
    transformation_logic: str
    is_mandatory: bool
    default_value: str
    validation_rules: str

    def to_dict(self) -> dict:
        return {
            "internal_field_name": self.internal_field_name,
            "external_system": self.external_system,
            "external_field_name": self.external_field_name,
            "data_type": self.data_type,
            "transformation_logic": self.transformation_logic,
            "is_mandatory": self.is_mandatory,
            "default_value": self.default_value,
            "validation_rules": self.validation_rules,
        }


@dataclass
class FontInfo:
    """Font formatting information for text runs."""
    family: str = ""           # Font name (Arial, Calibri)
    size_pt: float = 0.0       # Font size in points
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color_rgb: Optional[tuple] = None  # (R, G, B)

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "size_pt": self.size_pt,
            "bold": self.bold,
            "italic": self.italic,
            "underline": self.underline,
            "color_rgb": self.color_rgb,
        }


@dataclass
class ParagraphFormatting:
    """Paragraph-level formatting information."""
    alignment: str = "left"    # left/center/right/justify
    line_spacing: float = 1.0
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0
    left_indent_pt: float = 0.0
    right_indent_pt: float = 0.0
    first_line_indent_pt: float = 0.0

    def to_dict(self) -> dict:
        return {
            "alignment": self.alignment,
            "line_spacing": self.line_spacing,
            "space_before_pt": self.space_before_pt,
            "space_after_pt": self.space_after_pt,
            "left_indent_pt": self.left_indent_pt,
            "right_indent_pt": self.right_indent_pt,
            "first_line_indent_pt": self.first_line_indent_pt,
        }


@dataclass
class RunFormatting:
    """Text fragment with formatting information."""
    text: str
    font: FontInfo

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "font": self.font.to_dict(),
        }


@dataclass
class ImageReference:
    """Reference to an embedded image."""
    filename: str              # From word/media/
    image_data_base64: str     # Base64 encoded binary
    width_inches: float
    height_inches: float
    content_type: str          # image/png, image/jpeg
    position_index: int        # Position in document

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "image_data_base64": self.image_data_base64,
            "width_inches": self.width_inches,
            "height_inches": self.height_inches,
            "content_type": self.content_type,
            "position_index": self.position_index,
        }


@dataclass
class CellFormatting:
    """Table cell formatting information."""
    background_color: Optional[tuple] = None  # RGB
    vertical_alignment: str = "top"

    def to_dict(self) -> dict:
        return {
            "background_color": self.background_color,
            "vertical_alignment": self.vertical_alignment,
        }


@dataclass
class TableFormatting:
    """Table-level formatting information."""
    alignment: str = "left"
    width_inches: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "alignment": self.alignment,
            "width_inches": self.width_inches,
        }


@dataclass
class PageSetup:
    """Page setup information."""
    page_width_inches: float = 8.5
    page_height_inches: float = 11.0
    left_margin_inches: float = 1.0
    right_margin_inches: float = 1.0
    top_margin_inches: float = 1.0
    bottom_margin_inches: float = 1.0
    orientation: str = "portrait"  # portrait or landscape

    def to_dict(self) -> dict:
        return {
            "page_width_inches": self.page_width_inches,
            "page_height_inches": self.page_height_inches,
            "left_margin_inches": self.left_margin_inches,
            "right_margin_inches": self.right_margin_inches,
            "top_margin_inches": self.top_margin_inches,
            "bottom_margin_inches": self.bottom_margin_inches,
            "orientation": self.orientation,
        }


@dataclass
class HeaderFooter:
    """Header or footer content."""
    paragraphs: list[str] = field(default_factory=list)
    runs: list[list[RunFormatting]] = field(default_factory=list)
    paragraph_formats: list[ParagraphFormatting] = field(default_factory=list)
    images: list[ImageReference] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "paragraphs": self.paragraphs,
            "runs": [[r.to_dict() for r in para_runs] for para_runs in self.runs],
            "paragraph_formats": [p.to_dict() for p in self.paragraph_formats],
            "images": [img.to_dict() for img in self.images],
        }


@dataclass
class DocumentElement:
    """Represents a single element in the document in exact order."""
    element_type: str  # "paragraph", "table", "image", "page_break", "heading"
    index: int  # Position in document
    content: Any = None  # The actual content (paragraph text, table data, image ref, etc.)
    formatting: Any = None  # Formatting information
    runs: list[RunFormatting] = field(default_factory=list)  # For paragraphs
    paragraph_format: Optional[ParagraphFormatting] = None  # For paragraphs
    heading_level: int = 0  # For headings
    style_name: str = ""  # Actual Word style name for exact recreation

    def to_dict(self) -> dict:
        result = {
            "element_type": self.element_type,
            "index": self.index,
            "heading_level": self.heading_level,
            "style_name": self.style_name,
        }

        if self.content is not None:
            if hasattr(self.content, 'to_dict'):
                result["content"] = self.content.to_dict()
            else:
                result["content"] = str(self.content)

        if self.runs:
            result["runs"] = [r.to_dict() for r in self.runs]

        if self.paragraph_format:
            result["paragraph_format"] = self.paragraph_format.to_dict()

        return result


@dataclass
class DocumentRequirementMatrix:
    """Matrix of document requirements per vendor/entity type."""
    document_name: str
    requirements: dict[str, str]  # vendor_type -> requirement (Mandatory, Optional, Not Required)

    def to_dict(self) -> dict:
        return {
            "document_name": self.document_name,
            "requirements": self.requirements,
        }


@dataclass
class ParsedDocument:
    """Complete parsed document representation."""
    file_path: str
    metadata: DocumentMetadata
    version_history: list[VersionEntry] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    # Extracted entities
    all_fields: list[FieldDefinition] = field(default_factory=list)
    initiator_fields: list[FieldDefinition] = field(default_factory=list)
    spoc_fields: list[FieldDefinition] = field(default_factory=list)
    approver_fields: list[FieldDefinition] = field(default_factory=list)

    workflows: dict[str, list[WorkflowStep]] = field(default_factory=dict)
    approval_rules: list[ApprovalRule] = field(default_factory=list)

    # Reference data
    reference_tables: list[TableData] = field(default_factory=list)
    terminology: dict[str, str] = field(default_factory=dict)
    dropdown_mappings: dict[str, list[str]] = field(default_factory=dict)

    # Template-specific (Vendor Creation)
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    integration_fields: list[IntegrationField] = field(default_factory=list)
    document_requirements: list[DocumentRequirementMatrix] = field(default_factory=list)

    # Communication templates
    communication_channels: list[str] = field(default_factory=list)

    # Raw data for debugging
    raw_tables: list[TableData] = field(default_factory=list)

    # Visual elements
    images: list[ImageReference] = field(default_factory=list)

    # Exact document structure (for perfect recreation)
    document_elements: list[DocumentElement] = field(default_factory=list)
    page_setup: Optional[PageSetup] = None
    header: Optional[HeaderFooter] = None
    footer: Optional[HeaderFooter] = None

    def to_dict(self) -> dict:
        """Convert entire parsed document to dictionary."""
        return {
            "file_path": self.file_path,
            "metadata": self.metadata.to_dict(),
            "version_history": [v.to_dict() for v in self.version_history],
            "sections": [s.to_dict() for s in self.sections],
            "all_fields": [f.to_dict() for f in self.all_fields],
            "initiator_fields": [f.to_dict() for f in self.initiator_fields],
            "spoc_fields": [f.to_dict() for f in self.spoc_fields],
            "approver_fields": [f.to_dict() for f in self.approver_fields],
            "workflows": {k: [w.to_dict() for w in v] for k, v in self.workflows.items()},
            "approval_rules": [a.to_dict() for a in self.approval_rules],
            "reference_tables": [t.to_dict() for t in self.reference_tables],
            "terminology": self.terminology,
            "dropdown_mappings": self.dropdown_mappings,
            "scope_in": self.scope_in,
            "scope_out": self.scope_out,
            "objectives": self.objectives,
            "assumptions": self.assumptions,
            "dependencies": self.dependencies,
            "integration_fields": [i.to_dict() for i in self.integration_fields],
            "document_requirements": [d.to_dict() for d in self.document_requirements],
            "communication_channels": self.communication_channels,
            "images": [img.to_dict() for img in self.images],
            "document_elements": [elem.to_dict() for elem in self.document_elements],
            "page_setup": self.page_setup.to_dict() if self.page_setup else None,
            "header": self.header.to_dict() if self.header else None,
            "footer": self.footer.to_dict() if self.footer else None,
        }
