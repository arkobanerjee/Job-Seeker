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
    let match=/^\/answer ([a-f0-9]{24}) ([\s\S]{1,4000})$/.exec(m.text||'');
    if(!match && m.reply_to_message?.from?.is_bot && typeof m.text==='string' && m.text.length<=4000){
      const mapping=await env.STATE.get('telegram-messages/'+m.reply_to_message.message_id+'.json');
      if(mapping){const x=await mapping.json();match=[null,x.id,m.text]}
      else {
        // Compatibility with questions sent before message-ID receipts existed.
        const old=/Reply using: \/answer ([a-f0-9]{24}) /.exec(m.reply_to_message.text||'');
        if(old)match=[null,old[1],m.text];
        else if((m.reply_to_message.text||'').startsWith('Job Seeker needs input'))return json({error:'Delivery receipt pending'},503);
      }
    }
    // Ordinary chat text is unambiguous only with exactly one unanswered question.
    if(!match && typeof m.text==='string' && m.text.trim() && m.text.length<=4000 && !m.text.startsWith('/')){
      const list=await env.STATE.list({prefix:'questions/',limit:100});
      if(!list.truncated){
        const pending=[];
        for(const item of list.objects){
          const q=await (await env.STATE.get(item.key)).json();
          if(!await env.STATE.get('answers/'+q.id+'.json'))pending.push(q);
          if(pending.length>1)break;
        }
        if(pending.length===1)match=[null,pending[0].id,m.text];
      }
    }
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
  if(path==='/api/questions' && request.method==='GET'){
    const list=await env.STATE.list({prefix:'questions/',limit:100});const questions=[];
    for(const entry of list.objects){
      const q=await (await env.STATE.get(entry.key)).json();
      if(!await env.STATE.get('answers/'+q.id+'.json'))questions.push({id:q.id,run_id:q.run_id,revision:q.revision,prompt:q.prompt,reason:q.reason});
    }
    return json({questions,more:!!list.truncated});
  }
  if(path==='/api/answer' && request.method==='POST'){
    const b=await request.json();
    if(!/^[a-f0-9]{24}$/.test(b.id)||typeof b.answer!=='string'||!b.answer.trim()||b.answer.length>4000)return json({error:'Invalid answer'},400);
    const object=await env.STATE.get('questions/'+b.id+'.json');if(!object)return json({error:'Unknown question'},404);
    const q=await object.json();if(b.revision!==q.revision)return json({error:'Stale question'},409);
    const answer={answer:b.answer,revision:q.revision,run_id:q.run_id},key='answers/'+q.id+'.json';
    const stored=await env.STATE.put(key,JSON.stringify(answer),{onlyIf:{etagDoesNotMatch:'*'}});
    const previous=stored?answer:await (await env.STATE.get(key)).json();
    if(previous.answer!==answer.answer)return json({error:'Already answered'},409);
    return await resume(env,q.run_id)?json({saved:true,queued:true}):json({error:'Answer saved; resume failed. Retry the same answer.'},502);
  }
  if(path==='/api/question' && request.method==='POST'){
    const q=await request.json();
    if(!/^[a-f0-9]{24}$/.test(q.id)||!/^[a-f0-9]{32}$/.test(q.run_id)||typeof q.prompt!=='string'||q.prompt.length>1500||typeof q.revision!=='string'||q.revision.length>3000)return json({error:'Invalid question'},400);
    await env.STATE.put('questions/'+q.id+'.json',JSON.stringify(q),{onlyIf:{etagDoesNotMatch:'*'}});
    if(Number.isSafeInteger(q.message_id) && q.message_id>0){
      const original=await (await env.STATE.get('questions/'+q.id+'.json')).json();
      if(original.revision!==q.revision || original.run_id!==q.run_id)return json({error:'Stale receipt'},409);
      await env.STATE.put('telegram-messages/'+q.message_id+'.json',JSON.stringify({id:q.id}),{onlyIf:{etagDoesNotMatch:'*'}});
    }
    return json({saved:true});
  }
  if(path.startsWith('/api/answer/') && request.method==='GET'){
    const id=path.split('/').pop();if(!/^[a-f0-9]{24}$/.test(id))return json({error:'Invalid question'},400);
    const object=await env.STATE.get('answers/'+id+'.json');return json(object?await object.json():{answer:null});
  }
  return null;
}
