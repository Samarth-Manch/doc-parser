#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:?Usage: $0 <output-root-directory>}"

echo "========== Stage 1: Rule Placement =========="
python3 dispatchers/agents/rule_placement_dispatcher.py --bud "documents/Vendor Creation Sample BUD 2.docx" --keyword-tree "rule_extractor/static/keyword_tree.json" --rule-schemas "rules/Rule-Schemas.json" --output "${OUT_DIR}/rule_placement/all_panels_rules.json"
echo "========== Stage 1 Complete =========="

echo "========== Stage 2: Source / Destination =========="
python3 dispatchers/agents/source_destination_dispatcher.py --input "${OUT_DIR}/rule_placement/all_panels_rules.json" --output "${OUT_DIR}/source_destination/all_panels_source_dest.json" --rule-schemas rules/Rule-Schemas.json
echo "========== Stage 2 Complete =========="

echo "========== Stage 3: EDV Rules =========="
python3 dispatchers/agents/edv_rule_dispatcher.py --bud "documents/Vendor Creation Sample BUD 2.docx" --source-dest-output "${OUT_DIR}/source_destination/all_panels_source_dest.json" --output "${OUT_DIR}/edv_rules/all_panels_edv.json"
echo "========== Stage 3 Complete =========="

echo "========== Stage 4: Validate EDV =========="
python3 dispatchers/agents/validate_edv_dispatcher.py --bud "documents/Vendor Creation Sample BUD 2.docx" --edv-output "${OUT_DIR}/edv_rules/all_panels_edv.json" --output "${OUT_DIR}/validate_edv/all_panels_validate_edv.json"
echo "========== Stage 4 Complete =========="

echo "========== Stage 5: Expression Rules =========="
python3 dispatchers/agents/expression_rule_dispatcher.py --input "${OUT_DIR}/validate_edv/all_panels_validate_edv.json" --output "${OUT_DIR}/expression_rules/all_panels_expression_rules.json"
echo "========== Stage 5 Complete =========="

echo "========== Stage 6: Inter-Panel Rules =========="
python3 dispatchers/agents/inter_panel_dispatcher.py --clear-child-output "${OUT_DIR}/expression_rules/all_panels_expression_rules.json" --bud "documents/Vendor Creation Sample BUD 2.docx" --output "${OUT_DIR}/inter_panel/all_panels_inter_panel.json"
echo "========== Stage 6 Complete =========="

echo "========== Stage 7: Session Based =========="
python3 dispatchers/agents/session_based_dispatcher.py --input "${OUT_DIR}/inter_panel/all_panels_inter_panel.json" --bud "documents/Vendor Creation Sample BUD 2.docx" --output "${OUT_DIR}/session_based/all_panels_session_based.json"
echo "========== Stage 7 Complete =========="

echo "========== Stage 8: Convert to API Format =========="
python3 dispatchers/agents/convert_to_api_format.py --schema archive/output/complete_format/6421-schema.json --rules "${OUT_DIR}/session_based/all_panels_session_based.json" --output /tmp/test_merged.json --pretty
echo "========== Stage 8 Complete =========="
