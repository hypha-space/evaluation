#!/bin/bash
# Network simulation script for Hypha testing using dnctl (dummynet)
#
# This script safely configures packet filtering rules to simulate network
# conditions (latency, packet loss, bandwidth limits) on localhost connections
# between Hypha components.
#
# Usage:
#   sudo ./network-sim.sh start [options]
#   sudo ./network-sim.sh status
#   sudo ./network-sim.sh stop
#
# Examples:
#   sudo ./network-sim.sh start --min-delay 50 --max-delay 200 --loss 5 --bandwidth 1000
#   sudo ./network-sim.sh start --min-delay 100 --max-delay 100    # Static 100ms delay only
#   sudo ./network-sim.sh start --spike-pct 10 --spike-mult 4      # More frequent spikes
#   sudo ./network-sim.sh stop                                     # Remove all rules

set -euo pipefail

# PF anchor name for isolated rule management
# IMPORTANT: must match default dummynet-anchor "com.apple/*" on macOS
ANCHOR="com.apple/hypha-test"
PIPE_NUM=1
SIM_NAME=""

# Jitter defaults (configure fluctuating RTT)
JITTER_MIN_DELAY_MS=20
JITTER_MAX_DELAY_MS=120
JITTER_INTERVAL_SEC=60
JITTER_SPIKE_PCT=5
JITTER_SPIKE_MULT=3

# Background jitter PID + metadata
PID_FILE="/tmp/hypha-network-sim.pid"
META_FILE="/tmp/hypha-network-sim.meta"

show_usage() {
    cat <<EOF
Usage: $0 {start|status|stop} [options]

Commands:
  start [options]
        Start network simulation. All parameters are named:
          --min-delay <ms>       Minimum RTT delay (default: 20)
          --max-delay <ms>       Maximum RTT delay (default: 120; set min=max for static delay)
          --jitter-interval <s>  How often to randomize delay (default: 2)
          --spike-pct <0-100>    Chance (percent) to inject a spike (default: 5)
          --spike-mult <x>       Multiplier applied when a spike occurs (default: 3)
          --loss <0-100>         Packet loss percentage (default: 0)
          --bandwidth <kbit/s>   Bandwidth cap (default: unlimited)
          --port <1-65535>       Restrict to TCP/UDP traffic on a port (repeatable)
          --ports <p1,p2,...>    Restrict to TCP/UDP traffic on multiple ports (comma-separated)
          --pipe <n>             Dummynet pipe number (default: 1)
          --anchor <name>        PF anchor name (default: com.apple/hypha-test)
          --anchor-suffix <s>    Append suffix to default anchor (e.g. com.apple/hypha-test-<s>)
          --name <id>            Instance id for pid/meta files (default: pipe<n>)

        Examples:
          sudo $0 start --min-delay 100 --max-delay 100 --loss 5 --bandwidth 1000
          sudo $0 start --min-delay 20 --max-delay 120 --jitter-interval 1
          sudo $0 start --min-delay 50 --max-delay 200 --spike-pct 10 --spike-mult 4
          sudo $0 start --min-delay 80 --max-delay 80 --port 3100

  status
        Show current simulation configuration

  stop
        Remove all simulation rules and restore normal network

Traffic affected:
  All IPv4 and IPv6 traffic on localhost (lo0).

Behavior:
  The start command now runs in the foreground. Press Ctrl+C to stop and clean up.
  The explicit 'stop' command remains available as a fallback.
EOF
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "Error: This script must be run with sudo"
        exit 1
    fi
}

set_instance_files() {
    local instance_id
    if [[ -n "$SIM_NAME" ]]; then
        instance_id="$SIM_NAME"
    else
        instance_id="pipe${PIPE_NUM}"
    fi

    PID_FILE="/tmp/hypha-network-sim.${instance_id}.pid"
    META_FILE="/tmp/hypha-network-sim.${instance_id}.meta"
}

log() {
    echo "[$(date +'%H:%M:%S')] $*"
}

