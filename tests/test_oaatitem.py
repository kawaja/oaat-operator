from unittest.mock import MagicMock  # , patch, call
import unittest
import datetime

from tests.testdata import TestData
from oaatoperator.oaatitem import OaatItem, OaatItems


class OaatItemTests(unittest.TestCase):
    def test_create(self):
        oi = OaatItem({}, 'item1')

    def test_success(self):
        oi = OaatItem(TestData.kog_previous_success, 'item1')
        self.assertEqual(oi.success(), TestData.success_time)

    def test_failure(self):
        oi = OaatItem(TestData.kog_previous_fail, 'item1')
        self.assertEqual(oi.failure(), TestData.failure_time)
        self.assertEqual(oi.numfails(), TestData.failure_count)
