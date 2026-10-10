# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build

RUN python -m venv /opt/healer
COPY pyproject.toml README.md ./
COPY src ./src
RUN /opt/healer/bin/pip install --upgrade pip \
    && /opt/healer/bin/pip install '.[neatlogs,providers]'

FROM ${PYTHON_IMAGE} AS runtime

LABEL org.opencontainers.image.title="Spectre Healer" \
    org.opencontainers.image.description="Trace-driven QA service for AI agents" \
    org.opencontainers.image.version="0.1.0"

ENV PATH=/opt/healer/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEALER_HOST=0.0.0.0 \
    HEALER_PORT=8080 \
    HEALER_LOCAL_LOG=/data/runs.jsonl

RUN groupadd --system --gid 10001 healer \
    && useradd --system --uid 10001 --gid healer --home-dir /nonexistent healer \
    && mkdir /data \
    && chown healer:healer /data

COPY --from=builder /opt/healer /opt/healer

USER healer
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.getenv('HEALER_PORT', '8080')}/healthz\", timeout=2).read()"]

ENTRYPOINT ["healer"]
CMD ["serve"]
