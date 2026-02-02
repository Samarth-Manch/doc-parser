#!/usr/bin/env python3
"""
Expression Rule Converter

Converts EXECUTE rules with expression-based conditional values into standard rules
like MAKE_VISIBLE, MAKE_INVISIBLE, MAKE_MANDATORY, etc.

Supported expression functions:
- mvi() / makeVisible() -> MAKE_VISIBLE
- minvi() / makeInvisible() -> MAKE_INVISIBLE
- mm() / makeMandatory() -> MAKE_MANDATORY
- mnm() / makeNonMandatory() -> MAKE_NON_MANDATORY
- dis() / disable() -> MAKE_DISABLED
- en() / enable() -> MAKE_ENABLED
- touc() / toUpperCase() -> CONVERT_TO (UPPER_CASE)
- tolc() / toLowerCase() -> CONVERT_TO (LOWER_CASE)

NOT supported (session-based - these are different):
- sbmvi() / sessionBasedMakeVisible()
- sbminvi() / sessionBasedMakeInvisible()

Expression syntax:
- Multiple rules separated by ';'
- Function format: functionName(condition, destIds...)
- Conditions can be: true, vo("_varName_") == "value", complex expressions
- destIds are variable names like "_fieldVar_"
"""

import re
import json
import copy
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedFunction:
    """A parsed expression function call."""
    function_name: str
    condition: str
    dest_ids: List[str]  # Variable names
    raw_expression: str

    # For toUpperCase/toLowerCase, we need source value
    source_value: Optional[str] = None


@dataclass
class ConvertedRule:
    """A converted standard rule."""
    action_type: str
    source_ids: List[int]
    destination_ids: List[int]
    conditional_values: List[str]
    condition: str  # IN, NOT_IN, etc.
    condition_value_type: str  # TEXT
    params: Optional[str] = None


