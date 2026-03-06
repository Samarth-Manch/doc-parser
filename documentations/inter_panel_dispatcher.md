# Inter-Panel Dispatcher & Agent — Detailed Documentation

## Table of Contents

- [Overview](#overview)
- [Why This Stage Exists](#why-this-stage-exists)
- [High-Level Flow](#high-level-flow)
- [Quick Scan (Early Exit)](#quick-scan-early-exit)
- [Phase 1: Per-Panel Reference Detection](#phase-1-per-panel-reference-detection)
- [Phase 2: Rule Generation via Expression Agent](#phase-2-rule-generation-via-expression-agent)
- [Phase 3: Validate + Merge](#phase-3-validate--merge)
- [Phase 4: Cross-Panel EDV Processing](#phase-4-cross-panel-edv-processing)
- [File Structure](#file-structure)
- [Agent Prompts](#agent-prompts)
- [Utility Functions (inter_panel_utils.py)](#utility-functions-inter_panel_utilspy)
- [Data Formats](#data-formats)
- [Classification Types](#classification-types)
- [Rule Placement Logic](#rule-placement-logic)
- [Design Decisions & Rationale](#design-decisions--rationale)
- [CLI Usage](#cli-usage)
- [Example Walkthrough](#example-walkthrough)

---

## Overview

The Inter-Panel Dispatcher is **Stage 6** of the rule extraction pipeline. It handles **cross-panel dependencies** — rules where a field in one panel references or depends on a field in a different panel. This is the only stage that operates across panel boundaries; all previous stages (1–5) process each panel independently.

The dispatcher lives at `dispatchers/agents/inter_panel_dispatcher.py` with shared utilities in `dispatchers/agents/inter_panel_utils.py`.

---

## Why This Stage Exists

BUD documents frequently define logic that crosses panel boundaries. Examples:

- **Copy To**: "Company Code" in Purchase Org Details says *"Copy from Basic Details Panel"*
- **Visibility**: "Address Proof" in Address Details says *"Visible if Process Type (from Basic Details) is India-Domestic"*
- **Derivation**: "First Name" in Vendor Basic Details says *"First Name = first word of Vendor Name (from Basic Details Panel)"*
- **EDV Lookup**: A dropdown in Panel D gets its options filtered based on a selection made in Panel A
- **Clearing**: "Clear child fields when parent field from Panel X changes"

Stages 1–5 process panels in isolation, so they cannot see or create rules that reference fields across panels. Stage 6 fills this gap by:

1. Detecting which fields have cross-panel references in their logic text
2. Classifying those references by type (copy, visibility, derivation, EDV, clearing)
3. Generating the appropriate rules (Expression (Client), Copy To, EDV, Validate EDV)
4. Merging those rules back into the correct fields in the correct panels

---

## High-Level Flow

```
Input (from Stage 5: expression rules output)
  │
  ├── Quick Scan ─────────────── Regex check for cross-panel patterns
  │     └── No refs? → Copy input to output, exit immediately
  │
  ├── Phase 1 ────────────────── Per-panel reference detection (parallel, Haiku)
  │     └── Output: flat list of classified cross-panel references
  │
  ├── Phase 2 ────────────────── Rule generation via expression agent (Opus)
  │     └── Groups refs by source field → calls agent per group
  │     └── Output: Expression (Client) rules for all ref types
  │
  ├── Phase 3 ────────────────── Validate + Merge (deterministic, no LLM)
  │     └── Validates variableNames, deduplicates, merges into output
  │
  └── Phase 4 ────────────────── Cross-panel EDV processing (conditional)
        └── Only runs if Phase 1 found EDV-classified refs
        └── Runs EDV + Validate EDV agents on affected panels
  │
  Output: all_panels_inter_panel.json
```

---

## Quick Scan (Early Exit)

**Function**: `quick_cross_panel_scan()` in `inter_panel_utils.py`

Before invoking any LLM agents, the dispatcher performs a fast regex-based check to determine if cross-panel references likely exist at all. This avoids wasting time and API calls on BUDs that have no cross-panel logic.

### What it checks:

1. **Single panel shortcut**: If there's only 1 panel, there can be no cross-panel refs → returns `False`
2. **Explicit patterns**: Regex for phrases like `(from X Panel)`, `(from X)`, `from 'X' panel`
3. **Panel name mentions**: Checks if any panel's name appears in another panel's field logic text

### Behavior:
- If `False`: The dispatcher copies the input JSON directly to the output file and exits with code 0. No LLM calls are made.
- If `True`: Proceeds to Phase 1.

---

## Phase 1: Per-Panel Reference Detection

**Model**: Haiku (fast and cheap)
**Parallelism**: Up to 4 panels simultaneously (configurable via `--max-workers`)
**Agent**: `mini/inter_panel_detect_refs`

### Purpose

Detect and classify all cross-panel references in each panel's fields. This is a lightweight detection pass — it doesn't generate rules, just identifies what needs rules.

### How it works

1. **Build shared index**: Creates `all_panels_index.json` — a compact map of every panel's fields with just `field_name` and `variableName`. This is shared across all parallel detection calls so each agent can resolve referenced field names to variableNames.

2. **Per-panel detection** (parallel): For each panel, the dispatcher:
   - Strips the fields down to just `field_name`, `type`, `variableName`, and `logic` (no rules — saves context)
   - Writes the compact fields to a temp file
   - Calls the `inter_panel_detect_refs` agent with:
     - The panel's compact fields
     - The all-panels index (for resolving references)
   - The agent scans each field's `logic` for mentions of other panels and returns structured references

3. **Normalize output**: The agent output can vary in format (arrays vs objects, different key names). The `normalize_detection_output()` function handles all these variations and produces a consistent format. It also handles:
   - Nested reference formats (`{field_name, variableName, references: [{...}]}`)
   - Various key name variants (`referenced_panel` vs `target_panel` vs `source_panel`)
   - Classification normalization (maps `"cross_panel_field_copy"` → `"copy_to"`, etc.)

4. **Collect and classify**: All references from all panels are collected into a flat list and split into:
   - `simple_refs`: Classification is `copy_to` and type is `simple`
   - `complex_refs`: Everything else (visibility, derivation, edv, clearing)

5. **Filter garbage**: References with empty `field_variableName` are filtered out.

6. **Track EDV panels**: Panels containing `edv`-classified references are tracked for Phase 4.

7. **Filter EDV from Phase 2**: EDV-classified references are removed from the complex refs list since they'll be handled separately in Phase 4.

### Output of Phase 1

A flat list of reference records, each looking like:

```json
{
  "field_variableName": "__addressproof__",
  "field_name": "Address Proof",
  "referenced_panel": "Basic Details",
  "referenced_field_variableName": "__processtype__",
  "referenced_field_name": "Process Type",
  "type": "complex",
  "classification": "visibility",
  "logic_snippet": "Visible if Process Type (from Basic Details Panel) is India-Domestic",
  "description": "Address Proof visible when Process Type is India-Domestic"
}
```

---

## Phase 2: Rule Generation via Expression Agent

**Model**: Opus (powerful, handles complex expression syntax)
**Agent**: `mini/expression_rule_agent` (reused from Stage 5)

### Purpose

Generate actual `Expression (Client)` rules for all detected cross-panel references, including copy_to references (which use `ctfd` expressions with `on("change")` wrapping).

### How it works

1. **Merge simple into complex**: Copy-to references are merged into the complex refs list. The expression agent handles them using `ctfd` + `on("change")` syntax rather than the simpler `Copy To Form Field (Client)` rule. This gives more consistent handling.

2. **Group by source field**: References are grouped using `group_complex_refs_by_source_field()`. This means if 3 different panels all reference `__processtype__` from Basic Details, they end up in one group. Benefits:
   - One agent call sees all targets and produces consolidated rules
   - Avoids duplicate rules (e.g., one visibility rule with multiple destinations instead of separate rules per panel)

3. **Identify involved panels**: For each group, the dispatcher determines which panels are involved:
   - The source field's panel (looked up from `var_index`)
   - Each target field's panel
   - The explicitly referenced panel

4. **Strip rules from involved panels**: The involved panels' field data is deep-copied with all existing `rules` arrays removed. This saves context — the expression agent only needs field metadata, not existing rules.

5. **Call expression agent**: For each source-field group:
   - Writes the involved panels (stripped) to a temp file
   - Writes the complex refs for this group to a temp file
   - Calls the `expression_rule_agent` with both files
   - The agent reads the complex ref descriptions to understand what rules are needed
   - The agent reads the involved panels to get field details (variableNames, types)
   - The agent generates `Expression (Client)` rules with proper syntax

6. **Translate output format**: The expression agent writes output in its native format (`{panel: [{field_name, variableName, rules}]}`). The `translate_expression_agent_output()` function converts this to the inter-panel merge format (`{panel: [{target_field_variableName, rules_to_add}]}`).

7. **Accumulate results**: Rules from all groups are merged into an overall `complex_rules` dict.

### Expression Syntax Used

The expression agent generates rules using these expression functions:
- `ctfd(variableName)` — get field value (cross-tab field data)
- `asdff(variableName, value)` — set field value
- `cf(variableName, condition, value)` — conditional field check
- `rffdd(variableName)` — read from field dropdown data
- `on("change")` — trigger on field value change (used for copy-to)

---

## Phase 3: Validate + Merge

**No LLM** — this is entirely deterministic Python code.

### Purpose

Validate that all generated rules reference real fields, then merge them into the output data without losing any existing rules.

### Validation (`validate_inter_panel_rules()`)

For each rule generated in Phase 2:

1. **Target field exists**: Checks that `target_field_variableName` exists in the `var_index` (variableName → panel lookup). If not found, the rule entry is stripped.

2. **Target field in correct panel**: Checks that the target field is actually in the panel the rule claims. If it's in a different panel, the rule is **relocated** to the correct panel (not stripped).

3. **Source fields exist**: Checks that every field in `source_fields` exists in the var_index. If any are invalid, the entire rule is stripped.

4. **Destination fields exist**: Checks each field in `destination_fields`. Invalid destinations are removed, but the rule is kept if at least one valid destination remains. If all destinations are invalid, the rule is stripped.

The function returns the validated rules and a count of how many were stripped.

### Merging (`merge_all_rules_into_output()`)

1. **Deep copy**: The original input data is deep-copied to avoid mutating the input.

2. **Per-panel merge**: For each panel with new rules, `_merge_rules_into_panel()` is called:
   - Builds a `variableName → field index` map for fast lookup
   - For each new rule:
     - Finds the target field by variableName
     - **Deduplication check**: Compares against existing rules on that field. A rule is considered duplicate if:
       - Same `rule_name` AND same `source_fields` AND same `destination_fields`
       - Special case for `Expression (Client)`: also compares `conditionalValues` (because multiple expression rules can share source/destination but have different expressions)
     - If not duplicate: assigns the next available `id`, tags with `_inter_panel_source: "cross-panel"`, and appends to the field's `rules` array

3. **Rule audit**: After merging, the dispatcher counts:
   - Input rules (from the original data)
   - Output rules (after merging)
   - Cross-panel rules (those tagged with `_inter_panel_source: "cross-panel"`)
   - Logs a warning if any rules were lost (output < input)

---

## Phase 4: Cross-Panel EDV Processing

**Conditional** — only runs if Phase 1 detected any references classified as `edv`.
**Models**: Opus for both EDV and Validate EDV agents

### Purpose

Handle cross-panel dropdown dependencies. When a dropdown field in Panel B gets its options filtered based on a value selected in Panel A, this requires EDV (External Data Value) rules with proper `conditionList` configuration.

### How it works

1. **Parse BUD for reference tables**: Re-parses the original BUD document using `DocumentParser` to extract embedded Excel reference tables. These tables define the dropdown options and their relationships.

2. **Phase 4a — EDV Rules**: For each panel that had EDV-classified references:
   - Gets the panel's current fields (post-merge from Phase 3)
   - Extracts the reference tables relevant to this panel's fields
   - Calls the `call_edv_mini_agent()` function (reused from Stage 3's EDV dispatcher)
   - The EDV agent configures `params.conditionList` with `ddType`, `criterias`, and `da` for cross-panel dropdown lookups
   - Passes the `all_panels_index_file` so the agent can resolve cross-panel field references

3. **Phase 4b — Validate EDV**: For the same set of panels:
   - Calls the `call_validate_edv_mini_agent()` function (reused from Stage 4)
   - Adds Validate EDV rules that enforce dropdown validation using positional column mapping

4. **Recount rules**: After Phase 4, the dispatcher recounts all rules and cross-panel rules, logging the delta.

---

## File Structure

```
dispatchers/agents/
├── inter_panel_dispatcher.py          # Main dispatcher (orchestrates all 4 phases)
├── inter_panel_utils.py               # Shared utility functions
├── edv_rule_dispatcher.py             # Reused: call_edv_mini_agent(), extract_reference_tables_from_parser()
├── validate_edv_dispatcher.py         # Reused: call_validate_edv_mini_agent()
└── context_optimization.py            # strip_all_rules_multi_panel(), print_context_report()

.claude/agents/mini/
├── inter_panel_detect_refs.md         # Phase 1 agent: detect & classify cross-panel refs
├── 09_inter_panel_analysis_agent.md   # DEPRECATED: not used by v3 dispatcher (safe to delete)
└── expression_rule_agent.md           # Reused in Phase 2: generates Expression (Client) rules

output/inter_panel/
├── all_panels_inter_panel.json        # Final output
└── temp/
    ├── inter_panel_master.log         # Master log file (tail -f to monitor)
    ├── all_panels_index.json          # Shared panel/field index
    ├── detect_<panel>_fields.json     # Phase 1: per-panel input
    ├── detect_<panel>_output.json     # Phase 1: per-panel detection result
    ├── complex_<group>_panels.json    # Phase 2: involved panels for a group
    ├── complex_<group>_refs.json      # Phase 2: complex refs for a group
    ├── complex_<group>_rules.json     # Phase 2: generated rules for a group
    └── complex_<group>_log.txt        # Phase 2: agent log for a group
```

---

## Agent Prompts

### `09_inter_panel_analysis_agent.md` (DEPRECATED — Not Used)

> **Note**: This agent file still exists on disk but is **no longer called** by the v3 dispatcher. It was part of an older architecture where a single global agent analyzed all panels at once. The current dispatcher replaced it with per-panel detection via `inter_panel_detect_refs` (Phase 1). This file can be safely deleted.

### `expression_rule_agent.md` (Phase 2 — Rule Generation)

Reused from Stage 5. In the inter-panel context, it receives:
- A `COMPLEX_REFS_FILE` describing what cross-panel references need rules
- A `FIELDS_JSON` with only the involved panels (stripped of existing rules)
- Generates `Expression (Client)` rules using `ctfd`, `asdff`, `cf`, `rffdd` syntax

---

## Utility Functions (inter_panel_utils.py)

| Function | Purpose |
|----------|---------|
| `build_compact_single_panel_text()` | Compact one-line-per-field text for a single panel |
| `build_compact_panels_text()` | Compact text for ALL panels (used by global analysis agent) |
| `build_variablename_index()` | Builds `variableName → panel_name` lookup map |
| `quick_cross_panel_scan()` | Fast regex check for cross-panel references (early exit) |
| `group_complex_refs_by_source_panel()` | Groups refs by the panel containing the referenced field |
| `group_complex_refs_by_source_field()` | Groups refs by the referenced field's variableName |
| `validate_inter_panel_rules()` | Validates variableNames exist, strips/relocates invalid rules |
| `merge_all_rules_into_output()` | Deep-copies input and merges new rules into correct fields |
| `translate_expression_agent_output()` | Converts expression agent format to inter-panel merge format |
| `read_inter_panel_output()` | Reads an inter-panel output JSON file |
| `get_involved_panels()` | Extracts full panel data for panels involved in complex refs |

---

## Data Formats

### Input (from Stage 5)

```json
{
  "Basic Details": [
    {
      "field_name": "Company Code",
      "type": "DROPDOWN",
      "variableName": "__companycode__",
      "logic": "Dropdown for company selection",
      "rules": [
        { "rule_name": "EDV", "id": 1, ... }
      ]
    }
  ],
  "Address Details": [
    {
      "field_name": "Address Proof",
      "type": "FILE_UPLOAD",
      "variableName": "__addressproof__",
      "logic": "Visible if Process Type (from Basic Details Panel) is India-Domestic",
      "rules": []
    }
  ]
}
```

### Phase 1 Detection Output (per panel)

```json
{
  "panel_name": "Address Details",
  "cross_panel_references": [
    {
      "field_variableName": "__addressproof__",
      "field_name": "Address Proof",
      "referenced_panel": "Basic Details",
      "referenced_field_variableName": "__processtype__",
      "referenced_field_name": "Process Type",
      "type": "complex",
      "classification": "visibility",
      "logic_snippet": "Visible if Process Type (from Basic Details Panel) is India-Domestic",
      "description": "Address Proof visible when Process Type is India-Domestic"
    }
  ]
}
```

### Phase 2 Rule Output (merge format)

```json
{
  "Basic Details": [
    {
      "target_field_variableName": "__processtype__",
      "rules_to_add": [
        {
          "rule_name": "Expression (Client)",
          "source_fields": ["__processtype__"],
          "destination_fields": ["__addressproof__"],
          "conditionalValues": "cf('__processtype__', 'IN', ['India-Domestic']) ? asdff('__addressproof__', 'VISIBLE') : asdff('__addressproof__', 'INVISIBLE')",
          "_reasoning": "Cross-panel visibility: Address Proof depends on Process Type",
          "_inter_panel_source": "cross-panel"
        }
      ]
    }
  ]
}
```

### Final Output

Same structure as input, but with new cross-panel rules merged into the appropriate fields' `rules` arrays. Each new rule is tagged with `"_inter_panel_source": "cross-panel"`.

---

## Classification Types

| Classification | Type | Description | Handled By |
|---------------|------|-------------|------------|
| `copy_to` | simple | Copy a field's value to another panel's field | Phase 2 (via ctfd + on("change")) |
| `visibility` | complex | Show/hide/enable/disable/mandatory based on another panel's field | Phase 2 (Expression Agent) |
| `derivation` | complex | Compute/derive a value from another panel's field (substring, splitting, etc.) | Phase 2 (Expression Agent) |
| `edv` | complex | Dropdown options depend on a field in another panel | Phase 4 (EDV + Validate EDV agents) |
| `clearing` | complex | Clear child fields when a parent field in another panel changes | Phase 2 (Expression Agent) |

---

## Rule Placement Logic

A critical concept is **where a rule gets placed** — i.e., which field's `rules` array receives the new rule.

### Copy To
- **Host field** = the **source** field (the field being copied FROM)
- **Host panel** = the panel containing the source field
- Example: "Copy Company Code from Basic Details to Purchase Org Details"
  - Rule goes on `__companycode__` in Basic Details
  - `source_fields: ["__companycode__"]`, `destination_fields: ["__companycode__"]` (the Purchase Org one)

### Visibility / State
- **Host field** = the **controller** field (the field whose value determines the state change)
- **Host panel** = the panel containing the controller field
- Example: "Address Proof visible if Process Type is India-Domestic"
  - Rule goes on `__processtype__` in Basic Details
  - `source_fields: ["__processtype__"]`, `destination_fields: ["__addressproof__"]`

### Derivation
- **Host field** = the **source** field (the field whose value is used to derive)
- Same pattern as Copy To for placement

### Clearing
- **Host field** = the **parent** field (the field whose change triggers the clearing)
- Clearing rules fire `on("change")` of the parent

---

## Design Decisions & Rationale

### 1. Panel-by-panel detection (Phase 1) instead of global analysis

**Previous approach**: A single global agent analyzed all panels at once (the `09_inter_panel_analysis_agent.md` prompt).

**Current approach**: Each panel is analyzed independently in parallel.

**Why**:
- Parallel execution — 4 panels process simultaneously, much faster
- Uses cheap Haiku model (sufficient for pattern detection)
- Smaller context per call — each agent only sees one panel's fields + the shared index
- More robust — one panel failing doesn't block others

### 2. Grouping by source field (Phase 2) instead of by source panel

**Why**: When multiple panels all reference the same source field (e.g., `__processtype__`), grouping by source field means:
- One agent call produces all rules for that source field
- The agent can consolidate — e.g., one visibility rule with multiple destination fields instead of duplicate rules
- Avoids conflicting rules from separate agent calls

### 3. Merging copy_to into complex refs (Phase 2)

**Previous approach**: Copy To rules were built deterministically using `build_simple_copy_to_rules()`.

**Current approach**: Copy To references are merged into the complex refs and sent to the expression agent.

**Why**: The expression agent generates `ctfd` + `on("change")` expressions for copy-to, which is more consistent with the platform's expected format and handles edge cases better.

### 4. Targeted context (Phase 2)

Only the involved panels (source + targets) are sent to the expression agent, not all panels.

**Why**: Reduces context window usage dramatically. A BUD with 10 panels might only need 2-3 panels for a specific cross-panel reference group. Less noise = better agent output.

### 5. EDV separated into Phase 4

**Why**: EDV rules require reference table data from the BUD document parser, which no other rule type needs. Separating this:
- Avoids parsing the BUD unnecessarily if there are no EDV refs
- Reuses the existing EDV and Validate EDV agent infrastructure from Stages 3-4
- Keeps Phase 2 focused on expression rules only

### 6. Validation before merge (Phase 3)

**Why**: LLM agents sometimes hallucinate variableNames or assign rules to the wrong panel. Validation catches these errors deterministically before they pollute the output:
- Invalid variableNames → rule is stripped
- Wrong panel → rule is relocated to the correct panel
- Partial destination errors → invalid destinations removed, valid ones kept

---

## CLI Usage

```bash
# Basic usage
python3 dispatchers/agents/inter_panel_dispatcher.py \
  --clear-child-output output/expression/all_panels_expression.json \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --output output/inter_panel/all_panels_inter_panel.json

# With options
python3 dispatchers/agents/inter_panel_dispatcher.py \
  --clear-child-output output/expression/all_panels_expression.json \
  --bud "documents/Vendor Creation Sample BUD.docx" \
  --output output/inter_panel/all_panels_inter_panel.json \
  --model opus \
  --detect-model haiku \
  --max-workers 4 \
  --context-usage
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--clear-child-output` | Yes | — | Input JSON from previous stage (expression rules output) |
| `--bud` | Yes | — | Path to the BUD document (.docx) |
| `--output` | No | `output/inter_panel/all_panels_inter_panel.json` | Output file path |
| `--model` | No | `opus` | Claude model for Phase 2 (complex rule generation) |
| `--detect-model` | No | `haiku` | Claude model for Phase 1 (reference detection) |
| `--max-workers` | No | `4` | Max parallel workers for Phase 1 |
| `--context-usage` | No | `False` | Query and display context window usage after each phase |

### Monitoring Progress

```bash
# Watch the master log in real-time
tail -f output/inter_panel/temp/inter_panel_master.log
```

---

## Example Walkthrough

### Scenario

A BUD with 3 panels:
- **Basic Details**: Has "Process Type" (`__processtype__`) dropdown with values India-Domestic / International / SEZ
- **Address Details**: Has "Address Proof" (`__addressproof__`) — "Visible if Process Type (from Basic Details) is India-Domestic"
- **Bank Details**: Has "IFSC Code" (`__ifsccode__`), "Bank Name" (`__bankname__`) — both "Visible if Process Type (from Basic Details) is India-Domestic"

### What happens

**Quick Scan**: Finds "(from Basic Details)" in Address Details and Bank Details logic → returns `True`, proceeds.

**Phase 1** (3 parallel Haiku calls):
- Basic Details agent: No cross-panel refs in this panel's logic → returns empty
- Address Details agent: Finds `__addressproof__` references Basic Details → returns 1 visibility ref
- Bank Details agent: Finds `__ifsccode__` and `__bankname__` reference Basic Details → returns 2 visibility refs

Result: 3 references, all classified as `visibility`, all `complex`, all pointing to `__processtype__` in Basic Details.

**Phase 2**:
- Group by source field: All 3 refs grouped under `__processtype__`
- Involved panels: Basic Details (source) + Address Details + Bank Details
- One agent call → produces Expression (Client) rules:
  - Rule on `__processtype__`: `cf('__processtype__', 'IN', ['India-Domestic']) ? [asdff('__addressproof__', 'VISIBLE'), asdff('__ifsccode__', 'VISIBLE'), asdff('__bankname__', 'VISIBLE')] : [asdff('__addressproof__', 'INVISIBLE'), asdff('__ifsccode__', 'INVISIBLE'), asdff('__bankname__', 'INVISIBLE')]`
  - `source_fields: ["__processtype__"]`, `destination_fields: ["__addressproof__", "__ifsccode__", "__bankname__"]`

**Phase 3**:
- Validates all variableNames exist → all valid
- Merges the rule into Basic Details panel, on the `__processtype__` field
- Tags with `_inter_panel_source: "cross-panel"`
- Rule audit: input rules = N, output rules = N+1, added = 1

**Phase 4**: Skipped — no EDV-classified references.

**Output**: Same structure as input, with one new Expression (Client) rule on `__processtype__` in Basic Details that controls visibility of 3 fields across 2 other panels.
