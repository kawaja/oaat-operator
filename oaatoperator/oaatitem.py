"""
oaatitem.py

Manage OaatItems within an OaatGroup.
"""

from __future__ import annotations
import datetime
import kopf
import pykube
from typing import Any, Optional, TYPE_CHECKING

from oaatoperator.utility import date_from_isostr
from oaatoperator.common import ProcessingComplete


if TYPE_CHECKING:
    from oaatoperator.oaatgroup import OaatGroup

class OaatItem:
    name : str
    group : OaatGroup
    def __init__(self, group: OaatGroup, item_name: str) -> None:
        self.name = item_name
        self.group = group
        self._status = (group.status.get('items', {}).get(self.name, {}))

    def status(self, key: str, default: Optional[str] = None) -> str:
        """Get the status of an item. """
        return (self._status.get(key, default))

    def status_date(self,
                    key: str,
                    default: Optional[str] = None) -> datetime.datetime:
        """Get the status of a specific item, returned as a datetime."""
        print(f'key: {key}, default: {default}, _status: {self._status}, date: {self._status.get(key,default)}')
        return date_from_isostr(self._status.get(key, default))

    def success(self) -> datetime.datetime:
        return self.status_date('last_success')

    def failure(self) -> datetime.datetime:
        return self.status_date('last_failure')

    def numfails(self) -> int:
        return int(self.status('failure_count', '0'))

    def run(self) -> pykube.Pod:
        """
        run

        Execute an item job Pod with the spec details from the appropriate
        OaatType object.
        """
        # TODO: check oaatType
        spec = self.group.oaattype.podspec()
        contspec = spec['container']
        del spec['container']
        contspec.setdefault('env', []).append({
            'name': 'OAAT_ITEM',
            'value': self.name
        })
        for idx in range(len(contspec.get('command', []))):
            contspec['command'][idx] = (
                contspec['command'][idx].replace('%%oaat_item%%', self.name))
        for idx in range(len(contspec.get('args', []))):
            contspec['args'][idx] = (
                contspec['args'][idx].replace('%%oaat_item%%', self.name))
        for env in contspec['env']:
            env['value'] = (
                env.get('value', '').replace('%%oaat_item%%', self.name))

        # TODO: currently only supports a single container. Do we want
        # multi-container?
        doc = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'generateName': self.group.name + '-' + self.name + '-',
                'labels': {
                    'parent-name': self.group.name,
                    'oaat-name': self.name,
                    'app': 'oaat-operator'
                }
            },
            'spec': {
                'containers': [contspec],
                **spec,
                'restartPolicy': 'Never'
            },
        }

        kopf.adopt(doc)
        pod = pykube.Pod(self.group.api, doc)

        try:
            pod.create()
        except pykube.exceptions.KubernetesError as exc:
            self.group.mark_item_failed(self.name)
            raise ProcessingComplete(
                error=f'could not create pod {doc}: {exc}',
                message=f'error creating pod for {self.name}')
        return pod

class OaatItems:
    def __init__(self, group: OaatGroup, obj: dict[str, Any]) -> None:
        if not isinstance(obj, dict):
            print(f'obj: {obj}')
            raise TypeError(f'obj should be dict, not {type(obj)}={obj}')
        self.obj = obj
        self.group = group

    def get(self, item_name) -> OaatItem:
        return OaatItem(self.group, item_name)

    def list(self) -> list:
        """Return the names of all items in a list."""
        return [
            OaatItem(self.group, item_name)
            for item_name in self.obj.get('spec', {}).get('oaatItems', [])
        ]

#    def run(self) -> None:
#        pass

    def __len__(self) -> int:
        return len(self.obj.get('spec', {}).get('oaatItems', []))
