"""
Validators for rule extraction and generation.

Provides validation functions for:
- Generated rules structure
- Field ID references
- Rule schema compliance
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass

from .models import GeneratedRule, FieldInfo
from .schema_lookup import RuleSchemaLookup


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class RuleValidator:
    """Validates generated rules."""

    # Required fields for all rules
    REQUIRED_FIELDS = ['actionType', 'processingType', 'sourceIds', 'destinationIds']

    # Valid action types
    VALID_ACTION_TYPES = {
        'MAKE_VISIBLE', 'MAKE_INVISIBLE',
        'MAKE_MANDATORY', 'MAKE_NON_MANDATORY',
        'MAKE_DISABLED', 'MAKE_ENABLED',
        'SESSION_BASED_MAKE_VISIBLE', 'SESSION_BASED_MAKE_INVISIBLE',
        'SESSION_BASED_MAKE_MANDATORY', 'SESSION_BASED_MAKE_NON_MANDATORY',
        'VERIFY', 'OCR',
        'COPY_TO', 'CLEAR_FIELD', 'EXECUTE',
        'SET_DATE', 'CONVERT_TO',
        'EXT_VALUE', 'EXT_DROP_DOWN',
        'DUMMY_ACTION', 'COPY_TXNID_TO_FORM_FILL', 'COPY_TO_TRANSACTION_ATTR3',
    }

    # Valid conditions
    VALID_CONDITIONS = {'IN', 'NOT_IN', 'EQUALS', 'NOT_EQUALS'}

    def __init__(self, valid_field_ids: Optional[Set[int]] = None):
        """
        Initialize validator.

        Args:
            valid_field_ids: Set of valid field IDs for reference validation
        """
        self.valid_field_ids = valid_field_ids or set()

    def set_valid_field_ids(self, field_ids: Set[int]) -> None:
        """Update valid field IDs."""
        self.valid_field_ids = field_ids

    def validate(self, rule: Dict) -> ValidationResult:
        """
        Validate a single rule.

        Args:
            rule: Rule dict to validate

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in rule:
                errors.append(f"Missing required field: {field}")

        # Validate action type
        action_type = rule.get('actionType')
        if action_type and action_type not in self.VALID_ACTION_TYPES:
            warnings.append(f"Unknown action type: {action_type}")

        # Validate condition
        condition = rule.get('condition')
        if condition and condition not in self.VALID_CONDITIONS:
            warnings.append(f"Unknown condition: {condition}")

        # Validate field ID references
        if self.valid_field_ids:
            for sid in rule.get('sourceIds', []):
                if sid != -1 and sid not in self.valid_field_ids:
                    errors.append(f"Invalid sourceId: {sid}")

            for did in rule.get('destinationIds', []):
                if did != -1 and did not in self.valid_field_ids:
                    errors.append(f"Invalid destinationId: {did}")

        # Validate conditionalValues with condition
        if rule.get('conditionalValues') and not rule.get('condition'):
            warnings.append("Has conditionalValues but no condition")

        # Validate VERIFY/OCR have sourceType
        if action_type in ['VERIFY', 'OCR'] and not rule.get('sourceType'):
            warnings.append(f"{action_type} rule should have sourceType")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_batch(self, rules: List[Dict]) -> ValidationResult:
        """
        Validate multiple rules.

        Args:
            rules: List of rule dicts

        Returns:
            Aggregated ValidationResult
        """
        all_errors = []
        all_warnings = []

        for i, rule in enumerate(rules):
            result = self.validate(rule)
            for error in result.errors:
                all_errors.append(f"Rule {i}: {error}")
            for warning in result.warnings:
                all_warnings.append(f"Rule {i}: {warning}")

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
        )


