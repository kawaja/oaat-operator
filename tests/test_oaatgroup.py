import sys
import os
from copy import deepcopy
import datetime
import pykube
import kopf
from typing import cast

import unittest
import unittest.mock
from unittest.mock import patch, MagicMock

# enable importing of oaatoperator modules without placing constraints
# on how they handle non-test in-module importing
sys.path.append(
    os.path.dirname(os.path.realpath(__file__)) + "/../oaatoperator")

from tests.mocks_pykube import KubeObject, KubeObjectPod  # noqa: E402
from tests.testdata import TestData  # noqa: E402

from oaatoperator.oaatgroup import OaatGroup, OaatGroupOverseer  # noqa: E402
from oaatoperator.py_types import CallbackArgs  # noqa: E402
from oaatoperator.common import (KubeOaatGroup,  # noqa: E402
                                 ProcessingComplete)
import oaatoperator.utility  # noqa: E402

UTC = datetime.timezone.utc


class BasicTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_create_none(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_attrs)))
        self.assertIsInstance(og, OaatGroup)
        self.assertEqual(og.freq, datetime.timedelta(seconds=60))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_get_kubeobj(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_attrs)))
            kobj = og.get_kubeobj()
        self.assertIsInstance(kobj, KubeOaatGroup)
        self.assertEqual(kobj.name, TestData.kog_attrs['metadata']['name'])

    def test_invalid_object(self):
        with self.assertRaises(kopf.PermanentError) as exc:
            OaatGroup(kopf_object={})  # type: ignore
            self.assertRegex(
                str(exc.exception),
                'Overseer must be called with full kopf kwargs.*')

    def test_invalid_none(self):
        with self.assertRaises(kopf.PermanentError):
            OaatGroup(kopf_object=None)  # type: ignore

    def test_podspec_emptyspec(self):
        with KubeObject(KubeOaatGroup, TestData.kog_emptyspec_attrs):
            with self.assertRaises(ProcessingComplete) as exc:
                OaatGroup(kopf_object=cast(
                    CallbackArgs,
                    TestData.setup_kwargs(TestData.kog_emptyspec_attrs)))
            self.assertEqual(exc.exception.ret['error'],
                             'cannot find OaatType None')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_podspec_nofreq(self, _):
        kog = deepcopy(TestData.kog_attrs)
        kog['spec']['frequency'] = 'nofreq'
        kog_mock = TestData.new_mock(KubeOaatGroup, kog)
        with KubeObject(KubeOaatGroup, kog):
            with self.assertRaises(kopf.PermanentError) as exc:
                OaatGroup(kopf_object=cast(
                    CallbackArgs,
                    TestData.setup_kwargs(kog_mock.obj)))
            self.assertEqual(
                str(exc.exception),
                'invalid frequency specification nofreq in test-kog')


class FindJobTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_noitems(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_empty_attrs)))
            with self.assertRaisesRegex(ProcessingComplete,
                                        'error in OaatGroup definition'):
                og.find_job_to_run()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_noprevious_run(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_attrs)))
            job = og.find_job_to_run()
        self.assertEqual(job.name, 'item1')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_success_within_freq(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_attrs)))
            og.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})['item1'] = {
                    'last_success': oaatoperator.utility.now_iso(),
                    'failure_count': 0
                }
            with self.assertRaisesRegex(ProcessingComplete,
                                        'not time to run next item'):
                og.find_job_to_run()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_success_outside_freq(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_attrs)))
            og.kopf_object.debug = print  # type: ignore
            og.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})['item1'] = {
                    'last_success': (
                        (datetime.datetime.now(tz=UTC) -
                            datetime.timedelta(minutes=5))
                        .isoformat()),
                    'failure_count': 0
                }
            job = og.find_job_to_run()
            self.assertEqual(job.name, 'item1')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_failure_within_freq_no_cooloff(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_attrs)))
            og.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})['item1'] = {
                    'last_failure': oaatoperator.utility.now_iso(),
                    'failure_count': 0
                }
            job = og.find_job_to_run()
            self.assertEqual(job.name, 'item1')

    # inside frequency and cooloff => not valid (cooloff)
    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_failure_within_freq_within_cooloff(self, _):
        kog = deepcopy(TestData.kog_attrs)
        kog['spec']['failureCoolOff'] = '5m'
        kog['spec']['frequency'] = '10m'
        kog_mock = TestData.new_mock(KubeOaatGroup, kog)
        with KubeObject(KubeOaatGroup, kog_mock.obj):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(kog_mock.obj)))

            og.kopf_object.debug = unittest.mock.MagicMock()  # type: ignore
            og.kopf_object.info = unittest.mock.MagicMock()  # type: ignore
            og.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})['item1'] = {
                    'last_failure': (
                        (datetime.datetime.now(tz=UTC) -
                            datetime.timedelta(minutes=1))
                        .isoformat()),
                    'failure_count': 0
                }
            with self.assertRaisesRegex(ProcessingComplete,
                                        'not time to run next item'):
                og.find_job_to_run()
            print(og.kopf_object.info.call_args.args[0])  # type: ignore
            self.assertRegex(
                og.kopf_object.info.call_args.args[0],  # type: ignore
                'item1 cool_off.*not expired since last failure')

    # inside frequency but outside cooloff => valid job
    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_failure_within_freq_outside_cooloff(self, _):
        kog = deepcopy(TestData.kog_attrs)
        kog['spec']['failureCoolOff'] = '1m'
        kog['spec']['frequency'] = '10m'
        kog_mock = TestData.new_mock(KubeOaatGroup, kog)
        with KubeObject(KubeOaatGroup, kog_mock.obj):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(kog_mock.obj)))
            og.kopf_object.debug = print  # type: ignore
            og.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})['item1'] = {
                    'last_failure': (
                        (datetime.datetime.now(tz=UTC) -
                            datetime.timedelta(minutes=5))
                        .isoformat()),
                    'failure_count': 0
                }
            job = og.find_job_to_run()
            self.assertEqual(job.name, 'item1')

    # outside frequency but inside cooloff => not valid (cooloff)
    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_failure_outside_freq_within_cooloff(self, _):
        kog = deepcopy(TestData.kog_attrs)
        kog['spec']['failureCoolOff'] = '10m'
        kog['spec']['frequency'] = '1m'
        kog_mock = TestData.new_mock(KubeOaatGroup, kog)
        with KubeObject(KubeOaatGroup, kog_mock.obj):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(kog_mock.obj)))
            og.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})['item1'] = {
                    'last_failure': (
                        (datetime.datetime.now(tz=UTC) -
                            datetime.timedelta(minutes=5))
                        .isoformat()),
                    'failure_count': 0
                }
            with self.assertRaisesRegex(ProcessingComplete,
                                        'not time to run next item'):
                og.find_job_to_run()

    # outside both frequency and cooloff => valid job
    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_oneitem_failure_outside_freq_outside_cooloff(self, _):
        kog = deepcopy(TestData.kog_attrs)
        kog['spec']['failureCoolOff'] = '5m'
        kog['spec']['frequency'] = '1m'
        kog_mock = TestData.new_mock(KubeOaatGroup, kog)
        with KubeObject(KubeOaatGroup, kog_mock.obj):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(kog_mock.obj)))
            og.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})['item1'] = {
                    'last_failure': (
                        (datetime.datetime.now(tz=UTC) -
                            datetime.timedelta(minutes=10))
                        .isoformat()),
                    'failure_count': 1
                }
            job = og.find_job_to_run()
            self.assertEqual(job.name, 'item1')

    # should mock randrange to validate this
    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_5_noprevious_run(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog5_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog5_attrs)))
            job = og.find_job_to_run()
            self.assertIn(job.name,
                          ('item1', 'item2', 'item3', 'item4', 'item5'))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_5_single_oldest(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog5_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog5_attrs)))
            success = (datetime.datetime.now(tz=UTC) -
                       datetime.timedelta(minutes=5)).isoformat()
            osuccess = (datetime.datetime.now(tz=UTC) -
                        datetime.timedelta(minutes=7)).isoformat()
            for i in TestData.kog5_attrs['spec']['oaatItems']:
                og.items.obj.setdefault(
                    'status',
                    {}).setdefault('items', {})[i] = {
                        'last_success': success,
                        'failure_count': 0
                    }
            og.items.obj['status']['items']['item3']['last_success'] = osuccess
            job = og.find_job_to_run()
            self.assertEqual(job.name, 'item3')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_5_single_oldest_failure(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog5_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog5_attrs)))
            og.kopf_object.debug = print  # type: ignore
            success = ((datetime.datetime.now(tz=UTC) -
                        datetime.timedelta(minutes=5)).isoformat())
            failure = (datetime.datetime.now(tz=UTC) -
                       datetime.timedelta(minutes=7)).isoformat()
            for i in TestData.kog5_attrs['spec']['oaatItems']:
                og.items.obj.setdefault(
                    'status',
                    {}).setdefault('items', {})[i] = {
                        'last_success': success,
                        'failure_count': 0
                    }
            og.items.obj['status']['items']['item4']['last_failure'] = failure
            og.items.obj['status']['items']['item4']['failure_count'] = 1
            job = og.find_job_to_run()
            self.assertEqual(job.name, 'item4')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_5_single_multiple_failure(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog5_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog5_attrs)))
            og.kopf_object.debug = print  # type: ignore
            success = (datetime.datetime.now(tz=UTC) -
                       datetime.timedelta(minutes=5)).isoformat()
            failure = (datetime.datetime.now(tz=UTC) -
                       datetime.timedelta(minutes=7)).isoformat()
            for i in TestData.kog5_attrs['spec']['oaatItems']:
                og.items.obj.setdefault(
                    'status',
                    {}).setdefault('items', {})[i] = {
                        'last_success': success,
                        'failure_count': 0
                    }
            og.items.obj['status']['items']['item4']['last_failure'] = failure
            og.items.obj['status']['items']['item4']['failure_count'] = 1
            og.items.obj['status']['items']['item2']['last_failure'] = failure
            og.items.obj['status']['items']['item2']['failure_count'] = 1
            job = og.find_job_to_run()
            self.assertIn(job.name, ('item4', 'item2'))


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def tearDown(self):
        return super().tearDown()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_validate_items_none(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_empty_attrs)))
            with self.assertRaisesRegex(ProcessingComplete,
                                        'no items found.*'):
                og.validate_items()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_validate_items_none_annotation(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_empty_attrs)))
            with self.assertRaisesRegex(ProcessingComplete,
                                        'no items found.*'):
                og.validate_items(
                    status_annotation='test-status',
                    count_annotation='test-items')
            self.assertEqual(
                og.kopf_object.patch['metadata']  # type: ignore
                ['annotations'].get('kawaja.net/test-status'),
                'missingItems')
            self.assertEqual(
                og.kopf_object.patch['metadata']  # type: ignore
                ['annotations'].get('kawaja.net/test-items'),
                None)

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_validate_items_one_annotation(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kopf_object=cast(
                CallbackArgs, TestData.setup_kwargs(TestData.kog_attrs)))
            og.validate_items(
                status_annotation='test-status',
                count_annotation='test-items')
            self.assertEqual(
                og.kopf_object.patch['metadata']  # type: ignore
                ['annotations'].get('kawaja.net/test-status'),
                'active')
            self.assertEqual(
                og.kopf_object.patch['metadata']  # type: ignore
                ['annotations'].get('kawaja.net/test-items'),
                '1')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_delete_rogue_none(self, _):
        with KubeObjectPod(TestData.pod_spec) as pod1:
            with KubeObject(KubeOaatGroup, TestData.kog_attrs):
                kw = TestData.setup_kwargs(TestData.kog_attrs)
                kw.setdefault('status', {})['pod'] = pod1.name
                kw.setdefault('status', {})['currently_running'] = 'itemname'
                og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
                og.kopf_object.warning = print  # type: ignore
                self.assertEqual(og.get_status('pod'), pod1.name)
                # no rogue pod
                with self.assertRaisesRegex(
                        ProcessingComplete,
                        'Pod .* exists and is in state Running'):
                    og.verify_running()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_delete_rogue_skip_unrelated_xxx(self, _):
        with KubeObjectPod(TestData.pod_spec) as pod1:
            with KubeObjectPod(TestData.pod_spec_noapp):
                with KubeObject(KubeOaatGroup, TestData.kog_attrs):
                    kw = TestData.setup_kwargs(TestData.kog_attrs)
                    kw.setdefault('status', {})['pod'] = pod1.name
                    kw.setdefault('status',
                                  {})['currently_running'] = 'itemname'
                    og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
                    # no rogue pod
                    with self.assertRaisesRegex(
                            ProcessingComplete,
                            'Pod .* exists and is in state Running'):
                        og.verify_running()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_delete_rogue_skip_unrelated(self, _):
        with KubeObjectPod(TestData.pod_spec) as pod1:
            with KubeObjectPod(TestData.pod_spec_noapp):
                with KubeObject(KubeOaatGroup, TestData.kog_attrs):
                    kw = TestData.setup_kwargs(TestData.kog_attrs)
                    kw.setdefault('status', {})['pod'] = pod1.name
                    kw.setdefault('status',
                                  {})['currently_running'] = 'itemname'
                    og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
                    # no rogue pod
                    with self.assertRaisesRegex(
                            ProcessingComplete,
                            'Pod .* exists and is in state Running'):
                        og.verify_running()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_delete_rogue(self, _):
        with KubeObjectPod(TestData.pod_spec) as pod1:
            with KubeObjectPod(TestData.pod_spec):
                with KubeObject(KubeOaatGroup, TestData.kog_attrs):
                    kw = TestData.setup_kwargs(TestData.kog_attrs)
                    kw.setdefault('status', {})['pod'] = pod1.name
                    kw.setdefault('status',
                                  {})['currently_running'] = 'itemname'
                    og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
                    with self.assertRaisesRegex(ProcessingComplete,
                                                'rogue pods running'):
                        og.verify_running()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_verify_running_nopod_nocr(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            kw = TestData.setup_kwargs(TestData.kog_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            kw.setdefault('status', {})['pod'] = None
            kw.setdefault('status', {})['currently_running'] = None
            self.assertIsNone(og.verify_running())

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_verify_running_expected_running_and_is(self, _):
        with KubeObjectPod(TestData.pod_spec) as pod1:
            with KubeObject(KubeOaatGroup, TestData.kog_attrs):
                kw = TestData.setup_kwargs(TestData.kog_attrs)
                kw.setdefault('status', {})['pod'] = pod1.name
                kw.setdefault('status', {})['currently_running'] = 'itemname'
                og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
                self.assertEqual(og.get_status('pod'), pod1.name)
                with self.assertRaisesRegex(
                        ProcessingComplete,
                        'Pod .* exists and is in state Running'):
                    og.verify_running()


class OaatGroupTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.setup = None
        self.setup_kot = None
        return super().setUp()

    def tearDown(self):
        if self.setup:
            next(self.setup)  # delete KubeOaatGroup
        if self.setup_kot:
            next(self.setup_kot)  # delete KubeOaatType
        return super().tearDown()

    def test_create_none(self):
        with self.assertRaisesRegex(kopf.PermanentError,
                                    'OaatGroup must be called with either.*'):
            OaatGroup()

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_no_kopf(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kube_object_name='test-kog',
                           memo=MagicMock(),
                           logger=MagicMock())
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve find_job_to_run outside of kopf'):
                og.find_job_to_run()
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve validate_items outside of kopf'):
                og.validate_items()
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve identify_running_pod '
                    'outside of kopf'):
                og.identify_running_pod()
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve verify_running_pod outside of kopf'):
                og.verify_running_pod()
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve verify_running outside of kopf'):
                og.verify_running()
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve delete_non_survivor_pods '
                    'outside of kopf'):
                og.delete_non_survivor_pods('item')
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve resume_running_pod outside of kopf'):
                og.resume_running_pod([])
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve select_survivor outside of kopf'):
                og.select_survivor([])
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve set_status outside of kopf'):
                og.set_status('state', 'value')
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve set_object_status outside of kopf'):
                og.set_object_status('state', 'value')
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'attempt to retrieve get_kubeobj outside of kopf'):
                og.get_kubeobj('state', 'value')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_create_with_kubeobj(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            og = OaatGroup(kube_object_name='test-kog',
                           memo=MagicMock(),
                           logger=MagicMock())
            self.assertIsInstance(og.kube_object, KubeOaatGroup)
            self.assertEqual(og.kopf_object, None)
            self.assertEqual(og.kube_object.name,
                             TestData.kog_attrs['metadata']['name'])
            self.assertEqual(og.namespace(), 'default')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_create_with_kubeobj_no_logger(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'must supply logger= parameter .*kube_object_name'):
                OaatGroup(kube_object_name='test-kog', memo=MagicMock())

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_create_with_kubeobj_no_memo(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            with self.assertRaisesRegex(
                    kopf.PermanentError,
                    'must supply memo= parameter .*kube_object_name'):
                OaatGroup(kube_object_name='test-kog', logger=MagicMock())

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_create_with_kopfobj(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            kw = TestData.setup_kwargs(TestData.kog_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            self.assertFalse(hasattr(og, 'kube_object'))
            self.assertIsInstance(og.kopf_object, OaatGroupOverseer)
            self.assertEqual(
                og.kopf_object.name,  # type: ignore
                TestData.kog_attrs['metadata']['name'])
            self.assertEqual(og.namespace(), 'default')

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_mark_failed_invalid_finished_at(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_previous_fail_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_fail_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            with self.assertRaisesRegex(
                    ValueError, 'mark_item_failed finished_at= should '
                    'be datetime.datetime object'):
                og.mark_item_failed(
                    'item1',
                    finished_at='hello')  # type: ignore

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_mark_item_failed_new_failure(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_previous_fail_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_fail_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            self.assertTrue(
                og.mark_item_failed(
                    'item1',
                    finished_at=(TestData.failure_time +
                                 datetime.timedelta(hours=2))))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_mark_item_failed_old_failure(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_previous_fail_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_fail_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            self.assertFalse(
                og.mark_item_failed(
                    'item1',
                    finished_at=(TestData.failure_time -
                                 datetime.timedelta(hours=2))))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    @patch('oaatoperator.utility.now')
    def test_mark_item_failed_no_date_provided(self, now, _):
        now.return_value = (TestData.failure_time +
                            datetime.timedelta(hours=2))
        with KubeObject(KubeOaatGroup, TestData.kog_previous_fail_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_fail_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            self.assertTrue(og.mark_item_failed('item1'))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_mark_success_invalid_finished_at(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_previous_success_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_success_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            with self.assertRaisesRegex(
                    ValueError, 'mark_item_success finished_at= should '
                    'be datetime.datetime object'):
                og.mark_item_success(
                    'item1',
                    finished_at='hello')  # type: ignore

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_mark_item_success_new_success(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_previous_success_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_success_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            self.assertTrue(
                og.mark_item_success(
                    'item1',
                    finished_at=(TestData.success_time +
                                 datetime.timedelta(hours=2))))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_mark_item_success_old_success(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_previous_success_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_success_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            self.assertFalse(
                og.mark_item_success(
                    'item1',
                    finished_at=(TestData.success_time -
                                 datetime.timedelta(hours=2))))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    @patch('oaatoperator.utility.now')
    def test_mark_item_success_no_date_provided(self, now, _):
        now.return_value = (TestData.success_time +
                            datetime.timedelta(hours=2))
        with KubeObject(KubeOaatGroup, TestData.kog_previous_fail_attrs):
            kw = TestData.setup_kwargs(TestData.kog_previous_fail_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            self.assertTrue(og.mark_item_success('item1'))

    @patch('oaatoperator.oaatgroup.OaatType',
           autospec=True,
           obj=TestData.kot_mock)
    def test_find_job_oneitem_noprevious_run(self, _):
        with KubeObject(KubeOaatGroup, TestData.kog_attrs):
            kw = TestData.setup_kwargs(TestData.kog_attrs)
            og = OaatGroup(kopf_object=cast(CallbackArgs, kw))
            og.kopf_object.debug = print  # type: ignore
            job = og.find_job_to_run()
            self.assertEqual(job.name, 'item1')

# TODO:
# - find_job_to_run()
#   X no items
#   X one item
#   X no items within 'frequency'
#   X failed items within 'cool off'
#   X single oldest success
#   X multiple oldest success single oldest failure
#   X multiple oldest success multiple oldest failure (mock random)
# - run_item()
#   X valid spec
#   X invalid spec
#   X %%oaat_item%% substitution
# - validate_items()
#   X no items
#   X set annotations
#   X invalid state (failed pod creation)
#   X valid states
# - verify_running_pod()
#   X nothing expected to be running
#   X expected to be running, but not
#   X expected to be running, and is
#   - running with phase update
#   - succeeded, but not yet acknowledged
#   X unexpected state
