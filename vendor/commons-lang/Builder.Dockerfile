FROM python:3.11.16-alpine3.24@sha256:cd04730b8511def3fbf14204d66a0c1536f290b8e896ed5a94cd64cb15ac1356
RUN apk add --no-cache openjdk17-jdk=17.0.20_p8-r0 patch \
    && java -version \
    && javac -version
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk \
    PATH="/usr/lib/jvm/java-17-openjdk/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC \
    LANG=C.UTF-8
WORKDIR /work

