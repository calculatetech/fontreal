#!/usr/bin/env python3
"""Inspect residual contrast without changing the accepted strong-winner masks."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_font_matrix_test import sha, slug
from browser_stroke_axis_test import Oracle
from noto_stem_winner_test import keep_winner

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'docs/images/browser-common-ground'
OUT=ROOT/'results/contrast-focus/gallery'
FAMILIES=('Noto Sans','Segoe UI')
CHARACTERS='aemnou0358HMNW'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-library',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args=parser.parse_args()
    accepted=json.loads((PUBLIC/'stem-winner-captures.json').read_text())
    core=json.loads((PUBLIC/'stem-core-captures.json').read_text())
    full_path=ROOT/'results/stem-core-study/gallery/manifest.json'
    assert sha(full_path)==accepted['full_source_manifest_sha256']==core['full_manifest_sha256']
    full=json.loads(full_path.read_text())
    assert sha(PUBLIC/'stem-core-captures.json')==accepted['source_manifest_sha256']
    assert sha(ROOT/'tests/noto_stem_winner_test.py')==accepted['checker_sha256']
    assert sha(args.stock_library)==accepted['library_sha256']
    for file,digest in accepted['helpers'].items():assert sha(ROOT/'tests'/file)==digest
    OUT.mkdir(parents=True,exist_ok=True);manifest=OUT/'manifest.json'
    if manifest.exists():
        previous=json.loads(manifest.read_text());assert previous['producer']=='fontreal-contrast-focus'
        for image in previous['images']:
            path=OUT/image['file'];assert path.parent==OUT and sha(path)==image['sha256'];path.unlink()
    assert not list(OUT.glob('*.png'))
    heading=ImageFont.truetype(str(args.label_font),20);label=ImageFont.truetype(str(args.label_font),14)
    number=ImageFont.truetype(str(args.label_font),12);images=[];conditions=[];datasets={};records=[]
    oracle=Oracle(args.stock_library.resolve())
    try:
        for family in FAMILIES:
            source=next(c for c in full['conditions'] if c['font']['family']==family and c['font']['style']=='Regular' and c['point_size']==11)
            audit=next(c for c in accepted['audit'] if c['id']==source['id'])
            capture=ROOT/'build/stem-core-study/native'/(source['id']+'.json')
            assert sha(capture)==source['capture_sha256']
            case=json.loads(capture.read_text());glyphs={};masks={};raws={};charmap={};changed=set()
            for g in case['glyphs']:
                saved=next(r for r in source['glyphs'] if r['glyph']==g['glyph']);raw=g['rendered'][0]
                assert g['rendered'][1]==raw and oracle.raster(g['loaded'])==saved['raw']
                assert {k:raw[k] for k in saved['raw']}==saved['raw']
                assert hashlib.sha256(json.dumps(g['loaded'],sort_keys=True).encode()).hexdigest()==saved['loaded_sha256']
                gid=g['glyph'];current,changes=keep_winner(bytes.fromhex(raw['mask']),bytes.fromhex(saved['masks']['baseline']),raw['width'])
                if changes:
                    changed.add(gid);reference=next(r for r in audit['changed_glyphs'] if r['glyph']==gid)
                    assert hashlib.sha256(current).hexdigest()==reference['winner_sha256']
                else:assert current.hex()==saved['masks']['native-area']
                glyphs[gid]=dict(loaded=g['loaded'],raster=raw);masks[gid]=current
                raws[gid]=saved['raw'];charmap[g['codepoint']]=gid
            assert changed=={g['glyph'] for g in audit['changed_glyphs']} and len(glyphs)==95
            page=next(p for p in accepted['affected_pages'] if p['id']==source['id'])
            source_image=ROOT/'results/noto-stem-winner/gallery'/page['file']
            assert sha(source_image)==next(r['sha256'] for r in accepted['images'] if r['file']==page['file'])
            datasets[family]=dict(source=source,case=case,glyphs=glyphs,masks=masks,raws=raws,charmap=charmap,source_image=source_image)
            conditions.append(dict(id=source['id'],font=source['font'],point_size=11,native_size=source['native_size'],
                capture_sha256=sha(capture),accepted_image=dict(file=page['file'],sha256=sha(source_image)),
                glyphs=[dict(glyph=gid,mask_sha256=hashlib.sha256(masks[gid]).hexdigest()) for gid in sorted(glyphs)]))
    finally:
        oracle.close()

    def save(page,name,crops,cells=()):
        assert page.width==1440 and page.height<=880
        path=OUT/name;page.save(path)
        with Image.open(path) as saved:
            for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
            for x,y,v in cells:assert saved.getpixel((x,y))==(v,)*3
        images.append(dict(file=name,sha256=sha(path)))

    page=Image.new('RGB',(1440,800),(24,24,24));d=ImageDraw.Draw(page);crops=[]
    d.text((14,12),'Accepted strong-winner benchmark / Regular / 11pt | residual contrast inspection',font=heading,fill='white')
    d.text((14,44),'96 DPI / 100%. Both columns retain the accepted treatment. These are two fonts, not before and after.',font=label,fill='white')
    d.text((14,66),'No new threshold, coverage gain, pixel redistribution or hinting change is applied.',font=label,fill='white')
    for column,family in enumerate(FAMILIES):
        data=datasets[family];x=6+column*714;d.text((x+16,98),family,font=heading,fill='white')
        with Image.open(data['source_image']) as reference:
            for palette,dark in enumerate((True,False)):
                top=130+palette*325;d.rectangle((x,top,x+699,top+309),fill='black' if dark else 'white')
                d.text((x+16,top+3),'White on black' if dark else 'Black on white',font=label,fill='white' if dark else 'black')
                for index,row in enumerate(data['case']['rows']):
                    alpha=compose(row,data['glyphs'],data['masks'],0);rgb=alpha.convert('RGB')
                    if not dark:rgb=ImageOps.invert(rgb)
                    y=top+28+index*40;assert rgb.size==(470,40)
                    assert reference.crop((736,y,1206,y+40)).tobytes()==rgb.tobytes()
                    page.paste(rgb,(x+16,y));crops.append((x+16,y,rgb))
    save(page,'00_Accepted_Noto-Sans_Segoe-UI_Regular_11pt.png',crops)
    for ch in CHARACTERS:
        for dark in (True,False):
            for family in FAMILIES:
                data=datasets[family];gid=data['charmap'][ord(ch)];raw=data['raws'][gid]
                w,h=raw['width'],raw['height'];assert 0<w<=14 and 0<h<=11
                arrays=dict(raw=bytes.fromhex(raw['mask']),accepted=data['masks'][gid])
                page=Image.new('RGB',(1440,700),(24,24,24));d=ImageDraw.Draw(page);crops=[];cells=[]
                d.text((14,12),f'{family} Regular / 11pt / {ch} | original and accepted coverage',font=heading,fill='white')
                d.text((14,44),'Coverage: 0 = no ink, 255 = full ink. Rows and columns start at one within the glyph bitmap.',font=label,fill='white')
                d.text((14,67),'White on black.' if dark else 'Black on white. Gray is 255 minus coverage; the numbers do not change.',font=label,fill='white')
                d.text((14,90),'This is an unchanged accepted mask, not a new contrast trial. Orange marks changes from original native coverage.',font=label,fill='white')
                for column,mode in enumerate(('raw','accepted')):
                    x0=80+column*714;y0=224;step=32;values=arrays[mode]
                    d.text((x0-10,125),'Original native coverage' if mode=='raw' else 'Accepted strong-winner coverage',font=heading,fill='white')
                    native=Image.frombytes('L',(w,h),values).convert('RGB')
                    if not dark:native=ImageOps.invert(native)
                    strip=Image.new('RGB',(4*(w+8)+8,h+12),'black' if dark else 'white')
                    for repeat in range(4):strip.paste(native,(8+repeat*(w+8),6))
                    page.paste(strip,(x0,166));crops.append((x0,166,strip))
                    for x in range(w):d.text((x0+x*step+step/2,y0-20),str(x+1),font=number,fill='white',anchor='mt')
                    for y in range(h):
                        d.text((x0-13,y0+y*step+9),str(y+1),font=number,fill='white',anchor='rt')
                        for x in range(w):
                            i=y*w+x;v=values[i];display=v if dark else 255-v;xx=x0+x*step;yy=y0+y*step
                            d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(display,)*3,
                                        outline=(255,150,30) if v!=arrays['raw'][i] else (70,70,70))
                            d.text((xx+step/2,yy+9),str(v),font=number,fill='black' if display>=140 else 'white',anchor='mt')
                            cells.append((xx+step-3,yy+step-3,display))
                    assert x0+w*step<1440 and y0+h*step<590
                    d.text((x0-10,610),f'Coverage sum: {sum(values)}',font=label,fill='white')
                d.text((14,662),'Native-size samples repeat this exact glyph without resizing. The grid numbers are coverage, not RGB intensity.',font=label,fill='white')
                save(page,f"{len(images):02}_{slug(family)}_Regular_11pt_{ch}_{'dark' if dark else 'light'}.png",crops,cells)
                if dark:records.append(dict(family=family,character=ch,glyph=gid,raw=raw,accepted=arrays['accepted'].hex(),
                    coverage_rows={m:[list(arrays[m][y*w:(y+1)*w]) for y in range(h)] for m in arrays}))
    assert len(records)==len(FAMILIES)*len(CHARACTERS) and len(images)==1+2*len(records)
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    result=dict(producer='fontreal-contrast-focus',checker_sha256=sha(Path(__file__)),
        accepted_record_sha256=sha(PUBLIC/'stem-winner-captures.json'),core_record_sha256=sha(PUBLIC/'stem-core-captures.json'),
        full_source_sha256=sha(full_path),accepted_checker_sha256=accepted['checker_sha256'],helpers=accepted['helpers'],
        library_sha256=sha(args.stock_library),label_font=dict(file=args.label_font.name,sha256=sha(args.label_font)),
        logical_dpi=96,scale=1,point_size=11,characters=CHARACTERS,conditions=conditions,records=records,images=images,
        limits=['Exact accepted masks only; no new correction or installed profile change',
                'The overview compares fonts; grids compare original native and accepted coverage',
                'Coverage differences can reflect both native geometry and coverage processing'])
    manifest.write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS 190 source glyphs / accepted mask identities / overview equals approved gallery / all cell fills / {len(images)} pages')
    print(OUT)


if __name__=='__main__':
    main()
