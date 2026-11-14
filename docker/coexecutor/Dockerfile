# Staging image for Pulsar coexecution (Galaxy's Kubernetes, TES and GCP Batch
# runners). It runs pulsar-submit / pulsar-finish next to the tool container
# and, for jobs without a tool container, the tool itself with Conda
# dependencies. Build with `make -C docker/coexecutor all` from the repo root.
ARG PYTHON_IMAGE=python:3.12-slim-trixie
FROM ${PYTHON_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# Pulsar's wheel is pure Python and its dependencies ship wheels, so no
# compiler is needed. pycurl (opt-in via PULSAR_CURL_TRANSPORT=1) and drmaa are
# left out: coexecution stages over HTTP with requests and never talks to a DRM.
COPY pulsar_app-*.whl /tmp/
RUN pip install "$(ls /tmp/pulsar_app-*.whl)[amqp,galaxy_extended_metadata]" \
    && rm /tmp/pulsar_app-*.whl

# Containerless jobs resolve tool requirements with Conda under
# /pulsar_dependencies/conda (see Client.get_pulsar_app_config). Installing
# Conda here saves a download per job; pass --build-arg CONDA_INIT=false for an
# image that is only used with tool containers.
ARG CONDA_INIT=true
RUN if [ "$CONDA_INIT" = "true" ]; then \
        _pulsar-conda-init --conda_prefix=/pulsar_dependencies/conda \
        && /pulsar_dependencies/conda/bin/conda clean --all --yes; \
    fi
