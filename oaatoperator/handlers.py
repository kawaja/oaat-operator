import sys
import logging
from typing_extensions import Unpack
import kopf

import oaatoperator
from oaatoperator.oaatitem import OaatItem
from oaatoperator.py_types import CallbackArgs
from oaatoperator.utility import now_iso, my_name
from oaatoperator.common import ProcessingComplete
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
def configure(settings: kopf.OperatorSettings, **_) -> None:
    """Set kopf configuration."""
    settings.posting.level = logging.INFO
    settings.persistence.finalizer = 'oaatoperator.kawaja.net/kopf-finalizer'
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix='oaatoperator.kawaja.net',
        key='last-handled-configuration')
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix='oaatoperator.kawaja.net')
    settings.watching.server_timeout = 600
    settings.watching.client_timeout = 660
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
            initial_delay=90, interval=60,
            annotations={'oaatoperator.kawaja.net/operator-status': 'active'})
def oaat_timer(**kwargs: Unpack[CallbackArgs]):
    """
    oaat_timer (oaatgroup)

    Main loop to handle oaatgroup object.
    """
    kwargs['logger'].debug(f'[{my_name()}] reason: timer (60sec)')
    memo = kwargs['memo']
    try:
        oaatgroup = OaatGroup(kopf_object=kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    curloop = memo.get('loops', 0)

    try:
        oaatgroup.validate_items()

        # Verify that an existing job is running (returns if not)
        oaatgroup.verify_running()

        if kwargs['annotations'].get('pause_new_jobs'):
            raise ProcessingComplete(
                message='paused via pause_new_jobs annotation')

        # No item running, so check to see if we're ready to start another
        next_item: OaatItem = oaatgroup.find_job_to_run()

        # Found an oaatgroup job to run, now run it
        oaatgroup.info(f'running item {next_item.name}')
        oaatgroup.set_item_status(next_item.name, 'podphase', 'started')
        memo.state = 'running'
        memo.currently_running = next_item.name

        podobj = next_item.run()
        memo.pod = podobj.metadata['name']

        memo.last_run = now_iso()
        memo.children = [podobj.metadata['uid']]

        raise ProcessingComplete(message=f'started item {next_item.name}')

    except ProcessingComplete as exc:
        memo.loops = curloop + 1
        oaatgroup.set_status('handler_status', memo)
        return oaatgroup.handle_processing_complete(exc)


@kopf.timer('pods',
            interval=0.5 * 3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'})
@kopf.on.resume('pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_running)
@kopf.on.field('pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'})
def pod_phasechange(**kwargs: Unpack[CallbackArgs]) -> None:
    """
    pod_phasechange (pod)

    Update parent (OaatGroup) phase information for this item.
    Triggered by change in the pod's "phase" status field, or every
    1/2 hour just in case
    """
    logger = kwargs['logger']
    logger.debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer (30min)")}')
    logger.debug(f'[{my_name()}] diff: {kwargs.get("diff")}')
    logger.debug(f'[{my_name()}] status: {kwargs.get("status")}')
    try:
        pod = PodOverseer(**kwargs)
    except ProcessingComplete as exc:
        logger.error(f'Error: {exc.ret.get("error")}')
        return
    pod.info(f'[{my_name()}] status for {pod.name} has changed')

    try:
        pod.update_phase()
    except ProcessingComplete as exc:
        pod.handle_processing_complete(exc)
        return

    logger.error(f'[{my_name()}] should never happen')
    return


@kopf.timer('', 'v1', 'pods',
            interval=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=is_succeeded)
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_succeeded)
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
               when=is_succeeded)
def pod_succeeded(**kwargs: Unpack[CallbackArgs]) -> None:
    """
    pod_succeeded (pod)

    Record last_success for successful pod. Triggered by change in the
    pod's "phase" status field, or every 1/2 hour just in case
    """
    logger = kwargs['logger']
    logger.debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer (30min)")}')
    logger.debug(f'[{my_name()}] diff: {kwargs.get("diff")}')
    logger.debug(f'[{my_name()}] status: {kwargs.get("status")}')
    try:
        pod = PodOverseer(**kwargs)
    except ProcessingComplete as exc:
        logger.error(f'Error: {exc.ret.get("error")}')
        return

    try:
        pod.update_success_status()
    except ProcessingComplete as exc:
        pod.handle_processing_complete(exc)
        return

    logger.error(f'[{my_name()}] should never happen')
    return


