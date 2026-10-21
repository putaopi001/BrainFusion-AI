# BrainFusion-AI Release Candidate 2026-10-21.1

## Candidate identity

- Version: `BF-RC-20261021.1` (`rc-20261021-1` image tags).
- Source: `E:\BrainFusion-AI`, based on Git HEAD `d1bc7a0251d6ea03538d517f890bc20cbf63c048` plus its pre-existing working-tree changes and this RC Compose file.
- The C worktree supplied for comparison resolves to `C:\Users\mechrevo\.codex\worktrees\1924\BrainFusion-AI` (the path without `\.codex` does not exist). It remains untouched.
- Recoverable source-state snapshot: `C:\Users\mechrevo\AppData\Local\Temp\brainfusion-rc-source-snapshots-20261021-192342`. It contains each tree's HEAD/status, tracked-change patch, and untracked source files. The large `data/` tree and non-source caches were excluded; no DICOM, model weights, database, or runtime logs were copied.

## C/E integration decision

Both worktrees have the same HEAD but different dirty states: E has 387 changed paths, C has 20, with 9 overlapping paths. The overlapping paths are `.gitignore`, `backend/app/api/cases.py`, `backend/app/api/predict.py`, `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/models/report.py`, `backend/requirements-core.txt`, `frontend/src/views/CaseDetail.vue`, and `frontend/src/views/Report.vue`. The RC uses the E versions for these files because E has the fuller current schema/API integration and its PACS conversion, persistence, Docker and UI flows have existing targeted and live validation evidence.

C's 11 unique paths provide an alternate DICOM/PACS/task implementation (`dicom_pacs.py`, `dicom_*` models/services, a focused service test, and `DicomSeriesViewer.vue`). These overlap in responsibility with E's current `/pacs` API, conversion registry/jobs, PACS panel and Cornerstone viewer, but use a separate schema and task contract. They were not overlaid into the candidate; the original C worktree and its snapshot preserve them for later review. No unresolved textual merge markers remain in the selected candidate.

No original working-tree edits were discarded. E has additional untracked data and runtime-adjacent paths; they remain in place and are not included in the Docker build context.

## Build and isolation

- RC Compose: `docker-compose.rc.yml`; standalone configuration, not merged with the formal Compose project.
- RC backend/frontend containers: `brainfusion-rc-20261021-backend` / `brainfusion-rc-20261021-frontend`.
- Ports: `127.0.0.1:18104` / `127.0.0.1:18184`.
- Images: `brainfusion-rc-backend:rc-20261021-1` / `brainfusion-rc-frontend:rc-20261021-1`.
- Image IDs: backend `sha256:b14a640a2a5811ac5a980da8349a7a2d0d972150b342035f99a503c061459ce2`; frontend `sha256:4c6f389300d1900f32d1d7ec5eeba6cd721acdebf0370537f3ad358e560d4bfb`.
- RC Compose SHA-256: `96D64B0A9E2EB004BD84F30CC84489C689C718F818AA5C3B48A898724969F740`.
- Writable runtime and empty SQLite DB: `E:\BrainFusion-Runtime\release-candidate\brainfusion-rc-20261021\runtime`.
- Independent local auth and PACS config: `...\config`; empty dataset, research and PACS-derived directories are separately mounted read-only. PACS config is not copied from the formal runtime, the RC PACS target is deliberately unavailable, pixel reads are false, import candidates are empty, and AI bridge is false.
- The existing validated SegResNet weights are mounted read-only from the existing model directory. No Orthanc volume is mounted into RC.
- Both images built successfully. Vite emitted only its existing large-chunk and codec-module browser-compatibility warnings. Both RC containers reached healthy status. The RC backend was restarted once; its isolated DB, mask, analysis and report remained available afterward.

## Validation

- FastAPI root and OpenAPI: HTTP 200; 68 paths.
- Vue frontend: HTTP 200; headless Edge loaded `/case/1`, showed the isolated test case in analyzed state, and reported no page errors or failed requests.
- Core workflow: created an RC-only synthetic case, uploaded the existing four-sequence WAW-GliomAI engineering sample, and ran the official MONAI BraTS SegResNet through the RC analysis API. Inference succeeded on CPU in 16.35 s, with no fallback. Model revision `370f7f9d062745fbac445e7fe6d6616d35df04ec`; checkpoint SHA-256 `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`.
- Result persistence: mask exists at `runtime\uploads\case_1\f01f37f194ae4290ba51cb53e9aeebab\prediction.nii.gz`, shape 240×240×155, labels 0–3. WT/TC/ET = 6.284/3.374/0.008 mL. Analysis state is `succeeded`; report ID 1 references the same analysis run ID. Analysis, mask and report remained after an isolated backend restart.
- Case and task APIs responded for the isolated case; analysis history contained the successful run. Report and case detail endpoints returned the persisted current result.
- PACS fail-closed check: RC `/pacs/status` reported `read_available=false`, `import_available=false`, `dicom_view_available=false`, `pixel_read_enabled=false`, `ai_bridge_available=false`; `/pacs/studies` returned 503 and import-candidate count was zero. The RC does not connect to the Stage7 or formal Orthanc.
- Orthanc: Stage7 remains on `127.0.0.1:18142` with its independent volume. This turn reconfirmed the service responds with 401 without credentials. The existing Stage7 validation record documents authenticated `/system` success and empty REST/QIDO results. The stored credential value did not authenticate when reused as Basic credentials in this turn; the container, config, and volume were not changed.
- Targeted pytest: `test_pacs_runtime_layer.py` and `test_private_runtime_preflight.py` passed, 7 tests total. Six analysis/report/conversion/storage test files could not be collected because the existing project Conda environment lacks `pydicom`; the separate pytest launcher environment lacks the project dependencies, and the RC image has no pytest. No dependency was installed. Existing E-tree records contain prior 81-test M2 and 694-test backend regressions; these are historical evidence, not a rerun against this RC build.
- UPENN DICOM was not imported or used for inference. Its privacy, sequence identity and registration human-review gates remain closed.

## Deployment boundary

Formal `brainfusion-backend` and `brainfusion-frontend` remain exited on their original image IDs and original ports 18100/18180. Their runtime database and mounts were not used. No formal migration, container replacement, PACS import, pixel read or AI gate change was performed. This is an isolated engineering RC, not a clinical or production release approval.
