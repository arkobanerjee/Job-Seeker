import test from 'node:test';
import assert from 'node:assert/strict';
import {companyOpportunities,opportunityApi} from './opportunities.js';

test('only comparable positive board changes become opportunities',async()=>{
 const rows=await companyOpportunities({momentum:[{status:'insufficient_history',delta:3},{status:'observed',delta:0},{status:'observed',delta:2,url:'https://example.com',baseline:3,current:5,scope:'sample'}]});
 assert.equal(rows.length,1);assert.match(rows[0].uncertainty,/No matching role/);
});
test('stable company identities survive new evidence text',async()=>{
 const signal={company:'Example',url:'https://example.com',kind:'product',title:'Launch',evidence_quote:'First quote'};
 const a=await companyOpportunities({signals:[signal]});const b=await companyOpportunities({signals:[{...signal,evidence_quote:'Updated quote'}]});
 assert.equal(a[0].id,b[0].id);assert.match(a[0].uncertainty,/No suitable vacancy/);
});

test('qualification status separates historical, weak, supported and rejected signals',async()=>{
 const signal={company:'Example',url:'https://example.com/news',kind:'product',title:'Launch',evidence_quote:'Launch quote'};
 const rows=await companyOpportunities({signals:[signal,{...signal,qualification_status:'qualified',evidence_strength:'Relevant product launch',qualification_reasons:[]}],rejected_signals:[{...signal,reason:'Quote absent from source'}]});
 assert.equal(rows.length,1);
 assert.equal(rows[0].qualification_status,'qualified');
 assert.ok(rows[0].evidence_items.some(r=>r.qualification_status==='rejected'));
 const legacy=await companyOpportunities({signals:[signal]});
 assert.equal(legacy[0].qualification_status,'investigate');
 assert.match(legacy[0].qualification_reasons[0],/Historical/);
});

test('one company preserves different evidence and groups matching excerpt copies',async()=>{
 const base={company:'Example',url:'https://example.com/news?utm_source=mail',kind:'company',title:'Funding announcement',evidence_quote:'Example raised funding for its RAG platform.',event_date:'2026-10-01',qualification_status:'qualified',evidence_strength:'Reported funding',run_id:'one'};
 const rows=await companyOpportunities({signals:[base,{...base,url:'https://copy.example/news',run_id:'two'},
  {...base,url:'https://example.com/product',title:'Product release',evidence_quote:'Example launched a new RAG product.',evidence_strength:'Relevant product launch'}]});
 assert.equal(rows.length,1);assert.equal(rows[0].evidence_count,2);assert.equal(rows[0].source_count,3);
 assert.equal(rows[0].evidence_items.find(e=>e.label==='Reported funding').sources.length,2);
 assert.equal(rows[0].labels.length,2);
 const more=await companyOpportunities({signals:[...rows[0].evidence_items.map(e=>({...base,evidence_quote:e.evidence,url:e.url})),{...base,url:'https://new.example/news'}]});
 assert.equal(more[0].id,rows[0].id);
});

test('unconfigured names and unidentified boards do not merge by shared host',async()=>{
 const rows=await companyOpportunities({signals:[{company:'Acme',url:'https://shared.example/a'},{company:'Acme Labs',url:'https://shared.example/b'}],momentum:[{status:'observed',delta:1,url:'https://shared.example/c'},{status:'observed',delta:1,url:'https://shared.example/d'}]});
 assert.equal(rows.length,4);
});

test('configured aliases preserve old notes and dismissal when evidence changes',async()=>{
 const old={company:'Acme Labs',url:'https://acme.example/news',kind:'product',title:'Launch',evidence_quote:'Acme Labs launched a product.'};
 const data=new Map([['registry/latest.json',JSON.stringify({signals:[old]})]]);
 const env={STATE:{get:async key=>data.has(key)?{json:async()=>JSON.parse(data.get(key))}:null,put:async(key,value)=>data.set(key,value)}};
 const get=async()=>await (await opportunityApi(new Request('https://app/api/company-opportunities'),env,'/api/company-opportunities')).json();
 const save=async(id,status,note)=>opportunityApi(new Request('https://app/api/company-opportunity',{method:'POST',body:JSON.stringify({id,status,note})}),env,'/api/company-opportunity');
 const [before]=await get();await save(before.id,'dismissed','Already investigated');
 data.set('registry/latest.json',JSON.stringify({companies:[{name:'Acme',aliases:['Acme Labs'],identity_basis:'user_configured'}],signals:[old,{...old,company:'Acme',url:'https://acme.example/product'}]}));
 const [after]=await get();assert.equal(after.company,'Acme');assert.equal(after.decision.status,'dismissed');assert.equal(after.decision.note,'Already investigated');
 assert.equal(after.previous_decisions.length,1);
 await save(after.id,'watch','New combined note');
 const [saved]=await get();assert.equal(saved.decision.note,'New combined note');assert.equal(saved.previous_decisions[0].note,'Already investigated');
 assert.ok(data.has('company-decisions/'+before.id));
});

test('pre-aggregation decision IDs remain readable and save into company record',async()=>{
 const signal={company:'Example',url:'https://example.com/news',kind:'product',title:'Launch',evidence_quote:'A launch quote'};
 const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(['signal',signal.company,signal.url])));
 const oldId=Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,'0')).join('').slice(0,24);
 const data=new Map([['registry/latest.json',JSON.stringify({signals:[signal]})],['company-decisions/'+oldId,JSON.stringify({status:'watch',note:'Keep this note',at:'2026-10-01'})]]);
 const env={STATE:{get:async key=>data.has(key)?{json:async()=>JSON.parse(data.get(key))}:null,put:async(key,value)=>data.set(key,value)}};
 const [row]=await (await opportunityApi(new Request('https://app/api/company-opportunities'),env,'/api/company-opportunities')).json();
 assert.equal(row.decision.note,'Keep this note');
 const request=new Request('https://app/api/company-opportunity',{method:'POST',body:JSON.stringify({id:oldId,status:'dismissed',note:'Reviewed'})});
 assert.equal((await opportunityApi(request,env,'/api/company-opportunity')).status,200);
 assert.equal(JSON.parse(data.get('company-decisions/'+row.id)).status,'dismissed');
 assert.equal(JSON.parse(data.get('company-decisions/'+oldId)).note,'Keep this note');
});
test('company actions persist separately and reject unknown IDs',async()=>{
 const data=new Map([['registry/latest.json',JSON.stringify({competitors:[{company:'Example',seed_company:'Other',url:'https://example.com',evidence_quote:'An alternative'}]})]]);
 const env={STATE:{get:async key=>data.has(key)?{json:async()=>JSON.parse(data.get(key))}:null,put:async(key,value)=>data.set(key,value)}};
 const response=await opportunityApi(new Request('https://app/api/company-opportunities'),env,'/api/company-opportunities');const [row]=await response.json();
 const request=id=>new Request('https://app/api/company-opportunity',{method:'POST',body:JSON.stringify({id,status:'watch',note:'Investigate'})});
 assert.equal((await opportunityApi(request(row.id),env,'/api/company-opportunity')).status,200);
 assert.ok(data.has('company-decisions/'+row.id));assert.equal((await opportunityApi(request('bad'),env,'/api/company-opportunity')).status,400);
});
