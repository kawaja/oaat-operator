from __future__ import annotations
import sys
import os
import pykube
import kopf
from kopf._cogs.structs import credentials

import unittest
from unittest.mock import patch, MagicMock, Mock

# enable importing of oaatoperator modules without placing constraints
# on how they handle non-test in-module importing
sys.path.append(
    os.path.dirname(os.path.realpath(__file__)) + "/../oaatoperator")

from tests.testdata import TestData  # noqa: E402

from oaatoperator.common import ProcessingComplete  # noqa: E402
from oaatoperator.oaatitem import OaatItem  # noqa: E402
import oaatoperator.oaatgroup  # noqa: E402
import oaatoperator.handlers  # noqa: E402

status_running = {'status': {'phase': 'Running'}}
status_pending = {'status': {'phase': 'Pending'}}
status_failed = {'status': {'phase': 'Failed'}}
status_succeeded = {'status': {'phase': 'Succeeded'}}


class TestHelpers(unittest.TestCase):
    def test_is_running(self):
        f = oaatoperator.handlers.is_running
        self.assertTrue(f(**status_running))
        self.assertFalse(f(**status_pending))
        self.assertFalse(f(**status_failed))
        self.assertFalse(f(**status_succeeded))

    def test_is_failed(self):
        f = oaatoperator.handlers.is_failed
        self.assertFalse(f(**status_running))
        self.assertFalse(f(**status_pending))
        self.assertTrue(f(**status_failed))
        self.assertFalse(f(**status_succeeded))

    def test_is_succeeded(self):
        f = oaatoperator.handlers.is_succeeded
        self.assertFalse(f(**status_running))
        self.assertFalse(f(**status_pending))
        self.assertFalse(f(**status_failed))
        self.assertTrue(f(**status_succeeded))

    def test_configure(self):
        oaatoperator.handlers.configure(
            settings=kopf.OperatorSettings())  # type: ignore

    @patch('pykube.KubeConfig')
    def test_login(self, kc):
        kci = kc.from_service_account.return_value
        kci.user.get.side_effect = [
            None, None, None, 'username', 'password', 'token'
        ]
        kci.cluster.get.side_effect = [
            None, 'server', 'insecure'
        ]
        kw = {'logger': MagicMock()}
        l: credentials.ConnectionInfo = (
            oaatoperator.handlers.login(**kw))  # type: ignore
        self.assertIsInstance(l, credentials.ConnectionInfo)
        self.assertEqual(l.server, 'server')
        self.assertEqual(l.username, 'username')
        self.assertEqual(l.password, 'password')
        self.assertEqual(l.token, 'token')
        self.assertIsNone(l.ca_path)
        self.assertIsNone(l.certificate_data)
        self.assertIsNone(l.certificate_path)


class TestHandlerOaatAction(unittest.TestCase):
    @patch('oaatoperator.handlers.OaatGroup', autospec=True)
    def test_oaat_action_sunny(self, og):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        ogi = og.return_value
        ogi.validate_items = Mock(side_effect=[None])
        ogi.handle_processing_complete = Mock(return_value={})
        ogi.set_status = Mock(return_value=None)
        ogi.info = print
        ogi.name = 'name'
        oaatoperator.handlers.oaat_action(**kw)  # type: ignore
        result = ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'validated')

    @patch('oaatoperator.handlers.OaatGroup', autospec=True)
    def test_oaat_action_oaatgroup_error(self, og):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        og.side_effect = [
            ProcessingComplete(message='ogmessage', error='ogerror')
        ]
        result = oaatoperator.handlers.oaat_action(**kw)  # type: ignore
        self.assertEqual(result.get('message'), 'Error: ogerror')

    @patch('oaatoperator.handlers.OaatGroup', autospec=True)
    def test_oaat_action_validate_items_error(self, og):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        ogi = og.return_value
        ogi.validate_items = Mock(
            side_effect=[ProcessingComplete(message='ogmessage')])
        ogi.handle_processing_complete = Mock(return_value={})
        ogi.set_status = Mock(return_value=None)
        ogi.info = print
        ogi.name = 'name'
        oaatoperator.handlers.oaat_action(**kw)  # type: ignore
        result = ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'ogmessage')


