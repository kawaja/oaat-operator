"""
py_types.py

Types used for type validation.
"""
from typing import Any, TypedDict, Optional, Union
import kopf
from kopf._cogs.structs import bodies, references, patches, diffs
import datetime
import logging


# Adapted from kopf/_core/intents/callbacks.py because KOPF does not
# appear to expose callback arguments in its interface
class CallbackArgs(TypedDict):
    retry: int
    started: datetime.datetime
    runtime: datetime.timedelta
    annotations: bodies.Annotations
    labels: bodies.Labels
    body: bodies.Body
    meta: bodies.Meta
    spec: bodies.Spec
    status: bodies.Status
    resource: references.Resource
    uid: Optional[str]
    name: Optional[str]
    namespace: Optional[str]
    patch: patches.Patch
    reason: str
    diff: diffs.Diff
    old: Optional[Union[bodies.BodyEssence, Any]]
    new: Optional[Union[bodies.BodyEssence, Any]]
    logger: logging.Logger
    memo: kopf.Memo
    param: Any
