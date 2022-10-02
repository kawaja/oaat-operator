from time import sleep
from copy import deepcopy
from typing import Type
import dataclasses

from unittest.mock import Mock
import pytest
# import pytest_mock

import pykube


@dataclasses.dataclass(frozen=True, eq=False, order=False)
class LoginMocks:
    pykube_in_cluster: Mock
    pykube_from_file: Mock


@dataclasses.dataclass(frozen=True, eq=False, order=False)
class KubeOaatTypeMocks:
    pykube_in_cluster: Mock
    pykube_from_file: Mock


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
        else:
            print(f'[ensure_kubeobj_deleted] {name} deleted')


def ensure_kubeobj_exists(ktype: Type[pykube.objects.APIObject], spec: dict,
                          name: str):
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


class KubeObject:
    def __init__(self, ktype: Type[pykube.objects.APIObject],
                 input_spec: dict):
        self.spec = deepcopy(input_spec)
        self.type = ktype
        self.name = self.spec.get('metadata', {}).get('name', 'unknown')
        if self.name == 'unknown':
            raise ValueError(f'kube object {ktype} is missing name')

    def __enter__(self):
        kobj = ensure_kubeobj_deleted(self.type, self.name)
        kobj = ensure_kubeobj_exists(self.type, self.spec, self.name)
        return kobj

    def __exit__(self, exc_type, exc_value, exc_tb):
        print(f'[KubeObject] about to delete {self.name} ({self.type})')
        ensure_kubeobj_deleted(self.type, self.name)
        print(f'[KubeObject] deleted {self.name} ({self.type})')


class KubeObjectPod:
    def __init__(self, input_spec: dict):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.spec = deepcopy(input_spec)

    def __enter__(self) -> pykube.Pod:
        self.kobj = pykube.Pod(self.api, self.spec)
        self.kobj.create()
        while not self.kobj.ready:
            self.kobj.reload()
            sleep(1)
        return self.kobj

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        name = self.kobj.name
        print(f'[KubeObjectPod] about to delete {name}')
        # remove labels in case it takes a while for
        # the Pod to delete to avoid clashing with
        # future tests
        self.kobj.reload()
        self.kobj.obj['metadata']['labels'] = None
        self.kobj.update()
        self.kobj.delete()
        print(f'[KubeObjectPod] deleted {name}')
