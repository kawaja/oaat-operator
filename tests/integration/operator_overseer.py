import time
import re
import kopf
from pykube import Pod

from oaatoperator.common import ProcessingComplete
from oaatoperator.overseer import Overseer


@kopf.on.create('pods')  # type: ignore
def create_action(**kwargs):
    # [1] Overseer should raise kopf.PermanentError if kwargs are not passed
    try:
        Overseer()  # type: ignore
    except kopf.PermanentError as exc:
        assert re.search('Overseer must be called with full kopf kwargs',
                         str(exc)), exc
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
    pov.info('starting test 6')
    assert pov.get_status('unset_status') is None
    assert pov.get_status('unset_status', 'empty') == 'empty'
    # set_status
    pov.set_status('new_status')
    pov.set_status('new_status2', 'new_state')

    # [7] get_label
    pov.info('starting test 7')
    assert pov.get_label('nolabel') is None
    assert pov.get_label('nolabel', 'empty') == 'empty'
    assert pov.get_label('testlabel') == 'labelvalue'
    assert pov.get_label('testlabel', 'empty') == 'labelvalue'

    # [8] get_kubeobj without my_pykube_objtype
    pov.info('starting test 8')
    try:
        pov.get_kubeobj()
    except ProcessingComplete as exc:
        assert (str(exc) == 'inheriting class must set self.my_pykube_objtype'
                ), exc
        kwargs['logger'].debug('[8] successful')

    # [9] get_kubeobj missing object
    pov.info('starting test 9')
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
    pov.info('starting test 10')
    kobj = pov.get_kubeobj('examine it')
    kwargs['logger'].debug(f'kubeobj.metadata: {kobj.metadata}')
    assert kobj.metadata['name'] == kwargs['name']
    kwargs['logger'].debug('[10] successful')

    # [11] set_annotation
    pov.info('starting test 11')
    pov.set_annotation('testannotation')
    pov.set_annotation('numericannotation', 7)
    pov.set_annotation('new_annotation', 'annotation_value')

    # [12] handle_processing_complete
    pov.info('starting test 12')
    try:
        raise ProcessingComplete(
            state='retstate',
            info='retinfo',
            error='reterror',
            warning='retwarning',
            message='retmessage'
        )
    except ProcessingComplete as exc:
        pc = pov.handle_processing_complete(exc)
        assert pc is not None
        assert (
            pc.get('message') == 'retmessage'
            ), exc
        kwargs['logger'].debug('[12] successful')

    # [13] handle_processing_complete none
    pov.info('starting test 13')
    try:
        raise ProcessingComplete()
    except ProcessingComplete as exc:
        assert pov.handle_processing_complete(exc) is None, exc
        kwargs['logger'].debug('[13] successful')

    pov.debug('about to complete')
    pov.info('all tests complete')

    return {'message': 'all overseer tests successful'}


@kopf.on.update('pods', annotations={'readytodelete': 'true'})  # type: ignore
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
