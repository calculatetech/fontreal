#!/usr/bin/env python3
"""Show the exact Noto Sans Regular 11pt coverage from the broad core study."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_font_matrix_test import sha
from bridge_coverage_test import transform
from browser_stroke_axis_test import Oracle
from inconsolata_gain_test import gain
from stem_core_test import concentrate

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'docs/images/browser-common-ground/stem-core-captures.json'
OUT=ROOT/'results/noto-coverage-grid/gallery'
MODES=('raw','baseline','native-area','gain-area')
TITLES=('Original native coverage','170 + gain 226','Core 240 / native area','Core 240 / gained area')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-library',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args=parser.parse_args();parent=json.loads(PARENT.read_text())
    assert parent['producer']=='fontreal-stem-core-study'
    assert sha(args.stock_library)==parent['libraries']['libfreetype.so.']['sha256']
    for file,digest in parent['sources'].items():assert sha(ROOT/'tests'/file)==digest
    sources=[c for c in parent['conditions'] if c['font']['family']=='Noto Sans' and
             c['font']['style']=='Regular' and c['point_size']==11]
    assert len(sources)==1;source=sources[0]
    path=ROOT/'build/stem-core-study/native'/(source['id']+'.json')
    assert sha(path)==source['capture_sha256'], 'Regenerate the matching stem-core study capture first'
    case=json.loads(path.read_text());assert case['point_size']==11 and case['native_size']==source['native_size']
    assert case['font_id']==source['font']['id'] and case['font_format']==source['font']['format']
    OUT.mkdir(parents=True,exist_ok=True);manifest=OUT/'manifest.json'
    if manifest.exists():
        previous=json.loads(manifest.read_text());assert previous['producer']=='fontreal-noto-coverage-grid'
        for r in previous['images']:
            p=OUT/r['file'];assert p.parent==OUT and sha(p)==r['sha256'];p.unlink()
    assert not list(OUT.glob('*.png'))
    heading=ImageFont.truetype(str(args.label_font),20);label=ImageFont.truetype(str(args.label_font),14)
    number=ImageFont.truetype(str(args.label_font),12)
    oracle=Oracle(args.stock_library.resolve());records=[];images=[]
    try:
        for ch in 'aeon':
            g=next(g for g in case['glyphs'] if g['codepoint']==ord(ch));r=g['rendered'][0]
            reference=next(g for g in source['glyphs'] if g['codepoint']==ord(ch))
            assert g['glyph']==reference['glyph'] and g['rendered'][1]==r
            assert hashlib.sha256(json.dumps(g['loaded'],sort_keys=True).encode()).hexdigest()==reference['loaded_sha256']
            raw={k:r[k] for k in ('width','height','left','top','mask')}
            assert oracle.raster(g['loaded'])==raw and r['pixel_mode']==2 and r['grays']==256
            w,h=r['width'],r['height'];original=bytes.fromhex(r['mask'])
            baseline=gain(transform(original,w)[0]['bridge'],226)
            trials,pairs=concentrate(original,baseline,w);assert not pairs
            assert trials['native-area']==trials['gain-area']==baseline
            masks=dict(raw=original,**trials)
            assert hashlib.sha256(b''.join(masks[m] for m in MODES)).hexdigest()==reference['masks_sha256']
            assert (w,h)==(reference['width'],reference['height'])
            assert 0<w<=9 and h==8
            for dark in (True,False):
                page=Image.new('RGB',(1440,620),(24,24,24));d=ImageDraw.Draw(page);crops=[];cells=[]
                d.text((14,12),f'Noto Sans Regular / 11pt / {ch} | numbered pixel coverage',font=heading,fill='white')
                d.text((14,44),'96 DPI / 100%. Coverage: 0 = no ink, 255 = full ink. Row and column numbers start at 1.',font=label,fill='white')
                d.text((14,67),'White on black.' if dark else 'Black on white. Numbers remain coverage values; displayed gray is 255 minus coverage.',font=label,fill='white')
                d.text((14,90),'No straight-stem pairs qualify in this glyph. All three processed maps are identical.',font=label,fill='white')
                for col,mode in enumerate(MODES):
                    x0=36+col*356;y0=236;step=34;data=masks[mode]
                    d.text((x0-10,125),TITLES[col],font=label,fill='white')
                    d.text((x0-10,151),'Exact native pixels:',font=label,fill='white')
                    native=Image.frombytes('L',(w,h),data).convert('RGB')
                    if not dark:native=ImageOps.invert(native)
                    strip=Image.new('RGB',(4*(w+8)+8,h+12),'black' if dark else 'white')
                    for repeat in range(4):strip.paste(native,(8+repeat*(w+8),6))
                    page.paste(strip,(x0,177));crops.append((x0,177,strip))
                    for x in range(w):d.text((x0+x*step+step/2,y0-20),str(x+1),font=number,fill='white',anchor='mt')
                    for y in range(h):
                        d.text((x0-13,y0+y*step+10),str(y+1),font=number,fill='white',anchor='rt')
                        for x in range(w):
                            i=y*w+x;v=data[i];display=v if dark else 255-v;xx=x0+x*step;yy=y0+y*step
                            d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(display,)*3,
                                        outline=(255,150,30) if v!=original[i] else (70,70,70))
                            d.text((xx+step/2,yy+10),str(v),font=number,fill='black' if display>=140 else 'white',anchor='mt')
                            cells.append((xx+step-3,yy+step-3,display))
                    assert x0+w*step<1440 and y0+h*step<535
                    d.text((x0-10,535),f'Coverage sum: {sum(data)}',font=label,fill='white')
                d.text((14,578),'Orange borders mark changes from original native coverage. No new darkening is applied by this chart.',font=label,fill='white')
                name=f"{len(images):02}_Noto-Sans_Regular_11pt_{ch}_{'dark' if dark else 'light'}.png"
                target=OUT/name;page.save(target)
                with Image.open(target) as saved:
                    for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
                    for x,y,v in cells:assert saved.getpixel((x,y))==(v,)*3
                images.append(dict(file=name,sha256=sha(target)))
            records.append(dict(character=ch,glyph=g['glyph'],raw=raw,loaded=g['loaded'],masks={m:masks[m].hex() for m in MODES},
                                coverage_rows={m:[list(masks[m][y*w:(y+1)*w]) for y in range(h)] for m in MODES}))
    finally:
        oracle.close()
    assert len(records)==4 and len(images)==8
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    result=dict(producer='fontreal-noto-coverage-grid',source_manifest_sha256=sha(PARENT),native_capture_sha256=sha(path),
                checker_sha256=sha(Path(__file__)),helpers=parent['sources'],font=source['font'],point_size=11,
                native_size=source['native_size'],logical_dpi=96,scale=1,library_sha256=sha(args.stock_library),
                label_font=dict(file=args.label_font.name,sha256=sha(args.label_font)),records=records,images=images,
                limits=['Exact existing masks only; no new coverage treatment',
                        'All three processed maps are identical for these four glyphs',
                        'Cell numbers are coverage, not background-dependent RGB intensity'])
    manifest.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS 4 source glyphs / original and three exact processed masks / all native strips and numbered cell fills / 8 pages')
    print(OUT)


if __name__=='__main__':
    main()
