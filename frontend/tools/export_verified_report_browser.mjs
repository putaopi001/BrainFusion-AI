import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const output = process.env.BRAINFUSION_EVIDENCE_DIR
if (!output?.startsWith('E:/BrainFusion-Runtime/results/nightly/')) throw new Error('Use a new nightly evidence directory')
await fs.mkdir(output)
const id = Number(process.env.BRAINFUSION_CASE_ID || 17)
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 }, acceptDownloads: true })
try {
  const analysis = (await (await page.request.get(`http://127.0.0.1:8012/analysis/${id}`)).json()).data
  assert.equal(analysis.stale, false); assert(analysis.result)
  await page.goto(`http://127.0.0.1:5179/report?case_id=${id}`)
  await page.locator('#report-paper').waitFor()
  const text = await page.locator('#report-paper').innerText()
  assert(text.includes(analysis.id)); assert(text.includes(analysis.result.revision))
  for (const value of Object.values(analysis.result.volumes_ml)) assert(text.includes(`${value} mL`))
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出 PDF', exact: true }).click()
  const download = await downloading
  await download.saveAs(`${output}/case17-current-report.pdf`)
  await page.screenshot({ path: `${output}/report-page.png`, fullPage: true })
  await fs.writeFile(`${output}/validation.json`, JSON.stringify({ status: 'passed', analysis_run_id: analysis.id,
    revision: analysis.result.revision, volumes_ml: analysis.result.volumes_ml, report_text: text,
    pdf_visual_review: 'pending' }, null, 2))
} finally { await browser.close() }
