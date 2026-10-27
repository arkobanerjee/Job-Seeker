import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.js';
class R2 {
  objects=new Map(); version=0;
  async get(key){const x=this.objects.get(key);return x ? {etag:x.etag,body:x.body,json:async()=>JSON.parse(x.body)} : null}
  async put(key,body,options={}){const old=this.objects.get(key),c=options.onlyIf;
    if(c?.etagDoesNotMatch==='*'&&old)return null;
    if(c?.etagMatches&&c.etagMatches!==old?.etag)return null;
    const value={body,etag:String(++this.version)};this.objects.set(key,value);return value}
  async delete(keys){for(const key of Array.isArray(keys)?keys:[keys])this.objects.delete(key)}
  async list({prefix}){return {objects:[...this.objects.keys()].filter(x=>x.startsWith(prefix)).map(key=>({key}))}}
}
function env(){return {STATE:new R2(),APP_TOKEN:'test-only'}}
const req=(path,method='GET',body,token='test-only')=>new Request('https://jobs.example'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
test('evaluation logs require authentication, validate run IDs and survive state replacement',async()=>{
 const e=env(),id='a'.repeat(32),path='/api/evaluation/'+id;
 assert.equal((await worker.fetch(req(path,'GET',null,'wrong'),e)).status,401);
 assert.equal((await worker.fetch(req('/api/evaluation/not-a-run'),e)).status,400);
 assert.equal((await worker.fetch(req(path),e)).status,404);
 const log={schema_version:1,run_id:id,searches:[{query:'AI Poland',results:[{url:'https://example.com/job',snippet:'saved'}]}],calls:[],by_purpose:{}};
 assert.equal((await worker.fetch(req(path,'PUT',{...log,run_id:'b'.repeat(32)}),e)).status,400);
 assert.equal((await worker.fetch(req(path,'PUT',log),e)).status,200);
 await e.STATE.put('state/latest.zip','new snapshot');
 assert.deepEqual(await (await worker.fetch(req(path),e)).json(),log);
 assert.equal((await worker.fetch(req(path,'DELETE'),e)).status,405);
 assert.equal((await worker.fetch(req(path,'PUT',{...log,padding:'x'.repeat(2000001)}),e)).status,413);
});

test('restoring research cannot erase finished API receipts',async()=>{
 const e=env(),id='b'.repeat(32),path='/api/evaluation/'+id;
 const base={schema_version:1,run_id:id,searches:[],by_purpose:{}};
 const complete={id:'call1',provider:'tavily',purpose:'search',status:'success',finished_at:'2026-10-25T10:00:00Z',observed_estimate_usd:.008};
 await worker.fetch(req(path,'PUT',{...base,calls:[complete]}),e);
 await worker.fetch(req(path,'PUT',{...base,calls:[{id:'call1',provider:'tavily',purpose:'search',status:'started'}]}),e);
 let result=await (await worker.fetch(req(path),e)).json();assert.equal(result.calls[0].status,'success');
 await worker.fetch(req(path,'PUT',{...base,calls:[]}),e);
 result=await (await worker.fetch(req(path),e)).json();assert.equal(result.calls.length,1);assert.equal(result.by_purpose['tavily:search'].observed_estimate_usd,.008);
});
test('private data requires authentication',async()=>{assert.equal((await worker.fetch(req('/api/catalog','GET',null,'wrong'),env())).status,401)});
test('board observations dispatch a distinct workflow mode',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';const old=globalThis.fetch;
 globalThis.fetch=async(url,options)=>{assert.deepEqual(JSON.parse(options.body).inputs,{mode:'boards'});return new Response(null,{status:204})};
 try{assert.equal((await worker.fetch(req('/api/run','POST',{mode:'boards'}),e)).status,200)}finally{globalThis.fetch=old}
});

test('company discovery dispatches its own workflow mode',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';const old=globalThis.fetch;
 globalThis.fetch=async(url,options)=>{assert.deepEqual(JSON.parse(options.body).inputs,{mode:'company'});return new Response(null,{status:204})};
 try{assert.equal((await worker.fetch(req('/api/run','POST',{mode:'company'}),e)).status,200)}finally{globalThis.fetch=old}
});

test('a retry with the same receipt cannot queue duplicate research',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';const old=globalThis.fetch;let calls=0;
 globalThis.fetch=async()=>{calls++;return new Response(null,{status:204})};
 try{const body={mode:'company',request_id:'a'.repeat(32)};
 assert.equal((await worker.fetch(req('/api/run','POST',body),e)).status,200);
 assert.equal((await (await worker.fetch(req('/api/run','POST',body),e)).json()).duplicate,true);
 assert.equal(calls,1);
 assert.equal((await worker.fetch(req('/api/run','POST',{...body,mode:'discovery'}),e)).status,409);
 }finally{globalThis.fetch=old}
});

