"""
Enhanced Document Parser GUI Application with AI Rules Extraction
Graphical interface for parsing and viewing document extraction results with rules
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
from pathlib import Path
from datetime import datetime
import threading
from doc_parser.parser import DocumentParser
from doc_parser.models import ParsedDocument

# Import rules extractor
try:
    from rules_extractor import RulesExtractor, FieldWithRules
    RULES_AVAILABLE = True
except ImportError:
    RULES_AVAILABLE = False
    print("⚠️  Rules extraction not available. Install requirements: pip install openai python-dotenv")


class DocumentParserGUIEnhanced:
    def __init__(self, root):
        self.root = root
        self.root.title("Document Parser - OOXML Extractor with AI Rules")
        self.root.geometry("1400x900")

        self.parser = DocumentParser()
        self.current_document = None
        self.parsed_data = None
        self.fields_with_rules = []
        self.rules_extractor = None

        # Initialize rules extractor if available
        if RULES_AVAILABLE:
            try:
                self.rules_extractor = RulesExtractor()
                print(f"✓ Rules Extractor initialized with {len(self.rules_extractor.knowledge_base.rules)} rules")
            except Exception as e:
                print(f"⚠️  Could not initialize Rules Extractor: {e}")
                self.rules_extractor = None

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

        title_text = "Document Parser - OOXML Field Extractor"
        if RULES_AVAILABLE and self.rules_extractor:
            title_text += " with AI Rules"

        ttk.Label(
            header_frame,
            text=title_text,
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

        self.parse_button = ttk.Button(
            file_frame,
            text="Parse Document",
            command=self.parse_document,
            state=tk.DISABLED
        )
        self.parse_button.grid(row=0, column=2, padx=(10, 0))

        # Rules extraction button
        if RULES_AVAILABLE and self.rules_extractor:
            self.extract_rules_button = ttk.Button(
                file_frame,
                text="🤖 Extract Rules",
                command=self.extract_rules_dialog,
                state=tk.DISABLED
            )
            self.extract_rules_button.grid(row=0, column=3, padx=(10, 0))

        self.export_button = ttk.Button(
            file_frame,
            text="Export JSON",
            command=self.export_json,
            state=tk.DISABLED
        )
        self.export_button.grid(row=0, column=4, padx=(10, 0))

        # Results tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create tabs
        self.create_overview_tab()
        self.create_fields_tab()

        # Add Rules tab if available
        if RULES_AVAILABLE and self.rules_extractor:
            self.create_rules_tab()

        self.create_workflows_tab()
        self.create_tables_tab()
        self.create_metadata_tab()
        self.create_json_tab()

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
        """Create overview tab with statistics"""
        overview_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(overview_frame, text="Overview")

        # Statistics container
        stats_frame = ttk.LabelFrame(overview_frame, text="Document Statistics", padding="10")
        stats_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))

        self.stats_text = scrolledtext.ScrolledText(
            stats_frame,
            wrap=tk.WORD,
            width=80,
            height=15,
            font=("Courier", 10)
        )
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        stats_frame.rowconfigure(0, weight=1)
        stats_frame.columnconfigure(0, weight=1)

        # Rules statistics (if available)
        if RULES_AVAILABLE and self.rules_extractor:
            rules_stats_frame = ttk.LabelFrame(overview_frame, text="Rules Extraction Statistics", padding="10")
            rules_stats_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))

            self.rules_stats_text = scrolledtext.ScrolledText(
                rules_stats_frame,
                wrap=tk.WORD,
                width=80,
                height=10,
                font=("Courier", 10)
            )
            self.rules_stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            rules_stats_frame.rowconfigure(0, weight=1)
            rules_stats_frame.columnconfigure(0, weight=1)

    def create_fields_tab(self):
        """Create fields tab with field listing"""
        fields_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(fields_frame, text="Fields")

        # Filter controls
        filter_frame = ttk.Frame(fields_frame)
        filter_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(filter_frame, text="Filter:").grid(row=0, column=0, padx=(0, 5))

        self.field_filter_var = tk.StringVar(value="all")
        filters = [
            ("All Fields", "all"),
            ("Initiator", "initiator"),
            ("SPOC", "spoc"),
            ("Approver", "approver"),
            ("Mandatory Only", "mandatory")
        ]

        for i, (text, value) in enumerate(filters):
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self.field_filter_var,
                value=value,
                command=self.update_fields_view
            ).grid(row=0, column=i+1, padx=5)

        # Search
        ttk.Label(filter_frame, text="Search:").grid(row=0, column=len(filters)+1, padx=(20, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.update_fields_view())
        ttk.Entry(filter_frame, textvariable=self.search_var, width=30).grid(row=0, column=len(filters)+2)

        # Fields table
        table_frame = ttk.Frame(fields_frame)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        fields_frame.rowconfigure(1, weight=1)
        fields_frame.columnconfigure(0, weight=1)

        # Create treeview
        columns = ("name", "type", "mandatory", "logic")
        self.fields_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=20
        )

        # Define headings
        self.fields_tree.heading("name", text="Field Name", command=lambda: self.sort_column("name"))
        self.fields_tree.heading("type", text="Type", command=lambda: self.sort_column("type"))
        self.fields_tree.heading("mandatory", text="Mandatory", command=lambda: self.sort_column("mandatory"))
        self.fields_tree.heading("logic", text="Logic/Rules")

        # Define column widths
        self.fields_tree.column("name", width=250)
        self.fields_tree.column("type", width=100)
        self.fields_tree.column("mandatory", width=80)
        self.fields_tree.column("logic", width=500)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.fields_tree.yview)
        self.fields_tree.configure(yscrollcommand=scrollbar.set)

        self.fields_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

    def create_rules_tab(self):
        """Create rules extraction tab"""
        rules_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(rules_frame, text="🤖 Rules")

        # Info panel with Extract button
        info_frame = ttk.LabelFrame(rules_frame, text="Rules Extraction", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        info_frame.columnconfigure(0, weight=1)

        info_text = (
            "This tab shows AI-extracted rules from field logic using OpenAI.\n"
            f"Knowledge Base: {len(self.rules_extractor.knowledge_base.rules)} predefined rules loaded."
        )
        ttk.Label(info_frame, text=info_text, foreground="blue").grid(row=0, column=0, columnspan=2, sticky=tk.W)

        # Extract Rules button in the tab - on its own row for visibility
        button_frame = ttk.Frame(info_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(10, 5))

        self.rules_tab_extract_button = ttk.Button(
            button_frame,
            text="🤖 Extract Rules from Document",
            command=self.extract_rules_dialog,
            state=tk.DISABLED
        )
        self.rules_tab_extract_button.pack(side=tk.LEFT)

        # Status label
        self.rules_status_var = tk.StringVar(value="Parse a document first to enable rules extraction")
        ttk.Label(button_frame, textvariable=self.rules_status_var, foreground="gray", font=("", 9, "italic")).pack(
            side=tk.LEFT, padx=(15, 0)
        )

        # Filter controls
        filter_frame = ttk.Frame(rules_frame)
        filter_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(filter_frame, text="Filter by Confidence:").grid(row=0, column=0, padx=(0, 5))

        self.rules_filter_var = tk.StringVar(value="all")
        rule_filters = [
            ("All", "all"),
            ("High (≥0.8)", "high"),
            ("Medium (0.5-0.8)", "medium"),
            ("Low (<0.5)", "low")
        ]

        for i, (text, value) in enumerate(rule_filters):
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self.rules_filter_var,
                value=value,
                command=self.update_rules_view
            ).grid(row=0, column=i+1, padx=5)

        ttk.Label(filter_frame, text="Rule Type:").grid(row=0, column=len(rule_filters)+1, padx=(20, 5))

        self.rules_type_var = tk.StringVar(value="all")
        type_filters = [
            ("All", "all"),
            ("Expression", "expression"),
            ("Standard", "standard")
        ]

        for i, (text, value) in enumerate(type_filters):
            ttk.Radiobutton(
                filter_frame,
                text=text,
                variable=self.rules_type_var,
                value=value,
                command=self.update_rules_view
            ).grid(row=0, column=len(rule_filters)+i+2, padx=5)

        # Rules table
        table_frame = ttk.Frame(rules_frame)
        table_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        rules_frame.rowconfigure(2, weight=1)
        rules_frame.columnconfigure(0, weight=1)

        # Create treeview with different columns
        columns = ("field", "rule_name", "action", "source", "destination", "condition", "confidence")
        self.rules_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=20
        )

        # Define headings
        self.rules_tree.heading("field", text="Field Name")
        self.rules_tree.heading("rule_name", text="Rule Name")
        self.rules_tree.heading("action", text="Action")
        self.rules_tree.heading("source", text="Source")
        self.rules_tree.heading("destination", text="Destination")
        self.rules_tree.heading("condition", text="Condition")
        self.rules_tree.heading("confidence", text="Confidence")

        # Define column widths
        self.rules_tree.column("field", width=150)
        self.rules_tree.column("rule_name", width=200)
        self.rules_tree.column("action", width=90)
        self.rules_tree.column("source", width=150)
        self.rules_tree.column("destination", width=150)
        self.rules_tree.column("condition", width=300)
        self.rules_tree.column("confidence", width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.rules_tree.yview)
        self.rules_tree.configure(yscrollcommand=scrollbar.set)

        self.rules_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Bind double-click to show details
        self.rules_tree.bind("<Double-1>", self.show_rule_details)

        # Details panel
        details_frame = ttk.LabelFrame(rules_frame, text="Rule Details", padding="10")
        details_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        self.rules_details_text = scrolledtext.ScrolledText(
            details_frame,
            wrap=tk.WORD,
            width=80,
            height=6,
            font=("Courier", 9)
        )
        self.rules_details_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        details_frame.columnconfigure(0, weight=1)

    def create_workflows_tab(self):
        """Create workflows tab"""
        workflows_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(workflows_frame, text="Workflows")

        self.workflows_text = scrolledtext.ScrolledText(
            workflows_frame,
            wrap=tk.WORD,
            width=80,
            height=30,
            font=("Courier", 10)
        )
        self.workflows_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        workflows_frame.rowconfigure(0, weight=1)
        workflows_frame.columnconfigure(0, weight=1)

    def create_tables_tab(self):
        """Create tables tab"""
        tables_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tables_frame, text="Tables")

        self.tables_text = scrolledtext.ScrolledText(
            tables_frame,
            wrap=tk.WORD,
            width=80,
            height=30,
            font=("Courier", 10)
        )
        self.tables_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tables_frame.rowconfigure(0, weight=1)
        tables_frame.columnconfigure(0, weight=1)

    def create_metadata_tab(self):
        """Create metadata tab"""
        metadata_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(metadata_frame, text="Metadata")

        self.metadata_text = scrolledtext.ScrolledText(
            metadata_frame,
            wrap=tk.WORD,
            width=80,
            height=30,
            font=("Courier", 10)
        )
        self.metadata_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        metadata_frame.rowconfigure(0, weight=1)
        metadata_frame.columnconfigure(0, weight=1)

    def create_json_tab(self):
        """Create JSON tab"""
        json_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(json_frame, text="Raw JSON")

        self.json_text = scrolledtext.ScrolledText(
            json_frame,
            wrap=tk.WORD,
            width=80,
            height=30,
            font=("Courier", 9)
        )
        self.json_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        json_frame.rowconfigure(0, weight=1)
        json_frame.columnconfigure(0, weight=1)

    def select_document(self):
        """Open file dialog to select document"""
        filename = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")]
        )

        if filename:
            self.current_document = filename
            self.file_label.config(text=Path(filename).name, foreground="black")
            self.parse_button.config(state=tk.NORMAL)
            self.status_var.set(f"Selected: {Path(filename).name}")

    def parse_document(self):
        """Parse the selected document"""
        if not self.current_document:
            messagebox.showwarning("No Document", "Please select a document first")
            return

        self.status_var.set("Parsing document...")
        self.root.update()

        try:
            self.parsed_data = self.parser.parse(self.current_document)
            self.update_all_views()
            self.export_button.config(state=tk.NORMAL)

            if RULES_AVAILABLE and self.rules_extractor:
                self.extract_rules_button.config(state=tk.NORMAL)
                if hasattr(self, 'rules_tab_extract_button'):
                    self.rules_tab_extract_button.config(state=tk.NORMAL)
                    self.rules_status_var.set(f"Ready! Click 'Extract Rules' to process {len(self.parsed_data.all_fields)} fields")

            self.status_var.set(f"Parsed successfully - {len(self.parsed_data.all_fields)} fields found")
            messagebox.showinfo("Success", f"Document parsed successfully!\nFound {len(self.parsed_data.all_fields)} fields")

        except Exception as e:
            self.status_var.set("Error parsing document")
            messagebox.showerror("Error", f"Failed to parse document:\n{str(e)}")

    def extract_rules_dialog(self):
        """Show dialog to configure rules extraction"""
        if not self.parsed_data:
            messagebox.showwarning("No Document", "Please parse a document first")
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Extract Rules")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Content frame
        content_frame = ttk.Frame(dialog, padding="20")
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Info
        info_text = (
            f"Document has {len(self.parsed_data.all_fields)} fields.\n\n"
            "Rules extraction uses OpenAI to convert natural language logic to JSON rules.\n"
            "Processing all fields may take several minutes.\n\n"
            "Estimated cost: ~$0.0003 per field"
        )
        ttk.Label(content_frame, text=info_text, justify=tk.LEFT).pack(pady=(0, 20))

        # Number of fields selector
        selector_frame = ttk.Frame(content_frame)
        selector_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(selector_frame, text="Number of fields to process:").pack(side=tk.LEFT, padx=(0, 10))

        num_fields_var = tk.IntVar(value=min(20, len(self.parsed_data.all_fields)))
        num_fields_spinbox = ttk.Spinbox(
            selector_frame,
            from_=1,
            to=len(self.parsed_data.all_fields),
            textvariable=num_fields_var,
            width=10
        )
        num_fields_spinbox.pack(side=tk.LEFT)

        # Progress
        progress_frame = ttk.Frame(content_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 20))

        progress_label = ttk.Label(progress_frame, text="")
        progress_label.pack()

        progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        progress_bar.pack(fill=tk.X, pady=(5, 0))

        # Buttons
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X)

        def start_extraction():
            num_fields = num_fields_var.get()
            extract_button.config(state=tk.DISABLED)
            cancel_button.config(text="Close", state=tk.DISABLED)

            progress_bar['maximum'] = num_fields
            progress_bar['value'] = 0

            def extraction_thread():
                try:
                    from variable_name_generator import generate_variable_names

                    # Step 1: Generate variable names for ALL fields first
                    generate_variable_names(self.parsed_data.all_fields)

                    # Step 2: Set field map in rules extractor
                    self.rules_extractor.set_field_map(self.parsed_data.all_fields)

                    # Step 3: Extract rules for selected fields
                    fields_to_process = self.parsed_data.all_fields[:num_fields]
                    self.fields_with_rules = []

                    for i, field in enumerate(fields_to_process):
                        progress_label.config(text=f"Processing {i+1}/{num_fields}: {field.name}")
                        progress_bar['value'] = i + 1
                        dialog.update()

                        rules = self.rules_extractor.extract_rules_with_llm(field)
                        src_dest_info = self.rules_extractor.extract_source_destination_info(field.logic)

                        field_with_rules = FieldWithRules(
                            field_name=field.name,
                            field_type=field.field_type.name,
                            variable_name=field.variable_name,  # Include variable name
                            is_mandatory=field.is_mandatory,
                            original_logic=field.logic,
                            extracted_rules=rules,
                            source_info=src_dest_info.get('source'),
                            has_validation=any(r.action in ['VALIDATION', 'OCR', 'COMPARE'] for r in rules),
                            has_visibility_rules=any('visible' in r.rule_name.lower() for r in rules),
                            has_mandatory_rules=any('mandatory' in r.rule_name.lower() for r in rules)
                        )

                        self.fields_with_rules.append(field_with_rules)

                    # Update views
                    self.root.after(0, lambda: self.update_rules_view())
                    self.root.after(0, lambda: self.update_rules_stats())

                    progress_label.config(text=f"✓ Complete! Extracted rules from {num_fields} fields")
                    cancel_button.config(state=tk.NORMAL, text="Close")

                    total_rules = sum(len(f.extracted_rules) for f in self.fields_with_rules)

                    # Update status in Rules tab
                    if hasattr(self, 'rules_status_var'):
                        self.root.after(0, lambda: self.rules_status_var.set(
                            f"✓ Extraction complete! {num_fields} fields processed, {total_rules} rules extracted"
                        ))

                    self.root.after(0, lambda: messagebox.showinfo(
                        "Success",
                        f"Rules extraction complete!\n\n"
                        f"Processed: {num_fields} fields\n"
                        f"Total rules: {total_rules}"
                    ))

                except Exception as e:
                    progress_label.config(text=f"✗ Error: {str(e)}")
                    cancel_button.config(state=tk.NORMAL)
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Rules extraction failed:\n{str(e)}"))

            # Start thread
            thread = threading.Thread(target=extraction_thread, daemon=True)
            thread.start()

        extract_button = ttk.Button(button_frame, text="Extract Rules", command=start_extraction)
        extract_button.pack(side=tk.LEFT, padx=(0, 10))

        cancel_button = ttk.Button(button_frame, text="Cancel", command=dialog.destroy)
        cancel_button.pack(side=tk.LEFT)

        # Bind Enter key to start extraction
        dialog.bind('<Return>', lambda e: start_extraction())
        num_fields_spinbox.bind('<Return>', lambda e: start_extraction())

    def update_all_views(self):
        """Update all tab views with parsed data"""
        if not self.parsed_data:
            return

        self.update_overview()
        self.update_fields_view()
        self.update_workflows_view()
        self.update_tables_view()
        self.update_metadata_view()
        self.update_json_view()

    def update_overview(self):
        """Update overview statistics"""
        self.stats_text.delete(1.0, tk.END)

        if not self.parsed_data:
            return

        stats = f"""
