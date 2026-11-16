// Developer-only Chromium protocol client. Node inspect is not used.
import fs from 'node:fs';
const [endpoint,commandFile]=process.argv.slice(2);
const command=JSON.parse(fs.readFileSync(commandFile,'utf8'));
const socket=new WebSocket(endpoint);
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
const result=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(new Error('Chromium protocol timed out')),20000);
  socket.onclose=()=>{
    clearTimeout(timer);
    if(command.method==='Browser.close')resolve({});
    else reject(new Error('Chromium protocol closed before replying'));
  };
  socket.onmessage=event=>{
    const message=JSON.parse(event.data);
    if(message.id!==1)return;
    clearTimeout(timer);
    if(message.error || message.result?.exceptionDetails)reject(new Error('Chromium protocol request failed: '+(message.error?.code ?? message.result.exceptionDetails.exception?.className ?? 'exception')));
    else resolve(message.result);
  };
  socket.send(JSON.stringify({id:1,...command}));
});
socket.close();
process.stdout.write(JSON.stringify(result)+'\n');
