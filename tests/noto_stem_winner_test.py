#!/usr/bin/env python3
"""Keep one existing strong core in the Noto n split-stem diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_case_study_test import compose
from bridge_coverage_test import transform
from bridge_font_matrix_test import sha, slug
from browser_stroke_axis_test import Oracle
from inconsolata_gain_test import gain
from neighbor_coverage_test import repeat
from stem_core_test import concentrate

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'docs/images/browser-common-ground/stem-core-captures.json'
OUT=ROOT/'results/noto-stem-winner/gallery'
MODES=('previous','winner')
TITLES=('Previous core trial','Preserve the strong winner')


def keep_winner(raw,chosen,width):
    previous=concentrate(raw,chosen,width)[0]['native-area']
    # Detect weak native stems before the contrast pass raises an existing core.
    native_pairs=concentrate(raw,raw,width)[1]
    result=bytearray(previous);changes=[]
    for pair in native_pairs:
        core,fringe=pair['core'],pair['fringe']
        if chosen[core]<230 or chosen[fringe]>=230:
            continue
        remainder=raw[core]+raw[fringe]-chosen[core]
        if not 0<remainder<min(chosen[core],chosen[fringe]):
            continue
        assert previous[core]==chosen[core] and previous[fringe]==chosen[fringe]
        result[fringe]=remainder
        changes.append(dict(axis=pair['axis'],core=core,fringe=fringe,
                            previous=[chosen[core],chosen[fringe]],winner=[chosen[core],remainder],
                            native_total=raw[core]+raw[fringe]))
    result=bytes(result);selected={r['fringe'] for r in changes}
    assert {i for i,(a,b) in enumerate(zip(previous,result,strict=True)) if a!=b}==selected
    assert all((a>0)==(b>0) and (a<230 or a==b) for a,b in zip(chosen,result,strict=True))
    for pair in changes:
        assert result[pair['core']]+result[pair['fringe']]==pair['native_total']
        assert result[pair['core']]>result[pair['fringe']]>0
    return result,changes


def self_test():
    data=json.loads((ROOT/'docs/images/browser-common-ground/noto-coverage-captures.json').read_text())
    n=next(r for r in data['records'] if r['character']=='n')
    raw=bytes.fromhex(n['raw']['mask']);chosen=bytes.fromhex(n['masks']['baseline'])
    result,pairs=keep_winner(raw,chosen,8);expected=bytearray(chosen)
    for y in range(4,8):expected[y*8+1]=91
    assert result==bytes(expected) and len(pairs)==4
    assert all(r['previous']==[245,209] and r['winner']==[245,91] and r['native_total']==336 for r in pairs)
    assert result[:32]==chosen[:32] and sum(result)==sum(chosen)-472
    assert all(result[y*8]==245 for y in range(8))
    u=json.loads((ROOT/'docs/images/browser-common-ground/inconsolata-u-captures.json').read_text())['conditions'][0]['u']
    u_result,u_changes=keep_winner(bytes.fromhex(u['raw']['mask']),bytes.fromhex(u['chosen']),7)
    assert u_result.hex()==u['masks']['native-area'] and not u_changes
    def transpose(data,w):
        return bytes(data[y*w+x] for x in range(w) for y in range(len(data)//w))
    flip=lambda a:b''.join(a[i:i+8][::-1] for i in range(0,len(a),8))
    assert keep_winner(transpose(raw,8),transpose(chosen,8),8)[0]==transpose(result,8)
    assert keep_winner(flip(raw),flip(chosen),8)[0]==flip(result)
    raw=bytes([184,152]*4);chosen=bytes([245,209]*4)
    assert keep_winner(raw,chosen,2)[0]==bytes([245,91]*4)
    assert keep_winner(transpose(raw,2),transpose(chosen,2),4)[0]==transpose(bytes([245,91]*4),2)
    for raw,chosen,w in [(b'',b'',0),(bytes([184,152]*2),bytes([245,209]*2),2),
                         (bytes([184,152]*4),bytes([245,240]*4),2),
                         (bytes([120,80]*4),bytes([245,100]*4),2),
                         (bytes([255,200]*4),bytes([255,226]*4),2)]:
        assert keep_winner(raw,chosen,w)[0]==chosen and not keep_winner(raw,chosen,w)[1]
    print('PASS exact four n donors / protected cores and join / u identity / axes / reflection / exclusions')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-library',type=Path,required=True)
    parser.add_argument('--label-font',type=Path,required=True)
    args=parser.parse_args();self_test()
    parent=json.loads(PARENT.read_text());full_path=ROOT/'results/stem-core-study/gallery/manifest.json'
    assert sha(full_path)==parent['full_manifest_sha256']
    full=json.loads(full_path.read_text());assert sha(args.stock_library)==parent['libraries']['libfreetype.so.']['sha256']
    for file,digest in parent['sources'].items():assert sha(ROOT/'tests'/file)==digest
    audit=[];selected=None;audited_masks={}
    for source in full['conditions']:
        public=next(c for c in parent['conditions'] if c['id']==source['id'])
        assert source['capture_sha256']==public['capture_sha256'] and source['font']==public['font']
        glyphs=[];winners={}
        for g in source['glyphs']:
            reference=next(r for r in public['glyphs'] if r['glyph']==g['glyph'])
            raw=bytes.fromhex(g['raw']['mask']);baseline=gain(transform(raw,g['raw']['width'])[0]['bridge'],226)
            previous=concentrate(raw,baseline,g['raw']['width'])[0]['native-area']
            assert baseline.hex()==g['masks']['baseline'] and previous.hex()==g['masks']['native-area']
            assert hashlib.sha256(raw+b''.join(bytes.fromhex(g['masks'][m]) for m in ('baseline','native-area','gain-area'))).hexdigest()==reference['masks_sha256']
            winner,changes=keep_winner(raw,baseline,g['raw']['width'])
            winners[g['glyph']]=winner
            if changes:glyphs.append(dict(glyph=g['glyph'],codepoint=g['codepoint'],changes=changes,
                                         previous_sha256=hashlib.sha256(previous).hexdigest(),winner_sha256=hashlib.sha256(winner).hexdigest()))
        audit.append(dict(id=source['id'],font=source['font'],point_size=source['point_size'],changed_glyphs=glyphs))
        if glyphs:audited_masks[source['id']]=winners
        if source['font']['family']=='Noto Sans' and source['font']['style']=='Regular' and source['point_size']==11:selected=source
    assert len(audit)==len(full['conditions'])==108 and sum(len(c['glyphs']) for c in full['conditions'])==10260 and selected
    capture=ROOT/'build/stem-core-study/native'/(selected['id']+'.json');assert sha(capture)==selected['capture_sha256']
    case=json.loads(capture.read_text());glyphs={};masks={m:{} for m in MODES};oracle=Oracle(args.stock_library.resolve())
    try:
        for g in case['glyphs']:
            r=g['rendered'][0];assert g['rendered'][1]==r and oracle.raster(g['loaded'])=={k:r[k] for k in ('width','height','left','top','mask')}
            saved=next(x for x in selected['glyphs'] if x['glyph']==g['glyph'])
            assert hashlib.sha256(json.dumps(g['loaded'],sort_keys=True).encode()).hexdigest()==saved['loaded_sha256']
            previous=bytes.fromhex(saved['masks']['native-area']);gid=g['glyph']
            glyphs[gid]=dict(loaded=g['loaded'],raster=r);masks['previous'][gid]=previous;masks['winner'][gid]=previous
            if g['codepoint']==ord('n'):
                ngid=gid;baseline=bytes.fromhex(saved['masks']['baseline'])
                winner,pairs=keep_winner(bytes.fromhex(r['mask']),baseline,r['width'])
                masks['winner'][gid]=winner;assert len(pairs)==4
    finally:
        oracle.close()
    assert all(a==masks['winner'][gid] for gid,a in masks['previous'].items() if gid!=ngid)
    r=glyphs[ngid]['raster'];assert (r['width'],r['height'])==(8,8)
    advance=glyphs[ngid]['loaded']['advance'];assert advance[1]==0 and advance[0]>0 and advance[0]%64==0
    OUT.mkdir(parents=True,exist_ok=True);manifest=OUT/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text());assert old['producer']=='fontreal-noto-stem-winner'
        for record in old['images']:
            p=OUT/record['file'];assert p.parent==OUT and sha(p)==record['sha256'];p.unlink()
    assert not list(OUT.glob('*.png'))
    heading=ImageFont.truetype(str(args.label_font),20);label=ImageFont.truetype(str(args.label_font),14)
    number=ImageFont.truetype(str(args.label_font),15);images=[]
    def save(page,name,crops,cells=()):
        assert page.width==1440 and page.height<=880
        p=OUT/name;page.save(p)
        with Image.open(p) as saved:
            for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
            for x,y,value in cells:assert saved.getpixel((x,y))==(value,)*3
        images.append(dict(file=name,sha256=sha(p)))
    page=Image.new('RGB',(1440,800),(24,24,24));d=ImageDraw.Draw(page);crops=[]
    d.text((14,12),'Noto Sans Regular / 11pt / n | one strong core, less competing fringe',font=heading,fill='white')
    d.text((14,44),'Straight lower stem: 245 + 209 becomes 245 + 91. Original native pair total: 336.',font=label,fill='white')
    d.text((14,66),'Only n changes in this visual trial. The upper join, crown, other glyphs and all strong pixels stay identical.',font=label,fill='white')
    repeated=dict(width=470,height=32,occurrences=[dict(glyph=ngid,text=0,x=16+i*int(advance[0]/64),y=20) for i in range(16)])
    rows=[repeated]+[case['rows'][i] for i in (0,1,2,6)]
    for column,mode in enumerate(MODES):
        x=6+column*714;d.text((x+16,98),TITLES[column],font=heading,fill='white')
        for palette,dark in enumerate((True,False)):
            top=130+palette*244;d.rectangle((x,top,x+699,top+227),fill='black' if dark else 'white')
            d.text((x+16,top+3),'White on black' if dark else 'Black on white',font=label,fill='white' if dark else 'black')
            y=top+28
            for row in rows:
                alpha=compose(row,glyphs,masks[mode],0);rgb=alpha.convert('RGB')
                if not dark:rgb=ImageOps.invert(rgb)
                page.paste(rgb,(x+16,y));crops.append((x+16,y,rgb));y+=rgb.height
            assert y<=top+228
        d.text((x+16,620),'Exact n pixels x14, dark then light',font=label,fill='white')
        zoom=repeat(Image.frombytes('L',(8,8),masks[mode][ngid]).convert('RGB'),14)
        for i,crop in enumerate((zoom,ImageOps.invert(zoom))):page.paste(crop,(x+16+i*145,650));crops.append((x+16+i*145,650,crop))
    save(page,'00_Noto-Sans_Regular_11pt_n_native.png',crops)
    for dark in (True,False):
        page=Image.new('RGB',(1440,650),(24,24,24));d=ImageDraw.Draw(page);crops=[];cells=[]
        d.text((14,12),'Noto Sans Regular / 11pt / n | preserve 245, restore native pair area',font=heading,fill='white')
        d.text((14,44),'Coverage values: 0 = no ink, 255 = full ink. Rows and columns start at one.',font=label,fill='white')
        d.text((14,67),'White on black.' if dark else 'Black on white. Displayed gray is 255 minus coverage; numbers do not change.',font=label,fill='white')
        d.text((14,90),'Four fringe cells change, 209 to 91. The 245 cores and all other cells stay identical.',font=label,fill='white')
        for column,mode in enumerate(MODES):
            x0=120+column*714;y0=220;step=42;data=masks[mode][ngid]
            d.text((x0-10,125),TITLES[column],font=heading,fill='white')
            native=Image.frombytes('L',(8,8),data).convert('RGB')
            if not dark:native=ImageOps.invert(native)
            page.paste(native,(x0,166));crops.append((x0,166,native))
            for x in range(8):d.text((x0+x*step+step/2,y0-22),str(x+1),font=number,fill='white',anchor='mt')
            for y in range(8):
                d.text((x0-15,y0+y*step+12),str(y+1),font=number,fill='white',anchor='rt')
                for x in range(8):
                    i=y*8+x;v=data[i];display=v if dark else 255-v;xx=x0+x*step;yy=y0+y*step
                    d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(display,)*3,
                                outline=(255,150,30) if v!=masks['previous'][ngid][i] else (70,70,70))
                    d.text((xx+step/2,yy+12),str(v),font=number,fill='black' if display>=140 else 'white',anchor='mt')
                    cells.append((xx+step-3,yy+step-3,display))
            d.text((x0-10,577),f'Coverage sum: {sum(data)}',font=label,fill='white')
        d.text((14,615),'Orange marks changes from the previous core trial. The source outline and bitmap bounds remain fixed.',font=label,fill='white')
        save(page,f"{len(images):02}_Noto-Sans_Regular_11pt_n_grid_{'dark' if dark else 'light'}.png",crops,cells)
    affected_pages=[];oracle=Oracle(args.stock_library.resolve())
    try:
        for entry in audit:
            if not entry['changed_glyphs']:continue
            source=next(c for c in full['conditions'] if c['id']==entry['id'])
            capture_path=ROOT/'build/stem-core-study/native'/(source['id']+'.json')
            assert sha(capture_path)==source['capture_sha256']
            affected_case=json.loads(capture_path.read_text());affected_glyphs={}
            affected_masks=dict(previous={},winner=audited_masks[source['id']])
            assert len(affected_case['glyphs'])==95 and len(affected_case['rows'])==7
            for g in affected_case['glyphs']:
                saved=next(x for x in source['glyphs'] if x['glyph']==g['glyph']);raster=g['rendered'][0]
                assert g['rendered'][1]==raster
                assert {k:raster[k] for k in saved['raw']}==saved['raw']
                assert hashlib.sha256(json.dumps(g['loaded'],sort_keys=True).encode()).hexdigest()==saved['loaded_sha256']
                assert oracle.raster(g['loaded'])==saved['raw']
                affected_glyphs[g['glyph']]=dict(loaded=g['loaded'],raster=raster)
                affected_masks['previous'][g['glyph']]=bytes.fromhex(saved['masks']['native-area'])
            changed={gid for gid,data in affected_masks['previous'].items() if data!=affected_masks['winner'][gid]}
            assert changed=={g['glyph'] for g in entry['changed_glyphs']}
            for g in entry['changed_glyphs']:
                assert hashlib.sha256(affected_masks['winner'][g['glyph']]).hexdigest()==g['winner_sha256']
            page=Image.new('RGB',(1440,800),(24,24,24));d=ImageDraw.Draw(page);crops=[];font=entry['font']
            d.text((14,12),f"{font['family']} / {font['style']} / {entry['point_size']}pt | affected-stem comparison",font=heading,fill='white')
            d.text((14,44),'96 DPI / 100%. Right: the same strong-winner correction applied to all eligible glyphs.',font=label,fill='white')
            characters=' '.join(chr(g['codepoint']) for g in entry['changed_glyphs'])
            d.text((14,66),f'Additional changed glyphs ({len(changed)}): {characters}',font=label,fill='white')
            for column,mode in enumerate(MODES):
                x=6+column*714;d.text((x+16,98),TITLES[column],font=heading,fill='white')
                for palette,dark in enumerate((True,False)):
                    top=130+palette*325;d.rectangle((x,top,x+699,top+309),fill='black' if dark else 'white')
                    d.text((x+16,top+3),'White on black' if dark else 'Black on white',font=label,fill='white' if dark else 'black')
                    for number_,row in enumerate(affected_case['rows']):
                        alpha=compose(row,affected_glyphs,affected_masks[mode],0);rgb=alpha.convert('RGB')
                        if not dark:rgb=ImageOps.invert(rgb)
                        assert rgb.size==(470,40)
                        y=top+28+number_*40;page.paste(rgb,(x+16,y));crops.append((x+16,y,rgb))
            name=f"{len(images):02}_{slug(font['family'])}_{slug(font['style'])}_{entry['point_size']}pt_affected.png"
            save(page,name,crops);affected_pages.append(dict(id=entry['id'],file=name,capture_sha256=sha(capture_path)))
    finally:
        oracle.close()
    assert {p['id'] for p in affected_pages}=={c['id'] for c in audit if c['changed_glyphs']}
    assert len(images)==3+len(affected_pages) and {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
    metrics={m:dict(total=sum(masks[m][ngid]),pairs=[dict(row=i//8+1,core=masks[m][ngid][i],fringe=masks[m][ngid][i+1],
               total=sum(masks[m][ngid][i:i+2]),relative_centroid=masks[m][ngid][i+1]/sum(masks[m][ngid][i:i+2])) for i in (32,40,48,56)]) for m in MODES}
    assert all(metrics['winner']['pairs'][i]['relative_centroid']<metrics['previous']['pairs'][i]['relative_centroid'] for i in range(4))
    result=dict(producer='fontreal-noto-stem-winner',checker_sha256=sha(Path(__file__)),source_manifest_sha256=sha(PARENT),
        full_source_manifest_sha256=sha(full_path),native_capture_sha256=sha(capture),helpers=parent['sources'],font=selected['font'],
        fixtures={name:sha(ROOT/'docs/images/browser-common-ground'/name) for name in
                  ('noto-coverage-captures.json','inconsolata-u-captures.json')},
        logical_dpi=96,scale=1,point_size=11,native_size=selected['native_size'],library_sha256=sha(args.stock_library),
        label_font=dict(file=args.label_font.name,sha256=sha(args.label_font)),raw={k:r[k] for k in ('width','height','left','top','mask')},
        masks={m:masks[m][ngid].hex() for m in MODES},pairs=pairs,metrics=metrics,
        context_masks=[dict(glyph=gid,masks_sha256={m:hashlib.sha256(masks[m][gid]).hexdigest() for m in MODES}) for gid in sorted(glyphs)],
        audit=audit,affected_pages=affected_pages,images=images,limits=['Only n changes on the focused page; additional pages apply the correction to every affected glyph',
        'The numerical audit and samples do not establish optical acceptance; no installed profile change',
        'This extends the existing weak-native straight-run selector; already strong native profiles remain outside that selector',
        'Pair conservation does not preserve the coverage centroid or apparent geometry'])
    manifest.write_text(json.dumps(result,indent=2)+'\n')
    print(f"PASS 4 n donor changes / u identity / source rasters and two compositors / 108-condition audit ({sum(len(c['changed_glyphs']) for c in audit)} affected glyph conditions) / {len(images)} pages")
    print(OUT)


if __name__=='__main__':
    main()
