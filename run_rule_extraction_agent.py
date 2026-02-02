#!/usr/bin/env python3
"""Run the rule extraction agent."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rule_extraction_agent.main import main

if __name__ == '__main__':
    main()
