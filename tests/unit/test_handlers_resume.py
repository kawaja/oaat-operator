"""Integration tests for handlers.py resume functionality."""

from oaatoperator.common import ProcessingComplete, KubeOaatGroup
from oaatoperator.handlers import oaat_resume
from tests.unit.mocks_pykube import KubeObject
from tests.unit.testdata import TestData
import pytest
import unittest
import unittest.mock
from unittest.mock import Mock, patch

# Test setup imports
import sys
import os
sys.path.append(os.path.dirname(
    os.path.realpath(__file__)) + "/../../oaatoperator")


pytestmark = pytest.mark.unit


class TestHandlersResume(unittest.TestCase):
    """Test handlers.py resume functionality covering missing lines 260-274."""

    def setUp(self):
        self.test_data = TestData()

    def test_oaat_resume_oaatgroup_creation_failure(self):
        """Test oaat_resume when OaatGroup creation fails (lines 260-264)."""
        # Setup kwargs for resume handler
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)
        kopf_obj['memo'] = Mock()

        # Mock OaatGroup to raise ProcessingComplete during creation
        with patch('oaatoperator.handlers.OaatGroup') as mock_oaatgroup:
            mock_oaatgroup.side_effect = ProcessingComplete(
                error="Mock OaatGroup creation failure",
                message="Failed to create OaatGroup"
            )

            result = oaat_resume(**kopf_obj)

            # Should return error message from ProcessingComplete
            self.assertEqual(
                result, {'message': 'Error: Mock OaatGroup creation failure'})

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_oaat_resume_with_running_pod(self, oaat_type_mock):
        """Test oaat_resume with existing running pod (lines 266-274)."""
        # Setup kwargs for resume handler
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)
        memo = Mock()
        kopf_obj['memo'] = memo

        # Mock running pod info
        running_pod_info = {
            'oaat-name': 'test-item',
            'name': 'test-pod-12345'
        }

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            with patch('oaatoperator.handlers.OaatGroup') as mock_oaatgroup_class:
                mock_oaatgroup = Mock()
                mock_oaatgroup.name = 'test-group'
                mock_oaatgroup.resume_running_pod.return_value = running_pod_info
                mock_oaatgroup.info = Mock()
                mock_oaatgroup.set_status = Mock()
                mock_oaatgroup.handle_processing_complete = Mock()
                mock_oaatgroup_class.return_value = mock_oaatgroup

                result = oaat_resume(**kopf_obj)

                # Verify memo was updated with running pod info (lines 268-270)
                self.assertEqual(memo.state, 'running')
                self.assertEqual(memo.currently_running, 'test-item')
                self.assertEqual(memo.pod, 'test-pod-12345')

                # Verify status was set (line 273)
                mock_oaatgroup.set_status.assert_called_once_with(
                    'handler_status', memo)

                # Verify return message (line 274)
                self.assertEqual(
                    result, {'message': 'Successfully resumed test-group'})

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_oaat_resume_no_running_pod(self, oaat_type_mock):
        """Test oaat_resume with no running pod."""
        # Setup kwargs for resume handler
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)
        memo = Mock()
        kopf_obj['memo'] = memo

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            with patch('oaatoperator.handlers.OaatGroup') as mock_oaatgroup_class:
                mock_oaatgroup = Mock()
                mock_oaatgroup.name = 'test-group'
                mock_oaatgroup.resume_running_pod.return_value = None  # No running pod
                mock_oaatgroup.info = Mock()
                mock_oaatgroup.set_status = Mock()
                mock_oaatgroup_class.return_value = mock_oaatgroup

                # Record initial memo state
                initial_attrs = set(dir(memo))

                result = oaat_resume(**kopf_obj)

                # Verify no new memo attributes were added for running state
                final_attrs = set(dir(memo))
                new_attrs = final_attrs - initial_attrs

                # Should not have added running-related attributes
                running_attrs = {'state', 'currently_running', 'pod'}
                self.assertFalse(running_attrs.intersection(new_attrs),
                                 f"Unexpected running attributes added: {running_attrs.intersection(new_attrs)}")

                # Verify status was still set
                mock_oaatgroup.set_status.assert_called_once_with(
                    'handler_status', memo)

                # Verify return message
                self.assertEqual(
                    result, {'message': 'Successfully resumed test-group'})

    @patch('oaatoperator.oaatgroup.OaatType', autospec=True)
    def test_oaat_resume_with_partial_pod_info(self, oaat_type_mock):
        """Test oaat_resume with partial running pod info."""
        # Setup kwargs for resume handler
        kopf_obj = TestData.setup_kwargs(TestData.kog_empty_attrs)
        memo = Mock()
        kopf_obj['memo'] = memo

        # Mock running pod info with missing 'name' field
        running_pod_info = {
            'oaat-name': 'test-item'
            # Missing 'name' field
        }

        with KubeObject(KubeOaatGroup, TestData.kog_empty_attrs):
            with patch('oaatoperator.handlers.OaatGroup') as mock_oaatgroup_class:
                mock_oaatgroup = Mock()
                mock_oaatgroup.name = 'test-group'
                mock_oaatgroup.resume_running_pod.return_value = running_pod_info
                mock_oaatgroup.info = Mock()
                mock_oaatgroup.set_status = Mock()
                mock_oaatgroup_class.return_value = mock_oaatgroup

                result = oaat_resume(**kopf_obj)

                # Verify memo was updated with available info, defaults for missing
                self.assertEqual(memo.state, 'running')
                self.assertEqual(memo.currently_running, 'test-item')
                # Default for missing 'name'
                self.assertEqual(memo.pod, 'unknown')


if __name__ == '__main__':
    unittest.main()
