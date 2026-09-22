#!/bin/sh
set -eu

source_archive=/input/spark-4.2.0.tgz
printf '%s  %s\n' 6e7be4c3eee79903ed6c413f434fb2526b7ccd031f1f99a8db5c24cc5f66e8cd "$source_archive" | sha256sum -c -
mkdir -p /build/source /build/m2
sh /recipe/fetch-inputs.sh
if [ ! -f /build/source/spark-4.2.0/pom.xml ]; then
    tar -xzf "$source_archive" -C /build/source
fi
cd /build/source/spark-4.2.0
# Only build-process reservations change. Jetty is overridden through the public POM property.
sed -i \
    -e 's/<jvmArg>-Xms4g<\/jvmArg>/<jvmArg>-Xms256m<\/jvmArg>/' \
    -e 's/<jvmArg>-Xmx4g<\/jvmArg>/<jvmArg>-Xmx2g<\/jvmArg>/' \
    -e 's/<jvmArg>-Xss128m<\/jvmArg>/<jvmArg>-Xss16m<\/jvmArg>/' \
    -e 's/<jvmArg>-XX:MaxMetaspaceSize=2g<\/jvmArg>/<jvmArg>-XX:MaxMetaspaceSize=512m<\/jvmArg>/' pom.xml
tr -d '\r' < /recipe/spark-build-info > build/spark-build-info
# Clean only the prototype's superseded provenance file, if reusing its cache.
rm -f core/src/main/resources/META-INF/retail-runtime/spark-core.json
mkdir -p core/src/main/resources/META-INF
tr -d '\r' < /recipe/provenance.json > core/src/main/resources/META-INF/varejo-spark-core.json
export SOURCE_DATE_EPOCH=1783783091
export MAVEN_OPTS='-Xms128m -Xmx768m -Xss4m -XX:MaxMetaspaceSize=256m -XX:ActiveProcessorCount=1'
mvn -o -B -ntp --strict-checksums -Dmaven.repo.local=/build/m2 \
    -pl core -Djetty.version=12.1.13 -Dmaven.test.skip=true -DskipTests \
    -Dproject.build.outputTimestamp=2026-07-11T15:18:11Z -Dspotless.skip=true package
cp core/target/spark-core_2.13-4.2.0.jar /output/spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar
cp LICENSE NOTICE /output/
mvn -o -B -ntp --strict-checksums -Dmaven.repo.local=/build/m2 \
    -pl core -Djetty.version=12.1.13 org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree \
    -DoutputFile=/output/dependency-tree.txt
cp /recipe/inputs.sha256 /output/maven-materials.sha256
sha256sum /output/spark-core_2.13-4.2.0-retail-jetty-12.1.13.jar
