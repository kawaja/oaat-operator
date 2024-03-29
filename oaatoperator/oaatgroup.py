"""
oaatgroup.py

Overseer object for managing OaatGroup objects.
"""
from __future__ import annotations
from random import randrange
import datetime
from typing_extensions import Unpack
import logging
import pykube  # type: ignore
import kopf
from typing import Any, List, Set, Optional, TypedDict, Type, cast
from kopf._cogs.structs import bodies

# local imports
import oaatoperator.utility
import oaatoperator.py_types as py_types
from oaatoperator.oaatitem import OaatItems, OaatItem
from oaatoperator.oaattype import OaatType
from oaatoperator.overseer import Overseer
from oaatoperator.common import (ProcessingComplete, KubeOaatGroup,
                                 InternalError)


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
    freq: datetime.timedelta = datetime.timedelta(hours=1)
    oaattype: Optional[OaatType] = None
    status: Optional[bodies.Status] = None

    def __init__(self, parent: OaatGroup,
                 **kwargs: Unpack[py_types.CallbackArgs]) -> None:
        super().__init__(**kwargs)
        self.my_pykube_objtype: Type[pykube.objects.APIObject] = KubeOaatGroup
        self.obj = kwargs
        self.parent = parent
        specfreq = self.spec.get('frequency', '1h')
        freq = oaatoperator.utility.parse_duration(specfreq)
        if freq is None:
            raise kopf.PermanentError(
                f'invalid frequency specification {specfreq} in {self.name}')
        self.freq = freq
        self.oaattypename = self.spec.get('oaatType')
        self.oaattype = OaatType(name=self.oaattypename)
        self.cool_off = oaatoperator.utility.parse_duration(
            str(self.spec.get('failureCoolOff')))

    # TODO: consider whether this should be a method of OaatItems()
    def find_job_to_run(self) -> OaatItem:
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
        oaat_items: List[OaatItem] = self.parent.items.list()
        longest_item = max([len(item.name) for item in oaat_items]+[1])
        item_status = {item.name: 'candidate' for item in oaat_items}
        display_name = {
            item.name: item.name.ljust(longest_item, ' ')
            for item in oaat_items
        }

        if not oaat_items:
            raise ProcessingComplete(
                message='error in OaatGroup definition',
                error='no items found. please set "oaatItems"')

        self.debug('oaat_items: ' + ', '.join([i.name for i in oaat_items]))

        # Filter out items which have been recently successful
        self.debug(f'frequency: {self.freq}s')
        self.debug(f'now: {now}')
        self.debug(f'cool_off: {self.cool_off}')

        candidates = set()
        for item in oaat_items:
            if now > item.success() + self.freq:
                candidates.add(item)
                item_status[item.name] = (
                    f'not successful within last {self.freq}')
            else:
                item_status[item.name] = (
                    f'successful within last {self.freq}')

        self.debug('remaining items, based on last success & frequency: ' +
                   ', '.join(sorted([i.name for i in candidates])))

        # Filter out items which have failed within the cool off period
        if self.cool_off is not None:
            for item in candidates.copy():
                if now < item.failure() + self.cool_off:
                    candidates.remove(item)
                    item_status[item.name] = (
                        f'cool_off ({self.cool_off}) not expired since '
                        f'last failure')

            self.debug('remaining items, based on failure cool off: ' +
                       ', '.join(sorted([i.name for i in candidates])))

        find_job_status = (
            f'find_job last run: {now.isoformat()}\n'
            'item status (* = candidate):\n' +
            '\n'.join(sorted([
                ('* ' if i in candidates else '- ') +
                f'{display_name[i.name]} ' +
                f'{item_status[i.name]} - ' +
                f'success={i.success().isoformat()}, ' +
                f'failure={i.failure().isoformat()}, ' +
                f'numfails={i.numfails()}'
                for i in oaat_items
            ]))
        )
        self.info(find_job_status)
        self.set_status('find_job', find_job_status)

        if not candidates:
            self.set_status('state', 'idle')
            raise ProcessingComplete(
                message='not time to run next item')

        # return single candidate if there is only one left
        if len(candidates) == 1:
            return candidates.pop()

        # Phase 2: Choose the item to run from the valid item candidates
        # Get all items which are "oldest"
        oldest_success_items = oaatoperator.utility.min_set(
            candidates, lambda x: x.success())

        self.debug('oldest_success_items: ' +
                   ', '.join(sorted([i.name for i in oldest_success_items])))

        # Choose based on last failure (but only if there has been
        # a failure for the item)
        failure_items = {
            item
            for item in candidates
            if item.numfails() > 0}

        self.debug('failure_items: ' +
                   ', '.join(sorted([i.name for i in failure_items])))

        remaining_items: Set[OaatItem] = set()
        if len(failure_items) == 0:
            # nothing has failed
            remaining_items = oldest_success_items
        else:
            oldest_failure_items = oaatoperator.utility.min_set(
                failure_items, lambda x: x.failure())

            self.debug('oldest_failure_items: ' +
                       ', '.join(sorted(
                           [i.name for i in oldest_failure_items])))

            # if we always choose the failed items, we can get stuck
            # on items which consistently fail. So, 1 in 3 we should
            # ignore the failed items and choose from the non-failed items
            if randrange(3) == 0:
                self.debug(
                    'wildcard! selecting from previously-successful items')
                remaining_items = oaatoperator.utility.min_set(
                    candidates - failure_items, lambda x: x.success())
            if not remaining_items:
                remaining_items = oldest_failure_items

        # Choose at random
        self.debug('randomly choosing from: ' +
                   ', '.join(sorted([i.name for i in remaining_items])))

        return list(remaining_items)[randrange(len(remaining_items))]  # nosec

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
            self.set_annotation(count_annotation,
                                value=str(len(self.parent.items)))

    def select_survivor(self, pods: List[pykube.Pod]) -> pykube.Pod:
        def get_start_time(pod):
            start_time = pod.obj.get('status', {}).get('startTime', '')
            return oaatoperator.utility.date_from_isostr(start_time)

        ordered_pods = sorted(pods, key=get_start_time)
        return ordered_pods[0]

    def delete_non_survivor_pods(self, survivor) -> None:
        found_rogue = 0
        self.debug('searching for rogue pods.')
        self.debug(f'  survivor={survivor.name}')
        # (pykube needs Optional[str] for namespace)
        all_pods: pykube.query.Query = (
            pykube.Pod.objects(self.api).filter(
                namespace=self.namespace)  # type: ignore
            .filter(selector={
                'app': 'oaat-operator',
                'parent-name': self.name
            }))
        for pod in all_pods.iterator():
            self.debug(f'  checking {pod.name}')
            if pod.name == survivor.name:
                self.debug(f'  skipping {pod.name} as this is the survivor')
                continue    # skip over the surviving pod
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

    def resume_running_pod(self) -> Optional[dict[str, str]]:
        pod = self.identify_running_pod()
        if pod is not None:
            return {
                'oaat-name': pod.labels.get('oaat-name', 'unknown'),
                'pod': pod.name
            }
        return None

    def identify_running_pod(self) -> Optional[pykube.Pod]:
        running_pods: List[pykube.Pod] = []
        all_pods: pykube.query.Query = (
            pykube.Pod.objects(self.api).filter(
                namespace=self.namespace)  # type: ignore
            .filter(selector={
                'app': 'oaat-operator',
                'parent-name': self.name
            }))
        for pod in all_pods.iterator():
            self.debug(f'  checking {pod.name}')
            podphase = (pod.obj['status'].get('phase', 'unknown'))
            self.debug(f'    {pod.name} phase = {podphase}')
            if podphase in ['Running', 'Pending']:
                running_pods.append(pod)

        self.debug(f'    found {len(running_pods)} running pods')

        if len(running_pods) == 0:
            return None

        return self.select_survivor(running_pods)

    def verify_running_pod(self, pod: pykube.Pod) -> None:
        """
        verify_running_pod

        Verifies that the running pod is still healthy
        """
        phase = pod.obj.get('status', {}).get('phase', 'unknown')
        item_name = pod.labels.get('oaat-name', 'unknown')
        self._set_item_status(item_name, 'last_verified',
                              oaatoperator.utility.now_iso())
        raise ProcessingComplete(
            message=f'Pod {pod.name} exists and is in state {phase}')

    def verify_running(self) -> None:
        """
        verify_running

        Verifies that a valid pod is running and no
        other (ooat-operator) pods are running. `verify_running()` does
        the latter by selecting the oldest Pod in `Running` or `Pending` state
        and deletes all others.

        Returns:
        - ProcessingComplete exception
            - valid pod is running
            - one or more rogue pods found and deleted (ensures a
              full timer cycle is completed before attempting to
              start a new pod)
            - inconsistent state (value of 'curpod' and value of
              'currently_running' are not consistent with each other)
        - None
            - no pods running, OK to consider starting a new pod
        """
        curpod = self.identify_running_pod()
        if curpod is not None:
            self.delete_non_survivor_pods(curpod)
            self.verify_running_pod(curpod)

    def _set_item_status(self,
                         item_name: str,
                         key: str,
                         value: Optional[str] = None) -> None:
        if self.patch is None:
            raise kopf.PermanentError('kopf error: patch is None')
        patch: dict = (self.patch
                       .setdefault('status', {})
                       .setdefault('items', {})
                       .setdefault(item_name, {}))
        patch[key] = value


