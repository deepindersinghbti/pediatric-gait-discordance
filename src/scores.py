"""Step 5 - Phase-specific deviation scores and within-session repeatability thresholds.

Score = RMSE between a (trial, leg) curve and the TD reference, separately for
stance (0 .. toe_off-1) and swing (toe_off .. 100), for ankle, TA and GM.
TD children are scored against their leave-one-out reference.
EMG curves are scaled by 101 so 1.0 = mean activation level over the cycle.

Repeatability: for each visit (child, date, phase, leg) with >= 2 trials, take
|score(trial a) - score(trial b)| for the first two trials; the 95th percentile of
these absolute differences (pooled over all groups) is the threshold per score.
Visit-level scores = mean over that visit's trials.

Usage:  python src/scores.py results/ [out_dir --demean-ankle]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CHANNELS = ["ankle", "TA", "GM"]
SCALE = {"ankle": 1.0, "TA": 101.0, "GM": 101.0}
SCORES = [f"{c}_{p}" for c in CHANNELS for p in ("stance", "swing")]
DEMEAN = False
VISIT = ["group", "code", "date", "phase", "leg"]


def rmse(a, b):
    return float(np.sqrt(np.nanmean((a - b) ** 2)))


def main(results, out=None):
    results = Path(results)
    out = Path(out) if out else results
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(results / "trials.csv")
    curves = np.load(results / "curves.npz")["curves"]
    r = np.load(results / "reference.npz")
    loo = dict(zip(r["loo_codes"], r["loo"]))

    for i, row in df.iterrows():
        ref = loo[row.code] if row.group == "TD" else r["ref"]
        t = int(row.toe_off)
        for k, ch in enumerate(CHANNELS):
            x, y = curves[i, k] * SCALE[ch], ref[k] * SCALE[ch]
            if DEMEAN and ch == "ankle":          # remove sensor offset: compare shape only
                x, y = x - np.nanmean(x), y - np.nanmean(y)
            df.loc[i, f"{ch}_stance"] = rmse(x[:t], y[:t])
            df.loc[i, f"{ch}_swing"] = rmse(x[t:], y[t:])
    df.to_csv(out / "scores_trial.csv", index=False)

    # --- within-session repeatability
    diffs = []
    for key, g in df.sort_values("trial").groupby(VISIT):
        if len(g) >= 2:
            a, b = g.iloc[0], g.iloc[1]
            diffs.append(dict(zip(VISIT, key), **{s: abs(a[s] - b[s]) for s in SCORES}))
    diffs = pd.DataFrame(diffs)
    diffs.to_csv(out / "repeat_diffs.csv", index=False)
    thr = diffs[SCORES].quantile(0.95)
    thr_td = diffs.loc[diffs.group == "TD", SCORES].quantile(0.95)
    pd.DataFrame({"threshold_all": thr, "threshold_TD_only": thr_td}).to_csv(out / "thresholds.csv")

    # --- visit-level scores
    visits = df.groupby(VISIT, as_index=False).agg(
        n_trials=("trial", "size"), toe_off=("toe_off", "mean"), **{s: (s, "mean") for s in SCORES})
    visits.to_csv(out / "scores_visit.csv", index=False)

    print(f"Trial-level rows scored: {len(df)}")
    print(f"Visits (child x date x phase x leg): {len(visits)}  | with 2 trials: {len(diffs)}"
          f"  (TD {sum(diffs.group == 'TD')}, CP {sum(diffs.group == 'CP')}, ITW {sum(diffs.group == 'ITW')})")
    print("\n95th-percentile repeatability thresholds (pooled | TD only):")
    for s in SCORES:
        print(f"  {s:13s} {thr[s]:7.3f} | {thr_td[s]:7.3f}")
    print("\nMedian visit score by group:")
    print(visits.groupby("group")[SCORES].median().round(3).to_string())


if __name__ == "__main__":
    # python src/scores.py results/                                         (main analysis)
    # python src/scores.py results/ results/sens_demeaned --demean-ankle   (sensitivity)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    DEMEAN = "--demean-ankle" in sys.argv
    main(*args)
