'use strict';
const {ipcRenderer} = require('electron');
window.addEventListener('DOMContentLoaded', async () => {
  await document.fonts.load('15px Fixture', 'm8Wm8Wg');
  await document.fonts.ready;
  const painted = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await painted();
  document.getElementById('later').textContent = 'g';
  await painted();
  const rect = id => {
    const r = document.getElementById(id).getBoundingClientRect();
    return {x:r.x, y:r.y, width:r.width, height:r.height};
  };
  ipcRenderer.send('fixture-ready', {sandboxed:process.sandboxed, contextIsolated:process.contextIsolated,
    dpr:devicePixelRatio, width:innerWidth, height:innerHeight, fontLoaded:document.fonts.check('15px Fixture'),
    marker:rect('marker'), control:rect('control'), prefix:rect('prefix'), later:rect('later'),
    text:document.getElementById('text').textContent});
});
