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
