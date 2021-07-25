from oaatoperator.common import ProcessingComplete
import unittest
from unittest.mock import patch, MagicMock
from copy import deepcopy
import kopf
import pykube
import logging
from kopf._cogs.structs import credentials
import oaatoperator.oaatgroup
import oaatoperator.handlers

status_running = {'status': {'phase': 'Running'}}
status_pending = {'status': {'phase': 'Pending'}}
status_failed = {'status': {'phase': 'Failed'}}
status_succeeded = {'status': {'phase': 'Succeeded'}}


class TestData:
    body = {}
    kw = {
        'body': body,
        'spec': body.get('spec'),
        'meta': body.get('metadata'),
        'status': body.get('status'),
        'namespace': body.get('metadata', {}).get('namespace'),
        'name': body.get('metadata', {}).get('name'),
        'uid': body.get('metadata', {}).get('uid'),
        'labels': body.get('metadata', {}).get('labels'),
        'annotations': body.get('metadata', {}).get('annotations'),
        'logger': unittest.mock.MagicMock(spec=logging.Logger),
        'patch': {},
        'memo': {},
        'event': {},
        'reason': '',
        'old': {},
        'new': {},
        'diff': {}
    }


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
        oaatoperator.handlers.configure(settings=kopf.OperatorSettings())

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
        l: credentials.ConnectionInfo = oaatoperator.handlers.login(**kw)
        self.assertIsInstance(l, credentials.ConnectionInfo)
        self.assertEqual(l.server, 'server')
        self.assertEqual(l.username, 'username')
        self.assertEqual(l.password, 'password')
        self.assertEqual(l.token, 'token')
        self.assertIsNone(l.ca_path)
        self.assertIsNone(l.certificate_data)
        self.assertIsNone(l.certificate_path)


class TestHandlerOaatAction(unittest.TestCase):
    @patch('oaatoperator.handlers.OaatGroup')
    def test_oaat_action_sunny(self, og):
        kw = deepcopy(TestData.kw)
        ogi = og.return_value
        ogi.validate_oaat_type.side_effect = [None]
        ogi.validate_items.side_effect = [None]
        oaatoperator.handlers.oaat_action(**kw)
        result = ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'validated')

    @patch('oaatoperator.handlers.OaatGroup')
    def test_oaat_action_oaatgroup_error(self, og):
        kw = deepcopy(TestData.kw)
        og.side_effect = [
            ProcessingComplete(message='ogmessage', error='ogerror')
        ]
        result = oaatoperator.handlers.oaat_action(**kw)
        self.assertEqual(result.get('message'), 'Error: ogerror')

    @patch('oaatoperator.handlers.OaatGroup')
    def test_oaat_action_validate_oaat_type_error(self, og):
        kw = deepcopy(TestData.kw)
        ogi = og.return_value
        ogi.validate_oaat_type.side_effect = [
            ProcessingComplete(message='ogmessage')
        ]
        ogi.validate_items.side_effect = [None]
        oaatoperator.handlers.oaat_action(**kw)
        result = ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'ogmessage')

    @patch('oaatoperator.handlers.OaatGroup')
    def test_oaat_action_validate_items_error(self, og):
        kw = deepcopy(TestData.kw)
        ogi = og.return_value
        ogi.validate_oaat_type.side_effect = [None]
        ogi.validate_items.side_effect = [
            ProcessingComplete(message='ogmessage')
        ]
        oaatoperator.handlers.oaat_action(**kw)
        result = ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'ogmessage')


class TestHandlerCleanupPod(unittest.TestCase):
    @patch('oaatoperator.handlers.PodOverseer')
    def test_cleanup_pod_sunny(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        pi.delete.side_effect = [None]
        oaatoperator.handlers.cleanup_pod(**kw)
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), '[cleanup_pod] deleted')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_cleanup_pod_pod_error(self, p):
        kw = deepcopy(TestData.kw)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.cleanup_pod(**kw)
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_cleanup_pod_delete_error(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        pi.delete.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        oaatoperator.handlers.cleanup_pod(**kw)
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'pmessage')
        self.assertEqual(result.get('error'), 'perror')


