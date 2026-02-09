"""
Dispatchers for mini agents

These dispatchers:
1. Do initial deterministic processing (keyword matching, pattern detection)
2. Prepare focused chunks of data
3. Call specialized mini agents via claude -p
4. Merge results into final output
"""
