# Cross-Panel References Skill — Design

**Status:** Approved
**Date:** 2026-04-18
**Scope:** New standalone skill to extract all cross-panel field references from a BUD `.docx`, producing JSON + HTML reports.

---

## Problem

BUD documents describe form field behavior in free-text `logic` cells. When a field's logic references a field in a *different* panel (e.g., "Copy from Name field of basic detail panel", "Visible if Process Type is India-Domestic"), that is a **cross-panel reference**. Extracting these references is critical for downstream rule generation, evaluation, and reviewers who need to understand form-wide behavior.

Existing assets partially solve this:
- `.claude/commands/inter_panel_rule_field_references.md` — slash command that operates on already-extracted JSON; no HTML output; not a packaged skill.
- `.claude/agents/mini/inter_panel_detect_refs.md` + `dispatchers/agents/inter_panel_dispatcher.py` — baked into the rule-extraction pipeline; classifies by `simple`/`complex` for downstream rule generation; no standalone report.

Neither is a standalone, user-facing skill that takes a `.docx` and emits a human-readable report.

### Key gap: unnamed panel references

The user has confirmed (Option A) that the skill must resolve references where logic **names a referenced field but not its panel** (e.g., "Copy from Name field" — we must infer which panel "Name" lives in by searching all panels). The skill must not invent references where logic is silent.

---

## Goals

1. Run as a **standalone skill** (not wired into the rule-extraction pipeline).
2. Input: a BUD `.docx` path.
3. Output: both `<doc>_cross_panel_references.json` and `<doc>_cross_panel_references.html`.
4. Follow the **dispatcher pattern**: deterministic Python driver spawns `claude -p` subprocesses; **each panel runs in a fresh session** (no context bleed).
5. Resolve unnamed panel references using a global field index fed into every LLM session.
6. Emit `panel_resolution: "explicit" | "inferred" | "ambiguous"` so downstream consumers can judge match confidence.
7. Never emit intra-panel references; never invent references where logic is silent.

## Non-goals

- No integration with the rule-extraction pipeline (Stages 1–8). Output is a standalone artifact.
- No semantic/structural inference when logic is silent (that was explicitly rejected — Option B).
- No modification to existing dispatchers or agents.

---

## Architecture

### Location
```
.claude/skills/cross-panel-references/
├── SKILL.md                        # skill metadata + usage (frontmatter-style)
├── detect_cross_panel_refs.py      # deterministic driver (entry point)
└── cross_panel_ref_agent.md        # mini-agent prompt (bundled with skill)
```

Output location: `output/cross_panel_references/<bud_basename>/`
- `<bud_basename>_cross_panel_references.json`
- `<bud_basename>_cross_panel_references.html`
- `temp/panel_<idx>_input.json`, `temp/panel_<idx>_output.json` (intermediate per-panel files)
- `temp/all_panels_index.json`
- `run.log`

### Control flow (dispatcher pattern — LLM never calls back)

```
detect_cross_panel_refs.py (deterministic driver)
   │
   ├─ 1. Parse CLI args
   ├─ 2. DocumentParser().parse(bud_path) → fields_by_panel
   ├─ 3. Build global field index (all panels × all fields)
   ├─ 4. Write per-panel input files + all_panels_index.json to temp/
   ├─ 5. For each panel (parallel via ThreadPoolExecutor, bounded concurrency):
   │       subprocess.run(["claude", "-p", <prompt_with_vars_substituted>,
   │                       "--agent", "<path>/cross_panel_ref_agent.md"])
   │       → fresh session per panel (no --continue)
   │       → parse stdout JSON, validate schema
   ├─ 6. Aggregate per-panel outputs → single cross_panel_references[] list
   ├─ 7. Build panel_summary, relationship_summary, dependency_graph
   ├─ 8. Write <doc>_cross_panel_references.json
   └─ 9. Render <doc>_cross_panel_references.html (single-file HTML, inline CSS)
```

---

## Component 1: `SKILL.md`

Frontmatter format matching `bud-edv-table-verifier/SKILL.md`:

