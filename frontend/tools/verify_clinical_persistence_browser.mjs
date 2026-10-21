import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.env.BRAINFUSION_EVIDENCE_DIR
const validationName = process.env.BRAINFUSION_VALIDATION_NAME || 'clinical-persistence'
assert(/^[a-z0-9-]+$/.test(validationName))
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use nightly evidence')
const prior = process.env.BRAINFUSION_PRIOR_EVIDENCE_DIR || root
if (!prior?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use recorded nightly input evidence')
const before = JSON.parse(await fs.readFile(`${prior}/clinical-browser/validation.json`, 'utf8'))
assert.equal(before.status, 'passed')
const web = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const api = process.env.BRAINFUSION_API_URL || 'http://127.0.0.1:8012'
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const result = { status: 'in_progress', case_id: before.case_id, checks: [] }
try {
  const input = (await (await page.request.get(`${api}/research/cases/${before.case_id}/clinical-input`)).json()).data
  const job = (await (await page.request.get(`${api}/research/cases/${before.case_id}/features`)).json()).data
  assert.equal(input.version, before.after.input.version)
  assert.equal(input.age, before.after.input.age)
  assert.equal(job.id, before.after.job.id)
  assert.equal(job.clinical_input_version, input.version)
  assert.deepEqual(job.result.probabilities, before.after.job.result.probabilities)
  assert.equal(job.stale, false)
  await page.goto(`${web}/research?case_id=${before.case_id}`)
  await page.locator(`.feature-state[data-job-id="${job.id}"]`).waitFor()
  assert.equal(Number(await page.locator('.case-age input').inputValue()), input.age)
  await page.locator('.automatic-result').waitFor()
  await page.screenshot({ path: `${root}/${validationName}.png`, fullPage: true })
  result.checks.push('actual backend restart preserves saved case input/version, feature identity/probabilities and browser state')
  // Read existing persisted reports after schema migration and service restart.
  for (const id of [11, 12, 13, 14, 15, before.case_id]) {
    const report = await page.request.get(`${api}/reports/${id}`)
    assert.equal(report.status(), 200)
  }
  result.checks.push('six real current reports remain readable after additive schema migration/restart')
  await page.route(`**/research/cases/${before.case_id}/features`, route => route.fulfill({ status: 503, json: { detail: 'Injected feature service failure' } }))
  await page.getByRole('button', { name: '刷新任务', exact: true }).click()
  await page.getByText('Injected feature service failure', { exact: true }).waitFor()
  assert.equal(await page.locator('.automatic-result').count(), 0)
  await page.unroute(`**/research/cases/${before.case_id}/features`)
  await page.getByRole('button', { name: '刷新任务', exact: true }).click()
  await page.locator('.automatic-result').waitFor()
  result.checks.push('injected feature GET failure clears old probabilities; manual refresh recovers the same task')
  result.input = input; result.job_id = job.id; result.status = 'passed'
  console.log(JSON.stringify(result))
} catch (e) { result.status = 'failed'; result.error = String(e); throw e }
finally { await fs.writeFile(`${root}/${validationName}.json`, JSON.stringify(result, null, 2)); await browser.close() }
