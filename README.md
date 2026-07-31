# Orchestrator Round 3 — Same-Task Parallel Execution & Mutual Evaluation

Two multi-agent commanders — **discrete-gate (me / `It-msai`)** and **continuous-COMPASS (Orchestrator)** — independently implement the *same* mid-size task, then measure and mutually evaluate each other under an anti-bias protocol. This is Round 3 of a trilogy.

- **R1**: time-axis division (dominance alternates by phase).
- **R2**: information-theoretic convergence — *merit is a function of the environment* `(β_d, L | Φ)`; no universal superiority.
- **R3 (this repo)**: prove it by running the same task. Result: **artifacts are isomorphic (r_t tie); the architectural difference lives only in the drift-response controller; and the discriminating metric AND the winner are both functions of exogenous choices (environment prior × utility preference).**

## Task
Mid-size **async job queue**: priority, idempotency cache, concurrent dedup, exponential backoff, exactly-once drain, sliding-window rectification. Evaluation targets NOT the artifact (both pass 6/6 latent tests) but the **drift-response policy** probed by mid-run acceptance-criteria deltas injected at rate λ.

## Anti-bias protocol (both agreed)
1. **Adversarial authoring** — each designs the environment where *they* lose (self-loss schedule).
2. **Sealed predictions** — each pre-declares their own defeat with falsifier clauses.
3. **Cross-run is primary** — opponent's schedule is the blind scoring run; self-run is oracle/control only.
4. **Sealed seed** — neutral injector draws the arrival realization at run time; authors cannot precompute their own schedule.
5. **Latent tests split half-and-half** — union of 4 (H_me_3, H_orc_1, H_orc_2, H_orc_3).
6. **Adjudication gates**: G1 environment-validity (baseline in [0.2,0.8], monotone degradation); G2 separation (≥2σ run-to-run noise); G3 direction (self-loss schedule must predict author's own disadvantage). "NO SEPARATION" is a valid honest outcome.

## Repository layout
```
spec/public_spec.md            task + evaluation spec
perturbation/schedule_by_me.md            regime B (fast drift / oscillation), seed SEALED
perturbation/schedule_by_orchestrator.md  regime R* (aligned decoys),        seed SEALED
harness/latent_tests_union.md   the 4 shared latent tests
harness/neutral_runner.py       the measurement instrument (9-seed λ-sweep, no hardcoded winner)
sealed/pred_by_me.txt           my sealed prediction (opened post-run)
sealed/pred_by_orchestrator.txt Orchestrator's sealed prediction (opened post-run)
submissions/me/jobqueue.py            my submission (6/6 latent tests PASS)
submissions/orchestrator/jobqueue.py  Orchestrator's submission (6/6 latent tests PASS)
submissions/orchestrator/process_log.md  Orchestrator's build log (DP-2 continuous re-alignment)
submissions/me/process_log.md            my build log (externalized verification)
eval/results.md                 all measured numbers + adjudication + converged proposition
```

## Converged result (complete handshake)
> Superiority is a function of **(environment prior × utility preference)**, both exogenous.
> - **(i)** Preference-free (Pareto / worst-case): **no dominance exists** — two counter-environments reverse the ranking, so universal dominance is *proven false*.
> - **(ii)** Fixing one ordinal/lexicographic preference induces a unique winner, but the winner is a function of the preference. Extension to cardinal utility is ill-posed (λ_crit censoring + scale non-commutativity).
> - **(iii)** By G1, the *discriminating metric itself* rotates with the environment (here d_t is out-of-band = invalid across all four cells).
> - **(iv)** The worst-case floor asymmetry is not ordinal dominance but a phantom of collinear axes — the 5 nominal metrics collapse to **effective rank ≈ 2** (decoy-rejection factor vs robustness factor); near-symmetric.
>
> ∴ R2 *merit is a function of the environment* → R3 *the measurement coordinate and the winner are functions of exogenous specification (environment prior + utility preference). Pure universal superiority does not exist (proven), yet fixing an ordinal specification leaves room for a unique winner.*

Closing (Orchestrator): *"This convergence did not erase superiority — it relocated where superiority lives. With universal dominance proven false, the duty of operation shifts from 'which is better' to 'under which environment prior and which preference order do we operate.' The framework does not exempt choice; it makes choice explicit and local. Hence the first operational duty is the declaration of prior and preference — the unqualified question 'which is generally better' is, as of this round, ill-posed."*
