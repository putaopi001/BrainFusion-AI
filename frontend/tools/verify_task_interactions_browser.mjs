// Controlled transport states exercise the actual Vue pages. Real case results are read-only.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'

const root = process.env.BRAINFUSION_EVIDENCE_DIR
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use unique nightly evidence')
const web = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const api = process.env.BRAINFUSION_API_URL || 'http://127.0.0.1:8012'
const id = Number(process.env.BRAINFUSION_CASE_ID || 17)
await fs.mkdir(root, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const evidence = { status: 'in_progress', case_id: id, checks: [], page_errors: [], scope: 'Injected queued/running/failure/conflict transport responses, not new successful model inference; real persisted case result read-only regression.' }
page.on('pageerror', e => evidence.page_errors.push(e.message))
const get = async path => {
  const r = await page.request.get(api + path)
  assert.equal(r.status(), 200, await r.text())
  return (await r.json()).data
}
const present = async text => page.getByText(text, { exact: false }).first().waitFor()
try {
  const realRun = await get(`/analysis/${id}`)
  const realJob = await get(`/research/cases/${id}/features`)
  assert.equal(realRun.state, 'succeeded'); assert.equal(realJob.state, 'succeeded'); assert.equal(realJob.stale, false)
  let run = null, analysisPosts = 0, analysisUnavailable = false, held = null, holdNext = false
  const queuedRun = { ...realRun, id: 'CONTROLLED-browser-analysis', state: 'queued', result: null, error: null }
  await page.route(`**/analysis/${id}`, async route => {
    if (route.request().method() === 'POST') {
      ++analysisPosts
      run = { ...queuedRun, id: analysisPosts === 1 ? queuedRun.id : 'CONTROLLED-browser-retry-analysis' }
      return route.fulfill({ status: analysisPosts === 1 ? 409 : 202, json: analysisPosts === 1 ? { detail: 'An analysis is active; wait for it to finish' } : { data: run } })
    }
    if (holdNext) { holdNext = false; held = route; return }
    return route.fulfill({ status: analysisUnavailable ? 503 : 200, json: analysisUnavailable ? { detail: 'Controlled analysis status unavailable' } : { data: run } })
  })
  await page.goto(`${web}/analysis?case_id=${id}`)
  await present('任务状态：未启动')
  await page.getByRole('button', { name: '运行分割模型', exact: true }).click()
  await present('任务状态：排队中')
  assert.equal(analysisPosts, 1)
  assert(await page.getByRole('button', { name: '运行分割模型', exact: true }).isDisabled())
  await page.reload(); await page.locator(`[data-run-id="${queuedRun.id}"]`).waitFor()
  run = { ...run, state: 'running' }; await present('任务状态：分析中')
  evidence.checks.push('analysis conflict resumes the existing task; reload preserves identity; queued/running disable duplicate submission')
  run = { ...run, state: 'failed', error: 'Controlled worker failure: Empty sequence: t2f' }
  await present(run.error)
  await page.getByRole('button', { name: '重试分割模型', exact: true }).click()
  await page.locator('[data-run-id="CONTROLLED-browser-retry-analysis"]').waitFor()
  assert.equal(analysisPosts, 2)
  run = { ...run, state: 'failed', error: 'Controlled retry failed; original failure remains traceable' }
  await present(run.error)
  evidence.checks.push('analysis failure is visible, retry uses a new task identity, no success card is fabricated')
  // Same-case responses can arrive out of order, including an earlier successful result.
  holdNext = true
  await page.getByRole('button', { name: '刷新任务', exact: true }).click()
  await page.waitForFunction(() => true)
  await new Promise(resolve => setTimeout(resolve, 100))
  assert(held)
  await page.getByRole('button', { name: '刷新任务', exact: true }).click()
  await present(run.error)
  await held.fulfill({ status: 200, json: { data: realRun } }); held = null
  await new Promise(resolve => setTimeout(resolve, 200))
  assert.equal(await page.getByText(`模型：${realRun.result.model}`, { exact: true }).count(), 0)
  await page.screenshot({ path: `${root}/analysis-failed-retry.png`, fullPage: true })
  evidence.checks.push('late successful analysis response cannot overwrite a newer failed status')
  run = realRun
  await page.getByRole('button', { name: '刷新任务', exact: true }).click(); await present(`模型：${realRun.result.model}`)
  analysisUnavailable = true
  await page.getByRole('button', { name: '刷新任务', exact: true }).click(); await present('Controlled analysis status unavailable')
  assert.equal(await page.getByText(`模型：${realRun.result.model}`, { exact: true }).count(), 0)
  assert(await page.getByRole('button', { name: '运行分割模型', exact: true }).isDisabled())
  analysisUnavailable = false
  await page.getByRole('button', { name: '刷新任务', exact: true }).click(); await present(`模型：${realRun.result.model}`)
  assert.equal(await page.getByText('Controlled analysis status unavailable', { exact: true }).count(), 0)
  evidence.checks.push('analysis status failure clears old success and blocks unsafe submission; manual recovery clears the old error')
  await page.unroute(`**/analysis/${id}`)

  let job = null, featurePosts = 0, featureUnavailable = false
  const queuedJob = { ...realJob, id: 'CONTROLLED-browser-feature', state: 'queued', result: null, error: null, stale: false }
  await page.route(`**/research/cases/${id}/features`, async route => {
    if (route.request().method() === 'POST') {
      ++featurePosts
      job = { ...queuedJob, id: featurePosts === 1 ? queuedJob.id : 'CONTROLLED-browser-retry-feature' }
      return route.fulfill({ status: featurePosts === 1 ? 409 : 202, json: featurePosts === 1 ? { detail: 'A feature extraction is active for this analysis' } : { data: job } })
    }
    return route.fulfill({ status: featureUnavailable ? 503 : 200, json: featureUnavailable ? { detail: 'Controlled feature status unavailable' } : { data: job } })
  })
  await page.goto(`${web}/research?case_id=${id}`)
  const extract = page.getByRole('button', { name: '提取自动掩膜特征', exact: true })
  await page.locator('.case-age input').waitFor()
  await extract.click(); await page.locator(`[data-job-id="${queuedJob.id}"]`).waitFor()
  assert.equal(featurePosts, 1); assert(await extract.isDisabled())
  await page.reload(); await page.locator(`[data-job-id="${queuedJob.id}"]`).waitFor()
  job = { ...job, state: 'running' }; await present('特征任务：running')
  job = { ...job, state: 'failed', error: 'Controlled feature failure: Image and mask geometry differ' }
  await present(job.error)
  await extract.click(); await page.locator('[data-job-id="CONTROLLED-browser-retry-feature"]').waitFor()
  assert.equal(featurePosts, 2)
  job = { ...job, state: 'failed', error: 'Controlled retry failure retained' }; await present(job.error)
  assert.equal(await page.locator('.automatic-result').count(), 0)
  await page.screenshot({ path: `${root}/features-failed-retry.png`, fullPage: true })
  evidence.checks.push('feature conflict/reload resumes same queued/running task; failure/retry uses new identity without displaying probabilities')
  job = realJob
  await page.getByRole('button', { name: '刷新任务', exact: true }).click(); await page.locator('.automatic-result').waitFor()
  featureUnavailable = true
  await page.getByRole('button', { name: '刷新任务', exact: true }).click(); await present('Controlled feature status unavailable')
  assert.equal(await page.locator('.automatic-result').count(), 0); assert(await extract.isDisabled())
  featureUnavailable = false
  await page.getByRole('button', { name: '刷新任务', exact: true }).click(); await page.locator('.automatic-result').waitFor()
  assert.equal(await page.getByText('Controlled feature status unavailable', { exact: true }).count(), 0)
  await page.unroute(`**/research/cases/${id}/features`)
  await page.reload(); await page.locator(`[data-job-id="${realJob.id}"]`).waitFor(); await page.locator('.automatic-result').waitFor()
  assert.deepEqual((await get(`/research/cases/${id}/features`)).result.probabilities, realJob.result.probabilities)
  assert.equal((await get(`/analysis/${id}`)).id, realRun.id)
  await page.screenshot({ path: `${root}/real-result-restored.png`, fullPage: true })
  evidence.checks.push('feature failure/recovery clears old error; actual stored case17 task and probabilities remain unchanged')
  assert.deepEqual(evidence.page_errors, [])
  evidence.real_analysis_id = realRun.id; evidence.real_feature_id = realJob.id; evidence.status = 'passed'
  console.log(JSON.stringify(evidence))
} catch (e) { evidence.status = 'failed'; evidence.error = String(e); await page.screenshot({ path: `${root}/failed.png`, fullPage: true }); throw e }
finally { await fs.writeFile(`${root}/validation.json`, JSON.stringify(evidence, null, 2)); await browser.close() }
