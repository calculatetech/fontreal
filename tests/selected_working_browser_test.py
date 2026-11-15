#!/usr/bin/env python3
"""Explicit host check: enable and open the existing Firefox/Floorp profiles."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from PIL import Image
import browser_live_recipe_test as recipe
import browser_masks_test as masks
from selected_profile_test import ROOT, WORK, OUT, build, expected_mask


def main():
    _,record=build(); WORK.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
    fonts=[masks.NOTO/'NotoSans-Regular.ttf',Path('/usr/share/fonts/truetype/hack/Hack-Regular.ttf'),
           Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf')]
    reports={}
    css=''.join(f'@font-face{{font-family:F{i};src:url(/font/{i})}}' for i in range(3))
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/font/'):
                body=fonts[int(self.path.rsplit('/',1)[1])].read_bytes(); kind='font/ttf'
            else:
                name=self.path.strip('/')
                if name not in ('firefox','floorp'):
                    self.send_error(404); return
                cells=''.join(f'<div class="cell" data-font="{i}" data-dark="{dark}" style="font-family:F{i};color:{"white" if dark else "black"};background:{"black" if dark else "white"}"><span>m</span> The quick brown fox jumps over the lazy dog. 0358 WV</div>' for i in range(3) for dark in (0,1))
                body=('<!doctype html><meta charset="utf-8"><meta name="darkreader-lock"><title>Fontreal selected renderer</title><style>body{margin:0}#marker{width:8px;height:8px;background:rgb(17,91,143)}.cell{height:54px;padding:12px;font-size:15px;line-height:30px}.cell span{display:inline-block;width:40px}'+css+'</style><div id="marker"></div>'+cells+'''<script>document.fonts.ready.then(()=>setInterval(()=>fetch(location.pathname,{method:'POST',body:JSON.stringify({dpr:devicePixelRatio,neighbors:[{id:'marker',rect:document.querySelector('#marker').getBoundingClientRect().toJSON()}],cells:[...document.querySelectorAll('.cell')].map(e=>({...e.dataset,box:e.querySelector('span').getBoundingClientRect().toJSON()}))})}),500))</script>''').encode(); kind='text/html'
            self.send_response(200); self.send_header('Content-Type',kind); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            reports[self.path.strip('/')]=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(204); self.end_headers()
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results=[]
    def cli(action,name):
        return subprocess.check_output(['python3',str(ROOT/'tools/browser.py'),action,name],text=True)
    try:
        for name in ('firefox','floorp'):
            before=json.loads(cli('status',name))
            assert not before.get('restart_required_pids'), 'An old browser must be closed normally first'
            assert not before.get('active_pids') or before.get('contrast')=='weighted'
            # Re-observe immediately in the production enable path, preserving its restoration snapshot.
            cli('enable',name)
            with (WORK/f'working-{name}.log').open('w') as log:
                subprocess.Popen([str(Path.home()/'.local/bin'/name),f'http://127.0.0.1:{server.server_port}/{name}'],
                                 stdout=log,stderr=log,start_new_session=True)
            for _ in range(150):
                if name in reports:break
                time.sleep(.2)
            assert name in reports
            measurement=reports[name]; assert measurement['dpr']==1
            status=json.loads(cli('status',name))
            assert status['contrast']=='weighted' and status['active_pids'] and not status['restart_required_pids']
            assert status['profile']==before['profile']
            shot=WORK/f'working-{name}.png'
            subprocess.run(['spectacle','-b','-n','-f','-o',str(shot.resolve())],check=True,capture_output=True)
            image=Image.open(shot).convert('RGB'); errors=[]
            for cell in measurement['cells']:
                font=int(cell['font']); dark=int(cell['dark'])
                raw=recipe.probe(record['libraries']['stock']['library'],fonts[font],flags=0x8008,char='m')
                want=raw['rendered'][0]; data=expected_mask(bytes.fromhex(want['mask']),want['width'])
                error=masks.fit(masks.crop(image,measurement,cell['box']),want['width'],want['height'],
                                masks.blend(data,(255,)*3 if dark else (0,)*3,(0,)*3 if dark else (255,)*3,False))
                assert error['error']<=1,(name,font,dark,error); errors.append(error['error'])
            results.append(dict(browser=name,existing_profile_preserved=True,active_pids=status['active_pids'],
                                contrast=status['contrast'],conditions=len(errors),max_pixel_error=max(errors)))
            (OUT/'working.json').write_text(json.dumps(results,indent=2)+'\n')
            print('PASS selected working browser',json.dumps(results[-1]),flush=True)
    finally:
        server.shutdown();server.server_close()
    # Leave the real accounts and their windows running. Only test-owned captures are private.


if __name__=='__main__':main()
