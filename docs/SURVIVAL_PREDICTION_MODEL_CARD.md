# UPENN clinical Cox model card

## Model identity

- ID: `upenn-clinical-cox-research`
- Version: `1.0.1-research-only`
- Type: ridge-regularized Cox proportional-hazards model with Breslow ties
- Intended use: software demonstration and exploratory research-method evaluation only
- Prohibited use: clinical decisions, care prioritization, patient-level prognostic claims, or real-patient API requests
- Artifact location: protected runtime `E:\BrainFusion-Runtime\research-edition\results\survival-models\upenn-clinical-cox-research-v1.0.1`; model and manifest are not tracked in Git

## Cohort and endpoint

The fit uses the official-designated UPENN clinical v1.2 CSV whose audited SHA-256 is `fd5749ae5a8d77e599e02264d961d94107752f0244e34bf0bc711a75fe0e2ec5`. It uses only one baseline `_11` row per normalized patient. The researcher-defined S1 candidate rule labels `Deceased` with positive `Survival_from_surgery_days_UPDATED` as an event and `Alive` or `Lost to Follow-up` with positive `Survival_Censor` as right censored; three uncertain-date deaths are excluded. This yields 608 rows, 585 candidate events and 23 candidate censors.

This endpoint is **not officially validated**. Public materials do not establish `Survival_Censor` meaning, unit, time origin, derivation from last contact, the exact updated event-time transformation, or handling of uncertain deaths. The candidate time unit is assumed to be days in a first-surgery context. The model status is therefore `RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS`, not a formal OS endpoint.

## Predictors and processing

Prespecified concepts: age in years; gender (F reference, M indicator); IDH1 (Wildtype reference, Mutated and NOS/NEC indicators); and `GTR_over90percent` (N reference, Y indicator, plus an explicit unknown indicator). Age and gender were complete in the selected candidate rows. IDH1 values outside the observed trained categories are rejected. Numeric means and population standard deviations are stored in the artifact; cross-validation fits scaling separately inside each training fold. No outcome-informed imputation or feature selection was performed.

## Fitting and internal validation

- Optimizer: existing project Cox primitive, ridge penalty 0.1, Breslow ties.
- Internal validation: stratified five-fold split at patient level; one baseline row per patient; seed `20261026`; fold-local scaling; mean Harrell C-index `0.6462224`, fold SD `0.0147100`.
- Interpretation: C-index measures ranking among comparable pairs, not classification accuracy. This internal score is exploratory and is not independent external validation.
- The final full-cohort model is a separate fit, not a selected CV-fold model. The artifact stores standardized coefficients and a Breslow baseline cumulative hazard/survival function.
- A full-cohort Schoenfeld-residual trend screen is recorded as a screening diagnostic only; it is not a formal proportional-hazards test and has no multiple-testing correction. Regularized coefficient confidence intervals are not provided.

The reproducible clinical-artifact trainer is `backend/tools/train_upenn_clinical_cox.py`. It verifies the audited CSV SHA and S1 cohort counts, refuses an existing nonempty output directory, and writes only model/manifest metadata under the protected research runtime. Use a new versioned output path when rebuilding; never direct it to the repository or production runtime.

## Prediction contract

The software computes `S(t|x) = exp(-H0(t) * exp(lp))` in days. It rejects unsupported categories, missing or additional fields, ages outside the trained range, invalid/unsorted times, and requested times beyond the largest observed event time. Predictions are not stored. The API only accepts explicitly declared `SYNTHETIC_TEST` requests and requires the existing local doctor session/CSRF token. A local account is not proof of clinical qualification or research authorization. The runtime must be explicitly configured; checked-in settings disable model loading and prediction by default.

## Limitations and non-claims

- Official endpoint definition and clinical utility are not established.
- No independent validation, prospective validation, calibration assessment or external test cohort was performed.
- One-year classification is not implemented/run.
- No real-patient predictions were generated or persisted.
- The clinical artifact is not a fusion model; the separate CaPTk fusion artifact and its limitations are documented below. BrainFusion's 20 features are not mapped to CaPTk features.
- RSF is not implemented because compatible `sksurv` is unavailable.
- The previous exploratory Cox result around C-index 0.634 is a different analysis and is not validation for this artifact.

## Separate clinical + CaPTk fusion artifact

