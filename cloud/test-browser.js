import {JSDOM} from 'jsdom';
import {page} from './page.js';
import vm from 'node:vm';
export function browser(t,fetch=async()=>({ok:true,json:async()=>({})})){
 const dom=new JSDOM(page,{url:'https://workspace.test',runScripts:'outside-only'});
 const context=dom.getInternalVMContext();
 dom.window.fetch=fetch;vm.runInContext(page.split('<script>')[1].split('</script>')[0],context);
 t.after(()=>dom.window.close());
 return {window:dom.window,document:dom.window.document,eval:code=>vm.runInContext(code,context)};
}
