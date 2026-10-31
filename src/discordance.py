"""Step 6 - EMG-kinematic discordance: cross-sectional (main) + longitudinal pilot.

Part A (cross-sectional, all visits):
  * limbs: hemi/monoparetic CP -> affected leg only; diparetic CP, ITW, TD -> both legs
  * a score is ABNORMAL if it exceeds the TD 95th-percentile upper limit
    (TD limit for a TD child is computed leaving that child out);
    ROBUST version: exceeds limit + within-session repeatability threshold
  * ankle abnormal = stance or swing abnormal; EMG abnormal = any of TA/GM x stance/swing
  * 4 classes: concordant-normal, ankle-only, EMG-only, concordant-abnormal
  * 95% CIs: cluster bootstrap over children (2000 resamples)
Part B (longitudinal pilot): T0 -> follow-up (T2, else T1) within one treatment cycle;
  discordant = ankle improves beyond threshold AND no EMG score improves beyond threshold.

Usage:  python src/discordance.py results/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ANK = ["ankle_stance", "ankle_swing"]
EMG = ["TA_stance", "TA_swing", "GM_stance", "GM_swing"]
S = ANK + EMG
CLASSES = ["concordant_normal", "ankle_only", "EMG_only", "concordant_abnormal"]
rng = np.random.default_rng(2027)


def affected_side(pathology):
    p = str(pathology)
    if "Hemi" in p or "Mono" in p:
        return "Left" if "Left" in p else "Right"
    return "Both"


def classify(ank, emg):
    return np.select([~ank & ~emg, ank & ~emg, ~ank & emg], CLASSES[:3], CLASSES[3])


def boot_ci(rows, col, value, n=2000):
    """Cluster bootstrap over children of the proportion rows[col] == value."""
    codes = rows.code.unique()
    by = {c: (g[col] == value).to_numpy() for c, g in rows.groupby("code")}
    est = []
    for _ in range(n):
        pick = rng.choice(codes, len(codes), replace=True)
        x = np.concatenate([by[c] for c in pick])
        est.append(x.mean())
    return np.percentile(est, [2.5, 97.5])


def treatment_pairs(meta_xlsx, visits):
    """(code, T0 date, follow-up date, follow-up phase) within the same treatment cycle."""
    sheets = pd.read_excel(meta_xlsx, sheet_name=None)
    have = visits.groupby(["code", "phase"]).date.apply(lambda d: sorted(set(pd.to_datetime(d))))
    pairs = []
    for g in ("CP", "ITW"):
        m = sheets[g]
        dc = m.columns[0]
        m[dc] = pd.to_datetime(m[dc])
        for code, sub in m.groupby("CODE"):
            txs = sorted(sub.loc[sub.PHASE == "TX", dc])
            for i, tx in enumerate(txs):
                prv = txs[i - 1] if i else pd.Timestamp.min
                nxt = txs[i + 1] if i + 1 < len(txs) else pd.Timestamp.max
                t0 = [d for d in have.get((code, "T0"), []) if prv < d <= tx]
                for ph in ("T2", "T1"):
                    fu = [d for d in have.get((code, ph), []) if tx < d < nxt]
                    if t0 and fu:
                        pairs.append(dict(group=g, code=code, T0=max(t0), TX=tx, FU=max(fu), FU_phase=ph))
                        break
    return pd.DataFrame(pairs)


def main(results, meta_xlsx):
    results = Path(results)
    v = pd.read_csv(results / "scores_visit.csv", parse_dates=["date"])
    thr = pd.read_csv(results / "thresholds.csv", index_col=0)["threshold_all"]
    meta = pd.read_excel(meta_xlsx, sheet_name=None)
    side = {c: affected_side(p) for g in ("CP", "ITW")
            for c, p in meta[g].drop_duplicates("CODE")[["CODE", "PATHOLOGY"]].values}
    v["affected"] = v.code.map(side).fillna("Both")
    v = v[(v.affected == "Both") | (v.affected == v.leg)].copy()

    # --- TD upper limits (leave-one-child-out for TD rows)
    td = v[v.group == "TD"]
    lim_all = td[S].quantile(0.95)
    lim = pd.DataFrame([td.loc[td.code != c, S].quantile(0.95) if g == "TD" else lim_all
                        for c, g in zip(v.code, v.group)], index=v.index)
    for tag, cut in (("", lim), ("robust_", lim + thr)):
        ab = v[S].to_numpy() > cut.to_numpy()
        for j, s in enumerate(S):
            v[f"{tag}abn_{s}"] = ab[:, j]
        a = v[[f"{tag}abn_{s}" for s in ANK]].any(axis=1).to_numpy()
        e = v[[f"{tag}abn_{s}" for s in EMG]].any(axis=1).to_numpy()
        v[f"{tag}class"] = classify(a, e)
    v.to_csv(results / "discordance_visits.csv", index=False)

    out = []
    for tag in ("", "robust_"):
        for g in ("CP", "ITW", "TD"):
            rows = v[v.group == g]
            for c in CLASSES:
                lo, hi = boot_ci(rows, f"{tag}class", c)
                out.append(dict(definition=tag.rstrip("_") or "standard", group=g, cls=c,
                                n=int((rows[f"{tag}class"] == c).sum()), N=len(rows),
                                children=rows.code.nunique(),
                                pct=100 * (rows[f"{tag}class"] == c).mean(), lo=100 * lo, hi=100 * hi))
    tab = pd.DataFrame(out)
    tab.to_csv(results / "table_discordance.csv", index=False)
    print("=== Part A: cross-sectional classes (% of visit-limbs, 95% child-bootstrap CI)")
    for (d, g), t in tab.groupby(["definition", "group"], sort=False):
        print(f"\n[{d}] {g}: {t.N.iloc[0]} visit-limbs, {t.children.iloc[0]} children")
        for _, r in t.iterrows():
            print(f"   {r.cls:20s} {r.n:3d}  {r.pct:5.1f}%  [{r.lo:4.1f}, {r.hi:4.1f}]")

    # which EMG score drives EMG abnormality, per group
    print("\nEMG-abnormal visit-limbs: % flagged by each EMG score (standard definition)")
    for g in ("CP", "ITW", "TD"):
        r = v[(v.group == g) & v["class"].isin(["EMG_only", "concordant_abnormal"])]
        print(f"   {g} (n={len(r)}):", {s: round(100 * r[f'abn_{s}'].mean()) for s in EMG} if len(r) else "-")

    # --- Part B: longitudinal pilot
    pairs = treatment_pairs(meta_xlsx, v)
    long = []
    for _, p in pairs.iterrows():
        for leg in ("Right", "Left"):
            a = v[(v.code == p.code) & (v.leg == leg) & (v.date == p.T0) & (v.phase == "T0")]
            b = v[(v.code == p.code) & (v.leg == leg) & (v.date == p.FU) & (v.phase == p.FU_phase)]
            if a.empty or b.empty:
                continue
            d = b[S].iloc[0] - a[S].iloc[0]
            ank_imp = any(d[s] < -thr[s] for s in ANK)
            emg_imp = [s for s in EMG if d[s] < -thr[s]]
            emg_wor = [s for s in EMG if d[s] > thr[s]]
            status = ("discordant" if ank_imp and not emg_imp else
                      "concordant_improvement" if ank_imp else "ankle_not_improved")
            long.append(dict(group=p.group, code=p.code, leg=leg, T0=p.T0.date(), FU=p.FU.date(),
                             FU_phase=p.FU_phase, days=(p.FU - p.T0).days, status=status,
                             EMG_improved=",".join(emg_imp), EMG_worsened=",".join(emg_wor),
                             **{f"d_{s}": round(d[s], 3) for s in S}))
    long = pd.DataFrame(long)
    long.to_csv(results / "table_longitudinal.csv", index=False)
    print(f"\n=== Part B: longitudinal pilot ({long.code.nunique()} children, {len(long)} limbs)")
    print(long[["group", "code", "leg", "FU_phase", "days", "status", "d_ankle_stance", "d_ankle_swing",
                "EMG_improved", "EMG_worsened"]].to_string(index=False))
    kid = long.groupby(["group", "code"]).status.apply(lambda s: "discordant" if (s == "discordant").any() else s.iloc[0])
    print("\nChildren with >=1 discordant limb:", kid.groupby("group").apply(lambda s: f"{(s == 'discordant').sum()}/{len(s)}").to_dict())

    # --- figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"concordant_normal": "#9bbfdc", "ankle_only": "#e3a35b", "EMG_only": "#c0504d", "concordant_abnormal": "#6b4c8a"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), sharey=True)
    for ax, d in zip(axes, ("standard", "robust")):
        t = tab[tab.definition == d]
        left = np.zeros(3)
        for c in CLASSES:
            vals = t[t.cls == c].set_index("group").loc[["TD", "ITW", "CP"], "pct"].to_numpy()
            ax.barh(["TD", "ITW", "CP"], vals, left=left, color=colors[c], label=c.replace("_", " "))
            left += vals
        ax.set_title(f"{d} definition", fontsize=10)
        ax.set_xlabel("% of visit-limbs")
    axes[0].legend(fontsize=7, loc="lower left", bbox_to_anchor=(0, 1.12), ncol=4)
    fig.tight_layout()
    fig.savefig(results / "fig_discordance_classes.png", dpi=200, bbox_inches="tight")
    print("Saved", results / "fig_discordance_classes.png")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
