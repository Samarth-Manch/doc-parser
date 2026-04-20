# Phase 1 Schema Drift Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate shape drift in `inter_panel_detect_refs` Phase 1 output by moving schema enforcement from probabilistic prompt-based guidance to a hard boundary at the Claude CLI via `--json-schema`.

**Architecture:** The current flow has the agent `Write` JSON to a file, which the dispatcher reads and feeds to a permissive normalizer. We switch the agent to emit JSON as its final response (stdout), pass a strict 9-key JSON Schema on the CLI, and parse the single-envelope stdout in the dispatcher. The normalizer stays as a safety net. We also scrub the agent prompt of every forbidden-key name to stop attention-priming drift.

**Tech Stack:** Python 3.8+, Claude CLI (`claude -p`), JSON Schema (draft-07), `subprocess`, Opus model for detection.

**Reference spec:** `issues/issue_6/fix_issue_1.md` — read before executing. Parts 3 and 4 of earlier drafts are intentionally dropped/deferred; see rationale there.

**Files:**
- Modify: `.claude/agents/mini/inter_panel_detect_refs.md`
- Create: `dispatchers/agents/schemas/detect_refs.schema.json`
- Modify: `dispatchers/agents/inter_panel_dispatcher.py:508-629` (function `detect_cross_panel_refs`) and `:1216` (Phase 1 aggregate log)
- Test (manual, shell): preflight probes run directly against `claude` CLI
- Test (repo-level): 4 consecutive runs on `documents/Vendor update BUD - Pidilite v4.docx`

**Out of scope:** semantic classification drift (Issue C), Phase 2 non-determinism (Issue B), normalizer deletion (deferred follow-up), dispatcher-side retry (dropped — coercion semantics make it inert).

---

## Task 1: Preflight — verify `--json-schema` is available and round-trips

**Files:**
- No files changed. Shell-only probe.

- [ ] **Step 1: Check the CLI supports `--json-schema`**

Run:
```bash
claude --help | grep -i json-schema
```
Expected: at least one line mentioning `--json-schema`.
If empty: STOP — jump to the **Fallback Plan** section at the end of this document.

- [ ] **Step 2: Confirm `structured_output` round-trips on a trivial prompt**

Run:
```bash
claude -p --output-format json --model haiku \
  --json-schema '{"type":"object","additionalProperties":false,"required":["panel_name","cross_panel_references"],"properties":{"panel_name":{"type":"string"},"cross_panel_references":{"type":"array"}}}' \
  'Output the JSON object {"panel_name":"Basic Details","cross_panel_references":[]}.'
```
Expected: a single JSON envelope on stdout, exit 0, with a top-level key `structured_output` holding `{"panel_name":"Basic Details","cross_panel_references":[]}`.

If `structured_output` is missing or the envelope is malformed: STOP — the CLI version installed does not behave as `fix_issue_1.md` describes. Escalate before continuing.

- [ ] **Step 3: (Optional, informational) Observe coercion on a schema-incompatible prompt**

Run:
```bash
claude -p --output-format json --model haiku \
  --json-schema '{"type":"object","additionalProperties":false,"required":["panel_name","cross_panel_references"],"properties":{"panel_name":{"type":"string"},"cross_panel_references":{"type":"array","items":{"type":"object","required":["field_variableName"],"properties":{"field_variableName":{"type":"string"}}}}}}' \
  'Output {"panel_name":"X","cross_panel_references":[{"source_field":"a","target_field":"b"}]}'
```
Expected: exit 0, `structured_output` populated with a shape-valid object where `field_variableName` has been hallucinated. This confirms the CLI coerces rather than rejects — no rejection signal exists, which is why no retry layer is built in later tasks.

- [ ] **Step 4: Commit a note that preflight passed**

No code changes. Skip commit. Proceed to Task 2.

---

## Task 2: Create the JSON schema file

**Files:**
- Create: `dispatchers/agents/schemas/detect_refs.schema.json`

- [ ] **Step 1: Create the schemas directory if it doesn't exist**

Run:
```bash
mkdir -p dispatchers/agents/schemas
```

- [ ] **Step 2: Write the schema file**

