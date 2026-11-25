"""Fill the user's review-note template (Review_Note__FINAL.docx) with the Paper 984 response.
Keeps the template's styles, page setup, run formatting and numbering; replaces the body."""
import re
from xml.sax.saxutils import escape

SRC = "unpacked/word/document.xml"
NUM = "unpacked/word/numbering.xml"

BASE = '<w:rFonts w:eastAsia="Times New Roman" w:cs="Times New Roman"/>'
SZ = '<w:sz w:val="24"/><w:szCs w:val="24"/>'
REV = {1: ("1F6FB2", "CDE5F7", "blue"), 2: ("00B050", "D5EFD5", "green"),
       3: ("BF8F00", "FFF2CC", "amber"), 4: ("C2185B", "F9DCE8", "magenta")}
NUMID = {1: 21, 2: 22, 3: 23, 4: 24, "comp": 25}


def run(text, b=False, i=False, color=None, sz=SZ, shd=None, sub=False, hl=False):
    rpr = BASE + ("<w:b/><w:bCs/>" if b else "") + ("<w:i/><w:iCs/>" if i else "")
    rpr += f'<w:color w:val="{color}"/>' if color else ""
    rpr += '<w:highlight w:val="yellow"/>' if hl else ""
    rpr += sz + (f'<w:shd w:fill="{shd}" w:val="clear"/>' if shd else "")
    rpr += '<w:vertAlign w:val="subscript"/>' if sub else ""
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def rich(text, **kw):
    """Plain text with U_s / δ_s subscripts and [..] placeholders highlighted for finalising."""
    out = []
    for part in re.split(r"((?:U|δ)_s|\[[^\]]+\])", text):
        if not part:
            continue
        if re.fullmatch(r"(U|δ)_s", part):
            out += [run(part[0], **kw), run("s", sub=True, **kw)]
        elif part.startswith("["):
            out.append(run(part, hl=True, **kw))
        else:
            out.append(run(part, **kw))
    return "".join(out)


def para(runs, jc="both", before=110, after=110, line=283, ind=None, num=None, style="Normal", black=False):
    ppr = f'<w:pStyle w:val="{style}"/>'
    if num is not None:
        ppr += f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>'
    ppr += f'<w:spacing w:lineRule="auto" w:line="{line}" w:before="{before}" w:after="{after}"/>'
    ppr += f'<w:ind w:start="{ind}"/>' if ind else ""
    ppr += f'<w:jc w:val="{jc}"/>'
    ppr += '<w:rPr><w:color w:val="000000"/></w:rPr>' if black else "<w:rPr/>"
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs}</w:p>"


K = "000000"
body = []
P = body.append

# ------------------------------------------------------------------ cover letter
P(para(run("Date: ") + run("[25 Nov, 2026]", hl=True), jc="end"))
P(para(run("Dear Editor,")))
P(para(run("2027 17th International Conference on Cloud Computing, Data Science & Engineering (Confluence),")))
P(para(run("Subject: Submission of Final Camera-Ready Manuscript – Paper ID: ") + run("984", b=True)))
P(para(run("We are submitting the final camera-ready version of our paper titled “")
       + run("Repeatability-Calibrated EMG–Kinematic Discordance in Pediatric Gait: A Cross-Sectional and "
             "Longitudinal Pilot Study with Wearable Sensors", b=True)
       + run("” for Confluence 2027. We have carefully considered the comments provided by all four reviewers and "
             "made substantial revisions to address their concerns, in particular a data-quality screen that "
             "corrected two problems in the provided data, repeatability re-estimated in the SEM/ICC/MDC framework "
             "with a revised strict rule, positive controls for the EMG flag, EMG on/off timing measures, a joint "
             "analysis of the ankle and EMG flags, and an expanded set of sensitivity analyses. All results were "
             "recomputed after the data-quality screen.")))
hl_runs = run("Please find attached the revised manuscript along with a detailed, point-by-point response to the "
              "reviewers’ comments below. In the enclosed annotated copy of the manuscript, changes made in response to ")
for r in (1, 2, 3, 4):
    col, _, name = REV[r]
    hl_runs += run(f"Reviewer {r}", b=True) + run(" are ") + run(f"marked in {name} text", b=True, color=col)
    hl_runs += run(", " if r < 3 else (", and " if r == 3 else ""))
