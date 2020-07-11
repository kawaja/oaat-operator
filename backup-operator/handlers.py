from random import randrange
import datetime
import yaml
import kopf
import pykube
from pykube import Pod
import utility

utc = datetime.timezone.utc

class Backup(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'backups'
    kind = 'Backup'


class BackupType(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'backuptypes'
    kind = 'BackupType'


def _set_backup(patch, state, value):
    patch['status'][state] = value


def _set_backup_phase(patch, name, value):
    patch['status'] .setdefault('backups', {}) .setdefault(name, {})
    patch['phase'] = value


def _set_backup_job_state(patch, item_name, key, value):
    patch['status'].setdefault('backups', {}).setdefault(item_name, {})
    patch['status']['backups'][item_name][key] = value


def _get_backup_job(status, item_name, key, default=None):
    return status.get('backups', {}).get(item_name, {}).get(key, default)


def _find_job(status, spec, patch, logger):
    """
    Find the time and name of the backup job which has been least recently
    successful.
    """
    curloop = status.get('backup', {}).get('loops', 0)
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
        successstr = _get_backup_job(status, backup_item, 'last_success')
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
            f'{curloop}: '
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
                _set_backup(patch, 'state',
                            f'next backup {(oldest+freq).isoformat()}')
                logger.info(
                    f'{curloop}: Not yet time to run another backup '
                    f'(oldest: {item_name}={oldest.isoformat()}, '
                    f'freq: {freq} / {freq.total_seconds()}, '
                    f'now: {datetime.datetime.now(tz=utc).isoformat()} /'
                    f'{datetime.datetime.now(tz=utc).timestamp()}, '
                    f'next: {(oldest+freq).isoformat()} / '
                    f'{(oldest+freq).timestamp()})')
                return None
        except (TypeError, ValueError) as exc:
            logger.error(f'{curloop}: Error calculating times: {exc}')
            logger.info(
                f'{curloop}:Continuing with backup for {item_name} after error')
            return item_name

    return item_name


def _run_backup(name, item_name):
    doc = yaml.safe_load(f'''
        apiVersion: v1
        kind: Pod
        metadata:
          generateName: {name + '-' + item_name + '-'}
        spec:
          containers:
          - name: test
            image: busybox
            command: ["sh", "-x", "-c"]
            args:
            - |
              echo "BACKUP_ITEM=$BACKUP_ITEM"
              sleep $(shuf -i 10-180 -n 1)
              exit 0
            env:
            - name: BACKUP_ITEM
              value: "{item_name}"
          restartPolicy: OnFailure
    ''')
    kopf.adopt(doc)
    kopf.label(doc, {
        'parent-name': name,
        'backup-name': item_name,
        'app': 'backup-operator'
    })

    api = pykube.HTTPClient(pykube.KubeConfig.from_env())
    pod = pykube.Pod(api, doc)
    pod.create()
    api.session.close()
    return pod


@kopf.timer('kawaja.net', 'v1', 'backups', initial_delay=30, interval=30)
def backup(spec, status, logger, name, patch, namespace, **kwargs):
    curloop = status.get('backup', {}).get('loops', 0)
    curbackuppod = status.get('backup_pod', None)
    curbackup = status.get('currently_running', None)
    curphase = status.get('phase', 'unknown')
    patch.setdefault('status', {})
    backup_items = spec.get('backupItems')
    if backup_items is None:
        patch['state'] = 'nothing to do'
        return {
            'message':
            f'{curloop}: no backups found. ' +
            f'please set "backupItems" in {name}'
        }

    # TODO: curbackup and curbackuppod should both be set or both be None
    # should test this to ensure we're still in a valid state
    if curbackuppod:
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        pod = Pod.objects(api, namespace=namespace).get_by_name(curbackuppod)
        if not pod:
            logger.info(f'backup {curbackuppod} missing/deleted, cleaning up')
            _set_backup(patch, 'currently_running', None)
            _set_backup(patch, 'backup_pod', None)
            _set_backup(patch, 'state', 'missing')
            _set_backup_job_state(patch, curbackup, 'last_failure',
                                  datetime.datetime.now(tz=utc).isoformat())
            _set_backup_job_state(patch, curbackup, 'pod_detail', None)
            return {
                'loops': curloop + 1,
                'message': f'Cleaned up missing/deleted backup'
            }

        if curphase == 'Running':
            logger.info(f'backup {curbackup} still running: {curbackuppod}')
            return {
                'loops': curloop + 1,
                'message': f'backup {curbackup} still running'
            }

        if curphase == 'Succeeded':
            logger.info(f'backup {curbackup} succeeded but '
                        f'not yet acknowledged: {curbackuppod}')
            return {
                'loops': curloop + 1,
                'message': f'backup {curbackup} awaiting acknowledgement'
            }

        logger.debug(f'backup {curbackup} status: {curphase}')
        logger.debug(f'backup {curbackup} status: {str(status)}')
        return {
            'loops': curloop + 1,
            'message': f'backup {curbackup} unexpected state'
        }

    item_name = _find_job(status, spec, patch, logger)
    if item_name is None:
        return {
            'loops': curloop + 1,
            'message': f'Not yet time to try another backup'
        }

    # found a backup job to run, now run it
    logger.info(f'running backup {item_name}')
    _set_backup(patch, 'state', f'running backup {item_name}')
    _set_backup(patch, 'currently_running', item_name)
    _set_backup_phase(patch, item_name, 'started')
    pod = _run_backup(name, item_name)
    _set_backup(patch, 'backup_pod', pod.metadata['name'])

    return {
        'last_run': datetime.datetime.now(tz=utc).isoformat(),
        'message': f'running backup {item_name}',
        'loops': curloop + 1,
        'children': [pod.metadata['uid']]
    }


@kopf.on.resume('', 'v1', 'pods',
               labels={'parent-name': kopf.PRESENT, 'app': 'backup-operator'})
@kopf.on.event('', 'v1', 'pods',
               labels={'parent-name': kopf.PRESENT, 'app': 'backup-operator'})
def pod_event(meta, status, namespace, logger, **kwargs):
    api = pykube.HTTPClient(pykube.KubeConfig.from_env())
    phase = status.get('phase')
    query = Backup.objects(api, namespace=namespace)
    try:
        parent = query.get_by_name(meta['labels'].get('parent-name'))
    except pykube.exceptions.ObjectDoesNotExist as exc:
        logger.warn(f'pod_event: {exc}')
        return {}

    name = meta['labels'].get('backup-name', 'unknown')
    curphase = (parent.obj
                .get('status', {})
                .get('backups', {})
                .get(name, {})
                .get('podphase'))

    if phase == 'Succeeded':
        containerstatuses = status.get('containerStatuses', [])
        terminated = None
        for containerstatus in containerstatuses:
            terminated = (containerstatus.get('state', {}).get('terminated'))
            if terminated:
                if terminated.get('exitCode') == 0:
                    # fromisoformat() does not recognise trailing Z for UTC
                    endtime = terminated.get('finishedAt').replace('Z', '+00:00')
                    parent.patch({
                        'status': {
                            'backups': {
                                name: {'last_success': endtime}
                            },
                            'currently_running': None,
                            'backup_pod': None,
                            'backup': {'message': 'idle'},
                            'state': 'completed'
                        }
                    })
                else:
                    parent.patch(
                        {'status': {'backups': {name: {'podphase': 'BadExit'}}}})
                    return {
                        'message': f'backup failed with exit code: ' +
                                   str(terminated.get('exitCode'))
                    }

    parent.patch(
        {'status': {'backups': {name: {'podphase': phase}}}}
    )

    if curphase == 'Succeeded':
        return {'message': f'success of {name} previously recorded'}
    return {'message': f'recorded success of {name}'}


@kopf.on.create('kawaja.net', 'v1', 'backups')
def create(spec, status, **kwargs):
    api = pykube.HTTPClient(pykube.KubeConfig.from_env())
    backuptypes = BackupType.objects(api)
    backup_type = spec.get('backupType')
    if backup_type not in [x.name for x in backuptypes]:
        return {'message': f'unknown backup type {backup_type}'}
    kopf.info(spec, reason='Validation', message='found valid backup type')

    return {
        'message': 'validated'
    }


@kopf.on.login()
def login(**kwargs):
    return kopf.login_via_client(**kwargs)
