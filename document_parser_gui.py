"""
Document Parser GUI Application
Graphical interface for parsing and viewing document extraction results
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
from pathlib import Path
from datetime import datetime
from doc_parser.parser import DocumentParser
from doc_parser.models import ParsedDocument


class DocumentParserGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Document Parser - OOXML Extractor")
        self.root.geometry("1400x900")

        self.parser = DocumentParser()
        self.current_document = None
        self.parsed_data = None

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""

        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Document Parser - OOXML Field Extractor",
            font=("Helvetica", 16, "bold")
        ).grid(row=0, column=0, sticky=tk.W)

        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Document Selection", padding="10")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)

        ttk.Button(
            file_frame,
            text="Select Document",
            command=self.select_document
        ).grid(row=0, column=0, padx=(0, 10))

        self.file_label = ttk.Label(file_frame, text="No document selected", foreground="gray")
        self.file_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Button(
            file_frame,
            text="Parse Document",
            command=self.parse_document,
            state=tk.DISABLED
        ).grid(row=0, column=2, padx=(10, 0))
        self.parse_button = file_frame.winfo_children()[-1]

        ttk.Button(
            file_frame,
            text="Export JSON",
            command=self.export_json,
            state=tk.DISABLED
        ).grid(row=0, column=3, padx=(10, 0))
        self.export_button = file_frame.winfo_children()[-1]

        # Results tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create tabs
        self.create_overview_tab()
        self.create_fields_tab()
        self.create_workflows_tab()
        self.create_tables_tab()
        self.create_metadata_tab()
        self.create_json_tab()
        self.create_recreation_tab()

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

    def create_overview_tab(self):
        """Create overview tab"""
        frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(frame, text="Overview")

        # Statistics frame
        stats_frame = ttk.LabelFrame(frame, text="Extraction Statistics", padding="10")
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.stats_text = scrolledtext.ScrolledText(
            stats_frame,
            wrap=tk.WORD,
            width=100,
            height=30,
            font=("Courier", 10)
        )
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        self.stats_text.config(state=tk.DISABLED)

    def create_fields_tab(self):
        """Create fields tab with treeview"""
        frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(frame, text="Fields")

        # Filter frame
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))

        self.field_filter = ttk.Combobox(
            filter_frame,
            values=["All Fields", "Initiator", "SPOC/Vendor", "Approver", "Mandatory Only"],
            state="readonly"
        )
        self.field_filter.set("All Fields")
        self.field_filter.pack(side=tk.LEFT, padx=(0, 10))
        self.field_filter.bind("<<ComboboxSelected>>", self.filter_fields)

        ttk.Label(filter_frame, text="Search:").pack(side=tk.LEFT, padx=(10, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.search_fields)
        ttk.Entry(filter_frame, textvariable=self.search_var, width=30).pack(side=tk.LEFT)

        # Treeview
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        self.fields_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "type", "mandatory", "section", "logic"),
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )

        vsb.config(command=self.fields_tree.yview)
        hsb.config(command=self.fields_tree.xview)

        # Configure columns
        self.fields_tree.heading("#0", text="ID")
        self.fields_tree.heading("name", text="Field Name")
        self.fields_tree.heading("type", text="Type")
        self.fields_tree.heading("mandatory", text="Mandatory")
        self.fields_tree.heading("section", text="Section")
        self.fields_tree.heading("logic", text="Logic/Rules")

        self.fields_tree.column("#0", width=50)
        self.fields_tree.column("name", width=250)
        self.fields_tree.column("type", width=120)
        self.fields_tree.column("mandatory", width=80)
        self.fields_tree.column("section", width=150)
        self.fields_tree.column("logic", width=400)

        # Grid layout
        self.fields_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))

        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

    def create_workflows_tab(self):
        """Create workflows tab"""
        frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(frame, text="Workflows")

        # Actor selector
        actor_frame = ttk.Frame(frame)
        actor_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(actor_frame, text="Select Actor:").pack(side=tk.LEFT, padx=(0, 5))

        self.workflow_actor = ttk.Combobox(
            actor_frame,
            values=["All Actors"],
            state="readonly"
        )
        self.workflow_actor.set("All Actors")
        self.workflow_actor.pack(side=tk.LEFT)
        self.workflow_actor.bind("<<ComboboxSelected>>", self.filter_workflows)

        # Workflow text area
        self.workflow_text = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            width=100,
            height=35,
            font=("Courier", 10)
        )
        self.workflow_text.pack(fill=tk.BOTH, expand=True)
        self.workflow_text.config(state=tk.DISABLED)

    def create_tables_tab(self):
        """Create tables tab"""
        frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(frame, text="Tables")

        self.tables_text = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            width=100,
            height=40,
            font=("Courier", 9)
        )
        self.tables_text.pack(fill=tk.BOTH, expand=True)
        self.tables_text.config(state=tk.DISABLED)

    def create_metadata_tab(self):
        """Create metadata tab"""
        frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(frame, text="Metadata")

        self.metadata_text = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            width=100,
            height=40,
            font=("Courier", 10)
        )
        self.metadata_text.pack(fill=tk.BOTH, expand=True)
        self.metadata_text.config(state=tk.DISABLED)

    def create_json_tab(self):
        """Create raw JSON tab"""
        frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(frame, text="Raw JSON")

        self.json_text = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            width=100,
            height=40,
            font=("Courier", 9)
        )
        self.json_text.pack(fill=tk.BOTH, expand=True)
        self.json_text.config(state=tk.DISABLED)

    def create_recreation_tab(self):
        """Create the recreation tab"""
        recreation_frame = ttk.Frame(self.notebook)
        self.notebook.add(recreation_frame, text="Recreation")

        # Configure grid
        recreation_frame.columnconfigure(0, weight=1)
        recreation_frame.rowconfigure(1, weight=1)

        # Controls frame
        controls_frame = ttk.LabelFrame(recreation_frame, text="Document Recreation", padding="10")
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Button(
            controls_frame,
            text="Recreate Document",
            command=self.recreate_document,
            state=tk.DISABLED
        ).grid(row=0, column=0, padx=5)

        self.recreate_button = controls_frame.winfo_children()[-1]

        # Status frame
        status_frame = ttk.LabelFrame(recreation_frame, text="Extraction Status", padding="10")
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)

        self.recreation_status = scrolledtext.ScrolledText(status_frame, height=15)
        self.recreation_status.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Images preview frame
        images_frame = ttk.LabelFrame(recreation_frame, text="Extracted Images", padding="10")
        images_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=10, pady=(0, 10))
        images_frame.columnconfigure(0, weight=1)

        self.images_list = tk.Listbox(images_frame, height=6)
        self.images_list.grid(row=0, column=0, sticky=(tk.W, tk.E))

    def select_document(self):
        """Open file dialog to select document"""
        filename = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")],
            initialdir="./documents"
        )

        if filename:
            self.current_document = filename
            self.file_label.config(text=Path(filename).name, foreground="black")
            self.parse_button.config(state=tk.NORMAL)
            self.status_var.set(f"Selected: {Path(filename).name}")

    def parse_document(self):
        """Parse the selected document"""
        if not self.current_document:
            messagebox.showwarning("No Document", "Please select a document first.")
            return

        try:
            self.status_var.set("Parsing document...")
            self.root.update()

            # Parse the document
            self.parsed_data = self.parser.parse(self.current_document)

            # Update all displays
            self.display_overview()
            self.display_fields()
            self.display_workflows()
            self.display_tables()
            self.display_metadata()
            self.display_json()
            self.update_recreation_view()

            # Enable export button
            self.export_button.config(state=tk.NORMAL)

            self.status_var.set("Parsing complete!")
            messagebox.showinfo(
                "Success",
                f"Document parsed successfully!\n\n"
                f"Fields extracted: {len(self.parsed_data.all_fields)}\n"
                f"Workflows: {sum(len(steps) for steps in self.parsed_data.workflows.values())} steps\n"
                f"Tables: {len(self.parsed_data.reference_tables)} reference tables"
            )

        except Exception as e:
            self.status_var.set("Parsing failed!")
            messagebox.showerror("Error", f"Failed to parse document:\n\n{str(e)}")
            import traceback
            traceback.print_exc()

    def display_overview(self):
        """Display overview statistics"""
        if not self.parsed_data:
            return

        text = []
        text.append("=" * 100)
        text.append("DOCUMENT PARSING OVERVIEW")
        text.append("=" * 100)
        text.append("")

        # Document info
        text.append(f"Document: {Path(self.current_document).name}")
        text.append(f"Parsed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        text.append("")

        # Statistics
        text.append("EXTRACTION STATISTICS:")
        text.append("-" * 100)
        text.append(f"  Total Fields:                    {len(self.parsed_data.all_fields)}")
        text.append(f"  Initiator Fields:                {len(self.parsed_data.initiator_fields)}")
        text.append(f"  SPOC/Vendor Fields:              {len(self.parsed_data.spoc_fields)}")
        text.append(f"  Approver Fields:                 {len(self.parsed_data.approver_fields)}")
        text.append("")

        total_workflow_steps = sum(len(steps) for steps in self.parsed_data.workflows.values())
        text.append(f"  Total Workflow Steps:            {total_workflow_steps}")
        for actor, steps in self.parsed_data.workflows.items():
            text.append(f"    - {actor.capitalize()}: {len(steps)} steps")
        text.append("")

        # Count tables by source
        word_tables = [t for t in self.parsed_data.reference_tables if t.source == "document"]
        excel_tables = [t for t in self.parsed_data.reference_tables if t.source == "excel"]

        text.append(f"  Reference Tables:                {len(self.parsed_data.reference_tables)}")
        text.append(f"    - From Word document:          {len(word_tables)}")
        text.append(f"    - From Excel files:            {len(excel_tables)}")
        text.append(f"  Version History Entries:         {len(self.parsed_data.version_history)}")
        text.append(f"  Terminology Mappings:            {len(self.parsed_data.terminology)}")
        text.append(f"  Dropdown Mappings:               {len(self.parsed_data.dropdown_mappings)}")
        text.append(f"  Document Requirements:           {len(self.parsed_data.document_requirements)}")
        text.append(f"  Approval Rules:                  {len(self.parsed_data.approval_rules)}")
        text.append("")

        # Field type distribution
        text.append("FIELD TYPE DISTRIBUTION:")
        text.append("-" * 100)

        field_types = {}
        for field in self.parsed_data.all_fields:
            ft = field.field_type.value
            field_types[ft] = field_types.get(ft, 0) + 1

        for field_type, count in sorted(field_types.items(), key=lambda x: -x[1]):
            percentage = (count / len(self.parsed_data.all_fields)) * 100
            text.append(f"  {field_type:25s} : {count:4d} ({percentage:5.1f}%)")

        text.append("")

        # Mandatory vs Optional
        text.append("FIELD MANDATORY STATUS:")
        text.append("-" * 100)
        mandatory = sum(1 for f in self.parsed_data.all_fields if f.is_mandatory)
        optional = len(self.parsed_data.all_fields) - mandatory

        text.append(f"  Mandatory: {mandatory:4d} ({(mandatory/len(self.parsed_data.all_fields)*100):5.1f}%)")
        text.append(f"  Optional:  {optional:4d} ({(optional/len(self.parsed_data.all_fields)*100):5.1f}%)")

        # Update text widget
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, "\n".join(text))
        self.stats_text.config(state=tk.DISABLED)

    def display_fields(self):
        """Display fields in tree view"""
        if not self.parsed_data:
            return

        # Clear existing items
        for item in self.fields_tree.get_children():
            self.fields_tree.delete(item)

        # Add all fields
        for i, field in enumerate(self.parsed_data.all_fields, 1):
            self.fields_tree.insert(
                "",
                tk.END,
                text=str(i),
                values=(
                    field.name,
                    field.field_type.value,
                    "Yes" if field.is_mandatory else "No",
                    field.section or "-",
                    (field.logic[:100] + "...") if len(field.logic) > 100 else field.logic
                ),
                tags=(self._get_field_category(field),)
            )

        # Configure tag colors
        self.fields_tree.tag_configure("initiator", background="#e3f2fd")
        self.fields_tree.tag_configure("spoc", background="#fff3e0")
        self.fields_tree.tag_configure("approver", background="#f3e5f5")

    def _get_field_category(self, field):
        """Get field category for coloring"""
        if field in self.parsed_data.initiator_fields:
            return "initiator"
        elif field in self.parsed_data.spoc_fields:
            return "spoc"
        elif field in self.parsed_data.approver_fields:
            return "approver"
        return ""

    def filter_fields(self, event=None):
        """Filter fields based on selection"""
        if not self.parsed_data:
            return

        filter_value = self.field_filter.get()

        # Clear existing
        for item in self.fields_tree.get_children():
            self.fields_tree.delete(item)

        # Select fields based on filter
        if filter_value == "All Fields":
            fields = self.parsed_data.all_fields
        elif filter_value == "Initiator":
            fields = self.parsed_data.initiator_fields
        elif filter_value == "SPOC/Vendor":
            fields = self.parsed_data.spoc_fields
        elif filter_value == "Approver":
            fields = self.parsed_data.approver_fields
        elif filter_value == "Mandatory Only":
            fields = [f for f in self.parsed_data.all_fields if f.is_mandatory]
        else:
            fields = self.parsed_data.all_fields

        # Add filtered fields
        for i, field in enumerate(fields, 1):
            self.fields_tree.insert(
                "",
                tk.END,
                text=str(i),
                values=(
                    field.name,
                    field.field_type.value,
                    "Yes" if field.is_mandatory else "No",
                    field.section or "-",
                    (field.logic[:100] + "...") if len(field.logic) > 100 else field.logic
                ),
                tags=(self._get_field_category(field),)
            )

    def search_fields(self, *args):
        """Search fields by name"""
        if not self.parsed_data:
            return

        search_term = self.search_var.get().lower()

        # Clear existing
        for item in self.fields_tree.get_children():
            self.fields_tree.delete(item)

        # Filter by search term
        fields = [f for f in self.parsed_data.all_fields if search_term in f.name.lower()]

        # Add matching fields
        for i, field in enumerate(fields, 1):
            self.fields_tree.insert(
                "",
                tk.END,
                text=str(i),
                values=(
                    field.name,
                    field.field_type.value,
                    "Yes" if field.is_mandatory else "No",
                    field.section or "-",
                    (field.logic[:100] + "...") if len(field.logic) > 100 else field.logic
                ),
                tags=(self._get_field_category(field),)
            )

    def display_workflows(self):
        """Display workflows"""
        if not self.parsed_data:
            return

        # Update actor combobox
        actors = ["All Actors"] + list(self.parsed_data.workflows.keys())
        self.workflow_actor.config(values=actors)

        # Display all workflows
        self.update_workflow_display()

    def filter_workflows(self, event=None):
        """Filter workflows by actor"""
        self.update_workflow_display()

    def update_workflow_display(self):
        """Update workflow text display"""
        if not self.parsed_data:
            return

        actor_filter = self.workflow_actor.get()

        text = []
        text.append("=" * 100)
        text.append("WORKFLOW STEPS")
        text.append("=" * 100)
        text.append("")

        # Select workflows to display
        if actor_filter == "All Actors":
            workflows = self.parsed_data.workflows
        else:
            workflows = {actor_filter: self.parsed_data.workflows.get(actor_filter, [])}

        for actor, steps in workflows.items():
            text.append(f"{actor.upper()} WORKFLOW ({len(steps)} steps)")
            text.append("-" * 100)
            text.append("")

            for step in steps:
                action_info = f" [{step.action_type}]" if step.action_type else ""
                text.append(f"Step {step.step_number}: {step.description}{action_info}")

                if step.conditions:
                    text.append(f"  Conditions: {', '.join(step.conditions)}")
                if step.notes:
                    text.append(f"  Notes: {', '.join(step.notes)}")
                text.append("")

            text.append("")

        self.workflow_text.config(state=tk.NORMAL)
        self.workflow_text.delete(1.0, tk.END)
        self.workflow_text.insert(1.0, "\n".join(text))
        self.workflow_text.config(state=tk.DISABLED)

    def display_tables(self):
        """Display reference tables with full data"""
        if not self.parsed_data:
            return

        text = []
        text.append("=" * 120)
        text.append("REFERENCE TABLES")
        text.append("=" * 120)
        text.append("")

        # Count tables by source
        word_tables = [t for t in self.parsed_data.reference_tables if t.source == "document"]
        excel_tables = [t for t in self.parsed_data.reference_tables if t.source == "excel"]

        text.append(f"Total: {len(self.parsed_data.reference_tables)} reference tables")
        text.append(f"  • From Word document: {len(word_tables)}")
        text.append(f"  • From Excel files: {len(excel_tables)}")
        text.append("")
        text.append("=" * 120)
        text.append("")

        for i, table in enumerate(self.parsed_data.reference_tables, 1):
            # Show source information
            if table.source == "excel":
                text.append(f"📊 TABLE {i}: {table.table_type.upper()}")
                text.append(f"   Source: EXCEL FILE - {table.source_file}")
                text.append(f"   Sheet: {table.sheet_name}")
            else:
                text.append(f"📄 TABLE {i}: {table.table_type.upper()}")
                text.append(f"   Source: WORD DOCUMENT")

            text.append(f"   Context: {table.context}")
            text.append(f"   Size: {table.row_count} rows × {table.column_count} columns")
            text.append("")

            # Display data in formatted table
            if table.headers and table.rows:
                # Calculate column widths
                col_widths = []
                for col_idx, header in enumerate(table.headers):
                    max_width = len(str(header))
                    for row in table.rows[:50]:  # Check first 50 rows for width
                        if col_idx < len(row):
                            max_width = max(max_width, len(str(row[col_idx])))
                    # Cap width at 30 characters for display
                    col_widths.append(min(max_width + 2, 30))

                # Print headers
                header_line = "   │ "
                separator_line = "   ├─"
                for idx, header in enumerate(table.headers):
                    header_text = str(header)[:col_widths[idx]-2]
                    header_line += f"{header_text:<{col_widths[idx]}} │ "
                    separator_line += "─" * col_widths[idx] + "─┼─"

                text.append("   ┌─" + "─" * (len(header_line) - 6) + "─┐")
                text.append(header_line)
                text.append(separator_line[:-2] + "┤")

                # Print all rows (or first 100 for very large tables)
                display_limit = 100 if table.source == "excel" else 50
                rows_to_display = table.rows[:display_limit]

                for row in rows_to_display:
                    row_line = "   │ "
                    for col_idx, cell in enumerate(row):
                        if col_idx < len(table.headers):
                            cell_text = str(cell)[:col_widths[col_idx]-2]
                            row_line += f"{cell_text:<{col_widths[col_idx]}} │ "
                    text.append(row_line)

                text.append("   └─" + "─" * (len(header_line) - 6) + "─┘")

                # Show count if there are more rows
                if table.row_count > display_limit:
                    text.append(f"   ... and {table.row_count - display_limit} more rows (total: {table.row_count} rows)")
                else:
                    text.append(f"   Total: {table.row_count} rows displayed")

            else:
                text.append("   (No data available)")

            text.append("")
            text.append("-" * 120)
            text.append("")

        if not self.parsed_data.reference_tables:
            text.append("No reference tables found.")
            text.append("")

        self.tables_text.config(state=tk.NORMAL)
        self.tables_text.delete(1.0, tk.END)
        self.tables_text.insert(1.0, "\n".join(text))
        self.tables_text.config(state=tk.DISABLED)

    def display_metadata(self):
        """Display document metadata"""
        if not self.parsed_data:
            return

        text = []
        text.append("=" * 100)
        text.append("DOCUMENT METADATA")
        text.append("=" * 100)
        text.append("")

        # Core properties
        text.append("CORE PROPERTIES:")
        text.append("-" * 100)
        meta = self.parsed_data.metadata
        text.append(f"  Title:              {meta.title}")
        text.append(f"  Author:             {meta.author}")
        text.append(f"  Subject:            {meta.subject}")
        text.append(f"  Created:            {meta.created}")
        text.append(f"  Modified:           {meta.modified}")
        text.append(f"  Last Modified By:   {meta.last_modified_by}")
        text.append(f"  Process Name:       {meta.process_name}")
        text.append("")

        # Version history
        if self.parsed_data.version_history:
            text.append("VERSION HISTORY:")
            text.append("-" * 100)
            for entry in self.parsed_data.version_history:
                text.append(f"  Version:      {entry.version}")
                text.append(f"  Date:         {entry.revision_date}")
                text.append(f"  Author:       {entry.author}")
                text.append(f"  Approved By:  {entry.approved_by}")
                text.append(f"  Description:  {entry.description}")
                text.append("")

        # Terminology
        if self.parsed_data.terminology:
            text.append("TERMINOLOGY MAPPINGS:")
            text.append("-" * 100)
            for term, definition in self.parsed_data.terminology.items():
                text.append(f"  {term} → {definition}")
            text.append("")

        # Document requirements
        if self.parsed_data.document_requirements:
            text.append("DOCUMENT REQUIREMENTS MATRIX:")
            text.append("-" * 100)
            for req in self.parsed_data.document_requirements:
                text.append(f"  Document: {req.document_name}")
                text.append(f"  Requirements: {req.requirements}")
                text.append("")

        self.metadata_text.config(state=tk.NORMAL)
        self.metadata_text.delete(1.0, tk.END)
        self.metadata_text.insert(1.0, "\n".join(text))
        self.metadata_text.config(state=tk.DISABLED)

    def display_json(self):
        """Display raw JSON output"""
        if not self.parsed_data:
            return

        json_str = json.dumps(self.parsed_data.to_dict(), indent=2)

        self.json_text.config(state=tk.NORMAL)
        self.json_text.delete(1.0, tk.END)
        self.json_text.insert(1.0, json_str)
        self.json_text.config(state=tk.DISABLED)

    def recreate_document(self):
        """Handle document recreation with EVERYTHING preserved"""
        if not self.parsed_data:
            messagebox.showwarning("No Data", "Please parse a document first")
            return

        # Create output directory
        output_dir = Path("recreated_docs")
        output_dir.mkdir(exist_ok=True)

        # Generate output filename
        original_name = Path(self.parsed_data.file_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{original_name}_EXACT_COPY_{timestamp}.docx"

        try:
            self.status_var.set("Creating EXACT copy with ALL elements...")
            self.root.update()

            # Use comprehensive recreator that preserves EVERYTHING
            from doc_parser.comprehensive_recreator import ComprehensiveRecreator
            recreator = ComprehensiveRecreator(self.parsed_data)
            success = recreator.recreate_comprehensive(str(output_path))

            if success:
                messagebox.showinfo(
                    "Success",
                    f"EXACT document copy created!\n\n"
                    f"ALL elements preserved:\n"
                    f"• Letterheads and logos\n"
                    f"• Background colors\n"
                    f"• Image positions\n"
                    f"• Text boxes and shapes\n"
                    f"• All formatting\n\n"
                    f"Saved to: {output_path}"
                )
                self.status_var.set(f"EXACT copy created: {output_path}")
            else:
                messagebox.showerror("Error", "Failed to create exact copy")
                self.status_var.set("Recreation failed")
        except Exception as e:
            messagebox.showerror("Error", f"Recreation error: {str(e)}")
            self.status_var.set("Recreation error")
            import traceback
            traceback.print_exc()

    def update_recreation_view(self):
        """Update recreation tab with extraction status"""
        if not self.parsed_data:
            return

        # Clear status
        self.recreation_status.delete(1.0, tk.END)

        # Display extraction stats
        status_text = "COMPREHENSIVE EXTRACTION SUMMARY:\n"
        status_text += "=" * 70 + "\n\n"

        # Document structure
        status_text += "Document Structure:\n"
        status_text += "-" * 70 + "\n"
        status_text += f"  Total elements: {len(self.parsed_data.document_elements)}\n"
        status_text += f"  Paragraphs: {len([e for e in self.parsed_data.document_elements if e.element_type == 'paragraph'])}\n"
        status_text += f"  Headings: {len([e for e in self.parsed_data.document_elements if e.element_type == 'heading'])}\n"
        status_text += f"  Tables: {len(self.parsed_data.raw_tables)}\n"
        status_text += f"  Images: {len(self.parsed_data.images)}\n\n"

        # Page setup
        if self.parsed_data.page_setup:
            status_text += "Page Setup:\n"
            status_text += "-" * 70 + "\n"
            ps = self.parsed_data.page_setup
            status_text += f"  Size: {ps.page_width_inches:.2f}\" x {ps.page_height_inches:.2f}\"\n"
            status_text += f"  Margins: L={ps.left_margin_inches:.2f}\" R={ps.right_margin_inches:.2f}\" "
            status_text += f"T={ps.top_margin_inches:.2f}\" B={ps.bottom_margin_inches:.2f}\"\n"
            status_text += f"  Orientation: {ps.orientation.title()}\n\n"

        # Headers and Footers (Letterheads)
        status_text += "Headers & Footers:\n"
        status_text += "-" * 70 + "\n"
        if self.parsed_data.header:
            status_text += f"  ✓ Header: {len(self.parsed_data.header.paragraphs)} paragraphs\n"
            status_text += f"    (Includes letterhead/logos)\n"
        else:
            status_text += "  ✗ No header\n"

        if self.parsed_data.footer:
            status_text += f"  ✓ Footer: {len(self.parsed_data.footer.paragraphs)} paragraphs\n"
        else:
            status_text += "  ✗ No footer\n"
        status_text += "\n"

        # Visual Elements
        status_text += "Visual Elements Extracted:\n"
        status_text += "-" * 70 + "\n"
        status_text += f"  ✓ {len(self.parsed_data.images)} images with formatting\n"

        # Count formatted elements
        formatted_paras = sum(1 for e in self.parsed_data.document_elements
                             if e.runs and len(e.runs) > 0)
        status_text += f"  ✓ {formatted_paras} elements with font formatting\n"

        # Count elements with paragraph formatting
        para_formatted = sum(1 for e in self.parsed_data.document_elements
                            if e.paragraph_format is not None)
        status_text += f"  ✓ {para_formatted} elements with paragraph formatting\n"

        # Check for background colors in tables
        tables_with_formatting = sum(1 for t in self.parsed_data.raw_tables
                                    if hasattr(t, 'cell_formats') and t.cell_formats)
        status_text += f"  ✓ {tables_with_formatting} tables with cell formatting/colors\n"

        status_text += "\n"
        status_text += "=" * 70 + "\n"
        status_text += "RECREATION MODE: EXACT COPY\n"
        status_text += "-" * 70 + "\n"
        status_text += "The recreation will create an EXACT copy that preserves:\n"
        status_text += "  • ALL letterheads and logos\n"
        status_text += "  • ALL background colors and shading\n"
        status_text += "  • ALL image positions (inline, floating, anchored)\n"
        status_text += "  • ALL text boxes and shapes\n"
        status_text += "  • ALL borders and formatting\n"
        status_text += "  • EXACT page layout and structure\n"
        status_text += "  • EVERYTHING from the original document\n"
        status_text += "=" * 70 + "\n"

        self.recreation_status.insert(1.0, status_text)

        # Populate images list
        self.images_list.delete(0, tk.END)
        for img in self.parsed_data.images:
            self.images_list.insert(tk.END, f"{img.filename} ({img.content_type}) - {img.width_inches:.2f}\" x {img.height_inches:.2f}\"")

        # Enable recreate button
        self.recreate_button.config(state=tk.NORMAL)

    def export_json(self):
        """Export parsed data to JSON file"""
        if not self.parsed_data:
            messagebox.showwarning("No Data", "Please parse a document first.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export JSON",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=Path(self.current_document).stem + "_parsed.json"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.parsed_data.to_dict(), f, indent=2)

                self.status_var.set(f"Exported to: {Path(filename).name}")
                messagebox.showinfo("Success", f"Data exported successfully to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export:\n{str(e)}")


def main():
    root = tk.Tk()
    app = DocumentParserGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
