#!/usr/bin/env python3
"""Inspect the unchanged bridge treatment in five fonts at 11–12pt."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_coverage_test import transform, bridge_checks
from browser_stroke_axis_test import Oracle
from bridge_font_matrix_test import sha, slug

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'results/bridge-font-matrix/gallery'
NATIVE = ROOT/'build/bridge-font-matrix/native'
OUT = ROOT/'results/bridge-case-studies/gallery'
TARGETS = {'Hack':'noe8', 'Inconsolata Nerd Font':'moe8', 'Nimbus Roman':'oes8',
           'DejaVu Sans':'SAYW', 'Arial':'AVWY'}
STYLES = ('Regular', 'Italic', 'Bold', 'Bold Italic')


def compose(case, glyphs, masks, text=None):
    size = case['width'], case['height']
    scalar = bytearray(size[0]*size[1])
    image = Image.new('RGBA', size)
    for o in case['occurrences']:
        if text is not None and o['text'] != text:
            continue
        assert o['glyph'], 'Case-study text must exist in this exact face'
        r = glyphs[o['glyph']]['raster']; data = masks[o['glyph']]
        x, y = o['x']+r['left'], o['y']-r['top']
        assert x >= 0 and y >= 0 and x+r['width'] <= size[0] and y+r['height'] <= size[1]
        if not data:
            continue
        layer = Image.new('RGBA', (r['width'], r['height']))
        layer.putalpha(Image.frombytes('L', layer.size, data)); image.alpha_composite(layer, (x,y))
        for i, a in enumerate(data):
            at = (y+i//r['width'])*size[0]+x+i%r['width']
            scalar[at] = a+(scalar[at]*(255-a)+127)//255
    assert image.getchannel('A').tobytes() == bytes(scalar)
    return Image.frombytes('L', size, bytes(scalar))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-library', type=Path, required=True)
    parser.add_argument('--label-font', type=Path, required=True)
    args = parser.parse_args(); bridge_checks()
    manifest_path = SOURCE/'manifest.json'; manifest = json.loads(manifest_path.read_text())
    assert manifest['profile'] == '170 + guarded bridge only'
    for key, name in [('filter_sha256','bridge_coverage_test.py'), ('average_sha256','neighbor_coverage_test.py'),
                      ('checker_sha256','bridge_font_matrix_test.py'), ('batch_source_sha256','font_matrix_probe.cpp')]:
        assert manifest[key] == sha(ROOT/'tests'/name)
    assert sha(args.stock_library) == manifest['stock_library_sha256']
    OUT.mkdir(parents=True, exist_ok=True)
    previous = OUT/'manifest.json'
    if previous.exists():
        old = json.loads(previous.read_text()); assert old['producer'] == 'fontreal-bridge-case-studies'
        for r in old['images']:
            p = OUT/r['file']; assert p.parent == OUT and sha(p) == r['sha256']; p.unlink()
    assert not list(OUT.glob('*.png')), 'Unowned images in case-study folder'
    label = ImageFont.truetype(str(args.label_font), 15)
    heading = ImageFont.truetype(str(args.label_font), 21)
    tiny = ImageFont.truetype(str(args.label_font), 10)
    oracle = Oracle(args.stock_library.resolve())
    images, records, source_cases = [], [], []

    def save(image, name, crops=(), cells=()):
        assert image.size[0] == 1440 and image.size[1] <= 880
        path = OUT/name; image.save(path)
        with Image.open(path) as saved:
            for x,y,crop in crops:
                assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes() == crop.tobytes()
            for x,y,value in cells:
                assert saved.getpixel((x,y)) == (value,)*3
        images.append(dict(file=name, sha256=sha(path)))

    try:
        for family_number, (family, chars) in enumerate(TARGETS.items()):
            faces = [f for f in manifest['faces'] if f['family']==family and f['style'] in STYLES]
            faces.sort(key=lambda f: STYLES.index(f['style']))
            assert {f['style'] for f in faces} == (set(STYLES[:1])|{'Bold'} if family=='Inconsolata Nerd Font' else set(STYLES))
            summary = Image.new('RGB',(1440, 150+len(faces)*2*82),(30,30,30))
            draw = ImageDraw.Draw(summary)
            draw.text((20,14),family+' | 11–12pt | current 170 + guarded bridge',font=heading,fill='white')
            draw.text((20,48),'Native size, 96 DPI / 100%. All styles are actual faces. No new treatment is applied.',font=label,fill='white')
            crops = []; row = 0
            for point in (11,12):
                for face in faces:
                    identifier = f"{face['id']}-{point:02}"
                    record = next(r for r in manifest['conditions'] if r['id']==identifier)
                    path = NATIVE/(identifier+'.json'); assert sha(path)==record['native_capture_sha256']
                    case = json.loads(path.read_text())
                    assert case['id']==identifier and case['font_id']==face['id'] and case['point_size']==point
                    assert case['texts'][:10]==manifest['texts']
                    glyphs = {g['glyph']:g for g in case['glyphs']}; masks = {}
                    for gid,g in glyphs.items():
                        r = g['raster']; raw = bytes.fromhex(r['mask'])
                        assert oracle.raster(g['loaded']) == {k:r[k] for k in ('width','height','left','top','mask')}
                        masks[gid] = transform(raw,r['width'])[0]['bridge']
                    # Keep missing characters out of these focused native strips.
                    assert not any(o['text'] in (0,8) for o in case['missing'])
                    strips = []
                    for text in (0,8):
                        alpha = compose(case,glyphs,masks,text); box = alpha.getbbox(); assert box
                        assert box[2] <= 680
                        strip = alpha.crop((0,max(0,box[1]-1),680,min(alpha.height,box[3]+1)))
                        assert sum(strip.tobytes())==sum(alpha.tobytes())
                        strips.append(strip)
                    top = 96+row*82
                    for column, dark in enumerate((True,False)):
                        x=column*720; bg,fg=((0,0,0),'white') if dark else ((255,255,255),'black')
                        draw.rectangle((x,top,x+719,top+81),fill=bg)
                        draw.text((x+20,top+2),f"{point}pt / {face['style']} / "+('white on black' if dark else 'black on white'),font=label,fill=fg)
                        y=top+24
                        for strip in strips:
                            rgb=strip.convert('RGB') if dark else ImageOps.invert(strip.convert('RGB'))
                            assert y+rgb.height<=top+82
                            summary.paste(rgb,(x+20,y)); crops.append((x+20,y,rgb)); y+=rgb.height+3
                    row+=1
                    # Native strips must reproduce their pixels in the existing broad gallery.
                    broad = next(r for r in manifest['images'] if r.get('font_id')==face['id'] and point in r['points'] and r['palette']=='Dark')
                    image_path=SOURCE/broad['file']; assert sha(image_path)==broad['sha256']
                    body_y=126+sum(json.loads((NATIVE/f"{face['id']}-{p:02}.json").read_text())['height']+38 for p in broad['points'] if p<point)
                    with Image.open(image_path) as original:
                        for text,strip in zip((0,8),strips,strict=True):
                            alpha=compose(case,glyphs,masks,text); box=alpha.getbbox(); yy=max(0,box[1]-1)
                            assert original.crop((20,body_y+yy,700,body_y+yy+strip.height)).tobytes()==strip.convert('RGB').tobytes()
                    source_cases.append(dict(id=identifier,font=face,source_sha256=sha(path)))
                    if face['style'] != 'Regular':
                        continue
                    details=[]
                    for char in chars:
                        gid=case['character_map'][str(ord(char))]; r=glyphs[gid]['raster']; raw=bytes.fromhex(r['mask']); current=masks[gid]
                        modes, selected, decisions=transform(raw,r['width'])
                        assert current==modes['bridge']
                        detail=dict(family=family,point_size=point,native_size=case['native_size'],character=char,
                                    width=r['width'],height=r['height'],raw=list(raw),current=list(current),
                                    bridges=sorted(selected),bridge_decisions=decisions,
                                    changed_pixels=sum(a!=b for a,b in zip(raw,current,strict=True)),
                                    raw_row_sums=[sum(raw[i:i+r['width']]) for i in range(0,len(raw),r['width'])],
                                    current_row_sums=[sum(current[i:i+r['width']]) for i in range(0,len(current),r['width'])],
                                    raw_column_sums=[sum(raw[x::r['width']]) for x in range(r['width'])],
                                    current_column_sums=[sum(current[x::r['width']]) for x in range(r['width'])])
                        details.append(detail); records.append(detail)
                    for pair in range(2):
                        image=Image.new('RGB',(1440,820),(24,24,24)); d=ImageDraw.Draw(image); cells=[]; native_crops=[]
                        d.text((20,14),f'{family} / Regular / {point}pt | current coverage and original values',font=heading,fill='white')
                        d.text((20,49),'Each cell: original value above, current value below. Fill shows current white-on-black coverage.',font=label,fill='white')
                        d.text((20,75),'Orange = boosted. Blue = unchanged 1–169, including fringes. Neither marker declares a pixel defective.',font=label,fill='white')
                        for column, detail in enumerate(details[pair*2:pair*2+2]):
                            x0=30+column*710; y0=220; step=38; w=detail['width']; h=detail['height']
                            assert x0+w*step<1440 and y0+h*step<780
                            d.text((x0,119),detail['character']+f" | {detail['changed_pixels']} changed pixels",font=heading,fill='white')
                            native=Image.frombytes('L',(w,h),bytes(detail['current'])).convert('RGB')
                            image.paste(native,(x0,158)); native_crops.append((x0,158,native))
                            for xx in range(w):d.text((x0+xx*step+12,y0-21),str(xx+1),font=tiny,fill='white')
                            for yy in range(h):
                                d.text((x0-23,y0+yy*step+13),str(yy+1),font=tiny,fill='white')
                                for xx in range(w):
                                    i=yy*w+xx; a,b=detail['raw'][i],detail['current'][i]; x=x0+xx*step; y=y0+yy*step
                                    border=(255,150,30) if a!=b else ((70,170,255) if 0<a<170 else (70,70,70))
                                    d.rectangle((x,y,x+step-1,y+step-1),fill=(b,)*3,outline=border)
                                    fg='black' if b>=140 else 'white'
                                    d.text((x+step/2,y+3),str(a),font=tiny,fill=fg,anchor='mt')
                                    d.text((x+step/2,y+19),str(b),font=tiny,fill=fg,anchor='mt')
                                    cells.append((x+step-3,y+step-3,b))
                        save(image,f'{family_number:02}_2_{slug(family)}_{point}pt_pixels_{pair+1}.png',native_crops,cells)
            save(summary,f'{family_number:02}_1_{slug(family)}_11-12pt_native.png',crops)
    finally:
        oracle.close()
    assert len(records)==40 and len(source_cases)==36 and len(images)==25
    nimbus=next(r for r in records if r['family']=='Nimbus Roman' and r['point_size']==11 and r['character']=='o')
    assert nimbus['raw'][:6]==[3,113,105,144,133,4] and nimbus['current'][:6]==nimbus['raw'][:6]
    arial=next(r for r in records if r['family']=='Arial' and r['point_size']==11 and r['character']=='V')
    assert arial['raw'][:2]==[192,199] and arial['current'][:2]==[255,255]
    assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    result=dict(producer='fontreal-bridge-case-studies',source_manifest_sha256=sha(manifest_path),
                checker_sha256=sha(Path(__file__)),filter_sha256=manifest['filter_sha256'],
                average_sha256=manifest['average_sha256'],stock_library_sha256=sha(args.stock_library),
                points=[11,12],logical_dpi=96,scale=1,profile=manifest['profile'],
                source_cases=source_cases,glyphs=records,images=sorted(images,key=lambda r:r['file']),
                limits=['Unchanged diagnostic treatment; no installed profile change',
                        'Low coverage includes intended edge softening; marked cells are not an automatic repair mask',
                        'Row and column sums measure coverage, not perceived weight or outline accuracy'])
    previous.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS 36 exact font/point/style cases, 40 numbered glyphs, 25 native-size pages')
    print(OUT)


if __name__=='__main__':
    main()
