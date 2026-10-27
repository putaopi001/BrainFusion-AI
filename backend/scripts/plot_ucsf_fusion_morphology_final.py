"""Render reproducible, aggregate-only figures for the final UCSF analysis."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# Keep editable vector text and the selected Python plotting backend.
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
# svg.fonttype='none'; pdf.fonttype=42
plt.rcParams.update({"svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 7, "axes.labelsize": 7,
                     "axes.titlesize": 8, "axes.linewidth": 0.7,
                     "xtick.labelsize": 6, "ytick.labelsize": 6,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False, "figure.facecolor": "white"})

from audit_panel_alignment import require_matplotlib_panel_alignment

COLORS = {"clinical": "#30343B", "morph": "#8A6BBE", "radiomics": "#4F9B9B", "fusion": "#3775BA"}


def set_external_ylabels(ax, positions, labels) -> None:
    ax.set_yticks(positions)
    ax.tick_params(axis="y", labelleft=False, length=0)
    for position, label in zip(positions, labels):
        ax.text(-0.035, position, label, transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=6, clip_on=False)


def save_multi(fig, path: Path) -> None:
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig, json_out=str(path.with_suffix(".alignment.json")),
                                       overlay_svg=str(path.with_suffix(".alignment.svg")),
                                       tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True)
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def figure_model_comparison(existing: dict, morphology: dict, out: Path) -> None:
    current = {row["name"]: row for row in existing["models"]}
    all_models = [
        ("Clinical age + sex", "clinical_age_sex_ridge", COLORS["clinical"]),
        ("Reference morphology", "reference_morphology_ridge", COLORS["morph"]),
        ("Clinical + morphology", "clinical_plus_reference_morphology_ridge", COLORS["morph"]),
        ("Radiomics Ridge", "radiomics_ridge", COLORS["radiomics"]),
        ("Radiomics Elastic-Net", "radiomics_elastic_net", COLORS["radiomics"]),
        ("Clinical + radiomics Ridge", "clinical_radiomics_ridge", COLORS["fusion"]),
        ("Clinical + radiomics Elastic-Net", "clinical_radiomics_elastic_net", COLORS["fusion"]),
    ]
    morph_models = {row["name"]: row for row in morphology["models"]}
    cis = existing["oof_c_index_patient_bootstrap_95ci"]
    cis.update(morphology["patient_bootstrap_oof_c_index_95ci"])
    deltas = dict(existing["paired_oof_c_index_deltas_vs_matched_clinical"])
    deltas.update(morphology["paired_oof_c_index_deltas_vs_same_cohort_clinical"])
    delta_name = {
        "reference_morphology_ridge": "reference_morphology_ridge",
        "clinical_plus_reference_morphology_ridge": "clinical_plus_reference_morphology_ridge",
    }
    delta_pairs = []
    for label, key, color in all_models:
        if key == "clinical_age_sex_ridge":
            continue
        lookup = delta_name.get(key, key)
        delta_pairs.append((label, deltas[lookup], color))
    delta_display = {
        "Reference morphology": "Morphology",
        "Clinical + morphology": "Clinical + morph.",
        "Radiomics Ridge": "Rad. Ridge",
        "Radiomics Elastic-Net": "Rad. Elastic-Net",
        "Clinical + radiomics Ridge": "Clin. + rad. Ridge",
        "Clinical + radiomics Elastic-Net": "Clin. + rad. Elastic-Net",
    }

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.35), gridspec_kw={"width_ratios": [1, 1]})
    ax = axes[0]
    y = np.arange(len(all_models))[::-1]
    for pos, (label, key, color) in zip(y, all_models):
        row = current.get(key) or morph_models.get(key)
        if row is None:
            raise ValueError(f"Missing aggregate model row: {key}")
        lo, hi = cis[key]
        ax.errorbar(row["pooled_oof_c_index"], pos,
                    xerr=[[row["pooled_oof_c_index"] - lo], [hi - row["pooled_oof_c_index"]]],
                    fmt="o", markersize=3.4, capsize=2.3, color=color, ecolor=color, linewidth=1.0)
    set_external_ylabels(ax, y, [x[0] for x in all_models])
    ax.set_xlim(0.46, 0.71)
    ax.set_xlabel("Pooled out-of-fold Harrell C-index")
    ax.set_title("Patient-bootstrap 95% CI", loc="left", pad=7)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.text(-0.12, 1.04, "a", transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")

    ax = axes[1]
    y2 = np.arange(len(delta_pairs))[::-1]
    ax.axvline(0, color="#30343B", linewidth=0.8, linestyle="--", zorder=0)
    for pos, (label, result, color) in zip(y2, delta_pairs):
        estimate = result["mean_delta_c_index"]
        lo, hi = result["percentile_95_ci"]
        ax.errorbar(estimate, pos, xerr=[[estimate-lo], [hi-estimate]], fmt="o", markersize=3.4,
                    capsize=2.3, color=color, ecolor=color, linewidth=1.0)
    set_external_ylabels(ax, y2, [delta_display[x[0]] for x in delta_pairs])
    ax.set_xlim(-0.18, 0.04)
    ax.set_xlabel("Paired OOF Δ C-index vs clinical baseline")
    ax.set_title("Paired patient-bootstrap 95% CI", loc="left", pad=7)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.5)
    ax.set_axisbelow(True)
    ax.text(-0.12, 1.04, "b", transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")
    fig.suptitle("Imaging-derived features did not improve discrimination in this cohort", fontsize=9, y=0.995)
    fig.subplots_adjust(left=0.31, right=0.985, bottom=0.14, top=0.88, wspace=0.46)
    save_multi(fig, out / "figure1_model_comparison")


def figure_mask_stability(morphology: dict, out: Path) -> None:
    sensitivity = morphology["existing_ten_case_mask_feature_stability"]
    groups = sensitivity["reference_vs_prediction_feature_error"]
    low = sensitivity["low_recall_summary"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.75), gridspec_kw={"width_ratios": [1, 1]})
    ax = axes[0]
    labels = ["Edema-related features\n(label 2; 5 features)", "Enhancing-related features\n(label 3; 15 features)"]
    values = [groups["2"], groups["3"]]
    medians = [v["case_median_absolute_relative_difference_median"] for v in values]
    q1 = [v["case_median_absolute_relative_difference_q1_q3"][0] for v in values]
    q3 = [v["case_median_absolute_relative_difference_q1_q3"][1] for v in values]
    y = np.array([1, 0])
    ax.errorbar(medians, y, xerr=[np.asarray(medians)-q1, np.asarray(q3)-medians], fmt="o",
                markersize=4, capsize=3, color=COLORS["morph"], ecolor=COLORS["morph"], linewidth=1.2)
    ax.set_yticks(y, labels)
    ax.set_xlim(0, max(q3) * 1.3)
    ax.set_xlabel("Per-case median absolute relative feature difference")
    ax.set_title("Median and IQR across 10 paired cases", loc="left", pad=7)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.5); ax.set_axisbelow(True)
    ax.text(-0.12, 1.04, "a", transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")

    ax = axes[1]
    regions = ["WT", "TC", "ET"]
    means = [low[r]["bottom_quartile_mean_recall"] for r in regions]
    mins = [low[r]["minimum_recall"] for r in regions]
    pos = np.arange(len(regions))
    bars = ax.bar(pos, means, width=0.58, color=["#8795A1", "#6F8797", "#526B7A"], edgecolor="none")
    for bar, minimum, region in zip(bars, mins, regions):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.075,
                f"min {minimum:.2f}", ha="center", va="bottom", fontsize=6)
    ax.set_xticks(pos, regions)
    ax.set_ylim(0, 0.82)
    ax.set_ylabel("Recall")
    ax.set_title("Bottom-recall quartile (n=3 of 10)", loc="left", pad=7)
    ax.text(-0.12, 1.04, "b", transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")
    ax.set_yticks(np.arange(0, 0.81, 0.2))
    ax.grid(False)
    fig.suptitle("Automatic-mask disagreement can shift selected radiomics features", fontsize=9, y=1.02)
    fig.subplots_adjust(left=0.26, right=0.985, bottom=0.22, top=0.78, wspace=0.55)
    save_multi(fig, out / "figure2_mask_feature_stability")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--existing-comparison", type=Path, required=True)
    ap.add_argument("--morphology-results", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--replace-outputs", action="store_true", help="Replace figures just generated for this same versioned run")
    args = ap.parse_args()
    if args.out_dir.exists() and any(args.out_dir.iterdir()) and not args.replace_outputs:
        raise FileExistsError("Refusing to overwrite existing figure exports")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    existing = json.loads(args.existing_comparison.read_text(encoding="utf-8"))
    morphology = json.loads(args.morphology_results.read_text(encoding="utf-8"))
    figure_model_comparison(existing, morphology, args.out_dir)
    figure_mask_stability(morphology, args.out_dir)
    print(json.dumps({"figures": ["figure1_model_comparison", "figure2_mask_feature_stability"],
                      "backend": f"matplotlib {mpl.__version__}", "out_dir": str(args.out_dir)}, indent=2))


if __name__ == "__main__":
    main()
