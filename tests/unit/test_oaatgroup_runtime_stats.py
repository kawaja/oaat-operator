"""Integration tests for OaatGroup runtime statistics functionality."""

import pytest
import unittest
import unittest.mock
import datetime
from unittest.mock import Mock, patch

# Test setup imports
import sys
import os
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../../oaatoperator")

from tests.unit.testdata import TestData
from tests.unit.mocks_pykube import KubeObject
from oaatoperator.oaatgroup import OaatGroup
from oaatoperator.runtime_stats import JobRuntimeStats, RuntimeStatsManager
from oaatoperator.common import KubeOaatGroup
import oaatoperator.utility

pytestmark = pytest.mark.unit


class TestOaatGroupRuntimeStatsIntegration(unittest.TestCase):
    """Test OaatGroup runtime statistics integration."""

    def setUp(self):
        self.test_data = TestData()

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_init_with_existing_runtime_stats(self, oaat_type_mock):
        """Test OaatGroup initialization with existing runtime statistics."""
        # Setup test data with existing runtime statistics
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)
        kopf_obj['status'] = {
            'items': {
                'item1': {
                    'failure_count': '0',
                    'last_success': '2024-08-10T10:00:00Z',
                    'runtime_count': '5',
                    'runtime_total': '500.0',
                    'runtime_sum_squares': '50000.0',
                    'runtime_min': '90.0',
                    'runtime_max': '110.0',
                    'runtime_sample': '[90, 95, 100, 105, 110]',
                    'runtime_last_updated': '2024-08-10T10:00:00Z'
                },
                'item2': {
                    'failure_count': '1',
                    'last_failure': '2024-08-10T09:00:00Z',
                    'runtime_count': '3',
                    'runtime_total': '300.0',
                    'runtime_sample': '[95, 100, 105]'
                }
            }
        }

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=kopf_obj)

        # Verify statistics were loaded correctly
        self.assertIsNotNone(og.runtime_stats)

        # Check item1 statistics
        item1_stats = og.runtime_stats.get_stats('item1')
        self.assertIsNotNone(item1_stats)
        self.assertEqual(item1_stats.count, 5)
        self.assertEqual(item1_stats.get_mean(), 100.0)
        self.assertEqual(item1_stats.sample, [90, 95, 100, 105, 110])

        # Check item2 statistics
        item2_stats = og.runtime_stats.get_stats('item2')
        self.assertIsNotNone(item2_stats)
        self.assertEqual(item2_stats.count, 3)
        self.assertEqual(item2_stats.get_mean(), 100.0)

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_init_with_malformed_runtime_stats(self, oaat_type_mock):
        """Test OaatGroup initialization with malformed runtime statistics."""
        # Setup test data with malformed runtime statistics
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)
        kopf_obj['status'] = {
            'items': {
                'item1': {
                    'runtime_count': 'invalid_number',  # Invalid format
                    'runtime_sample': 'invalid_json',   # Invalid JSON
                }
            }
        }

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=kopf_obj)

        # Should fall back to empty stats without crashing
        self.assertIsNotNone(og.runtime_stats)
        self.assertIsNone(og.runtime_stats.get_stats('item1'))

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_runtime_recording_end_to_end(self, oaat_type_mock):
        """Test complete runtime recording workflow."""
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=kopf_obj)

        # Mock set_item_status to track calls
        og.set_item_status = Mock()

        # Record a runtime
        start_time = oaatoperator.utility.now() - datetime.timedelta(minutes=2)
        end_time = oaatoperator.utility.now()

        og._record_item_runtime('test-item', start_time, end_time)

        # Verify statistics were recorded
        stats = og.runtime_stats.get_stats('test-item')
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 1)

        # Verify set_item_status was called with correct statistics
        call_args = [call.args for call in og.set_item_status.call_args_list]

        # Should have calls for runtime_count, runtime_total, etc.
        expected_calls = [
            ('test-item', 'runtime_count'),
            ('test-item', 'runtime_total'),
            ('test-item', 'runtime_sum_squares'),
            ('test-item', 'runtime_min'),
            ('test-item', 'runtime_max'),
            ('test-item', 'runtime_sample'),
            ('test-item', 'runtime_last_updated')
        ]

        for expected_call in expected_calls:
            self.assertTrue(
                any(call[:2] == expected_call for call in call_args),
                f"Expected call {expected_call} not found in {call_args}"
            )

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_runtime_recording_no_start_time(self, oaat_type_mock):
        """Test runtime recording with missing start time."""
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=kopf_obj)

        # Mock logger to verify debug message
        og.logger = Mock()

        # Record runtime with None start_time
        end_time = oaatoperator.utility.now()
        og._record_item_runtime('test-item', None, end_time)

        # Verify no statistics were recorded
        stats = og.runtime_stats.get_stats('test-item')
        self.assertIsNone(stats)

        # Verify debug message was logged
        og.logger.debug.assert_called_once()

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_runtime_recording_invalid_runtime(self, oaat_type_mock):
        """Test runtime recording with invalid runtime values."""
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            og = OaatGroup(kopf_object=kopf_obj)

        # Mock logger to verify warning message
        og.logger = Mock()

        # Record runtime with negative duration (end before start)
        start_time = oaatoperator.utility.now()
        end_time = start_time - datetime.timedelta(minutes=1)  # Invalid!

        og._record_item_runtime('test-item', start_time, end_time)

        # Verify no statistics were recorded
        stats = og.runtime_stats.get_stats('test-item')
        self.assertIsNone(stats)

        # Verify warning was logged
        og.logger.warning.assert_called_once()

    def test_malformed_json_in_sample(self):
        """Test handling of malformed JSON in runtime_sample field."""
        og = OaatGroup.__new__(OaatGroup)  # Create without __init__
        og.runtime_stats = RuntimeStatsManager()
        og.logger = Mock()

        # Test malformed JSON
        item_data = {
            'runtime_count': '3',
            'runtime_total': '300.0',
            'runtime_sample': 'invalid json string'
        }

        og._load_item_runtime_stats('test-item', item_data)

        # Should handle gracefully and log warning
        og.logger.warning.assert_called_once()
        self.assertIsNone(og.runtime_stats.get_stats('test-item'))

    def test_malformed_numeric_fields(self):
        """Test handling of malformed numeric fields."""
        og = OaatGroup.__new__(OaatGroup)  # Create without __init__
        og.runtime_stats = RuntimeStatsManager()
        og.logger = Mock()

        # Test malformed numeric data
        item_data = {
            'runtime_count': 'not_a_number',
            'runtime_total': 'also_not_a_number',
            'runtime_sample': '[]'
        }

        og._load_item_runtime_stats('test-item', item_data)

        # Should handle gracefully and log warning
        og.logger.warning.assert_called_once()
        self.assertIsNone(og.runtime_stats.get_stats('test-item'))


