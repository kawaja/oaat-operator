from copy import deepcopy
from typing import Type
import dataclasses

from unittest.mock import Mock, patch
import pytest
import pykube
# import pytest_mock

import pykube

# Global pykube mocking for CI environments without kubeconfig
@pytest.fixture(autouse=True)
def mock_pykube_global():
    """Automatically mock pykube calls for all unit tests to prevent kubeconfig errors.

    This fixture addresses the issue where GitHub Actions and other CI environments
    don't have ~/.kube/config files or environment variables set up for Kubernetes
    authentication. Without this mocking, unit tests would fail with errors like:

    - pykube.KubeConfig.from_env() -> No KUBECONFIG env var
    - pykube.KubeConfig.from_file() -> No ~/.kube/config file
    - pykube.HTTPClient() -> Invalid config object

    The fixture automatically patches all pykube authentication methods to return
    mock objects, ensuring unit tests run successfully in any environment.
    """
    # Mock all KubeConfig methods that would fail in CI environments
    with patch('pykube.KubeConfig.from_env') as mock_from_env, \
         patch('pykube.KubeConfig.from_file') as mock_from_file, \
         patch('pykube.KubeConfig.from_service_account') as mock_from_sa, \
         patch('pykube.HTTPClient') as mock_http_client:

        # Create a mock config object that simulates proper kubeconfig
        mock_config = Mock()
        mock_config.api = {'server': 'https://mock-k8s-server'}
        mock_config.namespace = 'default'

        # All KubeConfig factory methods return the same mock config
        mock_from_env.return_value = mock_config
        mock_from_file.return_value = mock_config
        mock_from_sa.return_value = mock_config

        # Create a mock HTTP client that simulates kubernetes API client
        mock_client = Mock(spec=pykube.HTTPClient)
        mock_client.config = mock_config
        mock_client.session = Mock()
        mock_http_client.return_value = mock_client

        yield {
            'config': mock_config,
            'client': mock_client,
            'from_env': mock_from_env,
            'from_file': mock_from_file,
            'from_service_account': mock_from_sa,
            'http_client': mock_http_client
        }


@dataclasses.dataclass(frozen=True, eq=False, order=False)
class LoginMocks:
    pykube_in_cluster: Mock
    pykube_from_file: Mock


@dataclasses.dataclass(frozen=True, eq=False, order=False)
class KubeOaatTypeMocks:
    pykube_in_cluster: Mock
    pykube_from_file: Mock


@pytest.fixture()
def login_mocks(mocker):
    kwargs = {}
    try:
        import pykube
    except ImportError:
        pass
    else:
        cfg = pykube.KubeConfig({
            'current-context': 'self',
            'clusters': [{
                'name': 'self',
                'cluster': {
                    'server': 'localhost'
                }
            }],
            'contexts': [{
                'name': 'self',
                'context': {
                    'cluster': 'self',
                    'namespace': 'default'
                }
            }],
        })
        kwargs.update(
            pykube_in_cluster=mocker.patch.object(pykube.KubeConfig,
                                                  'from_service_account',
                                                  return_value=cfg),
            pykube_from_file=mocker.patch.object(pykube.KubeConfig,
                                                 'from_file',
                                                 return_value=cfg),
        )
    return LoginMocks(**kwargs)


def ensure_kubeobj_deleted(type, name):
    """Mock version - simulates object deletion without k3d."""
    print(f'[ensure_kubeobj_deleted] mocking deletion check for {name}')
    print(f'[ensure_kubeobj_deleted] {name} does not exist (mocked)')
    print(f'[ensure_kubeobj_deleted] {name} deleted (mocked)')


def ensure_kubeobj_exists(ktype: Type[pykube.objects.APIObject], spec: dict,
                          name: str):
    """Mock version - simulates object creation without k3d."""
    print(f'[ensure_kubeobj_exists] mocking creation of {ktype} {name} with {spec}')
    print(f'[ensure_kubeobj_exists] created {ktype} (mocked)')
    print(f'[ensure_kubeobj_exists] {name} exists (mocked)')
    # Return a mock object that behaves like the real Kubernetes object
    from unittest.mock import Mock
    mock_obj = Mock()
    mock_obj.name = name
    mock_obj.exists.return_value = True
    return mock_obj


