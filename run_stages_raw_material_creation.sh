#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:?Usage: $0 <output-root-directory> [max-workers] [start-stage]}"
MAX_WORKERS="${2:-4}"
START_STAGE="${3:-0}"

BUD="documents/BUD -Raw Material Creation.docx"

echo "Using output dir: ${OUT_DIR}"
echo "Using max workers: ${MAX_WORKERS}"
echo "Starting from stage: ${START_STAGE}"
echo ""

run_stage() {
    local stage_num="$1"
    local stage_name="$2"
    shift 2

    if [[ "$stage_num" -lt "$START_STAGE" ]]; then
        echo "========== Stage ${stage_num}: ${stage_name} — SKIPPED =========="
        return 0
    fi

    echo "========== Stage ${stage_num}: ${stage_name} =========="
    "$@"
    echo "========== Stage ${stage_num} Complete =========="
}

run_stage 0 "Field Extraction" \
    python3 -c "
import sys; sys.path.insert(0, '.')
from field_extractor.extract_fields_complete import extract_fields_complete
import json
schema = extract_fields_complete('${BUD}')
with open('archive/output/complete_format/raw_material_creation-schema.json', 'w') as f:
    json.dump(schema, f, indent=2, ensure_ascii=False)
n = len(schema['template']['documentTypes'][0]['formFillMetadatas'])
print(f'  Extracted {n} fields -> archive/output/complete_format/raw_material_creation-schema.json')
"

run_stage 1 "Rule Placement" \
    python3 dispatchers/agents/rule_placement_dispatcher.py --bud "${BUD}" --keyword-tree "rule_extractor/static/keyword_tree.json" --rule-schemas "rules/Rule-Schemas.json" --output "${OUT_DIR}/rule_placement/all_panels_rules.json" --max-workers "${MAX_WORKERS}"

run_stage 2 "Source / Destination" \
    python3 dispatchers/agents/source_destination_dispatcher.py --input "${OUT_DIR}/rule_placement/all_panels_rules.json" --output "${OUT_DIR}/source_destination/all_panels_source_dest.json" --rule-schemas rules/Rule-Schemas.json --max-workers "${MAX_WORKERS}"

run_stage 3 "EDV Rules" \
    python3 dispatchers/agents/edv_rule_dispatcher.py --bud "${BUD}" --source-dest-output "${OUT_DIR}/source_destination/all_panels_source_dest.json" --output "${OUT_DIR}/edv_rules/all_panels_edv.json" --max-workers "${MAX_WORKERS}"

run_stage 4 "Validate EDV" \
    python3 dispatchers/agents/validate_edv_dispatcher.py --bud "${BUD}" --edv-output "${OUT_DIR}/edv_rules/all_panels_edv.json" --output "${OUT_DIR}/validate_edv/all_panels_validate_edv.json" --max-workers "${MAX_WORKERS}"

run_stage 5 "Expression Rules" \
    python3 dispatchers/agents/expression_rule_dispatcher.py --input "${OUT_DIR}/validate_edv/all_panels_validate_edv.json" --output "${OUT_DIR}/expression_rules/all_panels_expression_rules.json" --max-workers "${MAX_WORKERS}"

run_stage 6 "Inter-Panel Rules" \
    python3 dispatchers/agents/inter_panel_dispatcher.py --clear-child-output "${OUT_DIR}/expression_rules/all_panels_expression_rules.json" --bud "${BUD}" --output "${OUT_DIR}/inter_panel/all_panels_inter_panel.json" --detect-model opus --max-workers "${MAX_WORKERS}"

# Stage 7 (Session Based) is skipped for this BUD

run_stage 8 "Convert to API Format" \
    python3 dispatchers/agents/convert_to_api_format.py --schema archive/output/complete_format/raw_material_creation-schema.json --rules "${OUT_DIR}/inter_panel/all_panels_inter_panel.json" --output "${OUT_DIR}/test_merged_raw_material_creation.json" --pretty

run_stage 9 "Fix Mandatory / Editable Fields" \
    python3 dispatchers/agents/fix_mandatory_fields.py --bud "${BUD}" --json "${OUT_DIR}/test_merged_raw_material_creation.json"

run_stage 10 "Resolve EDV Variable Names" \
    python3 dispatchers/agents/resolve_edv_varnames.py --json "${OUT_DIR}/test_merged_raw_material_creation.json"

run_stage 11 "Post Trigger Rule IDs" \
    python3 dispatchers/agents/post_trigger_linker.py --json "${OUT_DIR}/test_merged_raw_material_creation.json"