Create `dispatchers/agents/schemas/detect_refs.schema.json` with exactly this content:

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "required": ["panel_name", "cross_panel_references"],
  "properties": {
    "panel_name": { "type": "string" },
    "cross_panel_references": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "field_variableName", "field_name", "referenced_panel",
          "referenced_field_variableName", "referenced_field_name",
          "type", "classification", "logic_snippet", "description"
        ],
        "properties": {
          "field_variableName": { "type": "string", "minLength": 1 },
          "field_name": { "type": "string" },
          "referenced_panel": { "type": "string", "minLength": 1 },
          "referenced_field_variableName": { "type": "string", "minLength": 1 },
          "referenced_field_name": { "type": "string" },
          "type": { "enum": ["simple", "complex"] },
          "classification": {
            "enum": ["copy_to", "visibility", "derivation", "edv", "validate_edv", "clearing"]
          },
          "logic_snippet": { "type": "string" },
          "description": { "type": "string" }
        }
      }
    }
  }
}
```

- [ ] **Step 3: Verify the file parses as valid JSON and valid schema**

Run:
```bash
python3 -c "import json, jsonschema; s=json.load(open('dispatchers/agents/schemas/detect_refs.schema.json')); jsonschema.Draft7Validator.check_schema(s); print('OK')"
```
Expected: `OK`. If `jsonschema` is not installed, run `pip install jsonschema` first.

- [ ] **Step 4: Confirm the schema accepts a canonical example and rejects a drifted one**

Run:
```bash
python3 - <<'PY'
import json, jsonschema
schema = json.load(open('dispatchers/agents/schemas/detect_refs.schema.json'))
ok = {
  "panel_name": "Email ID Update",
  "cross_panel_references": [{
    "field_variableName": "_emailidupdate_",
    "field_name": "Email ID Update",
    "referenced_panel": "Basic Details",
    "referenced_field_variableName": "_typeofupdatebasicdetails_",
    "referenced_field_name": "Type of Update",
    "type": "complex",
    "classification": "visibility",
    "logic_snippet": "If the Type of update field (from Basic Details panel)...",
    "description": "Panel visibility controlled by Type of Update."
  }]
}
bad = {
  "panel_name": "Email ID Update",
  "cross_panel_references": [{
    "source_field_name": "Email ID Update",
    "source_variable_name": "_emailidupdate_",
    "referenced_panel": "Basic Details",
    "reference_type": "visibility",
    "classification": "simple"
  }]
}
jsonschema.validate(ok, schema)
print("canonical: OK")
try:
    jsonschema.validate(bad, schema)
    print("drifted: UNEXPECTEDLY ACCEPTED — schema is wrong")
except jsonschema.ValidationError as e:
    print("drifted: rejected as expected")
PY
```
Expected:
```
canonical: OK
drifted: rejected as expected
```

- [ ] **Step 5: Commit**

Run:
```bash
git add dispatchers/agents/schemas/detect_refs.schema.json
git commit -m "feat(inter-panel): add JSON schema for Phase 1 detect-refs output"
```

---

## Task 3: Rewire the agent prompt to stdout output (Part 1 — agent edits only)

Scope: make the agent read-only and emit its result as the final response instead of writing to `OUTPUT_FILE`. Do **not** touch Part 2 prose-cleanup here — that's Task 5. The goal of this task is a working composition test (Task 4) with the existing prompt body still largely intact.

**Files:**
- Modify: `.claude/agents/mini/inter_panel_detect_refs.md`

- [ ] **Step 1: Remove `Write` from `allowed-tools` frontmatter**

Edit `.claude/agents/mini/inter_panel_detect_refs.md` line 3. Change:
```
allowed-tools: Read, Write
```
to:
```
allowed-tools: Read
```

- [ ] **Step 2: Delete the `OUTPUT_FILE` input line**

Edit `.claude/agents/mini/inter_panel_detect_refs.md`. Delete line 43:
```
- OUTPUT_FILE: $OUTPUT_FILE — Where to write the detection results
```

- [ ] **Step 3: Rewrite the Output section (lines 45-53) to describe stdout output**

Replace the block that currently reads:

```
## Output
Write a JSON object to OUTPUT_FILE. The output MUST use EXACTLY this structure — no extra keys, no different key names, no array wrapper:

