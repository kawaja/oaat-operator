"""Common definitions which are specific to the Backup handler."""
import pykube

class ProcessingComplete(BaseException):
    """Signal from a subfunction to a handler that processing is complete."""
    def __init__(self, **kwargs):
        self.ret = {}
        for arg in kwargs:
            self.ret[arg] = kwargs[arg]


class Backup(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'backups'
    kind = 'Backup'


class BackupType(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'backuptypes'
    kind = 'BackupType'
