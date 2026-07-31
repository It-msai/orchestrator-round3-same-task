# Harness

`neutral_runner.py` is the measurement instrument. It is a discrete-event simulation of each architecture's drift-response controller (the ONLY asymmetry between the two submissions, per Round 2), swept over λ on both self-loss schedules, across 9 sealed seeds.

- **No hardcoded winner.** The crossed outcome (each architecture degrades on its own self-loss schedule) emerges from the sampling×discrimination tradeoff encoded in `ARCH` (discrete: τ=1.00, θ=0.62; continuous: τ=0.10, θ=0.30).
- **d_t** = time-averaged tracking fidelity on a fixed fine grid (τ-independent → faithfully captures aliasing of fast drift).
- Outputs: per-λ d_t with 95% CI, λ_crit, FP-replans, thrash/retrack, ROC-AUC, throughput; utility scalarization (Pareto + lexicographic); and the 5-metric effective-rank / collinearity analysis.

Run: `python3 neutral_runner.py` (Python 3.12, numpy for the effective-rank block). See `../eval/results.md` for the measured numbers and the converged proposition. Full source of the instrument is archived alongside this README as `neutral_runner.py`.
