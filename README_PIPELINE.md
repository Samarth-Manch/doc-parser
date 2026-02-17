# Rule Extraction Pipeline

Extracts structured rules from a BUD document (.docx) through a 7-stage pipeline. Each stage is a dispatcher that processes panels one-by-one, calling Claude mini agents (stages 1-5) or running deterministic logic (stages 6-7).

## Quick Start

```bash
# Vendor Creation Sample BUD — full pipeline with schema injection
./run_pipeline.sh \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --schema "documents/json_output/vendor_creation.json" \
    --pretty

# Vendor Creation Sample BUD — full pipeline without schema (legacy mode)
./run_pipeline.sh \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --pretty

# Vendor Creation Sample BUD — run only stage 5 (conditional logic)
./run_pipeline.sh \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --start-stage 5 --end-stage 5
```

## Pipeline Stages

```
BUD Document (.docx)
  |
  v
[Stage 1] Rule Placement .............. Assigns rule names to fields
  |
  v
[Stage 2] Source / Destination ........ Maps source & destination fields per rule
  |
  v
[Stage 3] EDV Rules ................... Populates EDV dropdown params
  |
  v
[Stage 4] Validate EDV ................ Places Validate EDV rules on dropdowns
  |
  v
[Stage 5] Conditional Logic ........... Adds visibility/state rules & conditions
  |
  v
[Stage 6] Session Based ............... Injects RuleCheck with session-based rules
  |
  v
[Stage 7] Convert to API Format ...... Outputs final API JSON
```

## Running the Full Pipeline

```bash
./run_pipeline.sh --bud <path-to-bud.docx> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--bud <path>` | *(required)* | Path to BUD document |
| `--schema <path>` | — | API schema JSON for injection mode (stage 7) |
| `--keyword-tree <path>` | `rule_extractor/static/keyword_tree.json` | Keyword tree for action type detection (stages 1) |
| `--rule-schemas <path>` | `rules/Rule-Schemas.json` | Rule schemas JSON (stages 1, 2) |
| `--output-dir <path>` | `output` | Base directory for intermediate outputs |
| `--final-output <path>` | `documents/json_output/vendor_creation_generated.json` | Final API JSON path |
| `--bud-name <name>` | `"Vendor Creation"` | BUD name (legacy mode, stage 7) |
| `--start-stage <1-7>` | `1` | Start from this stage |
| `--end-stage <1-7>` | `7` | Stop after this stage |
| `--pretty` | — | Pretty print final JSON |

### Resuming from a specific stage

If stage 3 fails, fix the issue and resume:

```bash
./run_pipeline.sh --bud "documents/Vendor Creation Sample BUD.docx" --start-stage 3
```

### Running a subset of stages

```bash
# Only EDV stages (3 and 4)
./run_pipeline.sh --bud "documents/Vendor Creation Sample BUD.docx" --start-stage 3 --end-stage 4
```

## Running Stages Individually

Each dispatcher is a standalone Python script. Below are the commands to run them one at a time.

### Stage 1: Rule Placement

Parses the BUD, extracts fields with logic, and assigns rule names using keyword matching + Claude mini agent.

```bash
python3 dispatchers/agents/rule_placement_dispatcher.py \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --output output/rule_placement/all_panels_rules.json
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--bud` | *(required)* | BUD document path |
| `--keyword-tree` | `rule_extractor/static/keyword_tree.json` | Keyword tree for action type detection |
| `--rule-schemas` | `rules/Rule-Schemas.json` | Rule schemas JSON |
| `--output` | `output/rule_placement/all_panels_rules.json` | Output path |

**Agent:** `mini/01_rule_type_placement_agent_v2`
**Output:** Fields grouped by panel, each with a `rules` array of rule name strings.

---

### Stage 2: Source / Destination

Takes rule names and determines which fields are sources (inputs) and destinations (outputs) for each rule.

```bash
python3 dispatchers/agents/source_destination_dispatcher.py \
    --input output/rule_placement/all_panels_rules.json \
    --output output/source_destination/all_panels_source_dest.json
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--input` | *(required)* | Stage 1 output |
| `--rule-schemas` | `rules/Rule-Schemas.json` | Rule schemas JSON |
| `--output` | `output/source_destination/all_panels_source_dest.json` | Output path |

**Agent:** `mini/02_source_destination_agent_v2`
**Output:** Rules as objects with `source_fields` and `destination_fields` arrays.

---

### Stage 3: EDV Rules

Populates EDV (External Data Value) params for dropdown fields — table name, display attributes, and cascading criteria.

```bash
python3 dispatchers/agents/edv_rule_dispatcher.py \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --source-dest-output output/source_destination/all_panels_source_dest.json \
    --output output/edv_rules/all_panels_edv.json
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--bud` | *(required)* | BUD document (for reference tables) |
| `--source-dest-output` | *(required)* | Stage 2 output |
| `--output` | `output/edv_rules/all_panels_edv.json` | Output path |

**Agent:** `mini/03_edv_rule_agent_v2`
**Output:** EDV rules with `params.conditionList` populated and `_dropdown_type` (Independent/Parent/Child).

