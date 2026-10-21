import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.env.BRAINFUSION_RUN_ROOT
if (!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw Error('Unique nightly root required')
const output = `${root}/delivery-guides-browser-final`
await fs.mkdir(output)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
const result = { status: 'running', checks: [], errors: [] }
page.on('pageerror', e => result.errors.push(e.message))
try {
  const request = await page.request.get('http://127.0.0.1:8012/research/cases/17/features')
  assert.equal(request.status(), 200)
  const job = (await request.json()).data
  assert.equal(job.id, 'c913b7963dbe4d9e8014ea6487069946')
  assert.equal(job.result.versions.python, '3.11.17')
  assert.equal(job.clinical_input.age, 57)
  assert.equal(job.clinical_input.female, false)
  await page.goto('http://127.0.0.1:5179/cases')
  await page.getByRole('button', { name: '创建病例', exact: true }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.waitFor()
  assert((await dialog.innerText()).includes('患者姓名'))
  assert((await dialog.innerText()).includes('病例描述'))
  assert.equal(await dialog.locator('.el-select').count(), 1, 'Current dialog has sex selection, not an existing-patient selector')
  await dialog.locator('.el-dialog__body').waitFor({ state: 'visible' })
  await dialog.screenshot({ path: `${output}/case-create-dialog.png`, animations: 'disabled' })
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
  result.checks.push('Actual create dialog matches guide: patient name/age/sex/description; no advertised existing-patient control, no create POST')
  await page.goto('http://127.0.0.1:5179/research?case_id=17')
  await page.locator('.automatic-result').waitFor()
  await page.locator('.automatic-result').scrollIntoViewIfNeeded()
  assert.equal(await page.locator('.feature-state').getAttribute('data-job-id'), job.id)
  assert((await page.locator('body').innerText()).includes(job.analysis_run_id))
  await page.screenshot({ path: `${output}/saved-research.png`, fullPage: true })
  result.checks.push('Current runtime still displays saved supported-worker task/input/version; no extraction, inference, or clinical edit')
  assert.deepEqual(result.errors, [])
  result.status = 'passed'
} catch (error) {
  result.status = 'failed'; result.error = String(error)
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  throw error
} finally {
  await fs.writeFile(`${output}/validation.json`, JSON.stringify(result, null, 2))
  await browser.close()
}
console.log(JSON.stringify(result))
