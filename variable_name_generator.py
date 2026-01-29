"""
Utility to generate unique variable names for fields in the format __fieldname__, __fieldname2__, etc.
"""

import re
from typing import List, Dict
from doc_parser.models import FieldDefinition


class VariableNameGenerator:
    """Generates unique alphanumeric variable names for fields."""

    def __init__(self):
        self.name_counts: Dict[str, int] = {}
        self.used_names: set = set()

    def generate_variable_name(self, field_name: str) -> str:
        """
        Generate a variable name from field name.

        Examples:
            PAN Number -> __pan__
            GST Number -> __gst__
            Mobile Number -> __mobile__
            PAN Number (second occurrence) -> __pan2__
        """
        # Convert to lowercase and remove special characters
        clean_name = field_name.lower()

        # Remove common suffixes
        clean_name = re.sub(r'\s*(number|no|id|name|code|type|value)\s*$', '', clean_name, flags=re.IGNORECASE)

        # Keep only alphanumeric and spaces
        clean_name = re.sub(r'[^a-z0-9\s]', '', clean_name)

        # Remove extra spaces and replace with underscore
        clean_name = '_'.join(clean_name.split())

        # Limit length (take first meaningful word if too long)
        if len(clean_name) > 20:
            words = clean_name.split('_')
            # Try to find the most meaningful word (usually the first significant one)
            for word in words:
                if len(word) > 3:  # Skip very short words like "is", "of", etc.
                    clean_name = word
                    break
            else:
                clean_name = words[0]  # Fallback to first word

        # Remove trailing/leading underscores
        clean_name = clean_name.strip('_')

        # If empty after cleaning, use generic name
        if not clean_name:
            clean_name = 'field'

        # Track count for this base name
        if clean_name not in self.name_counts:
            self.name_counts[clean_name] = 1
            variable_name = f"__{clean_name}__"
        else:
            self.name_counts[clean_name] += 1
            variable_name = f"__{clean_name}{self.name_counts[clean_name]}__"

        self.used_names.add(variable_name)
        return variable_name

    def generate_for_fields(self, fields: List[FieldDefinition]) -> None:
        """Generate and assign variable names to all fields in place."""
        for field in fields:
            if not field.variable_name:  # Only generate if not already set
                field.variable_name = self.generate_variable_name(field.name)

    def reset(self):
        """Reset the generator state."""
        self.name_counts.clear()
        self.used_names.clear()


def generate_variable_names(fields: List[FieldDefinition]) -> None:
    """
    Convenience function to generate variable names for a list of fields.

    Args:
        fields: List of FieldDefinition objects to assign variable names to
    """
    generator = VariableNameGenerator()
    generator.generate_for_fields(fields)
