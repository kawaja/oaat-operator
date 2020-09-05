import unittest
from copy import deepcopy
import datetime

from mocks_pykube import object_setUp
from oaatgroup import OaatGroupOverseer
from oaattype import OaatType
from common import KubeOaatGroup, KubeOaatType, ProcessingComplete
import pykube
from unittest.mock import MagicMock
import logging

# TODO: This expects a kubernetes cluster (like minikube). It would be better
# to use a mocking library to handle unit testing locally.


class BasicTests(unittest.TestCase):
    kot = {
        'apiVersion': 'kawaja.net/v1',
        'kind': 'OaatType',
        'metadata': {
            'name': 'test-kot'
        },
        'spec': {
            'type': 'pod',
            'podspec': {
                'container': {
                    'name': 'test',
                    'image': 'busybox',
                    'command': ['sh', '-x', '-c'],
                    'args': [
                        'echo "OAAT_ITEM={{oaat_item}}"\n'
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
            'name': 'test-kog'
        },
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
            'logger': MagicMock(spec=logging.Logger),
            'patch': {},
            'memo': {},
            'event': {},
            'reason': '',
            'old': {}, 'new': {}, 'diff': {}
        }

    def setUp(self):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        return super().setUp()

    def tearDown(self):
        return super().tearDown()

#    @pytest.mark.usefixtures('login_mocks')
    def test_create_none(self):
        kog = BasicTests.kog
        kw = self.setup_kwargs(kog)
        setup_kot = object_setUp(KubeOaatType, BasicTests.kot)
        setup = object_setUp(KubeOaatGroup, kog)
        next(setup_kot)
        next(setup)
        ogo = OaatGroupOverseer(**kw)
        self.assertIsInstance(ogo, OaatGroupOverseer)
        self.assertEqual(ogo.freq, datetime.timedelta(seconds=60))
        self.assertIsInstance(ogo.oaattype, OaatType)
        next(setup)  # delete KubeOaatGroup
        next(setup_kot)  # delete KubeOaatType

#    @pytest.mark.usefixtures('login_mocks')
    def test_validate_type(self):
        kog = BasicTests.kog
        kw = self.setup_kwargs(kog)
        setup_kot = object_setUp(KubeOaatType, BasicTests.kot)
        setup = object_setUp(KubeOaatGroup, kog)
        next(setup_kot)
        next(setup)
        ogo = OaatGroupOverseer(**kw)
        ogo.validate_oaat_type()
        next(setup)  # delete KubeOaatGroup
        next(setup_kot)  # delete KubeOaatType

#    @pytest.mark.usefixtures('login_mocks')
    def test_invalid_object(self):
        with self.assertRaises(ValueError) as exc:
            OaatGroupOverseer(a=1)
        self.assertEqual(str(exc.exception),
                         'Overseer must be called with kopf kwargs')

    def test_invalid_none(self):
        with self.assertRaises(TypeError):
            OaatGroupOverseer(None)

    def test_podspec_emptyspec(self):
        kog = BasicTests.kog_emptyspec
        kw = self.setup_kwargs(kog)
        setup_kot = object_setUp(KubeOaatType, BasicTests.kot)
        setup = object_setUp(KubeOaatGroup, kog)
        next(setup_kot)
        next(setup)
        og = OaatGroupOverseer(**kw)
        with self.assertRaises(ProcessingComplete) as exc:
            og.validate_oaat_type()
        self.assertEqual(exc.exception.ret['error'],
                         'unknown oaat type None')
        next(setup)
        next(setup_kot)

# TODO:
# - find_job_to_run()
#   - no items
#   - one item
#   - no items within 'frequency'
#   - failed items within 'cool off'
#   - single oldest success
#   - multiple oldest success single oldest failure
#   - multiple oldest success multiple oldest failure (mock random)
# - run_item()
#   - valid spec
#   - invalid spec
#   - %%oaat_item%% substitution
# - validate_items()
#   - no items
#   - set annotations
# - validate_state()
#   - invalid state (failed pod creation)
#   - valid state
# - validate_running_pod()
#   - nothing expected to be running
#   - expected to be running, but not
#   - expected to be running, and is
#   - running with phase update
#   - succeeded, but not yet acknowledged
#   - unexpected state
