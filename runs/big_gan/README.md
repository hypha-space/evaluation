# BigGAN


## Parameters

```toml
[scheduler.job.rounds]
# Total data points 585 files * 2048 | 1 batch = 1 file => 585/50 = 11.7 rounds to process all files once. Target 1e5 batches / 50 = 2,000
avg_samples_between_updates = 100
update_rounds = 500
max_batch_size=1
multi_batch_size = 5

[scheduler.job.inner_optimizer]
learning-rate = 0.001

[scheduler.job.outer_optimizer]
learning-rate = 0.7
momentum = 0.3
```

## PeerIDs

Gateway:   `12D3KooWSEQccCzm1WERGRHyfbEdD7fJBZkv4bnMPMPJf1eWYM6z`
Scheduler: `12D3KooWCbybUXB3btxCmPiuZ3gXoCSTC7gxhgq8wEj3AGhAjfvX`
Data1:     `12D3KooWKj7Qh4bkVjLKZqtjNxQgMCMGQKrU5jh4oUGai1dweKwv`
Worker 1:  `12D3KooWJwrPRX5GsoBV9HdHr7oXawBK5tgCFXkiu4L1dWyh9c4G`
Worker 2:  `2D3KooWRXmTacGaSyUZEGJJuSDPvWr1JQBRCf3zsWRVHTJkjsBr`
Worker 4:  `12D3KooWB9JZvpsU7u1Mxf1STyC9TYnYe4BjtKfSkPsXUvwBsHGR`
Worker 5:  `2D3KooWMALzU4wuci6PUJ9MGbFWDWUTBHeKLWekFLRMYGhwswi8`
Worker 6:  `12D3KooWEtNTTuDa9bYLyYqcmd89tdraDxRGZVz6GRY5Zci7uuzy`
Worker 8:  `12D3KooWCrsm9LonCnLLWQwoM2eMWMqneuwMXTUtcmyxPLmYhp6Y`


## Setup

- Gateway: AWS, EU / Frankfurt (eu-central-1), t3.micro,2 vCPUs, 1024MiB Mem, 8GB Storage, 0.064 Gigabit
- Worker 6: Hetzner, Deutschland, Falkenstein, 4 vCPUs, 1024 GB Disk, 64 GB RAM, 1Gbps
- Worker 1: AWS, EU / Frankfurt (eu-central-1), g6e.xlarg, L40s GPU, 4 vCPUs, 32 RAM, 250GB Disk, Up to 20 Gbps
- Worker 2: AWS, EU / Frankfurt (eu-central-1), g6e.xlarg, L40s GPU, 4 vCPUs, 32 RAM, 250GB Disk, Up to 20 Gbps
- Worker 4: AWS, EU / Frankfurt (eu-central-1), g6e.xlarg, L40s GPU, 4 vCPUs, 32 RAM, 250GB Disk, Up to 20 Gbps
- Worker 5: AWS, EU / Frankfurt (eu-central-1), g6e.xlarg, L40s GPU, 4 vCPUs, 32 RAM, 250GB Disk, Up to 20 Gbps
- Worker 8: Runpod, EU, RTX A40,  48GB VRAM, 50GB RAM, 9vCPUs, 120GB Disk
- Worker 7: Yorizon, Wien, NVIDIA B200 183359MiB GPU, 3.0Ti Mem, 256 (26x AMD EPYC 9575F 64-Core) CPUs
- Worker 9: Yorizon, Wien, NVIDIA B200 183359MiB GPU, 3.0Ti Mem, 256 (26x AMD EPYC 9575F 64-Core) CPUs
- Worker 10: Yorizon, Wien, NVIDIA B200 183359MiB GPU, 3.0Ti Mem, 256 (26x AMD EPYC 9575F 64-Core) CPUs


