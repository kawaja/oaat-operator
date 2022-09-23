from copy import deepcopy
import oaatoperator.utility
import logging
import pykube

from unittest.mock import MagicMock, Mock

from oaatoperator.common import KubeOaatGroup, KubeOaatType
from oaatoperator.oaattype import OaatType


def new_mock(mock_type, mock_attrs):
    attrs = deepcopy(mock_attrs)
    mock = Mock(mock_type)
    mock.configure_mock(**attrs, obj=attrs)
    return mock


def delkey(indict, key_to_del):
    return {key: val for (key, val) in indict.items() if key != key_to_del}


class TestData:
    new_mock = new_mock

    @classmethod
    def add_og_mock_attributes(cls, og_mock):
        og_mock.oaattype = MagicMock(spec=OaatType)
        og_mock.status = {}
        og_mock.name = ''
        og_mock.api = MagicMock(spec=pykube.HTTPClient)

    @classmethod
    def setup_kwargs(cls, input_obj):
        obj = deepcopy(input_obj)
        body = {
            'spec': obj['spec'],
            'metadata': {
                'namespace': obj.get('metadata',
                                     {}).get('namespace', 'default'),
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
            'logger': MagicMock(spec=logging.Logger),
            'patch': {},
            'memo': {},
            'event': {},
            'reason': '',
            'old': {},
            'new': {},
            'diff': {}
        }

    failure_time = oaatoperator.utility.now()
    success_time = oaatoperator.utility.now()

    # Pod
    kp_spec = {
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

    kp_failure = deepcopy(kp_spec)
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

    kp_success = deepcopy(kp_spec)
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

    # KubeOaatType variants
    kot_header = {
        'apiVersion': 'kawaja.net/v1',
        'kind': 'OaatType',
        'metadata': {
            'name': 'test-kot',
            'labels': {},
            'annotations': {}
        },
        'status': {},
    }
    kot_typespec = {
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
    kot_mock = new_mock(KubeOaatType, kot_typespec)

    kot_notype_spec = {**kot_header, 'spec': {**delkey(kot_typespec, 'type')}}
    kot_spec = {**kot_header, 'spec': {**kot_typespec}}
    kot_nospec_spec = {**kot_header}
    kot_nonepodspec_spec = {
        **kot_header, 'spec': {
            'type': 'pod',
            'podspec': None
        }
    }
    kot_nopodspec_spec = {**kot_header, 'spec': {'type': 'pod'}}
    kot_nocontainer_spec = {
        **kot_header, 'spec': {
            'type': 'pod',
            'podspec': {
                'something': 1
            }
        }
    }
    kot_containers_spec = {
        **kot_header, 'spec': {
            'type': 'pod',
            'podspec': {
                'containers': 1
            }
        }
    }
    kot_restartPolicy_spec = deepcopy(kot_spec)
    kot_restartPolicy_spec['spec']['podspec']['restartPolicy'] = 'Always'

    # KubeOaatGroup variants
    kog_empty_attrs = {
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
    kog_empty_mock = new_mock(KubeOaatGroup, kog_empty_attrs)

    kog_notype_attrs = deepcopy(kog_empty_attrs)
    del kog_notype_attrs['spec']['oaatType']
    kog_notype_mock = new_mock(KubeOaatGroup, kog_notype_attrs)

    kog_noitems_attrs = deepcopy(kog_empty_attrs)
    del kog_noitems_attrs['spec']['oaatItems']
    kog_noitems_mock = new_mock(KubeOaatGroup, kog_noitems_attrs)

    kog_emptyspec_attrs = deepcopy(kog_empty_attrs)
    kog_emptyspec_attrs['spec'] = {}
    kog_emptyspec_mock = new_mock(KubeOaatGroup, kog_emptyspec_attrs)

    kog_attrs = deepcopy(kog_empty_attrs)
    kog_attrs['spec']['oaatItems'] = ['item1']
    kog_mock = new_mock(KubeOaatGroup, kog_attrs)

    kog5_attrs = deepcopy(kog_empty_attrs)
    kog5_attrs['spec']['oaatItems'] = [
        'item1', 'item2', 'item3', 'item4', 'item5'
    ]
    kog5_mock = new_mock(KubeOaatGroup, kog5_attrs)

    failure_count = 1
    kog_previous_fail_attrs = deepcopy(kog_empty_attrs)
    kog_previous_fail_attrs['status']['items'] = {
        'item1': {
            'failure_count': failure_count,
            'last_failure': failure_time.isoformat()
        }
    }
    kog_previous_fail_mock = new_mock(KubeOaatGroup, kog_previous_fail_attrs)

    kog_previous_success_attrs = deepcopy(kog_empty_attrs)
    kog_previous_success_attrs['status']['items'] = {
        'item1': {
            'failure_count': 0,
            'last_success': success_time.isoformat()
        }
    }
    kog_previous_success_mock = new_mock(KubeOaatGroup,
                                         kog_previous_success_attrs)

    # POD specifications for passing to pykube.Pod()
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
