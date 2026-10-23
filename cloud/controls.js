export async function readControl(env,id){
 const object=await env.STATE.get('controls/'+id+'.json');return object?await object.json():{action:'run',revision:0};
}
export async function setControl(env,id,action){
 const key='controls/'+id+'.json',object=await env.STATE.get(key),old=object?await object.json():{action:'run',revision:0};
 if(old.action==='cancel'&&action!=='cancel')return {error:'Cancelled runs cannot resume'};
 const value={action,revision:old.revision+1,at:new Date().toISOString()};
 const stored=await env.STATE.put(key,JSON.stringify(value),{onlyIf:object?{etagMatches:object.etag}:{etagDoesNotMatch:'*'}});
 return stored?value:{error:'Concurrent control update; refresh and retry'};
}
