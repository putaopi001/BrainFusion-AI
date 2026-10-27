# UCSF-PDGM Reference-Radiomics Fusion V2

## Scope and source

This isolated research branch expands the existing ten-case feasibility pilot. The source is the `MedOtter/UCSF-PDGM` dataset pinned to revision `e9372219cf1cd2fdd52260cd45f7514b4aa7638e`; files are checked against the revision's LFS SHA-256 and sizes. The source dataset card identifies the source collection and CC BY 4.0 terms. The clinical cohort is independently rebuilt from the locally verified TCIA UCSF-PDGM v5 CSV and glossary.

- TCIA collection: <https://www.cancerimagingarchive.net/collection/ucsf-pdgm/>
- Pinned mirror revision: <https://huggingface.co/datasets/MedOtter/UCSF-PDGM/tree/e9372219cf1cd2fdd52260cd45f7514b4aa7638e>
- TCIA BraTS-2021 mapping/analysis result: <https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/>

The fixed v5 baseline cohort contract currently rebuilds 367 IDH-wildtype GBM patients (223 deaths, 144 alive/censored) after excluding one baseline GBM row with invalid OS. The pinned file listing provides all five required NIfTIs and LFS metadata for all 367 candidates (T1, T1c, T2, FLAIR, reference tumor segmentation); expected transfer is approximately 4.59 GB. A nonempty BraTS21 mapping is present for 269 of these v5 cohort rows. The official BraTS analysis-result page separately lists 298 subjects for its UCSF-PDGM v1 excerpt; those totals use different release/record definitions and are not treated as an exact patient crosswalk.

## Reproducible local workflow

Run from the `codex/ucsf-fusion-study-v2` worktree. Patient-level data and features stay under `E:\BrainFusion-Data\UCSF-PDGM\fusion-v2`; aggregate evidence stays under `E:\BrainFusion-Runtime\research-edition\results`.

```powershell
$dataRoot = 'E:\BrainFusion-Data\UCSF-PDGM\fusion-v2'
& 'E:\BrainFusion-AI\.conda\brainfusion\python.exe' -u backend/scripts/inventory_ucsf_fusion_cohort_v2.py --output-root $dataRoot
& 'E:\BrainFusion-AI\.conda\brainfusion\python.exe' -u backend/scripts/download_ucsf_fusion_cohort_v2.py --output-root $dataRoot --inventory "$dataRoot\cohort-file-inventory.json" --workers 3 --batch-size 10
& 'E:\BrainFusion-AI\.conda\brainfusion\python.exe' backend/scripts/extract_ucsf_reference_radiomics_v2.py --data-root $dataRoot
& 'E:\BrainFusion-AI\.conda\brainfusion\python.exe' backend/scripts/compare_ucsf_reference_radiomics_fusion_v2.py --features "$dataRoot\reference-radiomics-selected20-private.csv" --output 'E:\BrainFusion-Runtime\research-edition\results\ucsf-pdgm-fusion-v2-20261027'
```

The downloader resumes from verified files and partial `.part` files, makes bounded retries, and refuses to overwrite a completed file that differs from the pin. The feature extractor reuses the already verified ten-case features, then extracts the fixed 20-feature WAW-IDH-derived BrainFusion panel from UCSF reference masks using the existing isolated PyRadiomics worker. Official reference labels `0/1/2/4` are recoded only in derived copies to BrainFusion `0/1/2/3`; source NIfTIs remain unchanged. Four MRI sequences, reference-mask shape, affine, spacing/direction, label domain, and per-file hashes are checked before extraction. No SegResNet inference is run by this workflow.

The fusion comparison uses the same event-stratified five-fold patient split for age/sex Ridge Cox, radiomics Ridge/Elastic-Net Cox, and clinical+radiomics Ridge/Elastic-Net Cox. The feature panel is fixed without UCSF survival-outcome selection. Imputation and standardization are fit within each training fold; penalties are fixed in advance, with no tuning. Outputs include OOF Harrell C-index, fold IPCW Brier scores at 365/730/1095 days, supported-grid IBS, calibration-in-the-large summaries, fold variability, and paired OOF C-index bootstrap differences. The patient-level feature/endpoint table is never written to Git.

## Evidence and interpretation

