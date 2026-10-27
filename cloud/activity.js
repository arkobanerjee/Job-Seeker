// Combine saved research receipts with the actual executor. Missing evidence stays unknown.
import {readControl} from './controls.js';
const active = new Set(['queued','in_progress','waiting','pending','requested']);
export function reconcileActivity(runs, executions, checkedAt=new Date().toISOString()) {
  const latest=runs[0]||null;
  const linked=latest && executions.find(e=> latest.execution_id
    ? String(e.id)===String(latest.execution_id)
    : Date.parse(e.created_at)<=Date.parse(latest.started_at) && Date.parse(e.updated_at)+5000>=Date.parse(latest.started_at));
  let current=latest?{...latest}:null;
  if(current?.status==='running') {
    if(!linked) current={...current,status:'unknown',status_note:'The saved run says running, but its worker could not be verified.'};
    else if(linked.status==='completed') current={...current,status:linked.conclusion==='cancelled'?'cancelled':linked.conclusion==='success'?'interrupted':'failed',finished_at:linked.updated_at,
      failure_reason:current.failure_reason||(linked.conclusion==='success'?'The worker finished without publishing a final research status.':
        !current.searches&&!current.pages?'The research worker stopped before recording its first search. Check the execution log for the failure details.':'The research worker stopped unexpectedly. Saved progress is retained; check the execution log for details.')};
  }
  if(current&&linked) current.execution_url=linked.html_url;
  const newest=executions[0];
  if(newest?.status==='completed'&&(!latest||(!linked&&Date.parse(newest.created_at)>Date.parse(latest.started_at)))) {
    current={run_id:null,status:newest.conclusion==='success'?'completed':newest.conclusion==='cancelled'?'cancelled':'failed',mode:newest.mode||'worker',
      started_at:newest.run_started_at||newest.created_at,finished_at:newest.updated_at,execution_url:newest.html_url,execution_only:true,
      failure_reason:newest.conclusion==='success'?null:'The worker stopped before publishing a new research checkpoint. View the execution log for the failure details.'};
  }
  const running=executions.find(e=>e.status==='in_progress');
  const pending=executions.filter(e=>active.has(e.status)&&e.status!=='in_progress');
  return {checked_at:checkedAt,verified:true,current,executor:running||null,queued:pending,latest_execution:executions[0]||null};
}

export async function activitySnapshot(env) {
  const object=await env.STATE.get('runs/latest.json');
  const runs=object?await object.json():[];
  const fallback={...reconcileActivity(runs,[]),verified:false,verification_note:'Execution status is unavailable. Saved results remain available.'};
  if(!env.GITHUB_TOKEN||!env.GITHUB_REPOSITORY)return fallback;
  try {
    const response=await fetch(`https://api.github.com/repos/${env.GITHUB_REPOSITORY}/actions/workflows/research.yml/runs?per_page=15`,{
      headers:{Authorization:`Bearer ${env.GITHUB_TOKEN}`,'User-Agent':'Job-Seeker',Accept:'application/vnd.github+json'},signal:AbortSignal.timeout(8000)});
    if(!response.ok)return fallback;
    const body=await response.json();
    if(!Array.isArray(body.workflow_runs))return fallback;
    const executions=body.workflow_runs.map(e=>{
      const value=Object.fromEntries(['id','status','conclusion','created_at','updated_at','run_started_at','html_url','event'].map(k=>[k,e[k]]));
      const mode=String(e.display_title||'').split(' · ')[0];
      if(['discovery','company','monitor','boards','backup','restore','diagnostics','maintenance','notifications','scheduled'].includes(mode))value.mode=mode;
      return value;
    });
    const snapshot=reconcileActivity(runs,executions);
    if(snapshot.current?.status==='running')snapshot.control_request=(await readControl(env,snapshot.current.run_id)).action;
    return snapshot;
  }catch{return fallback}
}
