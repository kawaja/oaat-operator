import pytest
import sys
import os

# Only apply early mocking in CI environments or when kubeconfig is missing
def _should_apply_early_mocking():
    return (
        os.getenv('CI') == 'true' or 
        os.getenv('GITHUB_ACTIONS') == 'true' or
        not os.path.exists(os.path.expanduser('~/.kube/config'))
    )

# Apply early mocking only when needed (Docker/CI environments)
if _should_apply_early_mocking():
    early_mock_path = os.path.join(os.path.dirname(__file__), 'tests', 'unit')
    sys.path.insert(0, early_mock_path)
    import early_pykube_mock
    
    # pytest hooks for cleanup
    def pytest_sessionfinish(session, exitstatus):
        """Called after whole test run finished."""
        early_pykube_mock.cleanup_patches()
    
    # Session fixture for tests that need access to mock objects
    @pytest.fixture(scope='session')
    def mock_pykube_components():
        """Provide access to mock pykube components for tests that need them."""
        return early_pykube_mock.get_mock_objects()
else:
    # In local environments, rely on existing mocking in tests/unit/mocks_pykube.py
    @pytest.fixture(scope='session')
    def mock_pykube_components():
        """No early mocking needed in local environment."""
        return None