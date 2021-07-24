import logging
import sys
import kopf
import oaatoperator
from oaatoperator.utility import now_iso, my_name
from oaatoperator.common import ProcessingComplete, KubeOaatGroup
from oaatoperator.oaatgroup import OaatGroup
from oaatoperator.pod import PodOverseer

# TODO: investigate whether pykube will re-connect to k8s if the session drops
# for some reason


def is_running(status, **_):
    """For when= function to test if a pod is running."""
    return status.get('phase') == 'Running'


def is_failed(status, **_):
    """For when= function to test if a pod has failed."""
    return status.get('phase') == 'Failed'


def is_succeeded(status, **_):
    """For when= function to test if a pod has succeeded."""
    return status.get('phase') == 'Succeeded'


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """Set kopf configuration."""
    settings.posting.level = logging.INFO
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix='kawaja.net')
    print('Oaat Operator Version: ' +
          getattr(oaatoperator, '__version__', '<not set>'),
          file=sys.stderr)
    print('Oaat Operator Build Date: ' +
          getattr(oaatoperator, '__build_date__', '<not set>'),
          file=sys.stderr)
    print('Oaat Operator Git SHA: ' +
          getattr(oaatoperator, '__gitsha__', '<not set>'),
          file=sys.stderr)


@kopf.timer('kawaja.net', 'v1', 'oaatgroups',
            initial_delay=30, interval=30,
            annotations={'kawaja.net/operator-status': 'active'})
def oaat_timer(**kwargs):
    """
    oaat_timer (oaatgroup)

    Main loop to handle oaatgroup object.
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        oaatgroup = OaatGroup(**kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    curloop = oaatgroup.get_status('loops', 0)

    try:
        oaatgroup.validate_items()
        oaatgroup.validate_state()

        oaatgroup.validate_no_rogue_pods_are_running()

        # Check the currently-running job
        if oaatgroup.is_pod_expected():
            oaatgroup.validate_expected_pod_is_running()
            return {
                'message': 'validate_expected_pod_is_running'
                'unexpectedly returned (should never happen)'
            }

        # No item running, so check to see if we're ready to start another
        item_name = oaatgroup.find_job_to_run()

        # Found an oaatgroup job to run, now run it
        oaatgroup.info(f'running item {item_name}')
        oaatgroup.set_status('state', 'running')
        oaatgroup.set_item_status(item_name, 'podphase', 'started')
        oaatgroup.set_status('currently_running', item_name)
        podobj = oaatgroup.run_item(item_name)
        oaatgroup.set_status('pod', podobj.metadata['name'])

        oaatgroup.set_status('last_run', now_iso())
        oaatgroup.set_status('children', [podobj.metadata['uid']])
        raise ProcessingComplete(message=f'started item {item_name}')

    except ProcessingComplete as exc:
        oaatgroup.set_status('loops', curloop + 1)
        return oaatgroup.handle_processing_complete(exc)


@kopf.timer('', 'v1', 'pods',
            idle=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'})
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_running)
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'})
def pod_phasechange(**kwargs):
    """
    pod_phasechange (pod)

    Update parent (OaatGroup) phase information for this item.
    Triggered by change in the pod's "phase" status field, or every
    1/2 hour just in case
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(KubeOaatGroup, **kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    pod.info(f'[{my_name()}] {pod.name}')

    try:
        pod.update_phase()
    except ProcessingComplete as exc:
        return pod.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.timer('', 'v1', 'pods',
            idle=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=is_succeeded)
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_succeeded)
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
               when=is_succeeded)
def pod_succeeded(**kwargs):
    """
    pod_succeeded (pod)

    Record last_success for failed pod. Triggered by change in the
    pod's "phase" status field, or every 1/2 hour just in case
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(KubeOaatGroup, **kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}

    try:
        pod.update_success_status()
    except ProcessingComplete as exc:
        return pod.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.timer('', 'v1', 'pods',
            idle=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=is_failed)
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_failed)
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
               when=is_failed)
def pod_failed(**kwargs):
    """
    pod_failed (pod)

    Record last_failure for failed pod. Triggered by change in the
    pod's "phase" status field, or every 1/2 hour just in case
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(KubeOaatGroup, **kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    pod.info(f'[{my_name()}] {pod.name}')

    try:
        pod.update_failure_status()
    except ProcessingComplete as exc:
        return pod.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.timer('', 'v1', 'pods',
            idle=12*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=kopf.any_([is_succeeded, is_failed]))
def cleanup_pod(**kwargs):
    """
    cleanup_pod (pod)

    After pod has been in 'Failed' or 'Succeeded' phase for more than twelve
    hours, delete it.
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(KubeOaatGroup, **kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    pod.info(f'[{my_name()}] {pod.name}')

    try:
        pod.delete()
        raise ProcessingComplete(message=f'[{my_name()}] deleted')
    except ProcessingComplete as exc:
        return pod.handle_processing_complete(exc)


@kopf.on.resume('kawaja.net', 'v1', 'oaatgroups')
@kopf.on.update('kawaja.net', 'v1', 'oaatgroups')
@kopf.on.create('kawaja.net', 'v1', 'oaatgroups')
@kopf.timer('kawaja.net', 'v1', 'oaatgroups',
            initial_delay=30, interval=30,
            annotations={'kawaja.net/operator-status': kopf.ABSENT})
def oaat_action(**kwargs):
    """
    oaat_action (oaatgroup)

    Handle create/update/resume events for OaatGroup object:
        * validate oaatType
        * ensure "items" exist
        * annotate self with "operator-status=active" to enable timer
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        oaatgroup = OaatGroup(**kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}

    oaatgroup.info(f'[{my_name()}] {oaatgroup.name}')

    try:
        oaatgroup.validate_oaat_type()
        oaatgroup.validate_items(
            status_annotation='operator-status',
            count_annotation='oaatgroup-items')
        raise ProcessingComplete(message='validated')
    except ProcessingComplete as exc:
        return oaatgroup.handle_processing_complete(exc)


@kopf.on.login()
def login(**kwargs):
    """Kopf login."""
    return kopf.login_via_pykube(**kwargs)
