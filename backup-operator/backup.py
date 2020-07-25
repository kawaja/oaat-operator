"""
backup.py

Overseer object for managing Backup objects.
"""
from random import randrange
import kopf
import pykube
from pykube import Pod
from utility import parse_frequency, date_from_isostr, now, now_iso
from common import ProcessingComplete, BackupType, Backup
import overseer


# TODO: should this be moved to a separate BackupItem class?
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

    def get_podspec(self):
        """Retrieve Pod specification from relevant BackupType object."""
        backup_type = self.kwargs['spec'].get('backupType')
        if backup_type is None:
            raise ProcessingComplete(
                message=f'missing backupType in '
                        f'"{self.name}" Backup definition')
        try:
            btobj = BackupType.objects(
                self.api, namespace=self.namespace).get_by_name(backup_type).obj
        except pykube.exceptions.ObjectDoesNotExist as exc:
            raise ProcessingComplete(
                error=(
                    f'cannot find BackupType {self.namespace}/{backup_type} '
                    f'to retrieve podspec: {exc}'),
                message=f'cannot retrieve "{backup_type}" BackupType object')
        podspec = btobj.get('spec', {}).get('podspec')
        if podspec is None:
            raise ProcessingComplete(
                message=
                f'missing podspec in "{backup_type}" BackupType definition')
        return podspec

    # TODO: if the oldest backup keeps failing, consider running
    # other backups which are ready to run
    def find_job_to_run(self):
        """
        find_job_to_run

        Find the time and name of the backup job which has been least recently
        successful.
        """
        backup_items = self.kwargs['spec'].get('backupItems')
        if backup_items is None:
            return {
                'message':
                f'no backups found. please set "backupItems"'
            }

        # find entry with the least recent last_success and least recent
        # last_failure
        # dates are always UTC
        # need to take care that dates are all 'aware' of timezone so
        # date arithmetic works
        oldest_success_time = 0
        oldest_success_item = None
        oldest_failure_time = 0
        oldest_failure_item = None
        for backup_item in backup_items:
            last_success = self.item_status_date(backup_item, 'last_success')
            last_failure = self.item_status_date(backup_item, 'last_failure')
            self.debug(
                f'backup_item: {backup_item}, '
                f'oldest_success_time: {oldest_success_time}, '
                f'oldest_failure: {oldest_failure_time}, '
                f'last_success: {last_success}'
                f'last_failure: {last_failure}')
            if not oldest_success_time or last_success < oldest_success_time:
                oldest_success_time = last_success
                oldest_success_item = backup_item
            if not oldest_failure_time or last_failure < oldest_failure_time:
                oldest_failure_time = last_failure
                oldest_failure_item = backup_item
            self.info(
                f'Checking backup {backup_item}, '
                f'last_success={last_success}, '
                f'oldest_success_item={oldest_success_item}, '
                f'oldest_success_time={oldest_success_time}, '
                f'last_failure={last_failure}, '
                f'oldest_failure_item={oldest_failure_item}, '
                f'oldest_failure_time={oldest_failure_time}')

        # if none have been successful, choose randomly
        if oldest_success_item:
            self.debug(f'Found oldest_success_item: {oldest_success_item}')
            try:
                if oldest_success_time + self.freq > now():
                    self.set_status('state', 'idle')
                    self.info(
                        f'Not yet time to run another backup '
                        f'(oldest: {oldest_success_item}='
                        f'{oldest_success_time.isoformat()}, '
                        f'freq: {self.freq} / {self.freq.total_seconds()}, '
                        f'now: {now_iso()} /'
                        f'{now().timestamp()}, '
                        f'next: {(oldest_success_time+self.freq).isoformat()} / '
                        f'{(oldest_success_time+self.freq).timestamp()})')
                    raise ProcessingComplete(
                        message=
                        f'next backup "{oldest_success_item}" '
                        f'{(oldest_success_time+self.freq).isoformat()}')
            except (TypeError, ValueError) as exc:
                self.error(f'Error calculating times: {exc}')
                self.info(
                    f'Continuing with backup for {oldest_success_item} after error')
                return oldest_success_item

        if oldest_failure_item:
            self.debug(f'Found oldest_failure_item: {oldest_failure_item}')
            return oldest_failure_item

        self.debug(f'Didn\'t find any backup executions, choosing at random')
        return backup_items[randrange(len(backup_items))]  # nosec

    def run_backup(self, item_name):
        """
        run_backup

        Execute a backup Pod with the spec details from the appropriate BackupType
        object.
        """
        podspec = self.get_podspec()
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
                'generateName': self.name + '-' + item_name + '-',
                'labels': {
                    'parent-name': self.name,
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
        pod = Pod(self.api, doc)

        try:
            pod.create()
        except pykube.KubernetesError as exc:
            raise ProcessingComplete(
                info=f'failed creating pod: {podspec}',
                error=f'could not create pod: {exc}',
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
            message=(
                f'inconsistent state detected. '
                f'backup_pod ({curbackuppod}) is inconsistent '
                f'with currently_running ({curbackup})')
        )

    def validate_running_pod(self):
        """
        validate_running_pod

        Check whether the Pod we previously started is still running. If not,
        assume the job was killed without being processed by the backup operator
        (or was never started) and clean up. Mark as failed.

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
                self.info(f'backup {curbackuppod} missing/deleted, cleaning up')
                self.set_status('currently_running')
                self.set_status('backup_pod')
                self.set_status('state', 'missing')
                self.set_item_status(curbackup, 'last_failure', now_iso())
                self.set_item_status(curbackup, 'pod_detail')
                raise ProcessingComplete(
                    message=f'Cleaned up missing/deleted backup')

            podphase = pod.get('status', {}).get('phase', 'unknown')
            self.info(f'validated that pod {curbackuppod} is '
                      f'still running (phase={podphase})')

            recorded_phase = self.item_status(curbackup, 'podphase', 'unknown')

            # valid phases are Pending, Running, Succeeded, Failed, Unknown
            if recorded_phase in ('Pending', 'Running', 'Failed'):
                self.info(f'backup {curbackup} status for '
                          f'{curbackuppod}: {recorded_phase}')
                raise ProcessingComplete(message=f'backup {curbackup} %s' %
                                         curbackup.lower())

            if recorded_phase == 'Succeeded':
                self.info(f'backup {curbackup} podphase={recorded_phase} but '
                          f'not yet acknowledged: {curbackuppod}')
                raise ProcessingComplete(message=f'backup {curbackup} succeeded, '
                                         f'awaiting acknowledgement')

            self.debug(f'backup {curbackup} status: {recorded_phase}')
            self.debug(
                f'backup {curbackup} status: {str(self.kwargs["status"])}')
            raise ProcessingComplete(
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
                message=f'unknown backup type {backup_type}')
        kopf.info(self.kwargs['spec'],
                  reason='Validation',
                  message='found valid backup type')
