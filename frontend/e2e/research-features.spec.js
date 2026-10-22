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
