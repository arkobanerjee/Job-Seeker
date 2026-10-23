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
