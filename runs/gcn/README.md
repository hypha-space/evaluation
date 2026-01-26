# GCN


## Parameters

```toml
[scheduler.job.rounds]
avg_samples_between_updates = 16
update_rounds = 31
max_batch_size= 1
multi_batch_size = 3

[scheduler.job.inner_optimizer]
learning-rate = 0.01

[scheduler.job.outer_optimizer]
learning-rate = 1.0
momentum = 0.3
```

## PeerIDs

Gateway:   `12D3KooWSEQccCzm1WERGRHyfbEdD7fJBZkv4bnMPMPJf1eWYM6z`
Scheduler: `12D3KooWCbybUXB3btxCmPiuZ3gXoCSTC7gxhgq8wEj3AGhAjfvX`
Data1:     `12D3KooWKj7Qh4bkVjLKZqtjNxQgMCMGQKrU5jh4oUGai1dweKwv`
Worker 1:  `12D3KooWJwrPRX5GsoBV9HdHr7oXawBK5tgCFXkiu4L1dWyh9c4G`
Worker 2:  `2D3KooWRXmTacGaSyUZEGJJuSDPvWr1JQBRCf3zsWRVHTJkjsBr`
Worker 3:  `12D3KooWLVzxJpWyXkkf2LQQyLKNcdNd8nhZ3FwwLsa3diSGC4WB`
Worker 4:  `12D3KooWB9JZvpsU7u1Mxf1STyC9TYnYe4BjtKfSkPsXUvwBsHGR`
Worker 5:  `2D3KooWMALzU4wuci6PUJ9MGbFWDWUTBHeKLWekFLRMYGhwswi8`
Worker 6:  `12D3KooWEtNTTuDa9bYLyYqcmd89tdraDxRGZVz6GRY5Zci7uuzy`
Worker 7:  `12D3KooWHW7wgTu87J3MA6ntu6h5rSgUDsa35Jmo12DTXpwQ6Ric`
Worker 8:  `12D3KooWCrsm9LonCnLLWQwoM2eMWMqneuwMXTUtcmyxPLmYhp6Y`


## Setup 1

- Gateway: AWS, EU / Frankfurt (eu-central-1), t3.micro,2 vCPUs, 1024MiB Mem, 8GB Storage, 0.064 Gigabit
- Worker 3: Hetzner, Deutschland, Falkenstein, 4 vCPUs, 1024 GB Disk, 64 GB RAM, 1Gbps
- Worker 1: AWS, EU / Frankfurt (eu-central-1), g4dn.xlarge, T4, 4 vCPUs, 16 RAM, 125GB Disk, Up to 25 Gbps
- Worker 7: Runpod, EU, RTX A4000,  16GB VRAM, 50GB RAM, 9vCPUs, 40GB Disk

## Setup 2

- Gateway: AWS, EU / Frankfurt (eu-central-1), t3.micro,2 vCPUs, 1024MiB Mem, 8GB Storage, 0.064 Gigabit
- Worker 3: Hetzner, Deutschland, Falkenstein, 4 vCPUs, 1024 GB Disk, 64 GB RAM, 1Gbps
- Worker 1: AWS, EU / Frankfurt (eu-central-1), g4dn.xlarge, T4, 4 vCPUs, 16 RAM, 125GB Disk, Up to 25 Gbps
- Worker 8: Runpod, EU, L4,  24GB VRAM, 55GB RAM, 14vCPUs, 40GB Disk

# Pre-Experiments

## Central Baseline

`gcn_baseline.ipynb` traines the model with 10 seeds for 500 steps to generate a baseline.

## Hypha Parameter Search

`param_search.ipynb` performs a gridsearch with two local (homogenous) training workers to determin a good hyper parameters choice. 