"""
oaatgroup.py

Overseer object for managing OaatGroup objects.
"""
from __future__ import annotations
from random import randrange
import datetime
from typing_extensions import Unpack
import logging
import pykube
from typing import Any, Optional, TypedDict, cast

# local imports
import oaatoperator.utility
import oaatoperator.types as types
from oaatoperator.oaatitem import OaatItems
from oaatoperator.oaattype import OaatType
from oaatoperator.overseer import Overseer
from oaatoperator.common import (InternalError, ProcessingComplete, KubeOaatGroup)


# TODO: I'm not convinced about this composite object. It's essentially
# trying to keep things DRY when sometimes we need to operate with
# an OaatGroup Kopf object and sometimes we only have a KubeOaatGroup
# (specifically when Kopf is processing a Pod but we need to interact
# with the OaatGroup). However, there are so many conditionals required
# that it would seem like having separate objects might actually make
# more sense, even if there are two totally separate implementations
# of some functions (like mark_failed())

# TODO: could move all POD-related functions into OaatItem? Would help with
# future non-POD run mechanisms (e.g. Job)


class OaatGroupOverseer(Overseer):
    """
    OaatGroupOverseer

    Manager for OaatGroup objects.

    Initialise with the kwargs for a OaatGroup kopf handler.
    """
    # these are needed to populate the OaatGroup passthrough_names, so
    # OaatGroup.<attribute> works
    freq : Optional[datetime.timedelta] = None
    oaattype : Optional[OaatType] = None
    status : Optional[dict[str, Any]] = None

    def __init__(self, parent: OaatGroup, **kwargs: Unpack[types.CallbackArgs]) -> None:
        super().__init__(**kwargs)
        self.my_pykube_objtype = KubeOaatGroup
        self.obj = kwargs
        self.parent = parent
        self.freq = oaatoperator.utility.parse_duration(
            self.spec.get('frequency', '1h'))
        self.oaattypename = self.spec.get('oaatType')
        self.oaattype = OaatType(name=self.oaattypename)
        self.cool_off = oaatoperator.utility.parse_duration(
            str(self.spec.get('failureCoolOff')))

    # TODO: if the oldest item keeps failing, consider running
    # other items which are ready to run
    # TODO: consider whether this should be a method of OaatItems()
    def find_job_to_run(self) -> str:
        """
        find_job_to_run

        Find the best item job to run based on last success and
        failure times.

        Basic algorithm:
        - phase one: choose valid item candidates:
            - start with a list of all possible items to run
            - remove from the list items which have been successful within the
              period in the 'frequency' setting
            - remove from the list items which have failed within the period
              in the 'failureCoolOff' setting
        - phase two: choose the item to run from the valid item candidates:
            - if there is just one item, choose it
            - find the item with the oldest success (or has never succeeded)
            - if there is just one item that is 'oldest', choose it
            - of the items with the oldest success, find the item with the
              oldest failure
            - if there is just one item that has both the oldest success and
              the oldest failure, choose it
            - choose at random (this is likely to occur if no items have
              been run - i.e. first iteration)
        """
        now = oaatoperator.utility.now()

        # Phase One: Choose valid item candidates
        oaat_items = self.parent.items.list()
        item_status = {item.name: 'candidate' for item in oaat_items}

        if not oaat_items:
            raise ProcessingComplete(
                message='error in OaatGroup definition',
                error='no items found. please set "oaatItems"')

        self.debug('oaat_items: ' + ', '.join([i.name for i in oaat_items]))

        # Filter out items which have been recently successful
        self.debug(f'frequency: {self.freq}s')
        self.debug(f'now: {now}')
        self.debug(f'cool_off: {self.cool_off}')

        candidates = []
        for item in oaat_items:
            if now > item.success() + self.freq:
                candidates.append(item)
                item_status[item.name] = (
                    f'not successful within last freq ({self.freq})')
            else:
                item_status[item.name] = (
                    f'successful within last freq ({self.freq})')

        self.debug('remaining items, based on last success & frequency: ' +
                   ', '.join([i.name for i in candidates]))

        # Filter out items which have failed within the cool off period
        if self.cool_off is not None:
            for item in oaat_items:
                self.debug(f'testing {item.name} - '
                           f'now: {now}, '
                           f'failure: {item.failure()}, '
                           f'cool_off: {self.cool_off}, '
                           f'cooling off?: {now < item.failure() + self.cool_off}')
                if now < item.failure() + self.cool_off:
                    candidates.remove(item)
                    item_status[item.name] = (
                        f'cool_off ({self.cool_off}) not expired since '
                        f'last failure')

            self.debug('remaining items, based on failure cool off: ' +
                       ', '.join([i.name for i in candidates]))

        self.debug(
            'item status (* = candidate):\n' +
            '\n'.join([
                ('* ' if i in candidates else '- ') +
                f'{i.name} ' +
                f'{item_status[i.name]} ' +
                f'success={i.success().isoformat()}, ' +
                f'failure={i.failure().isoformat()}, ' +
                f'numfails={i.numfails()}'
                for i in oaat_items
            ])
        )

        if not candidates:
            self.set_status('state', 'idle')
            raise ProcessingComplete(
                message='not time to run next item')

        # return single candidate if there is only one left
        if len(candidates) == 1:
            return candidates[0]

        # Phase 2: Choose the item to run from the valid item candidates
        # Get all items which are "oldest"
        oldest_success_time = min(
            [t.success() for t in candidates])
        oldest_success_items = [
            item
            for item in candidates
            if item.success() == oldest_success_time
        ]

        self.debug(f'oldest_items {oldest_success_time}: ' +
                   ', '.join([i.name for i in oldest_success_items]))

        if len(oldest_success_items) == 1:
            return oldest_success_items[0]

        # More than one item "equally old" success. Choose based on
        # last failure (but only if there has been a failure for the item)
        failure_items = [
            item
            for item in oldest_success_items
            if item.numfails() > 0]

        if len(failure_items) == 0:
            # nothing has failed
            remaining_items = oldest_success_items
        else:
            oldest_failure_time = min(
                [item.failure() for item in failure_items])
            self.debug(f'oldest_failure_time: {oldest_failure_time}')
            oldest_failure_items = [
                item
                for item in oldest_success_items
                if item.failure() == oldest_failure_time
            ]

            self.debug('oldest_failure_items: ' +
                       ', '.join([i.name for i in oldest_failure_items]))

            if len(oldest_failure_items) == 1:
                return oldest_failure_items[0]

            remaining_items = oldest_failure_items

            self.debug('randomly choosing from: ' +
                       ', '.join([i.name for i in remaining_items]))

        # more than one "equally old" failure.  Choose at random
        return remaining_items[
            randrange(len(remaining_items))]  # nosec

    def validate_items(
            self, status_annotation=None, count_annotation=None) -> None:
        """
        validate_items

        Ensure there are oaatItems to process.
        """
        if not len(self.parent.items):
            if status_annotation:
                self.set_annotation(status_annotation, 'missingItems')
            raise ProcessingComplete(
                state='nothing to do',
                error='error in OaatGroup definition',
                message=f'no items found. '
                        f'Please set "oaatItems" in {self.name}'
            )

        # we have oaatItems, so mark the object as "active" (via annotation)
        if status_annotation:
            self.set_annotation(status_annotation, 'active')
        if count_annotation:
            self.set_annotation(count_annotation, value=str(len(self.parent.items)))

    def verify_running(self) -> None:
        self.verify_state()

        self.delete_rogue_pods()

        # Check the currently-running job
        if self.is_pod_expected():
            self.verify_expected_pod_is_running()

    # TODO: --> OaatItem.verify() ?
    def verify_state(self) -> None:
        """
        verify_state

        "pod" and "currently_running" should both be None or both be
        set. If they are out of sync, then our state is inconsistent.
        This should only happen in unusual situations such as the
        oaat-operator being killed while starting a pod.

        TODO: currently just resets both to None, effectively ignoring
        the result of a running pod. Ideally, we should verify the
        status of the pod and clean up.
        """
        curpod = self.get_status('pod')
        curitem = self.get_status('currently_running')
        if curpod is None and curitem is None:
            return None
        if curpod is not None and curitem is not None:
            return None

        self.set_status('currently_running')
        self.set_status('pod')

        raise ProcessingComplete(
            state='inconsistent state',
            message='internal error',
            error=(
                f'inconsistent state detected. '
                f'pod ({curpod}) is inconsistent '
                f'with currently_running ({curitem})')
        )

    # TODO: --> OaatItem.verify() ?
    def delete_rogue_pods(self) -> None:
        curpod = self.get_status('pod')
        if not curpod:
            self.info(f'curpod is "{curpod} (self: {self})')
            self.debug(
                f'currently_running: {self.get_status("currently_running")}')
            return
        found_rogue = 0
        self.debug(f'searching for rogue pods.')
        self.debug(f'  current={self.get_status("pod")}')
        candidate_pods: pykube.query.Query = (
            pykube.Pod
            .objects(self.api)
            .filter(namespace=self.namespace)   # type: ignore (pykube needs Optional[str] for namespace)
            .filter(selector={'app': 'oaat-operator'})
        )
        for pod in candidate_pods.iterator():
            self.debug(f'  checking {pod.name}')
            if pod.name == self.get_status('pod'):
                continue    # skip over the active pod
            if pod.labels.get('parent-name', '') == self.name:
                podphase = (pod.obj['status'].get('phase', 'unknown'))
                if podphase in ['Running', 'Pending']:
                    pod.delete()
                    self.warning(
                        f'rogue pod {pod.name} found (phase={podphase})')
                    found_rogue += 1

        if found_rogue > 0:
            raise ProcessingComplete(
                message='rogue pods running',
                error=f'found {found_rogue} rogue pods running'
            )

    # TODO: --> OaatItem.verify() ?
    def is_pod_expected(self) -> bool:
        curpod = self.get_status('pod')
        if curpod:
            return True
        return False

    # TODO: --> OaatItem.verify() ?
    def verify_expected_pod_is_running(self) -> None:
        """
        verify_expected_pod_is_running

        Verify that the pod which we expect should be running (based
        on `oaatgroup` status `pod` and `currently_running`) is actually
        running.

        Check whether the Pod we previously started is still running. If not,
        assume the job was killed without being processed by the
        operator (or was never started) and clean up. Mark as failed.

        Returns:
        - ProcessingComplete exception:
            - Cleaned up missing/deleted item
            - Pod exists and is in state: <state>
        """
        curpod = self.get_status('pod')
        curitem_name = self.get_status('currently_running')
        try:
            pod = pykube.Pod.objects(
                self.api,
                namespace=self.namespace).get_by_name(curpod).obj   # type: ignore (pykube needs Optional[str] for namespace)
        except pykube.exceptions.ObjectDoesNotExist:
            self.info(f'pod {curpod} missing/deleted, cleaning up')
            self.set_status('currently_running')
            self.set_status('pod')
            self.set_status('state', 'missing')
            self.parent.mark_item_failed(curitem_name)
            self.parent.set_item_status(curitem_name, 'pod_detail')
            raise ProcessingComplete(
                message=f'item {curitem_name} failed during validation',
                info='Cleaned up missing/deleted item')

        podphase = pod.get('status', {}).get('phase', 'unknown')
        self.info(f'verified that pod {curpod} exists '
                  f'(phase={podphase})')
        recorded_phase = self.parent.items.get(curitem_name).status('podphase', 'unknown')

        # if there is a mismatch in phase, then the pod phase handlers
        # have not yet picked it up and updated the oaatgroup phase.
        # Note it here, but take no further action (pod_phasechange should
        # deal with it within its interval time)
        if podphase != recorded_phase:
            self.info(f'mismatch in phase for pod {curpod}: '
                      f'pod={podphase}, oaatgroup={recorded_phase}')

        # valid phases are Pending, Running, Succeeded, Failed, Unknown
        # 'started' is the phase the pods start with when created by
        # operator.

        raise ProcessingComplete(
            message=f'Pod {curpod} exists and is in state {podphase}')

    def _set_item_status(self,
                         item_name: str,
                         key: str,
                         value: Optional[str] = None) -> None:
        patch: dict = (self.patch
                 .setdefault('status', {})
                 .setdefault('items', {})
                 .setdefault(item_name, {}))
        patch[key] = value

    # def validate_oaat_type(self) -> None:
    #     """
    #     validate_oaat_type

    #     Ensure the group refers to an appropriate OaatType object.
    #     """
    #     if self.oaattype is not None:
    #         self.info('found valid oaat type')
    #         return None
    #     self.set_annotation('operator-status', 'missingOaatType')
    #     raise ProcessingComplete(
    #         message='error in OaatGroup definition',
    #         error=f'unknown oaat type {self.oaattypename}')