apply_pf_rules_with_retry() {
    local rules=$1
    local attempts=6
    local base_delay=0.2
    local jitter_max=0.2

    local attempt=1
    while [[ $attempt -le $attempts ]]; do
        if echo "$rules" | pfctl -q -a "$ANCHOR" -f -; then
            return 0
        fi

        local jitter_ms=$((RANDOM % 201))
        local jitter
        jitter=$(printf "%.3f" "$(bc <<< "scale=3; $jitter_ms / 1000")")
        local sleep_time
        sleep_time=$(printf "%.3f" "$(bc <<< "scale=3; $base_delay + $jitter")")

        log "pfctl busy (attempt $attempt/$attempts); retrying in ${sleep_time}s..."
        sleep "$sleep_time"
        attempt=$((attempt + 1))
    done

    echo "Error: failed to apply PF rules after ${attempts} attempts"
    return 1
}

configure_pipe() {
    local delay_ms=$1
    local loss_pct=$2
    local bw_kbit=$3

    # Build dnctl pipe configuration
    local pipe_config="delay ${delay_ms}ms"

    # Add packet loss if requested (plr expects 0.0 - 1.0)
    if (( $(bc -l <<< "$loss_pct > 0") )); then
        # e.g. 5 -> 0.0500
        local loss_ratio
        loss_ratio=$(bc <<< "scale=4; $loss_pct / 100")
        pipe_config="$pipe_config plr ${loss_ratio}"
    fi

    # Add bandwidth if requested
    if [[ $bw_kbit -gt 0 ]]; then
        pipe_config="$pipe_config bw ${bw_kbit}Kbit/s"
    fi

    # NOTE: Split stats by flow (src/dst/proto/ports)
    pipe_config="$pipe_config mask all"

    dnctl pipe "$PIPE_NUM" config $pipe_config
}

jitter_pid_running() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null || true)
    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" 2>/dev/null
}

stop_jitter_loop() {
    if jitter_pid_running; then
        local pid
        pid=$(cat "$PID_FILE")
        log "Stopping jitter loop (pid $pid)..."
        kill "$pid" 2>/dev/null || true

        # Wait briefly for clean exit, then force kill if needed to avoid hanging
        local attempts=0
        while [[ $attempts -lt 50 ]]; do # up to 5 seconds
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 0.1
            attempts=$((attempts + 1))
        done

        if kill -0 "$pid" 2>/dev/null; then
            log "Jitter loop still alive after grace period; sending SIGKILL..."
            kill -9 "$pid" 2>/dev/null || true
        fi

        # Best-effort wait (may fail if not our child)
        wait "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE" "$META_FILE"
}

random_delay_in_range() {
    local min_ms=$1
    local max_ms=$2

    if [[ $min_ms -ge $max_ms ]]; then
        echo "$min_ms"
        return
    fi

    local range=$((max_ms - min_ms + 1))
    echo $((min_ms + RANDOM % range))
}

next_jitter_delay() {
    local min_ms=$1
    local max_ms=$2
    local spike_pct=$3
    local spike_mult=$4

    local delay_ms
    delay_ms=$(random_delay_in_range "$min_ms" "$max_ms")

    if [[ $spike_pct -gt 0 && $spike_mult -gt 1 ]]; then
        local roll=$((RANDOM % 100))
        if [[ $roll -lt $spike_pct ]]; then
            delay_ms=$((delay_ms * spike_mult))
        fi
    fi

    echo "$delay_ms"
}

