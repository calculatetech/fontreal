// Test-only client for the application's native Node inspector.
import fs from 'node:fs';
const [port,expressionFile]=process.argv.slice(2);
const targets=await (await fetch(`http://127.0.0.1:${Number(port)}/json/list`)).json();
if (targets.length!==1) throw new Error('Expected one owned application inspector');
const socket=new WebSocket(targets[0].webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
const result=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(new Error('Application inspection timed out')),20000);
  socket.onmessage=event=>{
    const message=JSON.parse(event.data);
    if(message.id!==1)return;
    clearTimeout(timer);
    if(message.error || message.result.exceptionDetails)reject(new Error('Application inspection failed: '+(message.result?.exceptionDetails?.exception?.className || 'protocol error')));
    else resolve(message.result.result.value);
  };
  socket.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression:fs.readFileSync(expressionFile,'utf8'),awaitPromise:true,returnByValue:true}}));
});
socket.close();
process.stdout.write(JSON.stringify(result)+'\n');
