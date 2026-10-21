// Installed Microsoft Edge, disposable E-drive profile, actual existing NIfTI and DICOM; business writes blocked.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2]?.replaceAll('\\','/');assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const out=root+'/edge-readonly';await fs.mkdir(out)
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1100}})
const result={status:'running',browser:await browser.version(),channel:'msedge',pageErrors:[],writes:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',route=>{const r=route.request();if(!['GET','HEAD'].includes(r.method())){result.writes.push({method:r.method(),path:new URL(r.url()).pathname});return route.abort()}return route.continue()})
const base='http://127.0.0.1:5179',api='http://127.0.0.1:8012'
async function state(){return page.evaluate(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);return {bytes:core.cache.getCacheSize(),engines:core.getRenderingEngines().map(e=>({id:e.id,views:e.getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange,actors:v.getActors().map(a=>a.referencedId),volume:{dimensions:core.cache.getVolume(v.getVolumeId()).dimensions,spacing:core.cache.getVolume(v.getVolumeId()).spacing}}))}))}})}
async function navigate(path){await page.evaluate(p=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(p),path);await page.waitForURL(u=>u.pathname+u.search===path)}
async function ready(source){await page.waitForFunction(s=>{const e=document.querySelector('.cs-viewer');return e?.dataset.source===s && ['ready','error'].includes(e.dataset.state)},source,{timeout:90000});assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready',await page.locator('.cs-viewer').innerText());assert.equal(await page.locator('.cs-viewport canvas').count(),3)}
async function clean(){await page.waitForTimeout(150);const s=await state();assert.deepEqual(s.engines,[]);assert.equal(s.bytes,0);return s}
async function interactions(source){
 let box=await page.locator('.cs-viewport').first().boundingBox()
 const center=[box.x+box.width/2,box.y+box.height/2]
 let before=await state();await page.mouse.move(...center);await page.mouse.wheel(0,120);await page.waitForTimeout(150)
 assert.notDeepEqual((await state()).engines[0].views[0].camera.focalPoint,before.engines[0].views[0].camera.focalPoint)
 for(const [tool,field] of [['窗宽窗位','voi'],['平移','focalPoint'],['缩放','parallelScale']]){
  await page.getByRole('button',{name:tool,exact:true}).click();before=await state()
  await page.mouse.move(...center);await page.mouse.down();await page.mouse.move(center[0]+35,center[1]+25,{steps:10});await page.mouse.up()
  const after=(await state()).engines[0].views[0],old=before.engines[0].views[0]
  assert.notDeepEqual(field==='voi'?after.voi:after.camera[field],field==='voi'?old.voi:old.camera[field])
 }
 await page.getByRole('button',{name:'重置视图',exact:true}).click()
 await page.getByRole('button',{name:'十字线',exact:true}).click();before=await state()
 await page.mouse.move(...center);await page.mouse.down();await page.mouse.move(center[0]+40,center[1]+20,{steps:10});await page.mouse.up();await page.waitForTimeout(150)
 assert.notDeepEqual((await state()).engines[0].views.map(v=>v.camera.focalPoint),before.engines[0].views.map(v=>v.camera.focalPoint))
 await page.getByRole('button',{name:'重置视图',exact:true}).click()
 const count=await page.locator('.cs-measurement-row').count()
 await page.getByRole('button',{name:'距离测量',exact:true}).click()
 box=await page.locator('.cs-viewport').first().boundingBox()
 const start=[Math.round(box.x+box.width*.43),Math.round(box.y+box.height*.48)],end=[Math.round(box.x+box.width*.56),Math.round(box.y+box.height*.48)+24]
 const distance=await page.evaluate(async({local})=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);const v=core.getRenderingEngines()[0].getViewports()[0];const [a,b]=local.map(p=>v.canvasToWorld(p));return Math.hypot(...a.map((n,i)=>b[i]-n))},{local:[start,end].map(p=>[p[0]-box.x,p[1]-box.y])})
 await page.mouse.move(...start);await page.mouse.down();await page.mouse.move(...end,{steps:10});await page.mouse.up()
 await page.waitForFunction(n=>document.querySelectorAll('.cs-measurement-row').length===n,count+1)
 const draft=page.locator('.cs-measurement-row[data-saved-id=""]');assert.equal(await draft.count(),1)
 const mm=Number((await draft.innerText()).match(/([\d.]+) mm/)[1]);assert.ok(Math.abs(mm-distance)<.01)
 await draft.getByRole('button',{name:'删除测量',exact:true}).click();assert.equal(await page.locator('.cs-measurement-row').count(),count)
 result.checks.push(source+': real wheel/window/pan/zoom/crosshair, unsaved physical-mm line and local deletion; no save or business write')
}
try{
 await page.goto(base+'/workstation/17?viewer=cornerstone');await ready('nifti')
 await interactions('NIfTI')
 const position=await state()
 for(const key of ['t1c','t1n','t2w','t2f']){
  await page.locator('.cs-toolbar select').selectOption(key)
  await page.waitForFunction(k=>document.querySelector('.cs-viewer')?.dataset.sequence===k && document.querySelector('.cs-viewer')?.dataset.state==='ready',key,{timeout:90000})
  const s=await state();assert.equal(s.engines[0].views.length,3)
  s.engines[0].views.forEach((v,i)=>{assert.equal(v.actors.length,2);v.camera.focalPoint.forEach((n,j)=>assert.ok(Math.abs(n-position.engines[0].views[i].camera.focalPoint[j])<.001))})
 }
 const maskPoint=await page.evaluate(async()=>{
  const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name),engine=core.getRenderingEngines()[0]
  const actor=engine.getViewports()[0].getActors().find(a=>a.referencedId?.endsWith('-mask'));const mask=core.cache.getVolume(actor.referencedId),s=mask.voxelManager.getCompleteScalarDataArray()
  let i=s.length-1;while(i>=0 && !s[i])i--;if(i<0)throw Error('Expected real nonempty mask')
  const [x,y]=mask.dimensions,point=mask.imageData.indexToWorld([i%x,Math.floor(i/x)%y,Math.floor(i/(x*y))])
  for(const v of engine.getViewports()){const c=v.getCamera(),normal=c.viewPlaneNormal,d=point.reduce((sum,n,j)=>sum+(n-c.focalPoint[j])*normal[j],0);v.setCamera({focalPoint:c.focalPoint.map((n,j)=>n+normal[j]*d),position:c.position.map((n,j)=>n+normal[j]*d)})}
  engine.render();return point
 })
 await page.waitForTimeout(250);const shown=await page.locator('.cs-grid').screenshot({path:out+'/nifti-nonempty-mask.png'})
 await page.getByRole('button',{name:'隐藏分割',exact:true}).click();await ready('nifti');await page.waitForTimeout(150)
 ;(await state()).engines[0].views.forEach(v=>assert.equal(v.actors.length,1))
 const hidden=await page.locator('.cs-grid').screenshot({path:out+'/nifti-mask-hidden.png'});assert.notDeepEqual(shown,hidden)
 await page.getByRole('button',{name:'显示分割',exact:true}).click();await ready('nifti')
 result.maskPointLps=maskPoint;result.checks.push('NIfTI four real sequences preserve physical position; nonempty original read-only mask changes rendered pixels when toggled')
 await navigate('/case/17');result.niftiExit=await clean()
 const candidate=(await (await page.request.get(api+'/pacs/import-candidates')).json()).data.items[0]
 const path=`/workstation/19?viewer=cornerstone&source=dicom&study_uid=${candidate.study_uid}&series_uid=${candidate.series_uid}`
 await navigate(path);await ready('dicom');await interactions('DICOM')
 const d=await state();assert.deepEqual(d.engines[0].views[0].volume.dimensions,[192,256,192])
 const directions=await page.locator('.cs-direction').allTextContents();assert.equal(directions.length,12);assert.ok(directions.every(t=>/^[LRAPSI]+$/.test(t)))
 assert.equal(await page.getByRole('button',{name:/显示分割|隐藏分割/}).count(),0)
 await page.locator('.cs-viewer').screenshot({path:out+'/dicom-edge-three-views.png'})
 await navigate('/case/19');result.dicomExit=await clean()
 await navigate('/workstation/17?viewer=cornerstone');await ready('nifti')
 assert.equal(await page.locator('.cs-measurement-row[data-saved-id=""]').count(),0)
 await page.locator('.cs-viewer').screenshot({path:out+'/nifti-return.png'})
 await navigate('/case/17');await clean()
 assert.deepEqual(result.writes,[]);assert.deepEqual(result.pageErrors,[])
 result.checks.push('Actual NIfTI→DICOM→NIfTI case switch and route exits clear engines/cache/drafts, DICOM direction labels and unsupported mask controls correct')
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify({status:result.status,browser:result.browser,checks:result.checks,error:result.error}))}
