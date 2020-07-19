from random import randrange
import datetime
import time
import logging
import kopf
import pykube
from pykube import Pod
import utility

#def trace_calls(frame, event, arg):
#    if event not in ('call', 'line'):
#        return
#    co = frame.f_code
#    func_name = co.co_name
#    if func_name == 'write':
#        # Ignore write() calls from print statements
#        return
#    func_line_no = frame.f_lineno
#    func_filename = co.co_filename
#    func_path = func_filename[:func_filename.rfind('/')]
#    if 'handler.py' not in func_path:
#        return
#    caller = frame.f_back
#    caller_line_no = caller.f_lineno
#    caller_filename = caller.f_code.co_filename
#    caller_path = caller_filename[:caller_filename.rfind('/')]
#    if 'handler.py' not in caller_path:
#        return
#    if event == 'call':
#        print('Call to %s on line %s of %s from line %s of %s' %
#            (func_name, func_line_no, func_filename, caller_line_no,
#            caller_filename))
#    else:
#        print(f'{func_filename}:{func_line_no}:{func_name}')
#    return

# TODO: delete old pods
# TODO: investigate whether pykube will re-connect to k8s if the session drops
# for some reason
utc = datetime.timezone.utc
pause = {}
api = pykube.HTTPClient(pykube.KubeConfig.from_env())

@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    settings.posting.level = logging.INFO