```markdown
---
name: cross-panel-references
description: Use when extracting cross-panel field references from a BUD .docx. Runs a per-panel LLM detection pass that resolves both explicit panel mentions (e.g., "Copy from Basic Details") and unnamed references (e.g., "Copy from Name field") against a global field index. Emits a JSON result and a self-contained HTML report.
---
```

Body contents:
- Purpose / when to invoke
- CLI usage:
  ```
  python3 .claude/skills/cross-panel-references/detect_cross_panel_refs.py \
    --bud "documents/<BUD>.docx" \
    --output output/cross_panel_references/
  ```
- Output description (paths, schema summary)
- Validation criteria (zero intra-panel refs, all referenced variable names exist in the global index)

---

## Component 2: `detect_cross_panel_refs.py`

CLI:
```
--bud <path>            # required, .docx
--output <dir>          # default: output/cross_panel_references/
--max-workers <int>     # default: 4, parallel panel workers
--skip-empty-logic      # optional: skip fields with empty logic before sending to LLM (saves tokens)
```

### Step-by-step behavior

1. **Parse CLI args.** Validate `.docx` exists.
2. **Parse BUD.** `DocumentParser().parse(bud_path)` → extract `fields_by_panel`. Keep PANEL-type fields in the per-panel input (their `logic` often carries cross-panel visibility controls like "this panel is visible when X from Basic Details is Y"). The agent is responsible for deduplicating PANEL-field logic that echoes a controlling field's logic (see Deduplication Rules below).
3. **Build global field index** — a JSON object:
   ```json
   {
     "Basic Details": [
       {"field_name": "Vendor Type", "variable_name": "__vendor_type__", "field_type": "DROPDOWN"},
       ...
     ],
     ...
   }
   ```
   Write to `temp/all_panels_index.json`.
4. **Per-panel worker** (called in parallel, each in its own LLM session):
   - Write `temp/panel_<slug>_input.json`:
     ```json
     {
       "panel_name": "<name>",
       "fields": [{"field_name", "variable_name", "field_type", "logic", "mandatory"}, ...]
     }
     ```
   - Build the prompt string with `$PANEL_NAME`, `$PANEL_FIELDS_FILE`, `$ALL_PANELS_INDEX_FILE`, `$OUTPUT_FILE`, `$LOG_FILE` substituted.
   - Spawn subprocess:
     ```python
     subprocess.run(
       ["claude", "-p", prompt, "--agent", str(agent_md_path)],
       timeout=600, capture_output=True, text=True, cwd=PROJECT_ROOT
     )
     ```
   - Read `$OUTPUT_FILE` (per-panel output JSON). Validate schema. On validation failure, record error and continue (do not abort whole run).
5. **Aggregate** — merge all per-panel `cross_panel_references[]` into one list. Drop any ref where source_panel == target_panel (defensive filter; should be zero).
6. **Build summaries:**
   - `panel_summary[]` — one entry per panel with `field_count`, `fields_with_cross_panel_refs`, `references_emitted_here`.
   - `relationship_summary` — count by `relationship_type`.
   - `dependency_graph.source_panels` / `dependency_graph.target_panels`.
7. **Write JSON** to `<bud_basename>_cross_panel_references.json`.
8. **Render HTML** — single-file, inline CSS, client-side filter/sort (no external JS libs). Sections:
   - Header: document name, total fields, total panels, total refs
   - Dependency graph summary (source → affected panels)
   - Filter bar: source panel, target panel, relationship_type, panel_resolution
   - Main table: one row per reference, color-coded by relationship_type, `panel_resolution` badge (green=explicit, yellow=inferred, red=ambiguous)

### Error handling

- If `DocumentParser` fails → abort with clear error.
- If a per-panel LLM call fails or returns invalid JSON → log error, emit empty `cross_panel_references: []` for that panel, mark in the final report's `errors[]` section. Do NOT abort the whole run.
- If **all** panels fail → exit nonzero.

---

## Component 3: `cross_panel_ref_agent.md` (mini-agent prompt)

Style: step-by-step, numbered, `<field_loop>` block — matching `01_rule_type_placement_agent_v2.md` and `02_source_destination_agent_v2.md`.

