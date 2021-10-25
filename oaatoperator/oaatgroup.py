"""
oaatgroup.py

Overseer object for managing OaatGroup objects.
"""
from random import randrange
import datetime
import kopf
import pykube
from typing import Any
import oaatoperator.utility
from oaatoperator.common import (InternalError, ProcessingComplete,
                                 KubeOaatGroup)
from oaatoperator.oaattype import OaatType
from oaatoperator.oaatitem import OaatItems
from oaatoperator.overseer import Overseer


# TODO: I'm not convinced about this composite object. It's essentially
# trying to keep things DRY when sometimes we need to operate with
# an OaatGroup Kopf object and sometimes we only have a KubeOaatGroup
# (specifically when Kopf is processing a Pod but we need to interact)
# with the OaatGroup. However, there's so many conditionals required
# that it would seem like having separate objects might actually make
# more sense, even if there are two totally separate implementations
# of some functions (like mark_failed())


class OaatGroupOverseer(Overseer):
    """
    OaatGroupOverseer

    Manager for OaatGroup objects.

    Initialise with the kwargs for a OaatGroup kopf handler.
    """
    def __init__(self, parent, **kwargs) -> None:
        super().__init__(**kwargs)
        self.my_pykube_objtype = KubeOaatGroup
        self.obj = kwargs
        self.parent = parent
        self.spec = kwargs.get('spec', {})
        self.body = kwargs.get('body')
        self.freq = oaatoperator.utility.parse_duration(
            self.spec.get('frequency', '1h'))
        self.oaattypename = self.spec.get('oaatType')
        self.oaattype = OaatType(name=self.oaattypename)
        self.cool_off = oaatoperator.utility.parse_duration(
            self.spec.get('failureCoolOff'))
        self.items = OaatItems(obj=self.obj)

    # TODO: if the oldest item keeps failing, consider running
    # other items which are ready to run
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
        oaat_items = self.items.list()
        item_status = {item['name']: 'candidate' for item in oaat_items}

        if not oaat_items:
            raise ProcessingComplete(
                message='error in OaatGroup definition',
                error='no items found. please set "oaatItems"')

        print(f'debug: {self.debug}')
        self.debug('oaat_items: ' +
                   ', '.join([i['name'] for i in oaat_items]))

        # Filter out items which have been recently successful
        self.debug(f'frequency: {self.freq}s')
        self.debug(f'now: {now}')
        self.debug(f'cool_off: {self.cool_off}')

        candidates = []
        for item in oaat_items:
            if now > item['success'] + self.freq:
                candidates.append(item)
                item_status[item['name']] = (
                    f'not successful within last freq ({self.freq})')
            else:
                item_status[item['name']] = (
                    f'successful within last freq ({self.freq})')

        self.debug('Valid, based on success: ' +
                   ', '.join([i['name'] for i in candidates]))

        # Filter out items which have failed within the cool off period
        if self.cool_off is not None:
            for item in oaat_items:
                self.debug(f'testing {item["name"]} - '
                           f'now: {now}, '
                           f'failure: {item["failure"]}, '
                           f'cool_off: {self.cool_off}, '
                           f'cooling off?: {now < item["failure"] + self.cool_off}')
                if now < item['failure'] + self.cool_off:
                    candidates.remove(item)
                    item_status[item['name']] = (
                        f'cool_off ({self.cool_off}) not expired since '
                        f'last failure')

            self.debug('Valid, based on success and failure cool off: ' +
                       ', '.join([i['name'] for i in candidates]))

        self.debug(
            'item status (* = candidate):\n' +
            '\n'.join([
                ('* ' if i in candidates else '- ') +
                f'{i["name"]} ' +
                f'{item_status[i["name"]]} ' +
                f'success={i["success"].isoformat()}, ' +
                f'failure={i["failure"].isoformat()}, ' +
                f'numfails={i["numfails"]}'
                for i in oaat_items
            ])
        )

        if not candidates:
            self.set_status('state', 'idle')
            raise ProcessingComplete(
                message='not time to run next item')

        # return single candidate if there is only one left
        if len(candidates) == 1:
            return candidates[0]['name']

        # Phase 2: Choose the item to run from the valid item candidates
        # Get all items which are "oldest"
        oldest_success_time = min(
            [t['success'] for t in candidates])
        oldest_success_items = [
            item
            for item in candidates
            if item['success'] == oldest_success_time
        ]

        self.debug(f'oldest_items {oldest_success_time}: ' +
                   ', '.join([i['name'] for i in oldest_success_items]))

        if len(oldest_success_items) == 1:
            return oldest_success_items[0]['name']

        # More than one item "equally old" success. Choose based on
        # last failure (but only if there has been a failure for the item)
        failure_items = [
            item
            for item in oldest_success_items
            if item['numfails'] > 0]

        if len(failure_items) == 0:
            # nothing has failed
            remaining_items = oldest_success_items
        else:
            oldest_failure_time = min(
                [item['failure'] for item in failure_items])
            self.debug(f'oldest_failure_time: {oldest_failure_time}')
            oldest_failure_items = [
                item
                for item in oldest_success_items
                if item['failure'] == oldest_failure_time
            ]

            self.debug('oldest_failure_items: ' +
                       ', '.join([i['name'] for i in oldest_failure_items]))

            if len(oldest_failure_items) == 1:
                return oldest_failure_items[0]['name']

            remaining_items = oldest_failure_items

            self.debug('randomly choosing from: ' +
                       ', '.join([i['name'] for i in remaining_items]))

        # more than one "equally old" failure.  Choose at random
        return remaining_items[
            randrange(len(remaining_items))]['name']  # nosec

    def run_item(self, item_name) -> dict:
        """
        run_item

        Execute an item job Pod with the spec details from the appropriate
        OaatType object.
        """
        # TODO: check oaatType
        spec = self.oaattype.podspec()
        contspec = spec['container']
        del spec['container']
        contspec.setdefault('env', []).append({
            'name': 'OAAT_ITEM',
            'value': item_name
        })
        for idx in range(len(contspec.get('command', []))):
            contspec['command'][idx] = (
                contspec['command'][idx].replace('%%oaat_item%%', item_name))
        for idx in range(len(contspec.get('args', []))):
            contspec['args'][idx] = (
                contspec['args'][idx].replace('%%oaat_item%%', item_name))
        for env in contspec['env']:
            env['value'] = (
                env.get('value', '').replace('%%oaat_item%%', item_name))

        # TODO: currently only supports a single container. Do we want
        # multi-container?
        doc = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'generateName': self.name + '-' + item_name + '-',
                'labels': {
                    'parent-name': self.name,
                    'oaat-name': item_name,
                    'app': 'oaat-operator'
                }
            },
            'spec': {
                'containers': [contspec],
                **spec,
                'restartPolicy': 'Never'
            },
        }

        kopf.adopt(doc)
        pod = pykube.Pod(self.api, doc)

        try:
            pod.create()
        except pykube.exceptions.KubernetesError as exc:
            self.parent.mark_item_failed(item_name)
            raise ProcessingComplete(
                error=f'could not create pod {doc}: {exc}',
                message=f'error creating pod for {item_name}')
        return pod

    def validate_items(
            self, status_annotation=None, count_annotation=None) -> None:
        """
        validate_items

        Ensure there are oaatItems to process.
        """
        if not len(self.items):
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
            self.set_annotation(count_annotation, value=len(self.items))

    def validate_state(self) -> None:
        """
        validate_state

        "pod" and "currently_running" should both be None or both be
        set. If they are out of sync, then our state is inconsistent.
        This should only happen in unusual situations such as the
        oaat-operator being killed while starting a pod.

        TODO: currently just resets both to None, effectively ignoring
        the result of a running pod. Ideally, we should validate the
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

    def validate_no_rogue_pods_are_running(self) -> None:
        found_rogue = 0
        for pod in pykube.Pod.objects(self.api,
                                      namespace=self.namespace).iterator():
            if pod.name == self.get_status('pod'):
                continue
            if pod.labels.get('parent-name', '') == self.name:
                if pod.labels.get('app', '') == 'oaat-operator':
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

    def is_pod_expected(self) -> bool:
        curpod = self.get_status('pod')
        if curpod:
            return True
        return False

    def validate_expected_pod_is_running(self) -> None:
        """
        validate_expected_pod_is_running

        Validate that the pod which we expect should be running (based
        on `oaatgroup` status `pod` and `currently_running`)

        Check whether the Pod we previously started is still running. If not,
        assume the job was killed without being processed by the
        operator (or was never started) and clean up. Mark as failed.

        Returns:
        - ProcessingComplete exception:
            - Cleaned up missing/deleted item
            - Pod exists and is in state: <state>
        """
        curpod = self.get_status('pod')
        curitem = self.get_status('currently_running')
        try:
            pod = pykube.Pod.objects(
                self.api,
                namespace=self.namespace).get_by_name(curpod).obj
        except pykube.exceptions.ObjectDoesNotExist:
            self.info(
                f'pod {curpod} missing/deleted, cleaning up')
            self.set_status('currently_running')
            self.set_status('pod')
            self.set_status('state', 'missing')
            self.parent.mark_item_failed(curitem)
            self.parent.set_item_status(curitem, 'pod_detail')
            raise ProcessingComplete(
                message=f'item {curitem} failed during validation',
                info='Cleaned up missing/deleted item')

        podphase = pod.get('status', {}).get('phase', 'unknown')
        self.info(f'validated that pod {curpod} exists '
                  f'(phase={podphase})')
        recorded_phase = self.items.status(curitem, 'podphase', 'unknown')

        # if there is a mismatch in phase, then the pod phase handlers
        # have not yet picked it up and updated the oaatgroup phase.
        # Note it here, but take no further action
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
                         value: str = None) -> None:
        patch = (self.patch
                 .setdefault('status', {})
                 .setdefault('items', {})
                 .setdefault(item_name, {}))
        patch[key] = value

    def validate_oaat_type(self) -> None:
        """
        validate_oaat_type

        Ensure the group refers to an appropriate OaatType object.
        """
        if self.oaattype.valid:
            self.info('found valid oaat type')
            return None
        self.set_annotation('operator-status', 'missingOaatType')
        raise ProcessingComplete(
            message='error in OaatGroup definition',
            error=f'unknown oaat type {self.oaattypename}')


class OaatGroup:
    """
    OaatGroup

    Composite object for KOPF and Kubernetes handling
    """
    api: pykube.HTTPClient = None
    kopf_object: dict = None
    kube_object: dict = None
    items: OaatItems = None
    passthrough_names: list = [
        i for i in dir(OaatGroupOverseer) if i[0] != '_'
    ] + ["name"]

    def __init__(self, **kwargs) -> None:
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        kube_object_name = None

        if 'kopf_object' in kwargs:
            kopf_object = kwargs.get('kopf_object')
            self.kopf_object = OaatGroupOverseer(self, **kopf_object)
            self.items = OaatItems(obj=kopf_object)
            kube_object_name = self.kopf_object.name

        # override kopf object
        if 'kube_object_name' in kwargs:
            kube_object_name = kwargs.get('kube_object_name')
            self.logger = kwargs.get('logger')
            if self.logger is None:
                raise InternalError(
                    'must supply logger= parameter to '
                    f'{self.__class__.__name__} when using kube_object_name'
                )

        if kube_object_name is None:
            raise InternalError(
                f'{self.__class__.__name__} must be called with either a '
                'kopf_object= kopf context or a kube_object_name= name')
        self.kube_object = self.get_kube_object(kube_object_name)
        if isinstance(self.kube_object, str):
            raise TypeError(
                f'get_kube_object returned string: {self.kube_object}')
        if self.items is None:
            self.logger.info(f'kube_object: {self.kube_object}')
            self.items = OaatItems(obj=self.kube_object.obj)

    def namespace(self) -> str:
        if self.kopf_object:
            return self.kopf_object.namespace
        if self.kube_object:
            return self.kube_object.metadata.get('namespace')
        return None

    def get_kube_object(self, name: str) -> KubeOaatGroup:
        namespace = self.namespace()

        try:
            return (KubeOaatGroup.objects(
                self.api, namespace=namespace).get_by_name(name))
        except pykube.exceptions.ObjectDoesNotExist as exc:
            self.message = f'cannot find Object {self.name}: {exc}'
            return None

    def __getattr__(self, name) -> Any:
        if name in self.passthrough_names:
            if self.kopf_object is None:
                raise InternalError(f'attempt to run {name} outside of kopf')
            return getattr(self.kopf_object, name)
        else:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

    def mark_item_failed(self,
                         item_name: str,
                         finished_at: datetime.datetime = None,
                         exit_code: int = -1) -> bool:
        """Mark an item as failed."""

        current_last_failure = self.items.status_date(item_name,
                                                      'last_failure')
        if not finished_at:
            finished_at = oaatoperator.utility.now()
        if not isinstance(finished_at, datetime.datetime):
            raise ValueError(
                'mark_item_failed finished_at= should be '
                'datetime.datetime object')

        if finished_at > current_last_failure:
            failure_count = self.items.status(item_name, 'failure_count', 0)
            self.set_item_status(item_name, 'failure_count', failure_count + 1)
            self.set_item_status(item_name, 'last_failure',
                                 finished_at.isoformat())

            # TODO: if via kopf, will this get overwritten by handler exit?
            self.kube_object.patch({
                'status': {
                    'currently_running': None,
                    'pod': None,
                    'oaat_timer': {
                        'message':
                        f'item {item_name} failed with exit '
                        f'code {exit_code}'
                    },
                    'state': 'idle',
                }
            })
            return True
        return False

    def mark_item_success(self,
                          item_name: str,
                          finished_at: datetime.datetime = None) -> bool:
        """Mark an item as succeeded."""

        current_last_success = self.items.status_date(item_name,
                                                      'last_success')
        if not finished_at:
            finished_at = oaatoperator.utility.now()
        if not isinstance(finished_at, datetime.datetime):
            raise ValueError(
                'mark_item_success finished_at= should be '
                'datetime.datetime object')

        if finished_at > current_last_success:
            self.set_item_status(item_name, 'failure_count', 0)
            self.set_item_status(item_name, 'last_success',
                                 finished_at.isoformat())

            # TODO: if via kopf, will this get overwritten by handler exit?
            self.kube_object.patch({
                'status': {
                    'currently_running': None,
                    'pod': None,
                    'oaat_timer': {
                        'message': f'item {item_name} completed '
                    },
                    'state': 'idle',
                }
            })
            return True
        return False

    def set_item_status(self,
                        item_name: str,
                        key: str,
                        value: str = None) -> None:
        if self.kopf_object is None:
            self.kube_object.patch(
                {'status': {
                    'items': {
                        item_name: {
                            key: value
                        }
                    }
                }})
        else:
            self.kopf_object._set_item_status(item_name, key, value)