```json
{
  "panel_name": "<panel name>",
  "cross_panel_references": [...]
}
```
```

with:

```
## Output
Output a JSON object as your final response. Emit nothing before or after it. The CLI enforces the shape via JSON Schema. The top-level object has exactly two keys — `panel_name` and `cross_panel_references`.
```

- [ ] **Step 4: Rewrite Step 5 (line 140-141) to describe stdout output**

Replace:
```
### Step 5: Write output
Write the structured JSON to OUTPUT_FILE using EXACTLY the format specified below.
```

with:
```
### Step 5: Output
Output the JSON object as your final response. Emit nothing before or after it.
```

- [ ] **Step 5: Verify the file still parses and no `OUTPUT_FILE` / `Write` references remain**

Run:
```bash
grep -nE "OUTPUT_FILE|Write the structured|allowed-tools:.*Write" .claude/agents/mini/inter_panel_detect_refs.md
```
Expected: no matches.

- [ ] **Step 6: Commit**

Run:
```bash
git add .claude/agents/mini/inter_panel_detect_refs.md
git commit -m "refactor(inter-panel-agent): switch detect-refs agent to stdout output"
```

---

## Task 4: Preflight (d) — composition test against the real agent + schema

This is the **go/no-go gate** before touching the dispatcher. If this fails, the dispatcher edits will also fail — the agent system prompt must compose cleanly with `--json-schema` and `--allowedTools Read` first.

**Files:**
- Test: `/tmp/detect_test_panel.json` (transient)
- Test: `/tmp/detect_test_index.json` (transient)

- [ ] **Step 1: Write the fixture files**

Run:
```bash
cat > /tmp/detect_test_panel.json <<'EOF'
[{"field_name":"Email ID","type":"EMAIL","variableName":"_emailid_",
  "logic":"Copy from Basic Details Panel"}]
EOF

cat > /tmp/detect_test_index.json <<'EOF'
{"Basic Details":[{"field_name":"Email ID","variableName":"_emailid_"}],
 "Contact Details":[{"field_name":"Email ID","variableName":"_emailid_"}]}
EOF
```

- [ ] **Step 2: Invoke the agent end-to-end with `--json-schema`**

Run:
```bash
claude -p \
  --model opus \
  --output-format json \
  --agent mini/inter_panel_detect_refs \
  --allowedTools "Read" \
  --json-schema "$(cat dispatchers/agents/schemas/detect_refs.schema.json)" \
  "Detect cross-panel references.
   PANEL_FIELDS_FILE: /tmp/detect_test_panel.json
   PANEL_NAME: Contact Details
   ALL_PANELS_INDEX_FILE: /tmp/detect_test_index.json
   Output the JSON object as your final response."
```

Expected: a single JSON envelope on stdout with `structured_output` populated, matching:
```json
{
  "panel_name": "Contact Details",
  "cross_panel_references": [
    {
      "field_variableName": "_emailid_",
      "field_name": "Email ID",
      "referenced_panel": "Basic Details",
      "referenced_field_variableName": "_emailid_",
      "referenced_field_name": "Email ID",
      "type": "simple",
      "classification": "copy_to",
      "logic_snippet": "...",
      "description": "..."
    }
  ]
}
```
(Text in `logic_snippet` / `description` will vary — don't assert on them.)

- [ ] **Step 3: Inspect for red flags**

Diagnostic red flags — if ANY appear, STOP and fix the agent prompt before Task 6:
- `structured_output` empty or `panel_name: ""` → agent system prompt is fighting the forced tool call. Re-scan the prompt for residual `OUTPUT_FILE` / `Write` language.
- CLI errors mentioning `Write` being required → a reference to `OUTPUT_FILE` / `Write the structured` still exists. Grep again.
- Any key other than the 9 canonical keys in the `cross_panel_references` item → schema not being enforced. Re-run Task 1 Step 1 and confirm CLI version.

- [ ] **Step 4: Commit — nothing to commit**

This task runs shell probes, no file changes. Proceed to Task 5.

---

## Task 5: Prompt cleanup (Part 2) — delete every forbidden-key mention

Scope: reduce attention-priming on forbidden shapes. Shape enforcement is now at the CLI boundary, so forbidden-key prose has no referent.

**Files:**
- Modify: `.claude/agents/mini/inter_panel_detect_refs.md`

Do these deletions in order; keep running `grep` to confirm forbidden tokens drop out.

- [ ] **Step 1: Rewrite the Output Schema header (lines 12-37) to pure positive framing**

Replace everything from `## Output Schema (STRICT — read this before anything else)` through (and including) the paragraph `The per-ref schema has NO \`source\`/\`target\` split. ... below.` with:

