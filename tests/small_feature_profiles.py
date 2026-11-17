"""Compact-component intensity on a frozen accepted mask."""
from bridge_coverage_test import components


def compact(fitted, width, target):
    height=len(fitted)//width if width else 0
    peaks=bytearray(fitted);proportional=bytearray(fitted);audit=[]
    for group in components({i for i,v in enumerate(fitted) if v},width,height):
        xs=[i%width for i in group];ys=[i//width for i in group]
        box=[min(xs),min(ys),max(xs)+1,max(ys)+1]
        peak=max(fitted[i] for i in group)
        eligible=box[2]-box[0]<=3 and box[3]-box[1]<=3 and peak<target
        selected=sorted(i for i in group if fitted[i]==peak) if eligible else []
        audit.append(dict(pixels=sorted(group),box=box,peak=peak,eligible=eligible,peaks=selected))
        if not eligible:continue
        for i in selected:peaks[i]=target
        for i in group:
            proportional[i]=max(fitted[i],(fitted[i]*target+peak//2)//peak)
    return bytes(peaks),bytes(proportional),dict(components=audit)
