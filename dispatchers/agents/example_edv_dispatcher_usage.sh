#!/bin/bash
# Example usage of EDV Rule Dispatcher
#
# This script demonstrates how to run the EDV dispatcher
# after running the source_destination_agent dispatcher

set -e  # Exit on error

# Configuration
BUD_FILE="documents/Vendor Creation Sample BUD.docx"
SOURCE_DEST_OUTPUT="output/source_destination/all_panels_source_dest.json"
EDV_OUTPUT="output/edv_rules/all_panels_edv.json"

echo "========================================"
echo "EDV Rule Dispatcher Example"
echo "========================================"
echo ""

# Check if source-destination output exists
if [ ! -f "$SOURCE_DEST_OUTPUT" ]; then
    echo "❌ Error: Source-destination output not found: $SOURCE_DEST_OUTPUT"
    echo ""
    echo "Please run the source_destination_agent dispatcher first:"
    echo "  python3 dispatchers/agents/source_destination_dispatcher.py \\"
    echo "    --bud \"$BUD_FILE\" \\"
    echo "    --output \"$SOURCE_DEST_OUTPUT\""
    exit 1
fi

# Check if BUD file exists
if [ ! -f "$BUD_FILE" ]; then
    echo "❌ Error: BUD file not found: $BUD_FILE"
    exit 1
fi

echo "📁 Input Files:"
echo "  BUD: $BUD_FILE"
echo "  Source-Dest Output: $SOURCE_DEST_OUTPUT"
echo ""
echo "📝 Output:"
echo "  EDV Output: $EDV_OUTPUT"
echo ""
echo "========================================"
echo ""

# Run the dispatcher
python3 dispatchers/agents/edv_rule_dispatcher.py \
  --bud "$BUD_FILE" \
  --source-dest-output "$SOURCE_DEST_OUTPUT" \
  --output "$EDV_OUTPUT"

echo ""
echo "========================================"
echo "✅ EDV Dispatcher Complete!"
echo "========================================"
echo ""
echo "Output file: $EDV_OUTPUT"
echo ""
echo "Next steps:"
echo "  - Review the output file to verify EDV params"
echo "  - Check that cascading dropdown criterias are correct"
echo "  - Verify table mappings match the logic sections"
echo ""
