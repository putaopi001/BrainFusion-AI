// Real archived MR; business writes restricted to this run's isolated DB.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const [root,mode,tag]=process.argv.slice(2)
if(!root?.startsWith('E:/BrainFusion-Runtime/results/nightly/') || !['create','restart','readonly'].includes(mode)) throw Error('Fresh run root and create/restart/readonly required')
const registry=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
if(mode!=='readonly') assert.equal(registry.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),root+'/database-backup/restored-validation.db')
const candidate=(await (await fetch('http://127.0.0.1:8012/pacs/import-candidates')).json()).data.items[0]
const prefix=`/pacs/cases/19/studies/${candidate.study_uid}/series/${candidate.series_uid}`
const endpoint=prefix+'/measurements'
const url=`http://127.0.0.1:5179/workstation/19?source=dicom&study_uid=${candidate.study_uid}&series_uid=${candidate.series_uid}`
const output=root+'/dicom-measure-'+mode+(tag?'-'+tag:'')
await fs.mkdir(output)
const result={status:'running',mode,pageErrors:[],writes:[],checks:[]}
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1100}})
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{
 const req=route.request()
 if(!['GET','HEAD'].includes(req.method())) {
  assert.notEqual(mode,'readonly','Read-only lifecycle probe must never send business writes')
  const path=new URL(req.url()).pathname
  assert.ok(path===endpoint || (req.method()==='DELETE' && path.startsWith(endpoint+'/')),path)
  result.writes.push({method:req.method(),path,body:req.postDataJSON()})
 }
 await route.continue()
})
const records=async()=>{
 const r=await page.request.get('http://127.0.0.1:8012'+endpoint)
 assert.equal(r.status(),200,await r.text())
 return (await r.json()).data
}
async function open(){
 await page.goto(url)
 await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.cs-viewer')?.dataset.state),null,{timeout:90000})
 assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready',await page.locator('.cs-viewer').innerText())
 assert.equal(await page.locator('.cs-viewer').getAttribute('data-source'),'dicom')
}
async function annotations(){
 return page.evaluate(async()=>{
  const tools=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_tools\.js/.test(r.name)).name)
  const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name)
  return {engines:core.getRenderingEngines().length,cacheBytes:core.cache.getCacheSize(),
   allAnnotations:tools.annotation.state.getAllAnnotations().map(a=>({tool:a.metadata.toolName,frame:a.metadata.FrameOfReferenceUID})),
   lengths:tools.annotation.state.getAllAnnotations().filter(a=>a.metadata.toolName==='Length').map(a=>({
    uid:a.annotationUID,points:a.data.handles.points,frame:a.metadata.FrameOfReferenceUID,
    owner:a.metadata.bfMeasurementSession,locked:tools.annotation.locking.isAnnotationLocked(a.annotationUID),stats:a.data.cachedStats}))}
 })
}
try{
 await open()
 if(mode==='readonly'){
  assert.equal((await records()).items.length,0)
  await page.screenshot({path:output+'/original-runtime-ready.png',fullPage:true})
  await page.getByRole('button',{name:'距离测量',exact:true}).click()
  const box=await page.locator('.cs-viewport').first().boundingBox()
  await page.mouse.click(box.x+box.width*.43,box.y+box.height*.48)
  await page.getByText('正在绘制测量；按 Esc 取消。',{exact:true}).waitFor()
  assert.equal(await page.getByRole('button',{name:'重置视图',exact:true}).isDisabled(),true)
  await page.keyboard.press('Escape')
  assert.equal((await annotations()).lengths.length,0)
  await page.mouse.move(box.x+box.width*.43,box.y+box.height*.48);await page.mouse.down()
  await page.mouse.move(box.x+box.width*.56,box.y+box.height*.52,{steps:12});await page.mouse.up()
  await page.locator('.cs-measurement-row').waitFor()
  const frame=(await records()).context.frame_of_reference_uid
  // Use the router owned by the mounted app. Reimporting a bare Vite module
  // after HMR can create a second router that changes URL without the view.
  await page.evaluate(async()=>{await document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/workstation/17?viewer=cornerstone')})
  await page.waitForURL('**/workstation/17?viewer=cornerstone')
  await page.waitForFunction(()=>{const v=document.querySelector('.cs-viewer');return v?.dataset.state==='ready' && v.dataset.source==='nifti'},null,{timeout:90000})
  assert.equal(await page.locator('.cs-viewer').getAttribute('data-source'),'nifti')
  result.afterCaseSwitch=await annotations()
  assert.equal(result.afterCaseSwitch.engines,1)
  assert.equal(result.afterCaseSwitch.lengths.length,0)
  assert.ok(!result.afterCaseSwitch.allAnnotations.some(a=>a.frame===frame))
  await page.getByRole('button',{name:'返回病例',exact:false}).click()
  await page.waitForFunction(()=>!document.querySelector('.cs-viewer'))
  result.afterLeave=await annotations()
  assert.equal(result.afterLeave.engines,0);assert.equal(result.afterLeave.cacheBytes,0)
  await open();assert.equal((await records()).items.length,0)
  assert.equal(await page.locator('.cs-measurement-row').count(),0)
  result.checks.push('Original runtime: incomplete draw Esc, drawing lock, unsaved DICOM draft removed on same-component case switch to NIfTI, old FrameOfReference annotations absent, route cleanup, no writes')
 }else if(mode==='create'){
  assert.equal((await records()).items.length,0)
  const expected=[]
  let drop=true
  await page.route('**'+endpoint,async route=>{
   if(route.request().method()==='POST' && drop){
    drop=false
    const response=await route.fetch();assert.equal(response.status(),200,await response.text())
    result.lostResponseCommitted=(await response.json()).data.id
    await route.abort()
   }else await route.fallback()
  })
  for(let i=0;i<3;i++){
   await page.getByRole('button',{name:'距离测量',exact:true}).click()
   const box=await page.locator('.cs-viewport').nth(i).boundingBox()
   const start=[Math.round(box.x+box.width*.43),Math.round(box.y+box.height*.48)]
   const end=[Math.round(box.x+box.width*.56),start[1]+24]
   const world=await page.evaluate(async({i,local})=>{
    const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name)
    return local.map(p=>core.getRenderingEngines()[0].getViewports()[i].canvasToWorld(p))
   },{i,local:[start,end].map(p=>[p[0]-box.x,p[1]-box.y])})
   await page.mouse.move(...start);await page.mouse.down();await page.mouse.move(...end,{steps:12});await page.mouse.up()
   await page.waitForFunction(n=>document.querySelectorAll('.cs-measurement-row').length===n,i+1)
   await page.getByRole('button',{name:'保存测量',exact:true}).click()
   if(i===0){
    await page.getByText(/保存失败/).waitFor()
    assert.equal((await records()).items.length,1)
    await page.getByRole('button',{name:'保存测量',exact:true}).click()
   }
   await page.waitForFunction(n=>document.querySelectorAll('.cs-measurement-row:not([data-saved-id=""])').length===n,i+1)
   const item=(await records()).items.at(-1)
   world.forEach((point,k)=>point.forEach((v,j)=>assert.ok(Math.abs(item.points_lps[k][j]-v)<.001)))
   assert.ok(Math.abs(item.length_mm-Math.hypot(...world[1].map((v,j)=>v-world[0][j])))<.001)
   expected.push(item)
  }
  await page.waitForTimeout(300)
  result.annotations=await annotations()
  assert.equal(result.annotations.lengths.length,3)
  for(const a of result.annotations.lengths){
   assert.ok(a.owner);assert.equal(a.locked,true)
   assert.equal(a.frame,expected[0].context.frame_of_reference_uid)
   assert.ok(Object.values(a.stats||{}).some(s=>s.unit==='mm' && Math.abs(s.length-Math.hypot(...a.points[1].map((v,j)=>v-a.points[0][j])))<.001),JSON.stringify(a))
  }
  await fs.writeFile(root+'/dicom-measurements-expected.json',JSON.stringify(expected,null,2),{flag:'wx'})
  await page.screenshot({path:output+'/saved-three-planes.png',fullPage:true})
  await page.reload();await page.waitForFunction(()=>document.querySelector('.cs-viewer')?.dataset.state==='ready',null,{timeout:90000})
  assert.equal(await page.locator('.cs-measurement-row').count(),3)
  const restored=(await annotations()).lengths
  for(const item of expected) assert.ok(restored.some(a=>a.locked && JSON.stringify(a.points)===JSON.stringify(item.points_lps)))
  result.checks.push('Real mouse on all three patient-axis planes; mm statistics; response loss idempotence; refresh restores locked world points')
 }else{
  const expected=JSON.parse(await fs.readFile(root+'/dicom-measurements-expected.json','utf8'))
  assert.deepEqual((await records()).items,expected)
  assert.equal((await annotations()).lengths.length,3)
  await page.screenshot({path:output+'/after-restart.png',fullPage:true})
  // Router navigation must dispose only this session and its rendering cache.
  await page.getByRole('button',{name:'返回病例',exact:false}).click()
  await page.waitForFunction(()=>!document.querySelector('.cs-viewer'))
  result.afterLeave=await annotations()
  assert.equal(result.afterLeave.engines,0);assert.equal(result.afterLeave.lengths.length,0)
  assert.equal(result.afterLeave.cacheBytes,0)
  await open()
  assert.equal(await page.locator('.cs-measurement-row').count(),3)
  for(const item of expected){
   await page.locator(`.cs-measurement-row[data-saved-id="${item.id}"]`).getByRole('button',{name:'删除测量'}).click()
   await page.waitForFunction(id=>!document.querySelector(`.cs-measurement-row[data-saved-id="${id}"]`),item.id)
  }
  assert.equal((await records()).items.length,0)
  await page.reload();await page.waitForFunction(()=>document.querySelector('.cs-viewer')?.dataset.state==='ready',null,{timeout:90000})
  assert.equal(await page.locator('.cs-measurement-row').count(),0)
  assert.equal((await annotations()).lengths.length,0)
  result.checks.push('Service restart restores same records; route leave releases annotations/engine/cache; reopen restores; delete and refresh remain empty')
 }
 assert.deepEqual(result.pageErrors,[])
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:output+'/failure.png',fullPage:true});process.exitCode=1}
finally{await fs.writeFile(output+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
