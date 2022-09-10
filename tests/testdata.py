import unittest
from copy import deepcopy
import oaatoperator.utility
import logging

class TestData:
    @classmethod
    def setup_kwargs(cls, input_obj):
        obj = deepcopy(input_obj)
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
    failure_count = 1
    kog_previous_fail['status']['items'] = {
        'item1': {
            'failure_count': failure_count,
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

