from oaatoperator.common import ProcessingComplete
import time
import kopf
from pykube import Pod
from oaatoperator.overseer import Overseer


@kopf.on.create('pods')
def create_action(**kwargs):
    # [1] Overseer should raise ValueError if kwargs are not passed
    try:
        Overseer()
    except ValueError as exc:
        assert str(exc) == 'Overseer must be called with kopf kwargs', exc
        kwargs['logger'].debug('[1] successful')

    pov = Overseer(**kwargs)

    # [2] error
    pov.error('[2] error message')

    # [3] warning
    pov.warning('[3] warning message')

    # [4] info
    pov.info('[4] info message')

    # [5] debug
    pov.debug('[5] debug message')

    # [6] get_status
    assert pov.get_status('unset_status') is None
    assert pov.get_status('unset_status', 'empty') == 'empty'
    # set_status
    pov.set_status('new_status')
    pov.set_status('new_status2', 'new_state')

    # [7] get_label
    assert pov.get_label('nolabel') is None
    assert pov.get_label('nolabel', 'empty') == 'empty'
    assert pov.get_label('testlabel') == 'labelvalue'
    assert pov.get_label('testlabel', 'empty') == 'labelvalue'

    # [8] get_kubeobj without my_pykube_objtype
    try:
        pov.get_kubeobj()
    except ProcessingComplete as exc:
        assert (str(exc) == 'inheriting class must set self.my_pykube_objtype'
                ), exc
        kwargs['logger'].debug('[8] successful')

    # [9] get_kubeobj missing object
    savename = pov.name
    pov.name = 'badname'
    pov.my_pykube_objtype = Pod
    try:
        pov.get_kubeobj()
    except ProcessingComplete as exc:
        assert str(exc) == 'cannot retrieve "badname" object', exc
        kwargs['logger'].debug('[9] successful')
    pov.name = savename

    # [10] get_kubeobj sunny day
    kobj = pov.get_kubeobj('examine it')
    kwargs['logger'].debug(f'kubeobj.metadata: {kobj.metadata}')
    assert kobj.metadata['name'] == kwargs['name']
    kwargs['logger'].debug('[10] successful')

    # [11] set_annotation
    pov.set_annotation('testannotation')
    pov.set_annotation('new_annotation', 'annotation_value')

    # [12] handle_processing_complete
    try:
        raise ProcessingComplete(
            state='retstate',
            info='retinfo',
            error='reterror',
            warning='retwarning',
            message='retmessage'
        )
    except ProcessingComplete as exc:
        assert (
            pov.handle_processing_complete(exc).get('message') == 'retmessage'
            ), exc
        kwargs['logger'].debug('[12] successful')

    # [13] handle_processing_complete none
    try:
        raise ProcessingComplete()
    except ProcessingComplete as exc:
        assert pov.handle_processing_complete(exc) is None, exc
        kwargs['logger'].debug('[13] successful')

    pov.debug('about to complete')

    return 'all overseer tests successful'


@kopf.on.update('pods', annotations={'readytodelete': 'true'})
def update_action(**kwargs):
    pov = Overseer(**kwargs)
    pov.my_pykube_objtype = Pod
    pov.set_annotation('deleting', 'true')
    pov.delete()
    time.sleep(2)

    try:
        pov.delete()
    except ProcessingComplete as exc:
        assert str(exc) == f'cannot delete "{kwargs["name"]}" object', exc
        kwargs['logger'].info('[14] successful')
