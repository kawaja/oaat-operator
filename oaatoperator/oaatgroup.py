"""
oaatgroup.py

Overseer object for managing OaatGroup objects.
"""
from random import randrange
import kopf
import pykube
from pykube import Pod
from oaatoperator.utility import parse_duration
import oaatoperator.utility
from oaatoperator.common import ProcessingComplete, KubeOaatGroup
from oaatoperator.oaattype import OaatType
from oaatoperator.oaatitem import OaatItems
from oaatoperator.overseer import Overseer


class OaatGroupOverseer(Overseer):
    """
    OaatGroupOverseer

    Manager for OaatGroup objects.

    Initialise with the kwargs for a OaatGroup kopf handler.
    """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.freq = parse_duration(kwargs['spec'].get('frequency', '1h'))
        self.my_pykube_objtype = KubeOaatGroup
        self.oaattypename = kwargs.get('spec', {}).get('oaatType')
        self.oaattype = OaatType(name=self.oaattypename)
        self.body = kwargs['body']
        self.cool_off = parse_duration(
            kwargs
            .get('spec', {})
            .get('failureCoolOff')
        )
        self.items = OaatItems(oaatgroupobject=self)

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
        if not oaat_items:
            raise ProcessingComplete(
                message='error in OaatGroup definition',
                error='no items found. please set "oaatItems"')

        self.debug('oaat_items:\n' +
                   '\n'.join([str(i) for i in oaat_items]))

        # Filter out items which have been recently successful
        candidates = [
            item for item in oaat_items
            if now > item['success'] + self.freq
        ]

        self.debug('Valid, based on success:\n' +
                   '\n'.join([str(i) for i in candidates]))

        # Filter out items which have failed within the cool off period
        if self.cool_off:
            candidates = [
                item for item in candidates
                if now > item['failure'] + self.cool_off
            ]

            self.debug('Valid, based on success and failure cool off:\n' +
                       '\n'.join([str(i) for i in candidates]))

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
        self.debug(f'oldest_success_time: {oldest_success_time}')
        oldest_items = [
            item
            for item in candidates
            if item['success'] == oldest_success_time
        ]

        self.debug('oldest_items:\n' +
                   '\n'.join([str(i) for i in oldest_items]))

        if len(oldest_items) == 1:
            return oldest_items[0]['name']

        # More than one item "equally old" success. Choose based on
        # last failure
        oldest_failure_time = min([t['failure'] for t in oldest_items])
        self.debug(f'oldest_failure_time: {oldest_failure_time}')
        oldest_failure_items = [
            item
            for item in oldest_items
            if item['failure'] == oldest_failure_time
        ]

        self.debug('oldest_failure_items:\n' +
                   '\n'.join([str(i) for i in oldest_failure_items]))

        if len(oldest_failure_items) == 1:
            return oldest_failure_items[0]['name']

        # more than one "equally old" failure.  Choose at random
        return oldest_failure_items[
            randrange(len(oldest_failure_items))]['name']  # nosec

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
            contspec['command'][idx] = (
                contspec['command'][idx].replace('%%oaat_item%%', item_name))
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
        pod = Pod(self.api, doc)

        try:
            pod.create()
        except pykube.KubernetesError as exc:
            self.items.mark_failed(item_name)
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
        if not self.items.count():
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
            self.set_annotation(count_annotation, value=self.items.count())

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

    def validate_running_pod(self) -> None:
        """
        validate_running_pod

        Check whether the Pod we previously started is still running. If not,
        assume the job was killed without being processed by the
        operator (or was never started) and clean up. Mark as failed.

        If Pod is still running, update the status details.
        """
        curpod = self.get_status('pod')
        curitem = self.get_status('currently_running')
        if curpod:
            try:
                pod = Pod.objects(
                    self.api,
                    namespace=self.namespace).get_by_name(curpod).obj
            except pykube.exceptions.ObjectDoesNotExist:
                self.info(
                    f'pod {curpod} missing/deleted, cleaning up')
                self.set_status('currently_running')
                self.set_status('pod')
                self.set_status('state', 'missing')
                self.items.mark_failed(curitem)
                self.items.set_status(curitem, 'pod_detail')
                raise ProcessingComplete(
                    info='Cleaned up missing/deleted item')

            podphase = pod.get('status', {}).get('phase', 'unknown')
            self.info(f'validated that pod {curpod} is '
                      f'still running (phase={podphase})')

            recorded_phase = self.items.status(curitem, 'podphase', 'unknown')

            # valid phases are Pending, Running, Succeeded, Failed, Unknown
            # 'started' is the phase the pods start with when created by
            # operator.
            if recorded_phase in ('started', 'Pending', 'Running', 'Failed'):
                self.info(f'item {curitem} status for '
                          f'{curpod}: {recorded_phase}')
                raise ProcessingComplete(message=f'item {curitem} %s' %
                                         recorded_phase.lower())

            if recorded_phase == 'Succeeded':
                self.info(f'item {curitem} podphase={recorded_phase} but '
                          f'not yet acknowledged: {curpod}')
                raise ProcessingComplete(
                    message=f'item {curitem} succeeded, '
                    'awaiting acknowledgement')

            raise ProcessingComplete(
                error=f'item {curitem} unexpected state: '
                      f'recorded_phase={recorded_phase}, '
                      f'status={str(self.kwargs["status"])}',
                message=f'item {curitem} unexpected state')

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
