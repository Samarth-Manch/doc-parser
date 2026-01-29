"""
Dispatchers module for BUD document analysis commands.

Each dispatcher handles:
1. Document parsing and field extraction
2. Calling Claude commands with pre-extracted data
3. Managing output files and directories
"""

from .inter_panel_rule_field_references import extract_fields_data, call_claude_command

__all__ = ['extract_fields_data', 'call_claude_command']
