"""Revision step J - longitudinal pilot as a descriptive case series.

Reviewers: R2 "restrict to limbs that were EMG-abnormal at baseline (otherwise there is
nothing to improve), use the same repeatability logic as for the baseline analysis";
R1/R3/R4: seven children only, acknowledge and reframe.

Pairs: same rule as discordance.py (T0 between the previous and current treatment,
follow-up T2, else T1, between the current and next treatment), analysed limbs only.
For every pair-limb:
  * baseline and follow-up class under the standard and the new strict rule
    (classes from rev_classify on the cleaned data);
  * score changes; a change counts if it exceeds
      delta_s                                  (the paper's change rule), or
      MDC95 = 1.96 * SEM * sqrt(1/n1 + 1/n2)   (two visit means; within-session SEM,
                                                so a best case: between-session error,
                                                e.g. sensor re-placement, is larger);
  * ankle change also with shape-only (mean-centred) and toe-off-registered scores.

Between-session error (R2: "add an unaffected or TD test-retest comparison if available";
R3: between-session variability): no TD child was re-tested, but the unaffected limb of
hemi/monoparetic CP children is recorded at every visit and is not the treated limb.
Consecutive visits of that limb give an upper-bound estimate of between-session error
(it also contains any real change of the unaffected limb):
  SEM_between = sqrt(mean(d^2) / 2), d = difference of consecutive visit means,
compared with the within-session SEM of a visit mean (SEM / sqrt(2)).

Usage:  python src/rev_pilot.py results/rev/clean/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ANK = ["ankle_stance", "ankle_swing"]
EMG = ["TA_stance", "TA_swing", "GM_stance", "GM_swing"]
S = ANK + EMG
EMG_CLASSES = ["EMG_only", "both_abnormal"]


def treatment_pairs(meta_xlsx, visits):
    """(code, T0 date, follow-up date, follow-up phase) within the same treatment cycle
    (copied from discordance.py so this script stands alone)."""
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


def between_session(rev, meta_xlsx, sem_within):
    """Consecutive-visit differences of the unaffected limb in hemi/monoparetic CP."""
    from rev_classify import affected_side, trial_scores
    t = trial_scores(rev)
    va = t.groupby(["group", "code", "date", "phase", "leg"], as_index=False).agg(
        n_trials=("trial", "size"), **{s: (s, "mean") for s in S})
    meta = pd.read_excel(meta_xlsx, sheet_name=None)
    side = {c: affected_side(p) for c, p in meta["CP"].drop_duplicates("CODE")[["CODE", "PATHOLOGY"]].values}
    va["affected"] = va.code.map(side)
    un = va[(va.group == "CP") & va.affected.isin(["Left", "Right"]) & (va.leg != va.affected)].sort_values("date")
    d = []
    for code, g in un.groupby("code"):
        for i in range(1, len(g)):
            a, b = g.iloc[i - 1], g.iloc[i]
            d.append(dict(code=code, days=(b.date - a.date).days, **{s: b[s] - a[s] for s in S}))
    d = pd.DataFrame(d)
    out = pd.DataFrame({"SEM_between_visit_mean": np.sqrt((d[S] ** 2).mean() / 2),
                        "SEM_within_visit_mean": sem_within[S] / np.sqrt(2)})
    out["ratio"] = out.SEM_between_visit_mean / out.SEM_within_visit_mean
    out["MDC95_between"] = 1.96 * np.sqrt(2) * out.SEM_between_visit_mean
    return d, out


def get(v, code, leg, date, phase):
    x = v[(v.code == code) & (v.leg == leg) & (v.date == date) & (v.phase == phase)]
    return None if x.empty else x.iloc[0]


def main(rev, meta_xlsx):
    rev = Path(rev)
    rd = lambda f: pd.read_csv(rev / f, parse_dates=["date"])
    v, vs, vr = rd("visits_main_scores.csv"), rd("visits_shape_ankle_scores.csv"), rd("visits_variant_registered.csv")
    thr = pd.read_csv(rev / "thresholds_rev.csv")
    thr = thr[thr.scores == "main_scores"].set_index("score")
    sem, delta = thr.SEM, thr.delta
    trials = pd.read_csv(rev / "trials.csv", parse_dates=["date"])
    pairs = treatment_pairs(meta_xlsx, v)
    rows = []
    for _, p in pairs.iterrows():
        for leg in ("Right", "Left"):
            a, b = get(v, p.code, leg, p.T0, "T0"), get(v, p.code, leg, p.FU, p.FU_phase)
            if a is None or b is None:
                continue
            mdc = 1.96 * sem * np.sqrt(1 / a.n_trials + 1 / b.n_trials)
            d = b[S].astype(float) - a[S].astype(float)
            r = dict(group=p.group, code=p.code, leg=leg, T0=p.T0.date(), FU=p.FU.date(), FU_phase=p.FU_phase,
                     days_T0_FU=(p.FU - p.T0).days, days_TX_FU=(p.FU - p.TX).days,
                     n_trials=f"{a.n_trials}/{b.n_trials}",
                     base_std=a.class_standard, fu_std=b.class_standard,
                     base_strict=a.class_strict_new, fu_strict=b.class_strict_new,
                     base_EMG_abnormal_std=a.class_standard in EMG_CLASSES,
                     base_EMG_abnormal_strict=a.class_strict_new in EMG_CLASSES,
                     ankle_improved_delta=any(d[s] < -delta[s] for s in ANK),
                     ankle_improved_MDC=any(d[s] < -mdc[s] for s in ANK),
                     EMG_improved_delta=",".join(s for s in EMG if d[s] < -delta[s]),
                     EMG_improved_MDC=",".join(s for s in EMG if d[s] < -mdc[s]),
                     EMG_worsened_MDC=",".join(s for s in EMG if d[s] > mdc[s]))
            for kind, vv in (("shape", vs), ("registered", vr)):
                aa, bb = get(vv, p.code, leg, p.T0, "T0"), get(vv, p.code, leg, p.FU, p.FU_phase)
                dd = bb[ANK].astype(float) - aa[ANK].astype(float)
                r[f"ankle_improved_MDC_{kind}"] = any(dd[s] < -mdc[s] for s in ANK)
                r[f"d_ankle_stance_{kind}"] = round(dd["ankle_stance"], 2)
            to = trials[(trials.code == p.code) & (trials.leg == leg)]
            r["toe_off_T0"] = to[(to.date == p.T0) & (to.phase == "T0")].toe_off.median()
            r["toe_off_FU"] = to[(to.date == p.FU) & (to.phase == p.FU_phase)].toe_off.median()
            r.update({f"d_{s}": round(d[s], 3) for s in S})
            r.update({f"MDC_{s}": round(mdc[s], 3) for s in S})
            rows.append(r)
    t = pd.DataFrame(rows)
    t.to_csv(rev / "pilot_case_series.csv", index=False)
    pd.set_option("display.width", 250)
    print(f"Pairs: {t.code.nunique()} children ({t.drop_duplicates('code').group.value_counts().to_dict()}), {len(t)} limbs; "
          f"follow-up {t.days_T0_FU.min()}-{t.days_T0_FU.max()} d after T0, {t.days_TX_FU.min()}-{t.days_TX_FU.max()} d after treatment")
    print(t[["group", "code", "leg", "FU_phase", "days_TX_FU", "n_trials", "base_std", "fu_std", "base_strict", "fu_strict",
             "ankle_improved_delta", "ankle_improved_MDC", "ankle_improved_MDC_shape", "ankle_improved_MDC_registered",
             "EMG_improved_MDC", "EMG_worsened_MDC", "toe_off_T0", "toe_off_FU"]].to_string(index=False))
    b = t[t.base_EMG_abnormal_std]
    print(f"\nLimbs EMG-abnormal at baseline: standard rule {len(b)} ({', '.join(b.code + ' ' + b.leg)}); "
          f"strict rule {int(t.base_EMG_abnormal_strict.sum())}")
    print(b[["code", "leg", "base_std", "fu_std", "base_strict", "fu_strict", "EMG_improved_delta", "EMG_improved_MDC"] +
            [f"d_{s}" for s in EMG] + [f"MDC_{s}" for s in EMG]].to_string(index=False))
    kid = t.groupby("code").agg(group=("group", "first"),
                                disc_MDC=("ankle_improved_MDC", "any"),
                                disc_shape=("ankle_improved_MDC_shape", "any"),
                                disc_reg=("ankle_improved_MDC_registered", "any"),
                                emg_imp=("EMG_improved_MDC", lambda s: (s != "").any()))
    print("\nChildren with ankle improvement > MDC95 (main / shape-only / registered) and any EMG improvement > MDC95:")
    print(kid.to_string())

    d, bs = between_session(rev, meta_xlsx, sem)
    bs.to_csv(rev / "between_session_unaffected_limb.csv")
    m = bs.MDC95_between
    t["ankle_improved_between_MDC"] = (t.d_ankle_stance < -m["ankle_stance"]) | (t.d_ankle_swing < -m["ankle_swing"])
    t["EMG_improved_between_MDC"] = [",".join(s for s in EMG if r[f"d_{s}"] < -m[s]) for _, r in t.iterrows()]
    t.to_csv(rev / "pilot_case_series.csv", index=False)
    print(f"\nBetween-session error, unaffected limb of hemi/monoparetic CP: {len(d)} consecutive-visit pairs, "
          f"{d.code.nunique()} children, {d.days.min()}-{d.days.max()} days apart (median {d.days.median():.0f})")
    print(bs.round(3).to_string())
    print("\nWith the between-session MDC95: ankle improvement in",
          ", ".join(t[t.ankle_improved_between_MDC].code + " " + t[t.ankle_improved_between_MDC].leg),
          "| EMG improvement in", ", ".join(t[t.EMG_improved_between_MDC != ""].code) or "none")


if __name__ == "__main__":
    main(*sys.argv[1:3])