@kopf.timer('', 'v1', 'pods',
            interval=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=is_failed)
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_failed)
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
               when=is_failed)
def pod_failed(**kwargs: Unpack[CallbackArgs]) -> None:
    """
    pod_failed (pod)

    Record last_failure for failed pod. Triggered by change in the
    pod's "phase" status field, or every 1/2 hour just in case
    """
    logger = kwargs['logger']
    logger.debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer (30min)")}')
    try:
        pod = PodOverseer(**kwargs)
    except ProcessingComplete as exc:
        logger.error(f'Error: {exc.ret.get("error")}')
        return
    pod.info(f'[{my_name()}] {pod.name}')

    try:
        pod.update_failure_status()
    except ProcessingComplete as exc:
        pod.handle_processing_complete(exc)
        return

    logger.error(f'[{my_name()}] should never happen')
    return


@kopf.timer('', 'v1', 'pods',
            interval=12*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=kopf.any_([is_succeeded, is_failed]))
def cleanup_pod(**kwargs: Unpack[CallbackArgs]) -> None:
    """
    cleanup_pod (pod)

    After pod has been in 'Failed' or 'Succeeded' phase for more than twelve
    hours, delete it.
    """
    logger = kwargs['logger']
    logger.debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer (12hrs)")}')
    try:
        pod = PodOverseer(**kwargs)
    except ProcessingComplete as exc:
        logger.error(f'Error: {exc.ret.get("error")}')
        return
    pod.info(f'[{my_name()}] {pod.name}')

    try:
        pod.delete()
        raise ProcessingComplete(message=f'[{my_name()}] deleted')
    except ProcessingComplete as exc:
        pod.handle_processing_complete(exc)
        return


@kopf.on.resume('kawaja.net', 'v1', 'oaatgroups')
def oaat_resume(**kwargs: Unpack[CallbackArgs]):
    """
    oaat_resume (oaatgroup)

    Handle resume event for OaatGroup object:
        * determine current state of running items
        * update memo
    """
    memo = kwargs['memo']
    try:
        oaatgroup = OaatGroup(kopf_object=kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}

    running_pod_info = oaatgroup.resume_running_pod()
    if running_pod_info is not None:
        memo.state = 'running'
        memo.currently_running = running_pod_info.get('oaat-name', 'unknown')
        memo.pod = running_pod_info.get('name', 'unknown')

    oaatgroup.info(f'[{my_name()}] {oaatgroup.name}')
    oaatgroup.set_status('handler_status', memo)
    return {'message': f'Successfully resumed {oaatgroup.name}'}


@kopf.on.update('kawaja.net', 'v1', 'oaatgroups')
@kopf.on.create('kawaja.net', 'v1', 'oaatgroups')
@kopf.timer('kawaja.net', 'v1', 'oaatgroups',
            initial_delay=90,
            interval=300,
            annotations={'oaatoperator.kawaja.net/operator-status':
                         kopf.ABSENT})
def oaat_action(**kwargs: Unpack[CallbackArgs]):
    """
    oaat_action (oaatgroup)

    Handle create/update events for OaatGroup object:
        * validate oaatType
        * ensure "items" exist
        * annotate self with "operator-status=active" to enable timer
    """
    memo = kwargs['memo']
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer (5min)")}')
    try:
        oaatgroup = OaatGroup(kopf_object=kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}

    oaatgroup.info(f'[{my_name()}] {oaatgroup.name}')

    try:
        oaatgroup.validate_items(
            status_annotation='operator-status',
            count_annotation='oaatgroup-items')
        raise ProcessingComplete(message='validated')
    except ProcessingComplete as exc:
        oaatgroup.set_status('handler_status', memo)
        return oaatgroup.handle_processing_complete(exc)


@kopf.on.login()
def login(**kwargs: Unpack[CallbackArgs]):
    """Kopf login."""
    return kopf.login_via_pykube(**kwargs)
