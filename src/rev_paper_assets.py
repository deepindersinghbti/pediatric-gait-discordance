"""Paper assets for the camera-ready revision, generated from the analysis of record.

Writes to <out>/ (default paper/):
  tables/tab_cohort.tex     Table I   cohort per group
  tables/tab_repeat.tex     Table II  repeatability, MDC95, TD limits, strict margins
  tables/tab_classes.tex    Table III classes under both rules (+ flags)
  tables/tab_controls.tex   Table IV  positive controls
  figs/fig_pipeline.pdf     Fig. 1    analysis pipeline (redrawn for the revised method)
  figs/fig_waveforms.pdf    Fig. 2    group waveforms over the TD band (copied from rev_figures.py)
  figs/fig_forest.pdf       Fig. 3    group differences across analyses, both rules

Usage:  python src/rev_paper_assets.py results/rev/clean/ paper/
"""
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

TXT, TXT2 = "#191919", "#666666"
COL = {"CP": "#257de0", "ITW": "#f47230", "TD": "#8a8a8a"}
plt.rcParams.update({"font.size": 7.5, "font.family": "DejaVu Sans", "axes.edgecolor": TXT2,
                     "axes.labelcolor": TXT, "xtick.color": TXT2, "ytick.color": TXT2,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
                     "legend.frameon": False, "pdf.fonttype": 42})
NAMES = {"ankle_stance": "Ankle stance (deg)", "ankle_swing": "Ankle swing (deg)",
         "TA_stance": "TA stance", "TA_swing": "TA swing", "GM_stance": "GM stance", "GM_swing": "GM swing"}


def f1(x):
    return f"{x:.1f}"


def ci(r, k="pct", d=1):
    return f"{r[k]:.{d}f} [{r['lo']:.{d}f}, {r['hi']:.{d}f}]"


