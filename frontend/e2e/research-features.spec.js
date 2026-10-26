import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

test('renders a saved radiomics result and downloads the CSV in the browser', async ({ page }) => {
  const fixturePath = process.env.BRAINFUSION_FEATURE_FIXTURE
  test.skip(!fixturePath, 'Set BRAINFUSION_FEATURE_FIXTURE to a sanitized saved result fixture')
  const fixture = JSON.parse(readFileSync(fixturePath, 'utf8'))
  const caseId = fixture.case_id
  const result = fixture.result

  await page.route('**/research/summary', route => route.fulfill({ json: { code: 200, data: {
    branch_models: {}, fusion: { validation_topsis: {
      weights: [0.5, 0.5], test: { auc: 0, balanced_accuracy: 0, brier: 0 },
    } },
    audit: { cohort_patients: 0 }, split_sizes: { train: 0, validation: 0, test: 0 },
    federated: { rounds: 0, local_steps: 0, methods: {} },
  } } }))
  await page.route('**/research/patients/*', route => route.fulfill({ json: { code: 200, data: {
    source_patient_id: 'SYNTHETIC', clinical_input: { age: 50, female: false }, reference_label: null,
    probabilities: {}, disclaimer: 'Synthetic UI fixture only.',
  } } }))
  await page.route('**/cases/?*', route => route.fulfill({ json: { code: 200, data: [{ id: caseId, patient_name: 'SYNTHETIC' }] } }))
  await page.route(`**/research/cases/${caseId}/clinical-input`, route => route.fulfill({ json: { code: 200, data: {
    patient_id: 'SYNTHETIC', source: 'associated_patient', version: 'synthetic-clinical-v1',
    age: 50, female: false, available: true,
  } } }))
  await page.route(`**/research/cases/${caseId}/features`, route => route.fulfill({ json: { code: 200, data: {
    id: fixture.job_id, case_id: caseId, analysis_run_id: fixture.analysis_run_id,
    research_run_id: fixture.research_run_id, state: 'succeeded', stale: false, cache_hit: true,
    clinical_input: { age: 50, female: false }, result,
  } } }))

  const csv = fixture.csv
  await page.route(`**/research/cases/${caseId}/features.csv`, route => route.fulfill({
    status: 200, contentType: 'text/csv; charset=utf-8', headers: { 'content-disposition': `attachment; filename=brainfusion-case-${caseId}-features.csv` }, body: csv,
  }))

  await page.goto(`/research?case_id=${caseId}`)
  await expect(page.locator('.radiomics-result')).toBeVisible()
  await expect(page.locator('.radiomics-result .el-table__body tr')).toHaveCount(Object.keys(result.selected_features).length)
  await expect(page.getByText(`特征记录 ${result.feature_record_id || '历史文件任务'}`)).toBeVisible()

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: '导出当前特征 CSV' }).click(),
  ])
  expect(download.suggestedFilename()).toBe(`brainfusion-case-${caseId}-features.csv`)
  const path = await download.path()
  expect(path).toBeTruthy()
  expect(readFileSync(path, 'utf8')).toBe(csv)
})

