import test from 'node:test';
import assert from 'node:assert/strict';
import {reconcileActivity,activitySnapshot} from './activity.js';
import worker from './worker.js';
const run={run_id:'a'.repeat(32),status:'running',started_at:'2026-10-27T14:05:58Z',searches:0,pages:0};
const execution={id:123,status:'completed',conclusion:'failure',created_at:'2026-10-27T14:03:34Z',updated_at:'2026-10-27T14:10:02Z',html_url:'https://github.com/owner/repo/actions/runs/123'};
test('a stopped worker cannot leave its saved checkpoint running',()=>{
 const a=reconcileActivity([run],[execution]);assert.equal(a.current.status,'failed');assert.match(a.current.failure_reason,/first search/);assert.equal(a.current.finished_at,execution.updated_at);assert.equal(run.status,'running');
});
test('unmatched historical checkpoint is unknown, never a confirmed live run',()=>{
 assert.equal(reconcileActivity([run],[]).current.status,'unknown');
 const unrelated={...execution,created_at:'2026-10-28T00:00:00Z',updated_at:'2026-10-28T01:00:00Z'};
 assert.equal(reconcileActivity([run],[unrelated]).current.execution_only,true);
 assert.equal(reconcileActivity([run],[unrelated]).current.run_id,null);
});

test('failure before a new checkpoint is visible without overwriting older research',()=>{
 const old={...run,status:'completed',started_at:'2026-10-26T10:00:00Z'};
 const a=reconcileActivity([old],[execution]);assert.equal(a.current.status,'failed');assert.equal(a.current.execution_only,true);assert.equal(a.current.run_id,null);assert.equal(old.status,'completed');assert.match(a.current.failure_reason,/new research checkpoint/);
});
test('execution id takes precedence over overlapping historical timestamps',()=>{
 assert.equal(reconcileActivity([{...run,execution_id:'456'}],[execution]).current.status,'unknown');
 assert.equal(reconcileActivity([{...run,execution_id:'123'}],[{...execution,conclusion:'cancelled'}]).current.status,'cancelled');
});
test('waiting for an answer is not overwritten by successful worker exit',()=>{
 assert.equal(reconcileActivity([{...run,status:'waiting_user'}],[{...execution,conclusion:'success'}]).current.status,'waiting_user');
});
test('queue and executor remain separate from research completion',()=>{
 const a=reconcileActivity([{...run,status:'completed'}],[{...execution,status:'in_progress'},{...execution,id:234,status:'queued'}]);
 assert.equal(a.current.status,'completed');assert.equal(a.executor.id,123);assert.equal(a.queued.length,1);
});
test('unavailable executor API returns explicit unverified saved state',async()=>{
 const env={STATE:{get:async()=>({json:async()=>[run]})}};const a=await activitySnapshot(env);assert.equal(a.verified,false);assert.equal(a.current.status,'unknown');
});
test('activity requires authentication',async()=>{
 const r=await worker.fetch(new Request('https://example.test/api/activity'),{APP_TOKEN:'private'});assert.equal(r.status,401);
});
