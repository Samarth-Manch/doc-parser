# Enhanced GUI with AI Rules Extraction - User Guide

## Overview

The Enhanced Document Parser GUI integrates AI-powered rules extraction directly into the graphical interface, providing a seamless experience for:
- Document parsing
- Field extraction
- **AI rules extraction** (NEW!)
- Visual rule exploration
- JSON export with rules

---

## Quick Start

### Option 1: Using Launch Script (Recommended)

```bash
./run_enhanced_gui.sh
```

The script will:
- Create virtual environment if needed
- Install dependencies automatically
- Check for .env configuration
- Launch the enhanced GUI

### Option 2: Manual Launch

```bash
# Activate virtual environment
source venv/bin/activate

# Run enhanced GUI
python document_parser_gui_enhanced.py
```

---

## Features

### 1. All Original Features
✅ Document selection and parsing
✅ Fields tab with filtering and search
✅ Workflows visualization
✅ Tables overview
✅ Metadata display
✅ JSON export

### 2. NEW: AI Rules Extraction
✅ **Rules Tab** - Dedicated tab for viewing extracted rules
✅ **🤖 Extract Rules Button** - One-click rules extraction
✅ **Interactive Configuration** - Choose how many fields to process
✅ **Real-time Progress** - See extraction progress live
✅ **Confidence Filtering** - Filter rules by confidence level
✅ **Rule Type Filtering** - View Expression or Standard rules
✅ **Rule Details Panel** - Double-click for detailed information
✅ **Enhanced Statistics** - Rules extraction metrics in Overview tab

---

## Using the Enhanced GUI

### Step 1: Select and Parse Document

1. Click **"Select Document"**
2. Choose a .docx file
3. Click **"Parse Document"**
4. Wait for parsing to complete (2-5 seconds)
5. View results in tabs:
   - **Overview** - Statistics
   - **Fields** - All extracted fields
   - **Workflows** - Process steps
   - **Tables** - Document tables
   - **Metadata** - Document info
   - **Raw JSON** - JSON output

### Step 2: Extract Rules (NEW!)

1. After parsing, click **"🤖 Extract Rules"**
2. Configuration dialog appears:
   - Shows total fields available
   - Displays estimated cost
   - Let you choose number of fields to process

3. Select number of fields (default: 20)
   - Recommended: Start with 10-20 fields
   - Full document (350 fields) takes ~10 minutes

4. Click **"Extract Rules"**
5. Watch real-time progress:
   - Current field being processed
   - Progress bar
   - Cannot close dialog during extraction

6. Wait for completion
   - Success message shows total rules extracted
   - Dialog can now be closed

### Step 3: Explore Extracted Rules

Navigate to the **"🤖 Rules"** tab to explore:

**Filter Options:**

*By Confidence:*
- **All** - Show all rules
- **High (≥0.8)** - High confidence rules (recommended for direct use)
- **Medium (0.5-0.8)** - Medium confidence (review recommended)
- **Low (<0.5)** - Low confidence (manual review required)

*By Rule Type:*
- **All** - Show all rule types
- **Expression** - Expression rules (makeVisible, makeMandatory, etc.)
- **Standard** - Standard rules (OCR, Validation, etc.)

**Rules Table Columns:**
- **Field Name** - Which field this rule applies to
- **Rule Name** - Descriptive name of the rule
- **Action** - EXECUTE, OCR, VALIDATION, etc.
- **Type** - EXPRESSION or STANDARD
- **Confidence** - Confidence score (color-coded)
  - 🟢 Green: High confidence (≥0.8)
  - 🟠 Orange: Medium confidence (0.5-0.8)
  - 🔴 Red: Low confidence (<0.5)
- **Expression/Details** - Expression syntax or conditions

**Rule Details:**
- Double-click any rule to see full details
- Details panel shows:
  - Complete rule information
  - Source and destination fields
  - Full conditions and expressions
  - Original logic from BUD document

### Step 4: Review Statistics

Go to **Overview** tab to see:

**Document Statistics:**
- Total fields
- Field type distribution
- Workflow counts
- Tables count

**Rules Extraction Statistics** (after extraction):
- Fields processed
- Total rules extracted
- Average confidence
- Confidence distribution
- Rule type breakdown
- Field categories (validation, visibility, mandatory)

