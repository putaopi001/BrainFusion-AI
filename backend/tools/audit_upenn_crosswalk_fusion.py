"""Build a local UPENN scan crosswalk and exploratory, fold-safe Cox comparison.

Patient-level outputs are written only to the caller-specified runtime folder.
The OS mapping is explicitly researcher-defined and never labelled official.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import nibabel as nib
import numpy as np
from sklearn.model_selection import StratifiedKFold

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.research.survival import (  # noqa: E402
    EndpointContract, concordance_index, cox_ph, validate_endpoint,
)

FEATURE_SPEC = [
    ("T1GD", "ET", "T1GD_ET_Intensity_Mean"),
    ("FLAIR", "ED", "FLAIR_ED_Intensity_Mean"),
    ("T2", "ED", "T2_ED_Intensity_Mean"),
    ("T1", "NC", "T1_NC_Intensity_Mean"),
]
MODALITIES = ("T1", "T1GD", "T2", "FLAIR")
REGIONS = ("ED", "ET", "NC")
SEED = 20261026
ORIGIN = ("RESEARCHER_DEFINED: first-surgery origin context; Survival_Censor "
          "assumed elapsed days; Alive/Lost to Follow-up treated as censored")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(value):
    try:
        value = float(str(value).strip())
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def dump_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False),
                    encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clinical", type=Path, required=True)
    parser.add_argument("--availability", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--radiomics-dir", type=Path, required=True)
    parser.add_argument("--local-mask", type=Path, required=True)
    parser.add_argument("--mirror-mask", type=Path, required=True)
    parser.add_argument("--manual-mask-manifest", type=Path, required=True)
    parser.add_argument("--mirror-revision", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    planned = [out / name for name in (
        "fusion-cv-results.json", "run-manifest.json", "upenn-cohort-reconciliation.csv",
        "upenn-cohort-flow.json", "upenn-os-field-evidence.json",
        "upenn-os-field-definition-audit.md", "upenn-crosswalk-evidence.json",
        "upenn-crosswalk-report.md")]
    existing = [str(p) for p in planned if p.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite prior run outputs: " + ", ".join(existing))
    if args.crosswalk.exists():
        raise FileExistsError(f"refusing to overwrite patient-level crosswalk: {args.crosswalk}")

    clinical, availability = load_csv(args.clinical), load_csv(args.availability)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    subjects = manifest["subjects"]
    cby = {r["ID"].strip(): r for r in clinical}
    aby = {r["ID"].strip(): r for r in availability}
    assert len(clinical) == len(cby) == 671
    assert len(availability) == len(aby) == 671
    assert len(subjects) == len({s["subject_id"] for s in subjects}) == 671
    assert {s["subject_id"] for s in subjects} == set(cby) == set(aby)

    table_ids, table_files, selected = {}, {}, {}
    for modality in MODALITIES:
        for region in REGIONS:
            name = f"Radiomic_Features_CaPTk_automaticsegm_{modality}_{region}.csv"
            path = args.radiomics_dir / name
            rows = load_csv(path)
            assert rows and "SubjectID" in rows[0]
            ids = [r["SubjectID"].strip() for r in rows]
            assert len(ids) == len(set(ids)), f"duplicate SubjectID in {name}"
            table_ids[(modality, region)] = set(ids)
            table_files[(modality, region)] = path
    complete_12 = set.intersection(*table_ids.values())
    for modality, region, feature in FEATURE_SPEC:
        rows = load_csv(table_files[(modality, region)])
        assert feature in rows[0], f"missing selected feature {feature}"
        for row in rows:
            value = number(row.get(feature))
            selected.setdefault(row["SubjectID"].strip(), {})[feature] = value

    # Exact scan ID join, preserving timepoint suffix. This local CSV contains
    # pseudonymous patient/scan keys and must never be committed or published.
    crosswalk = []
    for s in subjects:
        sid = s["subject_id"]
        c, a = cby[sid], aby[sid]
        crosswalk.append({
            "scan_id": sid, "patient_id": s["patient_id"], "timepoint": s["timepoint"],
            "clinical_id_exact_match": c["ID"].strip() == sid,
            "availability_id_exact_match": a["ID"].strip() == sid,
            "mirror_gt_source": s.get("gt_source") or "",
            "mirror_manual_mask_path": s.get("manual_segm") or "",
            "mirror_automated_mask_path": s.get("automated_segm") or "",
            "structural_imaging": a.get("Structural imaging", ""),
            "dti_imaging": a.get("DTI imaging", ""), "dsc_imaging": a.get("DSC imaging", ""),
            "automatic_segmentation": a.get("Automatic Tumor Segmentation", ""),
            "corrected_segmentation": a.get("Corrected Tumor Segmentation", ""),
            "official_overall_survival_available": a.get("Overall Survival", ""),
            "official_radiomics_available": a.get("CaPTk Radiomic Features", ""),
            "auto_structural_feature_table_count": sum(sid in v for v in table_ids.values()),
            "auto_structural_all_12_tables": sid in complete_12,
            "clinical_status": c.get("Survival_Status", ""),
            "updated_event_time_present": number(c.get("Survival_from_surgery_days_UPDATED")) is not None,
            "censor_time_present": number(c.get("Survival_Censor")) is not None,
        })
    with args.crosswalk.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(crosswalk[0]))
        writer.writeheader()
        writer.writerows(crosswalk)

    # Verify the original local release mask against the scan-specific pinned
    # manual reference. This is content evidence, not an ordinal join.
    local_img, mirror_img = nib.load(str(args.local_mask)), nib.load(str(args.mirror_mask))
    local, mirror = np.asanyarray(local_img.dataobj), np.asanyarray(mirror_img.dataobj)
    assert local.shape == mirror.shape and np.allclose(local_img.affine, mirror_img.affine, atol=1e-5, rtol=0)
    assert set(np.unique(local).tolist()) == {0, 1, 2, 3}
    assert set(np.unique(mirror).tolist()) == {0, 1, 2, 4}
    recoded = np.zeros_like(local)
    for source, target in {0: 0, 1: 1, 2: 2, 3: 4}.items():
        recoded[local == source] = target
    assert np.array_equal(recoded, mirror), "reference mask content match failed"
    mask_index = json.loads(args.manual_mask_manifest.read_text(encoding="utf-8"))
    mask_files = mask_index["entries"]
    target_entry = next(x for x in mask_files if x["path"] ==
                        "images_segm/UPENN-GBM-00002_11_segm.nii.gz")
    target_lfs = target_entry["lfs"]["oid"]
    lfs_matches = sum(x.get("lfs", {}).get("oid") == target_lfs for x in mask_files)

    # Researcher-defined primary candidate only; 3 uncertain deaths excluded.
    candidates, excluded = [], Counter()
    for c in clinical:
        sid = c["ID"].strip()
        if not sid.endswith("_11"):
            continue
        status = c["Survival_Status"].strip()
        event_time, censor_time = (number(c.get("Survival_from_surgery_days_UPDATED")),
                                   number(c.get("Survival_Censor")))
        if status == "Deceased" and event_time is not None and event_time > 0:
            duration, event = event_time, 1
        elif status in ("Alive", "Lost to Follow-up") and censor_time is not None and censor_time > 0:
            duration, event = censor_time, 0
        else:
            excluded[status] += 1
            continue
        candidates.append({"scan_id": sid, "patient_id": sid[:-3], "duration": duration,
                           "event": event, "status": status})
    assert len(candidates) == 608 and sum(x["event"] for x in candidates) == 585
    assert len({x["patient_id"] for x in candidates}) == 608

    # Four outcome-independent first-order means, pre-specified to constrain
    # dimensionality. Same feature-complete cohort and folds for each model.
    analysis = []
    for row in candidates:
        values = selected.get(row["scan_id"], {})
        names = [s[2] for s in FEATURE_SPEC]
        if any(values.get(n) is None for n in names):
            continue
        c = cby[row["scan_id"]]
        gender = 1.0 if c.get("Gender") == "M" else (0.0 if c.get("Gender") == "F" else np.nan)
        idh = c.get("IDH1", "")
        gtr = c.get("GTR_over90percent", "")
        clinical_x = [number(c.get("Age_at_scan_years")), gender,
                      1.0 if idh == "Mutated" else 0.0,
                      1.0 if idh == "NOS/NEC" else 0.0,
                      1.0 if gtr == "Y" else (0.0 if gtr == "N" else np.nan)]
        analysis.append({**row, "clinical_x": clinical_x,
                         "radiomic_x": [values[n] for n in names]})
    assert len(analysis) >= 400
    y = np.array([r["event"] for r in analysis], dtype=int)
    times = np.array([r["duration"] for r in analysis], dtype=float)
    pids = [r["patient_id"] for r in analysis]
    assert len(set(pids)) == len(pids)
    folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED).split(np.zeros(len(y)), y))
    clinical_names = ["age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC", "GTR_over_90pct"]
    radio_names = [s[2] for s in FEATURE_SPEC]
    models = {
        "clinical_only": (np.array([r["clinical_x"] for r in analysis], float), clinical_names),
        "radiomics_only": (np.array([r["radiomic_x"] for r in analysis], float), radio_names),
        "clinical_plus_radiomics": (np.array([r["clinical_x"] + r["radiomic_x"] for r in analysis], float), clinical_names + radio_names),
    }
    fitted = {}
    contract = EndpointContract("OS", "patient_id", "duration", "event", "time_origin",
                                ORIGIN, "days", "1", "0", True)
    for model_name, (matrix, feature_names) in models.items():
        oof = np.full(len(y), np.nan)
        fold_results = []
        for fold_id, (train_ix, test_ix) in enumerate(folds, 1):
            train, test = matrix[train_ix].copy(), matrix[test_ix].copy()
            keep = []
            for j in range(train.shape[1]):
                valid = train[:, j][np.isfinite(train[:, j])]
                if not len(valid):
                    continue
                median = float(np.median(valid))
                train[~np.isfinite(train[:, j]), j] = median
                test[~np.isfinite(test[:, j]), j] = median
                if float(np.std(train[:, j])) > 1e-12:
                    keep.append(j)
            assert keep
            train, test = train[:, keep], test[:, keep]
            kept_names = [feature_names[j] for j in keep]
            training_rows = [{"patient_id": pids[i], "duration": times[i], "event": str(y[i]),
                              "time_origin": ORIGIN} for i in train_ix]
            validation = validate_endpoint(training_rows, contract)
            assert validation["eligible"], validation["issues"]
            fit = cox_ph(validation, train, kept_names, l2=0.1)
            beta = np.array([fit["coefficients"][name] for name in kept_names])
            scores = test @ beta
            assert np.isfinite(scores).all()
            oof[test_ix] = scores
            fold_results.append({
                "fold": fold_id, "train_n": len(train_ix), "test_n": len(test_ix),
                "test_events": int(y[test_ix].sum()),
                "test_c_index": float(concordance_index(times[test_ix], y[test_ix], scores)),
                "cox_converged": fit["converged"], "optimizer_message": fit["optimizer_message"],
                "dropped_constant_or_all_missing": [feature_names[j] for j in range(len(feature_names)) if j not in keep],
                "ph_diagnostic": "Schoenfeld residual trend screen only; not a formal PH test",
            })
        assert np.isfinite(oof).all()
        fold_scores = [f["test_c_index"] for f in fold_results]
        fitted[model_name] = {
            "n": len(y), "events": int(y.sum()), "candidate_censored": int((y == 0).sum()),
            "feature_count": matrix.shape[1], "l2_penalty": 0.1,
            "five_fold_patient_level_cv": fold_results,
            "out_of_fold_c_index": float(concordance_index(times, y, oof)),
            "fold_c_index_mean": float(np.mean(fold_scores)),
            "fold_c_index_sd": float(np.std(fold_scores, ddof=1)),
        }

    official_452 = [r for r in crosswalk if r["timepoint"] == "11" and
                    r["official_overall_survival_available"] == "available"]
    assert len(official_452) == 452 and all(r["clinical_status"] == "Deceased" and
           r["updated_event_time_present"] and not r["censor_time_present"] for r in official_452)
    people = Counter(r["patient_id"] for r in crosswalk)
    assert len(people) == 630 and sum(n == 2 for n in people.values()) == 41

    cohort_csv = out / "upenn-cohort-reconciliation.csv"
    cohort_rows = [
        {"scenario": "baseline _11 scans", "N": 611, "events": "NA", "censored": "NA", "excluded_uncertain": 0, "definition": "one baseline scan per person"},
        {"scenario": "official Overall Survival=available flag", "N": 452, "events": 452, "censored": 0, "excluded_uncertain": 0, "definition": "all are Deceased with positive UPDATED; availability flag, not a right-censored analytic cohort"},
        {"scenario": "researcher-defined candidate S1", "N": 608, "events": 585, "censored": 23, "excluded_uncertain": 3, "definition": "Deceased + UPDATED event; Alive/Lost + Survival_Censor assumed elapsed days censor"},
        {"scenario": "S1 + four selected radiomics features", "N": len(analysis), "events": int(y.sum()), "censored": int((y == 0).sum()), "excluded_uncertain": 3, "definition": "exact scan ID and complete selected feature panel; same set for all models"},
        {"scenario": "BrainIAC published denominator", "N": 668, "events": "not reconstructible", "censored": "not reconstructible", "excluded_uncertain": "unknown", "definition": "paper count only; row/person inclusion list unavailable"},
    ]
    with cohort_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cohort_rows[0]))
        writer.writeheader(); writer.writerows(cohort_rows)

    flow = {
        "status": "PASS_AGGREGATE_RECONSTRUCTION; EXPLORATORY_MODEL_COHORT",
        "scan_counts": {"all": len(crosswalk), "baseline_11": 611, "followup_21": 60,
                        "paired_people": 41, "followup_only_people": 19,
                        "unique_people": len(people)},
        "researcher_defined_endpoint_counts": {
            "baseline_candidate": len(candidates), "events": int(sum(x["event"] for x in candidates)),
            "candidate_censored": int(sum(x["event"] == 0 for x in candidates)),
            "excluded_by_status_or_invalid_time": dict(sorted(excluded.items())),
            "official_endpoint_validated": False,
        },
        "feature_complete_model_cohort": {
            "n": len(analysis), "events": int(y.sum()), "candidate_censored": int((y == 0).sum()),
            "dropped_for_incomplete_four_feature_panel": len(candidates) - len(analysis),
            "drop_event_count": int(sum(x["event"] for x in candidates) - y.sum()),
            "drop_censor_count": int(sum(x["event"] == 0 for x in candidates) - (y == 0).sum()),
        },
        "non_baseline_records_used_as_patients": 0,
        "followup_records_kept_only_in_scan_crosswalk": 60,
        "limits": ["Outcome mapping is researcher-defined; Survival_Censor units/origin are not documented.",
                   "This flow is not a reconstruction of the historical paper's 452 analytic patients."],
    }
    dump_json(out / "upenn-cohort-flow.json", flow)

    field_evidence = {
        "status": "RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS",
        "official_endpoint_validated": False,
        "fields": {
            "Survival_from_surgery_days_UPDATED": {"evidence_level": "PUBLISHED_STUDY_DEFINED_CONTEXT; EXACT_UPDATED_RULE_RESEARCHER_INFERRED", "verified": False, "finding": "field name states surgery/days; 2022 cohort paper says survival information from first surgical operation, but neither defines the UPDATED transformation"},
            "Survival_Censor": {"evidence_level": "UNKNOWN_OFFICIAL_SEMANTICS; RESEARCHER_INFERRED_FOR_EXPLORATION", "verified": False, "finding": "26 baseline values among Alive/Lost/uncertain categories; unit, origin and last-contact derivation are not documented in the checked official assets/paper"},
            "Survival_Status": {"evidence_level": "OFFICIAL_OBSERVED_VALUES; EVENT_MAPPING_RESEARCHER_DEFINED", "verified": False, "finding": "literal categories are preserved; clear deceased is event and Alive/Lost censor only for exploratory scenario"},
            "time_origin": {"evidence_level": "PUBLISHED_STUDY_DEFINED_CONTEXT", "verified": False, "finding": "paper supports first-surgical-operation context, but does not tie censor field derivation to it"},
            "uncertain_death": {"evidence_level": "UNKNOWN_OFFICIAL_RULE", "verified": False, "finding": "3 explicit uncertain-date deaths; primary candidate excludes them; no authoritative inclusion/censor rule"},
            "452_cohort": {"evidence_level": "PUBLISHED_COUNT_AND_OFFICIAL_AVAILABILITY_FLAG; ROW_SELECTION_RULE_UNKNOWN", "verified": False, "finding": "paper reports 452 OS; availability marks exactly 452 baseline rows, all deceased; no published row-level rule"},
            "668_cohort": {"evidence_level": "PUBLISHED_COUNT_ONLY", "verified": False, "finding": "local 671 scan rows/630 people do not independently reproduce the paper's analytic denominator"},
        },
        "counts": {"baseline": 611, "availability_os": 452, "S1": 608, "S1_events": 585, "S1_censored": 23, "uncertain_excluded": 3},
        "sources": [
            "https://www.cancerimagingarchive.net/collection/upenn-gbm/",
            "https://github.com/data-nih/tcia/blob/main/upenn-gbm.md",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC9338035/",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC11643205/",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC12855786/",
        ],
    }
    dump_json(out / "upenn-os-field-evidence.json", field_evidence)
    (out / "upenn-os-field-definition-audit.md").write_text(
        "# UPENN OS field definition audit\n\n"
        "**Disposition: `RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS`; `OFFICIAL_ENDPOINT_VALIDATED=false`.**\n\n"
        "| Field | Evidence level | Verified? | Supported statement | Remaining gap |\n|---|---|---:|---|---|\n"
        "| `Survival_from_surgery_days_UPDATED` | Published cohort context; exact update rule researcher-inferred | No | Name states surgery/days; paper describes survival information from first surgery. | UPDATED transformation and added rows undocumented. |\n"
        "| `Survival_Censor` | Official semantics unknown; researcher-inferred for exploration | No | 26 baseline values occur among Alive/Lost/uncertain statuses. | Unit, origin, last-contact source/rule undocumented. |\n"
        "| `Survival_Status` | Literal official values observed; event map researcher-defined | No | Categories include Deceased, Alive, Lost to Follow-up and uncertain-date death. | No versioned dictionary specifies censor handling. |\n"
        "| Time origin | Published-study context | Partial | Cohort paper says survival information is from first surgical operation. | Exact censor field derivation is not linked to this statement. |\n"
        "| Three uncertain deaths | Official handling unknown | No | Separate status; excluded from primary candidate. | No source defines exclusion/censor handling. |\n"
        "| 452 | Published count plus availability flag | Count reproduced | Availability marks 452 rows, all deceased with positive UPDATED time. | Not a censored cohort; historical row-selection method remains unknown. |\n"
        "| 668 | Published count only | No | BrainIAC paper reports the number. | Analytic row/person rule not reproducible from local release. |\n\n"
        "The exploratory rule uses baseline `_11` only: Deceased + positive UPDATED as event; Alive/Lost + positive Survival_Censor as censor, **assuming elapsed days from first surgery**; uncertain deaths excluded. This is not an official validated endpoint. See `upenn-cohort-reconciliation.csv` and `analysis-v1/fusion-cv-results.json`.\n",
        encoding="utf-8")

    cross_evidence = {
        "status": "PASS_EXACT_SCAN_ID_CROSSWALK; REFERENCE_CONTENT_LINK_CONFIRMED; MRI_FILES_ARE_VARIANTS",
        "source_hashes": {"clinical": digest(args.clinical), "availability": digest(args.availability), "manifest": digest(args.manifest), "official_radiomics_zip": digest(args.radiomics_dir.parent / "radiomic_features_CaPTk.zip")},
        "scan_join": {"rule": "exact full scan ID equality; preserve _11/_21", "scans": 671, "clinical_unmatched": 0, "availability_unmatched": 0, "duplicate_ids": 0},
        "cohort_counts": {"people": 630, "baseline_11": 611, "followup_21": 60, "paired": 41, "followup_only": 19},
        "radiomics": {"automatic_structural_tables": 12, "intersection_all_12": len(complete_12), "table_ids_match_by_exact_scan_key": True, "selected_feature_panel": [x[2] for x in FEATURE_SPEC], "S1_complete_panel": len(analysis)},
        "sub002_reference_content_bridge": {"local_original_sha256": digest(args.local_mask), "pinned_mask_sha256": digest(args.mirror_mask), "pinned_scan_id": "UPENN-GBM-00002_11", "native_to_local_label_map": {"0": "0", "1": "1", "2": "2", "4": "3"}, "voxel_mismatches_after_map": 0, "pinned_manual_file_digest_unique_among_listed_masks": lfs_matches == 1, "manual_mask_entries_in_pinned_index": len(mask_files), "MRI_same_grid_but_voxel_identical": {k: False for k in MODALITIES}},
        "controls": ["No match was derived from numeric subject ordering.", "The separate UPENN-GBM-00001 DICOM case was not joined to sub-002.", "Patient-level crosswalk stays local and is not a Git artifact."],
    }
    cross_evidence["pinned_mirror_revision"] = args.mirror_revision
    dump_json(out / "upenn-crosswalk-evidence.json", cross_evidence)
    (out / "upenn-crosswalk-report.md").write_text(
        f"# UPENN imaging–clinical crosswalk\n\n"
        f"Exact full scan-ID equality joins {len(crosswalk)} manifest scans, official clinical rows and availability rows with zero missing/duplicate keys. Suffixes are preserved: 611 `_11`, 60 `_21`, 630 normalized people, 41 paired, 19 follow-up-only.\n\n"
        f"The patient-level file `{args.crosswalk.name}` is local-only under the controlled runtime directory. It contains scan/person keys and availability flags, not covariate values or image data.\n\n"
        f"## sub-002 reference bridge\n\n"
        f"The original local official-release `sub-002_seg.nii.gz` (SHA-256 `{digest(args.local_mask)}`) and pinned manifest `UPENN-GBM-00002_11_segm.nii.gz` (SHA-256 `{digest(args.mirror_mask)}`) share shape/affine and become exactly voxel-identical after mapping local 3 to mirror-native 4. Zero voxels differ; this is a content-based link, not an ordinal-ID assumption. The target mask digest appears once among {len(mask_files)} pinned manual-mask metadata entries. The four local MRI series share geometry with their pinned-mirror variants but are not voxel-identical; see the prior per-modality comparison in `sub002-candidate-match.json`.\n\n"
        f"The scan key and clinical key are exact matches in the release manifest/CSV. No DICOM PatientID was joined by numbering, and the separate UPENN-GBM-00001 DICOM case is not involved.\n\n"
        f"## Radiomics\n\nTCIA's official CaPTk archive contains {len(list(args.radiomics_dir.glob('Radiomic_Features*.csv')))} feature CSVs. The automatic-segmentation structural panel has 12 modality-region tables; the exact-ID intersection is {len(complete_12)} scans. The pre-specified four-feature panel intersects the researcher-defined S1 endpoint in N={len(analysis)}. Source asset hashes are in `source-assets/tcia-official/download-audit.json`.\n\n"
        f"## Limits\n\nThe NIfTI manifest is a pinned third-party mirror used as a fixed ID/path index; TCIA's published collection/paper remain the primary data provenance. MRI file identity across release variants is not claimed. The scan-level crosswalk is not an independent clinical dictionary or a DICOM crosswalk.\n",
        encoding="utf-8")

    fusion = {
        "status": "EXPLORATORY_COMPLETE_WITH_ENDPOINT_LIMITATIONS",
        "endpoint": {"status": "RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS", "official_validated": False, "time_unit_assumption": "days", "time_origin_assumption": "first surgery context; censor origin not officially documented"},
        "cohort": {"n": len(analysis), "events": int(y.sum()), "candidate_censored": int((y == 0).sum()), "baseline_only": True, "unique_patients": len(set(pids)), "uncertain_deaths_excluded": 3},
        "radiomics": {"source": "TCIA CaPTk official radiomic_features_CaPTk.zip", "segmentation": "automatic segmentation-derived", "features": [x[2] for x in FEATURE_SPEC], "feature_selection": "pre-specified first-order regional means; no outcome-driven selection"},
        "clinical_features": clinical_names,
        "excluded_covariates": {"MGMT": "high missingness; not included", "KPS": "high missingness; not included"},
        "models": fitted,
        "validation": {"method": "stratified 5-fold, one baseline row per patient", "seed": SEED, "imputation": "training-fold median only", "scaling": "fit by Cox estimator on training fold only", "cox": "existing BrainFusion Cox PH; Breslow ties; L2=0.1", "external_validation": False, "individual_predictions_saved": False},
        "limitations": ["The candidate censor time is assumed to be days from first surgery; the official field dictionary does not establish this.", "This is internal cross-validation, not independent external validation or clinical utility.", "Schoenfeld diagnostics are trend screens, not formal proportional-hazards tests.", "No patient-level risk predictions were persisted or reported."],
    }
    dump_json(out / "fusion-cv-results.json", fusion)

    inputs = [args.clinical, args.availability, args.manifest, args.local_mask, args.mirror_mask,
              args.manual_mask_manifest, args.radiomics_dir.parent / "radiomic_features_CaPTk.zip",
              args.radiomics_dir.parent / "UPENN-GBM_CaPTk_radiomic_features_list.csv",
              args.radiomics_dir.parent / "UPENN-GBM_CaPTk_fe_params.csv", Path(__file__).resolve()]
    dump_json(out / "run-manifest.json", {
        "script": Path(__file__).name, "script_sha256": digest(Path(__file__).resolve()),
        "git_head_at_run": "a72442af7f493cb335af3259424d033136aa576c",
        "seed": SEED, "inputs_sha256": {str(p): digest(p) for p in inputs},
        "outputs": [str(args.crosswalk), *[str(p) for p in planned]],
        "patient_level_crosswalk": "controlled runtime only; do not commit/publish",
        "no_mri_download_or_segmentation_inference": True,
    })
    print(json.dumps({"crosswalk_scans": len(crosswalk), "baseline": 611, "followup": 60,
                      "unique_people": len(people), "paired": 41, "manual_mask_digest_unique": lfs_matches == 1,
                      "radiomics_intersection_12_tables": len(complete_12), "fusion_n": len(analysis),
                      "fusion_events": int(y.sum()), "fusion_censored": int((y == 0).sum()),
                      "oof_c_index": {k: v["out_of_fold_c_index"] for k, v in fitted.items()},
                      "output": str(out)}, indent=2))


if __name__ == "__main__":
    main()
