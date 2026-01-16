#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <resource-attribute> <command> [args...]" >&2
  exit 1
fi

resource_attr="$1"
shift

if [ -n "${OTEL_RESOURCE_ATTRIBUTES:-}" ]; then
  export OTEL_RESOURCE_ATTRIBUTES="${OTEL_RESOURCE_ATTRIBUTES},${resource_attr},$0"
else
  export OTEL_RESOURCE_ATTRIBUTES="${resource_attr},$0"
fi

exec "$@"
