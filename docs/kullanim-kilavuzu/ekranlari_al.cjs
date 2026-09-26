// Güncel arayüzü ayrı profilde belgeler. Sunucuya kayıt/model isteği göndermez.
const { chromium } = require('../../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const dir=path.join(__dirname,'gorseller'); fs.mkdirSync(dir,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const screenshots=[], errors=[], blocked=[], inventory={};
  try {
    const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1.5});
    await page.addInitScript(()=>{localStorage.setItem('atlas_voice_alerts_enabled','false');localStorage.setItem('atlas_voice_auto_lock','false');});
    await page.route('**/api/**',route=>{
      const req=route.request();
      if(req.method()!=='GET'||req.url().includes('/threat-report/download')){blocked.push(req.method()+' '+new URL(req.url()).pathname);return route.abort();}
      return route.continue();
    });
    page.on('pageerror',e=>errors.push(e.message));
    async function shot(name,locator){
      const opts={path:path.join(dir,name+'.png')};
      if(locator)await locator.screenshot(opts);else await page.screenshot(opts);
      screenshots.push(name+'.png');
    }
    async function inspect(name){inventory[name]=await page.locator('button,select,input,summary').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().width&&n.getBoundingClientRect().height).map(n=>({tag:n.tagName,name:n.getAttribute('aria-label')||n.getAttribute('title')||n.textContent.trim(),disabled:n.disabled||false})));}
    await page.goto('http://127.0.0.1:5173/',{waitUntil:'networkidle'});
    await page.getByRole('button',{name:'Açık temaya geç',exact:true}).waitFor();
    await page.waitForTimeout(1000);await shot('ana-ekran');
    await page.getByRole('button',{name:'Açık temaya geç',exact:true}).click();
    await page.waitForTimeout(400);await shot('acik-tema');await inspect('ana-ekran');
    await shot('ust-cubuk',page.locator('.map-first-topbar'));
    await shot('harita-araclari',page.locator('.map-toolbar'));
    await shot('harita-gorunum',page.locator('.map-visual-controls'));
    await shot('zaman-cizelgesi',page.locator('.playback-timeline'));
    await shot('sol-panel',page.locator('.map-sidebar'));
    const filterA=await page.locator('.map-filter-search').boundingBox(),filterB=await page.locator('.map-filter-result').boundingBox();
    await page.screenshot({path:path.join(dir,'harita-filtreleri.png'),clip:{x:filterA.x-4,y:filterA.y-4,width:filterA.width+8,height:filterB.y+filterB.height-filterA.y+8}});screenshots.push('harita-filtreleri.png');
    await shot('katman-kutulari',page.locator('.compact-layer-grid'));
    await shot('pdf-dugmesi',page.locator('.pdf-report-download'));
    await shot('ses-dugmesi',page.locator('.voice-alert-toggle'));
    await shot('panel-basligi',page.locator('.map-sidebar > header'));
    const a=await page.locator('.theme-toggle').boundingBox(),b=await page.locator('.map-refresh').boundingBox();
    await page.screenshot({path:path.join(dir,'genel-kontroller.png'),clip:{x:a.x-5,y:Math.max(0,a.y-5),width:b.x+b.width-a.x+10,height:a.height+10}});screenshots.push('genel-kontroller.png');
    await page.getByRole('button',{name:'Harita panelini daralt',exact:true}).click();await shot('panel-ac',page.getByRole('button',{name:'Harita panelini aç',exact:true}));await shot('panel-kapali');await page.getByRole('button',{name:'Harita panelini aç',exact:true}).click();
    for(const [button,selector,name,close] of [
      ['Operasyon Özeti','.map-summary-popover','ozet-paneli','Operasyon özetini kapat'],
      ['Öncelikli Araçlar','.map-priority-popover','liste-paneli','Öncelikli araç listesini kapat'],
      ['Analist Onayı','.map-review-popover','onay-paneli','Analist onayı panelini kapat'],
      ['Ajan','.map-agent-chat','ajan-paneli','Ajan panelini kapat'],
    ]){
      await page.locator('.map-overlay-actions').getByRole('button',{name:new RegExp('^'+button)}).click();
      await page.locator(selector).waitFor();await shot(name,page.locator(selector));if(name==='ozet-paneli')await shot('ozet-sayaclar',page.locator('.compact-state-grid'));await inspect(name);await page.getByRole('button',{name:close,exact:true}).click();
    }
    await page.getByRole('button',{name:/^İzleme listesi bildirimleri/}).click();await shot('bildirim-paneli',page.locator('.watch-notification-panel'));await page.getByRole('button',{name:/^İzleme listesi bildirimleri/}).click();
    await page.locator('.bottom-panel-toggle').click();await page.locator('.track-explorer').waitFor();await shot('kayit-tablosu',page.locator('.bottom-track-panel'));await inspect('kayit-tablosu');
    await page.locator('.track-table tbody tr').first().click();await page.locator('.map-detail-drawer').waitFor();await shot('detay-paneli',page.locator('.map-detail-drawer'));await inspect('detay-paneli');
    await shot('detay-kontrolleri',page.locator('.details-heading'));
    const da=await page.locator('.details-heading').boundingBox(),db=await page.locator('.vehicle-actions').boundingBox();
    await page.screenshot({path:path.join(dir,'detay-ust.png'),clip:{x:da.x,y:da.y,width:da.width,height:db.y+db.height-da.y}});screenshots.push('detay-ust.png');
    // Yalnızca görüntüleme: kayıt üretme, değerlendirme ve karar düğmeleri tetiklenmez.
    const detail=page.locator('.map-detail-drawer');
    const sections=await detail.locator('.entity-detail-section-toggle').allTextContents();
    fs.writeFileSync(path.join(dir,'detay-basliklari.json'),JSON.stringify(sections,null,2)+'\n');
    const observation=detail.locator('.entity-detail-section').filter({has:page.getByRole('heading',{name:'Gözlem',exact:true})});
    if(await observation.count()){await observation.scrollIntoViewIfNeeded();await shot('gozlem-paneli',detail);await shot('kare-goruntusu',detail.locator('.frame-image'));}
    await page.getByRole('button',{name:'İz seçimini temizle',exact:true}).click();
    if(await page.locator('.bottom-track-panel.open').count())await page.locator('.bottom-panel-toggle').click();
    await page.getByRole('button',{name:'3D',exact:true}).click();await page.waitForTimeout(700);await shot('uc-boyutlu-gorunum');
    fs.writeFileSync(path.join(dir,'kontrol-envanteri.json'),JSON.stringify(inventory,null,2)+'\n');
    const manifest={captured_at:new Date().toISOString(),url:page.url(),viewport:{width:1600,height:1000},deviceScaleFactor:1.5,method:'Playwright / Chromium; isolated temporary profile; server writes and report generation blocked',screenshots,pageErrors:errors,blockedRequests:blocked,notes:['Ses geçici profilde kapalı; sunucu ayarları değiştirilmedi.','Boş paneller gerçek mevcut durumu gösterir; örnek karar veya bildirim üretilmedi.']};
    fs.writeFileSync(path.join(dir,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');console.log(JSON.stringify(manifest));
    if(errors.length||blocked.length)process.exitCode=1;
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
