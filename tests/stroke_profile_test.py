#!/usr/bin/env python3
"""Compare generic profile and corner rules with the accepted coverage benchmark."""
import argparse
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_coverage_test import transform
from bridge_font_matrix_test import sha, slug
from browser_stroke_axis_test import Oracle
from inconsolata_gain_test import gain
from noto_stem_winner_test import keep_winner
from stroke_profiles import refine

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'docs/images/browser-common-ground'
WORK=ROOT/'build/stroke-profile-study'
OUT=ROOT/'results/stroke-profile-study/gallery'
MODES=('accepted','profiles','corners')
TITLES=('Accepted benchmark','A / profiles and joins','B / A + native corner fringe')
SUBJECTS=(('Segoe UI','a'),('Noto Sans','m'),('Segoe UI','0'),('Noto Sans','3'),
          ('Noto Sans','H'),('Segoe UI','H'),('Noto Sans','M'))


def self_test():
    assert tuple(inspect.signature(refine).parameters)==('raw','accepted','width','connected')
    assert inspect.signature(refine).parameters['connected'].default is False
    tree=ast.parse((ROOT/'tests/stroke_profiles.py').read_text())
    assert {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}=={'collections','math','statistics'}
    assert not any(isinstance(n,ast.Name) and n.id in ('open','ord','chr','font','family','glyph','codepoint') for n in ast.walk(tree))
    for raw,accepted,w in [(b'',b'',0),(bytes([128]),bytes([176]),1),
                           (bytes([160]*4),bytes([220]*4),2),
                           (bytes([140,170]*2),bytes([193,234]*2),2),
                           (bytes([255,255]*4),bytes([255,255]*4),2),
                           (bytes([128,200,128]*4),bytes([176,226,176]*4),3),
                           (bytes([100,80]*4),bytes([138,110]*4),2)]:
        assert all(v==accepted for v in refine(raw,accepted,w)[0].values())
    out,_=refine(bytes([160,156]*5),bytes([220,215]*5),2)
    assert out['profiles']==bytes([240,76]*5)
    assert refine(bytes([160,160]*4),bytes([220,220]*4),2)[0]['profiles']==bytes([80,240]*4)
    raw=bytes([140,208,0]*2+[140,253,244]+[140,208,0]*2)
    accepted=bytes([99,249,0]*2+[193,253,244]+[99,249,0]*2)
    expected=bytearray(accepted);expected[6]=99
    assert refine(raw,accepted,3)[0]['profiles']==bytes(expected)
    raw=bytes([0,0,0,255,167,0,230,249,0]);accepted=bytes([0,0,0,255,226,0,230,249,0])
    out,_=refine(raw,accepted,3);assert out['profiles']==accepted and out['corners'][4]==167
    raw=bytes([0,255,0,0,0,0,0,0,180,170,0,0,0,0,0,0,255,0])
    accepted=bytearray(raw);accepted[8:10]=bytes([248,248]);accepted=bytes(accepted)
    assert refine(raw,accepted,6)[0]['profiles']==accepted
    raw=bytes([0,0,0,0,255,0]+[0,0,180,170,0,0]*2+[0,0,0,0,255,0])
    accepted=bytearray(raw);accepted[8:10]=bytes([248,248]);accepted[14:16]=bytes([248,248]);accepted=bytes(accepted)
    assert refine(raw,accepted,6)[0]['profiles']==accepted
    raw=bytes([0,255,0,0,0,0,0,0,170,180,0,0,0,0,0,255,0,0])
    accepted=bytearray(raw);accepted[8:10]=bytes([248,248]);accepted=bytes(accepted)
    assert refine(raw,accepted,6)[0]['profiles'][8:10]==bytes([248,102])
    focus=json.loads((PUBLIC/'contrast-focus-captures.json').read_text());cases={}
    for family,ch in SUBJECTS:
        r=next(r for r in focus['records'] if r['family']==family and r['character']==ch)
        raw=bytes.fromhex(r['raw']['mask']);accepted=bytes.fromhex(r['accepted']);w,h=r['raw']['width'],r['raw']['height']
        out,detail=refine(raw,accepted,w);cases[(family,ch)]=(out,w)
        flip=lambda a:b''.join(a[i:i+w][::-1] for i in range(0,len(a),w))
        transpose=lambda a:bytes(a[y*w+x] for x in range(w) for y in range(h))
        mirrored,_=refine(flip(raw),flip(accepted),w);transposed,_=refine(transpose(raw),transpose(accepted),h)
        for mode,data in out.items():assert mirrored[mode]==flip(data) and transposed[mode]==transpose(data)
        for run in detail['runs']:
            for p in run['pairs']:
                if p['anchor']:assert out['profiles'][p['core']]+out['profiles'][p['fringe']]==p['native_total']
    assert cases[('Segoe UI','a')][0]['profiles'][4*7+5:4*7+7]==bytes([240,68])
    assert cases[('Noto Sans','m')][0]['profiles'][2*12+5:2*12+7]==bytes([107,240])
    assert cases[('Segoe UI','0')][0]['profiles'][8+5:8+7]==bytes([250,114])
    assert cases[('Noto Sans','3')][0]['profiles'][6*8+6:6*8+8]==bytes([248,111])
    assert all(cases[('Noto Sans','H')][0]['profiles'][y*9]==99 for y in range(10))
    assert all(cases[('Noto Sans','H')][0]['profiles'][y*9+8]==96 for y in range(10))
    assert all(cases[('Segoe UI','H')][0]['profiles'][y*9]==240 for y in range(11))
    assert cases[('Noto Sans','M')][0]['profiles'][0]==70 and cases[('Noto Sans','M')][0]['corners'][2]==167
    print('PASS pure mask API / seven regressions / ties / dots / thickness / joins / corners / reflections and transposes',flush=True)


