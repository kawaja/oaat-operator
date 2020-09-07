import logging
import kopf
import oaatoperator
from oaatoperator.utility import now_iso, my_name
from oaatoperator.common import ProcessingComplete
from oaatoperator.oaatgroup import OaatGroupOverseer
from oaatoperator.pod import PodOverseer

# TODO: investigate whether pykube will re-connect to k8s if the session drops
# for some reason
# TODO: implement blackout windows for item job start
# TODO: add 'EachOnce' feature which ensures each item runs once
# successfully, then the OaatGroup object self-destructs


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
    kopf.info(f'Oaat Operator Version: {oaatoperator.__version__}',
              reason='Startup')
    kopf.info(f'Oaat Operator Build Date: {oaatoperator.__build_date__}',
              reason='Startup')
    kopf.info(f'Oaat Operator Git SHA: {oaatoperator.__gitsha__}',
              reason='Startup')


@kopf.timer('kawaja.net', 'v1', 'oaatgroups',
            initial_delay=30, interval=30,
            annotations={'kawaja.net/operator-status': 'active'})
def oaat_timer(**kwargs):
    """
    oaat_timer (oaatgroup)

    Main loop to handle oaatgroup object.
    """
    overseer = OaatGroupOverseer(**kwargs)
    curloop = overseer.get_status('loops', 0)

    try:
        overseer.validate_items()
        overseer.validate_state()

        # Check the currently-running job
        overseer.validate_running_pod()

        # No item running, so check to see if we're ready to start another
        item_name = overseer.find_job_to_run()

        # Found an oaatgroup job to run, now run it
        overseer.info(f'running item {item_name}')
        overseer.set_status('state', 'running')
        overseer.items.set_phase(item_name, 'started')
        overseer.set_status('currently_running', item_name)
        podobj = overseer.run_item(item_name)
        overseer.set_status('pod', podobj.metadata['name'])

        overseer.set_status('last_run', now_iso())
        overseer.set_status('children', [podobj.metadata['uid']])
        raise ProcessingComplete(message=f'started item {item_name}')

    except ProcessingComplete as exc:
        overseer.set_status('loops', curloop + 1)
        return overseer.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


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
    """
    overseer = PodOverseer(**kwargs)
    overseer.info(f'[{my_name()}] {overseer.name}')
    try:
        overseer.update_phase()
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


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

    Record last_success for failed pod.
    """
    overseer = PodOverseer(**kwargs)
    try:
        overseer.update_success_status()
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


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

    Record last_failure for failed pod.
    """
    overseer = PodOverseer(**kwargs)
    overseer.info(f'[{my_name()}] {overseer.name}')
    try:
        overseer.update_failure_status()
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

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
    overseer = PodOverseer(**kwargs)
    overseer.info(f'[{my_name()}] {overseer.name}')
    try:
        overseer.delete()
        raise ProcessingComplete(message=f'[{my_name()}] deleted')
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.on.resume('kawaja.net', 'v1', 'oaatgroups')
@kopf.on.update('kawaja.net', 'v1', 'oaatgroups')
@kopf.on.create('kawaja.net', 'v1', 'oaatgroups')
def oaat_action(**kwargs):
    """
    oaat_action (oaatgroup)

    Handle create/update/resume events for OaatGroup object:
        * validate oaatType
        * ensure "items" exist
        * annotate self with "operator-status=active" to enable timer
    """
    overseer = OaatGroupOverseer(**kwargs)
    overseer.info(f'[{my_name()}] {overseer.name}')

    try:
        overseer.validate_oaat_type()
        overseer.validate_items(
            status_annotation='operator-status',
            count_annotation='oaatgroup-items')
        raise ProcessingComplete(message='validated')
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

    return {'message': f'[{my_name()}] should never happen'}


@kopf.on.login()
def login(**kwargs):
    """Kopf login."""
    return kopf.login_via_client(**kwargs)