---

### Stage 4: Validate EDV

Places Validate EDV rules on dropdown fields that need server-side validation and auto-population from EDV tables.

```bash
python3 dispatchers/agents/validate_edv_dispatcher.py \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --edv-output output/edv_rules/all_panels_edv.json \
    --output output/validate_edv/all_panels_validate_edv.json
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--bud` | *(required)* | BUD document (for reference tables) |
| `--edv-output` | *(required)* | Stage 3 output |
| `--output` | `output/validate_edv/all_panels_validate_edv.json` | Output path |

**Agent:** `mini/04_validate_edv_agent_v2`
**Output:** New `Validate EDV (Server)` rules added to dropdowns with `source_fields`, `destination_fields`, and `params`.

---

### Stage 5: Conditional Logic

Handles all visibility/state rules. Discards any from previous stages and rebuilds from scratch by analyzing all fields in each panel.

```bash
python3 dispatchers/agents/conditional_logic_dispatcher.py \
    --validate-edv-output output/validate_edv/all_panels_validate_edv.json \
    --output output/conditional_logic/all_panels_conditional_logic.json
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--validate-edv-output` | *(required)* | Stage 4 output |
| `--output` | `output/conditional_logic/all_panels_conditional_logic.json` | Output path |

**Agent:** `mini/05_condition_agent_v2`
**Output:** Rules with `conditionalValues`, `condition`, `conditionValueType` added. Visibility/state rules consolidated on controller fields.

---

### Stage 6: Session Based

Deterministic (no AI agent). Reads BUD sections 4.5.1/4.5.2 and injects a `RuleCheck` field with session-based visibility rules into the second panel.

```bash
python3 dispatchers/agents/session_based_dispatcher.py \
    --conditional-logic-output output/conditional_logic/all_panels_conditional_logic.json \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --output output/session_based/all_panels_session_based.json
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--conditional-logic-output` | *(required)* | Stage 5 output |
| `--bud` | *(required)* | BUD document (for 4.5.1/4.5.2 sections) |
| `--output` | `output/session_based/all_panels_session_based.json` | Output path |

**Output:** `RuleCheck` field inserted at the start of the second panel with 4 session-based rules (FIRST_PARTY visible/invisible, SECOND_PARTY visible/invisible).

---

### Stage 7: Convert to API Format

Deterministic (no AI agent). Converts the pipeline output into the final API JSON format with `formFillMetadatas` and `formFillRules`.

```bash
# Injection mode (recommended — injects rules into existing schema)
python3 dispatchers/agents/convert_to_api_format.py \
    --schema "documents/json_output/vendor_creation.json" \
    --input output/session_based/all_panels_session_based.json \
    --output documents/json_output/vendor_creation_generated.json \
    --pretty

# Legacy mode (builds entire API template from scratch)
python3 dispatchers/agents/convert_to_api_format.py \
    --input output/session_based/all_panels_session_based.json \
    --output documents/json_output/vendor_creation_generated.json \
    --bud-name "Vendor Creation" \
    --pretty
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--schema` | — | Existing API schema (enables injection mode) |
| `--input` / `--rules` | `output/edv_rules/all_panels_edv.json` | Pipeline output to convert |
| `--output` | `documents/json_output/vendor_creation_generated.json` | Final output path |
| `--bud-name` | `"Vendor Creation"` | BUD name (legacy mode only) |
| `--pretty` | — | Pretty print JSON |

**Output:** Final API JSON ready for the platform.

---

## Output Directory Structure

```
output/
├── rule_placement/
│   ├── all_panels_rules.json           # Stage 1
│   └── temp/
├── source_destination/
│   ├── all_panels_source_dest.json     # Stage 2
│   └── temp/
├── edv_rules/
│   ├── all_panels_edv.json             # Stage 3
│   └── temp/
├── validate_edv/
│   ├── all_panels_validate_edv.json    # Stage 4
│   └── temp/
├── conditional_logic/
│   ├── all_panels_conditional_logic.json  # Stage 5
│   └── temp/
└── session_based/
    └── all_panels_session_based.json   # Stage 6

documents/json_output/
└── vendor_creation_generated.json      # Stage 7 (final)
```

## Prerequisites

- Python 3.8+
- `claude` CLI installed and authenticated
- `pip install -r requirements.txt`

## Data Flow Summary

| Stage | Input | Adds |
|-------|-------|------|
| 1 | BUD .docx | `rules: ["Rule Name"]` (strings) |
| 2 | Stage 1 + Rule-Schemas.json | `source_fields`, `destination_fields` |
| 3 | Stage 2 + BUD reference tables | `params.conditionList`, `_dropdown_type` |
| 4 | Stage 3 + BUD reference tables | New `Validate EDV` rule objects |
| 5 | Stage 4 | `conditionalValues`, `condition`, `conditionValueType` |
| 6 | Stage 5 + BUD 4.5.1/4.5.2 | `RuleCheck` field with session rules |
| 7 | Stage 6 | Converts to `formFillMetadatas` + `formFillRules` API format |
