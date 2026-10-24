// Evidence-derived company leads. No model calls or outbound messages.
async function evidenceRows(registry){
 const rows=[];
 for(const s of registry.signals||[])rows.push({company:s.company,type:'signal',label:s.evidence_strength||'Unclassified historical signal',qualification_status:s.qualification_status||'investigate',qualification_reasons:s.qualification_reasons||['Historical signal has not passed the new qualification checks'],source_ownership:s.source_ownership||'unverified',title:s.title,url:s.url,evidence:s.evidence_quote,relevance:s.relevance,observed_at:s.observed_at,event_date:s.event_date||'Unknown',run_id:s.run_id,uncertainty:'No suitable vacancy is established by this signal. Interpretation and source ownership need review.',next:'Verify the source and current careers listings before deciding whether to approach the company.'});
 for(const s of registry.rejected_signals||[])rows.push({company:s.company||'Unverified company',type:'rejected_signal',label:'Rejected evidence',qualification_status:'rejected',qualification_reasons:[s.reason],title:s.title,url:s.url,evidence:s.evidence_quote,observed_at:s.observed_at,run_id:s.run_id,uncertainty:'This claim failed source validation and must not be used as established evidence.',next:'Inspect the original source if you want to investigate further.'});
 for(const m of registry.momentum||[])if(m.status==='observed'&&m.delta>0)rows.push({company:m.company||'Company identity unverified',type:'momentum',qualification_status:'investigate',qualification_reasons:['Board activity does not establish company or profile suitability'],label:'Board activity increased',title:'More listings observed on this board',url:m.url,evidence:m.baseline+' → '+m.current+' ('+m.scope+')',observed_at:m.to_date,from_date:m.from_date,uncertainty:'Board growth may be unrelated to your skills. Samples may not represent total vacancies. No matching role or expansion is established.',next:'Inspect which listings changed and whether any match your profile.'});
 for(const l of registry.competitors||[])rows.push({company:l.company,type:'competitor',qualification_status:'investigate',qualification_reasons:['Competitor relationship needs company and profile qualification'],label:'Company to investigate',title:'Alternative to '+l.seed_company,url:l.url,evidence:l.evidence_quote,observed_at:l.observed_at,run_id:l.run_id,uncertainty:'A competitor relationship alone does not establish hiring, expansion or company suitability.',next:'Verify the company and investigate its products and careers page.'});
 for(const row of rows){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([row.type,row.company,row.url])));row.id=Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,'0')).join('').slice(0,24)}
 return rows;
}

const normalizedName=value=>String(value||'').normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
async function digest(value){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)));return Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,'0')).join('').slice(0,24)}
function sourceKey(value){try{const u=new URL(value);u.hash='';for(const k of [...u.searchParams.keys()])if(/^utm_/i.test(k)||['fbclid','gclid'].includes(k))u.searchParams.delete(k);return u.href}catch{return String(value||'')}}
const statusRank=value=>({qualified:0,investigate:1,rejected:2}[value]??1);
function compare(a,b){return statusRank(a.qualification_status)-statusRank(b.qualification_status)||(Date.parse(b.event_date)||0)-(Date.parse(a.event_date)||0)||String(a.url).localeCompare(String(b.url))||String(a.evidence).localeCompare(String(b.evidence))}

export async function companyOpportunities(registry){
 const aliases=new Map(),ambiguous=new Set();
 for(const c of registry.companies||[])if(c.identity_basis==='user_configured')for(const name of [c.name,...c.aliases||[]]){
  const key=normalizedName(name),previous=aliases.get(key);if(previous&&previous.name!==c.name)ambiguous.add(key);else aliases.set(key,c);
 }
 const groups=new Map();
 for(const row of await evidenceRows(registry)){
  const name=normalizedName(row.company),profile=ambiguous.has(name)?null:aliases.get(name);
  const anonymous=['','unverified company','company identity unverified'].includes(name);
  const key=anonymous?'unidentified:'+(row.url?sourceKey(row.url):JSON.stringify([row.run_id,row.title,row.evidence])):normalizedName(profile?.name||row.company);
  if(!groups.has(key))groups.set(key,{name:profile?.name||row.company,profile,rows:[],key});groups.get(key).rows.push(row);
 }
 const cards=[];
 for(const group of groups.values()){
  const rows=group.rows.sort(compare),primary=rows[0],items=new Map();
  for(const row of rows){
   // Matching excerpts are copies, not independent corroboration. Keep every receipt.
   const key=JSON.stringify([row.type,row.qualification_status,row.label,row.type==='momentum'?[row.from_date,row.observed_at]:row.event_date||'Unknown',String(row.evidence||'').trim().replace(/\s+/g,' ').toLowerCase()]);
   if(!items.has(key))items.set(key,{...row,sources:[],labels:[]});const item=items.get(key);
   if(!item.labels.includes(row.label))item.labels.push(row.label);
   const receipt={url:row.url,run_id:row.run_id,observed_at:row.observed_at};
   if(!item.sources.some(s=>sourceKey(s.url)===sourceKey(receipt.url)&&s.run_id===receipt.run_id))item.sources.push(receipt);
  }
  const id=await digest(['company',group.key]);
  const legacyIds=new Set(rows.map(r=>r.id));
  for(const alias of group.profile?.aliases||[])legacyIds.add(await digest(['company',normalizedName(alias)]));
  legacyIds.delete(id);
  cards.push({...primary,id,type:'company',company:group.name,identity_basis:group.profile?'user_configured':'normalized_name_unverified',
   evidence_items:[...items.values()],labels:[...new Set(rows.filter(r=>r.qualification_status===primary.qualification_status).map(r=>r.label))],
   legacy_ids:[...legacyIds],evidence_count:items.size,source_count:new Set(rows.map(r=>sourceKey(r.url))).size,
   aggregation_note:'Grouped by company name or configured aliases. Matching excerpts are grouped as copies; source count does not establish independent corroboration.'});
 }
 return cards.sort((a,b)=>statusRank(a.qualification_status)-statusRank(b.qualification_status)||a.company.localeCompare(b.company));
}

export async function opportunityApi(request,env,path){
 if(!['/api/company-opportunities','/api/company-opportunity'].includes(path))return null;
 const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
 const source=await env.STATE.get('registry/latest.json');
 const rows=await companyOpportunities(source?await source.json():{});
 if(path==='/api/company-opportunities'&&request.method==='GET'){
  for(const row of rows){
   const direct=await env.STATE.get('company-decisions/'+row.id),history=[];
   for(const id of row.legacy_ids){const stored=await env.STATE.get('company-decisions/'+id);if(stored)history.push({id,...await stored.json()})}
   history.sort((a,b)=>String(b.at||'').localeCompare(String(a.at||''))||a.id.localeCompare(b.id));
   row.decision=direct?await direct.json():history[0]||{status:'new',note:''};
   row.previous_decisions=history;
  }
  return reply(rows);
 }
 if(path==='/api/company-opportunity'&&request.method==='POST'){
  const b=await request.json();
  const target=rows.find(r=>r.id===b.id||r.legacy_ids.includes(b.id));
  if(!target||!['new','watch','investigate','draft_outreach','dismissed'].includes(b.status)||typeof b.note!=='string'||b.note.length>4000)return reply({error:'Invalid company decision'},400);
  await env.STATE.put('company-decisions/'+target.id,JSON.stringify({status:b.status,note:b.note,at:new Date().toISOString()}));
  return reply({saved:true});
 }
 return reply({error:'Method not allowed'},405);
}