DOCUMENT STATISTICS
{'=' * 70}

File: {Path(self.current_document).name}
Parsed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

FIELDS
  Total Fields:          {len(self.parsed_data.all_fields)}
  Initiator Fields:      {len(self.parsed_data.initiator_fields)}
  SPOC Fields:           {len(self.parsed_data.spoc_fields)}
  Approver Fields:       {len(self.parsed_data.approver_fields)}
  Mandatory Fields:      {sum(1 for f in self.parsed_data.all_fields if f.is_mandatory)}

FIELD TYPES
"""
        # Count field types
        from collections import Counter
        type_counts = Counter(f.field_type.name for f in self.parsed_data.all_fields)
        for field_type, count in sorted(type_counts.items()):
            stats += f"  {field_type:20} {count:3}\n"

        stats += f"""
WORKFLOWS
  Total Workflows:       {len(self.parsed_data.workflows)}
  Total Steps:           {sum(len(steps) for steps in self.parsed_data.workflows.values())}

OTHER
  Tables:                {len(self.parsed_data.raw_tables)}
  Reference Tables:      {len(self.parsed_data.reference_tables)}
  Dropdown Mappings:     {len(self.parsed_data.dropdown_mappings)}
"""

        self.stats_text.insert(1.0, stats)

    def update_rules_stats(self):
        """Update rules extraction statistics"""
        if not hasattr(self, 'rules_stats_text'):
            return

        self.rules_stats_text.delete(1.0, tk.END)

        if not self.fields_with_rules:
            self.rules_stats_text.insert(1.0, "No rules extracted yet. Click '🤖 Extract Rules' to process fields.")
            return

        total_rules = sum(len(f.extracted_rules) for f in self.fields_with_rules)
        fields_with_rules = sum(1 for f in self.fields_with_rules if f.extracted_rules)

        # Calculate confidence distribution
        all_rules_list = [rule for f in self.fields_with_rules for rule in f.extracted_rules]
        high_conf = sum(1 for r in all_rules_list if r.confidence >= 0.8)
        med_conf = sum(1 for r in all_rules_list if 0.5 <= r.confidence < 0.8)
        low_conf = sum(1 for r in all_rules_list if r.confidence < 0.5)

        avg_conf = sum(r.confidence for r in all_rules_list) / total_rules if total_rules > 0 else 0

        # Count by type
        expression_rules = sum(1 for r in all_rules_list if r.rule_type == 'EXPRESSION')
        standard_rules = sum(1 for r in all_rules_list if r.rule_type == 'STANDARD')

        stats = f"""
