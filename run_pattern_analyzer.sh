#!/bin/bash
# Run the Expression Pattern Analyzer dispatcher
# Analyzes production EXECUTE rules to discover cf/ctfd/asdff/rffdd patterns

cd "$(dirname "$0")"

python3 dispatchers/agents/expression_pattern_analyzer_dispatcher.py \
    --csv "rules/expression_rules_example/Form_FillRule_EXECUTE_DUMP.csv" \
    --output "documentations/expression_function_patterns.md" \
    --batch-size 10 \
    --model opus