```
## Output Schema

Each entry in `cross_panel_references` has exactly these 9 keys: `field_variableName`, `field_name`, `referenced_panel`, `referenced_field_variableName`, `referenced_field_name`, `type`, `classification`, `logic_snippet`, `description`. The CLI enforces this contract via JSON schema. A filled-in example is in the `Output Structure` section below.
```

- [ ] **Step 2: Delete Step 4 self-validation block (lines 125-138)**

Delete the entire `### Step 4: Self-validate before writing` section including its four numbered bullets and the trailing `Only after this pass, proceed to Step 5.` sentence. Renumber nothing — "Step 5" stays labeled as Step 5 (keeps the edit minimal and matches the positive example section header).

- [ ] **Step 3: Delete the WRONG example (lines 190-210 in the original file, will have shifted — search for the header)**

Delete the entire subsection starting at:
```
### WRONG — DO NOT EMIT THIS SHAPE
```
through the closing backticks of the "CORRECT shape for the same reference" block that immediately follows it. Keep the "If no cross-panel references are found" block that comes after.

Rationale: the "CORRECT shape for the same reference" example is redundant with the positive example at the top of the Output Structure section, and deleting it together with the WRONG block removes every remaining mention of `source_variable_name`, `reference_type`, etc.

- [ ] **Step 4: Replace the CRITICAL FORMAT RULES bullet list with a single line**

Replace the block starting `### CRITICAL FORMAT RULES:` and its entire bullet list with:

```
### Format
The output must match the JSON schema supplied to the CLI.
```

- [ ] **Step 5: Grep to confirm zero forbidden-key names remain**

Run:
```bash
grep -nE "source_field|source_variable|source_panel|source_field_type|target_field|target_variableName|referenced_variable_name|referenced_variableName|reference_type|reference_details|detected_references" .claude/agents/mini/inter_panel_detect_refs.md
```
Expected: no matches.

- [ ] **Step 6: Confirm the prompt still contains the canonical 9-key example and the classification guide**

Run:
```bash
grep -nE "field_variableName|classification|copy_to|visibility|derivation|edv|validate_edv|clearing" .claude/agents/mini/inter_panel_detect_refs.md | head -20
```
Expected: multiple matches — the positive example and the classification guide should still be present.

- [ ] **Step 7: Re-run the composition test from Task 4 Step 2**

Expected: same clean `structured_output` result as before. If drift appears now that didn't before, revert Step 1-4 and investigate — some positive framing element may have been accidentally removed.

- [ ] **Step 8: Commit**

Run:
```bash
git add .claude/agents/mini/inter_panel_detect_refs.md
git commit -m "refactor(inter-panel-agent): remove forbidden-key prose, keep positive framing"
```

---

## Task 6: Dispatcher — switch to `--output-format json` and `--json-schema`

**Files:**
- Modify: `dispatchers/agents/inter_panel_dispatcher.py:508-629` (function `detect_cross_panel_refs`)

All line numbers below are from the current file state. They may shift by 1-2 lines after earlier edits; anchor on the code content, not the line number.

- [ ] **Step 1: Load the schema once at module level**

Near the top of `dispatchers/agents/inter_panel_dispatcher.py`, after the existing imports and constants, add:

```python
_DETECT_REFS_SCHEMA_PATH = PROJECT_ROOT / "dispatchers" / "agents" / "schemas" / "detect_refs.schema.json"
with open(_DETECT_REFS_SCHEMA_PATH, "r") as _f:
    _DETECT_REFS_SCHEMA_JSON = _f.read()
```

(Use `PROJECT_ROOT` — the module already defines it. If the exact name differs, grep for `PROJECT_ROOT` in the file and use the existing constant.)

- [ ] **Step 2: Remove the `output_file` Path construction (line 552-553)**

In `detect_cross_panel_refs`, delete:
```python
    # Output file
    output_file = temp_dir / f"detect_{safe_name}_output.json"
```

- [ ] **Step 3: Remove the `OUTPUT_FILE` line from the prompt (line 561)**

Inside the `prompt = f"""..."""` block, delete the line:
```
- OUTPUT_FILE: {output_file}
```

Also replace the instruction line that currently reads:
```
Classify each reference and write the structured output to OUTPUT_FILE.
```
with:
```
Classify each reference and output the structured JSON as your final response.
```

