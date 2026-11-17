#!/usr/bin/env python3
"""Compare two fixed fractions of retained S edge proposals without native work."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from PIL import Image,ImageDraw,ImageFont
import pixel_references as base
import supersampling as shared

ROOT=shared.ROOT
METHODS=(('A','Native raw'),('D','Accepted baseline'),('O','Coherent weak cores'),
         ('L','Local weak cores'),('T','L + quarter edge'),('U','L + half edge'))
FOCUS='() () i8! W'
SOURCES=(*base.SOURCES,'tools/pixel_reference_smoothing.py','tests/pixel_reference_smoothing_test.py')


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def trials(l,s):
    if len(l)!=len(s) or any(type(a) is not int or type(b) is not int or not 0<=a<=b<=255 for a,b in zip(l,s)):
        raise ValueError('retained L/S must be equal-length monotone byte arrays')
    return dict(T=[a+(b-a+2)//4 for a,b in zip(l,s)],U=[a+(b-a+1)//2 for a,b in zip(l,s)])


def read_hashed(root,meta):
    path=root/meta['file']
    if shared.sha(path)!=meta['sha256']:raise ValueError('retained source hash differs: '+meta['file'])
    return json.loads(path.read_text())


def focus_layout(records):
    advances={r['code']:r['advance_pixels'] for r in records};places=[];x=0
    for char in FOCUS:
        places.append(dict(code=ord(char),x=x,line=0));x+=advances[ord(char)]
    return places


def grid(output,name,record,family,points,label,small):
    frame=record['frame'];w,h=frame['width'],frame['height'];cell=20;column=max(280,w*cell+40)
    image=Image.new('RGB',(column*4+20,h*cell+146),(24,24,24));draw=ImageDraw.Draw(image)
    title=f'{family} Regular / {points}pt / {chr(record["code"])} / fractional S edges'
    subtitle='Coverage: 0 = no ink, 255 = full ink. Orange marks T/U fringe additions to L. Native previews are not resized.'
    draw.text((12,10),title,font=label,fill='white');draw.text((12,32),subtitle,font=small,fill='white')
    cells=[];previews=[];headings=[]
    for col,key in enumerate(('O','L','T','U')):
        x=12+col*column;values=record['masks'][key];draw.text((x,58),key,font=label,fill='white');headings.append(dict(text=key,position=[x,58]))
        patch=Image.frombytes('L',(w,h),bytes(values)).convert('RGB');image.paste(patch,(x+38,58));previews.append(dict(method=key,box=[x+38,58,x+38+w,58+h]))
        for xx in range(w):draw.text((x+30+xx*cell,90),str(xx+1),font=small,fill='white')
        for yy in range(h):
            draw.text((x,110+yy*cell),str(yy+1),font=small,fill='white')
            for xx in range(w):
                i=yy*w+xx;v=values[i];left=x+26+xx*cell;top=108+yy*cell;l=record['masks']['L'][i]
                border=(240,150,70) if key in ('T','U') and v>l else (75,75,75)
                draw.rectangle((left,top,left+cell-1,top+cell-1),fill=(v,)*3,outline=border);draw.text((left+1,top+4),str(v),font=small,fill='black' if v>=145 else 'white')
                cells.append(dict(method=key,index=i,row=yy+1,column=xx+1,value=v,source_L=l,source_S=l+record['edge_increments'][i],box=[left,top,left+cell,top+cell],border=list(border),text_position=[left+1,top+4]))
    image.save(output/name)
    return dict(file=name,sha256=shared.sha(output/name),size=list(image.size),code=record['code'],title=title,subtitle=subtitle,headings=headings,cells=cells,previews=previews,cell_size=cell)


def export(source_manifest,output):
    source=json.loads(source_manifest.read_text());source_root=source_manifest.parent
    expected=[(fi,p) for fi in range(5) for p in (8,10,11,12)]
    if source['study']!='pixel-references-matrix' or [(c['font'],c['points']) for c in source['cases']]!=expected:
        raise ValueError('complete approved five-font Regular matrix required')
    if [f['family'] for f in source['fonts']]!=list(base.native_stems.FONTS):raise ValueError('approved matrix families differ')
    for path,sha in source['sources'].items():
        if shared.sha(ROOT/path)!=sha:raise ValueError('retained producer differs: '+path)
    fonts=[]
    for meta in source['fonts']:
        font,actual=base.match_font(meta['family'])
        if actual!=meta:raise ValueError('retained label font differs from source')
        fonts.append(font)
    output.mkdir(parents=True,exist_ok=False)
    for name in ('gallery','crops','masks','diagnostics'):(output/name).mkdir()
    manifest=dict(study='pixel-reference-smoothing',base_git='8caba95bc396957394b63e5040963d822ccde008',
                  source_manifest=os.path.relpath(source_manifest,output.resolve()),source_manifest_sha256=shared.sha(source_manifest),
                  source_contributors=source['sources'],sources={p:shared.sha(ROOT/p) for p in SOURCES},
                  methods=list(METHODS),focus=FOCUS,fonts=source['fonts'],target_dpi=96,blend='encoded',
                  specimen=source['specimen'],placement=source['placement'],cases=[])
    for ci,case in enumerate(source['cases']):
        fi,points=case['font'],case['points'];font=fonts[fi];family=source['fonts'][fi]['family'];label=ImageFont.truetype(str(font),14);small=ImageFont.truetype(str(font),9)
        read_hashed(source_root,case['capture']);inputs=read_hashed(source_root,case['inputs']);retained=read_hashed(source_root,case['masks'])
        if [r['code'] for r in retained]!=list(range(32,127)) or [r['code'] for r in inputs]!=list(range(32,127)):raise ValueError('complete retained ASCII records required')
        records=[]
        for r in retained:
            l,s=r['masks']['L'],r['masks']['S'];new=trials(l,s)
            records.append(dict(code=r['code'],advance_pixels=r['advance_pixels'],frame=r['frame'],source_record_sha256=canonical(r),
                                edge_increments=[b-a for a,b in zip(l,s)],masks={**{k:r['masks'][k] for k in 'ADOL'},**new}))
        name=f'masks/{fi}_{points}.json';shared.write_json(output/name,records)
        places,lines,bodies,old_sheets=base.images(output,inputs,records,font,family,points,METHODS,prefix=f'{fi+1:02}_{points}_',matrix=True)
        if places!=case['placements'] or lines!=case['lines']:raise ValueError('retained body layout differs')
        for crop in bodies:
            if crop['method'] in 'ADOL':
                control=next(c for c in case['crops'] if c['method']==crop['method'] and c['polarity']==crop['polarity'])
                if shared.sha(source_root/control['file'])!=control['sha256'] or crop['sha256']!=control['sha256']:raise ValueError('native body control differs')
        focus_places=focus_layout(records);focus_crops=[];sheets=[]
        for polarity in ('light','dark'):
            bg,fg=(255,0) if polarity=='light' else (0,255);focus_images={}
            for key,title in METHODS:
                patch=shared.compose({r['code']:{'final':{**r['frame'],'pixels':r['masks'][key]}} for r in records},focus_places,1,points)
                if polarity=='light':patch=Image.eval(patch,lambda v:255-v)
                fn=f'crops/{fi+1:02}_{points}_{key}_{polarity}_focus.png';patch.save(output/fn);focus_images[key]=patch;focus_crops.append(dict(method=key,polarity=polarity,file=fn,sha256=shared.sha(output/fn),size=list(patch.size)))
            focus_height=focus_images['A'].height;body_y=138+focus_height;body_height=next(c['size'][1] for c in bodies if c['method']=='A')
            image=Image.new('L',(1628,body_y+body_height+12),bg);draw=ImageDraw.Draw(image)
            title=f'{family} Regular | {points}pt | 96 DPI | retained L cores and fractional S edges'
            subtitle='O preferred general control. T/U add quarter/half of S-L to L. Extra edge ink can still add weight. View at 100%.'
            draw.text((12,10),title,font=label,fill=fg);draw.text((12,32),subtitle,font=label,fill=fg);draw.text((12,86),'Native focus: '+FOCUS,font=small,fill=fg);draw.text((12,body_y-16),'Full source specimen',font=small,fill=fg)
            headings=[];boxes=[]
            for col,(key,caption) in enumerate(METHODS):
                x=12+col*268;draw.text((x,64),f'{key}: {caption}',font=label,fill=fg);headings.append(dict(text=f'{key}: {caption}',position=[x,64]))
                focus=focus_images[key];image.paste(focus,(x,104))
                body=next(c for c in bodies if c['method']==key and c['polarity']==polarity);patch=Image.open(output/body['file']);image.paste(patch,(x,body_y))
                focus_meta=next(c for c in focus_crops if c['method']==key and c['polarity']==polarity)
                boxes.append(dict(method=key,focus=dict(file=focus_meta['file'],box=[x,104,x+focus.width,104+focus.height]),body=dict(file=body['file'],box=[x,body_y,x+patch.width,body_y+patch.height])))
            draw.line((12,110+focus_height,1616,110+focus_height),fill=fg)
            sheet_name=next(s['file'] for s in old_sheets if s['polarity']==polarity);image.save(output/sheet_name)
            sheets.append(dict(file=sheet_name,sha256=shared.sha(output/sheet_name),size=list(image.size),polarity=polarity,title=title,subtitle=subtitle,headings=headings,crops=boxes,body_y=body_y,divider_y=110+focus_height))
        grids=[]
        for code in map(ord,'()'):
            r=next(r for r in records if r['code']==code);grids.append(grid(output,f'diagnostics/{fi+1:02}_{points}_{code}.png',r,family,points,label,small))
        manifest['cases'].append(dict(source_case=ci,font=fi,points=points,source_capture=case['capture'],source_inputs=case['inputs'],source_masks=case['masks'],
                                      masks=dict(file=name,sha256=shared.sha(output/name)),placements=places,lines=lines,focus_placements=focus_places,crops=bodies,focus_crops=focus_crops,sheets=sheets,grids=grids))
    shared.write_json(output/'manifest.json',manifest)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-manifest',required=True,type=Path);args=parser.parse_args()
    output=ROOT/'results/pixel-reference-smoothing'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    print(export(args.source_manifest.resolve(strict=True),output))


if __name__=='__main__':main()
