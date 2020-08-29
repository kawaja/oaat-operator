from unittest.mock import MagicMock, patch, call
import unittest
import datetime

import oaatgroup
import common
from oaatitem import OaatItems


class OaatGroupTests(unittest.TestCase):
    def setUp(self):
        self.dt = datetime.datetime.now(tz=datetime.timezone.utc)
        self.og_populated = MagicMock(
            spec=oaatgroup.OaatGroupOverseer,
            kwargs={
                'patch': {'status': {}},
                'status': {
                    'items': {
                        'item': {
                            'test': 5,
                            'test_date': self.dt.isoformat()
                        }
                    }
                }
            }
        )
        self.og_empty = MagicMock(
            spec=oaatgroup.OaatGroupOverseer,
            kwargs={
                'patch': {'status': {}},
                'status': {}
            }
        )

    def test_create_oaatgroup(self):
        og = self.og_empty
        items = OaatItems(oaatgroupobject=og)
        self.assertIsInstance(items, OaatItems)
        self.assertIsInstance(items.oaatgroup, oaatgroup.OaatGroupOverseer)
        self.assertIsInstance(items.obj, dict)
        self.assertIsNone(items.kubeobject)

    def test_status_oaatgroup(self):
        og = self.og_populated
        items = OaatItems(oaatgroupobject=og)
        self.assertEqual(items.status('item', 'test'), 5)

    def test_status_date_oaatgroup(self):
        og = self.og_populated
        items = OaatItems(oaatgroupobject=og)
        rdt = items.status_date('item', 'test_date')
        self.assertIsInstance(rdt, datetime.datetime)
        self.assertEqual(rdt, self.dt)

    def test_set_status_oaatgroup(self):
        og = self.og_empty
        items = OaatItems(oaatgroupobject=og)
        items.set_status('item', 'test', 5)
        self.assertEqual(
            og.kwargs['patch']['status']['items']['item']['test'], 5)

    def test_set_phase_oaatgroup(self):
        og = self.og_empty
        items = OaatItems(oaatgroupobject=og)
        items.set_phase('item', 'Phase')
        self.assertEqual(
            og.kwargs['patch']['status']['items']['item']['podphase'], 'Phase')


class KubeTests(unittest.TestCase):
    def setUp(self):
        self.dt = datetime.datetime.now(tz=datetime.timezone.utc)
        self.k_empty = MagicMock(
            spec=common.KubeOaatGroup,
            obj={}
        )
        self.k_populated = MagicMock(
            spec=common.KubeOaatGroup,
            obj={
                'spec': {
                    'frequency': '1d',
                    'failureCoolOff': {
                        'duration': '4h'
                    },
                    'windows': {
                        'noStartItem': {
                            'start': {
                                'time': '06:00',
                            },
                            'end': {
                                'time': '21:00'
                            }
                        },
                    },
                    'oaatType': 'testtype',
                    'oaatItems': [
                        'item1',
                        'item2',
                        'item3'
                    ]
                },
                'status': {
                    'items': {
                        'item': {
                            'test': 5,
                            'test_date': self.dt.isoformat()
                        }
                    }
                }
            }
        )

    def test_create_kube(self):
        k = self.k_empty
        items = OaatItems(kubeobject=k)
        self.assertIsInstance(items, OaatItems)
        self.assertIsInstance(items.kubeobject, common.KubeOaatGroup)
        self.assertIsInstance(items.obj, dict)
        self.assertIsNone(items.oaatgroup)

    def test_status_kube(self):
        k = self.k_populated
        items = OaatItems(kubeobject=k)
        self.assertEqual(items.status('item', 'test'), 5)

    def test_status_date_kube(self):
        k = self.k_populated
        items = OaatItems(kubeobject=k)
        rdt = items.status_date('item', 'test_date')
        self.assertIsInstance(rdt, datetime.datetime)
        self.assertEqual(rdt, self.dt)

    def test_set_status_kube(self):
        k = self.k_empty
        items = OaatItems(kubeobject=k)
        items.set_status('item', 'test', 5)
        k.patch.assert_called_once_with(
            {'status': {'items': {'item': {'test': 5}}}})

    def test_set_phase_kube(self):
        k = self.k_empty
        items = OaatItems(kubeobject=k)
        items.set_phase('item', 'Phase')
        k.patch.assert_called_once_with(
            {'status': {'items': {'item': {'podphase': 'Phase'}}}})

    def test_mark_failed_kube_with_invalid_when(self):
        k = self.k_empty
        items = OaatItems(kubeobject=k)
        with self.assertRaises(ValueError):
            items.mark_failed('item', when=self.dt)

    def test_mark_failed_kube_with_when(self):
        k = self.k_empty
        items = OaatItems(kubeobject=k)
        items.mark_failed('item', when=self.dt.isoformat())
        self.assertEqual(
            k.method_calls[0],
            call.patch({'status': {'items': {'item': {'failure_count': 1}}}}))
        self.assertEqual(
            k.method_calls[1],
            call.patch({'status': {'items': {'item': {
                'last_failure': self.dt.isoformat()
            }}}}))

    @patch('utility.datetime', autospec=True)
    def test_mark_failed_kube_without_when(self, mock_dt):
        k = self.k_empty
        mock_dt.datetime.now.return_value = self.dt
        items = OaatItems(kubeobject=k)
        items.mark_failed('item')
        print(k.call_args_list)
        print(k.method_calls)
        print(type(k.method_calls[0]))
        print(type(k.method_calls[0].patch))
        print(k.method_calls[0].patch)
        self.assertEqual(
            k.method_calls[0],
            call.patch({'status': {'items': {'item': {'failure_count': 1}}}}))
        self.assertEqual(
            k.method_calls[1],
            call.patch({'status': {'items': {'item': {
                'last_failure': self.dt.isoformat()
            }}}}))

    def test_mark_success_self(self):
        k = self.k_empty
        items = OaatItems(kubeobject=k)
        with self.assertRaises(ValueError):
            items.mark_success('item', when=self.dt)

    def test_mark_success_kube_with_when(self):
        k = self.k_empty
        items = OaatItems(kubeobject=k)
        items.mark_success('item', when=self.dt.isoformat())
        self.assertEqual(
            k.method_calls[0],
            call.patch({'status': {'items': {'item': {'failure_count': 0}}}}))
        self.assertEqual(
            k.method_calls[1],
            call.patch({'status': {'items': {'item': {
                'last_success': self.dt.isoformat()
            }}}}))

    @patch('utility.datetime', autospec=True)
    def test_mark_success_kube_without_when(self, mock_dt):
        k = self.k_empty
        mock_dt.datetime.now.return_value = self.dt
        items = OaatItems(kubeobject=k)
        items.mark_success('item')
        self.assertEqual(
            k.method_calls[0],
            call.patch({'status': {'items': {'item': {'failure_count': 0}}}}))
        self.assertEqual(
            k.method_calls[1],
            call.patch({'status': {'items': {'item': {
                'last_success': self.dt.isoformat()
            }}}}))

    def test_count(self):
        k = self.k_populated
        items = OaatItems(kubeobject=k)
        self.assertEqual(items.count(), 3)

    def test_list(self):
        k = self.k_populated
        items = OaatItems(kubeobject=k)
        self.assertEqual(items.list()[0]['name'], 'item1')
        self.assertEqual(items.list()[1]['name'], 'item2')
        self.assertEqual(items.list()[2]['name'], 'item3')
        self.assertEqual(items.list()[0]['numfails'], 0)
        self.assertEqual(items.list()[1]['numfails'], 0)
        self.assertEqual(items.list()[2]['numfails'], 0)
