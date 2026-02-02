"""
Rule Builders - Generate formFillRules JSON structures.

Provides builders for different rule types:
- BaseRuleBuilder: Base class with common functionality
- VisibilityRuleBuilder: MAKE_VISIBLE, MAKE_INVISIBLE, etc.
- MandatoryRuleBuilder: MAKE_MANDATORY, MAKE_NON_MANDATORY
- VerifyRuleBuilder: VERIFY rules (PAN, GSTIN, Bank, etc.)
- OcrRuleBuilder: OCR rules (PAN_IMAGE, GSTIN_IMAGE, etc.)
- ExtDropdownRuleBuilder: EXT_DROP_DOWN rules
"""

from .base_builder import BaseRuleBuilder, RuleIdGenerator
from .visibility_builder import VisibilityRuleBuilder
from .verify_builder import VerifyRuleBuilder
from .ocr_builder import OcrRuleBuilder
from .ext_dropdown_builder import ExtDropdownRuleBuilder

__all__ = [
    'BaseRuleBuilder',
    'RuleIdGenerator',
    'VisibilityRuleBuilder',
    'VerifyRuleBuilder',
    'OcrRuleBuilder',
    'ExtDropdownRuleBuilder',
]
