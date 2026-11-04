"""Paper figures (vector PDF, IEEE column widths).

Fig. 1: TD reference waveforms (ankle, TA, GM), full text width.
Fig. 2: four-way concordance classes per group, main vs shape-only ankle, single column.

Usage:  python src/figures.py results/ results/sens_demeaned paper/figs/
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
                     "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.linewidth": 0.6,
                     "pdf.fonttype": 42})
COL, TXT = 3.4869, 7.1399  # IEEEtran column / text width (in)
CLASSES = ["concordant_normal", "ankle_only", "EMG_only", "concordant_abnormal"]
LABEL = {"concordant_normal": "Both normal", "ankle_only": "Ankle-only",
         "EMG_only": "EMG-only", "concordant_abnormal": "Both abnormal"}
COLOR = {"concordant_normal": "#a8c6e0", "ankle_only": "#e39a4a", "EMG_only": "#b8433f",
         "concordant_abnormal": "#5e4687"}


def fig_reference(res, out):
    r = np.load(res / "reference.npz")
    df = pd.read_csv(res / "trials.csv")
    toe = df.loc[df.group == "TD", "toe_off"].median()
    ref, sd = r["ref"].copy(), r["sd"].copy()
    ref[1:] *= 101
    sd[1:] *= 101
    x = np.arange(101)
    fig, ax = plt.subplots(1, 3, figsize=(TXT, 1.55))
    titles = ["(a) Ankle dorsi(+)/plantar(-)flexion", "(b) Tibialis anterior", "(c) Gastrocnemius medialis"]
    ylab = ["Angle (deg)", "Normalised envelope", "Normalised envelope"]
    for i in range(3):
        ax[i].fill_between(x, ref[i] - sd[i], ref[i] + sd[i], color="#9bbfdc", alpha=0.6, lw=0)
        ax[i].plot(x, ref[i], color="#1f4e79", lw=1.2)
        ax[i].axvline(toe, ls="--", c="k", lw=0.6)
        ax[i].set_title(titles[i])
        ax[i].set_ylabel(ylab[i])
        ax[i].set_xlabel("Gait cycle (%)")
        ax[i].set_xlim(0, 100)
        ax[i].spines[["top", "right"]].set_visible(False)
    fig.tight_layout(pad=0.3, w_pad=1.0)
    fig.savefig(out / "fig_reference.pdf")


def fig_classes(res, sens, out):
    fig, axes = plt.subplots(2, 1, figsize=(COL, 2.05), sharex=True)
    for ax, (path, title) in zip(axes, ((res, "(a) Main scores"), (sens, "(b) Shape-only ankle scores"))):
        t = pd.read_csv(path / "table_discordance.csv")
        t = t[t.definition == "standard"]
        groups = ["TD", "ITW", "CP"]
        left = np.zeros(3)
        for c in CLASSES:
            vals = t[t.cls == c].set_index("group").loc[groups, "pct"].to_numpy()
            ax.barh(groups, vals, left=left, color=COLOR[c], label=LABEL[c], height=0.62,
                    edgecolor="white", lw=0.4)
            for y, (l, v) in enumerate(zip(left, vals)):
                if v >= 7:
                    ax.text(l + v / 2, y, f"{v:.0f}", ha="center", va="center", fontsize=6.5,
                            color="white" if c != "concordant_normal" else "black")
            left += vals
        ax.set_title(title, loc="left")
        ax.set_xlim(0, 100)
        ax.spines[["top", "right"]].set_visible(False)
    axes[1].set_xlabel("Visit-limbs (%)")
    axes[0].legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.30), frameon=False,
                   handlelength=1.0, columnspacing=0.8)
    fig.tight_layout(pad=0.3, h_pad=0.6)
    fig.savefig(out / "fig_classes.pdf")


if __name__ == "__main__":
    res, sens, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    fig_reference(res, out)
    fig_classes(res, sens, out)
    print("Saved", out / "fig_reference.pdf", out / "fig_classes.pdf")
