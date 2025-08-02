import pytest
import sys
import os

# Import early pykube mocking BEFORE any other imports that might use pykube
# This ensures pykube is mocked before any test modules try to import oaatoperator
early_mock_path = os.path.join(os.path.dirname(__file__), 'tests')
print(f"[conftest.py] Adding path: {early_mock_path}")
print(f"[conftest.py] Path exists: {os.path.exists(early_mock_path)}")
sys.path.insert(0, early_mock_path)
print(f"[conftest.py] Importing early_pykube_mock...")
import early_pykube_mock
print(f"[conftest.py] early_pykube_mock imported successfully")

# pytest hooks for cleanup
def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished."""
    early_pykube_mock.cleanup_patches()

# Session fixture for tests that need access to mock objects
@pytest.fixture(scope='session')
def mock_pykube_components():
    """Provide access to mock pykube components for tests that need them."""
    return early_pykube_mock.get_mock_objects()