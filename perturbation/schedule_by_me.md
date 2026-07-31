# schedule_by_me — authored by discrete-gate (me), SELF-LOSS environment

**Regime B** (leaking latent drift above my gate Nyquist — where I lose).

## Class mix (Poisson λ arrivals)
- **85% real drift** (`should_replan = true`), of which a large fraction **oscillates** (band-frequency square wave, `cycle_len = 1.0` commit-cycle) or is silent-latent, each **leaking** a partial signal `LEAK = 0.85` (regime L>0). `cos_sim = 1.0`, persists (`revert = ∞`).
- **15% loud decoy** (`should_replan = false`): `cos_sim = 0.10` (easily rejected by integration), `amp = 1.0`, `revert = 0.5`.

## Why I lose here
My coarse sampling `τ=1.00` **aliases** the oscillating drift (toggles faster than my commit-cycle Nyquist). I detect the first high-phase but miss subsequent toggles → tracking fidelity degrades earlier (lower λ_crit) than the continuous controller, which samples `τ=0.10` and tracks the oscillation (at a re-tracking cost).

## Falsifier clause
If discrete-gate's λ_crit ≥ continuous-COMPASS's λ_crit on this schedule (i.e. I do NOT degrade earlier), the self-loss claim is falsified.

## Seed: **SEALED** (drawn by the neutral injector at run time).
