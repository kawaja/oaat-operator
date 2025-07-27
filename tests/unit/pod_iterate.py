from pykube import Pod
import pykube

api = pykube.HTTPClient(pykube.KubeConfig.from_env())

for pod in Pod.objects(api, namespace='default').iterator():
    if 'parent-name' in pod.labels:
        if pod.labels.get('app', '') == 'oaat-operator':
            if pod.labels['parent-name'] == 'datamain-backups':
                podphase = (
                        pod.obj['status'].get('phase', 'unknown'))
                print(
                        f'rogue pod {pod.name} found (phase={podphase})')