class Backup(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'backups'
    kind = 'Backup'


class BackupType(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'backuptypes'
    kind = 'BackupType'


class ProcessingComplete(BaseException):
    """Signal from a subfunction to a handler that processing is complete."""
    def __init__(self, **kwargs):
        self.ret = {}
        for arg in kwargs:
            self.ret[arg] = kwargs[arg]


def _set_backup(patch, state, value):
    patch['status'][state] = value


def _set_backup_phase(patch, name, value):
    patch['status'] .setdefault('backups', {}) .setdefault(name, {})
    patch['phase'] = value


def _get_status(obj, backup, key, default=None):
    return (obj
            .get('status', {})
            .get('backups', {})
            .get(backup, {})
            .get(key, default))


def _set_backup_job_state(patch, item_name, key, value):
    patch['status'].setdefault('backups', {}).setdefault(item_name, {})
    patch['status']['backups'][item_name][key] = value


def _find_job_to_run(body, spec, patch, logger, **_):
    """
    _find_job_to_run

    Find the time and name of the backup job which has been least recently
    successful.

    Expects Backup object.
    """
    backup_items = spec.get('backupItems')
    if backup_items is None:
        return {
            'message':
            f'no backups found. please set "backupItems"'
        }

    # find entry with the least recent last_success
    # dates are always UTC
    # need to take care that dates are all 'aware' of timezone so
    # date arithmetic works
    oldest = 0
    oldest_item = None
    for backup_item in backup_items:
        successstr = _get_status(body, backup_item, 'last_success')
        if isinstance(successstr, str):
            last_success = (
                datetime.datetime.fromisoformat(successstr)
                .replace(tzinfo=utc))
        else:
            last_success = datetime.datetime.fromtimestamp(0, tz=utc)
        logger.debug(
            f'backup_item: {backup_item}, '
            f'oldest: {oldest}, '
            f'last_success: {last_success}')
        if not oldest or last_success < oldest:
            oldest = last_success
            oldest_item = backup_item
        logger.info(
            f'Checking backup {backup_item}, last_success={last_success}, '
            f'oldest_item={oldest_item}, oldest={oldest}')

    freqstr = spec.get('frequency', '1h')
    freq = utility.parse_frequency(freqstr)

    # if none have been successful, choose randomly
    # TODO: track the unsuccessful times and chose the job least recently
    # unsuccesful if none have been successful.
    if oldest_item is None:
        item_name = backup_items[randrange(len(backup_items))]
    else:
        item_name = oldest_item

    if oldest:
        try:
            if oldest + freq > datetime.datetime.now(tz=utc):
                _set_backup(patch, 'state', 'idle')
                logger.info(
                    f'Not yet time to run another backup '
                    f'(oldest: {item_name}={oldest.isoformat()}, '
                    f'freq: {freq} / {freq.total_seconds()}, '
                    f'now: {datetime.datetime.now(tz=utc).isoformat()} /'
                    f'{datetime.datetime.now(tz=utc).timestamp()}, '
                    f'next: {(oldest+freq).isoformat()} / '
                    f'{(oldest+freq).timestamp()})')
                raise ProcessingComplete(
                    message=
                    f'next backup "{item_name}" {(oldest+freq).isoformat()}')
        except (TypeError, ValueError) as exc:
            logger.error(f'Error calculating times: {exc}')
            logger.info(
                f'Continuing with backup for {item_name} after error')
            return item_name

    return item_name


def _get_backup_podspec(meta, spec):
    backup_type = spec.get('backupType')
    if backup_type is None:
        raise ProcessingComplete(
            message=f'missing backupType in "{meta["name"]}" Backup definition')
    try:
        btobj = BackupType.objects(
            api, namespace=meta["namespace"]).get_by_name(backup_type).obj
    except pykube.exceptions.ObjectDoesNotExist as exc:
        raise ProcessingComplete(
            error=(
                f'cannot find BackupType {meta["namespace"]}/{backup_type} '
                f'to retrieve podspec: {exc}'),
            message=f'cannot retrieve "{backup_type}" BackupType object')
    podspec = btobj.get('spec', {}).get('podspec')
    if podspec is None:
        raise ProcessingComplete(
            message=
            f'missing podspec in "{backup_type}" BackupType definition')
    return podspec


def _run_backup(item_name, meta, spec, **_):
    """
    _run_backup

    Execute a backup Pod with the spec details from the appropriate BackupType
    object.

    Expects Backup object.
    """
    podspec = _get_backup_podspec(meta, spec)
    podspec.setdefault('env', []).append({
        'name': 'BACKUP_ITEM',
        'value': item_name
    })

    # TODO: currently only supports a single container. Do we want
    # multi-container?
    doc = {
        'apiVersion': 'v1',
        'kind': 'Pod',
        'metadata': {
            'generateName': meta['name'] + '-' + item_name + '-',
            'labels': {
                'parent-name': meta['name'],
                'backup-name': item_name,
                'app': 'backup-operator'
            }
        },
        'spec': {
            'containers': [podspec],
            'restartPolicy': 'Never'
        },
    }

    kopf.adopt(doc)
    pod = Pod(api, doc)

    try:
        pod.create()
    except pykube.KubernetesError as exc:
        raise ProcessingComplete(
            info=f'failed creating pod: {podspec}',
            error=f'could not create pod: {exc}',
            message=f'error creating pod for {item_name}')
    return pod


def _set_backup_annotation(name,
                           annotation,
                           value,
                           logger,
                           namespace=pykube.all):
    print(f'=> _set_backup_annotation: A')
    try:
        print(f'=> _set_backup_annotation: B')
        myobj = (Backup.objects(api, namespace=namespace).get_by_name(name))
        print(f'=> _set_backup_annotation: C')
    except pykube.exceptions.ObjectDoesNotExist as exc:
        print(f'=> _set_backup_annotation: exc1 A')
        logger.error(f'cannot find Backup {name} to update annotation: {exc}')
        raise ProcessingComplete(
            message=f'cannot retrieve "{name}" Backup object')
    print(f'=> _set_backup_annotation: D')
    myobj.annotations[f'kawaja.net/{annotation}'] = str(value)
    attempts = 3
    print(f'=> _set_backup_annotation: E')
    while attempts > 0:
        try:
            print(f'=> _set_backup_annotation: F')
            myobj.update()
            break
            print(f'=> _set_backup_annotation: G')
        except pykube.exceptions.KubernetesError as exc:
            print(f'=> _set_backup_annotation: exc2 A')
            if (isinstance(exc, pykube.exceptions.HTTPError)
                    and exc.args[0] == 429):
                time.sleep(10)
            attempts -= 1
            logger.debug(f'error: {type(exc)}, args: {str(exc.args)}')
            logger.warning(f'failed to set backup annotation '
                           f'(attempts remaining {attempts}): {exc}')
    print(f'=> _set_backup_annotation: H')
    logger.debug(f'added annotation {annotation}={value} to {name}')


def _check_backup_type(spec, meta, logger, namespace, **_):
    """
    _check_backup_type

    Ensure the backup refers to an appropriate BackupType object.

    Expects Backup object.
    """
    backuptypes = BackupType.objects(api)
    backup_type = spec.get('backupType')
    if backup_type not in [x.name for x in backuptypes]:
        _set_backup_annotation(name=meta['name'],
                               logger=logger,
                               namespace=namespace,
                               annotation='operator-status',
                               value='missingBackupType')
        raise ProcessingComplete(message=f'unknown backup type {backup_type}')
    kopf.info(spec, reason='Validation', message='found valid backup type')


def _remove_backup_annotation(name, annotation, logger, namespace=pykube.all):
    try:
        myobj = (Backup.objects(api, namespace=namespace).get_by_name(name))
    except pykube.exceptions.ObjectDoesNotExist as exc:
        logger.error(f'cannot find Backup {name} to remove annotation: {exc}')
        raise ProcessingComplete(
            message=f'cannot retrieve Backup object {name}')
    myobj.annotations.pop(f'kawaja.net/{annotation}', None)


def _check_backup_items(spec, name, namespace, meta, logger, **_):
    """
    _check_backup_items

    Ensure there are backupItems to process.

    Expects Backup object.
    """
    print(f'=> _check_backup_items: A')
    backup_items = spec.get('backupItems')
    print(f'=> _check_backup_items: B')
    if not backup_items:
        print(f'=> _check_backup_items: C')
        _set_backup_annotation(name=meta['name'],
                               logger=logger,
                               namespace=namespace,
                               annotation='operator-status',
                               value='missingBackupItems')
        print(f'=> _check_backup_items: D')
        raise ProcessingComplete(
            state='nothing to do',
            message=f'no backups found. Please set "backupItems" in {name}'
        )

    # we have backupItems, so mark the backup object as "active" (via
    # annotation)
    print(f'=> _check_backup_items: E')
    _set_backup_annotation(name=meta['name'],
                           logger=logger,
                           namespace=namespace,
                           annotation='operator-status',
                           value='active')

    print(f'=> _check_backup_items: F')
    _set_backup_annotation(name=meta['name'],
                           logger=logger,
                           namespace=namespace,
                           annotation='backup-items',
                           value=len(backup_items))

    print(f'=> _check_backup_items: F')
    return backup_items


def _validate_state(status, patch, **_):
    """
    _validate_state

    backup_pod and currently running should both be None or both be
    set. If they are out of sync, then our state is inconsistent.

    TODO: currently just resets both to None, effectively ignoring
    the result of a running pod. Ideally, we should validate the
    status of the pod and clean up.

    Expects Backup object.
    """
    curbackuppod = status.get('backup_pod', None)
    curbackup = status.get('currently_running', None)
    if curbackuppod is None and curbackup is None:
        return None
    if curbackuppod is not None and curbackup is not None:
        return None

    _set_backup(patch, 'currently_running', None)
    _set_backup(patch, 'backup_pod', None)

    raise ProcessingComplete(
        state='inconsistent state',
        message=(
            f'inconsistent state detected. '
            f'backup_pod ({curbackuppod}) is inconsistent '
            f'with currently_running ({curbackup})')
    )


def _validate_running_pod(body, status, namespace, logger, patch, **_):
    """
    _validate_running_pod

    Check whether the Pod we previously started is still running. If not,
    assume the job was killed without being processed by the backup operator
    (or was never started) and clean up. Mark as failed.

    If Pod is still running, update the status details.

    Expects Backup object.
    """
    curbackuppod = status.get('backup_pod', None)
    curbackup = status.get('currently_running', None)
    if curbackuppod:
        try:
            pod = Pod.objects(
                api, namespace=namespace).get_by_name(curbackuppod).obj
        except pykube.exceptions.ObjectDoesNotExist:
            logger.info(f'backup {curbackuppod} missing/deleted, cleaning up')
            _set_backup(patch, 'currently_running', None)
            _set_backup(patch, 'backup_pod', None)
            _set_backup(patch, 'state', 'missing')
            _set_backup_job_state(patch, curbackup, 'last_failure',
                                  datetime.datetime.now(tz=utc).isoformat())
            _set_backup_job_state(patch, curbackup, 'pod_detail', None)
            raise ProcessingComplete(
                message=f'Cleaned up missing/deleted backup')

        podphase = pod.get('status', {}).get('phase', 'unknown')
        logger.info(f'validated that pod {curbackuppod} is '
                    f'still running (phase={podphase})')

        recorded_phase = _get_status(body, curbackup, 'podphase', 'unknown')

        # valid phases are Pending, Running, Succeeded, Failed, Unknown
        if recorded_phase in ('Pending', 'Running', 'Failed'):
            logger.info(f'backup {curbackup} status for '
                        f'{curbackuppod}: {recorded_phase}')
            raise ProcessingComplete(message=f'backup {curbackup} %s' %
                                     curbackup.lower())

        if recorded_phase == 'Succeeded':
            logger.info(f'backup {curbackup} podphase={recorded_phase} but '
                        f'not yet acknowledged: {curbackuppod}')
            raise ProcessingComplete(message=f'backup {curbackup} succeeded, '
                                     f'awaiting acknowledgement')

        logger.debug(f'backup {curbackup} status: {recorded_phase}')
        logger.debug(f'backup {curbackup} status: {str(status)}')
        raise ProcessingComplete(
            message=f'backup {curbackup} unexpected state')


def _date_from_isostr(datestr):
    if datestr:
        # fromisoformat() does not recognise trailing Z for UTC
        if datestr[-1:] == 'Z':
            datestr = datestr[:-1] + '+00:00'
        return (datetime.datetime.fromisoformat(datestr).replace(tzinfo=utc))
    else:
        return datetime.datetime.fromtimestamp(0, tz=utc)


def _update_pod_status(parent, phase, backup_name, status, name, logger, **_):
    """
    _update_pod_status

    Update status of parent (Backup) object with details of execution
    of the current Pod.

    Expects Pod object.
    """
    # TODO: currently only supports a single container. To support
    # multiple containers, we need some logic around whether a particular
    # container needs to complete succesfully or all containers do.
    containerstatuses = status.get('containerStatuses', [])
    terminated = None
    finish_message = None
    parent_message = None
    new_status = {}

    current_last_success = _date_from_isostr(
        _get_status(parent.obj, backup_name, 'last_success'))

    current_last_failure = _date_from_isostr(
        _get_status(parent.obj, backup_name, 'last_failure'))

    for containerstatus in containerstatuses:
        terminated = (containerstatus.get('state', {}).get('terminated'))
        if terminated:
            exit_code = terminated.get('exitCode')
            endtime = _date_from_isostr(terminated.get('finishedAt'))
            if exit_code == 0:
                if endtime > current_last_success:
                    current_last_success = endtime
                    logger.debug(f'successful termination of pod {name}')
                    new_status = {
                        'last_success': endtime.isoformat(),
                        'podphase': phase
                    }
                    parent_message = f'backup {backup_name} completed'
                else:
                    raise ProcessingComplete(
                        message=f'ignoring old successful job {name}')
            else:
                if endtime > current_last_failure:
                    current_last_failure = endtime
                    logger.debug(f'pod {name}, podphase: BadExit')
                    new_status = {
                        'last_failure': endtime.isoformat(),
                        'podphase': 'BadExit'
                    }
                    parent_message = (f'backup {backup_name} failed with exit '
                                      f'code {exit_code}')
                    finish_message = f'backup failed with exit code: {exit_code}'
                else:
                    raise ProcessingComplete(
                        message=f'ignoring old failed job {name}')

            if parent_message and new_status:
                parent.patch({
                    'status': {
                        'backups': {backup_name: {**new_status}},
                        'currently_running': None,
                        'backup_pod': None,
                        'backup_timer': {'message': parent_message},
                        'state': 'idle',
                    }
                })

            if finish_message:
                raise ProcessingComplete(message=finish_message)

@kopf.timer('kawaja.net', 'v1', 'backups',
            initial_delay=30, interval=30,
            annotations={'kawaja.net/operator-status': 'active'})
def backup_timer(**kwargs):
    """
    backup_timer (backup)

    Main loop to handle backup object.
    """
    status = kwargs.get('status')
    logger = kwargs.get('logger')
    patch = kwargs.get('patch')

    curloop = status.get('backup_timer', {}).get('loops', 0)
    patch.setdefault('status', {})

    try:
        _check_backup_items(**kwargs)
        _validate_state(**kwargs)

        # Check the currently-running job
        _validate_running_pod(**kwargs)

        # No backup running, so check to see if we're ready to start another
        item_name = _find_job_to_run(**kwargs)

        # Found a backup job to run, now run it
        logger.info(f'running backup {item_name}')
        _set_backup(patch, 'state', f'running')
        _set_backup_phase(patch, item_name, 'started')
        _set_backup(patch, 'currently_running', item_name)
        pod = _run_backup(item_name, **kwargs)
        _set_backup(patch, 'backup_pod', pod.metadata['name'])

        raise ProcessingComplete(
            last_run=datetime.datetime.now(tz=utc).isoformat(),
            message=f'started backup {item_name}',
            children=[pod.metadata['uid']]
        )

    except ProcessingComplete as exc:
        if 'state' in exc.ret:
            patch['state'] = exc.ret['state']
        if 'info' in exc.ret:
            logger.info(exc.ret['info'])
        if 'error' in exc.ret:
            logger.error(exc.ret['error'])
        if 'message' in exc.ret:
            return {
                'loops': curloop + 1,
                'message': exc.ret['message']
            }

    return {'message': '[backup_timer] should never happen'}


def _get_backup_parent(meta, name, namespace, **_):
    query = Backup.objects(api, namespace=namespace)
    try:
        parent = query.get_by_name(meta['labels'].get('parent-name'))
    except pykube.exceptions.ObjectDoesNotExist:
        raise ProcessingComplete(
            message=
            f'ignoring pod {name} as associated Backup object no longer exists')
    if parent:
        return parent
    raise ProcessingComplete(
        message=
        f'ignoring pod {name} as we cannot find the associated Backup object')


# TODO: is it really on.event we want, or on.create?
@kopf.on.resume('', 'v1', 'pods',
                labels={'parent-name': kopf.PRESENT, 'app': 'backup-operator'})
@kopf.on.event('', 'v1', 'pods',
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
    meta = kwargs.get('meta')
    logger = kwargs.get('logger')
    status = kwargs.get('status')
    phase = status.get('phase')

    try:
        # Get parent (backup object)
        parent = _get_backup_parent(**kwargs)

        backup_name = meta['labels'].get('backup-name', 'unknown')

        recorded_phase = _get_status(parent.obj, backup_name, 'podphase')

        # valid phases are Pending, Running, Succeeded, Failed, Unknown
        if phase not in ('Running', 'Pending'):
            _update_pod_status(parent, phase, backup_name, **kwargs)
        else:
            logger.debug(f'pod {meta["name"]}, podphase: {phase}')
            parent.patch(
                {'status': {
                    'backups': {backup_name: {'podphase': phase}}
                }})
            raise ProcessingComplete(
                message=f'recorded phase "{phase}" for {backup_name}')

        if recorded_phase == 'Succeeded':
            raise ProcessingComplete(
                message=f'success of {backup_name} previously recorded')

        raise ProcessingComplete(message=f'completed processing {backup_name}')
    except ProcessingComplete as exc:
        if 'info' in exc.ret:
            logger.info(exc.ret['info'])
        if 'error' in exc.ret:
            logger.error(exc.ret['error'])
        if 'message' in exc.ret:
            return {'message': exc.ret["message"]}

    return {'message': '[pod_event] should never happen'}


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
    patch = kwargs.get('patch')
    logger = kwargs.get('logger')

    logger.info(f'running [backups_action] for {kwargs.get("name")}')
    try:
        _check_backup_type(**kwargs)
        _check_backup_items(**kwargs)
        raise ProcessingComplete(message='validated')
    except ProcessingComplete as exc:
        if 'state' in exc.ret:
            patch['state'] = exc.ret['state']
        if 'info' in exc.ret:
            logger.info(exc.ret['info'])
        if 'error' in exc.ret:
            logger.error(exc.ret['error'])
        if 'message' in exc.ret:
            return {'message': exc.ret['message']}

    return {'message': '[backups_action] should never happen'}


@kopf.on.login()
def login(**kwargs):
    return kopf.login_via_client(**kwargs)
