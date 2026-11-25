"""Revision step D - positive controls (power) for the EMG flag.

Reviewer R2: "Apply synthetic timing shifts and amplitude changes to TD EMG, and report
detection rates at U_s and at U_s + delta_s. Show that the threshold can be exceeded
before concluding that EMG deviations rarely exceed variability." Also: "The EMG
discordance rule should not be satisfiable merely because the EMG threshold is
unreachable."

Method
  * Every TD visit-limb (49) is altered by a known amount in BOTH of its trials, scored
    against the leave-one-out TD reference (which is not altered), and classified with
    the limits and margins of the main analysis (computed from the unaltered data).
  * Detection rate = % of TD visit-limbs whose EMG flag (any of the four EMG scores) is on.
    The unaltered rate is the false-positive floor.
  * Alterations (EMG curves are area-normalised, 1.0 = cycle-mean activation; 1% of the
    cycle is about 10 ms at a 1-s stride):
      - timing shift of GM, TA or both muscles, 2-15% of the cycle, earlier and later;
      - late-swing GM burst (Gaussian, centre 85% of the cycle, SD 4%), peak 0.25-2.0;
      - swing- or stance-phase amplitude scaling of GM or TA (x1.5 - x3);
      - whole-cycle amplitude scaling x2 (removed by area normalisation: should be
        undetectable, a built-in check);
      - the average CP or ITW EMG deviation from the TD reference, x0.5, x1, x2
        ("a TD child with the average patient pattern");
      - ankle comparisons: constant offset and the average CP ankle deviation.
  * Change rule (longitudinal pilot): an alteration of the same size between two visits
    counts as an EMG change if any EMG score changes by more than
      delta_s (the paper's rule) or 1.96 * SEM * sqrt(1/n1 + 1/n2) (MDC95 for the
      difference of two visit means, within-session error only: a best case).

Usage:  python src/rev_positive_controls.py results/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/rev/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from rev_classify import Z, limits, load
from rev_common import SCORES, VISIT, build_reference, score_curves

EMG_COLS, ANK_COLS = [2, 3, 4, 5], [0, 1]


def renorm(new, old):
    """Rescale an altered curve so its sum equals the original curve's sum, i.e. keep
    the area normalisation of the input (a uniform scaling is then removed exactly)."""
    return new * old.sum() / new.sum()


def make_manipulations(group_dev):
    t = np.arange(101)
    M = [("none", "baseline", 0, lambda c, to: c)]
    for mus, ks in (("GM", [2]), ("TA", [1]), ("both", [1, 2])):
        for s in (2, 5, 10, 15):
            for sign, lab in ((-1, "earlier"), (1, "later")):
                def f(c, to, s=s, sign=sign, ks=ks):
                    c = c.copy()
                    for k in ks:
                        c[k] = np.roll(c[k], sign * s)
                    return c
                M.append((f"{mus} {lab} {s}%", f"timing shift {mus} {lab}", s, f))
    for A in (0.25, 0.5, 1.0, 2.0):
        bump = np.exp(-0.5 * ((t - 85) / 4.0) ** 2)
        def f(c, to, A=A, bump=bump):
            c = c.copy(); c[2] = renorm(c[2] + A * bump / 101, c[2]); return c
        M.append((f"GM late-swing burst {A}", "GM late-swing burst", A, f))
    for mus, k in (("GM", 2), ("TA", 1)):
        for phase in ("swing", "stance"):
            for fac in (1.5, 2.0, 3.0):
                def f(c, to, k=k, phase=phase, fac=fac):
                    c = c.copy(); x = c[k].copy()
                    sl = slice(int(to), None) if phase == "swing" else slice(0, int(to))
                    x[sl] *= fac; c[k] = renorm(x, c[k]); return c
                M.append((f"{mus} {phase} x{fac}", f"{mus} {phase} amplitude", fac, f))
    def f(c, to):
        c = c.copy(); c[1] = renorm(2 * c[1], c[1]); c[2] = renorm(2 * c[2], c[2]); return c
    M.append(("whole-cycle EMG x2", "whole-cycle amplitude (check)", 2.0, f))
    for g in ("CP", "ITW"):
        for lam in (0.5, 1.0, 2.0):
            def f(c, to, g=g, lam=lam):
                c = c.copy()
                for k in (1, 2):
                    c[k] = renorm(c[k] + lam * group_dev[g][k], c[k])
                return c
            M.append((f"avg {g} EMG pattern x{lam}", f"average {g} EMG pattern", lam, f))
    for off in (3.0, 5.0, 10.0):
        def f(c, to, off=off):
            c = c.copy(); c[0] = c[0] + off; return c
        M.append((f"ankle offset +{off:.0f} deg", "ankle offset (comparison)", off, f))
    def f(c, to):
        c = c.copy(); c[0] = c[0] + group_dev["CP"][0]; return c
    M.append(("avg CP ankle pattern x1", "average CP ankle pattern (comparison)", 1.0, f))
    return M


def main(results, meta_xlsx, rev):
    results, rev = Path(results), Path(rev)
    df = pd.read_csv(results / "trials.csv", parse_dates=["date"])
    curves = np.load(results / "curves.npz")["curves"]
    ref, loo = build_reference(df, curves)
    v, pairs = load(results, meta_xlsx, demean=False)          # analysed visit-limbs, all groups
    X, D = v[SCORES].to_numpy(), pairs[SCORES].to_numpy()
    is_td = (v.group == "TD").to_numpy()
    U = limits(X, v.code.to_numpy(), is_td, np.full(6, 95.0))[is_td]
    sem = np.sqrt(np.nanmean(D ** 2, axis=0) / 2)
    delta = np.nanpercentile(np.abs(D), 95, axis=0)
    vt = v[is_td].reset_index(drop=True)
    ntr = vt.n_trials.to_numpy()
    margin = Z * sem / np.sqrt(ntr)[:, None]
    mdc_change = 1.96 * sem * np.sqrt(2 / ntr)[:, None]        # same n at both visits

    # trial rows of each TD visit-limb
    key = df[VISIT].astype(str).agg("|".join, axis=1)
    vkey = vt[VISIT].astype(str).agg("|".join, axis=1)
    rows = [np.where(key == k)[0] for k in vkey]

    # average patient deviation from the TD reference (equal weight per child, analysed limbs)
    group_dev = {}
    for g in ("CP", "ITW"):
        keep = set(v.loc[v.group == g, VISIT].astype(str).agg("|".join, axis=1))
        idx = np.where(key.isin(keep))[0]
        per = [np.nanmean(curves[idx[df.code.to_numpy()[idx] == c]], axis=0) for c in np.unique(df.code.to_numpy()[idx])]
        group_dev[g] = np.nanmean(np.stack(per), axis=0) - ref

    def visit_scores(transform):
        out = np.empty((len(vt), 6))
        for i, r in enumerate(rows):
            cc = np.stack([transform(curves[j], df.toe_off.iloc[j]) for j in r])
            s = score_curves(cc, df.group.to_numpy()[r], df.code.to_numpy()[r], df.toe_off.to_numpy()[r], ref, loo)
            out[i] = s.mean(0)
        return out

    X0 = visit_scores(lambda c, to: c)
    assert np.allclose(X0, vt[SCORES].to_numpy(), equal_nan=True), "unaltered TD scores do not match the main analysis"
    res = []
    for name, family, size, f in make_manipulations(group_dev):
        Xm = visit_scores(f)
        r = dict(manipulation=name, family=family, size=size)
        for rule, cut in (("standard", U), ("strict_new", U + margin), ("strict_old", U + delta)):
            r[f"EMG_flag_{rule}"] = 100 * (Xm[:, EMG_COLS] > cut[:, EMG_COLS]).any(1).mean()
            r[f"ankle_flag_{rule}"] = 100 * (Xm[:, ANK_COLS] > cut[:, ANK_COLS]).any(1).mean()
        dX = np.abs(Xm - X0)
        r["EMG_change_delta_s"] = 100 * (dX[:, EMG_COLS] > delta[EMG_COLS]).any(1).mean()
        r["EMG_change_MDC"] = 100 * (dX[:, EMG_COLS] > mdc_change[:, EMG_COLS]).any(1).mean()
        r["max_EMG_score_change_median"] = np.nanmedian(np.nanmax(dX[:, EMG_COLS], axis=1))
        res.append(r)
    res = pd.DataFrame(res)
    res.to_csv(rev / "positive_controls.csv", index=False)
    pd.set_option("display.width", 220)
    cols = ["manipulation", "EMG_flag_standard", "EMG_flag_strict_new", "EMG_flag_strict_old",
            "EMG_change_delta_s", "EMG_change_MDC", "max_EMG_score_change_median",
            "ankle_flag_standard", "ankle_flag_strict_new", "ankle_flag_strict_old"]
    print(f"TD visit-limbs: {len(vt)}; margins (2 trials) EMG: {np.round(Z * sem[EMG_COLS] / np.sqrt(2), 2)}, "
          f"delta_s EMG: {np.round(delta[EMG_COLS], 2)}")
    print(res[cols].round(1).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:4])
