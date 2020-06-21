import kopf
import pykube
import yaml


@kopf.on.create('kawaja.net', 'v1', 'backups')
def create(spec, **kwargs):
    print(f"And here we are! Creating: {spec}")
    doc = yaml.safe_load(f'''
        apiVersion: v1
        kind: Pod
        spec:
          containers:
          - name: test
            image: busybox
            command: ["sh", "-x", "-c"]
            args:
            - |
              echo "FIELD=$FIELD"
              sleep 10
              exit 0
            env:
            - name: FIELD
              value: "{','.join(spec.get('backupItems', 'none'))}"
          restartPolicy: OnFailure
    ''')
    kopf.adopt(doc)
    api = pykube.HTTPClient(pykube.KubeConfig.from_env())
    pod = pykube.Pod(api, doc)
    pod.create()
    api.session.close()
    return {
        'children': [pod.metadata['uid']],
        'message': 'running'
    }

@kopf.on.login()
def login(**kwargs):
    return kopf.login_via_client(**kwargs)
