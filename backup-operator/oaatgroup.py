"""
oaatgroup.py

Overseer object for managing OaatGroup objects.
"""
from random import randrange
import kopf
import pykube
from pykube import Pod
from utility import parse_frequency, date_from_isostr, now_iso
import utility
from common import ProcessingComplete, OaatType, OaatGroup
import overseer


# TODO: should these his be moved to a separate OaatItem class?
def get_status(obj, oaat_item, key, default=None):
    """
    get_status

    Get the status of an item.

    Intended to be called from handlers other than those for OaatGroup objects.
    """
    return (obj
            .get('status', {})
            .get('items', {})
            .get(oaat_item, {})
            .get(key, default))


def mark_failed(obj, item_name):
    failure_count = obj.item_status_date(item_name, 'failure_count')
    obj.set_item_status(item_name, 'failure_count', failure_count + 1)
    obj.set_item_status(item_name, 'last_failure', now_iso())


def mark_success(obj, item_name):
    obj.set_item_status(item_name, 'failure_count', 0)
    obj.set_item_status(item_name, 'last_success', now_iso())


class OaatGroupOverseer(overseer.Overseer):
    """
    OaatGroupOverseer

    Manager for OaatGroup objects.

    Initialise with the kwargs for a OaatGroup kopf handler.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        freqstr = kwargs['spec'].get('frequency', '1h')
        self.freq = parse_frequency(freqstr)
        self.my_pykube_objtype = OaatGroup
        self.oaattype = None
        self.body = kwargs['body']

    def item_status(self, item, key, default=None):
        """Get the status of a specific item."""
        return (self.get_status('items', {})
                .get(item, {})
                .get(key, default))

    def item_status_date(self, item, key, default=None):
        """Get the status of a specific item, returned as a datetime."""
        return date_from_isostr(self.item_status(item, key, default))

    def set_item_status(self, item, key, value=None):
        """Set the status of a specific item."""
        patch = (self.kwargs['patch']['status']
                 .setdefault('items', {})
                 .setdefault(item, {}))
        patch[item][key] = value

    def set_item_phase(self, item, value):
        """Set the phase of a specific item."""
        patch = (self.kwargs['patch']['status']
                 .setdefault('items', {})
                 .setdefault(item, {}))
        patch['podphase'] = value

    def get_oaattype(self):
        """Retrieve the OaatType object relevant to this OaatGroup."""
        if not self.oaattype:
            oaat_type = self.kwargs['spec'].get('oaatType')
            if oaat_type is None:
                raise ProcessingComplete(
                    message='error in OaatGroup definition',
                    error=f'missing oaatType in '
                          f'"{self.name}" OaatGroup definition')
            try:
                self.oaattype = (
                    OaatType
                    .objects(self.api, namespace=self.namespace)
                    .get_by_name(oaat_type)
                    .obj)
            except pykube.exceptions.ObjectDoesNotExist as exc:
                raise ProcessingComplete(
                    error=(
                        f'cannot find OaatType {self.namespace}/{oaat_type} '
                        f'to retrieve podspec: {exc}'),
                    message=f'error retrieving "{oaat_type}" OaatType object')
        return self.oaattype

    def get_podspec(self):
        """Retrieve Pod specification from relevant OaatType object."""
        msg = 'error in OaatType definition'
        btobj = self.get_oaattype()
        spec = btobj.get('spec')
        if spec is None:
            raise ProcessingComplete(
                message=msg,
                error='missing spec in OaatType definition')
        if spec.get('type') not in 'pod':
            raise ProcessingComplete(message=msg,
                                     error='spec.type must be "pod"')
        podspec = spec.get('podspec')
        if not podspec:
            raise ProcessingComplete(message=msg,
                                     error='spec.podspec is missing')
        if not podspec.get('container'):
            raise ProcessingComplete(
                message=msg,
                error='spec.podspec.container is missing')
        if podspec.get('containers'):
            raise ProcessingComplete(
                message=msg,
                error='currently only support a single container, '
                'please do not use "spec.podspec.containers"')
        if podspec.get('restartPolicy'):
            raise ProcessingComplete(
                message=msg,
                error='for spec.type="pod", you cannot specify '
                'a restartPolicy')
        return spec.get('podspec')

    # TODO: if the oldest item keeps failing, consider running
    # other items which are ready to run
    def find_job_to_run(self):
        """
        find_job_to_run

        Find the best item job to run based on last success and
        failure times.
        """
        now = utility.now()
        oaat_items = [
            {
                'name': item,
                'success': self.item_status_date(item, 'last_success'),
                'failure': self.item_status_date(item, 'last_failure'),
                'numfails': self.item_status_date(item, 'failure_count')
            }
            for item in self.kwargs['spec'].get('oaatItems', [])
        ]

        self.debug('oaat_items:\n' +
                   '\n'.join([str(i) for i in oaat_items]))

        if not oaat_items:
            raise ProcessingComplete(
                message='error in OaatGroup definition',
                error='no items found. please set "oaatItems"')

        # Filter out items which have been recently successful
        valid_based_on_success = [
            item for item in oaat_items if now > item['success'] + self.freq
        ]

        self.debug('valid_based_on_success:\n' +
                   '\n'.join([str(i) for i in valid_based_on_success]))

        if not valid_based_on_success:
            self.set_status('state', 'idle')
            raise ProcessingComplete(
                message='not time to run next item')

        if len(valid_based_on_success) == 1:
            return valid_based_on_success[0]['name']

        # Get all items which are "oldest"
        oldest_success_time = min(
            [t['success'] for t in valid_based_on_success])
        self.debug(f'oldest_success_time: {oldest_success_time}')
        oldest_items = [
            item
            for item in valid_based_on_success
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

    def run_item(self, item_name):
        """
        run_item

        Execute an item job Pod with the spec details from the appropriate
        OaatType object.
        """
        spec = self.get_podspec()
        contspec = spec['container']
        del spec['container']
        contspec.setdefault('env', []).append({
            'name': 'OAAT_ITEM',
            'value': item_name
        })

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
            mark_failed(self.body, item_name)
            raise ProcessingComplete(
                error=f'could not create pod {doc}: {exc}',
                message=f'error creating pod for {item_name}')
        return pod

    def validate_items(self, status_annotation=None, count_annotation=None):
        """
        validate_items

        Ensure there are oaatItems to process.
        """
        oaat_items = self.kwargs['spec'].get('oaatItems')
        if not oaat_items:
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
            self.set_annotation(count_annotation, value=len(oaat_items))

        return oaat_items

    def validate_state(self):
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

    def validate_running_pod(self):
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
                mark_failed(self.body, curitem)
                self.set_item_status(curitem, 'pod_detail')
                raise ProcessingComplete(
                    info='Cleaned up missing/deleted item')

            podphase = pod.get('status', {}).get('phase', 'unknown')
            self.info(f'validated that pod {curpod} is '
                      f'still running (phase={podphase})')

            recorded_phase = self.item_status(curitem, 'podphase', 'unknown')

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

    def check_oaat_type(self):
        """
        check_oaat_type

        Ensure the group refers to an appropriate OaatType object.
        """
        oaattypes = OaatType.objects(self.api)
        oaat_type = self.kwargs['spec'].get('oaatType')
        if oaat_type not in [x.name for x in oaattypes]:
            self.set_annotation('operator-status', 'missingOaatType')
            raise ProcessingComplete(
                message='error in OaatGroup definition',
                error=f'unknown oaat type {oaat_type}')
        kopf.info(self.kwargs['spec'],
                  reason='Validation',
                  message='found valid oaat type')