The isolated runtime also contains `upenn-clinical-captk-fusion-cox-research` version `1.0.0-research-only`. It was fit once on the already audited common cohort (N=596, 574 candidate events/22 candidate censors), not on a reselected cohort. The four required imaging inputs are exactly `T1GD_ET_Intensity_Mean`, `FLAIR_ED_Intensity_Mean`, `T2_ED_Intensity_Mean`, and `T1_NC_Intensity_Mean`, from TCIA's official CaPTk automatic-segmentation feature archive. Twelve of the 608 S1 candidate rows lack the complete feature panel. Its full-cohort fit is distinct from CV folds.

For the prior matched-cohort comparison, the existing five-fold CV is reused and not rerun: mean fold C-index was 0.6495 (SD 0.0252) for clinical-only, 0.5273 (0.0190) for CaPTk-only, and 0.6510 (0.0260) for combined. This does not demonstrate fusion gain. The inputs are modality-specific original intensity means; model standardization is fit on the full development cohort for the final artifact and separately within training folds in the previous CV. BrainFusion's own 20 features are not equivalent, are not accepted by the fusion API, and are not mapped to these CaPTk inputs.

The reproducible final fusion-artifact trainer is `backend/tools/train_upenn_fusion_cox.py`. It verifies the official clinical CSV SHA, TCIA feature archive SHA, existing audited CV results SHA, exact feature names, exact scan IDs and the expected N=596/574/22 cohort. It does not rerun CV or write IDs/rows/predictions. Use a new empty versioned runtime output path to rebuild.

## UCSF-PDGM GBM clinical Cox artifact

