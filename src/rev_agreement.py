"""Revision step F - joint distribution of the ankle and EMG flags.

Reviewer R2: report marginal flag rates with tests (done in rev_classify: outcomes
ankle_flag / EMG_flag), plus kappa or an odds ratio, or a hierarchical logistic model
(GEE) of one flag given the other with child as the cluster; compare observed
"both abnormal" with the independence expectation; say whether "discordance" is
supported as more than two independent flags.

Per group and rule:
  * N, ankle-flag rate, EMG-flag rate, observed both-abnormal, expected under
    independence (N * p_ankle * p_EMG), observed/expected, Cohen's kappa,
    odds ratio (Haldane +0.5) with a child-cluster bootstrap 95% CI.
  * GEE (binomial, logit, exchangeable working correlation, cluster = child):
      EMG_flag ~ ankle_flag + group (TD reference), all visit-limbs.

Usage:  python src/rev_agreement.py results/rev/clean/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

FLAGS = {"ankle": ["ankle_only", "both_abnormal"], "EMG": ["EMG_only", "both_abnormal"]}


def table(a, e):
    n11, n10 = (a & e).sum(), (a & ~e).sum()
    n01, n00 = (~a & e).sum(), (~a & ~e).sum()
    return n11, n10, n01, n00


def stats(a, e):
    n11, n10, n01, n00 = table(a, e)
    n = n11 + n10 + n01 + n00
    pa, pe = a.mean(), e.mean()
    po = (n11 + n00) / n
    pexp = pa * pe + (1 - pa) * (1 - pe)
    kappa = (po - pexp) / (1 - pexp) if pexp < 1 else np.nan
    OR = ((n11 + .5) * (n00 + .5)) / ((n10 + .5) * (n01 + .5))
    return dict(N=n, ankle_rate=100 * pa, EMG_rate=100 * pe, both_obs=int(n11), both_exp=n * pa * pe,
                obs_over_exp=n11 / (n * pa * pe) if pa * pe > 0 else np.nan, kappa=kappa, OR=OR)


def main(rev, n_boot=2000):
    rev = Path(rev)
    v = pd.read_csv(rev / "visits_main_scores.csv")
    rng = np.random.default_rng(2027)
    rows, gee_rows = [], []
    for rule in ("standard", "strict_new"):
        c = v[f"class_{rule}"]
        v["A"], v["E"] = c.isin(FLAGS["ankle"]), c.isin(FLAGS["EMG"])
        for g in ("CP", "ITW", "TD", "CP+ITW", "All"):
            sub = v if g == "All" else v[v.group.isin(["CP", "ITW"])] if g == "CP+ITW" else v[v.group == g]
            r = dict(rule=rule, group=g, children=sub.code.nunique(), **stats(sub.A.to_numpy(), sub.E.to_numpy()))
            kids = {k: x for k, x in sub.groupby("code")}
            bo = []
            for _ in range(n_boot):
                s = pd.concat([kids[k] for k in rng.choice(list(kids), len(kids))])
                bo.append(stats(s.A.to_numpy(), s.E.to_numpy())["OR"])
            r["OR_lo"], r["OR_hi"] = np.exp(np.percentile(np.log(bo), [2.5, 97.5]))
            rows.append(r)
        # GEE: EMG flag given ankle flag, child as cluster
        d = v.assign(EMGf=v.E.astype(int), ANKf=v.A.astype(int))
        try:
            m = smf.gee("EMGf ~ ANKf + C(group, Treatment('TD'))", groups="code", data=d,
                        family=sm.families.Binomial(), cov_struct=sm.cov_struct.Exchangeable()).fit()
            ci = m.conf_int()
            for term in m.params.index:
                gee_rows.append(dict(rule=rule, term=term, OR=np.exp(m.params[term]),
                                     lo=np.exp(ci.loc[term, 0]), hi=np.exp(ci.loc[term, 1]), p=m.pvalues[term]))
        except Exception as ex:   # too few events under strict rules
            gee_rows.append(dict(rule=rule, term=f"not estimable: {ex}"))
    tab, gee = pd.DataFrame(rows), pd.DataFrame(gee_rows)
    tab.to_csv(rev / "flag_agreement.csv", index=False)
    gee.to_csv(rev / "flag_agreement_gee.csv", index=False)
    pd.set_option("display.width", 200)
    print(tab.round(2).to_string(index=False))
    print("\nGEE: EMG flag ~ ankle flag + group (cluster = child)")
    print(gee.round(3).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
