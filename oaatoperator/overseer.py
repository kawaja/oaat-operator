"""
overseer.py

Overseer base class for Kopf object processing.
"""
from typing_extensions import Unpack
import pykube
from typing import Any, Optional, Type
from oaatoperator.common import ProcessingComplete
from oaatoperator.types import CallbackArgs
import logging


class Overseer:
    """
    Overseer

    Base class for managing objects under kopf handler.

    Inheriting class must set self.my_pykube_objtype
    """
    def __init__(self, **kwargs: Unpack[CallbackArgs]) -> None:
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.name = str(kwargs.get('name', ''))
        self.patch = kwargs.get('patch')
        self.status = kwargs.get('status')
        self.logger : logging.Logger = kwargs.get('logger')
        self.body = kwargs.get('body')
        self.meta = kwargs.get('meta')
        self.spec = kwargs.get('spec', {})
        self.namespace = kwargs.get('namespace')
        self.my_pykube_objtype : Optional[Type[pykube.objects.APIObject]] = None
        # this list should contain all elements of kwargs used in this class,
        # to avoid unpredictable behaviour if a full kwargs list is not passed
        required_kwargs = [
            self.name, self.namespace, self.patch, self.logger, self.status,
            self.meta
        ]

        if None in required_kwargs:
            raise ValueError('Overseer must be called with full kopf '
                             f'kwargs ({required_kwargs}')

    def error(self, *args) -> None:
        """Log an error."""
        self.logger.error(*args)

    def warning(self, *args) -> None:
        """Log a warning."""
        self.logger.warning(*args)

    def info(self, *args) -> None:
        """Log an info message."""
        self.logger.info(*args)

    def debug(self, *args) -> None:
        """Log a debug message."""
        self.logger.debug(*args)

    # TODO: check which types can actually be returned by
    # self.status
    def get_status(self, state: str, default: Any = None) -> Any:
        """Get a value from the "status" of the overseen object."""
        return self.status.get(state, default)

    def set_status(self, state: str, value: Optional[str] = None) -> None:
        """Set a field in the "status" of the overseen object."""
        # setting value to None will delete the state
        self.patch.setdefault('status', {})
        self.patch['status'][state] = value

    def set_object_status(self, value: Optional[dict[str, Any]] = None) -> None:
        """Set the entire status section of the overseen object."""
        if value is not None:
            self.patch['status'] = value

    def get_label(self, label: str, default: str|None = None) -> str:
        """Get a label from the overseen object."""
        return self.meta.get('labels', {}).get(label, default)

    def get_kubeobj(self, reason: str|None = None) -> pykube.objects.APIObject:
        """Get the kube object for the overseen object."""
        namespace = self.namespace if self.namespace else pykube.all
        if self.my_pykube_objtype is None:
            raise ProcessingComplete(
                message='inheriting class must set self.my_pykube_objtype')
        try:
            return (self
                    .my_pykube_objtype
                    .objects(self.api, namespace=namespace)  # type: ignore
                    .get_by_name(self.name))
        except pykube.exceptions.ObjectDoesNotExist as exc:
            raise ProcessingComplete(
                error=f'cannot find Object {self.name} ' +
                      f'to {reason}' if reason else '' +
                      f': {exc}',
                message=f'cannot retrieve "{self.name}" object')

    def set_annotation(self, annotation: str, value: str|None = None) -> None:
        """
        Set or Remove an annotation on the overseen object.

        All annotations are prefixed with kawaja.net/
        """
        if isinstance(value, int):
            value = str(value)

        (
            self
            .patch
            .setdefault('metadata', {})
            .setdefault('annotations', {})
            [f'kawaja.net/{annotation}']) = value
        if value:
            self.debug(f'added annotation {annotation}={value} to {self.name}')
        else:
            self.debug(f'removed annotation {annotation} from {self.name}')

    def delete(self) -> None:
        myobj = self.get_kubeobj('delete it')
        try:
            myobj.delete(propagation_policy='Background')
            self.debug(f'delete of {self.name} successful')
        except pykube.exceptions.KubernetesError as exc:
            raise ProcessingComplete(
                error=f'cannot delete Object {self.name}: {exc}',
                message=f'cannot delete "{self.name}" object')

    def handle_processing_complete(self, exc: ProcessingComplete) -> Optional[dict]:
        if 'state' in exc.ret:
            self.set_status('state', exc.ret['state'])
        if 'info' in exc.ret:
            self.info(exc.ret['info'])
        if 'error' in exc.ret:
            self.error(exc.ret['error'])
        if 'warning' in exc.ret:
            self.warning(exc.ret['warning'])
        if 'message' in exc.ret:
            return {'message': exc.ret['message']}
        return None
