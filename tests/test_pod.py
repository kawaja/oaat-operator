import sys
import os
import datetime
import copy
import kopf
from pykube import Pod

import unittest
import unittest.mock
from unittest.mock import patch, call

# enable importing of oaatoperator modules without placing constraints
# on how they handle non-test in-module importing
sys.path.append(
    os.path.dirname(os.path.realpath(__file__)) + "/../oaatoperator")

from tests.testdata import TestData  # noqa: E402
from tests.mocks_pykube import KubeObject  # noqa: E402
from oaatoperator.pod import PodOverseer  # noqa: E402
from oaatoperator.common import ProcessingComplete  # noqa: E402

UTC = datetime.timezone.utc


class OldTestData:
    kog_empty = {
        'apiVersion': 'kawaja.net/v1',
        'kind': 'OaatGroup',
        'metadata': {
            'name': 'test-kog'
        },
        'status': {},
        'spec': {
            'frequency': '1m',
            'oaatType': 'test-kot',
            'oaatItems': []
        }
    }

    kog = copy.deepcopy(kog_empty)
    kog['spec']['oaatItems'] = ['item1']
    kog_previous_fail = copy.deepcopy(kog)
    kog_previous_fail['status']['items'] = {
        'item1': {
            'failure_count': 1,
            'last_failure': TestData.failure_time.isoformat()
        }
    }
    kog_previous_success = copy.deepcopy(kog)
    kog_previous_success['status']['items'] = {
        'item1': {
            'failure_count': 0,
            'last_success': TestData.success_time.isoformat()
        }
    }


class BasicTests(unittest.TestCase):

    def setUp(self):
        return super().setUp()

    def test_create(self):
        kw = TestData.setup_kwargs(TestData.kp_spec)
        with KubeObject(Pod, TestData.kp_spec):
            op = PodOverseer(**kw)
        self.assertIsInstance(op, PodOverseer)

    def test_invalid_object(self):
        with self.assertRaises(kopf.PermanentError) as exc:
            PodOverseer(a=1)  # type: ignore
        self.assertRegex(str(exc.exception),
                         'Overseer must be called with full kopf kwargs.*')

    def test_invalid_none(self):
        with self.assertRaises(TypeError):
            PodOverseer(None)  # type: ignore


class StatusTests(unittest.TestCase):

    def setUp(self):
        return super().setUp()

    @patch('oaatoperator.pod.OaatGroup', autospec=True)
    def test_success(self, og_mock):
        og_mock.kopf_object = TestData.setup_kwargs(TestData.kog_empty_attrs)
        op = TestData.setup_kwargs(TestData.kp_success)
        p = PodOverseer(**op)
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaises(ProcessingComplete):
            p.update_success_status()
        self.assertEqual(
            og_mock().mark_item_success.call_args,
            call(op['labels']['oaat-name'], finished_at=TestData.success_time))

    @patch('oaatoperator.pod.OaatGroup', autospec=True)
    def test_failure(self, og_mock):
        og_mock.kopf_object = TestData.setup_kwargs(
            TestData.kog_previous_success_attrs)
        op = TestData.setup_kwargs(TestData.kp_failure)
        p = PodOverseer(**op)
        exit_code = (op['status']['containerStatuses'][0]['state']
                     ['terminated']['exitCode'])
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaisesRegex(
                ProcessingComplete,
                f'item failed with exit code: {exit_code}'):
            p.update_failure_status()
        self.assertEqual(
            og_mock().mark_item_failed.call_args,
            call(op['labels']['oaat-name'],
                 finished_at=TestData.failure_time,
                 exit_code=exit_code))

    @patch('oaatoperator.pod.OaatGroup', autospec=True)
    def test_success_old(self, og_mock):
        og_mock.kopf_object = TestData.setup_kwargs(
            TestData.kog_previous_success_attrs)
        og_instance_mock = og_mock.return_value
        og_instance_mock.mark_item_success.return_value = False
        op = TestData.setup_kwargs(TestData.kp_success)
        finished_at = (TestData.success_time - datetime.timedelta(hours=2))
        op['status']['containerStatuses'][0]['state']['terminated'][
            'finishedAt'] = finished_at.isoformat()
        p = PodOverseer(**op)
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaisesRegex(ProcessingComplete,
                                    'ignoring old successful job pod=test-kp'):
            p.update_success_status()
        self.assertEqual(p.finished_at, finished_at)
        self.assertEqual(
            og_instance_mock.mark_item_success.call_args,
            call(op['labels']['oaat-name'], finished_at=finished_at))
        newFA = (TestData.success_time - datetime.timedelta(days=2))
        p.finished_at = newFA
        with self.assertRaisesRegex(ProcessingComplete,
                                    'ignoring old successful job pod=test-kp'):
            p.update_success_status()
        # insure finished_at is not changed
        self.assertEqual(p.finished_at, newFA)

    @patch('oaatoperator.pod.OaatGroup', autospec=True)
    def test_failure_old(self, og_mock):
        og_mock.kopf_object = TestData.setup_kwargs(
            TestData.kog_previous_fail_attrs)
        og_instance_mock = og_mock.return_value
        og_instance_mock.mark_item_failed.return_value = False
        op = TestData.setup_kwargs(TestData.kp_failure)
        finished_at = (TestData.success_time - datetime.timedelta(hours=2))
        op['status']['containerStatuses'][0]['state']['terminated'][
            'finishedAt'] = finished_at.isoformat()
        p = PodOverseer(**op)
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaisesRegex(ProcessingComplete,
                                    'ignoring old failed job pod=test-kp'):
            p.update_failure_status()
        self.assertEqual(p.finished_at, finished_at)
        self.assertEqual(
            og_instance_mock.mark_item_failed.call_args,
            call(op['labels']['oaat-name'],
                 finished_at=finished_at,
                 exit_code=op['status']['containerStatuses'][0]['state']
                 ['terminated']['exitCode']))

    @patch('oaatoperator.pod.OaatGroup', autospec=True)
    def test_update_phase(self, og_mock):
        og_mock.kopf_object = TestData.setup_kwargs(TestData.kog_empty_attrs)
        op = TestData.setup_kwargs(TestData.kp_spec)
        p = PodOverseer(**op)
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaisesRegex(
                ProcessingComplete, f'updating phase for pod {op["name"]}: '
                f'new phase={op["status"]["phase"]}'):
            p.update_phase()
        print(og_mock.call_args_list)