class ExpressionRuleConverter:
    """
    Converts EXECUTE rules with expressions to standard predefined rules.

    Usage:
        converter = ExpressionRuleConverter()
        converted_json = converter.convert(input_json)
    """

    # Mapping from expression function to action type
    FUNCTION_TO_ACTION = {
        # Make Visible
        "mvi": "MAKE_VISIBLE",
        "makevisible": "MAKE_VISIBLE",
        # Make Invisible
        "minvi": "MAKE_INVISIBLE",
        "makeinvisible": "MAKE_INVISIBLE",
        # Make Mandatory
        "mm": "MAKE_MANDATORY",
        "makemandatory": "MAKE_MANDATORY",
        # Make Non-Mandatory
        "mnm": "MAKE_NON_MANDATORY",
        "makenonmandatory": "MAKE_NON_MANDATORY",
        # Disable
        "dis": "MAKE_DISABLED",
        "disable": "MAKE_DISABLED",
        # Enable
        "en": "MAKE_ENABLED",
        "enable": "MAKE_ENABLED",
        # To Upper Case
        "touc": "CONVERT_TO",
        "touppercase": "CONVERT_TO",
        # To Lower Case
        "tolc": "CONVERT_TO",
        "tolowercase": "CONVERT_TO",
    }

    # Session-based functions to skip (not supported)
    SESSION_BASED_FUNCTIONS = {
        "sbmvi", "sessionbasedmakevisible",
        "sbminvi", "sessionbasedmakeinvisible",
    }

    def __init__(self):
        self.variable_to_id: Dict[str, int] = {}
        self.id_to_variable: Dict[int, str] = {}
        self.next_rule_id: int = 1000000  # Start with a high number to avoid conflicts
        self.conversion_report: List[Dict[str, Any]] = []

    def build_variable_mapping(self, data: Dict[str, Any]) -> None:
        """
        Build mapping from variableName to field ID.

        Args:
            data: The JSON data containing formFillMetadatas
        """
        self.variable_to_id = {}
        self.id_to_variable = {}

        # Handle both with and without template wrapper
        template = data.get("template", data)
        document_types = template.get("documentTypes", [])

        for doc_type in document_types:
            fields = doc_type.get("formFillMetadatas", [])
            for field in fields:
                field_id = field.get("id")
                var_name = field.get("variableName", "")

                if field_id and var_name:
                    self.variable_to_id[var_name] = field_id
                    self.id_to_variable[field_id] = var_name

    def resolve_variable_to_id(self, var_name: str) -> Optional[int]:
        """
        Resolve a variable name to its field ID.

        Args:
            var_name: Variable name like "_fieldVar_"

        Returns:
            Field ID or None if not found
        """
        # Clean up the variable name (remove quotes if present)
        var_name = var_name.strip().strip('"').strip("'")
        return self.variable_to_id.get(var_name)

    def parse_function_call(self, expr: str) -> Optional[ParsedFunction]:
        """
        Parse a single function call from an expression.

        Args:
            expr: Expression like 'mvi(vo("_field_") == "Yes", "_dest1_", "_dest2_")'

        Returns:
            ParsedFunction or None if cannot parse
        """
        expr = expr.strip()
        if not expr:
            return None

        # Match function name and arguments
        # Pattern: functionName(...)
        match = re.match(r'^(\w+)\s*\((.*)\)$', expr, re.DOTALL)
        if not match:
            return None

        func_name = match.group(1).lower()
        args_str = match.group(2).strip()

        # Check if this is a supported function
        if func_name in self.SESSION_BASED_FUNCTIONS:
            # Skip session-based functions
            return None

        if func_name not in self.FUNCTION_TO_ACTION:
            # Not a supported function
            return None

        # Parse arguments - this is tricky due to nested parentheses
        args = self._parse_arguments(args_str)

        if len(args) < 2:
            # Need at least condition and one destination
            return None

        condition = args[0].strip()
        dest_vars = [arg.strip().strip('"').strip("'") for arg in args[1:]]

        # Handle toUpperCase/toLowerCase differently
        if func_name in ("touc", "touppercase", "tolc", "tolowercase"):
            # Format: touc(vo(123)) or touc(vo("_var_"))
            # The first arg is the source value
            return ParsedFunction(
                function_name=func_name,
                condition="true",  # Always execute
                dest_ids=[],
                raw_expression=expr,
                source_value=condition
            )

        return ParsedFunction(
            function_name=func_name,
            condition=condition,
            dest_ids=dest_vars,
            raw_expression=expr
        )

    def _parse_arguments(self, args_str: str) -> List[str]:
        """
        Parse comma-separated arguments handling nested parentheses and quotes.

        Args:
            args_str: Arguments string like 'vo("_f_") == "Yes", "_d1_", "_d2_"'

        Returns:
            List of argument strings
        """
        args = []
        current_arg = []
        paren_depth = 0
        in_string = False
        string_char = None

        i = 0
        while i < len(args_str):
            char = args_str[i]

            # Handle string boundaries
            if char in ('"', "'") and (i == 0 or args_str[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                current_arg.append(char)
            elif in_string:
                current_arg.append(char)
            elif char == '(':
                paren_depth += 1
                current_arg.append(char)
            elif char == ')':
                paren_depth -= 1
                current_arg.append(char)
            elif char == ',' and paren_depth == 0:
                # Argument separator
                args.append(''.join(current_arg).strip())
                current_arg = []
            else:
                current_arg.append(char)

            i += 1

        # Don't forget the last argument
        if current_arg:
            args.append(''.join(current_arg).strip())

        return args

    def parse_condition(self, condition: str) -> Tuple[Optional[int], List[str], str]:
        """
        Parse a condition expression to extract source field and values.

        Args:
            condition: Condition like 'vo("_field_") == "Yes"' or 'true'

        Returns:
            Tuple of (source_field_id, conditional_values, condition_type)
            condition_type is "IN" for ==, "NOT_IN" for !=
        """
        condition = condition.strip()

        # Handle boolean true/false
        if condition.lower() in ('true', '1'):
            return None, [], "TRUE"
        if condition.lower() in ('false', '0'):
            return None, [], "FALSE"

        # Try to extract vo("_var_") == "value" or vo("_var_") != "value"
        # Pattern: vo("_varName_") == "value"
        eq_pattern = r'vo\s*\(\s*["\']([^"\']+)["\']\s*\)\s*==\s*["\']([^"\']+)["\']'
        neq_pattern = r'vo\s*\(\s*["\']([^"\']+)["\']\s*\)\s*!=\s*["\']([^"\']+)["\']'

        eq_match = re.search(eq_pattern, condition)
        neq_match = re.search(neq_pattern, condition)

        if eq_match:
            var_name = eq_match.group(1)
            value = eq_match.group(2)
            source_id = self.resolve_variable_to_id(var_name)
            return source_id, [value], "IN"

        if neq_match:
            var_name = neq_match.group(1)
            value = neq_match.group(2)
            source_id = self.resolve_variable_to_id(var_name)
            return source_id, [value], "NOT_IN"

        # Complex condition - return as-is with no specific source
        return None, [], "COMPLEX"

    def split_expressions(self, expr_str: str) -> List[str]:
        """
        Split an expression string by semicolons, handling nested parens/quotes.

        Args:
            expr_str: Expression string with multiple statements separated by ';'

        Returns:
            List of individual expressions
        """
        expressions = []
        current_expr = []
        paren_depth = 0
        in_string = False
        string_char = None

        for i, char in enumerate(expr_str):
            # Handle string boundaries
            if char in ('"', "'") and (i == 0 or expr_str[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                current_expr.append(char)
            elif in_string:
                current_expr.append(char)
            elif char == '(':
                paren_depth += 1
                current_expr.append(char)
            elif char == ')':
                paren_depth -= 1
                current_expr.append(char)
            elif char == ';' and paren_depth == 0:
                # Expression separator
                expr = ''.join(current_expr).strip()
                if expr:
                    expressions.append(expr)
                current_expr = []
            else:
                current_expr.append(char)

        # Don't forget the last expression
        if current_expr:
            expr = ''.join(current_expr).strip()
            if expr:
                expressions.append(expr)

        return expressions

    def strip_wrapper(self, expr_str: str) -> str:
        """
        Strip the on("load") and (po() == X) and (...) wrapper if present.

        Args:
            expr_str: Expression string that may have wrapper

        Returns:
            Inner expression without wrapper
        """
        expr_str = expr_str.strip()

        # Pattern: on("load") and (po() == X) and (...)
        # We want to extract the ... part
        wrapper_pattern = r'^on\s*\(\s*["\']load["\']\s*\)\s+and\s+\(\s*po\s*\(\s*\)\s*==\s*\d+\s*\)\s+and\s+\((.*)\)$'
        match = re.match(wrapper_pattern, expr_str, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return expr_str

    def convert_function_to_rule(
        self,
        func: ParsedFunction,
        original_rule: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a parsed function to a standard rule.

        Args:
            func: ParsedFunction object
            original_rule: Original EXECUTE rule for copying common fields

        Returns:
            Converted rule dictionary or None if conversion failed
        """
        action_type = self.FUNCTION_TO_ACTION.get(func.function_name)
        if not action_type:
            return None

        # Parse the condition to get source field and values
        source_id, conditional_values, condition_type = self.parse_condition(func.condition)

        # Resolve destination variable names to IDs
        dest_ids = []
        for var_name in func.dest_ids:
            field_id = self.resolve_variable_to_id(var_name)
            if field_id:
                dest_ids.append(field_id)
            else:
                # Log warning but continue
                self.conversion_report.append({
                    "warning": f"Could not resolve variable '{var_name}' to field ID",
                    "expression": func.raw_expression
                })

        if not dest_ids and action_type not in ("CONVERT_TO",):
            # No valid destinations
            return None

        # Handle unconditional rules (condition is true)
        if condition_type == "TRUE":
            # Use the original source as source, and apply to all destinations
            source_ids = original_rule.get("sourceIds", [])
            conditional_values = []
            condition = "IN"  # Will always match
        elif condition_type == "COMPLEX":
            # Complex condition - cannot convert automatically
            self.conversion_report.append({
                "warning": f"Complex condition cannot be auto-converted",
                "expression": func.raw_expression,
                "condition": func.condition
            })
            return None
        else:
            # Simple condition
            source_ids = [source_id] if source_id else original_rule.get("sourceIds", [])
            condition = condition_type

        # Build the new rule
        new_rule = {
            "id": self.next_rule_id,
            "createUser": original_rule.get("createUser", "FIRST_PARTY"),
            "updateUser": original_rule.get("updateUser", "FIRST_PARTY"),
            "actionType": action_type,
            "processingType": original_rule.get("processingType", "CLIENT"),
            "sourceIds": source_ids,
            "destinationIds": dest_ids,
            "conditionalValues": conditional_values,
            "condition": condition,
            "conditionValueType": "TEXT",
            "postTriggerRuleIds": [],
            "button": "",
            "searchable": False,
            "executeOnFill": original_rule.get("executeOnFill", True),
            "executeOnRead": original_rule.get("executeOnRead", False),
            "executeOnEsign": original_rule.get("executeOnEsign", False),
            "executePostEsign": original_rule.get("executePostEsign", False),
            "runPostConditionFail": original_rule.get("runPostConditionFail", False),
        }

        # Handle CONVERT_TO specific params
        if action_type == "CONVERT_TO":
            if func.function_name in ("touc", "touppercase"):
                new_rule["params"] = "UPPER_CASE"
            elif func.function_name in ("tolc", "tolowercase"):
                new_rule["params"] = "LOWER_CASE"

        self.next_rule_id += 1
        return new_rule

    def convert_execute_rule(
        self,
        rule: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Convert a single EXECUTE rule to multiple standard rules.

        Args:
            rule: EXECUTE rule dictionary

        Returns:
            List of converted rules
        """
        # Check if this is an EXECUTE rule with EXPR condition
        if rule.get("actionType") != "EXECUTE":
            return [rule]

        if rule.get("conditionValueType") != "EXPR":
            return [rule]

        conditional_values = rule.get("conditionalValues", [])
        if not conditional_values:
            return [rule]

        converted_rules = []

        for expr_str in conditional_values:
            # Strip wrapper if present
            inner_expr = self.strip_wrapper(expr_str)

            # Split by semicolons
            expressions = self.split_expressions(inner_expr)

            for expr in expressions:
                # Parse the function call
                func = self.parse_function_call(expr)

                if func:
                    # Convert to standard rule
                    new_rule = self.convert_function_to_rule(func, rule)
                    if new_rule:
                        converted_rules.append(new_rule)
                        self.conversion_report.append({
                            "success": True,
                            "original_expression": expr,
                            "converted_action_type": new_rule["actionType"],
                            "rule_id": new_rule["id"]
                        })
                    else:
                        self.conversion_report.append({
                            "warning": "Failed to convert function to rule",
                            "expression": expr
                        })
                else:
                    # Could not parse - might be unsupported function
                    self.conversion_report.append({
                        "info": "Expression not converted (unsupported or session-based)",
                        "expression": expr
                    })

        # If no rules were converted, keep the original
        if not converted_rules:
            return [rule]

        return converted_rules

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert all EXECUTE rules in the JSON to standard rules.

        Args:
            data: Input JSON data

        Returns:
            Converted JSON data with EXECUTE rules replaced
        """
        # Make a deep copy to avoid modifying original
        result = copy.deepcopy(data)

        # Build variable to ID mapping
        self.build_variable_mapping(result)

        # Reset conversion report
        self.conversion_report = []

        # Handle both with and without template wrapper
        template = result.get("template", result)
        document_types = template.get("documentTypes", [])

        total_execute_rules = 0
        total_converted_rules = 0

        for doc_type in document_types:
            fields = doc_type.get("formFillMetadatas", [])

            for field in fields:
                rules = field.get("formFillRules", [])
                new_rules = []

                for rule in rules:
                    if rule.get("actionType") == "EXECUTE" and rule.get("conditionValueType") == "EXPR":
                        total_execute_rules += 1
                        converted = self.convert_execute_rule(rule)
                        new_rules.extend(converted)
                        total_converted_rules += len([r for r in converted if r.get("actionType") != "EXECUTE"])
                    else:
                        new_rules.append(rule)

                field["formFillRules"] = new_rules

        # Add conversion summary to report
        self.conversion_report.insert(0, {
            "summary": {
                "total_execute_rules_found": total_execute_rules,
                "total_rules_converted": total_converted_rules,
                "variable_mappings_built": len(self.variable_to_id)
            }
        })

        return result

    def get_conversion_report(self) -> List[Dict[str, Any]]:
        """Get the conversion report from the last conversion."""
        return self.conversion_report


def convert_execute_rules(
    input_path: str,
    output_path: Optional[str] = None,
    report_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to convert EXECUTE rules in a JSON file.

    Args:
        input_path: Path to input JSON file
        output_path: Optional path to save converted JSON
        report_path: Optional path to save conversion report

    Returns:
        Converted JSON data
    """
    # Load input
    with open(input_path, 'r') as f:
        data = json.load(f)

    # Convert
    converter = ExpressionRuleConverter()
    result = converter.convert(data)

    # Save output if path provided
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)

    # Save report if path provided
    if report_path:
        with open(report_path, 'w') as f:
            json.dump(converter.get_conversion_report(), f, indent=2)

    return result


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert EXECUTE rules with expressions to standard rules"
    )
    parser.add_argument(
        "input",
        help="Path to input JSON file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to save converted JSON (default: stdout)"
    )
    parser.add_argument(
        "-r", "--report",
        help="Path to save conversion report"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output"
    )

    args = parser.parse_args()

    # Load and convert
    with open(args.input, 'r') as f:
        data = json.load(f)

    converter = ExpressionRuleConverter()
    result = converter.convert(data)
    report = converter.get_conversion_report()

    # Print summary
    if args.verbose:
        summary = report[0].get("summary", {})
        print(f"Execute rules found: {summary.get('total_execute_rules_found', 0)}")
        print(f"Rules converted: {summary.get('total_rules_converted', 0)}")
        print(f"Variable mappings: {summary.get('variable_mappings_built', 0)}")
        print()

    # Save or print output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Converted JSON saved to: {args.output}")
    else:
        if not args.verbose:
            print(json.dumps(result, indent=2))

    # Save report
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Conversion report saved to: {args.report}")


if __name__ == "__main__":
    main()
