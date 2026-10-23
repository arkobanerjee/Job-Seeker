const json=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
export async function resume(env,runId){
  const r=await fetch(`https://api.github.com/repos/${env.GITHUB_REPOSITORY}/actions/workflows/research.yml/dispatches`,{method:'POST',headers:{Authorization:`Bearer ${env.GITHUB_TOKEN}`,'User-Agent':'Job-Seeker','Content-Type':'application/json',Accept:'application/vnd.github+json'},body:JSON.stringify({ref:env.GITHUB_REF,inputs:{run_id:runId}})});
  return r.status===204;
}
export async function webhook(request,env){
  if(!env.TELEGRAM_WEBHOOK_SECRET || request.headers.get('X-Telegram-Bot-Api-Secret-Token')!==env.TELEGRAM_WEBHOOK_SECRET)return json({error:'Unauthorized'},401);
  if(request.method!=='POST')return json({error:'Method'},405);
  try{
    const update=await request.json(),m=update.message;
    if(!m || m.chat?.type!=='private' || String(m.chat.id)!==env.TELEGRAM_CHAT_ID || String(m.from?.id)!==env.TELEGRAM_CHAT_ID)return json({ignored:true});
    const match=/^\/answer ([a-f0-9]{24}) ([\s\S]{1,4000})$/.exec(m.text||'');
    if(!match)return json({ignored:true});
    const object=await env.STATE.get('questions/'+match[1]+'.json');
    if(!object)return json({ignored:true});
    const question=await object.json(),key='answers/'+match[1]+'.json';
    if(!match[2].trim())return json({ignored:true});
    const answer={answer:match[2],revision:question.revision,run_id:question.run_id};
    const stored=await env.STATE.put(key,JSON.stringify(answer),{onlyIf:{etagDoesNotMatch:'*'}});
    const previous=stored?answer:await (await env.STATE.get(key)).json();
    if(previous.answer!==answer.answer)return json({ignored:true});
    // Duplicate dispatch is harmless: serialized runners load the same checkpoint.
    if(!await resume(env,question.run_id))return json({error:'Answer saved; resume dispatch failed'},502);
    return json({saved:true});
  }catch{return json({error:'Reply handling failed'},500)}
}
export async function questionApi(request,env,path){
  if(path==='/api/question' && request.method==='POST'){
    const q=await request.json();
    if(!/^[a-f0-9]{24}$/.test(q.id)||!/^[a-f0-9]{32}$/.test(q.run_id)||typeof q.prompt!=='string'||q.prompt.length>1500||typeof q.revision!=='string'||q.revision.length>3000)return json({error:'Invalid question'},400);
    await env.STATE.put('questions/'+q.id+'.json',JSON.stringify(q),{onlyIf:{etagDoesNotMatch:'*'}});return json({saved:true});
  }
  if(path.startsWith('/api/answer/') && request.method==='GET'){
    const id=path.split('/').pop();if(!/^[a-f0-9]{24}$/.test(id))return json({error:'Invalid question'},400);
    const object=await env.STATE.get('answers/'+id+'.json');return json(object?await object.json():{answer:null});
  }
  return null;
}
