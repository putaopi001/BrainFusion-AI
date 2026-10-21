// Edge persistent-profile account review/PDF verification. Never use a personal profile.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2]?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const exp=JSON.parse(await fs.readFile(root+'/expected.json','utf8'))
const registered=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.equal(registered.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),exp.database)
const c=exp.report.context,api='http://127.0.0.1:8012',prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const url=`http://127.0.0.1:5179/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`
const out=root+'/edge-account',profile=exp.private+'/edge-profile'
await fs.mkdir(out)
const result={status:'running',browser:'Microsoft Edge',mode:'headless persistent E-drive profile',writes:[],pageErrors:[],checks:[]}
let context,page
const get=async path=>{const r=await page.request.get(api+path);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
const ready=async()=>{await page.locator('#report-paper.dicom-report').waitFor({timeout:90000});await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))}
async function launch(){
 context=await chromium.launchPersistentContext(profile,{channel:'msedge',headless:true,viewport:{width:1600,height:1100},acceptDownloads:true})
 result.browserVersion=context.browser()?.version()??'persistent-context'
 page=context.pages()[0]??await context.newPage()
 page.on('pageerror',e=>result.pageErrors.push(e.message))
 await page.route('**/*',route=>{const req=route.request();if(!['GET','HEAD'].includes(req.method())){const path=new URL(req.url()).pathname;assert.ok(['/local-auth/login','/local-auth/logout',prefix+'/reviews'].includes(path));result.writes.push({method:req.method(),path})}return route.continue()})
 await page.goto(url);await ready()
}
try{
 await launch()
 const initial=await get(prefix+'/reading-report')
 for(const key of ['context','geometry','measurements','doctor_opinion','content_sha256','export_sha256','latest_review','review_history_count'])assert.deepEqual(initial[key],exp.report[key],key)
 assert.equal(initial.review_history_count,5)
 assert.equal((await get('/local-auth/session')).user,null)
 const password=(await fs.readFile(exp.password_file,'utf8')).trimEnd()
 await page.getByRole('textbox',{name:'本地账户',exact:true}).fill('engineering-doctor')
 await page.getByLabel('账户密码',{exact:true}).fill(password)
 await page.getByRole('button',{name:'登录复核账户',exact:true}).click()
 await page.getByRole('button',{name:'退出账户',exact:true}).waitFor()
 const user=(await get('/local-auth/session')).user
 assert.equal(user.id,exp.doctor_id)
 const signature=page.getByRole('textbox',{name:'复核署名',exact:true})
 assert.equal(await signature.inputValue(),user.display_name)
 assert.equal(await signature.getAttribute('readonly'),'')
 const opinion='Edge 浏览器复核保存与关闭恢复工程验收：核对本页来源、36条毫米距离和版本；本地账户不代表医师资质认证，本记录不是临床诊断。'
 await page.getByRole('textbox',{name:'本版本复核意见',exact:true}).fill(opinion)
 await page.locator('.review-editor .el-checkbox__label').click()
 const posted=page.waitForRequest(r=>r.method()==='POST' && new URL(r.url()).pathname===prefix+'/reviews')
 await page.getByRole('button',{name:'保存本版本复核',exact:true}).click()
 const payload=(await posted).postDataJSON()
 await page.locator('.review-save-message').getByText(/已保存/).waitFor();await ready()
 const after=await get(prefix+'/reading-report')
 assert.equal(after.review_history_count,6);assert.equal(after.latest_review.identity.id,user.id)
 assert.equal(after.latest_review.reviewer_authenticated,true);assert.equal(after.latest_review.identity.professional_credential_verified,false)
 assert.equal(after.content_sha256,initial.content_sha256);assert.notEqual(after.export_sha256,initial.export_sha256)
 const text=await page.locator('#report-paper').innerText()
 for(const v of [opinion,user.display_name,'本地账户已验证',c.study_uid,c.series_uid,c.metadata_sha256,after.content_sha256])assert.ok(text.includes(v),v)
 for(const row of after.measurements)assert.ok(text.includes(row.length_mm.toFixed(3)+' mm'))
 await page.locator('.local-auth-box').screenshot({path:out+'/edge-account.png'})
 await page.locator('#report-paper').screenshot({path:out+'/edge-report.png'})
 const download=page.waitForEvent('download',{timeout:120000})
 await page.getByRole('button',{name:'导出 PDF',exact:true}).click()
 const d=await download;await d.saveAs(out+'/edge-account-reading-record.pdf')
 await page.getByText('PDF 报告已导出',{exact:true}).waitFor()
 result.checks.push('Actual installed Edge login, fixed account signature, one source-bound review, stable content/new export revision and real PDF download')
 const cookie=(await context.cookies(api)).find(v=>v.name==='bf_local_session')
 assert.ok(cookie?.httpOnly);assert.equal(cookie.sameSite,'Strict');assert.ok(cookie.expires>Date.now()/1000)
 await fs.writeFile(exp.private+'/browser-cookie-metadata.json',JSON.stringify({httpOnly:cookie.httpOnly,sameSite:cookie.sameSite,persistent:cookie.expires>0},null,2),{flag:'wx'})
 // Explicitly close the entire Edge context/process, then start a new one with the same test profile.
 await context.close();context=null
 await launch()
 assert.equal((await get('/local-auth/session')).user.id,user.id)
 await page.getByRole('button',{name:'退出账户',exact:true}).waitFor()
 const reopened=await get(prefix+'/reading-report')
 for(const key of ['context','content_sha256','export_sha256','latest_review','review_history_count'])assert.deepEqual(reopened[key],after[key],key)
 assert.ok((await page.locator('#report-paper').innerText()).includes(opinion))
 assert.equal((await get(prefix+'/reviews')).total,6)
 await page.locator('.local-auth-box').screenshot({path:out+'/edge-after-natural-close.png'})
 result.checks.push('Graceful close of actual Edge process and reopen of the same isolated persistent profile restores existing server session and saved review without extra write')
 // Explicit logout removes server privilege and remains logged out after a second natural close.
 await page.getByRole('button',{name:'退出账户',exact:true}).click()
 await page.getByRole('button',{name:'登录复核账户',exact:true}).waitFor()
 assert.equal((await get('/local-auth/session')).user,null)
 await context.close();context=null
 await launch();assert.equal((await get('/local-auth/session')).user,null)
 assert.equal(await page.getByRole('button',{name:'保存本版本复核',exact:true}).isDisabled(),true)
 assert.equal((await get(prefix+'/reviews')).total,6)
 result.checks.push('Explicit logout stays logged out after a further process close/reopen; review remains readable and new save disabled')
 await fs.writeFile(root+'/edge-after-save.json',JSON.stringify({report:after,payload},null,2),{flag:'wx'})
 assert.deepEqual(result.pageErrors,[]);assert.equal(result.writes.length,3)
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page?.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{if(context)await context.close();await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result))}
