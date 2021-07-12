import unittest
# from copy import deepcopy
import datetime

from tests.mocks_pykube import object_setUp
from oaatoperator.pod import PodOverseer
import pykube
from pykube import Pod
import unittest.mock
import logging

UTC = datetime.timezone.utc


def get_env(env_array, env_var):
    for env in env_array:
        if env.get('name') == env_var:
            return env.get('value')


class TestData:
    @classmethod
    def setup_kwargs(cls, kog):
        body = {
            'spec': kog['spec'],
            'metadata': {
                'namespace': 'default',
                'name': kog.get('metadata', {}).get('name'),
                'uid': 'uid',
                'labels': {},
                'annotations': {}
            },
            'status': {}
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
            'name': 'test-kp'
        },
        'status': {},
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


class BasicTests(unittest.TestCase):
    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def test_create(self):
        kp = TestData.kp
        kw = TestData.setup_kwargs(kp)
        setup_kp = object_setUp(Pod, TestData.kp)
        next(setup_kp)
        op = PodOverseer(object, **kw)
        self.assertIsInstance(op, PodOverseer)
        next(setup_kp)  # delete Pod

    def test_invalid_object(self):
        with self.assertRaises(ValueError) as exc:
            PodOverseer(parent_type=unittest.mock.MagicMock(), a=1)
        self.assertRegex(
            str(exc.exception),
            'Overseer must be called with full kopf kwargs.*')

    def test_invalid_none(self):
        with self.assertRaises(TypeError):
            PodOverseer(unittest.mock.MagicMock(), None)

# TODO:
#   - create
