#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:?Usage: $0 <output-root-directory> [max-workers]}"
MAX_WORKERS="${2:-4}"

echo "Using output dir: ${OUT_DIR}"
echo "Using max workers: ${MAX_WORKERS}"
echo ""

echo "========== Stage 1: Rule Placement =========="
python3 dispatchers/agents/rule_placement_dispatcher.py --bud "documents/Vendor Creation Sample BUD 2.docx" --keyword-tree "rule_extractor/static/keyword_tree.json" --rule-schemas "rules/Rule-Schemas.json" --output "${OUT_DIR}/rule_placement/all_panels_rules.json" --max-workers "${MAX_WORKERS}"
echo "========== Stage 1 Complete =========="

echo "========== Stage 2: Source / Destination =========="
python3 dispatchers/agents/source_destination_dispatcher.py --input "${OUT_DIR}/rule_placement/all_panels_rules.json" --output "${OUT_DIR}/source_destination/all_panels_source_dest.json" --rule-schemas rules/Rule-Schemas.json --max-workers "${MAX_WORKERS}"
echo "========== Stage 2 Complete =========="

echo "========== Stage 3: EDV Rules =========="
python3 dispatchers/agents/edv_rule_dispatcher.py --bud "documents/Vendor Creation Sample BUD 2.docx" --source-dest-output "${OUT_DIR}/source_destination/all_panels_source_dest.json" --output "${OUT_DIR}/edv_rules/all_panels_edv.json" --max-workers "${MAX_WORKERS}"
echo "========== Stage 3 Complete =========="

echo "========== Stage 4: Validate EDV =========="
python3 dispatchers/agents/validate_edv_dispatcher.py --bud "documents/Vendor Creation Sample BUD 2.docx" --edv-output "${OUT_DIR}/edv_rules/all_panels_edv.json" --output "${OUT_DIR}/validate_edv/all_panels_validate_edv.json" --max-workers "${MAX_WORKERS}"
echo "========== Stage 4 Complete =========="

echo "========== Stage 5: Clear Child Fields =========="
python3 dispatchers/agents/clear_child_fields_dispatcher.py --derivation-output "${OUT_DIR}/validate_edv/all_panels_validate_edv.json" --output "${OUT_DIR}/clear_child_fields/all_panels_clear_child.json" --max-workers "${MAX_WORKERS}"
echo "========== Stage 5 Complete =========="

echo "========== Stage 6: Expression Rules =========="
python3 dispatchers/agents/expression_rule_dispatcher.py --input "${OUT_DIR}/clear_child_fields/all_panels_clear_child.json" --output "${OUT_DIR}/expression_rules/all_panels_expression_rules.json" --max-workers "${MAX_WORKERS}"
echo "========== Stage 6 Complete =========="

echo "========== Stage 7: Inter-Panel Rules =========="
python3 dispatchers/agents/inter_panel_dispatcher.py --clear-child-output "${OUT_DIR}/expression_rules/all_panels_expression_rules.json" --bud "documents/Vendor Creation Sample BUD 2.docx" --output "${OUT_DIR}/inter_panel/all_panels_inter_panel.json"
echo "========== Stage 7 Complete =========="

echo "========== Stage 8: Session Based =========="
python3 dispatchers/agents/session_based_dispatcher.py --input "${OUT_DIR}/inter_panel/all_panels_inter_panel.json" --bud "documents/Vendor Creation Sample BUD 2.docx" --output "${OUT_DIR}/session_based/all_panels_session_based.json"
echo "========== Stage 8 Complete =========="

echo "========== Stage 9: Convert to API Format =========="
python3 dispatchers/agents/convert_to_api_format.py --schema archive/output/complete_format/6421-schema.json --rules "${OUT_DIR}/session_based/all_panels_session_based.json" --output /tmp/test_merged.json --pretty
echo "========== Stage 9 Complete =========="

echo "========== Stage 10: Fix Mandatory / Editable Fields =========="
python3 dispatchers/agents/fix_mandatory_fields.py \
    --bud "documents/Vendor Creation Sample BUD 2.docx" \
    --json /tmp/test_merged.json
echo "========== Stage 10 Complete =========="

echo "========== Stage 11: Resolve EDV Variable Names =========="
python3 dispatchers/agents/resolve_edv_varnames.py --json /tmp/test_merged.json
echo "========== Stage 11 Complete =========="

echo "========== Stage 12: Post Trigger Rule IDs =========="
python3 dispatchers/agents/post_trigger_linker.py --json /tmp/test_merged.json
echo "========== Stage 12 Complete =========="
