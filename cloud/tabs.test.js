import test from 'node:test';
import assert from 'node:assert/strict';
import {browser} from './test-browser.js';
test('evaluation view preserves full receipts and safe spreadsheet exports',async t=>{
 const data={note:'Attribution is not causal improvement',by_purpose:{},calls:[],searches:[{id:'second',query:'=FORMULA',parent_search_id:'first',change_reason:'Too many senior roles',expected_improvement:'Find junior roles',status:'success',metrics:{},results:[{rank:1,title:'Junior AI engineer',url:'https://example.com/job',snippet:'Complete search snippet'}]}]};
 const h=browser(t,async()=>({ok:true,json:async()=>data}));h.window.card=h.document.createElement('article');h.window.run={run_id:'a'.repeat(32),evaluation_available:true};h.eval('renderEvaluation(run,card)');await h.window.card.querySelector('button').onclick();for(const value of ['Too many senior roles','Find junior roles','Complete search snippet','Download full JSON log'])assert.ok(h.window.card.textContent.includes(value),value);h.window.data=data;assert.ok(h.eval('evaluationCsv(data)').includes("'=FORMULA"));
});
test('tabs preserve selection and support keyboard navigation',t=>{
 const h=browser(t);h.document.getElementById('companiesTab').click();assert.equal(h.document.getElementById('jobsPanel').hidden,true);assert.equal(h.document.getElementById('companyOpportunities').hidden,false);assert.equal(h.document.getElementById('companiesTab').getAttribute('aria-selected'),'true');
 h.document.getElementById('opportunityTabs').dispatchEvent(new h.window.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}));assert.equal(h.document.getElementById('jobsPanel').hidden,false);assert.equal(h.document.getElementById('jobsTab').tabIndex,0);
});
test('company filters separate rejected evidence and preserve editable notes',async t=>{
 const rows=['qualified','investigate','rejected'].map((status,i)=>({id:String(i).repeat(24),company:'Example '+i,title:status,label:status,qualification_status:status,evidence_count:1,decision:{status:'new',note:''}}));const h=browser(t,async()=>({ok:true,json:async()=>rows}));await h.eval('renderCompanyOpportunities()');assert.equal(h.document.querySelectorAll('.company-card').length,2);const card=h.document.querySelector('.company-card');card.open=true;card.querySelector('textarea').value='My draft';card.querySelector('textarea').oninput();h.document.getElementById('companyFilter').value='all';h.eval('renderCompanyRows()');assert.equal(h.document.querySelectorAll('.company-card').length,3);assert.equal(h.document.querySelector('.company-card textarea').value,'My draft');assert.equal(h.document.querySelector('.company-card').open,true);
});
test('dismissed companies are hidden by default with evidence and prior notes retained',async t=>{
 const row={id:'a'.repeat(24),company:'Example',title:'Funding',labels:['Reported funding'],qualification_status:'qualified',decision:{status:'dismissed',note:'Already checked'},previous_decisions:[{status:'watch',note:'Earlier note'}],evidence_count:1,source_count:1,evidence_items:[{label:'Reported funding',qualification_status:'qualified',title:'Funding',evidence:'An exact quote',sources:[{url:'https://example.com/news',run_id:'one'}]}]};const h=browser(t,async()=>({ok:true,json:async()=>[row]}));await h.eval('renderCompanyOpportunities()');assert.equal(h.document.querySelectorAll('.company-card').length,0);h.document.getElementById('companyFilter').value='dismissed';h.eval('renderCompanyRows()');const card=h.document.querySelector('.company-card');assert.equal(card.querySelector('textarea').value,'Already checked');assert.match(card.textContent,/Earlier note/);assert.match(card.textContent,/An exact quote/);
});
test('research timeline reports saved evidence and omissions honestly',t=>{
 const h=browser(t);h.window.card=h.document.createElement('article');h.window.run={stop_reason:'page_limit',unread_pages:3,trace:{scope:'partial_saved_actions',omitted_events:2,note:'Started actions have uncertain outcomes',events:[{sequence:3,type:'plan',explanation:'Try another title',queries:['junior ML Germany'],coverage_gaps:['Data roles']},{sequence:4,type:'page',url:'https://example.com/expired',http_status:410},{sequence:5,type:'failure',error_type:'ServiceFailure'}]}};h.eval('renderResearchTrace(run,card)');for(const value of ['Page limit reached','3 discovered pages remain unread','Partial historical trace','2 earlier events omitted','junior ML Germany','Coverage gap: Data roles','HTTP 410','ServiceFailure'])assert.ok(h.window.card.textContent.includes(value),value);
 h.window.card=h.document.createElement('article');h.window.run={};h.eval('renderResearchTrace(run,card)');assert.match(h.window.card.textContent,/No chronological action receipts/);
});

test('a queued request never inherits the previous run failure or counters',t=>{
 const h=browser(t);h.window.snapshot={verified:true,current:{run_id:'a'.repeat(32),status:'failed',mode:'discovery',searches:3,pages:5,failure_reason:'Earlier failure',trace:{events:[]}},queued:[{id:1,status:'queued',mode:'company'}]};h.eval('activityData=snapshot;renderActivity()');
 assert.equal(h.document.getElementById('activityState').textContent,'Queued');
 assert.equal(h.document.getElementById('activityTitle').textContent,'Discovering companies');
 assert.equal(h.document.getElementById('activityError').hidden,true);
 assert.equal(h.document.getElementById('activityPages').textContent,'—');
});

test('refreshing operation history preserves a pending answer draft',async t=>{
 const payload={questions:{questions:[{id:'q1',revision:1,prompt:'Which locations should I search?'}]},runs:[],notifications:[],backups:[]};
 const h=browser(t,async url=>({ok:true,json:async()=>payload[url.split('/').pop()]}));await h.eval('renderOperations()');const answer=h.document.querySelector('#questionRows textarea');answer.value='Berlin and remote';answer.oninput();await h.eval('renderOperations()');assert.equal(h.document.querySelector('#questionRows textarea').value,'Berlin and remote');
});
