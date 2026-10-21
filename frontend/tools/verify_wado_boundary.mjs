// Read-only new WADO unavailable APIs and existing UI/NIfTI after actual service restart.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2], output=root+'/browser-wado-boundary'
await fs.mkdir(output)
const browser=await chromium.launch({headless:true}), page=await browser.newPage({viewport:{width:1500,height:1000}})
const result={status:'running',scope:'Actual localhost API/UI with unconfigured archive; no DICOM browser rendering acceptance',pageErrors:[],writes:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{
  if(['POST','PUT','PATCH','DELETE'].includes(route.request().method())){result.writes.push(route.request().url());await route.abort()}
  else await route.continue()
})
try {
  const health=await page.request.get('http://127.0.0.1:8012/pacs/status')
  const data=(await health.json()).data
  assert.equal(data.state,'unconfigured');assert.equal(data.pixel_read_enabled,false);assert.equal(data.dicom_view_available,false)
  for(const suffix of ['/metadata','/frames/1']){
    const response=await page.request.get('http://127.0.0.1:8012/pacs/studies/1.2.3/series/1.2.4/instances/1.2.5'+suffix)
    assert.equal(response.status(),503);assert.equal(response.headers()['cache-control'],'no-store');assert.equal((await response.json()).detail.reason,'unconfigured')
  }
  await page.goto('http://127.0.0.1:5179/case/17')
  const panel=page.locator('.pacs-panel')
  await panel.getByText('本地 PACS 尚未配置，DICOM 归档与阅片尚不可用。',{exact:true}).waitFor()
  assert.equal(await panel.getByRole('button',{name:'查询检查',exact:true}).count(),0)
  await panel.screenshot({path:output+'/actual-pacs-status.png'})
  await page.goto('http://127.0.0.1:5179/workstation/17?viewer=cornerstone')
  await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready')
  assert.equal(await page.locator('.cs-viewport canvas').count(),3)
  assert.deepEqual(result.pageErrors,[]);assert.deepEqual(result.writes,[])
  result.checks.push('Actual restarted backend WADO endpoints503/no-store, pixel flag false/no DICOM capability claim; existing case panel and real NIfTI Cornerstone3canvas preserved; no writes/page errors')
  result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1;await page.screenshot({path:output+'/failure.png',fullPage:true})}
finally{await fs.writeFile(output+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
