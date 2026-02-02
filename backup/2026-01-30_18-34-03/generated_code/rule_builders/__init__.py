"""
Rule builders for generating formFillRules JSON structures.
"""

try:
    from .base_builder import BaseRuleBuilder
    from .standard_builder import StandardRuleBuilder
    from .verify_builder import VerifyRuleBuilder
    from .ocr_builder import OcrRuleBuilder
    from .visibility_builder import VisibilityRuleBuilder
    from .edv_builder import EdvRuleBuilder
    from .copy_builder import CopyRuleBuilder
    from .document_builder import DocumentRuleBuilder
except ImportError:
    from base_builder import BaseRuleBuilder
    from standard_builder import StandardRuleBuilder
    from verify_builder import VerifyRuleBuilder
    from ocr_builder import OcrRuleBuilder
    from visibility_builder import VisibilityRuleBuilder
    from edv_builder import EdvRuleBuilder
    from copy_builder import CopyRuleBuilder
    from document_builder import DocumentRuleBuilder

__all__ = [
    'BaseRuleBuilder',
    'StandardRuleBuilder',
    'VerifyRuleBuilder',
    'OcrRuleBuilder',
    'VisibilityRuleBuilder',
    'EdvRuleBuilder',
    'CopyRuleBuilder',
    'DocumentRuleBuilder',
]
