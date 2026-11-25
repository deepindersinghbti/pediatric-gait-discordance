"""Revision steps E + G - score-type balance and phase-alignment sensitivity analyses.

Each variant changes how the trial-level scores are made, then reuses the full
classification of rev_classify.analyse (all rules, thresholds re-estimated inside the
bootstrap, child-level permutation tests) on the main analysis set.

E (R2: "use the same type of score for both modalities ... equal numbers of tests ...
add an amplitude-sensitive EMG measure")
  amplitude_EMG   raw ankle angle vs raw EMG envelope (NOT area-normalised), in units of
                  the TD median cycle-mean envelope of that muscle. No MVC normalisation
                  exists in the dataset, so amplitude also reflects electrode/skin factors.
  EMG_two_scores  one EMG score per phase (RMS of the TA and GM scores), so ankle and
                  EMG are each judged on two tests.
  (shape vs shape = rev_classify's shape_ankle analysis.)

G (R2, R4: toe-off range 35-81%, phase-alignment confound)
  registered      every EMG cycle time-warped piecewise-linearly so that its own toe-off
                  falls at the TD median cycle toe-off (stance and swing stretched
                  separately); ankle cycles warped with the trial's median toe-off (the
                  files do not pair kinematic and EMG cycles). Reference rebuilt from
                  registered TD curves; stance/swing boundary = TD median for all.
  fixed60         stance/swing boundary fixed at 60% of the cycle for every trial.
  excl_toeoff     trial-limbs whose median toe-off lies outside the range of 98% of TD
                  cycles (1st-99th percentile) are dropped before averaging visits.

Further sensitivity analyses
  strict_TD_SEM   measurement error (SEM, delta_s) estimated from TD repeat trials only
                  (R2, R4: "estimate delta_s per group (or TD-only)").
  excl_P15        child P15 removed: plantarflexion to -86 deg in every session (most likely
                  an IMU calibration offset in a fixed-equinus foot); influential in CP and in
                  the longitudinal pilot.

Usage:  python src/rev_variants.py results/rev/clean/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/rev/clean/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from rev_classify import GROUPS, analyse, holm, visits_from_trials
from rev_common import SCORES, build_reference, score_df

N = 101


def warp(x, to, T):
    """Piecewise-linear time warp: sample `to` (toe-off) -> T; 0 -> 0; 100 -> 100."""
    u = np.arange(N, dtype=float)
    src = np.where(u < T, u * to / T, to + (u - T) * (N - 1 - to) / (N - 1 - T))
    return np.interp(src, np.arange(N), x)


def scored(df, curves, **kw):
    ref, loo = build_reference(df, curves)
    return pd.concat([df, score_df(df, curves, ref, loo, **kw)], axis=1)


def main(results, meta_xlsx, out):
    results, out = Path(results), Path(out)
    rng = np.random.default_rng(2027)
    df = pd.read_csv(results / "trials.csv", parse_dates=["date"])
    curves = np.load(results / "curves.npz")["curves"]
    z = np.load(results / "cycles.npz")
    kin = pd.read_csv(results / "cycles_kin.csv")
    emg = pd.read_csv(results / "cycles_emg.csv")
    emg = emg.merge(df[["group"]], left_on="row", right_index=True)
    td_cyc = emg[(emg.group == "TD") & (emg.n_liftoffs >= 1)].toe_off
    T = int(td_cyc.median())
    lo_to, hi_to = td_cyc.quantile([0.01, 0.99])
    print(f"TD cycle toe-off: median {T}%, 1st-99th percentile {lo_to:.0f}-{hi_to:.0f}%")

    # ---------------- toe-off extremes (R2, R4)
    ext = df[~df.toe_off.between(lo_to, hi_to)].copy()
    rows = []
    for r, x in ext.iterrows():
        e = emg[emg.row == r]
        rows.append(dict(group=x.group, code=x.code, phase=x.phase, trial=x.trial, leg=x.leg, toe_off=x.toe_off,
                         n_emg_cycles=len(e), cycle_toe_off_min=e.toe_off.min(), cycle_toe_off_max=e.toe_off.max(),
                         cycle_toe_off_iqr=e.toe_off.quantile(0.75) - e.toe_off.quantile(0.25)))
    ext = pd.DataFrame(rows).sort_values("toe_off")
    ext.to_csv(out / "toe_off_extremes.csv", index=False)
    print(f"\nTrial-limbs with median toe-off outside {lo_to:.0f}-{hi_to:.0f}%: {len(ext)} of {len(df)} "
          f"({ext.groupby('group').size().to_dict()}, children {ext.code.nunique()})")
    print(ext.to_string(index=False))

    variants = {}
    # ---------------- G1: fixed 60% boundary
    variants["fixed60"] = scored(df, curves, boundary=60)

    # ---------------- G2: drop trial-limbs with implausible toe-off
    keep = df.toe_off.between(lo_to, hi_to).to_numpy()
    d2 = df[keep].reset_index(drop=True)
    variants["excl_toeoff"] = scored(d2, curves[keep])

    # ---------------- G3: per-cycle registration to the TD toe-off
    reg = np.full_like(curves, np.nan)
    for r in df.index:
        k = kin[(kin.row == r) & kin.finite]
        if len(k) and np.isfinite(df.toe_off[r]):
            reg[r, 0] = np.mean([warp(z["ankle"][i], df.toe_off[r], T) for i in k.index], axis=0)
        e = emg[emg.row == r]
        for ch, m in ((1, "TA"), (2, "GM")):
            ok = e[e[f"ok_{m}"] & (e.n_liftoffs >= 1)]
            if len(ok):
                w = np.stack([warp(z[m][i], to, T) for i, to in zip(ok.index, ok.toe_off)])
                reg[r, ch] = (w / np.abs(w).sum(1, keepdims=True)).mean(0)
    d3 = df.copy()
    d3["toe_off"] = T
    variants["registered"] = scored(d3, reg)

    # ---------------- E1: amplitude-aware EMG (raw envelopes)
    q = pd.read_csv(results / "emg_quality.csv")
    amp = q[(q.group == "TD") & ~q.excluded].groupby("muscle").mean_amp.median()
    raw = curves.copy()
    for r in df.index:
        e = emg[emg.row == r]
        for ch, m in ((1, "TA"), (2, "GM")):
            ok = e[e[f"ok_{m}"]]
            raw[r, ch] = z[m][ok.index].mean(0) / (N * amp[m]) if len(ok) else np.nan
    variants["amplitude_EMG"] = scored(df, raw)
    print(f"\nTD median cycle-mean raw envelope used as EMG amplitude unit: {amp.round(5).to_dict()}")

    # ---------------- E2: two EMG tests (RMS over muscles per phase)
    t = scored(df, curves)
    for ph in ("stance", "swing"):
        t[f"TA_{ph}"] = np.sqrt(np.nanmean(np.stack([t[f"TA_{ph}"] ** 2, t[f"GM_{ph}"] ** 2]), axis=0))
        t[f"GM_{ph}"] = np.nan
    variants["EMG_two_scores"] = t

    # ---------------- sensitivity: TD-only measurement error; without P15
    t0 = scored(df, curves)
    variants["strict_TD_SEM"] = t0
    keep = (df.code != "P15").to_numpy()
    variants["excl_P15"] = scored(df[keep].reset_index(drop=True), curves[keep])

    # ---------------- classify each variant (main analysis set)
    rate_rows, diff_rows, thr_rows = [], [], []
    for name, tt in variants.items():
        v, pairs = visits_from_trials(tt, meta_xlsx)
        if name == "strict_TD_SEM":
            pairs = pairs[pairs.group == "TD"].reset_index(drop=True)
        rr, dr, tr, vo, eq = analyse(v, pairs, {name: np.ones(len(v), bool)}, name, rng)
        rate_rows += rr; diff_rows += dr; thr_rows += tr
        vo.to_csv(out / f"visits_variant_{name}.csv", index=False)
        print(f"[{name}] visit-limbs: {v.group.value_counts().reindex(GROUPS).to_dict()}; eq10: {eq}")
    rates, diffs = pd.DataFrame(rate_rows), pd.DataFrame(diff_rows)
    diffs["p_holm"] = diffs.groupby(["rule", "group", "outcome"]).p.transform(holm)
    rates.to_csv(out / "variants_class_rates.csv", index=False)
    diffs.to_csv(out / "variants_group_differences.csv", index=False)
    pd.DataFrame(thr_rows).to_csv(out / "variants_thresholds.csv", index=False)

    # ---------------- compact comparison with the main analysis
    base_r = pd.read_csv(out / "class_rates.csv")
    base_d = pd.read_csv(out / "group_differences.csv")
    R = pd.concat([base_r[base_r.analysis.isin(["main", "shape_ankle"])], rates])
    Dd = pd.concat([base_d[base_d.analysis.isin(["main", "shape_ankle"])], diffs])
    print("\n%-15s %-10s | CP ankle-only vs TD (diff, p) | EMG flag CP / ITW / TD | CP EMG-flag diff p | ITW EMG-flag diff p"
          % ("analysis", "rule"))
    for a in ["main", "shape_ankle"] + list(variants):
        for rule in ("standard", "strict_new"):
            r = R[(R.analysis == a) & (R.rule == rule)].set_index(["group", "outcome"]).pct
            d = Dd[(Dd.analysis == a) & (Dd.rule == rule)].set_index(["group", "outcome"])
            print(f"{a:15s} {rule:10s} | {r[('CP', 'ankle_only')]:5.1f} vs {r[('TD', 'ankle_only')]:4.1f} "
                  f"({d.loc[('CP', 'ankle_only'), 'diff']:+5.1f}, p={d.loc[('CP', 'ankle_only'), 'p']:.4f}) | "
                  f"{r[('CP', 'EMG_flag')]:5.1f} / {r[('ITW', 'EMG_flag')]:5.1f} / {r[('TD', 'EMG_flag')]:5.1f} | "
                  f"{d.loc[('CP', 'EMG_flag'), 'diff']:+5.1f} p={d.loc[('CP', 'EMG_flag'), 'p']:.3f} | "
                  f"{d.loc[('ITW', 'EMG_flag'), 'diff']:+5.1f} p={d.loc[('ITW', 'EMG_flag'), 'p']:.3f}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
