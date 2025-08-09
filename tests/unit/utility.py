import unittest


class ExtendedTestCase(unittest.TestCase):
    def assertHasAttr(self, obj, intendedAttr):
        testBool = hasattr(obj, intendedAttr)

        # python >=3.8 only
        self.assertTrue(testBool, msg=f'obj lacking an attribute. {obj=}, {intendedAttr=}')

    def assertNotHaveAttr(self, obj, intendedAttr):
        testBool = hasattr(obj, intendedAttr)

        # python >=3.8 only
        self.assertFalse(testBool, msg=f'obj has attribute it shouldn\'t. {obj=}, {intendedAttr=}')


def get_env(env_array, env_var):
    for env in env_array:
        if env.get('name') == env_var:
            return env.get('value')
