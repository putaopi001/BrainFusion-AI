import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
const output = 'E:/BrainFusion-Runtime/results/stage6'
const evidence = JSON.parse(await fs.readFile(`${output}/automatic_validation.json`, 'utf8'))
const webBase = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5179'
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = [], samples = []
page.on('pageerror', error => errors.push(error.message))
try {
  await page.goto(`${webBase}/analysis?case_id=${evidence.samples[1].case_id}`)
  await page.getByRole('button', { name: '自动掩膜特征研究', exact: true }).click()
  await page.waitForURL(`**/research?case_id=${evidence.samples[1].case_id}`)
  await page.getByText('当前病例：自动掩膜特征研究', { exact: true }).waitFor()
  for (const sample of evidence.samples) {
    await page.locator('.case-feature-select').click()
    const responsePromise = page.waitForResponse(r => r.url().endsWith(`/research/cases/${sample.case_id}/features`) && r.request().method() === 'GET')
    await page.getByRole('option', { name: new RegExp(`^病例 ${sample.case_id} ·`) }).click()
    const response = await responsePromise
    if (response.status() !== 200) throw new Error('Feature read failed')
    const job = (await response.json()).data
    await page.locator('.feature-state').filter({ hasText: job.analysis_run_id }).waitFor()
    const probability = (job.result.probabilities.automatic_mask_radiomics * 100).toFixed(1) + '%'
    await page.locator('.automatic-result').getByText(probability, { exact: true }).first().waitFor()
    samples.push({ case_id: sample.case_id, displayed_probability: probability, job_id: job.id })
  }
  // Submit the actual form with an explicit age/sex; the existing case is unchanged.
  await page.locator('.el-input-number input').fill('50')
  await page.locator('.el-input-number input').press('Tab')
  const responsePromise = page.waitForResponse(r => r.url().endsWith(`/research/cases/${evidence.samples.at(-1).case_id}/features`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: '提取自动掩膜特征', exact: true }).click()
  const started = await responsePromise
  if (started.status() !== 202) throw new Error('Feature form submission failed')
  const submitted = (await started.json()).data
  await page.waitForFunction(id => {
    const state = document.querySelector('.feature-state')
    return state?.dataset.jobId === id && state.textContent.includes('succeeded')
  }, submitted.id, { timeout: 200000 })
  await page.getByText('工程迁移实验：', { exact: false }).waitFor()
  await page.locator('.automatic-result').scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${output}/automatic-features-page.png`, fullPage: true })
  await page.reload()
  await page.getByText('当前病例：自动掩膜特征研究', { exact: true }).waitFor()
  await page.locator('.case-feature-select').click()
  await page.getByRole('option', { name: new RegExp(`^病例 ${evidence.samples.at(-1).case_id} ·`) }).click()
  await page.locator('.feature-state').filter({ hasText: 'succeeded' }).waitFor()
  if (errors.length) throw new Error(errors.join('\n'))
  await fs.writeFile(`${output}/browser_validation.json`, JSON.stringify({ status: 'passed', samples, analysis_to_research_link: 'passed', actual_submission: 'passed', polling: 'passed', refresh_persistence: 'passed', errors }, null, 2))
  console.log('Five automatic feature results, actual form submission, polling and refresh PASS')
} catch (error) {
  await page.screenshot({ path: `${output}/automatic-features-failure.png`, fullPage: true })
  await fs.writeFile(`${output}/browser_validation.json`, JSON.stringify({ status: 'failed', samples, error: String(error), errors }, null, 2))
  throw error
} finally { await browser.close() }
