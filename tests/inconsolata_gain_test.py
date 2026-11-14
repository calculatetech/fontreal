#!/usr/bin/env python3
"""Compare the requested residual-coverage gain on native Inconsolata masks."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_coverage_test import transform
from bridge_font_matrix_test import sha
from browser_stroke_axis_test import Oracle

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'results/native-normal-study/gallery/manifest.json'
OUT=ROOT/'results/inconsolata-gain/gallery'
MODES=('baseline','partial','full')
TITLES=('Accepted native + 170','×1.375 / ceiling 226','×1.375 / ceiling 255')
TARGETS='HKMVWu'


def gain(data,ceiling):
    assert isinstance(data,bytes) and ceiling in (226,255)
    return bytes(max(v,min(ceiling,(11*v+4)//8)) if 128<=v<230 else v for v in data)


def self_check():
    ramp=bytes(range(256));partial=gain(ramp,226);full=gain(ramp,255)
    for output in (partial,full):
        assert all(a<=b for a,b in zip(ramp,output,strict=True))
        assert all(output[v]==v for v in range(256) if v<128 or v>=230)
    assert all(a<=b for a,b in zip(partial,partial[1:]))
    assert {v:partial[v] for v in (127,128,160,169,170,225,226,229,230,255)}=={
        127:127,128:176,160:220,169:226,170:226,225:226,226:226,229:229,230:230,255:255}
    assert full[169]==232 and full[170]==234 and full[180]==248
    assert full[229]==255 and full[230]==230


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-library',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args=parser.parse_args();self_check()
    parent=json.loads(SOURCE.read_text());assert sha(args.stock_library)==parent['stock_library_sha256']
    for key,name in [('checker_sha256','native_normal_test.py'),('probe_source_sha256','freetype_mask_probe.cpp'),
                     ('compositor_sha256','bridge_case_study_test.py'),('filter_sha256','bridge_coverage_test.py'),
                     ('average_sha256','neighbor_coverage_test.py')]:
        assert parent[key]==sha(ROOT/'tests'/name)
    sources=sorted([r for r in parent['conditions'] if r['font']['family']=='Inconsolata Nerd Font' and r['font']['style']=='Regular'],key=lambda r:r['point_size'])
    assert [r['point_size'] for r in sources]==[11,12]
    OUT.mkdir(parents=True,exist_ok=True);previous=OUT/'manifest.json'
    if previous.exists():
        old=json.loads(previous.read_text());assert old['producer']=='fontreal-inconsolata-gain'
        for r in old['images']:
            p=OUT/r['file'];assert p.parent==OUT and sha(p)==r['sha256'];p.unlink()
    assert not list(OUT.glob('*.png'))
    heading=ImageFont.truetype(str(args.label_font),20)
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
        for source in sources:
            identifier=source['id'];point=source['point_size']
            case_path=ROOT/'build/bridge-font-matrix/native'/(identifier+'.json')
            assert sha(case_path)==source['source_case_sha256']
            case=json.loads(case_path.read_text());assert case['point_size']==point and case['font_id']==source['font']['id']
            glyphs={};masks={mode:{} for mode in MODES};glyph_records=[]
            for record in source['glyphs']:
                gid=record['glyph'];capture_path=ROOT/'build/native-normal-study'/f'{identifier}-g{gid}.json'
                assert sha(capture_path)==record['capture_sha256']
                capture=json.loads(capture_path.read_text());raw=record['raw'];original=bytes.fromhex(raw['mask'])
                assert capture['glyph']==gid==case['character_map'][str(record['codepoint'])]
                assert hashlib.sha256(json.dumps(capture['loaded'],sort_keys=True).encode()).hexdigest()==record['loaded_sha256']
                assert all({k:r[k] for k in raw}==raw for r in capture['rendered'])
                assert oracle.raster(capture['loaded'])==raw
                baseline=bytes.fromhex(record['transformed_mask'])
                assert transform(original,raw['width'])[0]['bridge']==baseline
                glyphs[gid]=dict(glyph=gid,loaded=capture['loaded'],raster=raw)
                masks['baseline'][gid]=baseline;masks['partial'][gid]=gain(baseline,226);masks['full'][gid]=gain(baseline,255)
                for mode in MODES:
                    data=masks[mode][gid]
                    assert len(data)==raw['width']*raw['height']
                    assert all((a>0)==(b>0) for a,b in zip(baseline,data,strict=True))
                    assert all(a==b for a,b in zip(baseline,data,strict=True) if a<128 or a>=230)
                    assert all(a<=b for a,b in zip(baseline,data,strict=True))
                assert all((a>=230)==(b>=230) for a,b in zip(baseline,masks['partial'][gid],strict=True))
                glyph_records.append(dict(record,masks={mode:masks[mode][gid].hex() for mode in MODES},
                    changed_pixels={mode:sum(a!=b for a,b in zip(baseline,masks[mode][gid],strict=True)) for mode in MODES},
                    new_full_pixels={mode:sum(a<255 and b==255 for a,b in zip(baseline,masks[mode][gid],strict=True)) for mode in MODES}))
            assert len(glyph_records)==96
            assert set(TARGETS)<=set(''.join(case['texts'][r['text']][r['start']:r['end']] for r in source['rows']))
            rows=[]
            for definition in source['rows']:
                text=definition['text'];occurrences=[dict(o) for o in case['occurrences'] if o['text']==text and definition['start']<=o['string_index']<definition['end']]
                assert occurrences
                for o in occurrences:o['x']-=definition['x_shift']
                row_case=dict(case,occurrences=occurrences)
                alpha={mode:compose(row_case,glyphs,masks[mode],text) for mode in MODES}
                boxes=[im.getbbox() for im in alpha.values()];assert all(boxes) and max(b[2] for b in boxes)<=470
                top=max(0,min(b[1] for b in boxes)-1);bottom=min(case['height'],max(b[3] for b in boxes)+1)
                crops={mode:im.crop((0,top,470,bottom)) for mode,im in alpha.items()}
                for mode in MODES:assert sum(crops[mode].tobytes())==sum(alpha[mode].tobytes())
                rows.append(crops)
            body_height=sum(r['baseline'].height+8 for r in rows)+28
            image=Image.new('RGB',(1440,145+body_height*2+30),(24,24,24));d=ImageDraw.Draw(image);saved=[]
            d.text((14,12),f'Inconsolata Regular / {point}pt | requested ×1.375 weak-coverage gain',font=heading,fill='white')
            d.text((14,44),'Gain acts once on remaining values 128–229. Values below 128 and at or above 230 stay identical.',font=label,fill='white')
            for column,mode in enumerate(MODES):
                x=6+column*476;d.text((x+8,82),TITLES[column],font=heading,fill='white')
                for palette,dark in enumerate((True,False)):
                    top=115+palette*(body_height+15);bg,fg=((0,0,0),'white') if dark else ((255,255,255),'black')
                    d.rectangle((x,top,x+469,top+body_height-1),fill=bg)
                    d.text((x+8,top+3),'White on black' if dark else 'Black on white',font=label,fill=fg);y=top+28
                    for row in rows:
                        rgb=row[mode].convert('RGB')
                        if not dark:rgb=ImageOps.invert(rgb)
                        assert y+rgb.height<=top+body_height
                        image.paste(rgb,(x,y));saved.append((x,y,rgb));y+=rgb.height+8
            save(image,f'{len(images):04}_Inconsolata_Regular_{point}pt_gain.png',saved)
            if point==11:
                for char in TARGETS:
                    gid=next(r['glyph'] for r in source['glyphs'] if r['codepoint']==ord(char));r=glyphs[gid]['raster'];w,h=r['width'],r['height'];baseline=masks['baseline'][gid]
                    grid=Image.new('RGB',(1440,780),(24,24,24));d=ImageDraw.Draw(grid);saved=[];cells=[]
                    d.text((20,14),f'Inconsolata Regular {char} / 11pt | residual coverage and ×1.375 trials',font=heading,fill='white')
                    d.text((20,48),'Each cell: accepted baseline above, displayed trial below. Orange marks changed cells.',font=label,fill='white')
                    d.text((20,73),'The 226 ceiling retains partial coverage. The 255 control can saturate weak strokes above protected stronger ones.',font=label,fill='white')
                    for column,mode in enumerate(MODES):
                        x0=40+column*476;y0=225;step=36;data=masks[mode][gid]
                        assert x0+w*step<1440 and y0+h*step<740
                        d.text((x0,118),TITLES[column],font=heading,fill='white')
                        native=Image.frombytes('L',(w,h),data).convert('RGB');grid.paste(native,(x0,159));saved.append((x0,159,native))
                        for x in range(w):d.text((x0+x*step+12,y0-20),str(x+1),font=tiny,fill='white')
                        for y in range(h):
                            d.text((x0-23,y0+y*step+12),str(y+1),font=tiny,fill='white')
                            for x in range(w):
                                i=y*w+x;v=data[i];xx=x0+x*step;yy=y0+y*step
                                d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(v,)*3,outline=(255,150,30) if v!=baseline[i] else (70,70,70))
                                fg='black' if v>=140 else 'white'
                                d.text((xx+step/2,yy+2),str(baseline[i]),font=tiny,fill=fg,anchor='mt')
                                d.text((xx+step/2,yy+19),str(v),font=tiny,fill=fg,anchor='mt');cells.append((xx+step-3,yy+step-3,v))
                    save(grid,f'{len(images):04}_Inconsolata_{char}_11pt_grid.png',saved,cells)
            records.append(dict(id=identifier,font=source['font'],point_size=point,native_size=source['native_size'],
                                source_case_sha256=source['source_case_sha256'],rows=source['rows'],glyphs=glyph_records))
    finally:
        oracle.close()
    assert len(records)==2 and len(images)==8 and sum(len(r['glyphs']) for r in records)==192
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    result=dict(producer='fontreal-inconsolata-gain',source_manifest_sha256=sha(SOURCE),
                checker_sha256=sha(Path(__file__)),compositor_sha256=parent['compositor_sha256'],
                parent_checker_sha256=parent['checker_sha256'],filter_sha256=parent['filter_sha256'],
                average_sha256=parent['average_sha256'],stock_library_sha256=sha(args.stock_library),
                gain_ratio=[11,8],inclusive_range=[128,229],ceilings=[226,255],points=[11,12],logical_dpi=96,scale=1,
                conditions=records,images=images,
                limits=['Gain increases coverage; it does not concentrate split strokes or qualify native layout',
                        'The 255 control maps 229 to 255 while protected 230 remains 230; it is not a monotonic general policy',
                        'No installed profile or general gain selected; other fonts and weights remain unqualified'])
    previous.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS 256-value transfer checks / 192 native glyphs / 8 complete pages')
    print(OUT)


if __name__=='__main__':
    main()
