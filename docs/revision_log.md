# Revision log – Confluence 2027, Paper 984

Work done for the reviewer revisions, in the order it was done. Original scripts
(`src/load_data.py` … `src/checks.py`) and their outputs in `results/` are unchanged;
revision scripts are `src/rev_*.py`, outputs in `results/rev/` (git-ignored, like `results/`).

## Re-running everything

```bash
source .venv/bin/activate
# 1. bridge: reproduce the published numbers with the new code
python src/rev_load_cycles.py   data/raw/ANALYSIS results/ results/rev/
python src/rev_repeatability.py results/ results/rev/
python src/rev_cohort.py        data/raw/ANALYSIS data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/ results/rev/
python src/rev_classify.py      results/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/rev/
# 2. analysis of record: dead EMG channel removed
python src/rev_quality.py           results/ results/rev/ results/rev/clean/
python src/rev_repeatability.py     results/rev/clean/ results/rev/clean/
python src/rev_classify.py          results/rev/clean/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/rev/clean/
python src/rev_positive_controls.py results/rev/clean/ data/raw/PARTICIPANT_CHARACTERISTICS.xlsx results/rev/clean/
```

## 25 Nov 2026

**A – Keep every gait cycle (`rev_load_cycles.py`).** The original loader averaged cycles
per trial straight away. The new loader stores each cycle (3,619 kinematic, 3,931 EMG) and
rebuilds the trial averages: identical to the published curves (max difference 0).
Kinematic and EMG cycles are numbered separately in the files and cannot be paired, so
toe-off (from the EMG sheet's contact labels) is per EMG cycle only.
Result: median 9–11 cycles per trial (range 1–49). Every EMG cycle has exactly one toe-off.
TD toe-off is at 51% of the cycle (99% of TD cycles within 43–60%), not the textbook 60%.
14% of CP cycles fall outside the TD range (ITW 5.6%, TD 1.7%).

**B – Repeatability (`rev_repeatability.py`).** SEM, ICC(2,1), MDC95 with child-bootstrap
CIs, per group and pooled; odd/even-cycle split-half; cycle-level CMC.
- The paper's δs is reproduced exactly and is close to MDC95 (e.g. TA stance 0.72 vs 0.56).
- The margin for a two-trial visit average (1.645·SEM/√2) is about 40% of δs.
- Ankle ICC 0.89–0.97; EMG ICC 0.22–0.64 (children differ in EMG shape about as much as
  one child differs between two walks). EMG SEM similar in CP, ITW and TD.
- Odd vs even cycles agree closely (ICC 0.82–0.99); between-walk error is 2–5× what cycle
  noise alone predicts, so the two-trial estimate is the honest one.
- CMC across cycles: ankle 0.93, TA 0.84, GM 0.86.

**H – Cohort and flow (`rev_cohort.py`).** 59 children → 55 with processed files
(P31, P37, P44 CP; P20 ITW: no files; participant file notes missing video/IMU) →
179 trial files → 358 trial-limb records → 339 (19 without ankle column) → 183 visit-limbs →
153 for classification (30 unaffected CP limbs set aside); 151 with ≥2 trials for
repeatability. 24 classified visit-limbs have one trial only (CP 9, ITW 11, TD 4).
Sex column read as Spanish H/M (to confirm). GMFCS not in the dataset.

**C (+ I) – Revised strict rule (`rev_classify.py`).** New strict rule U_s + 1.645·SEM/√n;
old U_s + δs kept as sensitivity; equal 10% TD flag rate per modality as sensitivity;
thresholds re-estimated inside every bootstrap resample, bias-corrected CIs; child-level
permutation test on child shares; Holm across main / age-matched / shape-only / T0-only.
The pipeline reproduces the published Table II exactly on the original inputs.

**Problem found – dead EMG channel (`rev_quality.py`).** While building the positive
controls, TD child S09's right GM channel turned out to be flat in both trials (≈0% of
the GM median amplitude; next lowest channel 16%). Area normalisation had turned this
noise into a spurious waveform that entered the TD reference, the TD GM limits and the
TD background rate. Rule: exclude EMG channels below 5% of the muscle's median amplitude
(only this channel). All results from here on use the cleaned inputs (`results/rev/clean/`).
Effect: the single TD "EMG-only" case under the published strict rule was this channel
(now 0%); TD GM limits tighten, so standard-rule EMG flags in patients rise slightly
(CP 22.6 → 25.8%, ITW 26.2 → 31.0%); ankle results essentially unchanged.

