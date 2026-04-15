# doc-parser → Claude Plugin Architecture — Design Spec

**Date:** 2026-04-15
**Author:** Samarth Nimbargi
**Status:** Draft — pending review by Prashant
**Scope gate:** This document covers **plugin architecture only**. Feedback loops, memory, self-learning, overfitting evals, release-note impact analysis, and pre-validator unification are explicitly deferred to later phases. One step at a time.

---

## 1. Context and Motivation

### 1.1 Why this restructure

In the daily-status meeting on 2026-04-13 (`self-learning/Daily status update_2.docx`), Prashant laid out a phased plan for the doc-parser project:

- **Phase 0 (prerequisite, already in progress on `chore/archive-dead-code`)**: dead code cleanup.
- **Phase 1 (this spec)**: Restructure doc-parser into a proper Claude plugin with marketplace distribution.
- **Phase 2**: Feedback loops.
- **Phase 3**: Memory added to the feedback loops.
- **Phase 4**: Self-evolving / self-learning.

His exact framing: *"first step is essentially clean the code up … the first thing that we need to do is re-architecture this into a proper plugin and marketplace thing"*. He also emphasized one-step-at-a-time: *"don't put the cognitive load … no, no, I want this, that, all based in one step. The moment you do that, it fails. 1 million context window is insufficient in the design phase."*

### 1.2 The concrete pains this plan addresses

Direct quotes and paraphrases from the meeting:

1. **"I cannot install your package. I have to copy, and when I copied a lot of dependencies get missed because you have some MCP servers and I don't have those."** The current project isn't packageable — reviewers (and eventually customers) can't install it; they have to copy files and discover dependencies manually.
2. **"Cloud has given you a standard way to develop. If he has given a standard way to develop, then he knows while debugging, he knows that, okay, this is a plugin, so I need to figure out where to find what he knows already."** The current layout is ad-hoc (Python at root, agents under `.claude/agents/mini/`, bash in `bash_scripts/` and repo-root, commands under `.claude/commands/`). Claude's own tooling has to guess where things are. A plugin-standard layout gives Claude — and humans — a predictable map.
3. **"Tomorrow your customer wants that particular thing to be installed in his on-prem system, right? How long going to give that? You're not going to copy paste the code. You're going to give an installer to him."** Customer on-prem delivery requires a self-contained installable unit, not a git clone + tribal-knowledge setup.
4. **"Any kind of overfitting is not good as a sanity basically."** Not addressed by this spec directly — but by making the pipeline a clean plugin, the phase-2 overfitting agent (which will audit plugin code) can work against a standardized surface instead of a messy repo.

### 1.3 What is explicitly NOT in this plan

