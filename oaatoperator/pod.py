"""
pod.py

Overseer object for managing Pod objects.
"""
import datetime
import pykube
from typing import Optional

from oaatoperator.utility import date_from_isostr
from oaatoperator.oaatgroup import OaatGroup
from oaatoperator.common import ProcessingComplete
from oaatoperator.overseer import Overseer


class PodOverseer(Overseer):
    """
    PodOverseer

    Manager for Pod objects.

    Initialise with the kwargs for a Pod kopf handler.
    """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.phase = kwargs['status'].get('phase', '')
        self.my_pykube_objtype = pykube.Pod
        self.exitcode = -1
        self.reason: Optional[str] = None
        self.finished_at: Optional[datetime.datetime] = None

    # TODO: currently only supports a single container (searches for the
    # first container with a 'terminated' status). To support
    # multiple containers, we need some logic around whether a particular
    # container needs to complete succesfully or all containers do.
    def _retrieve_terminated(self) -> None:
        if self.exitcode != -1:
            return
        containerstatuses = self.get_status('containerStatuses', [])
        for containerstatus in containerstatuses:
            self.reason = (containerstatus.get('state', {}).get('reason'))
            terminated = (containerstatus.get('state', {}).get('terminated'))
            if terminated:
                self.exitcode = terminated.get('exitCode', -1)
                self.finished_at = date_from_isostr(
                    terminated.get('finishedAt'))
                return
            self.warning(
                f'cannot find terminated status for {self.name} '
                f'(reason: {self.reason})'
            )
        if self.reason is not None:
            return
        if self.finished_at is None:
            raise ProcessingComplete(
                error=f'unable to determine termination time for {self.name}',
                message=f'unable to determine termination time for {self.name}'
            )
        if self.exitcode == -1:
            raise ProcessingComplete(
                error=f'unable to determine exit code for {self.name}',
                message=f'unable to determine exit code for {self.name}'
            )

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
                error=f'item failed with exit code: {self.exitcode}, ' +
                      f'reason: {self.reason}',
                message=f'item failed with exit code: {self.exitcode}, ' +
                      f'reason: {self.reason}')
        raise ProcessingComplete(
            message=f'ignoring old failed job pod={self.name}')

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
            message=f'ignoring old successful job pod={self.name}')

    def update_phase(self) -> None:
        item_name = self.get_label('oaat-name', 'unknown')
        self.get_parent().set_item_status(item_name, 'podphase', self.phase)
        raise ProcessingComplete(
            message=f'updating phase for pod {self.name}: {self.phase}')

    def get_parent(self) -> OaatGroup:
        """Retrieve the Pod's parent from the parent-name label."""
        return OaatGroup(
            kube_object_name=self.meta['labels'].get('parent-name'),
            logger=self.logger)
