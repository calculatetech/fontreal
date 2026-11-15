"""Experimental minimum contrast for sustained native subpixel strokes."""
from collections import defaultdict
from math import hypot
from statistics import median


def normalize(raw, preferred, width):
    assert len(raw) == len(preferred) and (not raw or width > 0 and len(raw) % width == 0)
    modes = {name: bytearray(preferred) for name in ('core226', 'core240')}
    detail = dict(principal_width=0, lanes=[], conflicts=0)
    if not raw:
        return {k: bytes(v) for k, v in modes.items()}, detail
    height = len(raw) // width
    axes = [(width, height, lambda c, t: t * width + c),
            (height, width, lambda c, t: c * width + t)]
    widths = []
    for across, along, index in axes:
        lines = []
        for t in range(along):
            runs = []; c = 0
            while c < across:
                if not raw[index(c, t)]:
                    c += 1; continue
                start = c
                while c < across and raw[index(c, t)]: c += 1
                area = sum(raw[index(x, t)] for x in range(start, c))
                center = sum(x * raw[index(x, t)] for x in range(start, c)) / area
                runs.append((start, c, area, center))
            lines.append(runs)
        for t in range(along - 2):
            for a in lines[t]:
                for b in lines[t + 1]:
                    if max(abs(a[0]-b[0]), abs(a[1]-b[1])) > 1: continue
                    for c in lines[t + 2]:
                        if max(abs(b[0]-c[0]), abs(b[1]-c[1])) > 1: continue
                        areas = (a[2], b[2], c[2])
                        if max(areas) - min(areas) <= 16:
                            widths.append(median(areas) / hypot(1, (c[3]-a[3])/2))
    detail['principal_width'] = max(widths, default=0)
    # A wider sustained stroke makes thin channels intentional contrast controls.
    if not widths or max(widths) > 255:
        return {k: bytes(v) for k, v in modes.items()}, detail
    lanes = []
    for axis, (across, along, index) in enumerate(axes):
        for c in range(across):
            for direction in (-1, 1):
                donor = c + direction
                if not 0 <= donor < across: continue
                segments = []; last_end = -1
                for start in range(along):
                    segment = []; weak = []
                    for t in range(start, along):
                        i = index(c, t); v = raw[i]; outside = c - direction
                        valid = v and (v >= 230 or not 0 <= outside < across or raw[index(outside, t)] <= 32)
                        if not valid or v < 230 and weak and max(*weak,v)-min(*weak,v) > 16: break
                        segment.append(t)
                        if v < 230: weak.append(v)
                    if segment and segment[-1] > last_end:
                        segments.append(segment); last_end = segment[-1]
                for segment in segments:
                    if len(segment) < 5 or sum(raw[index(c,t)] < 230 for t in segment) < 3: continue
                    anchors = []
                    for t in segment:
                        i, j = index(c,t), index(donor,t); beyond = donor + direction
                        if (0 < raw[i] < 230 and raw[j] > 0 and 192 <= raw[i]+raw[j] < 255
                                and (not 0 <= beyond < across or raw[index(beyond,t)] == 0)):
                            anchors.append((i,j))
                    if not anchors: continue
                    vote = sum(raw[i]-raw[j] for i,j in anchors)
                    if not vote: vote = sum(preferred[i]-preferred[j] for i,j in anchors)
                    if vote < 0 or vote == 0 and direction > 0: continue
                    pairs = []
                    for t in segment:
                        i, j = index(c,t), index(donor,t)
                        if preferred[i] >= 230 or not raw[j]: continue
                        pairs.append(dict(core=i, fringe=j, native_total=raw[i]+raw[j]))
                    if pairs:
                        lanes.append(dict(axis=axis, channel=c, direction=direction,
                                          start=segment[0], end=segment[-1], anchors=anchors, pairs=pairs))
    roles = defaultdict(list)
    for number, lane in enumerate(lanes):
        for pair in lane['pairs']:
            roles[pair['core']].append((number,'core',pair['fringe']))
            if preferred[pair['fringe']] < 230:
                roles[pair['fringe']].append((number,'fringe',pair['core']))
    rejected = set()
    for entries in roles.values():
        if len({(role,other) for _,role,other in entries}) > 1:
            rejected.update(number for number,_,_ in entries)
    detail['conflicts'] = len(rejected)
    for number, lane in enumerate(lanes):
        if number in rejected: continue
        detail['lanes'].append(lane)
        for name, floor in (('core226',226),('core240',240)):
            for pair in lane['pairs']:
                i, j, total = pair['core'], pair['fringe'], pair['native_total']
                core = max(floor, preferred[i]); modes[name][i] = core
                if preferred[j] < 230 and total <= 384:
                    modes[name][j] = max(255,total) - core
    for output in modes.values():
        assert all(bool(a) == bool(b) and (p < 230 or p == b)
                   for a,p,b in zip(raw,preferred,output,strict=True))
    return {k: bytes(v) for k,v in modes.items()}, detail
