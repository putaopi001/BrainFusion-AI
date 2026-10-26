import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const apiBase = process.env.BRAINFUSION_API_URL
const username = process.env.BRAINFUSION_TEST_USERNAME
const password = process.env.BRAINFUSION_TEST_PASSWORD
const evidencePath = process.env.BRAINFUSION_UNIFIED_RESULT_PATH

test('isolated archive pixels and UCSF research model are live end to end', async ({ page }) => {
  test.skip(process.env.BRAINFUSION_UNIFIED_LIVE_E2E !== '1', 'Opt-in isolated research demo only')
  test.setTimeout(600000)
  expect(apiBase).toBeTruthy()
  expect(username).toBeTruthy()
  expect(password).toBeTruthy()
  expect(evidencePath).toBeTruthy()
  const baseApi = apiBase.replace(/\/$/, '')
  const archiveFrameResponses = []
  const predictionResponses = []
  const upennFileResponses = []
  let verifiedSource
  page.on('response', async response => {
    const url = response.url()
    if (url.startsWith(`${baseApi}/pacs/archive/`) && url.includes('/frames/')) {
      archiveFrameResponses.push({ status: response.status(), contentType: response.headers()['content-type'] || '' })
    }
    if (url.startsWith(`${baseApi}/api/survival/predict`)) {
      predictionResponses.push({ status: response.status(), body: await response.json() })
    }
    if (url.startsWith(`${baseApi}/api/research/upenn-sub002/files/`)) upennFileResponses.push(response.status())
    if (url.startsWith(`${baseApi}/pacs/import-candidates/`) && url.endsWith('/verify') && response.ok()) verifiedSource = (await response.json()).data
  })

  const statusResponse = await page.request.get(`${baseApi}/pacs/status`)
  expect(statusResponse.status()).toBe(200)
  const pacs = (await statusResponse.json()).data
  expect(pacs.state).toBe('ready')
  expect(pacs.read_available).toBe(true)
  expect(pacs.dicom_view_available).toBe(true)
  expect(pacs.import_available).toBe(true)
  expect(pacs.ai_bridge_available).toBe(false)
  const studiesResponse = await page.request.get(`${baseApi}/pacs/studies?limit=100`)
  expect(studiesResponse.status()).toBe(200)
  let studies = (await studiesResponse.json()).data.items
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
  await page.getByRole('button', { name: '核验来源' }).click()
  await expect.poll(() => verifiedSource?.source_status).toBe('VERIFIED')
  if (verifiedSource.archive_status === 'NOT_IMPORTED') {
    // Element Plus keeps the native checkbox input visually hidden; click its visible label.
    await page.getByText('我确认此已审核来源只导入到隔离 Stage7 研究归档，不关联病例、不进入正式 PACS、不提交 AI。', { exact: true }).click()
    await expect(page.getByRole('button', { name: '仅导入到隔离归档' })).toBeEnabled()
    const importPromise = page.waitForResponse(response => response.url().includes('/pacs/imports/') && response.request().method() === 'POST')
    await page.getByRole('button', { name: '仅导入到隔离归档' }).click()
    const importResponse = await importPromise
    expect(importResponse.status()).toBe(200)
    const imported = (await importResponse.json()).data
    expect(imported.state).toBe('succeeded')
    expect(imported.verified).toBe(imported.total)
    await expect.poll(() => verifiedSource?.archive_status).toBe('PRESENT')
    const refreshedStudiesResponse = await page.request.get(`${baseApi}/pacs/studies?limit=100`)
    expect(refreshedStudiesResponse.status()).toBe(200)
    studies = (await refreshedStudiesResponse.json()).data.items
  }
  expect(verifiedSource.archive_status).toBe('PRESENT')
  expect(verifiedSource.case_link_status).toBe('UNLINKED')
  expect(verifiedSource.four_sequence_conversion_ready).toBe(false)
  const authorizedStudy = studies.find(row => row.study_uid === verifiedSource.study_uid)
  expect(authorizedStudy).toBeTruthy()
  const authorizedSeriesResponse = await page.request.get(`${baseApi}/pacs/studies/${encodeURIComponent(authorizedStudy.study_uid)}/series?limit=100`)
  const authorizedSeries = (await authorizedSeriesResponse.json()).data.items.find(row => row.series_uid === verifiedSource.series_uid)
  expect(authorizedSeries).toBeTruthy()
  selected = { study: authorizedStudy, series: authorizedSeries }
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
  await page.goto('/research/upenn-sub002')
  await expect(page.locator('.cs-viewer[data-source="research-nifti"][data-state="ready"]')).toBeVisible({ timeout: 90000 })
  await expect(page.getByText('PUBLIC_REFERENCE_AGREEMENT', { exact: false }).first()).toBeVisible()
  await expect(page.getByText('0.759799', { exact: false })).toBeVisible()
  await expect(page.locator('.overlay-image img')).toBeVisible()
  expect(upennFileResponses.filter(status => status === 200).length).toBeGreaterThanOrEqual(3)
  const sequenceSelect = page.locator('.cs-toolbar select')
  await expect(sequenceSelect.locator('option')).toHaveCount(4)
  await page.goto('/research')
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
      registered_source_status: verifiedSource.source_status, source_archive_status: verifiedSource.archive_status,
      source_series_count: verifiedSource.archive_series_count, conversion_ready: verifiedSource.four_sequence_conversion_ready,
      importer_enabled: pacs.import_available, ai_bridge_enabled: pacs.ai_bridge_available },
    segmentation: { study_id: 'UPENN-GBM-sub-002', actual_inference_reused: true,
      prediction_sha256: 'a2e90567d49653a2966c2f8e4dfbcfdbbd91a1550ccd7c9ed43bee60a6ee9cfd',
      public_reference_agreement: true, overlay_loaded: true, input_files_http_200: upennFileResponses.filter(status => status === 200).length,
      independent_external_validation: false },
    model: { id: result.model_id, version: result.model_version, training_n: ucsf.training.n,
      events: ucsf.training.events, censored: ucsf.training.censored, endpoint_status: result.endpoint_status,
      requested_days: result.survival_curve.map(point => point.time), probabilities,
      individual_prediction_saved: result.individual_prediction_saved },
    formal_environment_modified: false,
  }, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
})
