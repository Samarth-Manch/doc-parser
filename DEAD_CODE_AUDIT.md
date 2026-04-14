# Dead Code Audit — doc-parser

Audit of which files in the repository are part of the active AI pipeline vs. leftover/experimental code that can be removed.

## Files You Asked Me to Check

You provided these as the known active entry points and directories:

**Active pipeline shell scripts (root)**
- `run_stages_ph_creation.sh`
- `run_stages_raw_material_creation.sh`
- `run_stages_sunpharma_material.sh`

**Active pipeline shell scripts (`bash_scripts/`)**
- `bash_scripts/run_pipeline.sh`
- `bash_scripts/run_stages_pidilite.sh`
- `bash_scripts/run_stages_unspsc.sh`
- `bash_scripts/run_stages_vendor_extension.sh`
- `bash_scripts/run_stages.sh`

**Mini agents directory**
- `.claude/agents/mini/`

**Dispatchers directory**
- `dispatchers/agents/`

---

## 1. Active Pipeline (Keep)

### Active Dispatchers — `dispatchers/agents/`

All called directly by your active shell scripts.

| File | Stage | Purpose |
|---|---|---|
| `rule_placement_dispatcher.py` | 1 | Assigns rule names to fields |
| `source_destination_dispatcher.py` | 2 | Maps source/destination fields per rule |
| `edv_rule_dispatcher.py` | 3 | Populates EDV dropdown params |
| `validate_edv_dispatcher.py` | 4 | Adds Validate EDV rules |
| `expression_rule_dispatcher.py` | 5 | All expression rules in one pass |
| `inter_panel_dispatcher.py` | 6 | Cross-panel rules |
| `session_based_dispatcher.py` | 7 | Session-based RuleCheck insertion |
| `convert_to_api_format.py` | 8 | Final platform JSON (deterministic) |
| `fix_mandatory_fields.py` | 9 | Deterministic post-processing |
| `resolve_edv_varnames.py` | 10 | Deterministic post-processing |
| `post_trigger_linker.py` | 11 | Deterministic post-processing |

**Support utilities** (imported by the dispatchers above):
- `dispatchers/agents/stream_utils.py`
- `dispatchers/agents/inter_panel_utils.py`
- `dispatchers/agents/context_optimization.py`

### Active Mini Agents — `.claude/agents/mini/`

| File | Used By |
|---|---|
| `01_rule_type_placement_agent_v2.md` | `rule_placement_dispatcher.py` |
| `02_source_destination_agent_v2.md` | `source_destination_dispatcher.py` |
| `03_edv_rule_agent_v2.md` | `edv_rule_dispatcher.py` |
| `04_validate_edv_agent_v2.md` | `validate_edv_dispatcher.py` |
| `expression_rule_agent.md` | `expression_rule_dispatcher.py` and `inter_panel_dispatcher.py` |
| `inter_panel_detect_refs.md` | `inter_panel_dispatcher.py` |
| `08_session_based_agent.md` | `session_based_dispatcher.py` |

### Active Core Resources

- `doc_parser/` — DOCX → JSON parser package
- `field_extractor/` — Stage 0 field extraction
- `helpers/` — Shared helper modules
- `rules/Rule-Schemas.json` — Loaded by every active stage
- `rule_extractor/static/keyword_tree.json` — Loaded by Stage 1 (only this JSON; the `.py` next to it is dead)
- `documents/` — Input BUD `.docx` files
- `test/` — Stage-by-stage test JSON outputs

---

## 2. Conditionally Active

These have real callers but only in some flows. Decide based on whether you still need those flows.

| File | Used By | Notes |
|---|---|---|
| `dispatchers/agents/workflow_graph_converter.py` | `run_stages_ph_creation_workflow.sh` only | Special workflow injection variant |

---

## 3. Dead Code (Safe to Delete)

### Orphan Dispatchers — `dispatchers/agents/`

Not referenced by any active shell script.

| File | Companion Mini Agent |
|---|---|
| `clear_child_fields_dispatcher.py` | `.claude/agents/mini/07_clear_child_fields_agent.md` |
| `conditional_logic_dispatcher.py` | `.claude/agents/mini/05_condition_agent_v2.md` |
| `derivation_logic_dispatcher.py` | `.claude/agents/mini/06_derivation_agent.md` |
| `expression_pattern_analyzer_dispatcher.py` + `bash_scripts/run_pattern_analyzer.sh` | Standalone analysis utility, retired |

### Retired QA Framework

| Path | Reason |
|---|---|
| `eval/` | Separate QA framework — retired. Skills (`eval_panel_rules`, `eval_rule_extraction`, etc.) that depend on it should also be removed. |

### Orphan Mini Agent Files — `.claude/agents/mini/`

| File | Reason |
|---|---|
| `09_inter_panel_agent_v1.md` | Superseded by current inter-panel agents |
| `09_inter_panel_analysis_agent.md` | Superseded |
| `09_inter_panel_complex_agent.md` | Superseded |
| `expression_rule_agent.md.bak` | Backup file |

### Dead Root-Level Scripts

| File | Status |
|---|---|
| `_build_rules.py` | 0 bytes (empty stub) |
| `_gen_rules.py` | Ad-hoc experiment, not in pipeline |
| `_tmp_build_rules.py` | Ad-hoc experiment, not in pipeline |
| `document_parser_gui_enhanced.py` | 0 bytes (empty stub) |
| `overfitting_risk_report.html` | Untracked output artifact |

### Dead Modules / Directories

| Path | Reason |
|---|---|
| `rule_extractor/stage_1_rule_type_placement.py` | Replaced by `rule_placement_dispatcher.py`. Only `static/keyword_tree.json` next to it is still in use. |
| `orchestrators/` | Abandoned infrastructure, no imports from active code |
| `commands/` | Empty / unused |
| `scripts/` | Empty / unused |
| `archive/` | ~165 MB graveyard, intentionally moved here in commits `798ec63`, `bdd82a8`, `f23a388` |
| `self-learning/` | Personal `.docx` status notes, not code |

---

## 4. Resolved Decisions

| Item | Decision |
|---|---|
| `bash_scripts/run_stages_unspsc.sh` | **Keep.** Stage 0–7 subset is intentional. |
| `session_based_dispatcher.py` + `08_session_based_agent.md` | **Keep — needed.** Promoted to Active (Stage 7). The PH/Raw/Sunpharma shells should be reviewed to confirm whether Stage 7 needs to be added back. |
| `eval/` | **Retire.** Move to dead code along with its dependent skills. |
| `expression_pattern_analyzer_dispatcher.py` + `bash_scripts/run_pattern_analyzer.sh` | **Delete.** Not needed. |

---

## Summary

- **Active pipeline** spans Stages 1–8 plus deterministic 9–11. Session-based (Stage 7) is part of the active set.
- **Three orphan dispatchers** (`clear_child_fields`, `conditional_logic`, `derivation_logic`) and their mini agents have full infrastructure but are never called — safe to delete.
- **Pattern analyzer** (dispatcher + shell) is retired.
- **`eval/`** framework is retired; dependent skills should be removed alongside it.
- **Four root-level Python files** are stubs or ad-hoc scripts.
- **`archive/`** (~165 MB) is a proper graveyard from prior cleanup commits — safe to ignore.
- **Open follow-up:** PH/Raw/Sunpharma shells currently skip Stage 7 — verify whether session-based should be wired in for those BUDs.
