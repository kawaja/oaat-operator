import unittest
from unittest.mock import patch
from copy import deepcopy

from tests.mocks_pykube import KubeObject, object_setUp, ensure_kubeobj_deleted
from tests.testdata import TestData
from oaatoperator.oaattype import OaatType
from oaatoperator.common import KubeOaatType, ProcessingComplete
import pykube
from pykube.query import Query

# TODO: This expects a kubernetes cluster (like minikube). It would be better
# to use a mocking library to handle unit testing locally.


class BasicTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def tearDown(self):
        return super().tearDown()

    #    @pytest.mark.usefixtures('login_mocks')
    def test_create_none(self):
        with self.assertRaises(ProcessingComplete) as exc:
            OaatType(None)  # type: ignore
        self.assertEqual(exc.exception.ret['error'],
                         'cannot find OaatType None')

#    @pytest.mark.usefixtures('login_mocks')
    def test_invalid_object(self):
        with self.assertRaises(ProcessingComplete) as exc:
            OaatType('testname')
        self.assertEqual(
            exc.exception.ret['error'],
            'cannot find OaatType None/testname: testname does not exist.')

    def test_podspec_nospec(self):
        with KubeObject(KubeOaatType, TestData.kot_nospec_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertEqual(exc.exception.ret['error'],
                             'missing spec in OaatType definition')

    def test_podspec_nonepodspec(self):
        with KubeObject(KubeOaatType, TestData.kot_nonepodspec_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertEqual(exc.exception.ret['error'], 'spec.podspec is missing')

    def test_podspec_nopodspec(self):
        with KubeObject(KubeOaatType, TestData.kot_nopodspec_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertEqual(exc.exception.ret['error'], 'spec.podspec is missing')

    def test_podspec_nocontainer(self):
        with KubeObject(KubeOaatType, TestData.kot_nocontainer_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertEqual(exc.exception.ret['error'],
                            'spec.podspec.container is missing')

    def test_podspec_containers(self):
        with KubeObject(KubeOaatType, TestData.kot_containers_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertRegex(exc.exception.ret['error'],
                            'currently only support a single container.*')

    def test_podspec_restartPolicy(self):
        with KubeObject(KubeOaatType, TestData.kot_restartPolicy_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertRegex(exc.exception.ret['error'],
                            '.*you cannot specify a restartPolicy')

    def test_podspec_without_type(self):
        with KubeObject(KubeOaatType, TestData.kot_notype_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertEqual(exc.exception.ret['error'], 'spec.type must be "pod"')

    def test_podspec(self):
        with KubeObject(KubeOaatType, TestData.kot_spec):
            ot = OaatType('test-kot')
            podspec = ot.podspec()
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
