# UCSF-PDGM final directed morphology and feature-stability analysis

**Status:** exploratory, same-cohort internal patient-level cross-validation. This analysis adds a pre-specified reference-mask morphology comparison and reuses the completed reference-radiomics and ten-case mask-sensitivity outputs. It did not download imaging, extract radiomics again, or run SegResNet.

## Cohort, endpoint, and validation

The pinned UCSF-PDGM v5 IDH-wildtype glioblastoma cohort contains 367 unique baseline patients (223 events, 144 censored). OS is recorded in days from initial diagnosis to last clinical follow-up; the official glossary defines dead/alive status. The reviewed source does not provide a reliable diagnosis-to-MRI interval. The MRI prediction landmark therefore cannot be aligned exactly with the OS time origin. Results below are exploratory associations and are not an independently validated prognostic model.

The morphology models and the age-plus-sex comparator used the same 367 patients and the existing event-stratified five-fold patient-level split (seed `20261027`). The Ridge Cox penalty was fixed at `alpha=0.01`; there was no hyperparameter search. Standardization was fitted within each training fold. C-index uncertainty is a 1,000-replicate patient bootstrap of pooled out-of-fold predictions. Brier and IBS uncertainty is the standard deviation across the five outer folds. IPCW scores use the previously implemented censoring-aware evaluator. No outcome-based feature selection was performed.

## Pre-specified morphology panel

The verified BraTS-format reference labels were interpreted as label 1 necrotic/non-enhancing core, label 2 edema/infiltrative region, and label 4 enhancing tumor. WT = 1+2+4, TC = 1+4, and ET = 4. Physical volumes use voxel counts multiplied by the verified reference-grid spacing product and divided by 1,000 to report mL. The five model inputs were log(1+WT mL), log(1+TC mL), log(1+ET mL), edema/WT, and ET/TC. Raw WT/TC/ET volumes are retained in the local protected derived table for descriptive reporting. There were no zero WT/TC denominators or morphology exclusions.

In this cohort, median (IQR) WT, TC, and ET volumes were 88.37 (45.88–130.39), 26.98 (11.79–49.90), and 18.94 (9.10–31.51) mL. Median edema/WT was 0.646 (0.494–0.780), and ET/TC was 0.713 (0.599–0.862).

## Model comparison

All candidate results are from the same 367-patient cohort and fixed outer folds. Values in Brier and IBS columns are mean ± fold SD; C-index intervals are patient-bootstrap 95% CIs. Paired ΔC is candidate minus the matched age-plus-sex clinical baseline, with paired patient-bootstrap 95% CI.

