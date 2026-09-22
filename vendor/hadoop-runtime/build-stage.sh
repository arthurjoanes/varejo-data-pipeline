#!/bin/sh
# Run inside the Maven/JDK image pinned in toolchain.json, after COPY of this directory.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export SOURCE_DATE_EPOCH=1790035200
export MAVEN_OPTS="${MAVEN_OPTS:--Xmx1024m}"
MAVEN_REPO="${MAVEN_REPO:-/root/.m2/repository}"
HADOOP_OUT="${HADOOP_OUT:-/out/hadoop-runtime}"

sha256sum -c definition.sha256
mkdir -p "$MAVEN_REPO" "$HADOOP_OUT"
while read -r expected relative; do
  case "$relative" in
    ''|/*|*../*) echo "Invalid locked Maven path: $relative" >&2; exit 1 ;;
  esac
  destination="$MAVEN_REPO/$relative"
  if [ -f "$destination" ] && printf '%s  %s\n' "$expected" "$destination" | sha256sum -c --status; then
    continue
  fi
  mkdir -p "$(dirname -- "$destination")"
  curl --silent --show-error --fail --location --retry 3 --connect-timeout 20 --max-time 180 \
    "https://repo.maven.apache.org/maven2/$relative" -o "$destination.download"
  printf '%s  %s\n' "$expected" "$destination.download" | sha256sum -c
  mv "$destination.download" "$destination"
done < inputs.sha256

mvn -B -ntp -C -o -s settings.xml "-Dmaven.repo.local=$MAVEN_REPO" package
sha256sum -c output.sha256
cp target/hadoop-client-runtime-3.5.0-retail-security.1.jar "$HADOOP_OUT/"
cp release-manifest.json "$HADOOP_OUT/manifest.json"
cp component-tests.json "$HADOOP_OUT/"
