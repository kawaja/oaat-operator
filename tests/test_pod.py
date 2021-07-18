import unittest
# from copy import deepcopy
import datetime

from tests.mocks_pykube import object_setUp
from oaatoperator.pod import PodOverseer
from oaatoperator.common import ProcessingComplete
import oaatoperator.utility
import pykube
from pykube import Pod
import unittest.mock
from unittest.mock import patch, call
import copy
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
            'namespace': body.get('metadata', {}).get('namespace'),
            'name': body.get('metadata', {}).get('name'),
            'uid': body.get('metadata', {}).get('uid'),
            'labels': body.get('metadata', {}).get('labels'),
            'annotations': body.get('metadata', {}).get('annotations'),
            'logger': unittest.mock.MagicMock(spec=logging.Logger),
            'patch': {},
            'memo': {},
            'event': {},
            'reason': '',
            'old': {}, 'new': {}, 'diff': {}
        }

    kp = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {
            'name': 'test-kp',
            'labels': {'parent-name': 'test-kog', 'oaat-name': 'item'}
        },
        'status': {
            'phase': 'Running'
        },
        'spec': {
            'containers': [
                {
                    'name': 'test',
                    'image': 'busybox',
                    'command': ['sh', '-x', '-c'],
                    'args': [
                        'echo "OAAT_ITEM=%%oaat_item%%"\n'
                        'sleep $(shuf -i 10-180 -n 1)\n'
                        'exit $(shuf -i 0-1 -n 1)\n'
                    ],
                }
            ]
        }
    }

    failure_time = oaatoperator.utility.now()
    kp_failure = copy.deepcopy(kp)
    kp_failure['status'] = {
        'phase': 'Failed',
        'containerStatuses': [{
            'state': {
                'terminated': {
                    'exitCode': 5,
                    'finishedAt': failure_time.isoformat()
                }
            }
        }]
    }

    success_time = oaatoperator.utility.now()
    kp_success = copy.deepcopy(kp)
    kp_success['status'] = {
        'phase': 'Completed',
        'containerStatuses': [{
            'state': {
                'terminated': {
                    'exitCode': 0,
                    'finishedAt': success_time.isoformat()
                }
            }
        }]
    }

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


class BasicTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def test_create(self):
        kp = TestData.kp
        kw = TestData.setup_kwargs(kp)
        setup_kp = object_setUp(Pod, TestData.kp)
        next(setup_kp)
        op = PodOverseer(**kw)
        self.assertIsInstance(op, PodOverseer)
        next(setup_kp)  # delete Pod

    def test_invalid_object(self):
        with self.assertRaises(ValueError) as exc:
            PodOverseer(a=1)
        self.assertRegex(
            str(exc.exception),
            'Overseer must be called with full kopf kwargs.*')

    def test_invalid_none(self):
        with self.assertRaises(TypeError):
            PodOverseer(None)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    @patch('oaatoperator.pod.OaatGroup', spec=True)
    def test_success(self, og):
        og.kopf_object = TestData.kog_empty
        op = TestData.setup_kwargs(TestData.kp_success)
        p = PodOverseer(**op)
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaises(ProcessingComplete):
            p.update_success_status()
        self.assertEqual(
            og().mark_item_success.call_args,
            call(op['labels']['oaat-name'],
                 finished_at=TestData.success_time))

    @patch('oaatoperator.pod.OaatGroup', spec=True)
    def test_failure(self, og):
        og.kopf_object = TestData.kog_empty
        op = TestData.setup_kwargs(TestData.kp_failure)
        p = PodOverseer(**op)
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaises(ProcessingComplete):
            p.update_failure_status()
        self.assertEqual(
            og().mark_item_failed.call_args,
            call(op['labels']['oaat-name'],
                 finished_at=TestData.failure_time,
                 exit_code=op['status']['containerStatuses'][0]['state']
                 ['terminated']['exitCode']))

    @patch('oaatoperator.pod.OaatGroup', spec=True)
    def test_update_phase(self, og):
        og.kopf_object = TestData.kog_empty
        op = TestData.setup_kwargs(TestData.kp)
        p = PodOverseer(**op)
        self.assertIsInstance(p, PodOverseer)
        with self.assertRaisesRegex(
                ProcessingComplete, f'updating phase for pod {op["name"]}: '
                f'{op["status"]["phase"]}'):
            p.update_phase()
        print(og.call_args_list)