class TestRuntimeStatsEdgeCases(unittest.TestCase):
    """Test edge cases in runtime statistics that aren't covered."""

    def test_predict_runtime_p90_only(self):
        """Test prediction when only P90 is available (no std deviation)."""
        stats = JobRuntimeStats()

        # Add exactly one runtime value
        stats.add_runtime(100.0)

        # Should return the single value (both mean and P90 are 100)
        prediction = stats.predict_runtime(confidence_factor=2.0)
        self.assertEqual(prediction, 100.0)

    def test_predict_runtime_conservative_estimate_higher(self):
        """Test prediction when conservative estimate is higher than P90."""
        stats = JobRuntimeStats()

        # Add values where conservative estimate > P90
        # Values: [10, 10, 10, 10, 200] - P90=200, but high std dev
        runtimes = [10, 10, 10, 10, 200]
        for runtime in runtimes:
            stats.add_runtime(runtime)

        prediction = stats.predict_runtime(confidence_factor=3.0)  # High confidence factor
        p90 = stats.get_percentile(0.9)
        mean = stats.get_mean()
        std_dev = stats.get_std_deviation()
        conservative = mean + 3.0 * std_dev

        # Conservative should be higher than P90 in this case
        self.assertGreater(conservative, p90)
        self.assertEqual(prediction, conservative)

    def test_datetime_parsing_invalid_formats(self):
        """Test datetime parsing with various invalid formats."""
        # Test various invalid datetime formats
        invalid_datetimes = [
            'not-a-datetime',
            '2024-13-01T10:00:00Z',  # Invalid month
            '2024-08-32T10:00:00Z',  # Invalid day
            '2024-08-01T25:00:00Z',  # Invalid hour
            '',                      # Empty string
            None                     # None value
        ]

        for invalid_dt in invalid_datetimes:
            data = {
                'count': 1,
                'total_runtime_seconds': 100.0,
                'sample': [100],
                'last_updated': invalid_dt
            }

            stats = JobRuntimeStats.from_dict(data)
            # Should not crash and should set last_updated to None
            self.assertIsNone(stats.last_updated)


if __name__ == '__main__':
    unittest.main()
