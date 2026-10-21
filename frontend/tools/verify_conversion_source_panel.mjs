// Real no-version state + explicitly SYNTHETIC display protocol, no registration.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const out=process.argv[2]+'/browser-conversion-source'+(process.argv[3]?'-'+process.argv[3]:'')
await fs.mkdir(out)
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1500,height:1100}})
const result={status:'running',scope:'Actual no registered conversion; SYNTHETIC UI responses only, no real DICOM or activation acceptance',pageErrors:[],writes:[],checks:[]}
let mock=false,mode='verified_readonly'
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{
 const req=route.request(),url=new URL(req.url())
 if(['POST','PUT','PATCH','DELETE'].includes(req.method())){result.writes.push(req.url());await route.abort();return}
 if(!mock||!url.pathname.includes('/conversions')){await route.continue();return}
 if(mode==='disconnected'){await route.abort('connectionrefused');return}
 if(url.pathname.endsWith('/inspection')){
  if(mode==='delayed')await new Promise(resolve=>setTimeout(resolve,700))
  const data={version_id:mode==='wrong_id'?'wrong-version':'SYNTHETIC-ui-only',status:mode==='delayed'?'verified_readonly':mode,
   reason:null,message:'SYNTHETIC 界面协议状态；没有真实版本登记',model_input_eligible:false,current_mri_replaced:false,live_archive_reconciled:false}
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:200,data})});return
 }
 const empty=url.pathname.includes('/cases/18/')
 const data={state:empty?'not_registered':'registered',message:empty?'SYNTHETIC 新病例没有转换版本':'SYNTHETIC 只读转换界面夹具，未写入病例或归档',
  items:empty?[]:[{version_id:'SYNTHETIC-ui-only',study_uid:'2.25.900',report_sha256:'a'.repeat(64),integrity_status:'not_rechecked',model_input_eligible:false}],model_input_eligible:false,current_mri_replaced:false}
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({code:200,data})})
})
const panel=page.locator('.pacs-panel'),section=page.getByRole('region',{name:'DICOM 转换来源'})
try{
 const live=await page.request.get('http://127.0.0.1:8012/pacs/cases/17/conversions')
 assert.equal(live.status(),200);assert.equal(live.headers()['cache-control'],'no-store')
 assert.equal((await live.json()).data.state,'not_registered')
 await page.goto('http://127.0.0.1:5179/case/17')
 await section.getByText('当前病例尚无登记的DICOM转换版本，现有NIfTI不受影响。',{exact:true}).waitFor()
 assert.equal(await section.getByRole('button',{name:'核对本地版本'}).count(),0)
 await panel.getByText('本地 PACS 尚未配置，DICOM 归档与阅片尚不可用。',{exact:true}).waitFor()
 await panel.screenshot({path:out+'/actual-case-source.png'})
 result.checks.push('Actual API no-store/not_registered; real case remains unconfigured and no model action')
 mock=true
 for(const status of ['verified_readonly','stale','unavailable','invalid']){
  mode=status
  await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
  await section.getByRole('button',{name:'核对本地版本',exact:true}).waitFor()
  await section.getByRole('button',{name:'核对本地版本',exact:true}).click()
  await section.locator('[role="status"]').getByText(/SYNTHETIC 界面协议状态/).waitFor()
  const text=await section.locator('[role="status"]').innerText()
  assert.ok(text.includes({verified_readonly:'本地完整性通过（待来源审核）',stale:'来源已失效',unavailable:'当前不可用',invalid:'完整性核对失败'}[status]))
 }
 result.checks.push('SYNTHETIC success/stale/unavailable/invalid clearly labeled; no AI submit action')
 mode='wrong_id'
 await section.getByRole('button',{name:'核对本地版本',exact:true}).click()
 await panel.getByText('转换版本核对返回的身份或提交状态不一致。',{exact:true}).waitFor()
 assert.equal(await section.locator('[role="status"]').count(),0)
 mode='disconnected'
 await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
 await section.getByText('转换版本读取失败，请刷新重试。',{exact:true}).waitFor()
 assert.equal(await section.getByRole('button',{name:'核对本地版本'}).count(),0)
 mode='verified_readonly'
 await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
 await section.getByRole('button',{name:'核对本地版本',exact:true}).waitFor()
 mode='delayed'
 await section.getByRole('button',{name:'核对本地版本',exact:true}).click()
 await page.evaluate(()=>{document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/case/18')})
 await section.getByText('SYNTHETIC 新病例没有转换版本',{exact:true}).waitFor()
 await page.waitForTimeout(900)
 assert.equal(await section.locator('[role="status"]').count(),0)
 assert.equal(await section.getByRole('button',{name:'核对本地版本'}).count(),0)
 result.checks.push('Wrong version, disconnection and delayed old-case response never persist success')
 mock=false
 await page.goto('http://127.0.0.1:5179/workstation/17?viewer=cornerstone')
 await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.cs-viewer')?.dataset.state))
 assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready')
 assert.equal(await page.locator('.cs-viewport canvas').count(),3)
 assert.deepEqual(result.pageErrors,[]);assert.deepEqual(result.writes,[])
 result.checks.push('Existing real NIfTI Cornerstone3canvas; no page errors or writes')
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1;await page.screenshot({path:out+'/failed.png',fullPage:true})}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
