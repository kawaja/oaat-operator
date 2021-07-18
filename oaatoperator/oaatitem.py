"""
oaatitem.py

Manage OaatItems within an OaatGroup.
"""

import datetime
from oaatoperator.utility import date_from_isostr


class OaatItems:
    def __init__(self, obj: dict) -> None:
        self.obj = obj

    def status(self, item_name: str, key: str, default: str = None) -> str:
        """Get the status of an item. """
        return (self.obj
                .get('status', {})
                .get('items', {})
                .get(item_name, {})
                .get(key, default))

    def status_date(self,
                    item_name: str,
                    key: str,
                    default: str = None) -> datetime.datetime:
        """Get the status of a specific item, returned as a datetime."""
        return date_from_isostr(self.status(item_name, key, default))

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
