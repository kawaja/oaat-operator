FROM python:3.7
RUN pip install kopf pykube-ng pyyaml
ADD *.py /oaat-operator/
WORKDIR /oaat-operator
RUN python3 -m py_compile utility.py common.py overseer.py pod.py oaatgroup.py handlers.py
CMD kopf run handlers.py --verbose