class OaatGroupArgs(TypedDict):
    kopf_object: Optional[py_types.CallbackArgs]
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
    memo: kopf.Memo
    items: OaatItems
    passthrough_names: list = [
        i for i in dir(OaatGroupOverseer) if i[0] != '_'
    ] + ["name"]

    def __init__(self,
                 kopf_object: Optional[py_types.CallbackArgs] = None,
                 kube_object_name: Optional[str] = None,
                 kube_object_namespace: str = 'default',
                 memo: Optional[kopf.Memo] = None,
                 logger: Optional[logging.Logger] = None) -> None:
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())

        # kopf object supplied
        if kopf_object is not None:
            self.kopf_object = OaatGroupOverseer(
                self, **cast(py_types.CallbackArgs, kopf_object))
            self.items = OaatItems(group=self,
                                   obj=cast(dict[str, Any], kopf_object))
            self.memo = kopf_object['memo']
            return

        # kube object name supplied
        if kube_object_name is not None:
            self.logger = cast(logging.Logger, logger)
            if memo is None:
                raise kopf.PermanentError(
                    'must supply memo= parameter to '
                    f'{self.__class__.__name__} when using kube_object_name'
                )
            self.memo = memo
            if self.logger is None:
                raise kopf.PermanentError(
                    'must supply logger= parameter to '
                    f'{self.__class__.__name__} when using kube_object_name'
                )

        # neither kopf object nor kube name supplied
        if kube_object_name is None:
            raise kopf.PermanentError(
                f'{self.__class__.__name__} must be called with either a '
                'kopf_object= kopf context or a kube_object_name= name')

        # retrieve kube object if we're provided a name
        # TODO: refactor to use self.group.get_kubeobj()
        self.kopf_object = None
        self.kube_object = self.get_kube_object(kube_object_name,
                                                kube_object_namespace)
        self.items = OaatItems(group=self,
                               obj=cast(dict[str, Any], self.kube_object.obj))
        self.status = self.kube_object.obj.get('status', {})

    def namespace(self) -> Optional[str]:
        if self.kopf_object:
            # (pykube needs Optional[str] for namespace)
            return self.kopf_object.namespace   # type: ignore
        if self.kube_object:
            return self.kube_object.metadata.get('namespace')
        raise InternalError(
            'neither kopf_object nor kube_object is set '
            f'{oaatoperator.utility.my_details(1)}'
        )

    def get_kube_object(self, name: str, namespace: str) -> KubeOaatGroup:
        try:
            # (pykube needs Optional[str] for namespace)
            return (KubeOaatGroup.objects(
                self.api,
                namespace=namespace).get_by_name(name))  # type: ignore
        except pykube.exceptions.ObjectDoesNotExist as exc:
            raise kopf.TemporaryError(f'cannot find Object {name}: {exc}')

    # expose kopf object data as attributes of the OaatGroup object
    # TODO: what if there is no kopf object? Shouldn't we get the data
    # from the kube object?
    def __getattr__(self, name) -> Any:
        if name in self.passthrough_names:
            if self.kopf_object is None:
                raise kopf.PermanentError(
                    f'attempt to retrieve {name} '
                    f'outside of kopf: {oaatoperator.utility.my_details(1)}'
                )
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
        if not finished_at:
            finished_at = oaatoperator.utility.now()
        if not isinstance(finished_at, datetime.datetime):
            raise ValueError(
                'mark_item_failed finished_at= should be '
                'datetime.datetime object')

        if finished_at > item.failure() and finished_at > item.success():
            failure_count = item.numfails()
            self.set_item_status(item_name, 'failure_count',
                                 str(failure_count + 1))
            self.set_item_status(item_name, 'last_failure',
                                 finished_at.isoformat())
            self.set_item_status(item_name, 'last_verified')

            self.memo.currently_running = None
            self.memo.pod = None
            self.memo.state = 'idle'
            # TODO: if via kopf, will this get overwritten by handler exit?
            self.set_group_status(
                'oaat_timer',
                {
                    'message':
                    f'item {item_name} failed with exit code {exit_code}'
                },
            )
            return True
        return False

    def mark_item_success(
            self,
            item_name: str,
            finished_at: Optional[datetime.datetime] = None) -> bool:
        """Mark an item as succeeded."""

        item = self.items.get(item_name)
        if not finished_at:
            finished_at = oaatoperator.utility.now()
        if not isinstance(finished_at, datetime.datetime):
            raise ValueError(
                'mark_item_success finished_at= should be '
                'datetime.datetime object')

        if finished_at > item.failure() and finished_at > item.success():
            self.set_item_status(item_name, 'failure_count', '0')
            self.set_item_status(item_name, 'last_success',
                                 finished_at.isoformat())
            self.set_item_status(item_name, 'last_verified')

            self.memo.currently_running = None
            self.memo.pod = None
            self.memo.state = 'idle'
            # TODO: if via kopf, will this get overwritten by handler exit?
            self.set_group_status('oaat_timer',
                                  {'message': f'item {item_name} completed'})
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
                        item_name: {key: value}
                    }
                }})
        else:
            self.kopf_object._set_item_status(item_name, key, value)

    def set_group_status(self, key: str, value: Optional[Any] = None) -> None:
        if self.kopf_object is None:
            self.kube_object.patch({'status': {key: value}})
        else:
            self.kopf_object.set_status(key, value)
