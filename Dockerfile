# Runtime fixado de propósito na combinação documentada em docs/architecture.md.
FROM eclipse-temurin:17.0.20_8-jre-jammy@sha256:e85989f3e4d136b3d7dde921e157fddb9c7016805a225c1ec483326b825b3ca5 AS java
FROM python:3.11.16-slim-bookworm@sha256:a36c24f9cbdf4fd0f52d67f0823eeac19c2028c637cecc392d97f980d4fec56b

COPY --from=java /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk \
    PATH="/opt/java/openjdk/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SPARK_LOCAL_IP=127.0.0.1 \
    DELTA_JARS_DIR=/opt/delta-jars \
    RETAIL_DATA_DIR=/data \
    RETAIL_EXPORT_DIR=/app/artifacts \
    SPARK_LOCAL_DIRS=/data/tmp/spark \
    RUFF_CACHE_DIR=/data/cache/ruff \
    MYPY_CACHE_DIR=/data/cache/mypy \
    TMPDIR=/data/tmp

WORKDIR /app
COPY requirements.lock requirements-build.lock /app/
RUN python -m pip install --no-cache-dir --no-deps --require-hashes -r requirements-build.lock \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation --require-hashes -r requirements.lock \
    && python -m pip check
COPY scripts/download_jars.py /tmp/download_jars.py
RUN python /tmp/download_jars.py \
    && rm /tmp/download_jars.py \
    && mkdir -p /data/tmp/spark /app/artifacts \
    && java -version \
    && python --version
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*
COPY . /app
ENTRYPOINT ["python", "-m", "retail_pipeline.cli"]
CMD ["--help"]
