# Runtime local sem acesso de rede após o build.
FROM python:3.11.16-alpine3.24@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356
RUN apk add --no-cache bash procps-ng openjdk17-jre-headless=17.0.20_p8-r0
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk \
    JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=/data/tmp" \
    PATH="/usr/lib/jvm/java-17-openjdk/bin:${PATH}" \
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
RUN apk add --no-cache gcompat \
    && python -m pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.11/ensurepip
COPY . /app
ENTRYPOINT ["python", "-m", "retail_pipeline.cli"]
CMD ["--help"]
