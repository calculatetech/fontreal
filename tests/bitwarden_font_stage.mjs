const [endpoint,text]=process.argv.slice(2);
const socket=new WebSocket(endpoint);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});let sequence=0;
async function call(method,params={}){const id=++sequence;return await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('CDP timed out')),20000);socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.id!==id)return;clearTimeout(timer);if(message.error||message.result?.exceptionDetails)reject(new Error('CDP request failed'));else resolve(message.result);};socket.send(JSON.stringify({id,method,params}));});}
try{
  await call('Page.bringToFront');
  const expression=`(async()=>{const input=document.querySelector('input[type=email]');if(!input)throw Error('Missing native input');input.value=${JSON.stringify(text)};input.dispatchEvent(new Event('input',{bubbles:true}));input.blur();await document.fonts.ready;await Promise.race([Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{}))),new Promise((_,reject)=>setTimeout(()=>reject(Error('Animation timed out')),5000))]);await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));const s=getComputedStyle(input),r=input.getBoundingClientRect();return {text:input.value,title:document.title,style:Object.fromEntries(['fontFamily','fontSize','fontWeight','fontStyle','fontOpticalSizing','fontVariationSettings','fontStretch','fontSizeAdjust','fontFeatureSettings','fontKerning','letterSpacing','lineHeight','color','backgroundColor','paddingLeft','paddingTop','borderLeftWidth','borderTopWidth','textAlign','textIndent','direction','transform','opacity','filter'].map(key=>[key,s[key]])),rect:{x:r.x,y:r.y,width:r.width,height:r.height},viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,scrollLeft:input.scrollLeft,blurred:document.activeElement!==input};})()`;
  const measure=(await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true})).result.value;
  await call('DOM.enable');await call('CSS.enable');const doc=await call('DOM.getDocument',{depth:-1,pierce:true});
  const node=await call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'input[type=email]'});
  const fonts=await call('CSS.getPlatformFontsForNode',{nodeId:node.nodeId});
  const screenshot=await call('Page.captureScreenshot',{format:'png',fromSurface:true});
  process.stdout.write(JSON.stringify({measure,fonts,screenshot:screenshot.data})+'\n');
}finally{socket.close();}