**Results on cleaned data, main analysis (n = 62 CP / 42 ITW / 49 TD visit-limbs):**
- New strict rule: CP ankle-only 53.2% vs TD 4.1% (+49.1 points, p = 0.0002, Holm 0.0008);
  EMG flag CP 4.8%, ITW 2.4%, TD 4.1%: no excess.
- Standard rule: CP ankle-only 53.2% vs 8.2% (+45.1, p = 0.0002); EMG flag CP 25.8% vs
  12.2% (+13.6, p = 0.052), ITW 31.0% vs 12.2% (+18.7, p = 0.038, Holm 0.085).
- Holds under age matching, pre-treatment (T0) visits only and shape-only ankle
  (strict rule: CP ankle-only 32.3% vs 6.1%, p = 0.017).

**D – Positive controls (`rev_positive_controls.py`).** Known changes added to all 49 TD
visit-limbs (floors with no change: standard 12.2%, new strict 4.1%, old strict 0%):
- Whole-cycle EMG ×2: no change at all (area normalisation removes amplitude – check passed).
- Timing shift of both muscles by 10% of the cycle: standard 35–49%, new strict 10–12%,
  old strict 2%; by 15%: standard 49–76%, new strict 25–29%, old strict 0–6%.
- GM swing activity ×3: 63% / 37% / 0%. TA stance ×3: 65% / 39% / 0%.
- A TD child given the average CP or ITW EMG deviation: 20% / 4–8% / 0%.
- Ankle for comparison: +5° offset 29% / 12% / 4%; average CP ankle deviation 71% / 57% / 25%.
- Change rule of the longitudinal pilot: with δs an EMG change was detected in 0% of limbs
  for almost every alteration (max 26%); with MDC95 of two visit means (best case) 25–49%
  for 15% shifts and ~50% for tripled phase activity.

Interpretation: the published strict rule could essentially never flag an EMG change, so
"no EMG-only cases remained" was a property of the threshold. The new rule can be crossed,
but only by large changes and with low sensitivity; the standard rule detects 10–15% timing
shifts in roughly a third to three quarters of limbs.

