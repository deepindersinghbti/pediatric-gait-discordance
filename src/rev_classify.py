"""Revision step C (+ I) - revised strict rule and complete class tables.

What changes relative to discordance.py / checks.py (reviewers R2, R3, R4):
  * Rules (a score s of a visit-limb with n trials is abnormal if it exceeds ...)
      standard        U_s                         (TD 95th percentile; as in the paper)
      strict_new      U_s + 1.645 * SEM_s / sqrt(n)   (TD limit + measurement error of the
                                                       visit average only; new main strict rule)
      strict_old      U_s + delta_s               (the paper's robust rule, kept as sensitivity)
      eq10_standard   per-modality TD percentile chosen so that the leave-one-out TD
                      any-flag rate is ~10% for ankle AND for EMG (equal false-positive rate)
      eq10_strict_new eq10 limits + the strict_new margin
  * U_s, SEM_s and delta_s are re-estimated inside every bootstrap resample, so the
    CIs include threshold uncertainty (the eq10 percentile itself is fixed at its
    full-data value).
  * All four classes plus the two marginal flags are reported for four analyses:
      main, age_matched (patient visits within the TD age range), shape_ankle
      (ankle curves mean-centred: mean posture removed, shape kept), T0_only
      (patient visits before treatment only).
  * CIs: bias-corrected (BC) percentile intervals from the child-cluster bootstrap
    (Efron & Tibshirani 1993). BC is needed because percentile limits re-estimated in
    resamples with duplicated children are biased low, which skews plain percentile CIs.
  * Differences vs TD: child-level permutation test (classes fixed, group labels
    shuffled between children, 5000 permutations, exact p = (hits + 1) / 5001).
    Test statistic = difference in mean CHILD-LEVEL class shares (each child weighted
    equally), because children contribute different numbers of visit-limbs and the
    visit-limb rate difference is then driven by cluster sizes when events are rare.
    The visit-limb-rate permutation p is kept as p_visit. Holm adjustment of p across
    the four analyses (main, age_matched, shape_ankle, T0_only).

Usage:  python src/rev_classify.py results/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/rev/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from rev_common import SCORES, VISIT, build_reference, score_df

CLASSES = ["both_normal", "ankle_only", "EMG_only", "both_abnormal"]
OUTCOMES = CLASSES + ["ankle_flag", "EMG_flag"]
RULES = ["standard", "strict_new", "strict_old", "eq10_standard", "eq10_strict_new"]
GROUPS = ["CP", "ITW", "TD"]
Z, TARGET = 1.645, 0.10
N_BOOT, N_PERM = 2000, 5000


def affected_side(p):
    p = str(p)
    if "Hemi" in p or "Mono" in p:
        return "Left" if "Left" in p else "Right"
    return "Both"


def trial_scores(results, demean=False, boundary=None):
    """Trial-level table (trials.csv rows) with the six phase scores."""
    df = pd.read_csv(results / "trials.csv", parse_dates=["date"])
    curves = np.load(results / "curves.npz")["curves"]
    ref, loo = build_reference(df, curves)
    return pd.concat([df, score_df(df, curves, ref, loo, demean_ankle=demean, boundary=boundary)], axis=1)


def visits_from_trials(t, meta_xlsx):
    """Visit-limb scores (mean over trials, analysed limbs only, with age) and the
    first-two-trial score differences used for repeatability (all limbs)."""
    pairs = []
    for key, g in t.sort_values("trial").groupby(VISIT):
        if len(g) >= 2:
            pairs.append(dict(group=key[0], code=key[1], **{s: g.iloc[0][s] - g.iloc[1][s] for s in SCORES}))
    pairs = pd.DataFrame(pairs)
    v = t.groupby(VISIT, as_index=False).agg(n_trials=("trial", "size"), **{s: (s, "mean") for s in SCORES})
    meta = pd.read_excel(meta_xlsx, sheet_name=None)
    side = {c: affected_side(p) for g in ("CP", "ITW") for c, p in
            meta[g].drop_duplicates("CODE")[["CODE", "PATHOLOGY"]].values}
    v["affected"] = v.code.map(side).fillna("Both")
    v = v[(v.affected == "Both") | (v.affected == v.leg)].reset_index(drop=True)
    dob = {c: pd.Timestamp(d) for m in meta.values() for c, d in
           m[["CODE", "DATE OF BIRTH"]].dropna().drop_duplicates("CODE").values}
    v["age"] = [(d - dob[c]).days / 365.25 if c in dob else np.nan for c, d in zip(v.code, v.date)]
    return v, pairs


def load(results, meta_xlsx, demean):
    return visits_from_trials(trial_scores(results, demean), meta_xlsx)


def limits(X, codes, is_td, q):
    """Per-row upper limits: TD q[j]-th percentile per score; leave-one-child-out for TD rows."""
    q = np.asarray(q, float)
    Xt, ct = X[is_td], codes[is_td]

    def pct(A):
        out = np.empty(A.shape[1])
        for qq in np.unique(q):
            j = q == qq
            out[j] = np.nanpercentile(A[:, j], qq, axis=0)
        return out
    U = pct(Xt)
    Urow = np.tile(U, (len(X), 1))
    for c in np.unique(ct):
        Urow[is_td & (codes == c)] = pct(Xt[ct != c])
    return Urow


def outcomes(X, cut):
    ab = X > cut
    a, e = ab[:, :2].any(1), ab[:, 2:].any(1)
    cls = np.select([~a & ~e, a & ~e, ~a & e], [0, 1, 2], 3)
    return np.column_stack([cls == k for k in range(4)] + [a, e]).astype(float)


def all_rules(X, codes, is_td, ntr, D, q_eq):
    sem = np.sqrt(np.nanmean(D ** 2, axis=0) / 2)
    delta = np.nanpercentile(np.abs(D), 95, axis=0)
    U95 = limits(X, codes, is_td, np.full(6, 95.0))
    Ueq = limits(X, codes, is_td, q_eq)
    margin = Z * sem / np.sqrt(ntr)[:, None]
    cuts = dict(standard=U95, strict_new=U95 + margin, strict_old=U95 + delta,
                eq10_standard=Ueq, eq10_strict_new=Ueq + margin)
    return {r: outcomes(X, c) for r, c in cuts.items()}, dict(SEM=sem, delta=delta, margin_2=Z * sem / np.sqrt(2))


def find_q_eq(X, codes, is_td):
    """Common percentile per modality giving a leave-one-out TD any-flag rate closest to 10%."""
    q = np.full(6, 95.0)
    info = {}
    for name, cols in (("ankle", [0, 1]), ("EMG", [2, 3, 4, 5])):
        best = None
        for qq in np.arange(80, 99.99, 0.05):
            qv = np.full(6, 95.0); qv[cols] = qq
            U = limits(X, codes, is_td, qv)
            rate = (X[is_td][:, cols] > U[is_td][:, cols]).any(1).mean()
            key = (abs(rate - TARGET), rate)
            if best is None or key < best[0]:
                best = (key, qq, rate)
        q[cols] = best[1]
        info[name] = dict(percentile=round(best[1], 2), td_rate=best[2])
    return q, info


def bc_ci(bv, obs):
    """Bias-corrected percentile bootstrap interval (95%)."""
    bv = bv[~np.isnan(bv)]
    if len(bv) == 0 or np.isnan(obs):
        return np.nan, np.nan
    p = (bv < obs).mean() + 0.5 * (bv == obs).mean()
    p = np.clip(p, 1 / (len(bv) + 1), 1 - 1 / (len(bv) + 1))
    z0 = norm.ppf(p)
    return tuple(np.percentile(bv, 100 * norm.cdf([2 * z0 - 1.96, 2 * z0 + 1.96])))


def summarise(O, groups, mask):
    """(3 groups, 6 outcomes) proportions over rows in mask."""
    return np.array([O[mask & (groups == g)].mean(0) if (mask & (groups == g)).any()
                     else np.full(O.shape[1], np.nan) for g in GROUPS])


def perm_p(O, groups, codes, mask, g, rng):
    """Child-level permutation test for (group g - TD), all outcomes at once.
    Returns p on child-share difference, p on visit-limb-rate difference, and the
    observed child-share difference (one vote per child)."""
    sel = mask & np.isin(groups, [g, "TD"])
    kids = np.unique(codes[sel])
    hits = np.array([O[sel & (codes == k)].sum(0) for k in kids])
    rows = np.array([(sel & (codes == k)).sum() for k in kids], float)
    share = hits / rows[:, None]
    is_g = np.array([groups[sel & (codes == k)][0] == g for k in kids])
    obs_c = share[is_g].mean(0) - share[~is_g].mean(0)
    obs_v = hits[is_g].sum(0) / rows[is_g].sum() - hits[~is_g].sum(0) / rows[~is_g].sum()
    A = np.zeros((N_PERM, len(kids)), bool)
    for i in range(N_PERM):
        A[i, rng.permutation(len(kids))[:is_g.sum()]] = True
    ca = (A @ share) / A.sum(1)[:, None]
    cb = (~A @ share) / (~A).sum(1)[:, None]
    ra = (A @ hits) / (A @ rows)[:, None]
    rb = (~A @ hits) / (~A @ rows)[:, None]
    p_c = ((np.abs(ca - cb) >= np.abs(obs_c) - 1e-12).sum(0) + 1) / (N_PERM + 1)
    p_v = ((np.abs(ra - rb) >= np.abs(obs_v) - 1e-12).sum(0) + 1) / (N_PERM + 1)
    return p_c, p_v, obs_c


def holm(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    adj = np.maximum.accumulate((len(p) - np.arange(len(p))) * p[o])
    out = np.empty_like(p); out[o] = np.minimum(adj, 1)
    return out


def analyse(v, pairs, masks, stype, rng):
    """Classify visit-limbs under all rules; child-bootstrap CIs (thresholds re-estimated
    in every resample) and child-level permutation tests for every analysis in masks."""
    rate_rows, diff_rows, thr_rows = [], [], []
    X, D = v[SCORES].to_numpy(), pairs[SCORES].to_numpy()
    groups, codes, ntr = v.group.to_numpy(), v.code.to_numpy(), v.n_trials.to_numpy()
    is_td = groups == "TD"
    q_eq, eq_info = find_q_eq(X, codes, is_td)
    O, thr = all_rules(X, codes, is_td, ntr, D, q_eq)
    for j, s in enumerate(SCORES):
        thr_rows.append(dict(scores=stype, score=s, U95=np.nanpercentile(X[is_td, j], 95), delta=thr["delta"][j],
                             SEM=thr["SEM"][j], margin_2trials=thr["margin_2"][j],
                             eq10_percentile=q_eq[j],
                             U_eq10=np.nanpercentile(X[is_td, j], q_eq[j])))

    # ---------- bootstrap (thresholds re-estimated in every resample)
    kid_rows = {c: np.where(codes == c)[0] for c in np.unique(codes)}
    pcodes = pairs.code.to_numpy()
    kid_pairs = {c: np.where(pcodes == c)[0] for c in np.unique(codes)}
    strata = {g: np.unique(codes[groups == g]) for g in GROUPS}
    boot = {a: {r: np.empty((N_BOOT, 3, 6)) for r in RULES} for a in masks}
    for b in range(N_BOOT):
        pick = np.concatenate([rng.choice(strata[g], len(strata[g])) for g in GROUPS])
        idx = np.concatenate([kid_rows[c] for c in pick])
        pidx = np.concatenate([kid_pairs[c] for c in pick])
        Ob, _ = all_rules(X[idx], codes[idx], is_td[idx], ntr[idx], D[pidx], q_eq)
        for a, m in masks.items():
            for r in RULES:
                boot[a][r][b] = summarise(Ob[r], groups[idx], m[idx])

    # ---------- point estimates, CIs, permutation tests
    for a, m in masks.items():
        for r in RULES:
            est = summarise(O[r], groups, m)
            for gi, g in enumerate(GROUPS):
                sel = m & (groups == g)
                for k, o in enumerate(OUTCOMES):
                    lo, hi = bc_ci(boot[a][r][:, gi, k], est[gi, k])
                    rate_rows.append(dict(analysis=a, rule=r, group=g, outcome=o,
                                          n=int(O[r][sel, k].sum()), N=int(sel.sum()),
                                          children=len(np.unique(codes[sel])),
                                          pct=100 * est[gi, k], lo=100 * lo, hi=100 * hi,
                                          boot_median=100 * np.nanmedian(boot[a][r][:, gi, k])))
            for gi, g in enumerate(GROUPS[:2]):
                p_c, p_v, d_c = perm_p(O[r], groups, codes, m, g, rng)
                for k, o in enumerate(OUTCOMES):
                    obs = est[gi, k] - est[2, k]
                    dlo, dhi = bc_ci(boot[a][r][:, gi, k] - boot[a][r][:, 2, k], obs)
                    diff_rows.append(dict(analysis=a, rule=r, group=g, outcome=o,
                                          diff=100 * obs, lo=100 * dlo, hi=100 * dhi,
                                          diff_child=100 * d_c[k], p=p_c[k], p_visit=p_v[k],
                                          boot_median=100 * np.nanmedian(boot[a][r][:, gi, k] - boot[a][r][:, 2, k])))
    vo = v.copy()
    for r in RULES:
        vo[f"class_{r}"] = np.array(CLASSES)[O[r][:, :4].argmax(1)]
    return rate_rows, diff_rows, thr_rows, vo, eq_info


def main(results, meta_xlsx, rev):
    results, rev = Path(results), Path(rev)
    rng = np.random.default_rng(2027)
    rate_rows, diff_rows, thr_rows, visit_out = [], [], [], {}
    for stype, demean in (("main_scores", False), ("shape_ankle_scores", True)):
        v, pairs = load(results, meta_xlsx, demean)
        is_td = (v.group == "TD").to_numpy()
        td_age = v.loc[is_td & v.age.notna(), "age"]
        masks = ({"main": np.ones(len(v), bool),
                  "age_matched": is_td | v.age.between(td_age.min(), td_age.max()).to_numpy(),
                  "T0_only": is_td | (v.phase == "T0").to_numpy()} if not demean
                 else {"shape_ankle": np.ones(len(v), bool)})
        rr, dr, tr, vo, eq_info = analyse(v, pairs, masks, stype, rng)
        print(f"[{stype}] equal-rate calibration: {eq_info}")
        if not demean:
            print(f"   TD age range for age matching: {td_age.min():.1f}-{td_age.max():.1f} y")
        rate_rows += rr; diff_rows += dr; thr_rows += tr
        visit_out[stype] = vo

    rates, diffs = pd.DataFrame(rate_rows), pd.DataFrame(diff_rows)
    diffs["p_holm"] = diffs.groupby(["rule", "group", "outcome"]).p.transform(holm)
    rates.to_csv(rev / "class_rates.csv", index=False)
    diffs.to_csv(rev / "group_differences.csv", index=False)
    pd.DataFrame(thr_rows).to_csv(rev / "thresholds_rev.csv", index=False)
    for k, vo in visit_out.items():
        vo.to_csv(rev / f"visits_{k}.csv", index=False)

    # ---------- check against the paper (Table II, standard and robust point estimates)
    old = pd.read_csv(results / "table_discordance.csv")
    old["rule"] = old.definition.map({"standard": "standard", "robust": "strict_old"})
    old["outcome"] = old.cls.map({"concordant_normal": "both_normal", "ankle_only": "ankle_only",
                                  "EMG_only": "EMG_only", "concordant_abnormal": "both_abnormal"})
    mm = old.merge(rates[rates.analysis == "main"], on=["rule", "group", "outcome"])
    print(f"Paper Table II point estimates vs this run: max diff {np.abs(mm.pct_x - mm.pct_y).max():.2e} "
          f"over {len(mm)} cells (0 = reproduced; non-zero expected for the cleaned inputs)")

    # ---------- print
    fmt = lambda r: f"{r.pct:5.1f} [{r.lo:4.1f},{r.hi:5.1f}]"
    for a in ("main", "age_matched", "shape_ankle", "T0_only"):
        print(f"\n################ {a}")
        for r in RULES:
            t = rates[(rates.analysis == a) & (rates.rule == r)]
            ns = t.drop_duplicates("group").set_index("group")
            print(f"-- {r}   (n visit-limbs/children: " +
                  ", ".join(f"{g} {ns.N[g]}/{ns.children[g]}" for g in GROUPS) + ")")
            for o in OUTCOMES:
                tt = t[t.outcome == o].set_index("group")
                print(f"   {o:13s} " + "  ".join(f"{g} {fmt(tt.loc[g])}" for g in GROUPS))
            d = diffs[(diffs.analysis == a) & (diffs.rule == r)]
            for _, x in d[d.outcome.isin(["ankle_only", "EMG_only", "both_abnormal", "EMG_flag"])].iterrows():
                print(f"      {x.group} {x.outcome:13s} vs TD {x['diff']:+6.1f} [{x.lo:+6.1f},{x.hi:+6.1f}] "
                      f"p={x.p:.4f} holm={x.p_holm:.4f} (visit-rate p={x.p_visit:.4f}; child-share diff {x.diff_child:+.1f})")


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:4]))
