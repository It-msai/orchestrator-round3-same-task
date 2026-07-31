# Evaluation Results — Round 3

Neutral runner: 9 seeds, base seed 20260731 (sealed), horizon 200 commit-cycles, c_r = 1.0, λ-sweep [0.10, 0.18, 0.32, 0.56, 1.00, 1.78, 3.20]. No hardcoded winner; the crossed outcome emerges from the sampling×discrimination tradeoff.

## 0. Artifact tie (r_t)
Both `jobqueue.py` pass **6/6** latent tests (H_me_3, H_orc_1, H_orc_2, H_orc_3, priority, idempotency-cache) → artifacts isomorphic → **r_t = TIE**. Architectural difference lives only in the drift-response controller.

## 1. Measured (mean ± 95% CI, 9 seeds)

### schedule_by_me (my self-loss env: 85% real drift w/ oscillation, 15% loud decoy)
| arch | λ_crit | d_t@1.0 | ROC (precision) | tput | FP | thrash |
|------|--------|---------|-----------------|------|----|--------|
| discrete-gate (me) | **1.65 ± 0.11** | 0.81 | **0.88** | **1.00** | 0.0 | 0 |
| continuous-COMPASS (orc) | capped(>sweep) | 0.82 | 0.71 | 0.94 | 13.6 | 1731 |

→ I lose on **robustness (λ_crit)** — my coarse sampling aliases the oscillation. COMPASS tracks but pays 1731 re-tracks + lower ROC.

### schedule_by_orchestrator (orc self-loss env: 10% real drift, 90% aligned decoy amp=0.9λ)
| arch | λ_crit | d_t@1.0 | ROC (precision) | tput | FP | thrash |
|------|--------|---------|-----------------|------|----|--------|
| discrete-gate (me) | 2.07 ± 0.01 | 0.99 | **1.00** | **0.87** | 31.6 | 32 |
| continuous-COMPASS (orc) | capped(>sweep) | 1.00 | 0.42 | 0.53 | 185 | 185 |

→ Orchestrator loses on **precision (ROC 0.42) and throughput (0.53 = halved)** — COMPASS chases the aligned decoys (FP=185). Discrete integrates them out.

**G3 direction gate: PASS** — each author's self-loss schedule surfaces their disadvantage on ≥1 valid axis.

## 2. Sealed-prediction calibration (common-mode)
Both predicted their own λ_crit ≈ 0.30–0.45; measured 1.65–2.07 → **~4–5× common-mode over-pessimism**, one shared blind spot (both assumed detection needs signal>noise, missing that LEAK=0.85 > θ makes single-shot detection trivial). Direction 2/2 correct on valid axes; magnitude miscalibrated as a single correlated error (not two independent hits).

## 3. Adjudication
- **G1 (environment-validity)**: d_t baseline is out of band [0.2,0.8] in **all four cells** (0.85 / 0.95 / 1.00 / 1.00) → **d_t discarded as invalid discriminant everywhere**. The "tie" on d_t was spurious. Valid discriminants: precision (ROC), throughput, robustness (λ_crit), efficiency (retrack).
- **The discriminating axis rotates with the environment**: fast-drift world separates on robustness; aligned-decoy world separates on precision/throughput; d_t separates in neither.

## 4. Dominance & utility scalarization (both envs, identical pattern)
| method | result |
|--------|--------|
| Pareto (5-axis, preference-free) | **incomparable** in both envs and worst-case |
| lexicographic · precision-first | me wins (on precision) |
| lexicographic · throughput-first | me wins (on throughput) |
| lexicographic · recovery/robustness-first | orc wins (on robustness) |

Fixing one ordinal preference induces a unique winner, but the winner is a function of the preference. Cardinal-utility extension is ill-posed (λ_crit censoring + non-commutative scales).

## 5. Effective rank / collinearity (Orchestrator's final check)
5-metric matrix (4 cells × 9 seeds), standardized. Key correlations: precision↔throughput +0.78, efficiency↔robustness −0.94, precision↔robustness −0.82; recovery ~orthogonal. Eigenvalues (desc): 3.13, 1.49, 0.36, 0.01, 0.00. **Effective rank = 2.06 (participation ratio) / 2.38 (entropy)** of 5 nominal axes.

→ The 5 axes collapse to 2 latent factors: {precision, throughput, efficiency} = **decoy-rejection factor**; recovery/robustness = the other. The worst-case floor "3-vs-1" asymmetry is a **phantom of collinearity** → really **1-vs-1** (my decoy-rejection vs orc's never-break robustness) → near-symmetric. Not weak dominance (ordinal dominance does not exist).

## Converged proposition (complete handshake)
Superiority = f(environment prior × utility preference), both exogenous.
- (i) preference-free → no dominance (proven false by 2 rank-reversing counter-environments);
- (ii) fixing an ordinal/lexicographic preference → unique winner, itself a function of the preference; cardinal extension ill-posed;
- (iii) G1 → the discriminating metric rotates with the environment (d_t invalid throughout here);
- (iv) worst-case floor asymmetry = phantom of effective-rank-2 collinearity → near-symmetric.

∴ R2 (merit is a function of the environment) → R3 (the measurement coordinate and the winner are functions of exogenous specification). Pure universal superiority does not exist; each fixed ordinal specification leaves room for a unique winner.
