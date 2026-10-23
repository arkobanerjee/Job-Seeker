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
  async list({prefix}){return {objects:[...this.objects.keys()].filter(x=>x.startsWith(prefix)).map(key=>({key}))}}
}
function env(){return {STATE:new R2(),APP_TOKEN:'test-only'}}
const req=(path,method='GET',body,token='test-only')=>new Request('https://jobs.example'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
test('private data requires authentication',async()=>{assert.equal((await worker.fetch(req('/api/catalog','GET',null,'wrong'),env())).status,401)});
test('budget cannot reset, double reserve, or exceed gate',async()=>{
  const e=env();assert.equal((await worker.fetch(req('/api/initialize','POST',{already_reserved:1.15}),e)).status,200);
  assert.equal((await worker.fetch(req('/api/initialize','POST',{already_reserved:0}),e)).status,409);
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'one',amount:2}),e)).status,200);
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'one',amount:2}),e)).status,200);
  assert.equal((await worker.fetch(req('/api/reserve','POST',{id:'two',amount:2}),e)).status,402);
});
test('compare and swap prevents concurrent overspend',async()=>{
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
