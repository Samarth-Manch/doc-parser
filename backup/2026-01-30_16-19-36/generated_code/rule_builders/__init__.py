"""
Rule builders for generating formFillRules JSON structures.
"""

import sys
import os

# Add directories to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from .base_builder import BaseRuleBuilder
    from .standard_builder import StandardRuleBuilder
except (ImportError, ValueError):
    import rule_builders.base_builder as base_builder_module
    import rule_builders.standard_builder as standard_builder_module
    BaseRuleBuilder = base_builder_module.BaseRuleBuilder
    StandardRuleBuilder = standard_builder_module.StandardRuleBuilder

__all__ = ['BaseRuleBuilder', 'StandardRuleBuilder']
