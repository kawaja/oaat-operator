"""
backup.py

Overseer object for managing Backup objects.
"""
from random import randrange
import kopf
import pykube
from pykube import Pod
from utility import parse_frequency, date_from_isostr, now_iso
import utility
from common import ProcessingComplete, BackupType, Backup
import overseer


# TODO: should these be moved to a separate BackupItem class?
def get_status(obj, backup, key, default=None):
    """
    get_status

    Get the status of a backup item.

    Intended to be called from handlers other than those for Backup objects.
    """
    return (obj
            .get('status', {})
            .get('backups', {})
            .get(backup, {})
            .get(key, default))

def mark_failed(obj, item_name):
    failure_count = obj.item_status_date(item_name, 'failure_count')
    obj.set_item_status(item_name, 'failure_count', failure_count + 1)
    obj.set_item_status(item_name, 'last_failure', now_iso())

def mark_success(obj, item_name):
    obj.set_item_status(item_name, 'failure_count', 0)
    obj.set_item_status(item_name, 'efailureast_success', now_iso())


class BackupOverseer(overseer.Overseer):
    """
    BackupOverseer

    Manager for Backup objects.

    Initialise with the kwargs for a Backup kopf handler.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        freqstr = kwargs['spec'].get('frequency', '1h')
        self.freq = parse_frequency(freqstr)
        self.my_pykube_objtype = Backup
        self.backuptype = None
        self.body = kwargs['body']

    def item_status(self, item, key, default=None):
        """Get the status of a specific backup item."""
        return (self.get_status('backups', {})
                .get(item, {})
                .get(key, default))

    def item_status_date(self, item, key, default=None):
        """Get the status of a specific backup item, returned as a datetime."""
        return date_from_isostr(self.item_status(item, key, default))

    def set_item_status(self, item, key, value=None):
        """Set the status of a specific backup item."""
        patch = (self.kwargs['patch']['status']
                 .setdefault('backups', {})
                 .setdefault(item, {}))
        patch[item][key] = value

    def set_item_phase(self, item, value):
        """Set the phase of a specific backup item."""
        patch = (self.kwargs['patch']['status']
                 .setdefault('backups', {})
                 .setdefault(item, {}))
        patch['podphase'] = value

    def get_backuptype(self):
        """Retrieve the BackupType object relevant to this Backup."""
        if not self.backuptype:
            backup_type = self.kwargs['spec'].get('backupType')
            if backup_type is None:
                raise ProcessingComplete(
                    message=f'error in Backup definition',
                    error=f'missing backupType in '
                          f'"{self.name}" Backup definition')
            try:
                self.backuptype = (
                    BackupType
                    .objects(self.api, namespace=self.namespace)
                    .get_by_name(backup_type)
                    .obj)
            except pykube.exceptions.ObjectDoesNotExist as exc:
                raise ProcessingComplete(
                    error=(
                        f'cannot find BackupType {self.namespace}/{backup_type} '
                        f'to retrieve podspec: {exc}'),
                    message=f'error retrieving "{backup_type}" BackupType object')
        return self.backuptype

    def get_podspec(self):
        """Retrieve Pod specification from relevant BackupType object."""
        msg = 'error in BackupType definition'
        btobj = self.get_backuptype()
        spec = btobj.get('spec')
        if spec is None:
            raise ProcessingComplete(
                message=msg,
                error='missing spec in BackupType definition')
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

    # TODO: if the oldest backup keeps failing, consider running
    # other backups which are ready to run
    def find_job_to_run(self):
        """
        find_job_to_run

        Find the best backup job to run based on last success and
        failure times.
        """
        now = utility.now()
        backup_items = [
            {
                'name': item,
                'success': self.item_status_date(item, 'last_success'),
                'failure': self.item_status_date(item, 'last_failure'),
                'numfails': self.item_status_date(item, 'failure_count')
            }
            for item in self.kwargs['spec'].get('backupItems', [])
        ]

        self.debug('backup_items:\n' +
                   '\n'.join([str(i) for i in backup_items]))

        if not backup_items:
            raise ProcessingComplete(
                message='error in Backup definition',
                error='no backups found. please set "backupItems"')

        # Filter out items which have been recently successful
        valid_based_on_success = [
            item for item in backup_items if now > item['success'] + self.freq
        ]

        self.debug('valid_based_on_success:\n' +
                   '\n'.join([str(i) for i in valid_based_on_success]))

        if not valid_based_on_success:
            self.set_status('state', 'idle')
            raise ProcessingComplete(
                message='not time to run next backup')

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

    def run_backup(self, item_name):
        """
        run_backup

        Execute a backup Pod with the spec details from the appropriate
        BackupType object.
        """
        spec = self.get_podspec()
        contspec = spec['container']
        del spec['container']
        contspec.setdefault('env', []).append({
            'name': 'BACKUP_ITEM',
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
                    'backup-name': item_name,
                    'app': 'backup-operator'
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

        Ensure there are backupItems to process.
        """
        backup_items = self.kwargs['spec'].get('backupItems')
        if not backup_items:
            if status_annotation:
                self.set_annotation(status_annotation, 'missingBackupItems')
            raise ProcessingComplete(
                state='nothing to do',
                error=f'error in Backup definition',
                message=f'no backups found. '
                        f'Please set "backupItems" in {self.name}'
            )

        # we have backupItems, so mark the backup object as "active" (via
        # annotation)
        if status_annotation:
            self.set_annotation(status_annotation, 'active')
        if count_annotation:
            self.set_annotation(count_annotation, value=len(backup_items))

        return backup_items

    def validate_state(self):
        """
        validate_state

        backup_pod and currently running should both be None or both be
        set. If they are out of sync, then our state is inconsistent.
        This should only happen in unusual situations such as the
        backup-operator being killed while starting a backup pod.

        TODO: currently just resets both to None, effectively ignoring
        the result of a running pod. Ideally, we should validate the
        status of the pod and clean up.
        """
        curbackuppod = self.get_status('backup_pod')
        curbackup = self.get_status('currently_running')
        if curbackuppod is None and curbackup is None:
            return None
        if curbackuppod is not None and curbackup is not None:
            return None

        self.set_status('currently_running')
        self.set_status('backup_pod')

        raise ProcessingComplete(
            state='inconsistent state',
            message='internal error',
            error=(
                f'inconsistent state detected. '
                f'backup_pod ({curbackuppod}) is inconsistent '
                f'with currently_running ({curbackup})')
        )

    def validate_running_pod(self):
        """
        validate_running_pod

        Check whether the Pod we previously started is still running. If not,
        assume the job was killed without being processed by the backup
        operator (or was never started) and clean up. Mark as failed.

        If Pod is still running, update the status details.
        """
        curbackuppod = self.get_status('backup_pod')
        curbackup = self.get_status('currently_running')
        if curbackuppod:
            try:
                pod = Pod.objects(
                    self.api,
                    namespace=self.namespace).get_by_name(curbackuppod).obj
            except pykube.exceptions.ObjectDoesNotExist:
                self.info(
                    f'backup {curbackuppod} missing/deleted, cleaning up')
                self.set_status('currently_running')
                self.set_status('backup_pod')
                self.set_status('state', 'missing')
                mark_failed(self.body, curbackup)
                self.set_item_status(curbackup, 'pod_detail')
                raise ProcessingComplete(
                    info='Cleaned up missing/deleted backup')

            podphase = pod.get('status', {}).get('phase', 'unknown')
            self.info(f'validated that pod {curbackuppod} is '
                      f'still running (phase={podphase})')

            recorded_phase = self.item_status(curbackup, 'podphase', 'unknown')

            # valid phases are Pending, Running, Succeeded, Failed, Unknown
            # 'started' is the phase the pods start with when created by
            # backup operator.
            if recorded_phase in ('started', 'Pending', 'Running', 'Failed'):
                self.info(f'backup {curbackup} status for '
                          f'{curbackuppod}: {recorded_phase}')
                raise ProcessingComplete(message=f'backup {curbackup} %s' %
                                         recorded_phase.lower())

            if recorded_phase == 'Succeeded':
                self.info(f'backup {curbackup} podphase={recorded_phase} but '
                          f'not yet acknowledged: {curbackuppod}')
                raise ProcessingComplete(
                    message=f'backup {curbackup} succeeded, '
                    'awaiting acknowledgement')

            raise ProcessingComplete(
                error=f'backup {curbackup} unexpected state: '
                      f'recorded_phase={recorded_phase}, '
                      f'status={str(self.kwargs["status"])}',
                message=f'backup {curbackup} unexpected state')

    def check_backup_type(self):
        """
        check_backup_type

        Ensure the backup refers to an appropriate BackupType object.
        """
        backuptypes = BackupType.objects(self.api)
        backup_type = self.kwargs['spec'].get('backupType')
        if backup_type not in [x.name for x in backuptypes]:
            self.set_annotation('operator-status', 'missingBackupType')
            raise ProcessingComplete(
                message='error in Backup definition',
                error=f'unknown backup type {backup_type}')
        kopf.info(self.kwargs['spec'],
                  reason='Validation',
                  message='found valid backup type')
