"""Revision step L - show the data (reviewer R2) and the counts behind the % statements.

  figs/fig_waveforms.pdf/.png   Fig. 1 revised: TD mean +- 1 SD between children (grey band)
                                with the CP and ITW group means (equal weight per child,
                                analysed limbs, cleaned data) for ankle, TA and GM; dashed line
                                = TD median cycle toe-off; GM panel shades the 85-100% pre-contact
                                window used by the timing measure.
  figs/fig_score_distributions  supplementary: visit-limb scores per group and phase, with the
                                TD normal limit U_s and U_s + strict margin (two-trial visit).
  emg_score_drivers.csv         among EMG-flagged visit-limbs (standard rule), how many were
                                flagged by each EMG score (counts behind the 64%/55%/71% text).

Colours: fixed per group (CP blue, ITW orange; TD = grey reference), validated for colour-vision
deficiency; line style is a second cue (CP solid, ITW dashed) for grayscale print.

Usage:  python src/rev_figures.py results/rev/clean/
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rev_classify import limits
from rev_common import EMG, SCORES, VISIT

COL = {"CP": "#257de0", "ITW": "#f47230", "TD": "#8a8a8a"}
LS = {"CP": "-", "ITW": "--"}
TXT, TXT2 = "#191919", "#666666"
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.edgecolor": TXT2,
                     "axes.labelcolor": TXT, "xtick.color": TXT2, "ytick.color": TXT2,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
                     "xtick.major.width": 0.6, "ytick.major.width": 0.6, "legend.frameon": False,
                     "pdf.fonttype": 42})


def group_curves(df, curves, keys, g):
    rows = df.merge(keys, on=VISIT).query("group == @g")
    per = [np.nanmean(curves[df.index[(df.code == c)].intersection(rows["index"])], axis=0)
           for c in rows.code.unique()]
    per = np.stack(per)
    return np.nanmean(per, axis=0), np.nanstd(per, axis=0), len(per)


def main(rev):
    rev = Path(rev)
    out = rev / "figs"
    out.mkdir(exist_ok=True)
    df = pd.read_csv(rev / "trials.csv", parse_dates=["date"])
    curves = np.load(rev / "curves.npz")["curves"].copy()
    curves[:, 1:] *= 101
    v = pd.read_csv(rev / "visits_main_scores.csv", parse_dates=["date"])
    keys = v[VISIT]
    dfi = df.reset_index()
    emg = pd.read_csv(rev / "cycles_emg.csv").merge(df[["group"]], left_on="row", right_index=True)
    T = emg[(emg.group == "TD") & (emg.n_liftoffs >= 1)].toe_off.median()

    # ---------------- Fig. 1: waveforms
    fig, ax = plt.subplots(1, 3, figsize=(7.16, 2.25))
    titles = ["Ankle dorsi(+)/plantar(−)flexion (deg)", "Tibialis anterior (×cycle mean)",
              "Gastrocnemius medialis (×cycle mean)"]
    x = np.arange(101)
    stats = {g: [group_curves(dfi, curves[:, k], keys, g) for k in range(3)] for g in ("TD", "CP", "ITW")}
    for k in range(3):
        a = ax[k]
        if k == 2:
            a.axvspan(85, 100, color="#efefef", lw=0, zorder=0)
            a.text(92.5, 0.98, "pre-\ncontact", transform=a.get_xaxis_transform(), ha="center", va="top",
                   fontsize=6.5, color=TXT2)
        m, s, n = stats["TD"][k]
        a.fill_between(x, m - s, m + s, color=COL["TD"], alpha=0.25, lw=0,
                       label=f"TD mean ± 1 SD (n = {n})")
        a.plot(x, m, color=COL["TD"], lw=1.0)
        for g in ("CP", "ITW"):
            m, s, n = stats[g][k]
            a.plot(x, m, color=COL[g], ls=LS[g], lw=1.4, label=f"{g} mean (n = {n})")
        a.axvline(T, color=TXT2, ls=":", lw=0.8)
        a.set_xlim(0, 100)
        a.set_xticks([0, 25, 50, 75, 100])
        a.set_title(titles[k], fontsize=8, color=TXT, loc="left")
        a.set_xlabel("% gait cycle")
        a.grid(axis="y", color="#e6e6e6", lw=0.5)
        a.set_axisbelow(True)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02), fontsize=7.5)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    for ext in ("pdf", "png"):
        fig.savefig(out / f"fig_waveforms.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ---------------- supplementary: score distributions with limits
    thr = pd.read_csv(rev / "thresholds_rev.csv")
    thr = thr[thr.scores == "main_scores"].set_index("score")
    fig, ax = plt.subplots(2, 3, figsize=(7.16, 4.0), sharex=True)
    rng = np.random.default_rng(1)
    order = ["TD", "CP", "ITW"]
    for j, s in enumerate(SCORES):
        a = ax[j % 2, j // 2]
        for i, g in enumerate(order):
            y = v.loc[v.group == g, s].dropna().to_numpy()
            a.scatter(i + rng.uniform(-0.18, 0.18, len(y)), y, s=8, color=COL[g], alpha=0.75, lw=0)
            a.hlines(np.median(y), i - 0.28, i + 0.28, color=TXT, lw=1.2)
        a.axhline(thr.U95[s], color=TXT2, lw=0.8, label="TD normal limit $U_s$")
        a.axhline(thr.U95[s] + thr.margin_2trials[s], color=TXT2, lw=0.8, ls="--",
                  label="$U_s$ + strict margin (2 trials)")
        unit = "deg" if s.startswith("ankle") else "×cycle mean"
        a.set_title(f"{s.replace('_', ' ')} ({unit})", fontsize=8, loc="left", color=TXT)
        a.set_xticks(range(3), order)
        a.grid(axis="y", color="#e6e6e6", lw=0.5)
        a.set_axisbelow(True)
    h, l = ax[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01), fontsize=7.5)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    for ext in ("pdf", "png"):
        fig.savefig(out / f"fig_score_distributions.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ---------------- counts behind "x% of EMG-abnormal visit-limbs were flagged by score s"
    X = v[SCORES].to_numpy()
    U = limits(X, v.code.to_numpy(), (v.group == "TD").to_numpy(), np.full(6, 95.0))
    ab = pd.DataFrame(X > U, columns=SCORES)
    rows = []
    for g in ("CP", "ITW", "TD"):
        sel = (v.group == g) & v.class_standard.isin(["EMG_only", "both_abnormal"])
        n = int(sel.sum())
        for s in EMG:
            k = int(ab.loc[sel, s].sum())
            rows.append(dict(group=g, EMG_flagged_visit_limbs=n, score=s, flagged_by_score=k,
                             pct=100 * k / n if n else np.nan, text=f"{k}/{n}"))
    drv = pd.DataFrame(rows)
    drv.to_csv(rev / "emg_score_drivers.csv", index=False)
    print(f"TD median cycle toe-off used in Fig. 1: {T:.0f}%")
    print("Children per curve:", {g: stats[g][0][2] for g in stats})
    print("\nEMG-flagged visit-limbs (standard rule): share flagged by each score")
    print(drv.pivot(index="score", columns="group", values="text").to_string())
    print(f"\nFigures written to {out}")


if __name__ == "__main__":
    main(sys.argv[1])
