FROM python:3.7
RUN pip install kopf kubernetes pykube-ng pyyaml
ADD *.py ./
RUN python3 -m py_compile utility.py
RUN python3 -m py_compile handlers.py
CMD kopf run handlers.py --verbose
