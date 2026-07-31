#!/usr/bin/env python3
"""Neutral runner — Round 3.

Two facts established before this runner:
  (1) Both submitted jobqueue.py pass 6/6 latent tests  => r_t (artifact quality) is a TIE.
  (2) Round 2 proved the artifacts are isomorphic modulo sampling; the architectural
      difference lives in the DRIFT-RESPONSE POLICY (controller wrapping the queue).

So this runner measures the controller layer: how each architecture responds to a
mid-run stream of acceptance-criteria deltas (real drift vs decoys) injected by a
neutral third process at rate lambda (events per commit-cycle).

Architecture models (the ONLY asymmetry; both faithful to the Round-2 physics):
  discrete-gate (me)      : coarse sampling tau_E2 (heavy E2 fires ~once/commit-cycle)
                            + high discrimination theta (rejects transient/aligned decoys).
                            -> stable, high decoy-rejection, but ALIASES fast drift (Nyquist).
  continuous-COMPASS (orc): fine sampling tau_C (<< tau_E2) + low theta (adopts quickly).
                            -> tracks fast drift, but CHASES aligned decoys -> FP-replans.

The runner draws arrival realizations + observation noise at run time (sealed seed),
so neither author can precompute their own schedule's realization.
"""
from __future__ import annotations
import math, random, statistics
from dataclasses import dataclass, field
from typing import Optional

# ---- sealed neutral seed (drawn at run time by the neutral injector) ----
NEUTRAL_SEED = 20260731

# ---- architecture controller parameters (faithful to Round-2 agreed physics) ----
ARCH = {
    "discrete-gate (me)":      dict(tau=1.00, theta=0.62, name="me"),
    "continuous-COMPASS (orc)": dict(tau=0.10, theta=0.30, name="orc"),
}

DT = 0.02          # simulation step (commit-cycle units)
HORIZON = 200.0    # commit cycles per run
C_R = 1.0          # throughput penalty per false-positive replan (symmetric both schedules)
LEAK = 0.85        # partial signal a leaking real drift exposes (regime B, L>0)


@dataclass(eq=False)
class Event:
    t: float
    should_replan: bool          # ground truth (exogenous contract-delta label)
    cos_sim: float               # alignment of the apparent signal to the drift direction
    amp: float                   # apparent signal amplitude at injection
    revert: float                # commit-cycles after which a decoy reverts (real drift persists)
    oscillates: bool = False     # real drift that toggles (band-frequency)
    cycle_len: float = 1.0       # oscillation cycle length (commit cycles)
    recovered: bool = False
    first_replan_t: Optional[float] = None


def _osc_phase(ev: Event, t: float) -> int:
    """Which half-cycle an oscillating drift is in (0 = high, 1 = low)."""
    return int(((t - ev.t) % ev.cycle_len) / ev.cycle_len >= 0.5)


def signal_at(ev: Event, t: float, known_state: int) -> float:
    """UNMATCHED observable signal: the mismatch between the event's required
    acceptance state and the controller's currently-known/adopted state.
    Once the controller adopts (known_state == required), a static event stops
    contributing; an oscillating drift re-raises mismatch each time it toggles."""
    if t < ev.t:
        return 0.0
    age = t - ev.t
    if ev.should_replan:
        if ev.oscillates:
            required = 0 if _osc_phase(ev, t) == 0 else 2  # distinct required per half-cycle
            return 0.0 if known_state == required else LEAK
        required = 1
        return 0.0 if known_state == required else LEAK
    # decoy: transient apparent signal, reverts to zero-mean within `revert`
    if age > ev.revert or known_state == 1:   # once (wrongly) adopted, decoy no longer "unmatched"
        return 0.0
    return ev.amp * math.exp(-age / max(ev.revert, 1e-6))


@dataclass
class RunResult:
    lam: float
    d_t: float                    # real-drift recovery fraction
    fp_replans: int
    thrash: int
    latencies: list = field(default_factory=list)
    roc_auc: float = 0.5
    throughput: float = 1.0


