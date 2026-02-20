# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Document Parser extracts structured data from BUD (Business Understanding Documents) — Word documents (.docx) that specify form fields, rules, and workflows for the Manch platform. The system parses BUDs into structured JSON, then runs a multi-stage AI pipeline to extract rules and convert them into the platform's API format.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest test_parser.py -v
python3 -m pytest test_parser.py::TestDocumentParser::test_04_field_extraction_count -v

# Run the full rule extraction pipeline (9 stages)
./run_pipeline.sh --bud "documents/Vendor Creation Sample BUD.docx" --schema "documents/json_output/vendor_creation.json" --pretty

# Run pipeline from a specific stage (resume after failure)
./run_pipeline.sh --bud "documents/Vendor Creation Sample BUD.docx" --start-stage 3 --end-stage 5

# Run stages via simple scripts (hardcoded BUD paths)
./run_stages.sh output/vendor          # Vendor Creation BUD
./run_stages_unspsc.sh output/unspsc   # UNSPSC Material BUD

# Run a single dispatcher stage manually
python3 dispatchers/agents/rule_placement_dispatcher.py --bud "documents/Vendor Creation Sample BUD.docx" --output output/rule_placement/all_panels_rules.json

# Run GUI application
python3 document_parser_gui.py

# Batch process all documents
python3 experiment_parser.py
```

## Architecture

There are two main systems: the **doc_parser** package (DOCX → structured JSON) and the **rule extraction pipeline** (structured JSON → platform API rules).

### Core Parser (`doc_parser/`)

- `parser.py` — `DocumentParser` class. Parses .docx via OOXML, extracts fields, tables, workflows, reference tables.
- `models.py` — Dataclasses: `ParsedDocument`, `FieldDefinition`, `WorkflowStep`, `TableData`, `Section`, `ApprovalRule`. All implement `to_dict()`.

```python
from doc_parser import DocumentParser
parser = DocumentParser()
parsed = parser.parse("documents/file.docx")
parsed.all_fields          # List[FieldDefinition]
parsed.reference_tables    # Embedded Excel tables (used by EDV stages)
parsed.to_dict()           # JSON-serializable dict
```

Table classification uses pattern-based header matching: `FIELD_HEADER_PATTERNS`, `INITIATOR_KEYWORDS`, `SPOC_KEYWORDS`, `APPROVAL_KEYWORDS` in `parser.py`.

### Rule Extraction Pipeline (9 Stages)

Each stage is a **dispatcher** (`dispatchers/agents/*.py`) that processes panels one-by-one. Stages 1–8 call Claude **mini agents** (prompt files in `.claude/agents/mini/`). Stage 9 is deterministic.

```
BUD (.docx)
  │
  ├─ Stage 1: Rule Placement ──────── Assigns rule names to fields (keyword tree + LLM)
  ├─ Stage 2: Source / Destination ── Maps source & destination fields per rule
  ├─ Stage 3: EDV Rules ───────────── Populates EDV dropdown params (conditionList)
  ├─ Stage 4: Validate EDV ────────── Adds Validate EDV rules on dropdowns
  ├─ Stage 5: Conditional Logic ───── Visibility/state rules (Make Visible, Enable, Mandatory, etc.)
  ├─ Stage 6: Derivation Logic ────── Expression (Client) rules with ctfd/asdff
  ├─ Stage 7: Clear Child Fields ──── Expression (Client) clearing rules (cf/asdff/rffdd)
  ├─ Stage 8: Session Based ────────── Session-based visibility rules + RuleCheck field
  └─ Stage 9: Convert to API Format ─ Final JSON for platform (formFillMetadatas + formFillRules)
```

**Data flows forward**: Stage N output → Stage N+1 input. Each stage's output is at `output/{stage_name}/all_panels_*.json`. Intermediate per-panel files go in `output/{stage_name}/temp/`.

### Dispatcher Pattern

Every dispatcher follows the same structure:
1. Parse CLI args (input from previous stage, output path, optional BUD path)
2. Load input JSON (panel name → field array)
3. Loop over panels: build prompt with `$FIELDS_JSON` etc., call `claude -p <prompt> --agent mini/<agent_file>`
4. Parse agent JSON output, accumulate results
5. Write `all_panels_*.json`

### Mini Agent Prompts (`.claude/agents/mini/`)

| File | Agent | Key Responsibility |
|------|-------|--------------------|
| `01_rule_type_placement_agent_v2.md` | Rule Placement | Which rules apply to each field |
| `02_source_destination_agent_v2.md` | Source/Destination | Which fields are inputs/outputs of each rule |
| `03_edv_rule_agent_v2.md` | EDV Rules | Dropdown params: ddType, criterias, da, cascading |
| `04_validate_edv_agent_v2.md` | Validate EDV | Validate EDV rules with positional column mapping |
| `05_condition_agent_v2.md` | Conditional Logic | Visibility/state rules with conditions (DISCARDS & rebuilds) |
| `06_derivation_agent.md` | Derivation | Value derivation via ctfd expressions |
| `07_clear_child_fields_agent.md` | Clear Child Fields | Parent→child clearing via cf/asdff/rffdd expressions |
| `08_session_based_agent.md` | Session Based | Session-based rules (FIRST_PARTY/SECOND_PARTY visibility) |

### Key Static Resources

- `rules/Rule-Schemas.json` — 182+ predefined rule patterns with schema IDs, action types, field counts
- `rule_extractor/static/keyword_tree.json` — Hierarchical keyword → action type → rule type mapping tree (used in Stage 1)
- `archive/output/complete_format/*.json` — Reference API schemas for injection mode (Stage 9)

### Convert to API Format (`dispatchers/agents/convert_to_api_format.py`)

Two modes:
- **Injection mode** (`--schema`): Injects extracted rules into an existing API schema. Matches fields by panel+name, preserves existing structure.
- **Legacy mode** (no `--schema`): Builds entire API template from scratch.

Handles: field type mapping, ARRAY_HDR/ARRAY_END linking via headerMetadataId, rule ID generation, variable name sanitization.

### Evaluation Framework (`eval/`)

Compares pipeline output against reference (human-made) output:
- `evaluator.py` — Main engine (deterministic + AI-based checks)
- `field_comparator.py` / `rule_comparator.py` — Structural comparison
- `report_generator.py` — HTML evaluation reports
- `orchestrator_integration.py` — Self-heal feedback loop for orchestrators

## Key Concepts

- **BUD**: Business Understanding Document — the input .docx specifying a form process
- **Panel**: A section/tab in the form (e.g., "Basic Details", "Address Details"). Pipeline processes panels independently.
- **EDV (External Data Value)**: External reference table on the Manch platform. Used for dropdowns, cascading lookups, and validation. Configured via `params.conditionList` with `ddType`, `criterias`, `da`.
- **variableName**: Internal field identifier (e.g., `__vendortype__`). Used in source_fields/destination_fields throughout the pipeline.
- **ARRAY_HDR / ARRAY_END**: Field types that define a repeatable row section (table/grid) in a form. Fields between them are columns.
- **Expression (Client)**: A rule type that uses expression syntax (`ctfd`, `asdff`, `cf`, `rffdd`) in `conditionalValues` for derivation and clearing logic.

## Environment

- **Python 3.8+** required
- **`claude` CLI** must be installed and authenticated (used by dispatchers to call mini agents)
- **tkinter** required for GUI (`sudo apt-get install python3-tk` on Ubuntu)
