// Render the standalone SVGs with the actual installed browser; no service or business writes.
import {chromium} from '@playwright/test'
import fs from 'node:fs/promises'
import {pathToFileURL} from 'node:url'
import assert from 'node:assert/strict'
const dir=process.argv[2]?.replaceAll('\\','/');assert.ok(dir?.startsWith('E:/BrainFusion-Runtime/results/nightly/'))
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1800,height:1200},deviceScaleFactor:1})
const result={status:'running',browser:await browser.version(),figures:[]}
try{
 for(const name of ['architecture-current','dicom-data-relations']){
  await page.goto(pathToFileURL(dir+'/'+name+'.svg').href);await page.evaluate(()=>document.fonts.ready)
  const proof=await page.evaluate(()=>{
   const svg=document.querySelector('svg'),v=svg.viewBox.baseVal,errors=[]
   for(const t of document.querySelectorAll('text')){
    const b=t.getBBox();if(b.x<0||b.y<0||b.x+b.width>v.width||b.y+b.height>v.height)errors.push('canvas: '+t.textContent)
    if(t.dataset.box){const rect=document.getElementById(t.dataset.box),r=rect.getBBox();if(b.x<r.x||b.y<r.y||b.x+b.width>r.x+r.width||b.y+b.height>r.y+r.height)errors.push('box: '+t.textContent)}
   }
   return {width:v.width,height:v.height,texts:document.querySelectorAll('text').length,fontLoaded:document.fonts.check('21px "Microsoft YaHei"'),overflow:errors}
  })
  await page.locator('svg').screenshot({path:dir+'/'+name+'.png'})
  result.figures.push({name,...proof});assert.deepEqual(proof.overflow,[],name);assert.equal(proof.fontLoaded,true)
 }
 result.status='passed'
}catch(e){result.status='failed';result.error=e.stack;process.exitCode=1}
finally{await fs.writeFile(dir+'/render-validation.json',JSON.stringify(result,null,2),{flag:'wx'});await browser.close();console.log(JSON.stringify(result))}
