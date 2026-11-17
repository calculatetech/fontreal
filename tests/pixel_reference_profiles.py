"""Same-outline coverage references and frozen positive per-pixel overlays."""
PHASES = tuple((dx, dy) for dy in range(-2, 3) for dx in range(-2, 3))


def snapshot(glyph):
    return dict(outline=[[*xy, tag] for xy, tag in zip(glyph['outline'], glyph['tags'])],
                contours=list(glyph['contours']))


def raster(oracle, outline, scale=1, shift=(0, 0)):
    source = dict(outline=[[x*scale, y*scale, tag] for x, y, tag in outline['outline']],
                  contours=outline['contours'])
    result = oracle.raster(source, shift)
    return dict(left=result['left'], top=-result['top'], width=result['width'],
                height=result['height'], pixels=list(bytes.fromhex(result['mask'])))


def place(source, frame):
    pixels = [0] * (frame['width']*frame['height'])
    for y in range(source['height']):
        for x in range(source['width']):
            xx, yy = x+source['left']-frame['left'], y+source['top']-frame['top']
            value = source['pixels'][y*source['width']+x]
            if 0 <= xx < frame['width'] and 0 <= yy < frame['height']:
                pixels[yy*frame['width']+xx] = value
            elif value:
                raise ValueError('registered outline exceeds its declared frame')
    return {**frame, 'pixels': pixels}


def padded(raw, values=None):
    source = raw if values is None else {**raw, 'pixels': list(values)}
    return place(source, dict(left=raw['left']-2, top=raw['top']-2,
                             width=raw['width']+4, height=raw['height']+4))


def high_source(oracle, outline, raw):
    frame = dict(left=(raw['left']-3)*4, top=(raw['top']-3)*4,
                 width=(raw['width']+6)*4, height=(raw['height']+6)*4)
    return place(raster(oracle, outline, 4), frame)


def neighbors(index, width, height):
    x, y = index % width, index // width
    return [yy*width+xx for yy in range(max(0, y-1), min(height, y+2))
            for xx in range(max(0, x-1), min(width, x+2)) if (xx, yy) != (x, y)]


def components(values, width):
    unseen = {i for i, value in enumerate(values) if value}
    result = []
    while unseen:
        first = min(unseen); unseen.remove(first)
        todo = [first]; component = []
        while todo:
            index = todo.pop(); component.append(index)
            for other in neighbors(index, width, len(values)//width):
                if other in unseen:
                    unseen.remove(other); todo.append(other)
        result.append(sorted(component))
    return result


def runs(values, width, index):
    height = len(values)//width; x, y = index % width, index // width
    left = right = x; top = bottom = y
    while left and values[y*width+left-1]: left -= 1
    while right+1 < width and values[y*width+right+1]: right += 1
    while top and values[(top-1)*width+x]: top -= 1
    while bottom+1 < height and values[(bottom+1)*width+x]: bottom += 1
    horizontal, vertical = right-left+1, bottom-top+1
    axis = 'x' if horizontal < vertical else 'y' if vertical < horizontal else 'xy'
    return horizontal, vertical, axis


def phase_key(phase):
    dx, dy = phase
    return dx*dx+dy*dy, dy, dx


def references(high, d, width, phases=PHASES):
    """Integral 4x4 footprints in the two-pixel common native frame."""
    height = len(d)//width; hw, hh = high['width'], high['height']
    stride = hw+1; integral = [0]*(stride*(hh+1))
    for y in range(hh):
        running = 0
        for x in range(hw):
            running += high['pixels'][y*hw+x]
            integral[(y+1)*stride+x+1] = integral[y*stride+x+1]+running
    sums = {}
    for dx, dy in phases:
        values = []
        for y in range(height):
            top = 4-dy+4*y; bottom = top+4
            for x in range(width):
                left = 4-dx+4*x; right = left+4
                values.append(integral[bottom*stride+right]-integral[top*stride+right]
                              -integral[bottom*stride+left]+integral[top*stride+left])
        sums[dx, dy] = values
    c = [0]*len(d); e = [0]*len(d); decisions = []; axes = {}
    for component in components(d, width):
        scores = {phase: sum(sums[phase][i]**2 for i in component) for phase in phases}
        best = min(phases, key=lambda phase: (-scores[phase], *phase_key(phase)))
        for index in component: c[index] = (sums[best][index]+8)//16
        decisions.append(dict(indices=component, phase=list(best),
                              scores=[[*phase, scores[phase]] for phase in sorted(phases)]))
    for index, value in enumerate(d):
        if not value: continue
        horizontal, vertical, axis = runs(d, width, index)
        allowed = [phase for phase in phases if (axis != 'x' or phase[1] == 0)
                   and (axis != 'y' or phase[0] == 0)]
        best = min(allowed, key=lambda phase: (-sums[phase][index], *phase_key(phase)))
        e[index] = (sums[best][index]+8)//16
        axes[str(index)] = dict(axis=axis, horizontal=horizontal, vertical=vertical,
                                phase=list(best))
    return dict(R=[(value+8)//16 for value in sums[0, 0]], C=c, E=e), dict(
        components=decisions, axes=axes,
        phase_sums=[dict(phase=list(phase), values=sums[phase]) for phase in sorted(phases)],
        source_window='4-dx,4-dy', scale=4, source_padding=3, native_padding=2)


def overlays(d, width, reference):
    height = len(d)//width
    def at(x, y):
        return d[y*width+x] if 0 <= x < width and 0 <= y < height else 0
    primary = []
    for index, value in enumerate(d):
        if value < 128: continue
        _, _, axis = runs(d, width, index); x, y = index % width, index // width
        horizontal = value >= max(at(x-1, y), at(x+1, y)) and value > min(at(x-1, y), at(x+1, y))
        vertical = value >= max(at(x, y-1), at(x, y+1)) and value > min(at(x, y-1), at(x, y+1))
        if (axis == 'x' and horizontal) or (axis == 'y' and vertical) or (axis == 'xy' and horizontal and vertical):
            primary.append(index)
    o = list(d); l = list(d)
    for index in primary:
        o[index] = max(d[index], reference['C'][index])
        l[index] = max(d[index], reference['E'][index])
    s = list(l); selected = set(primary); proposals = []
    for index in primary:
        if l[index] == d[index]: continue
        for other in neighbors(index, width, height):
            if other in selected or not 0 < d[other] < d[index] or reference['E'][other] <= d[other]: continue
            value = min(reference['E'][other], (2*d[other]*l[index]+d[index])//(2*d[index]))
            s[other] = max(s[other], value)
            proposals.append([index, other, value])
    masks = dict(O=o, L=l, S=s)
    return masks, dict(primary=primary, edges=proposals,
                       overlays={key: [v-u for u, v in zip(d, values)] for key, values in masks.items()})
