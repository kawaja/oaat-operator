FROM python:3.9
COPY requirements.txt ./
COPY requirements/* ./requirements/
RUN pip install -r requirements.txt
COPY oaatoperator/*.py /oaatoperator/
RUN cd /oaatoperator && \
    python3 -m py_compile \
        utility.py common.py overseer.py pod.py oaatgroup.py handlers.py
ENV PYTHONPATH /
CMD kopf run /oaatoperator/handlers.py --verbose
