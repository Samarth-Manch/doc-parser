"""
bud_validator.py
Parses the document and runs all registered validators,
then writes results to Excel and HTML reports, and optionally
runs an AI-based evaluation of the report against the BUD.
"""

import os
import sys

from document_reader import parse_document
from validators import ValidatorRegistry, ValidationContext
from excel_writer import write_validation_report
from html_writer import write_html_report

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_output")
EXCEL_DIR = os.path.join(OUTPUT_DIR, "excel_output")
HTML_DIR = os.path.join(OUTPUT_DIR, "html_output")
DEFAULT_FILE = "Vendor Creation Sample BUD 3.docx"
RUN_EVAL = True  # Set to True to enable AI-based evaluation after validation


def validate_bud(file_path: str, run_eval: bool = True) -> None:
    parsed = parse_document(file_path)
    print("Document Parsed Successfully.")

    ctx = ValidationContext(parsed=parsed)

    # Run all registered validators
    results = ValidatorRegistry.run_all(ctx)

    # Ensure output directories exist
    os.makedirs(EXCEL_DIR, exist_ok=True)
    os.makedirs(HTML_DIR, exist_ok=True)

    base = os.path.splitext(os.path.basename(file_path))[0]

    # Write Excel report
    excel_path = os.path.join(EXCEL_DIR, f"{base}_validation.xlsx")
    write_validation_report(excel_path, results)
    print(f"Excel report written to: {excel_path}")

    # Write HTML report
    html_path = os.path.join(HTML_DIR, f"{base}_validation.html")
    write_html_report(html_path, results, doc_name=base)
    print(f"HTML report written to: {html_path}")

    # Run AI-based evaluation of the report against the BUD
    if run_eval:
        _run_evaluation(file_path, html_path)


def _run_evaluation(bud_path: str, html_report_path: str) -> None:
    """Run the AI eval on the generated report."""
    try:
        from eval.evaluator import run_eval
        print("\n--- Running AI Evaluation ---")
        eval_path = run_eval(bud_path, html_report_path, verbose=True)
        if eval_path:
            print(f"Eval report: {eval_path}")
        else:
            print("Eval: no output generated (claude CLI may not be available)")
    except Exception as e:
        print(f"Eval skipped: {e}")


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    # CLI flags override the RUN_EVAL constant
    if "--eval" in sys.argv:
        eval_flag = True
    elif "--no-eval" in sys.argv:
        eval_flag = False
    else:
        eval_flag = RUN_EVAL
    validate_bud(file_path, run_eval=eval_flag)
