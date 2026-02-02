#!/usr/bin/env python3
"""
Rule Extraction Agent - Main Entry Point

Automatically extracts rules from BUD logic/rules sections and populates formFillRules arrays.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main

if __name__ == '__main__':
    main()
