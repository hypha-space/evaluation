#!/usr/bin/env bash
set -euo pipefail

child_pid=""

# Kill probability (percentage) per check
KILL_PROB_PERCENT=${KILL_PROB_PERCENT:-5}
CHECK_INTERVAL_MIN=${CHECK_INTERVAL_MIN:-10}
CHECK_INTERVAL_MAX=${CHECK_INTERVAL_MAX:-20}
DEAD_TIME_MIN=${DEAD_TIME_MIN:-10}
DEAD_TIME_MAX=${DEAD_TIME_MAX:-30}

usage() {
  echo "Usage: $0 [options] -- <command> [args...]"
  echo "Options:"
  echo "  --kill-prob-percent N     Kill probability per check (default 5)"
  echo "  --check-interval-min N    Minimum seconds between checks (default 10)"
  echo "  --check-interval-max N    Maximum seconds between checks (default 20)"
  echo "  --dead-time-min N         Minimum seconds to wait before restart (default 10)"
  echo "  --dead-time-max N         Maximum seconds to wait before restart (default 30)"
  echo "  -h, --help                Show this help"
  echo "Env overrides: KILL_PROB_PERCENT, CHECK_INTERVAL_MIN, CHECK_INTERVAL_MAX, DEAD_TIME_MIN, DEAD_TIME_MAX"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kill-prob-percent)
      KILL_PROB_PERCENT="$2"
      shift 2
      ;;
    --check-interval-min)
      CHECK_INTERVAL_MIN="$2"
      shift 2
      ;;
    --check-interval-max)
      CHECK_INTERVAL_MAX="$2"
      shift 2
      ;;
    --dead-time-min)
      DEAD_TIME_MIN="$2"
      shift 2
      ;;
    --dead-time-max)
      DEAD_TIME_MAX="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 1
fi

# Basic sanity to avoid zero-length waits
if (( CHECK_INTERVAL_MIN < 1 )); then CHECK_INTERVAL_MIN=1; fi
if (( CHECK_INTERVAL_MAX < CHECK_INTERVAL_MIN )); then CHECK_INTERVAL_MAX=$CHECK_INTERVAL_MIN; fi
if (( DEAD_TIME_MIN < 1 )); then DEAD_TIME_MIN=1; fi
if (( DEAD_TIME_MAX < DEAD_TIME_MIN )); then DEAD_TIME_MAX=$DEAD_TIME_MIN; fi

cleanup() {
  if [[ -n "${child_pid}" ]] && kill -0 "${child_pid}" 2>/dev/null; then
    kill "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

run_command() {
  "$@" &
  child_pid=$!
}

while true; do
  run_command "$@"

  while kill -0 "${child_pid}" 2>/dev/null; do
    sleep $((CHECK_INTERVAL_MIN + RANDOM % (CHECK_INTERVAL_MAX - CHECK_INTERVAL_MIN + 1)))
    if (( RANDOM % 100 < KILL_PROB_PERCENT )); then
      echo -e "[flaky] \033[0;31mKilling process ${child_pid}\033[0m" >&2
      kill "${child_pid}" 2>/dev/null || true
      wait "${child_pid}" 2>/dev/null || true
      child_pid=""
      delay=$((DEAD_TIME_MIN + RANDOM % (DEAD_TIME_MAX - DEAD_TIME_MIN + 1)))

      echo -e "[flaky] \033[0;34mSleeping ${delay}s before restart\033[0m " >&2
      sleep $delay

      continue 2
    fi
  done

  set +e
  wait "${child_pid}"
  exit_code=$?
  set -e

  child_pid=""
  exit "${exit_code}"
done
