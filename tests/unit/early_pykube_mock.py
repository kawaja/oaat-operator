"""
Conditional pykube mocking module for unit tests.

This module provides mocking functionality that is applied only when explicitly requested.
This prevents integration tests from being affected by the mocking.
"""

import os
import sys
from unittest.mock import Mock, patch
import pykube

# Global variables to store patches and mock objects
_active_patches = []
_mock_objects = None
_patches_applied = False
_original_http_client = pykube.HTTPClient


def apply_mocking():
    """Apply pykube mocking patches. Call this explicitly when needed."""
    global _active_patches, _mock_objects, _patches_applied

    if _patches_applied:
        return  # Already applied

    print("[early_pykube_mock] Applying unified pykube mocking for unit tests")

    # Create mock objects
    mock_config = Mock()
    mock_config.api = {'server': 'https://mock-k8s-server'}
    mock_config.namespace = 'default'

    mock_client = Mock(spec=_original_http_client)
    mock_client.config = mock_config
    mock_client.session = Mock()

    # Create a mock query object for Pod objects
    def create_mock_pod_query(*args, **kwargs):
        mock_query = Mock()
        # Create a chainable filter mock

        def mock_filter(*filter_args, **filter_kwargs):
            return mock_query

        mock_query.filter = mock_filter
        # Create iterator that returns empty list by default
        mock_query.iterator = Mock(return_value=iter([]))
        return mock_query

    # Create a mock query object for other Kubernetes objects (like KubeOaatType)
    def create_mock_kube_objects_query(*args, **kwargs):
        mock_query = Mock()

        # Mock get_by_name to raise ObjectDoesNotExist for non-existent objects
        def mock_get_by_name(name):
            # For test purposes, any name that isn't explicitly mocked will raise ObjectDoesNotExist
            # The KubeObject context manager will override this behavior for objects that should exist
            raise pykube.exceptions.ObjectDoesNotExist(f"{name} does not exist.")

        mock_query.get_by_name = mock_get_by_name
        return mock_query

    # Create patches
    patch_from_env = patch('pykube.KubeConfig.from_env', return_value=mock_config)
    patch_from_file = patch('pykube.KubeConfig.from_file', return_value=mock_config)
    patch_from_sa = patch('pykube.KubeConfig.from_service_account', return_value=mock_config)
    patch_http_client = patch('pykube.HTTPClient', return_value=mock_client)
    patch_pod_objects = patch('pykube.Pod.objects', side_effect=create_mock_pod_query)

    # Import KubeOaatType and patch its objects method
    # Add the parent directory to sys.path so we can import oaatoperator
    if '/home/runner/oaat-operator' not in sys.path:
        sys.path.insert(0, '/home/runner/oaat-operator')
    if os.path.dirname(os.path.dirname(os.path.dirname(__file__))) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from oaatoperator.common import KubeOaatType
    patch_oaattype_objects = patch.object(KubeOaatType, 'objects', side_effect=create_mock_kube_objects_query)

    # Start patches
    patch_from_env.start()
    patch_from_file.start()
    patch_from_sa.start()
    patch_http_client.start()
    patch_pod_objects.start()
    patch_oaattype_objects.start()

    print("[early_pykube_mock] pykube mocking applied successfully")

    # Store references to prevent garbage collection
    _active_patches = [
        patch_from_env, patch_from_file, patch_from_sa,
        patch_http_client, patch_pod_objects, patch_oaattype_objects
    ]
    _mock_objects = {'config': mock_config, 'client': mock_client}
    _patches_applied = True


def get_mock_objects():
    """Return mock objects for tests that need them."""
    if not _patches_applied:
        apply_mocking()
    return _mock_objects


def cleanup_patches():
    """Clean up patches (called by conftest.py on session finish)."""
    global _patches_applied
    for patch_obj in _active_patches:
        patch_obj.stop()
    _active_patches.clear()
    _patches_applied = False
