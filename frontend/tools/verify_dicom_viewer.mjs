// Real app + explicit synthetic WADO pixels; never clinical/PACS acceptance.
import { chromium } from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2],suffix=process.argv[3]||'dev',out=root+'/browser-dicom-'+suffix
await fs.mkdir(out)
const manifest=JSON.parse(await fs.readFile(root+'/SYNTHETIC-view-manifest.json','utf8'))
const base='http://127.0.0.1:5179',study=manifest.study_uid,series=manifest.series_uid
const target='/workstation/17?viewer=cornerstone&source=dicom&study_uid='+study+'&series_uid='+series
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1500,height:1050}})
const result={scope:'SYNTHETIC protocol only; no true DICOM archive, no model/doctor acceptance',status:'running',pageErrors:[],writes:[],frames:[],checks:[]}
result.consoleErrors=[];result.networkErrors=[]
page.on('console',m=>{if(['error','warning'].includes(m.type()))result.consoleErrors.push(m.text())})
page.on('requestfailed',r=>result.networkErrors.push({url:r.url(),error:r.failure()?.errorText}))
let mode='valid'
let mockPanel=false
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{
 const req=route.request(),url=new URL(req.url())
 if(['POST','PUT','PATCH','DELETE'].includes(req.method())){result.writes.push(url.pathname);await route.abort();return}
 if(mockPanel && url.pathname.startsWith('/pacs/') && !url.pathname.startsWith('/pacs/cases/17/studies/')){
  let data
  if(url.pathname==='/pacs/status')data={read_available:true,message:'SYNTHETIC 工程夹具：不是实际归档',pixel_read_enabled:true}
  else if(url.pathname==='/pacs/import-candidates')data={items:[]}
  else if(url.pathname.endsWith('/links'))data={items:[{id:900,archive_id:manifest.archive_id,study_uid:study,archive_matches_config:true}]}
  else if(url.pathname.endsWith('/conversions'))data={state:'not_registered',items:[],message:'SYNTHETIC 无转换版本登记'}
  else if(url.pathname==='/pacs/studies')data={items:[{study_uid:study,modalities:['MR']}],next_offset:null}
  else if(url.pathname.endsWith('/series'))data={items:[{series_uid:series,modality:'MR'}],next_offset:null}
  else if(url.pathname.endsWith('/instances'))data={items:manifest.instances.map(row=>({instance_uid:row.instance_uid})),next_offset:null}
  else if(url.pathname.endsWith('/view-manifest'))data=manifest
  else throw Error('Unexpected synthetic panel route '+url.pathname)
  await route.fulfill({contentType:'application/json',body:JSON.stringify({code:200,data})});return
 }
 if(url.pathname.endsWith('/view-manifest')&&url.pathname.startsWith('/pacs/cases/')){
  await route.fulfill({contentType:'application/json',body:JSON.stringify({code:200,data:manifest})});return
 }
 if(url.pathname.includes('/frames/')){
  result.frames.push({path:url.pathname,url:url.href,mode})
  if(mode==='fail'||(mode==='partial'&&url.pathname.includes('/instances/2.25.708/'))){
   await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:{message:'SYNTHETIC 实例版本变化，拒绝像素读取。'}})});return
  }
  if(mode==='slow')await new Promise(resolve=>setTimeout(resolve,2500))
  const uid=url.pathname.split('/instances/')[1].split('/')[0],k=Number(uid.split('.').at(-1))-700
  const pixels=Buffer.alloc(32*24*2)
  for(let r=0;r<24;r++)for(let c=0;c<32;c++)pixels.writeInt16LE(k*200+r*3+c-800,(r*32+c)*2)
  const boundary='BF_SYNTHETIC_ONLY'
  const body=Buffer.concat([Buffer.from('--'+boundary+'\r\nContent-Type: application/octet-stream; transfer-syntax=1.2.840.10008.1.2.1\r\n\r\n'),pixels,Buffer.from('\r\n--'+boundary+'--\r\n')])
  if(!page.isClosed())await route.fulfill({contentType:'multipart/related; type="application/octet-stream"; boundary="'+boundary+'"; transfer-syntax=1.2.840.10008.1.2.1',body}).catch(()=>{})
  return
 }
 await route.continue()
})
async function navigate(path){
 await page.evaluate(path=>{document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(path)},path)
 await page.waitForURL(url=>url.pathname+url.search===path)
}
async function ready(){
 await page.waitForFunction(()=>{const v=document.querySelector('.cs-viewer[data-source="dicom"]');return v && v.dataset.state!=='loading'},null,{timeout:75000})
 const state=await page.locator('.cs-viewer').getAttribute('data-state')
 assert.equal(state,'ready',state==='ready'?'':await page.locator('.cs-error').textContent())
}
async function inspectViews(){
 return page.evaluate(async()=>{const c=await import('/node_modules/.vite/deps/@cornerstonejs_core.js');return c.getRenderingEngines()[0].getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange,index:v.getCurrentImageIdIndex()}))})
}
async function cleanCache(){
 if(!suffix.startsWith('dev'))return
 const checkedIds=[...new Set(result.frames.map(row=>'bfwado:'+row.url))]
 const clean=await page.evaluate(async checkedIds=>{
  const c=await import('/node_modules/.vite/deps/@cornerstonejs_core.js')
  const m=await import('/node_modules/@cornerstonejs/dicom-image-loader/dist/esm/imageLoader/wadors/metaDataManager.js')
  return {engines:c.getRenderingEngines().length,bytes:c.cache.getCacheSize(),remaining:[...window.bfTestImageIds,...checkedIds].filter(id=>c.cache.getImageLoadObject(id)||m.default.get(id)).length}
 },checkedIds)
 assert.deepEqual(clean,{engines:0,bytes:0,remaining:0});result.cleanup=clean
}
try{
 await page.goto(base+'/case/17')
 const panel=page.locator('.pacs-panel')
 await panel.getByRole('button',{name:'刷新归档状态',exact:true}).waitFor()
 mockPanel=true
 await panel.getByRole('button',{name:'刷新归档状态',exact:true}).click()
 await panel.getByText('SYNTHETIC 工程夹具：不是实际归档',{exact:true}).waitFor()
 await panel.getByRole('button',{name:'查询检查',exact:true}).click()
 await panel.locator('.el-table__body tr').first().click()
 await panel.getByText(series,{exact:true}).first().click()
 await page.waitForFunction(()=>!document.querySelector('.pacs-panel').classList.contains('is-busy'))
 await panel.getByRole('button',{name:'核对序列空间',exact:true}).click()
 await panel.getByRole('button',{name:'Cornerstone 阅片（工程验证）',exact:true}).click()
 await ready()
 result.checks.push('Actual case UI, then explicitly synthetic linked study/series entry routes existing viewer without writes; no assumption that the real archive is unconfigured')
 assert.equal(await page.locator('.cs-viewport canvas').count(),3)
 await page.getByText(/SYNTHETIC 合成协议夹具/).waitFor()
 for(const name of ['距离测量','保存测量','保存视图','显示分割','隐藏分割'])assert.equal(await page.getByRole('button',{name,exact:true}).count(),0)
 result.checks.push('Explicit SYNTHETIC source; 3 MPR canvases; unsupported persistence/mask/AI controls absent')
 // Import the same Vite core module used by the mounted component. No new router.
 if(suffix.startsWith('dev')){
  result.voxels=await page.evaluate(async()=>{
   const core=await import('/node_modules/.vite/deps/@cornerstonejs_core.js')
   const engine=core.getRenderingEngines()[0],vp=engine.getViewports()[0],volume=core.cache.getVolume(vp.getVolumeId())
   let errors=0,count=0
   const scalar=volume.voxelManager.getCompleteScalarDataArray()
   window.bfTestImageIds=[...volume.imageIds]
   for(let k=0;k<9;k++)for(let r=0;r<24;r++)for(let c=0;c<32;c++){
    if(scalar[k*32*24+r*32+c]!==k*200+r*3+c-800)errors++;count++
   }
   const point=volume.imageData.indexToWorld([31,23,8])
   const expected=[10-31*2*.6-8*2,20-31*2*.8+8*1.5,30+23*3.25]
   return {count,errors,dimensions:volume.dimensions,spacing:volume.spacing,world:point,expected,geometryCorrect:point.every((v,i)=>Math.abs(v-expected[i])<.002)}
  })
  assert.equal(result.voxels.count,6912);assert.equal(result.voxels.errors,0);assert.ok(result.voxels.geometryCorrect)
  result.checks.push('All 6912 signed original pixels and independent oblique LPS corner match')
 }
 const view=page.locator('.cs-viewport').first()
 for(const name of ['窗宽窗位','平移','缩放','十字线']){
  await page.getByRole('button',{name,exact:true}).click()
  const box=await view.boundingBox()
  const before=suffix.startsWith('dev')?await inspectViews():null
  if(name==='十字线' && suffix.startsWith('dev')){
   // Use an independently selected in-volume point instead of a screen
   // percentage that can fall outside this thin oblique synthetic object.
   const point=await page.evaluate(async()=>{
    const c=await import('/node_modules/.vite/deps/@cornerstonejs_core.js')
    const engine=c.getRenderingEngines()[0],vp=engine.getViewports()[0],vol=c.cache.getVolume(vp.getVolumeId())
    const world=vol.imageData.indexToWorld([18,12,4]),canvas=vp.worldToCanvas(world)
    const state=document.querySelector('.cs-viewer').__vueParentComponent.setupState
    window.bfCrosshairEvents=[]
    vp.element.addEventListener(state.toolEnums.Events.MOUSE_DOWN,e=>window.bfCrosshairEvents.push({world:e.detail.currentPoints.world,buttons:e.detail.buttons}))
    const tool=state.group.getToolInstance('Crosshairs')
    return {canvas,world,active:state.activeTool,center:[...tool.toolCenter],options:state.group.toolOptions.Crosshairs,viewportBox:vp.element.getBoundingClientRect().toJSON()}
   })
   result.crosshairTarget=point
   await page.mouse.click(box.x+point.canvas[0],box.y+point.canvas[1])
  }else if(name==='十字线'){
   await page.mouse.click(box.x+box.width*.65,box.y+box.height*.65)
  }else{
   await page.mouse.move(box.x+box.width*.45,box.y+box.height*.45);await page.mouse.down()
   await page.mouse.move(box.x+box.width*.55,box.y+box.height*.55,{steps:8});await page.mouse.up()
  }
  // Installed 5.7 delays a single click for its 400 ms double-click window.
  await page.waitForTimeout(name==='十字线'?600:100)
  if(before){
   const after=await inspectViews();result.interactions||={};result.interactions[name]={before,after}
   if(name==='十字线')result.crosshairEvents=await page.evaluate(()=>window.bfCrosshairEvents)
   if(name==='窗宽窗位')assert.notDeepEqual(after[0].voi,before[0].voi)
   else if(name==='缩放')assert.notEqual(after[0].camera.parallelScale,before[0].camera.parallelScale)
   else if(name==='十字线')assert.ok(after.slice(1).some((v,i)=>JSON.stringify(v.camera.focalPoint)!==JSON.stringify(before[i+1].camera.focalPoint)))
   else assert.notDeepEqual(after[0].camera.focalPoint,before[0].camera.focalPoint)
  }
 }
 const beforeScroll=suffix.startsWith('dev')?await inspectViews():null
 await page.mouse.wheel(0,120);await page.waitForTimeout(350)
 if(beforeScroll){const after=await inspectViews();assert.notEqual(after[0].index,beforeScroll[0].index);result.scroll={before:beforeScroll[0].index,after:after[0].index}}
 await page.getByRole('button',{name:'重置视图',exact:true}).click()
 await page.locator('.cs-viewer').screenshot({path:out+'/SYNTHETIC-three-views.png'})
 result.checks.push('Window/pan/zoom/crosshair/scroll/reset interactions remain ready')
 if(suffix.startsWith('dev')){
  const before=result.frames.length
  await navigate(target.replace('series_uid='+series,'series_uid=2.25.999'))
  await page.locator('.cs-viewer[data-state="error"]').waitFor()
  assert.equal(result.frames.length,before)
  await page.getByText(/DICOM 来源、病例关联或像素读取契约不完整/).waitFor()
  await navigate('/case/17');await page.locator('.pacs-panel').waitFor();await cleanCache()
  mode='partial';await navigate(target)
  await page.locator('.cs-viewer[data-state="error"]').waitFor({timeout:75000})
  assert.equal(await page.locator('.cs-viewer[data-state="ready"]').count(),0)
  assert.equal(result.frames.filter(row=>row.mode==='partial').length,9)
  await page.locator('.cs-viewer').screenshot({path:out+'/SYNTHETIC-partial-frame-refusal.png'})
  result.checks.push('Direct series switch rejects wrong manifest before pixels; 1-of-9 frame failure never reports ready')
 }
 await navigate('/case/17');await page.locator('.pacs-panel').waitFor()
 await cleanCache()
 mode='fail';await navigate(target)
 await page.locator('.cs-viewer[data-state="error"]').waitFor({timeout:90000})
 assert.equal(await page.locator('.mri-viewer').count(),0)
 await page.locator('.cs-viewer').screenshot({path:out+'/SYNTHETIC-version-refusal.png'})
 result.checks.push('HTTP409 is explicit failure; no silent Canvas/NIfTI fallback')
 await page.getByRole('button',{name:'打开当前病例 NIfTI',exact:true}).click()
 await page.locator('.cs-viewer[data-source="nifti"][data-state="ready"]').waitFor({timeout:45000})
 assert.equal(await page.locator('.cs-viewport canvas').count(),3)
 result.checks.push('Only explicit user NIfTI selection opens original real case 3 views')
 await navigate('/case/17');await page.locator('.pacs-panel').waitFor()
 mode='slow';await navigate(target);await page.locator('.cs-viewer[data-state="loading"]').waitFor()
 await page.waitForTimeout(300);await navigate('/case/17');await page.locator('.pacs-panel').waitFor();await page.waitForTimeout(3000)
 assert.equal(await page.locator('.cs-viewer').count(),0)
 await cleanCache()
 result.checks.push('Mid-load SPA exit cancels without stale view or late mount')
 assert.equal(result.pageErrors.length,0,result.pageErrors.join('\n'));assert.equal(result.writes.length,0)
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page.screenshot({path:out+'/failed.png',fullPage:true});throw e}
finally{await fs.writeFile(out+'/result.json',JSON.stringify(result,null,2));await browser.close()}