test('an uncertain dispatch receipt never claims confirmed queueing',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';
 await e.STATE.put('dispatch/'+('b'.repeat(32))+'.json',JSON.stringify({mode:'company',backup_id:null,status:'dispatching'}));
 const response=await worker.fetch(req('/api/run','POST',{mode:'company',request_id:'b'.repeat(32)}),e);
 assert.equal(response.status,409);assert.equal((await response.json()).uncertain,true);
});
test('cold evidence archives are private, immutable and idempotent',async()=>{
 const e=env(),id='d'.repeat(32),data='synthetic archive';
 const upload=body=>new Request('https://jobs.example/api/run-archive/'+id,{method:'PUT',headers:{Authorization:'Bearer test-only','Content-Length':String(body.length)},body});
 assert.equal((await worker.fetch(req('/api/run-archives','GET',null,'wrong'),e)).status,401);
 const receipt=await (await worker.fetch(upload(data),e)).json();
 assert.equal(receipt.id,id);assert.equal(receipt.sha256.length,64);
 assert.equal((await worker.fetch(upload(data),e)).status,200);
 assert.equal((await worker.fetch(upload('different bytes'),e)).status,409);
 assert.equal(await (await worker.fetch(req('/api/run-archive/'+id),e)).text(),data);
 assert.equal((await (await worker.fetch(req('/api/run-archives'),e)).json()).archives.length,1);
});
test('health diagnostics are private and marked stale when state changes',async()=>{
 const e=env();assert.equal((await worker.fetch(req('/api/health','GET',null,'wrong'),e)).status,401);
 assert.deepEqual(await (await worker.fetch(req('/api/health'),e)).json(),{status:'not_checked',stale:true});
 const state=await e.STATE.put('state/latest.zip','archive');
 const report={status:'ok',checks:[],archive_bytes:7,expanded_bytes:10,files:1,state_etag:'"'+state.etag+'"'};
 assert.equal((await worker.fetch(req('/api/health','PUT',report),e)).status,200);
 assert.equal((await (await worker.fetch(req('/api/health'),e)).json()).stale,false);
 await e.STATE.put('state/latest.zip','new');
 assert.equal((await (await worker.fetch(req('/api/health'),e)).json()).stale,true);
 assert.equal((await worker.fetch(req('/api/health','PUT',{...report,files:-1}),e)).status,400);
});
test('cumulative accounting never blocks a new run and retains idempotency',async()=>{
  const e=env();assert.equal((await worker.fetch(req('/api/initialize','POST',{already_reserved:1.15}),e)).status,200);
  assert.equal((await worker.fetch(req('/api/initialize','POST',{already_reserved:0}),e)).status,409);
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'one',amount:2}),e)).status,200);
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'one',amount:2}),e)).status,200);
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'two',amount:2}),e)).status,200);
  const budget=await (await worker.fetch(req('/api/budget'),e)).json();assert.equal(budget.reserved,5.15);assert.equal(budget.ceiling,null);assert.equal(budget.policy,'per_run');
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'one',amount:.5}),e)).status,409);
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'bad',amount:3}),e)).status,400);
});
test('compare and swap prevents lost accounting updates',async()=>{
  const e=env();await worker.fetch(req('/api/initialize','POST',{already_reserved:2}),e);
  const results=await Promise.all(['a','b'].map(id=>worker.fetch(req('/api/reserve','POST',{id,amount:2}),e)));
  assert.equal(results.filter(r=>r.status===200).length,1);
});
test('decision validation and cross-origin protection',async()=>{
  const e=env();assert.equal((await worker.fetch(req('/api/decision','POST',{id:'bad',decision:'apply_anyway',note:''}),e)).status,400);
  const r=req('/api/decision','POST',{id:'a'.repeat(24),decision:'apply_anyway',note:'Try English team'});
  r.headers.set('Origin','https://attacker.example');assert.equal((await worker.fetch(r,e)).status,403);
});

