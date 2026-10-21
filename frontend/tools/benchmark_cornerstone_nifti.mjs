// One real existing NIfTI case, fresh browser context; warm server/OS caches possible.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const out=process.argv[2]+'/real-nifti-performance'
await fs.mkdir(out)
const browser=await chromium.launch({headless:true})
const page=await browser.newPage({viewport:{width:1500,height:1050}})
const cdp=await page.context().newCDPSession(page)
await cdp.send('Performance.enable')
const result={status:'running',case_id:17,scope:'Single existing real NIfTI case; actual dev viewer; no DICOM import/query or AI timings',
 cache_condition:'fresh_browser_context; server_OS_cache_warm_possible',timing_method:'Node monotonic time until visible ready state; includes browser automation/polling overhead',
 memory_scope:'Cornerstone cache bytes and Chromium renderer JS heap via CDP; excludes GPU memory/process RSS',pageErrors:[],writes:[],sequence_first_selection_ms:{},headers:[]}
page.on('pageerror',e=>result.pageErrors.push(e.message))
await page.route('**/*',async route=>{if(['POST','PUT','PATCH','DELETE'].includes(route.request().method())){result.writes.push(route.request().url());await route.abort()}else await route.continue()})
const ready=async sequence=>{
 await page.waitForFunction(key=>{const e=document.querySelector('.cs-viewer');return e?.dataset.state==='ready'&&(!key||e.dataset.sequence===key)},sequence)
 assert.equal(await page.locator('.cs-viewport canvas').count(),3)
}
const cacheState=()=>page.evaluate(async()=>{
 const core=await import('/node_modules/.vite/deps/@cornerstonejs_core.js')
 const engine=core.getRenderingEngines()[0],view=engine?.getViewports()[0]
 const volume=view&&core.cache.getVolume(view.getVolumeId())
 return {engines:core.getRenderingEngines().length,cache_bytes:core.cache.getCacheSize(),
  dimensions:volume?.dimensions,spacing_xyz_mm:volume?.spacing,index:view?.getCurrentImageIdIndex()}
})
const jsHeap=async()=>Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.filter(m=>['JSHeapUsedSize','JSHeapTotalSize'].includes(m.name)).map(m=>[m.name,m.value]))
try{
 const begin=performance.now()
 await page.goto('http://127.0.0.1:5179/workstation/17?viewer=cornerstone')
 await ready()
 result.first_three_view_ready_ms=performance.now()-begin
 result.initial_sequence=await page.locator('.cs-viewer').getAttribute('data-sequence')
 result.initial_memory={...await cacheState(),...await jsHeap()}
 for(const role of ['t1c','t1n','t2w','t2f']){
  const response=await page.request.get('http://127.0.0.1:8012/mri/17/volume?sequence='+role)
  assert.equal(response.status(),200)
  const data=(await response.json()).data
  result.headers.push({sequence:role,source_revision:data.source_revision})
  if(role===result.initial_sequence)continue
  const started=performance.now()
  await page.locator('.cs-toolbar select').selectOption(role);await ready(role)
  result.sequence_first_selection_ms[role]=performance.now()-started
 }
 result.four_sequence_memory={...await cacheState(),...await jsHeap()}
 assert.deepEqual(result.four_sequence_memory.dimensions,[240,240,155])
 assert.deepEqual(result.four_sequence_memory.spacing_xyz_mm,[1,1,1])
 const started=performance.now()
 await page.locator('.cs-toolbar select').selectOption(result.initial_sequence);await ready(result.initial_sequence)
 result.cached_sequence_return_ms=performance.now()-started
 const before=await cacheState(),box=await page.locator('.cs-viewport').first().boundingBox()
 await page.mouse.move(box.x+box.width/2,box.y+box.height/2)
 const scrolled=performance.now();await page.mouse.wheel(0,120)
 await page.waitForFunction(async prior=>{const core=await import('/node_modules/.vite/deps/@cornerstonejs_core.js');return core.getRenderingEngines()[0]?.getViewports()[0].getCurrentImageIdIndex()!==prior},before.index)
 result.single_scroll_change_ms=performance.now()-scrolled
 result.slice_indices=[before.index,(await cacheState()).index]
 await page.locator('.cs-viewer').screenshot({path:out+'/existing-real-nifti.png'})
 await page.evaluate(()=>{document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/case/17')})
 await page.locator('.pacs-panel').waitFor()
 await page.waitForFunction(async()=>{const core=await import('/node_modules/.vite/deps/@cornerstonejs_core.js');return core.getRenderingEngines().length===0&&core.cache.getCacheSize()===0})
 result.after_exit_memory={...await cacheState(),...await jsHeap()}
 assert.deepEqual(result.pageErrors,[]);assert.deepEqual(result.writes,[])
 result.status='passed'
 result.limitations=['One case/one run; not a statistical latency estimate or throughput guarantee.',
  'No archive upload/query/conversion/inference/feature-extraction measurement; those remain separate P4 tasks.',
  'Renderer JS heap is not total application or GPU memory; no low-resolution sample extrapolation.']
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1}
finally{await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2));await browser.close()}
