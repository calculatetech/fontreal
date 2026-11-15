'use strict';
const {ipcRenderer} = require('electron');
window.addEventListener('DOMContentLoaded', () => {
  (async () => {
    const selected = document.getElementById('selected');
    if (selected) {
      const config = await ipcRenderer.invoke('selected-config');
      const faces = [];
      for (const [index, font] of config.fonts.entries()) {
        const source = font.local ? `local("${font.family}")` : `url('/font/${index}')`;
        const face = new FontFace(`F${index}`, source, {variationSettings:font.variation || 'normal'});
        faces.push(face);document.fonts.add(face);await face.load();await document.fonts.load(`15px F${index}`, 'm8Wg');
      }
      await document.fonts.ready;
      const context = selected.getContext('2d');
      const painted = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      let contextChanges = 0;
      selected.addEventListener('contextlost', () => { contextChanges++; });
      selected.addEventListener('contextrestored', () => { contextChanges++; });
      async function draw(stage) {
        const cells = config.stages[stage];
        if (!cells) throw new Error('Unknown selected fixture stage');
        const deadline = performance.now() + 15000;
        for (;;) {
          if (performance.now() > deadline) throw new Error('Native canvas did not restore');
          const before = contextChanges;
          if (context.isContextLost()) { await painted();continue; }
          context.resetTransform();context.clearRect(0, 0, selected.width, selected.height);
          context.fillStyle = config.background;context.fillRect(0, 0, selected.width, selected.height);
          for (const cell of cells) {
            context.save();context.font = `${cell.pixels}px F${cell.font}`;
            context.textBaseline = 'alphabetic';context.fillStyle = config.foreground;context.strokeStyle = config.foreground;
            context.textRendering = cell.unhinted ? 'geometricPrecision' : 'auto';
            const metrics = context.measureText(cell.char);
            cell.metrics = {width:metrics.width,left:metrics.actualBoundingBoxLeft,right:metrics.actualBoundingBoxRight,ascent:metrics.actualBoundingBoxAscent,descent:metrics.actualBoundingBoxDescent};
            if (cell.transform) context.transform(...cell.transform);
            if (cell.stroke) {context.lineWidth = cell.stroke;context.lineJoin = 'miter';context.miterLimit = 10;context.strokeText(cell.char,cell.x,cell.y);}
            else context.fillText(cell.char,cell.x,cell.y);
            context.restore();
          }
          await document.fonts.ready;await painted();
          if (before !== contextChanges || context.isContextLost()) continue;
          ipcRenderer.send('fixture-ready', {sandboxed:process.sandboxed,contextIsolated:process.contextIsolated,
            dpr:devicePixelRatio,width:innerWidth,height:innerHeight,
            fontLoaded:document.fonts.status === 'loaded' && faces.every((face,index) => face.status === 'loaded' && document.fonts.check(`15px F${index}`, 'm8Wg')),
            contextLost:context.isContextLost(),contextChanges,stage,cells});
          return;
        }
      }
      ipcRenderer.on('selected-stage', (_, stage) => {draw(stage).catch(error => ipcRenderer.send('fixture-ready', {error:String(error)}));});
      await draw('empty');return;
    }
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
  })().catch(error => ipcRenderer.send('fixture-ready', {error:String(error)}));
});
