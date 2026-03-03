import json
import re

# Input data
panel_fields = [
  {
    "field_name": "Withholding Tax Details",
    "type": "PANEL",
    "variableName": "_withholdingtaxdetails_",
    "logic": "Panel applicable only for India Domestic (applicable only for Approver)"
  },
  {
    "field_name": "Withholding Tax Type",
    "type": "EXTERNAL_DROP_DOWN_VALUE",
    "variableName": "_withholdingtaxtypewithholdingtaxdetails_",
    "logic": "Multiple withholding tax selections should be available. Dropdown values refer table 1.6"
  },
  {
    "field_name": "Subject to w/tax",
    "type": "CHECK_BOX",
    "variableName": "_subjecttowtaxwithholdingtaxdetails_",
    "logic": "Approver can check/uncheck"
  },
  {
    "field_name": "Recipient Type",
    "type": "TEXT",
    "variableName": "_recipienttypewithholdingtaxdetails_",
    "logic": "Auto-derived. If PAN 4th Character is C then \"CO\" else OT"
  },
  {
    "field_name": "Withholding Tax Code",
    "type": "EXTERNAL_DROP_DOWN_VALUE",
    "variableName": "_withholdingtaxcodewithholdingtaxdetails_",
    "logic": "Dropdown values refer table 1.6"
  },
  {
    "field_name": "All financial & bank details are verified",
    "type": "CHECK_BOX",
    "variableName": "_allfinancialbankdetailsareverifiedwithholdingtaxdetails_",
    "logic": "Approver can check/uncheck"
  }
]

all_panels = [
  "Basic Details",
  "PAN and GST Details",
  "Vendor Basic Details",
  "Address Details",
  "Bank Details",
  "CIN and TDS Details",
  "MSME Details",
  "Vendor Duplicity Details",
  "Purchase Organization Details",
  "Payment Details",
  "Withholding Tax Details"
]

current_panel = "Withholding Tax Details"

def classify_reference(logic_lower, panel_name_lower):
    """Classify the type of reference based on logic text."""

    if any(kw in logic_lower for kw in ['visible', 'invisible', 'enable', 'disable', 'mandatory']):
        return "visibility"
    elif any(kw in logic_lower for kw in ['clear', 'cleared', 'clearing']):
        return "clearing"
    elif any(kw in logic_lower for kw in ['derived', 'auto-derived', 'auto derived']):
        return "derivation"
    elif any(kw in logic_lower for kw in ['copy', 'same as']):
        return "copy_to"
    elif any(kw in logic_lower for kw in ['validate', 'validation']):
        return "validation"
    else:
        return "other"

# Analyze references
references = []

for field in panel_fields:
    field_name = field.get('field_name', '')
    variable_name = field.get('variableName', '')
    logic = field.get('logic', '')

    if not logic:
        continue

    logic_lower = logic.lower()

    # Check specifically for PAN reference in Recipient Type field
    if 'PAN' in logic and field_name == "Recipient Type":
        references.append({
            "source_field": field_name,
            "source_variableName": variable_name,
            "reference_type": "derivation",
            "referenced_panels": ["PAN and GST Details"],
            "referenced_fields": ["PAN"],
            "logic_snippet": logic,
            "confidence": "high"
        })

    # Check for panel name mentions (Basic Details, India Domestic context)
    if 'India Domestic' in logic and field_name == "Withholding Tax Details":
        # This references a condition but not explicitly from another panel
        # The logic mentions "India Domestic" which is a process type value
        references.append({
            "source_field": field_name,
            "source_variableName": variable_name,
            "reference_type": "visibility",
            "referenced_panels": ["Basic Details"],
            "referenced_fields": ["Process Type"],
            "logic_snippet": logic,
            "confidence": "medium"
        })

# Output
output = {
    "panel_name": current_panel,
    "references": references,
    "notes": "Analysis detected 2 references: (1) Recipient Type field derives value from PAN field in PAN and GST Details panel. (2) Panel visibility is conditional on 'India Domestic' value, likely from Process Type in Basic Details panel."
}

print(json.dumps(output, indent=2))
