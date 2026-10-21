import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.env.BRAINFUSION_RUN_ROOT
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw Error('Unique E-drive evidence root required')
const output = `${root}/${process.env.BRAINFUSION_ATTEMPT || 'supported-browser'}`
await fs.mkdir(output)
const expected = JSON.parse(await fs.readFile(`${root}/${process.env.BRAINFUSION_COMPLETED_DIRECTORY || 'automatic-supported-complete'}/completed.json`, 'utf8'))[0].job
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
const result = { status: 'running', checks: [], pageErrors: [] }
page.on('pageerror', e => result.pageErrors.push(e.message))
try {
  const response = await page.request.get('http://127.0.0.1:8012/research/cases/17/features')
  assert.equal(response.status(), 200)
  const job = (await response.json()).data
  // A deliberate cache-hit POST updates only the access timestamp; science,
  // provenance, task identity and completion timestamp must remain exact.
  const stable = ({ updated_utc, ...rest }) => rest
  assert.deepEqual(stable(job), stable(expected))
  assert.equal(job.result.versions.python, '3.11.17')
  await page.goto('http://127.0.0.1:5179/research?case_id=17')
  await page.locator('.automatic-result').waitFor()
  await page.locator('.automatic-result').scrollIntoViewIfNeeded()
  const body = await page.locator('body').innerText()
  assert.equal(await page.locator('.feature-state').getAttribute('data-job-id'), job.id, 'Visible task state must bind the current job')
  assert(body.includes(job.analysis_run_id), 'Bound segmentation version must be displayed')
  await page.screenshot({ path: `${output}/research.png`, fullPage: true })
  result.checks.push('Actual browser shows the persisted supported-worker automatic-mask result and bound task/analysis versions; API equals saved result')
  await page.goto('http://127.0.0.1:5179/workstation/17')
  await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(i => i.complete && i.naturalWidth > 0))
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  for (const [key, label] of [['t1c', 'T1c · 增强 T1'], ['t1n', 'T1n · 平扫 T1'], ['t2w', 'T2w · T2'], ['t2f', 'FLAIR']]) {
    await page.locator('.mri-sequence-select').click()
    await page.getByRole('option', { name: label, exact: true }).click()
    await page.waitForFunction(key => {
      const images = [...document.querySelectorAll('.slice-img')], masks = [...document.querySelectorAll('.mask-img')]
      return document.querySelector('.current-sequence')?.dataset.sequence === key && images.length === 3 && masks.length === 3 && images.every(i => i.complete && i.naturalWidth > 0 && new URL(i.src).searchParams.get('sequence') === key) && masks.every(i => i.complete && i.naturalWidth > 0)
    }, key)
    await page.getByRole('option', { name: label, exact: true }).waitFor({ state: 'hidden' })
    await page.screenshot({ path: `${output}/${key}.png`, fullPage: true })
  }
  result.checks.push('Four real MRI sequences and three-view masks rendered after environment migration; no empty-image acceptance')
  await page.goto('http://127.0.0.1:5179/report?case_id=17')
  await page.locator('#report-paper').waitFor()
  assert((await page.locator('#report-paper').innerText()).includes(job.analysis_run_id))
  assert.equal(await page.getByRole('button', { name: '导出 PDF', exact: true }).isEnabled(), true)
  await page.screenshot({ path: `${output}/report.png`, fullPage: true })
  result.checks.push('Unchanged current report/analysis version and PDF entry visible; no PDF re-export or segmentation/training')
  await page.goto('http://127.0.0.1:5179/case/17')
  await page.getByText(job.analysis_run_id, { exact: false }).first().waitFor()
  assert((await page.locator('body').innerText()).includes('公开样本4'))
  await page.screenshot({ path: `${output}/case17.png`, fullPage: true })
  await page.goto('http://127.0.0.1:5179/research?case_id=11')
  await page.locator('.case-clinical-input .el-alert').waitFor()
  await page.locator('.case-clinical-input').scrollIntoViewIfNeeded()
  assert.equal(await page.getByRole('button', { name: '提取自动掩膜特征', exact: true }).isEnabled(), false)
  assert.equal(await page.locator('.automatic-result').count(), 0)
  await page.screenshot({ path: `${output}/unknown-clinical.png`, fullPage: true })
  result.checks.push('Fixed demonstration case detail renders; legacy unknown-clinical case shows warning, disables extraction and shows no fabricated probability')
  assert.deepEqual(result.pageErrors, [])
  result.status = 'passed'
} catch (e) {
  result.status = 'failed'; result.error = String(e)
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  throw e
} finally {
  await fs.writeFile(`${output}/validation.json`, JSON.stringify(result, null, 2))
  await browser.close()
}
console.log(JSON.stringify(result))
