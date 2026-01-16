# GPT-Neo

## PeerIDs

Gateway:   `12D3KooWSEQccCzm1WERGRHyfbEdD7fJBZkv4bnMPMPJf1eWYM6z`
Scheduler: `12D3KooWCbybUXB3btxCmPiuZ3gXoCSTC7gxhgq8wEj3AGhAjfvX`
Data1:     `12D3KooWKj7Qh4bkVjLKZqtjNxQgMCMGQKrU5jh4oUGai1dweKwv`
Worker 1:  `12D3KooWJwrPRX5GsoBV9HdHr7oXawBK5tgCFXkiu4L1dWyh9c4G`
Worker 2:  `2D3KooWRXmTacGaSyUZEGJJuSDPvWr1JQBRCf3zsWRVHTJkjsBr`
Worker 3:  `12D3KooWLVzxJpWyXkkf2LQQyLKNcdNd8nhZ3FwwLsa3diSGC4WB`
Worker 4:   `12D3KooWB9JZvpsU7u1Mxf1STyC9TYnYe4BjtKfSkPsXUvwBsHGR`
Worker 5:  `2D3KooWMALzU4wuci6PUJ9MGbFWDWUTBHeKLWekFLRMYGhwswi8`
Worker 6:  `12D3KooWEtNTTuDa9bYLyYqcmd89tdraDxRGZVz6GRY5Zci7uuzy`

## Params

Hypha: 869e88924327cdd917b3814a387448230e55ae82

```toml
[scheduler.job.rounds]
# Total data points 1.170.159
avg_samples_between_updates = 10000
update_rounds = 12600 # 3600
max_batch_size=80
multi_batch_size=10

[scheduler.job.inner_optimizer]
learning-rate = 0.00001

[scheduler.job.outer_optimizer]
learning-rate = 0.05
momentum = 0.9
```

## Setup

t3.micro

- Gateway, AWS, EU / Frankfurt (eu-central-1), t3.micro,2 vCPUs, 1024MiB Mem, 8GB Storage, 0.064 Gigabit
- Worker1, AWS, EU / Frankfurt (eu-central-1), g6e.xlarge, L40S 46068MiB (nvidia-smi) 45776MiB (aws describe-instance) GPU, 4 vCPUs, 32768MiB Mem, 300GB Storage, 2.5 Gigabit
- Worker3, Hetzner, EU, Nuremberg, cx53, 16 vCPUs, 32 GB Mem, 320 GB Storage,
- Worker4: AMD Developer Cloud (Digital Ocean), US / Atlanta,  MI300X Droplet,  MI300X 192 GB GPU, 240 GiB Mem, 720 GiB + 5 TiB Scratch Storage
- Worker2: Yorizon, Wien, NVIDIA B200 183359MiB GPU, 3.0Ti Mem, 256 (26x AMD EPYC 9575F 64-Core) CPUs
