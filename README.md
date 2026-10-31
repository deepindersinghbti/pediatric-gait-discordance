# Repeatability-Calibrated EMG–Kinematic Discordance in Pediatric Gait

Target: Confluence'27 (IEEE). Dataset: LIVE-GaitNeuroKids v1.1 (Zenodo 10.5281/zenodo.21278362, CC BY 4.0).

## Study design (approved)
- **Main (cross-sectional):** across all CP/ITW visits, how often is TA/GM activation timing abnormal
  beyond within-session trial-to-trial variability while ankle kinematics are near-normal? Stance vs swing.
- **Secondary (longitudinal pilot):** 8 children with T0 -> follow-up (T2, else T1) within the same treatment cycle.
  Reason: many children were treated repeatedly and T0/T1/T2 labels restart per treatment; only 3 have T0->T2.

## Layout
- `data/raw/` – ANALYSIS/ (unzipped) + PARTICIPANT_CHARACTERISTICS.xlsx (not tracked by git)
- `src/` – analysis scripts, run in order
- `results/` – generated outputs (not tracked by git)

## Run
    pip install -r requirements.txt
    python src/load_data.py data/raw/ANALYSIS results/

## Log
- Step 2: files already resampled to 101 points/cycle; Kinematics and SEMG step counts can differ, so
  stance/swing split = median toe-off from support labels per trial and leg.
- Step 3: 179 trial files -> 339 (trial, leg) rows; 19 legs skipped (ankle column absent, one-leg kinematics files).
