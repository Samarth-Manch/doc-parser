"""
Dispatchers module for BUD document analysis commands.

Each dispatcher handles:
1. Document parsing and field extraction
2. Calling Claude commands with pre-extracted data
3. Managing output files and directories

Available dispatchers:
- intra_panel_rule_field_references: Detect within-panel field dependencies
- inter_panel_rule_field_references: Detect cross-panel field dependencies
- rule_extraction_coding_agent: Implement rule extraction system from logic text
- rule_info_extractor: Extract natural language rules
- compare_form_builders: Compare generated form builders
"""

from .inter_panel_rule_field_references import extract_fields_data, call_claude_command

__all__ = ['extract_fields_data', 'call_claude_command']