### Frontmatter
```yaml
---
name: Cross-Panel Reference Detection Agent
allowed-tools: Read, Write
description: Per-panel agent that detects cross-panel field references in logic text. Receives one panel's fields plus a global index of all panels' fields, and emits structured JSON of references with explicit/inferred/ambiguous panel resolution.
---
```

### Input variables
- `$PANEL_NAME` — current panel name
- `$PANEL_FIELDS_FILE` — path to this panel's fields JSON
- `$ALL_PANELS_INDEX_FILE` — path to global field index JSON
- `$OUTPUT_FILE` — where to write results
- `$LOG_FILE` — append progress lines here

### Hard constraints
- Analyze **only** the `logic` field.
- **Never invent references** where logic is silent about a cross-panel link.
- Only emit refs where `source_panel != target_panel`.
- Use exact `field_name` and `variable_name` values from `$ALL_PANELS_INDEX_FILE` — do not fabricate.
- Abort (empty output with error key) if inputs are malformed.

### Approach

**Step 1** — Read `$PANEL_FIELDS_FILE` and `$ALL_PANELS_INDEX_FILE`.

**Step 2** — Build lookups:
- Set of all panel names **except** `$PANEL_NAME`.
- Map `panel_name → {field_name_lower → {variable_name, field_type, field_name_exact}}` for every other panel.

**Step 3** — Field loop. For each field in the current panel:

`<field_loop>`

1. **Read logic.** If empty or trivially static → skip, log, continue.
2. **Scan for reference markers** using the trigger table:

   | Trigger keywords | Relationship type |
   |---|---|
   | copy from, copied from, same as, populated from, get from, derived from, based on | copy_operation |
   | visible if/when, hide if/when, show when, applicable when | visibility_control |
   | mandatory if/when, required when, non-mandatory when | mandatory_control |
   | validate against, verify with, check against | validation |
   | enable when, disable when, editable when, non-editable when | enable_disable |
   | default value, by default, auto-derived, auto-filled | default_value |
   | clear when, reset when, blank when | clear_operation |
   | if ... then (conditional behavior referencing another field) | conditional |

3. **Extract the referenced field phrase** — the noun phrase after the marker.

4. **Panel Resolution Ladder** (this is the core of this skill):

   - **(a) Explicit panel in phrase** — logic names a panel ("from basic detail panel", "in PAN and GST panel"). Map the spoken name to the canonical panel name using the **Panel Name Variations Table** below.
     - If a canonical match exists → `panel_resolution: "explicit"`.
   - **(b) No panel named** — only the field name appears ("Copy from Name field", "Title derived from PAN"). Search `$ALL_PANELS_INDEX_FILE` for the referenced field name (case-insensitive; allow partial match on multi-word names):
     - Match exists in **exactly one** other panel → use it. `panel_resolution: "inferred"`.
     - Match exists only in the **current** panel → intra-panel reference, SKIP.
     - Match exists in **multiple** other panels:
       1. Try to narrow by `field_type` hint if logic implies one.
       2. If still >1 candidate → emit with `panel_resolution: "ambiguous"` and attach `candidate_panels: [{panel, variable_name, field_type}, ...]`.
     - Match does not exist anywhere → log warning and SKIP (do not invent).

5. **Operation type** (from the field-being-analyzed POV):
   - Current field RECEIVES / IS CONTROLLED → `operation_type: "incoming"`. Source = referenced field, Target = current field.
   - Current field PROVIDES / CONTROLS → `operation_type: "outgoing"`. Source = current field, Target = referenced field.

6. **Emit** only if `source.panel != target.panel`. Include in output:
   ```json
   {
     "source_field":  {"field_name", "variable_name", "panel", "field_type"},
     "target_field":  {"field_name", "variable_name", "panel", "field_type"},
     "reference_details": {
       "matched_text":       "<phrase matched>",
       "location_found":     "logic",
       "relationship_type":  "<one of the 9 types>",
       "operation_type":     "incoming|outgoing",
       "panel_resolution":   "explicit|inferred|ambiguous",
       "raw_expression":     "<full logic text>",
       "candidate_panels":   [...]   // only when ambiguous
     }
   }
   ```

`</field_loop>`

**Step 4** — Apply Deduplication Rules, then write output JSON to `$OUTPUT_FILE`.

