from unittest.mock import MagicMock  # , patch, call
import unittest
import datetime

from oaatoperator.oaatgroup import OaatGroupOverseer
from oaatoperator.common import KubeOaatGroup
from oaatoperator.oaatitem import OaatItems


class OaatGroupTests(unittest.TestCase):
    def setUp(self):
        self.dt = datetime.datetime.now(tz=datetime.timezone.utc)
        self.og_populated = MagicMock(
            spec=OaatGroupOverseer,
            patch={'status': {}},
            status={
                'items': {
                    'item': {
                        'test': 5,
                        'test_date': self.dt.isoformat()
                    }
                }
            },
            obj={
                'patch': {
                    'status': {}
                },
                'status': {
                    'items': {
                        'item': {
                            'test': 5,
                            'test_date': self.dt.isoformat()
                        }
                    }
                }
            })

        self.og_empty = MagicMock(
            spec=OaatGroupOverseer,
            body={},
            patch={'status': {}},
            status={},
            obj={
                'patch': {'status': {}},
                'status': {}
            }
        )

    def test_create_oaatgroup(self):
        og = self.og_empty
        items = OaatItems(obj=og.obj)
        self.assertIsInstance(items, OaatItems)
        # self.assertIsInstance(items.oaatgroup, OaatGroupOverseer)
        self.assertIsInstance(items.obj, dict)
        # self.assertIsNone(items.kubeobject)

    def test_status_oaatgroup(self):
        og = self.og_populated
        items = OaatItems(obj=og.obj)
        self.assertEqual(items.status('item', 'test'), 5)

    def test_status_date_oaatgroup(self):
        og = self.og_populated
        items = OaatItems(obj=og.obj)
        rdt = items.status_date('item', 'test_date')
        self.assertIsInstance(rdt, datetime.datetime)
        self.assertEqual(rdt, self.dt)

    # def test_set_status_oaatgroup(self):
    #     og = self.og_empty
    #     items = OaatItems(obj=og.obj)
    #     items.set_item_status('item', 'test', 5)
    #     self.assertEqual(ss.call_args, call(item='item', key='test',
    #                                         value=5))

    # def test_set_phase_oaatgroup(self):
    #     og = self.og_empty
    #     items = OaatItems(obj=og.obj)
    #     items.set_phase('item', 'Phase')
    #     self.assertEqual(ss.call_args,
    #                      call(item='item', key='podphase', value='Phase'))


