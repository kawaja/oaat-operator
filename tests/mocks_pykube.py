from unittest.mock import Mock
import pytest
# import pytest_mock
import dataclasses

import pykube
from time import sleep
from copy import deepcopy


@dataclasses.dataclass(frozen=True, eq=False, order=False)
class LoginMocks:
    pykube_in_cluster: Mock = None
    pykube_from_file: Mock = None


@dataclasses.dataclass(frozen=True, eq=False, order=False)
class KubeOaatTypeMocks:
    pykube_in_cluster: Mock = None
    pykube_from_file: Mock = None


@pytest.fixture()
def login_mocks(mocker):
    kwargs = {}
    try:
        import pykube
    except ImportError:
        pass
    else:
        cfg = pykube.KubeConfig({
            'current-context': 'self',
            'clusters': [{
                'name': 'self',
                'cluster': {
                    'server': 'localhost'
                }
            }],
            'contexts': [{
                'name': 'self',
                'context': {
                    'cluster': 'self',
                    'namespace': 'default'
                }
            }],
        })
        kwargs.update(
            pykube_in_cluster=mocker.patch.object(pykube.KubeConfig,
                                                  'from_service_account',
                                                  return_value=cfg),
            pykube_from_file=mocker.patch.object(pykube.KubeConfig,
                                                 'from_file',
                                                 return_value=cfg),
        )
    return LoginMocks(**kwargs)


def ensure_kubeobj_deleted(type, name):
    api = pykube.HTTPClient(pykube.KubeConfig.from_env())
    print(f'[ensure_kubeobj_deleted] about to check {name}')
    try:
        kobj = type.objects(api).get_by_name(name)
        print(f'[ensure_kubeobj_deleted] {name} returned object {kobj}')
    except pykube.exceptions.ObjectDoesNotExist:
        print(f'[ensure_kubeobj_deleted] {name} does not exist')
    else:
        print(f'[ensure_kubeobj_deleted] {name} deleting {kobj}')
        kobj.delete()
        try:
            while kobj.exists():
                sleep(1)
                print(f'[ensure_kubeobj_deleted] {name} still exists')
        except pykube.ObjectDoesNotExist:
            print(f'[ensure_kubeobj_deleted] {name} now deleted')
        print(f'[ensure_kubeobj_deleted] {name} deleted')


def ensure_kubeobj_exists(ktype, spec, name):
    api = pykube.HTTPClient(pykube.KubeConfig.from_env())
    kobj = ktype(api, spec)
    print(
        f'[ensure_kubeobj_exists] about to create {ktype} {name} with {spec}')
    kobj.create()
    print(f'[ensure_kubeobj_exists] created {ktype}')
    while True:
        try:
            kobj.exists()
            sleep(1)
        except pykube.ObjectDoesNotExist:
            print(f'[ensure_kubeobj_exists] {name} does not yet exist')
        else:
            print(f'[ensure_kubeobj_exists] {name} exists')
            break
    return kobj


def object_setUp(ktype, input_spec):
    spec = deepcopy(input_spec)
    name = spec.get('metadata', {}).get('name')
    if name is None:
        raise ValueError(f'kube object {ktype} is missing name')
    kobj = ensure_kubeobj_deleted(ktype, name)
    kobj = ensure_kubeobj_exists(ktype, spec, name)
    yield kobj
    print(f'[object_setUp] about to delete {name} ({ktype})')
    ensure_kubeobj_deleted(ktype, name)
    print(f'[object_setUp] deleted {name} ({ktype})')
    yield None
