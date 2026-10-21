import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import path from 'node:path'

const caseId = process.env.BRAINFUSION_CASE_ID
const webBase = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const outputPath = process.env.BRAINFUSION_EVIDENCE_JSON
if (!/^\d+$/.test(caseId || '') || !outputPath) {
  throw new Error('Set BRAINFUSION_CASE_ID and BRAINFUSION_EVIDENCE_JSON')
}

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1365, height: 900 } })
const errors = []
const responses = []
let writeRequests = 0
page.on('pageerror', () => errors.push('pageerror'))
page.on('request', request => {
  if (!['GET', 'HEAD'].includes(request.method())) writeRequests += 1
})
page.on('response', response => {
  const url = new URL(response.url())
  if (url.pathname.includes(`/research/cases/${caseId}/`)) {
    responses.push({ endpoint: url.pathname.split('/').slice(-2).join('/'), status: response.status() })
  }
})

try {
  await page.goto(`${webBase}/research?case_id=${caseId}`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'IDH 与融合研究' }).waitFor({ timeout: 15000 })
  await page.locator('.feature-state').waitFor({ timeout: 15000 })
  const state = await page.locator('.feature-state').innerText()
  const selectedFeatureSummary = await page.getByText(/选中特征 \d+ 个/).count()
  const resultRows = await page.locator('.automatic-result tbody tr').count()
  const unsavedInputWarning = await page.getByText(
    '研究输入已修改但尚未保存；旧概率暂不显示。保存后需按新版本重新计算。',
    { exact: true },
  ).count() > 0
  const result = {
    page: 'Research',
    case_id: Number(caseId),
    feature_state_contains_succeeded: state.includes('succeeded'),
    selected_feature_summary_present: selectedFeatureSummary > 0,
    automatic_result_row_count: resultRows,
    unsaved_clinical_input_warning: unsavedInputWarning,
    api_responses: responses,
    page_error_count: errors.length,
    write_requests_observed: writeRequests,
    screenshot_saved: false,
  }
  const expectedFeatureEndpoint = `${caseId}/features`
  const apiResponsesPassed = responses.length >= 3 &&
    responses.every(({ status }) => status === 200) &&
    responses.some(({ endpoint }) => endpoint === expectedFeatureEndpoint)
  result.api_responses_passed = apiResponsesPassed
  if (!result.feature_state_contains_succeeded || !result.selected_feature_summary_present ||
      resultRows < 1 || unsavedInputWarning || !apiResponsesPassed || errors.length || writeRequests !== 0) {
    throw new Error('Live research feature persistence check failed')
  }
  await fs.mkdir(path.dirname(outputPath), { recursive: true })
  await fs.writeFile(outputPath, JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result))
} finally {
  await browser.close()
}