### Step 5: Export Results

Click **"Export JSON"** to save:
- All parsed document data
- All extracted fields
- **Extracted rules** (if rules extraction was performed)

Export includes:
```json
{
  "file_path": "...",
  "metadata": {...},
  "fields": [...],
  "workflows": {...},
  "extracted_rules": {
    "total_fields_processed": 20,
    "total_rules": 25,
    "fields": [
      {
        "field_name": "Mobile Number",
        "field_type": "MOBILE",
        "rules": [...]
      }
    ]
  }
}
```

---

## Understanding the Rules Tab

### Rule Information Display

Each rule shows:

**1. Field Context**
- Which field the rule applies to
- Field type and mandatory status

**2. Rule Details**
- **Rule Name**: Human-readable description
- **Action**: What the rule does
  - `EXECUTE` - Expression rules
  - `OCR` - Optical character recognition
  - `VALIDATION` - Field validation
  - `COPY_TO` - Copy data between fields
  - `COMPARE` - Compare values
  - Many others from Rule-Schemas.json

**3. Expression/Conditions**
- For EXECUTE actions: Expression eval syntax
  - `makeVisible(vo(123)=='Yes', 124)`
  - `makeMandatory(vo(123)!='', 124)`
  - `disable(true, transactionId)`
- For STANDARD actions: Conditions in plain English

**4. Confidence Score**
- 0.9-1.0: Excellent - use directly
- 0.7-0.9: Good - minor review recommended
- 0.5-0.7: Fair - review needed
- <0.5: Poor - manual review required

### Color Coding

Rules are color-coded by confidence:
- 🟢 **Green** - High confidence (≥0.8) - Ready to use
- 🟠 **Orange** - Medium confidence (0.5-0.8) - Review recommended
- 🔴 **Red** - Low confidence (<0.5) - Manual review required

---

## Example Workflow

### Scenario: Extract and Review Rules from Vendor Creation BUD

1. **Launch GUI**
   ```bash
   ./run_enhanced_gui.sh
   ```

2. **Load Document**
   - Click "Select Document"
   - Choose "Vendor Creation Sample BUD(1).docx"
   - Click "Parse Document"
   - Wait ~3 seconds
   - ✓ 350 fields found

3. **Extract Rules**
   - Click "🤖 Extract Rules"
   - Dialog shows: 350 fields available
   - Set to 20 fields (for quick test)
   - Click "Extract Rules"
   - Watch progress: [1/20], [2/20], ...
   - Wait ~30 seconds
   - ✓ Complete! 23 rules extracted

4. **Review High-Confidence Rules**
   - Go to "🤖 Rules" tab
   - Select "High (≥0.8)" filter
   - Review ~18 high-confidence rules
   - Green color indicates ready to use

5. **Explore Expression Rules**
   - Select "Expression" type filter
   - See rules like:
     - "Transaction ID Non-Editable" - `disable(true, transactionId)`
     - "GST Conditional Visibility" - `makeVisible(vo(gstReg)=='Yes', gstNumber)`

6. **Check Rule Details**
   - Double-click "Mobile Number Validation"
   - Details panel shows:
     - Action: VALIDATION
     - Source: PAN validation
     - Confidence: 90%
     - Original logic: "Data from PAN validation..."

7. **Review Statistics**
   - Go to "Overview" tab
   - See rules statistics:
     - 20 fields processed
     - 23 rules extracted
     - 87% average confidence
     - 18 Expression, 5 Standard rules

8. **Export Everything**
   - Click "Export JSON"
   - Save as "vendor_creation_with_rules.json"
   - File includes:
     - All 350 fields
     - All workflows
     - 23 extracted rules with details

---

## Tips & Best Practices

### Starting Out
1. **Start Small**: Process 10-20 fields first
2. **Review Results**: Check extracted rules in Rules tab
3. **Verify High-Confidence**: Focus on green (high-confidence) rules
4. **Export Often**: Save results after each extraction

### Performance
- **Small Batches**: 10-20 fields = ~30 seconds
- **Medium Batches**: 50 fields = ~2 minutes
- **Full Document**: 350 fields = ~10 minutes
- **Cost**: ~$0.0003 per field (~$0.10 for full document)

