"""
oaatitem.py

Manage OaatItems within an OaatGroup.
"""

import datetime
from oaatoperator.utility import now_iso, date_from_isostr
from oaatoperator.common import InternalError


class OaatItems:
    def __init__(self, set_item_status, obj: dict) -> None:
        self.set_item_status_func = set_item_status
        self.obj = obj

    def status(self, name: str, key: str, default: str = None) -> str:
        """Get the status of an item. """
        return (self.obj
                .get('status', {})
                .get('items', {})
                .get(name, {})
                .get(key, default))

    def status_date(self,
                    item: str,
                    key: str,
                    default: str = None) -> datetime.datetime:
        """Get the status of a specific item, returned as a datetime."""
        return date_from_isostr(self.status(item, key, default))

    def set_item_status(self, item: str, key: str, value: str = None) -> None:
        """Set the status of a specific item."""
        if self.set_item_status_func is None:
            raise InternalError(
                f'{self.__class__.__name__} missing set_item_status')
        self.set_item_status_func(item=item, key=key, value=value)

    def set_phase(self, item: str, value: str) -> None:
        """Set the phase of a specific item."""
        self.set_item_status(item, 'podphase', value)

    def mark_failed(self, name: str, when: str = None) -> None:
        """Mark an item as failed."""
        if not when:
            when = now_iso()

        if not isinstance(when, str):
            raise ValueError('mark_failed when= should be iso date string')

        failure_count = self.status(name, 'failure_count', 0)
        self.set_item_status(name, 'failure_count', failure_count + 1)
        self.set_item_status(name, 'last_failure', when)

    def mark_success(self, name: str, when: str = None) -> None:
        """Mark an item as succeeded."""
        if not when:
            when = now_iso()

        if not isinstance(when, str):
            raise ValueError('mark_success when= should be iso date string')

        self.set_item_status(name, 'failure_count', 0)
        self.set_item_status(name, 'last_success', when)

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

    def __len__(self) -> int:
        return len(self.obj.get('spec', {}).get('oaatItems', []))
