#!/usr/bin/env python3
"""
GUI for creating External Data Value (EDV) metadata on the Manch platform.

Reads an Excel (.xlsx) or CSV (.csv) file, auto-detects candidate key columns,
and creates the EDV via the Manch API.

Usage:
    python3 create_edv_gui.py
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from create_edv import (
    BASE_URL,
    DEFAULT_COMPANY_ID,
    create_edv,
    find_candidate_key,
    read_file,
    sanitize_attribute_name,
)

# ──────────────────────────────────────────────
# Color / Style constants
# ──────────────────────────────────────────────
BG = "#f5f6fa"
CARD_BG = "#ffffff"
ACCENT = "#c0392b"
ACCENT_HOVER = "#e74c3c"
TEXT_PRIMARY = "#2c3e50"
TEXT_SECONDARY = "#7f8c8d"
SUCCESS_BG = "#27ae60"
KEY_TAG_BG = "#3498db"
KEY_TAG_FG = "#ffffff"
BORDER_COLOR = "#dcdde1"


class EdvCreatorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Manch - Create External Data Value")
        self.root.geometry("960x740")
        self.root.configure(bg=BG)
        self.root.minsize(800, 600)

        # State
        self.headers = []
        self.data = []
        self.col_stats = []
        self.uniqueness_indices: list[int] = []  # 1-based
        self.attr_check_vars: list[tk.BooleanVar] = []
        self.attr_name_entries: list[tk.Entry] = []
        self.attr_mandatory_vars: list[tk.BooleanVar] = []

        self._build_ui()

    # ──────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self.root, bg=ACCENT, height=56)
        top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(
            top, text="Create External Data Value", font=("Segoe UI", 16, "bold"),
            fg="white", bg=ACCENT,
        ).pack(side=tk.LEFT, padx=20)
        tk.Label(
            top, text="manch", font=("Segoe UI", 12), fg="#f1c4c0", bg=ACCENT,
        ).pack(side=tk.RIGHT, padx=20)

        # Scrollable body
        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=canvas.yview)
        self.body = tk.Frame(canvas, bg=BG)
        self.body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        pad = {"padx": 24, "pady": (10, 0)}

        # ── Card 1: Connection ──
        card1 = self._card(self.body, "Connection Settings")
        card1.pack(fill=tk.X, **pad)

        row = tk.Frame(card1, bg=CARD_BG)
        row.pack(fill=tk.X, pady=4)
        self._label(row, "Auth Token *").pack(side=tk.LEFT)
        self.auth_entry = self._entry(row, width=42, show="*")
        self.auth_entry.pack(side=tk.LEFT, padx=(8, 20))

        self._label(row, "Base URL").pack(side=tk.LEFT)
        self.url_entry = self._entry(row, width=30)
        self.url_entry.insert(0, BASE_URL)
        self.url_entry.pack(side=tk.LEFT, padx=(8, 20))

        self._label(row, "Company ID").pack(side=tk.LEFT)
        self.company_entry = self._entry(row, width=8)
        self.company_entry.insert(0, str(DEFAULT_COMPANY_ID))
        self.company_entry.pack(side=tk.LEFT, padx=(8, 0))

        # ── Card 2: File Selection ──
        card2 = self._card(self.body, "Input File")
        card2.pack(fill=tk.X, **pad)

        file_row = tk.Frame(card2, bg=CARD_BG)
        file_row.pack(fill=tk.X, pady=4)

        self.file_var = tk.StringVar(value="No file selected")
        self._btn(file_row, "Browse...", self._browse_file).pack(side=tk.LEFT)
        self.file_label = tk.Label(
            file_row, textvariable=self.file_var, font=("Segoe UI", 10),
            fg=TEXT_SECONDARY, bg=CARD_BG, anchor="w",
        )
        self.file_label.pack(side=tk.LEFT, padx=12, fill=tk.X, expand=True)

        sheet_frame = tk.Frame(card2, bg=CARD_BG)
        sheet_frame.pack(fill=tk.X, pady=4)
        self._label(sheet_frame, "Sheet (Excel only)").pack(side=tk.LEFT)
        self.sheet_entry = self._entry(sheet_frame, width=30)
        self.sheet_entry.pack(side=tk.LEFT, padx=(8, 20))

        self.load_btn = self._btn(sheet_frame, "Load & Analyze", self._load_file)
        self.load_btn.pack(side=tk.LEFT)

        # ── Card 3: EDV Details ──
        card3 = self._card(self.body, "EDV Details")
        card3.pack(fill=tk.X, **pad)

        r1 = tk.Frame(card3, bg=CARD_BG)
        r1.pack(fill=tk.X, pady=4)
        self._label(r1, "EDV Name *").pack(side=tk.LEFT)
        self.name_entry = self._entry(r1, width=40)
        self.name_entry.pack(side=tk.LEFT, padx=(8, 20))

        self._label(r1, "Description").pack(side=tk.LEFT)
        self.desc_entry = self._entry(r1, width=40)
        self.desc_entry.pack(side=tk.LEFT, padx=(8, 0))

        # ── Card 4: Attributes & Uniqueness ──
        self.attr_card = self._card(self.body, "Attributes & Uniqueness Criteria")
        self.attr_card.pack(fill=tk.X, **pad)

        self.attr_hint = tk.Label(
            self.attr_card, text="Load a file to see attributes here.",
            font=("Segoe UI", 10, "italic"), fg=TEXT_SECONDARY, bg=CARD_BG,
        )
        self.attr_hint.pack(anchor="w", pady=4)

        self.attr_table_frame = tk.Frame(self.attr_card, bg=CARD_BG)
        self.attr_table_frame.pack(fill=tk.X)

        # ── Card 5: Data Preview ──
        card5 = self._card(self.body, "Data Preview (first 5 rows)")
        card5.pack(fill=tk.X, **pad)
        self.preview_frame = tk.Frame(card5, bg=CARD_BG)
        self.preview_frame.pack(fill=tk.X)
        self.preview_hint = tk.Label(
            card5, text="Load a file to see data preview.",
            font=("Segoe UI", 10, "italic"), fg=TEXT_SECONDARY, bg=CARD_BG,
        )
        self.preview_hint.pack(anchor="w", pady=4)

        # ── Bottom bar ──
        bottom = tk.Frame(self.body, bg=BG)
        bottom.pack(fill=tk.X, padx=24, pady=20)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            bottom, textvariable=self.status_var, font=("Segoe UI", 10),
            fg=TEXT_SECONDARY, bg=BG, anchor="w",
        ).pack(side=tk.LEFT)

        self.create_btn = self._btn(bottom, "Create EDV", self._create_edv, accent=True)
        self.create_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.create_btn.config(state=tk.DISABLED)

        self.preview_btn = self._btn(bottom, "Preview Payload", self._preview_payload)
        self.preview_btn.pack(side=tk.RIGHT)
        self.preview_btn.config(state=tk.DISABLED)

    # ──────────────────────────────────────────
    # Widget helpers
    # ──────────────────────────────────────────

    def _card(self, parent, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=BORDER_COLOR, bd=0)
        inner = tk.Frame(outer, bg=CARD_BG, padx=16, pady=12)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        tk.Label(
            inner, text=title, font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY, bg=CARD_BG, anchor="w",
        ).pack(fill=tk.X, pady=(0, 6))
        ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))
        return inner

    def _label(self, parent, text: str) -> tk.Label:
        return tk.Label(
            parent, text=text, font=("Segoe UI", 10), fg=TEXT_PRIMARY, bg=CARD_BG,
        )

    def _entry(self, parent, width=20, show=None) -> tk.Entry:
        e = tk.Entry(
            parent, width=width, font=("Segoe UI", 10), bd=1,
            relief=tk.SOLID, highlightthickness=1,
            highlightcolor=ACCENT, show=show or "",
        )
        return e

    def _btn(self, parent, text, command, accent=False) -> tk.Button:
        bg = ACCENT if accent else "#ecf0f1"
        fg = "white" if accent else TEXT_PRIMARY
        hover_bg = ACCENT_HOVER if accent else "#bdc3c7"
        btn = tk.Button(
            parent, text=text, command=command, font=("Segoe UI", 10, "bold"),
            bg=bg, fg=fg, activebackground=hover_bg, activeforeground=fg,
            relief=tk.FLAT, padx=16, pady=6, cursor="hand2",
        )
        btn.bind("<Enter>", lambda e, b=btn, hb=hover_bg: b.config(bg=hb))
        btn.bind("<Leave>", lambda e, b=btn, ob=bg: b.config(bg=ob))
        return btn

    # ──────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Excel or CSV file",
            filetypes=[
                ("All supported", "*.xlsx *.xls *.csv"),
                ("Excel files", "*.xlsx *.xls"),
                ("CSV files", "*.csv"),
            ],
        )
        if path:
            self.file_var.set(path)
            self.file_label.config(fg=TEXT_PRIMARY)

    def _load_file(self):
        path = self.file_var.get()
        if not path or path == "No file selected":
            messagebox.showwarning("No file", "Please select an Excel or CSV file first.")
            return

        sheet = self.sheet_entry.get().strip() or None

        self.status_var.set("Loading file...")
        self.root.update_idletasks()

        try:
            self.headers, self.data = read_file(path, sheet)
        except Exception as e:
            messagebox.showerror("Error loading file", str(e))
            self.status_var.set("Error loading file")
            return

        # Run candidate key detection
        self.status_var.set("Analyzing candidate key...")
        self.root.update_idletasks()
        self.uniqueness_indices = find_candidate_key(self.headers, self.data)

        # Auto-fill EDV name and description
        base = os.path.splitext(os.path.basename(path))[0]
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, sanitize_attribute_name(base))
        self.desc_entry.delete(0, tk.END)
        self.desc_entry.insert(0, f"EDV created from {os.path.basename(path)}")

        self._populate_attributes()
        self._populate_preview()

        self.create_btn.config(state=tk.NORMAL)
        self.preview_btn.config(state=tk.NORMAL)
        self.status_var.set(
            f"Loaded {len(self.headers)} columns, {len(self.data)} rows. "
            f"Candidate key: {[self.headers[i-1] for i in self.uniqueness_indices]}"
        )

    def _populate_attributes(self):
        # Clear previous
        for w in self.attr_table_frame.winfo_children():
            w.destroy()
        self.attr_hint.pack_forget()

        self.attr_check_vars = []
        self.attr_name_entries = []
        self.attr_mandatory_vars = []

        # Header row
        hdr = tk.Frame(self.attr_table_frame, bg="#ecf0f1")
        hdr.pack(fill=tk.X, pady=(0, 2))
        col_defs = [
            ("#", 3), ("Attribute Name (editable)", 24), ("Original Header", 22),
            ("Unique", 8), ("Non-empty", 8), ("Mandatory", 7), ("Uniqueness", 7),
        ]
        for col, (text, w) in enumerate(col_defs):
            tk.Label(
                hdr, text=text, font=("Segoe UI", 9, "bold"), fg=TEXT_PRIMARY,
                bg="#ecf0f1", width=w, anchor="w",
            ).grid(row=0, column=col, padx=3, pady=4)

        total_rows = len(self.data)
        for i, header in enumerate(self.headers):
            is_key = (i + 1) in self.uniqueness_indices
            row_bg = "#eaf2fd" if is_key else CARD_BG

            row = tk.Frame(self.attr_table_frame, bg=row_bg)
            row.pack(fill=tk.X)

            # Column index
            tk.Label(
                row, text=str(i + 1), font=("Segoe UI", 9), fg=TEXT_SECONDARY,
                bg=row_bg, width=3, anchor="w",
            ).grid(row=0, column=0, padx=3, pady=2)

            # Editable attribute name
            name_entry = tk.Entry(
                row, font=("Segoe UI", 9, "bold"), width=24, bd=1,
                relief=tk.SOLID, highlightthickness=1, highlightcolor=ACCENT,
            )
            name_entry.insert(0, sanitize_attribute_name(header))
            name_entry.grid(row=0, column=1, padx=3, pady=2)
            self.attr_name_entries.append(name_entry)

            # Original header (read-only label)
            tk.Label(
                row, text=header, font=("Segoe UI", 9), fg=TEXT_SECONDARY,
                bg=row_bg, width=22, anchor="w",
            ).grid(row=0, column=2, padx=3, pady=2)

            # Uniqueness stats
            col_vals = [r[i] for r in self.data if r[i].strip()]
            unique_count = len(set(col_vals))
            non_empty = len(col_vals)
            ratio_text = f"{unique_count}/{non_empty}" if non_empty else "0/0"

            tk.Label(
                row, text=ratio_text, font=("Segoe UI", 9), fg=TEXT_PRIMARY,
                bg=row_bg, width=8, anchor="w",
            ).grid(row=0, column=3, padx=3, pady=2)

            pct = f"{non_empty}/{total_rows}" if total_rows else "0"
            tk.Label(
                row, text=pct, font=("Segoe UI", 9), fg=TEXT_PRIMARY,
                bg=row_bg, width=8, anchor="w",
            ).grid(row=0, column=4, padx=3, pady=2)

            # Mandatory checkbox
            mand_var = tk.BooleanVar(value=is_key)
            mand_cb = tk.Checkbutton(
                row, variable=mand_var, bg=row_bg, activebackground=row_bg,
            )
            mand_cb.grid(row=0, column=5, padx=3, pady=2)
            self.attr_mandatory_vars.append(mand_var)

            # Uniqueness checkbox
            uniq_var = tk.BooleanVar(value=is_key)
            uniq_cb = tk.Checkbutton(
                row, variable=uniq_var, bg=row_bg, activebackground=row_bg,
                command=self._on_uniqueness_change,
            )
            uniq_cb.grid(row=0, column=6, padx=3, pady=2)
            self.attr_check_vars.append(uniq_var)

    def _populate_preview(self):
        for w in self.preview_frame.winfo_children():
            w.destroy()
        self.preview_hint.pack_forget()

        if not self.headers:
            return

        # Create a treeview for data preview
        tree = ttk.Treeview(
            self.preview_frame, columns=list(range(len(self.headers))),
            show="headings", height=min(5, len(self.data)),
        )
        for i, h in enumerate(self.headers):
            tree.heading(i, text=h)
            tree.column(i, width=max(80, min(150, len(h) * 10)), anchor="w")

        for row in self.data[:5]:
            tree.insert("", tk.END, values=row)

        hsb = ttk.Scrollbar(self.preview_frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(xscrollcommand=hsb.set)

        tree.pack(fill=tk.X, pady=(0, 4))
        hsb.pack(fill=tk.X)

    def _on_uniqueness_change(self):
        self.uniqueness_indices = [
            i + 1 for i, var in enumerate(self.attr_check_vars) if var.get()
        ]
        self.status_var.set(
            f"Uniqueness: {[self.headers[i-1] for i in self.uniqueness_indices]}"
        )

    def _build_payload_data(self):
        """Build attributes list and uniqueness indices from current UI state."""
        if not self.headers:
            return None, None, None, None

        # Refresh uniqueness from checkboxes
        self.uniqueness_indices = [
            i + 1 for i, var in enumerate(self.attr_check_vars) if var.get()
        ]

        # Read attribute names from editable entries
        attributes = []
        for i in range(len(self.headers)):
            attr_name = self.attr_name_entries[i].get().strip() or f"ATTRIBUTE_{i+1}"
            is_mandatory = self.attr_mandatory_vars[i].get()
            attributes.append({"name": attr_name, "mandatory": is_mandatory})

        edv_name = self.name_entry.get().strip()
        description = self.desc_entry.get().strip() or f"EDV: {edv_name}"

        if not edv_name:
            messagebox.showwarning("Missing field", "Please enter an EDV Name.")
            return None, None, None, None

        if not self.uniqueness_indices:
            messagebox.showwarning(
                "No uniqueness", "Please select at least one column as uniqueness criteria."
            )
            return None, None, None, None

        return edv_name, description, attributes, self.uniqueness_indices

    def _preview_payload(self):
        import json as _json

        edv_name, description, attributes, uniq = self._build_payload_data()
        if edv_name is None:
            return

        # Build the payload the same way the API function does
        attrs = {}
        for i, attr in enumerate(attributes, start=1):
            key = f"attribute{i}"
            mandatory_str = "true" if attr.get("mandatory") else "false"
            validation_msg = (
                f"Please provide value for {attr['name']}" if attr.get("mandatory") else None
            )
            attrs[key] = {
                "name": attr["name"],
                "displayOrder": i,
                "externalDataRules": [{
                    "ruleType": "VALIDATION",
                    "type": "MANDATORY",
                    "value": mandatory_str,
                    "validationMessage": validation_msg,
                }],
                "edited": False,
            }

        payload = {
            "externalDataType": edv_name,
            "description": description,
            "genericData": "true",
            "criterias": [f"attribute{idx}value" for idx in uniq],
            "attributes": attrs,
        }

        # Show in a popup
        win = tk.Toplevel(self.root)
        win.title("API Payload Preview")
        win.geometry("700x500")
        win.configure(bg=BG)

        tk.Label(
            win, text="POST Payload", font=("Segoe UI", 13, "bold"),
            fg=TEXT_PRIMARY, bg=BG,
        ).pack(anchor="w", padx=12, pady=(12, 4))

        url = f"{self.url_entry.get().strip()}/app/v2/company/{self.company_entry.get().strip()}/external-data-metadata"
        tk.Label(
            win, text=f"POST {url}", font=("Consolas", 9),
            fg=TEXT_SECONDARY, bg=BG,
        ).pack(anchor="w", padx=12)

        text = tk.Text(
            win, font=("Consolas", 10), bg="#2d2d2d", fg="#e0e0e0",
            insertbackground="white", bd=0, padx=12, pady=8,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        text.insert("1.0", _json.dumps(payload, indent=2))
        text.config(state=tk.DISABLED)

    def _create_edv(self):
        auth_token = self.auth_entry.get().strip()
        if not auth_token:
            messagebox.showwarning("Missing field", "Please enter an Auth Token.")
            return

        edv_name, description, attributes, uniq = self._build_payload_data()
        if edv_name is None:
            return

        base_url = self.url_entry.get().strip()
        try:
            company_id = int(self.company_entry.get().strip())
        except ValueError:
            messagebox.showwarning("Invalid", "Company ID must be a number.")
            return

        self.create_btn.config(state=tk.DISABLED)
        self.status_var.set("Creating EDV...")
        self.root.update_idletasks()

        def _do_create():
            try:
                result = create_edv(
                    base_url=base_url,
                    auth_token=auth_token,
                    company_id=company_id,
                    edv_name=edv_name,
                    edv_description=description,
                    attributes=attributes,
                    uniqueness_indices=uniq,
                )
                self.root.after(0, lambda: self._on_create_done(result))
            except Exception as e:
                self.root.after(0, lambda: self._on_create_error(str(e)))

        threading.Thread(target=_do_create, daemon=True).start()

    def _on_create_done(self, result):
        self.create_btn.config(state=tk.NORMAL)
        if result.get("status") == "SUCCESS":
            edv_id = result.get("id", "?")
            self.status_var.set(f"SUCCESS! EDV created with ID: {edv_id}")
            messagebox.showinfo(
                "EDV Created",
                f"External Data Value created successfully!\n\n"
                f"Name: {self.name_entry.get().strip()}\n"
                f"ID: {edv_id}\n"
                f"Message: {result.get('message', '')}",
            )
        else:
            self.status_var.set(f"Response: {result}")
            messagebox.showwarning("Unexpected response", str(result))

    def _on_create_error(self, error_msg):
        self.create_btn.config(state=tk.NORMAL)
        self.status_var.set(f"Error: {error_msg}")
        messagebox.showerror("Error creating EDV", error_msg)


def main():
    root = tk.Tk()
    EdvCreatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
