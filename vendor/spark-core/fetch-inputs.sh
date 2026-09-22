#!/bin/sh
set -eu

# Maven runs offline afterwards. This is the only Maven-artifact network step.
# Every payload is fixed by path and SHA-256, including compiler executables.
repository=${MAVEN_REPO:-/build/m2}
mkdir -p "$repository"
export repository
fetch_one() {
    expected=$1
    relative=$2
    case "$relative" in
        /*|*..*) printf 'Unsafe Maven input path: %s\n' "$relative" >&2; return 1 ;;
    esac
    destination="$repository/$relative"
    if [ -f "$destination" ] && printf '%s  %s\n' "$expected" "$destination" | sha256sum -c - >/dev/null 2>&1; then
        return
    fi
    mkdir -p "$(dirname "$destination")"
    if [ -n "${SEED_MAVEN_REPO:-}" ] && [ -f "$SEED_MAVEN_REPO/$relative" ]; then
        cp "$SEED_MAVEN_REPO/$relative" "$destination.partial"
    else
        curl --fail --location --silent --show-error --retry 3 \
            "https://repo.maven.apache.org/maven2/$relative" --output "$destination.partial"
    fi
    printf '%s  %s\n' "$expected" "$destination.partial" | sha256sum -c - >/dev/null
    mv "$destination.partial" "$destination"
}

if [ "${1:-}" = '--one' ]; then
    fetch_one "$2" "$3"
else
    # A newline-normalized lock also works when a recipe is mounted from Windows.
    tr -d '\r' < /recipe/inputs.sha256 | xargs -P 6 -n 2 sh /recipe/fetch-inputs.sh --one
    cd "$repository"
    tr -d '\r' < /recipe/inputs.sha256 | sha256sum -c - >/dev/null
fi
