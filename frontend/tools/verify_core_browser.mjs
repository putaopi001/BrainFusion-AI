import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
const output = 'E:/BrainFusion-Runtime/results/stage3'
await fs.mkdir(output, { recursive: true })
const evidence = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/results/stage2/workflow_validation.json', 'utf8'))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1100 } })
const page = await context.newPage()
const errors = []
page.on('pageerror', e => errors.push(e.message))
const results = []
try {
  for (const sample of evidence.samples) {
    await page.goto(`http://127.0.0.1:5178/case/${sample.case_id}`)
    await page.getByText('真实窗宽窗位', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
    await page.waitForFunction(() => document.querySelectorAll('.mask-img').length > 0 && [...document.querySelectorAll('.mask-img')].every(image => image.complete && image.naturalWidth > 0))
    await page.getByText('真实模型输出，需医生核对。', { exact: true }).waitFor()
    await page.screenshot({ path: `${output}/sample-${sample.sample_id}-viewer.png`, fullPage: true })
    results.push({ sample_id: sample.sample_id, viewing: 'passed' })
  }
  const caseId = evidence.samples[0].case_id
  const current = await (await context.request.get(`http://127.0.0.1:8011/analysis/${caseId}`)).json()
  const confirmation = await context.request.post(`http://127.0.0.1:8011/mri/${caseId}/verify?run_id=${current.data.id}`)
  if (confirmation.status() !== 200) throw new Error('Cannot verify current engineering result')
  await page.goto(`http://127.0.0.1:5178/report?case_id=${caseId}`)
  await page.getByText('已确认当前版本', { exact: false }).waitFor()
  const downloadPromise = page.waitForEvent('download', { timeout: 60000 })
  await page.getByRole('button', { name: '导出 PDF', exact: true }).click()
  const download = await downloadPromise
  await download.saveAs(`${output}/sample-4-report.pdf`)
  const pdf = await fs.readFile(`${output}/sample-4-report.pdf`)
  if (pdf.subarray(0, 5).toString() !== '%PDF-' || pdf.length < 10000) throw new Error('Invalid PDF output')
  await page.screenshot({ path: `${output}/sample-4-report.png`, fullPage: true })
  // Exercise the actual four-file form and polling, with downloaded MRI data.
  await page.goto(`http://127.0.0.1:5178/analysis?case_id=${caseId}`)
  for (const [index, sequence] of ['t1c', 't1n', 't2w', 't2f'].entries()) {
    await page.locator('input[type=file]').nth(index).setInputFiles(`E:/BrainFusion-Data/WAW-GliomAI-v3/sample/images/gliomai_preop_scans_renamed/4/4_0_brain_${sequence}.nii.gz`)
  }
  await page.getByRole('button', { name: '上传四序列', exact: true }).click()
  await page.getByText('任务状态：未启动', { exact: true }).waitFor()
  await page.getByRole('button', { name: '运行分割模型', exact: true }).click()
  await page.getByText('任务状态：完成', { exact: true }).waitFor({ timeout: 120000 })
  await page.goto(`http://127.0.0.1:5178/case/${caseId}`)
  await page.getByText('真实窗宽窗位', { exact: true }).waitFor()
  await page.getByRole('button', { name: '测距', exact: true }).click()
  await page.locator('.image-box').first().scrollIntoViewIfNeeded()
  const box = await page.locator('.image-box').first().boundingBox()
  await page.mouse.move(box.x + box.width * .7, box.y + box.height * .3)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * .3, box.y + box.height * .7, { steps: 10 })
  await page.mouse.up()
  await page.getByRole('button', { name: '保存标注', exact: true }).click()
  await page.getByText('医生标注已保存', { exact: true }).waitFor()
  const annotations = await (await context.request.get(`http://127.0.0.1:8011/mri/${caseId}/annotations`)).json()
  const line = annotations.data.find(item => item.tool === 'line' && item.coordinate_contract === 'LPS_DISPLAY_V1')
  if (!line || JSON.parse(line.points)[0][0] <= JSON.parse(line.points)[1][0]) throw new Error('Negative-slope measurement was not preserved')
  await page.reload()
  await page.getByText('真实窗宽窗位', { exact: true }).waitFor()
  await page.locator('.label-text').filter({ hasText: 'mm' }).first().waitFor()
  await page.screenshot({ path: `${output}/sample-4-measurement.png`, fullPage: true })
  if (errors.length) throw new Error(errors.join('\n'))
  await fs.writeFile(`${output}/browser_validation.json`, JSON.stringify({ status: 'passed', samples: results, pdf_bytes: pdf.length, four_sequence_form: 'passed', analysis_polling: 'passed', measurement_persistence: 'passed', errors }, null, 2))
  console.log('Five real-data viewers and version-bound PDF PASS')
} catch (e) {
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true })
  await fs.writeFile(`${output}/browser_validation.json`, JSON.stringify({ status: 'failed', error: String(e), samples: results, errors }, null, 2))
  throw e
} finally { await browser.close() }
