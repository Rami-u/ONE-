# Concurrency benchmark — 2026-10-22

- CPU: 13th Gen Intel(R) Core(TM) i7-13650HX
- Logical CPUs: 20
- Input: `evaluation\clips\clip_01_normal.mp4`
- Unique clip frames decoded: 14
- JPEG frames measured after repeat: 70

| Mode | Throughput (frames/s) | Wall time (s) |
|---|---:|---:|
| 1 thread | 385.000 | 0.182 |
| 4 threads | 609.769 | 0.115 |
| 4 processes | 377.669 | 0.185 |

The `FrameWorker` uses four processes so each worker owns an independent landmarker instance. On this run, four threads were faster than four processes; the small, repeated single-clip sample is not enough to generalize that result.

Limitations: only 14 unique frames from one short normal clip were available; those frames were repeated to reach 70 measurements. Treat these results as a local smoke benchmark, not production capacity evidence.
