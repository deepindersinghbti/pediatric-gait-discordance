"""Step 4 - Typically-developing (TD) reference waveforms.

Per TD child: average all of that child's (trial, leg) curves -> one curve per channel.
Reference: average across TD children (each child weighted equally).
Leave-one-out references (one per TD child, built without that child) are used later
so a control is never scored against a reference that contains itself.

Usage:  python src/reference.py results/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CHANNELS = ["ankle", "TA", "GM"]


def load(results: Path):
    df = pd.read_csv(results / "trials.csv")
    curves = np.load(results / "curves.npz")["curves"]  # (rows, 3 channels, 101)
    return df, curves


def child_means(df, curves):
    """dict: TD child code -> (3, 101) mean curve over all its trials and legs."""
    td = df.index[df.group == "TD"]
    return {c: np.nanmean(curves[idx], axis=0)
            for c, idx in df.loc[td].groupby("code").groups.items()}


def reference(per_child: dict, exclude=None):
    """Equal-weight mean across TD children, optionally leaving one child out."""
    return np.nanmean(np.stack([v for c, v in per_child.items() if c != exclude]), axis=0)


def main(results):
    results = Path(results)
    df, curves = load(results)
    per_child = child_means(df, curves)
    ref = reference(per_child)
    sd = np.nanstd(np.stack(list(per_child.values())), axis=0)
    loo = {c: reference(per_child, exclude=c) for c in per_child}
    np.savez_compressed(results / "reference.npz", ref=ref, sd=sd,
                        loo_codes=np.array(list(loo)), loo=np.stack(list(loo.values())))
    print(f"TD children in reference: {len(per_child)}")
    for i, ch in enumerate(CHANNELS):
        print(f"{ch:5s}: peak at {np.argmax(ref[i]):3d}% of cycle, "
              f"min at {np.argmin(ref[i]):3d}%, range {ref[i].min():.3g} .. {ref[i].max():.3g}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    toe = df.loc[df.group == "TD", "toe_off"].median()
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.2))
    titles = ["Ankle dorsi(+)/plantar(-) flexion (deg)", "Tibialis anterior (area-normalised)",
              "Gastrocnemius medialis (area-normalised)"]
    x = np.arange(101)
    for i in range(3):
        ax[i].fill_between(x, ref[i] - sd[i], ref[i] + sd[i], alpha=0.25)
        ax[i].plot(x, ref[i], lw=2)
        ax[i].axvline(toe, ls="--", c="k", lw=1)
        ax[i].set_title(titles[i], fontsize=9)
        ax[i].set_xlabel("% gait cycle  (dashed = toe-off)")
    fig.suptitle(f"TD reference waveforms (n = {len(per_child)} children, mean ± SD between children)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(results / "fig_td_reference.png", dpi=200)
    print("Saved", results / "fig_td_reference.png")


if __name__ == "__main__":
    main(sys.argv[1])
