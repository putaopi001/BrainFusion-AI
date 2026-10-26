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
