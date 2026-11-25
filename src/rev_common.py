"""Shared helpers for the revision analyses (rev_*.py).

Same definitions as the paper's pipeline (reference.py, scores.py):
  * TD reference = equal-weight mean of per-child mean curves; TD children are
    scored against a leave-one-out reference that excludes them;
  * score = RMSE from the reference over stance (0 .. toe_off-1) and swing
    (toe_off .. 100); EMG is area-normalised and scaled by 101 so that
    1.0 = the cycle-mean activation.
"""
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message="Mean of empty slice")
warnings.filterwarnings("ignore", message="All-NaN slice encountered")

CHANNELS = ["ankle", "TA", "GM"]
SCALE = np.array([1.0, 101.0, 101.0])
SCORES = [f"{c}_{p}" for c in CHANNELS for p in ("stance", "swing")]
ANK, EMG = SCORES[:2], SCORES[2:]
VISIT = ["group", "code", "date", "phase", "leg"]


def rmse(a, b):
    return float(np.sqrt(np.nanmean((a - b) ** 2)))


def build_reference(df, curves):
    """TD reference (3, 101) and leave-one-child-out references {code: (3, 101)}."""
    td = df[df.group == "TD"]
    per = {c: np.nanmean(curves[td.index[i]], axis=0) for c, i in td.groupby("code").indices.items()}
    ref = np.nanmean(np.stack(list(per.values())), axis=0)
    loo = {c: np.nanmean(np.stack([v for k, v in per.items() if k != c]), axis=0) for c in per}
    return ref, loo


def score_curves(curves, groups, codes, toe_offs, ref, loo, demean_ankle=False):
    """Six phase scores for each curve. curves: (n, 3, 101)."""
    out = np.full((len(curves), 6), np.nan)
    for i in range(len(curves)):
        r = loo[codes[i]] if groups[i] == "TD" else ref
        t = int(toe_offs[i])
        for k in range(3):
            x, y = curves[i, k] * SCALE[k], r[k] * SCALE[k]
            if demean_ankle and k == 0:          # shape-only ankle: remove mean posture
                x, y = x - np.nanmean(x), y - np.nanmean(y)
            out[i, 2 * k] = rmse(x[:t], y[:t])
            out[i, 2 * k + 1] = rmse(x[t:], y[t:])
    return out


def score_df(df, curves, ref, loo, demean_ankle=False, boundary=None):
    t = np.full(len(df), boundary) if boundary is not None else df.toe_off.to_numpy()
    s = score_curves(curves, df.group.to_numpy(), df.code.to_numpy(), t, ref, loo, demean_ankle)
    return pd.DataFrame(s, columns=SCORES, index=df.index)


def area_norm(c):
    """Area-normalise EMG cycles row-wise (sum over 101 samples = 1)."""
    return c / np.nansum(np.abs(c), axis=-1, keepdims=True)


def load_cycles(results_rev):
    z = np.load(results_rev / "cycles.npz")
    kin = pd.read_csv(results_rev / "cycles_kin.csv")
    emg = pd.read_csv(results_rev / "cycles_emg.csv")
    return z, kin, emg


def child_boot(rows, stat, n=2000, seed=2027, strata="group"):
    """Cluster bootstrap over children (stratified by group). stat(rows) -> 1-D array."""
    rng = np.random.default_rng(seed)
    parts = {g: {c: x for c, x in t.groupby("code")} for g, t in rows.groupby(strata)}
    out = []
    for _ in range(n):
        pick = [parts[g][c] for g in parts for c in rng.choice(list(parts[g]), len(parts[g]))]
        out.append(stat(pd.concat(pick)))
    return np.array(out)