class KubeTests(unittest.TestCase):
    def setUp(self):
        self.dt = datetime.datetime.now(tz=datetime.timezone.utc)
        self.k_empty = MagicMock(
            spec=KubeOaatGroup,
            obj={}
        )
        self.k_populated = MagicMock(
            spec=KubeOaatGroup,
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
        items = OaatItems(obj=k.obj)
        self.assertIsInstance(items, OaatItems)
        self.assertIsInstance(items.obj, dict)

    def test_status_kube(self):
        k = self.k_populated
        items = OaatItems(obj=k.obj)
        self.assertEqual(items.status('item', 'test'), 5)

    def test_status_date_kube(self):
        k = self.k_populated
        items = OaatItems(obj=k.obj)
        rdt = items.status_date('item', 'test_date')
        self.assertIsInstance(rdt, datetime.datetime)
        self.assertEqual(rdt, self.dt)

    # def test_set_status_kube(self):
    #     ss = MagicMock()
    #     k = self.k_empty
    #     items = OaatItems(obj=k.obj, set_item_status=ss)
    #     items.set_item_status('item', 'test', 5)
    #     # k.patch.assert_called_once_with(
    #     # {'status': {'items': {'item': {'test': 5}}}})
    #     self.assertEqual(ss.call_args, call(item='item', key='test',
    #                                         value=5))

    # def test_set_phase_kube(self):
    #     ss = MagicMock()
    #     k = self.k_empty
    #     items = OaatItems(obj=k.obj, set_item_status=ss)
    #     items.set_phase('item', 'Phase')
    #     self.assertEqual(ss.call_args,
    #                      call(item='item', key='podphase', value='Phase'))
    #     # k.patch.assert_called_once_with(
    #     # {'status': {'items': {'item': {'podphase': 'Phase'}}}})

#     def test_mark_failed_kube_with_invalid_when(self):
#         ss = MagicMock()
#         k = self.k_empty
#         items = OaatItems(obj=k.obj, set_item_status=ss)
#         with self.assertRaises(ValueError):
#             items.mark_failed('item', when=self.dt)

#     def test_mark_failed_kube_with_when(self):
#         ss = MagicMock()
#         k = self.k_empty
#         items = OaatItems(obj=k.obj, set_item_status=ss)
#         items.mark_failed('item', when=self.dt.isoformat())
#         self.assertEqual(ss.call_args_list[0],
#                          call(item='item', key='failure_count', value=1))
#         self.assertEqual(
#             ss.call_args_list[1],
#             call(item='item', key='last_failure', value=self.dt.isoformat()))
# #        self.assertEqual(
# #            k.method_calls[0],
# #            call.patch(
# #               {'status': {'items': {'item': {'failure_count': 1}}}}))
# #        self.assertEqual(
# #            k.method_calls[1],
# #            call.patch({'status': {'items': {'item': {
# #                'last_failure': self.dt.isoformat()
# #            }}}}))

#     @patch('oaatoperator.utility.datetime', autospec=True)
#     def test_mark_failed_kube_without_when(self, mock_dt):
#         ss = MagicMock()
#         k = self.k_empty
#         mock_dt.datetime.now.return_value = self.dt
#         items = OaatItems(obj=k.obj, set_item_status=ss)
#         items.mark_failed('item')
#         self.assertEqual(ss.call_args_list[0],
#                          call(item='item', key='failure_count', value=1))
#         self.assertEqual(
#             ss.call_args_list[1],
#             call(item='item', key='last_failure', value=self.dt.isoformat()))

#     def test_mark_success_self(self):
#         ss = MagicMock()
#         k = self.k_empty
#         items = OaatItems(obj=k.obj, set_item_status=ss)
#         with self.assertRaises(ValueError):
#             items.mark_success('item', when=self.dt)

#     def test_mark_success_kube_with_when(self):
#         ss = MagicMock()
#         k = self.k_empty
#         items = OaatItems(obj=k.obj, set_item_status=ss)
#         items.mark_success('item', when=self.dt.isoformat())
#         self.assertEqual(ss.call_args_list[0],
#                          call(item='item', key='failure_count', value=0))
#         self.assertEqual(
#             ss.call_args_list[1],
#             call(item='item', key='last_success', value=self.dt.isoformat()))

#     @patch('oaatoperator.utility.datetime', autospec=True)
#     def test_mark_success_kube_without_when(self, mock_dt):
#         ss = MagicMock()
#         k = self.k_empty
#         mock_dt.datetime.now.return_value = self.dt
#         items = OaatItems(obj=k.obj, set_item_status=ss)
#         items.mark_success('item')
#         print(ss.call_args_list)
#         self.assertEqual(ss.call_args_list[0],
#                          call(item='item', key='failure_count', value=0))
#         self.assertEqual(
#             ss.call_args_list[1],
#             call(item='item', key='last_success', value=self.dt.isoformat()))

    def test_count(self):
        k = self.k_populated
        items = OaatItems(obj=k.obj)
        self.assertEqual(len(items), 3)

    def test_list(self):
        k = self.k_populated
        items = OaatItems(obj=k.obj)
        self.assertEqual(items.list()[0]['name'], 'item1')
        self.assertEqual(items.list()[1]['name'], 'item2')
        self.assertEqual(items.list()[2]['name'], 'item3')
        self.assertEqual(items.list()[0]['numfails'], 0)
        self.assertEqual(items.list()[1]['numfails'], 0)
        self.assertEqual(items.list()[2]['numfails'], 0)
