#!/usr/bin/env python3
"""
Rule Extraction Pipeline GUI
Upload a BUD and run all 10 dispatcher stages.
"""

import tkinter as tk
from tkinter import ttk, filedialog
import threading
import subprocess
import time
import re
from pathlib import Path

STAGE_LABELS = [
    "Creating fields and placing rules...",
    "Applying source and destination to rules...",
    "Applying the External Data Value rule...",
    "Validating External Data Values on dropdowns...",
    "Applying conditional visibility rules...",
    "Applying derivation logic to fields...",
    "Applying clearing rules for child fields...",
    "Applying cross-panel rules...",
    "Applying session-based rules...",
    "Converting to API format...",
]

PROJECT_ROOT = Path(__file__).resolve().parent
DISPATCHERS = PROJECT_ROOT / "dispatchers" / "agents"
DEFAULT_OUTPUT_DIR = "output"


def _suggest_name(filename):
    """Strip only file extension and trailing version numbers/parens."""
    name = Path(filename).stem
    name = re.sub(r'\s+\d+$', '', name).strip()
    name = re.sub(r'\s*\(\d+\)\s*$', '', name).strip()
    return name if name else Path(filename).stem


def _build_commands(bud_path, output_dir, bud_name):
    """Build the subprocess command list for each of the 10 pipeline stages."""
    d = str(DISPATCHERS)
    kw = "rule_extractor/static/keyword_tree.json"
    rs = "rules/Rule-Schemas.json"

    s = [
        f"{output_dir}/rule_placement/all_panels_rules.json",
        f"{output_dir}/source_destination/all_panels_source_dest.json",
        f"{output_dir}/edv_rules/all_panels_edv.json",
        f"{output_dir}/validate_edv/all_panels_validate_edv.json",
        f"{output_dir}/conditional_logic/all_panels_conditional_logic.json",
        f"{output_dir}/derivation_logic/all_panels_derivation.json",
        f"{output_dir}/clear_child_fields/all_panels_clear_child.json",
        f"{output_dir}/inter_panel/all_panels_inter_panel.json",
        f"{output_dir}/session_based/all_panels_session_based.json",
        f"{output_dir}/final_output.json",
    ]

    return [
        ["python3", f"{d}/rule_placement_dispatcher.py",
         "--bud", bud_path, "--keyword-tree", kw, "--rule-schemas", rs, "--output", s[0]],
        ["python3", f"{d}/source_destination_dispatcher.py",
         "--input", s[0], "--rule-schemas", rs, "--output", s[1]],
        ["python3", f"{d}/edv_rule_dispatcher.py",
         "--bud", bud_path, "--source-dest-output", s[1], "--output", s[2]],
        ["python3", f"{d}/validate_edv_dispatcher.py",
         "--bud", bud_path, "--edv-output", s[2], "--output", s[3]],
        ["python3", f"{d}/conditional_logic_dispatcher.py",
         "--validate-edv-output", s[3], "--output", s[4]],
        ["python3", f"{d}/derivation_logic_dispatcher.py",
         "--conditional-logic-output", s[4], "--output", s[5]],
        ["python3", f"{d}/clear_child_fields_dispatcher.py",
         "--derivation-output", s[5], "--output", s[6]],
        ["python3", f"{d}/inter_panel_dispatcher.py",
         "--clear-child-output", s[6], "--bud", bud_path, "--output", s[7]],
        ["python3", f"{d}/session_based_dispatcher.py",
         "--clear-child-output", s[7], "--bud", bud_path, "--output", s[8]],
        ["python3", f"{d}/convert_to_api_format.py",
         "--input", s[8], "--output", s[9], "--bud-name", bud_name, "--pretty"],
    ]


class PipelineGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Rule Extraction Pipeline")
        self.root.geometry("700x350")
        self.root.configure(bg="#1e1e2e")
        self.root.minsize(550, 300)

        self.bud_path = tk.StringVar(value="")
        self.bud_name = tk.StringVar(value="")
        self.running = False
        self.stop_flag = False
        self.current_process = None

        self._build_styles()
        self._build_ui()

    def _build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        bg = "#1e1e2e"
        fg = "#cdd6f4"
        accent = "#89b4fa"
        surface = "#313244"
        green = "#a6e3a1"
        yellow = "#f9e2af"
        red = "#f38ba8"

        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 11))
        style.configure("Header.TLabel", background=bg, foreground=accent, font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel", background=bg, foreground="#a6adc8", font=("Segoe UI", 9))
        style.configure("Stage.TLabel", background=surface, foreground=fg, font=("Segoe UI", 12, "bold"), padding=10)
        style.configure("Active.TLabel", background=surface, foreground=green, font=("Segoe UI", 12, "bold"), padding=10)
        style.configure("Error.TLabel", background=surface, foreground=red, font=("Segoe UI", 12, "bold"), padding=10)
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=10)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=accent, font=("Segoe UI", 11, "bold"))

        self.colors = {"bg": bg, "fg": fg, "accent": accent, "surface": surface,
                       "green": green, "yellow": yellow, "red": red}

    def _build_ui(self):
        px = 20

        # Header
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=px, pady=(15, 5))
        ttk.Label(header, text="Rule Extraction Pipeline", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(header, text="Upload a BUD document and run the full 10-stage pipeline",
                  style="Sub.TLabel").pack(anchor=tk.W)

        # BUD upload
        bud_frame = ttk.LabelFrame(self.root, text="BUD Document", padding=12)
        bud_frame.pack(fill=tk.X, padx=px, pady=5)

        row1 = ttk.Frame(bud_frame)
        row1.pack(fill=tk.X)
        row1.columnconfigure(1, weight=1)
        ttk.Button(row1, text="Browse", command=self._browse_bud).grid(row=0, column=0, padx=(0, 10))
        self.bud_label = ttk.Label(row1, text="No file selected", foreground="#a6adc8")
        self.bud_label.grid(row=0, column=1, sticky=tk.W)

        row2 = ttk.Frame(bud_frame)
        row2.pack(fill=tk.X, pady=(8, 0))
        row2.columnconfigure(1, weight=1)
        ttk.Label(row2, text="Name:").grid(row=0, column=0, padx=(0, 10))
        self.name_entry = tk.Entry(row2, textvariable=self.bud_name,
                                    bg=self.colors["surface"], fg=self.colors["fg"],
                                    insertbackground=self.colors["fg"],
                                    font=("Segoe UI", 10), relief=tk.FLAT)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, ipady=4)

        # Controls
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill=tk.X, padx=px, pady=(8, 5))
        self.run_btn = ttk.Button(ctrl, text="Run Pipeline", style="Accent.TButton",
                                   command=self._start_pipeline)
        self.run_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(ctrl, text="Stop", command=self._stop_pipeline, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(10, 0))
        self.status_label = ttk.Label(ctrl, text="Ready", foreground=self.colors["green"])
        self.status_label.pack(side=tk.RIGHT)

        # Current stage
        self.stage_label = ttk.Label(self.root, text="", style="Stage.TLabel", anchor=tk.W)
        self.stage_label.pack(fill=tk.X, padx=px, pady=(8, 15))

    def _browse_bud(self):
        path = filedialog.askopenfilename(
            title="Select BUD Document",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")]
        )
        if path:
            self.bud_path.set(path)
            self.bud_label.configure(text=Path(path).name, foreground=self.colors["green"])
            self.bud_name.set(_suggest_name(Path(path).name))

    def _start_pipeline(self):
        if not self.bud_path.get():
            return

        self.running = True
        self.stop_flag = False
        self.run_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)

        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _stop_pipeline(self):
        self.stop_flag = True
        if self.current_process:
            self.current_process.terminate()

    def _run_pipeline(self):
        total = len(STAGE_LABELS)
        bud_path = self.bud_path.get()
        bud_name = self.bud_name.get() or "Untitled"
        output_dir = DEFAULT_OUTPUT_DIR

        commands = _build_commands(bud_path, output_dir, bud_name)

        # Log directory for stage output
        log_dir = PROJECT_ROOT / output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        self.root.after(0, lambda: self.status_label.configure(
            text="Running...", foreground=self.colors["yellow"]))

        failed = False

        for i, msg in enumerate(STAGE_LABELS):
            if self.stop_flag:
                break

            num = i + 1

            self.root.after(0, lambda n=num, m=msg:
                            self.stage_label.configure(
                                text=f"  Stage {n} / {total}:  {m}",
                                style="Active.TLabel"))

            log_path = log_dir / f"stage_{num}.log"

            try:
                with open(log_path, 'w') as log_file:
                    proc = subprocess.Popen(
                        commands[i],
                        cwd=str(PROJECT_ROOT),
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                    )
                    self.current_process = proc

                    while proc.poll() is None:
                        if self.stop_flag:
                            proc.terminate()
                            proc.wait()
                            break
                        time.sleep(0.5)

                    self.current_process = None

                if self.stop_flag:
                    break

                if proc.returncode != 0:
                    error_text = log_path.read_text().strip()
                    last_line = error_text.split('\n')[-1][:80] if error_text else "Unknown error"
                    self.root.after(0, lambda n=num, e=last_line:
                        self.stage_label.configure(
                            text=f"  Stage {n} failed: {e}",
                            style="Error.TLabel"))
                    self.root.after(0, lambda: self.status_label.configure(
                        text="Failed", foreground=self.colors["red"]))
                    failed = True
                    break

            except Exception as e:
                self.root.after(0, lambda n=num, e=str(e)[:80]:
                    self.stage_label.configure(
                        text=f"  Stage {n} error: {e}",
                        style="Error.TLabel"))
                self.root.after(0, lambda: self.status_label.configure(
                    text="Failed", foreground=self.colors["red"]))
                failed = True
                break

        if not failed:
            if self.stop_flag:
                self.root.after(0, lambda: self.status_label.configure(
                    text="Stopped", foreground=self.colors["yellow"]))
                self.root.after(0, lambda: self.stage_label.configure(
                    text="  Pipeline stopped", style="Stage.TLabel"))
            else:
                self.root.after(0, lambda: self.status_label.configure(
                    text="Complete", foreground=self.colors["green"]))
                self.root.after(0, lambda: self.stage_label.configure(
                    text=f"  All {total} stages complete", style="Active.TLabel"))

        self.running = False
        self.root.after(0, lambda: self.run_btn.configure(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_btn.configure(state=tk.DISABLED))


def main():
    root = tk.Tk()
    PipelineGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