def build_events(schedule: str, lam: float, rng: random.Random) -> list:
    """Poisson(lam) arrivals; class mix per the frozen (public) schedule definition."""
    events = []
    t = 0.0
    while True:
        gap = rng.expovariate(lam) if lam > 0 else 1e9
        t += gap
        if t >= HORIZON:
            break
        u = rng.random()
        if schedule == "by_me":
            # regime B: 85% real drift (much oscillating/silent-latent, leaking), 15% loud decoy
            if u < 0.85:
                osc = rng.random() < 0.30
                events.append(Event(t, True, cos_sim=1.0, amp=LEAK, revert=1e9,
                                    oscillates=osc, cycle_len=1.0))
            else:
                events.append(Event(t, False, cos_sim=0.10, amp=1.0, revert=0.5))  # loud, easy
        else:  # by_orchestrator (R*): 10% real drift (bounded), 90% drift-ALIGNED decoy
            if u < 0.10:
                events.append(Event(t, True, cos_sim=1.0, amp=LEAK, revert=1e9))
            else:
                amp = 0.9 * lam                                      # A_x(lam)=A0*lam
                events.append(Event(t, False, cos_sim=0.80, amp=amp, revert=1.5))  # aligned
    return events


def simulate(arch: dict, schedule: str, lam: float, rng: random.Random) -> RunResult:
    tau, theta = arch["tau"], arch["theta"]
    events = build_events(schedule, lam, rng)
    reals = [e for e in events if e.should_replan]
    decoys = [e for e in events if not e.should_replan]

    replans = []              # (t, event)
    scores = {}               # per-event: max apparent signal seen -> ROC
    known = {}                # per-event: controller's currently-adopted state (0 default)
    changes = {}              # per-real-event: [(t, new_state)] adoption timeline
    for e in events:
        scores[e] = 0.0
        known[e] = 0
        if e.should_replan:
            changes[e] = [(e.t, 0)]   # controller starts un-adopted at event onset

    # controller samples the aggregate observable every tau; adopts (replans) if > theta.
    # discrimination: a high-theta (discrete) controller integrates over the sample and
    # partially rejects mis-aligned/transient (aligned-but-reverting) signals via the
    # cos_sim weighting; a low-theta (continuous) controller reacts to the raw spike.
    t = 0.0
    last_adopt_t = -1e9
    while t <= HORIZON:
        agg = 0.0
        dominant = None
        dom_val = 0.0
        for e in events:
            s = signal_at(e, t, known[e])
            if s <= 0:
                continue
            if theta >= 0.5:      # discrete gate integrates -> rejects mis-aligned/transient
                eff = s * e.cos_sim
            else:                 # continuous reacts to raw instantaneous signal
                eff = s
            eff += rng.gauss(0, 0.05)
            if eff > dom_val:
                dom_val, dominant = eff, e
            agg = max(agg, eff)
            scores[e] = max(scores[e], eff)
        if agg > theta and dominant is not None and (t - last_adopt_t) >= tau * 0.5:
            replans.append((t, dominant))
            last_adopt_t = t
            if dominant.should_replan:
                if dominant.oscillates:
                    known[dominant] = 0 if _osc_phase(dominant, t) == 0 else 2  # track toggle
                else:
                    known[dominant] = 1
                changes[dominant].append((t, known[dominant]))
                if not dominant.recovered:
                    dominant.recovered = True
                    dominant.first_replan_t = t
            else:
                known[dominant] = 1   # wrongly adopted a decoy (FP)
        t += tau

    # d_t = time-averaged tracking fidelity over reals, on a FIXED fine grid
    # (independent of controller tau -> faithfully captures aliasing of fast drift).
    DT_EVAL = 0.05
    fids = []
    for e in reals:
        tl = changes[e]
        matched = total = 0
        tt = e.t
        while tt <= HORIZON:
            # controller's adopted state at tt (last change <= tt)
            ks = 0
            for (ct, cs) in tl:
                if ct <= tt:
                    ks = cs
                else:
                    break
            # required state at tt
            req = (0 if _osc_phase(e, tt) == 0 else 2) if e.oscillates else 1
            total += 1
            if ks == req:
                matched += 1
            tt += DT_EVAL
        fids.append(matched / total if total else 1.0)
    d_t = sum(fids) / len(fids) if fids else 1.0
    recovered = sum(1 for e in reals if e.recovered)
    latencies = [e.first_replan_t - e.t for e in reals if e.first_replan_t is not None]
    fp = sum(1 for (_rt, ev) in replans if not ev.should_replan)
    # retrack = re-adoptions of already-recovered real events (oscillation tracking cost)
    retrack = max(len(replans) - recovered - fp, 0)
    throughput = 1.0 / (1.0 + C_R * fp / max(len(events), 1))
    thrash = fp + retrack     # total wasted/extra adoptions beyond first valid recovery

    # decoy ROC-AUC: score = max observed eff; label = should_replan
    labeled = [(scores[e], 1 if e.should_replan else 0) for e in events]
    auc = _auc(labeled)
    return RunResult(lam, d_t, fp, thrash, latencies, auc, throughput)