**E + G – Score balance and phase alignment (`rev_variants.py`, cleaned data, main set).**
CP ankle-only stays far above TD in every variant (standard rule +35.0 to +48.3 points,
strict rule +41.1 to +49.6; all p ≤ 0.003); EMG flags under the strict rule never exceed TD.
- Registration (each EMG cycle's toe-off moved to the TD median 51%; ankle cycles with the
  trial's toe-off): CP ankle-only 53.2 → 45.2% (standard), so part of the CP ankle signal is
  stance-duration timing. EMG differences do not disappear; ITW EMG flag 33.3% vs 12.2%
  (p = 0.007), CP 29.0% (p = 0.019).
- Fixed 60% boundary and dropping the 15 trial-limbs with toe-off outside the TD 43–60% range:
  no material change.
- Toe-off extremes: 15 trial-limbs (14 CP, 1 ITW; 7 children). The 35% and 81% values come from
  trials with only 1 and 2 usable EMG cycles (P34) – unreliable. The others are consistent
  over 9–49 cycles (e.g. P15 at 70–71%): genuine short or prolonged stance.
- Amplitude-aware EMG (raw envelopes, units of the TD median cycle-mean envelope; no MVC
  normalisation available): conclusions unchanged; ITW strict-rule EMG flag 11.9% vs TD 6.1% (n.s.).
- Two EMG tests per visit (RMS over TA and GM per phase) instead of four: standard-rule EMG flags
  fall (CP 17.7, ITW 23.8, TD 8.2%); conclusions unchanged.

**F – Joint distribution of flags (`rev_agreement.py`).** Standard rule: in CP both flags occur
together as often as independence predicts (9 observed vs 10.8 expected; kappa −0.10; OR 0.51,
95% CI 0.11–2.59). GEE (cluster = child): the ankle flag does not predict the EMG flag
(OR 1.36, 0.35–5.34, p = 0.66); ITW has higher odds of an EMG flag than TD (OR 3.25, 1.28–8.28,
p = 0.014). Strict rule: 6 EMG flags in total, association not estimable.
Consequence for the paper: CP "ankle-only discordance" is frequent ankle abnormality plus EMG
near background, not a joint phenomenon beyond two independent flags.

**J – Pilot as a case series (`rev_pilot.py`).** 7 children (3 CP, 4 ITW), 14 limbs, follow-up
14–131 days after treatment. EMG-abnormal at baseline: 4 limbs under the standard rule
(P15 L, P39 R, P39 L, P27 L), none under the strict rule.
Between-session error from the unaffected limb of hemi/monoparetic CP (no TD child was re-tested;
20 consecutive-visit pairs, 10 children, median 105 days apart): ankle error of a visit mean is
2.0–2.9× the within-session value (between-session MDC95 7.1° stance, 9.3° swing), EMG only
1.1–1.4×. Against this realistic threshold, ankle improvement remains in P15 (both limbs; also
with shape-only and registered scores) and P34 right; no EMG improvement (P39 right GM stance
−0.426 vs 0.43, just below). With the positive controls, absence of EMG change is uninformative.

**K – EMG on/off timing (`rev_timing.py`).** Muscle ON where the envelope exceeds its own cycle
mean; per-cycle toe-off. Group-level (difference in child means, Holm over 12 tests):
GM active before initial contact (85–100%) +18.3 (CP) and +16.3 (ITW) percentage points, Holm
p = 0.007 for both; GM active in swing +10.1 (CP, Holm 0.025) and +8.5 (ITW, 0.031); TA active
in stance +13.5 and in swing −10.1 (CP, Holm 0.014 and 0.027). Timing outside the TD range
(any of four phase measures): CP 45.2%, ITW 42.9% vs TD 18.4% (p = 0.008, 0.011); beyond the
range by more than the measurement-error margin: CP 8.1%, ITW 11.9%, TD 0% (p = 0.027, 0.006).
Timing measures are noisy within a session (ICC 0.40–0.58, SEM 16–23 points), so group-level
results are stronger than individual flags. Crossed with the ankle flag, flags again co-occur at
chance level; ITW's dominant abnormal class becomes EMG-timing-only (45.2% vs 12.2% TD).
=> Whole-phase RMSE of area-normalised envelopes is insensitive; on/off timing shows premature
calf activity in CP and ITW. Framing change proposed to the supervisor.

**L – Figures (`rev_figures.py`).** `figs/fig_waveforms` (revised Fig. 1: CP and ITW means over
the TD band, pre-contact window shaded), `figs/fig_score_distributions` (supplementary), and
`emg_score_drivers.csv` (counts for the "which EMG score drives the flag" statements:
CP TA stance 10/16, ITW GM swing 9/13 on cleaned data).

---

## Second data problem and full re-run (25 Nov 2026, afternoon)

**Ankle cycles not aligned to a gait event.** A final screen of every ankle curve found trial-limbs
whose kinematic cycles are cut at different points of the gait cycle (the plantarflexion trough
falls anywhere between 20% and 90%), so their average is a flattened curve. Rule added to
`rev_quality.py`: drop a trial-limb when the CMC across its ankle cycles is < 0.6 or undefined
(median 0.94; next lowest kept 0.64). 12 records excluded: TD S23 (2), S24 (4), S25 (4) – all of
their records – and one trial each of CP P10 and P11. EMG cycles carry their own contact labels
and are unaffected. TD is now 22 children / 43 visit-limbs; 327 trial-limb records; 147 visit-limbs
classified (CP 62, ITW 42, TD 43); 146 with ≥ 2 trials for repeatability.
These three children had been in the TD reference and limits since the original analysis.
Also checked: P15 reaches −86° plantarflexion consistently in all sessions (likely IMU calibration
offset in a fixed-equinus foot) – kept, with a sensitivity analysis without P15.

**Everything below supersedes the numbers in the earlier entries.** One script re-runs all steps:
`bash src/rev_run_all.sh`.

- Repeatability (pooled, 146 pairs): ankle SEM 1.60°/1.68°, ICC 0.92/0.97; EMG SEM 0.16–0.21,
  ICC 0.27–0.55; MDC95 close to the paper's δs (e.g. TA stance 0.52 vs 0.62); strict margin for
  a 2-trial visit ≈ 40% of δs. Odd/even-cycle ICC 0.87–0.99. Cycle CMC ankle 0.93, TA 0.85, GM 0.86.
- Classes, main analysis, strict rule: CP ankle-only 56.5% vs TD 0% (+56.5, p = 0.0002, Holm 0.0008);
  EMG flag CP 12.9%, ITW 14.3%, TD 2.3% (p = 0.057, 0.077).
  Standard rule: CP ankle-only 41.9%, both abnormal 29.0% (TD 0%, p = 0.0004), EMG flag CP 38.7%,
  ITW 38.1% vs TD 16.3% (p = 0.017, 0.029; Holm 0.061, 0.079).
  Published strict rule: CP ankle-only 53.2%, no EMG flags in any group.
- Shape-only ankle: strict rule CP 51.6% vs TD 4.7%; published strict rule 33.9% (was 12.9% in the
  paper). The paper's "mean-centring removes most of the robust ankle signal" was largely caused by
  the misaligned TD cycles widening the TD limits.
- Every variant (registration, fixed 60%, extreme toe-offs dropped, amplitude EMG, two EMG tests,
  TD-only SEM, without P15): CP ankle-only +43.7 to +59.7 points under the strict rule (all p = 0.0002).
- Flag agreement: CP both flags 18 observed vs 17.0 expected (kappa 0.06); GEE ankle flag OR 1.28
  (p = 0.62); ITW EMG flag OR 3.11 vs TD (p = 0.017).
- Positive controls (floors 16.3 / 2.3 / 0%): 10% timing shift 42–63% / 12–14% / 0%;
  15% shift 63–79% / 35–37% / 0–5%; tripled phase activity 65% / 42–47% / 0%; average CP EMG
  pattern 30% / 7% / 0%; average CP ankle pattern 81% / 60% / 26%.
- Timing: GM active before contact +18.6 (CP) and +16.6 (ITW) points (Holm 0.013, 0.007); GM swing
  +11.1 / +9.4 (Holm 0.017, 0.013); CP TA stance +14.6, TA swing −11.1 (Holm 0.008, 0.007).
  Timing flag CP 50.0%, ITW 45.2% vs TD 18.6% (p = 0.004, 0.017); strict timing flag 12.9% / 11.9%
  vs 2.3% (p = 0.044, 0.062). Premature GM activity holds in pre-treatment visits (CP p = 0.002,
  ITW 5 children p = 0.026) and age-matched visits (p = 0.003, 0.001).
- Pilot: between-session error (unaffected CP limb, 19 pairs, 10 children) ankle 2.6–3.2× and EMG
  1.2–1.4× the within-session value (between-session MDC95 8.3° / 10.4°); ankle improvement beyond it
  in P15 (both limbs) and P34 right; no EMG improvement beyond it.

## Paper revision (25 Nov 2026)

1. **Paper figures and tables.** Wrote `src/rev_paper_assets.py`, which turns the clean results into
   four LaTeX tables (cohort, repeatability, classes, positive controls) and three figures (pipeline,
   group waveforms, forest plot of the sensitivity analyses).
   Run: `python3 src/rev_paper_assets.py results/rev/clean/ paper/camera_ready/`.
   Problem: the pipeline figure's text ran over the box edges and the cohort-table notes were wider
   than the column. Fixed by shortening the box text, slightly enlarging the figure and splitting the
   table notes over three lines.
2. **Revised paper.** Started from the current Overleaf version (5 authors, kept unchanged in
   `paper/camera_ready/main_submitted.tex`) and wrote `paper/camera_ready/main.tex`:
   - Methods now III-A to III-G (cohort and quality screen, scores, repeatability, classification
     rules, EMG timing, statistics/positive controls/sensitivity, longitudinal pilot).
   - Results now IV-A to IV-F (repeatability, classes and joint flags, sensitivity, positive
     controls, timing, pilot).
   - Algorithm 1, the class bar chart and the old tests table were removed; the reference-waveform
     figure became the group-waveform figure; Plot.png became the forest plot.
   - Three references added (Kadaba CMC, Liang-Zeger GEE, Holm): 18 in total, numbered in citation order.
   - Abstract 145 words, no citations; no "we/our/us"; Confluence header and IEEE footer on page 1.
3. **Two builds.** `main.tex` gives the clean copy (`984_paper_clean.pdf`, 7 pages).
   `main_annotated.tex` gives the same paper with each change coloured by reviewer
   (R1 blue, R2 green, R3 amber, R4 magenta) for the response package (`984_paper_annotated.pdf`).
   Text highlighting packages are not installed, so coloured text is used instead of highlight.
4. **Review note** (`docs/984_Review_Note.docx`): section and table tags now match the final paper;
   "highlighted in light X" became "marked in X text"; page count (7), abstract length (145) and
   reference count (18) filled in. The date is still a yellow placeholder.
