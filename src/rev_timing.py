"""Revision step K - EMG on/off timing measures (complement to whole-phase RMSE).

Reviewer R3: "Consider including onset/offset-based EMG timing measures to complement
whole-phase RMSE." R2: whole-phase RMSE can dilute brief timing errors.

Per EMG cycle (cleaned data; area-normalised so 1.0 = the cycle-mean activation):
  the muscle is ON where its envelope exceeds its own cycle mean (scale-free threshold);
  each cycle's own toe-off splits stance and swing. Measures (% of samples ON):
    TA_stance_on, TA_swing_on, GM_stance_on, GM_swing_on        (phase activity)
    GM_preIC_on  = GM ON in 85-100% of the cycle (premature calf activity before
                   initial contact, reported in toe walkers)
    TA_postIC_on = TA ON in 0-15% of the cycle (TA after initial contact)
Trial value = median over the trial's cycles; visit-limb value = mean over its trials
(analysed limbs), as for the RMSE scores.
Normal range: TD 2.5th-97.5th percentile (two-sided, leave-one-child-out for TD).
Timing flag (standard) = any of the four phase measures outside the range.
Repeatability: first-two-trial differences (all limbs) -> SEM, ICC(2,1); strict timing
flag = outside the range by more than 1.645 * SEM / sqrt(n trials), as in the main rule.
Group differences: difference in child means (each child weighted equally), child-cluster
bootstrap CI, child-level permutation test (5000).

Robustness: the same comparisons on pre-treatment (T0) patient visits only and on patient
visits within the TD age range (botulinum toxin targets the calf, so post-treatment visits
could alter calf timing).

Usage:  python src/rev_timing.py results/rev/clean/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from rev_common import VISIT, area_norm
from rev_repeatability import icc21

PHASE = ["TA_stance_on", "TA_swing_on", "GM_stance_on", "GM_swing_on"]
TARGET = ["GM_preIC_on", "TA_postIC_on"]
ALL = PHASE + TARGET


def main(rev, n_boot=2000, n_perm=5000):
    rev = Path(rev)
    rng = np.random.default_rng(2027)
    df = pd.read_csv(rev / "trials.csv", parse_dates=["date"])
    z = np.load(rev / "cycles.npz")
    emg = pd.read_csv(rev / "cycles_emg.csv")
    rows = []
    for m in ("TA", "GM"):
        ok = emg[emg[f"ok_{m}"] & (emg.n_liftoffs >= 1)]
        x = area_norm(z[m][ok.index]) * 101
        on = x > 1.0
        for i, (r, to) in enumerate(zip(ok.row, ok.toe_off)):
            d = {"row": r, "muscle": m, f"{m}_stance_on": 100 * on[i, :to].mean(), f"{m}_swing_on": 100 * on[i, to:].mean()}
            if m == "GM":
                d["GM_preIC_on"] = 100 * on[i, 85:].mean()
            else:
                d["TA_postIC_on"] = 100 * on[i, :15].mean()
            rows.append(d)
    cyc = pd.DataFrame(rows).merge(df[VISIT + ["trial"]], left_on="row", right_index=True)
    tri = cyc.groupby(VISIT + ["trial"])[ALL].median().reset_index()
    pairs = []
    for key, g in tri.sort_values("trial").groupby(VISIT):
        if len(g) >= 2:
            pairs.append(np.stack([g.iloc[0][ALL].to_numpy(float), g.iloc[1][ALL].to_numpy(float)]))
    P = np.stack(pairs)                                       # (n, 2, measures)
    rep = []
    for j, a in enumerate(ALL):
        y = P[:, :, j][np.isfinite(P[:, :, j]).all(1)]
        d = y[:, 0] - y[:, 1]
        rep.append(dict(measure=a, n_pairs=len(y), SEM=np.sqrt((d ** 2).mean() / 2), ICC=icc21(y[:, :, None])[0]))
    rep = pd.DataFrame(rep).set_index("measure")
    vis = tri.groupby(VISIT).agg(n_trials=("trial", "size"), **{a: (a, "mean") for a in ALL}).reset_index()
    keep = pd.read_csv(rev / "visits_main_scores.csv", parse_dates=["date"])[VISIT]
    vis = keep.merge(vis, on=VISIT, how="left")              # analysed limbs only

    td = vis.group == "TD"
    lim = {}
    for c in vis.code[td].unique():
        lim[c] = vis.loc[td & (vis.code != c), ALL].quantile([0.025, 0.975])
    lim_all = vis.loc[td, ALL].quantile([0.025, 0.975])
    out = np.zeros((len(vis), len(ALL)), bool)
    out_s = np.zeros((len(vis), len(ALL)), bool)
    for i, (g, c, n) in enumerate(zip(vis.group, vis.code, vis.n_trials)):
        L = lim[c] if g == "TD" else lim_all
        x = vis.loc[i, ALL].astype(float)
        mg = 1.645 * rep.SEM[ALL] / np.sqrt(n)
        out[i] = ((x < L.loc[0.025]) | (x > L.loc[0.975])).to_numpy()
        out_s[i] = ((x < L.loc[0.025] - mg) | (x > L.loc[0.975] + mg)).to_numpy()
    for j, a in enumerate(ALL):
        vis[f"out_{a}"] = out[:, j]
    vis["timing_flag"] = out[:, :4].any(1)
    vis["timing_flag_strict"] = out_s[:, :4].any(1)
    vis.to_csv(rev / "timing_visits.csv", index=False)

    def compare(vv, cols, label):
        out = []
        tdd = vv[vv.group == "TD"]
        for col in cols:
            f = 100 if col.startswith("timing_flag") else 1
            tdm = tdd.groupby("code")[col].mean()
            for g in ("CP", "ITW"):
                sel = vv.group == g
                gm = vv[sel].groupby("code")[col].mean()
                obs = gm.mean() - tdm.mean()
                boots = [rng.choice(gm.values, len(gm)).mean() - rng.choice(tdm.values, len(tdm)).mean()
                         for _ in range(n_boot)]
                pool = np.concatenate([gm.values, tdm.values])
                perm = [abs((p := rng.permutation(pool))[:len(gm)].mean() - p[len(gm):].mean()) >= abs(obs) - 1e-12
                        for _ in range(n_perm)]
                flagcol = col if col.startswith("timing_flag") else f"out_{col}"
                out.append(dict(analysis=label, measure=col, group=g, children=len(gm), visit_limbs=int(sel.sum()),
                                group_value=f * vv.loc[sel, col].mean() if f == 100 else vv.loc[sel, col].median(),
                                TD_value=f * tdd[col].mean() if f == 100 else tdd[col].median(),
                                diff_child_means=f * obs, lo=f * np.percentile(boots, 2.5),
                                hi=f * np.percentile(boots, 97.5), p=(sum(perm) + 1) / (n_perm + 1),
                                outside_TD_range=f"{int(vv.loc[sel, flagcol].sum())}/{int(sel.sum())}"))
        return out

    res = compare(vis, ALL + ["timing_flag", "timing_flag_strict"], "main")
    res = pd.DataFrame(res)
    from rev_classify import holm
    m = ~res.measure.str.startswith("timing_flag")
    res.loc[m, "p_holm"] = holm(res.loc[m, "p"].to_numpy())
    res.to_csv(rev / "timing_summary.csv", index=False)
    rep.to_csv(rev / "timing_repeatability.csv")

    # robustness: pre-treatment visits only; patients within the TD age range
    ages = pd.read_csv(rev / "visits_main_scores.csv", parse_dates=["date"])[VISIT + ["age"]]
    va = vis.merge(ages, on=VISIT, how="left")
    tda = va.loc[va.group == "TD", "age"].dropna()
    key = ["GM_preIC_on", "GM_swing_on", "TA_stance_on", "TA_swing_on", "timing_flag", "timing_flag_strict"]
    sub = compare(va[(va.group == "TD") | (va.phase == "T0")], key, "T0_only")
    sub += compare(va[(va.group == "TD") | va.age.between(tda.min(), tda.max())], key, "age_matched")
    sub = pd.DataFrame(sub)
    sub.to_csv(rev / "timing_subsets.csv", index=False)
    print(f"EMG cycles used: {len(cyc)}; visit-limbs: {vis.group.value_counts().to_dict()}")
    print("TD normal ranges (2.5-97.5 pct, % of samples ON):")
    print(lim_all.round(1).to_string())
    print(f"TD timing-flag rate (leave-one-out, any of 4 phase measures): standard "
          f"{100 * vis.loc[td, 'timing_flag'].mean():.1f}%, strict {100 * vis.loc[td, 'timing_flag_strict'].mean():.1f}%")
    print("\nRepeatability of timing measures (first two trials, all limbs):")
    print(rep.round(2).to_string())
    print("\nGroup vs TD (values: median % ON per visit-limb; for timing_flag: % of visit-limbs flagged)")
    print(res.round(3).to_string(index=False))
    print("\nRobustness (pre-treatment visits only; age-matched):")
    print(sub[["analysis", "measure", "group", "children", "visit_limbs", "diff_child_means", "lo", "hi", "p"]]
          .round(3).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
