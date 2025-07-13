import unittest
import time
from kopf.testing import KopfRunner

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
                    'oaatoperator.kawaja.net/testannotation': 'annotationvalue'
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
                }],
                'restartPolicy':
                'Never'
            },
        }

        pod = pykube.Pod(api, doc)

        with KopfRunner([
                'run', '--namespace=default', '--verbose',
                'tests/operator_overseer.py']) as runner:
            pod.create()
            time.sleep(1)
            retryCount = 10
            while retryCount > 0:
                pod.reload()
                pod.annotations['readytodelete'] = 'true'
                try:
                    pod.update()
                except pykube.exceptions.HTTPError as exc:
                    if exc.code != 409:
                        raise
                    print('received HTTP error code 409, retrying')
                    time.sleep(3)
                    retry = retryCount - 1
                else:
                    retryCount = 0
            try:
                pod.reload()
            except pykube.exceptions.HTTPError as exc:
                self.assertRegex(str(exc), f'"{pod.name}" not found', exc)

            print(f'annotations at completion: {pod.annotations}')
            self.maxDiff = None
            self.assertEqual(runner.exit_code, 0)
            self.assertIsNone(runner.exception)
            self.assertRegex(runner.output, r'all overseer tests successful')
            self.assertRegex(runner.output, r'\[1\] successful')
            self.assertRegex(runner.output, r'\[8\] successful')
            self.assertRegex(runner.output, r'\[9\] successful')
            self.assertRegex(runner.output, r'\[10\] successful')
            self.assertRegex(runner.output, r'ERROR.*error message')
            self.assertRegex(runner.output, r'WARNING.*warning message')
            self.assertRegex(runner.output, r'INFO.*info message')
            self.assertRegex(runner.output, r'DEBUG.*debug message')
            self.assertRegex(
                runner.output, r'Patching with.*new_status.: None')
            self.assertRegex(
                runner.output, r'Patching with.*new_status2.: .new_state.')
            self.assertRegex(
                runner.output, r'removed annotation testannotation')
            self.assertEqual(
                pod.annotations.get('oaatoperator.kawaja.net/testannotation',
                                    'missing'), 'missing')
            self.assertEqual(
                pod.annotations.get(
                    'oaatoperator.kawaja.net/numericannotation', 'missing'),
                '7')
            self.assertRegex(
                runner.output,
                r'added annotation new_annotation=annotation_value')
            self.assertEqual(
                pod.annotations.get('oaatoperator.kawaja.net/new_annotation',
                                    'missing'), 'annotation_value')
            self.assertRegex(runner.output, r'ERROR.*reterror')
            self.assertRegex(runner.output, r'WARNING.*retwarning')
            self.assertRegex(runner.output, r'INFO.*retinfo')
            self.assertRegex(
                runner.output, r'status.: {[^{]*.state.: .retstate.')
            self.assertRegex(runner.output, r'\[12\] successful')
            self.assertRegex(runner.output, r'\[13\] successful')
# can't seem to get .delete() to fail, even if the pod is already deleted
#        self.assertRegex(runner.output, r'\[14\] successful')
