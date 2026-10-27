import test from 'node:test';
import assert from 'node:assert/strict';
import {browser} from './test-browser.js';
function harness(t,failed=false){
 const server={},requests=[];
 const h=browser(t,async(url,options)=>{const body=JSON.parse(options.body);requests.push(body);if(failed)return {ok:false,status:500,json:async()=>({error:'Saving failed'})};server[body.id]={decision:body.decision,note:body.note};return {ok:true,json:async()=>({saved:true})}});
 h.window.records=[{id:'a'.repeat(24),company:'First',title:'AI Engineer',kind:'vacancy',url:'https://example.com/one'},{id:'b'.repeat(24),company:'Second',title:'Data Analyst',kind:'vacancy',url:'https://example.com/two'},{id:'c'.repeat(24),company:'Earlier',title:'Engineer',kind:'vacancy',url:'https://example.com/three'}];
 h.eval("rows=records;decisions={[records[2].id]:{decision:'applied',note:'Already submitted'}};render()");return {...h,server,requests};
}
const cards=h=>[...h.document.querySelectorAll('.job-card')];
const select=c=>c.querySelector('select');
const notes=c=>c.querySelector('textarea');
const save=c=>[...c.querySelectorAll('button')].find(b=>b.textContent==='Save decision');
test('applied jobs leave review and remain accessible with saved notes',async t=>{
 const h=harness(t);assert.equal(cards(h).length,2);const card=cards(h)[0];select(card).value='applied';notes(card).value='Applied on company site';await save(card).onclick();
 assert.equal(cards(h).length,1);assert.equal(h.server['a'.repeat(24)].decision,'applied');assert.match(h.document.getElementById('jobFeedback').textContent,/Applied filter/);
 h.document.getElementById('decisionFilter').value='applied';h.eval('render()');assert.equal(cards(h).length,2);assert.equal(notes(cards(h)[0]).value,'Applied on company site');assert.match(cards(h)[0].querySelector('summary').textContent,/Applied/);
 h.window.persisted={...h.server,['c'.repeat(24)]:{decision:'applied',note:'Already submitted'}};h.eval('decisions=persisted;render()');assert.equal(cards(h).length,2);
});
test('failed save keeps the decision unchanged and the draft visible',async t=>{
 const h=harness(t,true),card=cards(h)[0];select(card).value='applied';notes(card).value='Keep my note';await save(card).onclick();assert.equal(cards(h).length,2);assert.match(card.textContent,/Could not save/);assert.equal(save(card).disabled,false);assert.equal(notes(card).value,'Keep my note');assert.equal(h.eval('decisions[records[0].id]'),undefined);
});
test('saving one job preserves another draft and expanded card',async t=>{
 const h=harness(t),[first,second]=cards(h);second.open=true;notes(second).value='Unfinished note';notes(second).oninput();select(first).value='applied';await save(first).onclick();assert.equal(notes(cards(h)[0]).value,'Unfinished note');assert.equal(cards(h)[0].open,true);h.document.getElementById('decisionFilter').value='all';h.eval('render()');assert.equal(cards(h).length,3);
});
