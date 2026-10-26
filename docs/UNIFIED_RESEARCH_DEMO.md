# Unified isolated research demo

## Start and stop

From PowerShell at the repository root, run:

```powershell
.\scripts\start-unified-research-demo.ps1
```

The launcher uses the existing runtime Python environment and frontend dependencies. It selects free loopback ports, prints the local frontend/API URLs and a disposable local review login, and creates an isolated SQLite database under `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo`. It does not bind the formal ports 18100/18180. Press Ctrl+C in that PowerShell window to stop only the backend and frontend processes started by this launcher. The demo database, copied engineering case files and logs remain available for reuse.

The UCSF-PDGM Cox artifact is loaded read-only from the protected research runtime and checked against its pinned artifact and manifest hashes at startup. The UPENN clinical and CaPTk models remain separately registered. Predictions require the local doctor session, CSRF protection and an explicit `SYNTHETIC_TEST` request; inputs and predictions are not written to the database.

## DICOM archive boundary

The demo checks that the existing Stage7 Orthanc container is running on loopback port 18142 and has the expected image/config mount. It authenticates to the archive, reads its current server identity and statistics, then writes a demo-only config with the refreshed identity pin. The original Stage7 config and Orthanc volume are untouched. Pixel access is enabled only in the isolated process by `PACS_RESEARCH_DEMO_PIXEL_READ`. Import is limited to the pre-registered source bundle and requires an explicit acknowledgement in the demo UI; AI bridge stays disabled. Generated runtime config and logs remain outside the repository for local reuse.

Choose **隔离 DICOM 归档** in the sidebar to inspect the registered source status and archive studies/series. The reviewed source bundle was revalidated and, after explicit acknowledgement, imported into the isolated Stage7 archive with 192/192 instances verified. The live acceptance then opened that exact MR series and received 192 real frame responses (HTTP 200). The resulting archive contained 6 studies, 6 series and 844 instances. This is a source-bundle import to isolated research storage, not the formal PACS. The viewer has no NIfTI case ID or case-link action. The source contains one MR series only, so four-sequence conversion remains blocked; no partial conversion or AI submission is offered.

## Demo sequence

1. Open **病例管理**, then the isolated engineering case. Review its existing four-sequence NIfTI view, persisted segmentation and report. Do not start another analysis.
2. Open **隔离 DICOM 归档** separately. Revalidate the registered source, acknowledge isolated-only import if it is not present, inspect the Study/Series, and open the real DICOM pixels. Do not describe this as the NIfTI case's source; no patient mapping is asserted. The one-series bundle cannot start four-sequence conversion.
3. Open **UPENN sub-002 分割研究**. Sign in through the local review session. View the independent `UPENN-GBM-sub-002` NIfTI entry, the existing SegResNet mask/overlay and WT/TC/ET report. The page reads pinned artifacts and does not rerun inference. It is not associated with the engineering case or the DICOM Study.
4. Open **IDH 与融合研究**. Review the research status and select the UCSF-PDGM GBM clinical Cox model. Enter only synthetic age/sex values and run the 365/730/1095-day example.
5. Review the API-backed relative risk, survival probabilities and curve. The model is an internal five-fold research model trained on 367 IDH-wildtype GBM records (223 events, 144 censored); mean fold Harrell C-index was 0.6373. This is not external or clinical validation.

## Verified results and limits

The final live Edge/API acceptance is `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo\evidence\final-integration-e2e-20261026-run4.json`. It records aggregate counts only, verifies source status and 192/192 archive instances, 192 HTTP 200 DICOM frame responses, the pinned UPENN sub-002 viewer/report/overlay, and an artifact-backed synthetic UCSF prediction with finite monotone probabilities. No patient identifiers were recorded and no prediction was persisted. Formal backend/frontend, formal database and formal PACS/AI gates were not changed.

The selected DICOM series, engineering NIfTI case and UPENN sub-002 research entry remain separate. The archive is browsable after the one registered source import; it cannot convert this one-series source. No automated identity mapping, DICOM-to-AI inference, patient-level survival prediction, or clinical use is enabled. UCSF endpoint fields are documented by TCIA v5, but the model has only internal validation and a single-center cohort; its output is research-only.
