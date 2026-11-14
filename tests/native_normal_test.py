#!/usr/bin/env python3
"""Compare native-normal shape and coverage against the accepted mono study."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_coverage_test import transform, bridge_checks
from bridge_font_matrix_test import inventory, sha, slug
from browser_stroke_axis_test import Oracle

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'build/native-normal-study'
OUT = ROOT/'results/native-normal-study/gallery'
MATRIX = ROOT/'results/bridge-font-matrix/gallery/manifest.json'
MODES = ('current','native','native-bridge')
TITLES = ('Current auto mono + 170','Native normal / raw','Native normal + 170')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-library',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args=parser.parse_args(); bridge_checks()
    matrix=json.loads(MATRIX.read_text())
    assert sha(args.stock_library)==matrix['stock_library_sha256']
    for key,name in [('filter_sha256','bridge_coverage_test.py'),('average_sha256','neighbor_coverage_test.py')]:
        assert matrix[key]==sha(ROOT/'tests'/name)
    faces=[]
    for family in ('Hack','Inconsolata Nerd Font','Nimbus Roman','DejaVu Sans','Arial'):
        styles=('Regular','Italic','Bold','Bold Italic') if family=='Hack' else ('Regular',)
        for style in styles:
            faces.append(next(f for f in matrix['faces'] if f['family']==family and f['style']==style))
    installed,_=inventory()
    files={f['id']:Path(next(r['file'] for r in installed if r['font_sha256']==f['font_sha256'])) for f in faces}
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    probe=WORK/'probe'
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','freetype2'],text=True))
    subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/freetype_mask_probe.cpp'),*flags,'-o',str(probe)],check=True)
    env={k:v for k,v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
         ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','FT2_DEBUG')}
    env['LD_LIBRARY_PATH']=str(args.stock_library.resolve().parent)
    previous=OUT/'manifest.json'
    if previous.exists():
        old=json.loads(previous.read_text()); assert old['producer']=='fontreal-native-normal-study'
        for r in old['images']:
            p=OUT/r['file']; assert p.parent==OUT and sha(p)==r['sha256']; p.unlink()
    assert not list(OUT.glob('*.png'))
    label=ImageFont.truetype(str(args.label_font),15)
    heading=ImageFont.truetype(str(args.label_font),20)
    tiny=ImageFont.truetype(str(args.label_font),10)
    oracle=Oracle(args.stock_library.resolve()); records=[]; images=[]

    def save(image,name,crops=(),cells=()):
        assert image.width==1440 and image.height<=880
        path=OUT/name; image.save(path)
        with Image.open(path) as saved:
            for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
            for x,y,v in cells:assert saved.getpixel((x,y))==(v,)*3
        images.append(dict(file=name,sha256=sha(path)))

    try:
        for face in faces:
            for point in (11,12):
                identifier=f"{face['id']}-{point:02}"
                source_path=ROOT/'build/bridge-font-matrix/native'/(identifier+'.json')
                source_record=next(r for r in matrix['conditions'] if r['id']==identifier)
                assert sha(source_path)==source_record['native_capture_sha256']
                case=json.loads(source_path.read_text())
                assert case['font_id']==face['id'] and case['point_size']==point and case['texts'][:10]==matrix['texts']
                assert not any(o['text'] in (0,2,3,4,8) for o in case['missing'])
                source_glyphs={g['glyph']:g for g in case['glyphs']}
                needed={o['glyph'] for o in case['occurrences'] if o['text'] in (0,2,3,4,8)}
                reverse={case['character_map'][str(ord(ch))]:ord(ch) for t in (0,2,3,4,8) for ch in case['texts'][t]}
                assert 0 not in needed and needed<=reverse.keys(), 'A shaped glyph has no exact character mapping'
                glyphs={'current':source_glyphs,'native':{},'native-bridge':{}}
                masks={mode:{} for mode in MODES}; captures=[]
                for gid in sorted(needed):
                    target=WORK/f'{identifier}-g{gid}.json'
                    subprocess.run([str(probe.resolve()),str(files[face['id']]),str(case['native_size']),
                                    '32776',str(reverse[gid]),'0','0','0','2',str(target.resolve()),'none','0'],env=env,check=True)
                    capture=json.loads(target.read_text()); raw=capture['rendered'][0]
                    assert capture['glyph']==gid and capture['font_format']==face['format']
                    assert all(r==raw for r in capture['rendered'])
                    assert oracle.raster(capture['loaded'])=={k:raw[k] for k in ('width','height','left','top','mask')}
                    old=source_glyphs[gid]['raster']
                    assert oracle.raster(source_glyphs[gid]['loaded'])=={k:old[k] for k in ('width','height','left','top','mask')}
                    masks['current'][gid]=transform(bytes.fromhex(old['mask']),old['width'])[0]['bridge']
                    masks['native'][gid]=bytes.fromhex(raw['mask'])
                    masks['native-bridge'][gid]=transform(masks['native'][gid],raw['width'])[0]['bridge']
                    for mode in ('native','native-bridge'):
                        glyphs[mode][gid]=dict(glyph=gid,loaded=capture['loaded'],raster=raw)
                    captures.append(dict(glyph=gid,codepoint=reverse[gid],capture_sha256=sha(target),
                                         loaded_sha256=hashlib.sha256(json.dumps(capture['loaded'],sort_keys=True).encode()).hexdigest(),
                                         raw={k:raw[k] for k in ('width','height','left','top','mask')},
                                         transformed_mask=masks['native-bridge'][gid].hex(),
                                         changed_pixels=sum(a!=b for a,b in zip(masks['native'][gid],masks['native-bridge'][gid],strict=True))))
                    if face['family']=='Hack' and face['style']=='Regular' and point==11 and reverse[gid]==56:
                        anchor=json.loads((ROOT/'docs/images/browser-common-ground/hack-eight-captures.json').read_text())
                        assert capture['loaded']==anchor['native_cases']['native']['capture']['loaded']
                        assert capture['rendered']==anchor['native_cases']['native']['capture']['rendered']
                rows=[]; split=case['texts'][8].index('0358'); alphabet_split=case['texts'][2].index(' ')+1
                segments=[(0,0,len(case['texts'][0])),(2,0,alphabet_split),(2,alphabet_split,len(case['texts'][2])),
                          (3,0,len(case['texts'][3])),(4,0,len(case['texts'][4])),
                          (8,0,split),(8,split,len(case['texts'][8]))]
                assert set('SAYVvWw8:;!')<=set(''.join(case['texts'][t][a:b] for t,a,b in segments))
                for text,start,end in segments:
                    occurrences=[dict(o) for o in case['occurrences'] if o['text']==text and start<=o['string_index']<end]
                    assert occurrences
                    shift=min(o['x'] for o in occurrences)-16
                    for o in occurrences:o['x']-=shift
                    row_case=dict(case,occurrences=occurrences)
                    alpha={mode:compose(row_case,glyphs[mode],masks[mode],text) for mode in MODES}
                    boxes=[im.getbbox() for im in alpha.values()]; assert all(boxes)
                    assert max(b[2] for b in boxes)<=470, 'Text exceeds its comparison column'
                    top=max(0,min(b[1] for b in boxes)-1);bottom=min(case['height'],max(b[3] for b in boxes)+1)
                    crops={mode:im.crop((0,top,470,bottom)) for mode,im in alpha.items()}
                    for mode in MODES:assert sum(crops[mode].tobytes())==sum(alpha[mode].tobytes())
                    rows.append(dict(text=text,start=start,end=end,x_shift=shift,images=crops))
                body_height=sum(row['images']['native'].height+8 for row in rows)+28
                image=Image.new('RGB',(1440,145+body_height*2+30),(24,24,24));draw=ImageDraw.Draw(image);saved=[]
                draw.text((14,12),f"{face['family']} / {face['style']} / {point}pt | native-normal shape and coverage",font=heading,fill='white')
                draw.text((14,44),'96 DPI / 100%. Matched shaped positions in all columns; native hints explicitly disable the auto-hinter.',font=label,fill='white')
                for column,mode in enumerate(MODES):
                    x=6+column*476
                    draw.text((x+8,82),TITLES[column],font=heading,fill='white')
                    for palette,dark in enumerate((True,False)):
                        top=115+palette*(body_height+15);bg,fg=((0,0,0),'white') if dark else ((255,255,255),'black')
                        draw.rectangle((x,top,x+469,top+body_height-1),fill=bg)
                        draw.text((x+8,top+3),'White on black' if dark else 'Black on white',font=label,fill=fg)
                        y=top+28
                        for row in rows:
                            rgb=row['images'][mode].convert('RGB')
                            if not dark:rgb=ImageOps.invert(rgb)
                            assert y+rgb.height<=top+body_height
                            image.paste(rgb,(x,y));saved.append((x,y,rgb));y+=rgb.height+8
                save(image,f"{len(images):04}_{slug(face['family'])}_{slug(face['style'])}_{point}pt.png",saved)
                records.append(dict(id=identifier,font=face,point_size=point,native_size=case['native_size'],
                                    source_case_sha256=sha(source_path),load_flags=32776,glyphs=captures,
                                    rows=[{k:v for k,v in r.items() if k!='images'} for r in rows]))
                if face['family']=='Hack' and face['style']=='Regular' and point==11:
                    gid=case['character_map']['56']
                    grid=Image.new('RGB',(1440,800),(24,24,24));d=ImageDraw.Draw(grid);saved=[];cells=[]
                    d.text((20,14),'Hack Regular 8 / 11pt | old geometry versus native-normal coverage',font=heading,fill='white')
                    d.text((20,49),'Each cell: original coverage above, displayed coverage below. Orange marks coverage changes only.',font=label,fill='white')
                    d.text((20,74),'Native raw and native + 170 share one outline and bitmap origin. The mono control has different geometry.',font=label,fill='white')
                    for column,mode in enumerate(MODES):
                        x0=40+column*476;y0=225;step=36;r=glyphs[mode][gid]['raster'];data=masks[mode][gid];original=bytes.fromhex(r['mask'])
                        w,h=r['width'],r['height'];assert x0+w*step<1440 and y0+h*step<760
                        d.text((x0,118),TITLES[column],font=heading,fill='white')
                        native=Image.frombytes('L',(w,h),data).convert('RGB');grid.paste(native,(x0,159));saved.append((x0,159,native))
                        for x in range(w):d.text((x0+x*step+12,y0-20),str(x+1),font=tiny,fill='white')
                        for y in range(h):
                            d.text((x0-23,y0+y*step+12),str(y+1),font=tiny,fill='white')
                            for x in range(w):
                                i=y*w+x;xx=x0+x*step;yy=y0+y*step;v=data[i]
                                d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(v,)*3,outline=(255,150,30) if v!=original[i] else (70,70,70))
                                fg='black' if v>=140 else 'white'
                                d.text((xx+step/2,yy+2),str(original[i]),font=tiny,fill=fg,anchor='mt')
                                d.text((xx+step/2,yy+19),str(v),font=tiny,fill=fg,anchor='mt');cells.append((xx+step-3,yy+step-3,v))
                    save(grid,'0001_Hack_Regular_11pt_8_grid.png',saved,cells)
                print('Verified',face['label'],point,'pt',len(needed),'glyphs',flush=True)
            assert sha(files[face['id']])==face['font_sha256']
    finally:
        oracle.close()
    assert len(records)==16 and len({r['id'] for r in records})==16 and len(images)==17
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    result=dict(producer='fontreal-native-normal-study',source_manifest_sha256=sha(MATRIX),
                checker_sha256=sha(Path(__file__)),probe_source_sha256=sha(ROOT/'tests/freetype_mask_probe.cpp'),
                probe_binary_sha256=sha(probe),compositor_sha256=sha(ROOT/'tests/bridge_case_study_test.py'),
                stock_library_sha256=sha(args.stock_library),selected_library_sha256=matrix['library_sha256'],
                filter_sha256=matrix['filter_sha256'],average_sha256=matrix['average_sha256'],
                points=[11,12],logical_dpi=96,scale=1,modes=list(zip(MODES,TITLES,strict=True)),
                conditions=records,images=images,
                limits=['Fixed original shaped positions isolate raster geometry; native-hinted layout and live apps remain unqualified',
                        'The accepted local 1.375 preview does not transfer its coordinates or gain to native-normal masks',
                        'No installed profile or general filter change'])
    previous.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS 16 font/point cases and 17 native-size comparison pages')
    print(OUT)


if __name__=='__main__':
    main()
