import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {page} from './page.js';

function harness(failed=false){
 const nodes=new Map(),server={},requests=[];
 const make=tag=>({tag,children:[],value:'',hidden:false,attributes:{},textContent:'',append(...x){this.children.push(...x)},replaceChildren(){this.children=[]},setAttribute(k,v){this.attributes[k]=v}});
 const document={createElement:make,getElementById(id){if(!nodes.has(id))nodes.set(id,make('div'));return nodes.get(id)}};
 document.getElementById('category').value='all';document.getElementById('decisionFilter').value='active';
 const fetch=async(url,options)=>{const body=JSON.parse(options.body);requests.push(body);if(failed)return {ok:false,status:500};server[body.id]={decision:body.decision,note:body.note};return {ok:true,json:async()=>({saved:true})}};
 const context=vm.createContext({document,fetch});vm.runInContext(page.split('<script>')[1].split('</script>')[0],context);
 context.records=[{id:'a'.repeat(24),company:'First',title:'AI Engineer',kind:'vacancy',url:'https://example.com/one'},{id:'b'.repeat(24),company:'Second',title:'Data Analyst',kind:'vacancy',url:'https://example.com/two'},{id:'c'.repeat(24),company:'Earlier',title:'Engineer',kind:'vacancy',url:'https://example.com/three'}];
 vm.runInContext("rows=records;decisions={[records[2].id]:{decision:'applied',note:'Already submitted'}};render()",context);
 return {nodes,context,server,requests};
}
const cards=h=>h.nodes.get('jobs').children.filter(x=>x.tag==='article');
const select=c=>c.children.find(x=>x.tag==='select');
const notes=c=>c.children.find(x=>x.tag==='textarea');
const save=c=>c.children.find(x=>x.tag==='button'&&x.textContent==='Save decision');
const texts=n=>[n.textContent,...n.children.flatMap(texts)].join(' ');

test('applied jobs leave review immediately and remain accessible after reload',async()=>{
 const h=harness();assert.equal(cards(h).length,2);assert.match(h.nodes.get('jobCounts').textContent,/1 applied/);
 const card=cards(h)[0];select(card).value='applied';notes(card).value='Applied on company site';await save(card).onclick();
 assert.equal(cards(h).length,1);assert.equal(h.server['a'.repeat(24)].decision,'applied');assert.match(h.nodes.get('jobFeedback').textContent,/Applied filter/);
 h.nodes.get('decisionFilter').value='applied';vm.runInContext('render()',h.context);
 assert.equal(cards(h).length,2);assert.match(texts(cards(h)[0]),/Application status: Applied/);assert.equal(notes(cards(h)[0]).value,'Applied on company site');
 h.context.persisted={...h.server,['c'.repeat(24)]:{decision:'applied',note:'Already submitted'}};
 vm.runInContext('decisions=persisted;render()',h.context);assert.equal(cards(h).length,2);
});

test('a failed save shows an inline error and does not mark a job applied',async()=>{
 const h=harness(true),card=cards(h)[0];select(card).value='applied';notes(card).value='Keep my note';await save(card).onclick();
 assert.equal(cards(h).length,2);assert.match(texts(card),/Could not save/);assert.equal(save(card).disabled,false);assert.equal(notes(card).value,'Keep my note');
 assert.equal(vm.runInContext("decisions[records[0].id]",h.context),undefined);
});

test('saving one job preserves unsaved notes on another card',async()=>{
 const h=harness(),[first,second]=cards(h);notes(second).value='Unfinished note';notes(second).oninput();
 select(first).value='applied';await save(first).onclick();assert.equal(notes(cards(h)[0]).value,'Unfinished note');
 h.nodes.get('decisionFilter').value='all';vm.runInContext('render()',h.context);assert.equal(cards(h).length,3);
});
