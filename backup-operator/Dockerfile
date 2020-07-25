FROM python:3.7
RUN pip install kopf kubernetes pykube-ng pyyaml
ADD *.py ./
RUN python3 -m py_compile utility.py
RUN python3 -m py_compile common.py
RUN python3 -m py_compile overseer.py
RUN python3 -m py_compile pod.py
RUN python3 -m py_compile backup.py
RUN python3 -m py_compile handlers.py
CMD kopf run handlers.py --verbose