test('Telegram requires secret and owner, answers once and resumes saved run',async()=>{
 const e=env();e.TELEGRAM_WEBHOOK_SECRET='hook';e.TELEGRAM_CHAT_ID='123';e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';
 const q={id:'a'.repeat(24),run_id:'b'.repeat(32),revision:'rev',prompt:'Remote only?',message_id:42};
 await worker.fetch(req('/api/question','POST',q),e);
 const message={chat:{type:'private',id:123},from:{id:123},text:'/answer '+q.id+' yes'};
 const hook=(m,secret='hook')=>new Request('https://jobs.example/telegram',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Bot-Api-Secret-Token':secret},body:JSON.stringify({message:m})});
 assert.equal((await worker.fetch(hook(message,'wrong'),e)).status,401);
 await worker.fetch(hook({...message,from:{id:999}}),e);assert.equal(await e.STATE.get('answers/'+q.id+'.json'),null);
 const original=globalThis.fetch;let dispatches=0;
 globalThis.fetch=async(url,options)=>{dispatches++;assert.equal(JSON.parse(options.body).inputs.run_id,q.run_id);return new Response(null,{status:204})};
 try{
  assert.equal((await worker.fetch(hook({...message,text:'yes'}),e)).status,200);
  await worker.fetch(hook({...message,text:'/answer '+q.id+' no'}),e);
  assert.equal(dispatches,1);assert.equal((await (await e.STATE.get('answers/'+q.id+'.json')).json()).answer,'yes');
 }finally{globalThis.fetch=original}
});

test('standalone reply cannot select between multiple pending questions',async()=>{
 const e=env();e.TELEGRAM_WEBHOOK_SECRET='hook';e.TELEGRAM_CHAT_ID='123';
 for(const id of ['a','b'])await worker.fetch(req('/api/question','POST',{id:id.repeat(24),run_id:'c'.repeat(32),revision:'rev',prompt:'Question?'}),e);
 const request=new Request('https://jobs.example/telegram',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Bot-Api-Secret-Token':'hook'},body:JSON.stringify({message:{chat:{id:123,type:'private'},from:{id:123},text:'Received'}})});
 assert.deepEqual(await (await worker.fetch(request,e)).json(),{ignored:true});
 assert.equal((await e.STATE.list({prefix:'answers/'})).objects.length,0);
});

test('registry stays private and validates its container schema',async()=>{
 const e=env();assert.equal((await worker.fetch(req('/api/registry','GET',null,'wrong'),e)).status,401);
 assert.equal((await worker.fetch(req('/api/registry','PUT',{companies:'bad',sources:[]}),e)).status,400);
 const registry={companies:[{name:'Example',sources:[]}],sources:[]};
 assert.equal((await worker.fetch(req('/api/registry','PUT',registry),e)).status,200);
 assert.deepEqual(await (await worker.fetch(req('/api/registry'),e)).json(),registry);
});

test('monitor button dispatches a bounded monitor workflow mode',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';
 const original=globalThis.fetch;let body;
 globalThis.fetch=async(url,options)=>{body=JSON.parse(options.body);return new Response(null,{status:204})};
 try{
  assert.equal((await worker.fetch(req('/api/run','POST',{mode:'monitor'}),e)).status,200);
  assert.equal(body.inputs.mode,'monitor');
  assert.equal((await worker.fetch(req('/api/run','POST',{mode:'unlimited'}),e)).status,400);
 }finally{globalThis.fetch=original}
});

test('daily claims are idempotent and monitor status stays private',async()=>{
 const e=env();
 const results=await Promise.all([1,2].map(()=>worker.fetch(req('/api/schedule-claim','POST',{date:'2026-10-23'}),e).then(r=>r.json())));
 assert.equal(results.filter(x=>x.claimed).length,1);
 assert.equal((await worker.fetch(req('/api/monitor-status','GET',null,'wrong'),e)).status,401);
 await worker.fetch(req('/api/monitor-status','PUT',{status:'skipped',reason:'budget_review_required'}),e);
 assert.equal((await (await worker.fetch(req('/api/monitor-status'),e)).json()).reason,'budget_review_required');
});

test('dashboard questions validate revision and persist immutable answers',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';
 const q={id:'d'.repeat(24),run_id:'e'.repeat(32),revision:'rev',prompt:'Hybrid work?',reason:'Preference needed'};
 await worker.fetch(req('/api/question','POST',q),e);
 assert.equal((await worker.fetch(req('/api/questions','GET',null,'wrong'),e)).status,401);
 assert.equal((await (await worker.fetch(req('/api/questions'),e)).json()).questions.length,1);
 assert.equal((await worker.fetch(req('/api/answer','POST',{id:q.id,revision:'old',answer:'yes'}),e)).status,409);
 const original=globalThis.fetch;globalThis.fetch=async()=>new Response(null,{status:204});
 try{
  assert.equal((await worker.fetch(req('/api/answer','POST',{id:q.id,revision:q.revision,answer:'yes'}),e)).status,200);
  assert.equal((await (await worker.fetch(req('/api/questions'),e)).json()).questions.length,0);
  assert.equal((await worker.fetch(req('/api/answer','POST',{id:q.id,revision:q.revision,answer:'no'}),e)).status,409);
 }finally{globalThis.fetch=original}
});
test('history resumes only a recoverable saved cloud run',async()=>{
 const e=env();const run_id='f'.repeat(32);
 assert.equal((await worker.fetch(req('/api/runs','GET',null,'wrong'),e)).status,401);
 await worker.fetch(req('/api/runs','PUT',[{run_id,status:'completed',can_resume:false}]),e);
 assert.equal((await worker.fetch(req('/api/resume','POST',{run_id}),e)).status,409);
 await worker.fetch(req('/api/runs','PUT',[{run_id,status:'partial',can_resume:true}]),e);
 const original=globalThis.fetch;globalThis.fetch=async()=>new Response(null,{status:204});
 try{assert.equal((await worker.fetch(req('/api/resume','POST',{run_id}),e)).status,200)}finally{globalThis.fetch=original}
});