- ID: `ucsf-pdgm-clinical-cox-research`
- Version: `1.0.0`
- Dataset: TCIA UCSF-PDGM Version 5 (2025-05-30); clinical CSV and glossary downloaded from the TCIA official release attachments. Model artifact and manifest are held only in the protected research runtime.
- Official source references: [TCIA UCSF-PDGM collection](https://www.cancerimagingarchive.net/collection/ucsf-pdgm/), [official metadata v5 CSV](https://www.cancerimagingarchive.net/wp-content/uploads/UCSF-PDGM-metadata_v5.csv), [official metadata glossary](https://www.cancerimagingarchive.net/wp-content/uploads/UCSF-PDGM-metadata_glossary.csv), [TCIA release data notes](https://github.com/data-nih/tcia/blob/main/ucsf-pdgm.md).
- Cohort: baseline-only final diagnosis `Glioblastoma, IDH-wildtype`; N=367, with 223 deaths and 144 censored records. The other six `_FU` follow-up rows are excluded so each patient appears once.
- Endpoint: TCIA v5 glossary documents `OS` in days from initial diagnosis to last clinical follow-up and `1-dead 0-alive` as vital status at last follow-up. The event/time interpretation follows those dataset fields; the model remains research-only and does not establish clinical utility.
- Inputs: age at preoperative MRI and sex only. Survival time, vital status and follow-up fields are never predictors. MRI age is not asserted to equal age at initial diagnosis. The model does not accept UPENN resection or CaPTk features.
- Training: ridge Cox PH (`alpha=0.01`) with Efron tie handling; five-fold patient-level stratified internal cross-validation, seed `20261026`, all preprocessing fit within training folds. Mean fold Harrell C-index `0.6373`; pooled out-of-fold C-index `0.6321`. Mean-fold IPCW Brier scores at 365/730/1095 days were `0.2082/0.2105/0.1648`.
- Artifact SHA-256: `9ce60525516db23436e818d1e5f84dda71a6fc505889ffefb625bf77646d0016`. The isolated runtime checks the manifest hash before loading.
- Limits: one-center internal validation only; no external cohort or clinical validation. Age is measured at MRI, which can differ from the initial-diagnosis time origin. The model is suitable only for `SYNTHETIC_TEST` software demonstration, not real-patient prediction or decisions. UCSF and UPENN C-index values are not directly comparable because cohorts and endpoints differ.
- Reproduction entry point: `backend/scripts/train_ucsf_pdgm_cox.py`; the script is for a new versioned runtime output and must not target the repository or production paths.

## UCSF-PDGM V2 fair comparison and selected artifact — 2026-10-27

This section supersedes the V1-only UCSF software state above. V1 remains an earlier artifact/history; V2 uses the same TCIA v5 clinical source and is installed only in the isolated runtime package.

- Model ID/version: `ucsf-pdgm-clinical-cox-research` / `2.0.0`.
- Source: TCIA UCSF-PDGM metadata v5; pinned CSV SHA-256 `afc1c23a0eb0597b56e603741e72f2308b4860281187cd3808e05b7a0116fd78`.
- Cohort: one baseline row per patient, final diagnosis `Glioblastoma, IDH-wildtype`, positive documented OS and known vital-status field; N=367, 223 event-coded deaths, 144 censored. OS is documented in days from initial diagnosis to last clinical follow-up in the v5 glossary. Age is measured at MRI, so the diagnosis-to-MRI interval is not modeled.
- Shared comparison protocol: stratified five-fold patient-level outer split, seed `20261027`; all feature centering, standardization and fitted model parameters are learned within each training fold. Fixed candidate penalties: Ridge alpha `0.01`; Elastic-Net alpha `0.01`, L1 ratio `0.5`. No hyperparameter search or seed search was performed.

| Candidate | Mean fold Harrell C (SD) | Pooled OOF C | IPCW Brier 365d | IPCW Brier 730d | IPCW Brier 1095d | Mean fold IBS | Selected |
|---|---:|---:|---:|---:|---:|---:|---|
| Age + sex Ridge Cox (baseline) | 0.6333 (0.0447) | 0.6320 | 0.2075 | 0.2130 | 0.1669 | 0.1994 | Yes |
| Age + sex + biopsy-before-MRI Ridge Cox | 0.6347 (0.0467) | 0.6330 | 0.2059 | 0.2179 | 0.1702 | 0.2018 | No |
| Age quadratic + sex Ridge Cox | 0.6377 (0.0492) | 0.6376 | 0.2038 | 0.2123 | 0.1625 | 0.1970 | No |
| Age + sex + biopsy-before-MRI + age quadratic Elastic-Net Cox | 0.6354 (0.0477) | 0.6341 | 0.2020 | 0.2170 | 0.1656 | 0.1992 | No |

The predeclared upgrade rule required pooled OOF C-index gain ≥0.01, paired percentile-bootstrap 95% CI lower bound >0, improvement in at least four of five folds, and non-worse paired IPCW Brier (within 0.005) at at least two of three horizons. No candidate passed; the age+sex Ridge baseline is retained. The quadratic candidate's numerical C-index increase is small and did not meet the rule. Bootstrap intervals are descriptive and do not account for dependence among overlapping CV training folds; all results remain internal, exploratory comparisons, not an unbiased external performance estimate.

- Selected full eligible cohort fit: ridge Cox PH with Efron ties, alpha `0.01`; N=367 / 223 / 144 (events/censors). Cross-validation models are not reused as the final fit. The artifact stores ordered features `age_at_mri_years`, `sex_M`, means/scales, coefficients and a full-cohort Breslow baseline survival function in days.
- Validation for the selected baseline: mean fold C `0.6333`, SD `0.0447`; pooled OOF C `0.6320`, descriptive patient bootstrap 95% interval `[0.5945, 0.6709]`; mean-fold IPCW Brier at 365/730/1095 days `0.2075 / 0.2130 / 0.1669`; mean fold IBS `0.1994`. Calibration output is fold-level calibration-in-the-large only; no calibration slope, independent test set or external validation.
- Artifact SHA-256: `820ee0c05d50b49ee7343a2bed51b5ff60c70fad7d83551d5fa7f9fb60c5144c`; manifest SHA-256: `7a21393e7e3c5f02ca14a16f41eaac90b00885d0cdcd94958a975dd388f8799c`. Protected runtime directory: `E:\BrainFusion-Runtime\research-edition\results\ucsf-pdgm-survival-v2-20261027\model-artifact`.
- Aggregate comparison/contract and patient-level OOF rows are under that versioned protected runtime result directory. OOF rows contain no ID column but include row index, time/event, fold and estimates; treat them as patient-level research data, do not publish or commit. Individual API requests/predictions are not persisted.
- Candidate policy: RSF `NOT_RUN` because `sksurv` is unavailable in approved environments; no dependency was installed. UCSF radiomics fusion `NOT_RUN` because no verified UCSF patient-level radiomics table/crosswalk is present. No UPENN model was refit or included in this comparison.
- Scope: RESEARCH_CASE is disabled by default and can be enabled only by a separate isolated runtime setting. It accepts only the UCSF model ID and exact UCSF cohort declaration, has no patient identifier field, requires local doctor-session/CSRF protection, and returns `RESEARCHER_ASSERTED_NOT_INDEPENDENTLY_VERIFIED`. The API cannot independently establish cohort membership from age/sex fields; do not submit UPENN or out-of-cohort records. This is not clinical use.