### Deduplication Rules

(Adapted from `.claude/agents/mini/inter_panel_detect_refs.md` — keep the behavior consistent with the existing detection agent.)

1. **PANEL field echoing a controlling field's logic**: If a PANEL-type field's logic says "this panel is visible when [dropdown] from [other panel] has value X", that is a redundant echo of the dropdown's own logic. Point the reference at the **controlling field** (the dropdown) — set `source_field` to the controlling field in the other panel, `target_field` to the PANEL field — instead of creating a second ref where the PANEL field is incorrectly treated as an independent target of the dropdown.
2. **Bidirectional echoes**: If Field A in Panel 1 has outgoing logic controlling Panel 2 AND Panel 2's PANEL field has a mirrored incoming logic pointing back to Field A, emit only one reference. Prefer the ref anchored on the field with the richer logic text.
3. **Exact duplicates**: Collapse entries where `(source_field.variable_name, target_field.variable_name, relationship_type)` already appear together.

### Panel Name Variations Table

Same as the existing `.claude/commands/inter_panel_rule_field_references.md` — literal inclusion so the agent has a canonical mapping. The table will be embedded in the prompt (not loaded from file), with placeholders for BUD-specific panel names supplied in `$ALL_PANELS_INDEX_FILE`.

### Output schema (per-panel)

```json
{
  "panel_name": "Vendor Basic Details",
  "cross_panel_references": [
    {
      "source_field": {...},
      "target_field": {...},
      "reference_details": {...}
    }
  ],
  "errors": []
}
```

### Aggregated output schema (final JSON)

```json
{
  "document_info": {
    "file_name": "...",
    "file_path": "...",
    "extraction_timestamp": "...",
    "total_fields": 0,
    "total_panels": 0
  },
  "panel_summary": [
    {"panel_name": "...", "field_count": 0, "fields_with_cross_panel_refs": 0, "references_emitted_here": 0}
  ],
  "cross_panel_references": [...],
  "relationship_summary": {
    "copy_operation": 0, "visibility_control": 0, "mandatory_control": 0,
    "validation": 0, "enable_disable": 0, "default_value": 0,
    "conditional": 0, "clear_operation": 0, "other": 0
  },
  "dependency_graph": {
    "source_panels": {"<panel>": {"affects_panels": [...], "reference_count": 0}},
    "target_panels": {"<panel>": {"affected_by_panels": [...], "reference_count": 0}}
  },
  "errors": []
}
```

---

## HTML report

Single-file HTML, inline CSS, vanilla JS only.

Sections:
1. **Document header** — BUD name, timestamp, totals
2. **Summary cards** — total refs, refs by relationship_type (colored pills), refs by panel_resolution
3. **Dependency graph** — collapsible list: each source panel → affected panels with counts; each target panel → source panels
4. **Main reference table** — one row per reference, columns: Source (panel / field), Target (panel / field), Relationship, Operation, Resolution (badge), Matched text, Raw logic (truncated w/ expand). Client-side filter bar above the table.
5. **Errors section** (only rendered if non-empty)

---

## Validation & acceptance

Run against all 5 BUDs listed in the request:
- `documents/Vendor Creation Sample BUD 3.docx`
- `documents/Vendor update BUD - Pidilite v3.docx`
- `documents/Pidilite Vendor block-unblock BUD 1.3_modified.docx`
- `documents/PH Creation new BUD_V7.docx`
- `documents/Profit Center Creation BUD.docx`

Acceptance criteria:
1. Zero intra-panel refs in output (source_panel != target_panel for every emitted ref).
2. Every `referenced_field.variable_name` exists in the global field index at the referenced panel.
3. At least one `panel_resolution: "inferred"` emitted on BUDs known to contain unnamed refs (manual spot-check).
4. HTML loads standalone without network access; filters work.
5. Per-panel LLM failures do not abort the whole run — they surface in `errors[]`.

---

## Open items

None. The two earlier design questions are resolved:
- Output dir: `output/cross_panel_references/<bud_basename>/`
- Ambiguous panel resolution: emit with `panel_resolution: "ambiguous"` + `candidate_panels[]` (do not drop)