class OaatGroupArgs(TypedDict):
    kopf_object: Optional[types.CallbackArgs]
    kube_object_name: Optional[str]

class OaatGroup:
    """
    OaatGroup

    Composite object for KOPF and Kubernetes handling
    """
    api: pykube.HTTPClient
    kopf_object: Optional[OaatGroupOverseer]
    kube_object: KubeOaatGroup
    logger: logging.Logger
    status: dict
    items: OaatItems
    passthrough_names: list = [
        i for i in dir(OaatGroupOverseer) if i[0] != '_'
    ] + ["name"]

    def __init__(self,
                 kopf_object: Optional[types.CallbackArgs] = None,
                 kube_object_name: Optional[str] = None,
                 kube_object_namespace: str = 'default',
                 logger: Optional[logging.Logger] = None) -> None:
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())

        # kopf object supplied
        if kopf_object is not None:
            self.kopf_object = OaatGroupOverseer(
                self, **cast(types.CallbackArgs, kopf_object))
            self.items = OaatItems(group=self,
                                   obj=cast(dict[str, Any], kopf_object))
            return

        # kube object name supplied
        if kube_object_name is not None:
            self.logger = cast(logging.Logger, logger)
            if self.logger is None:
                raise InternalError(
                    'must supply logger= parameter to '
                    f'{self.__class__.__name__} when using kube_object_name'
                )

        # neither kopf object nor kube name supplied
        if kube_object_name is None:
            raise InternalError(
                f'{self.__class__.__name__} must be called with either a '
                'kopf_object= kopf context or a kube_object_name= name')

        # retrieve kube object if we're provided a name
        # TODO: refactor to use self.group.get_kubeobj()
        self.kopf_object = None
        self.kube_object = self.get_kube_object(kube_object_name,
                                                kube_object_namespace)
        self.logger.debug(f'kube_object: {self.kube_object}')
        self.items = OaatItems(group=self,
                               obj=cast(dict[str, Any], self.kube_object.obj))
        self.status = self.kube_object.obj.get('status', {})

    def namespace(self) -> Optional[str]:
        if self.kopf_object:
            return self.kopf_object.namespace   # type: ignore (pykube needs Optional[str] for namespace)
        if self.kube_object:
            return self.kube_object.metadata.get('namespace')

    def get_kube_object(self, name: str, namespace: str) -> KubeOaatGroup:
        try:
            return (KubeOaatGroup.objects(
                self.api, namespace=namespace).get_by_name(name))   # type: ignore (pykube needs Optional[str] for namespace)
        except pykube.exceptions.ObjectDoesNotExist as exc:
            raise RuntimeError(f'cannot find Object {name}: {exc}')

    # expose kopf object data as attributes of the OaatGroup object
    # TODO: what if there is no kopf object? Shouldn't we get the data
    # from the kube object?
    def __getattr__(self, name) -> Any:
        if name in self.passthrough_names:
            if self.kopf_object is None:
                raise InternalError(f'attempt to retrieve {name} outside of kopf')
            return getattr(self.kopf_object, name)
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

    def mark_item_failed(self,
                         item_name: str,
                         finished_at: Optional[datetime.datetime] = None,
                         exit_code: int = -1) -> bool:
        """Mark an item as failed."""
        item = self.items.get(item_name)
        current_last_failure = item.status_date('last_failure')
        if not finished_at:
            finished_at = oaatoperator.utility.now()
        if not isinstance(finished_at, datetime.datetime):
            raise ValueError(
                'mark_item_failed finished_at= should be '
                'datetime.datetime object')

        if finished_at > current_last_failure:
            failure_count = item.numfails()
            self.set_item_status(item_name, 'failure_count', str(failure_count + 1))
            self.set_item_status(item_name, 'last_failure',
                                 finished_at.isoformat())

            # TODO: if via kopf, will this get overwritten by handler exit?
            self.set_group_status({
                'currently_running': None,
                'pod': None,
                'oaat_timer': {
                    'message':
                    f'item {item_name} failed with exit '
                    f'code {exit_code}'
                },
                'state': 'idle',
            })
            return True
        return False

    def mark_item_success(self,
                          item_name: str,
                          finished_at: Optional[datetime.datetime] = None) -> bool:
        """Mark an item as succeeded."""

        item = self.items.get(item_name)
        current_last_success = item.success()
        if not finished_at:
            finished_at = oaatoperator.utility.now()
        if not isinstance(finished_at, datetime.datetime):
            raise ValueError(
                'mark_item_success finished_at= should be '
                'datetime.datetime object')

        if finished_at > current_last_success:
            self.set_item_status(item_name, 'failure_count', '0')
            self.set_item_status(item_name, 'last_success',
                                 finished_at.isoformat())

            # TODO: if via kopf, will this get overwritten by handler exit?
            self.set_group_status({
                'currently_running': None,
                'pod': None,
                'oaat_timer': {
                    'message': f'item {item_name} completed '
                },
                'state': 'idle',
            })
            return True
        return False

    def set_item_status(self,
                        item_name: str,
                        key: str,
                        value: Optional[str] = None) -> None:
        if self.kopf_object is None:
            self.kube_object.patch(
                {'status': {
                    'items': {
                        item_name: { key: value }
                    }
                }})
        else:
            self.kopf_object._set_item_status(item_name, key, value)

    def set_group_status(self, values: dict[str, Any]) -> None:
        if self.kopf_object is None:
            self.kube_object.patch({'status': values})
        else:
            self.kopf_object.set_object_status(values)