RULES EXTRACTION STATISTICS
{'=' * 70}

SUMMARY
  Fields Processed:      {len(self.fields_with_rules)}
  Fields with Rules:     {fields_with_rules}
  Total Rules Extracted: {total_rules}
  Average Confidence:    {avg_conf:.1%}

CONFIDENCE DISTRIBUTION
  High (≥0.8):           {high_conf} ({high_conf/total_rules*100 if total_rules > 0 else 0:.1f}%)
  Medium (0.5-0.8):      {med_conf} ({med_conf/total_rules*100 if total_rules > 0 else 0:.1f}%)
  Low (<0.5):            {low_conf} ({low_conf/total_rules*100 if total_rules > 0 else 0:.1f}%)

RULE TYPES
  Expression Rules:      {expression_rules}
  Standard Rules:        {standard_rules}

FIELD CATEGORIES
  With Validation:       {sum(1 for f in self.fields_with_rules if f.has_validation)}
  With Visibility:       {sum(1 for f in self.fields_with_rules if f.has_visibility_rules)}
  With Mandatory Rules:  {sum(1 for f in self.fields_with_rules if f.has_mandatory_rules)}
"""

        self.rules_stats_text.insert(1.0, stats)

    def update_fields_view(self):
        """Update fields table based on filter"""
        # Clear existing items
        for item in self.fields_tree.get_children():
            self.fields_tree.delete(item)

        if not self.parsed_data:
            return

        # Get filter
        filter_value = self.field_filter_var.get()
        search_term = self.search_var.get().lower()

        # Get fields based on filter
        if filter_value == "all":
            fields = self.parsed_data.all_fields
        elif filter_value == "initiator":
            fields = self.parsed_data.initiator_fields
        elif filter_value == "spoc":
            fields = self.parsed_data.spoc_fields
        elif filter_value == "approver":
            fields = self.parsed_data.approver_fields
        elif filter_value == "mandatory":
            fields = [f for f in self.parsed_data.all_fields if f.is_mandatory]
        else:
            fields = self.parsed_data.all_fields

        # Apply search filter
        if search_term:
            fields = [f for f in fields if search_term in f.name.lower()]

        # Populate tree
        for field in fields:
            logic_preview = field.logic[:100] + "..." if len(field.logic) > 100 else field.logic
            self.fields_tree.insert("", tk.END, values=(
                field.name,
                field.field_type.name,
                "Yes" if field.is_mandatory else "No",
                logic_preview
            ))

    def update_rules_view(self):
        """Update rules table based on filter"""
        if not hasattr(self, 'rules_tree'):
            return

        # Clear existing items
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)

        if not self.fields_with_rules:
            return

        # Get filters
        conf_filter = self.rules_filter_var.get()
        type_filter = self.rules_type_var.get()

        # Populate tree
        for field_with_rules in self.fields_with_rules:
            for rule in field_with_rules.extracted_rules:
                # Apply confidence filter
                if conf_filter == "high" and rule.confidence < 0.8:
                    continue
                elif conf_filter == "medium" and not (0.5 <= rule.confidence < 0.8):
                    continue
                elif conf_filter == "low" and rule.confidence >= 0.5:
                    continue

                # Apply type filter
                if type_filter == "expression" and rule.rule_type != "EXPRESSION":
                    continue
                elif type_filter == "standard" and rule.rule_type != "STANDARD":
                    continue

                # Format source (show variable name if available)
                source_display = rule.source_variable_name if hasattr(rule, 'source_variable_name') and rule.source_variable_name else (rule.source or "")

                # Format destination (show variable names)
                dest_display = ""
                if hasattr(rule, 'destination_variable_names') and rule.destination_variable_names:
                    dest_display = ", ".join(rule.destination_variable_names[:3])  # Show first 3
                    if len(rule.destination_variable_names) > 3:
                        dest_display += f" +{len(rule.destination_variable_names) - 3}"
                elif rule.destination_fields:
                    dest_display = ", ".join(rule.destination_fields[:2])
                    if len(rule.destination_fields) > 2:
                        dest_display += "..."

                # Format condition (show expression syntax)
                condition_display = ""
                if rule.conditions:
                    condition_display = rule.conditions[:60] + "..." if len(rule.conditions) > 60 else rule.conditions
                elif rule.expression:
                    condition_display = rule.expression[:60] + "..." if len(rule.expression) > 60 else rule.expression

                # Color code by confidence
                tag = ""
                if rule.confidence >= 0.8:
                    tag = "high"
                elif rule.confidence >= 0.5:
                    tag = "medium"
                else:
                    tag = "low"

                self.rules_tree.insert("", tk.END, values=(
                    field_with_rules.field_name,
                    rule.rule_name,
                    rule.action,
                    source_display,
                    dest_display,
                    condition_display,
                    f"{rule.confidence:.0%}"
                ), tags=(tag,))

        # Configure tags
        self.rules_tree.tag_configure("high", foreground="green")
        self.rules_tree.tag_configure("medium", foreground="orange")
        self.rules_tree.tag_configure("low", foreground="red")

    def show_rule_details(self, event):
        """Show detailed information for selected rule"""
        if not hasattr(self, 'rules_details_text'):
            return

        selection = self.rules_tree.selection()
        if not selection:
            return

        values = self.rules_tree.item(selection[0], 'values')
        field_name, rule_name = values[0], values[1]

        # Find the rule
        rule = None
        for field_with_rules in self.fields_with_rules:
            if field_with_rules.field_name == field_name:
                for r in field_with_rules.extracted_rules:
                    if r.rule_name == rule_name:
                        rule = r
                        break
                break

        if not rule:
            return

        # Show details
        self.rules_details_text.delete(1.0, tk.END)

        details = f"""
