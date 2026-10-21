// Direct CPU interpreter plus pinned PACS layer, restored data, real HTTP/Edge; no business writes.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import path from 'node:path'
const [root,mode]=process.argv.slice(2);assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'));assert.ok(['capture','first','restart'].includes(mode))
const exp=JSON.parse(await fs.readFile(root+'/expected.json','utf8')),api='http://127.0.0.1:8012',web='http://127.0.0.1:5179'
const manifest=mode==='capture'?null:JSON.parse(await fs.readFile(exp.private+'/snapshot/application/manifest.json','utf8'))
function clean(value,key=''){
 if(['web_path','nifti_url','mask_url','cache_key','updated_utc'].includes(key))return undefined
 if(Array.isArray(value))return value.map(v=>clean(v))
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,clean(v,k)]).filter(([,v])=>v!==undefined))
 if(typeof value==='string'&&path.win32.isAbsolute(value)){
  const p=value.replaceAll('\\','/').toLowerCase();if(manifest){const base=exp.private.toLowerCase()+'/restored/application/'
   const exact=manifest.files.find(v=>base+v.relative.toLowerCase()===p);if(exact)return exact.source.replaceAll('\\','/').toLowerCase()
   for(const m of [...manifest.root_mapping].sort((a,b)=>b.relative.length-a.relative.length)){const prefix=base+m.relative.toLowerCase();if(p===prefix||p.startsWith(prefix+'/'))return m.source.replaceAll('\\','/').toLowerCase()+p.slice(prefix.length)}
  }return p
 }return value
}
const get=async e=>{const r=await fetch(api+e);assert.equal(r.status,200);return (await r.json()).data}
async function science(){const cases=await get('/cases/'),detail=await get('/cases/17/detail'),features=await get('/research/cases/17/features');return clean({case_identities:cases.map(v=>({id:v.id,patient_id:v.patient_id,status:v.status})).sort((a,b)=>a.id-b.id),patient:detail.patient,case:detail.case,analysis:detail.analysis,report:await get('/reports/17'),doctor_verified:detail.mri.doctor_verified,verified_run_id:detail.mri.verified_run_id,clinical:await get('/research/cases/17/clinical-input'),features:features?{id:features.id,state:features.state,clinical_input:features.clinical_input,clinical_input_version:features.clinical_input_version,stale:features.stale,result:features.result}:null})}
if(mode==='capture'){const s=await science();assert.equal(s.case_identities.length,19);await fs.writeFile(root+'/original-scientific-api.json',JSON.stringify(s,null,2),{flag:'wx'});console.log('Captured original scientific API');process.exit(0)}
const state=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'));assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),exp.restored_database);assert.equal(state.backend_python.replaceAll('\\','/'),exp.base_python);assert.equal(state.pacs_runtime_layer.identity_sha256,exp.layer_identity)
assert.deepEqual(await science(),JSON.parse(await fs.readFile(root+'/original-scientific-api.json','utf8')))
const out=root+'/cpu-browser-'+mode;await fs.mkdir(out)
const result={status:'running',mode,writes:[],pageErrors:[],checks:['19 original case identities and NIfTI scientific API fields preserved across CPU runtime/relocation']}
const browser=await chromium.launch({channel:'msedge',headless:true});result.browser=await browser.version()
const context=await browser.newContext({viewport:{width:1600,height:1100},...(mode==='restart'?{storageState:exp.browser_state}:{})}),page=await context.newPage()
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',route=>{const r=route.request();if(!['GET','HEAD'].includes(r.method())){const p=new URL(r.url()).pathname;if(!['/local-auth/login','/local-auth/logout'].includes(p)){result.writes.push({method:r.method(),path:p});return route.abort()}}return route.continue()})
const viaPage=async e=>{const r=await page.request.get(api+e);assert.equal(r.status(),200);return (await r.json()).data}
async function ready(source){await page.waitForFunction(s=>{const e=document.querySelector('.cs-viewer');return e?.dataset.source===s&&['ready','error'].includes(e.dataset.state)},source,{timeout:90000});assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready');assert.equal(await page.locator('.cs-viewport canvas').count(),3)}
async function views(){return page.evaluate(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);return core.getRenderingEngines()[0].getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange,actors:v.getActors().length,dimensions:core.cache.getVolume(v.getVolumeId()).dimensions}))})}
function compare(saved,actual,nifti){actual.forEach((v,i)=>{const c=saved.state.cameras[['axial','sagittal','coronal'][i]];for(const [a,b] of [['focalPoint','focal_point'],['position','position'],['viewPlaneNormal','view_plane_normal'],['viewUp','view_up']])c[b].forEach((n,j)=>assert.ok(Math.abs(n-v.camera[a][j])<.001));assert.ok(Math.abs(c.parallel_scale-v.camera.parallelScale)<.001);assert.deepEqual(v.voi,nifti?saved.state.window_ranges[saved.state.sequence][i]:saved.state.window_ranges[i]);if(nifti)assert.equal(v.actors,saved.state.segmentation_visible?2:1)})}
const c=exp.context,prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
async function login(){await page.getByRole('textbox',{name:'本地账户',exact:true}).fill(exp.doctor.username);await page.getByLabel('账户密码',{exact:true}).fill((await fs.readFile(exp.password_file,'utf8')).trimEnd());await page.getByRole('button',{name:'登录复核账户',exact:true}).click();await page.getByRole('button',{name:'退出账户',exact:true}).waitFor();assert.deepEqual((await viaPage('/local-auth/session')).user,exp.doctor);assert.equal(await page.getByRole('textbox',{name:'复核署名',exact:true}).inputValue(),exp.doctor.display_name)}
try{
 assert.equal((await viaPage('/local-auth/session')).user,null)
 if(mode==='restart')result.checks.push('Old active cookie rejected after backend restart')
 await page.goto(web+'/workstation/17?viewer=cornerstone');await ready('nifti');const n=(await viaPage('/mri/17/view-state')).saved;assert.equal(n.state.sequence,'t1n');compare(n,await views(),true)
 await page.locator('.cs-grid').screenshot({path:out+'/cpu-nifti-saved-view.png'})
 await page.goto(web+`/workstation/19?viewer=cornerstone&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`);await ready('dicom');assert.equal(await page.locator('.cs-measurement-row').count(),36);const d=await viaPage(prefix+'/view-state');compare(d.saved,await views(),false);assert.deepEqual((await views())[0].dimensions,[192,256,192]);await page.locator('.cs-grid').screenshot({path:out+'/cpu-dicom-saved-view.png'})
 result.checks.push('Actual NIfTI and DICOM three-view saved cameras/windows/mask state, 192-frame volume and 36 saved distances loaded using the direct CPU runtime')
 const report=await viaPage(prefix+'/reading-report'),reviews=await viaPage(prefix+'/reviews');assert.equal(reviews.total,7)
 const snapshot=Object.fromEntries(['context','geometry','measurements','doctor_opinion','content_sha256','export_sha256','latest_review','review_history_count'].map(k=>[k,report[k]]))
 if(mode==='first')await fs.writeFile(root+'/cpu-report-before-restart.json',JSON.stringify(snapshot,null,2),{flag:'wx'});else assert.deepEqual(snapshot,JSON.parse(await fs.readFile(root+'/cpu-report-before-restart.json','utf8')))
 await page.goto(web+`/report?case_id=19&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`);await page.locator('#report-paper.dicom-report').waitFor({timeout:90000});await login();await page.locator('.local-auth-box').screenshot({path:out+'/cpu-account-state.png'}).catch(()=>page.screenshot({path:out+'/cpu-account-state.png'}))
 if(mode==='first')await context.storageState({path:exp.browser_state});else{await page.getByRole('button',{name:'退出账户',exact:true}).click();await page.getByRole('button',{name:'登录复核账户',exact:true}).waitFor();assert.equal((await viaPage('/local-auth/session')).user,null)}
 assert.equal((await viaPage(prefix+'/reviews')).total,7);result.checks.push('Restored local account login/fixed attribution works; all seven historical records, review actor and report hashes unchanged; no new review or PDF')
 assert.deepEqual(result.writes,[]);assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png'}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,mode,error:result.error}))}

