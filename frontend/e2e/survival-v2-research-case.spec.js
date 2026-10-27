import { expect, request, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'

const apiBase = process.env.BRAINFUSION_API_URL
const username = process.env.BRAINFUSION_TEST_USERNAME
const password = process.env.BRAINFUSION_TEST_PASSWORD
const evidencePath = process.env.BRAINFUSION_LIVE_RESULT_PATH
const MODEL_ID = 'ucsf-pdgm-clinical-cox-research'
const COHORT = 'UCSF-PDGM-v5-IDH-wildtype-GBM'

test('UCSF V2 artifact serves synthetic and opt-in RESEARCH_CASE predictions through real API and Vue', async ({ page }) => {
  test.setTimeout(60000)
  test.skip(process.env.BRAINFUSION_SURVIVAL_V2_LIVE_E2E !== '1', 'Opt-in isolated UCSF V2 artifact integration only')
  expect(apiBase).toBeTruthy(); expect(username).toBeTruthy(); expect(password).toBeTruthy(); expect(evidencePath).toBeTruthy()
  const baseApi = apiBase.replace(/\/$/, '')
  const predictionResponses = []
  page.on('response', async response => {
    if (response.url().startsWith(`${baseApi}/api/survival/predict`)) {
      predictionResponses.push({ status: response.status(), body: await response.json() })
    }
  })
  // Only unrelated legacy panels are synthetic fixtures. Survival endpoints remain live.
  await page.route('**/research/summary', route => route.fulfill({ json: { code: 200, data: {
    branch_models: {}, fusion: { validation_topsis: { weights: [0.5, 0.5], test: { auc: 0, balanced_accuracy: 0, brier: 0 } } },
    audit: { cohort_patients: 0 }, split_sizes: { train: 0, validation: 0, test: 0 },
    federated: { rounds: 0, local_steps: 0, methods: {} },
  } } }))
  await page.route('**/research/patients/*', route => route.fulfill({ json: { code: 200, data: {
    source_patient_id: 'SYNTHETIC-UI-FIXTURE', clinical_input: { age: 50, female: false },
    reference_label: null, probabilities: {}, disclaimer: 'Synthetic UI fixture only.',
  } } }))

  const statusResponse = await page.context().request.get(`${baseApi}/api/survival/status`)
  expect(statusResponse.status()).toBe(200)
  const status = (await statusResponse.json()).data
  expect(status.supported_prediction_scopes).toContain('SYNTHETIC_TEST')
  expect(status.supported_prediction_scopes).toContain('RESEARCH_CASE')
  const modelResponse = await page.context().request.get(`${baseApi}/api/survival/models`)
  expect(modelResponse.status()).toBe(200)
  const models = (await modelResponse.json()).data.models
  expect(models).toHaveLength(1)
  const model = models[0]
  expect(model.model_id).toBe(MODEL_ID)
  expect(model.model_version).toBe('2.0.0')
  expect(model.training.n).toBe(367)
  expect(model.training.events).toBe(223)
  expect(model.validation.external_validation).toBe(false)
  expect(model.validation.candidate_comparison.selected_candidate).toBe('age_sex_ridge')

  await page.goto('/research')
  await expect(page.getByText('同一患者级外层划分的预设模型比较')).toBeVisible()
  await expect(page.getByText('保留用于 V2')).toBeVisible()
  await page.getByRole('textbox', { name: '评价本地账户' }).fill(username)
  await page.getByRole('textbox', { name: '评价账户密码' }).fill(password)
  await page.getByRole('button', { name: '登录本地复核账户' }).click()
  await expect(page.getByText(/本地身份：Synthetic research test doctor（doctor）/)).toBeVisible()

  async function checkActualPrediction(scope) {
    const before = predictionResponses.length
    const buttonName = scope === 'SYNTHETIC_TEST' ? '运行合成研究示例' : '运行 RESEARCH_CASE 研究输入'
    await page.getByRole('button', { name: buttonName }).click()
    await expect.poll(() => predictionResponses.length).toBe(before + 1)
    const response = predictionResponses.at(-1)
    expect(response.status).toBe(200)
    const result = response.body.data
    expect(result.model_id).toBe(MODEL_ID)
    expect(result.model_version).toBe('2.0.0')
    expect(result.input_scope).toBe(scope)
    expect(result.individual_prediction_saved).toBe(false)
    expect(Number.isFinite(result.relative_risk) && result.relative_risk > 0).toBe(true)
    const points = result.survival_curve
    expect(points.map(point => point.time)).toEqual([365, 730, 1095])
    const probabilities = points.map(point => point.survival_probability)
    expect(probabilities.every(value => Number.isFinite(value) && value >= 0 && value <= 1)).toBe(true)
    expect(probabilities[0] >= probabilities[1] && probabilities[1] >= probabilities[2]).toBe(true)
    await expect(page.getByText(new RegExp(`模型 ${MODEL_ID} / 2\\.0\\.0`))).toBeVisible()
    await expect(page.getByRole('img', { name: `${scope} 生存曲线` }).locator('polyline')).toHaveAttribute('points', /,/)
    for (const year of [1, 2, 3]) await expect(page.getByText(`${year} 年（${year * 365} 天）`)).toBeVisible()
    return result
  }

  const synthetic = await checkActualPrediction('SYNTHETIC_TEST')
  await page.locator('.survival-input-scope-select .el-select__wrapper').click()
  await page.getByRole('option', { name: 'RESEARCH_CASE' }).click()
  await expect(page.getByText(/服务无法独立核验队列成员身份/)).toBeVisible()
  await page.getByText('我已在本地核验该输入属于所选 UCSF-PDGM 研究队列，并确认已获研究授权').click()
  await page.getByRole('spinbutton', { name: '研究输入年龄（年）' }).fill('63')
  await page.locator('.survival-ucsf-sex-select .el-select__wrapper').click()
  await page.getByRole('option', { name: 'F', exact: true }).click()
  const research = await checkActualPrediction('RESEARCH_CASE')
  expect(research.research_cohort).toBe(COHORT)
  expect(research.cohort_attestation).toBe('RESEARCHER_ASSERTED_NOT_INDEPENDENTLY_VERIFIED')

  const cookies = await page.context().cookies(baseApi)
  const cookieHeader = cookies.map(cookie => `${cookie.name}=${cookie.value}`).join('; ')
  const origin = page.url().split('/research')[0]
  const session = await page.context().request.get(`${baseApi}/local-auth/session`, {
    headers: { Cookie: cookieHeader, Origin: origin },
  })
  expect(session.status()).toBe(200)
  const csrf = (await session.json()).data.csrf
  const invalid = await page.context().request.post(`${baseApi}/api/survival/predict`, {
    headers: { Cookie: cookieHeader, Origin: origin, 'X-BF-CSRF': csrf },
    data: { declared_use_scope: 'RESEARCH_CASE', research_cohort: 'UPENN-GBM', model_id: MODEL_ID,
      clinical: { age_years: 63, sex: 'F' }, requested_times_days: [365] },
  })
  expect(invalid.status()).toBe(422)
  const anonymousRequest = await request.newContext()
  const noAuth = await anonymousRequest.post(`${baseApi}/api/survival/predict`, {
    data: { declared_use_scope: 'RESEARCH_CASE', research_cohort: COHORT, model_id: MODEL_ID,
      clinical: { age_years: 63, sex: 'F' }, requested_times_days: [365] },
  })
  expect(noAuth.status()).toBe(401)
  await anonymousRequest.dispose()

  const evidence = { status: 'PASS', input_modes: ['SYNTHETIC_TEST', 'RESEARCH_CASE'],
    model: { model_id: model.model_id, model_version: model.model_version, training_n: model.training.n,
      events: model.training.events, selected_candidate: model.validation.candidate_comparison.selected_candidate },
    predictions: [synthetic, research], rejected_wrong_cohort_status: invalid.status(),
    rejected_unauthenticated_status: noAuth.status(), patient_identifier_used: false,
    prediction_persisted: false, external_validation: false }
  mkdirSync(dirname(evidencePath), { recursive: true })
  writeFileSync(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
})
