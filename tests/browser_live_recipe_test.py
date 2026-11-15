#!/usr/bin/env python3
"""Check the accepted live recipe against the installed provider's raw rasters."""
import argparse
from contextlib import suppress
import copy
import http.server
import importlib.util
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time

from PIL import Image
import browser_masks_test as masks
from curve_contrast_test import ROOT, TEXT, Oracle, compose, sha
from encoded_refinement_test import matrix, scalar_mask
from coverage_shoulder_test import expected_table, self_check
from dropout_continuity_test import mono_raster, bits

BUILD = ROOT / 'build/browser-live-recipe'
OUT = ROOT / 'results/browser-live-recipe'
FIELDS = ('mask','width','height','left','top')
CFF_FONTS = {
    'Nimbus Sans Regular': Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf'),
    'Nimbus Sans Bold': Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf'),
    'Nimbus Sans Italic': Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Italic.otf'),
    'Nimbus Sans Bold Italic': Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-BoldItalic.otf'),
    'Nimbus Roman Regular': Path('/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf'),
    'URW Bookman Light': Path('/usr/share/fonts/opentype/urw-base35/URWBookman-Light.otf'),
    'Cantarell Variable': Path('/usr/share/fonts/opentype/cantarell/Cantarell-VF.otf'),
    'Noto Sans CJK JP': Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
}


def builder_rejection_command(version, machine):
    code = f'''import importlib.util,sys
spec=importlib.util.spec_from_file_location('builder',sys.argv[1])
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
builder.installed=lambda package:{version!r}
builder.platform.machine=lambda:{machine!r}
sys.argv=[sys.argv[1]]
builder.main()
'''
    return [sys.executable,'-c',code,str(ROOT/'tools/build-freetype.py')]


def run(args, **kwargs):
    return subprocess.run(list(map(str,args)),check=True,text=True,capture_output=True,**kwargs)


def environment(library, enabled=False):
    env = {k:v for k,v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
           ('LD_PRELOAD','LD_LIBRARY_PATH','FT2_DEBUG','FREETYPE_PROPERTIES')}
    return dict(env, LD_LIBRARY_PATH=str(Path(library).parent), FONTREAL_FT_RENDERING='1' if enabled else '0',
                FONTREAL_FT_CONTRAST='ramp217', QT_QPA_PLATFORM='offscreen', QT_FONT_DPI='96',
                FREETYPE_PROPERTIES='autofitter:no-stem-darkening=1')


