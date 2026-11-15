#!/usr/bin/env python3
"""Compare the preferred B masks with two generic thin-stroke budgets."""
import argparse
import ast
import hashlib
import inspect
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_font_matrix_test import sha, slug
from browser_stroke_axis_test import Oracle
from thin_stroke_profiles import normalize

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT/'docs/images/browser-common-ground'
SOURCE = ROOT/'results/stroke-profile-study/gallery'
OUT = ROOT/'results/thin-stroke-study/gallery'
MODES = ('preferred', 'core226', 'core240')
TITLES = ('Preferred B / unchanged', 'Thin main stroke / core 226', 'Thin main stroke / core 240')


def self_test():
    assert tuple(inspect.signature(normalize).parameters) == ('raw','preferred','width')
    tree = ast.parse((ROOT/'tests/thin_stroke_profiles.py').read_text())
    assert not any(isinstance(n,ast.Name) and n.id in ('open','ord','chr','font','family','glyph','codepoint') for n in ast.walk(tree))
    raw = bytes([135,59]*7); preferred = bytes([186,59]*7)
    result, detail = normalize(raw,preferred,2)
    assert result == dict(core226=bytes([226,29]*7),core240=bytes([240,15]*7))
    assert detail['principal_width'] == 194 and len(detail['lanes']) == 1
    joined = bytes([135,59,0]*3 + [255,255,255] + [135,59,0]*3)
    chosen = bytes([186,59,0]*3 + [255,255,255] + [186,59,0]*3)
    out,_ = normalize(joined,chosen,3)
    assert out['core240'] == bytes([240,15,0]*3+[255,255,255]+[240,15,0]*3)
    near = bytes([100,98]*6)
    assert normalize(near,near,2)[0]['core240'] == bytes([240,15]*6)
    tie = bytes([99,99]*6)
    assert normalize(tie,tie,2)[0]['core240'] == bytes([15,240]*6)
    for source,current,w in [(b'',b'',0),(bytes([135,59]*4),bytes([186,59]*4),2),
                              (bytes([90,80]*7),bytes([124,110]*7),2),
                              (bytes([160,156]*7),bytes([220,215]*7),2),
                              (bytes([135,59,0,240,240]*7),bytes([186,59,0,255,255]*7),5),
                              (raw,bytes([240,15]*7),2)]:
        assert all(v == current for v in normalize(source,current,w)[0].values())
    for source,current,w in [(raw,preferred,2),(joined,chosen,3),(near,near,2)]:
        h = len(source)//w; expected,_ = normalize(source,current,w)
        for new_width,fn in [(w,lambda a:b''.join(a[i:i+w][::-1] for i in range(0,len(a),w))),
                             (w,lambda a:b''.join(a[i:i+w] for i in range(len(a)-w,-1,-w))),
                             (h,lambda a:bytes(a[y*w+x] for x in range(w) for y in range(h)))]:
            actual,_ = normalize(fn(source),fn(current),new_width)
            assert all(actual[m] == fn(v) for m,v in expected.items())
    print('PASS long subpixel / joined core / near tie / wide contrast / short marks / anchors / strong pixels / transforms',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--stock-library',type=Path); parser.add_argument('--label-font',type=Path)
    args = parser.parse_args(); self_test()
    if args.self_test: return
    assert args.stock_library and args.label_font
    record = json.loads((PUBLIC/'stroke-profile-captures.json').read_text())
    assert sha(SOURCE/'manifest.json') == record['full_manifest_sha256']
    source = json.loads((SOURCE/'manifest.json').read_text())
    assert sha(SOURCE/'masks.json') == source['processed_masks_sha256'] == record['processed_masks_sha256']
    assert sha(args.stock_library) == source['library_sha256']
    assert sha(ROOT/'tests/stroke_profiles.py') == source['processor_sha256']
    assert sha(ROOT/'tests/stroke_profile_test.py') == source['checker_sha256']
    for file,digest in source['helpers'].items(): assert sha(ROOT/'tests'/file) == digest
    arrays = json.loads((SOURCE/'masks.json').read_text()); by_id = {c['id']:c for c in arrays}
    assert len(by_id) == len(arrays) == len(source['audit']) == len(record['audit']) == 118
    assert set(by_id) == {c['id'] for c in source['audit']} == {c['id'] for c in record['audit']}
    public_audit = {c['id']:c for c in record['audit']}
    oracle = Oracle(args.stock_library.resolve()); cache = {}; audit = []; all_arrays = []
    try:
        for old in source['audit']:
            identifier = old['id']; saved = by_id[identifier]
            path = (ROOT/'build/stroke-profile-study/decorative-native' if old['extra'] else ROOT/'build/stem-core-study/native')/(identifier+'.json')
            assert sha(path) == old['capture_sha256']; case = json.loads(path.read_text())
            assert {g['codepoint'] for g in case['glyphs']} == set(range(32,127)) and len(case['glyphs']) == 95
            previous = {g['glyph']:g for g in saved['glyphs']}; glyphs = {}; masks = {m:{} for m in ('raw',*MODES)}
            details = {}; entries = []; charmap = {}; stored = []
            for g in case['glyphs']:
                gid = g['glyph']; r = g['rendered'][0]; raw = {k:r[k] for k in ('width','height','left','top','mask')}
                assert g['rendered'][1] == r and oracle.raster(g['loaded']) == raw
                original = bytes.fromhex(r['mask']); preferred = bytes.fromhex(previous[gid]['masks']['corners'])
                assert previous[gid]['width'] == r['width'] and previous[gid]['height'] == r['height']
                assert original.hex() == previous[gid]['masks']['raw']
                old_entry = next(v for v in old['glyphs'] if v['codepoint'] == g['codepoint'])
                public_entry = next(v for v in public_audit[identifier]['glyphs'] if v['codepoint'] == g['codepoint'])
                assert hashlib.sha256(json.dumps(old_entry,sort_keys=True,separators=(',',':')).encode()).hexdigest() == public_entry['record_sha256']
                assert hashlib.sha256(original).hexdigest() == old_entry['masks_sha256']['raw']
                assert hashlib.sha256(preferred).hexdigest() == old_entry['masks_sha256']['corners']
                trials,detail = normalize(original,preferred,r['width'])
                if gid in glyphs:
                    assert glyphs[gid] == dict(loaded=g['loaded'],raster=r)
                    assert all(masks[m][gid] == trials[m] for m in trials)
                else:
                    w,h = r['width'],r['height']
                    if original:
                        for new_width,fn in [(w,lambda a:b''.join(a[i:i+w][::-1] for i in range(0,len(a),w))),
                                             (w,lambda a:b''.join(a[i:i+w] for i in range(len(a)-w,-1,-w))),
                                             (h,lambda a:bytes(a[y*w+x] for x in range(w) for y in range(h)))]:
                            transformed,_ = normalize(fn(original),fn(preferred),new_width)
                            assert all(transformed[m] == fn(v) for m,v in trials.items())
                    stored.append(dict(glyph=gid,width=r['width'],height=r['height'],masks=dict(raw=original.hex(),preferred=preferred.hex(),
                        **{m:v.hex() for m,v in trials.items()}),detail=detail))
                glyphs[gid] = dict(loaded=g['loaded'],raster=r); charmap[g['codepoint']] = gid; details[gid] = detail
                masks['raw'][gid] = original; masks['preferred'][gid] = preferred
                for mode,values in trials.items():
                    assert len(values) == len(original)
                    assert all(bool(a) == bool(b) and (p < 230 or p == b) for a,p,b in zip(original,preferred,values,strict=True))
                    masks[mode][gid] = values
                centroids = {}
                for mode in masks:
                    values = masks[mode][gid]; total = sum(values)
                    centroids[mode] = [sum((i % r['width'])*v for i,v in enumerate(values))/total,
                                       sum((i // r['width'])*v for i,v in enumerate(values))/total] if total else None
                entries.append(dict(codepoint=g['codepoint'],glyph=gid,principal_width=detail['principal_width'],centroids=centroids,
                    changed={m:sum(a!=b for a,b in zip(preferred,v,strict=True)) for m,v in trials.items()},
                    coverage_sums={m:sum(masks[m][gid]) for m in masks},masks_sha256={m:hashlib.sha256(masks[m][gid]).hexdigest() for m in masks}))
            changed = {g for g in glyphs if any(masks[m][g] != masks['preferred'][g] for m in MODES[1:])}
            assert changed <= {o['glyph'] for row in case['rows'] for o in row['occurrences']}
            cache[identifier] = dict(source=old,case=case,glyphs=glyphs,masks=masks,charmap=charmap,details=details,changed=changed)
            audit.append(dict(id=identifier,font=old['font'],point_size=old['point_size'],native_size=old['native_size'],
                capture_sha256=sha(path),unique_glyphs=len(glyphs),glyphs=entries))
            all_arrays.append(dict(id=identifier,glyphs=stored))
        assert sum(len(v['glyphs']) for v in all_arrays) == source['unique_glyph_cases']
    finally: oracle.close()
    OUT.mkdir(parents=True,exist_ok=True); manifest = OUT/'manifest.json'
    if manifest.exists():
        old = json.loads(manifest.read_text()); assert old['producer'] == 'fontreal-thin-strokes'
        for r in old['images']:
            p = OUT/r['file']; assert p.parent == OUT and sha(p) == r['sha256']; p.unlink()
    assert not list(OUT.glob('*.png'))
    heading = ImageFont.truetype(str(args.label_font),20); label = ImageFont.truetype(str(args.label_font),14)
    number = ImageFont.truetype(str(args.label_font),11); images = []; pages = []; regressions = []
    def save(page,name,crops,cells=()):
        p = OUT/name; page.save(p)
        with Image.open(p) as saved:
            for x,y,crop in crops: assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes() == crop.tobytes()
            for x,y,value in cells: assert saved.getpixel((x,y)) == (value,)*3
        images.append(dict(file=name,sha256=sha(p)))
    focus = next(k for k,d in cache.items() if d['source']['font']['family'] == 'Nimbus Mono PS' and d['source']['font']['style'] == 'Regular' and d['source']['point_size'] == 11)
    controls = {k for k,d in cache.items() if d['source']['extra'] or d['source']['font']['family'] in ('Noto Sans','Segoe UI') and d['source']['font']['style'] == 'Regular' and d['source']['point_size'] == 11}
    selected = {k for k,d in cache.items() if d['changed']} | controls | {focus}
    order = [focus] + sorted(selected-{focus},key=lambda k:(k not in controls,k))
    for identifier in order:
        data = cache[identifier]; src = data['source']; f = src['font']; crops = []
        page = Image.new('RGB',(1440,800),(24,24,24)); d = ImageDraw.Draw(page)
        d.text((14,12),f"{f['family']} / {f['style']} / {src['point_size']}pt | thin main-stroke trials",font=heading,fill='white')
        d.text((14,44),'Generic native-width and sustained-lane rules. Already-strong preferred pixels remain exact.',font=label,fill='white')
        changed_chars = ''.join(chr(cp) for cp,gid in data['charmap'].items() if gid in data['changed'])
        d.text((14,66),'Changed characters: '+(changed_chars or 'none (regression control)'),font=label,fill='white')
        baseline = next((p for p in source['pages'] if p['id'] == identifier and not p['intent']),None)
        if baseline: assert sha(SOURCE/baseline['file']) == next(i['sha256'] for i in source['images'] if i['file'] == baseline['file'])
        for column,mode in enumerate(MODES):
            x = 6+column*476; d.text((x+8,98),TITLES[column],font=label,fill='white')
            for palette,dark in enumerate((True,False)):
                top = 130+palette*325; d.rectangle((x,top,x+469,top+309),fill='black' if dark else 'white')
                d.text((x+8,top+3),'White on black' if dark else 'Black on white',font=label,fill='white' if dark else 'black')
                for i,row in enumerate(data['case']['rows']):
                    rgb = compose(row,data['glyphs'],data['masks'][mode],0).convert('RGB')
                    if not dark: rgb = ImageOps.invert(rgb)
                    assert rgb.size == (470,40); y = top+28+i*40
                    if mode == 'preferred' and baseline:
                        with Image.open(SOURCE/baseline['file']) as previous:
                            assert previous.crop((958,y,1428,y+40)).tobytes() == rgb.tobytes()
                    page.paste(rgb,(x,y)); crops.append((x,y,rgb))
        name = f"{len(images):03}_{slug(f['family'])}_{slug(f['style'])}_{src['point_size']}pt_trials.png"
        save(page,name,crops); pages.append(dict(id=identifier,file=name,changed_characters=changed_chars,control=identifier in controls))
    data = cache[focus]
    stems = dict(b=(1,1,8),d=(7,0,8),f=(2,3,8),p=(1,1,9),q=(7,1,9))
    for ch in 'bdfpq':
        gid = data['charmap'][ord(ch)]; r = data['glyphs'][gid]['raster']; w,h = r['width'],r['height']
        assert data['masks']['core240'][gid] != data['masks']['preferred'][gid]
        column,start,end = stems[ch]
        for mode,floor in (('core226',226),('core240',240)):
            assert all(data['masks'][mode][gid][y*w+column] >= floor for y in range(start,end))
        for dark in (True,False):
            page = Image.new('RGB',(1440,700),(24,24,24)); d = ImageDraw.Draw(page); crops = []; cells = []
            d.text((14,12),f'Nimbus Mono PS Regular / 11pt / {ch} | sustained-stem coverage',font=heading,fill='white')
            d.text((14,44),'Coverage: 0 = no ink, 255 = full ink. Orange marks changes from preferred B.',font=label,fill='white')
            d.text((14,66),'White on black.' if dark else 'Black on white. Displayed gray is 255 minus coverage.',font=label,fill='white')
            for column,mode in enumerate(MODES):
                x0 = 30+column*476; y0 = 220; step = 28; values = data['masks'][mode][gid]
                d.text((x0,122),TITLES[column],font=label,fill='white')
                bitmap = Image.frombytes('L',(w,h),values).convert('RGB')
                if not dark: bitmap = ImageOps.invert(bitmap)
                page.paste(bitmap,(x0,164)); crops.append((x0,164,bitmap))
                for x in range(w): d.text((x0+x*step+14,y0-18),str(x+1),font=number,fill='white',anchor='mt')
                for y in range(h):
                    d.text((x0-8,y0+y*step+7),str(y+1),font=number,fill='white',anchor='rt')
                    for x in range(w):
                        i = y*w+x; v = values[i]; display = v if dark else 255-v; xx = x0+x*step; yy = y0+y*step
                        d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(display,)*3,
                            outline=(255,150,30) if v != data['masks']['preferred'][gid][i] else (70,70,70))
                        d.text((xx+14,yy+7),str(v),font=number,fill='black' if display >= 140 else 'white',anchor='mt')
                        cells.append((xx+step-3,yy+step-3,display))
                assert x0+w*step < 1440 and y0+h*step < 620
                d.text((x0,644),f'Coverage sum: {sum(values)}',font=label,fill='white')
            name = f"{len(images):03}_Nimbus-Mono-PS_Regular_11pt_{ch}_{'dark' if dark else 'light'}_grid.png"
            save(page,name,crops,cells)
        regressions.append(dict(character=ch,glyph=gid,raw={k:r[k] for k in ('width','height','left','top','mask')},
            masks={m:data['masks'][m][gid].hex() for m in MODES},detail=data['details'][gid]))
    assert {p['id'] for p in pages} == selected
    assert {p.name for p in OUT.glob('*.png')} == {r['file'] for r in images}
    arrays_path = OUT/'masks.json'; arrays_path.write_text(json.dumps(all_arrays,indent=2)+'\n')
    result = dict(producer='fontreal-thin-strokes',checker_sha256=sha(Path(__file__)),processor_sha256=sha(ROOT/'tests/thin_stroke_profiles.py'),
        preferred_record_sha256=sha(PUBLIC/'stroke-profile-captures.json'),preferred_manifest_sha256=sha(SOURCE/'manifest.json'),
        preferred_arrays_sha256=sha(SOURCE/'masks.json'),preferred_processor_sha256=source['processor_sha256'],
        library_sha256=sha(args.stock_library),label_font=dict(file=args.label_font.name,sha256=sha(args.label_font)),
        logical_dpi=96,scale=1,codepoint_cases=sum(len(c['glyphs']) for c in audit),unique_glyph_cases=sum(c['unique_glyphs'] for c in audit),
        processed_masks_sha256=sha(arrays_path),audit=audit,regressions=regressions,pages=pages,images=images,
        limits=['Experimental one-pixel budget deliberately changes native and preferred coverage area and centroid',
                'Persistent wider strokes block normalization, but this is not a proof of preserved design intent',
                'Printable ASCII, 118 conditions, 11-12pt, 96 DPI, scale 1; installed profiles unchanged'])
    manifest.write_text(json.dumps(result,indent=2)+'\n')
    print(f"PASS {len(audit)} conditions / {result['codepoint_cases']} codepoint cases / {result['unique_glyph_cases']} unique glyphs / {len(images)} pages",flush=True)
    print(OUT,flush=True)


if __name__ == '__main__': main()