| Model | OOF Harrell C (95% CI) | IBS, 180–1095 d | Brier 365 d | Brier 730 d | Brier 1095 d | Paired ΔC vs clinical (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Clinical age + sex Ridge Cox | 0.6320 (0.5913–0.6710) | 0.1999 ± 0.0201 | 0.2076 ± 0.0254 | 0.2132 ± 0.0213 | 0.1691 ± 0.0530 | — |
| Reference morphology Ridge Cox | 0.5511 (0.5060–0.5951) | 0.2112 ± 0.0211 | 0.2255 ± 0.0192 | 0.2242 ± 0.0229 | 0.1679 ± 0.0591 | −0.0804 (−0.1380 to −0.0219) |
| Clinical + reference morphology Ridge Cox | 0.6273 (0.5878–0.6670) | 0.2015 ± 0.0173 | 0.2059 ± 0.0255 | 0.2167 ± 0.0157 | 0.1690 ± 0.0530 | −0.0053 (−0.0250 to 0.0122) |
| Fixed-20 radiomics Ridge Cox | 0.5365 (0.4905–0.5802) | 0.2210 ± 0.0189 | 0.2297 ± 0.0141 | 0.2417 ± 0.0191 | 0.1833 ± 0.0551 | −0.0932 (−0.1578 to −0.0306) |
| Fixed-20 radiomics Elastic-Net Cox | 0.5372 (0.4913–0.5847) | 0.2195 ± 0.0186 | 0.2292 ± 0.0144 | 0.2390 ± 0.0197 | 0.1811 ± 0.0546 | −0.0956 (−0.1566 to −0.0358) |
| Clinical + fixed-20 radiomics Ridge Cox | 0.6180 (0.5813–0.6568) | 0.2098 ± 0.0171 | 0.2088 ± 0.0302 | 0.2320 ± 0.0137 | 0.1820 ± 0.0490 | −0.0150 (−0.0493 to 0.0173) |
| Clinical + fixed-20 radiomics Elastic-Net Cox | 0.6202 (0.5785–0.6596) | 0.2082 ± 0.0168 | 0.2081 ± 0.0296 | 0.2292 ± 0.0139 | 0.1793 ± 0.0484 | −0.0119 (−0.0390 to 0.0141) |

**Conclusion:** Neither the five pre-specified morphology variables nor the pre-existing fixed-20 radiomics panel demonstrated a stable improvement over the age-plus-sex baseline. Clinical plus morphology had a small negative C-index difference whose interval includes zero; its IBS was also slightly worse than baseline. The radiomics-only models performed below the clinical comparator. Retain age-plus-sex Cox as the benchmark; do not start further model search on this cohort under this task.

## Fixed-20 feature quality and extraction consistency

The reused fixed panel contained 20/20 finite features for all 367 cases (7,340 finite cells, no missing cells). All cases had the same recorded image geometry signature and the same fixed extraction contract. Input scaling was whole-volume min-max to [0,1]; the prior audit notes that this scaling is inferred from source statistics rather than explicitly specified by the publisher. PyRadiomics used Original images, `binWidth=0.02`, no normalization, no resampling, distance 1, and `force2D=false`. The panel was selected in a separate WAW IDH task and was not selected on UCSF survival outcomes.

Feature scales are heterogeneous by construction: observed values across the panel ranged from 0.0183 to 84,287 in their feature-specific units. A descriptive Tukey 1.5×IQR check flagged 116 feature-cells out of 7,340; none were removed or winsorized. Of 190 feature pairs, 39 had absolute Spearman rho ≥0.85. Correlations and outlier flags were used only for QC, not feature selection. Full per-feature medians, IQRs, ranges, skewness, and correlation pairs are in the aggregate evidence JSON.

## Existing ten-case reference-versus-prediction mask sensitivity

Previously extracted features from the ten paired reference and existing prediction masks were reanalyzed; no inference or feature extraction was rerun. Per case, the median absolute relative difference across label-2 edema features had median 7.31% (IQR 5.59–11.97%); for label-3 enhancing features it was 26.77% (IQR 16.39–32.74%). Across-case feature-wise Spearman correlation medians from the existing pilot summary were 0.745 (label 2; 5 features) and 0.952 (label 3; 15 features). In this ten-case pilot, case-level enhancing-feature error was descriptively inversely associated with ET recall (Spearman rho −0.867, n=10); edema-feature error vs WT recall rho was −0.479 (n=10). These are descriptive pilot associations, not inferential effects.

Among the three lowest-recall cases, mean WT/TC/ET recall was 0.666/0.606/0.460; minima across all ten were 0.629/0.386/0.379. This small selected pilot is not an independent test set and does not establish survival-feature validity.

## Figure and evidence files

Aggregate-only results, model table, two reproducible Python figures, figure QA reports, and checksums are under `E:\BrainFusion-Runtime\research-edition\results\ucsf-pdgm-last-directed-20261027-v1`. The patient-level morphology table and original feature rows remain under the access-controlled `E:\BrainFusion-Data\UCSF-PDGM\fusion-v2` tree and are not in this repository. Figures show aggregate results only.

## Reproduction

Use the already installed research Python environment; do not overwrite an existing evidence version. Run the analysis script with a new, empty versioned output path:

```powershell
$py = 'E:\BrainFusion-Runtime\envs\main-env-rebuild-20261018T2150\Scripts\python.exe'
& $py backend/scripts/analyze_ucsf_morphology_final.py `
  --data-root E:\BrainFusion-Data\UCSF-PDGM\fusion-v2 `
  --feature-table E:\BrainFusion-Data\UCSF-PDGM\fusion-v2\reference-radiomics-selected20-private.csv `
  --output-private E:\BrainFusion-Data\UCSF-PDGM\fusion-v2\derived\reference-morphology-<new-version> `
  --output-runtime E:\BrainFusion-Runtime\research-edition\results\ucsf-pdgm-morphology-<new-version>
```

The fixed comparison helper reuses seed `20261027`, five folds, `alpha=0.01`, and the prior OOF/IPCW/bootstrap implementation. Plot regeneration uses `backend/scripts/plot_ucsf_fusion_morphology_final.py` with the existing aggregate comparison and morphology JSON as inputs; use a new output folder or the script's explicit replace option only for the current generated figure bundle.

## Limits and interpretation

- TCIA v5 OS starts at initial diagnosis; diagnosis-to-MRI time is not available in the reviewed table, so landmark alignment is unresolved.
- The analysis uses one public UCSF cohort with internal patient-level CV. It is not independent external validation and does not establish clinical utility.
- Known BraTS overlap and unknown SegResNet training-case overlap remain separate from this reference-mask morphology analysis.
- The fixed-20 feature panel has external-task provenance and its source preprocessing includes an inferred image-intensity scale.
- Ten mask-paired cases are too few to establish general segmentation-derived feature reliability.
- No additional feature search, model search, individual risk prediction, or model deployment was performed.
