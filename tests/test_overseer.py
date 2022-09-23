import unittest
import time
from kopf.testing import KopfRunner
from copy import deepcopy

import pykube
import unittest.mock


class BasicTests(unittest.TestCase):

    def test_kopfrunner(self):
        api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        doc = {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'generateName': 'oaat-testing-',
                'namespace': 'default',
                'annotations': {
                    'kawaja.net/testannotation': 'annotationvalue'
                },
                'labels': {
                    'testlabel': 'labelvalue'
                }
            },
            'spec': {
                'containers': [{
                        'name': 'oaat-testing',
                        'image': 'busybox',
                        'command': ['sleep', '50']
                    }
                ],
                'restartPolicy': 'Never'
            },
        }

        pod = pykube.Pod(api, doc)

        with KopfRunner([
                'run', '--namespace=default', '--verbose',
                'tests/operator_overseer.py']) as runner:
            pod.create()
            time.sleep(1)
            annotations1 = {}
            retry = True
            while retry:
                pod.reload()
                annotations1 = deepcopy(pod.annotations)
                pod.annotations['readytodelete'] = 'true'
                try:
                    pod.update()
                except pykube.exceptions.HTTPError as exc:
                    if exc.code != 409:
                        raise
                else:
                    retry = False
            time.sleep(3)
            try:
                pod.reload()
            except pykube.exceptions.HTTPError as exc:
                self.assertRegex(str(exc), f'"{pod.name}" not found', exc)

        self.maxDiff = None
        self.assertEqual(runner.exit_code, 0)
        self.assertIsNone(runner.exception)
        self.assertRegex(runner.stdout, r'all overseer tests successful')
        self.assertRegex(runner.stdout, r'\[1\] successful')
        self.assertRegex(runner.stdout, r'\[8\] successful')
        self.assertRegex(runner.stdout, r'\[9\] successful')
        self.assertRegex(runner.stdout, r'\[10\] successful')
        self.assertRegex(runner.stdout, r'ERROR.*error message')
        self.assertRegex(runner.stdout, r'WARNING.*warning message')
        self.assertRegex(runner.stdout, r'INFO.*info message')
        self.assertRegex(runner.stdout, r'DEBUG.*debug message')
        self.assertRegex(
            runner.stdout, r'Patching with.*new_status.: None')
        self.assertRegex(
            runner.stdout, r'Patching with.*new_status2.: .new_state.')
        self.assertRegex(
            runner.stdout, r'removed annotation testannotation')
        self.assertEqual(
            annotations1.get(
                'kawaja.net/testannotation', 'missing'),
            'missing')
        self.assertRegex(
            runner.stdout,
            r'added annotation new_annotation=annotation_value')
        self.assertEqual(
            annotations1['kawaja.net/new_annotation'],
            'annotation_value')
        self.assertRegex(runner.stdout, r'ERROR.*reterror')
        self.assertRegex(runner.stdout, r'WARNING.*retwarning')
        self.assertRegex(runner.stdout, r'INFO.*retinfo')
        self.assertRegex(
            runner.stdout, r'status.: {[^{]*.state.: .retstate.')
        self.assertRegex(runner.stdout, r'\[12\] successful')
        self.assertRegex(runner.stdout, r'\[13\] successful')
# can't seem to get .delete() to fail, even if the pod is already deleted
#        self.assertRegex(runner.stdout, r'\[14\] successful')
