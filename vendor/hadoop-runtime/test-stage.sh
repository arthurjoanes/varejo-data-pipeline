#!/bin/sh
# Component checks for the pinned Maven/JDK build stage; no Docker or Python needed.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
MAVEN_REPO="${MAVEN_REPO:-/root/.m2/repository}"
HADOOP_OUT="${HADOOP_OUT:-/out/hadoop-runtime}"

sha256sum -c probe-definition.sha256
sha256sum -c output.sha256
mkdir -p target/probe-dependencies target/probe "$HADOOP_OUT"
classpath="target/hadoop-client-runtime-3.5.0-retail-security.1.jar"
while read -r expected relative; do
  case "$relative" in
    ''|/*|*../*) echo "Invalid locked probe path: $relative" >&2; exit 1 ;;
  esac
  destination="target/probe-dependencies/${relative##*/}"
  if [ -f "$destination" ] && printf '%s  %s\n' "$expected" "$destination" | sha256sum -c --status; then
    :
  elif [ -f "$MAVEN_REPO/$relative" ] && printf '%s  %s\n' "$expected" "$MAVEN_REPO/$relative" | sha256sum -c --status; then
    cp "$MAVEN_REPO/$relative" "$destination"
  else
    curl --silent --show-error --fail --location --retry 3 --connect-timeout 20 --max-time 180 \
      "https://repo.maven.apache.org/maven2/$relative" -o "$destination.download"
    printf '%s  %s\n' "$expected" "$destination.download" | sha256sum -c
    mv "$destination.download" "$destination"
  fi
  classpath="$classpath:$destination"
done < probe-inputs.sha256

javac -J-Xmx256m --release 17 -cp "$classpath" -d target/probe ComponentSmoke.java
if ! timeout 45s java -Xmx256m -Xss256k -cp "target/probe:$classpath" ComponentSmoke \
  > "$HADOOP_OUT/component-stage.log" 2>&1; then
  cat "$HADOOP_OUT/component-stage.log"
  exit 1
fi
cat "$HADOOP_OUT/component-stage.log"
