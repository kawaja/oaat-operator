import sys
import os
import pykube
from copy import deepcopy

from unittest.mock import patch
import unittest

# enable importing of oaatoperator modules without placing constraints
# on how they handle non-test in-module importing
sys.path.append(
    os.path.dirname(os.path.realpath(__file__)) + "/../oaatoperator")

from tests.testdata import TestData  # noqa: E402
from tests.utility import ExtendedTestCase, get_env  # noqa: E402
from oaatoperator.oaatitem import OaatItem, OaatItems  # noqa: E402
from oaatoperator.common import ProcessingComplete  # noqa: E402


class OaatItemTests(unittest.TestCase):
    def test_create(self):
        OaatItem(TestData.kog_emptyspec_mock, 'item1')

    def test_success(self):
        oi = OaatItem(TestData.kog_previous_success_mock, 'item1')
        self.assertEqual(oi.success(), TestData.success_time)

    def test_failure(self):
        oi = OaatItem(TestData.kog_previous_fail_mock, 'item1')
        self.assertEqual(oi.failure(), TestData.failure_time)
        self.assertEqual(oi.numfails(), TestData.failure_count)


class RunItemTests(unittest.TestCase):
    def setUp(self):
        return super().setUp()

    @patch('kopf.adopt')
    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    @patch('pykube.Pod')
    def test_sunny(self, pod_mock, og_mock, kopf_adopt_mock):
        TestData.add_og_mock_attributes(og_mock)
        og_mock.oaattype.podspec.return_value = deepcopy(
            TestData.kot_typespec.get('podspec', {}))
        oi = OaatItem(og_mock, 'item1')
        oi.run()
        og_mock.oaattype.podspec.assert_called_once()
        kopf_adopt_mock.assert_called_once()
        pod = pod_mock.call_args.args[1]
        self.assertEqual(pod['metadata']['labels']['oaat-name'], 'item1')
        self.assertEqual(
            get_env(pod['spec']['containers'][0]['env'], 'OAAT_ITEM'), 'item1')

    @patch('kopf.adopt')
    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    @patch('pykube.Pod')
    def test_podfail(self, pod_mock, og_mock, kopf_adopt_mock):
        TestData.add_og_mock_attributes(og_mock)
        og_mock.oaattype.podspec.return_value = deepcopy(
            TestData.kot_typespec.get('podspec', {}))
        pod_instance_mock = pod_mock.return_value
        pod_instance_mock.create.side_effect = pykube.KubernetesError(
            'test error')
        oi = OaatItem(og_mock, 'item1')
        with self.assertRaisesRegex(ProcessingComplete,
                                    'error creating pod for item1'):
            oi.run()
        og_mock.oaattype.podspec.assert_called_once()
        kopf_adopt_mock.assert_called_once()

    @patch('kopf.adopt')
    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    @patch('pykube.Pod')
    def test_substitute(self, pod_mock, og_mock, kopf_adopt_mock):
        TestData.add_og_mock_attributes(og_mock)
        kot_substitutions_podspec = deepcopy(
            TestData.kot_typespec.get('podspec', {}))
        kot_substitutions_podspec['container']['command'] = [
            'a', 'b', '%%oaat_item%%', 'c'
        ]
        kot_substitutions_podspec['container']['args'] = [
            'a', 'b', '%%oaat_item%%', 'c'
        ]
        kot_substitutions_podspec['container']['env'] = [
            {'name': 'first', 'value': '%%oaat_item%%'},
            {'name': 'second', 'value': 'abc%%oaat_item%%def'},
        ]
        og_mock.oaattype.podspec.return_value = kot_substitutions_podspec
        oi = OaatItem(og_mock, 'item1')
        oi.run()
        og_mock.oaattype.podspec.assert_called_once()
        kopf_adopt_mock.assert_called_once()

        pod = pod_mock.call_args.args[1]
        self.assertEqual(pod['metadata']['labels']['oaat-name'], 'item1')
        self.assertEqual(pod['spec']['containers'][0]['command'][0], 'a')
        self.assertEqual(pod['spec']['containers'][0]['command'][1], 'b')
        self.assertEqual(pod['spec']['containers'][0]['command'][2], 'item1')
        self.assertEqual(pod['spec']['containers'][0]['command'][3], 'c')
        self.assertEqual(pod['spec']['containers'][0]['args'][0], 'a')
        self.assertEqual(pod['spec']['containers'][0]['args'][1], 'b')
        self.assertEqual(pod['spec']['containers'][0]['args'][2], 'item1')
        self.assertEqual(pod['spec']['containers'][0]['args'][3], 'c')
        self.assertEqual(
            get_env(pod['spec']['containers'][0]['env'], 'OAAT_ITEM'), 'item1')
        self.assertEqual(
            get_env(pod['spec']['containers'][0]['env'], 'first'), 'item1')
        self.assertEqual(
            get_env(pod['spec']['containers'][0]['env'], 'second'),
            'abcitem1def')


