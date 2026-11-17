#!/usr/bin/env python3
"""Separate native hinting evidence from retained local phase-coherence trials."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from PIL import Image,ImageDraw,ImageFont
import pixel_references as base
import pixel_reference_smoothing as smooth
import supersampling as shared

ROOT=shared.ROOT
FOCUS='() O O i8! W'
RAW=(('native_mono','Native MONO'),('native_normal','Native NORMAL'),('auto_mono','Auto MONO'),('off_mono','Unhinted MONO'))
TRIALS=(('A','Native raw'),('O','Profile O'),('L','Local cores'),('U','L + half edges'),('K3','3x3 coherence'),('K5','5x5 coherence'))
NEW_SOURCES=('tests/arial_hinting_probe.cpp','tools/arial_coherence.py','tests/arial_coherence_test.py')


def load_retained(path,expected_sha):
    if shared.sha(path)!=expected_sha:raise ValueError('retained source hash differs')
    return json.loads(path.read_text())


def local_coherence(d,l,s,phase_sums,axes,primary,components,width):
    sums={tuple(p['phase']):p['values'] for p in phase_sums}
    membership={i:component['indices'] for component in components for i in component['indices']}
    half=[(b-a+1)//2 for a,b in zip(l,s)];outputs={};audits={}
    for name,radius in (('K3',1),('K5',2)):
        values=list(d);decisions=[]
        for i in primary:
            neighbors=sorted(j for j in membership[i] if abs(j%width-i%width)<=radius and abs(j//width-i//width)<=radius)
            axis=axes[str(i)]['axis'];allowed=[p for p in sums if (axis!='x' or p[1]==0) and (axis!='y' or p[0]==0)]
            scores={p:sum(sums[p][j]**2 for j in neighbors) for p in allowed}
            chosen=min(allowed,key=lambda p:(-scores[p],p[0]*p[0]+p[1]*p[1],p[1],p[0]));reference=(sums[chosen][i]+8)//16
            values[i]=max(d[i],reference)
            decisions.append(dict(index=i,neighbors=neighbors,axis=axis,phase=list(chosen),score=scores[chosen],scores=[[*p,scores[p]] for p in sorted(allowed)],reference=reference,core=values[i]))
        outputs[name]=[a+b for a,b in zip(values,half)];audits[name]=decisions
    return outputs,audits


def common_frame(masks,pad=2):
    nonempty=[m for m in masks if m['pixels']]
    left=min((m['left'] for m in nonempty),default=0)-pad;top=min((m['top'] for m in nonempty),default=0)-pad
    right=max((m['left']+m['width'] for m in nonempty),default=0)+pad;bottom=max((m['top']+m['height'] for m in nonempty),default=0)+pad
    return dict(left=left,top=top,width=right-left,height=bottom-top)


def focus_places(records):
    advances={r['code']:r['advance_pixels'] for r in records};result=[];x=0
    for c in FOCUS:result.append(dict(code=ord(c),x=x,line=0));x+=advances[ord(c)]
    return result


def panels(output,records,methods,places,lines,points,width,font,prefix,title,subtitle):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9);focus=focus_places(records);crops=[];sheets=[];step=width+28
    for key,caption in methods:
        glyphs={r['code']:{'final':{**r['frame'],'pixels':r['masks'][key]}} for r in records}
        for kind,placements,nlines in (('body',places,lines),('focus',focus,1)):
            mask=shared.compose(glyphs,placements,nlines,points,width)
            for polarity in ('light','dark'):
                image=Image.eval(mask,lambda v:255-v) if polarity=='light' else mask
                name=f'crops/{prefix}_{key}_{kind}_{polarity}.png';image.save(output/name);crops.append(dict(method=key,kind=kind,polarity=polarity,file=name,sha256=shared.sha(output/name),size=list(image.size)))
    for polarity in ('light','dark'):
        bg,fg=(255,0) if polarity=='light' else (0,255);fh=next(c['size'][1] for c in crops if c['kind']=='focus');bh=next(c['size'][1] for c in crops if c['kind']=='body');body_y=138+fh
        image=Image.new('L',(step*len(methods)+20,body_y+bh+12),bg);draw=ImageDraw.Draw(image);draw.text((12,10),title,font=label,fill=fg);draw.text((12,32),subtitle,font=label,fill=fg);draw.text((12,86),'Native focus: '+FOCUS,font=small,fill=fg);draw.text((12,body_y-16),'Full source specimen',font=small,fill=fg);draw.line((12,110+fh,image.width-12,110+fh),fill=fg)
        headings=[];boxes=[]
        for col,(key,caption) in enumerate(methods):
            x=12+col*step;draw.text((x,64),caption,font=label,fill=fg);headings.append(dict(text=caption,position=[x,64]));entry=dict(method=key)
            for kind,y in (('focus',104),('body',body_y)):
                meta=next(c for c in crops if c['method']==key and c['kind']==kind and c['polarity']==polarity);patch=Image.open(output/meta['file']);image.paste(patch,(x,y));entry[kind]=dict(file=meta['file'],box=[x,y,x+patch.width,y+patch.height])
            boxes.append(entry)
        name=f'gallery/{prefix}_{polarity}.png';image.save(output/name);sheets.append(dict(file=name,sha256=shared.sha(output/name),size=list(image.size),title=title,subtitle=subtitle,polarity=polarity,headings=headings,crops=boxes,body_y=body_y,divider_y=110+fh))
    return dict(crops=crops,sheets=sheets,focus_placements=focus)


def geometry(output,oracle,glyphs,code,font,prefix,title):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),10);scaled={key:base.numerical.raster(oracle,base.numerical.snapshot(g),8) for key,g in glyphs.items()};frame=common_frame(scaled.values(),8)
    references=glyphs['off_mono']['outline'];topology=glyphs['off_mono'];metrics={}
    for key,g in glyphs.items():
        comparable=len(g['outline'])==len(references) and [t&3 for t in g['tags']]==[t&3 for t in topology['tags']] and g['contours']==topology['contours']
        diffs=[[x-a,y-b] for (x,y),(a,b) in zip(g['outline'],references)] if comparable else []
        xs=[p[0] for p in g['outline']];ys=[p[1] for p in g['outline']]
        metrics[key]=dict(comparable=comparable,point_deltas=diffs,max_abs_x=max((abs(p[0]) for p in diffs),default=0) if comparable else None,max_abs_y=max((abs(p[1]) for p in diffs),default=0) if comparable else None,bbox=[min(xs),min(ys),max(xs),max(ys)],bitmap={k:g[k] for k in ('left','top','advance')},bitmap_size=[g['bitmap']['width'],g['bitmap']['rows']])
    column=max(280,frame['width']+24);size=(column*4+20,frame['height']+174);image=Image.new('RGB',size,(24,24,24));draw=ImageDraw.Draw(image);draw.text((12,10),title,font=label,fill='white');subtitle='NON-NATIVE geometry: captured outline coordinates x8. Not a resized bitmap or larger-DPI hinting.';draw.text((12,32),subtitle,font=small,fill='white');boxes=[]
    for col,(key,caption) in enumerate(RAW):
        x=12+col*column;draw.text((x,58),caption,font=label,fill='white');draw.text((x,82),f'vs unhinted: dx {metrics[key]["max_abs_x"]}/64, dy {metrics[key]["max_abs_y"]}/64',font=small,fill='white')
        patch=Image.frombytes('L',(frame['width'],frame['height']),bytes(base.numerical.place(scaled[key],frame)['pixels'])).convert('RGB');image.paste(patch,(x,112));baseline=112-frame['top'];draw.line((x,baseline,x+frame['width']-1,baseline),fill=(100,70,30));boxes.append(dict(method=key,box=[x,112,x+patch.width,112+patch.height],baseline_y=baseline))
    name=f'gallery/{prefix}_glyph-{code}.png';image.save(output/name)
    return dict(file=name,sha256=shared.sha(output/name),size=list(size),title=title,subtitle=subtitle,code=code,scale=8,frame=frame,rasters=scaled,metrics=metrics,boxes=boxes)


def phase_grid(output,record,source,font,prefix,title):
    label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9);w,h=record['frame']['width'],record['frame']['height'];column=max(242,w*20+40);methods=('D','O','L','U','K3','K5');positive=[i for i,v in enumerate(source['masks']['D']) if v];phase_y=h*20+130
    image=Image.new('RGB',(column*6+20,phase_y+36+len(positive)*13),(24,24,24));draw=ImageDraw.Draw(image);draw.text((12,10),title,font=label,fill='white');draw.text((12,32),'Profile O differs from glyph O. Phase rows: row,col | C | E | K3 | K5 (quarter-pixel shifts).',font=small,fill='white');cells=[];previews=[];rows=[]
    for col,key in enumerate(methods):
        x=12+col*column;draw.text((x,58),key,font=label,fill='white');v=record['masks'][key];image.paste(Image.frombytes('L',(w,h),bytes(v)).convert('RGB'),(x+36,58));previews.append(dict(method=key,box=[x+36,58,x+36+w,58+h]))
        for xx in range(w):draw.text((x+30+xx*20,82),str(xx+1),font=small,fill='white')
        for yy in range(h):draw.text((x,104+yy*20),str(yy+1),font=small,fill='white')
        for i,value in enumerate(v):
            left=x+26+(i%w)*20;top=100+(i//w)*20;draw.rectangle((left,top,left+19,top+19),fill=(value,)*3,outline=(75,75,75));draw.text((left+1,top+4),str(value),font=small,fill='black' if value>=145 else 'white');cells.append(dict(method=key,index=i,row=i//w+1,column=i%w+1,value=value,box=[left,top,left+20,top+20]))
    membership={i:c['phase'] for c in source['reference']['components'] for i in c['indices']};choices={k:{d['index']:d for d in record['audit'][k]} for k in ('K3','K5')}
    for row,i in enumerate(positive):
        info=dict(index=i,row=i//w+1,column=i%w+1,C=membership[i],E=source['reference']['axes'][str(i)]['phase'],K3=choices['K3'].get(i),K5=choices['K5'].get(i))
        text=f'{info["row"]},{info["column"]} | C {info["C"]} | E {info["E"]} | K3 {info["K3"]["phase"] if info["K3"] else "-"} | K5 {info["K5"]["phase"] if info["K5"] else "-"}'
        draw.text((12,phase_y+row*13),text,font=small,fill='white');rows.append(dict(**info,text=text,position=[12,phase_y+row*13]))
    name=f'diagnostics/{prefix}_glyph-{record["code"]}.png';image.save(output/name)
    return dict(file=name,sha256=shared.sha(output/name),size=list(image.size),title=title,code=record['code'],cells=cells,previews=previews,rows=rows)


def export(record_path,source_path,output):
    source=json.loads(source_path.read_text());source_root=source_path.parent
    if [(c['font'],c['points']) for c in source['cases']]!=[(f,p) for f in range(5) for p in (8,10,11,12)]:raise ValueError('approved complete matrix required')
    for path,sha in source['sources'].items():
        if shared.sha(ROOT/path)!=sha:raise ValueError('retained source producer changed')
    provider,env=base.prepare(record_path)
    if shared.sha(provider)!=source['provider']['sha256']:raise ValueError('paired FreeType provider differs from retained matrix')
    fonts=[base.match_font(f['family']) for f in source['fonts']]
    for (_,meta),expected in zip(fonts,source['fonts']):
        if meta!=expected:raise ValueError('retained font changed')
    build=ROOT/'build/arial-coherence';build.mkdir(parents=True,exist_ok=True);probe=build/'arial-hinting-probe';flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','freetype2'],text=True));subprocess.run(['c++','-std=c++17','-O2','-fPIC',str(ROOT/'tests/arial_hinting_probe.cpp'),'-o',str(probe),*flags,'-ldl'],check=True)
    output.mkdir(parents=True,exist_ok=False)
    for name in ('gallery','crops','captures','raw','masks','diagnostics'):(output/name).mkdir()
    manifest=dict(study='arial-coherence',base_git='bb54852def911ee26a0a1178c64ce5453101ffa3',source_manifest=os.path.relpath(source_path,output.resolve()),source_manifest_sha256=shared.sha(source_path),sources={p:shared.sha(ROOT/p) for p in (*smooth.SOURCES,*NEW_SOURCES)},provider=dict(file=provider.name,sha256=shared.sha(provider)),record_sha256=shared.sha(record_path),focus=FOCUS,fonts=source['fonts'],raw_methods=list(RAW),trial_methods=list(TRIALS),specimen=source['specimen'],source_cases=[],cases=[])
    oracle=base.Oracle(provider)
    try:
        for order,ci in enumerate((1,2,13,14)):
            oldcase=source['cases'][ci];fi,points=oldcase['font'],oldcase['points'];font=fonts[fi][0];family=source['fonts'][fi]['family'];cap=json.loads(subprocess.check_output([str(probe),str(font),str(points)],env=env))
            if Path(cap['provider']).resolve()!=provider:raise ValueError('focused probe loaded different provider')
            capname=f'captures/{fi}_{points}.json';shared.write_json(output/capname,cap);retained=load_retained(source_root/oldcase['masks']['file'],oldcase['masks']['sha256']);records=[]
            captures={c['mode']:c for c in cap['captures']}
            for idx,old in enumerate(retained):
                masks={key:shared.decode_bitmap(captures[key]['glyphs'][idx]) for key,title in RAW};frame=common_frame(masks.values());records.append(dict(code=old['code'],advance_pixels=old['advance_pixels'],actual_advances={key:captures[key]['glyphs'][idx]['advance'] for key,title in RAW},frame=frame,masks={key:base.numerical.place(m,frame)['pixels'] for key,m in masks.items()}))
            rawname=f'raw/{fi}_{points}.json';shared.write_json(output/rawname,records)
            title=f'{family} Regular | {points}pt | native grayscale SOURCE policies | darkening off'
            panels_meta=panels(output,records,RAW,oldcase['placements'],oldcase['lines'],points,320,font,f'01_source_{order+1}',title,'Same retained MONO advances/baseline. Actual advances recorded separately. No coverage profiles applied.')
            geoms=[]
            for code in map(ord,'O()'):
                glyphs={key:next(g for g in captures[key]['glyphs'] if g['code']==code) for key,title in RAW};geoms.append(geometry(output,oracle,glyphs,code,font,f'02_geometry_{order+1}',f'{family} Regular {points}pt | glyph {chr(code)} | fixed-outline geometry'))
            manifest['source_cases'].append(dict(source_case=ci,font=fi,points=points,capture=dict(file=capname,sha256=shared.sha(output/capname)),records=dict(file=rawname,sha256=shared.sha(output/rawname)),placements=oldcase['placements'],lines=oldcase['lines'],geometry=geoms,**panels_meta))
    finally:oracle.close()
    for ci,case in enumerate(source['cases']):
        fi,points=case['font'],case['points'];font=fonts[fi][0];family=source['fonts'][fi]['family'];retained=load_retained(source_root/case['masks']['file'],case['masks']['sha256']);records=[]
        for old in retained:
            extra,audit=local_coherence(old['masks']['D'],old['masks']['L'],old['masks']['S'],old['reference']['phase_sums'],old['reference']['axes'],old['overlay']['primary'],old['reference']['components'],old['frame']['width'])
            u=[l+(s-l+1)//2 for l,s in zip(old['masks']['L'],old['masks']['S'])];records.append(dict(code=old['code'],frame=old['frame'],advance_pixels=old['advance_pixels'],source_record_sha256=smooth.canonical(old),masks={**{k:old['masks'][k] for k in 'ADOL'},'U':u,**extra},audit=audit))
        name=f'masks/{fi}_{points}.json';shared.write_json(output/name,records);native=panels(output,records,TRIALS,case['placements'],case['lines'],points,240,font,f'03_trial_{fi+1}_{points}',f'{family} Regular | {points}pt | retained local phase-coherence trials','Profile O is the Arial control. U tentative. K3/K5 can reduce L cores; no optical winner selected.')
        diagnostics=[]
        if fi==3 and points in (10,11):
            for code in map(ord,'()O'):
                r=next(r for r in records if r['code']==code);old=next(r for r in retained if r['code']==code);diagnostics.append(phase_grid(output,r,old,font,f'{fi}_{points}',f'{family} Regular {points}pt | glyph {chr(code)} | component/local phase choices'))
        manifest['cases'].append(dict(source_case=ci,font=fi,points=points,source_masks=case['masks'],masks=dict(file=name,sha256=shared.sha(output/name)),placements=case['placements'],lines=case['lines'],diagnostics=diagnostics,**native))
    shared.write_json(output/'manifest.json',manifest);return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--record',required=True,type=Path);parser.add_argument('--source-manifest',required=True,type=Path);args=parser.parse_args();output=ROOT/'results/arial-coherence'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');print(export(args.record.resolve(strict=True),args.source_manifest.resolve(strict=True),output))


if __name__=='__main__':main()