def main(rev, out):
    rev, out = Path(rev), Path(out)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figs").mkdir(parents=True, exist_ok=True)

    # ---------------- Table I: cohort
    c = pd.read_csv(rev / "cohort_table.csv", index_col=0)
    flow = pd.read_csv(rev / "flow.csv").set_index("stage")
    age_raw = c.loc["Age at first analysed visit, y, mean (SD) [range]"]
    age = age_raw.str.extract(r"^([\d.]+ \([\d.]+\))")[0]
    for g in age.index:   # mark groups where an age is missing (TD S18 has no participant record)
        n_age = age_raw[g].split("n=")[-1].rstrip("]) ") if "n=" in age_raw[g] else None
        if n_age and n_age.isdigit() and int(n_age) < int(c.loc["Children", g]):
            age[g] += "$^a$"
    sex = c.loc["Sex, male/female"].str.replace(r" \(\+1 unknown\)", "$^a$", regex=True)
    rows = [("Children analysed", c.loc["Children"]),
            ("Age, y, mean (SD)", age),
            ("Male/female", sex),
            ("Visits per child, median [range]", c.loc["Analysed visits per child, median [range]"].str.replace("-", "--")),
            ("Visit-limbs: classified / repeatability", c.loc["Visit-limbs: concordance / repeatability"].str.replace("/", "/"))]
    lines = [r"\begin{tabular}{lccc}", r"\toprule", r" & CP & ITW & TD \\", r"\midrule"]
    for name, s in rows:
        lines.append(f"{name} & {s['CP']} & {s['ITW']} & {s['TD']} \\\\")
    lines += [r"\midrule",
              r"\multicolumn{4}{l}{CP subtype: hemiparesis 9, diparesis 9, monoparesis 1;} \\",
              r"\multicolumn{4}{l}{GMFCS not recorded. Botulinum toxin: CP 16, ITW 10;} \\",
              r"\multicolumn{4}{l}{nerve ablation: CP 5; casting: ITW 2; Achilles tenotomy: ITW 1} \\",
              r"\bottomrule", r"\end{tabular}"]
    (out / "tables/tab_cohort.tex").write_text("\n".join(lines) + "\n")

    # ---------------- Table II: repeatability and limits
    r = pd.read_csv(rev / "repeatability.csv")
    r = r[(r.analysis == "between_trials") & (r.group == "All")].set_index("score")
    t = pd.read_csv(rev / "thresholds_rev.csv")
    t = t[t.scores == "main_scores"].set_index("score")
    lines = [r"\begin{tabular}{lcccccc}", r"\toprule",
             r"Score & SEM [95\% CI] & ICC [95\% CI] & MDC$_{95}$ & $\delta_s$ & $U_s$ & $m_s$ ($n$=2) \\", r"\midrule"]
    for s, name in NAMES.items():
        x, y = r.loc[s], t.loc[s]
        lines.append(f"{name} & {x.SEM:.2f} [{x.SEM_lo:.2f}, {x.SEM_hi:.2f}] & {x.ICC:.2f} [{x.ICC_lo:.2f}, {x.ICC_hi:.2f}] & "
                     f"{x.MDC95:.2f} & {y.delta:.2f} & {y.U95:.2f} & {y.margin_2trials:.2f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / "tables/tab_repeat.tex").write_text("\n".join(lines) + "\n")

    # ---------------- Table III: classes under both rules (+ flags)
    cr = pd.read_csv(rev / "class_rates.csv")
    cr = cr[cr.analysis == "main"]
    tm = pd.read_csv(rev / "timing_visits.csv")
    nmap = cr.drop_duplicates("group").set_index("group")
    head = " & ".join(f"{g} ($n$={nmap.N[g]}/{nmap.children[g]})" for g in ("CP", "ITW", "TD"))
    lines = [r"\begin{tabular}{llccc}", r"\toprule", f"Rule & Class & {head} \\\\", r"\midrule"]
    lab = [("both_normal", "Both normal"), ("ankle_only", "Ankle-only"), ("EMG_only", "EMG-only"),
           ("both_abnormal", "Both abn."), ("ankle_flag", "Ankle flag"), ("EMG_flag", "EMG flag")]
    for rule, rname, tcol in (("standard", "Std.", "timing_flag"), ("strict_new", "Strict", "timing_flag_strict")):
        x = cr[cr.rule == rule].set_index(["outcome", "group"])
        for i, (o, nm) in enumerate(lab):
            first = rf"\multirow{{7}}{{*}}{{{rname}}}" if i == 0 else ""
            cells = []
            for g in ("CP", "ITW", "TD"):
                v = x.loc[(o, g)]
                cell = ci(v)
                if o == "ankle_only" and g == "CP":
                    cell = rf"\textbf{{{v.pct:.1f}}} [{v.lo:.1f}, {v.hi:.1f}]"
                cells.append(cell)
            if i == 4:
                lines.append(r"\cmidrule(l){2-5}")
            lines.append(f"{first} & {nm} & " + " & ".join(cells) + r" \\")
        tf = [f"{100 * tm.loc[tm.group == g, tcol].mean():.1f}" for g in ("CP", "ITW", "TD")]
        lines.append(f" & Timing flag & " + " & ".join(tf) + r" \\")
        lines.append(r"\midrule" if rule == "standard" else r"\bottomrule")
    lines.append(r"\end{tabular}")
    (out / "tables/tab_classes.tex").write_text("\n".join(lines) + "\n")

    # ---------------- Table IV: positive controls
    p = pd.read_csv(rev / "positive_controls.csv").set_index("manipulation")

    def rng(names, col):
        v = [p.loc[n, col] for n in names]
        lo, hi = min(v), max(v)
        return f"{lo:.0f}" if round(lo) == round(hi) else f"{lo:.0f}--{hi:.0f}"
    spec = [("No change (false-alarm rate)", ["none"], "EMG"),
            ("Timing shift 10\\% (TA+GM)", ["both earlier 10%", "both later 10%"], "EMG"),
            ("Timing shift 15\\% (TA+GM)", ["both earlier 15%", "both later 15%"], "EMG"),
            ("GM swing activity $\\times$3", ["GM swing x3.0"], "EMG"),
            ("TA stance activity $\\times$3", ["TA stance x3.0"], "EMG"),
            ("Whole-cycle amplitude $\\times$2", ["whole-cycle EMG x2"], "EMG"),
            ("Average CP EMG deviation", ["avg CP EMG pattern x1.0"], "EMG"),
            ("Average ITW EMG deviation", ["avg ITW EMG pattern x1.0"], "EMG"),
            ("Average CP ankle deviation$^b$", ["avg CP ankle pattern x1"], "ankle")]
    lines = [r"\begin{tabular}{lccccc}", r"\toprule",
             r" & \multicolumn{3}{c}{Visit flagged} & \multicolumn{2}{c}{Change detected$^a$} \\",
             r"\cmidrule(lr){2-4}\cmidrule(lr){5-6}",
             r"Change added to TD data & $U_s$ & Strict & $U_s{+}\delta_s$ & $\delta_s$ & MDC$_{95}$ \\", r"\midrule"]
    for name, ms, mod in spec:
        f = "EMG_flag" if mod == "EMG" else "ankle_flag"
        ch = [rng(ms, "EMG_change_delta_s"), rng(ms, "EMG_change_MDC")] if mod == "EMG" else ["--", "--"]
        lines.append(f"{name} & {rng(ms, f + '_standard')} & {rng(ms, f + '_strict_new')} & "
                     f"{rng(ms, f + '_strict_old')} & {ch[0]} & {ch[1]} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (out / "tables/tab_controls.tex").write_text("\n".join(lines) + "\n")

    # ---------------- Fig. 3: forest plot across analyses, both rules
    g1 = pd.read_csv(rev / "group_differences.csv")
    g2 = pd.read_csv(rev / "variants_group_differences.csv")
    g = pd.concat([g1, g2])
    lab_a = {"main": "Main", "age_matched": "Age-matched", "T0_only": "Pre-treatment (T0)",
             "shape_ankle": "Shape-only ankle", "registered": "Toe-off registered", "excl_P15": "Without child P15",
             "amplitude_EMG": "Amplitude EMG", "EMG_two_scores": "Two EMG tests", "strict_TD_SEM": "TD-only SEM"}
    blocks = [("CP ankle-only", "CP", "ankle_only",
               ["main", "age_matched", "T0_only", "shape_ankle", "registered", "excl_P15"]),
              ("CP EMG flag", "CP", "EMG_flag", ["main", "age_matched", "T0_only", "registered", "amplitude_EMG", "EMG_two_scores"]),
              ("ITW EMG flag", "ITW", "EMG_flag", ["main", "age_matched", "T0_only", "registered", "amplitude_EMG", "EMG_two_scores"])]
    fig, ax = plt.subplots(figsize=(3.45, 4.1))
    y, ticks, labels, heads = 0, [], [], []
    for title, grp, outc, ans in blocks:
        heads.append((y, title, grp))
        y -= 1
        for a in ans:
            for k, (rule, mk, off) in enumerate((("standard", "s", 0.17), ("strict_new", "o", -0.17))):
                x = g[(g.analysis == a) & (g.rule == rule) & (g.group == grp) & (g.outcome == outc)].iloc[0]
                ax.plot([x.lo, x.hi], [y + off] * 2, color=COL[grp], lw=1.0)
                ax.plot(x["diff"], y + off, mk, ms=4.2, color=COL[grp],
                        mfc="white" if rule == "standard" else COL[grp], mew=1.0)
            ticks.append(y); labels.append(lab_a[a])
            y -= 1
        y -= 0.4
    for yy, title, grp in heads:
        ax.text(-0.02, yy, title, transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=7.5, fontweight="bold", color=TXT)
    ax.axvline(0, color=TXT2, ls="--", lw=0.7)
    ax.set_yticks(ticks, labels)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(y + 0.6, 0.6)
    ax.set_xlabel("Difference from TD (percentage points)")
    ax.grid(axis="x", color="#e6e6e6", lw=0.5)
    ax.set_axisbelow(True)
    h1 = plt.Line2D([], [], marker="s", ls="-", color=TXT2, mfc="white", ms=4.2, lw=1, label="Standard rule ($U_s$)")
    h2 = plt.Line2D([], [], marker="o", ls="-", color=TXT2, ms=4.2, lw=1, label="Strict rule ($U_s$+$m_s$)")
    fig.legend(handles=[h1, h2], loc="upper center", ncol=2, bbox_to_anchor=(0.55, 1.0), fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    for ext in ("pdf", "png"):
        fig.savefig(out / f"figs/fig_forest.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ---------------- Fig. 1: pipeline
    fig, ax = plt.subplots(figsize=(7.16, 2.35))
    ax.set_xlim(0, 100); ax.set_ylim(0, 34); ax.axis("off")

    def box(x, y, w, h, title, body, fc="#f4f6f8", ec="#9aa5b1"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.8", fc=fc, ec=ec, lw=0.8))
        ax.text(x + w / 2, y + h - 1.6, title, ha="center", va="top", fontsize=7, fontweight="bold", color=TXT)
        ax.text(x + w / 2, y + h - 5.2, body, ha="center", va="top", fontsize=6, color=TXT, linespacing=1.3)

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", lw=0.8, color=TXT2,
                                                                     shrinkA=0, shrinkB=0))
    top, h, w, gap = 18.5, 15, 17.2, 3.1
    xs = [0.4 + i * (w + gap) for i in range(5)]
    tops = [("Data", "LIVE-GaitNeuroKids\n52 children\n(19 CP, 11 ITW, 22 TD)\n327 trial-limb records"),
            ("Quality screen", "dead EMG channel\nankle cycles not\naligned to a gait\nevent (CMC < 0.6)"),
            ("Scores", "leave-one-out\nTD reference\n6 phase RMSE scores\nEMG on/off timing"),
            ("Repeatability", "two trials per visit\nSEM, ICC, MDC$_{95}$\nodd/even split-half\nwaveform CMC"),
            ("Limits", "$U_s$: TD 95th pct.\nmargin\n$m_s = 1.645\\,$SEM$/\\sqrt{n}$")]
    for x, (t_, b_) in zip(xs, tops):
        box(x, top, w, h, t_, b_)
    for i in range(4):
        arrow(xs[i] + w + 0.35, top + h / 2, xs[i + 1] - 0.35, top + h / 2)
    bot, hb = 0.4, 14
    wb = [36, 28, 27.6]
    xb = [0.4, 0.4 + wb[0] + 3.3, 0.4 + wb[0] + wb[1] + 6.6]
    bots = [("Concordance class per visit-limb",
             "ankle flag (2 scores) $\\times$ EMG flag (4 scores)\nnormal, ankle-only, EMG-only, both abnormal\n"
             "standard: score $> U_s$;   strict: score $> U_s + m_s$"),
            ("Inference", "child bootstrap, limits re-estimated\nchild-level permutation, Holm\nGEE for the joint flags"),
            ("Checks and pilot", "positive controls\nsensitivity analyses\npre/post pairs vs\nbetween-session error")]
    for i, (x, ww, (t_, b_)) in enumerate(zip(xb, wb, bots)):
        box(x, bot, ww, hb, t_, b_, **({"fc": "#eef4fc", "ec": "#7aa9de"} if i == 0 else {}))
    mid = (top + bot + hb) / 2
    xl = xs[4] + w / 2
    ax.plot([xl, xl, xb[0] + wb[0] / 2], [top - 0.3, mid, mid], color=TXT2, lw=0.8)
    arrow(xb[0] + wb[0] / 2, mid, xb[0] + wb[0] / 2, bot + hb + 0.35)
    for i in range(2):
        arrow(xb[i] + wb[i] + 0.35, bot + hb / 2, xb[i + 1] - 0.35, bot + hb / 2)
    fig.savefig(out / "figs/fig_pipeline.pdf", bbox_inches="tight")
    fig.savefig(out / "figs/fig_pipeline.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    for ext in ("pdf", "png"):
        shutil.copy(rev / f"figs/fig_waveforms.{ext}", out / f"figs/fig_waveforms.{ext}")
    print("written:", sorted(str(q.relative_to(out)) for q in out.rglob("*") if q.is_file()))


if __name__ == "__main__":
    main(*sys.argv[1:3])
