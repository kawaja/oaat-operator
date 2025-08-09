import unittest
import pytest

from tests.unit.mocks_pykube import KubeObject
from tests.unit.testdata import TestData
from oaatoperator.oaattype import OaatType
from oaatoperator.common import KubeOaatType, ProcessingComplete

pytestmark = pytest.mark.unit


class BasicTests(unittest.TestCase):
    def setUp(self):
        return super().setUp()

    def tearDown(self):
        return super().tearDown()

    def test_create_none(self):
        with self.assertRaises(ProcessingComplete) as exc:
            OaatType(None)  # type: ignore
        self.assertEqual(exc.exception.ret['error'],
                         'cannot find OaatType None')

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
            self.assertEqual(exc.exception.ret['error'],
                             'spec.podspec is missing')

    def test_podspec_nopodspec(self):
        with KubeObject(KubeOaatType, TestData.kot_nopodspec_spec):
            ot = OaatType('test-kot')
            with self.assertRaises(ProcessingComplete) as exc:
                ot.podspec()
            self.assertEqual(exc.exception.ret['error'],
                             'spec.podspec is missing')

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
            self.assertEqual(exc.exception.ret['error'],
                             'spec.type must be "pod"')

    def test_podspec(self):
        with KubeObject(KubeOaatType, TestData.kot_spec):
            ot = OaatType('test-kot')
            podspec = ot.podspec()
            self.assertEqual(podspec['container']['name'], 'test')
