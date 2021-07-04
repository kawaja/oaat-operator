import unittest
import time
import yaml
from pathlib import Path
from kopf.testing import KopfRunner

import pykube
import unittest.mock
import oaatoperator.common


class BasicTests(unittest.TestCase):

    def test_integration(self):
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        ns = 'oaat-integration'

        # Ensure namespace exists
        try:
            pykube.Namespace.objects(api).get(name=ns)
        except pykube.ObjectDoesNotExist:
            print(f'creating namespace {ns}')
            pykube.objects.Namespace(
                api, {
                    'apiVersion': 'v1',
                    'kind': 'Namespace',
                    'metadata': {
                        'name': ns
                    }
                }).create()

        # get KubeOaatType test configuration
        with Path('tests/integration_oaattype.yaml').open() as f:
            oaattypedef = yaml.safe_load(f.read())

        oaattype = oaatoperator.common.KubeOaatType(api, oaattypedef)

        # delete KubeOaatType if it already exists
        try:
            kot = (
                    oaatoperator.common.KubeOaatType.
                    objects(api).
                    filter(namespace=oaattype.namespace).
                    get(name=oaattype.name))
        except pykube.exceptions.ObjectDoesNotExist:
            print(f'{oaattype.kind} {oaattype.name} does not exist')
            pass
        else:
            print(f'deleting existing {oaattype.kind}: {oaattype.name}')
            kot.delete()

        # create KubeOaatType
        print(f'creating {oaattype.kind}: {oaattype.name}')
        oaattype.create()

        # get KubeOaatGroup test configuration
        with Path('tests/integration_oaatgroup.yaml').open() as f:
            oaatgroupdef = yaml.safe_load(f.read())

        oaatgroup = oaatoperator.common.KubeOaatGroup(api, oaatgroupdef)

        # delete KubeOaatGroup if it already exists
        try:
            kog = (
                    oaatoperator.common.KubeOaatGroup.
                    objects(api).
                    filter(namespace=oaatgroup.namespace).
                    get(name=oaatgroup.name))
        except pykube.exceptions.ObjectDoesNotExist:
            print(f'{oaatgroup.kind} {oaatgroup.name} does not exist')
            pass
        else:
            print(f'deleting existing {oaatgroup.kind}: {oaatgroup.name}')
            kog.delete()

        with KopfRunner([
                'run', '--namespace=default', '--verbose',
                'oaatoperator/handlers.py']) as runner:
            oaatgroup.create()
            time.sleep(1)
            oaatgroup.reload()

        oaatgroup.delete()
        oaattype.delete()