def prepare():
    BUILD.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    path = Path(run([sys.executable,ROOT/'tools/build-freetype.py']).stdout.strip().splitlines()[-1])
    record = json.loads(path.read_text()); parent = path.parent
    spec = importlib.util.spec_from_file_location('builder',ROOT/'tools/build-freetype.py')
    builder = importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    for version in builder.SOURCES:
        assert builder.source_configuration(version,'x86_64') == builder.SOURCES[version]
    for version,machine in [('unknown','x86_64'),(record['spec']['source'],'aarch64')]:
        try: builder.source_configuration(version,machine)
        except ValueError: pass
        else: raise AssertionError('unsupported provider accepted')
        before={str(p):p.stat().st_mtime_ns for p in (builder.WORK/'artifacts').rglob('*') if p.is_file()}
        rejected=subprocess.run(builder_rejection_command(version,machine),text=True,capture_output=True)
        assert rejected.returncode==2 and 'Requires amd64' in rejected.stderr
        assert before=={str(p):p.stat().st_mtime_ns for p in (builder.WORK/'artifacts').rglob('*') if p.is_file()}
    assert path == Path(run([sys.executable,ROOT/'tools/build-freetype.py']).stdout.strip())
    trace = json.loads(Path(run([sys.executable,ROOT/'tools/build-freetype.py','--trace']).stdout.strip().splitlines()[-1]).read_text())
    assert trace['spec']['trace'] and not record['spec']['trace']
    assert record['libraries']['candidate']['library'] != trace['libraries']['candidate']['library']
    source = BUILD/'nearest-source'; build = BUILD/'nearest'
    baseline = parent/'stock-source/src/autofit/aflatin.c'
    inputs = dict(provider=record['spec']['source'],archives=record['spec']['archives'],source=sha(baseline),
                  compiler=record['spec']['compiler'],headers=record['spec']['headers'],harfbuzz=record['spec']['harfbuzz'])
    manifest = BUILD/'reference.json'
    library = build/'.libs/libfreetype.so.6'
    if manifest.exists():
        saved = json.loads(manifest.read_text());assert saved['inputs'] == inputs and saved['sha256'] == sha(library)
    else:
        shutil.copytree(parent/'stock-source',source,symlinks=True)
        target = source/'src/autofit/aflatin.c'
        text = target.read_text();needle = 'dist = ( dist + 16 ) & ~63;'
        assert text.count(needle) == 1
        target.write_text(text.replace(needle,'dist = ( dist + 32 ) & ~63;'))
        build.mkdir()
        env = dict(environment(record['libraries']['stock']['library']),CC='cc',CFLAGS='-O2',
                   PKG_CONFIG_PATH=str(parent/'headers/usr/lib/x86_64-linux-gnu/pkgconfig'))
        for command,label in [([source/'configure',f'--prefix={BUILD}/unused-install',inputs['harfbuzz']],'configure'),
                              (['make','-j12'],'build')]:
            with (build/(label+'.log')).open('w') as log:
                subprocess.run(list(map(str,command)),cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        manifest.write_text(json.dumps(dict(inputs=inputs,sha256=sha(library)),indent=2))
    flags = shlex.split(run(['pkg-config','--cflags','--libs','Qt6Gui','freetype2']).stdout)
    for source_name,binary in [('point_benchmark_chart.cpp','chart'),('freetype_variable_probe.cpp','variable'),('freetype_mask_probe.cpp','probe')]:
        source_file = ROOT/'tests'/source_name
        if binary == 'probe':
            # Observe retained native outline storage after the renderer changes its format.
            text = source_file.read_text()
            text = text.replace('if (s->format == FT_GLYPH_FORMAT_OUTLINE) {','if (s->outline.n_points) {')
            text = text.replace('{"contours", contours},','{"contours", contours}, {"outline_flags", s->outline.flags},')
            source_file = BUILD/source_name
            source_file.write_text(text)
        run(['c++','-std=c++17','-fPIC','-include','algorithm',source_file,*flags,'-o',BUILD/binary])
    return record,trace,library


def expected(oracle, loaded, raw, weight=400):
    if weight < 400: return dict(raw)
    normalized = copy.deepcopy(loaded); first = 0
    for end in normalized['contours']:
        normalized['outline'][first][2] &= ~4;first=end+1
    enabled = mono_raster(oracle,normalized,False); ignored=mono_raster(oracle,normalized,True)
    assert all(enabled[k] == ignored[k] for k in ('width','height','left','top'))
    a,b = [bits(bytes.fromhex(r['mask']),r['width'],r['height']) for r in (enabled,ignored)]
    selected = {(enabled['left']+i%enabled['width'],enabled['top']-i//enabled['width'])
                for i,(on,off) in enumerate(zip(a,b)) if on and not off}
    table = expected_table('ramp')
    result = []
    for i,v in enumerate(bytes.fromhex(raw['mask'])):
        location = (raw['left']+i%raw['width'],raw['top']-i//raw['width'])
        result.append(max(table[v],217) if location in selected else table[v])
    return dict(raw,mask=bytes(result).hex())


def probe(library,font,size=15,flags=0x20028,char='2',enabled=False,contrast='ramp217',dx=0,transform='none',remove=False,scope=None):
    env=environment(library,enabled);env['FONTREAL_FT_CONTRAST']=contrast
    if scope is not None: env['FONTREAL_FT_EXECUTABLE']=scope
    target=OUT/'probe.json'
    run([BUILD/'probe',font,size,flags,ord(char),0,dx,0,2,target,transform,int(remove)],env=env)
    return json.loads(target.read_text())


def v1_provider(record):
    """Rebuild the retained complete TT-only provider for the matching distro."""
    patch = ROOT/'tests/freetype_tt_only_v1.patch'
    inputs = dict(spec=record['spec'], patch=sha(patch))
    manifest = BUILD/'v1-provider.json'
    source, build = BUILD/'v1-source', BUILD/'v1-build'
    library = build/'.libs/libfreetype.so.6'
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        assert saved['inputs'] == inputs and saved['libraries']['candidate']['sha256'] == sha(library)
    else:
        parent = Path(record['libraries']['candidate']['library']).parents[2]
        shutil.copytree(parent/'candidate-source',source,symlinks=True)
        run(['patch','--batch','--fuzz=0','-p1','-i',patch],cwd=source)
        build.mkdir()
        env = dict(environment(record['libraries']['stock']['library']), CC='cc', CFLAGS='-O2',
                   PKG_CONFIG_PATH=str(parent/'headers/usr/lib/x86_64-linux-gnu/pkgconfig'))
        for command,label in [([source/'configure',f'--prefix={BUILD}/unused-v1-install',record['spec']['harfbuzz']],'configure'),
                              (['make','-j4'],'build')]:
            with (build/(label+'.log')).open('w') as log:
                subprocess.run(list(map(str,command)),cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        saved = dict(inputs=inputs, spec=dict(source=record['spec']['source'], contract='TrueType-only v1'),
                     libraries=dict(candidate=dict(library=str(library.resolve()),sha256=sha(library))))
        manifest.write_text(json.dumps(saved,indent=2)+'\n')
    return manifest, saved['libraries']['candidate']


def native(record,nearest,variable):
    oracle=Oracle(Path(record['libraries']['stock']['library']));candidate=record['libraries']['candidate']['library']
    qt=ROOT/'results/encoded-refinement/qt/rows.json'; controls=json.loads(qt.read_text());matrix(controls)
    protected={str(p):sha(p) for p in [qt,ROOT/'results/encoded-refinement/reference/rows.json',ROOT/'tests/point_benchmark_chart.cpp']}
    for bad in (controls[:-1]+[controls[0]],controls[:-1],[dict(controls[0],point_size=8.5)]+controls[1:],
                [{k:v for k,v in controls[0].items() if k != 'point_size'}]+controls[1:]):
        try: matrix(bad)
        except AssertionError: pass
        else: raise AssertionError('incomplete point matrix accepted')
    for name,library,enabled in [('raw',nearest,False),('actual',candidate,True)]:
        run([BUILD/'chart','candidate',qt,OUT/name],env=environment(library,enabled))
    raw,actual=[matrix(json.loads((OUT/name/'rows.json').read_text())) for name in ('raw','actual')]
    historical=matrix(json.loads((ROOT/'results/encoded-refinement/reference/rows.json').read_text()))
    count=changes=history=0
    for key,row in raw.items():
        treated=[]
        for ref,got,old in zip(row['glyphs'],actual[key]['glyphs'],historical[key]['glyphs']):
            assert got['loaded'] == ref['loaded'],(key,'geometry')
            want=expected(oracle,ref['loaded'],ref,row['weight'])
            assert all(got[k] == want[k] for k in FIELDS),(key,'mask')
            count+=1;changes+=got['mask']!=ref['mask'];history+=ref['mask']!=old['mask'];treated.append(want)
        alpha=compose(actual[key]['glyphs'],row['height'],160,table=list(range(256)))
        assert alpha.tobytes() == scalar_mask(treated,row['height'],list(range(256)))
        for dark in (False,True):
            alpha.point(list(range(256)) if dark else list(range(255,-1,-1))).convert('RGB').save(OUT/f'{row["id"]}-{"dark" if dark else "light"}.png')
    values={a for row in raw.values() if row['weight']>=400 for glyph in row['glyphs'] for a in bytes.fromhex(glyph['mask'])}
    assert values==set(range(256))
    assert count==5643 and changes
    font=masks.NOTO/'NotoSans-Regular.ttf'; life=[]
    for dx in (0,32):
        ref=probe(nearest,font,dx=dx);got=probe(candidate,font,flags=0x28,dx=dx,enabled=True)
        want=expected(oracle,ref['loaded'],ref['rendered'][0])
        assert got['loaded']==ref['loaded'] and got['rendered']==[want,want]
        g=probe(nearest,font,char='g');assert got['next']==expected(oracle,g['loaded'],g['rendered'][0])
        life.append(dx)
    delayed=probe(candidate,font,flags=0x28,enabled=True);immediate=probe(candidate,font,flags=0x2c,enabled=True)
    assert immediate['loaded']==delayed['rendered'][0]
    embedded,tricky=masks.font_fixtures(delayed['glyph'])
    scanmodes=0
    for path,transform,remove in [(font,'quarter',False),(font,'diagonal',False),(tricky,'none',False),(font,'none',True),(embedded,'none',False)]:
        ref=probe(nearest,path,transform=transform,remove=remove)
        got=probe(candidate,path,flags=0,enabled=True,transform=transform,remove=remove)
        assert got['loaded']==ref['loaded']
        assert got['rendered']==[expected(oracle,ref['loaded'],ref['rendered'][0])]*2,(path,transform)
        for rendered in got['rendered']:
            assert all(rendered[k]==got['loaded'][k] for k in ('outline','contours','outline_flags'))
        scanmodes+=sum(bool(p[2]&4) for p in ref['loaded']['outline'])
    assert scanmodes
    stock=record['libraries']['stock']['library']
    for flags in (1,2,0x400,0x100,0x400000,1|4,0x400|4,0x400000|4):
        a=masks.probe(record,font,flags=flags,mode=-1,contrast='ramp217')
        b=masks.probe(record,font,flags=flags,mode=-1,variant='stock',contrast='ramp217')
        assert a==b,flags
    for path,char,flags in [('/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf','m',0x28),
                           (masks.NOTO/'NotoColorEmoji.ttf','😀',0x100000),('/usr/share/fonts/X11/misc/6x13-ISO8859-1.pcf.gz','m',0)]:
        assert probe(candidate,path,flags=flags,char=char,enabled=True)==probe(stock,path,flags=flags,char=char)
    executable=str((BUILD/'probe').resolve());different=False
    for scope,on in [(executable,True),(executable+'-prefix',False),('/wrong:'+executable,True),(executable+'-prefix:/wrong',False)]:
        got=probe(candidate,font,size=21,flags=0x28,char='n',enabled=True,scope=scope)
        ref=probe(nearest if on else stock,font,size=21,flags=0x20028 if on else 0x28,char='n')
        assert got['loaded']==ref['loaded']
        if on: assert got['rendered']==[expected(oracle,ref['loaded'],ref['rendered'][0])]*2
        else: assert got==ref
        different |= got['loaded'] != probe(stock,font,size=21,flags=0x20028,char='n')['loaded']
    assert different
    variable_results={}
    for name,library,on in [('actual',candidate,True),('nearest',nearest,False),('stock',stock,False)]:
        target=OUT/(name+'-variable.json')
        run([BUILD/'variable',variable,15,'0x28' if on else '0x20028',target],env=environment(library,on))
        variable_results[name]=json.loads(target.read_text())
    variable_changes=0
    for got,near,old in zip(variable_results['actual'],variable_results['nearest'],variable_results['stock']):
        ref=near if got['mode']=='ramp217' else old
        assert got['weight']==got['requested_weight']==ref['weight']
        for a,b in zip(got['glyphs'],ref['glyphs']):
            assert a['loaded']==b['loaded']
            want=expected(oracle,b['loaded'],b['rendered'],got['weight']) if got['mode']=='ramp217' else masks.mild(b['rendered']) if got['mode']=='mild' else b['rendered']
            assert a['rendered']==want,(got['weight'],got['mode'])
            variable_changes+=want!=b['rendered']
    assert variable_changes
    self_check();assert protected=={p:sha(Path(p)) for p in protected};oracle.close()
    return dict(conditions=171,glyphs=count,changed=changes,historical_provider_mask_differences=history,
                lifecycle_translations=life,native_scanmode_tags=scanmodes,variable_steps=9,production_alpha_inputs=len(values),reference=sha(nearest))


def browser(record,trace,nearest,variable,mode='ramp217',font_group='tt'):
    fonts=[masks.NOTO/'NotoSans-Regular.ttf',masks.NOTO/'NotoSerif-Regular.ttf',Path('/usr/share/fonts/truetype/lato/Lato-Light.ttf'),variable]
    faces=[(0,400),(1,400),(2,300),(3,300),(3,400),(3,700)]
    if mode in ('raw','weighted'):
        fonts += [Path('/usr/share/fonts/truetype/msttcorefonts/Arial.ttf'),
                  Path('/usr/share/fonts/truetype/hack/Hack-Bold.ttf'),masks.NOTO/'NotoSerif-Italic.ttf']
        faces += [(4,400),(5,700),(6,400)]
    assert font_group in ('tt','tt-tail','cff','cff-tail','cff2') and (font_group=='tt' or mode in ('raw','weighted'))
    variables={3}
    if font_group in ('cff','cff-tail'):
        fonts=list(CFF_FONTS.values())
        faces=[(i,700 if i in (1,3) else 300 if i==5 else 400) for i in range(8)]
        variables={6}
    elif font_group=='cff2':
        fonts=[CFF_FONTS['Cantarell Variable']]
        faces=[(0,w) for w in (300,399.5,400,700)]
        variables={0}
    if mode in ('raw','weighted') and font_group!='cff2':
        faces=faces[6:] if font_group.endswith('-tail') else faces[:6]
    points = (8,11,12,16) if mode in ('raw','weighted') else (8,11,16)
    row_height,line_height = (40,36) if mode in ('raw','weighted') else (55,50)
    css=''.join(f'@font-face{{font-family:F{i};src:url(/font/{i});font-weight:100 900;}}' for i in range(len(fonts)))
    if font_group in ('cff','cff-tail'):
        css=css.replace('src:url(/font/7);','src:local("Noto Sans CJK JP");')
    rows=[]
    for index,(font,weight) in enumerate(faces):
        for point in points:
            character='漢' if font_group in ('cff','cff-tail') and font==7 else '2'
            text='漢国文 漢国文' if character=='漢' else TEXT
            cells=''.join(f'<div class="cell" data-font="{font}" data-weight="{weight}" data-point="{point}" data-dark="{dark}" data-character="{character}" style="font-family:F{font};font-weight:{weight};font-size:{point}pt;color:{"white" if dark else "black"};background:{"black" if dark else "white"}"><span class="two">{character}</span><span class="word">{text}</span></div>' for dark in (0,1))
            rows.append('<div class="row">'+cells+'</div>')
    html=('<!doctype html><meta charset="utf-8"><title>Fontreal '+mode+' recipe</title><style>body{margin:0}#marker{width:8px;height:8px;background:rgb(17,91,143)}'+f'.row{{display:flex;height:{row_height}px}}.cell{{width:670px;height:{row_height}px;line-height:{line_height}px;white-space:nowrap;padding-left:8px}}'+'.two{display:inline-block;width:40px}'+css+'</style><div id="marker"></div>'+''.join(rows)+'''<script>document.fonts.ready.then(()=>{window.ready=true});window.measure=()=>({dpr:devicePixelRatio,neighbors:[{id:'marker',rect:document.querySelector('#marker').getBoundingClientRect().toJSON()}],cells:[...document.querySelectorAll('.cell')].map(e=>({...e.dataset,box:(()=>{const r=e.querySelector('.two').getBoundingClientRect();return {x:r.x-4,y:r.y-2,width:r.width+8,height:r.height+4}})()}))})</script>''').encode()
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            content=fonts[int(self.path.rsplit('/',1)[1])].read_bytes() if self.path.startswith('/font/') else html
            self.send_response(200);self.send_header('Content-Type','font/ttf' if self.path.startswith('/font/') else 'text/html');self.end_headers();self.wfile.write(content)
        def log_message(self,*args): pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    oracle=Oracle(Path(record['libraries']['stock']['library']));results=[]
    reference_library=record['libraries']['stock']['library'] if mode=='weighted' else nearest
    reference_flags=0x8008 if mode=='weighted' else 0x20028
    def reference(font,**kwargs):
        return probe(reference_library,font,flags=reference_flags,**kwargs)
    def coverage(loaded,rendered,weight):
        if mode=='weighted':
            from selected_profile_test import expected_mask
            return dict(rendered,mask=expected_mask(bytes.fromhex(rendered['mask']),rendered['width']).hex())
        return expected(oracle,loaded,rendered,0 if mode=='raw' else weight)
    try:
        with masks.nested_display() as display:
            for name in ('firefox','floorp'):
                directory=OUT/(name if mode == 'ramp217' else name+'-'+mode+('' if font_group=='tt' else '-'+font_group));directory.mkdir(exist_ok=True)
                with socket.socket() as reservation:
                    reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
                logpath=directory/'browser.log';client=None
                with logpath.open('w') as log:
                    child=subprocess.Popen([sys.executable,str(ROOT/'tools/preview-browser.py'),mode,f'http://127.0.0.1:{server.server_port}/','--browser',name,'--trace','--marionette-port',str(port)],env=dict(display,GDK_BACKEND='wayland',MOZ_ENABLE_WAYLAND='1'),stdout=log,stderr=log,start_new_session=True)
                    try:
                        for _ in range(300):
                            assert child.poll() is None,logpath.read_text()[-2000:]
                            if 'Marionette\tINFO\tListening on port' in logpath.read_text(): break
                            time.sleep(.1)
                        client=masks.Marionette(port)
                        client.command('WebDriver:SetWindowRect',dict(x=0,y=0,width=1380,height=1240))
                        for _ in range(100):
                            if client.script('return !!window.ready && document.fonts.status === "loaded"'): break
                            time.sleep(.1)
                        measured=client.script('return window.measure()');assert len(measured['cells'])==len(faces)*len(points)*2
                        word_layout=client.script('''return [...document.querySelectorAll('.cell')].map(e=>{
                          const word=e.querySelector('.word'), node=word.firstChild, b=word.getBoundingClientRect();
                          return {wordBox:{x:b.x-4,y:b.y-2,width:b.width+8,height:b.height+4},
                            occurrences:[...node.textContent].map((character,i)=>{
                              const r=document.createRange();r.setStart(node,i);r.setEnd(node,i+1);
                              return {character,x:r.getBoundingClientRect().x};})};});''')
                        assert len(word_layout)==len(measured['cells'])
                        for cell,layout in zip(measured['cells'],word_layout,strict=True): cell.update(layout)
                        (directory/'measurement.json').write_text(json.dumps(measured,indent=2))
                        for _ in range(50):
                            image=masks.screenshot(display,directory/'screen.png')
                            if (17,91,143) in set(image.getdata()): break
                            time.sleep(.1)
                        rasters=masks.raw_masks(logpath);errors=[];keys=set();word_checks=0;word_errors=[];glyph_cache={}
                        for cell in measured['cells']:
                            font,point,dark=[int(cell[k]) for k in ('font','point','dark')];weight=float(cell['weight'])
                            size=point*96/72
                            if font in variables:
                                target=directory/f'variable-{point}.json'
                                run([BUILD/'variable',fonts[font],size,reference_flags,target],env=environment(reference_library))
                                step=next(r for r in json.loads(target.read_text()) if r['weight']==weight and r['mode']=='ramp217')
                                ref=step['glyphs'][0];want=coverage(ref['loaded'],ref['rendered'],weight)
                            else:
                                ref=reference(fonts[font],size=size,char=cell['character']);want=coverage(ref['loaded'],ref['rendered'][0],weight)
                            family=reference(fonts[font],size=size,char=cell['character'])['family'].encode().hex()
                            selected=[r for r in rasters if r['glyph']==ref['glyph'] and (font_group=='tt' or r['family']==family) and
                                      abs(r['y_scale']*r['units']/65536/64-size)<.02 and
                                      all(r[k]==want[k] for k in ('mask','width','height'))]
                            assert selected,(name,cell,'native final mask not observed')
                            text='漢国文 漢国文' if cell['character']=='漢' else TEXT
                            assert ''.join(o['character'] for o in cell['occurrences'])==text
                            expected_occurrences=[]
                            for char in text:
                                if font in variables:
                                    glyph=next(g for g in step['glyphs'] if g['char']==char)
                                    glyph_expected=coverage(glyph['loaded'],glyph['rendered'],weight)
                                else:
                                    key=(font,weight,point,char)
                                    if key not in glyph_cache: glyph_cache[key]=reference(fonts[font],size=size,char=char)
                                    glyph=glyph_cache[key]
                                    glyph_expected=coverage(glyph['loaded'],glyph['rendered'][0],weight)
                                expected_occurrences.append(glyph_expected)
                                if char!=' ': assert any(r['glyph']==glyph['glyph'] and (font_group=='tt' or r['family']==family) and abs(r['y_scale']*r['units']/65536/64-size)<.02 and
                                           all(r[k]==glyph_expected[k] for k in ('mask','width','height')) for r in rasters),(name,cell,char,'word raster')
                                word_checks+=1
                            error=masks.fit(masks.crop(image,measured,cell['box']),want['width'],want['height'],masks.blend(bytes.fromhex(want['mask']),(255,)*3 if dark else (0,)*3,(0,)*3 if dark else (255,)*3,False))
                            assert error['error']<=1,(name,cell,error)
                            actual_word=masks.crop(image,measured,cell['wordBox']);width,height=actual_word.size
                            alpha=bytearray(width*height)
                            baseline=math.floor(cell['box']['y'])+error['y']+want['top']-math.floor(cell['wordBox']['y'])
                            for occurrence,glyph in zip(cell['occurrences'],expected_occurrences,strict=True):
                                x=round(occurrence['x'])+glyph['left']-math.floor(cell['wordBox']['x'])
                                y=baseline-glyph['top']
                                assert not glyph['width'] or (x>=0 and y>=0 and x+glyph['width']<=width and y+glyph['height']<=height),(name,cell,'word ink bounds',x,y)
                                raw=bytes.fromhex(glyph['mask'])
                                for yy in range(glyph['height']):
                                    for xx in range(glyph['width']):
                                        a=raw[yy*glyph['width']+xx];at=(y+yy)*width+x+xx
                                        alpha[at]=a+(alpha[at]*(255-a)+127)//255
                            expected_word=masks.blend(bytes(alpha),(255,)*3 if dark else (0,)*3,(0,)*3 if dark else (255,)*3,False)
                            maximum=max(abs(a-b) for p,q in zip(actual_word.getdata(),expected_word,strict=True) for a,b in zip(p,q,strict=True))
                            if maximum>1:
                                actual_word.save(directory/'word-actual.png')
                                predicted=Image.new('RGB',actual_word.size);predicted.putdata(expected_word);predicted.save(directory/'word-expected.png')
                                (directory/'word-failure.json').write_text(json.dumps(dict(cell=cell,baseline=baseline,prefix_fit=error,maximum=maximum),indent=2))
                            assert maximum<=1,(name,font_group,font,weight,point,dark,'whole word RGB',maximum)
                            word_errors.append(maximum)
                            errors.append(error['error']);keys.add((font,weight,point,dark))
                        assert keys=={(font,weight,point,dark) for font,weight in faces for point in points for dark in (0,1)}
                        identity=[json.loads(line.split('FONTREAL_BROWSER ',1)[1]) for line in logpath.read_text().splitlines() if line.startswith('FONTREAL_BROWSER ')][0]
                        assert identity['library']==trace['libraries']['candidate']['library']
                        assert identity['library'] in Path(f'/proc/{identity["pid"]}/maps').read_text()
                        results.append(dict(browser=name,font_group=font_group,conditions=len(keys),word_glyph_checks=word_checks,max_encoded_error=max(errors),max_word_encoded_error=max(word_errors),native_masks=len(rasters)))
                        (directory/'result.json').write_text(json.dumps(results[-1],indent=2))
                        client.command('Marionette:Quit',{'flags':['eForceQuit']});client.close();client=None
                        assert child.wait(timeout=20)==0
                    finally:
                        if client:
                            with suppress(Exception): client.command('Marionette:Quit',{'flags':['eForceQuit']})
                            client.close()
                        if child.poll() is None: masks.stop(child)
    finally:
        server.shutdown();server.server_close();oracle.close()
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variable-font',type=Path,required=True)
    parser.add_argument('--case',choices=('native','browser'),required=True)
    args=parser.parse_args();before=masks.protected()
    record,trace,nearest=prepare()
    result=native(record,nearest,args.variable_font) if args.case=='native' else browser(record,trace,nearest,args.variable_font)
    assert masks.protected()==before
    (OUT/(args.case+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS live recipe '+args.case,flush=True)


if __name__=='__main__': main()