def decorative(core,library):
    families=('Broadway','Calisto MT','Castellar');styles=('Regular','Bold','Italic');faces=[]
    for line in subprocess.check_output(['fc-list','-f','%{family}|%{style}|%{fontformat}|%{file}\n'],text=True).splitlines():
        family,names,format_,file=line.split('|',3);family=family.split(',')[0];style=names.split(',')[0]
        if family in families and style in styles:
            p=Path(file).resolve();faces.append(dict(family=family,style=style,format=format_,file=str(p),font_file=p.name,font_sha256=sha(p)))
    assert {f['family'] for f in faces}==set(families)
    assert len({(f['family'],f['style']) for f in faces})==len(faces)
    faces.sort(key=lambda f:(families.index(f['family']),styles.index(f['style'])))
    for i,f in enumerate(faces):f.update(id=f'x{i+1:03}',label=f['family']+' / '+f['style'],symbols=False,nerd=False)
    texts=['The quick brown fox','jumps over the lazy dog.','ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz',
           '0123456789 0358 HMNW','!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~','minimum  :;!  VvWwYy']
    config=WORK/'decorative-input.json';config.write_text(json.dumps(dict(faces=faces,texts=texts),indent=2)+'\n')
    probe=ROOT/'build/stem-core-study/probe';assert sha(probe)==core['probe_sha256']
    assert sha(ROOT/'tests/stem_core_probe.cpp')==core['sources']['stem_core_probe.cpp']
    qt=(ROOT/'build/stem-core-study/stock-qt/usr/lib/x86_64-linux-gnu').resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('FONTREAL_','QT_')) and k not in
         ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','FT2_DEBUG')}
    env.update(LD_LIBRARY_PATH=os.pathsep.join((str(library.resolve().parent),str(qt))),QT_QPA_PLATFORM='offscreen',
               QT_FONT_DPI='96',QT_SCALE_FACTOR='1',QT_QPA_PLATFORM_PLUGIN_PATH=str(qt/'qt6/plugins/platforms'))
    native=WORK/'decorative-native'
    with (WORK/'decorative.log').open('w') as log:
        subprocess.run([str(probe.resolve()),str(config.resolve()),str(native.resolve())],env=env,check=True,stdout=log,stderr=log)
    maps=(native/'maps.txt').read_text()
    for prefix,reference in core['libraries'].items():
        paths={Path(line.split()[-1]).resolve() for line in maps.splitlines() if prefix in line}
        assert len(paths)==1 and sha(paths.pop())==reference['sha256']
    expected={f"{f['id']}-{pt}" for f in faces for pt in (11,12)}
    assert set(json.loads((native/'index.json').read_text()))==expected
    records=[]
    for f in faces:
        assert sha(Path(f['file']))==f['font_sha256']
        for pt in (11,12):
            identifier=f"{f['id']}-{pt}";path=native/(identifier+'.json');case=json.loads(path.read_text())
            assert case['font_id']==f['id'] and case['point_size']==pt and case['font_format']==f['format']
            records.append(dict(id=identifier,font={k:v for k,v in f.items() if k!='file'},point_size=pt,native_size=case['native_size'],
                                capture_sha256=sha(path),glyphs=[],extra=True))
    return records,dict(probe_sha256=sha(probe),texts=texts,missing_styles={family:[s for s in (*styles,'Light') if not any(
        f['family']==family and f['style']==s for f in faces)] for family in families})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--stock-library',type=Path);parser.add_argument('--label-font',type=Path)
    args=parser.parse_args();self_test()
    if args.self_test:return
    assert args.stock_library and args.label_font
    WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    accepted=json.loads((PUBLIC/'stem-winner-captures.json').read_text())
    full_path=ROOT/'results/stem-core-study/gallery/manifest.json';assert sha(full_path)==accepted['full_source_manifest_sha256']
    full=json.loads(full_path.read_text());assert sha(args.stock_library)==accepted['library_sha256']
    for file,digest in accepted['helpers'].items():assert sha(ROOT/'tests'/file)==digest
    assert sha(ROOT/'tests/noto_stem_winner_test.py')==accepted['checker_sha256']
    extras,extra_proof=decorative(full,args.stock_library)
    sources=full['conditions']+extras;cache={};audit=[];codepoints=0;unique_glyphs=0
    oracle=Oracle(args.stock_library.resolve())
    try:
        for source in sources:
            extra=source.get('extra',False)
            path=(WORK/'decorative-native' if extra else ROOT/'build/stem-core-study/native')/(source['id']+'.json')
            assert sha(path)==source['capture_sha256'];case=json.loads(path.read_text())
            assert len(case['glyphs'])==95 and {g['codepoint'] for g in case['glyphs']}==set(range(32,127))
            glyphs={};masks={m:{} for m in (*MODES,'raw')};details={};entries=[];charmap={}
            for g in case['glyphs']:
                gid=g['glyph'];r=g['rendered'][0];raw={k:r[k] for k in ('width','height','left','top','mask')}
                assert g['rendered'][1]==r and oracle.raster(g['loaded'])==raw
                original=bytes.fromhex(r['mask']);chosen=gain(transform(original,r['width'])[0]['bridge'],226)
                current,_=keep_winner(original,chosen,r['width'])
                if not extra:
                    saved=next(x for x in source['glyphs'] if x['glyph']==gid)
                    assert saved['raw']==raw and chosen.hex()==saved['masks']['baseline']
                    assert hashlib.sha256(json.dumps(g['loaded'],sort_keys=True).encode()).hexdigest()==saved['loaded_sha256']
                    a=next(x for x in accepted['audit'] if x['id']==source['id'])
                    change=next((x for x in a['changed_glyphs'] if x['glyph']==gid),None)
                    assert hashlib.sha256(current).hexdigest()==change['winner_sha256'] if change else current.hex()==saved['masks']['native-area']
                trials,detail=refine(original,current,r['width'])
                for run in detail['runs']:
                    for pair in run['pairs']:
                        if pair['anchor']:assert sum(trials['profiles'][i] for i in (pair['core'],pair['fringe']))==pair['native_total']
                if gid in glyphs:
                    assert glyphs[gid]==dict(loaded=g['loaded'],raster=r) and masks['accepted'][gid]==current
                glyphs[gid]=dict(loaded=g['loaded'],raster=r);charmap[g['codepoint']]=gid;details[gid]=detail
                masks['raw'][gid]=original;masks['accepted'][gid]=current
                for mode in trials:masks[mode][gid]=trials[mode]
                entries.append(dict(codepoint=g['codepoint'],glyph=gid,changed={m:sum(a!=b for a,b in zip(current,trials[m],strict=True)) for m in trials},
                    masks_sha256={m:hashlib.sha256(masks[m][gid]).hexdigest() for m in masks},
                    coverage_sums={m:sum(masks[m][gid]) for m in masks}))
            changed={gid for gid in glyphs if any(masks[m][gid]!=masks['accepted'][gid] for m in ('profiles','corners'))}
            assert changed<={o['glyph'] for row in case['rows'] for o in row['occurrences']}
            codepoints+=95;unique_glyphs+=len(glyphs)
            cache[source['id']]=dict(source=source,case=case,glyphs=glyphs,masks=masks,details=details,charmap=charmap,changed=changed)
            audit.append(dict(id=source['id'],font=source['font'],point_size=source['point_size'],native_size=source['native_size'],
                extra=extra,capture_sha256=sha(path),glyphs=entries,unique_glyphs=len(glyphs)))
            print('PASS audit',source['font']['family'],source['font']['style'],source['point_size'],flush=True)
    finally:
        oracle.close()
    manifest=OUT/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text());assert old['producer']=='fontreal-stroke-profiles'
        for r in old['images']:
            p=OUT/r['file'];assert p.parent==OUT and sha(p)==r['sha256'];p.unlink()
    assert not list(OUT.glob('*.png'))
    heading=ImageFont.truetype(str(args.label_font),20);label=ImageFont.truetype(str(args.label_font),14)
    number=ImageFont.truetype(str(args.label_font),11);images=[];pages=[];regressions=[]
    def save(page,name,crops,cells=()):
        assert page.width==1440 and page.height<=880
        p=OUT/name;page.save(p)
        with Image.open(p) as saved:
            for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
            for x,y,v in cells:assert saved.getpixel((x,y))==(v,)*3
        images.append(dict(file=name,sha256=sha(p)))
    def native(data,intent=False):
        source=data['source'];font=source['font'];modes=('raw','accepted') if intent else MODES
        titles=('Original native coverage','Existing treatment (new font control)') if intent else TITLES
        page=Image.new('RGB',(1440,800),(24,24,24));d=ImageDraw.Draw(page);crops=[]
        d.text((14,12),f"{font['family']} / {font['style']} / {source['point_size']}pt | {'native intent reference' if intent else 'generic profile trials'}",font=heading,fill='white')
        d.text((14,44),'Same mask-only rule for every glyph. No font names, codepoints or annotated coordinates enter the processor.',font=label,fill='white')
        d.text((14,66),'This font is a new regression input; its intentional stroke contrast is not presumed correct in any processed column.' if intent else
               'A resolves profiles and carries edge phase. B also restores native fringe at exposed corners.',font=label,fill='white')
        for column,mode in enumerate(modes):
            x=6+column*(714 if intent else 476);pane=700 if intent else 470
            d.text((x+8,98),titles[column],font=label,fill='white')
            for palette,dark in enumerate((True,False)):
                top=130+palette*325;d.rectangle((x,top,x+pane-1,top+309),fill='black' if dark else 'white')
                d.text((x+8,top+3),'White on black' if dark else 'Black on white',font=label,fill='white' if dark else 'black')
                for i,row in enumerate(data['case']['rows']):
                    alpha=compose(row,data['glyphs'],data['masks'][mode],0);rgb=alpha.convert('RGB')
                    if not dark:rgb=ImageOps.invert(rgb)
                    assert rgb.size==(470,40);y=top+28+i*40
                    page.paste(rgb,(x,y));crops.append((x,y,rgb))
        name=f"{len(images):03}_{slug(font['family'])}_{slug(font['style'])}_{source['point_size']}pt_{'intent' if intent else 'trials'}.png"
        save(page,name,crops);pages.append(dict(id=source['id'],intent=intent,file=name))
    priority=[]
    for family in ('Noto Sans','Segoe UI'):
        priority.append(next(k for k,d in cache.items() if d['source']['font']['family']==family and d['source']['font']['style']=='Regular' and d['source']['point_size']==11))
    order=priority+[s['id'] for s in extras]+[s['id'] for s in full['conditions'] if s['id'] not in priority]
    for identifier in order:
        data=cache[identifier]
        if data['source'].get('extra'):native(data,True)
        if data['changed'] or data['source'].get('extra') or identifier in priority:native(data)
    for family,ch in SUBJECTS:
        data=next(d for d in cache.values() if d['source']['font']['family']==family and d['source']['font']['style']=='Regular' and d['source']['point_size']==11)
        gid=data['charmap'][ord(ch)];r=data['glyphs'][gid]['raster'];w,h=r['width'],r['height']
        for dark in (True,False):
            page=Image.new('RGB',(1440,700),(24,24,24));d=ImageDraw.Draw(page);crops=[];cells=[]
            d.text((14,12),f'{family} Regular / 11pt / {ch} | generic profiles, joins and corners',font=heading,fill='white')
            d.text((14,44),'Coverage values remain 0-255 on both backgrounds. Rows and columns start at one.',font=label,fill='white')
            d.text((14,66),'White on black.' if dark else 'Black on white; displayed gray is 255 minus coverage.',font=label,fill='white')
            d.text((14,88),'Orange marks changes from the accepted benchmark. Glyph selection affects this figure, not the processing rule.',font=label,fill='white')
            for column,mode in enumerate(MODES):
                x0=30+column*476;y0=220;step=28;values=data['masks'][mode][gid]
                d.text((x0,122),TITLES[column],font=label,fill='white')
                bitmap=Image.frombytes('L',(w,h),values).convert('RGB')
                if not dark:bitmap=ImageOps.invert(bitmap)
                page.paste(bitmap,(x0,164));crops.append((x0,164,bitmap))
                for x in range(w):d.text((x0+x*step+14,y0-18),str(x+1),font=number,fill='white',anchor='mt')
                for y in range(h):
                    d.text((x0-8,y0+y*step+7),str(y+1),font=number,fill='white',anchor='rt')
                    for x in range(w):
                        i=y*w+x;v=values[i];display=v if dark else 255-v;xx=x0+x*step;yy=y0+y*step
                        d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(display,)*3,
                                    outline=(255,150,30) if v!=data['masks']['accepted'][gid][i] else (70,70,70))
                        d.text((xx+14,yy+7),str(v),font=number,fill='black' if display>=140 else 'white',anchor='mt')
                        cells.append((xx+step-3,yy+step-3,display))
                assert x0+w*step<1440 and y0+h*step<620
                d.text((x0,644),f'Coverage sum: {sum(values)}',font=label,fill='white')
            name=f"{len(images):03}_{slug(family)}_Regular_11pt_{ch}_{'dark' if dark else 'light'}_grid.png"
            save(page,name,crops,cells)
        regressions.append(dict(family=family,character=ch,glyph=gid,raw={k:r[k] for k in ('width','height','left','top','mask')},
            masks={m:data['masks'][m][gid].hex() for m in ('raw',*MODES)},detail=data['details'][gid]))
    expected={k for k,d in cache.items() if d['changed'] or d['source'].get('extra') or k in priority}
    assert {p['id'] for p in pages if not p['intent']}==expected
    assert len(pages)==len(expected)+len(extras) and len(images)==len(pages)+14
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    arrays=OUT/'masks.json'
    arrays.write_text(json.dumps([dict(id=identifier,glyphs=[dict(glyph=gid,width=d['glyphs'][gid]['raster']['width'],
        height=d['glyphs'][gid]['raster']['height'],masks={m:d['masks'][m][gid].hex() for m in ('raw',*MODES)})
        for gid in sorted(d['glyphs'])]) for identifier,d in cache.items()],indent=2)+'\n')
    result=dict(producer='fontreal-stroke-profiles',checker_sha256=sha(Path(__file__)),processor_sha256=sha(ROOT/'tests/stroke_profiles.py'),
        accepted_record_sha256=sha(PUBLIC/'stem-winner-captures.json'),focus_record_sha256=sha(PUBLIC/'contrast-focus-captures.json'),
        full_source_sha256=sha(full_path),helpers=accepted['helpers'],accepted_checker_sha256=accepted['checker_sha256'],
        library_sha256=sha(args.stock_library),label_font=dict(file=args.label_font.name,sha256=sha(args.label_font)),
        logical_dpi=96,scale=1,extra_proof=extra_proof,codepoint_cases=codepoints,unique_glyph_cases=unique_glyphs,processed_masks_sha256=sha(arrays),
        audit=audit,regressions=regressions,pages=pages,images=images,limits=[
        'Two experimental variants; the accepted benchmark and installed profile remain unchanged',
        'Join and corner normalization can change area and perceived geometry',
        'New regression fonts have native references and no presumed optical acceptance',
        'A finite matrix does not prove all possible fonts, sizes, scripts or glyphs'])
    manifest.write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS {len(sources)} conditions / {codepoints} codepoint cases / {unique_glyphs} unique glyph cases / {len(images)} complete pages')
    print(OUT)


if __name__=='__main__':main()
