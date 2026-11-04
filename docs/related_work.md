# Related work notes (literature check, 2026-10-31)

## Dataset
- LIVE-GaitNeuroKids: published as a Scientific Data Data Descriptor on 2026-10-09 (cite this, not only the Research Square preprint).
  Zenodo v1.0 2026-03-22 (10.5281/zenodo.19162582); we use v1.1 (10.5281/zenodo.21278362).
- Already used by others: PACE-Net GitHub repo (zxh19970809-ship-it/PaceNet) has a LIVE-GaitNeuroKids classification
  experiment (5-fold subject-independent CV). => do NOT claim "first use of the dataset".
  Safe claim: "to our knowledge, the first repeatability-calibrated EMG-kinematic concordance analysis on this dataset".

## EMG / gait deviation indices (closest prior methods - position against these)
- Kinematic indices: Gillette Gait Index, Gait Deviation Index (GDI), Gait Profile Score (GPS).
- EMG analogues: Kerpape-Rennes EMG-based Gait Index (EDI) and EMG Profile Score (EPS = mean RMSE per muscle vs TD);
  Walking Dynamic Motor Control index (walk-DMC, synergy-based; Schwartz et al.).
  Davoudi et al., Applied Sciences 2025, "Are EMG data a fingerprint for patients with CP?" - 167 CP + 117 TD, pre/post SEMLS:
  kinematic norm-distance improved after surgery; EDI/EPS compared across responder groups.
- Our RMSE-vs-TD EMG score is essentially EPS-like => not novel by itself.
- Miljkovic et al.-type EMG envelope-vs-norm gait metric (J Neurosci Methods) - dynamic EMG shape vs norms in CP.

## EMG vs kinematics relationship in CP (supports our main finding)
- Acta Bioeng Biomech 2016 (51 CP): EMG patterns patient-specific; kinematic pathology depends on activation pattern
  "not in a direct way".
- van der Houwen et al., Gait & Posture 2011 (RCT, 22 CP): BTX-A did NOT improve sEMG patterns, yet BTX-A + rehab improved
  gait kinematics. => direct precedent for "kinematics improve, EMG shape does not" (our longitudinal idea).
- Gross et al., Clin Biomech 2015: coactivation related to drop foot, not stiff-knee gait.

## EMG repeatability (supports our noise argument)
- Granata, Padua, Abel, Gait & Posture 2005: within-session EMG waveform variability in children ~2x adult values.
- Steele et al., Gait & Posture 2019: inter-visit EMG repeatability in 20 bilateral CP similar to TD/adults; cosine
  similarity > 0.9; provides baseline for "real change vs inter-visit variability".
- Ferrari/others (PMC7857309): in healthy children, main EMG variability source = stride-to-stride (intra-subject).
- NCT06355869: repeatability of gait deviations in CP (SEM/MDC for kinematics).

## ITW (supports our ITW trend)
- Policy et al., J Pediatr Orthop 2001: premature gastrocnemius firing in SWING in both mild diplegic CP and ITW vs controls.
- Brunt et al., JSOA 2004 (5 ITW): BTX-A normalised ankle EMG timing (GM onset, TA swing duration).
- Premature/prolonged plantarflexor EMG in toe-walking (Kalen 1986; Perry 2003; Romkes & Brunner 2007).

## Refined novelty statement
1. Visit-level four-way concordance classification (kinematic x EMG) instead of separate indices.
2. Calibrated by within-session two-trial repeatability AND a TD background rate (leave-one-out).
3. Wearable IMU + sEMG (not lab motion capture), phase-specific (stance/swing).
4. Finding: EMG-shape deviations rarely exceed same-day trial-to-trial noise -> limits EMG-shape-based treatment tracking;
   CP kinematic-dominant discordance (consistent with van der Houwen 2011 and Acta 2016).
5. Practical: treatment-cycle-aware T0/T1/T2 pairing for this dataset.
