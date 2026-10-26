# Survival prediction implementation closeout

Date: 2026-10-26
Branch at implementation: `codex/research-edition-20261022`
Baseline source commit: `a1c1fe33497c6f93512b00804f8fe4cee714fd0b`

## Delivery status

| Area | Status | Evidence / boundary |
|---|---|---|
| Cox artifact loader and SHA-256 manifest verification | PASS | Versioned runtime artifact; tamper, schema, feature order and baseline checks are tested. |
| Clinical Cox model fit | EXPLORATORY_COMPLETE | Full candidate fit converged on 608 researcher-defined S1 rows; 585 candidate events/23 candidate censors. |
| Clinical internal validation | EXPLORATORY | Five patient-level stratified folds, seed 20261026; mean Harrell C-index 0.6462, SD 0.0147. Not external validation. |
| Fusion Cox model fit | EXPLORATORY_COMPLETE | Final fit converged on the existing feature-complete N=596 cohort; 574 candidate events/22 candidate censors; prior CV reused, not rerun. |
| Existing matched-cohort comparison | EXPLORATORY | Mean fold C-index: clinical 0.6495 (SD 0.0252), CaPTk-only 0.5273 (0.0190), combined 0.6510 (0.0260). No demonstrated fusion gain; not external validation. |
| Survival probability software | PASS_SYNTHETIC_TEST | Breslow baseline function and Cox formula tested for monotonicity, finite range, deterministic output, supported time window and categories. |
| API/UI | PASS_SOFTWARE_SYNTHETIC_ONLY | `/api/survival/status`, `/models`, `/predict`; clinical/fusion selection, exact CaPTk schema, synthetic request contract; browser renders both synthetic responses. |
| Official OS endpoint | BLOCKED_BY_DATA_DICTIONARY | Censor semantics/unit/origin/derivation and updated event-time rules remain unresolved. |
| One-year classification | NOT_RUN | Endpoint is unvalidated; no binary target was created. |
| Real-patient risk predictions | NOT_GENERATED | API forbids patient IDs, allows only declared synthetic scope, and stores no predictions. |
| Fusion input source | PASS_SOFTWARE / EXPLORATORY_MODEL | Reuses exact-ID joined official CaPTk features; BrainFusion's 20 features are explicitly incompatible and rejected. Clinical endpoint still unvalidated. |
| RSF | NOT_IMPLEMENTED | Compatible `sksurv` is unavailable; no dependency was installed. |

## Model artifact

Clinical runtime artifact: `E:\BrainFusion-Runtime\research-edition\results\survival-models\upenn-clinical-cox-research-v1.0.1`. Fusion runtime artifact: `E:\BrainFusion-Runtime\research-edition\results\survival-models\upenn-clinical-captk-fusion-cox-research-v1.0.0`.

- Model `upenn-clinical-cox-research`, version `1.0.1-research-only`.
- Training data: official v1.2 CSV SHA-256 `fd5749ae5a8d77e599e02264d961d94107752f0244e34bf0bc711a75fe0e2ec5`; exact audited S1 cohort contract is enforced by the training script.
- Training rows/events/censors: 608 / 585 / 23; baseline `_11` only, one row per normalized patient.
- Covariates: age, gender, IDH1 and resection categories. Age and gender complete; unknown resection has an explicit indicator; unsupported IDH1 categories are rejected.
- Cox optimizer converged; ridge penalty 0.1; Breslow ties. The final all-cohort fit is distinct from the five cross-validation fits.
- Baseline cumulative hazard and survival are stored in days and generated from the full fit.
- Model artifact SHA-256: `41c52f20371dd33a25c60bf981a6a811c6863bc01834062d33e6e4ae7f3ce8ff`.
- Fusion model `upenn-clinical-captk-fusion-cox-research`, version `1.0.0-research-only`, uses the existing TCIA CaPTk archive and exact scan-ID joins for `T1GD_ET_Intensity_Mean`, `FLAIR_ED_Intensity_Mean`, `T2_ED_Intensity_Mean`, and `T1_NC_Intensity_Mean` plus the five clinical terms in the prior 596-row comparison. Twelve of the 608 S1 candidates lacked a complete panel, yielding N=596/574/22. BrainFusion's 20 features are not mapped or accepted.
- Fusion CV is reused from the audited `analysis-v2/fusion-cv-results.json`; it was not rerun. The final full-cohort fusion fit is separate from the fold models. Artifact SHA-256: `0988d6d145e103cea90c5c15daff94a17d1cf8741ea65c63d957f7915de3b034`.
- The artifact/manifest are local runtime research material and are deliberately not committed to Git.

