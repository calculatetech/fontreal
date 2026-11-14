#!/usr/bin/env python3
"""Separate Hack 11pt 8 hinting from annotated partial-coverage trials."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps
from bridge_font_matrix_test import sha
from bridge_coverage_test import transform
from browser_stroke_axis_test import Oracle
from neighbor_coverage_test import repeat

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'build/hack-eight'
OUT = ROOT/'results/hack-eight/gallery'
ANNOTATED = ((0,2),(0,5),(1,1),(1,2),(1,5),(1,6),(4,1),(4,2),(4,5),(4,6))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('font','stock-library','label-font'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    matrix_path=ROOT/'results/bridge-font-matrix/gallery/manifest.json'
    matrix=json.loads(matrix_path.read_text())
    for key,name in [('filter_sha256','bridge_coverage_test.py'),('average_sha256','neighbor_coverage_test.py')]:
        assert matrix[key]==sha(ROOT/'tests'/name)
    font=next(f for f in matrix['faces'] if f['family']=='Hack' and f['style']=='Regular')
    assert sha(args.font)==font['font_sha256'] and sha(args.stock_library)==matrix['stock_library_sha256']
    source_path=ROOT/'build/bridge-font-matrix/native'/f"{font['id']}-11.json"
    condition=next(c for c in matrix['conditions'] if c['id']==f"{font['id']}-11")
    assert sha(source_path)==condition['native_capture_sha256']
    source=json.loads(source_path.read_text()); assert source['point_size']==11 and source['native_size']==15
    glyph=next(g for g in source['glyphs'] if g['glyph']==source['character_map']['56'])
    raw=glyph['raster']; original=bytes.fromhex(raw['mask'])
    assert (raw['width'],raw['height'])==(7,12)
    current=transform(original,7)[0]['bridge']
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    probe=WORK/'probe'
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','freetype2'],text=True))
    subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/freetype_mask_probe.cpp'),*flags,'-o',str(probe)],check=True)
    env={k:v for k,v in os.environ.items() if not k.startswith('FONTREAL_') and k not in
         ('LD_LIBRARY_PATH','LD_PRELOAD','FREETYPE_PROPERTIES','FT2_DEBUG')}
    env['LD_LIBRARY_PATH']=str(args.stock_library.resolve().parent)
    modes=[]; native_cases={}; oracle=Oracle(args.stock_library.resolve())
    try:
        for name,title,load in [('unhinted','Unhinted source',10),('native','Font-native normal',8),
                                ('auto-normal','Stock auto normal',40),('auto-mono','Stock auto mono',131112)]:
            target=WORK/(name+'.json')
            subprocess.run([str(probe.resolve()),str(args.font.resolve()),'15',str(load),'56','0','0','0','2',str(target.resolve()),'none','0'],env=env,check=True)
            case=json.loads(target.read_text()); raster=case['rendered'][0]
            assert case['family']=='Hack' and case['style']=='Regular' and case['glyph']==glyph['glyph']
            assert all(r==raster for r in case['rendered'])
            assert oracle.raster(case['loaded'])=={k:raster[k] for k in ('width','height','left','top','mask')}
            native_cases[name]=dict(load_flags=load,capture=case,capture_sha256=sha(target))
            modes.append(dict(id=name,title=title,loaded=case['loaded'],raster=raster))
        stock=native_cases['auto-mono']['capture']
        assert stock['loaded']['outline']==glyph['loaded']['outline']
        assert stock['loaded']['contours']==glyph['loaded']['contours']
        assert all(stock['rendered'][0][k]==raw[k] for k in ('width','height','left','top','mask'))
        assert oracle.raster(glyph['loaded'])=={k:raw[k] for k in ('width','height','left','top','mask')}
        modes += [dict(id='selected-raw',title='Fontreal mono raw',loaded=glyph['loaded'],raster=raw),
                  dict(id='current',title='Current 170 + bridge',loaded=glyph['loaded'],raster=dict(raw,mask=current.hex()))]
        selected={y*7+x for y,x in ANNOTATED}
        assert len(selected)==10 and all(140<=original[i]<170 and current[i]==original[i] for i in selected)
        trials={}
        for name,title,numerator,denominator in [('local-5-4','Local coverage ×1.25',5,4),('local-11-8','Local coverage ×1.375',11,8),('full','Full-cell control',0,1)]:
            data=bytearray(current)
            for i in selected:
                data[i]=255 if name=='full' else (2*original[i]*numerator+denominator)//(2*denominator)
            data=bytes(data)
            assert {i for i,(a,b) in enumerate(zip(current,data,strict=True)) if a!=b}==selected
            assert all((a>0)==(b>0) for a,b in zip(current,data,strict=True))
            if name!='full':
                assert all(original[i]<data[i]<230 for i in selected)
                assert all((original[a]<=original[b])==(data[a]<=data[b]) for a in selected for b in selected)
            trials[name]=dict(id=name,title=title,loaded=glyph['loaded'],raster=dict(raw,mask=data.hex()))
        modes += [trials['local-5-4'],trials['local-11-8']]
        heading=ImageFont.truetype(str(args.label_font),21)
        label=ImageFont.truetype(str(args.label_font),14)
        tiny=ImageFont.truetype(str(args.label_font),10)
        images=[]

        def canvas(raster,factor=1):
            image=Image.new('L',(16*factor,20*factor))
            x,y=(3*factor+raster['left'],16*factor-raster['top'])
            w,h=raster['width'],raster['height']; data=bytes.fromhex(raster['mask'])
            assert len(data)==w*h and x>=0 and y>=0 and x+w<=image.width and y+h<=image.height
            image.paste(Image.frombytes('L',(w,h),data),(x,y))
            assert sum(image.tobytes())==sum(data)
            return image.convert('RGB')

        def save(image,name,crops,cells=()):
            path=OUT/name; image.save(path)
            with Image.open(path) as saved:
                for x,y,crop in crops:assert saved.crop((x,y,x+crop.width,y+crop.height)).tobytes()==crop.tobytes()
                for x,y,v in cells:assert saved.getpixel((x,y))==(v,)*3
            images.append(dict(file=name,sha256=sha(path)))

        previous=OUT/'manifest.json'
        if previous.exists():
            old=json.loads(previous.read_text()); assert old['producer']=='fontreal-hack-eight'
            for r in old['images']:
                p=OUT/r['file']; assert p.parent==OUT and sha(p)==r['sha256']; p.unlink()
        assert not list(OUT.glob('*.png'))
        overview=Image.new('RGB',(1440,820),(24,24,24)); draw=ImageDraw.Draw(overview); crops=[]
        draw.text((18,12),'Hack Regular / 11pt | hinting geometry and local coverage trials',font=heading,fill='white')
        draw.text((18,46),'Left in each panel: enlarged outline. Right: exact pixels ×10. Native repetitions below use both backgrounds.',font=label,fill='white')
        draw.text((18,69),'All origins and baselines match. Local trials change ten annotated cells only; they are not a general filter.',font=label,fill='white')
        for n,mode in enumerate(modes):
            x0=10+(n%4)*358; y0=105+(n//4)*350
            draw.text((x0,y0),mode['title'],font=heading,fill='white')
            enlarged=copy.deepcopy(mode['loaded'])
            for p in enlarged['outline']:p[0]*=10;p[1]*=10
            shape=canvas(oracle.raster(enlarged),10)
            pixel=repeat(canvas(mode['raster']),10)
            assert shape.size==pixel.size==(160,200)
            for x,img in [(x0,shape),(x0+176,pixel)]:
                overview.paste(img,(x,y0+32));crops.append((x,y0+32,img))
            # Use fixed advance and exact native masks so placement cannot hide the coverage change.
            sample=Image.new('L',(336,24));r=mode['raster'];mask=Image.frombytes('L',(r['width'],r['height']),bytes.fromhex(r['mask']))
            advance=round(glyph['loaded']['advance'][0]/64); assert advance>=r['width']
            for k in range(8):sample.paste(mask,(3+k*advance+r['left'],16-r['top']))
            assert sum(sample.tobytes())==8*sum(mask.tobytes())
            rgb=sample.convert('RGB')
            for y,img in [(y0+245,rgb),(y0+276,ImageOps.invert(rgb))]:
                overview.paste(img,(x0,y));crops.append((x0,y,img))
        save(overview,'00_Hack_11pt_shape-and-coverage.png',crops)
        grid=Image.new('RGB',(1440,760),(24,24,24));d=ImageDraw.Draw(grid); crops=[];cells=[]
        d.text((20,14),'Hack Regular 8 / 11pt | upper corners and waist: partial coverage versus full cells',font=heading,fill='white')
        d.text((20,48),'Each cell: current value above, preview value below. Orange marks the ten explicitly annotated cells.',font=label,fill='white')
        d.text((20,73),'These coordinates are a one-glyph visual experiment. No automatic connection detector or global floor is applied.',font=label,fill='white')
        for column,mode in enumerate([modes[5],trials['local-5-4'],trials['local-11-8'],trials['full']]):
            x0=30+column*358; y0=210; step=34;data=bytes.fromhex(mode['raster']['mask'])
            d.text((x0,116),mode['title'],font=heading,fill='white')
            native=canvas(mode['raster']);grid.paste(native,(x0,153));crops.append((x0,153,native))
            for x in range(7):d.text((x0+x*step+12,y0-20),str(x+1),font=tiny,fill='white')
            for y in range(12):
                d.text((x0-23,y0+y*step+12),str(y+1),font=tiny,fill='white')
                for x in range(7):
                    i=y*7+x;v=data[i];xx=x0+x*step;yy=y0+y*step
                    d.rectangle((xx,yy,xx+step-1,yy+step-1),fill=(v,)*3,outline=(255,150,30) if i in selected else (70,70,70))
                    fg='black' if v>=140 else 'white'
                    d.text((xx+step/2,yy+2),str(current[i]),font=tiny,fill=fg,anchor='mt')
                    d.text((xx+step/2,yy+17),str(v),font=tiny,fill=fg,anchor='mt');cells.append((xx+step-3,yy+step-3,v))
        save(grid,'01_Hack_11pt_numbered-local-trials.png',crops,cells)
        assert {p.name for p in OUT.glob('*.png')}=={r['file'] for r in images}
        portable=dict(producer='fontreal-hack-eight',point_size=11,native_size=15,logical_dpi=96,scale=1,
                      font=font,source_manifest_sha256=sha(matrix_path),source_case_sha256=sha(source_path),
                      checker_sha256=sha(Path(__file__)),probe_source_sha256=sha(ROOT/'tests/freetype_mask_probe.cpp'),
                      probe_binary_sha256=sha(probe),stock_library_sha256=sha(args.stock_library),
                      selected_library_sha256=matrix['library_sha256'],
                      filter_sha256=sha(ROOT/'tests/bridge_coverage_test.py'),average_sha256=sha(ROOT/'tests/neighbor_coverage_test.py'),
                      annotated_zero_based_yx=ANNOTATED,current=list(current),original=list(original),
                      native_cases=native_cases,modes=modes,full_cell_control=trials['full'],images=images,
                      stock_auto_mono_equals_selected_raw=True,
                      limits=['Local coordinates are diagnostic annotations, not a production rule',
                              'Outline enlargement is rerasterized geometry, not native-size pixel output',
                              'Raster bounds do not measure stroke width; other fonts and sizes remain unqualified'])
        previous.write_text(json.dumps(portable,indent=2)+'\n')
        print('PASS 4 native hinting controls, exact selected source, 10-cell partial trials, 2 complete figures')
        print(OUT)
    finally:
        oracle.close()


if __name__=='__main__':
    main()