class SchemaValidator:
    """Validates rules against Rule-Schemas.json."""

    def __init__(self, schema_lookup: RuleSchemaLookup):
        """Initialize with schema lookup."""
        self.schema_lookup = schema_lookup

    def validate_verify_rule(self, rule: Dict) -> ValidationResult:
        """
        Validate a VERIFY rule against its schema.

        Args:
            rule: Rule dict

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        source_type = rule.get('sourceType')
        if not source_type:
            errors.append("VERIFY rule missing sourceType")
            return ValidationResult(False, errors, warnings)

        # Find matching schema
        schema = self.schema_lookup.find_by_action_and_source('VERIFY', source_type)
        if not schema:
            warnings.append(f"No schema found for VERIFY with source {source_type}")
            return ValidationResult(True, errors, warnings)

        # Check destinationIds length
        expected_length = schema.num_destination_items
        actual_length = len(rule.get('destinationIds', []))

        if actual_length != expected_length and actual_length > 0:
            errors.append(
                f"destinationIds length mismatch: expected {expected_length}, got {actual_length}"
            )

        return ValidationResult(len(errors) == 0, errors, warnings)

    def validate_ocr_rule(self, rule: Dict) -> ValidationResult:
        """
        Validate an OCR rule against its schema.

        Args:
            rule: Rule dict

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        source_type = rule.get('sourceType')
        if not source_type:
            errors.append("OCR rule missing sourceType")
            return ValidationResult(False, errors, warnings)

        # Find matching schema
        schema = self.schema_lookup.find_by_action_and_source('OCR', source_type)
        if not schema:
            warnings.append(f"No schema found for OCR with source {source_type}")

        # OCR rules should have sourceIds (upload field)
        if not rule.get('sourceIds'):
            errors.append("OCR rule missing sourceIds (upload field)")

        return ValidationResult(len(errors) == 0, errors, warnings)


class ExtractionValidator:
    """Validates extraction results."""

    def validate_extraction_coverage(
        self,
        total_fields: int,
        fields_with_logic: int,
        rules_generated: int,
    ) -> ValidationResult:
        """
        Validate extraction coverage.

        Args:
            total_fields: Total number of fields
            fields_with_logic: Fields that have logic text
            rules_generated: Number of rules generated

        Returns:
            ValidationResult with coverage assessment
        """
        warnings = []

        if fields_with_logic == 0:
            warnings.append("No fields with logic found")
        elif rules_generated == 0:
            warnings.append("No rules were generated")
        else:
            coverage = rules_generated / fields_with_logic
            if coverage < 0.5:
                warnings.append(f"Low rule coverage: {coverage:.1%}")

        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=warnings,
        )

    def validate_no_orphan_rules(
        self,
        rules: List[Dict],
        field_ids: Set[int],
    ) -> ValidationResult:
        """
        Validate that all rules reference existing fields.

        Args:
            rules: List of rule dicts
            field_ids: Set of valid field IDs

        Returns:
            ValidationResult
        """
        errors = []

        for i, rule in enumerate(rules):
            for sid in rule.get('sourceIds', []):
                if sid != -1 and sid not in field_ids:
                    errors.append(f"Rule {i}: Orphan sourceId {sid}")

            for did in rule.get('destinationIds', []):
                if did != -1 and did not in field_ids:
                    errors.append(f"Rule {i}: Orphan destinationId {did}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[],
        )


def validate_generated_rules(
    generated_rules: List[GeneratedRule],
    valid_field_ids: Set[int],
) -> List[str]:
    """
    Simple validation function for generated rules.

    Args:
        generated_rules: List of GeneratedRule objects
        valid_field_ids: Set of valid field IDs

    Returns:
        List of error messages
    """
    errors = []

    for i, rule in enumerate(generated_rules):
        if not rule.action_type:
            errors.append(f"Rule {i}: Missing action_type")

        if not rule.source_ids:
            errors.append(f"Rule {i}: Missing source_ids")

        for sid in rule.source_ids:
            if sid != -1 and sid not in valid_field_ids:
                errors.append(f"Rule {i}: Invalid source_id {sid}")

        for did in rule.destination_ids:
            if did != -1 and did not in valid_field_ids:
                errors.append(f"Rule {i}: Invalid destination_id {did}")

    return errors