hl_runs += run(", matching the tags below (where a change answers several reviewers, the colour of the most specific comment is used); a clean copy without colour marking is also enclosed for final submission.")
P(para(hl_runs))
P(para(run("We hope the revised manuscript meets the expectations of the reviewers and the Technical Program "
            "Committee. Thank you for considering our submission.")))
P(para(run("Sincerely,")))
P(para(run("Deepinder Singh")))
P(para(run("(on behalf of all authors)")))
P('<w:p><w:pPr><w:pStyle w:val="Normal"/><w:rPr/></w:pPr></w:p>')
P(para(run("Response to Reviewers’ Comments", b=True, color=K), before=0, black=True))

# ------------------------------------------------------------------ responses
R = {
1: ("Four concerns below, each marked in blue text where addressed.", [
 ("The repeatability calibration is based on only two trials.",
  "Repeatability is now reported as SEM, ICC(2,1) and MDC95 with child-bootstrap 95% CIs (146 visit-limbs). An "
  "independent odd/even-cycle split-half estimate agrees closely (ICC 0.87–0.99), and walk-to-walk error is 2.2–4.5× "
  "cycle-to-cycle noise, so the two-trial estimate is the conservative choice; more walks per session are listed as "
  "future work.", "Sec. III-C, IV-A, Table II."),
 ("The clinical validity of the proposed classification remains uncertain.",
  "The dataset contains no clinical outcome scores (GMFCS is not recorded), so the classification is now presented as "
  "a measurement-level description; clinical validation is stated as a limitation and future work.", "Sec. V."),
 ("The longitudinal evidence is limited to seven children.",
  "The pilot is reframed as an exploratory case series: EMG improvement is assessed only in limbs EMG-abnormal at "
  "baseline (5 under the standard rule, 3 under the strict rule), change is judged against a between-session error "
  "from untreated limbs, and the positive controls show that absence of EMG change is uninformative.",
  "Sec. III-G, IV-F."),
 ("The substantial sensitivity of the ankle-related findings to sensor-offset correction raises concerns about "
  "measurement reliability.",
  "Most of the submitted drop after mean-centring (41.9% → 12.9%) came from three TD children whose kinematic cycles "
  "were not aligned to a gait event, which widened the TD shape limits. After excluding these records, shape-only CP "
  "ankle abnormality is 51.6% vs 4.7% in TD. Untreated CP limbs show between-session ankle error 2.6–3.2× the "
  "within-session error, so treatment-tracking claims are limited to shape-based scores.", "Sec. III-A, IV-C, V."),
]),
2: ("Fifteen points below, each marked in green text where addressed.", [
 ("Add positive controls and a power analysis for the EMG flag; apply synthetic timing shifts and amplitude changes "
  "to TD EMG and report detection rates at U_s and at U_s+δ_s.",
  "Known changes were added to all 43 TD visit-limbs. A 15% timing shift is detected in 63–79% of limbs at U_s, "
  "35–37% under the revised strict rule and 0–5% at U_s+δ_s; a whole-cycle amplitude change is invisible after area "
  "normalisation. The submitted U_s+δ_s rule could essentially never flag EMG, so the conclusion based on it is "
  "withdrawn.", "Sec. III-F, IV-D, Table IV."),
 ("Re-estimate repeatability properly (δ_s per group or TD-only; SEM, ICC and MDC95 with CIs; √2 correction; "
  "waveform-level repeatability; thresholds inside the bootstrap).",
  "All added: pooled and per-group SEM, ICC(2,1) and MDC95 with child-bootstrap CIs; a margin of 1.645·SEM/√n for "
  "visit means; CMC across cycles (ankle 0.93, TA 0.85, GM 0.86) and between-trial RMSE. Limits and SEM are "
  "re-estimated in every resample (bias-corrected CIs); a TD-only calibration gives the same conclusions.",
  "Sec. III-C, III-F, IV-A, IV-C, Table II."),
 ("Consider a less redundant calibration; make clear what U_s+δ_s is supposed to mean.",
  "Adopted: the strict rule now inflates U_s only by the measurement error of the visit mean (1.645·SEM/√n), meaning "
  "“beyond the TD limit with 95% confidence”. U_s+δ_s is kept as a sensitivity analysis and described as "
  "double-counting trial variability.", "Sec. III-D."),
 ("Analyse the joint distribution of flags (marginal rates with tests, kappa, odds ratio or GEE, observed vs expected "
  "“both abnormal”).",
  "EMG flags: CP 38.7% and ITW 38.1% vs TD 16.3% (p = 0.017, 0.029). In CP both flags co-occur as independence "
  "predicts (18 observed vs 17.0 expected; κ = 0.06); a GEE with child as cluster shows no association with the ankle "
  "flag (OR 1.28, p = 0.62). “EMG-only not elevated” is replaced accordingly.", "Sec. IV-B."),
 ("Equalize the two modalities (same score type, equal numbers of tests or correction, amplitude-sensitive EMG).",
  "Added shape-vs-shape and amplitude-vs-amplitude (raw envelope) scores, a version with two EMG tests, and limits "
  "giving an equal 9.3% TD flag rate per modality. CP ankle-only stays +47.0 to +59.7 points above TD under the strict "
  "rule (all p = 0.0002).", "Sec. III-D, IV-B, IV-C, Fig. 3."),
 ("Address offset properly; do not call mean-centring “sensor offset removal”.",
  "Renamed “mean posture vs shape”; the release contains no static calibration trial, which is stated. The Discussion "
  "notes that equinus posture is clinically real. One child with −86° plantarflexion in every session (likely a "
  "calibration offset) does not change the results.", "Sec. III-B, IV-C, V."),
 ("Complete the robust-definition results for all three analyses and state which definition each abstract number "
  "refers to.",
  "All four classes with CIs are given for the standard and strict rules, and differences with exact permutation "
  "p-values for the main, age-matched, pre-treatment and shape-only analyses; full tables, including the submitted "
  "U_s+δ_s rule, are in the public repository. The abstract names each definition. Shape-only CP ankle-only under the "
  "submitted rule is now 33.9%.", "Abstract, Sec. IV-B–C, Table III, Fig. 3."),
 ("Cover phase segmentation and gait details (toe-off range, fixed 60% boundary, cycles per trial, trial duration, "
  "walking speed).",
  "TD toe-off is at 51% in these labels (98% of cycles within 43–60%). The 35% and 81% extremes come from trials with "
  "one and two usable cycles; fixed-60%, per-cycle registration and exclusion analyses leave CP ankle-only at "
  "48.4–59.7% (strict rule). Cycles per trial are reported (median 9–11); duration and speed are not in the release "
  "and are stated as a limitation.", "Sec. III-B, IV-C, V."),
 ("Add a cohort table and flow diagram; explain the differing ITW/TD counts.",
  "Added Table I (age, sex, CP subtype, treatment, visits per child) and a flow from 59 to 52 children and from 358 "
  "records to 147/146 visit-limbs with every reason. GMFCS is not recorded. Counts differ because 22 visit-limbs have "
  "one trial and repeatability also uses the unaffected CP limb.", "Sec. III-A, Table I."),
 ("Separate pre- and post-treatment states.",
  "On pre-treatment visits only, CP ankle-only is 46.4% vs 0% in TD (p = 0.0002), and premature GM activity persists "
  "(CP p = 0.002).", "Sec. IV-C, IV-E."),
 ("Strengthen or reframe the longitudinal pilot.",
  "Reframed as a case series restricted to baseline EMG-abnormal limbs with the same measurement-error logic. "
  "Untreated CP limbs give a between-session estimate (ankle error 2.6–3.2×, EMG 1.2–1.4× the within-session value); "
  "no TD child was re-tested. No EMG improvement exceeds it, and the positive controls show that the change rule "
  "detects only large changes.", "Sec. III-G, IV-F."),
 ("Show the data (group waveforms, score distributions, counts next to percentages, excluded limbs and children).",
  "Fig. 2 now overlays the CP and ITW means on the TD band; percentages carry counts (e.g. CP TA stance 15/24). Score "
  "distributions, the pilot table and the list of exclusions are in the public repository.", "Fig. 2, Sec. IV-B, VI."),
 ("Tone down the claims.",
  "The ITW swing-GM and treatment-sensitivity statements are phrased as hypotheses; the paper states that discordance "
  "is not supported beyond two independent flags and limits findings to area-normalised, two-trial wearable data.",
  "Abstract, Sec. V–VI."),
 ("Cite waveform-repeatability and hierarchical-model literature; give exact permutation p-values; correct for "
  "multiplicity.",
  "The coefficient of multiple correlation (Kadaba et al.) and GEE (Liang and Zeger) are cited; “p = 1.00” is replaced "
  "by exact permutation p-values (smallest 1/5001); Holm correction is applied across analyses.", "Sec. II, III-F."),
 ("Presentation: Fig. 3 legend, terminology, early definition of “visit-limb”, Fig. 2 rounding.",
  "The class bar chart is replaced by Table III, whose caption notes rounding; the forest plot (Fig. 3) is redrawn "
  "with a legend clear of the data; “shape-only ankle” is used throughout; “visit-limb” is defined at first use.",
  "Sec. III-A, Table III, Fig. 3."),
]),
3: ("Seven points below, each marked in amber text where addressed.", [
 ("Clarify the statistical rationale for combining the TD normal limit and the repeatability threshold, and its "
  "implications for sensitivity and specificity.",
  "The TD limit sets specificity (the leave-one-out TD false-positive rate, reported per rule); the added margin is "
  "only the visit’s measurement error. Positive controls quantify sensitivity: the revised rule keeps TD false "
  "positives at 2.3% and detects large EMG changes in 35–47% of limbs.", "Sec. III-D, IV-D."),
 ("Provide stronger justification for using only two trials; additional trials or external repeatability data would "
  "help.",
  "An odd/even-cycle split-half estimate and a between-session estimate from untreated limbs were added; the two-trial "
  "estimate is the conservative within-session one. Values are compared with published pediatric repeatability "
  "studies.", "Sec. IV-A, V."),
 ("Explain how missing records and differences in visit-limb sample sizes affect the analysis.",
  "The flow (59 → 52 children; 358 → 327 records) lists every exclusion: four children without processed files, 19 "
  "records without ankle data, 12 with misaligned kinematic cycles and one dead EMG channel. All are technical, and "
  "the excluded children’s ages lie within the analysed range.", "Sec. III-A, Table I."),
 ("Expand the longitudinal analysis while acknowledging the limited number of valid treatment-cycle pairs.",
  "Expanded to a limb-by-limb case series with classes under both rules, change scores against within- and "
  "between-session thresholds, and shape-only and registered ankle scores; the paper summarises it, the full table is "
  "in the public repository, and the paper states that only seven children have a valid pair.", "Sec. III-G, IV-F."),
 ("Discuss sensor placement and between-session variability, particularly for treatment monitoring.",
  "Untreated CP limbs show between-session ankle error 2.6–3.2× the within-session value (MDC95 8.3° stance, 10.4° "
  "swing), EMG only 1.2–1.4×. The Discussion explains why mean ankle posture is unreliable for monitoring with "
  "re-applied inertial sensors.", "Sec. IV-F, V."),
 ("Consider onset/offset-based EMG timing measures to complement whole-phase RMSE.",
  "Added on/off detection per cycle. GM is active before initial contact in CP and ITW (+18.6 and +16.6 points vs TD; "
  "Holm p = 0.013 and 0.007), also on pre-treatment and age-matched visits; TA activity shifts from swing to stance in "
  "CP.", "Sec. III-E, IV-E."),
 ("Improve figure readability, technical presentation and consistency in terminology and formatting.",
  "Figures are redrawn at print size with legends and line styles as a second cue; terminology is unified "
  "(“shape-only ankle”, “visit-limb”, standard and strict rules); IEEE template formatting is applied.", "Figs. 1–3."),
]),
4: ("Five points below, each marked in magenta text where addressed.", [
 ("Correct the multiplicity imbalance between modalities: calibrate an equal TD any-flag rate or report per-modality "
  "TD false-positive rates.",
  "Both are reported: TD false-positive rates are 11.6% (ankle) and 16.3% (EMG). An equal 9.3% calibration leaves CP "
  "ankle-only at 56.5% vs 9.3%; EMG flags become CP 24.2% and ITW 28.6% (p = 0.038, 0.031).", "Sec. III-D, IV-B, Table III."),
 ("Derive δ_s from the SEM/MDC framework, scale it by about 1/√2 for two-trial means, and report group-specific δ_s.",
  "MDC95 = 1.96·√2·SEM is reported and matches δ_s; the visit margin is 1.645·SEM/√n. EMG SEM is 0.12–0.14 in TD, "
  "0.15–0.24 in CP and 0.19–0.23 in ITW; a TD-only calibration gives the same conclusions.", "Sec. III-C, IV-A, IV-C, Table II."),
 ("Check for a phase-alignment confound (register stance and swing to the TD phase boundaries) and verify the 81% "
  "toe-off detections.",
  "Per-cycle registration to the TD toe-off (51%) lowers CP ankle-only from 56.5% to 48.4% (TD 4.7%, p = 0.0002); EMG "
  "differences persist. The 81% detection comes from a trial with two usable cycles; excluding extreme trials changes "
  "nothing material.", "Sec. III-F, IV-C."),
 ("Discuss or adjust for walking speed.",
  "Speed is not provided (the release contains time-normalised cycles only); the limitation and its possible effect "
  "on EMG envelopes and ankle kinematics are discussed.", "Sec. V."),
 ("Report why 4 of the 59 children and 19 limb records were excluded, and comment on possible selection bias.",
  "Three CP children have no processed files (participant file: video or IMU unavailable; pre-treatment visit only) "
  "and one ITW child has no note; their ages are 7.0–13.4 y. The 19 records come from one-leg kinematic files (6 "
  "visit-limbs lost, 10 left with one trial). Exclusions are technical; selection bias is discussed.",
  "Sec. III-A, V."),
]),
}

