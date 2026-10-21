// Actual case-bound DICOM UI rejection, without synthetic interception.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const out=process.argv[2]+'/browser-dicom-unconfigured'
await fs.mkdir(out)
const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1500,height:1050}})
const result={status:'running',pageErrors:[],writes:[],pixelRequests:[],scope:'Actual unconfigured source; no real DICOM acceptance'}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{
 const req=route.request()
 if(['POST','PUT','PATCH','DELETE'].includes(req.method())){result.writes.push(req.url());await route.abort();return}
 if(req.url().includes('/frames/'))result.pixelRequests.push(req.url())
 await route.continue()
})
try{
 await page.goto('http://127.0.0.1:5179/workstation/17?source=dicom&viewer=cornerstone&study_uid=1.2.3&series_uid=1.2.4')
 await page.locator('.cs-viewer[data-source="dicom"][data-state="error"]').waitFor()
 await page.getByText(/本地 PACS 尚未配置/).waitFor()
 assert.equal(await page.locator('.mri-viewer').count(),0)
 assert.ok(await page.getByRole('radio',{name:'Canvas（已验入口）',exact:true}).isDisabled())
 assert.equal(await page.locator('.cs-viewer[data-source="nifti"]').count(),0)
 await page.locator('.cs-viewer').screenshot({path:out+'/actual-source-refusal.png'})
 assert.deepEqual(result.pageErrors,[]);assert.deepEqual(result.writes,[]);assert.deepEqual(result.pixelRequests,[])
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1;await page.screenshot({path:out+'/failed.png',fullPage:true})}
finally{await fs.writeFile(out+'/result.json',JSON.stringify(result,null,2));await browser.close()}
