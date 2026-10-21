// Final built HTTP page, actual unavailable PACS; no synthetic data or writes.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root = process.argv[2], output = root + '/browser-pacs-production' + (process.argv[3] ? '-' + process.argv[3] : '')
const services = JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.equal(services.frontend_mode,'preview')
assert.ok(services.frontend_preview_dist.replaceAll('\\','/').startsWith(root+'/preview-frontend/'))
await fs.mkdir(output)
const browser = await chromium.launch({headless:true}), page = await browser.newPage({viewport:{width:1500,height:1000}})
const result = {status:'running',scope:'Actual final static build and unconfigured local backend, original DB read-only',pageErrors:[],writes:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{
  if (['POST','PUT','PATCH','DELETE'].includes(route.request().method())) {result.writes.push(route.request().url()); await route.abort()}
  else await route.continue()
})
try {
  await page.goto('http://127.0.0.1:5179/case/17')
  const panel = page.locator('.pacs-panel')
  await panel.getByText('本地 PACS 尚未配置，DICOM 归档与阅片尚不可用。',{exact:true}).waitFor()
  assert.equal(await panel.getByRole('button',{name:'查询检查',exact:true}).count(),0)
  assert.match(await panel.innerText(),/DICOM 导入、阅片与 AI 输入转换尚未开放/)
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'))
  await panel.screenshot({path:output+'/actual-unconfigured.png'})
  await page.goto('http://127.0.0.1:5179/workstation/17?viewer=cornerstone')
  await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready')
  assert.equal(await page.locator('.cs-viewport canvas').count(),3)
  assert.deepEqual(result.pageErrors,[]); assert.deepEqual(result.writes,[])
  result.checks.push('Final static HTTP existing case: explicit unavailable PACS/refresh/no DICOM query, original NIfTI Cornerstone still ready with3canvas; no writes/page errors')
  result.status='passed'
} catch(e) {result.status='failed'; result.error=e.stack; process.exitCode=1; await page.screenshot({path:output+'/failure.png',fullPage:true})}
finally {await fs.writeFile(output+'/validation.json',JSON.stringify(result,null,2)); await browser.close()}
