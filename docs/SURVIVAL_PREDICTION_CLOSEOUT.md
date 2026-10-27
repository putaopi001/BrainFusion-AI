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
- Live artifact-to-Vue E2E: `frontend/e2e/survival-live-artifact.spec.js` is opt-in and is launched by `frontend/e2e/run-survival-live-artifact.ps1`. The runner verifies the expected artifact hashes, starts FastAPI and Vite on free loopback ports with a new temporary SQLite and synthetic doctor account, and removes its temporary database/account after the run. The Edge test uses the real `/api/survival/status`, `/models`, `/predict`, and local login/CSRF flow; only unrelated legacy research summary/patient panels are synthetic fixtures. Both actual models rendered their returned curves; missing CaPTk input, unsupported IDH1 category, and descending times were rejected; the isolated prediction table remained empty. Latest run evidence: `E:\BrainFusion-Runtime\research-edition\results\survival-live-artifact-e2e-20261026\run-20261026T181052-1af8d93e`.
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

To repeat the full real-artifact UI/API integration from PowerShell, run `& .\e2e\run-survival-live-artifact.ps1` from `E:\BrainFusion-AI\frontend`. The runner refuses model-hash mismatches, chooses free non-production ports, verifies the isolated DB has zero prediction rows, and saves each run under the versioned runtime evidence directory above.

## Survival prediction V2 research branch — 2026-10-27

This is the latest software closeout for branch `codex/survival-research-v2`, based on frozen engineering commit `2684bff19ceb4706b30a8cafe61a2c7a1b2acb7d`. It does not modify the frozen worktree or formal deployment.

- **Model comparison: EXPLORATORY_COMPLETE.** Four UCSF-PDGM v5 clinical Cox candidates were compared on the same patient-level five-fold split. No candidate met the preregistered stable-improvement rule; V2 preserves the age+sex Ridge Cox baseline rather than claiming an upgrade. Results and experiment contract: `E:\BrainFusion-Runtime\research-edition\results\ucsf-pdgm-survival-v2-20261027\model-comparison.json`, `.csv`, and `run-contract.json`.
- **Final model artifact: PASS_INTEGRITY.** Version `2.0.0`, N=367, 223 events, 144 censored; artifact SHA-256 `820ee0c05d50b49ee7343a2bed51b5ff60c70fad7d83551d5fa7f9fb60c5144c`; manifest SHA-256 `7a21393e7e3c5f02ca14a16f41eaac90b00885d0cdcd94958a975dd388f8799c`. The runtime package is not committed.
- **Research API/UI: PASS_ISOLATED_E2E.** V2 adds an isolated `RESEARCH_CASE` scope for the UCSF model, while retaining `SYNTHETIC_TEST`. The additional `SURVIVAL_RESEARCH_CASE_ENABLED` switch defaults false. RESEARCH_CASE requires a UCSF cohort declaration, a user checkbox attestation in the UI, local doctor-session/CSRF authorization, and accepts no patient identifier. The service cannot independently verify cohort membership; response states `RESEARCHER_ASSERTED_NOT_INDEPENDENTLY_VERIFIED`, rejects a declared UPENN cohort/model, and instructs users not to submit UPENN records. Predictions are not written to the database.
- **Real browser/API evidence:** `E:\BrainFusion-Runtime\research-edition\results\survival-v2-live-e2e-20261027\run-20261027T141518-6128e721`. Both input scopes used the real V2 artifact and live isolated FastAPI routes through Edge/Vue. Authenticated 365/730/1095-day curves were finite, in `[0,1]`, and non-increasing; incorrect cohort was 422, unauthenticated request 401, isolated prediction rows 0. Only unrelated legacy research panels used synthetic fixtures.
- **Targeted backend tests:** `18 passed`; **frontend build:** passed; **V2 live Edge E2E:** `1 passed`; no formal service/model was started or altered. Test execution used the existing Python environment and read-only dependency reuse; no package installation was performed.
- **Not run:** RSF (no compatible `sksurv`); UCSF radiomics fusion (no verified feature/crosswalk table); one-year classification; external validation; UPENN inference; production deployment.

The V2 OS endpoint follows the documented TCIA UCSF-PDGM v5 glossary, but the model remains single-center, internally validated and research-only. Age is measured at MRI while OS starts at initial diagnosis. The API cannot authenticate that a manually entered research record belongs to UCSF-PDGM; RESEARCH_CASE is an explicit researcher attestation, not identity verification. Never represent these results as clinical prediction or external validation.

Reproduction command from the independent worktree's backend directory:

```powershell
& 'E:\BrainFusion-AI\.conda\brainfusion\python.exe' scripts\compare_ucsf_pdgm_survival_v2.py `
  --clinical-csv 'E:\BrainFusion-Data\UCSF-PDGM\clinical\UCSF-PDGM-metadata_v5.csv' `
  --output-root '<new protected versioned runtime directory>'
```

The command refuses a non-empty output directory. It writes model artifact/manifest, aggregate candidate metrics, and a protected local OOF file without identifiers. OOF data must remain in protected runtime and must not be committed. For an isolated real-artifact Edge run, use `frontend\e2e\run-survival-live-artifact.ps1 -V2`; it verifies the pinned artifact hash, selects non-production ports, generates a temporary local account and SQLite, then removes that temporary sandbox. The run saves aggregate evidence under the dated runtime results directory.
