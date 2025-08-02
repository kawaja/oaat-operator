import pytest

# Simplified conftest.py - mocking is now handled by the unified test runner
# This ensures consistent behavior across all environments

@pytest.fixture(scope='session')
def mock_pykube_components():
    """Provide access to mock pykube components for tests that need them."""
    # Mock objects are set up by the test runner before pytest starts
    try:
        import early_pykube_mock
        return early_pykube_mock.get_mock_objects()
    except ImportError:
        return None