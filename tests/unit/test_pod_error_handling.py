"""Integration tests for pod.py error handling scenarios."""

import oaatoperator.utility
from oaatoperator.common import ProcessingComplete
from oaatoperator.pod import PodOverseer
from tests.unit.testdata import TestData
import pytest
import unittest
import unittest.mock
import datetime
from unittest.mock import Mock, patch

# Test setup imports
import sys
import os
sys.path.append(os.path.dirname(
    os.path.realpath(__file__)) + "/../../oaatoperator")


pytestmark = pytest.mark.unit


class TestPodErrorHandling(unittest.TestCase):
    """Test pod.py error handling scenarios covering missing lines 53-60, 116-124."""

    def setUp(self):
        self.test_data = TestData()

    def test_retrieve_terminated_no_terminated_status(self):
        """Test _retrieve_terminated when no terminated status exists (lines 53-56)."""
        # Setup kwargs for PodOverseer
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)

        # Mock status with containerStatuses but no terminated state
        kopf_obj['status'] = {
            'phase': 'Running',
            'containerStatuses': [{
                'name': 'test-container',
                'state': {
                    'running': {  # Not terminated
                        'startedAt': '2024-08-10T11:00:00Z'
                    }
                }
            }]
        }

        mock_time = datetime.datetime(
            2024, 8, 10, 12, 0, 0, tzinfo=oaatoperator.utility.UTC)
        with patch('oaatoperator.pod.now', return_value=mock_time):
            pod = PodOverseer(**kopf_obj)
            pod.logger = Mock()

            pod._retrieve_terminated()

            # The logic warns about missing terminated status, then falls back to setting finished_at
            warnings = [call.args[0]
                        for call in pod.logger.warning.call_args_list]
            self.assertIn(
                f'cannot find terminated status for {pod.name} (reason: None)',
                warnings
            )
            self.assertIn(
                f'unable to determine termination time for {pod.name}',
                warnings
            )

            # Should set finished_at to current time as fallback
            self.assertEqual(pod.finished_at, mock_time)
            self.assertIsNone(pod.started_at)

    def test_retrieve_terminated_finished_at_fallback(self):
        """Test _retrieve_terminated fallback when finished_at is None (lines 57-60)."""
        # Setup kwargs for PodOverseer
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)

        # Mock status with no containerStatuses (empty list)
        kopf_obj['status'] = {
            'phase': 'Succeeded',
            'containerStatuses': []  # Empty list
        }

        # Create pod and manually call the patched now function before _retrieve_terminated
        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        # Patch now() at the module level where it's imported in pod.py
        mock_time = datetime.datetime(
            2024, 8, 10, 12, 0, 0, tzinfo=oaatoperator.utility.UTC)
        with patch('oaatoperator.pod.now', return_value=mock_time):
            pod._retrieve_terminated()

            # Should log warning about unable to determine termination time (line 58-59)
            pod.logger.warning.assert_called_with(
                f'unable to determine termination time for {pod.name}')

            # Should set finished_at to current time as fallback (line 60)
            self.assertEqual(pod.finished_at, mock_time)

            # started_at should remain None
            self.assertIsNone(pod.started_at)

    def test_retrieve_terminated_missing_timestamps(self):
        """Test _retrieve_terminated with terminated status but missing timestamps."""
        # Setup kwargs for PodOverseer
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)

        # Mock status with terminated but missing both timestamps
        kopf_obj['status'] = {
            'phase': 'Succeeded',
            'containerStatuses': [{
                'name': 'test-container',
                'state': {
                    'terminated': {
                        'exitCode': 0,
                        'reason': 'Completed'
                        # Missing both 'startedAt' and 'finishedAt'
                    }
                }
            }]
        }

        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        pod._retrieve_terminated()

        # Should find terminated status and extract what's available
        self.assertEqual(pod.exitcode, 0)
        # Both timestamps should be None (date_from_isostr returns epoch for None)
        self.assertEqual(pod.finished_at, datetime.datetime.fromtimestamp(
            0, tz=oaatoperator.utility.UTC))
        self.assertEqual(pod.started_at, datetime.datetime.fromtimestamp(
            0, tz=oaatoperator.utility.UTC))

    def test_handle_processing_complete_with_info(self):
        """Test handle_processing_complete with info message (line 116-117)."""
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)
        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        exc = ProcessingComplete(info="Test info message")
        result = pod.handle_processing_complete(exc)

        # Should log info message and return None
        pod.logger.info.assert_called_once_with("Test info message")
        self.assertIsNone(result)

    def test_handle_processing_complete_with_error(self):
        """Test handle_processing_complete with error message (line 118-119)."""
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)
        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        exc = ProcessingComplete(error="Test error message")
        result = pod.handle_processing_complete(exc)

        # Should log error message and return None
        pod.logger.error.assert_called_once_with("Test error message")
        self.assertIsNone(result)

    def test_handle_processing_complete_with_warning(self):
        """Test handle_processing_complete with warning message (line 120-121)."""
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)
        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        exc = ProcessingComplete(warning="Test warning message")
        result = pod.handle_processing_complete(exc)

        # Should log warning message and return None
        pod.logger.warning.assert_called_once_with("Test warning message")
        self.assertIsNone(result)

    def test_handle_processing_complete_with_message(self):
        """Test handle_processing_complete with message (line 122-124)."""
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)
        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        exc = ProcessingComplete(message="Test message")
        result = pod.handle_processing_complete(exc)

        # Should log message as info and return None (pod.py returns None, not dict)
        pod.logger.info.assert_called_once_with("Test message")
        self.assertIsNone(result)

    def test_handle_processing_complete_with_multiple_fields(self):
        """Test handle_processing_complete with multiple message types."""
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)
        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        exc = ProcessingComplete(
            info="Info message",
            error="Error message",
            warning="Warning message",
            message="General message"
        )
        result = pod.handle_processing_complete(exc)

        # Should log all message types
        pod.logger.info.assert_any_call("Info message")
        pod.logger.info.assert_any_call("General message")
        pod.logger.error.assert_called_once_with("Error message")
        pod.logger.warning.assert_called_once_with("Warning message")
        self.assertIsNone(result)

    def test_handle_processing_complete_empty_exception(self):
        """Test handle_processing_complete with empty ProcessingComplete."""
        kopf_obj = TestData.setup_kwargs(TestData.kp_spec)
        pod = PodOverseer(**kopf_obj)
        pod.logger = Mock()

        exc = ProcessingComplete()  # No fields set
        result = pod.handle_processing_complete(exc)

        # Should not log anything and return None
        pod.logger.info.assert_not_called()
        pod.logger.error.assert_not_called()
        pod.logger.warning.assert_not_called()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
