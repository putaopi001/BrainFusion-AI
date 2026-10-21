// Actual CLI joint restore: account attribution and source/history persistence, without repeated pixel loading or PDF.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [rawRoot,mode='save']=process.argv.slice(2),root=rawRoot?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'));assert.ok(['save','restart'].includes(mode))
const expected=JSON.parse(await fs.readFile(root+'/expected.json','utf8'))
const state=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),expected.restored_database.replaceAll('\\','/'))
const privateRoot='E:/BrainFusion-Runtime/backups/'+root.split('/').at(-1)
const c=expected.context,api='http://127.0.0.1:8012',prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const out=root+'/joint-account-browser-'+mode;await fs.mkdir(out)
const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1600,height:1100}}),page=await context.newPage()
const result={status:'running',mode,writes:[],pageErrors:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',route=>{const r=route.request();if(!['GET','HEAD'].includes(r.method())){const path=new URL(r.url()).pathname;assert.ok(['/local-auth/login',prefix+'/reviews'].includes(path));result.writes.push({method:r.method(),path})}return route.continue()})
const get=async path=>{const r=await page.request.get(api+path);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
const ready=async()=>{await page.locator('#report-paper.dicom-report').waitFor({timeout:90000});await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))}
async function login(){
 const secret=await fs.readFile('E:/BrainFusion-Runtime/results/nightly/2026-10-15/20261015T231143_p4identity/private/doctor.password.txt','utf8')
 await page.getByRole('textbox',{name:'本地账户',exact:true}).fill('engineering-doctor')
 await page.getByLabel('账户密码',{exact:true}).fill(secret.trimEnd())
 await page.getByRole('button',{name:'登录复核账户',exact:true}).click()
 await page.getByRole('button',{name:'退出账户',exact:true}).waitFor()
 const s=await get('/local-auth/session');assert.equal(s.user.id,expected.doctor_id);return s
}
try{
 await page.goto(`http://127.0.0.1:5179/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`);await ready()
 assert.equal(await page.getByRole('button',{name:'保存本版本复核',exact:true}).isDisabled(),true)
 const initial=await get(prefix+'/reading-report')
 if(mode==='save'){
  for(const key of ['context','geometry','measurements','doctor_opinion','content_sha256','export_sha256','latest_review','review_history_count'])assert.deepEqual(initial[key],expected.source_report[key],key)
  assert.equal((await get(prefix+'/reviews')).total,4)
  await login()
  const signature=page.getByRole('textbox',{name:'复核署名',exact:true});assert.equal(await signature.inputValue(),'身份工程验收（非医师认证）');assert.equal(await signature.getAttribute('readonly'),'')
  await page.getByRole('textbox',{name:'本版本复核意见',exact:true}).fill('恢复接线工程验证：账户与来源绑定，不构成医师资质认证或临床结论。')
  await page.locator('.review-editor .el-checkbox__label').click()
  const posted=page.waitForRequest(r=>r.method()==='POST' && new URL(r.url()).pathname===prefix+'/reviews')
  await page.getByRole('button',{name:'保存本版本复核',exact:true}).click()
  const payload=(await posted).postDataJSON()
  await page.locator('.review-save-message').getByText(/已保存/).waitFor();await ready()
  const after=await get(prefix+'/reading-report');assert.equal(after.review_history_count,5);assert.equal(after.latest_review.identity.id,expected.doctor_id)
  assert.equal(after.latest_review.reviewer_authenticated,true);assert.equal(after.latest_review.identity.professional_credential_verified,false)
  assert.equal(after.content_sha256,initial.content_sha256);assert.notEqual(after.export_sha256,initial.export_sha256)
  await page.reload();await ready();assert.equal((await get('/local-auth/session')).user.id,expected.doctor_id)
  await page.locator('.local-auth-box').screenshot({path:out+'/restored-account.png'})
  await page.locator('.dicom-review-paper').screenshot({path:out+'/restored-source-bound-review.png'})
  const cookie=(await context.cookies(api)).find(c=>c.name==='bf_local_session');assert.ok(cookie?.httpOnly)
  await fs.writeFile(privateRoot+'/active-session-before-restart.token',cookie.value,{flag:'wx'})
  await fs.writeFile(root+'/after-restored-account-save.json',JSON.stringify({report:after,payload},null,2),{flag:'wx'})
  result.checks.push('Actual joint restored archive/case, 36 distances/1 view/4 historical snapshots and stable content/export revision; restored account login, one new immutable account review and refresh')
 }else{
  const before=JSON.parse(await fs.readFile(root+'/after-restored-account-save.json','utf8'))
  for(const key of ['context','content_sha256','export_sha256','latest_review','review_history_count'])assert.deepEqual(initial[key],before.report[key],key)
  const token=await fs.readFile(privateRoot+'/active-session-before-restart.token','utf8')
  const old=await page.request.get(api+'/local-auth/session',{headers:{Cookie:'bf_local_session='+token}});assert.equal((await old.json()).data.user,null)
  const s=await login()
  const retry=await page.request.post(api+prefix+'/reviews',{data:before.payload,headers:{'X-BF-CSRF':s.csrf}})
  assert.equal(retry.status(),200,await retry.text());assert.equal((await retry.json()).data.id,before.report.latest_review.id)
  result.writes.push({method:'POST',path:prefix+'/reviews',scope:'same-UID retry through APIRequestContext'})
  assert.equal((await get(prefix+'/reviews')).total,5)
  await page.locator('.paper-header').screenshot({path:out+'/restarted-attribution.png'})
  result.checks.push('Actual backend restart retains restored account-owned history/content/export versions, invalidates previously active cookie, allows re-login and same-UID retry without another record')
 }
 assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,checks:result.checks,error:result.error}))}
