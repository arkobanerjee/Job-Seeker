const json=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
const valid=id=>/^[a-f0-9]{32}$/.test(id);
export async function backupApi(request,env,path){
 if(path==='/api/backups'&&request.method==='GET'){
  const list=await env.STATE.list({prefix:'backups/manifests/',limit:1000});
  const rows=await Promise.all(list.objects.map(async x=>await (await env.STATE.get(x.key)).json()));
  return json(rows.sort((a,b)=>b.created_at.localeCompare(a.created_at)));
 }
 if(!path.startsWith('/api/backup/'))return null;
 const id=path.split('/').pop();if(!valid(id))return json({error:'Invalid backup ID'},400);
 if(request.method==='GET'){
  const object=await env.STATE.get('backups/archives/'+id+'.zip');if(!object)return json({error:'Unknown backup'},404);
  return new Response(object.body,{headers:{'Content-Type':'application/zip','Cache-Control':'no-store'}});
 }
 if(request.method==='PUT'){
  const length=Number(request.headers.get('Content-Length'));if(!length||length>20000000)return json({error:'Backup too large'},413);
  const data=await request.arrayBuffer();if(data.byteLength!==length)return json({error:'Invalid backup length'},400);
  const digest=await crypto.subtle.digest('SHA-256',data),sha256=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
  const stored=await env.STATE.put('backups/archives/'+id+'.zip',data,{onlyIf:{etagDoesNotMatch:'*'}});
  if(!stored)return json({error:'Backup already exists'},409);
  const manifest={id,created_at:new Date().toISOString(),bytes:data.byteLength,sha256};
  await env.STATE.put('backups/manifests/'+id+'.json',JSON.stringify(manifest));
  const list=await env.STATE.list({prefix:'backups/manifests/',limit:1000});
  if(!list.truncated){
   const rows=await Promise.all(list.objects.map(async x=>await (await env.STATE.get(x.key)).json()));
   rows.sort((a,b)=>b.created_at.localeCompare(a.created_at)||(a.id===id?-1:b.id===id?1:a.id.localeCompare(b.id)));
   for(const old of rows.slice(5)){if(valid(old.id))await env.STATE.delete(['backups/manifests/'+old.id+'.json','backups/archives/'+old.id+'.zip'])}
  }
  return json(manifest);
 }
 return json({error:'Method'},405);
}
