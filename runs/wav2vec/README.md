# Wav2Vec

## HyperParameters

Hypha: 4ba6b0ef95a4c1677f3e04013ab8df92b920ffa9

```toml
[scheduler.job.rounds]
# Steps per epoch 28 * 30 = 840 // 280 with 100 samples each / 1000 for updates
avg_samples_between_updates = 1000
update_rounds = 840 # 3600
max_batch_size=100
multi_batch_size = 6

[scheduler.job.inner_optimizer]
learning-rate = 1e-4


[scheduler.job.outer_optimizer]
learning-rate = 1.0
momentum = 0.0
```

## Default Setup

- Gateway, AWS, EU / Frankfurt (eu-central-1), t3.micro,2 vCPUs, 1024MiB Mem, 8GB Storage, 0.064 Gigabit
- Hetzner, Deutschland, Falkenstein, 4 vCPUs, 1024 GB Disk, 64 GB RAM, 1Gbps
- Worker1, AWS, EU / Frankfurt (eu-central-1), t2.xlarge, 4, 16GiB,  40GB, 
- Worker2: Yorizon, Wien, NVIDIA B200 183359MiB GPU, 3.0Ti Mem, 256 (26x AMD EPYC 9575F 64-Core) CPUs
- Worker4: AMD Developer Cloud (Digital Ocean), US / Atlanta,  MI300X Droplet,  MI300X 192 GB GPU, 240 GiB Mem, 720 GiB + 5 TiB Scratch Storage
