import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {page} from './page.js';

test('opportunity tabs switch panels and job filters without resetting on refresh',()=>{
 const nodes=new Map();
 const document={getElementById(id){if(!nodes.has(id))nodes.set(id,{hidden:false,attributes:{},setAttribute(k,v){this.attributes[k]=v}});return nodes.get(id)}};
 const context=vm.createContext({document});
 vm.runInContext(page.split('<script>')[1].split('</script>')[0],context);
 nodes.get('companiesTab').onclick();
 assert.equal(nodes.get('jobsPanel').hidden,true);
 assert.equal(nodes.get('companyOpportunities').hidden,false);
 assert.equal(nodes.get('category').hidden,true);
 assert.equal(nodes.get('companiesTab').attributes['aria-selected'],'true');
 vm.runInContext('selectOpportunityTab(activeTab)',context);
 assert.equal(nodes.get('companyOpportunities').hidden,false);
 nodes.get('jobsTab').onclick();
 assert.equal(nodes.get('jobsPanel').hidden,false);
 assert.equal(nodes.get('companyOpportunities').hidden,true);
 assert.equal(nodes.get('search').hidden,false);
});

test('weak and rejected company cards render in collapsed investigation section',async()=>{
 const nodes=new Map();
 const make=tag=>({tag,children:[],hidden:false,attributes:{},append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},setAttribute(k,v){this.attributes[k]=v}});
 const document={createElement:make,getElementById(id){if(!nodes.has(id))nodes.set(id,make('div'));return nodes.get(id)}};
 const rows=['qualified','investigate','rejected'].map(status=>({company:'Example',title:status,label:status,qualification_status:status,decision:{status:'new',note:''}}));
 const context=vm.createContext({document,fetch:async()=>({ok:true,json:async()=>rows})});
 vm.runInContext(page.split('<script>')[1].split('</script>')[0],context);
 await vm.runInContext('renderCompanyOpportunities()',context);
 const root=nodes.get('companyRows'),review=root.children.find(n=>n.tag==='details');
 assert.equal(root.children.filter(n=>n.tag==='article').length,1);
 assert.equal(review.children.filter(n=>n.tag==='article').length,2);
 assert.equal(review.open,undefined);
});

test('dismissed companies stay out of the main queue with evidence and notes preserved',async()=>{
 const nodes=new Map();
 const make=tag=>({tag,children:[],hidden:false,attributes:{},append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},setAttribute(k,v){this.attributes[k]=v}});
 const document={createElement:make,getElementById(id){if(!nodes.has(id))nodes.set(id,make('div'));return nodes.get(id)}};
 const row={company:'Example',title:'Funding',labels:['Reported funding'],qualification_status:'qualified',decision:{status:'dismissed',note:'Already checked'},previous_decisions:[{status:'watch',note:'Earlier note'}],evidence_count:1,source_count:2,evidence_items:[{label:'Reported funding',qualification_status:'qualified',title:'Funding',evidence:'An exact quote',sources:[{url:'https://example.com/news',run_id:'one'},{url:'https://copy.example/news',run_id:'two'}]}]};
 const context=vm.createContext({document,fetch:async()=>({ok:true,json:async()=>[row]})});
 vm.runInContext(page.split('<script>')[1].split('</script>')[0],context);
 await vm.runInContext('renderCompanyOpportunities()',context);
 const root=nodes.get('companyRows'),review=root.children.find(n=>n.tag==='details');
 assert.equal(root.children.filter(n=>n.tag==='article').length,0);
 const card=review.children.find(n=>n.tag==='article');
 assert.equal(card.children.filter(n=>n.tag==='details').length,2);
 assert.equal(card.children.find(n=>n.tag==='textarea').value,'Already checked');
});

test('research timeline renders recorded queries, gaps, failures and truncation honestly',()=>{
 const nodes=new Map();
 const make=tag=>({tag,children:[],attributes:{},append(...items){this.children.push(...items)},setAttribute(k,v){this.attributes[k]=v}});
 const document={createElement:make,getElementById(id){if(!nodes.has(id))nodes.set(id,make('div'));return nodes.get(id)}};
 const context=vm.createContext({document});vm.runInContext(page.split('<script>')[1].split('</script>')[0],context);
 context.card=make('article');context.run={stop_reason:'page_limit',unread_pages:3,trace:{scope:'partial_saved_actions',omitted_events:2,note:'Started actions without end receipts have uncertain outcomes',events:[
  {sequence:3,type:'plan',explanation:'Try another title',queries:['junior ML Germany'],coverage_gaps:['Data roles']},
  {sequence:4,type:'page',url:'https://example.com/expired',http_status:410},
  {sequence:5,type:'failure',error_type:'ServiceFailure'}]}};
 vm.runInContext('renderResearchTrace(run,card)',context);
 const texts=node=>[node.textContent||'',...node.children.flatMap(texts)];
 const output=texts(context.card).join(' ');
 for(const value of ['Page limit reached','3 discovered pages remain unread','Partial historical trace','2 earlier events omitted','junior ML Germany','Coverage gap: Data roles','HTTP 410','ServiceFailure'])assert.ok(output.includes(value),value);
 context.card=make('article');context.run={};vm.runInContext('renderResearchTrace(run,card)',context);
 assert.match(texts(context.card).join(' '),/No chronological action receipts/);
});
