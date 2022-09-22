import sys
import logging
from typing_extensions import Unpack
import kopf

import oaatoperator
from oaatoperator.types import CallbackArgs
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


@kopf.on.startup()  # type: ignore
def configure(settings: kopf.OperatorSettings, **_) -> None:
    """Set kopf configuration."""
    settings.posting.level = logging.INFO
    settings.persistence.finalizer = 'oaatoperator.kawaja.net/kopf-finalizer'
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix='oaatoperator.kawaja.net',
        key='last-handled-configuration')
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix='oaatoperator.kawaja.net')
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
            initial_delay=90, interval=300,
            annotations={'kawaja.net/operator-status': 'active'})  # type: ignore
def oaat_timer(**kwargs: Unpack[CallbackArgs]):
    """
    oaat_timer (oaatgroup)

    Main loop to handle oaatgroup object.
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        oaatgroup = OaatGroup(kopf_object=kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    curloop = oaatgroup.get_status('loops', 0)

    try:
        oaatgroup.validate_items()

        # Verify that an existing job is running (returns if not)
        oaatgroup.verify_running()

        # No item running, so check to see if we're ready to start another
        next_item = oaatgroup.find_job_to_run()

        # Found an oaatgroup job to run, now run it
        oaatgroup.info(f'running item {next_item.name}')
        oaatgroup.set_status('state', 'running')
        oaatgroup.set_item_status(next_item.name, 'podphase', 'started')
        oaatgroup.set_status('currently_running', next_item.name)

        if kwargs['annotations'].get('pause_new_jobs'):
            raise ProcessingComplete(
                message='paused via pause_new_jobs annotation')

        podobj = next_item.run()
        oaatgroup.set_status('pod', podobj.metadata['name'])

        oaatgroup.set_status('last_run', now_iso())
        oaatgroup.set_status('children', [podobj.metadata['uid']])
        raise ProcessingComplete(message=f'started item {next_item.name}')

    except ProcessingComplete as exc:
        oaatgroup.set_status('loops', curloop + 1)
        return oaatgroup.handle_processing_complete(exc)


@kopf.timer('', 'v1', 'pods',
            interval=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'})  # type: ignore
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_running)  # type: ignore
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'})  # type: ignore
def pod_phasechange(**kwargs: Unpack[CallbackArgs]):
    """
    pod_phasechange (pod)

    Update parent (OaatGroup) phase information for this item.
    Triggered by change in the pod's "phase" status field, or every
    1/2 hour just in case
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(**kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    pod.info(f'[{my_name()}] {pod.name}')
    pod.debug(f'[{my_name()}] {kwargs}')

    try:
        pod.update_phase()
    except ProcessingComplete as exc:
        return pod.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.timer('', 'v1', 'pods',
            interval=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=is_succeeded)  # type: ignore
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_succeeded)  # type: ignore
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
               when=is_succeeded)  # type: ignore
def pod_succeeded(**kwargs: Unpack[CallbackArgs]):
    """
    pod_succeeded (pod)

    Record last_success for failed pod. Triggered by change in the
    pod's "phase" status field, or every 1/2 hour just in case
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(**kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}

    try:
        pod.update_success_status()
    except ProcessingComplete as exc:
        return pod.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.timer('', 'v1', 'pods',
            interval=0.5*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=is_failed)  # type: ignore
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
                when=is_failed)  # type: ignore
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
               when=is_failed)  # type: ignore
def pod_failed(**kwargs: Unpack[CallbackArgs]):
    """
    pod_failed (pod)

    Record last_failure for failed pod. Triggered by change in the
    pod's "phase" status field, or every 1/2 hour just in case
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(**kwargs)
    except ProcessingComplete as exc:
        return {'message': f'Error: {exc.ret.get("error")}'}
    pod.info(f'[{my_name()}] {pod.name}')

    try:
        pod.update_failure_status()
    except ProcessingComplete as exc:
        return pod.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.timer('', 'v1', 'pods',
            interval=12*3600,
            labels={'parent-name': kopf.PRESENT, 'app': 'oaat-operator'},
            when=kopf.any_([is_succeeded, is_failed]))  # type: ignore
def cleanup_pod(**kwargs: Unpack[CallbackArgs]):
    """
    cleanup_pod (pod)

    After pod has been in 'Failed' or 'Succeeded' phase for more than twelve
    hours, delete it.
    """
    kwargs['logger'].debug(
        f'[{my_name()}] reason: {kwargs.get("reason", "timer?")}')
    try:
        pod = PodOverseer(**kwargs)
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
@kopf.on.create('kawaja.net', 'v1', 'oaatgroups')  # type: ignore
@kopf.timer('kawaja.net', 'v1', 'oaatgroups',
            initial_delay=90, interval=300,
            annotations={'kawaja.net/operator-status': kopf.ABSENT})  # type: ignore
def oaat_action(**kwargs: Unpack[CallbackArgs]):
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
        oaatgroup = OaatGroup(kopf_object=kwargs)
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


@kopf.on.login()  # type: ignore
def login(**kwargs: CallbackArgs):
    """Kopf login."""
    return kopf.login_via_pykube(**kwargs)  # type: ignore
