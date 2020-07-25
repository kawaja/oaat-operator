import datetime
import logging
import kopf
import pykube
from pykube import Pod
from utility import now_iso, my_name
from common import ProcessingComplete
import backup
import pod

# TODO: Generalise from backup to "OneAtATime" ?
# TODO: delete old pods
# TODO: investigate whether pykube will re-connect to k8s if the session drops
# for some reason
# TODO: implement blackout windows for backup start
# TODO: cool-off for failed backups (don't restart a specfic backup unless
# the cool-off period has completed)
# TODO: add 'EachOnce' feature which ensures each backup runs once
# successfully, then the Backup object self-destructs


def is_running(status, **_):
    return status.get('phase') == 'Running'


def is_failed(status, **_):
    return status.get('phase') == 'Failed'


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """Set kopf configuration."""
    settings.posting.level = logging.INFO

@kopf.timer('kawaja.net', 'v1', 'backups',
            initial_delay=30, interval=30,
            annotations={'kawaja.net/operator-status': 'active'})
def backup_timer(**kwargs):
    """
    backup_timer (backup)

    Main loop to handle backup object.
    """
    overseer = backup.BackupOverseer(**kwargs)
    curloop = overseer.get_status('loops', 0)

    try:
        overseer.validate_items()
        overseer.validate_state()

        # Check the currently-running job
        overseer.validate_running_pod()

        # No backup running, so check to see if we're ready to start another
        item_name = overseer.find_job_to_run()

        # Found a backup job to run, now run it
        overseer.info(f'running backup {item_name}')
        overseer.set_status('state', 'running')
        overseer.set_item_phase(item_name, 'started')
        overseer.set_status('currently_running', item_name)
        podobj = overseer.run_backup(item_name)
        overseer.set_status('backup_pod', podobj.metadata['name'])

        overseer.set_status('last_run', now_iso())
        overseer.set_status('children', [podobj.metadata['uid']])
        raise ProcessingComplete(message=f'started backup {item_name}')

    except ProcessingComplete as exc:
        overseer.set_status('loops', curloop + 1)
        return overseer.handle_processing_complete(exc)

    return {'message': '[{my_name()}] should never happen'}


# TODO: decompose into separate handlers, based on pod phase
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'backup-operator'})
@kopf.on.create('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'backup-operator'})
def pod_event(**kwargs):
    """
    pod_event (pod)

    Handle events from child PODs:
        * set 'podphase' in parent (Backup) object as pod changes phase
        * set 'last_success' in parent (Backup) object when pod
          successfully completes
        * set 'last_failure' in parent (Backup) object when pod fails.
    """
    overseer = pod.PodOverseer(**kwargs)

    try:
        # Get parent (backup object)
        parent = overseer.get_parent()

        backup_name = overseer.get_label('backup-name', 'unknown')

        recorded_phase = backup.get_status(parent.obj, backup_name, 'podphase')

        # valid phases are Pending, Running, Succeeded, Failed, Unknown
        if overseer.phase not in ('Running', 'Pending'):
            overseer.update_status(parent, overseer.phase, backup_name)
        else:
            overseer.debug(f'pod {overseer.name}, podphase: {overseer.phase}')
            parent.patch(
                {'status': {
                    'backups': {backup_name: {'podphase': overseer.phase}}
                }})
            raise ProcessingComplete(
                message=f'recorded phase "{overseer.phase}" for {backup_name}')

        if recorded_phase == 'Succeeded':
            raise ProcessingComplete(
                message=f'success of {backup_name} previously recorded')

        raise ProcessingComplete(message=f'completed processing {backup_name}')
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

    return {'message': '[{my_name()}] should never happen'}


@kopf.on.field('', 'v1', 'pods',
               when=kopf.any_([is_running, is_failed, is_succeeded]))
def any_pod_status_change(**kwargs):
    overseer = pod.PodOverseer(**kwargs)
    overseer.info(f'[{my_name()}]: '
                  f'name={kwargs.get("name")}, '
                  f'phase={kwargs.get("status").get("phase")}')


@kopf.timer('kawaja.net', 'v1', 'pods',
            initial_delay=600,
            idle=3600,
            when=kopf.any_([is_running, is_failed]))
def cleanup_pod(**kwargs):
    """
    cleanup_pod (pod)

    After pod has been in 'Failed' or 'Succeeded' phase for more than an
    hour, delete it.
    """
    overseer = pod.PodOverseer(**kwargs)
    try:
        overseer.delete()
        raise ProcessingComplete(message='[{my_name()}] deleted')
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

    return {'message': '[{my_name()}] should never happen'}


@kopf.on.resume('kawaja.net', 'v1', 'backups')
@kopf.on.update('kawaja.net', 'v1', 'backups')
@kopf.on.create('kawaja.net', 'v1', 'backups')
def backups_action(**kwargs):
    """
    backups_action (backups)

    Handle create/update/resume events for Backup object:
        * validate backupType
        * ensure backupItems exist
        * annotate self with "operator-status=active" to enable timer
    """
    overseer = backup.BackupOverseer(**kwargs)

    overseer.info(f'running [{my_name()}] for {kwargs.get("name")}')
    try:
        overseer.check_backup_type()
        overseer.validate_items(
            status_annotation='operator-status',
            count_annotation='backup-items')
        raise ProcessingComplete(message='validated')
    except ProcessingComplete as exc:
        return overseer.handle_processing_complete(exc)

    return {'message': '[{my_name()}] should never happen'}


@kopf.on.login()
def login(**kwargs):
    """Kopf login."""
    return kopf.login_via_client(**kwargs)
