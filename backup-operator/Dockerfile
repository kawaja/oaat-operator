FROM python:3.7
ADD handlers.py .
RUN pip install kopf kubernetes pykube-ng pyyaml
CMD kopf run handlers.py --verbose
