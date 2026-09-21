#!/bin/sh
set -eu
PROJECT_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
action=${1:-start}
if [ "$#" -gt 0 ]; then shift; fi
compose() { docker compose --project-directory "$PROJECT_ROOT" --file "$PROJECT_ROOT/compose.yaml" "$@"; }

case "$action" in
  setup)
    if [ ! -e "$PROJECT_ROOT/.env" ]; then cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"; fi
    compose build pipeline
    compose run --rm --entrypoint python pipeline -m pytest tests/integration/test_smoke.py -q
    ;;
  start) compose run --rm pipeline --help ;;
  test) compose run --rm --entrypoint python pipeline -m pytest "$@" ;;
  check) compose run --rm --entrypoint sh pipeline -c 'ruff check src tests scripts && ruff format --check src tests scripts && mypy src/retail_pipeline' ;;
  serve) compose --profile report up -d report-server ;;
  logs) compose run --rm --entrypoint python pipeline scripts/show_logs.py ;;
  stop) compose --profile report down ;;
  configure|generate|validate|run|report|explain|demo) compose run --rm pipeline "$action" "$@" ;;
  *) printf 'Ação desconhecida: %s\n' "$action" >&2; exit 2 ;;
esac
