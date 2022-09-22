"""
oaattype.py

Class for managing OaatType kubernetes objects.
"""
from typing import Optional
import pykube
from oaatoperator.common import ProcessingComplete, KubeOaatType


class OaatType:
    """
    OaatType

    Manager for OaatType objects.
    """
    def __init__(self, name: Optional[str], namespace: Optional[str] = None) -> None:
        self.name = str(name)
        self.namespace = namespace
        if name is None:
            raise ProcessingComplete(message='OaatType invalid',
                                     error=f'cannot find OaatType {self.name}')
        self.api = pykube.HTTPClient(pykube.KubeConfig.from_env())
        self.obj = self.get_oaattype()

    def get_oaattype(self) -> dict:
        """Retrieve the OaatType object."""
        try:
            return (
                KubeOaatType
                .objects(self.api, namespace=self.namespace)  # type: ignore
                .get_by_name(self.name)
                .obj)
        except pykube.exceptions.ObjectDoesNotExist as exc:
            raise ProcessingComplete(
                error=(
                    f'cannot find OaatType {self.namespace}/{self.name}: '
                    f'{exc}'),
                message=f'error retrieving "{self.name}" OaatType object')

    def podspec(self) -> dict:
        """Retrieve Pod specification from this OaatType."""
        msg = 'error in OaatType definition'
        spec = self.obj.get('spec')
        if spec is None:
            raise ProcessingComplete(
                message=msg,
                error='missing spec in OaatType definition')
        if spec.get('type', '') not in ('pod',):
            raise ProcessingComplete(message=msg,
                                     error='spec.type must be "pod"')
        podspec = spec.get('podspec')
        if not podspec:
            raise ProcessingComplete(message=msg,
                                     error='spec.podspec is missing')
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
