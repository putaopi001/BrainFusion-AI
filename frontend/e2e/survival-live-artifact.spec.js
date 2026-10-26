import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const apiBase = process.env.BRAINFUSION_API_URL
const username = process.env.BRAINFUSION_TEST_USERNAME
const password = process.env.BRAINFUSION_TEST_PASSWORD
const evidencePath = process.env.BRAINFUSION_LIVE_RESULT_PATH

test('live Cox artifacts drive real API and Vue predictions (opt-in, synthetic only)', async ({ page }) => {
  test.skip(process.env.BRAINFUSION_SURVIVAL_LIVE_E2E !== '1', 'Opt-in isolated artifact integration only')
  expect(apiBase).toBeTruthy()
  expect(username).toBeTruthy()
  expect(password).toBeTruthy()
  expect(evidencePath).toBeTruthy()

  const baseApi = apiBase.replace(/\/$/, '')
  const predictionResponses = []
  page.on('response', async response => {
    if (response.url().startsWith(`${baseApi}/api/survival/predict`)) {
      predictionResponses.push({ status: response.status(), body: await response.json() })
    }
  })

  // The page also renders unrelated legacy research panels. Keep those routes
  // synthetic; all survival status/models/predict and auth requests are live.
  await page.route('**/research/summary', route => route.fulfill({ json: { code: 200, data: {
    branch_models: {}, fusion: { validation_topsis: { weights: [0.5, 0.5], test: { auc: 0, balanced_accuracy: 0, brier: 0 } } },
    audit: { cohort_patients: 0 }, split_sizes: { train: 0, validation: 0, test: 0 },
    federated: { rounds: 0, local_steps: 0, methods: {} },
  } } }))
  await page.route('**/research/patients/*', route => route.fulfill({ json: { code: 200, data: {
    source_patient_id: 'SYNTHETIC', clinical_input: { age: 50, female: false }, reference_label: null,
    probabilities: {}, disclaimer: 'Synthetic UI fixture only.',
  } } }))

  const apiResponse = await page.context().request.get(`${baseApi}/api/survival/status`)
  expect(apiResponse.status()).toBe(200)
  const status = (await apiResponse.json()).data
  expect(status.status).toBe('RESEARCH_ONLY')
  expect(status.official_endpoint_status).toBe('BLOCKED_BY_DATA_DICTIONARY')
  const modelsResponse = await page.context().request.get(`${baseApi}/api/survival/models`)
  expect(modelsResponse.status()).toBe(200)
  const models = (await modelsResponse.json()).data.models
  expect(models.map(model => model.model_version)).toEqual([
    '1.0.1-research-only', '1.0.0-research-only',
  ])

  await page.goto('/research')
  await expect(page.getByText('研究模型演示仅限 SYNTHETIC_TEST')).toBeVisible()
  await page.getByRole('textbox', { name: '评价本地账户' }).fill(username)
  await page.getByRole('textbox', { name: '评价账户密码' }).fill(password)
  await page.getByRole('button', { name: '登录本地复核账户' }).click()
  await expect(page.getByText(/本地身份：Synthetic research test doctor（doctor）/)).toBeVisible()

  async function runAndCheck(modelId) {
    if (modelId === 'upenn-clinical-captk-fusion-cox-research') {
      await page.locator('.survival-model-select .el-select__wrapper').click()
      await page.getByRole('option', { name: '临床 + CaPTk 四特征 Cox' }).click()
    }
    const count = predictionResponses.length
    await page.getByRole('button', { name: '运行合成研究示例' }).click()
    await expect.poll(() => predictionResponses.length).toBe(count + 1)
    const response = predictionResponses.at(-1)
    expect(response.status).toBe(200)
    const data = response.body.data
    expect(data.model_id).toBe(modelId)
    expect(data.input_scope).toBe('SYNTHETIC_TEST')
    expect(data.research_only).toBe(true)
    expect(data.individual_prediction_saved).toBe(false)
    const curve = data.survival_curve
    expect(curve.map(point => point.time)).toEqual([365, 730, 1095])
    const probabilities = curve.map(point => point.survival_probability)
    expect(probabilities.every(value => Number.isFinite(value) && value >= 0 && value <= 1)).toBe(true)
    expect(probabilities[0] >= probabilities[1] && probabilities[1] >= probabilities[2]).toBe(true)
    await expect(page.getByText(new RegExp(`模型 ${modelId} / ${data.model_version}`))).toBeVisible()
    await expect(page.getByText(/相对风险指数：/)).toBeVisible()
    await expect(page.getByRole('img', { name: '合成生存曲线' }).locator('polyline')).toHaveAttribute('points', /,/)
    await expect(page.getByText('1 年（365 天）')).toBeVisible()
    await expect(page.getByText('2 年（730 天）')).toBeVisible()
    await expect(page.getByText('3 年（1095 天）')).toBeVisible()
    return data
  }

  const clinical = await runAndCheck('upenn-clinical-cox-research')
  const fusion = await runAndCheck('upenn-clinical-captk-fusion-cox-research')

  const badTimesInput = page.getByRole('textbox', { name: '合成生存时间点（天）' })
  await badTimesInput.fill('1095,365')
  await page.getByRole('button', { name: '运行合成研究示例' }).click()
  await expect(page.getByText('时间点请按天数从小到大填写。')).toBeVisible()
  expect(predictionResponses).toHaveLength(2)

  const cookies = await page.context().cookies(baseApi)
  const cookieHeader = cookies.map(cookie => `${cookie.name}=${cookie.value}`).join('; ')
  const sessionResponse = await page.context().request.get(`${baseApi}/local-auth/session`, {
    headers: { Cookie: cookieHeader, Origin: page.url().split('/research')[0] },
  })
  expect(sessionResponse.status()).toBe(200)
  const csrf = (await sessionResponse.json()).data.csrf
  expect(csrf).toBeTruthy()
  const authHeaders = {
    Cookie: cookieHeader, Origin: page.url().split('/research')[0], 'X-BF-CSRF': csrf,
  }
  const fusionInput = {
    declared_use_scope: 'SYNTHETIC_TEST', model_id: 'upenn-clinical-captk-fusion-cox-research',
    clinical: { age_years: 63, gender: 'F', IDH1: 'Wildtype', GTR_over90percent: 'N' },
    requested_times_days: [365, 730, 1095],
  }
  const invalids = []
  for (const [name, body] of [
    ['missing_captk_feature', { ...fusionInput, radiomics: {
      T1GD_ET_Intensity_Mean: 1, FLAIR_ED_Intensity_Mean: 2, T2_ED_Intensity_Mean: 3,
    } }],
    ['unsupported_category', { ...fusionInput, radiomics: {
      T1GD_ET_Intensity_Mean: 1, FLAIR_ED_Intensity_Mean: 2, T2_ED_Intensity_Mean: 3, T1_NC_Intensity_Mean: 4,
    }, clinical: { ...fusionInput.clinical, IDH1: 'UNKNOWN' } }],
    ['invalid_time_order', { ...fusionInput, radiomics: {
      T1GD_ET_Intensity_Mean: 1, FLAIR_ED_Intensity_Mean: 2, T2_ED_Intensity_Mean: 3, T1_NC_Intensity_Mean: 4,
    }, requested_times_days: [1095, 365] }],
  ]) {
    const result = await page.context().request.post(`${baseApi}/api/survival/predict`, {
      headers: authHeaders,
      data: body,
    })
    expect(result.status()).toBe(422)
    invalids.push({ case: name, status: result.status(), rejected: true,
      error_detail: (await result.json().catch(() => ({}))).detail ?? null })
  }

  const evidence = {
    status: 'PASS', api_origin: baseApi, browser_origin: page.url().split('/research')[0],
    synthetic_only: true, patient_id_used: false, prediction_persisted: false,
    models: [clinical, fusion], invalid_input_checks: invalids,
    endpoint_status: status.official_endpoint_status,
  }
  mkdirSync(dirname(evidencePath), { recursive: true })
  writeFileSync(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
})
