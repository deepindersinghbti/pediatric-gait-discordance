"""Revision step B - repeatability in the standard SEM / ICC / MDC framework.

Reviewers R2, R3 and R4 asked for:
  * SEM, ICC and MDC95 with confidence intervals, per group and pooled;
  * the link between the paper's delta_s (95th percentile of |trial1 - trial2|)
    and MDC95 = 1.96 * sqrt(2) * SEM;
  * the margin for a visit score that averages n trials: 1.645 * SEM / sqrt(n)
    (one-sided 95%), used by the revised strict rule;
  * a repeatability estimate that does not rest on two trials only
    (odd vs even cycles within each trial);
  * waveform-level repeatability: CMC across all cycles of the visit (Kadaba)
    and the RMSE between the two trials' mean curves.

Definitions (two trials per visit-limb, the first two as in the paper):
  d = score(trial 1) - score(trial 2)
  SEM = sqrt(mean(d^2) / 2)            (within-visit error of one trial's score,
                                        includes any systematic trial-order bias)
  ICC = ICC(2,1), two-way random effects, absolute agreement, single trial
  95% CIs: cluster bootstrap over children (2000 resamples, stratified by group)

Usage:  python src/rev_repeatability.py results/ results/rev/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from rev_common import (CHANNELS, SCALE, SCORES, VISIT, area_norm, build_reference,
                        load_cycles, score_curves, score_df)

ALL = SCORES + ["ankleShape_stance", "ankleShape_swing"]
GROUPS = ["TD", "CP", "ITW", "All"]
N_BOOT = 2000


def icc21(Y):
    """ICC(2,1) for Y (n subjects, 2 trials, n_scores)."""
    n, k = Y.shape[0], Y.shape[1]
    gm, rm, cm = Y.mean((0, 1)), Y.mean(1), Y.mean(0)
    msr = k * ((rm - gm) ** 2).sum(0) / (n - 1)
    msc = n * ((cm - gm) ** 2).sum(0) / (k - 1)
    mse = ((Y - rm[:, None] - cm[None] + gm) ** 2).sum((0, 1)) / ((n - 1) * (k - 1))
    return (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)


KEYS = ["bias", "delta95", "SEM", "ICC", "MDC95", "margin_2trials", "n_used"]


def stats(Y):
    """Y (n, 2, S) -> dict of arrays over scores; pairs with a missing score are
    dropped for that score only (e.g. an excluded EMG channel)."""
    out = {k: np.full(Y.shape[2], np.nan) for k in KEYS}
    for j in range(Y.shape[2]):
        y = Y[:, :, j]
        y = y[np.isfinite(y).all(1)]
        if len(y) < 3:
            continue
        d = y[:, 0] - y[:, 1]
        sem = np.sqrt((d ** 2).mean() / 2)
        out["bias"][j], out["delta95"][j], out["SEM"][j] = d.mean(), np.percentile(np.abs(d), 95), sem
        out["ICC"][j] = icc21(y[:, :, None])[0]
        out["MDC95"][j], out["margin_2trials"][j] = 1.96 * np.sqrt(2) * sem, 1.645 * sem / np.sqrt(2)
        out["n_used"][j] = len(y)
    return out


def boot(Y, codes, groups, n=N_BOOT, seed=2027):
    """Cluster bootstrap over children, stratified by group -> dict of (n, S) arrays."""
    rng = np.random.default_rng(seed)
    strata = [[np.where(codes == c)[0] for c in np.unique(codes[groups == g])] for g in np.unique(groups)]
    out = {k: [] for k in stats(Y)}
    for _ in range(n):
        idx = np.concatenate([s[i] for s in strata for i in rng.integers(0, len(s), len(s))])
        for k, v in stats(Y[idx]).items():
            out[k].append(v)
    return {k: np.array(v) for k, v in out.items()}


def cmc(Y):
    """Kadaba coefficient of multiple correlation for waveforms Y (n_waveforms, 101).
    Returns NaN when undefined (between-waveform offset larger than total variance)."""
    n, t = Y.shape
    num = ((Y - Y.mean(0)) ** 2).sum() / (t * (n - 1))
    den = ((Y - Y.mean()) ** 2).sum() / (t * n - 1)
    v = 1 - num / den
    return np.sqrt(v) if v >= 0 else np.nan


def summarise(pairs, label):
    rows = []
    for g in GROUPS:
        p = pairs if g == "All" else pairs[pairs.group == g]
        Y = np.stack([p[[f"{s}_1" for s in ALL]].to_numpy(), p[[f"{s}_2" for s in ALL]].to_numpy()], axis=1)
        est, b = stats(Y), boot(Y, p.code.to_numpy(), p.group.to_numpy())
        for j, s in enumerate(ALL):
            r = dict(analysis=label, group=g, score=s, n_visit_limbs=len(p), n_children=p.code.nunique())
            for k in est:
                r[k] = est[k][j]
                if k not in ("bias", "n_used"):
                    r[f"{k}_lo"], r[f"{k}_hi"] = np.percentile(b[k][:, j], [2.5, 97.5])
            rows.append(r)
    return pd.DataFrame(rows)


def main(results, rev):
    results, rev = Path(results), Path(rev)
    df = pd.read_csv(results / "trials.csv")
    curves = np.load(results / "curves.npz")["curves"]
    ref, loo = build_reference(df, curves)
    sc = pd.concat([score_df(df, curves, ref, loo),
                    score_df(df, curves, ref, loo, demean_ankle=True)[["ankle_stance", "ankle_swing"]]
                    .set_axis(["ankleShape_stance", "ankleShape_swing"], axis=1)], axis=1)
    t = pd.concat([df, sc], axis=1)

    # ---------- 1. between-trial repeatability (first two trials of each visit-limb, all limbs)
    pairs = []
    for key, g in t.sort_values("trial").groupby(VISIT):
        if len(g) >= 2:
            a, b = g.iloc[0], g.iloc[1]
            pairs.append(dict(zip(VISIT, key), n_trials=len(g), row1=a.name, row2=b.name,
                              **{f"{s}_1": a[s] for s in ALL}, **{f"{s}_2": b[s] for s in ALL}))
    pairs = pd.DataFrame(pairs)
    rep = summarise(pairs, "between_trials")
    old = pd.read_csv(results / "thresholds.csv", index_col=0)["threshold_all"]
    chk = rep[(rep.group == "All") & rep.score.isin(SCORES)].set_index("score").delta95
    print(f"Visit-limbs with >=2 trials: {len(pairs)} "
          f"({', '.join(f'{g} {(pairs.group == g).sum()}' for g in GROUPS[:3])})")
    print(f"Paper's delta_s vs this run: max diff {np.abs(chk - old).max():.2e} (0 = reproduced)")

    # ---------- 2. split-half: odd vs even cycles within each trial
    z, kin, emg = load_cycles(rev)
    half_curves, half_rows = [], []
    for r in df.index:
        ka = z["ankle"][kin.index[(kin.row == r) & kin.finite]]
        e = emg[emg.row == r]
        ta = area_norm(z["TA"][e.index[e.ok_TA]])
        gm = area_norm(z["GM"][e.index[e.ok_GM]])
        chans = [ka, ta, gm]
        if max(len(c) for c in chans) < 4:          # need >= 2 cycles in each half
            continue
        for h in (0, 1):                            # a channel with < 4 cycles -> missing
            half_curves.append(np.stack([c[h::2].mean(0) if len(c) >= 4 else np.full(101, np.nan)
                                         for c in chans]))
        half_rows.append(r)
    hc = np.stack(half_curves)
    hrow = np.repeat(half_rows, 2)
    g_, c_, to_ = df.group.to_numpy()[hrow], df.code.to_numpy()[hrow], df.toe_off.to_numpy()[hrow]
    hs = np.hstack([score_curves(hc, g_, c_, to_, ref, loo),
                    score_curves(hc, g_, c_, to_, ref, loo, demean_ankle=True)[:, :2]])
    halves = df.loc[half_rows, ["group", "code"]].reset_index(drop=True)
    for j, s in enumerate(ALL):
        halves[f"{s}_1"], halves[f"{s}_2"] = hs[0::2, j], hs[1::2, j]
    split = summarise(halves, "odd_vs_even_cycles")
    print(f"Trial-limbs with >= 4 usable cycles in at least one channel (split-half): {len(halves)} of {len(df)}")

    # ---------- 3. waveform-level repeatability
    wave = []
    for _, p in pairs.iterrows():
        c1, c2 = curves[p.row1] * SCALE[:, None], curves[p.row2] * SCALE[:, None]
        rows = [p.row1, p.row2]
        r = dict(group=p.group, code=p.code)
        for k, ch in enumerate(CHANNELS):
            r[f"rmse_{ch}"] = np.sqrt(np.nanmean((c1[k] - c2[k]) ** 2))
            if ch == "ankle":
                cyc = z["ankle"][kin.index[kin.row.isin(rows) & kin.finite]]
            else:
                e = emg[emg.row.isin(rows) & emg[f"ok_{ch}"]]
                cyc = area_norm(z[ch][e.index]) * 101
            r[f"cmc_cycles_{ch}"] = cmc(cyc) if len(cyc) >= 2 else np.nan
        wave.append(r)
    wave = pd.DataFrame(wave)
    wsum = []
    for g in GROUPS:
        w = wave if g == "All" else wave[wave.group == g]
        for col in [c for c in wave.columns if c not in ("group", "code")]:
            q = w[col].quantile([0.25, 0.5, 0.75])
            wsum.append(dict(group=g, measure=col, n=len(w), median=q[0.5], q1=q[0.25], q3=q[0.75],
                             n_undefined=int(w[col].isna().sum())))
    wsum = pd.DataFrame(wsum)

    # ---------- save + print
    out = pd.concat([rep, split])
    out.to_csv(rev / "repeatability.csv", index=False)
    pairs.to_csv(rev / "repeat_pairs.csv", index=False)
    wave.to_csv(rev / "waveform_repeatability_visits.csv", index=False)
    wsum.to_csv(rev / "waveform_repeatability.csv", index=False)

    f = lambda r, k: f"{r[k]:.2f} [{r[k + '_lo']:.2f}, {r[k + '_hi']:.2f}]"
    for label, tab in (("BETWEEN TRIALS", rep), ("ODD vs EVEN CYCLES", split)):
        print(f"\n=== {label}: SEM, ICC, MDC95 [95% CI]; delta95 = paper-style 95th pct of |d|")
        for g in GROUPS:
            print(f"-- {g} (n = {tab[tab.group == g].n_visit_limbs.iloc[0]} pairs, "
                  f"{tab[tab.group == g].n_children.iloc[0]} children)")
            for _, r in tab[tab.group == g].iterrows():
                print(f"   {r.score:18s} SEM {f(r, 'SEM'):20s} ICC {f(r, 'ICC'):20s} MDC95 {f(r, 'MDC95'):20s} "
                      f"delta95 {r.delta95:.2f}  margin(2 trials) {r.margin_2trials:.2f}  bias {r.bias:+.2f}")
    ratio = (rep.set_index(["group", "score"]).SEM /
             (split.set_index(["group", "score"]).SEM / np.sqrt(2)))
    print("\nBetween-trial SEM / (split-half SEM / sqrt 2)  [>1 = extra trial-to-trial variation beyond cycle noise]")
    print(ratio.unstack("score")[ALL].round(2).reindex(GROUPS).to_string())
    print("\n=== Waveform repeatability (median [IQR]); EMG in units of cycle-mean activation")
    piv = wsum.assign(v=wsum.apply(lambda r: f"{r['median']:.2f} [{r.q1:.2f}-{r.q3:.2f}]", axis=1))
    print(piv.pivot(index="measure", columns="group", values="v")[GROUPS].to_string())
    print("undefined CMC counts:", wsum[wsum.n_undefined > 0][["group", "measure", "n_undefined"]].to_dict("records"))


if __name__ == "__main__":
    main(*sys.argv[1:3])
