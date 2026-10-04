#!/bin/sh
set -eu
recipe=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
parquet_input=${PARQUET_INPUT:-/input}
parquet_build=${PARQUET_BUILD:-/build}
parquet_output=${PARQUET_OUTPUT:-/output}
parquet_maven=${PARQUET_MAVEN:-/build/m2}
cd "$recipe"
sha256sum -c definition.sha256
mkdir -p "$parquet_input" "$parquet_build" "$parquet_output" "$parquet_maven"
source_archive="$parquet_input/parquet-1.18.1.tar.gz"
source_sha=8c93ac92bd76f2167154ededcdb79b32d4725d9d940f9fedc84bef5103912546
if ! printf '%s  %s\n' "$source_sha" "$source_archive" | sha256sum -c --status; then
    curl --fail --location --silent --show-error --retry 3 \
        --connect-timeout 20 --max-time 300 \
        https://codeload.github.com/apache/parquet-java/tar.gz/refs/tags/apache-parquet-1.18.1 \
        --output "$source_archive.download"
    printf '%s  %s\n' "$source_sha" "$source_archive.download" | sha256sum -c
    mv "$source_archive.download" "$source_archive"
fi
printf '%s  %s\n' "$source_sha" "$source_archive" | sha256sum -c
while read -r expected relative; do
    case "$relative" in
        ''|/*|*../*) echo "Invalid locked Maven path: $relative" >&2; exit 1 ;;
    esac
    destination="$parquet_maven/$relative"
    if [ -f "$destination" ] && printf '%s  %s\n' "$expected" "$destination" | sha256sum -c --status; then
        continue
    fi
    mkdir -p "$(dirname -- "$destination")"
    curl --fail --location --silent --show-error --retry 3 \
        --connect-timeout 20 --max-time 180 \
        "https://repo.maven.apache.org/maven2/$relative" --output "$destination.download"
    printf '%s  %s\n' "$expected" "$destination.download" | sha256sum -c
    mv "$destination.download" "$destination"
done < inputs.sha256
# Extract into a new directory even if the build cache is reused.
parquet_work=$(mktemp -d "$parquet_build/parquet.XXXXXX")
tar -xzf "$source_archive" -C "$parquet_work"
cd "$parquet_work/parquet-java-apache-parquet-1.18.1"
mkdir -p parquet-jackson/src/main/resources/META-INF
tr -d '\r' < "$recipe/provenance.json" > parquet-jackson/src/main/resources/META-INF/varejo-parquet-jackson.json
export SOURCE_DATE_EPOCH=1790985600
export MAVEN_OPTS='-Xms64m -Xmx512m -XX:ActiveProcessorCount=1'
mvn -B -ntp --strict-checksums -o "-Dmaven.repo.local=$parquet_maven" \
    -pl parquet-jackson -Djackson.version=2.22.3 -Djackson-databind.version=2.22.3 \
    -Dproject.build.outputTimestamp=2026-10-03T00:00:00Z \
    -DskipTests -Dmaven.javadoc.skip=true -Dcheckstyle.skip=true \
    -Dcyclonedx.skip=true package
cp parquet-jackson/target/parquet-jackson-1.18.1.jar \
    "$parquet_output/parquet-jackson-1.18.1-retail-jackson-2.22.3.jar"
cp LICENSE NOTICE "$parquet_output/"
javac -cp "$parquet_output/parquet-jackson-1.18.1-retail-jackson-2.22.3.jar" \
    -d "$parquet_output/component-classes" "$recipe/JacksonComponentCheck.java"
java -Xmx128m -cp "$parquet_output/component-classes:$parquet_output/parquet-jackson-1.18.1-retail-jackson-2.22.3.jar" \
    JacksonComponentCheck
cd "$parquet_output"
sha256sum -c "$recipe/output.sha256"