Aggregate cohort, feature QC, model comparison, and the ten-case reference-versus-prediction-mask sensitivity results are written to the versioned Runtime evidence directory. Patient-level inventory, images, derived label maps, masks, and feature rows remain in the protected Data directory. Model results are exploratory internal cross-validation only. Diagnosis-to-MRI interval is not recorded in the reviewed v5 contract, so the MRI landmark and diagnosis-origin OS are not fully aligned. The fixed feature panel was selected in an unrelated WAW IDH task and is not UCSF-survival validated.

BraTS21 overlap is tracked through the v5 `BraTS21 ID` field. The MONAI checkpoint used in the prior ten-case segmentation pilot has no complete training-subject manifest available; its overlap with UCSF cannot be excluded. Consequently, neither the prior segmentation metrics nor this reference-mask radiomics study is independent external validation. No clinical individual-risk predictions are generated.

## V2 run results (2026-10-27)

- All 367 prespecified baseline patients had all five pinned files available in the fixed revision; all 1,835 files were downloaded/reused and SHA-256 verified (4,594,335,385 bytes). Ten already verified pilot cases were reused without redownloading.
- All 367 patients had four MRI sequences and a reference mask that passed the extractor's geometry/label checks. The fixed 20-feature panel is complete and finite for 367/367 patients (7,340/7,340 values); no extraction failures. The private feature table remains under `E:\BrainFusion-Data\UCSF-PDGM\fusion-v2`.
- Matched v5 endpoint count: N=367, 223 events, 144 censored. Official OS is days from initial diagnosis to last clinical follow-up, with event=dead; the diagnostic-MRI prediction landmark remains imperfect because diagnosis-to-MRI interval is unavailable.

| Same-cohort model | OOF Harrell C-index | Mean fold IBS (180–1095 days) | Mean IPCW Brier at 365 / 730 / 1095 days |
|---|---:|---:|---|
| Clinical age + sex Ridge Cox | 0.6320 | 0.1999 | 0.2076 / 0.2132 / 0.1691 |
| 20-feature radiomics Ridge Cox | 0.5365 | 0.2210 | 0.2297 / 0.2417 / 0.1833 |
| 20-feature radiomics Elastic-Net Cox | 0.5372 | 0.2195 | 0.2292 / 0.2390 / 0.1811 |
| Clinical + radiomics Ridge Cox | 0.6180 | 0.2098 | 0.2088 / 0.2320 / 0.1820 |
| Clinical + radiomics Elastic-Net Cox | 0.6202 | 0.2082 | 0.2081 / 0.2292 / 0.1793 |

The outer evaluation used one row per patient, the same seeded event-stratified five folds for every model (seed 20261027), fold-local median imputation and model-internal training-fold scaling, fixed penalties, and no hyperparameter search. Paired bootstrap OOF C-index differences versus the matched clinical model were -0.0932 (95% CI -0.1578 to -0.0306) for radiomics Ridge, -0.0956 (-0.1566 to -0.0358) for radiomics Elastic-Net, -0.0150 (-0.0493 to 0.0173) for fused Ridge, and -0.0119 (-0.0390 to 0.0141) for fused Elastic-Net. The fusion intervals cross zero and neither fusion model improves the clinical baseline, so the clinical model remains the baseline choice; this is not a claim that age/sex is a clinical prediction tool.

The existing ten-case reference-versus-prediction-mask feature sensitivity result is reused without inference rerun: label-2 edema-related features (5 features) had median absolute relative difference 0.0629 and median feature-wise across-case Spearman 0.7455; label-3 enhancing-related features (15) had 0.2489 and 0.9515, respectively. Among the three lowest-recall cases, mean WT/TC/ET recall was 0.6659/0.6063/0.4603. This is descriptive feature sensitivity on ten pilot cases, not independent validation.

Aggregate evidence is in `E:\BrainFusion-Runtime\research-edition\results\ucsf-pdgm-fusion-v2-20261027` and the companion `ucsf-pdgm-reference-radiomics-v2-20261027` directory. The patient-level expanded cohort manifest, images, masks, and feature table remain only in protected Data. No segmentation inference was run in this V2 expansion. The panel originated in an unrelated WAW IDH task, known BraTS overlap is present, and the prior checkpoint's training-case manifest is unavailable; results are exploratory internal CV and public-reference comparisons only, not independent external validation. No individual risk predictions were generated.
