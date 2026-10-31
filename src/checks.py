"""Step 8 - Robustness checks before writing.

1. Group comparison: difference in class rate (patient group - TD) with child-cluster
   bootstrap 95% CI, plus a child-level permutation test (group labels shuffled between children).
2. One-vote-per-child: per-child class share, then mean across children (equal weight).
3. Age: (a) Spearman correlation of age with each score within TD;
        (b) age-matched rerun keeping patient visits within the TD age range.

Reads discordance_visits.csv produced by discordance.py.
Usage:  python src/checks.py results/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

S = ["ankle_stance", "ankle_swing", "TA_stance", "TA_swing", "GM_stance", "GM_swing"]
TESTS = [("CP", "ankle_only"), ("CP", "EMG_only"), ("ITW", "EMG_only"), ("ITW", "ankle_only")]
rng = np.random.default_rng(2027)


def rate(rows, cls):
    return (rows["class"] == cls).mean()


def child_rate(rows, cls):
    return rows.assign(h=rows["class"] == cls).groupby("code").h.mean().mean()


def compare(v, g, cls, n_boot=2000, n_perm=5000):
    a, b = v[v.group == g], v[v.group == "TD"]
    obs = rate(a, cls) - rate(b, cls)
    ga = {c: x for c, x in a.groupby("code")}
    gb = {c: x for c, x in b.groupby("code")}
    boots = []
    for _ in range(n_boot):
        ra = pd.concat([ga[c] for c in rng.choice(list(ga), len(ga))])
        rb = pd.concat([gb[c] for c in rng.choice(list(gb), len(gb))])
        boots.append(rate(ra, cls) - rate(rb, cls))
    both = pd.concat([a, b])
    codes = both.code.unique()
    n_a = a.code.nunique()
    hits = 0
    for _ in range(n_perm):
        perm = set(rng.permutation(codes)[:n_a])
        x = both.code.isin(perm)
        hits += abs(rate(both[x], cls) - rate(both[~x], cls)) >= abs(obs) - 1e-12
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return obs, lo, hi, (hits + 1) / (n_perm + 1)


def ages(meta_xlsx):
    out = {}
    for g, m in pd.read_excel(meta_xlsx, sheet_name=None).items():
        for code, dob in m[["CODE", "DATE OF BIRTH"]].dropna().drop_duplicates("CODE").values:
            out[code] = pd.Timestamp(dob)
    return out


def run(results, meta_xlsx, label):
    v = pd.read_csv(Path(results) / "discordance_visits.csv", parse_dates=["date"])
    dob = ages(meta_xlsx)
    v["age"] = [(d - dob[c]).days / 365.25 if c in dob else np.nan for c, d in zip(v.code, v.date)]
    print(f"\n################ {label} ({results})")

    print("\n[1] Group difference vs TD (visit-limb rate; 95% child-bootstrap CI; permutation p)")
    for g, cls in TESTS:
        d, lo, hi, p = compare(v, g, cls)
        print(f"   {g:3s} {cls:11s}: {100*d:+6.1f} pts  [{100*lo:+6.1f}, {100*hi:+6.1f}]  p = {p:.4f}")

    print("\n[2] One vote per child (mean of per-child shares) vs per-visit rate")
    for g in ("CP", "ITW", "TD"):
        r = v[v.group == g]
        print(f"   {g:3s} (n={r.code.nunique():2d} children): " + ", ".join(
            f"{c} {100*child_rate(r, c):4.1f}% (per-visit {100*rate(r, c):4.1f}%)"
            for c in ("ankle_only", "EMG_only")))

    td = v[(v.group == "TD") & v.age.notna()]
    print(f"\n[3a] Age vs score within TD ({td.code.nunique()} children with age; Spearman rho, p)")
    print("   " + ", ".join(f"{s} {spearmanr(td.age, td[s]).statistic:+.2f} "
                           f"(p={spearmanr(td.age, td[s]).pvalue:.2f})" for s in S))
    amin, amax = td.age.min(), td.age.max()
    m = v[(v.group == "TD") | v.age.between(amin, amax)]
    print(f"\n[3b] Age-matched rerun: patient visits aged {amin:.1f}-{amax:.1f} y "
          f"(kept CP {m[m.group == 'CP'].code.nunique()}/{v[v.group == 'CP'].code.nunique()} children, "
          f"ITW {m[m.group == 'ITW'].code.nunique()}/{v[v.group == 'ITW'].code.nunique()})")
    print("   mean age: " + ", ".join(f"{g} {m[m.group == g].age.mean():.1f}" for g in ("CP", "ITW", "TD")))
    for g, cls in TESTS[:3]:
        d, lo, hi, p = compare(m, g, cls, n_perm=2000)
        print(f"   {g:3s} {cls:11s}: {100*rate(m[m.group == g], cls):4.1f}% vs TD "
              f"{100*rate(m[m.group == 'TD'], cls):4.1f}%  diff {100*d:+5.1f} [{100*lo:+5.1f}, {100*hi:+5.1f}]  p = {p:.4f}")


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], "MAIN")
    if len(sys.argv) > 3:
        run(sys.argv[3], sys.argv[2], "SHAPE-ONLY ANKLE")
