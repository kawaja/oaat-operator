"""
pod.py

Overseer object for managing Pod objects.
"""
import pykube
# from pykube import Pod
from oaatoperator.utility import date_from_isostr
from oaatoperator.oaatgroup import OaatGroup
from oaatoperator.common import ProcessingComplete
from oaatoperator.overseer import Overseer


class OaatPod:
    """
    OaatPod

    Composite object for KOPF and Kubernetes handling
    """
    def __init__(self, **kwargs):
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        if 'kube_object' in kwargs:
            self.kube_object = self.get_kube_object(kwargs.get('kube_object'))
        if 'kopf_object' in kwargs:
            self.kopf_object = PodOverseer(**kwargs.get('kopf_object'))

    def get_kube_object(self, name):
        namespace = self.namespace if self.namespace else pykube.all
        try:
            return (Pod.objects(
                self.api, namespace=namespace).get_by_name(name))
        except pykube.exceptions.ObjectDoesNotExist as exc:
            self.message = f'cannot find Object {self.name}: {exc}'
            return None


class PodOverseer(Overseer):
    """
    PodOverseer

    Manager for Pod objects.

    Initialise with the kwargs for a Pod kopf handler.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.phase = kwargs['status'].get('phase', '')
        self.my_pykube_objtype = pykube.Pod
        self.exitcode = None
        self.finished_at = None

    # TODO: currently only supports a single container (searches for the
    # first container with a 'terminated' status). To support
    # multiple containers, we need some logic around whether a particular
    # container needs to complete succesfully or all containers do.
    def _retrieve_terminated(self) -> None:
        if self.exitcode is not None:
            return
        containerstatuses = self.get_status('containerStatuses', [])
        for containerstatus in containerstatuses:
            terminated = (containerstatus.get('state', {}).get('terminated'))
            if terminated:
                self.exitcode = terminated.get('exitCode')
                self.finished_at = date_from_isostr(
                    terminated.get('finishedAt'))

    def update_failure_status(self) -> None:
        """
        update_failure_status

        Update status of parent object with details of an
        execution failure for the current Pod.
        """
        item_name = self.get_label('oaat-name', 'unknown')
        self._retrieve_terminated()
        if self.get_parent().mark_item_failed(
                item_name,
                finished_at=self.finished_at,
                exit_code=self.exitcode):
            raise ProcessingComplete(
                error=f'item failed with exit code: {self.exitcode}',
                message=f'item failed with exit code: {self.exitcode}')
        raise ProcessingComplete(
            info=f'ignoring old failed job {self.name}')

    def update_success_status(self) -> None:
        """
        update_success_status

        Update status of parent object with details of an
        execution success for the current Pod.
        """
        item_name = self.get_label('oaat-name', 'unknown')
        self._retrieve_terminated()
        if self.get_parent().mark_item_success(
                item_name, finished_at=self.finished_at):
            raise ProcessingComplete(message=f'item {item_name} completed')
        raise ProcessingComplete(
            info=f'ignoring old successful job {self.name}')

    def update_phase(self) -> None:
        item_name = self.get_label('oaat-name', 'unknown')
        self.get_parent().set_item_status(item_name, 'podphase', self.phase)
        raise ProcessingComplete(
            message=f'updating phase for pod {self.name}: {self.phase}')

    def get_parent(self) -> OaatGroup:
        """Retrieve the Pod's parent from the parent-name label."""
        return OaatGroup(kube_object=self.meta['labels'].get('parent-name'))
