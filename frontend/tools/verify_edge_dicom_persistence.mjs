// Edge DICOM persistence through a real process close: physical points and presentation are separate records.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2]?.replaceAll('\\','/');assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const exp=JSON.parse(await fs.readFile(root+'/expected.json','utf8')),base='http://127.0.0.1:5179',api='http://127.0.0.1:8012'
const state=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'));assert.equal(state.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),exp.database)
const c=exp.report.context,prefix=`/pacs/cases/19/studies/${c.study_uid}/series/${c.series_uid}`
const url=`${base}/workstation/19?viewer=cornerstone&source=dicom&study_uid=${c.study_uid}&series_uid=${c.series_uid}`
const out=root+'/edge-dicom-persistence';await fs.mkdir(out)
const result={status:'running',pageErrors:[],writes:[],checks:[]};let context,page
const get=async path=>{const response=await page.request.get(api+path);assert.equal(response.status(),200,await response.text());return (await response.json()).data}
async function launch(){
 context=await chromium.launchPersistentContext(exp.private+'/edge-view-profile',{channel:'msedge',headless:true,viewport:{width:1600,height:1100}})
 page=context.pages()[0]??await context.newPage();result.browserVersion=context.browser()?.version()
 page.on('pageerror',e=>result.pageErrors.push(e.message))
 await page.route('**/*',route=>{const req=route.request();if(!['GET','HEAD'].includes(req.method())){const path=new URL(req.url()).pathname;assert.ok((req.method()==='POST' && [prefix+'/measurements',prefix+'/view-state'].includes(path)) || (req.method()==='DELETE' && path===prefix+'/measurements/'+result.newMeasurement?.id));result.writes.push({method:req.method(),path})}return route.continue()})
 await page.goto(url);await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.cs-viewer')?.dataset.state),null,{timeout:90000})
 assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready',await page.locator('.cs-viewer').innerText())
}
async function inspect(){return page.evaluate(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);const tools=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_tools\.js/.test(r.name)).name);return {views:core.getRenderingEngines()[0].getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange})),lengths:tools.annotation.state.getAllAnnotations().filter(a=>a.metadata.toolName==='Length').map(a=>({points:a.data.handles.points,locked:tools.annotation.locking.isAnnotationLocked(a.annotationUID)}))}})}
function compareView(expected,actual){actual.views.forEach((v,i)=>{const c=expected.state.cameras[['axial','sagittal','coronal'][i]];for(const [camel,snake] of [['focalPoint','focal_point'],['position','position'],['viewPlaneNormal','view_plane_normal'],['viewUp','view_up']])c[snake].forEach((n,j)=>assert.ok(Math.abs(n-v.camera[camel][j])<.001));assert.ok(Math.abs(c.parallel_scale-v.camera.parallelScale)<.001);assert.deepEqual(v.voi,expected.state.window_ranges[i])})}
try{
 await launch()
 const originalMeasurements=(await get(prefix+'/measurements')).items,originalView=(await get(prefix+'/view-state')).saved,originalReport=await get(prefix+'/reading-report')
 assert.equal(originalMeasurements.length,36);assert.equal(originalReport.review_history_count,6)
 const initial=await inspect()
 for(let i=0;i<3;i++){
  const b=await page.locator('.cs-viewport').nth(i).boundingBox()
  await page.mouse.move(b.x+b.width*.5,b.y+b.height*.5);await page.mouse.wheel(0,120*(i+1));await page.waitForTimeout(150)
  for(const tool of ['平移','缩放','窗宽窗位']){await page.getByRole('button',{name:tool,exact:true}).click();await page.mouse.move(b.x+b.width*.45,b.y+b.height*.45);await page.mouse.down();await page.mouse.move(b.x+b.width*.51,b.y+b.height*.50,{steps:10});await page.mouse.up()}
 }
 const changed=await inspect()
 initial.views.forEach((v,i)=>{assert.notDeepEqual(v.camera.focalPoint,changed.views[i].camera.focalPoint);assert.notEqual(v.camera.parallelScale,changed.views[i].camera.parallelScale);assert.notDeepEqual(v.voi,changed.views[i].voi)})
 await page.getByRole('button',{name:'保存视图',exact:true}).click();await page.getByText(/视图已保存/).waitFor()
 const savedView=(await get(prefix+'/view-state')).saved
 assert.notEqual(savedView.id,originalView.id);compareView(savedView,changed)
 await page.getByRole('button',{name:'距离测量',exact:true}).click()
 const b=await page.locator('.cs-viewport').first().boundingBox(),start=[Math.round(b.x+b.width*.42),Math.round(b.y+b.height*.46)],end=[Math.round(b.x+b.width*.58),Math.round(b.y+b.height*.54)]
 const world=await page.evaluate(async local=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);return local.map(p=>core.getRenderingEngines()[0].getViewports()[0].canvasToWorld(p))},[start,end].map(p=>[p[0]-b.x,p[1]-b.y]))
 await page.mouse.move(...start);await page.mouse.down();await page.mouse.move(...end,{steps:12});await page.mouse.up()
 await page.locator('.cs-measurement-row[data-saved-id=""]').waitFor()
 await page.getByRole('button',{name:'保存测量',exact:true}).click()
 await page.waitForFunction(()=>document.querySelectorAll('.cs-measurement-row:not([data-saved-id=""])').length===37)
 const current=(await get(prefix+'/measurements')).items
 const added=current.find(v=>!originalMeasurements.some(o=>o.id===v.id));assert.ok(added);result.newMeasurement=added
 assert.equal(current.length,37)
 world.forEach((p,i)=>p.forEach((n,j)=>assert.ok(Math.abs(n-added.points_lps[i][j])<.001)))
 assert.ok(Math.abs(added.length_mm-Math.hypot(...world[0].map((n,i)=>n-world[1][i])))<.001)
 const stale=await get(prefix+'/reading-report');assert.notEqual(stale.content_sha256,originalReport.content_sha256);assert.equal(stale.latest_review.current,false)
 await page.locator('.cs-grid').screenshot({path:out+'/edge-saved-view.png'})
 result.checks.push('Edge real mouse modifies all three cameras/VOIs, saves a new immutable view and one physical-mm line; report content changes and previous account review becomes stale')
 await context.close();context=null;await launch()
 const reopened=await inspect();compareView(savedView,reopened)
 assert.deepEqual((await get(prefix+'/measurements')).items,current)
 assert.ok(reopened.lengths.some(a=>a.locked && JSON.stringify(a.points)===JSON.stringify(added.points_lps)))
 await page.locator('.cs-grid').screenshot({path:out+'/edge-reopened-view.png'})
 result.checks.push('New Edge process with same isolated profile restores persisted three-camera/VOI version and locked LPS points, length tolerance below 0.001 mm')
 const row=page.locator(`.cs-measurement-row[data-saved-id="${added.id}"]`)
 await row.getByRole('button',{name:'删除测量',exact:true}).click()
 await page.waitForFunction(id=>!document.querySelector(`.cs-measurement-row[data-saved-id="${id}"]`),added.id)
 assert.deepEqual((await get(prefix+'/measurements')).items,originalMeasurements)
 await page.reload();await page.waitForFunction(()=>document.querySelector('.cs-viewer')?.dataset.state==='ready',null,{timeout:90000})
 assert.equal(await page.locator('.cs-measurement-row').count(),36);compareView(savedView,await inspect())
 await page.getByRole('button',{name:'返回病例',exact:false}).click();await page.waitForFunction(()=>!document.querySelector('.cs-viewer'))
 const cleanup=await page.evaluate(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);return {engines:core.getRenderingEngines().length,cache:core.cache.getCacheSize()}})
 assert.deepEqual(cleanup,{engines:0,cache:0})
 result.checks.push('Only the new saved distance deleted through Edge; refresh retains all 36 old distances and new view, route exit disposes engine and cache')
 result.savedView=savedView;result.cleanup=cleanup
 assert.deepEqual(result.pageErrors,[]);assert.equal(result.writes.length,3);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page?.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{if(context)await context.close();await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result))}
