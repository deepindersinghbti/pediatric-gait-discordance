"""Revision step D0 - signal-quality screen and cleaned inputs.

Two problems in the provided data were found during the revision:

1. Dead EMG channel. TD child S09's right gastrocnemius (GM) is flat in both trials
   (mean raw envelope ~0% of the GM median, about half its samples negative). Area
   normalisation turns that noise into a large spurious waveform.
   Rule: an EMG channel (trial x limb x muscle) is excluded when its mean raw envelope is
   below 5% of that muscle's median over all trial-limbs. Small negative excursions in
   channels of normal amplitude are filter ripple and are kept. The channel is set to
   missing; the limb's other channels are kept.

2. Misaligned kinematic cycles. In some trial-limbs the ankle cycles supplied in the
   Kinematics sheet are not cut at the same gait event (the plantarflexion trough falls
   anywhere between 20% and 90% of the "cycle"), so their average is a flattened,
   meaningless curve. EMG cycles carry their own contact labels and are not affected.
   Rule: a trial-limb is excluded when the coefficient of multiple correlation (Kadaba)
   across its ankle cycles is below 0.6 or undefined (>= 2 cycles needed). Like the 19
   records without an ankle column in load_data.py, the whole trial-limb record is dropped,
   so every analysed record has both modalities.

Writes a cleaned copy of all inputs to <out>/ (trial table, trial curves, cycle tables and
cycle arrays re-indexed), so every rev_* script runs unchanged with results=rev=<out>.
Dropped records are appended to <out>/skipped_legs.csv with their reason.

Usage:  python src/rev_quality.py results/ results/rev/ results/rev/clean/
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from rev_repeatability import cmc

MIN_REL_AMP = 0.05
MIN_ANKLE_CMC = 0.6


def main(results, rev, out):
    results, rev, out = Path(results), Path(rev), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(results / "trials.csv")
    curves = np.load(results / "curves.npz")["curves"].copy()
    z = dict(np.load(rev / "cycles.npz"))
    emg = pd.read_csv(rev / "cycles_emg.csv")
    kin = pd.read_csv(rev / "cycles_kin.csv")

    # ---------------- 1. EMG amplitude screen
    rows = []
    for r in df.index:
        e = emg[emg.row == r]
        for k, m in ((1, "TA"), (2, "GM")):
            cy = z[m][e.index[e[f"ok_{m}"]]]
            if len(cy):
                rows.append(dict(row=r, group=df.group[r], code=df.code[r], phase=df.phase[r], trial=df.trial[r],
                                 leg=df.leg[r], muscle=m, k=k, n_cycles=len(cy), mean_amp=float(np.nanmean(cy)),
                                 neg_fraction=float((cy < 0).mean())))
    q = pd.DataFrame(rows)
    q["rel_amp"] = q.mean_amp / q.groupby("muscle").mean_amp.transform("median")
    q["excluded"] = q.rel_amp < MIN_REL_AMP
    bad = q[q.excluded]
    for _, b in bad.iterrows():
        curves[b.row, b.k] = np.nan
        emg.loc[emg.row == b.row, f"ok_{b.muscle}"] = False

    # ---------------- 2. ankle cycle alignment screen
    arow = []
    for r in df.index:
        k = z["ankle"][kin.index[(kin.row == r) & kin.finite]]
        arow.append(dict(row=r, group=df.group[r], code=df.code[r], phase=df.phase[r], trial=df.trial[r],
                         leg=df.leg[r], n_cycles=len(k), ankle_cycle_cmc=cmc(k) if len(k) >= 2 else np.nan))
    a = pd.DataFrame(arow)
    a["excluded"] = (a.n_cycles >= 2) & ~(a.ankle_cycle_cmc >= MIN_ANKLE_CMC)
    drop = a.loc[a.excluded, "row"].to_numpy()

    # ---------------- write cleaned, re-indexed inputs
    keep = np.setdiff1d(df.index.to_numpy(), drop)
    new_id = {old: i for i, old in enumerate(keep)}
    df2 = df.loc[keep].reset_index(drop=True)
    kin2 = kin[kin.row.isin(keep)]
    emg2 = emg[emg.row.isin(keep)]
    z2 = {"ankle": z["ankle"][kin2.index], "TA": z["TA"][emg2.index], "GM": z["GM"][emg2.index],
          "support": z["support"][emg2.index]}
    kin2 = kin2.assign(row=kin2.row.map(new_id)).reset_index(drop=True)
    emg2 = emg2.assign(row=emg2.row.map(new_id)).reset_index(drop=True)
    df2.to_csv(out / "trials.csv", index=False)
    np.savez_compressed(out / "curves.npz", curves=curves[keep], channels=np.array(["ankle", "TA", "GM"]))
    np.savez_compressed(out / "cycles.npz", **z2)
    kin2.to_csv(out / "cycles_kin.csv", index=False)
    emg2.to_csv(out / "cycles_emg.csv", index=False)
    tr = pd.read_csv(rev / "trials_rev.csv")
    tr.loc[keep].reset_index(drop=True).to_csv(out / "trials_rev.csv", index=False)
    q.to_csv(out / "emg_quality.csv", index=False)
    a.to_csv(out / "ankle_quality.csv", index=False)
    sk = pd.read_csv(results / "skipped_legs.csv")
    new = df.loc[drop, ["group", "code", "date", "phase", "trial", "file", "leg"]].assign(issue="ankle_cycles_misaligned")
    pd.concat([sk, new]).to_csv(out / "skipped_legs.csv", index=False)
    for f in ("thresholds.csv", "table_discordance.csv"):
        shutil.copy(results / f, out / f)

    print(f"EMG channels screened: {len(q)}; excluded (< {MIN_REL_AMP:.0%} of muscle median): {len(bad)}")
    print(bad[["group", "code", "phase", "trial", "leg", "muscle", "rel_amp", "neg_fraction"]].round(4).to_string(index=False))
    nxt = q[~q.excluded].sort_values("rel_amp").iloc[0]
    print(f"Lowest kept EMG channel: {nxt.code} {nxt.phase} trial {nxt.trial} {nxt.leg} {nxt.muscle}, rel. amplitude {nxt.rel_amp:.2f}")
    print(f"\nAnkle cycle CMC, all trial-limbs: median {a.ankle_cycle_cmc.median():.2f}; "
          f"excluded (< {MIN_ANKLE_CMC} or undefined): {len(drop)}")
    print(a[a.excluded].round(2).to_string(index=False))
    kept = a[~a.excluded & a.ankle_cycle_cmc.notna()].sort_values("ankle_cycle_cmc").head(4)
    print("Lowest kept:", ", ".join(f"{x.code} {x.phase} t{x.trial} {x.leg} {x.ankle_cycle_cmc:.2f}" for _, x in kept.iterrows()))
    print(f"\nTrial-limb records: {len(df)} -> {len(df2)}; children per group: "
          f"{df2.groupby('group').code.nunique().to_dict()}")
    print(f"Cleaned inputs written to {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
