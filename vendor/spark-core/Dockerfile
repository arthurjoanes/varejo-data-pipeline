FROM maven:3.9.15-eclipse-temurin-17@sha256:527989ca6d3279cc9494d665f617374c428eccd7248dbadf0d03bceaa70b9c5d AS build
COPY vendor/spark-core /recipe
RUN mkdir -p /input /output /build \
    && curl --fail --location --silent --show-error \
        https://archive.apache.org/dist/spark/spark-4.2.0/spark-4.2.0.tgz \
        --output /input/spark-4.2.0.tgz \
    && sh /recipe/build.sh

FROM scratch AS artifacts
COPY --from=build /output/ /
