const {chromium}=require('playwright-core');const fs=require('fs');const assert=require('assert');
(async()=>{
 const auth=JSON.parse(fs.readFileSync('.runtime/ota-session.json'));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1050}});
  await context.addCookies(Object.entries(auth.cookie).map(([name,value])=>({name,value,url:'http://127.0.0.1:5173',httpOnly:true,sameSite:'Lax'})));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));const pages=[];
  for(const route of ['/',...Array.from({length:6},(_,i)=>`/analytics/analog-${i+1}`),'/controls','/can','/bms','/account','/ota']){
   await page.goto('http://127.0.0.1:5173'+route);await page.locator('main h1').waitFor({timeout:20000});
   assert(!page.url().includes('/login'));pages.push({route,heading:await page.locator('main h1').innerText()});
  }
  await page.getByText('Live report from chip',{exact:true}).waitFor();
  const chip=(await (await context.request.get('http://127.0.0.1:5173/api/v1/ota')).json()).chip;
  assert(await page.getByText(chip.ip_address,{exact:true}).isVisible());
  assert(await page.getByText('Device MQTT: Unencrypted',{exact:true}).isVisible());
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'output/testing/screenshots/ota-final-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1));
  await page.screenshot({path:'output/testing/screenshots/ota-final-mobile.png',fullPage:true});
  const result={passed:true,live_backend:true,pages,chip,page_errors:errors};fs.writeFileSync('output/testing/ota-live-gui-regression.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