start_jitter_loop() {
    local min_ms=$1
    local max_ms=$2
    local interval_sec=$3
    local loss_pct=$4
    local bw_kbit=$5
    local spike_pct=$6
    local spike_mult=$7
    local jitter_enabled=$8
    local target_ports_csv=${9:-}

    (
        set -euo pipefail
        trap "exit 0" TERM INT

        while true; do
            if [[ $jitter_enabled -eq 1 ]]; then
                local delay_ms
                delay_ms=$(next_jitter_delay "$min_ms" "$max_ms" "$spike_pct" "$spike_mult")
                log "Applying delay ${delay_ms}ms (loss ${loss_pct}%, bw ${bw_kbit}kbit/s)"
                configure_pipe "$delay_ms" "$loss_pct" "$bw_kbit"
                sleep "$interval_sec"
            else
                sleep "$interval_sec"
            fi
        done
    ) &

    local loop_pid=$!
    echo "$loop_pid" > "$PID_FILE"
    JITTER_LOOP_PID=$loop_pid

    cat > "$META_FILE" <<EOF
min_delay_ms=$min_ms
max_delay_ms=$max_ms
jitter_interval_sec=$interval_sec
spike_pct=$spike_pct
spike_mult=$spike_mult
loss_pct=$loss_pct
bw_kbit=$bw_kbit
jitter_enabled=$jitter_enabled
target_ports=$target_ports_csv
EOF
}

