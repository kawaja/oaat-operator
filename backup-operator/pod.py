"""
pod.py

Overseer object for managing Pod objects.
"""
import pykube
from pykube import Pod
from utility import date_from_isostr
from common import ProcessingComplete, Backup
import overseer
import backup

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

    def update_status(self, parent, phase, backup_name):
        #, status, name, logger, **_):
        """
        _update_pod_status

        Update status of parent (Backup) object with details of execution
        of the current Pod.
        """
        # TODO: currently only supports a single container. To support
        # multiple containers, we need some logic around whether a particular
        # container needs to complete succesfully or all containers do.
        containerstatuses = self.get_status('containerStatuses', [])
        terminated = None
        finish_message = None
        parent_message = None
        new_status = {}

        current_last_success = date_from_isostr(
            backup.get_status(parent.obj, backup_name, 'last_success'))

        current_last_failure = date_from_isostr(
            backup.get_status(parent.obj, backup_name, 'last_failure'))

        for containerstatus in containerstatuses:
            terminated = (containerstatus.get('state', {}).get('terminated'))
            if terminated:
                exit_code = terminated.get('exitCode')
                endtime = date_from_isostr(terminated.get('finishedAt'))
                if exit_code == 0:
                    if endtime > current_last_success:
                        current_last_success = endtime
                        self.debug(f'successful termination of pod {self.name}')
                        new_status = {
                            'last_success': endtime.isoformat(),
                            'podphase': phase
                        }
                        parent_message = f'backup {backup_name} completed'
                    else:
                        raise ProcessingComplete(
                            message=f'ignoring old successful job {self.name}')
                else:
                    if endtime > current_last_failure:
                        current_last_failure = endtime
                        self.debug(f'pod {self.name}, podphase: BadExit')
                        new_status = {
                            'last_failure': endtime.isoformat(),
                            'podphase': 'BadExit'
                        }
                        parent_message = (f'backup {backup_name} failed with exit '
                                          f'code {exit_code}')
                        finish_message = f'backup failed with exit code: {exit_code}'
                    else:
                        raise ProcessingComplete(
                            message=f'ignoring old failed job {self.name}')

                if parent_message and new_status:
                    parent.patch({
                        'status': {
                            'backups': {backup_name: {**new_status}},
                            'currently_running': None,
                            'backup_pod': None,
                            'backup_timer': {'message': parent_message},
                            'state': 'idle',
                        }
                    })

                if finish_message:
                    raise ProcessingComplete(message=finish_message)

    def get_parent(self):
        """Retrieve the Pod's parent from the parent-name label."""
        #, meta, name, namespace, **_):
        self.get_kubeobject()
        namespace = self.namespace if self.namespace else pykube.all
        query = Backup.objects(self.api, namespace=namespace)
        try:
            parent = (query.get_by_name(
                self.kwargs['meta']['labels'].get('parent-name')))
        except pykube.exceptions.ObjectDoesNotExist:
            raise ProcessingComplete(
                message=
                f'ignoring pod {self.name} as associated Backup '
                f'object no longer exists'
            )
        if parent:
            return parent
        raise ProcessingComplete(
            message=
            f'ignoring pod {self.name} as we cannot find the '
            f'associated Backup object')
