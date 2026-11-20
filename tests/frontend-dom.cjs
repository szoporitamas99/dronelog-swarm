const fs = require('fs');
const {JSDOM} = require('jsdom');
const assert = require('node:assert/strict');
const ROOT=require('node:path').resolve(__dirname, '../frontend');
const html=fs.readFileSync(ROOT+'/index.html','utf8');
const js=fs.readFileSync(ROOT+'/app.js','utf8');
const TOKEN='local-contract-test-token-12345';
const fixture=()=>[
{id:1,title:'Napelempark ellenőrzése',location:'Déli tesztterület',aircraft:'DJI Mavic Air 2',mission_date:'2026-11-20',flight_minutes:22,status:'planned',notes:'Oktatási tesztadat',created_at:'2026-11-20T09:00:00Z'},
{id:2,title:'Távvezeték felmérése',location:'Északi gyakorlótér',aircraft:'DJI Matrice',mission_date:'2026-11-19',flight_minutes:30,status:'active',notes:'Oktatási tesztadat',created_at:'2026-11-20T09:00:00Z'},
{id:3,title:'Gyakorlórepülés',location:'Tesztpálya',aircraft:'DJI Mini',mission_date:'2026-11-18',flight_minutes:18,status:'completed',notes:'Oktatási tesztadat',created_at:'2026-11-20T09:00:00Z'}
];
const passed=[];
async function waitFor(check,description){let n=0;while(!check()){if(n++>1000)throw Error('Timeout: '+description);await new Promise(r=>setTimeout(r,2));}}
function setup({badInitial=false,savedToken=null}={}){
 const dom=new JSDOM(html,{url:'http://dronelog.test/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window;const doc=w.document;let items=fixture();let failReads=badInitial;let failWrite=false;const calls=[];
 w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
 w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');w.queueMicrotask(()=>this.dispatchEvent(new w.Event('close')));};
 w.fetch=async(url,options={})=>{
  calls.push({url,method:options.method,headers:options.headers,body:options.body});
  const path=new URL(url,w.location.href).pathname;const method=options.method||'GET';let status=200;let body;
  if(failReads&&method==='GET'&&path!='/api/admin/check')throw new w.TypeError('network error');
  if(failWrite&&method!=='GET')throw new w.TypeError('network error');
  if(path==='/api/admin/check'){
   status=options.headers['X-Admin-Token']===TOKEN?200:401;body=status===200?{authorized:true}:{detail:'Hibás szerkesztői token.'};
  }else if(method!=='GET'&&options.headers['X-Admin-Token']!==TOKEN){status=401;body={detail:'Nincs jogosultság.'};
  }else if(path==='/api/health'){body={status:'ok',database:'ok',instance:'dom-contract-test',version:'1.0.0'};
  }else if(path==='/api/missions'&&method==='GET'){body={items,count:items.length};
  }else if(path==='/api/stats'){body={total:items.length,planned:items.filter(x=>x.status==='planned').length,active:items.filter(x=>x.status==='active').length,completed:items.filter(x=>x.status==='completed').length,flight_minutes:items.filter(x=>x.status==='completed').reduce((a,x)=>a+x.flight_minutes,0)};
  }else if(path==='/api/missions'&&method==='POST'){body={...JSON.parse(options.body),id:Math.max(...items.map(x=>x.id))+1,created_at:'2026-11-20T12:00:00Z'};items.unshift(body);status=201;
  }else if(/^\/api\/missions\/\d+$/.test(path)){
   const id=Number(path.split('/').pop());const item=items.find(x=>x.id===id);
   if(method==='PATCH'){Object.assign(item,JSON.parse(options.body));body=item;}
   if(method==='DELETE'){items=items.filter(x=>x.id!==id);status=204;}
  }else{status=404;body={detail:'Ismeretlen tesztútvonal.'};}
  return new Response(status===204?null:JSON.stringify(body),{status,headers:{'Content-Type':'application/json','X-Instance-ID':'dom-contract-test'}});
 };
 if(savedToken)w.sessionStorage.setItem('dronelog_admin_token',savedToken);
 w.eval(js);
 const $=s=>doc.querySelector(s);
 const click=s=>$(s).click();
 const submit=s=>$(s).dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 const input=(selector,value)=>{const x=$(selector);x.value=value;x.dispatchEvent(new w.Event('input',{bubbles:true}));};
 return {dom,w,doc,$,click,submit,input,calls,items:()=>items,failReads:x=>{failReads=x;},failWrite:x=>{failWrite=x;}};
}
(async()=>{
 const t=setup();const {$,click,submit,input,w,doc}=t;
 await waitFor(()=>$('.mission-card'),'initial list');
 assert.equal(doc.querySelectorAll('.mission-card').length,3);assert.equal($('#stat-total').textContent,'3');assert.equal($('.delete-button'),null);assert.equal($('#connection-label').textContent,'API és adatbázis elérhető');
 assert(t.calls.filter(c=>c.method==='GET').every(c=>!('X-Admin-Token'in c.headers)));
 passed.push('Public read-only initial load; real-looking status only after successful API contract response; no token on public reads');
 click('#new-mission');assert($('#auth-dialog').hasAttribute('open'));assert.equal(doc.activeElement.id,'admin-token');
 input('#admin-token','invalid-token-123456');submit('#auth-form');await waitFor(()=>!$('#auth-error').hidden,'bad token error');
 assert.equal($('.delete-button'),null);assert.equal(w.sessionStorage.getItem('dronelog_admin_token'),null);
 passed.push('Invalid token rejected and mutation controls remain unavailable');
 input('#admin-token',TOKEN);submit('#auth-form');await waitFor(()=>$('#mission-dialog').hasAttribute('open'),'create modal after authorization');
 assert.equal(w.sessionStorage.getItem('dronelog_admin_token'),TOKEN);assert.equal(w.localStorage.getItem('dronelog_admin_token'),null);assert.equal(doc.activeElement.name,'title');
 passed.push('Validated login, session-only token, continuation into requested create dialog, explicit focus');
 const malicious='<img src=x onerror=alert(1)>';
 input('[name=title]','Böngészős szerződésteszt');input('[name=location]','Tesztterület');input('[name=aircraft]','DJI teszt');input('[name=mission_date]','2026-11-20');input('[name=flight_minutes]','22');input('[name=notes]',malicious);
 submit('#mission-form');await waitFor(()=>$('#stat-total').textContent==='4','created');
 assert.equal(t.items().length,4);assert.equal(doc.querySelectorAll('.mission-card').length,4);assert.equal(doc.querySelector('.mission-card img'),null);assert.equal(doc.querySelector('.mission-notes').textContent,malicious);assert.equal($('#mission-dialog').hasAttribute('open'),false);
 passed.push('POST create plus refresh; untrusted notes rendered as literal text without injected image/event');
 click('.mission-card .text-button');await waitFor(()=>$('#mission-dialog').hasAttribute('open'),'edit dialog');
 assert.equal($('[name=title]').value,'Böngészős szerződésteszt');input('[name=status]','completed');submit('#mission-form');
 await waitFor(()=>$('#stat-completed').textContent==='2','edited stats');assert.equal($('#flight-total').textContent,'40 perc');
 passed.push('PATCH edit prefilled values and updated status/statistics');
 input('#search','bongeszos');assert.equal(doc.querySelectorAll('.mission-card').length,1);
 click('.delete-button');assert($('#delete-dialog').hasAttribute('open'));click('#delete-dialog [data-close]');assert.equal(t.items().length,4);
 click('.delete-button');click('#confirm-delete');await waitFor(()=>$('#stat-total').textContent==='3','deleted');
 assert.equal(t.items().length,3);input('#search','');click('[data-filter=completed]');assert.equal(doc.querySelectorAll('.mission-card').length,1);click('[data-filter=all]');assert.equal(doc.querySelectorAll('.mission-card').length,3);
 passed.push('Accent-insensitive search, status filters, cancellation without deletion, confirmed DELETE with refresh');
 t.failReads(true);click('#refresh-button');await waitFor(()=>!$('#error-banner').hidden,'read error');
 assert.equal(doc.querySelectorAll('.mission-card').length,3);assert.equal($('#connection-label').textContent,'A kapcsolat ellenőrzést igényel');
 t.failReads(false);click('#retry-button');await waitFor(()=>$('#error-banner').hidden,'read recovery');
 passed.push('Read failure preserves existing data with visible error and disconnected status; explicit retry recovers');
 click('#new-mission');input('[name=title]','Bizonytalan mentés');input('[name=location]','Teszt');input('[name=aircraft]','Teszt');input('[name=mission_date]','2026-11-20');input('[name=flight_minutes]','1');t.failWrite(true);submit('#mission-form');
 await waitFor(()=>!$('#mission-error').hidden,'write failure');assert.match($('#mission-error').textContent,/eredménye bizonytalan/);assert.equal(t.items().length,3);t.failWrite(false);click('#mission-dialog [data-close]');
 passed.push('Failed write marked as uncertain; no automatic POST retry');
 click('#auth-button');assert.equal($('.delete-button'),null);assert.equal(w.sessionStorage.getItem('dronelog_admin_token'),null);
 passed.push('Logout removes stored token and all mutation controls');
 t.dom.window.close();
 const bad=setup({badInitial:true});await waitFor(()=>!bad.$('#error-banner').hidden,'initial error');assert.equal(bad.$('#list-count').textContent,'Nem elérhető');assert.equal(bad.$('.mission-card'),null);assert.equal(bad.$('#connection-label').textContent,'A kapcsolat ellenőrzést igényel');bad.dom.window.close();
 passed.push('Initial connection failure does not fabricate records, totals or healthy status');
 const restore=setup({savedToken:TOKEN});await waitFor(()=>restore.$('.delete-button'),'restored token');assert(restore.calls.some(c=>c.url==='/api/admin/check'));restore.dom.window.close();
 const expired=setup({savedToken:'expired-token'});await waitFor(()=>expired.$('.mission-card'),'expired token list');await waitFor(()=>expired.w.sessionStorage.getItem('dronelog_admin_token')===null,'expired token cleared');assert.equal(expired.$('.delete-button'),null);expired.dom.window.close();
 passed.push('Session token restored only after API authorization; expired saved token removed');
 console.log(JSON.stringify({status:'PASS',scope:'jsdom DOM/API contract tests with mocked API. No browser layout, nginx, Docker or Swarm exercised.',checks:passed,count:passed.length},null,2));
})().catch(e=>{console.error(e);process.exit(1);});
