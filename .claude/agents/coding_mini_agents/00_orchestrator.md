---
name: Coding Mini Agent Orchestrator
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
description: Orchestrates 5-stage code-generating pipeline with deterministic-first approach and LLM fallback.
---

# Coding Mini Agent Orchestrator

## Overview

This orchestrator runs mini agents that **generate Python code** for rule extraction. Each agent writes a Python script that:
1. Uses deterministic pattern matching first
2. Falls back to LLM only when patterns don't match
3. Includes comprehensive logging
4. Outputs JSON to the workspace

## Pipeline Architecture

```
BUD Document + Schema JSON
        │
        ▼
┌─ Stage 1: Rule Type Placement ─────────────────┐
│  Agent generates: stage_1_rule_placement.py    │
│  Orchestrator runs: python stage_1_...py       │
│  Output: stage_1_output.json                   │
└────────────────────────────────────────────────┘
        │
        ▼
┌─ Stage 2: Source Destination ──────────────────┐
│  Agent generates: stage_2_source_dest.py       │
│  Orchestrator runs: python stage_2_...py       │
│  Output: stage_2_output.json                   │
└────────────────────────────────────────────────┘
        │
        ▼
┌─ Stage 3: EDV Rules ───────────────────────────┐
│  Agent generates: stage_3_edv_rules.py         │
│  Orchestrator runs: python stage_3_...py       │
│  Output: stage_3_output.json                   │
└────────────────────────────────────────────────┘
        │
        ▼
┌─ Stage 4: Post Trigger Chains ─────────────────┐
│  Agent generates: stage_4_post_trigger.py      │
│  Orchestrator runs: python stage_4_...py       │
│  Output: stage_4_output.json                   │
└────────────────────────────────────────────────┘
        │
        ▼
┌─ Stage 5: Assembly ────────────────────────────┐
│  Agent generates: stage_5_assembly.py          │
│  Orchestrator runs: python stage_5_...py       │
│  Output: final_schema.json                     │
└────────────────────────────────────────────────┘
```

## Deterministic-First Architecture

Each generated script follows this pattern:

```python
import logging
import json
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DeterministicMatcher:
    """Pattern-based matching using keyword tree and regex."""

    def __init__(self, keyword_tree: dict):
        self.keyword_tree = keyword_tree
        self.patterns = self._compile_patterns()

    def match(self, text: str, category: str) -> Optional[str]:
        """Try deterministic match first."""
        # Pattern matching logic
        pass

class LLMFallback:
    """LLM-based matching when deterministic fails."""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    def match(self, text: str, candidates: List[str]) -> Optional[str]:
        """Use LLM only for ambiguous cases."""
        pass

class HybridMatcher:
    """Combines deterministic and LLM approaches."""

    def __init__(self, keyword_tree: dict, llm_threshold: float = 0.8):
        self.deterministic = DeterministicMatcher(keyword_tree)
        self.llm_fallback = LLMFallback(llm_threshold)
        self.stats = {"deterministic": 0, "llm": 0, "failed": 0}

    def match(self, text: str, category: str) -> Optional[str]:
        # Try deterministic first
        result = self.deterministic.match(text, category)
        if result:
            self.stats["deterministic"] += 1
            logger.debug(f"Deterministic match: {result}")
            return result

        # Fall back to LLM
        result = self.llm_fallback.match(text, self.deterministic.get_candidates(category))
        if result:
            self.stats["llm"] += 1
            logger.info(f"LLM fallback match: {result}")
            return result

        self.stats["failed"] += 1
        logger.warning(f"No match found for: {text[:50]}...")
        return None
```

## Workspace Structure

```
adws/<timestamp>/
├── templates_output/
│   ├── BUD_intra_panel_references.json
│   ├── BUD_inter_panel_references.json
│   ├── BUD_meta_rules.json
│   └── BUD_edv_tables.json
├── generated_code/
│   ├── stage_1_rule_placement_v1.py
│   ├── stage_1_rule_placement_v2.py  (if retry)
│   ├── stage_2_source_dest_v1.py
│   └── ...
├── stage_outputs/
│   ├── stage_1_output_v1.json
│   └── ...
├── stage_1_eval_v1.json
├── orchestrator.log
├── iteration_summary.json
└── orchestration_summary.json
```

## Running the Orchestrator

```bash
python orchestrators/coding_mini_agent_orchestrator.py \
    "documents/Vendor Creation Sample BUD.docx" \
    --schema documents/json_output/schema.json \
    --reference documents/json_output/reference.json \
    --verbose
```

## Stage Configuration

| Stage | Name | Code File | Threshold | Max Retries |
|-------|------|-----------|-----------|-------------|
| 1 | Rule Type Placement | stage_1_rule_placement.py | 60% | 2 |
| 2 | Source Destination | stage_2_source_dest.py | 70% | 2 |
| 3 | EDV Rules | stage_3_edv_rules.py | 75% | 2 |
| 4 | Post Trigger Chain | stage_4_post_trigger.py | 80% | 2 |
| 5 | Assembly | stage_5_assembly.py | 90% | 3 |

## Key Files

| File | Purpose |
|------|---------|
| `.claude/agents/coding_mini_agents/01_rule_type_placement_agent.md` | Stage 1 code gen prompt |
| `.claude/agents/coding_mini_agents/02_source_destination_agent.md` | Stage 2 code gen prompt |
| `.claude/agents/coding_mini_agents/03_edv_rule_agent.md` | Stage 3 code gen prompt |
| `.claude/agents/coding_mini_agents/04_post_trigger_chain_agent.md` | Stage 4 code gen prompt |
| `.claude/agents/coding_mini_agents/05_assembly_agent.md` | Stage 5 code gen prompt |
| `rule_extractor/static/keyword_tree.json` | Deterministic patterns |
