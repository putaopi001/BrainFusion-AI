// Read-only formal account UI: login/logout only, never save a review.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2]?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const api='http://127.0.0.1:8012'
const c=(await (await fetch(api+'/pacs/import-candidates')).json()).data.items[0]
const prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const url=`http://127.0.0.1:5179/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`
const out=root+'/formal-account-browser';await fs.mkdir(out)
const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1600,height:1200}})
const result={status:'running',writes:[],pageErrors:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',r=>{
 const q=r.request();if(!['GET','HEAD'].includes(q.method())){
  const path=new URL(q.url()).pathname
  assert.ok(['/local-auth/login','/local-auth/logout'].includes(path),'No clinical write allowed')
  result.writes.push({method:q.method(),path})
 }
 return r.continue()
})
try{
 await page.goto(url);await page.locator('#report-paper.dicom-report').waitFor({timeout:90000})
 assert.equal((await (await page.request.get(api+prefix+'/reviews')).json()).data.total,0)
 for(const role of ['researcher','reviewer']){
  const password=(await fs.readFile('E:/BrainFusion-Runtime/local/credentials/20261015T231143_p4identity-'+role+'.password.txt','utf8')).trimEnd()
  await page.getByRole('textbox',{name:'本地账户',exact:true}).fill('local-'+role)
  await page.getByLabel('账户密码',{exact:true}).fill(password)
  await page.getByRole('button',{name:'登录复核账户',exact:true}).click()
  await page.getByRole('button',{name:'退出账户',exact:true}).waitFor()
  const s=(await (await page.request.get(api+'/local-auth/session')).json()).data
  assert.equal(s.user.role,role==='reviewer'?'doctor':'researcher')
  await page.getByRole('textbox',{name:'本版本复核意见',exact:true}).fill('未提交的界面工程检查，不会保存。')
  await page.locator('.review-editor .el-checkbox__label').click()
  assert.equal(await page.getByRole('button',{name:'保存本版本复核',exact:true}).isEnabled(),role==='reviewer')
  await page.locator('.local-auth-box').screenshot({path:out+'/'+role+'-account.png'})
  await page.getByRole('button',{name:'退出账户',exact:true}).click()
  await page.getByRole('button',{name:'登录复核账户',exact:true}).waitFor()
 }
 assert.equal((await (await page.request.get(api+prefix+'/reviews')).json()).data.total,0)
 assert.deepEqual(result.pageErrors,[])
 result.status='passed';result.checks.push('Actual formal operator-provisioned researcher/doctor UI logins, role-bound save button, logout; only authentication requests, zero clinical writes or saved engineering opinions')
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close()}