class TestOaatItems(ExtendedTestCase):
    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_create(self, og_mock):
        ois = OaatItems(og_mock, {})
        self.assertEqual(ois.obj, {})
        self.assertEqual(ois.group, og_mock)

    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_nondict(self, og_mock):
        with self.assertRaisesRegex(
                TypeError, 'obj should be dict, not <class \'str\'>=string'):
            OaatItems(og_mock, 'string')  # type: ignore

    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_get_kubeobj(self, og_mock):
        og_mock.obj = TestData.kog5_mock
        og_mock.status = TestData.kog5_mock.status
        ois = OaatItems(group=og_mock, obj=TestData.kog5_mock.obj)
        self.assertEqual(ois.obj, TestData.kog5_mock.obj)
        self.assertEqual(ois.group, og_mock)
        i = ois.get('item1')
        self.assertIsInstance(i, OaatItem)
        self.assertEqual(i.name, 'item1')
        self.assertEqual(i.status('podphase', 'test'), 'test')

    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_get_kopfobj(self, og_mock):
        og_mock.obj = TestData.kog5_mock
        og_mock.status = TestData.kog5_mock.status
        kopfobj = TestData.setup_kwargs(TestData.kog5_mock.obj)
        ois = OaatItems(group=og_mock, obj=kopfobj)
        self.assertEqual(ois.obj, kopfobj)
        self.assertEqual(ois.group, og_mock)
        i = ois.get('item1')
        self.assertIsInstance(i, OaatItem)
        self.assertEqual(i.name, 'item1')
        self.assertEqual(i.status('podphase', 'test'), 'test')

    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_list_kubeobj(self, og_mock):
        TestData.add_og_mock_attributes(og_mock)
        og_mock.obj = TestData.kog5_mock
        ois = OaatItems(group=og_mock, obj=TestData.kog5_mock.obj)
        self.assertEqual(ois.obj, TestData.kog5_mock.obj)
        self.assertEqual(ois.group, og_mock)
        items = ois.list()
        self.assertIsInstance(items, list)

    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_list_kopfobj(self, og_mock):
        TestData.add_og_mock_attributes(og_mock)
        og_mock.obj = TestData.kog5_mock
        kopfobj = TestData.setup_kwargs(TestData.kog5_mock.obj)
        ois = OaatItems(group=og_mock, obj=kopfobj)
        self.assertEqual(ois.obj, kopfobj)
        self.assertEqual(ois.group, og_mock)
        items = ois.list()
        self.assertIsInstance(items, list)

    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_len_kubeobj(self, og_mock):
        og_mock.obj = TestData.kog5_mock
        ois = OaatItems(group=og_mock, obj=TestData.kog5_mock.obj)
        self.assertEqual(ois.obj, TestData.kog5_mock.obj)
        self.assertEqual(ois.group, og_mock)
        self.assertEqual(len(ois), 5)

    @patch('oaatoperator.oaatgroup.OaatGroup', autospec=True)
    def test_len_kopfobj(self, og_mock):
        og_mock.obj = TestData.kog5_mock
        kopfobj = TestData.setup_kwargs(TestData.kog5_mock.obj)
        ois = OaatItems(group=og_mock, obj=kopfobj)
        self.assertEqual(ois.obj, kopfobj)
        self.assertEqual(ois.group, og_mock)
        self.assertEqual(len(ois), 5)