class TestHandlerCleanupPod(unittest.TestCase):
    @patch('oaatoperator.handlers.PodOverseer', spec_set=False, autospec=True)
    def test_cleanup_pod_sunny(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.name = 'name'
        pi.info.side_effect = [None]
        pi.delete.side_effect = [None]
        oaatoperator.handlers.cleanup_pod(**kw)  # type: ignore
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), '[cleanup_pod] deleted')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_cleanup_pod_pod_error(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.cleanup_pod(**kw)  # type: ignore
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_cleanup_pod_delete_error(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.name = 'name'
        pi.info.side_effect = [None]
        pi.delete.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        oaatoperator.handlers.cleanup_pod(**kw)  # type: ignore
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'pmessage')
        self.assertEqual(result.get('error'), 'perror')


class TestHandlerPodStatus(unittest.TestCase):
    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_failed_sunny(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.name = 'name'
        pi.info.side_effect = [None]
        pi.update_failure_status.side_effect = [
            ProcessingComplete(message='item failed message',
                               error='item failed error')
        ]
        oaatoperator.handlers.pod_failed(**kw)  # type: ignore
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'item failed message')
        self.assertEqual(result.get('error'), 'item failed error')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_failed_pod_error(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.pod_failed(**kw)  # type: ignore
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_failed_failed(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.name = 'name'
        pi.info.side_effect = [None]
        result = oaatoperator.handlers.pod_failed(**kw)  # type: ignore
        self.assertEqual(result.get('message'),
                         '[pod_failed] should never happen')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_succeeded_sunny(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.info.side_effect = [None]
        pi.update_success_status.side_effect = [
            ProcessingComplete(message='item succeeded message',
                               error='item succeeded error')
        ]
        oaatoperator.handlers.pod_succeeded(**kw)  # type: ignore
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'item succeeded message')
        self.assertEqual(result.get('error'), 'item succeeded error')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_succeeded_pod_error(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.pod_succeeded(**kw)  # type: ignore
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_succeeded_failed(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.info.side_effect = [None]
        result = oaatoperator.handlers.pod_succeeded(**kw)  # type: ignore
        self.assertEqual(result.get('message'),
                         '[pod_succeeded] should never happen')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_phasechange_sunny(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.name = 'name'
        pi.info.side_effect = [None]
        pi.update_phase.side_effect = [
            ProcessingComplete(message='item phasechange message')
        ]
        oaatoperator.handlers.pod_phasechange(**kw)  # type: ignore
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'item phasechange message')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_phasechange_pod_error(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.pod_phasechange(**kw)  # type: ignore
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer', autospec=True)
    def test_pod_phasechange_failed(self, p):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        pi = p.return_value
        pi.name = 'name'
        pi.info.side_effect = [None]
        pi.update_phase.side_effect = [None]
        result = oaatoperator.handlers.pod_phasechange(**kw)  # type: ignore
        self.assertEqual(result.get('message'),
                         '[pod_phasechange] should never happen')


class TestHandlerOaatTimer(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch('oaatoperator.handlers.OaatGroup',
                        spec=oaatoperator.oaatgroup.OaatGroup)
        self.addCleanup(patcher.stop)
        self.og = patcher.start()
        self.ogi = self.og.return_value
        self.ogi.info = MagicMock()
        self.ogi.debug = MagicMock()
        self.ogi.get_status = MagicMock(side_effect=[5])
        self.ogi.validate_items = MagicMock(side_effect=[None])
        self.ogi.verify_running = MagicMock(side_effect=[None])
        self.ogi.verify_running_pod = MagicMock(side_effect=[None])
        self.ogi.identify_running_pod = MagicMock(side_effect=[None])
        self.ogi.resume_running_pod = MagicMock(side_effect=[None])
        self.ogi.delete_non_survivor_pods = MagicMock(side_effect=[None])
        self.ogi.select_survivor = MagicMock(side_effect=[None])
        self.ogi.find_job_to_run = MagicMock(spec=OaatItem)
        item = self.ogi.find_job_to_run.return_value
        item.name = 'item'  # name is special
        self.ogi.set_status = MagicMock(side_effect=None)
        self.pi = MagicMock(spec_set=pykube.Pod).return_value
        self.pi.metadata.return_value = {'name': 'podname'}
        self.ogi.handle_processing_complete = MagicMock(return_value=None)
        return super().setUp()

    def test_oaat_timer_sunny(self):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        oaatoperator.handlers.oaat_timer(**kw)  # type: ignore
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(self.ogi.verify_running.call_count, 1)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 1)
        self.assertEqual(
            self.ogi.find_job_to_run.return_value.run.call_count, 1)
        self.assertEqual(result.get('message'), 'started item item')

    def test_oaat_timer_paused(self):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        kw['body'].setdefault('metadata',
                              {}).setdefault('annotations',
                                             {})['pause_new_jobs'] = 'yes'
        kw['meta'].setdefault('annotations', {})['pause_new_jobs'] = 'yes'
        kw['annotations']['pause_new_jobs'] = 'yes'
        oaatoperator.handlers.oaat_timer(**kw)  # type: ignore
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(self.ogi.verify_running.call_count, 1)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 0)
        self.assertEqual(
            self.ogi.find_job_to_run.return_value.run.call_count, 0)
        self.assertEqual(result.get('message'),
                         'paused via pause_new_jobs annotation')

    def test_oaat_timer_items_issue(self):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        self.ogi.validate_items.side_effect = [
            ProcessingComplete(message='ogmessage', error='ogerror')
        ]
        oaatoperator.handlers.oaat_timer(**kw)  # type: ignore
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(self.ogi.verify_running.call_count, 0)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 0)
        self.assertEqual(
            self.ogi.find_job_to_run.return_value.run.call_count, 0)
        self.assertEqual(result.get('message'), 'ogmessage')
        self.assertEqual(result.get('error'), 'ogerror')

    def test_oaat_timer_oaatgroup_error(self):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        self.og.side_effect = [
            ProcessingComplete(message='ogmessage', error='ogerror')
        ]
        result = oaatoperator.handlers.oaat_timer(**kw)  # type: ignore
        self.assertEqual(result.get('message'), 'Error: ogerror')

    def test_oaat_timer_expected_pod_found_bad_running_function(self):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        self.ogi.verify_running.side_effect = [
            ProcessingComplete(message='item item failed during validation',
                               info='Cleaned up missing/deleted item')
        ]
        oaatoperator.handlers.oaat_timer(**kw)  # type: ignore
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(self.ogi.verify_running.call_count, 1)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 0)
        self.assertEqual(
            self.ogi.find_job_to_run.return_value.run.call_count, 0)
        self.assertRegex(result.get('message'),
                         'item item failed during validation')

    def test_oaat_timer_expected_pod_found(self):
        kw = TestData.setup_kwargs(TestData.kog_attrs)
        self.ogi.verify_running.side_effect = [
            ProcessingComplete(
                message='pod xxx exists and is in state Running')
        ]
        oaatoperator.handlers.oaat_timer(**kw)  # type: ignore
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(self.ogi.verify_running.call_count, 1)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 0)
        self.assertEqual(
            self.ogi.find_job_to_run.return_value.run.call_count, 0)
        self.assertRegex(result.get('message'),
                         'pod xxx exists and is in state Running')


if __name__ == '__main__':
    unittest.main()