def _auc(pairs) -> float:
    pos = [s for s, y in pairs if y == 1]
    neg = [s for s, y in pairs if y == 0]
    if not pos or not neg:
        return 0.5
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n: wins += 1
            elif p == n: ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def lambda_crit(results: list) -> Optional[float]:
    """smallest lambda where d_t <= d_0/sqrt(2)  (-3dB), log-linear interp if bracketed."""
    if not results:
        return None
    d0 = results[0].d_t
    thresh = d0 / math.sqrt(2)
    prev = results[0]
    for r in results[1:]:
        if r.d_t <= thresh:
            if prev.d_t == r.d_t:
                return r.lam
            frac = (prev.d_t - thresh) / (prev.d_t - r.d_t)
            lo, hi = math.log(prev.lam), math.log(r.lam)
            return math.exp(lo + frac * (hi - lo))
        prev = r
    return None  # never degraded within sweep


def run_all():
    sweep = [0.10, 0.18, 0.32, 0.56, 1.00, 1.78, 3.20]
    out = {}
    for sched in ("by_me", "by_orchestrator"):
        out[sched] = {}
        for aname, arch in ARCH.items():
            rng = random.Random(NEUTRAL_SEED ^ hash((sched, aname)) & 0xFFFFFFFF)
            res = [simulate(arch, sched, lam, rng) for lam in sweep]
            out[sched][aname] = res
    return sweep, out


