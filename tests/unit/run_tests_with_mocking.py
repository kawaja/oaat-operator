#!/usr/bin/env python3
"""
Unified test runner script that ensures pykube mocking is applied before running pytest.
Works in both local and Docker environments.
"""

import sys
import os

# Determine the correct path to the unit tests directory
script_dir = os.path.dirname(os.path.abspath(__file__))
unit_tests_dir = script_dir  # This script is in tests/unit/

# Add unit tests directory to path
sys.path.insert(0, unit_tests_dir)

# Import early mocking BEFORE pytest or any test modules
print("Importing unified pykube mocking...")
import early_pykube_mock
early_pykube_mock.apply_mocking()
print("Early mocking applied, now running pytest...")

# Now run pytest
import pytest
sys.exit(pytest.main(sys.argv[1:]))
