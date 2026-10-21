import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'

const output = 'E:/BrainFusion-Runtime/results/stage4'
const webBase = process.env.BRAINFUSION_WEB_URL || 'http://127.0.0.1:5178'
await fs.mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = []
page.on('pageerror', e => errors.push(e.message))
const samples = []
try {
  await page.goto(`${webBase}/research`)
  await page.getByRole('heading', { name: 'IDH 与融合研究' }).waitFor()
  await page.getByText('同构模拟联邦', { exact: true }).waitFor()
  await page.getByText('源患者 13；', { exact: false }).waitFor()
  for (const id of ['4', '13', '16', '17', '19']) {
    await page.locator('.el-select').first().click()
    const responsePromise = page.waitForResponse(r => r.url().endsWith(`/research/patients/${id}`))
    // The initial selection is 13; selecting a different first patient triggers every request.
    await page.getByText(`数据集患者 ${id}`, { exact: true }).last().click()
    const response = await responsePromise
    if (response.status() !== 200) throw new Error(`Patient ${id} failed`)
    const item = (await response.json()).data
    await page.getByText(`源患者 ${id}；`, { exact: false }).waitFor()
    const radio = (item.probabilities.reference_mask_radiomics * 100).toFixed(1) + '%'
    await page.getByText(radio, { exact: true }).first().waitFor()
    samples.push({ source_patient_id: id, displayed_radiomics: radio, run_id: item.run_id })
  }
  await page.getByText('参考标签 缺失', { exact: false }).waitFor()
  const clinicalResponse = page.waitForResponse(r => r.url().endsWith('/research/clinical') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '计算临床概率', exact: true }).click()
  const clinical = await clinicalResponse
  if (clinical.status() !== 200) throw new Error('Clinical input form failed')
  await page.getByText('仅年龄与性别的研究基线概率', { exact: false }).waitFor()
  await page.screenshot({ path: `${output}/research-page.png`, fullPage: true })
  await page.locator('.content').evaluate(element => { element.scrollTop = 0 })
  await page.screenshot({ path: `${output}/research-summary.png`, fullPage: true })
  if (errors.length) throw new Error(errors.join('\n'))
  await fs.writeFile(`${output}/browser_validation.json`, JSON.stringify({ status: 'passed', samples, clinical_input_form: 'passed', method_tables: 'passed', errors }, null, 2))
  console.log('Research page, five public-data patients, probability display and clinical form PASS')
} catch (e) {
  await page.screenshot({ path: `${output}/research-failure.png`, fullPage: true })
  await fs.writeFile(`${output}/browser_validation.json`, JSON.stringify({ status: 'failed', error: String(e), samples, errors }, null, 2))
  throw e
} finally {
  await browser.close()
}
