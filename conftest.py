import pytest

# Minimal conftest.py - mocking is handled by the unit test runner only
# Integration tests use real Kubernetes API calls without any mocking


@pytest.fixture(scope='session')
def mock_pykube_components():
    """Provide access to mock pykube components when available."""
    # Only return mock components if they've been explicitly set up by the test runner
    # Integration tests won't have these available, which is correct
    try:
        import early_pykube_mock
        # Only return mock objects if patches have already been applied
        # This prevents automatic mocking for integration tests
        if hasattr(early_pykube_mock, '_patches_applied') and early_pykube_mock._patches_applied:
            return early_pykube_mock._mock_objects
        else:
            return None
    except (ImportError, AttributeError):
        return None