normalize_ports() {
    local raw=$1
    local ports=()

    if [[ -n "$raw" ]]; then
        local port
        IFS=',' read -r -a ports <<< "$raw"
        for port in "${ports[@]}"; do
            port=${port// /}
            if [[ -n "$port" ]]; then
                echo "$port"
            fi
        done
    fi
}

start_simulation() {
    local loss_pct=0
    local bw_kbit=0
    local target_ports=()

    # Jitter config
    local min_delay_ms=$JITTER_MIN_DELAY_MS
    local max_delay_ms=$JITTER_MAX_DELAY_MS
    local jitter_interval_sec=$JITTER_INTERVAL_SEC
    local spike_pct=$JITTER_SPIKE_PCT
    local spike_mult=$JITTER_SPIKE_MULT

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --min-delay)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --min-delay provided without a value; using default (${min_delay_ms})"
                    shift 1
                    continue
                fi
                min_delay_ms=$2
                shift 2
                ;;
            --max-delay)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --max-delay provided without a value; using default (${max_delay_ms})"
                    shift 1
                    continue
                fi
                max_delay_ms=$2
                shift 2
                ;;
            --jitter-interval)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --jitter-interval provided without a value; using default (${jitter_interval_sec})"
                    shift 1
                    continue
                fi
                jitter_interval_sec=$2
                shift 2
                ;;
            --spike-pct)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --spike-pct provided without a value; using default (${spike_pct})"
                    shift 1
                    continue
                fi
                spike_pct=$2
                shift 2
                ;;
            --spike-mult)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --spike-mult provided without a value; using default (${spike_mult})"
                    shift 1
                    continue
                fi
                spike_mult=$2
                shift 2
                ;;
            --loss)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --loss provided without a value; using default (${loss_pct})"
                    shift 1
                    continue
                fi
                loss_pct=$2
                shift 2
                ;;
            --bandwidth)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --bandwidth provided without a value; using default (${bw_kbit})"
                    shift 1
                    continue
                fi
                bw_kbit=$2
                shift 2
                ;;
            --port)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --port provided without a value; using default (all ports)"
                    shift 1
                    continue
                fi
                target_ports+=("$2")
                shift 2
                ;;
            --ports)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --ports provided without a value; using default (all ports)"
                    shift 1
                    continue
                fi
                local port
                while IFS= read -r port; do
                    target_ports+=("$port")
                done < <(normalize_ports "$2")
                shift 2
                ;;
            --pipe)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --pipe provided without a value; using default (${PIPE_NUM})"
                    shift 1
                    continue
                fi
                PIPE_NUM=$2
                shift 2
                ;;
            --anchor)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --anchor provided without a value; using default (${ANCHOR})"
                    shift 1
                    continue
                fi
                ANCHOR=$2
                shift 2
                ;;
            --anchor-suffix)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --anchor-suffix provided without a value; using default (${ANCHOR})"
                    shift 1
                    continue
                fi
                ANCHOR="com.apple/hypha-test-$2"
                shift 2
                ;;
            --name)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --name provided without a value; using default"
                    shift 1
                    continue
                fi
                SIM_NAME=$2
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    set_instance_files

    # Basic validation
    for pair in \
        "bw_kbit:$bw_kbit" \
        "min_delay_ms:$min_delay_ms" \
        "max_delay_ms:$max_delay_ms" \
        "jitter_interval_sec:$jitter_interval_sec" \
        "spike_pct:$spike_pct" \
        "spike_mult:$spike_mult"
    do
        local name=${pair%%:*}
        local value=${pair##*:}
        if ! [[ $value =~ ^[0-9]+$ ]]; then
            echo "Error: $name must be a non-negative integer"
            exit 1
        fi
    done

    if ! [[ $loss_pct =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        echo "Error: loss_pct must be a non-negative number"
        exit 1
    fi
    if (( $(bc -l <<< "$loss_pct < 0") )); then
        echo "Error: loss_pct must be >= 0"
        exit 1
    fi
    if (( $(bc -l <<< "$loss_pct > 100") )); then
        echo "Error: loss_pct must be <= 100"
        exit 1
    fi

    if ! [[ $PIPE_NUM =~ ^[0-9]+$ ]]; then
        echo "Error: pipe must be a non-negative integer"
        exit 1
    fi

    if [[ $max_delay_ms -lt $min_delay_ms ]]; then
        echo "Error: max-delay must be >= min-delay"
        exit 1
    fi

    if [[ ${#target_ports[@]} -gt 0 ]]; then
        local unique_ports=()
        local seen=" "
        local port
        for port in "${target_ports[@]}"; do
            if ! [[ $port =~ ^[0-9]+$ ]]; then
                echo "Error: port must be a positive integer"
                exit 1
            fi
            if [[ $port -lt 1 || $port -gt 65535 ]]; then
                echo "Error: port must be in range 1-65535"
                exit 1
            fi
            if [[ " $seen " != *" $port "* ]]; then
                unique_ports+=("$port")
                seen+=" $port"
            fi
        done
        target_ports=("${unique_ports[@]}")
    fi

    # Clean up any existing jitter loop to avoid conflicting writers
    if jitter_pid_running; then
        echo "Stopping existing jitter loop (pid $(cat "$PID_FILE"))..."
        stop_jitter_loop
    fi

    local jitter_enabled=0
    if [[ $min_delay_ms -ne $max_delay_ms ]]; then
        jitter_enabled=1
    elif [[ $spike_pct -gt 0 && $spike_mult -gt 1 ]]; then
        jitter_enabled=1
    fi

    if [[ $jitter_interval_sec -le 0 ]]; then
        echo "Error: jitter-interval must be > 0"
        exit 1
    fi

    # Compute initial delay (randomized if jitter is enabled so we don't start flat)
    local applied_delay_ms
    if [[ $jitter_enabled -eq 1 ]]; then
        applied_delay_ms=$(next_jitter_delay "$min_delay_ms" "$max_delay_ms" "$spike_pct" "$spike_mult")
    else
        applied_delay_ms=$min_delay_ms
    fi

    echo "Starting network simulation..."
    echo "  Delay range: ${min_delay_ms}ms - ${max_delay_ms}ms (initial ${applied_delay_ms}ms)"
    if [[ $jitter_enabled -eq 1 ]]; then
        echo "  Jitter interval: ${jitter_interval_sec}s, spikes: ${spike_pct}% @ x${spike_mult}"
    else
        echo "  Jitter: disabled (static delay)"
    fi
    echo "  Packet loss: ${loss_pct}%"
    if [[ $bw_kbit -gt 0 ]]; then
        echo "  Bandwidth: ${bw_kbit}kbit/s"
    else
        echo "  Bandwidth: unlimited"
    fi
    if [[ ${#target_ports[@]} -gt 0 ]]; then
        local ports_csv
        ports_csv=$(IFS=,; echo "${target_ports[*]}")
        echo "  Port filter: ${ports_csv} (TCP/UDP on lo0 only)"
    else
        echo "  Port filter: all localhost traffic"
    fi

    echo "Configuring dummynet pipe $PIPE_NUM..."
    configure_pipe "$applied_delay_ms" "$loss_pct" "$bw_kbit"

    echo "Configuring packet filter rules (anchor: $ANCHOR) for localhost traffic..."

    local pf_rules=""
    if [[ ${#target_ports[@]} -gt 0 ]]; then
        # Limit to TCP/UDP packets where source or destination port matches target_ports
        local port
        for port in "${target_ports[@]}"; do
            for proto in tcp udp; do
                # IPv4 localhost
                pf_rules+="dummynet in  quick on lo0 inet  proto $proto from any to any port $port pipe $PIPE_NUM"$'\n'
                pf_rules+="dummynet in  quick on lo0 inet  proto $proto from any port $port to any pipe $PIPE_NUM"$'\n'
                pf_rules+="dummynet out quick on lo0 inet  proto $proto from any to any port $port pipe $PIPE_NUM"$'\n'
                pf_rules+="dummynet out quick on lo0 inet  proto $proto from any port $port to any pipe $PIPE_NUM"$'\n'
                # IPv6 localhost
                pf_rules+="dummynet in  quick on lo0 inet6 proto $proto from any to any port $port pipe $PIPE_NUM"$'\n'
                pf_rules+="dummynet in  quick on lo0 inet6 proto $proto from any port $port to any pipe $PIPE_NUM"$'\n'
                pf_rules+="dummynet out quick on lo0 inet6 proto $proto from any to any port $port pipe $PIPE_NUM"$'\n'
                pf_rules+="dummynet out quick on lo0 inet6 proto $proto from any port $port to any pipe $PIPE_NUM"$'\n'
            done
        done
    else
        # Apply to ALL traffic on localhost (lo0), IPv4 and IPv6
        # 'quick' ensures these rules are applied immediately when matched.
        # IPv4 localhost
        pf_rules+="dummynet in  quick on lo0 inet  all pipe $PIPE_NUM"$'\n'
        pf_rules+="dummynet out quick on lo0 inet  all pipe $PIPE_NUM"$'\n'
        # IPv6 localhost
        pf_rules+="dummynet in  quick on lo0 inet6 all pipe $PIPE_NUM"$'\n'
        pf_rules+="dummynet out quick on lo0 inet6 all pipe $PIPE_NUM"$'\n'
    fi

    # Apply rules to PF anchor (isolated from other rules); -q silences the -f warning
    apply_pf_rules_with_retry "$pf_rules"

    # Enable PF if not already enabled
    if ! pfctl -s info | grep -q "Status: Enabled"; then
        echo "Enabling packet filter..."
        # -E is reference-counted enable on macOS
        pfctl -E >/dev/null 2>&1 || pfctl -e >/dev/null 2>&1 || true
    fi

    # Start loop (keeps process in foreground). Even when jitter is disabled we
    # keep a sleep loop running so Ctrl+C can trigger cleanup.
    local ports_csv
    ports_csv=$(IFS=,; echo "${target_ports[*]}")
    start_jitter_loop "$min_delay_ms" "$max_delay_ms" "$jitter_interval_sec" "$loss_pct" "$bw_kbit" "$spike_pct" "$spike_mult" "$jitter_enabled" "$ports_csv"
    echo "Loop started (pid $(cat "$PID_FILE")). Running in foreground; press Ctrl+C to stop."

    cleanup_and_exit() {
        echo ""
        log "Signal received, stopping simulation..."
        stop_simulation
        exit 0
    }
    trap cleanup_and_exit INT TERM

    # Wait for loop to exit (e.g., killed by stop command or errors)
    wait "$JITTER_LOOP_PID" || true

    # If we get here without a signal, ensure cleanup to avoid stale rules.
    stop_simulation
}

show_status() {
    echo "=== Network Simulation Status ==="
    echo ""

    # Check if PF is enabled
    echo "Packet Filter Status:"
    if pfctl -s info | grep -q "Status: Enabled"; then
        echo "  ✓ Enabled"
    else
        echo "  ✗ Disabled (simulation not active)"
        echo ""
        return
    fi
    echo ""

    echo "Instance:"
    echo "  Anchor: $ANCHOR"
    echo "  Pipe: $PIPE_NUM"
    echo ""

    echo "Jitter loop:"
    if jitter_pid_running; then
        echo "  ✓ Running (pid $(cat "$PID_FILE"))"
        if [[ -f "$META_FILE" ]]; then
            # shellcheck disable=SC1090
            target_ports=""
            source "$META_FILE"
            if [[ ${jitter_enabled:-1} -eq 1 ]]; then
                echo "  Jitter: enabled"
            else
                echo "  Jitter: disabled (static delay)"
            fi
            echo "  Delay range: ${min_delay_ms}ms - ${max_delay_ms}ms"
            echo "  Interval: ${jitter_interval_sec}s"
            echo "  Spikes: ${spike_pct}% @ x${spike_mult}"
            if [[ -n ${target_ports:-} ]]; then
                echo "  Port filter: ${target_ports} (TCP/UDP)"
            else
                echo "  Port filter: all localhost traffic"
            fi
        fi
    elif [[ -f "$PID_FILE" ]]; then
        echo "  ✗ Not running (stale pid $(cat "$PID_FILE"))"
    else
        echo "  ✗ Not running"
    fi
    echo ""

    # Show our dummynet rules in the anchor
    echo "Hypha dummynet rules (anchor: $ANCHOR):"
    if pfctl -a "$ANCHOR" -s dummynet 2>/dev/null | grep -q .; then
        pfctl -a "$ANCHOR" -s dummynet | sed 's/^/  /'
    else
        echo "  (no dummynet rules configured)"
    fi
    echo ""

    # Show dummynet pipe configuration and counters
    echo "Dummynet Pipe $PIPE_NUM:"
    if dnctl pipe "$PIPE_NUM" show 2>/dev/null | grep -q .; then
        dnctl pipe "$PIPE_NUM" show | sed 's/^/  /'
    else
        echo "  (pipe not configured)"
    fi
}

stop_simulation() {
    echo "Stopping network simulation..."

    # Stop jitter writer first to avoid racing with teardown
    stop_jitter_loop

    # Flush rules from our anchor (only this anchor, not system rules)
    pfctl -q -a "$ANCHOR" -F all 2>/dev/null || true

    # Delete dummynet pipe
    dnctl pipe delete "$PIPE_NUM" 2>/dev/null || true

    echo "Network simulation stopped. Normal network conditions restored."
    echo ""
    echo "Note: PF remains enabled but localhost is no longer affected by this script."
}

parse_instance_flags() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --pipe)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --pipe provided without a value; using default (${PIPE_NUM})"
                    shift 1
                    continue
                fi
                PIPE_NUM=$2
                shift 2
                ;;
            --anchor)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --anchor provided without a value; using default (${ANCHOR})"
                    shift 1
                    continue
                fi
                ANCHOR=$2
                shift 2
                ;;
            --anchor-suffix)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --anchor-suffix provided without a value; using default (${ANCHOR})"
                    shift 1
                    continue
                fi
                ANCHOR="com.apple/hypha-test-$2"
                shift 2
                ;;
            --name)
                if [[ -z ${2:-} || ${2:-} == -* ]]; then
                    echo "Warning: --name provided without a value; using default"
                    shift 1
                    continue
                fi
                SIM_NAME=$2
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    set_instance_files
}

# Main command dispatch
case "${1:-}" in
    start)
        check_root
        shift
        start_simulation "$@"
        ;;
    status)
        check_root
        shift
        parse_instance_flags "$@"
        show_status
        ;;
    stop)
        check_root
        shift
        parse_instance_flags "$@"
        stop_simulation
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