for r in (1, 2, 3, 4):
    col, fill, _ = REV[r]
    P('<w:p><w:pPr><w:pStyle w:val="Normal"/><w:rPr/></w:pPr></w:p>' if r > 1 else "")
    P(para(run(f"Reviewer #{r}:", b=True, color=K) + run("  " + R[r][0], i=True, color=K), black=True))
    for c, resp, tag in R[r][1]:
        P(para(run("Comment: ", b=True, color=K) + rich(c, i=True, color=K), num=NUMID[r],
               style="ListParagraph", black=True))
        P(para(run("Response: ", b=True, color=K) + rich(resp, color=K)
               + run("  " + tag, b=True, color=K, sz='<w:sz w:val="21"/><w:szCs w:val="21"/>', shd=fill),
               before=50, after=130, ind=576, black=True))

# ------------------------------------------------------------------ compliance
P('<w:p><w:pPr><w:pStyle w:val="Normal"/><w:rPr/></w:pPr></w:p>')
P(para(run("Compliance with Camera-Ready Requirements", b=True, color=K), before=0, black=True))
P(para(run("The camera-ready manuscript follows the mandatory requirements of the acceptance notice:", color=K),
       black=True))
items = [
    "IEEE conference template with unchanged margins; submitted as 984_Camera_Ready_Paper.docx and .pdf.",
    "7 pages; Confluence header and IEEE copyright footer on the first page only.",
    "Abstract of 145 words (120–150) without citations; no citations in the Conclusion.",
    "No “our”, “we” or “us”; no salutations in the author details; affiliations and email addresses of all authors.",
    "18 references in IEEE style, cited in ascending order, each in-text citation matched to the list.",
    "Original, high-quality figures; all tables as text.",
    "Spellchecked and proofread; similarity and AI-content checked with Turnitin.",
]
for it in items:
    P(para(rich(it, color=K), num=NUMID["comp"], style="ListParagraph", black=True, before=40, after=40, jc="start"))

P(para(run("We appreciate the constructive and detailed feedback provided by all four reviewers. We have addressed "
            "the concerns raised, and we believe the revisions substantially strengthen the manuscript. We hope that "
            "the revised version meets the expectations of the Technical Program Committee.", b=True, color=K),
       before=180, after=100, line=288, black=True))

# ------------------------------------------------------------------ write
x = open(SRC).read()
head, rest = x[:x.index("<w:body>") + len("<w:body>")], x[x.index("<w:sectPr>"):]
open(SRC, "w").write(head + "".join(body) + rest)

n = open(NUM).read()
new = "".join(f'<w:num w:numId="{i}"><w:abstractNumId w:val="3"/><w:lvlOverride w:ilvl="0">'
              f'<w:startOverride w:val="1"/></w:lvlOverride></w:num>' for i in NUMID.values())
n = n.replace("</w:numbering>", new + "</w:numbering>")
open(NUM, "w").write(n)
print("paragraphs:", len(body))
