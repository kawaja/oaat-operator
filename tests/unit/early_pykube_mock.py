"""
Unified pykube mocking module for all unit tests.

This module applies pykube patches immediately upon import, before any
test modules can import oaatoperator code and trigger real pykube calls.

This ensures consistent test behavior in all environments (local and Docker)
without depending on kubeconfig files.
"""

import os
from unittest.mock import Mock, patch

# Always apply mocking for unit tests - no environment dependency
print("[early_pykube_mock] Applying unified pykube mocking for unit tests")

# Import pykube to get access to the classes
import pykube

# Store the original HTTPClient class before we patch it
_original_http_client = pykube.HTTPClient

# Create mock objects
mock_config = Mock()
mock_config.api = {'server': 'https://mock-k8s-server'}
mock_config.namespace = 'default'

mock_client = Mock(spec=_original_http_client)
mock_client.config = mock_config
mock_client.session = Mock()

# Create a mock query object that returns empty results by default
def create_mock_pod_query(*args, **kwargs):
    mock_query = Mock()
    # Create a chainable filter mock
    def mock_filter(*filter_args, **filter_kwargs):
        return mock_query
    mock_query.filter = mock_filter
    # Create iterator that returns empty list by default
    mock_query.iterator = Mock(return_value=iter([]))
    return mock_query

# Create patches
_patch_from_env = patch('pykube.KubeConfig.from_env', return_value=mock_config)
_patch_from_file = patch('pykube.KubeConfig.from_file', return_value=mock_config)
_patch_from_sa = patch('pykube.KubeConfig.from_service_account', return_value=mock_config)
_patch_http_client = patch('pykube.HTTPClient', return_value=mock_client)
_patch_pod_objects = patch('pykube.Pod.objects', side_effect=create_mock_pod_query)

# Start patches immediately
_patch_from_env.start()
_patch_from_file.start()
_patch_from_sa.start()
_patch_http_client.start()
_patch_pod_objects.start()

print("[early_pykube_mock] pykube mocking applied successfully")

# Store references to prevent garbage collection
_active_patches = [_patch_from_env, _patch_from_file, _patch_from_sa, _patch_http_client, _patch_pod_objects]
_mock_objects = {'config': mock_config, 'client': mock_client}


def get_mock_objects():
    """Return mock objects for tests that need them."""
    return _mock_objects


def cleanup_patches():
    """Clean up patches (called by conftest.py on session finish)."""
    for patch_obj in _active_patches:
        patch_obj.stop()
    _active_patches.clear()