// One-owner control plane. All data endpoints require a high-entropy bearer secret.
import { page } from './page.js';
import { webhook,questionApi } from './questions.js';
const headers = {'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
const reply = (body,status=200) => new Response(JSON.stringify(body),{status,headers});
const keyFor = path => path === '/api/state' ? 'state/latest.zip' : path === '/api/catalog' ? 'catalog/latest.json' : null;
export default {
  async fetch(request,env) {
    const u=new URL(request.url);
    if(u.pathname==='/telegram') return webhook(request,env);
    if(u.pathname==='/' && request.method==='GET') return new Response(page,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"}});
    if(!env.APP_TOKEN || request.headers.get('Authorization')!==`Bearer ${env.APP_TOKEN}`) return reply({error:'Unauthorized'},401);
    if(request.headers.get('Origin') && request.headers.get('Origin')!==u.origin) return reply({error:'Invalid origin'},403);
    try {
      const questionResponse=await questionApi(request,env,u.pathname);
      if(questionResponse)return questionResponse;
      if(u.pathname==='/api/monitor-status' && request.method==='GET') {
        const object=await env.STATE.get('monitor-status.json');return reply(object?await object.json():{status:'not_checked'});
      }
      if(u.pathname==='/api/monitor-status' && request.method==='PUT') {
        const body=await request.json();
        if(!['skipped','completed','partial','failed','waiting_user'].includes(body.status))return reply({error:'Invalid status'},400);
        await env.STATE.put('monitor-status.json',JSON.stringify({...body,at:new Date().toISOString()}));return reply({saved:true});
      }
      if(u.pathname==='/api/schedule-claim' && request.method==='POST') {
        const {date}=await request.json();if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return reply({error:'Invalid date'},400);
        const stored=await env.STATE.put('schedule/'+date+'.json',JSON.stringify({date}),{onlyIf:{etagDoesNotMatch:'*'}});return reply({claimed:!!stored});
      }
      if(u.pathname==='/api/budget' && request.method==='GET') {
        const object=await env.STATE.get('budget.json');
        return object ? reply(await object.json()) : reply({error:'Initialize state before running'},409);
      }
      if(u.pathname==='/api/initialize' && request.method==='POST') {
        const body=await request.json();
        if(!Number.isFinite(body.already_reserved) || body.already_reserved<0 || body.already_reserved>5) return reply({error:'Invalid migration balance'},400);
        const result=await env.STATE.put('budget.json',JSON.stringify({reserved:body.already_reserved,ceiling:5,reservations:[]}),{onlyIf:{etagDoesNotMatch:'*'}});
        return result ? reply({initialized:true}) : reply({error:'Already initialized'},409);
      }
      if(u.pathname==='/api/reserve' && request.method==='POST') {
        const {id,amount}=await request.json();
        if(!/^[a-zA-Z0-9_-]{1,80}$/.test(id) || !Number.isFinite(amount) || amount<=0 || amount>2) return reply({error:'Invalid reservation'},400);
        const object=await env.STATE.get('budget.json');
        if(!object) return reply({error:'Budget is not initialized'},409);
        const budget=await object.json();
        // Idempotency for a response lost after a successful write.
        const previous=budget.reservations.find(x=>x.id===id);
        if(previous) return previous.amount===amount ? reply({reserved:true}) : reply({error:'Reservation mismatch'},409);
        if(budget.reserved+amount>budget.ceiling) return reply({error:'Review budget reached'},402);
        budget.reserved+=amount; budget.reservations.push({id,amount,at:new Date().toISOString()});
        const stored=await env.STATE.put('budget.json',JSON.stringify(budget),{onlyIf:{etagMatches:object.etag}});
        return stored ? reply({reserved:true}) : reply({error:'Concurrent reservation; retry later'},409);
      }
      if(u.pathname==='/api/run' && request.method==='POST') {
        if(!env.GITHUB_TOKEN) return reply({error:'GitHub dispatch not configured'},409);
        const body=await request.json(),mode=body.mode||'discovery';
        if(!['discovery','monitor'].includes(mode))return reply({error:'Invalid research mode'},400);
        const response=await fetch(`https://api.github.com/repos/${env.GITHUB_REPOSITORY}/actions/workflows/research.yml/dispatches`,{
          method:'POST',headers:{Authorization:`Bearer ${env.GITHUB_TOKEN}`,'User-Agent':'Job-Seeker','Accept':'application/vnd.github+json','Content-Type':'application/json'},body:JSON.stringify({ref:env.GITHUB_REF,inputs:{mode}})});
        return response.status===204 ? reply({queued:true}) : reply({error:'GitHub dispatch failed',status:response.status},502);
      }
      if(u.pathname==='/api/decisions' && request.method==='GET') {
        const list=await env.STATE.list({prefix:'decisions/',limit:1000});
        const entries=await Promise.all(list.objects.map(async x=>[x.key.split('/')[1],await (await env.STATE.get(x.key)).json()]));
        return reply(Object.fromEntries(entries));
      }
      if(u.pathname==='/api/settings' && request.method==='GET') {
        const object=await env.STATE.get('settings.json');
        return object ? reply(await object.json()) : reply({error:'Settings not initialized'},404);
      }
      if(u.pathname==='/api/settings' && request.method==='PUT') {
        const body=await request.json(), allowed=['config.toml','prompts/master.md','private/profile.md','private/resume.md'];
        if(Object.keys(body).some(k=>!allowed.includes(k)) || allowed.slice(0,3).some(k=>typeof body[k]!=='string') || Object.values(body).some(v=>typeof v!=='string'||v.length>30000)) return reply({error:'Invalid settings'},400);
        await env.STATE.put('settings.json',JSON.stringify(body)); return reply({saved:true});
      }
      if(u.pathname==='/api/decision' && request.method==='POST') {
        const b=await request.json();
        if(!/^[a-f0-9]{24}$/.test(b.id) || !['unreviewed','saved','apply_anyway','applied','dismissed'].includes(b.decision) || typeof b.note!=='string' || b.note.length>4000) return reply({error:'Invalid decision'},400);
        await env.STATE.put(`decisions/${b.id}`,JSON.stringify({decision:b.decision,note:b.note,at:new Date().toISOString()}));
        return reply({saved:true});
      }
      if(u.pathname==='/api/registry' && request.method==='GET') {
        const object=await env.STATE.get('registry/latest.json');
        return reply(object?await object.json():{companies:[],sources:[]});
      }
      if(u.pathname==='/api/registry' && request.method==='PUT') {
        const body=await request.json();
        if(!Array.isArray(body.companies)||!Array.isArray(body.sources)||JSON.stringify(body).length>2000000)return reply({error:'Invalid registry'},400);
        await env.STATE.put('registry/latest.json',JSON.stringify(body));return reply({saved:true});
      }
      const key=keyFor(u.pathname);
      if(key && request.method==='GET') {
        const object=await env.STATE.get(key);
        return object ? new Response(object.body,{headers:{...headers,'Content-Type':key.endsWith('.zip')?'application/zip':'application/json'}}) : reply({error:'Not initialized'},404);
      }
      if(key && request.method==='PUT') {
        const length=Number(request.headers.get('Content-Length'));
        if(!length || length>20000000) return reply({error:'State limit is 20 MB'},413);
        await env.STATE.put(key,request.body); return reply({saved:true});
      }
      return reply({error:'Not found'},404);
    } catch { return reply({error:'Request failed'},500); }
  }
};
