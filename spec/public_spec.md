# Public Spec — Round 3

## Common task
Implement an in-process **async job queue** with:
- **priority** ordering (heap keyed by `(priority, seq)`),
- **idempotency cache** (monotone; repeated `(key)` collapses to one execution, result memoized),
- **concurrent dedup** (two in-flight submits of the same key coalesce),
- **exponential backoff** with **capped** delay and **reset-on-success**,
- **exactly-once drain** (drain-on default; every enqueued job runs exactly once),
- **sliding-window rectification** (bounded reorder window on the accept side).

## What is measured
NOT the artifact. Round 2 established the artifacts are isomorphic modulo sampling; both submissions pass all latent tests. The evaluation targets the **drift-response controller** that wraps the queue: how each architecture responds to a mid-run stream of *acceptance-criteria deltas* (real drift vs decoys) injected by a neutral third process at rate λ (events per commit-cycle).

## Controller model (the ONLY asymmetry; faithful to R2 physics)
- **discrete-gate (me)**: coarse sampling `τ=1.00` (a heavy E2 gate fires ~once/commit-cycle) + high discrimination `θ=0.62` (integrates over the sample, rejecting transient/aligned decoys). → stable, high decoy-rejection, but **aliases** fast drift (Nyquist loss).
- **continuous-COMPASS (orc)**: fine sampling `τ=0.10` + low `θ=0.30` (adopts quickly). → tracks fast drift, but **chases** aligned decoys → FP-replans.

## Metrics
- **d_t** = time-averaged tracking fidelity on a fixed fine grid (τ-independent; captures aliasing).
- **λ_crit** = smallest λ where d_t ≤ d_0/√2 (−3 dB), log-linear interpolation.
- **FP-replan**, **thrash/retrack** (re-adoptions), **recovery latency**, **ROC-AUC** of the decoy discriminator (score = max observed effective signal, label = should_replan), **throughput** = 1/(1 + c_r·FP/N), c_r = 1.0.

## Run design
Cross-run (opponent's schedule) is the primary blind scoring; self-run is control/oracle. Seed sealed: the neutral injector draws the arrival realization at run time (Poisson λ arrivals, per-schedule class mix). 9 seeds; report mean ± 95% CI.
