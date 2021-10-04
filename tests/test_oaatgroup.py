import unittest
from copy import deepcopy
import datetime
from time import sleep

from tests.mocks_pykube import object_setUp
from oaatoperator.oaatgroup import OaatGroup, OaatGroupOverseer
from oaatoperator.oaattype import OaatType
from oaatoperator.common import (InternalError, KubeOaatGroup, KubeOaatType,
                                 ProcessingComplete)
import oaatoperator.utility
import pykube
import unittest.mock
from unittest.mock import MagicMock, patch
import logging

UTC = datetime.timezone.utc


def get_env(env_array, env_var):
    for env in env_array:
        if env.get('name') == env_var:
            return env.get('value')


class TestData:
    @classmethod
    def setup_kwargs(cls, obj):
        body = {
            'spec': obj['spec'],
            'metadata': {
                'namespace': 'default',
                'name': obj.get('metadata', {}).get('name', 'unknown'),
                'uid': 'uid',
                'labels': obj.get('metadata', {}).get('labels', {}),
                'annotations': obj.get('metadata', {}.get('annotations', {}))
            },
            'status': obj.get('status')
        }

        return {
            'body': body,
            'spec': body.get('spec'),
            'meta': body.get('metadata'),
            'status': body.get('status'),
            'namespace': body.get('metadata', {}).get('namespace', 'default'),
            'name': body.get('metadata', {}).get('name'),
            'uid': body.get('metadata', {}).get('uid'),
            'labels': body.get('metadata', {}).get('labels', {}),
            'annotations': body.get('metadata', {}).get('annotations', {}),
            'logger': unittest.mock.MagicMock(spec=logging.Logger),
            'patch': {},
            'memo': {},
            'event': {},
            'reason': '',
            'old': {}, 'new': {}, 'diff': {}
        }

    failure_time = oaatoperator.utility.now()
    success_time = oaatoperator.utility.now()

    kot = {
        'apiVersion': 'kawaja.net/v1',
        'kind': 'OaatType',
        'metadata': {
            'name': 'test-kot',
            'labels': {},
            'annotations': {}
        },
        'status': {},
        'spec': {
            'type': 'pod',
            'podspec': {
                'container': {
                    'name': 'test',
                    'image': 'busybox',
                    'command': ['sh', '-x', '-c'],
                    'args': [
                        'echo "OAAT_ITEM=%%oaat_item%%"\n'
                        'sleep $(shuf -i 10-180 -n 1)\n'
                        'exit $(shuf -i 0-1 -n 1)\n'
                    ],
                }
            }
        }
    }

    kog_empty = {
        'apiVersion': 'kawaja.net/v1',
        'kind': 'OaatGroup',
        'metadata': {
            'name': 'test-kog',
            'labels': {},
            'annotations': {}
        },
        'status': {},
        'spec': {
            'frequency': '1m',
            'oaatType': 'test-kot',
            'oaatItems': []
        }
    }

    kog_nofreq = deepcopy(kog_empty)
    del kog_nofreq['spec']['frequency']
    kog_notype = deepcopy(kog_empty)
    del kog_notype['spec']['oaatType']
    kog_noitems = deepcopy(kog_empty)
    del kog_noitems['spec']['oaatItems']
    kog_emptyspec = deepcopy(kog_empty)
    kog_emptyspec['spec'] = {}
    kog = deepcopy(kog_empty)
    kog['spec']['oaatItems'] = ['item1']
    kog5 = deepcopy(kog_empty)
    kog5['spec']['oaatItems'] = ['item1', 'item2', 'item3', 'item4', 'item5']
    kog_previous_fail = deepcopy(kog)
    kog_previous_fail['status']['items'] = {
        'item1': {
            'failure_count': 1,
            'last_failure': failure_time.isoformat()
        }
    }
    kog_previous_success = deepcopy(kog)
    kog_previous_success['status']['items'] = {
        'item1': {
            'failure_count': 0,
            'last_success': success_time.isoformat()
        }
    }

    contspec = {
        'name': 'test',
        'image': 'busybox',
        'command': ['/bin/sleep', '30']
    }

    pod_spec = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {
            'generateName': 'oaat-item1-',
            'labels': {
                'parent-name': 'test-kog',
                'app': 'oaat-operator',
                'oaat-name': 'item1'
            }
        },
        'spec': {
            'containers': [contspec],
            'restartPolicy': 'Never'
        }
    }

    pod_spec_noapp = deepcopy(pod_spec)
    del pod_spec_noapp['metadata']['labels']['app']
    pod_spec_noapp['metadata']['generateName'] = 'oaat-noapp-'

    pod_spec_noapp_or_parent = deepcopy(pod_spec)
    del pod_spec_noapp_or_parent['metadata']['labels']['app']
    del pod_spec_noapp_or_parent['metadata']['labels']['parent-name']
    pod_spec_noapp['metadata']['generateName'] = 'oaat-noapp-or-parent-'


class BasicTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

#    @pytest.mark.usefixtures('login_mocks')
    def test_create_none(self):
        kog = TestData.kog
        kw = TestData.setup_kwargs(kog)
        setup_kot = object_setUp(KubeOaatType, TestData.kot)
        setup = object_setUp(KubeOaatGroup, kog)
        next(setup_kot)
        next(setup)
        ogo = OaatGroupOverseer(MagicMock(), **kw)
        self.assertIsInstance(ogo, OaatGroupOverseer)
        self.assertEqual(ogo.freq, datetime.timedelta(seconds=60))
        self.assertIsInstance(ogo.oaattype, OaatType)
        next(setup)  # delete KubeOaatGroup
        next(setup_kot)  # delete KubeOaatType

    def test_get_kubeobj(self):
        kog = TestData.kog
        kw = TestData.setup_kwargs(kog)
        setup_kot = object_setUp(KubeOaatType, TestData.kot)
        setup = object_setUp(KubeOaatGroup, kog)
        next(setup_kot)
        next(setup)
        ogo = OaatGroupOverseer(MagicMock(), **kw)
        kobj = ogo.get_kubeobj()
        self.assertIsInstance(kobj, KubeOaatGroup)
        self.assertEqual(kobj.name, kog['metadata']['name'])
        next(setup)  # delete KubeOaatGroup
        next(setup_kot)  # delete KubeOaatType

#    @pytest.mark.usefixtures('login_mocks')
    def test_validate_type(self):
        kog = TestData.kog
        kw = TestData.setup_kwargs(kog)
        setup_kot = object_setUp(KubeOaatType, TestData.kot)
        setup = object_setUp(KubeOaatGroup, kog)
        next(setup_kot)
        next(setup)
        ogo = OaatGroupOverseer(MagicMock(), **kw)
        ogo.validate_oaat_type()
        next(setup)  # delete KubeOaatGroup
        next(setup_kot)  # delete KubeOaatType

#    @pytest.mark.usefixtures('login_mocks')
    def test_invalid_object(self):
        with self.assertRaises(ValueError) as exc:
            OaatGroupOverseer(MagicMock(), a=1)
        self.assertRegex(
            str(exc.exception),
            'Overseer must be called with full kopf kwargs.*')

    def test_invalid_none(self):
        with self.assertRaises(TypeError):
            OaatGroupOverseer(MagicMock(), None)

    def test_podspec_emptyspec(self):
        kog = TestData.kog_emptyspec
        kw = TestData.setup_kwargs(kog)
        setup_kot = object_setUp(KubeOaatType, TestData.kot)
        setup = object_setUp(KubeOaatGroup, kog)
        next(setup_kot)
        next(setup)
        og = OaatGroupOverseer(MagicMock(), **kw)
        with self.assertRaises(ProcessingComplete) as exc:
            og.validate_oaat_type()
        self.assertEqual(exc.exception.ret['error'],
                         'unknown oaat type None')
        next(setup)
        next(setup_kot)


class FindJobTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def tearDown(self):
        if self.setup:
            next(self.setup)  # delete KubeOaatGroup
        if self.setup_kot:
            next(self.setup_kot)  # delete KubeOaatType
        return super().tearDown()

    def extraSetUp(self, kot, kog):
        kw = TestData.setup_kwargs(kog)
        self.setup_kot = object_setUp(KubeOaatType, deepcopy(kot))
        self.setup = object_setUp(KubeOaatGroup, deepcopy(kog))
        next(self.setup_kot)
        next(self.setup)
        ogo = OaatGroupOverseer(MagicMock(), **kw)
        self.assertIsInstance(ogo, OaatGroupOverseer)
        self.assertIsInstance(ogo.oaattype, OaatType)
        return ogo

    def test_noitems(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog_empty)
        ogo.validate_oaat_type()
        with self.assertRaisesRegex(ProcessingComplete,
                                    'error in OaatGroup definition'):
            ogo.find_job_to_run()

    def test_oneitem_noprevious_run(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.debug = print
        ogo.validate_oaat_type()
        job = ogo.find_job_to_run()
        self.assertEqual(job, 'item1')

    def test_oneitem_success_within_freq(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.validate_oaat_type()
        ogo.items.obj.setdefault(
            'status',
            {}).setdefault('items', {})['item1'] = {
                'last_success':
                oaatoperator.utility.now_iso(),
                'failure_count': 0
            }
        with self.assertRaisesRegex(ProcessingComplete,
                                    'not time to run next item'):
            ogo.find_job_to_run()

    def test_oneitem_success_outside_freq(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.validate_oaat_type()
        ogo.debug = print
        ogo.items.obj.setdefault(
            'status',
            {}).setdefault('items', {})['item1'] = {
                'last_success': (
                    (datetime.datetime.now(tz=UTC) -
                        datetime.timedelta(minutes=5))
                    .isoformat()),
                'failure_count': 0
            }
        job = ogo.find_job_to_run()
        self.assertEqual(job, 'item1')

    def test_oneitem_failure_within_freq_no_cooloff(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.validate_oaat_type()
        ogo.items.obj.setdefault(
            'status',
            {}).setdefault('items', {})['item1'] = {
                'last_failure': oaatoperator.utility.now_iso(),
                'failure_count': 0
            }
        job = ogo.find_job_to_run()
        self.assertEqual(job, 'item1')

    # inside frequency and cooloff => not valid (cooloff)
    def test_oneitem_failure_within_freq_within_cooloff(self):
        kog = deepcopy(TestData.kog)
        kog['spec']['failureCoolOff'] = '5m'
        kog['spec']['frequency'] = '10m'
        ogo = self.extraSetUp(TestData.kot, kog)
        ogo.validate_oaat_type()
        ogo.debug = unittest.mock.MagicMock()
        ogo.items.obj.setdefault(
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
            ogo.find_job_to_run()
        print(ogo.debug.call_args.args[0])
        self.assertRegex(
            ogo.debug.call_args.args[0],
            'item1 cool_off.*not expired since last failure')

    # inside frequency but outside cooloff => valid job
    def test_oneitem_failure_within_freq_outside_cooloff(self):
        kog = deepcopy(TestData.kog)
        kog['spec']['failureCoolOff'] = '1m'
        kog['spec']['frequency'] = '10m'
        ogo = self.extraSetUp(TestData.kot, kog)
        ogo.validate_oaat_type()
        ogo.debug = print
        ogo.items.obj.setdefault(
            'status',
            {}).setdefault('items', {})['item1'] = {
                'last_failure': (
                    (datetime.datetime.now(tz=UTC) -
                        datetime.timedelta(minutes=5))
                    .isoformat()),
                'failure_count': 0
            }
        job = ogo.find_job_to_run()
        self.assertEqual(job, 'item1')

    # outside frequency but inside cooloff => not valid (cooloff)
    def test_oneitem_failure_outside_freq_within_cooloff(self):
        kog = deepcopy(TestData.kog)
        kog['spec']['failureCoolOff'] = '10m'
        kog['spec']['frequency'] = '1m'
        ogo = self.extraSetUp(TestData.kot, kog)
        ogo.validate_oaat_type()
        ogo.items.obj.setdefault(
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
            ogo.find_job_to_run()

    # outside both frequency and cooloff => valid job
    def test_oneitem_failure_outside_freq_outside_cooloff(self):
        kog = deepcopy(TestData.kog)
        kog['spec']['failureCoolOff'] = '5m'
        kog['spec']['frequency'] = '1m'
        ogo = self.extraSetUp(TestData.kot, kog)
        ogo.validate_oaat_type()
        ogo.items.obj.setdefault(
            'status',
            {}).setdefault('items', {})['item1'] = {
                'last_failure': (
                    (datetime.datetime.now(tz=UTC) -
                        datetime.timedelta(minutes=10))
                    .isoformat()),
                'failure_count': 1
            }
        job = ogo.find_job_to_run()
        self.assertEqual(job, 'item1')

    # should mock randrange to validate this
    def test_5_noprevious_run(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog5)
        ogo.validate_oaat_type()
        job = ogo.find_job_to_run()
        self.assertIn(job, ('item1', 'item2', 'item3', 'item4', 'item5'))

    def test_5_single_oldest(self):
        kog = deepcopy(TestData.kog5)
        ogo = self.extraSetUp(TestData.kot, kog)
        ogo.validate_oaat_type()
        success = (datetime.datetime.now(tz=UTC) -
                   datetime.timedelta(minutes=5)).isoformat()
        osuccess = (datetime.datetime.now(tz=UTC) -
                    datetime.timedelta(minutes=7)).isoformat()
        for i in kog['spec']['oaatItems']:
            ogo.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})[i] = {
                    'last_success': success,
                    'failure_count': 0
                }
        ogo.items.obj['status']['items']['item3']['last_success'] = osuccess
        job = ogo.find_job_to_run()
        self.assertEqual(job, 'item3')

    def test_5_single_oldest_failure(self):
        kog = deepcopy(TestData.kog5)
        ogo = self.extraSetUp(TestData.kot, kog)
        ogo.validate_oaat_type()
        ogo.debug = print
        success = ((datetime.datetime.now(tz=UTC) -
                    datetime.timedelta(minutes=5)).isoformat())
        failure = (datetime.datetime.now(tz=UTC) -
                   datetime.timedelta(minutes=7)).isoformat()
        for i in kog['spec']['oaatItems']:
            ogo.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})[i] = {
                    'last_success': success,
                    'failure_count': 0
                }
        ogo.items.obj['status']['items']['item4']['last_failure'] = failure
        ogo.items.obj['status']['items']['item4']['failure_count'] = 1
        job = ogo.find_job_to_run()
        self.assertEqual(job, 'item4')

    def test_5_single_multiple_failure(self):
        kog = deepcopy(TestData.kog5)
        ogo = self.extraSetUp(TestData.kot, kog)
        ogo.validate_oaat_type()
        ogo.debug = print
        success = (datetime.datetime.now(tz=UTC) -
                   datetime.timedelta(minutes=5)).isoformat()
        failure = (datetime.datetime.now(tz=UTC) -
                   datetime.timedelta(minutes=7)).isoformat()
        for i in kog['spec']['oaatItems']:
            ogo.items.obj.setdefault(
                'status',
                {}).setdefault('items', {})[i] = {
                    'last_success': success,
                    'failure_count': 0
                }
        ogo.items.obj['status']['items']['item4']['last_failure'] = failure
        ogo.items.obj['status']['items']['item4']['failure_count'] = 1
        ogo.items.obj['status']['items']['item2']['last_failure'] = failure
        ogo.items.obj['status']['items']['item2']['failure_count'] = 1
        job = ogo.find_job_to_run()
        self.assertIn(job, ('item4', 'item2'))


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def tearDown(self):
        return super().tearDown()

    def extraSetUp(self, kot, kog):
        self.kw = TestData.setup_kwargs(deepcopy(kog))
        self.setup_kot = object_setUp(KubeOaatType, deepcopy(kot))
        self.setup = object_setUp(KubeOaatGroup, deepcopy(kog))
        next(self.setup_kot)
        next(self.setup)
        ogo = OaatGroup(kopf_object=self.kw)
        self.assertIsInstance(ogo, OaatGroup)
        self.assertIsInstance(ogo.kopf_object, OaatGroupOverseer)
        self.assertIsInstance(ogo.kopf_object.oaattype, OaatType)
        return ogo

    def test_validate_items_none(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog_empty)
        with self.assertRaisesRegex(ProcessingComplete, 'no items found.*'):
            ogo.validate_items()

    def test_validate_items_none_annotation(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog_empty)
        with self.assertRaisesRegex(ProcessingComplete, 'no items found.*'):
            ogo.validate_items(
                status_annotation='test-status',
                count_annotation='test-items')
        self.assertEqual(
            ogo.kopf_object.patch['metadata']['annotations'].get(
                'kawaja.net/test-status'), 'missingItems')
        self.assertEqual(
            ogo.kopf_object.patch['metadata']['annotations'].get(
                'kawaja.net/test-items'), None)

    def test_validate_items_one_annotation(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.validate_items(
            status_annotation='test-status',
            count_annotation='test-items')
        self.assertEqual(
            ogo.kopf_object.patch['metadata']['annotations'].get(
                'kawaja.net/test-status'), 'active')
        self.assertEqual(
            ogo.kopf_object.patch['metadata']['annotations'].get(
                'kawaja.net/test-items'), '1')

    def test_validate_state_pod_cr(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.kw.setdefault('status', {})['pod'] = 'podname'
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        self.assertIsNone(ogo.validate_state())

    def test_validate_is_pod_expected(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.assertFalse(ogo.is_pod_expected())
        self.kw.setdefault('status', {})['pod'] = 'podname'
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        self.assertTrue(ogo.is_pod_expected())

    def test_validate_expected_pod(self):
        pod1 = pykube.Pod(self.api, TestData.pod_spec)
        pod1.create()
        while not pod1.ready:
            pod1.reload()
            sleep(1)
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.assertFalse(ogo.is_pod_expected())
        self.kw.setdefault('status', {})['pod'] = pod1.name
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        self.assertEqual(ogo.get_status('pod'), pod1.name)
        with self.assertRaisesRegex(ProcessingComplete,
                                    'Pod.*exists and is in state'):
            ogo.validate_expected_pod_is_running()
        pod1.obj['metadata']['labels'] = None
        pod1.update()
        pod1.delete()

    def test_validate_expected_pod_negative(self):
        pod1 = pykube.Pod(self.api, TestData.pod_spec)
        pod1.create()
        while not pod1.ready:
            pod1.reload()
            sleep(1)
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.assertFalse(ogo.is_pod_expected())
        self.kw.setdefault('status', {})['pod'] = f'not-{pod1.name}'
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        with self.assertRaisesRegex(ProcessingComplete,
                                    'item.*failed during validation'):
            ogo.validate_expected_pod_is_running()
        pod1.obj['metadata']['labels'] = None
        pod1.update()
        pod1.delete()

    def test_validate_no_rogue(self):
        pod1 = pykube.Pod(self.api, TestData.pod_spec)
        pod1.create()
        while not pod1.ready:
            pod1.reload()
            sleep(1)
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.assertFalse(ogo.is_pod_expected())
        self.kw.setdefault('status', {})['pod'] = pod1.name
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        self.assertEqual(ogo.get_status('pod'), pod1.name)
        self.assertIsNone(ogo.validate_no_rogue_pods_are_running())
        pod1.obj['metadata']['labels'] = None
        pod1.update()
        pod1.delete()

    def test_validate_rogue_unrelated(self):
        pod1 = pykube.Pod(self.api, TestData.pod_spec)
        pod2 = pykube.Pod(self.api, TestData.pod_spec_noapp)
        pod1.create()
        pod2.create()
        while not pod1.ready:
            pod1.reload()
            sleep(1)
        while not pod2.ready:
            pod2.reload()
            sleep(1)
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.assertFalse(ogo.is_pod_expected())
        self.kw.setdefault('status', {})['pod'] = pod1.name
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        self.assertIsNone(ogo.validate_no_rogue_pods_are_running())
        pod1.reload()
        pod2.reload()
        pod1.obj['metadata']['labels'] = None
        pod2.obj['metadata']['labels'] = None
        pod1.update()
        pod2.update()
        pod1.delete()
        pod2.delete()

    def test_validate_rogue(self):
        pod1 = pykube.Pod(self.api, TestData.pod_spec)
        pod2 = pykube.Pod(self.api, TestData.pod_spec)
        pod1.create()
        pod2.create()
        while not pod1.ready:
            pod1.reload()
            sleep(1)
        while not pod2.ready:
            pod2.reload()
            sleep(1)
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.assertFalse(ogo.is_pod_expected())
        self.kw.setdefault('status', {})['pod'] = pod1.name
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        with self.assertRaisesRegex(ProcessingComplete, 'rogue pods running'):
            ogo.validate_no_rogue_pods_are_running()
        pod1.reload()
        pod2.reload()
        pod1.obj['metadata']['labels'] = None
        pod2.obj['metadata']['labels'] = None
        pod1.update()
        pod2.update()
        pod1.delete()
        pod2.delete()

    def test_validate_state_nopod_nocr(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.kw.setdefault('status', {})['pod'] = None
        self.kw.setdefault('status', {})['currently_running'] = None
        self.assertIsNone(ogo.validate_state())

    def test_validate_state_pod_nocr(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.kw.setdefault('status', {})['pod'] = 'podname'
        self.kw.setdefault('status', {})['currently_running'] = None
        with self.assertRaisesRegex(ProcessingComplete, 'internal error'):
            ogo.validate_state()

    def test_validate_state_nopod_cr(self):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        self.kw.setdefault('status', {})['pod'] = None
        self.kw.setdefault('status', {})['currently_running'] = 'itemname'
        with self.assertRaisesRegex(ProcessingComplete, 'internal error'):
            ogo.validate_state()

    # def test_validate_running_nothing_expected(self):
    #     ogo = self.extraSetUp(TestData.kot, TestData.kog)
    #     self.kw.setdefault('status', {})['pod'] = None
    #     self.kw.setdefault('status', {})['currently_running'] = None
    #     ogo.validate_running_pod()

    # def test_validate_running_expected_running_but_is_not(self):
    #     ogo = self.extraSetUp(TestData.kot, TestData.kog)
    #     self.kw.setdefault('status', {})['pod'] = 'podname'
    #     self.kw.setdefault('status', {})['currently_running'] = 'itemname'
    #     with self.assertRaises(ProcessingComplete):
    #         ogo.validate_running_pod()

    # def test_validate_running_pod_expected_running_and_is(self):


class RunItemTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def extraSetUp(self, kot, kog):
        self.kw = TestData.setup_kwargs(deepcopy(kog))
        self.setup_kot = object_setUp(KubeOaatType, deepcopy(kot))
        self.setup = object_setUp(KubeOaatGroup, deepcopy(kog))
        next(self.setup_kot)
        next(self.setup)
        ogo = OaatGroupOverseer(MagicMock(), **self.kw)
        self.assertIsInstance(ogo, OaatGroupOverseer)
        self.assertIsInstance(ogo.oaattype, OaatType)
        return ogo

    @unittest.mock.patch('kopf.adopt')
    @unittest.mock.patch('pykube.Pod')
    def test_sunny(self, pod_mock, kopf_adopt_mock):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.validate_oaat_type()
        ogo.run_item('item1')
        pod = pod_mock.call_args.args[1]
        self.assertEqual(pod['metadata']['labels']['oaat-name'], 'item1')
        self.assertEqual(
            get_env(pod['spec']['containers'][0]['env'], 'OAAT_ITEM'), 'item1')

    @unittest.mock.patch('kopf.adopt')
    @unittest.mock.patch('pykube.Pod')
    def test_podfail(self, pod_mock, kopf_adopt_mock):
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.validate_oaat_type()
        pod_instance_mock = pod_mock.return_value
        pod_instance_mock.create.side_effect = pykube.KubernetesError(
            'test error')
        with self.assertRaisesRegex(ProcessingComplete,
                                    'error creating pod for item1'):
            ogo.run_item('item1')
        print(f'pod_mock: {pod_mock.call_args}')
        pod = pod_mock.call_args.args[1]
        self.assertEqual(pod['metadata']['labels']['oaat-name'], 'item1')
        self.assertEqual(
            get_env(pod['spec']['containers'][0]['env'], 'OAAT_ITEM'), 'item1')

    @unittest.mock.patch('kopf.adopt')
    @unittest.mock.patch('pykube.Pod')
    def test_substitute(self, pod_mock, kopf_adopt_mock):
        kot = TestData.kot
        kot['spec']['podspec']['container']['command'] = [
            'a', 'b', '%%oaat_item%%', 'c'
        ]
        kot['spec']['podspec']['container']['args'] = [
            'a', 'b', '%%oaat_item%%', 'c'
        ]
        kot['spec']['podspec']['container']['env'] = [
            {'name': 'first', 'value': '%%oaat_item%%'},
            {'name': 'second', 'value': 'abc%%oaat_item%%def'},
        ]
        ogo = self.extraSetUp(TestData.kot, TestData.kog)
        ogo.validate_oaat_type()
        ogo.run_item('item1')
        pod = pod_mock.call_args.args[1]
        print(f'pod: {pod}')
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

    def extraSetUp(self, kot, kog):
        self.kw = TestData.setup_kwargs(deepcopy(kog))
        self.setup_kot = object_setUp(KubeOaatType, deepcopy(kot))
        self.setup = object_setUp(KubeOaatGroup, deepcopy(kog))
        next(self.setup_kot)
        next(self.setup)

    def test_create_none(self):
        with self.assertRaisesRegex(InternalError,
                                    'OaatGroup must be called with either.*'):
            OaatGroup()

    def test_no_kopf(self):
        kog = TestData.kog
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kube_object_name='test-kog', logger=MagicMock())
        with self.assertRaisesRegex(
                InternalError,
                'attempt to run find_job_to_run outside of kopf'):
            og.find_job_to_run()
        with self.assertRaisesRegex(
                InternalError,
                'attempt to run run_item outside of kopf'):
            og.run_item('item')
        with self.assertRaisesRegex(
                InternalError,
                'attempt to run set_status outside of kopf'):
            og.set_status('state', 'value')

    def test_create_with_kubeobj(self):
        kog = TestData.kog
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kube_object_name='test-kog', logger=MagicMock())
        self.assertIsInstance(og.kube_object, KubeOaatGroup)
        self.assertEqual(og.kopf_object, None)
        self.assertEqual(og.kube_object.name, kog['metadata']['name'])
        self.assertEqual(og.namespace(), 'default')

    def test_create_with_kopfobj(self):
        kog = TestData.kog
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        self.assertIsInstance(og.kube_object, KubeOaatGroup)
        self.assertIsInstance(og.kopf_object, OaatGroupOverseer)
        self.assertEqual(og.kube_object.name, kog['metadata']['name'])
        self.assertEqual(og.kopf_object.name, kog['metadata']['name'])
        self.assertEqual(og.namespace(), 'default')

    def test_mark_failed_invalid_finished_at(self):
        kog = TestData.kog_previous_fail
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        with self.assertRaisesRegex(
                ValueError, 'mark_item_failed finished_at= should '
                'be datetime.datetime object'):
            og.mark_item_failed(
                'item1',
                finished_at='hello')

    def test_mark_item_failed_new_failure(self):
        kog = TestData.kog_previous_fail
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        self.assertTrue(
            og.mark_item_failed(
                'item1',
                finished_at=(TestData.failure_time +
                             datetime.timedelta(hours=2))))

    def test_mark_item_failed_old_failure(self):
        kog = TestData.kog_previous_fail
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        self.assertFalse(
            og.mark_item_failed(
                'item1',
                finished_at=(TestData.failure_time -
                             datetime.timedelta(hours=2))))

    @patch('oaatoperator.utility.now')
    def test_mark_item_failed_no_date_provided(self, now):
        now.return_value = (TestData.failure_time +
                            datetime.timedelta(hours=2))
        kog = TestData.kog_previous_fail
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        self.assertTrue(og.mark_item_failed('item1'))

    def test_mark_success_invalid_finished_at(self):
        kog = TestData.kog_previous_success
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        with self.assertRaisesRegex(
                ValueError, 'mark_item_success finished_at= should '
                'be datetime.datetime object'):
            og.mark_item_success(
                'item1',
                finished_at='hello')

    def test_mark_item_success_new_success(self):
        kog = TestData.kog_previous_success
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        self.assertTrue(
            og.mark_item_success(
                'item1',
                finished_at=(TestData.success_time +
                             datetime.timedelta(hours=2))))

    def test_mark_item_success_old_success(self):
        kog = TestData.kog_previous_success
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        self.assertFalse(
            og.mark_item_success(
                'item1',
                finished_at=(TestData.success_time -
                             datetime.timedelta(hours=2))))

    @patch('oaatoperator.utility.now')
    def test_mark_item_success_no_date_provided(self, now):
        now.return_value = (TestData.success_time +
                            datetime.timedelta(hours=2))
        kog = TestData.kog_previous_fail
        self.extraSetUp(TestData.kot, kog)
        og = OaatGroup(kopf_object={**self.kw})
        self.assertTrue(og.mark_item_success('item1'))

    def test_find_job_oneitem_noprevious_run(self):
        self.extraSetUp(TestData.kot, TestData.kog)
        og = OaatGroup(kopf_object={**self.kw})
        job = og.find_job_to_run()
        self.assertEqual(job, 'item1')

    @unittest.mock.patch('kopf.adopt')
    @unittest.mock.patch('pykube.Pod')
    def test_run_item_sunny(self, pod_mock, kopf_adopt_mock):
        self.extraSetUp(TestData.kot, TestData.kog)
        og = OaatGroup(kopf_object={**self.kw})
        og.run_item('item1')
        pod = pod_mock.call_args.args[1]
        self.assertEqual(pod['metadata']['labels']['oaat-name'], 'item1')
        self.assertEqual(
            get_env(pod['spec']['containers'][0]['env'], 'OAAT_ITEM'), 'item1')

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
# - validate_state()
#   X invalid state (failed pod creation)
#   X valid states
# - validate_running_pod()
#   X nothing expected to be running
#   X expected to be running, but not
#   - expected to be running, and is
#   - running with phase update
#   - succeeded, but not yet acknowledged
#   - unexpected state
