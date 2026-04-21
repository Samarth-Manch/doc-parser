"""
validators/registry.py
Central validator registry and base class.

Every validator inherits from BaseValidator and is registered via
the @ValidatorRegistry.register decorator.  The main pipeline calls
ValidatorRegistry.run_all() and write_all().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from openpyxl import Workbook

from section_parser import BUDDocument


@dataclass
class ValidationContext:
    """All data produced by document_reader.parse_document()."""
    parsed: BUDDocument


class BaseValidator(ABC):
    """Interface every validator must implement."""

    name: str          # human-readable name shown in logs
    sheet_name: str    # Excel sheet title
    description: str = ""  # short description shown in HTML report

    @abstractmethod
    def validate(self, ctx: ValidationContext) -> list:
        """Run the validation and return a list of result dataclasses."""
        ...

    @abstractmethod
    def write_sheet(self, wb: Workbook, results: list) -> None:
        """Write *results* into a new (or the active) sheet of *wb*."""
        ...


class ValidatorRegistry:
    """Maintains an ordered list of registered validators."""

    _validators: list[BaseValidator] = []

    @classmethod
    def register(cls, validator_cls: type[BaseValidator]) -> type[BaseValidator]:
        """Class decorator that instantiates and registers a validator."""
        cls._validators.append(validator_cls())
        return validator_cls

    @classmethod
    def all(cls) -> list[BaseValidator]:
        return list(cls._validators)

    @classmethod
    def run_all(cls, ctx: ValidationContext) -> dict[str, list]:
        """Execute every registered validator and return {name: results}."""
        results: dict[str, list] = {}
        for i, v in enumerate(cls._validators, start=1):
            results[v.name] = v.validate(ctx)
            print(f"Validation {i}: {v.name} -> DONE")
        return results

    @classmethod
    def write_all(cls, wb: Workbook, results: dict[str, list]) -> None:
        """Write one sheet per validator into *wb*."""
        for v in cls._validators:
            v.write_sheet(wb, results[v.name])
