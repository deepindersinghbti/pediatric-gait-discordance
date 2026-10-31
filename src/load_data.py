"""Step 3 - Load LIVE-GaitNeuroKids processed gait cycles into one tidy table.

For every trial file and every leg (Right / Left) this script:
  1. reads the ankle dorsiflexion/plantarflexion angle (Kinematics sheet)
     and the tibialis anterior (TA) + gastrocnemius medialis (GM) EMG
     envelopes plus the support label (SEMG sheet);
  2. normalises EACH EMG cycle by its area (sum over 101 points = 1), so we
     compare activation SHAPE (timing), not loudness;
  3. averages all cycles of the trial -> one 101-point curve per signal;
  4. finds the stance/swing split = median sample where the foot leaves the
     ground (support 1 -> 0) across the trial's cycles;
  5. writes curves to curves.npz and one row per (trial, leg) to trials.csv.

Usage:  python src/load_data.py data/raw/ANALYSIS results/
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

N = 101
SKIPPED = []  # (trial, leg) pairs with no ankle data in the file
NAME_RE = re.compile(r"(?P<code>[PS]\d+)-(?P<date>\d{6})-(?P<phase>\w+)-GAIT-(?P<trial>\d+)")


def toe_off_index(support: np.ndarray):
    """First sample where support goes from 1 to 0 (foot leaves ground)."""
    drops = np.where((support[:-1] == 1) & (support[1:] == 0))[0]
    return int(drops[0] + 1) if len(drops) else None


def load_trial(path: Path, group: str):
    m = NAME_RE.match(path.name)
    meta = dict(group=group, code=m["code"], date=pd.Timestamp("20" + m["date"]),
                phase=m["phase"], trial=int(m["trial"]), file=path.name)
    sheets = pd.read_excel(path, sheet_name=None)
    kin, emg = sheets["Kinematics"], sheets["SEMG"]
    rows, curves = [], []
    for leg in ("Right", "Left"):
        row = dict(meta, leg=leg, issue="")
        if f"{leg} Ankle Dorsiflexion/Plantarflexion" not in kin.columns:
            SKIPPED.append(dict(meta, leg=leg, issue="ankle_column_absent"))
            continue
        # --- ankle angle: average across cycles
        ank = kin.pivot(index="Step", columns="Sample",
                        values=f"{leg} Ankle Dorsiflexion/Plantarflexion").to_numpy(float)
        # --- EMG: area-normalise each cycle, then average
        out = {}
        for mus, col in (("TA", f"{leg}_Tibialis_Anterior"), ("GM", f"{leg}_Gastrocnemius_Medialis")):
            c = emg.pivot(index="Step", columns="Sample", values=col).to_numpy(float)
            area = np.nansum(np.abs(c), axis=1, keepdims=True)
            ok = (area[:, 0] > 0) & np.isfinite(c).all(axis=1)
            out[mus] = np.nanmean(c[ok] / area[ok], axis=0) if ok.any() else np.full(N, np.nan)
            row[f"n_cycles_{mus}"] = int(ok.sum())
        # --- stance/swing split from support labels
        sup = emg.pivot(index="Step", columns="Sample", values=f"{leg}_Support").to_numpy()
        tos = [t for t in (toe_off_index(s) for s in sup) if t is not None]
        row["toe_off"] = int(np.median(tos)) if tos else np.nan
        row["n_cycles_kin"] = int(np.isfinite(ank).all(axis=1).sum())
        ank_mean = np.nanmean(ank, axis=0)
        # --- quality flags
        problems = []
        if ank.shape[1] != N or not np.isfinite(ank_mean).all():
            problems.append("ankle_missing")
        if not np.isfinite(out["TA"]).all() or not np.isfinite(out["GM"]).all():
            problems.append("emg_missing")
        if not tos:
            problems.append("no_toe_off")
        row["issue"] = ";".join(problems)
        rows.append(row)
        curves.append(np.stack([ank_mean, out["TA"], out["GM"]]))
    return rows, curves


def main(data_dir: str, out_dir: str):
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows, all_curves = [], []
    for f in sorted(data_dir.glob("*/*/*_sync_segment.xlsx")):
        try:
            r, c = load_trial(f, f.parts[-3])
        except Exception as e:  # keep going, but record the failure
            print(f"FAILED {f.name}: {e}")
            continue
        all_rows += r
        all_curves += c
    df = pd.DataFrame(all_rows)
    df.to_csv(out_dir / "trials.csv", index=False)
    np.savez_compressed(out_dir / "curves.npz", curves=np.stack(all_curves),
                        channels=np.array(["ankle", "TA", "GM"]))
    print(f"Loaded {df.file.nunique()} files -> {len(df)} (trial, leg) rows")
    print(df.groupby("group").agg(children=("code", "nunique"), files=("file", "nunique")))
    print("Toe-off (% of cycle):", df.toe_off.describe()[["min", "50%", "max"]].round(0).to_dict())
    sk = pd.DataFrame(SKIPPED)
    sk.to_csv(out_dir / "skipped_legs.csv", index=False)
    print(f"Legs skipped (ankle column absent): {len(sk)}")
    if len(sk):
        print(sk.groupby(["group", "leg"]).size().to_string())
    bad = df[df.issue != ""]
    print(f"Rows with problems: {len(bad)}")
    if len(bad):
        print(bad[["group", "code", "phase", "trial", "leg", "issue"]].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
