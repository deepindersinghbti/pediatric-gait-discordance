"""Revision step H - cohort table, exclusion flow and excluded-record list.

Reviewers R2, R3 and R4 asked for: age, sex, CP subtype, GMFCS, treatment type
and visits per child; a flow from 59 to 55 children and from the trial-limb
records to the 153 (concordance) and 151 (repeatability) visit-limbs with a
reason for each drop; an explanation of the differing ITW/TD counts; the list
of excluded children and limbs; and a comment on selection bias.

Notes
  * SEX is coded H/M in the participant file, read here as Spanish
    (H = hombre = male, M = mujer = female). Check against the dataset paper.
  * GMFCS is not recorded in the participant file.
  * TD child S18 has gait files but no participant record (no age or sex).

Usage:  python src/rev_cohort.py data/raw/ANALYSIS data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/ results/rev/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

GROUPS = ["CP", "ITW", "TD"]
VISIT = ["group", "code", "date", "phase", "leg"]


def affected_side(p):
    p = str(p)
    if "Hemi" in p or "Mono" in p:
        return "Left" if "Left" in p else "Right"
    return "Both"


def treatment_type(t):
    t = str(t).lower()
    kinds = []
    if "botulinum" in t:
        kinds.append("botulinum toxin")
    if "radiofrequency" in t or "ablation" in t:
        kinds.append("nerve ablation")
    if "cast" in t:
        kinds.append("casting")
    if "tenotomy" in t:
        kinds.append("Achilles tenotomy")
    return kinds or ["other: " + t[:40]]


def main(data_dir, meta_xlsx, results, rev):
    data_dir, results, rev = Path(data_dir), Path(results), Path(rev)
    sheets = pd.read_excel(meta_xlsx, sheet_name=None)
    meta = []
    for g in GROUPS:
        m = sheets[g].copy()
        m = m.rename(columns={m.columns[0]: "DATE"})
        m["group"] = g
        meta.append(m)
    meta = pd.concat(meta, ignore_index=True)
    meta["DATE"] = pd.to_datetime(meta.DATE)
    folders = {g: sorted(p.name for p in (data_dir / g).iterdir() if p.is_dir()) for g in GROUPS}
    t = pd.read_csv(results / "trials.csv", parse_dates=["date"])
    skipped = pd.read_csv(results / "skipped_legs.csv", parse_dates=["date"])

    # ------------------------------------------------------------ flow
    in_meta = {g: set(meta.loc[meta.group == g, "CODE"]) for g in GROUPS}
    all_kids = {g: in_meta[g] | set(folders[g]) for g in GROUPS}
    loaded = {g: set(t.loc[t.group == g, "code"]) for g in GROUPS}
    flow = []

    def add(stage, counts, note=""):
        flow.append(dict(stage=stage, **{g: counts[g] for g in GROUPS}, total=sum(counts.values()), note=note))

    add("Children in dataset (participant file or gait folder)", {g: len(all_kids[g]) for g in GROUPS},
        "TD S18 has gait files but no participant record")
    with_files = {g: set(folders[g]) for g in GROUPS}
    add("Children with processed gait files", {g: len(with_files[g]) for g in GROUPS},
        "no processed gait files: " + ", ".join(sorted(set().union(*[all_kids[g] - with_files[g] for g in GROUPS]))))
    all_files = pd.concat([t[["group", "file"]], skipped[["group", "file"]]]).drop_duplicates("file")
    files = t.drop_duplicates("file")
    add("Trial files", all_files.group.value_counts().to_dict())
    rec = pd.concat([t[["group"]], skipped[["group"]]])
    add("Trial-limb records (2 per file)", rec.group.value_counts().to_dict())
    reasons = {"ankle_column_absent": "ankle angle column absent (one-leg kinematics)",
               "ankle_cycles_misaligned": "ankle cycles not aligned to a gait event (cycle CMC < 0.6)"}
    for iss, txt in reasons.items():
        sk_i = skipped[skipped.issue == iss]
        if len(sk_i):
            add(f"  excluded: {txt}", sk_i.group.value_counts().reindex(GROUPS, fill_value=0).to_dict(),
                "children: " + ", ".join(sorted(sk_i.code.unique())))
    add("Trial-limb records analysed", t.group.value_counts().to_dict())
    lost = sorted(set().union(*[with_files[g] - loaded[g] for g in GROUPS]))
    add("Children with >= 1 analysed record", {g: len(loaded[g]) for g in GROUPS},
        "all records excluded: " + (", ".join(lost) or "none"))

    side = {c: affected_side(p) for c, p in meta.drop_duplicates("CODE")[["CODE", "PATHOLOGY"]].values}
    vl = t.groupby(VISIT).trial.nunique().rename("n_trials").reset_index()
    vl["affected"] = vl.code.map(side).fillna("Both")
    vl["analysed_limb"] = (vl.affected == "Both") | (vl.affected == vl.leg)
    add("Visit-limbs (all limbs)", vl.group.value_counts().to_dict())
    add("  excluded from concordance: unaffected limb of hemi/monoparetic CP",
        vl[~vl.analysed_limb].group.value_counts().reindex(GROUPS, fill_value=0).to_dict())
    conc = vl[vl.analysed_limb]
    add("Concordance analysis: visit-limbs", conc.group.value_counts().to_dict())
    add("Concordance analysis: children", conc.groupby("group").code.nunique().to_dict())
    add("  of which single-trial visit-limbs (kept: score = that one trial)",
        conc[conc.n_trials == 1].group.value_counts().reindex(GROUPS, fill_value=0).to_dict())
    rep = vl[vl.n_trials >= 2]
    add("Repeatability analysis: visit-limbs with >= 2 trials (all limbs)", rep.group.value_counts().to_dict())
    add("Repeatability analysis: children", rep.groupby("group").code.nunique().to_dict())
    add("  single-trial visit-limbs (all limbs), not usable for repeatability",
        vl[vl.n_trials == 1].group.value_counts().reindex(GROUPS, fill_value=0).to_dict())
    flow = pd.DataFrame(flow)

    # what the 19 skipped records did to the visit-limbs
    sk = skipped.merge(vl, on=VISIT, how="left")
    sk["effect"] = np.where(sk.n_trials.isna(), "visit-limb lost entirely",
                            np.where(sk.n_trials == 1, "visit-limb reduced to 1 trial", "visit-limb kept with >= 2 trials"))

    # ------------------------------------------------------------ cohort table
    dob = meta.dropna(subset=["DATE OF BIRTH"]).drop_duplicates("CODE").set_index("CODE")["DATE OF BIRTH"]
    sex = meta.dropna(subset=["SEX"]).drop_duplicates("CODE").set_index("CODE").SEX.str.strip()
    t["age"] = [(d - pd.Timestamp(dob[c])).days / 365.25 if c in dob else np.nan for c, d in zip(t.code, t.date)]
    rows = []
    for g in GROUPS:
        kids = sorted(loaded[g])
        first = t[t.group == g].sort_values("date").drop_duplicates("code")
        a = first.age.dropna()
        s = sex.reindex(kids)
        r = {"Group": g, "Children": len(kids),
             "Age at first analysed visit, y, mean (SD) [range]": f"{a.mean():.1f} ({a.std():.1f}) [{a.min():.1f}-{a.max():.1f}]"
             + (f", n={len(a)}" if len(a) < len(kids) else ""),
             "Sex, male/female": f"{(s == 'H').sum()}/{(s == 'M').sum()}" + (f" (+{s.isna().sum()} unknown)" if s.isna().any() else "")}
        if g == "CP":
            sub = meta[(meta.group == g) & meta.CODE.isin(kids)].drop_duplicates("CODE").PATHOLOGY.str.strip()
            sub = sub.str.replace("Left |Right ", "", regex=True)
            r["CP subtype"] = ", ".join(f"{k} {v}" for k, v in sub.value_counts().items())
        else:
            r["CP subtype"] = "-"
        r["GMFCS"] = "not reported in dataset" if g == "CP" else "-"
        if g != "TD":
            tx = meta[(meta.group == g) & meta.CODE.isin(kids) & (meta.PHASE == "TX")]
            kinds = tx.assign(k=tx.TREATMENT.map(treatment_type)).explode("k").groupby("k").CODE.nunique()
            eps = tx.groupby("CODE").size().reindex(kids, fill_value=0)
            r["Treatment (children)"] = ", ".join(f"{k} {v}" for k, v in kinds.items())
            r["Treatment episodes per child, median [range]"] = f"{eps.median():.0f} [{eps.min()}-{eps.max()}]"
        else:
            r["Treatment (children)"] = r["Treatment episodes per child, median [range]"] = "-"
        v = t[t.group == g].drop_duplicates(["code", "date", "phase"]).groupby("code").size()
        r["Analysed visits per child, median [range]"] = f"{v.median():.0f} [{v.min()}-{v.max()}]"
        r["Trial files with analysed records"] = files[files.group == g].shape[0]
        r["Visit-limbs: concordance / repeatability"] = f"{(conc.group == g).sum()} / {(rep.group == g).sum()}"
        rows.append(r)
    cohort = pd.DataFrame(rows).set_index("Group").T

    # ------------------------------------------------------------ selection bias: excluded vs included children
    exc = sorted(set().union(*[all_kids[g] - with_files[g] for g in GROUPS]))
    em = meta[meta.CODE.isin(exc)].sort_values("DATE")
    exc_tab = em.groupby("CODE").agg(group=("group", "first"), phases=("PHASE", lambda x: ",".join(x)),
                                     dob=("DATE OF BIRTH", "first"), first_date=("DATE", "first"),
                                     sex=("SEX", "first"), pathology=("PATHOLOGY", "first"),
                                     issues=("ISSUES", lambda x: "; ".join(x.dropna().astype(str))))
    exc_tab["age"] = ((exc_tab.first_date - pd.to_datetime(exc_tab.dob)).dt.days / 365.25).round(1)

    # ------------------------------------------------------------ excluded-record list (R2)
    ex = [dict(level="child", group=r.group, code=c, detail=f"phases in participant file: {r.phases}",
               reason="no processed gait files in ANALYSIS release" + (f" (file note: {r.issues})" if r.issues else ""))
          for c, r in exc_tab.iterrows()]
    ex += [dict(level="child", group=g, code=c, detail="has processed gait files",
                reason="all trial-limb records excluded (see trial-limb rows)") for g in GROUPS
           for c in sorted(with_files[g] - loaded[g])]
    ex += [dict(level="trial-limb", group=r.group, code=r.code, detail=f"{r.file} {r.leg}",
                reason=f"{reasons.get(r.issue, r.issue)}; {r.effect}") for _, r in sk.iterrows()]
    ex += [dict(level="visit-limb", group=r.group, code=r.code, detail=f"{r.date.date()} {r.phase} {r.leg}",
                reason="unaffected limb (hemi/monoparetic CP): repeatability only") for _, r in vl[~vl.analysed_limb].iterrows()]
    ex = pd.DataFrame(ex)

    flow.to_csv(rev / "flow.csv", index=False)
    cohort.to_csv(rev / "cohort_table.csv")
    ex.to_csv(rev / "excluded_records.csv", index=False)
    pd.set_option("display.width", 200)
    print("=== FLOW"); print(flow.to_string(index=False))
    print("\n=== Effect of the excluded trial-limb records"); print(sk.groupby(["issue", "group", "effect"]).size().to_string())
    print("\n=== COHORT"); print(cohort.to_string())
    print("\n=== Children without processed gait files"); print(exc_tab[["group", "phases", "age", "sex", "pathology", "issues"]].to_string())
    inc = t.sort_values("date").drop_duplicates("code").groupby("group").age.mean().round(1).to_dict()
    print("Mean age of included children at first analysed visit:", inc)
    print(f"\nExcluded-record list: {len(ex)} rows -> {rev / 'excluded_records.csv'}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
