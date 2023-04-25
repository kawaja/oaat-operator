import logging
import kopf


def is_running(status, **_):
    """For when= function to test if a pod is running."""
    return status.get('phase') == 'Running'


def is_failed(status, **_):
    """For when= function to test if a pod has failed."""
    return status.get('phase') == 'Failed'


def is_succeeded(status, **_):
    """For when= function to test if a pod has succeeded."""
    return status.get('phase') == 'Succeeded'


@kopf.on.startup()  # type: ignore
def configure(settings: kopf.OperatorSettings, **_) -> None:
    """Set kopf configuration."""
    settings.posting.level = logging.DEBUG
    settings.persistence.finalizer = (
        'phasechange-test.kawaja.net/kopf-finalizer')
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix='phasechange-test.kawaja.net',
        key='last-handled-configuration')
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix='phasechange-test.kawaja.net')


@kopf.on.field('', 'v1', 'pod',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               })  # type: ignore
def pod_phasechange_m_singular(**kwargs):
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')
    return {'message': f'[pod_phasechange] {kwargs["status"].get("phase")}'}


@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               })  # type: ignore
def pod_phasechange_m_plural(**kwargs):
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')
    return {'message': f'[pod_phasechange] {kwargs["status"].get("phase")}'}


@kopf.on.field('pod',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               })  # type: ignore
def pod_phasechange_s_singular(**kwargs):
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')
    return {'message': f'[pod_phasechange] {kwargs["status"].get("phase")}'}


@kopf.on.field('pods',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               })  # type: ignore
def pod_phasechange_s_plural(**kwargs):
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')
    return {'message': f'[pod_phasechange] {kwargs["status"].get("phase")}'}


@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               },
               when=is_succeeded)  # type: ignore
def pod_succeeded(**kwargs):
    """
    pod_succeeded (pod)
    """
    kwargs['logger'].debug(
        f'[pod_succeeded] reason: {kwargs.get("reason", "unknown")}')

    return {'message': f'[pod_phasechange] {kwargs["status"].get("phase")}'}


@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'phasechange-test'},
               when=is_failed)  # type: ignore
def pod_failed(**kwargs):
    """
    pod_failed (pod)
    """
    kwargs['logger'].debug(
        f'[pod_failed] reason: {kwargs.get("reason", "unknown")}')

    return {'message': f'[pod_failed] {kwargs["status"].get("phase")}'}


@kopf.on.login()  # type: ignore
def login(**kwargs):
    """Kopf login."""
    return kopf.login_via_pykube(**kwargs)  # type: ignore
