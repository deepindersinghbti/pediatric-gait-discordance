# Result tables for the Confluence 2027 paper (Paper 984)

These files are copies of the final analysis outputs in `results/rev/clean/`, which is not tracked by git.
To regenerate them, run `bash src/rev_run_all.sh` (see the main README).

| File | Contents |
|---|---|
| `visits_main_scores.csv` | Six phase scores, number of trials, age and class (standard, strict and sensitivity rules) for every classified visit-limb: the score distributions behind Table III and Fig. 3 |
| `figs/fig_score_distributions.png` | Score distributions per group with the TD limit $U_s$ and the strict limit |
| `class_rates.csv` | Class and flag percentages with 95% child-bootstrap CIs, every analysis and rule |
| `group_differences.csv` | Differences from TD, CIs, exact permutation p-values and Holm-adjusted p-values |
| `repeatability.csv` | SEM, ICC(2,1), MDC95 and δs per score, pooled and per group, with CIs |
| `positive_controls.csv` | Detection rates for every known change added to TD data (Table IV) |
| `timing_summary.csv` | EMG on/off timing measures by group, with p-values |
| `pilot_case_series.csv` | Limb-by-limb longitudinal pilot: classes, change scores and thresholds |
| `excluded_records.csv` | Every excluded child and trial-limb record, with the reason |
| `flow.csv`, `cohort_table.csv` | Cohort flow (59 → 52 children, 358 → 327 records) and Table I |

Child codes (P = patient, S = TD) are the pseudonymous codes of the public LIVE-GaitNeuroKids dataset (CC BY 4.0).
