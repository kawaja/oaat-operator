#!/usr/bin/env python3
"""
Test runner script that ensures pykube mocking is applied before running pytest.
"""

import sys
import os

# Add unit tests directory to path
sys.path.insert(0, '/home/runner/oaat-operator/tests/unit')

# Import early mocking BEFORE pytest or any test modules
print("Importing early pykube mocking...")
import early_pykube_mock
print("Early mocking applied, now running pytest...")

# Now run pytest
import pytest
sys.exit(pytest.main(sys.argv[1:]))