class TestHandlerPodStatus(unittest.TestCase):
    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_failed_sunny(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        pi.update_failure_status.side_effect = [
            ProcessingComplete(message='item failed message',
                               error='item failed error')
        ]
        oaatoperator.handlers.pod_failed(**kw)
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'item failed message')
        self.assertEqual(result.get('error'), 'item failed error')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_failed_pod_error(self, p):
        kw = deepcopy(TestData.kw)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.pod_failed(**kw)
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_failed_failed(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        result = oaatoperator.handlers.pod_failed(**kw)
        self.assertEqual(result.get('message'),
                         '[pod_failed] should never happen')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_succeeded_sunny(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        pi.update_success_status.side_effect = [
            ProcessingComplete(message='item succeeded message',
                               error='item succeeded error')
        ]
        oaatoperator.handlers.pod_succeeded(**kw)
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'item succeeded message')
        self.assertEqual(result.get('error'), 'item succeeded error')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_succeeded_pod_error(self, p):
        kw = deepcopy(TestData.kw)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.pod_succeeded(**kw)
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_succeeded_failed(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        result = oaatoperator.handlers.pod_succeeded(**kw)
        self.assertEqual(result.get('message'),
                         '[pod_succeeded] should never happen')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_phasechange_sunny(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        pi.update_phase.side_effect = [
            ProcessingComplete(message='item phasechange message')
        ]
        oaatoperator.handlers.pod_phasechange(**kw)
        result = pi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(result.get('message'), 'item phasechange message')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_phasechange_pod_error(self, p):
        kw = deepcopy(TestData.kw)
        p.side_effect = [
            ProcessingComplete(message='pmessage', error='perror')
        ]
        result = oaatoperator.handlers.pod_phasechange(**kw)
        self.assertEqual(result.get('message'), 'Error: perror')

    @patch('oaatoperator.handlers.PodOverseer')
    def test_pod_phasechange_failed(self, p):
        kw = deepcopy(TestData.kw)
        pi = p.return_value
        pi.info.side_effect = [None]
        pi.update_phase.side_effect = [None]
        result = oaatoperator.handlers.pod_phasechange(**kw)
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
        self.ogi.get_status = MagicMock()
        self.ogi.get_status.side_effect = [5]
        self.ogi.validate_items = MagicMock()
        self.ogi.validate_items.side_effect = [None]
        self.ogi.validate_state = MagicMock()
        self.ogi.validate_state.side_effect = [None]
        self.ogi.validate_no_rogue_pods_are_running = MagicMock()
        self.ogi.validate_no_rogue_pods_are_running.side_effect = [None]
        self.ogi.is_pod_expected = MagicMock()
        self.ogi.is_pod_expected.side_effect = [None]
        self.ogi.validate_expected_pod_is_running = MagicMock()
        self.ogi.validate_expected_pod_is_running.side_effect = [
            ProcessingComplete(
                message='pod xxx exists and is in state Running')
        ]
        self.ogi.find_job_to_run = MagicMock()
        self.ogi.find_job_to_run.side_effect = [None]
        self.ogi.set_status = MagicMock()
        self.ogi.set_status.side_effect = None
        self.pi = MagicMock(pykube.Pod).return_value
        self.pi.metadata.return_value = {'name': 'podname'}
        self.ogi.run_item = MagicMock()
        self.ogi.run_item.side_effect = [self.pi]
        self.ogi.handle_processing_complete = MagicMock()
        return super().setUp()

    def test_oaat_timer_sunny(self):
        kw = deepcopy(TestData.kw)
        oaatoperator.handlers.oaat_timer(**kw)
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(
            self.ogi.validate_expected_pod_is_running.call_count, 0)
        self.assertEqual(self.ogi.is_pod_expected.call_count, 1)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 1)
        self.assertEqual(self.ogi.run_item.call_count, 1)
        self.assertEqual(result.get('message'), 'started item None')

    def test_oaat_timer_items_issue(self):
        kw = deepcopy(TestData.kw)
        self.ogi.validate_items.side_effect = [
            ProcessingComplete(message='ogmessage', error='ogerror')
        ]
        oaatoperator.handlers.oaat_timer(**kw)
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(
            self.ogi.validate_expected_pod_is_running.call_count, 0)
        self.assertEqual(self.ogi.is_pod_expected.call_count, 0)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 0)
        self.assertEqual(self.ogi.run_item.call_count, 0)
        self.assertEqual(result.get('message'), 'ogmessage')
        self.assertEqual(result.get('error'), 'ogerror')

    def test_oaat_timer_oaatgroup_error(self):
        kw = deepcopy(TestData.kw)
        self.og.side_effect = [
            ProcessingComplete(message='ogmessage', error='ogerror')
        ]
        result = oaatoperator.handlers.oaat_timer(**kw)
        self.assertEqual(result.get('message'), 'Error: ogerror')

    def test_oaat_timer_expected_pod_found_bad_running_function(self):
        kw = deepcopy(TestData.kw)
        self.ogi.is_pod_expected.side_effect = [True]
        self.ogi.validate_expected_pod_is_running.side_effect = [None]
        result = oaatoperator.handlers.oaat_timer(**kw)
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(
            self.ogi.validate_expected_pod_is_running.call_count, 1)
        self.assertEqual(self.ogi.is_pod_expected.call_count, 1)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 0)
        self.assertEqual(self.ogi.run_item.call_count, 0)
        self.assertRegex(result.get('message'),
                         'validate_expected.*should never happen')

    def test_oaat_timer_expected_pod_found(self):
        kw = deepcopy(TestData.kw)
        self.ogi.is_pod_expected.side_effect = [True]
        oaatoperator.handlers.oaat_timer(**kw)
        result = self.ogi.handle_processing_complete.call_args[0][0].ret
        self.assertEqual(self.ogi.validate_items.call_count, 1)
        self.assertEqual(
            self.ogi.validate_expected_pod_is_running.call_count, 1)
        self.assertEqual(self.ogi.is_pod_expected.call_count, 1)
        self.assertEqual(self.ogi.find_job_to_run.call_count, 0)
        self.assertEqual(self.ogi.run_item.call_count, 0)
        self.assertRegex(result.get('message'),
                         'pod xxx exists and is in state Running')


if __name__ == '__main__':
    unittest.main()
