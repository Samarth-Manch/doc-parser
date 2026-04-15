# doc-parser Plugin Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the doc-parser repo into a proper Claude plugin distributed via a `manch-tooling` marketplace, with all Python code moved under the plugin's `scripts/lib/`, mini-agent prompts promoted to plugin-native agents, bash pipeline orchestration replaced by Python, and 18 slash commands exposing the pipeline and tool surface — **without changing the pipeline's output**.

**Architecture:** Fat plugin (`plugins/doc-parser/`) containing a pip-installable Python package (`pyproject.toml` + `scripts/lib/`), promoted mini-agents in `agents/` (frontmatter added, Python dispatchers still read and shell out to `claude -p` via a frontmatter-stripping loader), 18 slash commands in `commands/`, static data in `resources/`, and a Python-driven pipeline runner (`scripts/lib/pipeline/run_pipeline.py`) that replaces `bash_scripts/run_pipeline.sh`. Marketplace manifest at repo root declares `manch-tooling` with `doc-parser` as its first plugin, leaving room for phase-2+ siblings (pre-validator, eval-harness, self-learning).

**Tech Stack:** Python 3.10+, `pyproject.toml` setuptools layout, Claude Code plugin manifest format (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`), YAML frontmatter for plugin agents, bash only for legacy baseline capture.

**Reference spec:** `docs/superpowers/specs/2026-04-15-plugin-architecture-design.md` — if anything in this plan contradicts the spec, the spec wins and the plan must be corrected before continuing.

**Branch:** `plugin-architecture` (cut from `chore/archive-dead-code`).

---

## File Structure Map

This section fixes the file layout before any task starts so decomposition decisions are locked in. Every task below references one of these files.

### Files created

- `.claude-plugin/marketplace.json` — repo-root marketplace manifest declaring `manch-tooling`
- `plugins/doc-parser/.claude-plugin/plugin.json` — plugin manifest
- `plugins/doc-parser/pyproject.toml` — makes `scripts/lib/` pip-installable
- `plugins/doc-parser/requirements.txt` — pinned runtime deps
- `plugins/doc-parser/README.md` — install + usage docs
- `plugins/doc-parser/scripts/lib/pipeline/__init__.py` — new package
- `plugins/doc-parser/scripts/lib/pipeline/resources.py` — resource path helper
- `plugins/doc-parser/scripts/lib/pipeline/stages.py` — `STAGE_AGENTS`, `STAGE_OUTPUTS` constants
- `plugins/doc-parser/scripts/lib/pipeline/run_pipeline.py` — Python port of `bash_scripts/run_pipeline.sh`
- `plugins/doc-parser/scripts/lib/dispatchers/_agent_loader.py` — frontmatter stripper
- `plugins/doc-parser/resources/presets.json` — 8 per-BUD presets (replaces 8 shell scripts)
- `plugins/doc-parser/commands/run.md` — aggregate pipeline slash command
- `plugins/doc-parser/commands/extract-fields.md` — Stage 0
- `plugins/doc-parser/commands/place-rules.md` — Stage 1
- `plugins/doc-parser/commands/source-dest.md` — Stage 2
- `plugins/doc-parser/commands/edv.md` — Stage 3
- `plugins/doc-parser/commands/validate-edv.md` — Stage 4
- `plugins/doc-parser/commands/expression.md` — Stage 5
- `plugins/doc-parser/commands/inter-panel.md` — Stage 6
- `plugins/doc-parser/commands/session-based.md` — Stage 7
- `plugins/doc-parser/commands/convert-api.md` — Stage 8
- `plugins/doc-parser/commands/eval-rule-extraction.md` — tool command (folded from `.claude/commands/`)
- `plugins/doc-parser/commands/eval-panel-rules.md` — tool command
- `plugins/doc-parser/commands/compare-form-builders.md` — tool command
- `plugins/doc-parser/commands/rule-info-extractor.md` — tool command
- `plugins/doc-parser/commands/edv-table-mapping.md` — tool command
- `plugins/doc-parser/commands/table-excel-file-map.md` — tool command
- `plugins/doc-parser/commands/inter-panel-refs.md` — tool command
- `plugins/doc-parser/commands/intra-panel-refs.md` — tool command
- `plugins/doc-parser/agents/rule-type-placement.md` — Stage 1 mini-agent (promoted, frontmattered)
- `plugins/doc-parser/agents/source-destination.md` — Stage 2 mini-agent
- `plugins/doc-parser/agents/edv-rule.md` — Stage 3 mini-agent
- `plugins/doc-parser/agents/validate-edv.md` — Stage 4 mini-agent
- `plugins/doc-parser/agents/expression-rule.md` — Stage 5 mini-agent
- `plugins/doc-parser/agents/inter-panel-detect-refs.md` — Stage 6 mini-agent
- `plugins/doc-parser/agents/session-based.md` — Stage 7 mini-agent (Stage 7 is hybrid)
- `plugins/doc-parser/agents/extract-fields-to-json.md` — standalone, preserved for Phase 2
- `plugins/doc-parser/agents/rule-extraction-coding.md` — standalone, preserved for Phase 2

### Files moved (git mv, content only lightly edited for paths)

- `doc_parser/*` → `plugins/doc-parser/scripts/lib/doc_parser/*`
- `field_extractor/*.py` → `plugins/doc-parser/scripts/lib/field_extractor/*.py`
- `rule_extractor/*` → `plugins/doc-parser/scripts/lib/rule_extractor/*`
- `dispatchers/agents/rule_placement_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/rule_placement.py`
- `dispatchers/agents/source_destination_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/source_destination.py`
- `dispatchers/agents/edv_rule_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/edv_rule.py`
- `dispatchers/agents/validate_edv_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/validate_edv.py`
- `dispatchers/agents/expression_rule_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/expression_rule.py`
- `dispatchers/agents/inter_panel_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/inter_panel.py`
- `dispatchers/agents/session_based_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/session_based.py`
- `dispatchers/agents/convert_to_api_format.py` → `plugins/doc-parser/scripts/lib/dispatchers/convert_to_api_format.py`
- `dispatchers/agents/workflow_graph_converter.py` → `plugins/doc-parser/scripts/lib/dispatchers/workflow_graph_converter.py`
- `dispatchers/agents/context_optimization.py` → `plugins/doc-parser/scripts/lib/dispatchers/context_optimization.py`
- `dispatchers/agents/stream_utils.py` → `plugins/doc-parser/scripts/lib/dispatchers/stream_utils.py`
- `dispatchers/agents/inter_panel_utils.py` → `plugins/doc-parser/scripts/lib/dispatchers/inter_panel_utils.py`
- `dispatchers/agents/resolve_edv_varnames.py` → `plugins/doc-parser/scripts/lib/dispatchers/resolve_edv_varnames.py`
- `dispatchers/agents/fix_mandatory_fields.py` → `plugins/doc-parser/scripts/lib/dispatchers/fix_mandatory_fields.py`
- `dispatchers/agents/post_trigger_linker.py` → `plugins/doc-parser/scripts/lib/dispatchers/post_trigger_linker.py`
- `rules/Rule-Schemas.json` → `plugins/doc-parser/resources/rule-schemas.json`
- `rules/rules_buckets.json` → `plugins/doc-parser/resources/rules-buckets.json`
- `rules/RULES_CLASSIFICATION.md` → `plugins/doc-parser/resources/rules-classification.md`
- `rule_extractor/static/keyword_tree.json` → `plugins/doc-parser/resources/keyword-tree.json`
- `.claude/agents/docs/expression_rules.md` → `plugins/doc-parser/resources/expression-rules.md`

### Files modified

- Every dispatcher Python file — imports updated from `from dispatchers.agents.X` to `from dispatchers.X` and prompt-file reads rerouted through `_agent_loader.load_agent_prompt(name)`
- `CLAUDE.md` — rewritten to describe the plugin layout

### Files deleted (final commit only)

- `bash_scripts/run_pipeline.sh`, `bash_scripts/run_stages*.sh` (4 files)
- `run_stages_ph_creation.sh`, `run_stages_ph_creation_workflow.sh`, `run_stages_raw_material_creation.sh`, `run_stages_sunpharma_material.sh` (4 root-level)
- `.claude/agents/mini/` (entire directory)
- `.claude/agents/docs/` (entire directory, after expression-rules.md is moved)
- `.claude/commands/*.md` (after they're folded into plugin commands)
- Old `doc_parser/`, `field_extractor/`, `dispatchers/`, `rule_extractor/`, `rules/` at repo root (after all contents are moved)
- Temporary symlinks added in Task 3

### Files NOT touched (user data)

- `documents/` — user BUDs, input
- `output/` — pipeline outputs
- `self-learning/` — meeting transcripts
- `archive/` — dead-code graveyard
- `bud_issues/`, `issues/` — issue notes

---

## Pre-flight: Baseline Capture (Task 0)

This is a non-negotiable gate. Without a pre-migration baseline, there is no way to verify that any subsequent commit hasn't silently broken the pipeline.

### Task 0: Capture baseline output for all 8 presets

**Files:**
- Create: `/tmp/plugin-migration-baseline/<preset>/` (8 directories, one per preset)
- Read: `bash_scripts/run_pipeline.sh`, all 8 `run_stages_*.sh` files

- [ ] **Step 1: Confirm working tree is clean on `chore/archive-dead-code` and all 8 shell scripts exist**

Run:
```bash
git status
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD
ls bash_scripts/run_pipeline.sh \
   bash_scripts/run_stages.sh \
   bash_scripts/run_stages_unspsc.sh \
   bash_scripts/run_stages_pidilite.sh \
   bash_scripts/run_stages_vendor_extension.sh \
   run_stages_ph_creation.sh \
   run_stages_ph_creation_workflow.sh \
   run_stages_raw_material_creation.sh \
   run_stages_sunpharma_material.sh
```

Expected: working tree clean (or only un-pipeline-related changes), current branch `chore/archive-dead-code`, HEAD commit SHA captured, and all 9 listed shell scripts exist. If any script is missing (e.g., because it was archived), stop and resolve the inconsistency before continuing — this plan assumes the 8-preset pipeline is fully functional at the baseline.

Save the SHA to a local note — you'll need it in Task 1.

- [ ] **Step 2: Create the baseline directory**

Run:
```bash
mkdir -p /tmp/plugin-migration-baseline
```

- [ ] **Step 3: Run each preset end-to-end and snapshot its `output/` tree**

For each of the 8 presets, run the current shell script, then snapshot the produced output directory. Here is the exact mapping (from the existing shell scripts):

```bash
# Preset: vendor-creation
./bash_scripts/run_stages.sh output/vendor
cp -a output/vendor /tmp/plugin-migration-baseline/vendor-creation

# Preset: unspsc
./bash_scripts/run_stages_unspsc.sh output/unspsc
cp -a output/unspsc /tmp/plugin-migration-baseline/unspsc

# Preset: pidilite
./bash_scripts/run_stages_pidilite.sh output/block_unblock
cp -a output/block_unblock /tmp/plugin-migration-baseline/pidilite

# Preset: vendor-extension
./bash_scripts/run_stages_vendor_extension.sh output/vendor_extension
cp -a output/vendor_extension /tmp/plugin-migration-baseline/vendor-extension

# Preset: ph-creation
./run_stages_ph_creation.sh output/ph
cp -a output/ph /tmp/plugin-migration-baseline/ph-creation

# Preset: ph-creation-workflow
./run_stages_ph_creation_workflow.sh output/ph
cp -a output/ph /tmp/plugin-migration-baseline/ph-creation-workflow

# Preset: raw-material-creation
./run_stages_raw_material_creation.sh output/raw_material_creation
cp -a output/raw_material_creation /tmp/plugin-migration-baseline/raw-material-creation

# Preset: sunpharma
./run_stages_sunpharma_material.sh output/sunpharma
cp -a output/sunpharma /tmp/plugin-migration-baseline/sunpharma
```

If a preset has already been run and its `output/...` tree is fresh, `cp -a` alone is sufficient — rerunning is only required if the output doesn't exist or has been deleted.

- [ ] **Step 4: Verify all 8 baselines captured**

Run:
```bash
ls /tmp/plugin-migration-baseline/
```

Expected: 8 directories listed — `vendor-creation`, `unspsc`, `pidilite`, `vendor-extension`, `ph-creation`, `ph-creation-workflow`, `raw-material-creation`, `sunpharma`. Each directory must contain the full per-stage output tree (check one: `ls /tmp/plugin-migration-baseline/vendor-creation/`).

- [ ] **Step 5: Record the baseline commit SHA in a note file**

Run:
```bash
git rev-parse HEAD > /tmp/plugin-migration-baseline/BASELINE_COMMIT_SHA.txt
cat /tmp/plugin-migration-baseline/BASELINE_COMMIT_SHA.txt
```

Expected: one 40-character SHA printed. This is the commit every subsequent commit is implicitly diffed against.

- [ ] **Step 6: DO NOT commit anything**

Task 0 is baseline-only. There is nothing to commit yet because the branch doesn't exist. Move to Task 1.

---

## Task 1: Create `plugin-architecture` branch and plugin skeleton

**Files:**
- Create: `.claude-plugin/marketplace.json`
- Create: `plugins/doc-parser/.claude-plugin/plugin.json`
- Create: `plugins/doc-parser/README.md`
- Create: `plugins/doc-parser/pyproject.toml`
- Create: `plugins/doc-parser/requirements.txt`
- Create: `plugins/doc-parser/{agents,commands,hooks,scripts/lib,scripts/pipeline,resources}/.gitkeep`

- [ ] **Step 1: Cut the branch**

Run:
```bash
git checkout chore/archive-dead-code
git pull --ff-only
git checkout -b plugin-architecture
```

Expected: on branch `plugin-architecture`, working tree clean.

- [ ] **Step 2: Create `.claude-plugin/marketplace.json`**

File: `.claude-plugin/marketplace.json`

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

- [ ] **Step 3: Create `plugins/doc-parser/.claude-plugin/plugin.json`**

File: `plugins/doc-parser/.claude-plugin/plugin.json`

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

- [ ] **Step 4: Create `plugins/doc-parser/pyproject.toml`**

File: `plugins/doc-parser/pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "doc-parser-pipeline"
version = "0.1.0"
description = "BUD parsing and rule extraction pipeline for the Manch platform."
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

- [ ] **Step 5: Create `plugins/doc-parser/requirements.txt`** (mirror of `[project].dependencies`)

File: `plugins/doc-parser/requirements.txt`

```
python-docx
lxml
openai
anthropic
requests
python-dotenv
```

- [ ] **Step 6: Create `plugins/doc-parser/README.md`** (stub — filled in by Task 14)

File: `plugins/doc-parser/README.md`

```markdown
# doc-parser plugin

Parses BUDs (Business Understanding Documents) and extracts structured form-fill rules for the Manch platform.

## Install

```bash
# Add marketplace (once per machine)
/plugin marketplace add <git-url-to-this-repo>

# Install plugin
/plugin install doc-parser@manch-tooling

# Install Python deps (one-time, from repo root)
pip install -e plugins/doc-parser/
```

## Usage

See CLAUDE.md at the repo root for the full command reference. Quick start:

```
/doc-parser:run --preset vendor-creation
```
```

- [ ] **Step 7: Create empty subdirectories with `.gitkeep` files**

Run:
```bash
mkdir -p plugins/doc-parser/agents
mkdir -p plugins/doc-parser/commands
mkdir -p plugins/doc-parser/hooks
mkdir -p plugins/doc-parser/scripts/lib
mkdir -p plugins/doc-parser/scripts/pipeline
mkdir -p plugins/doc-parser/resources
touch plugins/doc-parser/agents/.gitkeep
touch plugins/doc-parser/commands/.gitkeep
touch plugins/doc-parser/hooks/.gitkeep
touch plugins/doc-parser/scripts/lib/.gitkeep
touch plugins/doc-parser/scripts/pipeline/.gitkeep
touch plugins/doc-parser/resources/.gitkeep
```

- [ ] **Step 8: Verify the old pipeline still runs after skeleton creation**

Run:
```bash
./bash_scripts/run_stages.sh /tmp/skeleton-check-vendor
diff -r /tmp/plugin-migration-baseline/vendor-creation /tmp/skeleton-check-vendor
```

Expected: output tree exists at `/tmp/skeleton-check-vendor`, diff shows only non-deterministic differences (timestamps, LLM variance — expected to be small and semantic-only).

- [ ] **Step 9: Commit**

Run:
```bash
git add .claude-plugin plugins/
git commit -m "Scaffold doc-parser plugin skeleton

Create .claude-plugin/marketplace.json (manch-tooling marketplace)
and plugins/doc-parser/ with .claude-plugin/plugin.json, pyproject.toml,
requirements.txt, README.md stub, and empty agents/, commands/, hooks/,
scripts/lib/, scripts/pipeline/, resources/ directories.

Old pipeline at bash_scripts/run_pipeline.sh still runs unchanged.

Part 1/14 of plugin architecture migration.
Ref: docs/superpowers/specs/2026-04-15-plugin-architecture-design.md"
```

---

## Task 2: Move static resources into `plugins/doc-parser/resources/`

**Files:**
- Move: `rules/Rule-Schemas.json` → `plugins/doc-parser/resources/rule-schemas.json`
- Move: `rules/rules_buckets.json` → `plugins/doc-parser/resources/rules-buckets.json`
- Move: `rules/RULES_CLASSIFICATION.md` → `plugins/doc-parser/resources/rules-classification.md`
- Move: `rule_extractor/static/keyword_tree.json` → `plugins/doc-parser/resources/keyword-tree.json`
- Move: `.claude/agents/docs/expression_rules.md` → `plugins/doc-parser/resources/expression-rules.md`

Not moved (dropped in Task 13): `.claude/agents/helpers/expression_pattern_analyzer.md` — not needed per user direction.

- [ ] **Step 1: Move each resource file via `git mv`**

Run:
```bash
git mv rules/Rule-Schemas.json plugins/doc-parser/resources/rule-schemas.json
git mv rules/rules_buckets.json plugins/doc-parser/resources/rules-buckets.json
git mv rules/RULES_CLASSIFICATION.md plugins/doc-parser/resources/rules-classification.md
git mv rule_extractor/static/keyword_tree.json plugins/doc-parser/resources/keyword-tree.json
git mv .claude/agents/docs/expression_rules.md plugins/doc-parser/resources/expression-rules.md
```

Note: `rules/Expression Eval Custom Functions-2.pdf`, `rules/RULES_CLASSIFICATION.html`, and `rules/expression_rules_example/` are not moved — they are reference PDFs/examples, not pipeline data. They will be deleted in Task 13.

- [ ] **Step 2: Add backward-compatibility symlinks at old paths**

So the old pipeline still runs against old hardcoded paths until Task 6 routes everything through the helper:

```bash
ln -s ../plugins/doc-parser/resources/rule-schemas.json rules/Rule-Schemas.json
ln -s ../plugins/doc-parser/resources/rules-buckets.json rules/rules_buckets.json
ln -s ../plugins/doc-parser/resources/rules-classification.md rules/RULES_CLASSIFICATION.md
ln -s ../../plugins/doc-parser/resources/keyword-tree.json rule_extractor/static/keyword_tree.json
ln -s ../../../plugins/doc-parser/resources/expression-rules.md .claude/agents/docs/expression_rules.md
```

These are temporary — removed in Task 13.

- [ ] **Step 3: Verify old pipeline still runs end-to-end**

Run one preset and diff against baseline:
```bash
./bash_scripts/run_stages.sh /tmp/task2-check-vendor
diff -r /tmp/plugin-migration-baseline/vendor-creation /tmp/task2-check-vendor | head -20
```

Expected: only semantic/non-deterministic differences.

- [ ] **Step 4: Commit**

```bash
git add plugins/doc-parser/resources rules .claude/agents/docs rule_extractor/static
git commit -m "Move static pipeline resources into plugin

Relocate Rule-Schemas.json, rules_buckets.json, RULES_CLASSIFICATION.md,
keyword_tree.json, and expression_rules.md into plugins/doc-parser/resources/
(renamed to kebab-case). Temporary symlinks at old paths keep the existing
pipeline runnable; removed in Task 13.

Part 2/14 of plugin architecture migration."
```

---

## Task 3: Create `pipeline/resources.py` helper and `_agent_loader.py`

**Files:**
- Create: `plugins/doc-parser/scripts/lib/pipeline/__init__.py` (empty)
- Create: `plugins/doc-parser/scripts/lib/pipeline/resources.py`
- Create: `plugins/doc-parser/scripts/lib/dispatchers/__init__.py` (empty)
- Create: `plugins/doc-parser/scripts/lib/dispatchers/_agent_loader.py`
- Delete: `plugins/doc-parser/scripts/lib/.gitkeep` (now superseded)
- Delete: `plugins/doc-parser/scripts/pipeline/.gitkeep` (replaced — note the scripts/pipeline/ skeleton directory from Task 1 is now unused; `pipeline` lives under `scripts/lib/pipeline`. Remove the unused empty dir.)

- [ ] **Step 1: Remove the unused `scripts/pipeline/` skeleton dir from Task 1**

The Task 1 skeleton created both `scripts/lib/` (correct) and `scripts/pipeline/` (misplaced). The `pipeline` package belongs under `scripts/lib/pipeline/`. Remove the misplaced dir:

```bash
git rm plugins/doc-parser/scripts/pipeline/.gitkeep
rmdir plugins/doc-parser/scripts/pipeline 2>/dev/null || true
git rm plugins/doc-parser/scripts/lib/.gitkeep
```

- [ ] **Step 2: Create `scripts/lib/pipeline/__init__.py`**

File: `plugins/doc-parser/scripts/lib/pipeline/__init__.py` (empty file)

```bash
mkdir -p plugins/doc-parser/scripts/lib/pipeline
touch plugins/doc-parser/scripts/lib/pipeline/__init__.py
```

- [ ] **Step 3: Create `scripts/lib/pipeline/resources.py`**

File: `plugins/doc-parser/scripts/lib/pipeline/resources.py`

```python
"""Plugin resource path discovery.

Resolves the plugin's install location at runtime and provides an
absolute path to any file under plugins/doc-parser/resources/.

Works whether the plugin is installed inside the repo (during
development) or under ~/.claude/plugins/<marketplace>/<plugin>/
(production install via /plugin install).
"""

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
RESOURCES = PLUGIN_ROOT / "resources"


def resource_path(name: str) -> Path:
    """Return an absolute path to a plugin resource file.

    Raises FileNotFoundError if the resource doesn't exist, so callers
    fail fast during the restructure rather than passing a nonexistent
    path to downstream code.
    """
    p = RESOURCES / name
    if not p.exists():
        raise FileNotFoundError(f"Plugin resource not found: {p}")
    return p
```

- [ ] **Step 4: Create `scripts/lib/dispatchers/__init__.py`**

```bash
mkdir -p plugins/doc-parser/scripts/lib/dispatchers
touch plugins/doc-parser/scripts/lib/dispatchers/__init__.py
```

- [ ] **Step 5: Create `scripts/lib/dispatchers/_agent_loader.py`**

File: `plugins/doc-parser/scripts/lib/dispatchers/_agent_loader.py`

```python
"""Frontmatter-stripping prompt loader for plugin agents.

Plugin agents under plugins/doc-parser/agents/ have YAML frontmatter
(name, description, model). Python dispatchers that shell out to
`claude -p <prompt>` need the prompt body only. This module reads an
agent file, strips frontmatter if present, and returns the body.
"""

from pathlib import Path
from pipeline.resources import PLUGIN_ROOT

AGENTS_DIR = PLUGIN_ROOT / "agents"


def load_agent_prompt(agent_name: str) -> str:
    """Load the prompt body for a plugin agent by name (without extension).

    Strips YAML frontmatter delimited by `---` if present. Returns the
    body unchanged if the file has no frontmatter.
    """
    path = AGENTS_DIR / f"{agent_name}.md"
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip()
    return text
```

- [ ] **Step 6: Verify the helper modules are importable** (without fully installing the package yet — we use `PYTHONPATH`)

Run:
```bash
PYTHONPATH=plugins/doc-parser/scripts/lib python3 -c "
from pipeline.resources import resource_path, PLUGIN_ROOT
print('PLUGIN_ROOT:', PLUGIN_ROOT)
print('rule-schemas.json:', resource_path('rule-schemas.json'))
"
```

Expected output:
```
PLUGIN_ROOT: /home/samart/project/doc-parser/plugins/doc-parser
rule-schemas.json: /home/samart/project/doc-parser/plugins/doc-parser/resources/rule-schemas.json
```

- [ ] **Step 7: Commit**

```bash
git add plugins/doc-parser/scripts
git commit -m "Add pipeline.resources helper and dispatcher agent loader

- scripts/lib/pipeline/resources.py: resource_path() helper that
  resolves PLUGIN_ROOT at runtime via __file__. Used everywhere to
  replace hardcoded 'rules/...' and 'rule_extractor/static/...' paths.
- scripts/lib/dispatchers/_agent_loader.py: load_agent_prompt() reads
  a plugin agent file and strips YAML frontmatter, returning the
  prompt body for existing 'claude -p' shell-out dispatchers.

No existing code calls either yet. Part 3/14 of plugin migration."
```

---

## Task 4: Move `doc_parser/` package

**Files:**
- Move: `doc_parser/*.py` → `plugins/doc-parser/scripts/lib/doc_parser/`

- [ ] **Step 1: Move the package**

Run:
```bash
mkdir -p plugins/doc-parser/scripts/lib/doc_parser
git mv doc_parser/__init__.py plugins/doc-parser/scripts/lib/doc_parser/__init__.py
git mv doc_parser/parser.py plugins/doc-parser/scripts/lib/doc_parser/parser.py
git mv doc_parser/models.py plugins/doc-parser/scripts/lib/doc_parser/models.py
git mv doc_parser/recreator.py plugins/doc-parser/scripts/lib/doc_parser/recreator.py
git mv doc_parser/recreator_exact.py plugins/doc-parser/scripts/lib/doc_parser/recreator_exact.py
git mv doc_parser/comprehensive_recreator.py plugins/doc-parser/scripts/lib/doc_parser/comprehensive_recreator.py
rm -rf doc_parser/__pycache__
rmdir doc_parser
```

- [ ] **Step 2: Install the plugin package in editable mode**

Run:
```bash
pip install -e plugins/doc-parser/
```

Expected: `Successfully installed doc-parser-pipeline-0.1.0`. This registers `doc_parser` (and later `field_extractor`, `dispatchers`, `rule_extractor`, `pipeline`) as importable from anywhere on this machine.

- [ ] **Step 3: Verify the import works from `/tmp`**

Run:
```bash
cd /tmp && python3 -c "from doc_parser import DocumentParser; print(DocumentParser().__class__.__name__)"
cd -
```

Expected output: `DocumentParser`.

- [ ] **Step 4: Verify old pipeline still runs**

Run:
```bash
./bash_scripts/run_stages.sh /tmp/task4-check-vendor
ls /tmp/task4-check-vendor/ | head
```

Expected: stage output tree exists. This works because `doc_parser` is now importable via the installed package even though the physical files moved.

- [ ] **Step 5: Commit**

```bash
git add plugins/doc-parser/scripts/lib/doc_parser
git commit -m "Move doc_parser package under plugin scripts/lib/

The DocumentParser and models (ParsedDocument, FieldDefinition,
WorkflowStep, TableData, Section, ApprovalRule) now live under
plugins/doc-parser/scripts/lib/doc_parser/. The package is discoverable
via 'pip install -e plugins/doc-parser/' which was run against the
pyproject.toml added in Task 1.

Existing 'from doc_parser import ...' imports resolve unchanged.

Part 4/14 of plugin architecture migration."
```

---

## Task 5: Move `field_extractor/` package

**Files:**
- Move: `field_extractor/*.py` → `plugins/doc-parser/scripts/lib/field_extractor/`

- [ ] **Step 1: Move the package**

Run:
```bash
mkdir -p plugins/doc-parser/scripts/lib/field_extractor
# Note: field_extractor has no __init__.py today; create one.
touch plugins/doc-parser/scripts/lib/field_extractor/__init__.py
git add plugins/doc-parser/scripts/lib/field_extractor/__init__.py
git mv field_extractor/extract_field_rules.py plugins/doc-parser/scripts/lib/field_extractor/extract_field_rules.py
git mv field_extractor/extract_fields_complete.py plugins/doc-parser/scripts/lib/field_extractor/extract_fields_complete.py
git mv field_extractor/extract_fields_schema_format.py plugins/doc-parser/scripts/lib/field_extractor/extract_fields_schema_format.py
git mv field_extractor/extract_fields_simple.py plugins/doc-parser/scripts/lib/field_extractor/extract_fields_simple.py
rm -rf field_extractor/__pycache__
rmdir field_extractor
```

- [ ] **Step 2: Re-install the editable package to pick up the new subpackage**

Run:
```bash
pip install -e plugins/doc-parser/
```

- [ ] **Step 3: Verify the import works from `/tmp`**

Run:
```bash
cd /tmp && python3 -c "from field_extractor.extract_fields_complete import extract_fields_complete; print('ok')"
cd -
```

Expected output: `ok`.

- [ ] **Step 4: Verify Stage 0 still runs end-to-end** (vendor-creation preset)

```bash
./bash_scripts/run_stages.sh /tmp/task5-check-vendor
```

Expected: stage output tree produced; Stage 0 is the only stage that imports `field_extractor` directly.

- [ ] **Step 5: Commit**

```bash
git add plugins/doc-parser/scripts/lib/field_extractor
git commit -m "Move field_extractor package under plugin scripts/lib/

Four extractors (extract_field_rules, extract_fields_complete,
extract_fields_schema_format, extract_fields_simple) moved to
plugins/doc-parser/scripts/lib/field_extractor/. Added __init__.py
(the old location didn't have one).

Existing 'from field_extractor.extract_fields_complete import ...'
imports resolve via the editable install.

Part 5/14 of plugin architecture migration."
```

---

## Task 6: Move `rule_extractor/` package and drop keyword-tree symlink

**Files:**
- Move: `rule_extractor/*` → `plugins/doc-parser/scripts/lib/rule_extractor/`
- Delete: `rule_extractor/static/keyword_tree.json` symlink (created in Task 2)

- [ ] **Step 1: List `rule_extractor/` contents**

Run:
```bash
find rule_extractor -type f -not -path "*/__pycache__/*"
```

- [ ] **Step 2: Move the package**

Run:
```bash
mkdir -p plugins/doc-parser/scripts/lib/rule_extractor
# Move every Python file found in Step 1 preserving structure.
# Example (adjust based on step 1 output):
git mv rule_extractor/__init__.py plugins/doc-parser/scripts/lib/rule_extractor/__init__.py 2>/dev/null || true
# Move any other .py files found in step 1 (this task section cannot
# hardcode the list because the existing rule_extractor structure
# may include more files than listed here — use Step 1's output).
```

If `rule_extractor/` contains additional Python files not caught above, `git mv` each one into `plugins/doc-parser/scripts/lib/rule_extractor/` preserving the subpath.

- [ ] **Step 3: Drop the keyword-tree symlink, remove old static dir**

Run:
```bash
rm rule_extractor/static/keyword_tree.json  # this is the symlink from Task 2
rmdir rule_extractor/static 2>/dev/null || true
rm -rf rule_extractor/__pycache__ 2>/dev/null || true
rmdir rule_extractor 2>/dev/null || true
```

- [ ] **Step 4: Update any dispatcher that hardcodes `rule_extractor/static/keyword_tree.json`**

Run:
```bash
grep -rn "rule_extractor/static/keyword_tree.json" plugins/doc-parser/scripts/lib/ bash_scripts/ *.sh 2>/dev/null
```

For each hit, leave bash_scripts alone (they'll be deleted later) but update any Python file to use `resource_path("keyword-tree.json")`. Typically the Python callers receive the keyword-tree path via a `--keyword-tree` CLI flag, so no Python change is needed — the shell script provides the path. Verify by grepping Python files:

```bash
grep -rn "keyword_tree" plugins/doc-parser/scripts/lib/
```

If a Python file hardcodes the path, replace the hardcoded string with:
```python
from pipeline.resources import resource_path
DEFAULT_KEYWORD_TREE = resource_path("keyword-tree.json")
```

- [ ] **Step 5: Re-install the editable package**

```bash
pip install -e plugins/doc-parser/
```

- [ ] **Step 6: Verify import from `/tmp`**

```bash
cd /tmp && python3 -c "import rule_extractor; print('ok')"
cd -
```

Expected: `ok`.

- [ ] **Step 7: Verify Stages 0 and 1 still run end-to-end**

```bash
./bash_scripts/run_stages.sh /tmp/task6-check-vendor
ls /tmp/task6-check-vendor/rule_placement/all_panels_rules.json
```

Expected: file exists.

- [ ] **Step 8: Commit**

```bash
git add plugins/doc-parser/scripts/lib/rule_extractor rule_extractor
git commit -m "Move rule_extractor package under plugin scripts/lib/

Package moved to plugins/doc-parser/scripts/lib/rule_extractor/.
keyword_tree.json already lives in plugins/doc-parser/resources/
(moved in Task 2); the symlink at rule_extractor/static/ is removed.

Part 6/14 of plugin architecture migration."
```

---

## Task 7: Move and rename `dispatchers/agents/*.py` → `dispatchers/*.py`

**Files:**
- Move (and rename): `dispatchers/agents/rule_placement_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/rule_placement.py`
- Move (and rename): `dispatchers/agents/source_destination_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/source_destination.py`
- Move (and rename): `dispatchers/agents/edv_rule_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/edv_rule.py`
- Move (and rename): `dispatchers/agents/validate_edv_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/validate_edv.py`
- Move (and rename): `dispatchers/agents/expression_rule_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/expression_rule.py`
- Move (and rename): `dispatchers/agents/inter_panel_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/inter_panel.py`
- Move (and rename): `dispatchers/agents/session_based_dispatcher.py` → `plugins/doc-parser/scripts/lib/dispatchers/session_based.py`
- Move: `dispatchers/agents/convert_to_api_format.py` → `plugins/doc-parser/scripts/lib/dispatchers/convert_to_api_format.py`
- Move: `dispatchers/agents/workflow_graph_converter.py` → `plugins/doc-parser/scripts/lib/dispatchers/workflow_graph_converter.py`
- Move: `dispatchers/agents/context_optimization.py` → `plugins/doc-parser/scripts/lib/dispatchers/context_optimization.py`
- Move: `dispatchers/agents/stream_utils.py` → `plugins/doc-parser/scripts/lib/dispatchers/stream_utils.py`
- Move: `dispatchers/agents/inter_panel_utils.py` → `plugins/doc-parser/scripts/lib/dispatchers/inter_panel_utils.py`
- Move: `dispatchers/agents/resolve_edv_varnames.py` → `plugins/doc-parser/scripts/lib/dispatchers/resolve_edv_varnames.py`
- Move: `dispatchers/agents/fix_mandatory_fields.py` → `plugins/doc-parser/scripts/lib/dispatchers/fix_mandatory_fields.py`
- Move: `dispatchers/agents/post_trigger_linker.py` → `plugins/doc-parser/scripts/lib/dispatchers/post_trigger_linker.py`
- Modify: every moved file's intra-dispatcher imports (e.g., `from dispatchers.agents.context_optimization` → `from dispatchers.context_optimization`)

- [ ] **Step 1: Move all dispatcher files with `git mv`** (one command per file, renaming the 7 stage dispatchers that carry `_dispatcher.py` suffix)

Run:
```bash
git mv dispatchers/agents/rule_placement_dispatcher.py plugins/doc-parser/scripts/lib/dispatchers/rule_placement.py
git mv dispatchers/agents/source_destination_dispatcher.py plugins/doc-parser/scripts/lib/dispatchers/source_destination.py
git mv dispatchers/agents/edv_rule_dispatcher.py plugins/doc-parser/scripts/lib/dispatchers/edv_rule.py
git mv dispatchers/agents/validate_edv_dispatcher.py plugins/doc-parser/scripts/lib/dispatchers/validate_edv.py
git mv dispatchers/agents/expression_rule_dispatcher.py plugins/doc-parser/scripts/lib/dispatchers/expression_rule.py
git mv dispatchers/agents/inter_panel_dispatcher.py plugins/doc-parser/scripts/lib/dispatchers/inter_panel.py
git mv dispatchers/agents/session_based_dispatcher.py plugins/doc-parser/scripts/lib/dispatchers/session_based.py
git mv dispatchers/agents/convert_to_api_format.py plugins/doc-parser/scripts/lib/dispatchers/convert_to_api_format.py
git mv dispatchers/agents/workflow_graph_converter.py plugins/doc-parser/scripts/lib/dispatchers/workflow_graph_converter.py
git mv dispatchers/agents/context_optimization.py plugins/doc-parser/scripts/lib/dispatchers/context_optimization.py
git mv dispatchers/agents/stream_utils.py plugins/doc-parser/scripts/lib/dispatchers/stream_utils.py
git mv dispatchers/agents/inter_panel_utils.py plugins/doc-parser/scripts/lib/dispatchers/inter_panel_utils.py
git mv dispatchers/agents/resolve_edv_varnames.py plugins/doc-parser/scripts/lib/dispatchers/resolve_edv_varnames.py
git mv dispatchers/agents/fix_mandatory_fields.py plugins/doc-parser/scripts/lib/dispatchers/fix_mandatory_fields.py
git mv dispatchers/agents/post_trigger_linker.py plugins/doc-parser/scripts/lib/dispatchers/post_trigger_linker.py
# __init__.py was created fresh in Task 3, so skip the old one:
rm -f dispatchers/agents/__init__.py dispatchers/__init__.py
rm -rf dispatchers/agents/__pycache__ dispatchers/__pycache__ 2>/dev/null || true
rmdir dispatchers/agents dispatchers 2>/dev/null || true
```

- [ ] **Step 2: Fix intra-dispatcher imports**

Inside every moved file, replace `from dispatchers.agents.` with `from dispatchers.`. Use a targeted edit. Grep first:

```bash
grep -rn "from dispatchers.agents" plugins/doc-parser/scripts/lib/dispatchers/
grep -rn "import dispatchers.agents" plugins/doc-parser/scripts/lib/dispatchers/
```

For each hit, edit the file to change `dispatchers.agents.X` → `dispatchers.X`. If a dispatcher imports another dispatcher by its old suffixed name, update that too:
- `from dispatchers.agents.context_optimization` → `from dispatchers.context_optimization`
- `from dispatchers.agents.stream_utils` → `from dispatchers.stream_utils`
- `from dispatchers.agents.inter_panel_utils` → `from dispatchers.inter_panel_utils`
- `from dispatchers.agents.rule_placement_dispatcher` → `from dispatchers.rule_placement`
- `from dispatchers.agents.source_destination_dispatcher` → `from dispatchers.source_destination`
- `from dispatchers.agents.edv_rule_dispatcher` → `from dispatchers.edv_rule`
- `from dispatchers.agents.validate_edv_dispatcher` → `from dispatchers.validate_edv`
- `from dispatchers.agents.expression_rule_dispatcher` → `from dispatchers.expression_rule`
- `from dispatchers.agents.inter_panel_dispatcher` → `from dispatchers.inter_panel`
- `from dispatchers.agents.session_based_dispatcher` → `from dispatchers.session_based`
- `from dispatchers.agents.resolve_edv_varnames` → `from dispatchers.resolve_edv_varnames`
- `from dispatchers.agents.fix_mandatory_fields` → `from dispatchers.fix_mandatory_fields`
- `from dispatchers.agents.post_trigger_linker` → `from dispatchers.post_trigger_linker`
- `from dispatchers.agents.convert_to_api_format` → `from dispatchers.convert_to_api_format`
- `from dispatchers.agents.workflow_graph_converter` → `from dispatchers.workflow_graph_converter`

Re-grep after edits to confirm zero hits:
```bash
grep -rn "dispatchers.agents" plugins/doc-parser/scripts/lib/dispatchers/
```

Expected: no output.

- [ ] **Step 3: Re-install the editable package**

```bash
pip install -e plugins/doc-parser/
```

- [ ] **Step 4: Verify each dispatcher is importable standalone from `/tmp`**

```bash
cd /tmp && python3 -c "
import dispatchers.rule_placement
import dispatchers.source_destination
import dispatchers.edv_rule
import dispatchers.validate_edv
import dispatchers.expression_rule
import dispatchers.inter_panel
import dispatchers.session_based
import dispatchers.convert_to_api_format
import dispatchers.workflow_graph_converter
print('all dispatcher imports ok')
"
cd -
```

Expected output: `all dispatcher imports ok`.

- [ ] **Step 5: Update `bash_scripts/run_pipeline.sh` to point `DISPATCHERS` at the new location**

The existing shell script uses `$DISPATCHERS` for dispatcher paths. It currently resolves to `dispatchers/agents`. Update it so old bash still works:

```bash
grep -n "DISPATCHERS=" bash_scripts/run_pipeline.sh
```

Replace the `DISPATCHERS=` line with:
```bash
DISPATCHERS="plugins/doc-parser/scripts/lib/dispatchers"
```

Also update the filenames referenced in bash (they lost their `_dispatcher.py` suffix):
```bash
sed -i \
    -e 's|rule_placement_dispatcher\.py|rule_placement.py|g' \
    -e 's|source_destination_dispatcher\.py|source_destination.py|g' \
    -e 's|edv_rule_dispatcher\.py|edv_rule.py|g' \
    -e 's|validate_edv_dispatcher\.py|validate_edv.py|g' \
    -e 's|expression_rule_dispatcher\.py|expression_rule.py|g' \
    -e 's|inter_panel_dispatcher\.py|inter_panel.py|g' \
    -e 's|session_based_dispatcher\.py|session_based.py|g' \
    bash_scripts/run_pipeline.sh
```

Verify by grepping:
```bash
grep -n "_dispatcher.py" bash_scripts/run_pipeline.sh
```

Expected: no output.

- [ ] **Step 6: Verify old bash pipeline still runs**

```bash
./bash_scripts/run_stages.sh /tmp/task7-check-vendor
ls /tmp/task7-check-vendor/convert_to_api_format/ 2>/dev/null || \
    ls /tmp/task7-check-vendor/ | tail
```

Expected: full stage output tree.

- [ ] **Step 7: Commit**

```bash
git add plugins/doc-parser/scripts/lib/dispatchers dispatchers bash_scripts/run_pipeline.sh
git commit -m "Move dispatchers under plugin scripts/lib/, flatten to dispatchers/

Move dispatchers/agents/*.py to plugins/doc-parser/scripts/lib/dispatchers/
and drop the redundant /agents/ subdirectory. Rename the 7 stage
dispatchers to drop the '_dispatcher' suffix (rule_placement_dispatcher.py
→ rule_placement.py etc).

Update intra-dispatcher imports: 'from dispatchers.agents.X' → 'from dispatchers.X'.
Update bash_scripts/run_pipeline.sh to reference the new paths and filenames
so the old pipeline continues to work during migration.

Part 7/14 of plugin architecture migration."
```

---

## Task 8: Promote mini-agents to plugin agents

**Files:**
- Move + rename: 7 files from `.claude/agents/mini/` → `plugins/doc-parser/agents/`
- Move + rename: 2 standalone files from `.claude/agents/` → `plugins/doc-parser/agents/`
- Modify: each dispatcher that reads a mini-agent file, rerouting through `_agent_loader.load_agent_prompt()`

- [ ] **Step 1: Move and rename the 7 mini-agent files**

Run:
```bash
git mv .claude/agents/mini/01_rule_type_placement_agent_v2.md plugins/doc-parser/agents/rule-type-placement.md
git mv .claude/agents/mini/02_source_destination_agent_v2.md plugins/doc-parser/agents/source-destination.md
git mv .claude/agents/mini/03_edv_rule_agent_v2.md plugins/doc-parser/agents/edv-rule.md
git mv .claude/agents/mini/04_validate_edv_agent_v2.md plugins/doc-parser/agents/validate-edv.md
git mv .claude/agents/mini/expression_rule_agent.md plugins/doc-parser/agents/expression-rule.md
git mv .claude/agents/mini/inter_panel_detect_refs.md plugins/doc-parser/agents/inter-panel-detect-refs.md
git mv .claude/agents/mini/08_session_based_agent.md plugins/doc-parser/agents/session-based.md
rmdir .claude/agents/mini 2>/dev/null || true
```

- [ ] **Step 2: Move the 2 standalone agents**

```bash
git mv .claude/agents/extract-fields-to-json.md plugins/doc-parser/agents/extract-fields-to-json.md
git mv .claude/agents/rule_extraction_coding_agent.md plugins/doc-parser/agents/rule-extraction-coding.md
```

- [ ] **Step 3: Add YAML frontmatter to each of the 7 pipeline agents**

For each of the 7 agents, prepend a frontmatter block before the existing content. Use the Edit tool (not sed, so you can verify each file individually). Template:

```yaml
---
name: <agent-name>
description: <one-sentence action-oriented description — see table below>
model: opus
---
```

Agent-specific descriptions:

| File | `name` | `description` |
|---|---|---|
| `rule-type-placement.md` | `rule-type-placement` | Determines which rules from the rule catalog apply to each field in a BUD panel. Reads panel fields + rule schemas, returns a per-field rule-name list. Used by Stage 1. |
| `source-destination.md` | `source-destination` | Maps source and destination fields for each rule placed on a panel. Uses rule schemas + panel field context to assign input and output fields. Used by Stage 2. |
| `edv-rule.md` | `edv-rule` | Populates External Data Value (EDV) dropdown parameters — ddType, criterias, da, cascading table references — based on field logic and reference tables. Used by Stage 3. |
| `validate-edv.md` | `validate-edv` | Places Validate EDV rules on dropdown fields and populates their params with positional column-to-field mapping. Used by Stage 4. |
| `expression-rule.md` | `expression-rule` | Authors Manch expression-engine strings (ctfd, asdff, cf, rffdd) for all expression-shaped field logic — visibility, derivation, clearing, session-based triggers. Used by Stage 5 and Stage 6 Pass 2. |
| `inter-panel-detect-refs.md` | `inter-panel-detect-refs` | Detects cross-panel field references in field logic and classifies each one as Copy To, visibility, or complex. Used by Stage 6 Pass 1. |
| `session-based.md` | `session-based` | Handles session-based visibility and state rules that depend on field logic within a panel. Determines rule placement and source/destination. Used by Stage 7 (hybrid deterministic + agent stage). |

For the 2 standalone agents:

| File | `name` | `description` |
|---|---|---|
| `extract-fields-to-json.md` | `extract-fields-to-json` | Standalone agent that extracts fields from a BUD document into the Manch schema JSON format. Not invoked by the pipeline — available for ad-hoc use via the Task tool. |
| `rule-extraction-coding.md` | `rule-extraction-coding` | Standalone coding agent for implementing rule-extraction features. Not invoked by the pipeline — preserved for Phase 2 coding assistance. |

- [ ] **Step 4: Verify frontmatter is parseable for every agent**

```bash
for f in plugins/doc-parser/agents/*.md; do
    head -6 "$f" | head -1 | grep -q '^---$' && echo "OK $f" || echo "FAIL $f"
done
```

Expected: all files report `OK`.

- [ ] **Step 5: Find all prompt-file read sites in dispatchers**

```bash
grep -rn "mini/\|agents/mini\|\.read_text\|open.*\.md" plugins/doc-parser/scripts/lib/dispatchers/
```

For each hit that reads a mini-agent file by path, refactor to call `load_agent_prompt("<agent-name>")` from `dispatchers._agent_loader`. Example change:

Before:
```python
prompt_file = Path(__file__).parent.parent.parent / ".claude/agents/mini/01_rule_type_placement_agent_v2.md"
prompt_template = prompt_file.read_text()
```

After:
```python
from dispatchers._agent_loader import load_agent_prompt
prompt_template = load_agent_prompt("rule-type-placement")
```

Do this for every dispatcher that currently reads a mini-agent file. The mapping from dispatcher to agent name is:

| Dispatcher file | Agent name to load |
|---|---|
| `rule_placement.py` | `rule-type-placement` |
| `source_destination.py` | `source-destination` |
| `edv_rule.py` | `edv-rule` |
| `validate_edv.py` | `validate-edv` |
| `expression_rule.py` | `expression-rule` |
| `inter_panel.py` | `inter-panel-detect-refs` (Pass 1), `expression-rule` (Pass 2) |
| `session_based.py` | `session-based` |

- [ ] **Step 6: Re-install the editable package**

```bash
pip install -e plugins/doc-parser/
```

- [ ] **Step 7: Verify `load_agent_prompt` returns stripped body for each agent**

```bash
cd /tmp && python3 -c "
from dispatchers._agent_loader import load_agent_prompt
for name in ['rule-type-placement', 'source-destination', 'edv-rule', 'validate-edv', 'expression-rule', 'inter-panel-detect-refs', 'session-based']:
    body = load_agent_prompt(name)
    assert not body.startswith('---'), f'{name} frontmatter not stripped'
    assert len(body) > 100, f'{name} body suspiciously short: {len(body)}'
    print(f'{name}: {len(body)} chars')
"
cd -
```

Expected: 7 lines, each `<agent-name>: NNNN chars`, no assertion failures.

- [ ] **Step 8: Run full pipeline against vendor-creation preset and diff against baseline**

```bash
./bash_scripts/run_stages.sh /tmp/task8-check-vendor
diff -rq /tmp/plugin-migration-baseline/vendor-creation /tmp/task8-check-vendor
```

Expected: only expected LLM variance (non-deterministic JSON field ordering, timestamps). Spot-check one stage output to confirm semantic equivalence:

```bash
python3 -c "
import json
a = json.load(open('/tmp/plugin-migration-baseline/vendor-creation/rule_placement/all_panels_rules.json'))
b = json.load(open('/tmp/task8-check-vendor/rule_placement/all_panels_rules.json'))
panels_a = sorted(a.keys()) if isinstance(a, dict) else []
panels_b = sorted(b.keys()) if isinstance(b, dict) else []
print('panels match:', panels_a == panels_b)
print('panel count:', len(panels_a))
"
```

Expected: `panels match: True` (panel names are deterministic even though rule text may vary).

- [ ] **Step 9: Commit**

```bash
git add plugins/doc-parser/agents plugins/doc-parser/scripts/lib/dispatchers .claude/agents
git commit -m "Promote mini-agents to plugin agents, wire via _agent_loader

Move 7 stage mini-agents and 2 standalone agents from .claude/agents/
into plugins/doc-parser/agents/ with kebab-case names and YAML frontmatter
(name, description, model: opus). Dispatchers that used to read the old
prompt files by path now call load_agent_prompt(name), which strips
frontmatter and returns the prompt body.

Stage 7 (session-based) is treated as a hybrid deterministic + agent
stage per the spec — its agent file is live, not just preserved.

End-to-end run on vendor-creation matches baseline semantically.

Part 8/14 of plugin architecture migration."
```

---

## Task 9: Write `pipeline/stages.py` and `pipeline/run_pipeline.py`

**Files:**
- Create: `plugins/doc-parser/scripts/lib/pipeline/stages.py`
- Create: `plugins/doc-parser/scripts/lib/pipeline/run_pipeline.py`
- Create: `plugins/doc-parser/scripts/lib/pipeline/run_stage.py` (single-stage entry point for per-stage slash commands)

- [ ] **Step 1: Create `stages.py`**

File: `plugins/doc-parser/scripts/lib/pipeline/stages.py`

```python
"""Pipeline stage registry.

Single source of truth for stage → agent mapping and stage → output-subpath
wiring. Used by run_pipeline.py (full pipeline) and run_stage.py
(per-stage slash commands).
"""

# Maps stage number → plugin agent name (the file under plugins/doc-parser/agents/
# without the .md extension). Stages 0 and 8 are pure-deterministic and have no
# entry. Stage 7 is a hybrid deterministic + agent stage per the design spec.
STAGE_AGENTS = {
    1: "rule-type-placement",
    2: "source-destination",
    3: "edv-rule",
    4: "validate-edv",
    5: "expression-rule",
    6: "inter-panel-detect-refs",  # Pass 1; Pass 2 re-invokes expression-rule
    7: "session-based",
}

# Maps stage number → output file path relative to --output-dir.
# Mirrors STAGE1_OUT..STAGE7_OUT from bash_scripts/run_pipeline.sh.
STAGE_OUTPUTS = {
    1: "rule_placement/all_panels_rules.json",
    2: "source_destination/all_panels_source_dest.json",
    3: "edv_rules/all_panels_edv.json",
    4: "validate_edv/all_panels_validate_edv.json",
    5: "expression_rules/all_panels_expression_rules.json",
    6: "inter_panel/all_panels_inter_panel.json",
    7: "session_based/all_panels_session_based.json",
}

# Human-readable stage names for logging.
STAGE_NAMES = {
    0: "Field Extraction",
    1: "Rule Placement",
    2: "Source / Destination",
    3: "EDV Rules",
    4: "Validate EDV",
    5: "Expression Rules",
    6: "Inter-Panel Rules",
    7: "Session Based",
    8: "Convert to API Format",
}
```

- [ ] **Step 2: Create `run_pipeline.py`**

File: `plugins/doc-parser/scripts/lib/pipeline/run_pipeline.py`

This is a faithful Python port of `bash_scripts/run_pipeline.sh`. Port every argument, every stage invocation, every flag. Reference the bash script while writing.

```python
"""Full pipeline runner — Python port of bash_scripts/run_pipeline.sh.

Runs Stages 0 through 8 in sequence. Each stage's output becomes the
next stage's input. Supports --start-stage/--end-stage for resume and
--preset for one-shot wiring from resources/presets.json.

This file is the sole entry point for /doc-parser:run. It delegates to
the individual stage dispatchers (plugins/doc-parser/scripts/lib/dispatchers/*.py)
and to the deterministic Stage 0 (field_extractor) and Stage 8
(dispatchers.convert_to_api_format).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from pipeline.resources import resource_path
from pipeline.stages import STAGE_NAMES, STAGE_OUTPUTS


def _resolve_preset(name: str) -> dict:
    """Load a preset by name from resources/presets.json.

    Preset paths are interpreted relative to the user's cwd (where the
    pipeline is being invoked), not the plugin install dir. Absolute
    paths in presets are used as-is.
    """
    presets_file = resource_path("presets.json")
    presets = json.loads(presets_file.read_text(encoding="utf-8"))
    if name not in presets:
        raise KeyError(
            f"Unknown preset: {name}. Available: {sorted(presets.keys())}"
        )
    return presets[name]


def _run_stage(stage: int, cmd: list[str]) -> None:
    """Print a header and shell out to a stage command.

    Fails loudly on non-zero exit — no silent continuation between
    stages (matching bash_scripts/run_pipeline.sh's `set -euo pipefail`).
    """
    print(f"\n[Stage {stage}] {STAGE_NAMES[stage]}")
    print("  " + " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(
            f"[Stage {stage}] FAILED (exit {result.returncode})",
            file=sys.stderr,
        )
        sys.exit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the doc-parser BUD → API-format pipeline (Stages 0–8).",
    )
    parser.add_argument("--preset", help="Preset name from resources/presets.json")
    parser.add_argument("--bud", help="Path to BUD document (.docx)")
    parser.add_argument("--schema", help="API schema JSON for injection mode (Stage 0/8)")
    parser.add_argument(
        "--keyword-tree",
        default=str(resource_path("keyword-tree.json")),
        help="Keyword tree JSON (default: plugin resource)",
    )
    parser.add_argument(
        "--rule-schemas",
        default=str(resource_path("rule-schemas.json")),
        help="Rule schemas JSON (default: plugin resource)",
    )
    parser.add_argument("--output-dir", default="output", help="Base output directory")
    parser.add_argument("--final-output", help="Final API JSON output path")
    parser.add_argument("--bud-name", default="Vendor Creation", help="BUD name for legacy mode")
    parser.add_argument("--start-stage", type=int, default=0, choices=range(9))
    parser.add_argument("--end-stage", type=int, default=8, choices=range(9))
    parser.add_argument("--pretty", action="store_true", help="Pretty print final JSON")
    parser.add_argument(
        "--include-workflow-graph",
        action="store_true",
        help="Run workflow_graph_converter after Stage 6 (for PH Creation workflow preset)",
    )

    args = parser.parse_args()

    # Apply preset, letting explicit CLI flags override preset values.
    if args.preset:
        preset = _resolve_preset(args.preset)
        for key, val in preset.items():
            attr = key.replace("-", "_")
            if getattr(args, attr, None) in (None, False, "output"):
                setattr(args, attr, val)

    if args.bud is None:
        parser.error("--bud is required (or use --preset)")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stage_outs = {
        stage: str(output_dir / rel) for stage, rel in STAGE_OUTPUTS.items()
    }
    stage_outs[8] = args.final_output or "documents/json_output/vendor_creation_generated.json"

    # Stage 0: Field Extraction (deterministic Python, inline)
    if args.start_stage <= 0 <= args.end_stage:
        if args.schema:
            print(f"\n[Stage 0] {STAGE_NAMES[0]}")
            from field_extractor.extract_fields_complete import extract_fields_complete

            schema = extract_fields_complete(args.bud)
            schema_path = Path(args.schema)
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            schema_path.write_text(
                json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            n = len(schema["template"]["documentTypes"][0]["formFillMetadatas"])
            print(f"  Extracted {n} fields -> {args.schema}")
        else:
            print(f"\n[Stage 0] {STAGE_NAMES[0]} — SKIPPED (no --schema provided)")

    # Stages 1–7: dispatcher subprocess calls
    stage_commands = {
        1: [
            sys.executable, "-m", "dispatchers.rule_placement",
            "--bud", args.bud,
            "--keyword-tree", args.keyword_tree,
            "--rule-schemas", args.rule_schemas,
            "--output", stage_outs[1],
        ],
        2: [
            sys.executable, "-m", "dispatchers.source_destination",
            "--input", stage_outs[1],
            "--rule-schemas", args.rule_schemas,
            "--output", stage_outs[2],
        ],
        3: [
            sys.executable, "-m", "dispatchers.edv_rule",
            "--bud", args.bud,
            "--source-dest-output", stage_outs[2],
            "--output", stage_outs[3],
        ],
        4: [
            sys.executable, "-m", "dispatchers.validate_edv",
            "--bud", args.bud,
            "--edv-output", stage_outs[3],
            "--output", stage_outs[4],
        ],
        5: [
            sys.executable, "-m", "dispatchers.expression_rule",
            "--input", stage_outs[4],
            "--output", stage_outs[5],
        ],
        6: [
            sys.executable, "-m", "dispatchers.inter_panel",
            "--clear-child-output", stage_outs[5],
            "--bud", args.bud,
            "--output", stage_outs[6],
        ],
        7: [
            sys.executable, "-m", "dispatchers.session_based",
            "--input", stage_outs[6],
            "--bud", args.bud,
            "--output", stage_outs[7],
        ],
    }

    for stage in range(1, 8):
        if args.start_stage <= stage <= args.end_stage:
            _run_stage(stage, stage_commands[stage])

    # Optional: workflow graph converter after Stage 6 (for PH Creation workflow)
    if args.include_workflow_graph and args.start_stage <= 6 <= args.end_stage:
        _run_stage(
            6,
            [
                sys.executable,
                "-m",
                "dispatchers.workflow_graph_converter",
                "--input",
                stage_outs[6],
                "--output",
                stage_outs[6],
            ],
        )

    # Stage 8: Convert to API Format
    if args.start_stage <= 8 <= args.end_stage:
        cmd = [
            sys.executable, "-m", "dispatchers.convert_to_api_format",
            "--input", stage_outs[7],
            "--output", stage_outs[8],
            "--bud-name", args.bud_name,
        ]
        if args.schema:
            cmd += ["--schema", args.schema]
        if args.pretty:
            cmd.append("--pretty")
        _run_stage(8, cmd)

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Create `run_stage.py`** (single-stage entry point used by per-stage slash commands)

File: `plugins/doc-parser/scripts/lib/pipeline/run_stage.py`

```python
"""Single-stage entry point for per-stage slash commands.

Delegates to run_pipeline.py with --start-stage N --end-stage N set,
so per-stage invocations share the same argument surface as the full
pipeline runner.
"""

from __future__ import annotations

import argparse
import sys

from pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--stage", type=int, required=True, choices=range(9))
    known, rest = parser.parse_known_args()
    sys.argv = (
        [sys.argv[0]]
        + rest
        + ["--start-stage", str(known.stage), "--end-stage", str(known.stage)]
    )
    return run_pipeline.main()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Re-install the editable package**

```bash
pip install -e plugins/doc-parser/
```

- [ ] **Step 5: Verify the Python runner works for Stage 1 in isolation**

```bash
cd /tmp && python3 -m pipeline.run_pipeline \
    --bud "$HOME/project/doc-parser/documents/Vendor Creation Sample BUD.docx" \
    --schema /tmp/task9-vendor-schema.json \
    --output-dir /tmp/task9-vendor-output \
    --start-stage 0 \
    --end-stage 1
cd -
ls /tmp/task9-vendor-output/rule_placement/all_panels_rules.json
```

Expected: Stage 0 produces the schema, Stage 1 produces its output file.

- [ ] **Step 6: Commit** (presets.json not yet created — Task 10 handles it)

```bash
git add plugins/doc-parser/scripts/lib/pipeline
git commit -m "Add Python pipeline runner (ports bash_scripts/run_pipeline.sh)

- pipeline/stages.py: STAGE_AGENTS, STAGE_OUTPUTS, STAGE_NAMES registry
- pipeline/run_pipeline.py: argparse-based full-pipeline runner,
  faithful port of bash run_pipeline.sh including --start-stage/--end-stage,
  --preset, --include-workflow-graph (optional post-Stage-6 step for PH),
  and inline Stage 0 + Stage 8 invocation.
- pipeline/run_stage.py: thin per-stage wrapper that rewrites argv to
  --start-stage N --end-stage N and re-enters run_pipeline.main().

Presets file will be added in Task 10. Old bash pipeline still runs.

Part 9/14 of plugin architecture migration."
```

---

## Task 10: Build `resources/presets.json` from the 8 shell scripts

**Files:**
- Create: `plugins/doc-parser/resources/presets.json`
- Read: `bash_scripts/run_stages.sh`, `bash_scripts/run_stages_unspsc.sh`, `bash_scripts/run_stages_pidilite.sh`, `bash_scripts/run_stages_vendor_extension.sh`, `run_stages_ph_creation.sh`, `run_stages_ph_creation_workflow.sh`, `run_stages_raw_material_creation.sh`, `run_stages_sunpharma_material.sh`

- [ ] **Step 1: Read each shell script and extract its `--bud`, `--schema`, `--output-dir`, `--final-output`, `--bud-name` values**

Run each of these to read the 8 shell scripts and extract the flag values:
```bash
cat bash_scripts/run_stages.sh
cat bash_scripts/run_stages_unspsc.sh
cat bash_scripts/run_stages_pidilite.sh
cat bash_scripts/run_stages_vendor_extension.sh
cat run_stages_ph_creation.sh
cat run_stages_ph_creation_workflow.sh
cat run_stages_raw_material_creation.sh
cat run_stages_sunpharma_material.sh
```

For each script, note: the BUD path, the schema path (if any), the output directory, the final output path (if any), the bud-name, and whether it uses the workflow graph converter.

- [ ] **Step 2: Create `presets.json`** with one entry per shell script. Transcribe the actual values read in Step 1 — do not guess. Shape:

File: `plugins/doc-parser/resources/presets.json`

```json
{
  "vendor-creation": {
    "bud": "<from bash_scripts/run_stages.sh>",
    "schema": "<from bash_scripts/run_stages.sh>",
    "output_dir": "output/vendor",
    "final_output": "<from bash_scripts/run_stages.sh>",
    "bud_name": "<from bash_scripts/run_stages.sh>"
  },
  "unspsc": { "bud": "<...>", "schema": "<...>", "output_dir": "output/unspsc", "final_output": "<...>", "bud_name": "<...>" },
  "pidilite": { "bud": "<...>", "schema": "<...>", "output_dir": "output/block_unblock", "final_output": "<...>", "bud_name": "<...>" },
  "vendor-extension": { "bud": "<...>", "schema": "<...>", "output_dir": "output/vendor_extension", "final_output": "<...>", "bud_name": "<...>" },
  "ph-creation": { "bud": "<...>", "schema": "<...>", "output_dir": "output/ph", "final_output": "<...>", "bud_name": "<...>" },
  "ph-creation-workflow": { "bud": "<...>", "schema": "<...>", "output_dir": "output/ph", "final_output": "<...>", "bud_name": "<...>", "include_workflow_graph": true },
  "raw-material-creation": { "bud": "<...>", "schema": "<...>", "output_dir": "output/raw_material_creation", "final_output": "<...>", "bud_name": "<...>" },
  "sunpharma": { "bud": "<...>", "schema": "<...>", "output_dir": "output/sunpharma", "final_output": "<...>", "bud_name": "<...>" }
}
```

Replace every `<...>` placeholder with the actual value from Step 1. Any preset key that the source shell script doesn't set should be omitted from the JSON (don't write `"schema": null`).

- [ ] **Step 3: Validate presets.json is well-formed and every listed BUD exists**

```bash
python3 -c "
import json
from pathlib import Path

data = json.loads(Path('plugins/doc-parser/resources/presets.json').read_text())
assert set(data.keys()) == {'vendor-creation', 'unspsc', 'pidilite', 'vendor-extension', 'ph-creation', 'ph-creation-workflow', 'raw-material-creation', 'sunpharma'}, f'wrong keys: {sorted(data.keys())}'
for name, preset in data.items():
    assert 'bud' in preset, f'{name} missing bud'
    bud_path = Path(preset['bud'])
    assert bud_path.exists(), f'{name}: bud file does not exist: {bud_path}'
    print(f'{name}: {bud_path.name} ✓')
"
```

Expected: 8 lines, one per preset, all with `✓`.

- [ ] **Step 4: Run each preset via the new Python runner and diff output against baseline**

For each of the 8 presets, run:
```bash
rm -rf /tmp/task10-check-<preset>
python3 -m pipeline.run_pipeline --preset <preset> --output-dir /tmp/task10-check-<preset>
diff -rq /tmp/plugin-migration-baseline/<preset> /tmp/task10-check-<preset> | head -20
```

Expected for each: only non-deterministic LLM variance differences. Do the semantic panel-count spot check from Task 8 Step 8 on at least one stage per preset.

- [ ] **Step 5: Commit**

```bash
git add plugins/doc-parser/resources/presets.json
git commit -m "Add presets.json replacing 8 per-BUD shell scripts

Transcribed BUD path, schema, output dir, final output, and bud_name
from the 8 existing run_stages*.sh files into a single data file.
ph-creation-workflow carries include_workflow_graph=true, matching the
corresponding shell script's post-Stage-6 workflow graph converter call.

All 8 presets verified via 'python -m pipeline.run_pipeline --preset <name>'
against the baseline captured in Task 0.

Part 10/14 of plugin architecture migration."
```

---

## Task 11: Write 10 pipeline slash commands

**Files:**
- Create: `plugins/doc-parser/commands/run.md`
- Create: `plugins/doc-parser/commands/extract-fields.md`
- Create: `plugins/doc-parser/commands/place-rules.md`
- Create: `plugins/doc-parser/commands/source-dest.md`
- Create: `plugins/doc-parser/commands/edv.md`
- Create: `plugins/doc-parser/commands/validate-edv.md`
- Create: `plugins/doc-parser/commands/expression.md`
- Create: `plugins/doc-parser/commands/inter-panel.md`
- Create: `plugins/doc-parser/commands/session-based.md`
- Create: `plugins/doc-parser/commands/convert-api.md`

- [ ] **Step 1: Create the aggregate `run.md`**

File: `plugins/doc-parser/commands/run.md`

```markdown
---
name: run
description: Run the full doc-parser pipeline (Stages 0–8) on a BUD. Accepts --preset for one-shot wiring or explicit --bud / --schema / --output-dir flags.
argument-hint: [--preset <name> | --bud <path> --schema <path> --output-dir <path>] [--start-stage N] [--end-stage N] [--pretty]
---

Run the full BUD → API-format pipeline.

!python -m pipeline.run_pipeline $ARGUMENTS
```

- [ ] **Step 2: Create `extract-fields.md`** (Stage 0)

File: `plugins/doc-parser/commands/extract-fields.md`

```markdown
---
name: extract-fields
description: Stage 0 — deterministic field extraction from a BUD .docx into the Manch schema JSON. No LLM.
argument-hint: --bud <path> --schema <path>
---

Run Stage 0 only (field extraction).

!python -m pipeline.run_stage --stage 0 $ARGUMENTS
```

- [ ] **Step 3: Create `place-rules.md`** (Stage 1)

File: `plugins/doc-parser/commands/place-rules.md`

```markdown
---
name: place-rules
description: Stage 1 — assign rule types to each field using the keyword tree and rule-type-placement agent. Input is the schema from Stage 0; output goes to <output-dir>/rule_placement/all_panels_rules.json.
argument-hint: --bud <path> [--keyword-tree <path>] [--rule-schemas <path>] --output-dir <path>
---

Run Stage 1 only (rule placement).

!python -m pipeline.run_stage --stage 1 $ARGUMENTS
```

- [ ] **Step 4: Create `source-dest.md`** (Stage 2)

File: `plugins/doc-parser/commands/source-dest.md`

```markdown
---
name: source-dest
description: Stage 2 — determine source and destination fields for each placed rule. Uses the source-destination agent + rule schemas.
argument-hint: --output-dir <path> [--rule-schemas <path>]
---

Run Stage 2 only (source/destination mapping).

!python -m pipeline.run_stage --stage 2 $ARGUMENTS
```

- [ ] **Step 5: Create `edv.md`** (Stage 3)

File: `plugins/doc-parser/commands/edv.md`

```markdown
---
name: edv
description: Stage 3 — populate External Data Value (EDV) dropdown parameters including ddType, criterias, da, and cascading table references. Uses the edv-rule agent.
argument-hint: --bud <path> --output-dir <path>
---

Run Stage 3 only (EDV rule parameter population).

!python -m pipeline.run_stage --stage 3 $ARGUMENTS
```

- [ ] **Step 6: Create `validate-edv.md`** (Stage 4)

File: `plugins/doc-parser/commands/validate-edv.md`

```markdown
---
name: validate-edv
description: Stage 4 — place Validate EDV rules on dropdown fields and populate their params with positional column-to-field mapping. Uses the validate-edv agent.
argument-hint: --bud <path> --output-dir <path>
---

Run Stage 4 only (Validate EDV rule placement).

!python -m pipeline.run_stage --stage 4 $ARGUMENTS
```

- [ ] **Step 7: Create `expression.md`** (Stage 5)

File: `plugins/doc-parser/commands/expression.md`

```markdown
---
name: expression
description: Stage 5 — author all expression-engine rules (visibility, derivation, clearing, session triggers) using the expression-rule agent.
argument-hint: --output-dir <path>
---

Run Stage 5 only (expression rules).

!python -m pipeline.run_stage --stage 5 $ARGUMENTS
```

- [ ] **Step 8: Create `inter-panel.md`** (Stage 6)

File: `plugins/doc-parser/commands/inter-panel.md`

```markdown
---
name: inter-panel
description: Stage 6 — detect and place cross-panel field references (Copy To, visibility, expression). Pass 1 uses inter-panel-detect-refs; Pass 2 uses expression-rule.
argument-hint: --bud <path> --output-dir <path> [--include-workflow-graph]
---

Run Stage 6 only (inter-panel rules).

!python -m pipeline.run_stage --stage 6 $ARGUMENTS
```

- [ ] **Step 9: Create `session-based.md`** (Stage 7)

File: `plugins/doc-parser/commands/session-based.md`

```markdown
---
name: session-based
description: Stage 7 — hybrid deterministic + session-based-agent stage that handles session-based visibility and state rules. Inserts RuleCheck fields per panel.
argument-hint: --bud <path> --output-dir <path>
---

Run Stage 7 only (session-based rules).

!python -m pipeline.run_stage --stage 7 $ARGUMENTS
```

- [ ] **Step 10: Create `convert-api.md`** (Stage 8)

File: `plugins/doc-parser/commands/convert-api.md`

```markdown
---
name: convert-api
description: Stage 8 — deterministic final conversion to Manch API format. Injection mode (with --schema) injects rules into an existing schema; legacy mode (no --schema) builds from scratch.
argument-hint: --output-dir <path> [--schema <path>] [--final-output <path>] [--pretty]
---

Run Stage 8 only (API format conversion).

!python -m pipeline.run_stage --stage 8 $ARGUMENTS
```

- [ ] **Step 11: Verify all 10 command files parse as plugin commands**

```bash
for f in plugins/doc-parser/commands/*.md; do
    head -1 "$f" | grep -q '^---$' && echo "OK $f" || echo "FAIL $f"
done
```

Expected: 10 `OK` lines (run, extract-fields, place-rules, source-dest, edv, validate-edv, expression, inter-panel, session-based, convert-api).

- [ ] **Step 12: Commit**

```bash
git add plugins/doc-parser/commands
git commit -m "Add 10 pipeline slash commands (run + 9 per-stage)

/doc-parser:run wraps pipeline.run_pipeline.main() for the full pipeline.
Per-stage commands /doc-parser:extract-fields, place-rules, source-dest,
edv, validate-edv, expression, inter-panel, session-based, and
convert-api each delegate to pipeline.run_stage with --stage N set.

Frontmatter carries name, description, and argument-hint. The command
body is a single '!python -m pipeline.<entry> $ARGUMENTS' line so Claude
Code can execute it verbatim.

Part 11/14 of plugin architecture migration."
```

---

## Task 12: Fold the 8 existing `.claude/commands/*.md` into plugin commands

**Files:**
- Move (and rename): 8 files from `.claude/commands/` → `plugins/doc-parser/commands/`

- [ ] **Step 1: Move each tool command**

Run:
```bash
git mv .claude/commands/eval_rule_extraction.md plugins/doc-parser/commands/eval-rule-extraction.md
git mv .claude/commands/eval_panel_rules.md plugins/doc-parser/commands/eval-panel-rules.md
git mv .claude/commands/compare_form_builders.md plugins/doc-parser/commands/compare-form-builders.md
git mv .claude/commands/rule_info_extrator.md plugins/doc-parser/commands/rule-info-extractor.md
git mv .claude/commands/edv_table_mapping.md plugins/doc-parser/commands/edv-table-mapping.md
git mv .claude/commands/table_excel_file_map.md plugins/doc-parser/commands/table-excel-file-map.md
git mv .claude/commands/inter_panel_rule_field_references.md plugins/doc-parser/commands/inter-panel-refs.md
git mv .claude/commands/intra_panel_rule_field_references.md plugins/doc-parser/commands/intra-panel-refs.md
```

Note the filename corrections:
- `rule_info_extrator.md` → `rule-info-extractor.md` (fixes the typo in the source file — `extrator` → `extractor`)
- `inter_panel_rule_field_references.md` → `inter-panel-refs.md` (shorter, still unambiguous)
- `intra_panel_rule_field_references.md` → `intra-panel-refs.md`

- [ ] **Step 2: Verify each moved command has usable frontmatter or add it**

Tool commands under `.claude/commands/` may or may not have frontmatter today. For each one, check:

```bash
for f in plugins/doc-parser/commands/eval-rule-extraction.md plugins/doc-parser/commands/eval-panel-rules.md plugins/doc-parser/commands/compare-form-builders.md plugins/doc-parser/commands/rule-info-extractor.md plugins/doc-parser/commands/edv-table-mapping.md plugins/doc-parser/commands/table-excel-file-map.md plugins/doc-parser/commands/inter-panel-refs.md plugins/doc-parser/commands/intra-panel-refs.md; do
    head -1 "$f" | grep -q '^---$' && echo "OK $f" || echo "NEEDS FRONTMATTER $f"
done
```

For any file reporting `NEEDS FRONTMATTER`, add a minimal frontmatter block at the top. Template (the `description` should be a one-sentence summary of what the command does — read the file body to determine it):

```yaml
---
name: <same-as-filename-without-.md>
description: <one-sentence action-oriented description>
---
```

Do not modify the command body — only prepend the frontmatter.

- [ ] **Step 3: Verify each command still references content by paths that work from the new location**

Grep for any tool command that references a path like `.claude/...` or a hardcoded project path that might break after the move:

```bash
grep -rn "\.claude/\|bash_scripts/\|dispatchers/agents" plugins/doc-parser/commands/
```

For any hits, update the path to reference the plugin-relative equivalent or document in a comment why the path is intentional.

- [ ] **Step 4: Clean up the now-empty old commands dir**

```bash
rmdir .claude/commands 2>/dev/null || true
```

If `rmdir` fails because `.claude/commands/` still contains subdirectories (like `document_skills/`), that's fine — those are not part of doc-parser and stay untouched. Just confirm no `.md` files remain at the top level:

```bash
ls .claude/commands/*.md 2>/dev/null && echo "stray files" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 5: Commit**

```bash
git add plugins/doc-parser/commands .claude/commands
git commit -m "Fold 8 existing .claude/commands/*.md into plugin commands

Move eval_rule_extraction, eval_panel_rules, compare_form_builders,
rule_info_extrator (renamed rule-info-extractor, fixing typo),
edv_table_mapping, table_excel_file_map, inter_panel_rule_field_references
(renamed inter-panel-refs), and intra_panel_rule_field_references
(renamed intra-panel-refs) into plugins/doc-parser/commands/ with
kebab-case names and frontmatter.

Prashant's anti-fragmentation directive: one system for all doc-parser
tooling.

Part 12/14 of plugin architecture migration."
```

---

## Task 13: Delete legacy entry points and empty stubs

**Files:**
- Delete: `bash_scripts/run_pipeline.sh`, `bash_scripts/run_stages*.sh` (4 files)
- Delete: `run_stages_ph_creation.sh`, `run_stages_ph_creation_workflow.sh`, `run_stages_raw_material_creation.sh`, `run_stages_sunpharma_material.sh` (4 root-level)
- Delete: symlinks created in Task 2
- Delete: the `.gitkeep` placeholders from Task 1 wherever the directory now has real files
- Delete: empty `rules/`, `.claude/agents/mini/`, `.claude/agents/docs/`, `.claude/agents/helpers/` etc.
- Delete: `_gen_rules.py` at repo root (if it's still there)

- [ ] **Step 1: Delete all 8 shell scripts**

```bash
git rm bash_scripts/run_pipeline.sh
git rm bash_scripts/run_stages.sh
git rm bash_scripts/run_stages_unspsc.sh
git rm bash_scripts/run_stages_pidilite.sh
git rm bash_scripts/run_stages_vendor_extension.sh
git rm run_stages_ph_creation.sh
git rm run_stages_ph_creation_workflow.sh
git rm run_stages_raw_material_creation.sh
git rm run_stages_sunpharma_material.sh
rmdir bash_scripts 2>/dev/null || true
```

- [ ] **Step 2: Delete the Task 2 symlinks**

```bash
rm -f rules/Rule-Schemas.json rules/rules_buckets.json rules/RULES_CLASSIFICATION.md
rm -f rule_extractor/static/keyword_tree.json 2>/dev/null || true
rm -f .claude/agents/docs/expression_rules.md 2>/dev/null || true
```

- [ ] **Step 3: Delete remaining residue in the old top-level directories**

```bash
# rules/ — delete non-migrated files (PDFs, HTML, examples)
git rm -r rules/ 2>/dev/null || rm -rf rules/

# rule_extractor/ — delete if any files remain that weren't moved
git rm -r rule_extractor/ 2>/dev/null || rm -rf rule_extractor/

# .claude/agents/ — remove empty subdirs (mini/, docs/) and the
# no-longer-needed helpers/ dir (expression_pattern_analyzer.md is
# deliberately dropped per user direction, not migrated to the plugin).
git rm -rf .claude/agents/helpers 2>/dev/null || rm -rf .claude/agents/helpers
rmdir .claude/agents/mini 2>/dev/null || true
rmdir .claude/agents/docs 2>/dev/null || true
rmdir .claude/agents 2>/dev/null || true

# _gen_rules.py at repo root if it still exists
git rm -f _gen_rules.py 2>/dev/null || true
```

- [ ] **Step 4: Delete the `.gitkeep` stubs from Task 1 now that their directories have real files**

```bash
git rm -f plugins/doc-parser/agents/.gitkeep
git rm -f plugins/doc-parser/commands/.gitkeep
git rm -f plugins/doc-parser/resources/.gitkeep
# hooks/ stays empty in scope A; keep its .gitkeep so the directory survives.
```

- [ ] **Step 5: Verify the repo has no references to deleted paths**

```bash
git grep -l "bash_scripts/\|dispatchers/agents\|\.claude/agents/mini\|rule_extractor/static\|rules/Rule-Schemas\.json" || echo "clean"
```

Expected: `clean` (or a list of files that `git grep` found, which you then edit — if anything in `plugins/doc-parser/` still references the old path, something is wrong).

- [ ] **Step 6: Run one preset end-to-end as final sanity check**

```bash
python3 -m pipeline.run_pipeline --preset vendor-creation --output-dir /tmp/task13-final-check
ls /tmp/task13-final-check/
```

Expected: full stage output tree, with the same top-level subdirectories as the baseline.

- [ ] **Step 7: Commit**

```bash
git add --all
git commit -m "Delete legacy pipeline entry points and migration symlinks

Remove all 8 run_stages*.sh scripts (4 under bash_scripts/, 4 at repo
root), bash_scripts/run_pipeline.sh, the temporary symlinks added in
Task 2 for rules/, rule_extractor/static/, and .claude/agents/docs/,
and the empty .gitkeep stubs left over from Task 1.

The plugin is now the sole source of truth. 'git grep' for old paths
returns clean. /doc-parser:run --preset vendor-creation still produces
baseline-matching output.

Part 13/14 of plugin architecture migration."
```

---

## Task 14: Rewrite `CLAUDE.md` for the new layout

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read the existing CLAUDE.md**

Read the current file end-to-end. Note which sections describe:
- The old `dispatchers/agents/` layout
- The old `bash_scripts/run_pipeline.sh` command surface
- The 8 per-BUD shell scripts
- `.claude/agents/mini/` as the mini-agent location
- Hardcoded `rules/` and `rule_extractor/static/` paths

These all need to be rewritten.

- [ ] **Step 2: Rewrite the Common Commands section**

Replace the existing "Common Commands" block with:

```markdown
## Common Commands

```bash
# Install the plugin (one-time, from repo root)
/plugin marketplace add .
/plugin install doc-parser@manch-tooling
pip install -e plugins/doc-parser/

# Run the full rule extraction pipeline via preset
/doc-parser:run --preset vendor-creation

# Run via explicit flags
/doc-parser:run \
    --bud "documents/Vendor Creation Sample BUD.docx" \
    --schema "documents/json_output/vendor_creation.json" \
    --output-dir output/vendor \
    --pretty

# Resume from a specific stage (after a failure)
/doc-parser:run --preset vendor-creation --start-stage 3 --end-stage 5

# Run a single stage
/doc-parser:place-rules --bud "documents/Vendor Creation Sample BUD.docx" --output-dir output/vendor

# Run directly via Python (no Claude Code)
python -m pipeline.run_pipeline --preset vendor-creation
```

All 8 presets live in `plugins/doc-parser/resources/presets.json`:
vendor-creation, unspsc, pidilite, vendor-extension, ph-creation,
ph-creation-workflow, raw-material-creation, sunpharma.
```

- [ ] **Step 3: Rewrite the Architecture section**

Replace the existing "Architecture" block with a description of the plugin layout:

```markdown
## Architecture

The repo is a Claude Code marketplace (`manch-tooling`) containing one
plugin today (`doc-parser`), with room for phase-2+ siblings.

```
doc-parser/                              # repo root
├── .claude-plugin/
│   └── marketplace.json                 # manch-tooling marketplace
├── plugins/
│   └── doc-parser/
│       ├── .claude-plugin/plugin.json
│       ├── agents/                      # 7 pipeline mini-agents + 2 standalone
│       ├── commands/                    # 18 slash commands (10 pipeline + 8 tools)
│       ├── hooks/                       # empty (reserved for phase 2)
│       ├── scripts/lib/
│       │   ├── doc_parser/              # DOCX parsing
│       │   ├── field_extractor/         # Stage 0 field extraction
│       │   ├── dispatchers/             # Stage 1–8 Python orchestration
│       │   ├── rule_extractor/
│       │   └── pipeline/                # run_pipeline, stages, resources helper
│       ├── resources/                   # rule-schemas, keyword-tree, presets
│       ├── pyproject.toml               # pip-installable Python package
│       └── requirements.txt
├── documents/                           # user BUDs (input)
├── output/                              # pipeline outputs
├── self-learning/                       # meeting transcripts
└── archive/                             # dead-code graveyard
```

### Plugin-Internal Pipeline

The pipeline runs Stages 0 through 8 in sequence:

```
BUD (.docx)
  │
  ├─ Stage 0: Field Extraction      (deterministic, field_extractor)
  ├─ Stage 1: Rule Placement         (LLM, agents/rule-type-placement.md)
  ├─ Stage 2: Source / Destination   (LLM, agents/source-destination.md)
  ├─ Stage 3: EDV Rules              (LLM, agents/edv-rule.md)
  ├─ Stage 4: Validate EDV           (LLM, agents/validate-edv.md)
  ├─ Stage 5: Expression Rules       (LLM, agents/expression-rule.md)
  ├─ Stage 6: Inter-Panel Rules      (LLM, agents/inter-panel-detect-refs.md + expression-rule pass 2)
  ├─ Stage 7: Session Based          (hybrid deterministic + agents/session-based.md)
  └─ Stage 8: Convert to API Format  (deterministic)
```

Stages 1–7 are implemented as Python dispatchers under
`plugins/doc-parser/scripts/lib/dispatchers/` that shell out to
`claude -p <prompt>` with the prompt body from the matching plugin
agent file (frontmatter stripped by `_agent_loader.load_agent_prompt()`).

The stage → agent and stage → output-path wiring lives in
`plugins/doc-parser/scripts/lib/pipeline/stages.py`. The full-pipeline
runner lives in `plugins/doc-parser/scripts/lib/pipeline/run_pipeline.py`.

### Slash Command Surface

Pipeline commands (10):
- `/doc-parser:run` — full pipeline
- `/doc-parser:extract-fields` — Stage 0
- `/doc-parser:place-rules` — Stage 1
- `/doc-parser:source-dest` — Stage 2
- `/doc-parser:edv` — Stage 3
- `/doc-parser:validate-edv` — Stage 4
- `/doc-parser:expression` — Stage 5
- `/doc-parser:inter-panel` — Stage 6
- `/doc-parser:session-based` — Stage 7
- `/doc-parser:convert-api` — Stage 8

Tool commands (8):
- `/doc-parser:eval-rule-extraction`
- `/doc-parser:eval-panel-rules`
- `/doc-parser:compare-form-builders`
- `/doc-parser:rule-info-extractor`
- `/doc-parser:edv-table-mapping`
- `/doc-parser:table-excel-file-map`
- `/doc-parser:inter-panel-refs`
- `/doc-parser:intra-panel-refs`

### Plugin Agents

| Agent | Stage | File |
|---|---|---|
| rule-type-placement | 1 | `plugins/doc-parser/agents/rule-type-placement.md` |
| source-destination | 2 | `plugins/doc-parser/agents/source-destination.md` |
| edv-rule | 3 | `plugins/doc-parser/agents/edv-rule.md` |
| validate-edv | 4 | `plugins/doc-parser/agents/validate-edv.md` |
| expression-rule | 5, 6 (Pass 2) | `plugins/doc-parser/agents/expression-rule.md` |
| inter-panel-detect-refs | 6 (Pass 1) | `plugins/doc-parser/agents/inter-panel-detect-refs.md` |
| session-based | 7 | `plugins/doc-parser/agents/session-based.md` |

Two standalone agents (`extract-fields-to-json`, `rule-extraction-coding`)
are preserved under `plugins/doc-parser/agents/` for ad-hoc use via the
Task tool. They are not invoked by the pipeline.

### Static Resources

All accessed via `pipeline.resources.resource_path(name)`:

- `rule-schemas.json` — 180+ predefined rule patterns
- `rules-buckets.json` — higher-level rule groupings (Stage 1)
- `rules-classification.md` — rule taxonomy reference
- `keyword-tree.json` — keyword → action type → rule type tree (Stage 1)
- `expression-rules.md` — expression-engine cheat sheet
- `presets.json` — 8 per-BUD preset wirings
```

- [ ] **Step 4: Delete the old "Convert to API Format" section, "Key Concepts", and any reference to `archive/output/complete_format/*.json`**

Keep only Key Concepts that are still accurate (BUD, Panel, EDV, variableName, ARRAY_HDR/ARRAY_END, Expression (Client)). Remove references to `dispatchers/agents/`, `bash_scripts/`, `run_stages_*.sh` patterns, and the `.claude/agents/mini/` path.

- [ ] **Step 5: Update the "Environment" section**

Replace the old Environment section with:

```markdown
## Environment

- **Python 3.10+** required.
- **`claude` CLI** must be installed and authenticated — dispatchers for
  Stages 1–7 shell out to `claude` to invoke mini-agents.
- Install the Python package once per machine: `pip install -e plugins/doc-parser/`
- Plugin must be installed: `/plugin marketplace add .` then `/plugin install doc-parser@manch-tooling`
- `ANTHROPIC_API_KEY` in the environment for the `claude` CLI auth.
```

- [ ] **Step 6: Run the "fresh-reader" sanity check**

Ask yourself: if I wiped my memory of the pre-migration layout, could I follow this CLAUDE.md to install the plugin and run a preset? If not, what's missing? Edit until the answer is yes.

- [ ] **Step 7: Verify the full pipeline still runs from a cold terminal**

Open a fresh terminal (or `cd /tmp` to simulate) and run:

```bash
cd /home/samart/project/doc-parser
python3 -m pipeline.run_pipeline --preset vendor-creation --output-dir /tmp/task14-final-check
ls /tmp/task14-final-check/
```

Expected: full stage output tree. This is the acceptance test for the whole migration.

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md
git commit -m "Rewrite CLAUDE.md for plugin architecture

Replace the old layout description (dispatchers/agents/, bash_scripts/,
.claude/agents/mini/, per-BUD shell scripts) with a description of the
manch-tooling marketplace, plugins/doc-parser/ layout, 18 slash commands,
plugin agents, and static resources accessed via resource_path().

Environment section lists the new install steps. Command surface lists
all 10 pipeline + 8 tool commands.

Part 14/14 of plugin architecture migration. Branch plugin-architecture
is now mergeable."
```

---

## Post-Implementation: Acceptance Tests

After all 14 tasks are complete, run the acceptance-test suite from the spec (§5.1). These are checks against the final state of the branch, not per-commit gates.

- [ ] **Acceptance 1: All 8 presets produce baseline-matching output**

```bash
for preset in vendor-creation unspsc pidilite vendor-extension ph-creation ph-creation-workflow raw-material-creation sunpharma; do
    rm -rf /tmp/accept-$preset
    python3 -m pipeline.run_pipeline --preset $preset --output-dir /tmp/accept-$preset || echo "FAIL: $preset"
done
```

For each preset, spot-check panel count and rule count against the baseline at `/tmp/plugin-migration-baseline/<preset>/`.

- [ ] **Acceptance 2: All 18 slash commands are callable from Claude Code**

Inside a Claude Code session, run each command with `--help` or a minimal arg set and verify no "command not found" error.

- [ ] **Acceptance 3: `pip install -e` succeeds in a clean venv**

```bash
python3 -m venv /tmp/clean-venv
/tmp/clean-venv/bin/pip install -e plugins/doc-parser/
/tmp/clean-venv/bin/python -c "from doc_parser import DocumentParser; from dispatchers import rule_placement; from pipeline.resources import resource_path; print('ok')"
rm -rf /tmp/clean-venv
```

Expected: `ok`.

- [ ] **Acceptance 4: CLAUDE.md fresh-reader test**

Have a colleague who has never seen the pre-migration codebase (or yourself, after a day away) follow only CLAUDE.md to run `/doc-parser:run --preset vendor-creation` and verify it produces a valid output tree.

- [ ] **Acceptance 5: No legacy paths remain**

```bash
git grep -l "bash_scripts/\|dispatchers/agents\|\.claude/agents/mini\|rule_extractor/static/\|rules/Rule-Schemas\.json"
```

Expected: zero hits.

- [ ] **Acceptance 6: Fresh-clone install test**

On a different machine (or in a tmp clone):

```bash
cd /tmp && git clone <repo-url> doc-parser-test
cd doc-parser-test && git checkout plugin-architecture
pip install -e plugins/doc-parser/
python3 -m pipeline.run_pipeline --preset vendor-creation --output-dir /tmp/fresh-clone-test
ls /tmp/fresh-clone-test/
```

Expected: full stage output tree. This is the "Prashant can install your package" test.

---

## Rollback

The entire migration lives on `plugin-architecture` branch, never touching `main`. If anything goes wrong after merge, revert the merge commit. If anything goes wrong during migration, `git rebase -i` on the branch to rewrite a problem commit, or abandon the branch entirely — `chore/archive-dead-code` remains unaffected.
