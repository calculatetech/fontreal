#!/usr/bin/env python3
"""Compare added coverage with a defined core in one annotated u stem."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_coverage_test import transform
from bridge_font_matrix_test import sha
from browser_stroke_axis_test import Oracle
from inconsolata_gain_test import gain
from neighbor_coverage_test import repeat

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'results/inconsolata-gain/gallery/manifest.json'
OUT=ROOT/'results/inconsolata-u/gallery'
MODES=('chosen','floor','gain-area','native-area')
TITLES=('Chosen gain / 226','Core floor 226','Core 240 / gain area','Core 240 / native area')
TEXTS=['uuuu uuuu UUUU','un nu minimum mu','H K M V W u',
       'The quick brown fox','jumps over the lazy dog.',
       'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz','0123456789 :;!ij.,|[]()']


def u_trials(raw,chosen,width):
    assert isinstance(raw,bytes) and isinstance(chosen,bytes) and width==7 and len(raw)==len(chosen)==49
    reference=raw[5*width+5];assert reference==240
    masks={mode:bytearray(chosen) for mode in MODES}
    peaks={y*width+5 for y in range(4)};pairs=peaks|{i+1 for i in peaks}
    for i in sorted(peaks):
        assert raw[i:i+2]==bytes((144,124)) and chosen[i:i+2]==bytes((198,124))
        masks['floor'][i]=226
        for mode,source in [('gain-area',chosen),('native-area',raw)]:
            total=source[i]+source[i+1]
            assert 0<total-reference<255
            masks[mode][i]=reference;masks[mode][i+1]=total-reference
    result={mode:bytes(data) for mode,data in masks.items()}
    expected={'chosen':(198,124),'floor':(226,124),'gain-area':(240,82),'native-area':(240,28)}
    for mode,data in result.items():
        assert {i for i,(a,b) in enumerate(zip(chosen,data,strict=True)) if a!=b}==(
            set() if mode=='chosen' else peaks if mode=='floor' else pairs)
        assert all((a>0)==(b>0) and (a>=170)==(b>=170) for a,b in zip(chosen,data,strict=True))
        assert all(a==b for a,b in zip(chosen,data,strict=True) if a>=230)
        assert not any(a<255 and b==255 for a,b in zip(chosen,data,strict=True))
        for i in peaks:
            assert tuple(data[i:i+2])==expected[mode]
            if mode!='chosen':assert data[i+1]/sum(data[i:i+2])<chosen[i+1]/sum(chosen[i:i+2])
            if mode=='gain-area':assert sum(data[i:i+2])==sum(chosen[i:i+2])
            if mode=='native-area':assert sum(data[i:i+2])==sum(raw[i:i+2])
    assert sum(result['floor'])==sum(chosen)+112
    assert sum(result['gain-area'])==sum(chosen)
    assert sum(result['native-area'])==sum(chosen)-216
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-library',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args=parser.parse_args();parent=json.loads(SOURCE.read_text())
    assert sha(args.stock_library)==parent['stock_library_sha256']
    for key,name in [('checker_sha256','inconsolata_gain_test.py'),('compositor_sha256','bridge_case_study_test.py'),
                     ('filter_sha256','bridge_coverage_test.py'),('average_sha256','neighbor_coverage_test.py')]:
        assert parent[key]==sha(ROOT/'tests'/name)
    OUT.mkdir(parents=True,exist_ok=True);previous=OUT/'manifest.json'
    if previous.exists():
        old=json.loads(previous.read_text());assert old['producer']=='fontreal-inconsolata-u'
        for r in old['images']:
            p=OUT/r['file'];assert p.parent==OUT and sha(p)==r['sha256'];p.unlink()
    assert not list(OUT.glob('*.png'))
    heading=ImageFont.truetype(str(args.label_font),20)
    title=ImageFont.truetype(str(args.label_font),18)
    label=ImageFont.truetype(str(args.label_font),14)
    tiny=ImageFont.truetype(str(args.label_font),10)
    oracle=Oracle(args.stock_library.resolve());images=[];records=[]

    def save(image,name,crops=(),cells=()):
        assert image.width==1440 and image.height<=880
        path=OUT/name;image.save(path)
        with Image.open(path) as saved:
            for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
            for x,y,v in cells:assert saved.getpixel((x,y))==(v,)*3
        images.append(dict(file=name,sha256=sha(path)))

    try:
        for source in parent['conditions']:
            point=source['point_size'];assert point in (11,12)
            assert source['font']['family']=='Inconsolata Nerd Font' and source['font']['style']=='Regular'
            glyphs={};charmap={};advances=set();masks={mode:{} for mode in MODES}
            for record in source['glyphs']:
                gid=record['glyph'];capture_path=ROOT/'build/native-normal-study'/f"{source['id']}-g{gid}.json"
                assert sha(capture_path)==record['capture_sha256']
                capture=json.loads(capture_path.read_text());raw=record['raw']
                assert capture['glyph']==gid
                assert hashlib.sha256(json.dumps(capture['loaded'],sort_keys=True).encode()).hexdigest()==record['loaded_sha256']
                assert all({k:r[k] for k in raw}==raw for r in capture['rendered'])
                assert oracle.raster(capture['loaded'])==raw
                baseline=transform(bytes.fromhex(raw['mask']),raw['width'])[0]['bridge']
                chosen=bytes.fromhex(record['masks']['partial']);assert gain(baseline,226)==chosen
                assert baseline.hex()==record['masks']['baseline']
                glyphs[gid]=dict(glyph=gid,loaded=capture['loaded'],raster=raw)
                charmap[record['codepoint']]=gid;advances.add(tuple(capture['loaded']['advance']))
                for mode in MODES:masks[mode][gid]=chosen
            assert len(glyphs)==96 and advances=={(512,0)}
            ugid=charmap[ord('u')];r=glyphs[ugid]['raster'];raw=bytes.fromhex(r['mask']);chosen=masks['chosen'][ugid]
            if point==11:
                trials=u_trials(raw,chosen,r['width'])
                for mode in MODES:masks[mode][ugid]=trials[mode]
            for mode in MODES:
                assert all(data==masks['chosen'][gid] for gid,data in masks[mode].items() if gid!=ugid or point==12)
            rows=[]
            for text in TEXTS:
                assert all(ord(ch) in charmap for ch in text)
                layout=dict(width=344,height=32,occurrences=[dict(glyph=charmap[ord(ch)],x=16+index*8,y=20,text=0) for index,ch in enumerate(text)])
                alpha={mode:compose(layout,glyphs,masks[mode],0) for mode in MODES}
                boxes=[im.getbbox() for im in alpha.values()];assert all(boxes)
                top=max(0,min(b[1] for b in boxes)-1);bottom=min(32,max(b[3] for b in boxes)+1)
                crops={mode:im.crop((0,top,344,bottom)) for mode,im in alpha.items()}
                for mode in MODES:assert sum(crops[mode].tobytes())==sum(alpha[mode].tobytes())
                rows.append(crops)
            body_height=sum(row['chosen'].height+5 for row in rows)+28
            zoom_label=145+2*body_height;zoom_y=zoom_label+24;zoom_height=r['height']*12
            image=Image.new('RGB',(1440,zoom_y+zoom_height+20),(24,24,24));d=ImageDraw.Draw(image);saved=[]
            d.text((14,12),f'Inconsolata Regular u / {point}pt | defined core and coverage distribution',font=heading,fill='white')
            d.text((14,44),'Manual upper-right-stem trials only.' if point==11 else '12pt identity holdout: all local previews remain unchanged.',font=label,fill='white')
            d.text((14,66),'The 240 reference comes from the existing lower stem. Outlines stay fixed; concentration shifts the ink centroid.',font=label,fill='white')
            for column,mode in enumerate(MODES):
                x=6+column*356;d.text((x+8,94),TITLES[column],font=title,fill='white')
                for palette,dark in enumerate((True,False)):
                    top=125+palette*(body_height+15);bg,fg=((0,0,0),'white') if dark else ((255,255,255),'black')
                    d.rectangle((x,top,x+343,top+body_height-1),fill=bg)
                    d.text((x+8,top+3),'White on black' if dark else 'Black on white',font=label,fill=fg);y=top+28
                    for row in rows:
                        rgb=row[mode].convert('RGB')
                        if not dark:rgb=ImageOps.invert(rgb)
                        assert y+rgb.height<=top+body_height
                        image.paste(rgb,(x,y));saved.append((x,y,rgb));y+=rgb.height+5
                d.text((x+8,zoom_label),'Exact u pixels ×12',font=label,fill='white')
                zoom=repeat(Image.frombytes('L',(r['width'],r['height']),masks[mode][ugid]).convert('RGB'),12)
                image.paste(zoom,(x+16,zoom_y));saved.append((x+16,zoom_y,zoom))
            save(image,f'{len(images):02}_Inconsolata_u_{point}pt_stem.png',saved)
            if point==11:
                grid=Image.new('RGB',(1440,730),(24,24,24));d=ImageDraw.Draw(grid);saved=[];cells=[]
                d.text((20,14),'Inconsolata u / 11pt | four annotated stem pairs; bowl and other pixels unchanged',font=heading,fill='white')
                d.text((20,48),'Each cell: chosen gain above, displayed trial below. Orange marks changes. No new pixel reaches 255.',font=label,fill='white')
                d.text((20,73),'Top stem pairs: 198+124 / 226+124 / 240+82 / 240+28. The latter totals retain gained or original native stem area.',font=label,fill='white')
                for column,mode in enumerate(MODES):
                    x0=35+column*356;y0=225;step=36;data=masks[mode][ugid];w,h=r['width'],r['height']
                    assert x0+w*step<1440 and y0+h*step<700
                    d.text((x0,120),TITLES[column],font=title,fill='white')
                    native=Image.frombytes('L',(w,h),data).convert('RGB');grid.paste(native,(x0,160));saved.append((x0,160,native))
                    for x in range(w):d.text((x0+x*step+12,y0-20),str(x+1),font=tiny,fill='white')
                    for y in range(h):
                        d.text((x0-23,y0+y*step+12),str(y+1),font=tiny,fill='white')
                        for x in range(w):
                            i=y*w+x;xx=x0+x*step;yy=y0+y*step;v=data[i]
                            d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(v,)*3,outline=(255,150,30) if v!=chosen[i] else (70,70,70))
                            fg='black' if v>=140 else 'white'
                            d.text((xx+step/2,yy+2),str(chosen[i]),font=tiny,fill=fg,anchor='mt')
                            d.text((xx+step/2,yy+19),str(v),font=tiny,fill=fg,anchor='mt');cells.append((xx+step-3,yy+step-3,v))
                save(grid,'01_Inconsolata_u_11pt_grid.png',saved,cells)
            metrics={mode:dict(total=sum(masks[mode][ugid]),pairs=[dict(row=y+1,values=list(masks[mode][ugid][y*r['width']+5:y*r['width']+7]),
                total=sum(masks[mode][ugid][y*r['width']+5:y*r['width']+7]),
                relative_centroid=masks[mode][ugid][y*r['width']+6]/sum(masks[mode][ugid][y*r['width']+5:y*r['width']+7])) for y in range(4)]) for mode in MODES}
            records.append(dict(id=source['id'],font=source['font'],point_size=point,native_size=source['native_size'],native_advance=8,
                                source_case_sha256=source['source_case_sha256'],u=dict(raw=r,chosen=chosen.hex(),masks={mode:masks[mode][ugid].hex() for mode in MODES},metrics=metrics),
                                glyphs=[dict(glyph=g['glyph'],codepoint=g['codepoint'],capture_sha256=g['capture_sha256'],
                                    masks_sha256={mode:hashlib.sha256(masks[mode][g['glyph']]).hexdigest() for mode in MODES}) for g in source['glyphs']]))
    finally:
        oracle.close()
    assert len(records)==2 and [r['point_size'] for r in records]==[11,12] and len(images)==3
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    result=dict(producer='fontreal-inconsolata-u',source_manifest_sha256=sha(SOURCE),checker_sha256=sha(Path(__file__)),
                gain_checker_sha256=parent['checker_sha256'],compositor_sha256=parent['compositor_sha256'],
                filter_sha256=parent['filter_sha256'],average_sha256=parent['average_sha256'],stock_library_sha256=sha(args.stock_library),
                texts=TEXTS,logical_dpi=96,scale=1,annotated_zero_based_rows=[0,1,2,3],core_column=5,fringe_column=6,reference_cell=[5,5],
                conditions=records,images=images,
                limits=['One-glyph manual annotations, not a general stroke detector or installed policy',
                        'Concentration shifts the ink centroid; unchanged outlines do not guarantee identical perceived geometry',
                        'Controlled simple Latin native advances do not qualify general shaping, kerning or live applications'])
    previous.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS 192 native sources / exact 4-or-8-cell deltas / pair totals / held-out masks / 3 complete pages')
    print(OUT)


if __name__=='__main__':
    main()