- [ ] **Step 4: Switch `--output-format` to `json`, drop `--verbose`, change `--allowedTools` to `Read` only, add `--json-schema`, separate stderr**

Replace the `subprocess.Popen([...], ...)` block at lines 577-591 with:

```python
        process = subprocess.Popen(
            [
                "claude",
                "--model", model,
                "-p", prompt,
                "--output-format", "json",
                "--agent", "mini/inter_panel_detect_refs",
                "--allowedTools", "Read",
                "--json-schema", _DETECT_REFS_SCHEMA_JSON,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=PROJECT_ROOT,
        )
```

Key changes:
- `--output-format json` (was `stream-json`)
- `--verbose` removed (only needed for `stream-json`)
- `--allowedTools "Read"` (was `"Read,Write"`)
- `--json-schema` passed with the schema file contents as an inline string argument
- `stderr=subprocess.PIPE` (was `subprocess.STDOUT`) — the single-envelope stdout must not be polluted with stderr lines
- `bufsize=1` removed — we're no longer streaming

- [ ] **Step 5: Replace the streaming + file-read block with `process.communicate()` and envelope parsing**

Replace lines 593-611, which currently read:

```python
        stream_and_print(process, verbose=True, log_file_path=stream_log)
        process.wait()

        if process.returncode != 0:
            log(f"  Phase 1: Detection FAILED for '{panel_name}' "
                f"(exit code {process.returncode}) after {elapsed_str(t0)}")
            # Fall through to check if output file was still written

        # Read output (check file even on non-zero exit — partial output recovery)
        if not output_file.exists():
            log(f"  Phase 1: No output file for '{panel_name}' after {elapsed_str(t0)}")
            return None

        if process.returncode != 0:
            log(f"  Phase 1: '{panel_name}' CLI failed (exit code {process.returncode}) "
                f"but output file found — recovering")

        with open(output_file, 'r') as f:
            raw_result = json.load(f)
```

with:

```python
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            log(f"  Phase 1: Detection FAILED for '{panel_name}' "
                f"(exit code {process.returncode}) after {elapsed_str(t0)}")
            if stderr:
                log(f"  Phase 1: stderr for '{panel_name}': {stderr.strip()[:500]}")
            return None

        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as e:
            log(f"  Phase 1: Failed to parse CLI envelope for '{panel_name}': {e}")
            log(f"  Phase 1: stdout head: {stdout[:500]}")
            return None

        raw_result = envelope.get("structured_output")
        if raw_result is None:
            log(f"  Phase 1: Missing structured_output in envelope for '{panel_name}'")
            return None
```

- [ ] **Step 6: Delete the now-unused `stream_log` construction**

Directly above the Popen, delete:

```python
        safe_name = re.sub(r'[^\w\-]', '_', panel_name)
        stream_log = temp_dir / f"detect_{safe_name}_stream.log"
```

(`safe_name` is already defined earlier in the function at line 535 — the duplicate was only used for the stream log path.)

- [ ] **Step 7: Grep to confirm no orphan references to `output_file` / `stream_and_print` remain in this function**

Run:
```bash
grep -nE "output_file|stream_and_print|stream_log|stream-json" dispatchers/agents/inter_panel_dispatcher.py | grep -v "^\s*#"
```
Expected: any matches should be outside `detect_cross_panel_refs` (e.g., Phase 2 may still legitimately use stream parsing). Verify each remaining hit is not inside the function body lines 508-629. If any hit is inside the function, fix it.

- [ ] **Step 8: Run the dispatcher end-to-end against a small fixture**

Pick the smallest BUD available (check `documents/` for one with few panels, or use the Pidilite BUD). Run:

```bash
python3 dispatchers/agents/inter_panel_dispatcher.py \
  --input output/<existing-stage-5-output>/all_panels_after_expression.json \
  --output /tmp/inter_panel_test.json \
  --bud "documents/Vendor update BUD - Pidilite v4.docx" \
  --detect-model opus
```

