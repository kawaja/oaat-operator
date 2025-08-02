"""Integration tests for OaatType class requiring k3d cluster."""
import unittest
import pytest
import pykube
from pykube.query import Query

from tests.unit.mocks_pykube import ensure_kubeobj_deleted
from oaatoperator.common import KubeOaatType


pytestmark = pytest.mark.integration


class MiniKubeTests(unittest.TestCase):
    """Integration tests that require a real Kubernetes cluster."""

    def test_pod_objects(self):
        """Test real pykube Pod.objects() query functionality."""
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        pod = pykube.Pod.objects(api)
        self.assertIsInstance(pod, Query)

    def test_pod_create(self):
        """Test real pod creation/deletion in k3d cluster."""
        ensure_kubeobj_deleted(pykube.Pod, 'testpod')
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        newpod = pykube.Pod(api, {
            'metadata': {
                'name': 'testpod'
            },
            'spec': {
                'containers': [
                    {
                        'name': 'testcontainer',
                        'image': 'busybox',
                        'command': ['/bin/sleep', '1000']
                    }
                ]
            }
        })
        newpod.create()
        pod = pykube.Pod.objects(api)
        self.assertIsInstance(pod, Query)
        obj = pod.get_by_name('testpod')
        self.assertIsInstance(obj, pykube.Pod)
        ensure_kubeobj_deleted(pykube.Pod, 'testpod')

    def test_oaattype_objects(self):
        """Test real KubeOaatType.objects() query functionality."""
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        kot = KubeOaatType.objects(api)
        self.assertIsInstance(kot, Query)

    def test_oaattype_query(self):
        """Test real OaatType retrieval from k3d cluster.

        Note: If this test fails, it could be because there is no 'oaattest'
        OaatType loaded. Try: kubectl apply -f manifests/sample-oaat-type.yaml
        """
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        kot = KubeOaatType.objects(api)
        self.assertIsInstance(kot, Query)
        obj = kot.get_by_name('oaattest')
        self.assertIsInstance(obj, KubeOaatType)
