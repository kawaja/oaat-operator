"""
overseer.py

Overseer base class for Kopf object processing.
"""
import pykube
from typing import Any
from oaatoperator.common import ProcessingComplete


# TODO: the kwargs passed to Overseer needs to be complete (i.e.
# if the kopf handler "absorbs" a kw arg, then it will not appear in
# **kwargs, so the Overseer may not behave correctly).

class Overseer:
    """
    Overseer

    Base class for managing objects under kopf handler.

    Inheriting class must set self.my_pykube_objtype
    """
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.name = kwargs.get('name')
        self.patch = kwargs.get('patch')
        self.namespace = kwargs.get('namespace')
        self.my_pykube_objtype = None
        if self.name is None or self.namespace is None:
            raise ValueError('Overseer must be called with kopf kwargs')

    def error(self, *args) -> None:
        """Log an error."""
        self.kwargs['logger'].error(*args)

    def warning(self, *args) -> None:
        """Log a warning."""
        self.kwargs['logger'].warning(*args)

    def info(self, *args) -> None:
        """Log an info message."""
        self.kwargs['logger'].info(*args)

    def debug(self, *args) -> None:
        """Log a debug message."""
        self.kwargs['logger'].debug(*args)

    def get_status(self, state: str, default: str = None) -> Any:
        """Get a value from the "status" of the overseen object."""
        return self.kwargs['status'].get(state, default)

    def set_status(self, state: str, value: str = None) -> None:
        """Set a field in the "status" of the overseen object."""
        self.kwargs['patch'].setdefault('status', {})
        self.kwargs['patch']['status'][state] = value

    def get_label(self, label: str, default: str = None) -> str:
        """Get a label from the overseen object."""
        return self.kwargs['meta'].get('labels', {}).get(label, default)

    def get_kubeobj(self, reason: str = None):
        """Get the kube object for the overseen object."""
        namespace = self.namespace if self.namespace else pykube.all
        if self.my_pykube_objtype is None:
            raise ProcessingComplete(
                message='inheriting class must set self.my_pykube_objtype')
        try:
            return (self
                    .my_pykube_objtype
                    .objects(self.api, namespace=namespace)
                    .get_by_name(self.name))
        except pykube.exceptions.ObjectDoesNotExist as exc:
            raise ProcessingComplete(
                error=f'cannot find Object {self.name} ' +
                      f'to {reason}' if reason else '' +
                      f': {exc}',
                message=f'cannot retrieve "{self.name}" object')

    def set_annotation(self, annotation: str, value: str = None) -> None:
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

    def handle_processing_complete(self, exc: Exception) -> dict:
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
