FROM python:3.7
RUN pip install kopf pykube-ng pyyaml
#RUN git clone https://github.com/kawaja/oaat-operator /oaat-operator
ADD oaatoperator/*.py /oaat-operator
WORKDIR /oaat-operator
RUN cd oaatoperator && python3 -m py_compile utility.py common.py overseer.py pod.py oaatgroup.py handlers.py
CMD kopf run handlers.py --verbose
