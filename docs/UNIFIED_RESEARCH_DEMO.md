# Unified isolated research demo

## Start and stop

From PowerShell at the repository root, run:

```powershell
.\scripts\start-unified-research-demo.ps1
```

The launcher uses the existing runtime Python environment and frontend dependencies. It selects free loopback ports, prints the local frontend/API URLs and a disposable local review login, and creates an isolated SQLite database under `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo`. It does not bind the formal ports 18100/18180. Press Ctrl+C in that PowerShell window to stop only the backend and frontend processes started by this launcher. The demo database, copied engineering case files and logs remain available for reuse.

The UCSF-PDGM Cox artifact is loaded read-only from the protected research runtime and checked against its pinned artifact and manifest hashes at startup. The UPENN clinical and CaPTk models remain separately registered. Predictions require the local doctor session, CSRF protection and an explicit `SYNTHETIC_TEST` request; inputs and predictions are not written to the database.

## DICOM archive boundary

The demo checks that the existing Stage7 Orthanc container is running on loopback port 18142 and has the expected image/config mount. It authenticates to the archive, reads its current server identity and statistics, then writes a temporary demo-only config with the refreshed identity pin. The original Stage7 config and Orthanc volume are untouched. Pixel access is enabled only in the isolated process by `PACS_RESEARCH_DEMO_PIXEL_READ`; import and AI bridge remain disabled. The temporary config contains archive credentials and is removed during normal launcher cleanup.

Choose **隔离 DICOM 归档** in the sidebar, inspect a study and its series, then open a supported MR series. This route has no NIfTI case ID, case-link action, conversion action or model-submit action. It reads pixels directly from the selected archive series, preserves its DICOM geometry and rejects unsupported or inconsistent series. The verified live archive contained 5 studies, 5 series and 652 instances; the browser acceptance loaded 192 real frames from one supported series. These study counts and pixels are from the isolated research archive, not the formal PACS.

## Demo sequence

1. Open **病例管理**, then the isolated engineering case. Review its existing four-sequence NIfTI view, persisted segmentation and report. Do not start another analysis.
2. Open **隔离 DICOM 归档** separately. Select a Study and Series and open the real DICOM pixels. Do not describe this as the NIfTI case's source; no patient mapping is asserted.
3. Open **IDH 与融合研究**. Review the research status and select the UCSF-PDGM GBM clinical Cox model. Enter only synthetic age/sex values and run the prefilled 365/730/1095-day example.
4. Review the API-backed relative risk, survival probabilities and curve. The model is an internal five-fold research model trained on 367 IDH-wildtype GBM records (223 events, 144 censored); mean fold Harrell C-index was 0.637. This is not external or clinical validation.

## Verified results and limits

The one-run browser/API acceptance is `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo\unified-live-e2e.json`. It records aggregate counts only, verifies HTTP 200 frame responses and a real Cornerstone viewer-ready state, then verifies a synthetic UCSF prediction and monotone finite probabilities. The isolated database had zero prediction rows after the run. Formal backend/frontend, formal database and formal PACS/AI gates were not changed.

The selected DICOM series and engineering NIfTI case remain separate. The archive is read-only in this demo. No conversion, automated identity mapping, AI inference, patient-level survival prediction, or clinical use is enabled. UCSF endpoint fields are documented by TCIA v5, but the model has only internal validation and a single-center cohort; its output is research-only.
