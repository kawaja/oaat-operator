import unittest
from copy import deepcopy

from tests.mocks_pykube import object_setUp, ensure_kubeobj_deleted
from oaatoperator.oaattype import OaatType
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

#    def oaattype_setUp(self, spec):
#        ensure_kubeobj_deleted(KubeOaatType, 'test-kot')
#        kot = KubeOaatType(self.api, spec)
#        print(spec)
#        kot.create()
#        yield kot
#        ensure_kubeobj_deleted(KubeOaatType, 'test-kot')
#        yield None

#    @pytest.mark.usefixtures('login_mocks')
    def test_create_none(self):
        ot = OaatType(None)
        self.assertIsInstance(ot, OaatType)
        self.assertEqual(ot.name, None)
        self.assertEqual(ot.get_oaattype(), None)

#    @pytest.mark.usefixtures('login_mocks')
    def test_invalid_object(self):
        with self.assertRaises(ProcessingComplete):
            OaatType('testname')

    def test_invalid_none_podspec(self):
        ot = OaatType(None)
        with self.assertRaises(ProcessingComplete):
            ot.podspec()

    def test_podspec_nospec(self):
        setup = object_setUp(KubeOaatType, BasicTests.kot_nospec)
        next(setup)
        ot = OaatType('test-kot')
        with self.assertRaises(ProcessingComplete) as exc:
            ot.podspec()
        self.assertEqual(exc.exception.ret['error'],
                         'missing spec in OaatType definition')
        next(setup)

    def test_podspec_nocontainer(self):
        setup = object_setUp(KubeOaatType, BasicTests.kot_nocontainer)
        next(setup)
        ot = OaatType('test-kot')
        with self.assertRaises(ProcessingComplete) as exc:
            ot.podspec()
        self.assertEqual(exc.exception.ret['error'],
                         'spec.podspec.container is missing')
        next(setup)

    def test_podspec_containers(self):
        setup = object_setUp(KubeOaatType, BasicTests.kot_containers)
        next(setup)
        ot = OaatType('test-kot')
        with self.assertRaises(ProcessingComplete) as exc:
            ot.podspec()
        self.assertRegex(exc.exception.ret['error'],
                         'currently only support a single container.*')
        next(setup)

    def test_podspec_restartPolicy(self):
        setup = object_setUp(KubeOaatType, BasicTests.kot_restartPolicy)
        next(setup)
        ot = OaatType('test-kot')
        with self.assertRaises(ProcessingComplete) as exc:
            ot.podspec()
        self.assertRegex(exc.exception.ret['error'],
                         '.*you cannot specify a restartPolicy')
        next(setup)

    def test_podspec_without_type(self):
        setup = object_setUp(KubeOaatType, BasicTests.kot_notype)
        next(setup)
        ot = OaatType('test-kot')
        with self.assertRaises(ProcessingComplete) as exc:
            ot.podspec()
        self.assertEqual(exc.exception.ret['error'], 'spec.type must be "pod"')
        next(setup)

    def test_podspec(self):
        setup = object_setUp(KubeOaatType, BasicTests.kot)
        next(setup)
        ot = OaatType('test-kot')
        podspec = ot.podspec()
        self.assertEqual(podspec['container']['name'], 'test')
        next(setup)


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
    def test_oaattype_query(self):
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        kot = KubeOaatType.objects(api)
        self.assertIsInstance(kot, Query)
        obj = kot.get_by_name('oaattest')
        self.assertIsInstance(obj, KubeOaatType)
