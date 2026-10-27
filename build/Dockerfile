FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.source=https://github.com/kawaja/oaat-operator
LABEL org.opencontainers.image.description="Kubernetes 'one at a time' operator based on kopf"
LABEL org.opencontainers.image.licenses=MIT
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates && \
    apt-get install -y --no-install-recommends --only-upgrade ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
COPY requirements/* ./requirements/
RUN pip install --no-cache-dir -r requirements.txt
# pip packages vendor their own CA bundle; use the system one and fail the build if any emSign root remains
COPY --chmod=755 build/assert-no-emsign.sh /usr/local/bin/assert-no-emsign
RUN find /usr/local/lib -name cacert.pem -exec ln -sf /etc/ssl/certs/ca-certificates.crt {} \; && \
    assert-no-emsign && find /usr/local/lib -name cacert.pem -exec assert-no-emsign {} \;
COPY oaatoperator/*.py /oaatoperator/
RUN cd /oaatoperator && \
    python3 -m py_compile \
        utility.py common.py overseer.py pod.py oaatgroup.py handlers.py oaatitem.py oaattype.py py_types.py
ENV PYTHONPATH=/
CMD ["kopf", "run", "--all-namespaces", "--verbose", "/oaatoperator/handlers.py"]
