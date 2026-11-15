'use strict';
const {app, BrowserWindow, ipcMain} = require('electron');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const config = JSON.parse(fs.readFileSync(process.env.FONTREAL_FIXTURE_CONFIG, 'utf8'));
app.setPath('userData', config.userData);
app.enableSandbox();
let server;
let quitPoll;
app.on('will-quit', () => { clearInterval(quitPoll); if (server) server.close(); });

app.whenReady().then(async () => {
  const dark = config.palette === 'dark';
  const html = `<!doctype html><meta charset="utf-8"><title>Fontreal stock owner fixture</title>
<style>
@font-face {font-family:Fixture;src:url('/font')}
html,body {margin:0;background:${dark ? '#202124' : '#ffffff'};color:${dark ? '#f1f3f4' : '#000000'}}
#marker {position:absolute;left:16px;top:16px;width:8px;height:8px;background:rgb(17,91,143)}
#control {position:absolute;left:40px;top:16px;width:18px;height:18px;background:rgb(53,89,131)}
#text {position:absolute;left:24px;top:64px;font:normal 15px Fixture;white-space:pre}
</style><div id="marker"></div><div id="control"></div><div id="text"><span id="prefix">m8Wm8W</span><span id="later"></span></div>`;
  server = http.createServer((request, response) => {
    if (request.url === '/') {
      response.writeHead(200, {'Content-Type':'text/html', 'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; font-src 'self'"});
      response.end(html);
    } else if (request.url === '/font') {
      response.writeHead(200, {'Content-Type':'font/otf'});
      response.end(fs.readFileSync(config.font));
    } else { response.writeHead(404); response.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const window = new BrowserWindow({width:480, height:220, useContentSize:true, frame:false,
    show:true, backgroundColor:dark ? '#202124' : '#ffffff',
    webPreferences:{preload:path.join(__dirname, 'preload.js'), sandbox:true,
      contextIsolation:true, nodeIntegration:false}});
  window.setMenu(null);
  window.webContents.setWindowOpenHandler(() => ({action:'deny'}));
  window.webContents.on('will-navigate', (event, url) => { if (url !== origin + '/') event.preventDefault(); });
  ipcMain.once('fixture-ready', async (event, measurement) => {
    try {
      if (event.sender !== window.webContents) throw new Error('Unexpected fixture sender');
      const page = await window.webContents.executeJavaScript('({require:typeof require,process:typeof process})');
      const image = await window.webContents.capturePage();
      fs.writeFileSync(config.capture, image.toPNG());
      const result = {measurement, page, userData:app.getPath('userData'),
        rendererPid:window.webContents.getOSProcessId(), mainPid:process.pid,
        versions:process.versions, preferences:window.webContents.getLastWebPreferences(),
        contentBounds:window.getContentBounds(), captureSize:image.getSize()};
      fs.writeFileSync(config.ready + '.tmp', JSON.stringify(result));
      fs.renameSync(config.ready + '.tmp', config.ready);
    } catch (error) { console.error(error); app.exit(1); }
  });
  quitPoll = setInterval(() => { if (fs.existsSync(config.quit)) app.quit(); }, 100);
  await window.loadURL(origin + '/');
}).catch(error => { console.error(error); app.exit(1); });