- **No feedback loops.** No event hooks, no learning events, no eval writebacks. Phase 2.
- **No agent memory.** Phase 3.
- **No self-learning / auto-fix mechanisms.** Phase 4.
- **No log-commit-sync hook** (Prashant mentioned it as a plugin feature, but the user scoped this plan to "minimum" — the hook lands later).
- **No pre-validator codebase unification** (Prashant mentioned it in passing at 1:01 — scoped out of this plan at the user's direction; will be a sibling plugin in the same marketplace later).
- **No new features of any kind.** This is a restructure, not a rewrite.
- **No new unit tests.** Existing code has none; writing them is out of scope.
- **No overfitting analysis, eval harness, or cross-BUD regression beyond the 8 presets.**

### 1.4 Scope anchor

The definition of "done" for this plan is exactly three things:

1. Every currently-working pipeline run (all 8 BUD presets — vendor-creation, unspsc, pidilite, vendor-extension, ph-creation, ph-creation-workflow, raw-material-creation, sunpharma) still works, producing baseline-matching output.
2. The project is a Claude plugin in the structural sense: manifest, marketplace.json, agents in `agents/`, commands in `commands/`, Python in `scripts/`, static data in `resources/`, installable via standard plugin + pip install.
3. `CLAUDE.md` reflects the new layout accurately.

Nothing else.

---

## 2. Current State (as of 2026-04-15)

### 2.1 Repo layout

```
doc-parser/
├── doc_parser/              # DOCX → structured JSON (package)
├── field_extractor/         # BUD → schema JSON (Stage 0)
├── dispatchers/agents/      # Python orchestration, one file per stage
├── rule_extractor/          # keyword_tree.json lives under rule_extractor/static/
├── rules/                   # Rule-Schemas.json, rules_buckets.json, classification docs
├── bash_scripts/            # run_pipeline.sh + per-BUD wrappers
├── run_stages_*.sh          # 4 root-level per-BUD wrappers (not symmetric with bash_scripts/)
├── documents/               # user BUDs (input)
├── output/                  # pipeline outputs (by preset)
├── archive/                 # dead-code graveyard
├── self-learning/           # meeting transcripts
├── .claude/
│   ├── agents/
│   │   ├── mini/            # 7 mini-agent prompt files (invoked by dispatchers via `claude -p`)
│   │   ├── docs/            # expression_rules.md reference cheat sheet
│   │   ├── helpers/
│   │   └── *.md             # 2 standalone agents (rule_extraction_coding_agent, extract-fields-to-json)
│   ├── commands/            # 8 user-level slash commands (eval, compare, extract tools)
│   └── settings.local.json
├── requirements.txt
└── CLAUDE.md
```

### 2.2 Pipeline execution model (what actually happens on a run)

1. `bash_scripts/run_pipeline.sh` orchestrates Stages 0–8 in sequence, passing each stage's output to the next.
2. Stages 0 and 8 are pure-deterministic Python — no LLM. Stage 0 = field extraction. Stage 8 = API-format conversion.
3. Stage 7 (session-based RuleCheck) is **hybrid — deterministic Python + agent invocation**. Some of its logic is deterministic field insertion; other parts delegate to the session-based mini-agent (`08_session_based_agent.md`). CLAUDE.md's "deterministic" label is a simplification.
4. Stages 1–6 are dispatched by Python (`dispatchers/agents/*.py`). Each dispatcher:
   - Loads the previous stage's `all_panels_*.json`.
   - Iterates over panels (sometimes in parallel).
   - Templates panel data into a mini-agent prompt (`.claude/agents/mini/*.md`).
   - Shells out: `claude -p "<templated_prompt>"` and streams back JSON.
   - Parses the agent's response, retries on failure, aggregates across panels.
   - Writes the stage's `all_panels_*.json` for the next stage.
5. Resume semantics: `--start-stage N --end-stage M` lets a user re-run a subset of stages using whatever outputs already exist from previous runs.

### 2.3 Known fragility points (acknowledged, not fixed in this plan)

- **Position-dependent imports.** Every `from dispatchers.agents.X` only resolves when `cwd` is the repo root.
- **Hardcoded static-data paths.** `"rules/Rule-Schemas.json"`, `"rule_extractor/static/keyword_tree.json"`, `".claude/agents/mini/..."` — all repo-root-relative, all fragile.
- **Bash wrappers live in two places.** 4 under `bash_scripts/`, 4 at repo root, no rhyme or reason. CLAUDE.md explicitly flags this asymmetry.
- **Mini-agent prompts are data files masquerading as agents.** They're markdown files under `.claude/agents/mini/` but they are not plugin-native agents — they're strings that Python reads and pipes to a CLI. No frontmatter, no discoverability.
- **No installable-unit concept.** To run the pipeline on another machine: clone repo, `pip install -r requirements.txt`, hope `claude` CLI is authenticated, hope no MCP servers are missing, hope the cwd is right.

These are the things the restructure fixes — not by rewriting them, but by moving them into a shape where each one becomes trivially solvable.

---

## 3. Target Architecture

### 3.1 Decisions locked during brainstorming

| # | Decision | Rationale |
|---|---|---|
| D1 | **Scope = plugin architecture only.** | Prashant's one-step-at-a-time directive. |
| D2 | **Fat plugin: all Python moves under `plugins/doc-parser/scripts/lib/`.** | Makes plugin fully self-contained — plugin dir + pip install = ready. Matches Prashant's installable-package ask. |
| D3 | **Aggregate `/doc-parser:run` + 9 per-stage commands.** | Matches existing stage-by-stage debug/resume workflow. |
| D4 | **Mini-agents get promoted to plugin agents (frontmatter added), dispatchers keep shelling out to `claude -p`.** | Zero behavior change in dispatcher loop; gains plugin-native discoverability. |
| D5 | **Marketplace shape: `.claude-plugin/marketplace.json` at repo root declaring a `manch-tooling` marketplace with one plugin.** | Phase-2/3/4 sibling plugins (pre-validator, eval-harness, self-learning) drop in with zero user re-install. |
| D6 | **Fold the 8 existing `.claude/commands/*.md` into plugin commands.** | Prashant's anti-fragmentation directive. |
| D7 | **Migration style: big-bang dev branch, staged reviewable commits.** | Prashant wants to review commit-by-commit. |
| D8 | **Model for every plugin agent: `opus`.** | User directive. |

### 3.2 Target repo layout

```
doc-parser/                                    # repo root unchanged
├── .claude-plugin/
│   └── marketplace.json                       # manch-tooling marketplace (1 plugin today)
├── plugins/
│   └── doc-parser/                            # the plugin
│       ├── .claude-plugin/
│       │   └── plugin.json                    # plugin manifest
│       ├── agents/                            # 7 promoted mini-agents, frontmatter added
│       │   ├── rule-type-placement.md
│       │   ├── source-destination.md
│       │   ├── edv-rule.md
│       │   ├── validate-edv.md
│       │   ├── expression-rule.md
│       │   ├── inter-panel-detect-refs.md
│       │   └── session-based.md
│       ├── commands/                          # 18 slash commands
│       │   ├── run.md                         # aggregate pipeline runner
│       │   ├── extract-fields.md              # Stage 0
│       │   ├── place-rules.md                 # Stage 1
│       │   ├── source-dest.md                 # Stage 2
│       │   ├── edv.md                         # Stage 3
│       │   ├── validate-edv.md                # Stage 4
│       │   ├── expression.md                  # Stage 5
│       │   ├── inter-panel.md                 # Stage 6
│       │   ├── session-based.md               # Stage 7
│       │   ├── convert-api.md                 # Stage 8
│       │   ├── eval-rule-extraction.md        # (8 tool commands folded in)
│       │   ├── eval-panel-rules.md
│       │   ├── compare-form-builders.md
│       │   ├── rule-info-extractor.md
│       │   ├── edv-table-mapping.md
│       │   ├── table-excel-file-map.md
│       │   ├── inter-panel-refs.md
│       │   └── intra-panel-refs.md
│       ├── hooks/                             # empty for scope A (no hooks yet)
│       ├── scripts/
│       │   ├── lib/                           # installable Python package root
│       │   │   ├── __init__.py
│       │   │   ├── doc_parser/                # moved from repo root
│       │   │   ├── field_extractor/           # moved
│       │   │   ├── dispatchers/               # moved (was dispatchers/agents/, flattened)
│       │   │   │   ├── __init__.py
│       │   │   │   ├── _agent_loader.py       # NEW: frontmatter stripper
│       │   │   │   ├── rule_placement.py      # was rule_placement_dispatcher.py
│       │   │   │   ├── source_destination.py
│       │   │   │   ├── edv_rule.py
│       │   │   │   ├── validate_edv.py
│       │   │   │   ├── expression_rule.py
│       │   │   │   ├── inter_panel.py
│       │   │   │   ├── session_based.py
│       │   │   │   ├── convert_to_api_format.py
│       │   │   │   ├── workflow_graph_converter.py
│       │   │   │   ├── context_optimization.py
│       │   │   │   ├── stream_utils.py
│       │   │   │   ├── resolve_edv_varnames.py
│       │   │   │   ├── fix_mandatory_fields.py
│       │   │   │   ├── post_trigger_linker.py
│       │   │   │   └── inter_panel_utils.py
│       │   │   ├── rule_extractor/            # moved
│       │   │   └── pipeline/                  # NEW: entry-point wrappers
│       │   │       ├── __init__.py
│       │   │       ├── run_pipeline.py        # replaces bash run_pipeline.sh
│       │   │       ├── stages.py              # STAGE_AGENTS, STAGE_OUTPUTS, STAGE_DEPS
│       │   │       └── resources.py           # resource_path() helper
│       │   └── bash/                          # kept only if something truly needs shell
│       ├── resources/                         # static pipeline data
│       │   ├── rule-schemas.json              # from rules/Rule-Schemas.json
│       │   ├── rules-buckets.json
│       │   ├── rules-classification.md
│       │   ├── keyword-tree.json              # from rule_extractor/static/
│       │   ├── expression-rules.md            # from .claude/agents/docs/
│       │   └── presets.json                   # per-BUD wiring, replaces 8 shell scripts
│       ├── pyproject.toml                     # makes scripts/lib/ pip-installable
│       ├── requirements.txt                   # deps pinned for plugin
│       └── README.md                          # plugin install + usage docs
├── documents/                                 # UNCHANGED — user BUDs
├── output/                                    # UNCHANGED — pipeline outputs
├── self-learning/                             # UNCHANGED — meeting transcripts
├── archive/                                   # UNCHANGED — dead-code graveyard
├── requirements.txt                           # optional: top-level compat, points to plugin pyproject
└── CLAUDE.md                                  # REWRITTEN: describes plugin layout
```

### 3.3 Plugin manifest shapes

**`.claude-plugin/marketplace.json`** (at repo root):

```json
{
  "name": "manch-tooling",
  "owner": {
    "name": "Manch",
    "email": "engineering@manchtech.com"
  },
  "description": "Internal Claude Code tooling for the Manch platform — BUD parsing, rule extraction, eval harness, and the self-learning pipeline.",
  "plugins": [
    {
      "name": "doc-parser",
      "source": "./plugins/doc-parser",
      "description": "Parses BUDs (Business Understanding Documents) and extracts structured form-fill rules for the Manch platform.",
      "version": "0.1.0",
      "category": "document-processing",
      "tags": ["bud", "form-builder", "rule-extraction", "manch"]
    }
  ]
}
```

**`plugins/doc-parser/.claude-plugin/plugin.json`**:

```json
{
  "name": "doc-parser",
  "version": "0.1.0",
  "description": "BUD → form-fill rules pipeline. 9 stages (field extraction, rule placement, source/destination, EDV, validate EDV, expression, inter-panel, session-based, API conversion) plus eval and comparison tools.",
  "author": {
    "name": "Manch",
    "email": "engineering@manchtech.com"
  },
  "keywords": ["bud", "form-builder", "rule-extraction"]
}
```

`agents/`, `commands/`, `hooks/`, `scripts/` are auto-discovered by Claude Code — no explicit listing in the manifest.

### 3.4 Python package strategy

**The problem:** position-dependent imports only work when `cwd == repo root`. Slash commands may run from anywhere. The plugin may be installed in `~/.claude/plugins/...`.

**The fix:** make the plugin's Python tree a proper installable package via `pyproject.toml`. After `pip install -e plugins/doc-parser/`, all these imports work from any `cwd`:

```python
from doc_parser import DocumentParser
from field_extractor.extract_fields_complete import extract_fields_complete
from dispatchers.rule_placement import main as run_stage1
from pipeline.stages import STAGE_AGENTS, STAGE_OUTPUTS
from pipeline.resources import resource_path
```

**`pyproject.toml`** (at `plugins/doc-parser/pyproject.toml`):

```toml
[project]
name = "doc-parser-pipeline"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "python-docx",
    "lxml",
    "openai",
    "anthropic",
    "requests",
    "python-dotenv",
]

[tool.setuptools.packages.find]
where = ["scripts/lib"]
```

**Two rules for imports:**
1. Every intra-plugin import is absolute, never relative to `cwd`.
2. No hardcoded paths to static data. All static-data access goes through `pipeline.resources.resource_path(name)`.

**Install-path discovery** (`scripts/lib/pipeline/resources.py`):

```python
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]  # scripts/lib/pipeline → plugin root
RESOURCES = PLUGIN_ROOT / "resources"

def resource_path(name: str) -> Path:
    p = RESOURCES / name
    if not p.exists():
        raise FileNotFoundError(f"Plugin resource not found: {p}")
    return p
```

Works whether the plugin lives inside the repo or is installed to `~/.claude/plugins/manch-tooling/doc-parser/`.

### 3.5 Slash command surface (18 total)

**Pipeline commands (10):**

| Command | Wraps | Purpose |
|---|---|---|
| `/doc-parser:run` | `pipeline/run_pipeline.py` | Full Stage 0→8 run. Accepts `--bud`, `--schema`, `--start-stage`, `--end-stage`, `--output-dir`, `--preset`. Replaces `bash_scripts/run_pipeline.sh`. |
| `/doc-parser:extract-fields` | Stage 0 | Deterministic field extraction (BUD → schema JSON). |
| `/doc-parser:place-rules` | Stage 1 dispatcher | Rule placement per panel. |
| `/doc-parser:source-dest` | Stage 2 dispatcher | Source/destination fields. |
| `/doc-parser:edv` | Stage 3 dispatcher | EDV dropdown params. |
| `/doc-parser:validate-edv` | Stage 4 dispatcher | Validate EDV rules. |
| `/doc-parser:expression` | Stage 5 dispatcher | Expression rules. |
| `/doc-parser:inter-panel` | Stage 6 dispatcher | Cross-panel rules. |
| `/doc-parser:session-based` | Stage 7 dispatcher | Session-based RuleCheck (hybrid deterministic + agent). |
| `/doc-parser:convert-api` | Stage 8 | API-format conversion (deterministic). |

**Tool commands (8)** — the existing `.claude/commands/*.md` folded in:

| New command | Source file |
|---|---|
| `/doc-parser:eval-rule-extraction` | `eval_rule_extraction.md` |
| `/doc-parser:eval-panel-rules` | `eval_panel_rules.md` |
| `/doc-parser:compare-form-builders` | `compare_form_builders.md` |
| `/doc-parser:rule-info-extractor` | `rule_info_extrator.md` |
| `/doc-parser:edv-table-mapping` | `edv_table_mapping.md` |
| `/doc-parser:table-excel-file-map` | `table_excel_file_map.md` |
| `/doc-parser:inter-panel-refs` | `inter_panel_rule_field_references.md` |
| `/doc-parser:intra-panel-refs` | `intra_panel_rule_field_references.md` |

**Command file shape** (example: `commands/place-rules.md`):

```markdown
---
name: place-rules
description: Stage 1 — assign rule types to each field in the BUD using the keyword tree and mini-agent.
argument-hint: --input <schema.json> --output <rules.json> [--bud <bud.docx>]
---

Run the rule-placement dispatcher:

!python -m pipeline.run_stage \
    --stage 1 \
    --bud "$BUD" \
    --input "$INPUT" \
    --output "$OUTPUT"
```

Markdown is the contract. Python is the work.

### 3.6 Mini-agent promotion

All 7 prompt files under `.claude/agents/mini/` move to `plugins/doc-parser/agents/` with two changes: (1) rename/flatten, (2) add YAML frontmatter.

**File moves:**

| Old path | New path |
|---|---|
| `.claude/agents/mini/01_rule_type_placement_agent_v2.md` | `plugins/doc-parser/agents/rule-type-placement.md` |
| `.claude/agents/mini/02_source_destination_agent_v2.md` | `plugins/doc-parser/agents/source-destination.md` |
| `.claude/agents/mini/03_edv_rule_agent_v2.md` | `plugins/doc-parser/agents/edv-rule.md` |
| `.claude/agents/mini/04_validate_edv_agent_v2.md` | `plugins/doc-parser/agents/validate-edv.md` |
| `.claude/agents/mini/expression_rule_agent.md` | `plugins/doc-parser/agents/expression-rule.md` |
| `.claude/agents/mini/inter_panel_detect_refs.md` | `plugins/doc-parser/agents/inter-panel-detect-refs.md` |
| `.claude/agents/mini/08_session_based_agent.md` | `plugins/doc-parser/agents/session-based.md` |

(Stage 7 is a hybrid deterministic-plus-agent stage — see §2.2 — so the session-based agent is a live pipeline agent, not a standalone.)

Version suffixes (`_v2`) and numeric prefixes (`01_`, `02_`) dropped — versioning lives in git, ordering lives in `pipeline/stages.py`.

**Standalone agents at `.claude/agents/` top level** (`extract-fields-to-json.md`, `rule_extraction_coding_agent.md`) are **not** part of the mini-agent pipeline and are **not** actively invoked by any dispatcher today. Disposition:

- `extract-fields-to-json.md` — move to `plugins/doc-parser/agents/extract-fields-to-json.md` with frontmatter. Still not invoked by any dispatcher. Preserved for phase-2 use as a standalone callable agent.
- `rule_extraction_coding_agent.md` — move to `plugins/doc-parser/agents/rule-extraction-coding.md` with frontmatter. Same rationale: preserved as a callable plugin agent, not wired into the pipeline.

Neither affects baseline output because neither is in the pipeline execution path.

**Frontmatter template** (applied to every agent):

```markdown
---
name: rule-type-placement
description: Determines which rules from the rule catalog apply to each field in a BUD panel. Reads panel fields + rule schemas, returns a per-field rule-name list. Used by Stage 1.
model: opus
---

<existing prompt body, unchanged>
```

**Dispatcher compatibility** — the critical bit. Python dispatchers keep reading the agent markdown and shelling out via `claude -p`. One helper strips frontmatter before the prompt body reaches the CLI:

```python
# scripts/lib/dispatchers/_agent_loader.py
from pathlib import Path
from pipeline.resources import PLUGIN_ROOT

AGENTS_DIR = PLUGIN_ROOT / "agents"

def load_agent_prompt(agent_name: str) -> str:
    path = AGENTS_DIR / f"{agent_name}.md"
    text = path.read_text()
    if text.startswith("---"):
        _, _, body = text.split("---", 2)
        return body.lstrip()
    return text
```

Every dispatcher that used to read a mini-agent file by path now calls `load_agent_prompt("rule-type-placement")`. One place to strip, zero changes to the dispatcher loop.

**Stage-to-agent mapping** (`scripts/lib/pipeline/stages.py`):

```python
STAGE_AGENTS = {
    1: "rule-type-placement",
    2: "source-destination",
    3: "edv-rule",
    4: "validate-edv",
    5: "expression-rule",
    6: "inter-panel-detect-refs",  # Stage 6 also re-invokes expression-rule for pass 2
    7: "session-based",            # Stage 7 is hybrid: deterministic Python + agent invocation
    # Stage 0 and 8 are pure-deterministic — no agent
}
```

**Docs/helpers files** (`expression_rules.md`, `expression_pattern_analyzer.md`, etc.) are not agents — they move to `plugins/doc-parser/resources/` as static reference data.

### 3.7 User-data path conventions

| Kind | Where | How commands reach it |
|---|---|---|
| Plugin code (Python, agents, commands) | Plugin install dir | Auto-resolved via `PLUGIN_ROOT` + package imports |
| Plugin static data (rule schemas, keyword tree, cheat sheets) | `<plugin>/resources/` | `resource_path("name")` helper |
| **User BUDs** | Wherever the user keeps them (default: repo's `documents/`) | Absolute path via `--bud` flag |
| **Pipeline outputs** | Wherever the user wants them (default: repo's `output/`) | Absolute path via `--output-dir` flag |
| **Per-BUD presets** | `<plugin>/resources/presets.json` | `--preset <name>` flag |

**`resources/presets.json`** replaces the 8 per-BUD shell scripts:

```json
{
  "vendor-creation": {
    "bud": "documents/Vendor Creation Sample BUD.docx",
    "schema": "documents/json_output/vendor_creation.json",
    "output_dir": "output/vendor"
  },
  "unspsc": { "...": "..." },
  "pidilite-block-unblock": { "...": "..." },
  "vendor-extension": { "...": "..." },
  "ph-creation": { "...": "..." },
  "ph-creation-workflow": {
    "bud": "documents/PH Creation BUD.docx",
    "schema": "documents/json_output/ph_creation.json",
    "output_dir": "output/ph",
    "include_workflow_graph": true
  },
  "raw-material-creation": { "...": "..." },
  "sunpharma-material": { "...": "..." }
}
```

Preset paths are relative to the **user's cwd** (where they're running from), not the plugin install dir. That's intentional: a preset `bud` of `documents/...` means "from your current project". Absolute paths in a preset override. Explicit `--bud`/`--schema`/`--output-dir` flags override preset values individually.

**Environment / API keys:** `ANTHROPIC_API_KEY` and any other secrets come from the user's environment — the plugin does not ship or manage secrets.

### 3.8 What is NOT in the plugin

- **No hooks.** Scope A.
- **No MCP server declarations.** None currently in use.
- **No skills.** Claude Code skills are workflows (like `superpowers:brainstorming`); this pipeline is commands + agents, not skill-shaped.
- **No feedback/eval/learning machinery.** Phase 2+.

---

## 4. Migration Plan (Commit-by-Commit)

Branch: `plugin-architecture`, cut from `chore/archive-dead-code`. Single PR. Reviewed at the commit level. Every commit must leave `main`-equivalent behavior intact (or be explicitly marked "wip: pipeline broken until commit N"). Prashant reviews commits; the final commit flips the switch.

**Commit 0 (pre-branch):** Baseline capture. Before creating the branch, run `./bash_scripts/run_pipeline.sh` (or the matching per-BUD shell script) for **all 8 presets** against current `chore/archive-dead-code` HEAD. Save outputs to `/tmp/plugin-migration-baseline/<preset>/`. This is the regression oracle for every subsequent commit.

**Commit 1: Scaffold plugin skeleton (no moves).**
Create `.claude-plugin/marketplace.json`, `plugins/doc-parser/.claude-plugin/plugin.json`, all empty plugin subdirectories (`agents/`, `commands/`, `hooks/`, `scripts/lib/`, `scripts/pipeline/`, `resources/`) with `.gitkeep`, `pyproject.toml`, `README.md`.
**Verify:** Old pipeline still runs. One preset end-to-end.

**Commit 2: Move static resources.**
`rules/Rule-Schemas.json`, `rules/rules_buckets.json`, `rules/RULES_CLASSIFICATION.md`, `rule_extractor/static/keyword_tree.json`, `.claude/agents/docs/expression_rules.md` → `plugins/doc-parser/resources/` (renamed to kebab-case). Add `scripts/lib/pipeline/resources.py`. Temporary symlinks at old paths so existing code still resolves.
**Verify:** Stage 0 output matches baseline for one preset.

**Commit 3: Move `doc_parser/` package.**
`doc_parser/` → `plugins/doc-parser/scripts/lib/doc_parser/`. Update `pyproject.toml` so `pip install -e plugins/doc-parser/` registers it. Old `from doc_parser import DocumentParser` still resolves because the package is now installed, not path-resolved.
**Verify:** `python -c "from doc_parser import DocumentParser; DocumentParser().parse('documents/X.docx')"` works from `/tmp`.

**Commit 4: Move `field_extractor/`.** Same pattern.
**Verify:** Stage 0 matches baseline.

**Commit 5: Move `rule_extractor/`.** Drop the `keyword_tree.json` symlink now that `rule_extractor` is inside the plugin and resources are accessed via `resource_path()`.
**Verify:** Stage 0 + Stage 1 match baseline.

**Commit 6: Move `dispatchers/`.**
`dispatchers/agents/*.py` → `plugins/doc-parser/scripts/lib/dispatchers/*.py` (flatten — drop the `agents/` subdir; it was always redundant). Rename `rule_placement_dispatcher.py` → `rule_placement.py` etc. Update every intra-dispatcher import. Add `scripts/lib/dispatchers/_agent_loader.py`.
**Verify:** Each dispatcher runs standalone via `python -m dispatchers.<name>`.

**Commit 7: Promote mini-agents to plugin agents.**
Move and rename the 7 `.claude/agents/mini/*.md` files. Add frontmatter (`name`, `description`, `model: opus`). Update every dispatcher that reads a prompt file to go through `_agent_loader.load_agent_prompt(name)`.
**Verify:** Full pipeline runs on vendor-creation BUD, output matches baseline.

**Commit 8: Write pipeline runner.**
`scripts/lib/pipeline/run_pipeline.py` ports `bash_scripts/run_pipeline.sh` logic. `scripts/lib/pipeline/stages.py` holds `STAGE_AGENTS`, `STAGE_OUTPUTS`, `STAGE_DEPS`. Flag handling, preset expansion, `--start-stage`/`--end-stage`, explicit override precedence.
**Verify:** `python -m pipeline.run_pipeline --preset vendor-creation` matches baseline.

**Commit 9: Write slash commands (18 files).**
Create the 10 pipeline commands + 8 tool commands under `plugins/doc-parser/commands/`. Each is thin markdown invoking the Python entry point. Fold the 8 existing `.claude/commands/*.md` into the plugin commands dir with updated invocation paths.
**Verify:** `/doc-parser:run --preset vendor-creation` from inside Claude Code matches the direct Python invocation's output.

**Commit 10: Port presets.**
Build `resources/presets.json` from the 8 per-BUD shell scripts (`run_stages_ph_creation.sh`, `run_stages_vendor_extension.sh`, `bash_scripts/run_stages.sh`, etc.). Run each preset end-to-end and diff output against baseline.
**Verify:** All 8 presets match their pre-migration baselines.

**Commit 11: Delete legacy entry points.**
Remove `bash_scripts/run_pipeline.sh`, `bash_scripts/run_stages*.sh`, `run_stages_*.sh` at repo root, `.claude/agents/mini/`, `.claude/agents/docs/`, `.claude/commands/`, the symlinks from commit 2, the now-empty old `rules/`, `rule_extractor/static/`, `doc_parser/`, `field_extractor/`, `dispatchers/`.
**Verify:** `git status` shows only plugin paths; old paths are gone. One preset end-to-end as a final sanity check.

**Commit 12: Update `CLAUDE.md`.**
Rewrite the architecture and commands sections to describe the plugin layout, the `.claude-plugin/` manifest shape, and the new slash commands. Delete references to `dispatchers/agents/`, `bash_scripts/`, and old file paths. Final commit.

**Rollback strategy:** branch is rebaseable. If commit 7 breaks something that commits 8+ depend on, `git rebase -i` to rewrite. If the whole thing is worse than expected at commit 9, the branch never merges and `main` stays clean. Production is safe throughout.

---

## 5. Verification and Definition of Done

### 5.1 "Done" acceptance criteria

1. **All 8 presets produce baseline-matching output** on the final commit. Semantic equivalence (not byte-identical — Claude's LLM output has run-to-run variance). Spot checks on field count, rule count per panel, and a random 10% of generated rules.
2. **All 18 slash commands are callable from Claude Code** and each one either runs the correct underlying Python or produces the same output as its pre-migration equivalent. Tested interactively.
3. **`pip install -e plugins/doc-parser/` succeeds in a clean venv** and `python -c "from doc_parser import DocumentParser; from dispatchers import rule_placement; from pipeline.resources import resource_path"` runs without error from `/tmp`.
4. **`CLAUDE.md` describes the new layout accurately.** Fresh-reader test: someone who has never seen the pre-migration codebase can follow CLAUDE.md and run `/doc-parser:run --preset vendor-creation` to completion.
5. **No dead paths left behind.** `git grep` for `bash_scripts`, `dispatchers/agents`, `.claude/agents/mini`, `rule_extractor/static`, `rules/Rule-Schemas.json` returns zero hits.
6. **Plugin is installable from a fresh checkout.** On a machine that isn't the dev box: `git clone <branch> && cd doc-parser && /plugin marketplace add . && /plugin install doc-parser@manch-tooling && pip install -e plugins/doc-parser/ && /doc-parser:run --preset vendor-creation` — one preset works. This is the acceptance test Prashant implicitly asked for.

### 5.2 Per-commit testing rhythm

| Commit | Verification gate |
|---|---|
| 0 | Baseline captured for all 8 presets |
| 1 | Old pipeline still runs one preset end-to-end |
| 2 | Stage 0 output matches baseline |
| 3 | Import works from `/tmp`; Stage 0 matches baseline |
| 4 | Stage 0 matches baseline |
| 5 | Stages 0–1 match baseline |
| 6 | Each dispatcher runs standalone; one preset end-to-end |
| 7 | Full pipeline on vendor-creation matches baseline |
| 8 | `python -m pipeline.run_pipeline --preset vendor-creation` matches baseline |
| 9 | `/doc-parser:run --preset vendor-creation` from Claude Code matches baseline |
| 10 | All 8 presets match their baselines |
| 11 | `git grep` for legacy paths returns zero; one preset end-to-end |
| 12 | Fresh-reader follows CLAUDE.md blind, one preset works |

### 5.3 Explicitly NOT tested in this plan

- No new unit tests added.
- No overfitting analysis (phase 2).
- No feedback-loop plumbing (phase 2).
- No performance benchmarks.
- No cross-BUD regression beyond the 8 presets.

### 5.4 Known risks and mitigations

| Risk | Mitigation |
|---|---|
| Silent behavior change from frontmatter leaking into prompt | `_agent_loader.py` strips frontmatter before `claude -p`; verified in commit 7 |
| Import path breakage in edge modules | `pip install -e` + running every dispatcher standalone from `/tmp` |
| Static resource path drift | `resource_path()` helper; commit 2 adds symlinks, commit 11 removes them after all routing goes through the helper |
| Per-BUD preset wiring typo | Commit 10 runs all 8 presets |
| Fresh-install dependency gaps (what Prashant complained about) | Acceptance test #6 |
| Commit order error leaves branch un-reviewable | Rebaseable branch; commits 8–10 are where order matters most |

### 5.5 Accepted (unmitigated) risks

- No automated regression tests after landing. Phase 2 adds the eval harness; until then, "did it still work?" is a human-with-a-preset task.
- If a BUD that isn't one of the 8 presets regresses, we only find out when someone runs it.

---

## 6. What Happens After This Plan Lands (Sequencing for Future Phases)

This spec deliberately builds the substrate for phases 2–4. None of that work lives here, but the plugin shape makes it cheap to add later:

- **Phase 2 (feedback loops)** — new sibling plugins in the same marketplace (`plugins/eval-harness/`, `plugins/overfitting-agent/`), or new hooks in `plugins/doc-parser/hooks/`. No restructure needed.
- **Phase 3 (agent memory)** — turn on Claude Code's agent-level memory for the plugin agents. Zero code changes; it's a setting.
- **Phase 4 (self-learning)** — a new orchestrator plugin that consumes the eval harness output. Drops into the marketplace.
- **Pre-validator unification** — lands as `plugins/pre-validator/` in the same marketplace. Users already have `manch-tooling` added; `/plugin install pre-validator@manch-tooling` is the whole onboarding flow.
- **Log-commit-sync hook** — lands as a `PostToolUse` or `Stop` hook in `plugins/doc-parser/hooks/` once phase 2 needs it.

If this spec is done right, every phase 2+ item is a drop-in, not a migration.

---

## 7. Resolved Items (decisions captured during review)

- **Marketplace name:** `manch-tooling`. Confirmed.
- **Presets file location:** ship with the plugin at `plugins/doc-parser/resources/presets.json` (version-controlled alongside plugin code). No user-overridable variant in scope A.
- **Stage 7 execution model:** hybrid — deterministic Python + session-based mini-agent invocation. The existing CLAUDE.md "deterministic" label understates what Stage 7 actually does. This spec now reflects the correct model throughout (see §2.2, §3.5, §3.6). Phase 2's eval work can trust the STAGE_AGENTS mapping in §3.6.
- Whether to keep a top-level `requirements.txt` at repo root (for discovery) or delete it once plugin's own `requirements.txt` is authoritative. Current design: keep repo-root `requirements.txt` as a one-liner pointing to the plugin.