## API behavior

Checked-in defaults are empty clinical/fusion model directories and `SURVIVAL_RESEARCH_PREDICTION_ENABLED=false`. An isolated research process must explicitly configure model paths and enable the feature. The prediction schema has no patient identifier and requires a model ID, `declared_use_scope: "SYNTHETIC_TEST"`, local doctor session authentication and CSRF protection. Fusion requests require exactly the four CaPTk values; the clinical model rejects radiomics payloads. The API does not log or persist inputs or scores. The existing formal service/container configuration was not changed.

Example request (synthetic fixture only):

```json
{
  "declared_use_scope": "SYNTHETIC_TEST",
  "model_id": "upenn-clinical-cox-research",
  "clinical": {
    "age_years": 63,
    "gender": "F",
    "IDH1": "Wildtype",
    "GTR_over90percent": "N"
  },
  "requested_times_days": [365, 730, 1095]
}
```

Use `GET /api/survival/status` and `GET /api/survival/models` before synthetic testing. The fusion model additionally requires a `radiomics` object with exactly the four registered CaPTk keys. The API returns a relative-risk index and researcher-defined endpoint survival probabilities, each marked `research_only`; it rejects times beyond observed event follow-up. The service is disabled unless separately configured in an isolated environment.

## Verification

- Backend: existing BrainFusion Conda Python, `pytest tests/test_survival_prediction.py tests/test_research.py -q`: **26 passed**, 4 existing Starlette/FastAPI deprecation warnings.
- UI/API contract: one Playwright Microsoft Edge test with explicit synthetic API fixtures selected both models: **1 passed**. Initial default Chromium launch could not start because the local Chromium executable was absent; no browser was downloaded or installed.
- Frontend: `npm run build`: **passed**; existing Node-core externalization and large-chunk warnings remain.
- Actual artifacts/API: both runtime artifacts loaded through FastAPI with synthetic covariates; clinical and fusion calls returned 365/730/1095-day curves; incompatible BrainFusion feature keys returned 422. No patient was used for inference and no output persisted.
- Not run: complete backend suite, live production browser/API integration, production container tests, one-year classification, external validation, SegResNet, or any model/production deployment.

## Remaining external work

Obtain authoritative UPENN/TCIA clarification for `Survival_Censor`, the updated event time, and uncertain-death handling before describing any artifact as a validated OS model or enabling real-patient prediction. The available fusion artifact uses the specifically named CaPTk panel, but its same-cohort CV showed no demonstrated gain; it is not a BrainFusion-radiomics model. No code or software behavior can substitute for missing endpoint definitions and external validation.

## Reproduction

Run from `E:\BrainFusion-AI\backend` with the existing BrainFusion Conda interpreter and the protected, previously audited inputs. Each output directory must be new and versioned; both trainers refuse to overwrite existing artifacts. These commands refit the exploratory research artifacts and do not authorize real-patient predictions:

```powershell
& 'E:\BrainFusion-AI\.conda\brainfusion\python.exe' tools\train_upenn_clinical_cox.py `
  --clinical '<protected official v1.2 CSV>' `
  --output-dir '<new protected runtime version directory>'

& 'E:\BrainFusion-AI\.conda\brainfusion\python.exe' tools\train_upenn_fusion_cox.py `
  --clinical '<protected official v1.2 CSV>' `
  --radiomics-zip '<verified official CaPTk feature archive>' `
  --existing-cv '<audited fusion CV JSON>' `
  --output-dir '<new protected runtime version directory>'
```

After fitting, configure `SURVIVAL_MODEL_DIR`, `SURVIVAL_FUSION_MODEL_DIR`, and `SURVIVAL_RESEARCH_PREDICTION_ENABLED=true` only in an isolated research process. Checked-in and formal deployment defaults remain disabled. Exercise `/api/survival/predict` only with synthetic fixture values and `declared_use_scope: "SYNTHETIC_TEST"`.
