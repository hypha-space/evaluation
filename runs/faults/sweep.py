#!/usr/bin/env -S uv run
# /// script
# dependencies = [
# ]
# ///

import itertools
import os
import random
import shlex
import subprocess
from typing import Iterable, List, Optional, Sequence

# This script is used to setup the environment for the
# experiments and start the experiment using zellij.

def run(cmd: Sequence[str], dry_run: bool, env=None):
    print(f"[cmd] {' '.join(shlex.quote(part) for part in cmd)}")
    if dry_run:
        return

    subprocess.run(cmd, check=True, env=env)

if __name__ == "__main__":
    dry_run = False

    network_delays = [(10,20), (40,100)]
    network_bandwidths = [100, 200, 300]
    worker_faults  = [0, 1, 3]

    # Min/max network delays
    targeted_network_delays = [(40, 100),(80, 200)]
    # Spike prob percent + multiplier
    targeted_network_spikes = [(10, 4), (20, 4)]
    # Loss prob percent
    targeted_network_losses = [1, 2, 3,]
    # Bandwidth in kbps
    targeted_network_bandwidths = [100, 200, 300]
    # worker name + port
    workers = [("worker1",58041), ("worker2", 58042), ("worker3", 58043), ("worker4", 58044), ("worker5", 58045), ("worker6", 58046), ("worker7", 58047), ("worker8", 58048), ("worker9", 58049), ("worker10", 58050)]


    # Build target list
    targets = []
    for l in [0, 3, 5, 7]:
        targets.append([w[0] for w in random.sample(workers, k=l+1)])

    for (faults,  delays, bandwidths, targeted_delays,    targeted_spikes,    targeted_losses,    targeted_bandwidths, targets) in random.sample(list(itertools.product(worker_faults, network_delays, network_bandwidths, targeted_network_delays, targeted_network_spikes, targeted_network_losses, targeted_network_bandwidths, targets)), k=10):
        service_namespace = f"r600w4p2_f{faults}_d{'_'.join([str(d) for d in delays])}b{bandwidths}l1td{'_'.join([str(d) for d in targeted_delays])}ts{'_'.join([str(s) for s in targeted_spikes])}tl{int(targeted_losses*100)}_tb{targeted_bandwidths}_{'_'.join(targets)}"

        env = os.environ.copy()

        if env.get("OTEL_RESOURCE_ATTRIBUTES"):
            env["OTEL_RESOURCE_ATTRIBUTES"] = f"{env['OTEL_RESOURCE_ATTRIBUTES']},service.namespace={service_namespace}"
        else:
            env["OTEL_RESOURCE_ATTRIBUTES"] = f"service.namespace={service_namespace}"

        for worker in workers:
            prefix = worker[0].upper()

            env[f"{prefix}_FAULT_PROB_PERCENT"] = str(faults)
            env[f"{prefix}_PORT"] = str(worker[1])

            if worker[0] in targets:
                env[f"{prefix}_MIN_DELAY"] = str(targeted_delays[0])
                env[f"{prefix}_MAX_DELAY"] = str(targeted_delays[1])
                env[f"{prefix}_SPIKE_PROB_PERCENT"] = str(targeted_spikes[0])
                env[f"{prefix}_SPIKE_MULT"] = str(targeted_spikes[1])
                env[f"{prefix}_BANDWIDTH"] = str(targeted_bandwidths * 1000)
                env[f"{prefix}_LOSS"] = str(targeted_losses)
            else:
                env[f"{prefix}_MIN_DELAY"] = str(delays[0])
                env[f"{prefix}_MAX_DELAY"] = str(delays[1])
                env[f"{prefix}_SPIKE_PROB_PERCENT"] = "0"
                env[f"{prefix}_SPIKE_MULT"] = "0"
                env[f"{prefix}_BANDWIDTH"] = str(bandwidths * 1000)
                env[f"{prefix}_LOSS"] = "0"

        input(f"Press Enter to start {service_namespace} ... ")
        run(["zellij", "--layout", "run.zellij.kdl"], dry_run, env=env)
