// Installed Edge with a fresh E-drive persistent profile; only this run's SQLite copy may be written.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import assert from 'node:assert/strict'
const root=process.argv[2]?.replaceAll('\\','/');assert.ok(root?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const registration=JSON.parse(await fs.readFile('E:/BrainFusion-Runtime/local/processes.json','utf8'))
assert.equal(registration.runtime_paths.DATABASE_PATH.replaceAll('\\','/'),root+'/database-backup/restored-validation.db')
const out=root+'/edge-nifti',profile='E:/BrainFusion-Runtime/backups/'+root.split('/').at(-1)+'/edge-profile';await fs.mkdir(out)
const api='http://127.0.0.1:8012',url='http://127.0.0.1:5179/workstation/17?viewer=cornerstone'
const result={status:'running',pageErrors:[],writes:[],checks:[],created:[]};let context,page
const get=async path=>{const r=await page.request.get(api+path);assert.equal(r.status(),200,await r.text());return (await r.json()).data}
async function ready(sequence){await page.waitForFunction(()=>['ready','error'].includes(document.querySelector('.cs-viewer')?.dataset.state),null,{timeout:90000});assert.equal(await page.locator('.cs-viewer').getAttribute('data-state'),'ready',await page.locator('.cs-viewer').innerText());assert.equal(await page.locator('.cs-viewer').getAttribute('data-source'),'nifti');if(sequence)assert.equal(await page.locator('.cs-viewer').getAttribute('data-sequence'),sequence)}
async function launch(){
 context=await chromium.launchPersistentContext(profile,{channel:'msedge',headless:true,viewport:{width:1600,height:1100}})
 result.browserVersion=context.browser()?.version();page=context.pages()[0]??await context.newPage()
 page.on('pageerror',e=>result.pageErrors.push(e.message))
 await page.route('**/*',route=>{const r=route.request();if(!['GET','HEAD'].includes(r.method())){const p=new URL(r.url()).pathname;assert.ok((r.method()==='POST' && ['/mri/17/measurements','/mri/17/view-state'].includes(p)) || (r.method()==='DELETE' && result.created.some(v=>p==='/mri/17/measurements/'+v.id)));result.writes.push({method:r.method(),path:p})}return route.continue()})
 await page.goto(url);await ready()
}
async function inspect(){return page.evaluate(async()=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name),tools=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_tools\.js/.test(r.name)).name);return {views:core.getRenderingEngines()[0].getViewports().map(v=>({camera:v.getCamera(),voi:v.getProperties().voiRange,actors:v.getActors().map(a=>a.referencedId)})),lengths:tools.annotation.state.getAllAnnotations().filter(a=>a.metadata.toolName==='Length').map(a=>({points:a.data.handles.points,locked:tools.annotation.locking.isAnnotationLocked(a.annotationUID),stats:a.data.cachedStats}))}})}
function compare(saved,state){state.views.forEach((v,i)=>{const c=saved.state.cameras[['axial','sagittal','coronal'][i]];for(const [camel,snake] of [['focalPoint','focal_point'],['position','position'],['viewPlaneNormal','view_plane_normal'],['viewUp','view_up']])c[snake].forEach((n,j)=>assert.ok(Math.abs(n-v.camera[camel][j])<.001));assert.ok(Math.abs(c.parallel_scale-v.camera.parallelScale)<.001);assert.deepEqual(v.voi,saved.state.window_ranges[saved.state.sequence][i]);assert.equal(v.actors.length,saved.state.segmentation_visible?2:1)})}
try{
 await launch()
 const old=(await get('/mri/17/measurements')).items,oldCanvas=await get('/mri/17/annotations')
 assert.equal(old.length,0);assert.equal((await get('/mri/17/view-state')).saved,null)
 for(let i=0;i<3;i++){
  await page.getByRole('button',{name:'距离测量',exact:true}).click();const b=await page.locator('.cs-viewport').nth(i).boundingBox()
  const start=[Math.round(b.x+b.width*.43),Math.round(b.y+b.height*.48)],end=[Math.round(b.x+b.width*.56),start[1]+24]
  const world=await page.evaluate(async({i,local})=>{const core=await import(performance.getEntriesByType('resource').find(r=>/\/@cornerstonejs_core\.js/.test(r.name)).name);return local.map(p=>core.getRenderingEngines()[0].getViewports()[i].canvasToWorld(p))},{i,local:[start,end].map(p=>[p[0]-b.x,p[1]-b.y])})
  await page.mouse.move(...start);await page.mouse.down();await page.mouse.move(...end,{steps:12});await page.mouse.up()
  await page.waitForFunction(n=>document.querySelectorAll('.cs-measurement-row').length===n,i+1)
  await page.getByRole('button',{name:'保存测量',exact:true}).click()
  await page.waitForFunction(n=>document.querySelectorAll('.cs-measurement-row:not([data-saved-id=""])').length===n,i+1)
  const added=(await get('/mri/17/measurements')).items.at(-1)
  world.forEach((p,k)=>p.forEach((n,j)=>assert.ok(Math.abs(n-added.points_lps[k][j])<.001)))
  assert.ok(Math.abs(added.length_mm-Math.hypot(...world[0].map((n,j)=>n-world[1][j])))<.001)
  result.created.push(added)
 }
 await page.locator('.cs-toolbar select').selectOption('t1n');await ready('t1n')
 const before=await inspect()
 for(let i=0;i<3;i++){
  const b=await page.locator('.cs-viewport').nth(i).boundingBox();await page.mouse.move(b.x+b.width*.5,b.y+b.height*.5);await page.mouse.wheel(0,120*(i+1));await page.waitForTimeout(150)
  for(const label of ['平移','缩放','窗宽窗位']){await page.getByRole('button',{name:label,exact:true}).click();await page.mouse.move(b.x+b.width*.45,b.y+b.height*.45);await page.mouse.down();await page.mouse.move(b.x+b.width*.51,b.y+b.height*.50,{steps:10});await page.mouse.up()}
 }
 await page.getByRole('button',{name:'隐藏分割',exact:true}).click();await ready('t1n')
 const changed=await inspect();before.views.forEach((v,i)=>{assert.notDeepEqual(v.camera.focalPoint,changed.views[i].camera.focalPoint);assert.notEqual(v.camera.parallelScale,changed.views[i].camera.parallelScale);assert.notDeepEqual(v.voi,changed.views[i].voi)})
 await page.getByRole('button',{name:'保存视图',exact:true}).click();await page.getByText(/视图已保存/).waitFor()
 const saved=(await get('/mri/17/view-state')).saved
 assert.equal(saved.current,true);assert.equal(saved.state.sequence,'t1n');assert.equal(saved.state.segmentation_visible,false);compare(saved,changed)
 await page.locator('.cs-grid').screenshot({path:out+'/edge-nifti-saved-view.png'})
 result.checks.push('Three actual NIfTI plane mouse distances saved with independent LPS length tolerance <0.001mm; three cameras/windows changed and explicit T1n/hidden original mask view saved')
 await context.close();context=null;await launch();await ready('t1n')
 assert.deepEqual((await get('/mri/17/measurements')).items,result.created);assert.deepEqual((await get('/mri/17/view-state')).saved,saved)
 const reopened=await inspect();compare(saved,reopened)
 for(const item of result.created)assert.ok(reopened.lengths.some(a=>a.locked && JSON.stringify(a.points)===JSON.stringify(item.points_lps)))
 await page.locator('.cs-grid').screenshot({path:out+'/edge-nifti-reopened-view.png'})
 result.checks.push('Whole Edge process graceful close and same test-profile relaunch restores saved T1n, hidden-mask flag, three physical cameras/VOIs and all three locked distances')
 const position=reopened.views.map(v=>v.camera.focalPoint)
 for(const key of ['t1c','t2w','t2f','t1n']){
  await page.locator('.cs-toolbar select').selectOption(key);await ready(key)
  const now=await inspect();now.views.forEach((v,i)=>v.camera.focalPoint.forEach((n,j)=>assert.ok(Math.abs(n-position[i][j])<.001)))
  for(const item of result.created)assert.ok(now.lengths.some(a=>a.locked && JSON.stringify(a.points)===JSON.stringify(item.points_lps)))
  assert.deepEqual((await get('/mri/17/measurements')).items,result.created)
 }
 for(const item of result.created){await page.locator(`.cs-measurement-row[data-saved-id="${item.id}"]`).getByRole('button',{name:'删除测量',exact:true}).click();await page.waitForFunction(id=>!document.querySelector(`.cs-measurement-row[data-saved-id="${id}"]`),item.id)}
 assert.deepEqual((await get('/mri/17/measurements')).items,old)
 await context.close();context=null;await launch();await ready('t1n');compare(saved,await inspect());assert.equal((await inspect()).lengths.length,0)
 assert.deepEqual((await get('/mri/17/measurements')).items,old);assert.deepEqual(await get('/mri/17/annotations'),oldCanvas)
 await page.getByText('Canvas（已验入口）',{exact:true}).click();await page.reload();await page.locator('.slice-img').first().waitFor({timeout:60000});assert.equal(await page.locator('.cs-viewer').count(),0)
 result.checks.push('Four real sequences preserve saved LPS points; only three new distances deleted and a second close/relaunch stays empty; old Canvas annotations untouched and explicit Canvas fallback survives refresh')
 result.savedView=saved;assert.equal(result.writes.length,7);assert.deepEqual(result.pageErrors,[]);result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;await page?.screenshot({path:out+'/failure.png',fullPage:false}).catch(()=>{});process.exitCode=1}
finally{if(context)await context.close();await fs.writeFile(out+'/validation.json',JSON.stringify(result,null,2),{flag:'wx'});console.log(JSON.stringify(result))}
