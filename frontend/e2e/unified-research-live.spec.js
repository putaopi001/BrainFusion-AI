import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const apiBase = process.env.BRAINFUSION_API_URL
const username = process.env.BRAINFUSION_TEST_USERNAME
const password = process.env.BRAINFUSION_TEST_PASSWORD
const evidencePath = process.env.BRAINFUSION_UNIFIED_RESULT_PATH

test('isolated archive pixels and UCSF research model are live end to end', async ({ page }) => {
  test.skip(process.env.BRAINFUSION_UNIFIED_LIVE_E2E !== '1', 'Opt-in isolated research demo only')
  test.setTimeout(120000)
  expect(apiBase).toBeTruthy()
  expect(username).toBeTruthy()
  expect(password).toBeTruthy()
  expect(evidencePath).toBeTruthy()
  const baseApi = apiBase.replace(/\/$/, '')
  const archiveFrameResponses = []
  const predictionResponses = []
  page.on('response', async response => {
    const url = response.url()
    if (url.startsWith(`${baseApi}/pacs/archive/`) && url.includes('/frames/')) {
      archiveFrameResponses.push({ status: response.status(), contentType: response.headers()['content-type'] || '' })
    }
    if (url.startsWith(`${baseApi}/api/survival/predict`)) {
      predictionResponses.push({ status: response.status(), body: await response.json() })
    }
  })

  const statusResponse = await page.request.get(`${baseApi}/pacs/status`)
  expect(statusResponse.status()).toBe(200)
  const pacs = (await statusResponse.json()).data
  expect(pacs.state).toBe('ready')
  expect(pacs.read_available).toBe(true)
  expect(pacs.dicom_view_available).toBe(true)
  expect(pacs.import_available).toBe(false)
  expect(pacs.ai_bridge_available).toBe(false)
  const studiesResponse = await page.request.get(`${baseApi}/pacs/studies?limit=100`)
  expect(studiesResponse.status()).toBe(200)
  const studies = (await studiesResponse.json()).data.items
  expect(studies.length).toBeGreaterThan(0)

  let selected = null
  for (const study of studies) {
    const response = await page.request.get(`${baseApi}/pacs/studies/${encodeURIComponent(study.study_uid)}/series?limit=100`)
    if (response.status() !== 200) continue
    const series = (await response.json()).data.items
    const candidate = series.find(row => row.modality === 'MR' && Number(row.instance_count) >= 2)
    if (candidate) { selected = { study, series: candidate }; break }
  }
  expect(selected).not.toBeNull()

  await page.goto('/dicom-archive')
  const studyRow = page.getByRole('row').filter({ hasText: selected.study.study_uid })
  await studyRow.getByRole('button', { name: '查看序列' }).click()
  const seriesRow = page.getByRole('row').filter({ hasText: selected.series.series_uid })
  await seriesRow.getByRole('button', { name: '打开真实像素' }).click()
  await expect(page.locator('.cs-viewer[data-source="dicom"][data-state="ready"]')).toBeVisible({ timeout: 90000 })
  expect(archiveFrameResponses.length).toBeGreaterThan(0)
  expect(archiveFrameResponses.every(row => row.status === 200 && row.contentType.includes('multipart/related'))).toBe(true)
  await expect(page.getByText('隔离序列阅片')).toBeVisible()

  await page.goto('/research')
  await page.getByRole('textbox', { name: '评价本地账户' }).fill(username)
  await page.getByRole('textbox', { name: '评价账户密码' }).fill(password)
  await page.getByRole('button', { name: '登录本地复核账户' }).click()
  await expect(page.getByText(/本地身份：.*（doctor）/)).toBeVisible()
  const modelsResponse = await page.request.get(`${baseApi}/api/survival/models`)
  expect(modelsResponse.status()).toBe(200)
  const models = (await modelsResponse.json()).data.models
  const ucsf = models.find(model => model.model_id === 'ucsf-pdgm-clinical-cox-research')
  expect(ucsf).toBeTruthy()
  expect(ucsf.dataset.id).toBe('UCSF-PDGM')
  expect(ucsf.training.n).toBe(367)
  await page.locator('.survival-model-select .el-select__wrapper').click()
  await page.getByRole('option', { name: 'UCSF-PDGM GBM 临床 Cox' }).click()
  await page.locator('.survival-predict-inputs .el-select__wrapper').first().click()
  await page.getByRole('option', { name: 'M（合成）' }).click()
  await page.getByRole('button', { name: '运行合成研究示例' }).click()
  await expect.poll(() => predictionResponses.length).toBe(1)
  const prediction = predictionResponses[0]
  expect(prediction.status).toBe(200)
  const result = prediction.body.data
  expect(result.model_id).toBe('ucsf-pdgm-clinical-cox-research')
  expect(result.input_scope).toBe('SYNTHETIC_TEST')
  expect(result.individual_prediction_saved).toBe(false)
  const probabilities = result.survival_curve.map(point => point.survival_probability)
  expect(result.survival_curve.map(point => point.time)).toEqual([365, 730, 1095])
  expect(probabilities.every(value => Number.isFinite(value) && value >= 0 && value <= 1)).toBe(true)
  expect(probabilities[0]).toBeGreaterThanOrEqual(probabilities[1])
  expect(probabilities[1]).toBeGreaterThanOrEqual(probabilities[2])
  await expect(page.getByText(new RegExp(`模型 ucsf-pdgm-clinical-cox-research / ${result.model_version}`))).toBeVisible()
  await expect(page.getByRole('img', { name: '合成生存曲线' }).locator('polyline')).toHaveAttribute('points', /,/)
  await expect(page.getByText('1 年（365 天）')).toBeVisible()
  await expect(page.getByText('2 年（730 天）')).toBeVisible()
  await expect(page.getByText('3 年（1095 天）')).toBeVisible()

  mkdirSync(dirname(evidencePath), { recursive: true })
  writeFileSync(evidencePath, `${JSON.stringify({
    status: 'PASS', synthetic_prediction_only: true, patient_identifiers_recorded: false,
    archive: { state: pacs.state, study_count: studies.length,
      selected_series_instance_count: Number(selected.series.instance_count),
      real_frame_responses: archiveFrameResponses.length, frame_http_statuses: [...new Set(archiveFrameResponses.map(row => row.status))],
      importer_enabled: pacs.import_available, ai_bridge_enabled: pacs.ai_bridge_available },
    model: { id: result.model_id, version: result.model_version, training_n: ucsf.training.n,
      events: ucsf.training.events, censored: ucsf.training.censored, endpoint_status: result.endpoint_status,
      requested_days: result.survival_curve.map(point => point.time), probabilities,
      individual_prediction_saved: result.individual_prediction_saved },
    formal_environment_modified: false,
  }, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
})
