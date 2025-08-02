"""Unit tests for Overseer class with full mocking."""
import pytest
from unittest.mock import Mock, patch
import kopf
import pykube
import logging

from oaatoperator.overseer import Overseer
from oaatoperator.common import ProcessingComplete


pytestmark = pytest.mark.unit


class TestOverseerConstruction:
    """Test Overseer constructor and initialization."""

    def test_constructor_with_valid_kwargs(self):
        """Test successful construction with all required kwargs."""
        mock_logger = Mock(spec=logging.Logger)
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': {},
            'logger': mock_logger,
            'status': {},
            'meta': {'labels': {}},
            'body': {},
            'memo': {},
            'spec': {}
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            overseer = Overseer(**kwargs)

        assert overseer.name == 'test-pod'
        assert overseer.namespace == 'default'
        assert overseer.patch == {}
        assert overseer.logger == mock_logger
        assert overseer.status == {}
        assert overseer.meta == {'labels': {}}

    def test_constructor_missing_required_kwargs(self):
        """Test constructor raises error when required kwargs are missing."""
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            # Missing patch, logger, status, meta
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            with pytest.raises(kopf.PermanentError, match='Overseer must be called with full kopf kwargs'):
                Overseer(**kwargs)

    def test_constructor_with_none_values(self):
        """Test constructor handles None values properly."""
        mock_logger = Mock(spec=logging.Logger)
        kwargs = {
            'name': None,  # This should be converted to string
            'namespace': None,
            'patch': {},
            'logger': mock_logger,
            'status': {},
            'meta': {},
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            with pytest.raises(kopf.PermanentError):
                Overseer(**kwargs)


class TestOverseerLogging:
    """Test Overseer logging methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': {},
            'logger': self.mock_logger,
            'status': {},
            'meta': {'labels': {}},
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            self.overseer = Overseer(**kwargs)

    def test_error_logging(self):
        """Test error method calls logger.error."""
        self.overseer.error('test error message')
        self.mock_logger.error.assert_called_once_with('test error message')

    def test_warning_logging(self):
        """Test warning method calls logger.warning."""
        self.overseer.warning('test warning message')
        self.mock_logger.warning.assert_called_once_with('test warning message')

    def test_info_logging(self):
        """Test info method calls logger.info."""
        self.overseer.info('test info message')
        self.mock_logger.info.assert_called_once_with('test info message')

    def test_debug_logging(self):
        """Test debug method calls logger.debug."""
        self.overseer.debug('test debug message')
        self.mock_logger.debug.assert_called_once_with('test debug message')

    def test_logging_with_multiple_args(self):
        """Test logging methods handle multiple arguments."""
        self.overseer.error('error %s %d', 'message', 42)
        self.mock_logger.error.assert_called_once_with('error %s %d', 'message', 42)


class TestOverseerStatus:
    """Test Overseer status management methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.status = {'existing_state': 'existing_value'}
        self.patch = {}
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': self.patch,
            'logger': self.mock_logger,
            'status': self.status,
            'meta': {'labels': {}},
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            self.overseer = Overseer(**kwargs)

    def test_get_status_existing_key(self):
        """Test get_status returns existing value."""
        result = self.overseer.get_status('existing_state')
        assert result == 'existing_value'

    def test_get_status_missing_key_no_default(self):
        """Test get_status returns None for missing key with no default."""
        result = self.overseer.get_status('missing_key')
        assert result is None

    def test_get_status_missing_key_with_default(self):
        """Test get_status returns default for missing key."""
        result = self.overseer.get_status('missing_key', 'default_value')
        assert result == 'default_value'

    def test_get_status_none_status(self):
        """Test get_status raises error when status is None."""
        self.overseer.status = None
        with pytest.raises(kopf.PermanentError, match='kopf error: status is None'):
            self.overseer.get_status('any_key')

    def test_set_status_with_value(self):
        """Test set_status sets value in patch."""
        self.overseer.set_status('new_state', 'new_value')
        assert self.patch['status']['new_state'] == 'new_value'

    def test_set_status_none_value(self):
        """Test set_status with None value."""
        self.overseer.set_status('state_to_delete', None)
        assert self.patch['status']['state_to_delete'] is None

    def test_set_status_none_patch(self):
        """Test set_status raises error when patch is None."""
        self.overseer.patch = None
        with pytest.raises(kopf.PermanentError, match='kopf error: patch is None'):
            self.overseer.set_status('any_state', 'any_value')

    def test_set_object_status(self):
        """Test set_object_status sets entire status."""
        new_status = {'state1': 'value1', 'state2': 'value2'}
        self.overseer.set_object_status(new_status)
        assert self.patch['status'] == new_status

    def test_set_object_status_none_value(self):
        """Test set_object_status with None value doesn't modify patch."""
        original_patch = self.patch.copy()
        self.overseer.set_object_status(None)
        assert self.patch == original_patch


class TestOverseerLabels:
    """Test Overseer label management methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.meta = {
            'labels': {
                'existing_label': 'existing_value',
                'app': 'test-app'
            }
        }
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': {},
            'logger': self.mock_logger,
            'status': {},
            'meta': self.meta,
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            self.overseer = Overseer(**kwargs)

    def test_get_label_existing(self):
        """Test get_label returns existing label value."""
        result = self.overseer.get_label('existing_label')
        assert result == 'existing_value'

    def test_get_label_missing_no_default(self):
        """Test get_label returns None for missing label."""
        result = self.overseer.get_label('missing_label')
        assert result is None

    def test_get_label_missing_with_default(self):
        """Test get_label returns default for missing label."""
        result = self.overseer.get_label('missing_label', 'default_value')
        assert result == 'default_value'

    def test_get_label_none_meta(self):
        """Test get_label raises error when meta is None."""
        self.overseer.meta = None
        with pytest.raises(kopf.PermanentError, match='kopf error: meta is None'):
            self.overseer.get_label('any_label')

    def test_get_label_no_labels_key(self):
        """Test get_label handles missing labels key."""
        self.overseer.meta = {}
        result = self.overseer.get_label('any_label', 'default')
        assert result == 'default'


class TestOverseerKubeObj:
    """Test Overseer Kubernetes object operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': {},
            'logger': self.mock_logger,
            'status': {},
            'meta': {'labels': {}},
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            self.overseer = Overseer(**kwargs)

    def test_get_kubeobj_no_objtype(self):
        """Test get_kubeobj raises error when my_pykube_objtype is None."""
        with pytest.raises(ProcessingComplete, match='inheriting class must set self.my_pykube_objtype'):
            self.overseer.get_kubeobj()

    @patch('pykube.Pod')
    def test_get_kubeobj_object_not_found(self, mock_pod_class):
        """Test get_kubeobj raises ProcessingComplete when object doesn't exist."""
        self.overseer.my_pykube_objtype = mock_pod_class

        # Mock the objects() chain to raise ObjectDoesNotExist
        mock_objects = Mock()
        mock_objects.get_by_name.side_effect = pykube.exceptions.ObjectDoesNotExist('Not found')
        mock_pod_class.objects.return_value = mock_objects

        with pytest.raises(ProcessingComplete, match='cannot retrieve "test-pod" object'):
            self.overseer.get_kubeobj('delete it')

    @patch('pykube.Pod')
    def test_get_kubeobj_success(self, mock_pod_class):
        """Test get_kubeobj returns object successfully."""
        self.overseer.my_pykube_objtype = mock_pod_class

        # Mock successful object retrieval
        mock_pod_instance = Mock()
        mock_objects = Mock()
        mock_objects.get_by_name.return_value = mock_pod_instance
        mock_pod_class.objects.return_value = mock_objects

        result = self.overseer.get_kubeobj('examine it')

        assert result == mock_pod_instance
        mock_pod_class.objects.assert_called_once_with(self.overseer.api, namespace='default')
        mock_objects.get_by_name.assert_called_once_with('test-pod')

    @patch('pykube.Pod')
    def test_get_kubeobj_no_namespace(self, mock_pod_class):
        """Test get_kubeobj handles None namespace."""
        self.overseer.namespace = None
        self.overseer.my_pykube_objtype = mock_pod_class

        mock_pod_instance = Mock()
        mock_objects = Mock()
        mock_objects.get_by_name.return_value = mock_pod_instance
        mock_pod_class.objects.return_value = mock_objects

        self.overseer.get_kubeobj()

        # Should use pykube.all when namespace is None
        mock_pod_class.objects.assert_called_once_with(self.overseer.api, namespace=pykube.all)


class TestOverseerAnnotations:
    """Test Overseer annotation management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.patch = {}
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': self.patch,
            'logger': self.mock_logger,
            'status': {},
            'meta': {'labels': {}},
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            self.overseer = Overseer(**kwargs)

    def test_set_annotation_string_value(self):
        """Test set_annotation with string value."""
        self.overseer.set_annotation('test_annotation', 'test_value')

        expected_key = 'oaatoperator.kawaja.net/test_annotation'
        assert self.patch['metadata']['annotations'][expected_key] == 'test_value'
        self.mock_logger.debug.assert_called_once_with('added annotation test_annotation=test_value to test-pod')

    def test_set_annotation_int_value(self):
        """Test set_annotation converts int to string."""
        self.overseer.set_annotation('numeric_annotation', 42)

        expected_key = 'oaatoperator.kawaja.net/numeric_annotation'
        assert self.patch['metadata']['annotations'][expected_key] == '42'
        self.mock_logger.debug.assert_called_once_with('added annotation numeric_annotation=42 to test-pod')

    def test_set_annotation_none_value(self):
        """Test set_annotation with None value (removal)."""
        self.overseer.set_annotation('remove_annotation', None)

        expected_key = 'oaatoperator.kawaja.net/remove_annotation'
        assert self.patch['metadata']['annotations'][expected_key] is None
        self.mock_logger.debug.assert_called_once_with('removed annotation remove_annotation from test-pod')

    def test_set_annotation_none_patch(self):
        """Test set_annotation raises error when patch is None."""
        self.overseer.patch = None
        with pytest.raises(kopf.PermanentError, match='kopf error: patch is None'):
            self.overseer.set_annotation('any_annotation', 'any_value')


class TestOverseerDelete:
    """Test Overseer delete operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': {},
            'logger': self.mock_logger,
            'status': {},
            'meta': {'labels': {}},
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            self.overseer = Overseer(**kwargs)

    @patch('pykube.Pod')
    def test_delete_success(self, mock_pod_class):
        """Test successful delete operation."""
        self.overseer.my_pykube_objtype = mock_pod_class

        # Mock successful object retrieval and deletion
        mock_pod_instance = Mock()
        mock_objects = Mock()
        mock_objects.get_by_name.return_value = mock_pod_instance
        mock_pod_class.objects.return_value = mock_objects

        self.overseer.delete()

        mock_pod_instance.delete.assert_called_once_with(propagation_policy='Background')
        self.mock_logger.debug.assert_called_once_with('delete of test-pod successful')

    @patch('pykube.Pod')
    def test_delete_kubernetes_error(self, mock_pod_class):
        """Test delete handles KubernetesError."""
        self.overseer.my_pykube_objtype = mock_pod_class

        # Mock object retrieval but deletion fails
        mock_pod_instance = Mock()
        mock_pod_instance.delete.side_effect = pykube.exceptions.KubernetesError('Delete failed')
        mock_objects = Mock()
        mock_objects.get_by_name.return_value = mock_pod_instance
        mock_pod_class.objects.return_value = mock_objects

        with pytest.raises(ProcessingComplete, match='cannot delete "test-pod" object'):
            self.overseer.delete()


class TestOverseerProcessingComplete:
    """Test Overseer ProcessingComplete exception handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.patch = {}
        kwargs = {
            'name': 'test-pod',
            'namespace': 'default',
            'patch': self.patch,
            'logger': self.mock_logger,
            'status': {},
            'meta': {'labels': {}},
        }

        with patch('pykube.HTTPClient'), patch('pykube.KubeConfig.from_env'):
            self.overseer = Overseer(**kwargs)

    def test_handle_processing_complete_with_all_fields(self):
        """Test handle_processing_complete with all fields set."""
        exc = ProcessingComplete(
            state='test_state',
            info='test info',
            error='test error',
            warning='test warning',
            message='test message'
        )

        result = self.overseer.handle_processing_complete(exc)

        # Check status was set
        assert self.patch['status']['state'] == 'test_state'

        # Check logging calls
        self.mock_logger.info.assert_called_once_with('test info')
        self.mock_logger.error.assert_called_once_with('test error')
        self.mock_logger.warning.assert_called_once_with('test warning')

        # Check return value
        assert result == {'message': 'test message'}

    def test_handle_processing_complete_minimal(self):
        """Test handle_processing_complete with minimal fields."""
        exc = ProcessingComplete()

        result = self.overseer.handle_processing_complete(exc)

        # Should not modify patch or call logging
        assert 'status' not in self.patch
        self.mock_logger.info.assert_not_called()
        self.mock_logger.error.assert_not_called()
        self.mock_logger.warning.assert_not_called()

        # Should return None
        assert result is None

    def test_handle_processing_complete_partial_fields(self):
        """Test handle_processing_complete with some fields set."""
        exc = ProcessingComplete(
            error='partial error',
            message='partial message'
        )

        result = self.overseer.handle_processing_complete(exc)

        # Check only error logging was called
        self.mock_logger.error.assert_called_once_with('partial error')
        self.mock_logger.info.assert_not_called()
        self.mock_logger.warning.assert_not_called()

        # Check return value
        assert result == {'message': 'partial message'}

        # Status should not be modified
        assert 'status' not in self.patch
