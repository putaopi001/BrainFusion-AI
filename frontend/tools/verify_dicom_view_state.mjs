// Real local DICOM; writes confined to a run-owned business database copy.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [root,mode]=process.argv.slice(2)
if(!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/') || !['save','restart','readonly'].includes(mode)) throw Error('Run root and save/restart/readonly required')
const registered=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
if(mode!=='readonly') assert.equal(registered.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),root+'/database-backup/restored-validation.db')
const candidate=(await (await fetch('http://127.0.0.1:8012/pacs/import-candidates')).json()).data.items[0]
const endpoint=`/pacs/cases/19/studies/${candidate.study_uid}/series/${candidate.series_uid}/view-state`
const target=`http://127.0.0.1:5179/workstation/19?source=dicom&study_uid=${candidate.study_uid}&series_uid=${candidate.series_uid}`
const output=root+'/dicom-view-'+mode
await fs.mkdir(output)
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1100}})
const result={status:'running',mode,pageErrors:[],writes:[],checks:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{
 const req=route.request()
 if(!['GET','HEAD'].includes(req.method())){
  assert.notEqual(mode,'readonly','No write authorized in original runtime check')
  assert.equal(new URL(req.url()).pathname,endpoint);assert.equal(req.method(),'POST')
  result.writes.push(req.postDataJSON())
 }
 await route.continue()
})
async function inspect(){return page.evaluate(async()=>{
 const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name)
 return core.getRenderingEngines()[0].getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange}))
})}
async function ready(){
 await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.cs-viewer')?.dataset.state),null,{timeout:90000})
 assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready',await page.locator('.cs-viewer').innerText())
 assert.equal(await page.locator('.cs-viewer').getAttribute('data-source'),'dicom')
}
async function saved(){
 const r=await page.request.get('http://127.0.0.1:8012'+endpoint);assert.equal(r.status(),200,await r.text())
 return (await r.json()).data.saved
}
function compare(expected,actual){
 actual.forEach((view,i)=>{
  const c=expected.state.cameras[['axial','sagittal','coronal'][i]]
  for(const [camel,snake] of [['focalPoint','focal_point'],['position','position'],['viewPlaneNormal','view_plane_normal'],['viewUp','view_up']]){
   c[snake].forEach((v,j)=>assert.ok(Math.abs(v-view.camera[camel][j])<.001,`${i} ${camel} ${v} != ${view.camera[camel][j]}`))
  }
  assert.ok(Math.abs(c.parallel_scale-view.camera.parallelScale)<.001)
  assert.deepEqual(view.voi,expected.state.window_ranges[i])
 })
}
try{
 await page.goto(target);await ready()
 assert.equal(await page.getByRole('button',{name:'保存视图',exact:true}).count(),1)
 if(mode==='save'){
  assert.equal(await saved(),null)
  result.initial=await inspect()
  for(let i=0;i<3;i++){
   const box=await page.locator('.cs-viewport').nth(i).boundingBox()
   await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.wheel(0,120*(i+1))
   await page.waitForTimeout(150)
   for(const label of ['平移','缩放','窗宽窗位']){
    await page.getByRole('button',{name:label,exact:true}).click()
    await page.mouse.move(box.x+box.width*.45,box.y+box.height*.45);await page.mouse.down()
    await page.mouse.move(box.x+box.width*.51,box.y+box.height*.50,{steps:10});await page.mouse.up()
   }
  }
  result.beforeSave=await inspect()
  result.initial.forEach((v,i)=>{
   assert.notDeepEqual(v.camera.focalPoint,result.beforeSave[i].camera.focalPoint)
   assert.notEqual(v.camera.parallelScale,result.beforeSave[i].camera.parallelScale)
   assert.notDeepEqual(v.voi,result.beforeSave[i].voi)
  })
  let drop=true
  await page.route('**'+endpoint,async route=>{
   if(route.request().method()==='POST' && drop){
    drop=false;result.writes.push(route.request().postDataJSON())
    const r=await route.fetch();assert.equal(r.status(),200,await r.text())
    result.lostResponseCommitted=(await r.json()).data.id;await route.abort()
   }else await route.fallback()
  })
  await page.getByRole('button',{name:'保存视图',exact:true}).click()
  await page.getByText(/视图保存失败/).waitFor()
  assert.equal((await saved()).id,result.lostResponseCommitted)
  await page.getByRole('button',{name:'保存视图',exact:true}).click()
  await page.getByText(/视图已保存/).waitFor()
  const expected=await saved();assert.equal(expected.id,result.lostResponseCommitted)
  assert.equal(result.writes[0].client_uid,result.writes[1].client_uid)
  compare(expected,result.beforeSave)
  await fs.writeFile(root+'/dicom-view-expected.json',JSON.stringify(expected,null,2),{flag:'wx'})
  await page.screenshot({path:output+'/saved-view.png',fullPage:true})
  await page.reload();await ready();await page.getByText(/已恢复保存视图/).waitFor()
  result.afterRefresh=await inspect();compare(expected,result.afterRefresh)
  await page.getByRole('button',{name:'重置视图',exact:true}).click()
  assert.notDeepEqual(await inspect(),result.afterRefresh)
  assert.deepEqual(await saved(),expected)
  await page.reload();await ready();compare(expected,await inspect())
  result.checks.push('Real scroll/pan/zoom/window in all three DICOM planes; response loss retry deduplicates; reload exactly restores physical cameras and three VOIs; reset does not overwrite saved version')
 }else if(mode==='restart'){
  const expected=JSON.parse(await fs.readFile(root+'/dicom-view-expected.json','utf8'))
  assert.deepEqual(await saved(),expected)
  result.afterRestart=await inspect();compare(expected,result.afterRestart)
  await page.screenshot({path:output+'/after-service-restart.png',fullPage:true})
  // Controlled stale saved-record response, without changing real PACS data.
  await page.route('**'+endpoint,async route=>{
   const response=await route.fetch();const body=await response.json()
   body.data.saved.current=false;body.data.saved.context.metadata_sha256='0'.repeat(64)
   await route.fulfill({response,json:body})
  })
  await page.reload();await ready();await page.getByText(/旧DICOM视图属于其他/).waitFor()
  result.controlledStaleView=await inspect()
  assert.notDeepEqual(result.controlledStaleView,result.afterRestart)
  assert.equal(result.writes.length,0)
  result.checks.push('Actual services restart restores same immutable view; controlled stale saved version shows notice and keeps default DICOM view without applying historical camera/window')
 }else{
  assert.equal(await saved(),null)
  await page.screenshot({path:output+'/original-runtime-ready.png',fullPage:true})
  await page.getByRole('button',{name:'返回病例',exact:false}).click()
  await page.waitForFunction(()=>!document.querySelector('.cs-viewer'))
  result.checks.push('Original runtime: new save-view control available, no test view or write persisted; route exits cleanly')
 }
 assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:output+'/failure.png',fullPage:true});process.exitCode=1}
finally{await fs.writeFile(output+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