test('research survival panel submits only a synthetic Cox example and renders API response', async ({ page }) => {
  let submitted
  await page.route('**/api/survival/status', route => route.fulfill({ json: { code: 200, data: {
    available: true, status: 'RESEARCH_ONLY', research_only: true,
    official_endpoint_validated: false, endpoint_status: 'RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS',
    official_endpoint_status: 'BLOCKED_BY_DATA_DICTIONARY',
  } } }))
  await page.route('**/api/survival/models', route => route.fulfill({ json: { code: 200, data: { models: [
    { model_id: 'upenn-clinical-cox-research', model_version: 'clinical-test-only', research_only: true,
      endpoint_status: 'RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS',
      validation: { mean_fold_harrell_c_index: 0.6462 } },
    { model_id: 'upenn-clinical-captk-fusion-cox-research', model_version: 'fusion-test-only', research_only: true,
      endpoint_status: 'RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS',
      validation: { fusion_mean_fold_c_index: 0.6510 },
      radiomics: { required_inputs: ['T1GD_ET_Intensity_Mean', 'FLAIR_ED_Intensity_Mean', 'T2_ED_Intensity_Mean', 'T1_NC_Intensity_Mean'] } },
  ] } } }))
  await page.route('**/api/survival/predict', async route => {
    submitted = route.request().postDataJSON()
    await route.fulfill({ json: { code: 200, data: {
      model_id: submitted.model_id, model_version: 'test-only', research_only: true,
      input_scope: 'SYNTHETIC_TEST', relative_risk: 1.1, time_unit: 'days',
      survival_curve: [
        { time: 365, time_unit: 'days', survival_probability: 0.8 },
        { time: 730, time_unit: 'days', survival_probability: 0.6 },
        { time: 1095, time_unit: 'days', survival_probability: 0.3 },
      ], limitations: ['Synthetic fixture only.'],
    } } })
  })
  await page.route('**/local-auth/session', route => route.fulfill({ json: { code: 200, data: {
    user: { id: 'synthetic-reviewer', role: 'doctor', display_name: 'SYNTHETIC reviewer' },
    csrf: 's'.repeat(32), configured: true,
  } } }))
  await page.route('**/research/survival/status', route => route.fulfill({ json: { code: 200, data: {
    research_status: 'BLOCKED_BY_DATA', reason: 'Synthetic endpoint test only.',
    software: { endpoint_validation: 'available', kaplan_meier: 'synthetic_engineering_only',
      cox_ph: 'synthetic_engineering_only', random_survival_forest: 'not_available' },
  } } }))
  await page.route('**/research/summary', route => route.fulfill({ json: { code: 200, data: {
    branch_models: {}, fusion: { validation_topsis: { weights: [0.5, 0.5], test: { auc: 0, balanced_accuracy: 0, brier: 0 } } },
    audit: { cohort_patients: 0 }, split_sizes: { train: 0, validation: 0, test: 0 },
    federated: { rounds: 0, local_steps: 0, methods: {} },
  } } }))
  await page.route('**/research/patients/*', route => route.fulfill({ json: { code: 200, data: {
    source_patient_id: 'SYNTHETIC', clinical_input: { age: 50, female: false }, reference_label: null,
    probabilities: {}, disclaimer: 'Synthetic UI fixture only.',
  } } }))
  await page.route('**/cases/?*', route => route.fulfill({ json: { code: 200, data: [] } }))

  await page.goto('/research')
  await expect(page.getByText('研究模型演示仅限 SYNTHETIC_TEST')).toBeVisible()
  await page.getByRole('button', { name: '运行合成研究示例' }).click()
  await expect(page.getByText(/相对风险指数：1\.1000/)).toBeVisible()
  await expect(page.getByText('80.0%', { exact: true })).toBeVisible()
  expect(submitted.declared_use_scope).toBe('SYNTHETIC_TEST')
  expect(submitted.model_id).toBe('upenn-clinical-cox-research')
  expect(submitted).not.toHaveProperty('patient_id')
  expect(submitted.clinical.age_years).toBe(63)

  await page.locator('.survival-model-select .el-select__wrapper').click()
  await page.getByRole('option', { name: '临床 + CaPTk 四特征 Cox' }).click()
  await page.getByRole('button', { name: '运行合成研究示例' }).click()
  await expect(page.getByText('60.0%', { exact: true })).toBeVisible()
  await expect(page.getByRole('img', { name: '合成生存曲线' })).toBeVisible()
  await expect(page.getByRole('img', { name: '合成生存曲线' }).locator('polyline')).toHaveAttribute('points', /,/)
  expect(submitted.model_id).toBe('upenn-clinical-captk-fusion-cox-research')
  expect(Object.keys(submitted.radiomics).sort()).toEqual([
    'FLAIR_ED_Intensity_Mean', 'T1GD_ET_Intensity_Mean', 'T1_NC_Intensity_Mean', 'T2_ED_Intensity_Mean',
  ])
  expect(submitted).not.toHaveProperty('patient_id')
})
