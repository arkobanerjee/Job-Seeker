const json=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
export async function archivesApi(request,env,path){
 if(path==='/api/run-archives'&&request.method==='GET'){
  const list=await env.STATE.list({prefix:'evidence/manifests/',limit:1000});
  const rows=await Promise.all(list.objects.map(async x=>(await env.STATE.get(x.key)).json()));
  return json({archives:rows,truncated:!!list.truncated});
 }
 if(!path.startsWith('/api/run-archive/'))return null;
 const id=path.split('/').pop();if(!/^[a-f0-9]{32}$/.test(id))return json({error:'Invalid archive ID'},400);
 if(request.method==='GET'){
  const object=await env.STATE.get('evidence/archives/'+id+'.zip');
  return object?new Response(object.body,{headers:{'Content-Type':'application/zip','Cache-Control':'no-store'}}):json({error:'Not found'},404);
 }
 if(request.method==='PUT'){
  const length=Number(request.headers.get('Content-Length'));if(!length||length>20000000)return json({error:'Archive too large'},413);
  const data=await request.arrayBuffer();if(data.byteLength!==length)return json({error:'Invalid archive length'},400);
  const digest=await crypto.subtle.digest('SHA-256',data),sha256=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');
  const existing=await env.STATE.get('evidence/manifests/'+id+'.json');
  if(existing){const receipt=await existing.json();return receipt.sha256===sha256?json(receipt):json({error:'Archived evidence differs; retained hot copy'},409)}
  const stored=await env.STATE.put('evidence/archives/'+id+'.zip',data,{onlyIf:{etagDoesNotMatch:'*'}});
  if(!stored)return json({error:'Incomplete or concurrent archive; inspect before retry'},409);
  const receipt={id,sha256,bytes:length,created_at:new Date().toISOString()};
  await env.STATE.put('evidence/manifests/'+id+'.json',JSON.stringify(receipt));return json(receipt);
 }
 return json({error:'Method'},405);
}
