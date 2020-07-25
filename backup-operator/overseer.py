"""
overseer.py

Overseer base class.
"""
import time
import pykube
from common import ProcessingComplete

class Overseer:
    """
    Overseer

    Base class for managing objects under kopf handler.
    """
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.name = kwargs['name']
        self.namespace = kwargs['namespace']
        self.my_pykube_objtype = None

    def error(self, *args):
        """Log an error."""
        self.kwargs['logger'].error(*args)

    def warning(self, *args):
        """Log a warning."""
        self.kwargs['logger'].warning(*args)

    def info(self, *args):
        """Log an info message."""
        self.kwargs['logger'].info(*args)

    def debug(self, *args):
        """Log a debug message."""
        self.kwargs['logger'].debug(*args)

    def get_status(self, state, default=None):
        """Get a value from the "status" of the overseen object."""
        return self.kwargs['status'].get(state, default)

    def set_status(self, state, value=None):
        """Set a field in the "status" of the overseen object."""
        self.kwargs['patch'].setdefault('status', {})
        self.kwargs['patch']['status'][state] = value

    def get_label(self, label, default=None):
        """Get a label from the overseen object."""
        return self.kwargs['meta'].get('labels', {}).get(label, default)

    def get_kubeobj(self, reason=None):
        """Get the kube object for the overseen object."""
        namespace = self.namespace if self.namespace else pykube.all
        try:
            return (self
                    .my_pykube_objtype
                    .objects(self.api, namespace=namespace)
                    .get_by_name(self.name))
        except pykube.exceptions.ObjectDoesNotExist as exc:
            self.error(f'cannot find Object {self.name} ' +
                       f'to {reason}' if reason else '' +
                       f': {exc}')
            raise ProcessingComplete(
                message=f'cannot retrieve "{self.name}" object')

    def set_annotation(self, annotation, value=None):
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

    def delete(self):
        myobj = self.get_kubeobj('delete it')
        try:
            myobj.delete(propagation_policy='Background')
        except pykube.exceptions.KubernetesError as exc:
            self.error(f'cannot delete Object {self.name}: {exc}')
            raise ProcessingComplete(
                message=f'cannot delete "{self.name}" object')

    # TODO: handle multiple warnings, errors, etc.?
    def handle_processing_complete(self, exc):
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

