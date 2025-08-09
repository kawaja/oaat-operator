"""Utility functions for integration tests that need real Kubernetes interactions."""
import pykube
import time
from typing import Type


def ensure_kubeobj_deleted(ktype: Type[pykube.objects.APIObject], name: str, namespace: str = 'default'):
    """Ensure a Kubernetes object is deleted from the cluster.

    This is the real version that actually interacts with Kubernetes,
    unlike the mock version in tests/unit/mocks_pykube.py.
    """
    api = pykube.HTTPClient(pykube.KubeConfig.from_env())

    try:
        # Try to get the object
        obj = ktype.objects(api, namespace=namespace).get_by_name(name)
        print(f'[ensure_kubeobj_deleted] Found existing {name}, deleting it')
        obj.delete()

        # Wait for deletion to complete (up to 10 seconds)
        for i in range(10):
            try:
                ktype.objects(api, namespace=namespace).get_by_name(name)
                print(f'[ensure_kubeobj_deleted] Waiting for {name} deletion... ({i+1}/10)')
                time.sleep(1)
            except pykube.exceptions.ObjectDoesNotExist:
                print(f'[ensure_kubeobj_deleted] {name} deleted successfully')
                return

        print(f'[ensure_kubeobj_deleted] Warning: {name} still exists after 10 seconds')

    except pykube.exceptions.ObjectDoesNotExist:
        # Object doesn't exist, which is what we want
        print(f'[ensure_kubeobj_deleted] {name} does not exist, no action needed')
    except Exception as e:
        print(f'[ensure_kubeobj_deleted] Error while checking/deleting {name}: {e}')
        # Continue anyway - the test will fail if creation fails due to existing object
