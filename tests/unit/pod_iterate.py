from pykube import Pod
import pykube

# Mock API for unit testing - no real k3d connection needed
from unittest.mock import Mock
api = Mock()  # Remove spec since pykube.HTTPClient is already mocked globally

for pod in Pod.objects(api, namespace='default').iterator():
    if 'parent-name' in pod.labels:
        if pod.labels.get('app', '') == 'oaat-operator':
            if pod.labels['parent-name'] == 'datamain-backups':
                podphase = (
                        pod.obj['status'].get('phase', 'unknown'))
                print(
                        f'rogue pod {pod.name} found (phase={podphase})')
