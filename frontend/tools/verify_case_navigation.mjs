// Real Edge navigation and lifecycle regression; API business writes are blocked.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2]?.replaceAll('\\','/');assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const out=root+'/browser-after-accepted';await fs.mkdir(out)
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1500,height:1000}})
const result={status:'running',browser:await browser.version(),requests:[],pageErrors:[],writes:[],checks:[]}
page.on('response',r=>{const u=new URL(r.url());if(u.port==='8012')result.requests.push({path:u.pathname,status:r.status()})})
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('http://127.0.0.1:8012/**',async route=>{if(!['GET','HEAD','OPTIONS'].includes(route.request().method())){result.writes.push(route.request().method()+' '+new URL(route.request().url()).pathname);await route.abort();return}await route.continue()})
const nav=p=>page.evaluate(async p=>{await document.getElementById('app').__vue_app__.config.globalProperties.$router.push(p)},p)
const shown=id=>page.waitForFunction(id=>new RegExp('病例ID:\\s*'+id+'\\b').test(document.querySelector('.page')?.innerText||''),id)
const context=()=>page.evaluate(()=>{const s=document.getElementById('app').__vue_app__.config.globalProperties.$pinia.state.value;return {id:s.case.currentCaseId,dataId:s.case.currentCase?.id??null,mri:!!s.mri.mri,ai:!!s.ai.prediction,report:!!s.report.report}})
try{
 await page.goto('http://127.0.0.1:5179/cases');await page.waitForSelector('.el-table__row')
 assert.equal(await page.locator('.el-table__row').count(),19)
 await page.locator('.el-table__row').first().getByRole('button',{name:'详情',exact:true}).click();await shown(19)
 result.checks.push('Actual19-row list → normal detail button → case19, no 422')
 for(const bad of [':id','undefined','NaN','0','9007199254740992']){
  for(const prefix of ['/case/','/workstation/']){
   await nav(prefix+bad);await page.getByText('病例链接无效，请从病例管理选择病例。',{exact:true}).waitFor()
   assert.equal(await page.locator('.cs-viewport canvas').count(),0)
   if(prefix==='/case/'){assert.equal(await page.locator('.pacs-panel').count(),0);assert.deepEqual(await context(),{id:null,dataId:null,mri:false,ai:false,report:false})}
  }
 }
 assert.equal(result.requests.filter(r=>r.status===422).length,0)
 assert.ok(!(await page.locator('body').innerText()).includes('该病例暂无 MRI 影像，请先上传'))
 await page.screenshot({path:out+'/invalid-route-clear.png'})
 await page.getByRole('button',{name:'返回病例管理',exact:true}).click();await page.waitForSelector('.el-table__row');assert.equal(new URL(page.url()).pathname,'/cases')
 result.checks.push('Five malformed IDs in detail/workstation show a clear error, never send invalid case/PACS requests, render no previous patient or viewer')
 await nav('/case/19');await shown(19)
 await nav('/case/999999');await page.getByText('病例不存在，请返回病例管理选择病例。',{exact:true}).waitFor()
 assert.deepEqual(await context(),{id:null,dataId:null,mri:false,ai:false,report:false})
 assert.equal(await page.locator('.pacs-panel').count(),0)
 result.checks.push('Real404 after case19 clears displayed/store data and hides case operations')
 await nav('/cases');await page.waitForSelector('.el-table__row')
 let arrived;const seen=new Promise(resolve=>arrived=resolve);let release;const hold=new Promise(resolve=>release=resolve)
 const delay=async route=>{const response=await route.fetch();arrived();await hold;await route.fulfill({response}).catch(()=>{})}
 await page.route('**/cases/19/detail',delay)
 await nav('/case/19');await seen;await nav('/case/17');await shown(17);release();await page.waitForTimeout(300)
 assert.equal(new URL(page.url()).pathname,'/case/17');assert.equal((await context()).id,17);assert.equal((await context()).dataId,17)
 assert.ok(!/病例ID:\s*19\b/.test(await page.locator('.page').innerText()))
 await page.unroute('**/cases/19/detail',delay)
 await page.screenshot({path:out+'/late-response-keeps17.png'})
 result.checks.push('Hold real19 HTTP response, navigate17 then release19: route/render/store remain17 and obsolete request cannot apply')
 // A failed load cannot retain a previous clinical result; recover through normal reload.
 const failure=route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'owned transient service failure fixture'})})
 await page.route('**/cases/19/detail',failure);await nav('/case/19');await page.getByText('病例加载失败，请检查本机服务后重试。',{exact:true}).waitFor()
 assert.deepEqual(await context(),{id:null,dataId:null,mri:false,ai:false,report:false})
 await page.unroute('**/cases/19/detail',failure);await page.reload();await shown(19)
 result.checks.push('Owned503 fixture clears prior case; normal refresh recovers real19')
 await nav('/workstation/17?viewer=cornerstone')
 await page.waitForFunction(()=>document.querySelector('.cs-viewer')?.dataset.state==='ready',null,{timeout:90000})
 assert.equal(await page.locator('.cs-viewport canvas').count(),3)
 await page.locator('.cs-viewer').screenshot({path:out+'/nifti-ready.png'})
 await nav('/case/19');await shown(19)
 const candidate=(await (await page.request.get('http://127.0.0.1:8012/pacs/import-candidates')).json()).data.items[0]
 await nav(`/workstation/19?viewer=cornerstone&source=dicom&study_uid=${candidate.study_uid}&series_uid=${candidate.series_uid}`)
 await page.waitForFunction(()=>document.querySelector('.cs-viewer')?.dataset.state==='ready'&&document.querySelector('.cs-viewer')?.dataset.source==='dicom',null,{timeout:90000})
 assert.equal(await page.locator('.cs-viewport canvas').count(),3)
 await page.locator('.cs-viewer').screenshot({path:out+'/dicom-ready.png'})
 await nav('/case/19');await shown(19)
 await page.waitForFunction(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);return core.getRenderingEngines().length===0})
 result.checks.push('Changed case lifecycle still opens actual NIfTI and archived DICOM three-view Cornerstone; route exit clears rendering engine')
 assert.deepEqual(result.writes,[]);assert.deepEqual(result.pageErrors,[]);assert.equal(result.requests.filter(r=>r.status===422).length,0)
 result.status='passed'
}catch(e){result.status='failed';result.route=new URL(page.url()).pathname;result.error=e.stack;await page.screenshot({path:out+'/failure.png'}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,browser:result.browser,checks:result.checks,error:result.error}))}
