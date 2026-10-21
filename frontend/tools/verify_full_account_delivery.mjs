// Full multicase application + archive + formal account recovery. Never write the original database.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import path from 'node:path'
const [rawRoot,mode]=process.argv.slice(2),root=rawRoot?.replaceAll('\\','/')
assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'));assert.ok(['capture','save','restart'].includes(mode))
const exp=JSON.parse(await fs.readFile(root+'/expected.json','utf8')),api='http://127.0.0.1:8012',web='http://127.0.0.1:5179'
const registered=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
if(mode!=='capture')assert.equal(registered.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),exp.restored_database)
let manifest=null
if(mode!=='capture')manifest=JSON.parse(await fs.readFile(exp.private+'/snapshot/application/manifest.json','utf8'))
function clean(value,key=''){
 if(['web_path','nifti_url','mask_url','cache_key','updated_utc'].includes(key))return undefined
 if(Array.isArray(value))return value.map(v=>clean(v))
 if(value && typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,clean(v,k)]).filter(([,v])=>v!==undefined))
 if(typeof value==='string' && path.win32.isAbsolute(value)){
  let p=value.replaceAll('\\','/').toLowerCase()
  if(manifest){const base=exp.private.toLowerCase()+'/restored/application/'
   const exact=manifest.files.find(v=>base+v.relative.toLowerCase()===p)
   if(exact)return exact.source.replaceAll('\\','/').toLowerCase()
   for(const mapping of [...manifest.root_mapping].sort((a,b)=>b.relative.length-a.relative.length)){
    const prefix=base+mapping.relative.toLowerCase()
    if(p===prefix||p.startsWith(prefix+'/'))return mapping.source.replaceAll('\\','/').toLowerCase()+p.slice(prefix.length)
   }
  }
  return p
 }
 return value
}
const get=async endpoint=>{const r=await fetch(api+endpoint);assert.equal(r.status,200);return (await r.json()).data}
async function science(){
 const cases=await get('/cases/'),detail=await get('/cases/17/detail'),features=await get('/research/cases/17/features')
 return clean({case_identities:cases.map(v=>({id:v.id,patient_id:v.patient_id,status:v.status})).sort((a,b)=>a.id-b.id),patient:detail.patient,case:detail.case,analysis:detail.analysis,report:await get('/reports/17'),doctor_verified:detail.mri.doctor_verified,verified_run_id:detail.mri.verified_run_id,clinical:await get('/research/cases/17/clinical-input'),features:features?{id:features.id,state:features.state,clinical_input:features.clinical_input,clinical_input_version:features.clinical_input_version,stale:features.stale,result:features.result}:null})
}
if(mode==='capture'){
 const signature=await science();await fs.writeFile(root+'/original-scientific-api.json',JSON.stringify(signature,null,2),{flag:'wx'});console.log(JSON.stringify({status:'passed',mode,case_count:signature.case_identities.length}));process.exit(0)
}
const out=root+'/full-account-browser-'+mode;await fs.mkdir(out)
const c=exp.report.context,prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const result={status:'running',mode,writes:[],pageErrors:[],checks:[]}
const browser=await chromium.launch({channel:'msedge',headless:true}),context=await browser.newContext({viewport:{width:1600,height:1100}}),page=await context.newPage()
result.browser=await browser.version();page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',route=>{const r=route.request();if(!['GET','HEAD'].includes(r.method())){const p=new URL(r.url()).pathname;assert.ok(['/local-auth/login',prefix+'/reviews'].includes(p));result.writes.push({method:r.method(),path:p})}return route.continue()})
const viaPage=async endpoint=>{const r=await page.request.get(api+endpoint);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
async function viewer(source){await page.waitForFunction(source=>{const e=document.querySelector('.cs-viewer');return e?.dataset.source===source && ['ready','error'].includes(e.dataset.state)},source,{timeout:90000});assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready',await page.locator('.cs-viewer').innerText())}
async function cameras(){return page.evaluate(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);return core.getRenderingEngines()[0].getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange,actors:v.getActors().length}))})}
function compareCameras(saved,actual,nifti){actual.forEach((v,i)=>{const c=saved.state.cameras[['axial','sagittal','coronal'][i]];for(const [camel,snake] of [['focalPoint','focal_point'],['position','position'],['viewPlaneNormal','view_plane_normal'],['viewUp','view_up']])c[snake].forEach((n,j)=>assert.ok(Math.abs(n-v.camera[camel][j])<.001));assert.ok(Math.abs(c.parallel_scale-v.camera.parallelScale)<.001);assert.deepEqual(v.voi,nifti?saved.state.window_ranges[saved.state.sequence][i]:saved.state.window_ranges[i]);if(nifti)assert.equal(v.actors,saved.state.segmentation_visible?2:1)})}
async function reportReady(){await page.locator('#report-paper.dicom-report').waitFor({timeout:90000});await page.waitForFunction(()=>!document.querySelector('.report-toolbar .el-button.is-loading'))}
async function login(){
 const password=(await fs.readFile(exp.password_file,'utf8')).trimEnd()
 await page.getByRole('textbox',{name:'本地账户',exact:true}).fill(exp.doctor.username)
 await page.getByLabel('账户密码',{exact:true}).fill(password)
 await page.getByRole('button',{name:'登录复核账户',exact:true}).click();await page.getByRole('button',{name:'退出账户',exact:true}).waitFor()
 const session=await viaPage('/local-auth/session');assert.deepEqual(session.user,exp.doctor);return session
}
try{
 assert.deepEqual(await science(),JSON.parse(await fs.readFile(root+'/original-scientific-api.json','utf8')))
 result.checks.push('All case identities and representative NIfTI patient/clinical/analysis/report/feature scientific API fields survive full path relocation without inference or extraction')
 if(mode==='save'){
  await page.goto(web+'/workstation/17?viewer=cornerstone');await viewer('nifti')
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-sequence'),'t1n');assert.deepEqual((await viaPage('/mri/17/view-state')).saved,exp.nifti_view);compareCameras(exp.nifti_view,await cameras(),true)
  await page.locator('.cs-grid').screenshot({path:out+'/full-restored-nifti-view.png'})
  await page.evaluate(()=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/workstation/1?viewer=cornerstone'));await viewer('nifti')
  assert.equal(await page.locator('.cs-measurement-row').count(),0)
  await page.evaluate(c=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(`/workstation/19?source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`),c);await viewer('dicom')
  assert.equal(await page.locator('.cs-measurement-row').count(),36)
  const view=(await viaPage(prefix+'/view-state')).saved;compareCameras(view,await cameras(),false)
  await page.locator('.cs-grid').screenshot({path:out+'/full-restored-dicom-view.png'})
  result.checks.push('Actual full restored model/artifact directories serve NIfTI17 saved T1n/hidden-mask/cameras, another real case1 and DICOM19 persisted cameras/36 distances without case contamination')
 }
 await page.goto(web+`/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`);await reportReady()
 const report=await viaPage(prefix+'/reading-report')
 if(mode==='save'){
  for(const key of ['context','geometry','measurements','doctor_opinion','content_sha256','export_sha256','latest_review','review_history_count'])assert.deepEqual(report[key],exp.report[key],key)
  assert.equal((await viaPage(prefix+'/reviews')).total,6)
  await login();assert.equal(await page.getByRole('textbox',{name:'复核署名',exact:true}).inputValue(),exp.doctor.display_name)
  await page.getByRole('textbox',{name:'本版本复核意见',exact:true}).fill('完整多病例本机恢复工程验收：本地账户、来源与历史版本保持；此记录不核验医师资质，不作临床诊断。')
  await page.locator('.review-editor .el-checkbox__label').click()
  const posted=page.waitForRequest(r=>r.method()==='POST' && new URL(r.url()).pathname===prefix+'/reviews')
  await page.getByRole('button',{name:'保存本版本复核',exact:true}).click();const payload=(await posted).postDataJSON()
  await page.locator('.review-save-message').getByText(/已保存/).waitFor();await reportReady()
  const after=await viaPage(prefix+'/reading-report');assert.equal(after.review_history_count,7);assert.equal(after.latest_review.identity.id,exp.doctor.id)
  assert.equal(after.latest_review.reviewer_authenticated,true);assert.equal(after.latest_review.identity.professional_credential_verified,false)
  assert.equal(after.content_sha256,report.content_sha256);assert.notEqual(after.export_sha256,report.export_sha256)
  await page.reload();await reportReady();assert.equal((await viaPage('/local-auth/session')).user.id,exp.doctor.id)
  await page.locator('.dicom-review-paper').screenshot({path:out+'/full-restored-account-review.png'})
  const cookie=(await context.cookies(api)).find(v=>v.name==='bf_local_session');assert.ok(cookie?.httpOnly)
  await fs.writeFile(exp.private+'/active-session-before-restart.token',cookie.value,{flag:'wx'})
  await fs.writeFile(root+'/after-full-account-save.json',JSON.stringify({report:after,payload},null,2),{flag:'wx'})
  result.checks.push('Restored original formal account logs in with stable ID, old six engineering histories remain unchanged, one new current review saved/refreshed and export revision changes')
 }else{
  const expected=JSON.parse(await fs.readFile(root+'/after-full-account-save.json','utf8'))
  for(const key of ['context','content_sha256','export_sha256','latest_review','review_history_count'])assert.deepEqual(report[key],expected.report[key],key)
  const token=await fs.readFile(exp.private+'/active-session-before-restart.token','utf8')
  const old=await page.request.get(api+'/local-auth/session',{headers:{Cookie:'bf_local_session='+token}});assert.equal((await old.json()).data.user,null)
  const session=await login()
  const retry=await page.request.post(api+prefix+'/reviews',{data:expected.payload,headers:{'X-BF-CSRF':session.csrf}});assert.equal(retry.status(),200,await retry.text());assert.equal((await retry.json()).data.id,expected.report.latest_review.id)
  result.writes.push({method:'POST',path:prefix+'/reviews',scope:'Same-client-UID API retry after actual app restart'})
  assert.equal((await viaPage(prefix+'/reviews')).total,7)
  await page.locator('.paper-header').screenshot({path:out+'/full-restart-report-header.png'})
  result.checks.push('Actual restored archive/app restart retains account-owned version/history and science, old active token is invalid, restored account re-login and same-UID retry does not duplicate')
 }
 assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,mode,checks:result.checks,error:result.error}))}
