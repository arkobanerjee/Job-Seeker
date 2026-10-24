// Evidence-derived company leads. No model calls or outbound messages.
export async function companyOpportunities(registry){
 const rows=[];
 for(const s of registry.signals||[])rows.push({company:s.company,type:'signal',label:s.evidence_strength||'Unclassified historical signal',qualification_status:s.qualification_status||'investigate',qualification_reasons:s.qualification_reasons||['Historical signal has not passed the new qualification checks'],source_ownership:s.source_ownership||'unverified',title:s.title,url:s.url,evidence:s.evidence_quote,relevance:s.relevance,observed_at:s.observed_at,event_date:s.event_date||'Unknown',run_id:s.run_id,uncertainty:'No suitable vacancy is established by this signal. Interpretation and source ownership need review.',next:'Verify the source and current careers listings before deciding whether to approach the company.'});
 for(const s of registry.rejected_signals||[])rows.push({company:s.company||'Unverified company',type:'rejected_signal',label:'Rejected evidence',qualification_status:'rejected',qualification_reasons:[s.reason],title:s.title,url:s.url,evidence:s.evidence_quote,observed_at:s.observed_at,run_id:s.run_id,uncertainty:'This claim failed source validation and must not be used as established evidence.',next:'Inspect the original source if you want to investigate further.'});
 for(const m of registry.momentum||[])if(m.status==='observed'&&m.delta>0)rows.push({company:m.company||'Company identity unverified',type:'momentum',qualification_status:'investigate',qualification_reasons:['Board activity does not establish company or profile suitability'],label:'Board activity increased',title:'More listings observed on this board',url:m.url,evidence:m.baseline+' → '+m.current+' ('+m.scope+')',observed_at:m.to_date,from_date:m.from_date,uncertainty:'Board growth may be unrelated to your skills. Samples may not represent total vacancies. No matching role or expansion is established.',next:'Inspect which listings changed and whether any match your profile.'});
 for(const l of registry.competitors||[])rows.push({company:l.company,type:'competitor',qualification_status:'investigate',qualification_reasons:['Competitor relationship needs company and profile qualification'],label:'Company to investigate',title:'Alternative to '+l.seed_company,url:l.url,evidence:l.evidence_quote,observed_at:l.observed_at,run_id:l.run_id,uncertainty:'A competitor relationship alone does not establish hiring, expansion or company suitability.',next:'Verify the company and investigate its products and careers page.'});
 for(const row of rows){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([row.type,row.company,row.url])));row.id=Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,'0')).join('').slice(0,24)}
 const grouped=new Map();for(const row of rows){const old=grouped.get(row.id);if(!old||row.qualification_status==='qualified'||old.qualification_status!=='qualified')grouped.set(row.id,row)}
 return [...grouped.values()];
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
