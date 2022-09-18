import sys
import os
import pykube
from copy import deepcopy
# enable importing of oaatoperator modules without placing constraints
# on how they handle non-test in-module importing
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../oaatoperator")

from unittest.mock import MagicMock, patch
import unittest

from tests.mocks_pykube import object_setUp
from tests.testdata import TestData
from oaatoperator.oaatitem import OaatItem, OaatItems
from oaatoperator.oaatgroup import OaatGroupOverseer
from oaatoperator.oaattype import OaatType
from oaatoperator.common import (KubeOaatGroup, KubeOaatType, ProcessingComplete)


def get_env(env_array, env_var):
    for env in env_array:
        if env.get('name') == env_var:
            return env.get('value')


class OaatItemTests(unittest.TestCase):
    def test_create(self):
        oi = OaatItem(TestData.kog_emptyspec_mock, 'item1')

    def test_success(self):
        oi = OaatItem(TestData.kog_previous_success_mock, 'item1')
        self.assertEqual(oi.success(), TestData.success_time)

    def test_failure(self):
        oi = OaatItem(TestData.kog_previous_fail_mock, 'item1')
        self.assertEqual(oi.failure(), TestData.failure_time)
        self.assertEqual(oi.numfails(), TestData.failure_count)


class RunItemTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    @patch('kopf.adopt')
    @patch('oaatoperator.oaatgroup.OaatGroup')
    @patch('pykube.Pod')
    def test_sunny(self, pod_mock, og_mock, kopf_adopt_mock):
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
    @patch('oaatoperator.oaatgroup.OaatGroup')
    @patch('pykube.Pod')
    def test_podfail(self, pod_mock, og_mock, kopf_adopt_mock):
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
    @patch('oaatoperator.oaatgroup.OaatGroup')
    @patch('pykube.Pod')
    def test_substitute(self, pod_mock, og_mock, kopf_adopt_mock):
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
