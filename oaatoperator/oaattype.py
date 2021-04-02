"""
oaattype.py

Utilities for working iwth OaatType kubernetes objects.
"""
from oaatoperator.common import ProcessingComplete


# TODO: do a full schema validation on the pod spec?
def podspec(oaattype: dict, name: str = '') -> dict:
    """Retrieve Pod specification from this OaatType."""
    if not oaattype:
        raise ProcessingComplete(message='OaatType invalid',
                error=f'cannot find OaatType {name}')
    msg = 'error in OaatType definition'
    spec = oaattype.get('spec')
    if spec is None:
        raise ProcessingComplete(
            message=msg,
            error='missing spec in OaatType definition')
    if spec.get('type', '') not in ('pod',):
        raise ProcessingComplete(message=msg, error='spec.type must be "pod"')
    podspec = spec.get('podspec')
    if not podspec:
        raise ProcessingComplete(message=msg, error='spec.podspec is missing')
    if podspec.get('containers'):
        raise ProcessingComplete(
            message=msg,
            error='currently only support a single container, '
            'please do not use "spec.podspec.containers"')
    if not podspec.get('container'):
        raise ProcessingComplete(
            message=msg,
            error='spec.podspec.container is missing')
    if podspec.get('restartPolicy'):
        raise ProcessingComplete(
            message=msg,
            error='for spec.type="pod", you cannot specify '
            'a restartPolicy')
    return podspec