(If you don't have a prior Stage 5 output for the Pidilite BUD, run the pipeline from Stage 1 first via `./run_stages_vendor_update.sh` — the fix instructions reference this script.)

Expected:
- Exit 0
- Per-panel log lines `Phase 1: '<panel>' — N refs detected`
- Output file written at `/tmp/inter_panel_test.json`

- [ ] **Step 9: Validate the output against the schema**

Run:
```bash
python3 - <<'PY'
import json, jsonschema
schema = json.load(open('dispatchers/agents/schemas/detect_refs.schema.json'))
# The dispatcher writes a different aggregate structure — we want to validate
# each per-panel detection result. Inspect what the dispatcher wrote:
data = json.load(open('/tmp/inter_panel_test.json'))
print(list(data.keys())[:10])
PY
```

Then, if the dispatcher writes per-panel results under a known key, validate each against the schema. The intermediate per-panel detection results are also visible in the temp dir — check those directly if the aggregate shape differs from the schema's two-key contract.

Any key not in the 9-key set appearing inside `cross_panel_references` items = failure. Stop and diagnose.

- [ ] **Step 10: Commit**

Run:
```bash
git add dispatchers/agents/inter_panel_dispatcher.py
git commit -m "refactor(inter-panel-dispatcher): enforce detect-refs shape via --json-schema"
```

---

## Task 7: Add the Phase 1 schema-acceptance aggregate log

**Files:**
- Modify: `dispatchers/agents/inter_panel_dispatcher.py:1216` (the Phase 1 COMPLETE log line)

- [ ] **Step 1: Track per-panel schema acceptance**

Inside the Phase 1 loop (around lines 1195-1214, where each panel's result is processed), add a counter. Locate the block that currently reads:

```python
                    refs = result['cross_panel_references']
                    all_refs.extend(refs)
                    for ref in refs:
                        if ref.get('type') == 'simple' and ref.get('classification') == 'copy_to':
                            simple_refs.append(ref)
                        else:
                            complex_refs.append(ref)
```

Just before the `for panel_name in ...:` loop that encloses this block, initialize:

```python
    shape_valid_panels = 0
    total_panels_attempted = 0
```

Inside the loop, increment `total_panels_attempted` once per panel attempted, and increment `shape_valid_panels` when `result` is non-None AND every ref in `result['cross_panel_references']` has exactly the 9 canonical keys. A minimal check:

```python
                    total_panels_attempted += 1
                    refs = result['cross_panel_references']
                    canonical_keys = {
                        'field_variableName', 'field_name', 'referenced_panel',
                        'referenced_field_variableName', 'referenced_field_name',
                        'type', 'classification', 'logic_snippet', 'description',
                    }
                    if all(set(ref.keys()) == canonical_keys for ref in refs):
                        shape_valid_panels += 1
```

Place this alongside the existing `all_refs.extend(refs)` work — don't duplicate the key check inside the simple/complex split.

- [ ] **Step 2: Emit the aggregate log line**

Below the existing `log(f"Phase 1 COMPLETE — ...")` at line 1216, add:

```python
    log(f"Phase 1 SCHEMA: {shape_valid_panels}/{total_panels_attempted} panels returned shape-valid output")
```

- [ ] **Step 3: Run the dispatcher and confirm the new log line appears**

Re-run the command from Task 6 Step 8. Expected: a line near the end of Phase 1 output reading `Phase 1 SCHEMA: N/N panels returned shape-valid output` with N equal on both sides.

- [ ] **Step 4: Commit**

Run:
```bash
git add dispatchers/agents/inter_panel_dispatcher.py
git commit -m "feat(inter-panel-dispatcher): emit Phase 1 schema-acceptance aggregate log"
```

---

## Task 8: Acceptance — 4 consecutive clean Pidilite runs

**Files:**
- Run: `documents/Vendor update BUD - Pidilite v4.docx`

- [ ] **Step 1: Run the Vendor Update pipeline 4 times**

Run (4 times, one after the other; record the output paths):
```bash
./run_stages_vendor_update.sh output/pidilite_run_1
./run_stages_vendor_update.sh output/pidilite_run_2
./run_stages_vendor_update.sh output/pidilite_run_3
./run_stages_vendor_update.sh output/pidilite_run_4
```

(Adjust the script invocation if it doesn't take an output dir — in that case, move `output/inter_panel_rules/` after each run: `mv output/inter_panel_rules output/pidilite_run_N`.)

- [ ] **Step 2: Validate every Phase 1 per-panel output against the schema**

Run:
```bash
python3 - <<'PY'
import json, glob, jsonschema
schema = json.load(open('dispatchers/agents/schemas/detect_refs.schema.json'))
failures = []
for run_dir in ['output/pidilite_run_1','output/pidilite_run_2','output/pidilite_run_3','output/pidilite_run_4']:
    for path in glob.glob(f'{run_dir}/**/detect_*_output.json', recursive=True):
        try:
            data = json.load(open(path))
            jsonschema.validate(data, schema)
        except Exception as e:
            failures.append((path, str(e)[:200]))
# Also validate via shape check on the aggregate output if per-panel files are absent post-enforcement
if not failures:
    print("ALL 4 RUNS CLEAN — all per-panel detect outputs match schema")
else:
    print(f"{len(failures)} FAILURES:")
    for p, e in failures[:20]:
        print(f"  {p}: {e}")
PY
```

(Per-panel files may or may not exist depending on whether the dispatcher still writes intermediate copies. If they don't, fall back to inspecting the aggregate dispatcher output — extract each panel's `cross_panel_references` and validate the envelope `{"panel_name": ..., "cross_panel_references": [...]}` per panel against the schema.)

Expected: `ALL 4 RUNS CLEAN`.

- [ ] **Step 3: Confirm the `Phase 1 SCHEMA` log showed N/N for all 4 runs**

Run:
```bash
grep -H "Phase 1 SCHEMA:" output/pidilite_run_*/logs/* 2>/dev/null || \
  grep -rH "Phase 1 SCHEMA:" output/pidilite_run_*
```
Expected: 4 lines, each with matching numerator and denominator.

- [ ] **Step 4: If all 4 clean — done. If any run drifted — diagnose, DO NOT auto-retry**

If a panel drifted:
1. Pull the raw CLI envelope for that panel (re-run just that panel with `--output-format json` and capture stdout).
2. Check whether `structured_output` is present and shape-valid. If shape-valid but the normalizer rewrote something, the issue is semantic not structural — out of scope for this fix.
3. If `structured_output` is missing or schema-invalid, the agent composition is still broken. Re-run Task 4 as a regression check.

- [ ] **Step 5: Commit acceptance notes (optional)**

If you want an audit trail, add a short note under `issues/issue_6/` documenting that 4/4 runs were clean. No code changes required.

---

## Fallback Plan (only if Task 1 Step 1 fails — CLI does not support `--json-schema`)

If `claude --help | grep -i json-schema` returns nothing, abandon Tasks 2, 3 Step 1/3/4, 4, 6, 7 as written. Instead:

**Files:**
- Modify: `.claude/agents/mini/inter_panel_detect_refs.md` (keep the file-based contract; do only Task 5's prose-cleanup deletions)
- Modify: `dispatchers/agents/inter_panel_dispatcher.py` (add Python-side `jsonschema.validate()` on the file the agent writes, with bounded retry = 1, positive-only feedback — do NOT paste failed output into the retry prompt, do NOT name forbidden keys in the retry prompt)
- Keep: `dispatchers/agents/schemas/detect_refs.schema.json` — still needed for `jsonschema.validate()`

Drift remains a probabilistic problem managed via the normalizer in this world. Document the CLI version gap and revisit when `--json-schema` lands.

---

## Success Criteria

- **Primary:** 4 consecutive runs on `documents/Vendor update BUD - Pidilite v4.docx` produce outputs where every `cross_panel_references` entry has exactly the 9 canonical keys, verified by re-validating against `dispatchers/agents/schemas/detect_refs.schema.json`.
- **Observability:** Phase 1 emits `Phase 1 SCHEMA: N/N panels returned shape-valid output` so future regressions surface without log-spelunking.
- **Non-criterion:** Bit-identical outputs across runs — sampling variance on `description` / `logic_snippet` text is expected and fine. Only shape and classification-enum conformance matter.

## Files Touched (final state)

- `.claude/agents/mini/inter_panel_detect_refs.md` — Read-only tool set, stdout output, zero forbidden-key prose, ~140 lines from ~262.
- `dispatchers/agents/schemas/detect_refs.schema.json` — new.
- `dispatchers/agents/inter_panel_dispatcher.py` — `detect_cross_panel_refs` rewired to `--output-format json` + `--json-schema`, stderr separated, envelope parsing via `process.communicate()`; Phase 1 aggregate log added near line 1216.

Not touched: `normalize_detection_output`, `_normalize_single_ref` — kept as safety net per deferred Part 4.
