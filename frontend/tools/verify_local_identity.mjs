// Actual local account UI and source-bound review on an owned database copy only.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [rawRoot,mode='save']=process.argv.slice(2)
const root=rawRoot?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
assert.ok(['save','restart'].includes(mode))
const registry=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.equal(registry.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),root+'/database-backup/restored-validation.db')
const api='http://127.0.0.1:8012'
const c=(await (await fetch(api+'/pacs/import-candidates')).json()).data.items[0]
const prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const url=`http://127.0.0.1:5179/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`
const out=root+'/identity-browser-'+mode
await fs.mkdir(out)
const browser=await chromium.launch({headless:true})
const context=await browser.newContext({viewport:{width:1600,height:1200}})
const page=await context.newPage()
const result={status:'running',pageErrors:[],writes:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',route=>{
 const r=route.request()
 if(!['GET','HEAD'].includes(r.method()))result.writes.push({method:r.method(),path:new URL(r.url()).pathname})
 return route.continue()
})
const get=async path=>{const r=await page.request.get(api+path);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
const saveButton=()=>page.getByRole('button',{name:'保存本版本复核',exact:true})
async function ready(){await page.locator('#report-paper.dicom-report').waitFor({timeout:90000});await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))}
async function login(role){
 const password=(await fs.readFile(root+'/private/'+role+'.password.txt','utf8')).trimEnd()
 await page.getByRole('textbox',{name:'本地账户',exact:true}).fill('engineering-'+role)
 await page.getByLabel('账户密码',{exact:true}).fill(password)
 await page.getByRole('button',{name:'登录复核账户',exact:true}).click()
 await page.getByRole('button',{name:'退出账户',exact:true}).waitFor()
 assert.equal(await page.getByRole('textbox',{name:'复核署名',exact:true}).inputValue(),role==='doctor'?'身份工程验收（非医师认证）':'研究工程验收')
 return get('/local-auth/session')
}
try{
 await page.goto(url);await ready()
 assert.equal(await saveButton().isDisabled(),true)
 const initial=await get(prefix+'/reading-report')
 const payload={context:initial.context,content_sha256:initial.content_sha256,client_uid:'REAL-LOCAL-IDENTITY-REVIEW',
  reviewer:'身份工程验收（非医师认证）',opinion:'工程验证本地账户、来源和不可变版本绑定；不构成医师资质或临床判断。',decision:'checked',acknowledge_local_record_only:true}
 const anon=await page.request.post(api+prefix+'/reviews',{data:payload});assert.equal(anon.status(),401)
 if(mode==='save'){
  assert.equal(initial.review_history_count,3)
  assert.ok((await get(prefix+'/reviews')).items.every(r=>!r.reviewer_authenticated && r.identity===null))
  let session=await login('researcher')
  assert.equal(await saveButton().isDisabled(),true)
  const denied=await page.request.post(api+prefix+'/reviews',{data:payload,headers:{'X-BF-CSRF':session.csrf}})
  assert.equal(denied.status(),403)
  await page.getByRole('button',{name:'退出账户',exact:true}).click()
  await page.getByRole('button',{name:'登录复核账户',exact:true}).waitFor()
  session=await login('doctor')
  const cookies=await context.cookies(api);const cookie=cookies.find(c=>c.name==='bf_local_session')
  assert.ok(cookie.httpOnly && cookie.sameSite==='Strict')
  assert.ok(!await page.evaluate(()=>document.cookie.includes('bf_local_session')))
  assert.equal(await page.getByRole('textbox',{name:'复核署名',exact:true}).getAttribute('readonly'),'')
  const forged=await page.request.post(api+prefix+'/reviews',{data:{...payload,reviewer:'伪造署名'},headers:{'X-BF-CSRF':session.csrf}})
  assert.equal(forged.status(),403)
  const noCsrf=await page.request.post(api+prefix+'/reviews',{data:payload});assert.equal(noCsrf.status(),403)
  await page.getByRole('textbox',{name:'本版本复核意见',exact:true}).fill(payload.opinion)
  await page.locator('.review-editor .el-checkbox__label').click()
  const posted=page.waitForRequest(r=>r.method()==='POST' && new URL(r.url()).pathname===prefix+'/reviews')
  await saveButton().click()
  const submitted=(await posted).postDataJSON()
  await page.locator('.review-save-message').getByText(/已保存/).waitFor();await ready()
  const current=await get(prefix+'/reading-report')
  assert.equal(current.review_history_count,4);assert.equal(current.latest_review.reviewer_authenticated,true)
  assert.equal(current.latest_review.identity.username,'engineering-doctor')
  assert.equal(current.latest_review.identity.professional_credential_verified,false)
  assert.equal(current.content_sha256,initial.content_sha256);assert.notEqual(current.export_sha256,initial.export_sha256)
  const history=await get(prefix+'/reviews')
  assert.equal(history.items[0].reviewed_snapshot.review_actor.id,current.latest_review.identity.id)
  assert.ok(history.items.slice(1).every(r=>r.reviewer_authenticated===false && r.identity===null))
  await fs.writeFile(root+'/identity-before-restart.json',JSON.stringify({report:current,payload:submitted},null,2),{flag:'wx'})
  await page.reload();await ready()
  assert.ok((await page.locator('.local-auth-box').innerText()).includes('本地医生角色'))
  await page.locator('.local-auth-box').screenshot({path:out+'/logged-in-account.png'})
  await page.locator('.paper-header').screenshot({path:out+'/authenticated-review-status.png'})
  await page.getByRole('button',{name:'退出账户',exact:true}).click()
  await page.getByRole('button',{name:'登录复核账户',exact:true}).waitFor()
  const replay=await page.request.post(api+prefix+'/reviews',{data:payload,headers:{Cookie:'bf_local_session='+cookie.value,'X-BF-CSRF':session.csrf}})
  assert.equal(replay.status(),401)
  assert.equal(await saveButton().isDisabled(),true)
  await login('doctor')
  const activeCookie=(await context.cookies(api)).find(c=>c.name==='bf_local_session')
  assert.ok((await get('/local-auth/session')).user)
  await fs.writeFile(root+'/private/session-before-restart.token',activeCookie.value,{flag:'wx'})
  result.checks.push('Actual UI anonymous/researcher denied, doctor login with HttpOnly cookie/CSRF, fixed account signature, forged name rejected, source-bound immutable review saved, refresh/login persists and logout replay rejected; all 3 legacy records stay unauthenticated')
 }else{
  const expected=JSON.parse(await fs.readFile(root+'/identity-before-restart.json','utf8'))
  assert.equal(initial.latest_review.id,expected.report.latest_review.id)
  assert.equal(initial.export_sha256,expected.report.export_sha256)
  const oldToken=await fs.readFile(root+'/private/session-before-restart.token','utf8')
  const old=await page.request.get(api+'/local-auth/session',{headers:{Cookie:'bf_local_session='+oldToken}})
  assert.equal((await old.json()).data.user,null)
  const session=await login('doctor')
  const retried=await page.request.post(api+prefix+'/reviews',{data:expected.payload,headers:{'X-BF-CSRF':session.csrf}})
  assert.equal(retried.status(),200,await retried.text())
  assert.equal((await retried.json()).data.id,expected.report.latest_review.id)
  assert.equal((await get(prefix+'/reviews')).total,4)
  await page.locator('.local-auth-box').screenshot({path:out+'/relogin-after-restart.png'})
  result.checks.push('Actual backend restart preserves actor/content/export/history; old session invalid, new local login succeeds, same account retry remains one immutable review')
 }
 assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,checks:result.checks,error:result.error}))}
