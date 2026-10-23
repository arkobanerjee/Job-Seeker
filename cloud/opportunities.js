// Evidence-derived company leads. No model calls or outbound messages.
export async function companyOpportunities(registry){
 const rows=[];
 for(const s of registry.signals||[])rows.push({company:s.company,type:'signal',label:s.kind==='technology'?'Relevant technology':s.kind==='hiring'?'Hiring signal':'Company activity',title:s.title,url:s.url,evidence:s.evidence_quote,relevance:s.relevance,observed_at:s.observed_at,event_date:s.event_date,run_id:s.run_id,uncertainty:'No suitable vacancy is established by this signal. Interpretation and source ownership need review.',next:'Check current careers listings and consider a speculative introduction.'});
 for(const m of registry.momentum||[])if(m.status==='observed'&&m.delta>0)rows.push({company:m.company||'Company identity unverified',type:'momentum',label:'Board activity increased',title:'More listings observed on this board',url:m.url,evidence:m.baseline+' → '+m.current+' ('+m.scope+')',observed_at:m.to_date,from_date:m.from_date,uncertainty:'Board growth may be unrelated to your skills. Samples may not represent total vacancies. No matching role or expansion is established.',next:'Inspect which listings changed and whether any match your profile.'});
 for(const l of registry.competitors||[])rows.push({company:l.company,type:'competitor',label:'Company to investigate',title:'Alternative to '+l.seed_company,url:l.url,evidence:l.evidence_quote,observed_at:l.observed_at,run_id:l.run_id,uncertainty:'A competitor relationship alone does not establish hiring, expansion or company suitability.',next:'Verify the company and investigate its products and careers page.'});
 for(const row of rows){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([row.type,row.company,row.url])));row.id=Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,'0')).join('').slice(0,24)}
 return [...new Map(rows.map(r=>[r.id,r])).values()];
}

export async function opportunityApi(request,env,path){
 if(!['/api/company-opportunities','/api/company-opportunity'].includes(path))return null;
 const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 const source=await env.STATE.get('registry/latest.json');
 const rows=await companyOpportunities(source?await source.json():{});
 if(path==='/api/company-opportunities'&&request.method==='GET'){
  for(const row of rows){const stored=await env.STATE.get('company-decisions/'+row.id);row.decision=stored?await stored.json():{status:'new',note:''}}
  return reply(rows);
 }
 if(path==='/api/company-opportunity'&&request.method==='POST'){
  const b=await request.json();
  if(!rows.some(r=>r.id===b.id)||!['new','watch','investigate','draft_outreach','dismissed'].includes(b.status)||typeof b.note!=='string'||b.note.length>4000)return reply({error:'Invalid company decision'},400);
  await env.STATE.put('company-decisions/'+b.id,JSON.stringify({status:b.status,note:b.note,at:new Date().toISOString()}));
  return reply({saved:true});
 }
 return reply({error:'Method not allowed'},405);
}
