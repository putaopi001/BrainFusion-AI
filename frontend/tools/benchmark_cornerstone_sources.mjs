// Bounded real Edge viewer observations: read-only; fresh browser per source; no claim of OS-cold cache or peak GPU memory.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
import {execFileSync} from 'node:child_process'
const root=process.argv[2]?.replaceAll('\\','/');assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const out=root+'/viewer-profile';await fs.mkdir(out)
const state=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8')),archive=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/orthanc-local/process.json','utf8'))
const bindings=[{pid:state.backend_pid,role:'backend',expected_started_utc:state.backend_start_utc},{pid:state.frontend_pid,role:'vite-dev-server',expected_started_utc:state.frontend_start_utc},{pid:archive.pid,role:'orthanc',expected_started_utc:archive.started_utc}]
const result={status:'running',started_utc:new Date().toISOString(),method:{browser:'Installed Microsoft Edge, headless, viewport1600x1100',cache:'Fresh Edge process/context for each source, HTTP cache disabled; server/OS/file caches not cleared; NIfTI cached switches use existing in-memory volumes.',load_timing:'Node monotonic time from page.goto to viewer ready + 3 canvases + two animation frames; includes automation and frontend startup.',slice_timing:'Browser monotonic time from pre-wheel marker to first IMAGE_RENDERED on axial viewport with a changed image index; includes command delivery, excludes later memory probes.',memory:'Boundary samples via Windows Get-Process and browser SystemInfo process IDs; working-set sums can double-count shared pages, private commit is not resident RAM, lifetime peak belongs to entire process lifetime. No sampled max is called an exact interaction peak or GPU memory.'},queries:[],sources:[],writes:[],pageErrors:[]}
let browser
const api='http://127.0.0.1:8012',base='http://127.0.0.1:5179'
async function get(path){const start=performance.now(),r=await fetch(api+path);assert.equal(r.status,200);const body=await r.json();return {data:body.data,wall_ms:performance.now()-start}}
const category=url=>{const p=new URL(url).pathname;return /\/frames\/1$/.test(p)?'dicom-frame':/view-manifest$/.test(p)?'dicom-manifest':/\.nii(?:\.gz)?$/.test(p)?'nifti-file':/\/mri\/.*\/volume$/.test(p)?'nifti-header':/\/mri\/.*\/segmentation$/.test(p)?'segmentation-status':p.startsWith('/pacs/')?'pacs-other':p.startsWith('/mri/')?'mri-other':/node_modules|src\/|@vite/.test(p)?'frontend-code':'other'}
async function profile(source,url){
 browser=await chromium.launch({channel:'msedge',headless:true});const context=await browser.newContext({viewport:{width:1600,height:1100}}),page=await context.newPage()
 const browserCDP=await browser.newBrowserCDPSession(),cdp=await context.newCDPSession(page)
 await cdp.send('Network.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});await cdp.send('Performance.enable')
 const p={source,browser:await browser.version(),load_ms:null,sequences:[],slices:[],memory:[],network:[],pageErrors:[],writes:[]}
 result.sources.push(p)
 page.on('pageerror',e=>p.pageErrors.push(e.message))
 await page.route('**/*',route=>{if(!['GET','HEAD'].includes(route.request().method())){p.writes.push({method:route.request().method(),category:category(route.request().url())});return route.abort()}return route.continue()})
 page.on('requestfinished',req=>{const t=req.timing();p.network.push({category:category(req.url()),duration_ms:t.responseEnd,phase:p.phase??'startup'})})
 await page.addInitScript(()=>{globalThis.__bfInitialRenders=[];document.addEventListener('CORNERSTONE_IMAGE_RENDERED',e=>globalThis.__bfInitialRenders.push({at:performance.now(),viewport:e.detail?.viewportId}),true)})
 async function inspect(){return page.evaluate(async()=>{const resource=performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name));const core=await import(resource.name),views=core.getRenderingEngines()[0]?.getViewports()??[],v=views[0],volume=v&&core.cache.getVolume(v.getVolumeId());return {engines:core.getRenderingEngines().length,cache_bytes:core.cache.getCacheSize(),dimensions:volume?.dimensions,spacing_xyz_mm:volume?.spacing,index:v?.getCurrentImageIdIndex(),views:views.map(v=>({id:v.id,focal:v.getCamera().focalPoint,actors:v.getActors().length})),initial_rendered_viewports:[...new Set(globalThis.__bfInitialRenders.map(e=>e.viewport))]}})}
 async function ready(sequence){await page.waitForFunction(({source,sequence})=>{const e=document.querySelector('.cs-viewer');return e?.dataset.source===source && ['ready','error'].includes(e.dataset.state) && (!sequence||e.dataset.sequence===sequence)}, {source,sequence},{timeout:90000});assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready',await page.locator('.cs-viewer').innerText());assert.equal(await page.locator('.cs-viewport canvas').count(),3);await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))}
 async function memory(stage){
  const info=(await browserCDP.send('SystemInfo.getProcessInfo')).processInfo
  const list=bindings.concat(info.map(v=>({pid:v.id,role:'edge-'+v.type})))
  const raw=execFileSync('pwsh',['-NoProfile','-File','E:/BrainFusion-AI/backend/tools/measure_viewer_memory.ps1','-BindingsJson',JSON.stringify(list)],{encoding:'utf8',windowsHide:true,maxBuffer:1024*1024})
  const rows=JSON.parse(raw.replace(/^\uFEFF/,'')),metrics=Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.filter(v=>['JSHeapUsedSize','JSHeapTotalSize'].includes(v.name)).map(v=>[v.name,v.value]))
  p.memory.push({stage,...rows,renderer_js_heap_metrics:metrics,browser_cpu_time_seconds:info.map(v=>({pid:v.id,type:v.type,cpuTime:v.cpuTime})),viewer:stage==='before-navigation'?null:await inspect()})
 }
 p.phase='before-navigation';await memory(p.phase)
 p.phase='first-load';let start=performance.now();await page.goto(url);await ready();p.load_ms=performance.now()-start
 p.initial=await inspect();assert.equal(p.initial.initial_rendered_viewports.length,3)
 assert.deepEqual(p.initial.dimensions,source==='nifti'?[240,240,155]:[192,256,192])
 p.initial_sequence=await page.locator('.cs-viewer').getAttribute('data-sequence');await memory('first-ready')
 if(source==='nifti'){
  for(const key of ['t1c','t1n','t2w'].filter(v=>v!==p.initial_sequence)){
   p.phase='first-sequence-'+key;start=performance.now();await page.locator('.cs-toolbar select').selectOption(key);await ready(key)
   p.sequences.push({sequence:key,kind:'first-selection-in-this-browser',wall_ms:performance.now()-start})
  }
  for(const key of [p.initial_sequence,'t1c',p.initial_sequence]){
   p.phase='cached-sequence-'+key;start=performance.now();await page.locator('.cs-toolbar select').selectOption(key);await ready(key)
   p.sequences.push({sequence:key,kind:'existing-in-memory-volume',wall_ms:performance.now()-start})
  }
  await memory('four-sequences-ready')
 }else{p.sequence_switch='Not measured: only one supported real DICOM series is present; no fabricated four-sequence switch.'}
 await page.evaluate(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name),v=core.getRenderingEngines()[0].getViewports()[0];globalThis.__bfSliceEvents=[];globalThis.__bfAxial=v;v.element.addEventListener('CORNERSTONE_IMAGE_RENDERED',()=>{globalThis.__bfSliceEvents.push({at:performance.now(),index:v.getCurrentImageIdIndex()})})})
 const box=await page.locator('.cs-viewport').first().boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5)
 for(let i=0;i<3;i++){
  const before=await page.evaluate(()=>({index:globalThis.__bfAxial.getCurrentImageIdIndex(),start:performance.now(),events:globalThis.__bfSliceEvents.length}))
  p.phase='slice-'+(i+1);await page.mouse.wheel(0,120)
  await page.waitForFunction(b=>globalThis.__bfSliceEvents.slice(b.events).some(e=>e.at>=b.start && e.index!==b.index),before,{timeout:15000})
  const rendered=await page.evaluate(b=>globalThis.__bfSliceEvents.slice(b.events).find(e=>e.at>=b.start && e.index!==b.index),before)
  p.slices.push({from:before.index,to:rendered.index,to_changed_image_rendered_ms:rendered.at-before.start})
 }
 await memory('after-three-slices');await page.locator('.cs-grid').screenshot({path:out+'/'+source+'-profile-view.png'})
 p.phase='route-exit';await page.evaluate(source=>document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/case/'+(source==='nifti'?17:19)),source)
 await page.waitForFunction(()=>!document.querySelector('.cs-viewer'));await page.waitForTimeout(150)
 p.after_exit=await inspect();assert.equal(p.after_exit.engines,0);assert.equal(p.after_exit.cache_bytes,0)
 await memory('after-route-exit')
 assert.deepEqual(p.pageErrors,[]);assert.deepEqual(p.writes,[])
 p.status='passed';await browser.close();browser=null
}
try{
 const candidate=(await get('/pacs/import-candidates')).data.items[0];assert.ok(candidate)
 for(const [name,path] of [['study-query','/pacs/studies?study_uid='+candidate.study_uid],['series-query',`/pacs/studies/${candidate.study_uid}/series`]]){
  const q=await get(path);result.queries.push({name,wall_ms:q.wall_ms,scope:'single authenticated backend DICOMweb query, including local HTTP and JSON; excludes upload/archive writes'})
 }
 await profile('nifti',base+'/workstation/17?viewer=cornerstone')
 await profile('dicom',base+`/workstation/19?source=dicom&study_uid=${candidate.study_uid}&series_uid=${candidate.series_uid}`)
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1}
finally{
 if(browser)await browser.close();result.finished_utc=new Date().toISOString()
 await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'})
 console.log(JSON.stringify({status:result.status,sources:result.sources.map(p=>({source:p.source,status:p.status,load_ms:p.load_ms,sequences:p.sequences,slices:p.slices,memory_samples:p.memory.length})),queries:result.queries,error:result.error}))
}
