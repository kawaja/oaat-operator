"""
pod.py

Overseer object for managing Pod objects.
"""
import pykube
from pykube import Pod
from utility import date_from_isostr
from common import ProcessingComplete, OaatGroup
import overseer
import oaatgroup


class PodOverseer(overseer.Overseer):
    """
    PodOverseer

    Manager for Pod objects.

    Initialise with the kwargs for a Pod kopf handler.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phase = kwargs['status']['phase']
        self.my_pykube_objtype = Pod
        self.exitcode = None
        self.finished_at = None

    # TODO: currently only supports a single container (searches for the
    # first container with a 'terminated' status). To support
    # multiple containers, we need some logic around whether a particular
    # container needs to complete succesfully or all containers do.
    def _retrieve_terminated(self):
        if self.exitcode:
            return
        containerstatuses = self.get_status('containerStatuses', [])
        for containerstatus in containerstatuses:
            terminated = (containerstatus.get('state', {}).get('terminated'))
            if terminated:
                self.exitcode = terminated.get('exitCode')
                self.finished_at = date_from_isostr(
                    terminated.get('finishedAt'))

    def update_failure_status(self):
        """
        _update_pod_status

        Update status of parent (OaatGroup) object with details of an
        execution failure for the current Pod.
        """
        parent = self.get_parent()
        item_name = self.get_label('oaat-name', 'unknown')

        current_last_failure = date_from_isostr(
            oaatgroup.get_status(parent.obj, item_name, 'last_failure'))

        self._retrieve_terminated()

        if self.finished_at > current_last_failure:
            current_last_failure = self.finished_at

            failure_count = oaatgroup.get_status(
                parent.obj, item_name, 'failure_count')

            parent.patch({
                'status': {
                    'items': {item_name: {
                        'last_failure': self.finished_at.isoformat(),
                        'failure_count': failure_count + 1
                    }},
                    'currently_running': None,
                    'pod': None,
                    'oaat_timer': {
                        'message':
                        f'item {item_name} failed with exit '
                        f'code {self.exitcode}'
                    },
                    'state': 'idle',
                }
            })
            raise ProcessingComplete(
                error=f'item failed with exit code: {self.exitcode}',
                message=f'item failed with exit code: {self.exitcode}')
        raise ProcessingComplete(
            info=f'ignoring old failed job {self.name}')

    def update_success_status(self):
        """
        _update_pod_status

        Update status of parent (OaatGroup) object with details of an
        execution failure for the current Pod.
        """
        parent = self.get_parent()
        item_name = self.get_label('oaat-name', 'unknown')

        current_last_success = date_from_isostr(
            oaatgroup.get_status(parent.obj, item_name, 'last_success'))

        self._retrieve_terminated()

        if self.finished_at > current_last_success:
            current_last_success = self.finished_at
            self.debug(f'successful termination of pod {self.name}')

            parent.patch({
                'status': {
                    'items': {item_name: {
                        'last_success': self.finished_at.isoformat(),
                        'failure_count': 0
                    }},
                    'currently_running': None,
                    'pod': None,
                    'oaat_timer': {
                        'message': f'item {item_name} completed '
                    },
                    'state': 'idle',
                }
            })
            raise ProcessingComplete(message=f'item {item_name} completed')
        raise ProcessingComplete(
            info=f'ignoring old successful job {self.name}')

    def update_phase(self):
        parent = self.get_parent()
        item_name = self.get_label('oaat-name', 'unknown')

        self.debug(f'pod {self.name}, podphase: {self.phase}')
        parent.patch(
            {'status': {
                'items': {item_name: {'podphase': self.phase}}
            }})

    def get_parent(self):
        """Retrieve the Pod's parent from the parent-name label."""
        namespace = self.namespace if self.namespace else pykube.all
        query = OaatGroup.objects(self.api, namespace=namespace)
        try:
            parent = (query.get_by_name(
                self.kwargs['meta']['labels'].get('parent-name')))
        except pykube.exceptions.ObjectDoesNotExist:
            raise ProcessingComplete(
                info=f'ignoring pod {self.name} as associated OaatGroup '
                f'object no longer exists'
            )
        if parent:
            return parent
        raise ProcessingComplete(
            info=f'ignoring pod {self.name} as we cannot find the '
            f'associated OaatGroup object')