Rule: {rule.rule_name}
Action: {rule.action}
Type: {rule.rule_type}
Processing: {rule.processing_type}
Confidence: {rule.confidence:.0%}

"""
        # Show source with variable name
        if hasattr(rule, 'source_variable_name') and rule.source_variable_name:
            details += f"Source Variable: {rule.source_variable_name}\n"
        elif rule.source:
            details += f"Source: {rule.source}\n"

        # Show destination variable names
        if hasattr(rule, 'destination_variable_names') and rule.destination_variable_names:
            details += f"Destination Variables: {', '.join(rule.destination_variable_names)}\n"
        elif rule.destination_fields:
            details += f"Destination Fields: {', '.join(rule.destination_fields)}\n"

        # Show conditions and expression
        if rule.conditions:
            details += f"\nCondition (Expression Syntax):\n{rule.conditions}\n"
        if rule.expression:
            details += f"\nFull Expression:\n{rule.expression}\n"

        details += f"\nOriginal Logic:\n{rule.original_logic}\n"

        self.rules_details_text.insert(1.0, details)

    def update_workflows_view(self):
        """Update workflows display"""
        self.workflows_text.delete(1.0, tk.END)

        if not self.parsed_data or not self.parsed_data.workflows:
            self.workflows_text.insert(1.0, "No workflows found")
            return

        output = "WORKFLOW STEPS\n" + "=" * 70 + "\n\n"

        for actor, steps in self.parsed_data.workflows.items():
            output += f"\n{actor.upper()}\n{'-' * 70}\n\n"

            for step in steps:
                output += f"{step.step_number}. {step.description}\n"
                if step.action_type:
                    output += f"   Action: {step.action_type}\n"
                output += "\n"

        self.workflows_text.insert(1.0, output)

    def update_tables_view(self):
        """Update tables display"""
        self.tables_text.delete(1.0, tk.END)

        if not self.parsed_data or not self.parsed_data.raw_tables:
            self.tables_text.insert(1.0, "No tables found")
            return

        output = f"TABLES ({len(self.parsed_data.raw_tables)} found)\n" + "=" * 70 + "\n\n"

        for i, table in enumerate(self.parsed_data.raw_tables, 1):
            output += f"Table {i}: {table.table_type}\n"
            output += f"Headers: {', '.join(table.headers)}\n"
            output += f"Rows: {len(table.rows)}\n"
            if table.context:
                output += f"Context: {table.context}\n"
            output += "\n"

        self.tables_text.insert(1.0, output)

    def update_metadata_view(self):
        """Update metadata display"""
        self.metadata_text.delete(1.0, tk.END)

        if not self.parsed_data:
            return

        meta = self.parsed_data.metadata
        output = "DOCUMENT METADATA\n" + "=" * 70 + "\n\n"

        output += f"Title: {meta.title}\n"
        output += f"Author: {meta.author}\n"
        output += f"Subject: {meta.subject}\n"
        output += f"Process Name: {meta.process_name}\n"
        output += f"Created: {meta.created}\n"
        output += f"Modified: {meta.modified}\n"
        output += f"Last Modified By: {meta.last_modified_by}\n"

        self.metadata_text.insert(1.0, output)

    def update_json_view(self):
        """Update JSON display"""
        self.json_text.delete(1.0, tk.END)

        if not self.parsed_data:
            return

        # Convert to dict
        parsed_dict = {
            "file_path": self.parsed_data.file_path,
            "metadata": {
                "title": self.parsed_data.metadata.title,
                "author": self.parsed_data.metadata.author,
                "subject": self.parsed_data.metadata.subject,
                "process_name": self.parsed_data.metadata.process_name,
            },
            "total_fields": len(self.parsed_data.all_fields),
            "fields": [
                {
                    "name": f.name,
                    "type": f.field_type.name,
                    "mandatory": f.is_mandatory,
                    "logic": f.logic,
                    "section": f.section
                }
                for f in self.parsed_data.all_fields[:50]  # Limit for performance
            ]
        }

        if len(self.parsed_data.all_fields) > 50:
            parsed_dict["note"] = f"Showing first 50 of {len(self.parsed_data.all_fields)} fields"

        json_str = json.dumps(parsed_dict, indent=2, ensure_ascii=False)
        self.json_text.insert(1.0, json_str)

    def sort_column(self, col):
        """Sort treeview column"""
        # This is a simplified sort - could be enhanced
        pass

    def export_json(self):
        """Export parsed data to JSON file"""
        if not self.parsed_data:
            messagebox.showwarning("No Data", "Please parse a document first")
            return

        filename = filedialog.asksaveasfilename(
            title="Export JSON",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )

        if filename:
            try:
                # Export full data
                export_data = {
                    "file_path": self.parsed_data.file_path,
                    "metadata": self.parsed_data.metadata.__dict__,
                    "fields": [f.__dict__ for f in self.parsed_data.all_fields],
                    "workflows": {k: [s.__dict__ for s in v] for k, v in self.parsed_data.workflows.items()}
                }

                # Add rules if available
                if self.fields_with_rules:
                    export_data["extracted_rules"] = {
                        "total_fields_processed": len(self.fields_with_rules),
                        "total_rules": sum(len(f.extracted_rules) for f in self.fields_with_rules),
                        "fields": [
                            {
                                "field_name": f.field_name,
                                "field_type": f.field_type,
                                "rules": [r.__dict__ for r in f.extracted_rules]
                            }
                            for f in self.fields_with_rules
                        ]
                    }

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

                self.status_var.set(f"Exported to {Path(filename).name}")
                messagebox.showinfo("Success", f"Data exported to:\n{filename}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export:\n{str(e)}")


def main():
    root = tk.Tk()
    app = DocumentParserGUIEnhanced(root)

    # Check if rules available
    if not RULES_AVAILABLE:
        messagebox.showwarning(
            "Rules Extraction Unavailable",
            "Rules extraction requires additional dependencies.\n\n"
            "To enable:\n"
            "1. source venv/bin/activate\n"
            "2. pip install openai python-dotenv\n"
            "3. Configure .env with OPENAI_API_KEY"
        )

    root.mainloop()


if __name__ == "__main__":
    main()
