"""
oaatitem.py

Manage OaatItems within an OaatGroup.
"""

import datetime
from oaatoperator.utility import now_iso, date_from_isostr
import oaatoperator.oaatgroup
from oaatoperator.common import KubeOaatGroup


# WARNING: this code assumes the pykube object (.obj) and the kopf object
# both have the same structure

class OaatItems:
    def __init__(
            self,
            oaatgroupobject: 'oaatoperator.oaatgroup.OaatGroupOverseer' = None,
            kubeobject: 'KubeOaatGroup' = None) -> None:
        self.oaatgroup = None
        self.kubeobject = None
        self.obj = None
        if oaatgroupobject:
            self.oaatgroup = oaatgroupobject
            self.obj = oaatgroupobject.obj
        elif kubeobject:
            self.kubeobject = kubeobject
            self.obj = kubeobject.obj
        else:
            raise ValueError(
                'must supply either oaatgroup or kubeobject to OaatItems')

    # uses only common elements of pykube object and kopf object
    def status(self, name: str, key: str, default: str = None) -> str:
        """Get the status of an item. """
        return (self.obj
                .get('status', {})
                .get('items', {})
                .get(name, {})
                .get(key, default))

    # agnostic of object structure
    def status_date(self,
                    item: str,
                    key: str,
                    default: str = None) -> datetime.datetime:
        """Get the status of a specific item, returned as a datetime."""
        return date_from_isostr(self.status(item, key, default))

    # needs to support pykube object and kopf object separately
    def set_status(self, item: str, key: str, value: str = None) -> None:
        """Set the status of a specific item."""
        if self.oaatgroup:
            self._set_status_kopf(item, key, value)
        elif self.kubeobject:
            self._set_status_pykube(item, key, value)

    def _set_status_kopf(
            self, item: str, key: str, value: str = None) -> None:
        patch = (self.oaatgroup.patch
                 .setdefault('status', {})
                 .setdefault('items', {})
                 .setdefault(item, {}))
        patch[key] = value

    def _set_status_pykube(
            self, item: str, key: str, value: str = None) -> None:
        self.kubeobject.patch({
            'status': {
                'items': {
                    item: {
                        key: value
                    }
                }
            }
        })

    # agnostic of object structure
    def set_phase(self, item: str, value: str) -> None:
        """Set the phase of a specific item."""
        self.set_status(item, 'podphase', value)

    # agnostic of object structure
    def mark_failed(self, name: str, when: str = None) -> None:
        """Mark an item as failed."""
        if not when:
            when = now_iso()

        if not isinstance(when, str):
            raise ValueError('mark_failed when= should be iso date string')

        failure_count = self.status(name, 'failure_count', 0)
        self.set_status(name, 'failure_count', failure_count + 1)
        self.set_status(name, 'last_failure', when)

    # agnostic of object structure
    def mark_success(self, name: str, when: str = None) -> None:
        """Mark an item as succeeded."""
        if not when:
            when = now_iso()

        if not isinstance(when, str):
            raise ValueError('mark_success when= should be iso date string')

        self.set_status(name, 'failure_count', 0)
        self.set_status(name, 'last_success', when)

    # agnostic of object structure
    def list(self) -> list:
        """Return the names of all items in a list."""
        return [
            {
                'name': item,
                'success': self.status_date(item, 'last_success'),
                'failure': self.status_date(item, 'last_failure'),
                'numfails': self.status(item, 'failure_count', 0)
            }
            for item in self.obj.get('spec', {}).get('oaatItems', [])
        ]

    # agnostic of object structure
    def count(self) -> int:
        return len(self.obj.get('spec', {}).get('oaatItems', []))