### Quality Assurance
1. **Filter by Confidence**: Use "High" filter for production-ready rules
2. **Review Medium**: Check orange rules for accuracy
3. **Ignore Low**: Red rules usually need manual review
4. **Double-Check Expressions**: Verify expression syntax is correct
5. **Compare with BUD**: Cross-reference with original document

### Workflow Tips
1. **Parse First**: Always parse before extracting rules
2. **Incremental Extraction**: Can extract rules multiple times
3. **Export Incrementally**: Save after each extraction batch
4. **Review in Batches**: Don't try to review all rules at once

---

## Troubleshooting

### Issue: "Rules extraction not available"

**Cause**: Dependencies not installed or .env not configured

**Solution:**
```bash
source venv/bin/activate
pip install openai python-dotenv
echo "OPENAI_API_KEY=your_key_here" > .env
```

### Issue: Rules extraction is slow

**Cause**: OpenAI API calls take time

**Solution:**
- Normal - each field takes 1-2 seconds
- Process fewer fields at once
- Use high-speed internet connection

### Issue: Low confidence scores

**Cause**: Ambiguous or complex logic in BUD

**Solution:**
- Review original logic in Fields tab
- Check if logic is clear and unambiguous
- May need manual rule creation for complex cases
- Use as starting point and refine manually

### Issue: GUI freezes during extraction

**Cause**: Long-running operation

**Solution:**
- This is normal - extraction runs in background thread
- Progress dialog shows real-time status
- Do not close dialog during extraction
- Wait for completion message

### Issue: Cannot close dialog during extraction

**Cause**: By design - prevents interruption

**Solution:**
- Wait for extraction to complete
- "Close" button enables after completion
- If truly stuck, can force-quit application

---

## Keyboard Shortcuts

- **Ctrl+O**: Select Document (when implemented)
- **Double-Click Rule**: Show rule details
- **Escape**: Close dialogs

---

## Comparison with Command Line Tool

| Feature | Enhanced GUI | CLI Tool (`run_rules_extraction_demo.py`) |
|---------|-------------|------------------------------------------|
| Visual interface | ✅ Yes | ❌ No |
| Real-time progress | ✅ Yes | ✅ Yes |
| Interactive filtering | ✅ Yes | ❌ No |
| Rule details panel | ✅ Yes | ⚠️ Text only |
| Confidence color-coding | ✅ Yes | ❌ No |
| Export with rules | ✅ Yes | ✅ Yes |
| Batch configuration | ✅ Dialog | ✅ Prompt |
| Best for | Interactive exploration | Batch processing |

---

## Technical Details

### Threading
- Rules extraction runs in background thread
- GUI remains responsive during extraction
- Progress updates in real-time

### Memory Usage
- Efficient handling of large documents
- Rules stored in memory during session
- Full export includes all data

### Data Persistence
- Extracted rules persist during session
- Saved in exported JSON
- Can re-extract anytime

---

## What's Next

### Planned Enhancements
1. **Field ID Mapping**: Auto-detect field IDs from BUD metadata
2. **Rule Validation**: Validate expressions against form metadata
3. **Batch Export**: Export to Rule-Schemas.json format
4. **Rule Editing**: Edit extracted rules in GUI
5. **Comparison**: Compare rules across documents
6. **Templates**: Save common rule patterns

### Integration Points
- Export format compatible with existing systems
- Rules can be imported into form builders
- Expression syntax matches expr-eval library
- Standard rules match Rule-Schemas.json format

---

## Summary

The Enhanced GUI provides:

✅ **Seamless Integration**: Rules extraction built into familiar interface
✅ **Visual Exploration**: Color-coded, filterable rules display
✅ **Real-time Feedback**: See extraction progress live
✅ **Quality Assurance**: Confidence scores and filtering
✅ **Complete Export**: All data including rules in one JSON file
✅ **Production Ready**: High-confidence rules ready for immediate use

**Start extracting rules today with:**
```bash
./run_enhanced_gui.sh
```

---

**Version:** 1.0
**Last Updated:** 2026-01-16
**Status:** ✅ Production Ready
