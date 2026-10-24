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
