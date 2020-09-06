"""
overseer.py

Overseer base class for Kopf object processing.
"""
import time
import pykube
from typing import Any
from oaatoperator.common import ProcessingComplete


class Overseer:
    """
    Overseer

    Base class for managing objects under kopf handler.
    """
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.name = kwargs.get('name')
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

    def get_kubeobj(self, reason: str = None) -> None:
        """Get the kube object for the overseen object."""
        namespace = self.namespace if self.namespace else pykube.all
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
        """Set or Remove an annotation on the overseen object."""
        myobj = self.get_kubeobj('set annotation')
        if value:
            myobj.annotations[f'kawaja.net/{annotation}'] = str(value)
            attempts = 3
            while attempts > 0:
                try:
                    myobj.update()
                    break
                except pykube.exceptions.KubernetesError as exc:
                    if (isinstance(exc, pykube.exceptions.HTTPError)
                            and exc.args[0] == 429):
                        time.sleep(10)
                    attempts -= 1
                    self.debug(f'error: {type(exc)}, args: {str(exc.args)}')
                    self.warning(f'failed to set annotation '
                                 f'(attempts remaining {attempts}): {exc}')
            self.debug(f'added annotation {annotation}={value} to {self.name}')
        else:
            myobj.annotations.pop(f'kawaja.net/{annotation}', None)
            self.debug(f'removed annotation {annotation} from {self.name}')

    def delete(self) -> None:
        myobj = self.get_kubeobj('delete it')
        try:
            myobj.delete(propagation_policy='Background')
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
            self.warning(exc.ret['error'])
        if 'message' in exc.ret:
            return {'message': exc.ret['message']}
        return None
