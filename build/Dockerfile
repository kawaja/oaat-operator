FROM python:3.7
RUN pip install kopf pykube-ng pyyaml
ADD *.py /oaatoperator/
RUN cd /oaatoperator && python3 -m py_compile utility.py common.py overseer.py pod.py oaatgroup.py handlers.py
CMD kopf run /oaatoperator/handlers.py --verbose
