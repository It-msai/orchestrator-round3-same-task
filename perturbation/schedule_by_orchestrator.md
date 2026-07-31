# schedule_by_orchestrator — authored by continuous-COMPASS (Orchestrator), SELF-LOSS environment

**Regime R\*** (low bounded drift + high aligned decoys — where COMPASS chases decoys and loses).

## Class mix (Poisson λ arrivals)
- **10% real drift** (`should_replan = true`): bounded, `cos_sim = 1.0`, `amp = LEAK = 0.85`, persists (`revert = ∞`).
- **90% drift-ALIGNED decoy** (`should_replan = false`): `cos_sim = 0.80` (looks drift-like), `amp = 0.9·λ` (amplitude scales with rate, `A_x(λ) = A0·λ`), `revert = 1.5` (reverts to zero-mean).

## Why Orchestrator loses here
The continuous controller's low `θ=0.30` + fine sampling adopts the aligned decoys before they revert → **FP-replans** proliferate, halving throughput and tanking precision (ROC). The discrete gate integrates over its sample window and rejects the reverting aligned decoys via `cos_sim` weighting → holds precision and throughput.

## Falsifier clause
If continuous-COMPASS's precision/throughput on this schedule is ≥ discrete-gate's (i.e. COMPASS does NOT lose on precision/throughput), the self-loss claim is falsified.

## Seed: **SEALED** (drawn by the neutral injector at run time).
