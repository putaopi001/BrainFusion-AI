# BrainFusion-AI final engineering closeout

Date: 2026-10-26
Branch: `codex/research-edition-20261022`
Source baseline: `e8cdfddd1b5322487c4665b88fc61ca0d39d2b82`

## Delivery

An isolated source-based research demo is available at `scripts/start-unified-research-demo.ps1`. It uses the existing Python and Node environments, a dedicated copy of the previously reviewed RC engineering sample, independent SQLite/uploads/logs, non-production loopback ports, and the two protected Cox artifacts after checking their exact hashes and manifests. The launcher prints the selected local URLs and a one-run synthetic demo login. Press `Ctrl+C` in that PowerShell window to stop only the processes it started. The verified database/upload copy and logs remain under `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo`; the launcher does not delete them.

Start from the repository root:

```powershell
.\scripts\start-unified-research-demo.ps1
```

The launcher refuses to start if a model or manifest hash differs, if the existing demo copy is incomplete, or if no free loopback port is available. It does not install dependencies, start Docker, or target formal ports `18100/18180`. Model artifacts remain in the protected Runtime directory. SegResNet weights are deliberately unavailable in this demo process so the historical result can be viewed without rerunning inference. The demo UI disables new radiomics extraction, research-input writes, and reference-label uploads.

## Suggested walkthrough

1. From Home, open Case Management and case `1` (`RC-Engineering-Smoke`).
2. Open the workstation and view the existing four-sequence MRI and saved segmentation. Do not trigger a new analysis or write a review.
3. Open the saved report to review the model lineage and WT/TC/ET volumes. PDF export is available from that report.
4. Open Research to view the available aggregate research summary and the independent synthetic survival panel.
5. Log in using the local demo credential printed by the launcher. Run the synthetic clinical Cox example, then the clinical + CaPTk Cox example. The real protected model artifacts and real API generate the curves; the request is explicitly `SYNTHETIC_TEST` and is not stored.
6. Keep the engineering case, aggregate cohort findings, and synthetic survival predictions distinct in any presentation.

The isolated sample database has one case, one MRI, one saved analysis and report, and no `mri_features` rows. Therefore its current-case radiomics table remains empty and extraction is disabled. Do not claim that another case's features belong to this sample. Existing archived feature SQL/API/CSV evidence and aggregate research results remain separate evidence sources.

## Acceptance evidence

- Production frontend build: PASS (Vite completed; existing dependency externalization and large-chunk warnings remain).
- Live unified route smoke in Microsoft Edge: PASS for `/`, `/case/1`, `/workstation/1`, `/report?case_id=1`, `/research?case_id=1`; 0 page errors and 0 failed loopback requests. Existing analysis and report were current; report export was available.
- Real-artifact survival Edge/API E2E: PASS, 1 test. Both clinical Cox v`1.0.1-research-only` and clinical + CaPTk Cox v`1.0.0-research-only` were loaded from the protected artifacts. Their model SHA-256 values are `41c52f20371dd33a25c60bf981a6a811c6863bc01834062d33e6e4ae7f3ce8ff` and `0988d6d145e103cea90c5c15daff94a17d1cf8741ea65c63d957f7915de3b034`; manifests were checked. Real local login/CSRF and prediction endpoints were exercised with synthetic inputs. Curves were finite, in `[0,1]`, and nonincreasing; missing fusion features, unsupported category and descending time inputs were rejected. No prediction was persisted.
- Isolated database check: PASS (`integrity_check=ok`, no foreign-key errors). The original RC source database/upload hashes matched the copied manifest; the container upload paths in the demo copy use JSON-safe forward slashes.
- Shutdown check: PASS. Demo ports were released. Formal backend and frontend returned HTTP 200 on `18100/18180`; formal `/pacs/status` remained unavailable with read/import/DICOM/pixel/AI-bridge gates all false. No formal service, database, container or gate was modified.
- Evidence: `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo\logs\unified-demo-acceptance.json`, `live-artifact-e2e-20261026-recheck1.json`, `SHA256SUMS.txt`, and `demo-copy-manifest.json`.

No retraining, clinical cohort audit, SegResNet inference, feature re-extraction, formal deployment, or unrelated full test suite was run in this closeout.

## Research limits and freeze status

The software demonstration is complete. The OS endpoint remains `BLOCKED_BY_DATA_DICTIONARY`; both Cox artifacts use a researcher-defined endpoint and remain exploratory. The demo accepts only synthetic survival inputs. No clinical-validity or independent external-validation claim is made. The one-case public-reference segmentation agreement remains an agreement result, not independent validation. Official OS field definitions, approved clinical prediction use, model training-case overlap evidence, and any permitted clinical workflow integration remain outside this engineering freeze.

Git source changes for this closeout are limited to the isolated launcher/setup helpers, Home/Research presentation safeguards, the demo guide and this closeout record. The existing untracked `data/` directory was retained and excluded from Git. No model, patient data, runtime database, credential, or individual prediction is included in the source delivery.