test('notification recovery dispatches separately and delivery metadata is private',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';
 assert.equal((await worker.fetch(req('/api/notifications','GET',null,'wrong'),e)).status,401);
 await worker.fetch(req('/api/notifications','PUT',[{id:'completion:one',status:'pending',attempts:1}]),e);
 assert.equal((await (await worker.fetch(req('/api/notifications'),e)).json())[0].status,'pending');
 const original=globalThis.fetch;let mode;
 globalThis.fetch=async(url,options)=>{mode=JSON.parse(options.body).inputs.mode;return new Response(null,{status:204})};
 try{assert.equal((await worker.fetch(req('/api/run','POST',{mode:'notifications'}),e)).status,200);assert.equal(mode,'notifications')}finally{globalThis.fetch=original}
});

test('pause cancel and resume respect terminal cancellation and authentication',async()=>{
 const e=env();e.GITHUB_TOKEN='dispatch';e.GITHUB_REPOSITORY='owner/repo';e.GITHUB_REF='main';const run_id='9'.repeat(32);
 await worker.fetch(req('/api/runs','PUT',[{run_id,status:'running',can_resume:false}]),e);
 assert.equal((await worker.fetch(req('/api/control','POST',{run_id,action:'pause'},'wrong'),e)).status,401);
 assert.equal((await worker.fetch(req('/api/control','POST',{run_id,action:'pause'}),e)).status,200);
 assert.equal((await (await worker.fetch(req('/api/control/'+run_id),e)).json()).action,'pause');
 await worker.fetch(req('/api/runs','PUT',[{run_id,status:'paused',can_resume:true}]),e);
 const original=globalThis.fetch;globalThis.fetch=async()=>new Response(null,{status:204});
 try{
  assert.equal((await worker.fetch(req('/api/resume','POST',{run_id}),e)).status,200);
  assert.equal((await (await worker.fetch(req('/api/control/'+run_id),e)).json()).action,'run');
  assert.equal((await worker.fetch(req('/api/control','POST',{run_id,action:'cancel'}),e)).status,200);
  assert.equal((await worker.fetch(req('/api/resume','POST',{run_id}),e)).status,409);
 }finally{globalThis.fetch=original}
});

test('private backups retain five snapshots and reject reused IDs',async()=>{
 const e=env();
 assert.equal((await worker.fetch(req('/api/backups','GET',null,'wrong'),e)).status,401);
 for(let i=0;i<6;i++){
  const id=i.toString(16).padStart(32,'0');const body=new TextEncoder().encode('private-test-archive-'+i);
  const r=new Request('https://jobs.example/api/backup/'+id,{method:'PUT',headers:{Authorization:'Bearer test-only','Content-Length':String(body.length)},body});
  assert.equal((await worker.fetch(r,e)).status,200);
 }
 const rows=await (await worker.fetch(req('/api/backups'),e)).json();assert.equal(rows.length,5);
 const id=rows[0].id,body=new TextEncoder().encode('again');
 const request=new Request('https://jobs.example/api/backup/'+id,{method:'PUT',headers:{Authorization:'Bearer test-only','Content-Length':String(body.length)},body});
 assert.equal((await worker.fetch(request,e)).status,409);
 assert.ok(rows.every(x=>x.sha256.length===64));assert.ok(!e.STATE.objects.has('budget.json'));
});
test('version-checked state updates cannot overwrite a changed snapshot',async()=>{
 const e=env();await e.STATE.put('state/latest.zip','original');const body=new TextEncoder().encode('restored');
 const request=new Request('https://jobs.example/api/state',{method:'PUT',headers:{Authorization:'Bearer test-only','Content-Length':String(body.length),'If-Match':'"wrong"'},body});
 assert.equal((await worker.fetch(request,e)).status,409);
});


test('legacy gate state is readable without resetting its history',async()=>{
 const e=env();await e.STATE.put('budget.json',JSON.stringify({reserved:20,ceiling:5,reservations:[]}));
 const b=await (await worker.fetch(req('/api/budget'),e)).json();assert.equal(b.reserved,20);assert.equal(b.ceiling,null);
 assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'next',amount:.5}),e)).status,200);
 assert.equal((await (await worker.fetch(req('/api/budget'),e)).json()).reserved,20.5);
});
