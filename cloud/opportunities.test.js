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
test('company actions persist separately and reject unknown IDs',async()=>{
 const data=new Map([['registry/latest.json',JSON.stringify({competitors:[{company:'Example',seed_company:'Other',url:'https://example.com',evidence_quote:'An alternative'}]})]]);
 const env={STATE:{get:async key=>data.has(key)?{json:async()=>JSON.parse(data.get(key))}:null,put:async(key,value)=>data.set(key,value)}};
 const response=await opportunityApi(new Request('https://app/api/company-opportunities'),env,'/api/company-opportunities');const [row]=await response.json();
 const request=id=>new Request('https://app/api/company-opportunity',{method:'POST',body:JSON.stringify({id,status:'watch',note:'Investigate'})});
 assert.equal((await opportunityApi(request(row.id),env,'/api/company-opportunity')).status,200);
 assert.ok(data.has('company-decisions/'+row.id));assert.equal((await opportunityApi(request('bad'),env,'/api/company-opportunity')).status,400);
});
