import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
const root = process.env.BRAINFUSION_RUN_ROOT
const fixture = JSON.parse(await fs.readFile(`${root}/fixture.json`, 'utf8'))
const change = action => execFileSync('E:/BrainFusion-AI/.conda/brainfusion/python.exe', ['-B', 'E:/BrainFusion-AI/backend/tools/prepare_integrity_fixture.py', '--root', root, '--action', action], { windowsHide: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } })
const events = []
page.on('response', r => { if (r.url().includes(`/mri/${fixture.case_id}/`)) events.push({ url: r.url(), status: r.status() }) })
page.on('requestfailed', r => events.push({ url: r.url(), failure: r.failure() }))
page.on('request', r => { if (r.resourceType() === 'image' && r.url().includes('/mask/')) events.push({ mask_requested: r.url() }) })
try {
  change('restore')
  await page.goto(`http://127.0.0.1:5179/case/${fixture.case_id}`)
  await page.waitForFunction(() => document.querySelectorAll('.slice-img').length === 3 && [...document.querySelectorAll('.slice-img')].every(i => i.complete && i.naturalWidth > 0))
  await page.getByRole('button', { name: 'AI分割叠加', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.mask-img').length === 3 && [...document.querySelectorAll('.mask-img')].every(i => i.complete && i.naturalWidth > 0))
  change('mask-change')
  await page.locator('.viewport-panel[data-view="axial"] .viewport').hover()
  await page.mouse.wheel(0, 120)
  await page.waitForFunction(() => document.querySelectorAll('.mask-img').length === 0)
  await page.getByText('模型分割已失效：', { exact: false }).first().waitFor()
  const result = { events, mask_count: await page.locator('.mask-img').count(), reason: await page.locator('.seg-disclaimer').innerText() }
  await fs.writeFile(`${root}/mask-diagnosis.json`, JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result))
} finally { change('restore'); await browser.close() }