class KubeObject:
    """Mock context manager that simulates Kubernetes objects without k3d."""
    def __init__(self, ktype: Type[pykube.objects.APIObject],
                 input_spec: dict):
        self.spec = deepcopy(input_spec)
        self.type = ktype
        self.name = self.spec.get('metadata', {}).get('name', 'unknown')
        if self.name == 'unknown':
            raise ValueError(f'kube object {ktype} is missing name')

    def __enter__(self):
        print(f'[KubeObject] mocking creation of {self.name} ({self.type})')

        # Create a mock Kubernetes object with the same interface
        from unittest.mock import Mock, patch
        mock_obj = Mock(spec=self.type)
        mock_obj.name = self.name
        mock_obj.obj = self.spec
        # Mock metadata with proper dict-like behavior
        metadata_dict = self.spec.get('metadata', {})
        if 'namespace' not in metadata_dict:
            metadata_dict['namespace'] = 'default'
        mock_obj.metadata = metadata_dict
        mock_obj.spec = self.spec.get('spec', {})
        mock_obj.status = self.spec.get('status', {})
        mock_obj.exists.return_value = True
        mock_obj.ready = True
        mock_obj.create.return_value = None
        mock_obj.update.return_value = None
        mock_obj.delete.return_value = None
        mock_obj.reload.return_value = None

        # Mock namespace property - return from metadata or default to 'default'
        namespace = self.spec.get('metadata', {}).get('namespace', 'default')
        mock_obj.namespace = namespace
        # Also provide namespace() method for compatibility
        def mock_namespace_method():
            return namespace
        mock_obj.namespace = mock_namespace_method

        # Mock the .objects().get_by_name() call chain
        mock_objects_query = Mock()
        mock_objects_query.get_by_name.return_value = mock_obj

        # Patch the class to return our mock when .objects() is called
        self.patcher = patch.object(self.type, 'objects', return_value=mock_objects_query)
        self.patcher.start()

        # Note: Global pykube mocking handled by mock_pykube_global fixture

        return mock_obj

    def __exit__(self, exc_type, exc_value, exc_tb):
        print(f'[KubeObject] mocking deletion of {self.name} ({self.type})')
        # Stop patches
        self.patcher.stop()


# Global registry for active pods to support multiple pod mocking
_active_pods = []

class KubeObjectPod:
    """Mock context manager that simulates Pod objects without k3d."""
    _pod_objects_patcher = None

    def __init__(self, input_spec: dict):
        self.spec = deepcopy(input_spec)

    def __enter__(self) -> Mock:
        print('[KubeObjectPod] mocking pod creation')
        # Create a mock Pod object with the same interface
        from unittest.mock import Mock, patch
        mock_pod = Mock(spec=pykube.Pod)
        # Generate unique name, similar to how Kubernetes handles generateName
        base_name = self.spec.get('metadata', {}).get('name',
                   self.spec.get('metadata', {}).get('generateName', 'mock-pod-'))
        if base_name.endswith('-'):
            import uuid
            unique_name = base_name + str(uuid.uuid4())[:8]
        else:
            unique_name = base_name
        mock_pod.name = unique_name
        mock_pod.obj = self.spec
        mock_pod.metadata = self.spec.get('metadata', {})
        mock_pod.spec = self.spec.get('spec', {})
        mock_pod.status = self.spec.get('status', {})
        mock_pod.ready = True
        mock_pod.exists.return_value = True
        mock_pod.create.return_value = None
        mock_pod.update.return_value = None
        mock_pod.delete.return_value = None
        mock_pod.reload.return_value = None

        # Mock labels and ensure status/phase are properly set for pod verification
        mock_pod.labels = self.spec.get('metadata', {}).get('labels', {})
        # Set default 'oaat-name' label if not present
        if 'oaat-name' not in mock_pod.labels:
            mock_pod.labels['oaat-name'] = 'mock-item'

        # Ensure the pod has a Running phase in status for verify_running tests
        if 'status' not in mock_pod.obj:
            mock_pod.obj['status'] = {}
        if 'phase' not in mock_pod.obj['status']:
            mock_pod.obj['status']['phase'] = 'Running'

        # Add this pod to the global registry
        _active_pods.append(mock_pod)
        self.mock_pod = mock_pod

        # Create a mock query that properly filters pods by labels
        def get_mock_query(*args, **kwargs):
            mock_query = Mock()

            # Keep track of filter criteria
            class MockFilteredQuery:
                def __init__(self):
                    self.namespace_filter = None
                    self.selector_filter = {}

                def filter(self, namespace=None, selector=None):
                    if namespace is not None:
                        self.namespace_filter = namespace
                    if selector is not None:
                        self.selector_filter.update(selector)
                    return self

                def iterator(self):
                    # Filter active pods based on the selector criteria
                    filtered_pods = []
                    for pod in _active_pods:
                        pod_labels = pod.labels
                        # Check if pod matches all selector criteria
                        matches = True
                        for key, value in self.selector_filter.items():
                            if key not in pod_labels or pod_labels[key] != value:
                                matches = False
                                break
                        if matches:
                            filtered_pods.append(pod)
                    return filtered_pods

            mock_filtered_query = MockFilteredQuery()
            mock_query.filter.return_value = mock_filtered_query
            return mock_query

        # Patch pykube.Pod.objects to return our mock query - only patch once
        if not hasattr(KubeObjectPod, '_pod_objects_patcher') or not KubeObjectPod._pod_objects_patcher:
            KubeObjectPod._pod_objects_patcher = patch.object(pykube.Pod, 'objects', side_effect=get_mock_query)
            KubeObjectPod._pod_objects_patcher.start()

        return mock_pod

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        print('[KubeObjectPod] mocking pod deletion')
        # Remove this pod from the global registry
        if self.mock_pod in _active_pods:
            _active_pods.remove(self.mock_pod)

        # Stop the Pod.objects patch only when no pods are active
        if not _active_pods and hasattr(KubeObjectPod, '_pod_objects_patcher') and KubeObjectPod._pod_objects_patcher:
            KubeObjectPod._pod_objects_patcher.stop()
            KubeObjectPod._pod_objects_patcher = None
