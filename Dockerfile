# Rebuilds identificados; fontes upstream, compiladores e caches ficam fora do runtime.
FROM maven:3.9.15-eclipse-temurin-17@sha256:527989ca6d3279cc9494d665f617374c428eccd7248dbadf0d03bceaa70b9c5d AS spark-core-build
COPY vendor/spark-core /recipe
RUN --mount=type=cache,id=varejo-spark-source,target=/input,sharing=locked \
    --mount=type=cache,id=varejo-spark-m2,target=/build/m2,sharing=locked \
    mkdir -p /input /output /build \
    && if ! printf '%s  %s\n' \
        6e7be4c3eee79903ed6c413f434fb2526b7ccd031f1f99a8db5c24cc5f66e8cd \
        /input/spark-4.2.0.tgz | sha256sum -c --status; then \
        curl --fail --location --silent --show-error --retry 2 \
            --connect-timeout 20 --max-time 1800 --speed-limit 1024 --speed-time 60 \
            https://archive.apache.org/dist/spark/spark-4.2.0/spark-4.2.0.tgz \
            --output /input/spark-4.2.0.tgz.download \
        && mv /input/spark-4.2.0.tgz.download /input/spark-4.2.0.tgz; fi \
    && sh /recipe/build.sh
RUN --mount=type=cache,id=varejo-spark-m2,target=/build/m2,sharing=locked \
    javac -d /output/component-classes \
        -cp /output/spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar:/build/m2/org/slf4j/slf4j-api/2.0.17/slf4j-api-2.0.17.jar \
        /recipe/JettyComponentCheck.java \
    && java -Xmx128m \
        -cp /output/component-classes:/output/spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar:/build/m2/org/slf4j/slf4j-api/2.0.17/slf4j-api-2.0.17.jar \
        JettyComponentCheck true

FROM maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82 AS hadoop-runtime-build
COPY vendor/hadoop-runtime /build/hadoop-runtime
RUN --mount=type=cache,id=varejo-hadoop-m2,target=/root/.m2/repository,sharing=locked \
    HADOOP_OUT=/out/hadoop-runtime sh /build/hadoop-runtime/build-stage.sh
RUN --mount=type=cache,id=varejo-hadoop-m2,target=/root/.m2/repository,sharing=locked \
    HADOOP_OUT=/out/hadoop-runtime sh /build/hadoop-runtime/test-stage.sh

FROM python:3.11.16-alpine3.24@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356 AS commons-lang-build
RUN apk add --no-cache openjdk17-jdk=17.0.20_p8-r0 patch
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk \
    PATH="/usr/lib/jvm/java-17-openjdk/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC \
    LANG=C.UTF-8
COPY scripts/build_commons_lang.py /build/scripts/build_commons_lang.py
COPY vendor/commons-lang /build/vendor/commons-lang
RUN python /build/scripts/build_commons_lang.py \
    --downloads /tmp/commons-lang-downloads --output /output/commons-lang --fetch

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
COPY scripts/download_jars.py scripts/patch_runtime_jars.py scripts/install_rebuilt_jars.py scripts/fetch_artifact.py runtime-jars.lock.json /tmp/
COPY --from=spark-core-build /output/spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar /tmp/rebuilt/spark-core/spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar
COPY --from=hadoop-runtime-build /out/hadoop-runtime/hadoop-client-runtime-3.5.0-retail-security.1.jar /tmp/rebuilt/hadoop-runtime/hadoop-client-runtime-3.5.0-retail-security.1.jar
COPY --from=commons-lang-build /output/commons-lang/commons-lang-2.6-retail-classutils-v1.jar /tmp/rebuilt/commons-lang/commons-lang-2.6-retail-classutils-v1.jar
RUN --mount=type=cache,id=varejo-runtime-jars,target=/var/cache/varejo-jars,sharing=locked \
    export VAREJO_JAR_CACHE=/var/cache/varejo-jars \
    && python /tmp/download_jars.py \
    && python /tmp/patch_runtime_jars.py /tmp/runtime-jars.lock.json \
    && python /tmp/install_rebuilt_jars.py /tmp/runtime-jars.lock.json /tmp/rebuilt /opt/varejo-runtime-builds \
    && rm /tmp/download_jars.py /tmp/patch_runtime_jars.py /tmp/install_rebuilt_jars.py /tmp/fetch_artifact.py /tmp/runtime-jars.lock.json \
    && rm -rf /tmp/rebuilt \
    && mkdir -p /data/tmp/spark /app/artifacts \
    && java -version \
    && python --version
RUN apk add --no-cache gcompat \
    && python -m pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.11/ensurepip
COPY src /app/src
COPY tests /app/tests
COPY scripts /app/scripts
COPY data /app/data
COPY docs /app/docs
COPY README.md LICENSE pyproject.toml compose.yaml Dockerfile .env.example runtime-jars.lock.json /app/
ENTRYPOINT ["python", "-m", "retail_pipeline.cli"]
CMD ["--help"]
