"""Experimental mask-only profiles; no font or character information is used."""
from collections import defaultdict
from math import floor
from statistics import median


def refine(raw,accepted,width,connected=False):
    assert isinstance(raw,bytes) and isinstance(accepted,bytes) and len(raw)==len(accepted)
    assert width>=0 and (not raw if width==0 else len(raw)%width==0)
    if not raw:return dict(profiles=accepted,corners=accepted),dict(runs=[],steps=[],corners=[])
    height=len(raw)//width
    def value(x,y):return raw[y*width+x] if 0<=x<width and 0<=y<height else 0
    def at(axis,a,b):return (a,b) if axis=='v' else (b,a)
    runs=[]
    for axis in ('v','h'):
        across,along=(width,height) if axis=='v' else (height,width)
        for a in range(across):
            for side in (-1,1):
                if not 0<=a+side<across:continue
                rows=[]
                for b in range(along):
                    x,y=at(axis,a,b);cx,cy=at(axis,a+side,b);ox,oy=at(axis,a-side,b);ix,iy=at(axis,a+2*side,b)
                    fringe=y*width+x;core=cy*width+cx
                    rows.append(dict(fringe=fringe,core=core,inner=value(ix,iy)) if
                                0<raw[fringe]<230 and raw[core]>0 and value(ox,oy)<=32 else None)
                windows=[]
                for start in range(along-1):
                    if rows[start] is None:continue
                    lo=hi=raw[rows[start]['fringe']];end=start+1
                    while end<along and rows[end] is not None:
                        v=raw[rows[end]['fringe']]
                        if max(hi,v)-min(lo,v)>16:break
                        lo=min(lo,v);hi=max(hi,v);end+=1
                    if end-start>=2:windows.append((start,end))
                windows=[(s,e) for s,e in windows if not any(ss<=s and ee>=e and (ss,ee)!=(s,e) for ss,ee in windows)]
                for start,end in windows:
                    if end-start==2 and not all(any(value(*at(axis,aa,bb))>=230 for aa in range(
                            a+side-1,a+side+2)) for bb in (start-1,end)):
                        continue
                    anchors=[]
                    for b in range(start,end):
                        r=rows[b];c,f=r['core'],r['fringe'];total=raw[c]+raw[f];peak=max(240,accepted[c])
                        if r['inner']==0 and 192<=total<=384 and 0<total-peak<=accepted[f]:
                            anchors.append((b,peak,total-peak))
                    if len(anchors)<2:continue
                    native=sum(raw[rows[b]['core']]-raw[rows[b]['fringe']] for b,_,_ in anchors)
                    chosen=sum(accepted[rows[b]['core']]-accepted[rows[b]['fringe']] for b,_,_ in anchors)
                    if connected and native==0 and chosen==0:continue
                    if (native,chosen,side)<(0,0,0):continue
                    phase=floor(median(v-raw[rows[b]['fringe']] for b,_,v in anchors)+.5)
                    fixed={b:(peak,v) for b,peak,v in anchors};proposals={};cores=set();pairs=[]
                    for b in range(start,end):
                        r=rows[b];c,f=r['core'],r['fringe'];peak=max(240,accepted[c]);total=raw[c]+raw[f]
                        fringe=fixed[b][1] if b in fixed else min(accepted[f],raw[f]+phase,total-peak)
                        if not 0<fringe<peak or peak>=total:continue
                        proposals[c]=peak;proposals[f]=min(accepted[f],fringe);cores.add(c)
                        pairs.append(dict(core=c,fringe=f,peak=peak,value=proposals[f],anchor=b in fixed,native_total=total))
                    if any(accepted[i]!=v for i,v in proposals.items()):
                        runs.append(dict(axis=axis,side=side,pairs=pairs,cores=cores,proposals=proposals,anchors=anchors,rows=rows,start=start,end=end))
    # Crossing candidates are ambiguous (for example, a two-by-two punctuation dot).
    memberships=defaultdict(set)
    for run in runs:
        for i in run['proposals']:memberships[i].add(run['axis'])
    runs=[run for run in runs if all(len(memberships[i])==1 for i in run['proposals'])]
    competing=defaultdict(set)
    for run in runs:
        for i,v in run['proposals'].items():competing[i].add(v)
    runs=[run for run in runs if all(len(competing[i])==1 for i in run['proposals'])]
    proposals=defaultdict(list);cores=set();votes=defaultdict(list)
    for run in runs:
        for i,v in run['proposals'].items():proposals[i].append(v)
        cores.update(run['cores'])
        for b,peak,_ in run['anchors']:
            c=run['rows'][b]['core'];x,y=c%width,c//width
            across,along=(x,y) if run['axis']=='v' else (y,x)
            votes[(run['axis'],across,run['side'])].append((along,peak,c))
    result=bytearray(accepted)
    for i,values in proposals.items():
        if len(set(values))==1:result[i]=values[0]
    # A join can interrupt the donor channel without moving the winning edge.
    anchored_cores={c for group in votes.values() for _,_,c in group}
    for (axis,a,side),anchors in votes.items():
        if len(anchors)<2:continue
        for start,_,_ in anchors:
            for end,_,_ in anchors:
                if end-start<2:continue
                native=[];indices=[]
                for b in range(start,end+1):
                    x,y=at(axis,a,b);ox,oy=at(axis,a+side,b)
                    i=y*width+x
                    if raw[i]==0 or value(ox,oy)>32:break
                    native.append(raw[i]);indices.append(i)
                else:
                    if max(native)-min(native)<=16:
                        peak=floor(median(p for b,p,_ in anchors if start<=b<=end)+.5)
                        for i in indices:
                            if i not in anchored_cores:result[i]=max(result[i],peak);cores.add(i)
    steps=[];step_proposals=defaultdict(list)
    frozen=bytes(result)
    for axis in ('v','h'):
        across,along=(width,height) if axis=='v' else (height,width)
        for a in range(across-1):
            for b in range(1,along-1):
                x,y=at(axis,a,b);xx,yy=at(axis,a+1,b);pair=(y*width+x,yy*width+xx)
                if not all(0<raw[i]<230 and frozen[i]>=230 for i in pair):continue
                if not 192<=sum(raw[i] for i in pair)<=384:continue
                ox,oy=at(axis,a-1,b);ex,ey=at(axis,a+2,b)
                if max(value(ox,oy),value(ex,ey))>32:continue
                supports=[]
                for bb in (b-1,b+1):
                    supports.append(any(value(*at(axis,aa,bb))>=230 for aa in range(a-1,a+3)))
                if not all(supports):continue
                eligible=[]
                for i in pair:
                    aa=i%width if axis=='v' else i//width
                    if all(any(value(*at(axis,j,bb))>=230 for j in range(aa-1,aa+2)) for bb in (b-1,b+1)):
                        eligible.append(i)
                if not eligible:continue
                c=max(eligible,key=lambda i:(raw[i],frozen[i],i));f=next(i for i in pair if i!=c)
                if f in cores:continue
                peak=max(240,frozen[c]);fringe=sum(raw[i] for i in pair)-peak
                if not 0<fringe<frozen[f]:continue
                step_proposals[c].append(peak);step_proposals[f].append(fringe)
                steps.append(dict(core=c,fringe=f,peak=peak,value=fringe))
    steps=[p for p in steps if len(set(step_proposals[p['core']]))==1 and len(set(step_proposals[p['fringe']]))==1]
    for p in steps:result[p['core']]=p['peak'];result[p['fringe']]=p['value']
    cores.update(p['core'] for p in steps)
    profiles=bytes(result);corners=bytearray(profiles);corner_indices=[]
    directions=((1,0),(0,1),(-1,0),(0,-1))
    for i,original in enumerate(raw):
        if not 0<original<230 or i in cores or profiles[i]<=original:continue
        x,y=i%width,i//width
        for d in range(4):
            a,b=directions[d],directions[(d+1)%4]
            if min(value(x+a[0],y+a[1]),value(x+b[0],y+b[1]))>=230 and max(value(x-a[0],y-a[1]),value(x-b[0],y-b[1]))<=32:
                corners[i]=original;corner_indices.append(i);break
    outputs=dict(profiles=profiles,corners=bytes(corners))
    for data in outputs.values():
        assert len(data)==len(raw)
        assert all((a>0)==(b>0) for a,b in zip(raw,data,strict=True))
        assert all(data[i]>=accepted[i] for i,v in enumerate(raw) if v>=230)
        assert all(data[i]>=accepted[i] for i in cores)
    return outputs,dict(runs=[dict(axis=r['axis'],side=r['side'],pairs=r['pairs']) for r in runs],steps=steps,corners=corner_indices)
