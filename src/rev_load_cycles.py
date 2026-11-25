"""Revision step A - keep every gait cycle, not just the trial average.

Why: reviewers asked for cycle-by-cycle phase alignment (R4), a split-half
(odd vs even cycle) repeatability estimate (R1-R3) and EMG onset/offset timing
(R3). All three need the individual cycles, which load_data.py averaged away.

For every trial file and leg this script stores
  * each ankle-angle cycle (Kinematics sheet),
  * each raw TA / GM envelope cycle with its support (foot-contact) labels
    (SEMG sheet) and that cycle's own toe-off sample.
Kinematic and EMG cycles are numbered separately in the files and their counts
differ, so they cannot be paired one-to-one; toe-off exists only for EMG cycles.

It then rebuilds the trial-average curves exactly as load_data.py did and
checks that they match results/curves.npz (the curves used in the paper).

Usage:  python src/rev_load_cycles.py data/raw/ANALYSIS results/ results/rev/
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

N = 101
NAME_RE = re.compile(r"(?P<code>[PS]\d+)-(?P<date>\d{6})-(?P<phase>\w+)-GAIT-(?P<trial>\d+)")


def lift_offs(support):
    """Samples where support goes 1 -> 0 (foot leaves the ground)."""
    return np.where((support[:-1] == 1) & (support[1:] == 0))[0] + 1


def main(data_dir, old_results, out_dir):
    data_dir, old_results, out_dir = Path(data_dir), Path(old_results), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, kin_idx, kin_c, emg_idx, ta_c, gm_c, sup_c, rebuilt = [], [], [], [], [], [], [], []
    for f in sorted(data_dir.glob("*/*/*_sync_segment.xlsx")):
        m = NAME_RE.match(f.name)
        sheets = pd.read_excel(f, sheet_name=None)
        kin, emg = sheets["Kinematics"], sheets["SEMG"]
        for leg in ("Right", "Left"):
            col = f"{leg} Ankle Dorsiflexion/Plantarflexion"
            if col not in kin.columns:          # same 19 skips as load_data.py
                continue
            r = len(rows)                        # row number = row in trials.csv
            ank = kin.pivot(index="Step", columns="Sample", values=col)
            ta = emg.pivot(index="Step", columns="Sample", values=f"{leg}_Tibialis_Anterior")
            gm = emg.pivot(index="Step", columns="Sample", values=f"{leg}_Gastrocnemius_Medialis")
            sup = emg.pivot(index="Step", columns="Sample", values=f"{leg}_Support")
            for step, x in ank.iterrows():
                kin_idx.append(dict(row=r, step=step, finite=bool(np.isfinite(x).all())))
                kin_c.append(x.to_numpy(float))
            tos = []
            for step in sup.index:
                s = sup.loc[step].to_numpy()
                lo = lift_offs(s)
                a, g = ta.loc[step].to_numpy(float), gm.loc[step].to_numpy(float)
                emg_idx.append(dict(row=r, step=step,
                                    toe_off=int(lo[0]) if len(lo) else -1, n_liftoffs=len(lo),
                                    ok_TA=bool(np.isfinite(a).all() and np.nansum(np.abs(a)) > 0),
                                    ok_GM=bool(np.isfinite(g).all() and np.nansum(np.abs(g)) > 0)))
                if len(lo):
                    tos.append(int(lo[0]))
                ta_c.append(a); gm_c.append(g); sup_c.append(s.astype(np.int8))
            # --- rebuild the trial average exactly as load_data.py did
            out = [np.nanmean(ank.to_numpy(float), axis=0)]
            for c in (ta.to_numpy(float), gm.to_numpy(float)):
                area = np.nansum(np.abs(c), axis=1, keepdims=True)
                ok = (area[:, 0] > 0) & np.isfinite(c).all(axis=1)
                out.append(np.nanmean(c[ok] / area[ok], axis=0) if ok.any() else np.full(N, np.nan))
            rebuilt.append(np.stack(out))
            rows.append(dict(group=f.parts[-3], code=m["code"], date=pd.Timestamp("20" + m["date"]),
                             phase=m["phase"], trial=int(m["trial"]), leg=leg, file=f.name,
                             toe_off=int(np.median(tos)) if tos else np.nan))
    df = pd.DataFrame(rows)
    kin_idx, emg_idx = pd.DataFrame(kin_idx), pd.DataFrame(emg_idx)

    # --- per-row cycle counts
    df["n_cyc_kin"] = kin_idx[kin_idx.finite].groupby("row").size().reindex(df.index, fill_value=0)
    df["n_cyc_TA"] = emg_idx[emg_idx.ok_TA].groupby("row").size().reindex(df.index, fill_value=0)
    df["n_cyc_GM"] = emg_idx[emg_idx.ok_GM].groupby("row").size().reindex(df.index, fill_value=0)

    # --- check against the paper's inputs
    old = pd.read_csv(old_results / "trials.csv")
    old_curves = np.load(old_results / "curves.npz")["curves"]
    rebuilt = np.stack(rebuilt)
    same_rows = (old[["code", "phase", "trial", "leg"]].values == df[["code", "phase", "trial", "leg"]].values).all()
    max_diff = np.nanmax(np.abs(rebuilt - old_curves), axis=(0, 2))
    nan_match = (np.isnan(rebuilt) == np.isnan(old_curves)).all()
    toe_match = (old.toe_off.values == df.toe_off.values).all()
    print(f"Rows: {len(df)} (paper: {len(old)}); same order: {same_rows}; toe-off identical: {toe_match}")
    print(f"Max |rebuilt - paper curve| per channel (ankle, TA, GM): {max_diff}; NaN pattern identical: {nan_match}")
    if not (same_rows and toe_match and nan_match and (max_diff < 1e-9).all()):
        sys.exit("MISMATCH - stopping")

    df.to_csv(out_dir / "trials_rev.csv", index=False)
    kin_idx.to_csv(out_dir / "cycles_kin.csv", index=False)
    emg_idx.to_csv(out_dir / "cycles_emg.csv", index=False)
    np.savez_compressed(out_dir / "cycles.npz", ankle=np.stack(kin_c), TA=np.stack(ta_c),
                        GM=np.stack(gm_c), support=np.stack(sup_c))

    # --- what the reviewers asked about: cycles per trial and toe-off detections
    print(f"\nCycles stored: {len(kin_idx)} kinematic, {len(emg_idx)} EMG")
    print("Usable cycles per trial-limb (median [min-max]):")
    for g, t in df.groupby("group"):
        print(f"   {g:3s}: ankle {t.n_cyc_kin.median():.0f} [{t.n_cyc_kin.min()}-{t.n_cyc_kin.max()}], "
              f"TA {t.n_cyc_TA.median():.0f} [{t.n_cyc_TA.min()}-{t.n_cyc_TA.max()}], "
              f"GM {t.n_cyc_GM.median():.0f} [{t.n_cyc_GM.min()}-{t.n_cyc_GM.max()}]")
    e = emg_idx.merge(df[["group"]], left_on="row", right_index=True)
    print("\nEMG cycles by number of lift-offs (0 = no toe-off found, >1 = foot left the ground twice):")
    print(e.groupby("group").n_liftoffs.value_counts().unstack(fill_value=0).to_string())
    ok = e[e.n_liftoffs >= 1]
    q = ok[ok.group == "TD"].toe_off.quantile([0.01, 0.5, 0.99])
    print(f"\nCycle-level toe-off, TD: median {q[0.5]:.0f}, 1st-99th pct {q[0.01]:.0f}-{q[0.99]:.0f}")
    for g, t in ok.groupby("group"):
        out = ~t.toe_off.between(q[0.01], q[0.99])
        print(f"   {g:3s}: median {t.toe_off.median():.0f}, range {t.toe_off.min()}-{t.toe_off.max()}, "
              f"outside TD 1-99 pct: {out.sum()}/{len(t)} cycles ({100*out.mean():.1f}%)")
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
