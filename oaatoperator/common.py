"""Common definitions which are specific to the Oaat handler."""
import pykube


class ProcessingComplete(BaseException):
    """Signal from a subfunction to a handler that processing is complete."""
    def __init__(self, **kwargs):
        self.ret = {}
        for arg in kwargs:
            self.ret[arg] = kwargs[arg]

    def __str__(self):
        return self.ret.get('message', '')


class KubeOaatGroup(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'oaatgroups'
    kind = 'OaatGroup'


class KubeOaatType(pykube.objects.NamespacedAPIObject):
    version = 'kawaja.net/v1'
    endpoint = 'oaattypes'
    kind = 'OaatType'
