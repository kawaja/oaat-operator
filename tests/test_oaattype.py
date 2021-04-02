import unittest
from copy import deepcopy

from tests.mocks_pykube import ensure_kubeobj_deleted
import oaatoperator.oaattype
from oaatoperator.common import KubeOaatType, ProcessingComplete
import pykube
from pykube.query import Query

# TODO: This expects a kubernetes cluster (like minikube). It would be better
# to use a mocking library to handle unit testing locally.


class BasicTests(unittest.TestCase):
    header = {
        'apiVersion': 'kawaja.net/v1',
        'kind': 'OaatType',
        'metadata': {
            'name': 'test-kot'
        }
    }

    kot_spec = {
        'podspec': {
            'container': {
                'name': 'test',
                'image': 'busybox',
                'command': ['sh', '-x', '-c'],
                'args': [
                    'echo "OAAT_ITEM={{oaat_item}}"\n'
                    'sleep $(shuf -i 10-180 -n 1)\nexit $(shuf -i 0-1 -n 1)\n'
                ],
            }
        }
    }

    kot_notype = {**header, 'spec': {**kot_spec}}
    kot = {**header, 'spec': {**kot_spec, 'type': 'pod'}}
    kot_nospec = {**header}
    kot_nocontainer = {
        **header, 'spec': {'type': 'pod', 'podspec': {'something': 1}}
    }
    kot_containers = {
        **header, 'spec': {'type': 'pod', 'podspec': {'containers': 1}}
    }
    kot_restartPolicy = deepcopy(kot)
    kot_restartPolicy['spec']['podspec']['restartPolicy'] = 'Always'

    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def tearDown(self):
        return super().tearDown()

    def test_invalid_none_podspec(self):
        with self.assertRaises(ProcessingComplete):
            oaatoperator.oaattype.podspec({}, 'test-kot')

    def test_podspec_nospec(self):
        with self.assertRaises(ProcessingComplete) as exc:
            oaatoperator.oaattype.podspec(BasicTests.kot_nospec,
                    name='test-kot')
        self.assertEqual(exc.exception.ret['error'],
                'missing spec in OaatType definition')

    def test_podspec_nocontainer(self):
        with self.assertRaises(ProcessingComplete) as exc:
            oaatoperator.oaattype.podspec(
                    BasicTests.kot_nocontainer, name='test-kot')
        self.assertEqual(exc.exception.ret['error'],
                'spec.podspec.container is missing')

    def test_podspec_containers(self):
        with self.assertRaises(ProcessingComplete) as exc:
            oaatoperator.oaattype.podspec(
                BasicTests.kot_containers, name='test-kot')
        self.assertRegex(exc.exception.ret['error'],
                         'currently only support a single container.*')

    def test_podspec_restartPolicy(self):
        with self.assertRaises(ProcessingComplete) as exc:
            oaatoperator.oaattype.podspec(
                BasicTests.kot_restartPolicy, name='test-kot')
        self.assertRegex(exc.exception.ret['error'],
                         '.*you cannot specify a restartPolicy')

    def test_podspec_without_type(self):
        with self.assertRaises(ProcessingComplete) as exc:
            oaatoperator.oaattype.podspec(
                BasicTests.kot_notype, name='test-kot')
        self.assertEqual(exc.exception.ret['error'], 'spec.type must be "pod"')

    def test_podspec(self):
        podspec = oaatoperator.oaattype.podspec(BasicTests.kot,
                                                name='test-kot')
        self.assertEqual(podspec['container']['name'], 'test')


class MiniKubeTests(unittest.TestCase):
    #    @pytest.mark.usefixtures('login_mocks')
    def test_pod_objects(self):
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        pod = pykube.Pod.objects(api)
        self.assertIsInstance(pod, Query)

#    @pytest.mark.usefixtures('login_mocks')
    def test_pod_create(self):
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

#    @pytest.mark.usefixtures('login_mocks')
    def test_oaattype_objects(self):
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        kot = KubeOaatType.objects(api)
        self.assertIsInstance(kot, Query)

#    @pytest.mark.usefixtures('login_mocks')
# if this test fails, it could be because there is no 'oaattest'
# OaatType loaded. try:
#   kubectl apply -f manifests/sample-oaat-type.yaml
    def test_oaattype_query(self):
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        kot = KubeOaatType.objects(api)
        self.assertIsInstance(kot, Query)
        obj = kot.get_by_name('oaattest')
        self.assertIsInstance(obj, KubeOaatType)