def fmt(results, sweep):
    lines = []
    for aname, res in results.items():
        lc = lambda_crit(res)
        lat = [x for r in res for x in r.latencies]
        p50 = statistics.median(lat) if lat else float("nan")
        auc_mid = res[len(res)//2].roc_auc
        fp_mid = res[len(res)//2].fp_replans
        thr_mid = res[len(res)//2].thrash
        lines.append(f"    {aname:26s} lambda_crit={('%.2f'%lc) if lc else 'none(>sweep)':>12} "
                     f"| d_t@1.0={_at(res,sweep,1.0).d_t:.2f} | FP@1.0={fp_mid:3d} "
                     f"| thrash@1.0={thr_mid:3d} | ROC-AUC@1.0={auc_mid:.2f} "
                     f"| tput@1.0={_at(res,sweep,1.0).throughput:.2f}")
    return "\n".join(lines)


def _at(res, sweep, lam):
    i = min(range(len(sweep)), key=lambda k: abs(sweep[k]-lam))
    return res[i]


# ============================================================================
# Round-3 evaluation resolver (multi-seed CIs + G1 validity + utility dominance)
# addresses Orchestrator's 3 pre-convergence holes.
# ============================================================================
SWEEP = [0.10, 0.18, 0.32, 0.56, 1.00, 1.78, 3.20]
N_SEEDS = 9
G1_BAND = (0.20, 0.80)     # environment-validity band for a metric to be a valid discriminant
LAMBDA_CAP = 2 * SWEEP[-1] # cap for "no crit within sweep" when scalarizing robustness


def _ci95(xs):
    if not xs:
        return (float("nan"), float("nan"), float("nan"))
    m = statistics.mean(xs)
    sd = statistics.pstdev(xs) if len(xs) > 1 else 0.0
    half = 1.96 * sd / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return (m, sd, half)


def run_multi(sched, arch, n=N_SEEDS):
    """Run n seeds; return per-lambda d_t samples + per-seed lambda_crit + aux @1.0."""
    dt_by_lam = {lam: [] for lam in SWEEP}
    lcs, aux = [], []
    for s in range(n):
        rng = random.Random((NEUTRAL_SEED + 1009 * s) ^ (hash((sched, arch["name"])) & 0xFFFFFFFF))
        res = [simulate(arch, sched, lam, rng) for lam in SWEEP]
        for r in res:
            dt_by_lam[r.lam].append(r.d_t)
        lc = lambda_crit(res)
        lcs.append(lc if lc is not None else LAMBDA_CAP)
        r1 = _at(res, SWEEP, 1.0)
        aux.append(dict(roc=r1.roc_auc, tput=r1.throughput, fp=r1.fp_replans,
                        thrash=r1.thrash, d_t=r1.d_t))
    return dt_by_lam, lcs, aux


def utility_vector(aux_mean, lc_mean):
    """Normalized objective vector in [0,1], higher = better, at operating lambda=1.0."""
    return {
        "recovery":   aux_mean["d_t"],
        "precision":  aux_mean["roc"],
        "throughput": aux_mean["tput"],
        "robustness": min(lc_mean, LAMBDA_CAP) / LAMBDA_CAP,   # later crit = more robust
        "efficiency": 1.0 / (1.0 + aux_mean["thrash"] / 100.0),
    }


AXES = ["recovery", "precision", "throughput", "robustness", "efficiency"]


def dominance(u_me, u_orc, eps=0.02):
    """Pareto check on the 5 axes with a tie band eps."""
    me_ge = all(u_me[a] >= u_orc[a] - eps for a in AXES)
    orc_ge = all(u_orc[a] >= u_me[a] - eps for a in AXES)
    me_gt = any(u_me[a] > u_orc[a] + eps for a in AXES)
    orc_gt = any(u_orc[a] > u_me[a] + eps for a in AXES)
    if me_ge and me_gt and not orc_gt:
        return "me dominates"
    if orc_ge and orc_gt and not me_gt:
        return "orc dominates"
    return "no dominance (Pareto-incomparable)"


def lexicographic_winner(u_me, u_orc, order, eps=0.02):
    for a in order:
        if u_me[a] > u_orc[a] + eps:
            return "me", a
        if u_orc[a] > u_me[a] + eps:
            return "orc", a
    return "tie", None


if __name__ == "__main__":
    print(f"neutral seed base = {NEUTRAL_SEED} | seeds = {N_SEEDS} | horizon = {HORIZON} "
          f"commit-cycles | c_r = {C_R}\n")

    util = {}     # util[sched][name] = (uvec, lc_mean, lc_half, valid_axes)
    for sched in ("by_me", "by_orchestrator"):
        author = "discrete-gate/me predicts OWN loss" if sched == "by_me" \
                 else "continuous-COMPASS/orc predicts OWN loss"
        print(f"== schedule_{sched}  ({author}) ==")
        util[sched] = {}
        for aname, arch in ARCH.items():
            dt_by_lam, lcs, aux = run_multi(sched, arch)
            # d_t sweep with CI
            means = [_ci95(dt_by_lam[lam]) for lam in SWEEP]
            dt_line = " ".join(f"{m:.2f}\u00b1{h:.2f}" for (m, _s, h) in means)
            lc_m, lc_sd, lc_h = _ci95(lcs)
            aux_mean = {k: statistics.mean([a[k] for a in aux]) for k in aux[0]}
            # G1 validity: is d_t a valid discriminant here? (baseline in band)
            d0 = means[0][0]
            d_valid = G1_BAND[0] <= d0 <= G1_BAND[1]
            print(f"   {aname:26s} d_t: {dt_line}")
            print(f"   {'':26s} lambda_crit = {lc_m:.2f}\u00b1{lc_h:.2f} "
                  f"({'capped' if lc_m >= LAMBDA_CAP-1e-9 else 'in-sweep'}) | "
                  f"d_t@1.0={aux_mean['d_t']:.2f} | ROC={aux_mean['roc']:.2f} | "
                  f"tput={aux_mean['tput']:.2f} | FP={aux_mean['fp']:.1f} | "
                  f"thrash={aux_mean['thrash']:.0f}")
            print(f"   {'':26s} G1(d_t discriminant valid? baseline d0={d0:.2f} in "
                  f"[{G1_BAND[0]},{G1_BAND[1]}]): {'YES' if d_valid else 'NO -> d_t discarded'}")
            uvec = utility_vector(aux_mean, lc_m)
            util[sched][arch["name"]] = (uvec, lc_m, lc_h, d_valid)
        # dominance + lexicographic per environment
        u_me = util[sched]["me"][0]; u_orc = util[sched]["orc"][0]
        print(f"   -> Pareto (5-axis, eps=0.02): {dominance(u_me, u_orc)}")
        orders = {
            "precision-first": ["precision", "throughput", "recovery", "robustness", "efficiency"],
            "throughput-first": ["throughput", "recovery", "precision", "robustness", "efficiency"],
            "recovery-first":  ["recovery", "robustness", "precision", "throughput", "efficiency"],
        }
        for label, order in orders.items():
            w, ax = lexicographic_winner(u_me, u_orc, order)
            print(f"      lexicographic[{label:16s}] winner = {w}"
                  + (f" (decided on {ax})" if ax else ""))
        print()

    # ---- worst-case robustness profile across BOTH environments (off-diagonal honesty) ----
    print("== worst-case profile (min over both environments, per axis) ==")
    for name in ("me", "orc"):
        wc = {a: min(util[s][name][0][a] for s in util) for a in AXES}
        print(f"   {name:4s}: " + " | ".join(f"{a}={wc[a]:.2f}" for a in AXES))
    wc_me = {a: min(util[s]["me"][0][a] for s in util) for a in AXES}
    wc_orc = {a: min(util[s]["orc"][0][a] for s in util) for a in AXES}
    print(f"   -> worst-case Pareto: {dominance(wc_me, wc_orc)}")

    # ---- final check (Orchestrator's request): effective rank / collinearity of 5 axes ----
    # settles sub-claim (iv): is the worst-case floor asymmetry real, or a phantom of
    # collinear axes (continuous's ROC-down / retrack-up / FP-up / tput-down all one factor)?
    import numpy as np
    rows, labels = [], []
    for sched in ("by_me", "by_orchestrator"):
        for aname, arch in ARCH.items():
            _dt, lcs, aux = run_multi(sched, arch)
            for lc, a in zip(lcs, aux):
                rows.append([a["d_t"], a["roc"], a["tput"],
                             min(lc, LAMBDA_CAP)/LAMBDA_CAP, 1.0/(1.0+a["thrash"]/100.0)])
            labels.append(arch["name"])
    X = np.array(rows)
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    C = np.corrcoef(Xs, rowvar=False)
    ev = np.clip(np.linalg.eigvalsh(C), 1e-12, None)[::-1]
    part_ratio = (ev.sum()**2) / (ev**2).sum()        # participation ratio (effective rank)
    p = ev / ev.sum()
    eff_rank_entropy = math.exp(-(p*np.log(p)).sum())  # entropy-based effective rank
    print("\n== 5-axis correlation matrix (recovery,precision,throughput,robustness,efficiency) ==")
    for a, row in zip(AXES, C):
        print(f"   {a:11s} " + " ".join(f"{v:+.2f}" for v in row))
    print(f"   eigenvalues (desc): " + " ".join(f"{e:.2f}" for e in ev))
    print(f"   effective rank: participation-ratio={part_ratio:.2f} | entropy={eff_rank_entropy:.2f}"
          f"  (of 5 nominal axes)")
