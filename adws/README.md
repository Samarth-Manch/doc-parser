# AI Developer Workflows (ADWs) Output Directory

This directory contains output from orchestrated AI developer workflows.

## Structure

Each workflow run creates a timestamped subdirectory:

```
adws/
├── README.md                          # This file
├── 2026-01-30_14-30-45/              # Example workflow run
│   ├── intra_panel_references.json   # Step 1 output
│   ├── schema.json                   # Parsed BUD schema
│   ├── generated_code/               # Step 2 output
│   │   ├── rule_extraction_agent.py
│   │   └── rule_extraction_agent/
│   ├── populated_schema.json         # Step 3 output
│   ├── eval_report.json              # Step 4 output
│   └── self_heal_feedback.txt        # Step 5 output (if needed)
└── template/                          # Template structure
    └── README.md                      # Template documentation
```

## Workflow Types

### 1. Rule Extraction Workflow

**Purpose:** Generate code to extract formFillRules from BUD documents

**Orchestrator:** `orchestrators/rule_extraction_workflow.py`

**Output Files:**
- `intra_panel_references.json` - Field dependencies within panels
- `schema.json` - Parsed BUD document structure
- `generated_code/` - Complete rule extraction module
- `populated_schema.json` - Schema with formFillRules populated
- `eval_report.json` - Evaluation metrics and feedback
- `self_heal_feedback.txt` - Feedback for self-healing iterations

**Usage:**
```bash
python3 orchestrators/rule_extraction_workflow.py "documents/Vendor Creation Sample BUD.docx"
```

## Output Retention

- Keep successful runs for reference
- Failed runs can be deleted after debugging
- Consider archiving old runs after 30 days

## Directory Naming

Format: `YYYY-MM-DD_HH-MM-SS`

Example: `2026-01-30_14-30-45` = January 30, 2026 at 2:30:45 PM

## Template Structure

See `template/` directory for example workflow output structure.

---

Generated outputs are self-contained and can be archived or analyzed independently.
