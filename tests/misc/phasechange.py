"""
Test the phasechange detection behaviour of KOPF

To run this test, use (from oaat-operater directory):
    kopf run --verbose tests/phasechange.py
In separate window:
    kubectl create -f tests/testpod.yaml
"""
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
def pod_phasechange_m_singular(**kwargs) -> None:
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')


@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               })  # type: ignore
def pod_phasechange_m_plural(**kwargs) -> None:
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')


@kopf.on.field('pod',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               })  # type: ignore
def pod_phasechange_s_singular(**kwargs) -> None:
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')


@kopf.on.field('pods',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               })  # type: ignore
def pod_phasechange_s_plural(**kwargs) -> None:
    """
    pod_phasechange (pod)
    """
    kwargs['logger'].debug(
        f'[pod_phasechange] reason: {kwargs.get("reason", "unknown")}')


@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               },
               when=is_succeeded)  # type: ignore
def pod_succeeded(**kwargs) -> None:
    """
    pod_succeeded (pod)
    """
    kwargs['logger'].debug(
        f'[pod_succeeded] reason: {kwargs.get("reason", "unknown")}')


@kopf.timer('', 'v1', 'pods',
            interval=240,
            labels={
                'parent-name': kopf.PRESENT,
                'app': 'phasechange-test'
            },
            when=is_succeeded)
@kopf.on.resume('', 'v1', 'pods',
                labels={
                    'parent-name': kopf.PRESENT,
                    'app': 'phasechange-test'
                },
                when=is_succeeded)
@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={
                   'parent-name': kopf.PRESENT,
                   'app': 'phasechange-test'
               },
               when=is_succeeded)
def pod_succeeded_with_timer_with_resume(**kwargs) -> None:
    """
    pod_succeeded (pod)
    """
    kwargs['logger'].debug(
        f'[pod_succeeded_with_timer_with_resume] '
        f'reason: {kwargs.get("reason", "unknown")}')


@kopf.on.field('', 'v1', 'pods',
               field='status.phase',
               labels={'parent-name': kopf.PRESENT, 'app': 'phasechange-test'},
               when=is_failed)  # type: ignore
def pod_failed(**kwargs) -> None:
    """
    pod_failed (pod)
    """
    kwargs['logger'].debug(
        f'[pod_failed] reason: {kwargs.get("reason", "unknown")}')


@kopf.on.login()  # type: ignore
def login(**kwargs):
    """Kopf login."""
    return kopf.login_via_pykube(**kwargs)  # type: ignore
